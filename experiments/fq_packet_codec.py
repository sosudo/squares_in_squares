"""Versioned self-contained lossless packet codec for FUTURE jobs only.

Two ZIP_STORED members hold canonical JSON and a deduplicated byte pool. No
NPY/object pickle is written or read. Admission still requires external packet
SHA binding and the unchanged geometry gates; this codec certifies no poses.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import io
import json
import math
import re
import struct
import zipfile
import numpy as np

BLOCK_BYTES=1536
FORMAT='fq-self-contained-blocks'
VERSION=1
NAME=re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,127}\Z')
HEX=re.compile(r'[0-9a-f]{64}\Z')


class CodecError(ValueError):pass


@dataclass(frozen=True)
class Limits:
    packet_bytes:int=128*1024**2
    decoded_bytes:int=128*1024**2
    payload_bytes:int=128*1024**2
    manifest_bytes:int=4*1024**2
    arrays:int=128
    indices:int=262144
    pool_blocks:int=262144
    dimensions:int=8
    dimension:int=1000000
    elements:int=128*1024**2
    dtype_itemsize:int=65536
    dtype_depth:int=8
    dtype_fields:int=256


DEFAULT_LIMITS=Limits()


def _limits(value):
    if not isinstance(value,Limits) or any(type(n)is not int or n<=0 for n in vars(value).values()):
        raise CodecError('invalid_limits')
    return value


def _sha(data):return hashlib.sha256(data).hexdigest()
def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def _keys(value,keys,label):
    if type(value)is not dict or set(value)!=set(keys):raise CodecError('invalid_'+label+'_keys')
def _integer(value,minimum,maximum,label):
    if type(value)is not int or not minimum<=value<=maximum:raise CodecError('invalid_'+label)
    return value
def _hash(value,label):
    if type(value)is not str or not HEX.fullmatch(value):raise CodecError('invalid_'+label)
    return value


def _dtype_schema(dtype,limits,depth=0):
    dtype=np.dtype(dtype)
    if depth>limits.dtype_depth or dtype.hasobject or dtype.metadata is not None:
        raise CodecError('object_metadata_or_deep_dtype_forbidden')
    if not 0<dtype.itemsize<=limits.dtype_itemsize:raise CodecError('dtype_itemsize_limit')
    if dtype.fields is not None:
        if len(dtype.names)>limits.dtype_fields:raise CodecError('dtype_field_limit')
        fields=[]
        for name in dtype.names:
            field=dtype.fields[name];title=field[2] if len(field)==3 else None
            if (type(name)is not str or not name or len(name)>128 or '\x00'in name
                    or (title is not None and (type(title)is not str or len(title)>128))):
                raise CodecError('unsupported_dtype_field_name_or_title')
            fields.append(dict(name=name,offset=int(field[1]),dtype=_dtype_schema(field[0],limits,depth+1),title=title))
        return dict(kind='struct',itemsize=dtype.itemsize,aligned=bool(dtype.isalignedstruct),fields=fields)
    if dtype.subdtype is not None:
        base,shape=dtype.subdtype
        return dict(kind='subarray',base=_dtype_schema(base,limits,depth+1),shape=list(shape))
    if dtype.kind not in 'biufcmMSUV':raise CodecError('unsupported_primitive_dtype')
    return dict(kind='plain',str=dtype.str)


def _shape(shape,limits):
    if type(shape)is not list or len(shape)>limits.dimensions:raise CodecError('invalid_shape')
    dimensions=tuple(_integer(x,0,limits.dimension,'dimension')for x in shape)
    # Bound even empty arrays with enormous nonzero extents/strides.
    if math.prod(max(1,x)for x in dimensions)>limits.elements:raise CodecError('shape_extent_limit')
    return dimensions


def _dtype_from(schema,limits,depth=0):
    if type(schema)is not dict or depth>limits.dtype_depth:raise CodecError('invalid_dtype_schema')
    kind=schema.get('kind')
    try:
        if kind=='plain':
            _keys(schema,('kind','str'),'plain_dtype')
            if type(schema['str'])is not str or len(schema['str'])>128:raise CodecError('invalid_dtype_string')
            dtype=np.dtype(schema['str'])
            if dtype.fields is not None or dtype.subdtype is not None or dtype.str!=schema['str']:
                raise CodecError('noncanonical_primitive_dtype')
        elif kind=='subarray':
            _keys(schema,('kind','base','shape'),'subarray_dtype')
            shape=_shape(schema['shape'],limits)
            if not shape or 0 in shape:raise CodecError('invalid_subarray_shape')
            base=_dtype_from(schema['base'],limits,depth+1)
            if base.itemsize*math.prod(shape)>limits.dtype_itemsize:raise CodecError('dtype_itemsize_limit')
            dtype=np.dtype((base,shape))
        elif kind=='struct':
            _keys(schema,('kind','itemsize','aligned','fields'),'struct_dtype')
            itemsize=_integer(schema['itemsize'],1,limits.dtype_itemsize,'dtype_itemsize')
            if type(schema['aligned'])is not bool or type(schema['fields'])is not list or len(schema['fields'])>limits.dtype_fields:
                raise CodecError('invalid_struct_dtype')
            names=[];formats=[];offsets=[];titles=[]
            for field in schema['fields']:
                _keys(field,('name','offset','dtype','title'),'struct_field')
                name=field['name'];title=field['title']
                if (type(name)is not str or not name or len(name)>128 or '\x00'in name or name in names
                        or (title is not None and (type(title)is not str or len(title)>128))):
                    raise CodecError('invalid_struct_field_name')
                value=_dtype_from(field['dtype'],limits,depth+1)
                offset=_integer(field['offset'],0,itemsize,'field_offset')
                if offset+value.itemsize>itemsize:raise CodecError('struct_field_outside_item')
                names.append(name);formats.append(value);offsets.append(offset);titles.append(title)
            dtype=np.dtype(dict(names=names,formats=formats,offsets=offsets,titles=titles,itemsize=itemsize),align=schema['aligned'])
        else:raise CodecError('unknown_dtype_kind')
    except (TypeError,ValueError,OverflowError)as error:
        if isinstance(error,CodecError):raise
        raise CodecError('invalid_dtype_constructor')from error
    if _dtype_schema(dtype,limits,depth)!=schema:raise CodecError('noncanonical_or_unsafe_dtype')
    return dtype


def _piece_lengths(shape,itemsize):
    count=math.prod(shape);total=count*itemsize
    if total==0:return
    if len(shape)==3:
        width=shape[1]*shape[2]*itemsize
        for _ in range(shape[0]):
            for start in range(0,width,BLOCK_BYTES):yield min(BLOCK_BYTES,width-start)
    else:
        for start in range(0,total,BLOCK_BYTES):yield min(BLOCK_BYTES,total-start)


def _piece_count(shape,itemsize):
    total=math.prod(shape)*itemsize
    if total==0:return 0
    if len(shape)==3:
        width=shape[1]*shape[2]*itemsize
        return shape[0]*((width+BLOCK_BYTES-1)//BLOCK_BYTES)
    return (total+BLOCK_BYTES-1)//BLOCK_BYTES


def _archive(document,payload):
    """Internal writer also used by adversarial tests to construct valid ZIPs."""
    body=dict(document);body['manifest_sha256']=_sha(_canonical(document))
    manifest=_canonical(body);stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,data in [('manifest.json',manifest),('payload.bin',payload)]:
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED
            archive.writestr(info,data)
    return stream.getvalue(),len(manifest)


def encode(arrays,*,limits=DEFAULT_LIMITS):
    """Encode one independent packet; preserve key order, scalar shape and bytes."""
    limits=_limits(limits)
    if type(arrays)is not dict or not 0<len(arrays)<=limits.arrays:raise CodecError('array_count_or_mapping')
    specifications=[];total=0;expected_indices=0
    for name,value in arrays.items():
        if type(name)is not str or not NAME.fullmatch(name):raise CodecError('invalid_array_name')
        if not isinstance(value,np.ndarray):raise CodecError('ndarray_required')
        shape=_shape(list(value.shape),limits);schema=_dtype_schema(value.dtype,limits)
        _dtype_from(schema,limits)
        size=math.prod(shape)*value.dtype.itemsize;total+=size
        if total>limits.decoded_bytes:raise CodecError('decoded_byte_limit')
        expected_indices+=_piece_count(shape,value.dtype.itemsize)
        if expected_indices>limits.indices:raise CodecError('index_count_limit')
        specifications.append((name,value,shape,schema))
    pool=[];ends=[];lookup={};records=[];payload_bytes=0;indices_total=0
    for name,value,shape,schema in specifications:
        # Direct C-order bytes preserve0d shape and structured padding. Never
        # use ascontiguousarray/copy, which can alter either of those details.
        raw=value.tobytes(order='C');indices=[];position=0
        for size in _piece_lengths(shape,value.dtype.itemsize):
            part=raw[position:position+size];position+=size
            index=lookup.get(part)
            if index is None:
                if len(pool)>=limits.pool_blocks:raise CodecError('pool_block_limit')
                index=len(pool);lookup[part]=index;pool.append(part);payload_bytes+=len(part);ends.append(payload_bytes)
                if payload_bytes>limits.payload_bytes:raise CodecError('payload_byte_limit')
            indices.append(index);indices_total+=1
            if indices_total>limits.indices:raise CodecError('index_count_limit')
        if position!=len(raw):raise CodecError('internal_piece_length_mismatch')
        records.append(dict(name=name,dtype=schema,shape=list(shape),bytes=len(raw),sha256=_sha(raw),indices=indices))
    payload=b''.join(pool)
    document=dict(format=FORMAT,version=VERSION,block_bytes=BLOCK_BYTES,decoded_bytes=total,
                  payload_bytes=len(payload),payload_sha256=_sha(payload),pool_ends=ends,arrays=records)
    raw,manifest_bytes=_archive(document,payload)
    if manifest_bytes>limits.manifest_bytes or len(raw)>limits.packet_bytes:raise CodecError('encoded_packet_or_manifest_limit')
    return raw


def _json(data):
    def unique(items):
        answer={}
        for key,value in items:
            if key in answer:raise CodecError('duplicate_json_key')
            answer[key]=value
        return answer
    def constant(value):raise CodecError('nonfinite_json_constant')
    try:return json.loads(data,object_pairs_hook=unique,parse_constant=constant)
    except (UnicodeError,json.JSONDecodeError,RecursionError)as error:raise CodecError('invalid_manifest_json')from error


def _zip_envelope(raw):
    """Bound directory parsing BEFORE constructing Python's ZipFile.

    Our two fixed ASCII filenames need exactly116 central-directory bytes;
    ZIP64, split disks, extra members and comments are never emitted.
    """
    if not raw.startswith(b'PK\x03\x04')or len(raw)<22 or raw[-22:-18]!=b'PK\x05\x06':
        raise CodecError('invalid_or_truncated_zip_envelope')
    _,disk,cd_disk,on_disk,total,cd_bytes,cd_offset,comment=struct.unpack('<4s4H2IH',raw[-22:])
    if (disk or cd_disk or on_disk!=2 or total!=2 or comment or cd_bytes!=116
            or cd_offset+cd_bytes!=len(raw)-22 or cd_offset<30
            or raw[-42:-38]==b'PK\x06\x07'):
        raise CodecError('noncanonical_zip_directory_envelope')


def decode(raw,*,expected_sha256=None,limits=DEFAULT_LIMITS):
    """Validate every bound/hash before reconstructing independent owned arrays.

    Supply the trusted raw-index SHA for authentication. Internal hashes catch
    accidental corruption; they are not a signature against a rewritten packet.
    """
    limits=_limits(limits)
    if type(raw)is not bytes or len(raw)>limits.packet_bytes:raise CodecError('packet_type_or_size_limit')
    if expected_sha256 is not None:
        _hash(expected_sha256,'external_sha256')
        if _sha(raw)!=expected_sha256:raise CodecError('external_packet_hash_mismatch')
    try:
        _zip_envelope(raw)
        with zipfile.ZipFile(io.BytesIO(raw))as archive:
            infos=archive.infolist()
            if len(infos)!=2 or {i.filename for i in infos}!={'manifest.json','payload.bin'}:
                raise CodecError('unexpected_or_duplicate_zip_members')
            if any(i.compress_type!=zipfile.ZIP_STORED or i.flag_bits or i.extra or i.comment for i in infos):
                raise CodecError('compressed_or_encrypted_zip_forbidden')
            info={i.filename:i for i in infos}
            if info['manifest.json'].file_size>limits.manifest_bytes or info['payload.bin'].file_size>limits.payload_bytes:
                raise CodecError('zip_member_size_limit')
            metadata=archive.read('manifest.json');document=_json(metadata)
            _keys(document,('format','version','block_bytes','decoded_bytes','payload_bytes','payload_sha256','pool_ends','arrays','manifest_sha256'),'manifest')
            signature=_hash(document.pop('manifest_sha256'),'manifest_sha256')
            if _sha(_canonical(document))!=signature or _canonical(dict(document,manifest_sha256=signature))!=metadata:
                raise CodecError('manifest_hash_or_canonical_form_mismatch')
            if document['format']!=FORMAT or type(document['version'])is not int or document['version']!=VERSION:
                raise CodecError('unsupported_format_version')
            if type(document['block_bytes'])is not int or document['block_bytes']!=BLOCK_BYTES:raise CodecError('invalid_block_size')
            declared=_integer(document['decoded_bytes'],0,limits.decoded_bytes,'decoded_bytes')
            size=_integer(document['payload_bytes'],0,limits.payload_bytes,'payload_bytes')
            if size!=info['payload.bin'].file_size:raise CodecError('payload_size_mismatch')
            _hash(document['payload_sha256'],'payload_sha256')
            ends=document['pool_ends']
            if type(ends)is not list or len(ends)>limits.pool_blocks:raise CodecError('pool_block_limit')
            previous=0
            for end in ends:
                _integer(end,previous+1,min(size,previous+BLOCK_BYTES),'pool_end');previous=end
            if previous!=size:raise CodecError('pool_ends_do_not_cover_payload')
            records=document['arrays']
            if type(records)is not list or not 0<len(records)<=limits.arrays:raise CodecError('array_count_limit')
            specifications=[];seen=set();total=0;indices_total=0
            for record in records:
                _keys(record,('name','dtype','shape','bytes','sha256','indices'),'array')
                name=record['name']
                if type(name)is not str or not NAME.fullmatch(name)or name in seen:raise CodecError('invalid_or_duplicate_array_name')
                seen.add(name);dtype=_dtype_from(record['dtype'],limits);shape=_shape(record['shape'],limits)
                if dtype.subdtype is not None:raise CodecError('top_level_subarray_dtype_forbidden')
                nbytes=math.prod(shape)*dtype.itemsize;total+=nbytes
                if total>limits.decoded_bytes or total>declared:raise CodecError('decoded_byte_limit_or_mismatch')
                if _integer(record['bytes'],0,limits.decoded_bytes,'array_bytes')!=nbytes:raise CodecError('array_shape_byte_mismatch')
                _hash(record['sha256'],'array_sha256');indices=record['indices']
                if type(indices)is not list:raise CodecError('invalid_indices')
                indices_total+=len(indices)
                if indices_total>limits.indices:raise CodecError('index_count_limit')
                expected=_piece_count(shape,dtype.itemsize)
                if expected>limits.indices or len(indices)!=expected:raise CodecError('index_shape_count_mismatch')
                for index,length in zip(indices,_piece_lengths(shape,dtype.itemsize)):
                    _integer(index,0,len(ends)-1,'block_index')
                    if ends[index]-(ends[index-1]if index else 0)!=length:raise CodecError('block_length_mismatch')
                specifications.append((record,dtype,shape))
            if total!=declared:raise CodecError('decoded_total_mismatch')
            payload=archive.read('payload.bin')
            if _sha(payload)!=document['payload_sha256']:raise CodecError('payload_hash_mismatch')
    except (zipfile.BadZipFile,RuntimeError,EOFError,OverflowError,RecursionError)as error:
        if isinstance(error,CodecError):raise
        raise CodecError('invalid_zip_or_manifest')from error
    result={}
    for record,dtype,shape in specifications:
        data=b''.join(payload[(ends[i-1]if i else 0):ends[i]]for i in record['indices'])
        if _sha(data)!=record['sha256']:raise CodecError('array_hash_mismatch:'+record['name'])
        # ndarray over an owned bytearray preserves padding/NaN payloads and
        # endian bytes; structured-array copy() can lose padding bytes.
        value=np.ndarray(shape,dtype=dtype,buffer=bytearray(data),order='C')
        if value.shape!=shape or value.dtype!=dtype:raise CodecError('reconstructed_array_schema_mismatch')
        result[record['name']]=value
    return result
