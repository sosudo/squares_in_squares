"""Exact copy/literal byte patches. Standard library only; no numerical edits."""
from __future__ import annotations
import argparse
import hashlib
import json
import lzma
from pathlib import Path

MAGIC=b'FQBYTES1\n'
MAX_CSV=64*1024**2
MAX_PATCH=96*1024**2
MAX_OPERATIONS=3000000


def sha(data):return hashlib.sha256(data).hexdigest()
def require(condition,label):
    if not condition:raise ValueError(label)


def _varint(number):
    require(type(number)is int and 0<=number<2**63,'invalid_integer')
    output=bytearray()
    while number>=128:output.append((number&127)|128);number>>=7
    output.append(number);return bytes(output)


def _read_integer(data,position):
    value=0
    for count in range(9):
        require(position<len(data),'truncated_integer')
        byte=data[position];position+=1;value|=(byte&127)<<(7*count)
        if byte<128:
            require(count==0 or byte!=0,'noncanonical_integer')
            return value,position
    raise ValueError('oversized_integer')


def make_patch(parent,target):
    """Deterministic aligned-line byte differences; never parse coordinates."""
    require(type(parent)is bytes and type(target)is bytes and max(len(parent),len(target))<=MAX_CSV,'csv_size')
    first=parent.splitlines(keepends=True);second=target.splitlines(keepends=True)
    require(len(first)==len(second),'line_count_differs')
    output=bytearray(MAGIC);pending=None;operations=0
    def flush():
        nonlocal pending,operations
        if pending is None:return
        kind,value,length=pending
        if kind=='C':output.extend(b'C'+_varint(value)+_varint(length))
        else:output.extend(b'L'+_varint(len(value))+value)
        operations+=1;pending=None
    def copy(start,length):
        nonlocal pending
        if not length:return
        if pending is not None and pending[0]=='C' and pending[1]+pending[2]==start:
            pending=('C',pending[1],pending[2]+length)
        else:flush();pending=('C',start,length)
    def literal(data):
        nonlocal pending
        if not data:return
        if pending is not None and pending[0]=='L':pending[1].extend(data)
        else:flush();pending=('L',bytearray(data),None)
    offset=0;changed=0
    for old,new in zip(first,second):
        if old==new:copy(offset,len(old))
        else:
            changed+=1
            # Separate exact line-ending bytes solely to find matching byte
            # runs. Restoration performs only literal insertion and copying.
            old_end=2 if old.endswith(b'\r\n')else 1 if old.endswith(b'\n')else 0
            new_end=2 if new.endswith(b'\r\n')else 1 if new.endswith(b'\n')else 0
            a=old[:-old_end]if old_end else old;b=new[:-new_end]if new_end else new
            prefix=0;bound=min(len(a),len(b))
            while prefix<bound and a[prefix]==b[prefix]:prefix+=1
            suffix=0
            while suffix<bound-prefix and a[-suffix-1]==b[-suffix-1]:suffix+=1
            copy(offset,prefix)
            literal(b[prefix:len(b)-suffix if suffix else len(b)])
            if suffix:copy(offset+len(a)-suffix,suffix)
            if old_end==new_end and old[len(a):]==new[len(b):]:copy(offset+len(a),old_end)
            else:literal(new[len(b):])
        offset+=len(old)
    flush();require(operations<=MAX_OPERATIONS and len(output)<=MAX_PATCH,'patch_resource_limit')
    raw=bytes(output);compressed=lzma.compress(raw,preset=6)
    record=dict(parent_sha256=sha(parent),parent_bytes=len(parent),target_sha256=sha(target),target_bytes=len(target),
        patch_sha256=sha(raw),patch_bytes=len(raw),compressed_sha256=sha(compressed),compressed_bytes=len(compressed),
        operations=operations,lines=len(first),changed_lines=changed,format='FQBYTES1_copy_literal')
    return compressed,record


def apply_patch(parent,compressed,record):
    require(type(parent)is bytes and len(parent)==record['parent_bytes'] and sha(parent)==record['parent_sha256'],'wrong_parent_bytes_or_hash')
    require(0<=record['target_bytes']<=MAX_CSV and 0<record['patch_bytes']<=MAX_PATCH,'declared_resource_limit')
    require(type(compressed)is bytes and len(compressed)==record['compressed_bytes'] and sha(compressed)==record['compressed_sha256'],'compressed_patch_hash')
    decoder=lzma.LZMADecompressor(memlimit=128*1024**2)
    raw=decoder.decompress(compressed,max_length=record['patch_bytes']+1)
    require(decoder.eof and not decoder.unused_data and len(raw)==record['patch_bytes'] and sha(raw)==record['patch_sha256'],'raw_patch_stream_or_hash')
    require(raw.startswith(MAGIC),'patch_magic')
    output=bytearray();position=len(MAGIC);operations=0
    while position<len(raw):
        kind=raw[position];position+=1;number,position=_read_integer(raw,position)
        if kind==ord('C'):
            length,position=_read_integer(raw,position)
            require(length>0 and number+length<=len(parent),'copy_bounds')
            require(len(output)+length<=record['target_bytes'],'target_length_limit')
            output.extend(parent[number:number+length])
        elif kind==ord('L'):
            require(number>0 and position+number<=len(raw),'literal_bounds')
            require(len(output)+number<=record['target_bytes'],'target_length_limit')
            output.extend(raw[position:position+number]);position+=number
        else:raise ValueError('unknown_operation')
        operations+=1;require(operations<=MAX_OPERATIONS,'operation_limit')
    require(operations==record['operations'],'operation_count')
    result=bytes(output)
    require(len(result)==record['target_bytes'] and sha(result)==record['target_sha256'],'target_bytes_or_hash')
    return result


def restore(checkpoint,parent_path,out):
    checkpoint=Path(checkpoint).resolve();manifest=json.loads((checkpoint/'manifest.json').read_bytes())
    require(manifest['kind']=='local_only_exact_byte_checkpoint' and manifest['no_remote_export'],'checkpoint_kind')
    parent_path=Path(parent_path);require(parent_path.stat().st_size<=MAX_CSV,'parent_size')
    parent=parent_path.read_bytes();results={}
    for label,record in manifest['targets'].items():
        patch=(checkpoint/record['patch_file']).resolve()
        require(patch.is_relative_to(checkpoint),'patch_path_escape')
        require(patch.stat().st_size==record['compressed_bytes'],'compressed_patch_size')
        data=apply_patch(parent,patch.read_bytes(),record)
        destination=Path(out)/record['output_file']
        require(destination.name==record['output_file'],'output_filename')
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():require(destination.read_bytes()==data,'existing_destination_differs')
        else:
            temporary=destination.with_suffix(destination.suffix+'.incoming')
            with temporary.open('xb')as stream:stream.write(data)
            temporary.replace(destination)
        results[label]=dict(path=str(destination),sha256=sha(data),bytes=len(data))
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(restore(Path(__file__).parent,args.parent,args.out),indent=2))
