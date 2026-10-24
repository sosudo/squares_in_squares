#!/usr/bin/env python3
"""Exact SAFE-CSV row patches over the verified private 8cd7 parent export.

This concrete fallback neither recomputes coordinates nor reapplies transport
scaling. It builds a private offline notebook; it never launches one.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import lzma
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRIC_SHA = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'
PARENT_REF = 'sos54352/squares-portfolio-8cd7c023ab18/1'
PARENT_SHA = '8cd7c023ab18b5875fcd5084e23415eda3181df1f4e70b5558bfe9eb039b0658'

COMPRESSED_MANIFEST_RUNTIME = r'''
import base64,hashlib,json,lzma

def _decode_embedded_manifest(payload,raw_size,raw_sha,compressed_sha):
    if type(raw_size)is not int or not 0<raw_size<4*1024*1024:
        raise ValueError('Invalid embedded manifest size')
    compressed=base64.b64decode(payload,validate=True)
    if hashlib.sha256(compressed).hexdigest()!=compressed_sha:
        raise ValueError('Compressed manifest SHA256 differs')
    decoder=lzma.LZMADecompressor(memlimit=64*1024*1024)
    raw=decoder.decompress(compressed,max_length=raw_size+1)
    if not decoder.eof or decoder.unused_data or len(raw)!=raw_size:
        raise ValueError('Embedded manifest stream or size differs')
    if hashlib.sha256(raw).hexdigest()!=raw_sha:
        raise ValueError('Exact manifest SHA256 differs')
    result=json.loads(raw)
    if not isinstance(result,dict):raise ValueError('Expected manifest object')
    return result
'''

RUNTIME = r'''
import base64,hashlib,json,lzma,re
from pathlib import Path

_HEADER=b'id,n,square_id,x,y,angle\r\n'
_NUMBER=re.compile(rb'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?')

def _sha(data):
    return hashlib.sha256(data).hexdigest()

def _require(condition,message):
    if not condition:raise ValueError(message)

def _fields(line,rid,n,sid):
    _require(isinstance(line,bytes) and line.endswith(b'\r\n'),'Expected an exact CRLF row')
    values=line[:-2].split(b',')
    _require(len(values)==6,'CSV schema differs')
    _require(values[:3]==[str(rid).encode(),str(n).encode(),str(sid).encode()],
             'CSV row id, puzzle count or square id differs')
    _require(all(_NUMBER.fullmatch(value) for value in values[3:]),'Nonfinite or malformed coordinate string')
    return values

def _validate_csv(raw):
    lines=raw.splitlines(keepends=True)
    _require(len(lines)==500501 and lines[0]==_HEADER,'Expected complete six-column SAFE-CSV')
    rid=0
    for n in range(1,1001):
        for sid in range(n):
            _fields(lines[rid+1],rid,n,sid);rid+=1
    _require(rid==500500,'Complete puzzle/row coverage required')
    return lines

def _line_digest(lines,changed,include_changed):
    result=hashlib.sha256()
    if not include_changed:result.update(lines[0])
    for rid,line in enumerate(lines[1:]):
        if (rid in changed)==include_changed:result.update(line)
    return result.hexdigest()

def _decode_patch(payload,manifest):
    try:compressed=base64.b64decode(payload,validate=True)
    except Exception as error:raise ValueError('Invalid patch encoding') from error
    _require(_sha(compressed)==manifest['patch_compressed_sha256'],'Compressed patch SHA256 differs')
    decoder=lzma.LZMADecompressor(memlimit=64*1024*1024)
    try:raw=decoder.decompress(compressed,max_length=manifest['patch_bytes']+1)
    except lzma.LZMAError as error:raise ValueError('Invalid compressed patch') from error
    _require(decoder.eof and not decoder.unused_data and len(raw)==manifest['patch_bytes'],
             'Patch length/stream differs')
    _require(_sha(raw)==manifest['patch_sha256'],'Exact patch SHA256 differs')
    patch=json.loads(raw)
    _require(isinstance(patch,dict) and set(patch)=={'rows'} and isinstance(patch['rows'],list),
             'Unexpected row-patch schema')
    return patch['rows']

def apply_safe_row_patch(parent,payload,manifest):
    _require(len(parent)==manifest['parent_csv_bytes'] and _sha(parent)==manifest['parent_csv_sha256'],
             'Parent SAFE-CSV SHA256 or length differs')
    original=_validate_csv(parent)
    rows=_decode_patch(payload,manifest)
    _require(len(rows)==manifest['changed_rows'],'Changed-row count differs')
    output=original.copy();changed=set();puzzles=set();previous=-1
    for record in rows:
        _require(isinstance(record,list) and len(record)==2,'Malformed row patch')
        rid,text=record
        _require(type(rid)is int and previous<rid<500500 and rid>=0,'Duplicate, unsorted or invalid row id')
        _require(isinstance(text,str),'Patch coordinates must remain strings')
        try:replacement=text.encode('ascii')
        except UnicodeEncodeError as error:raise ValueError('Non-ASCII CSV row') from error
        old=original[rid+1][:-2].split(b',');n,sid=int(old[1]),int(old[2])
        fields=_fields(replacement,rid,n,sid)
        _require(replacement!=original[rid+1],'Patch contains an unchanged row')
        output[rid+1]=replacement;changed.add(rid);puzzles.add(n);previous=rid
    _require(sorted(puzzles)==manifest['changed_puzzles'],'Changed-puzzle coverage differs')
    _require(_line_digest(original,changed,True)==manifest['changed_parent_rows_sha256'],
             'Changed parent-row bytes differ')
    _require(_line_digest(output,changed,True)==manifest['changed_target_rows_sha256'],
             'Changed coordinate strings differ')
    unchanged=_line_digest(original,changed,False)
    _require(unchanged==manifest['unchanged_rows_sha256'] and
             _line_digest(output,changed,False)==unchanged,'Unchanged CSV bytes were modified')
    data=b''.join(output)
    _require(len(data)==manifest['csv_bytes'] and _sha(data)==manifest['csv_sha256'],
             'Final exact SAFE-CSV SHA256 or length differs')
    return data

def reconstruct_safe_portfolio(destination,parent_path=None,mount_root='/kaggle/input'):
    manifest=INCREMENTAL_MANIFEST
    if parent_path is None:
        mount=Path(mount_root).resolve();matches=[]
        _require(mount.is_dir(),'Parent notebook output mount missing')
        for path in sorted(mount.rglob(manifest['parent_output_file'])):
            real=path.resolve()
            if real.is_relative_to(mount) and real.is_file() and real.stat().st_size==manifest['parent_csv_bytes']:
                if _sha(real.read_bytes())==manifest['parent_csv_sha256']:matches.append(real)
        _require(bool(matches),'No parent notebook CSV matches the exact content hash')
        parent_path=matches[0]
    data=apply_safe_row_patch(Path(parent_path).read_bytes(),INCREMENTAL_PATCH,manifest)
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        _require(destination.read_bytes()==data,'Existing destination differs from the exact target')
    else:
        temporary=destination.with_suffix(destination.suffix+'.incoming')
        temporary.write_bytes(data);temporary.replace(destination)
    _require(_sha(destination.read_bytes())==manifest['csv_sha256'],'Written CSV differs')
    return destination
'''

ENTRYPOINT = r'''
if __name__=='__main__':
    import os,signal,time
    started=time.monotonic()
    def expired(signum,frame):raise TimeoutError('Incremental SAFE-CSV export exceeded120s')
    signal.signal(signal.SIGALRM,expired);signal.alarm(120)
    root=Path(os.environ.get('INCREMENTAL_OUTPUT_ROOT','/kaggle/working' if Path('/kaggle/working').is_dir() else str(Path.cwd())))
    target=reconstruct_safe_portfolio(root/'submission.csv',os.environ.get('INCREMENTAL_PARENT_PATH'),
                                     os.environ.get('INCREMENTAL_INPUT_ROOT','/kaggle/input'))
    proof={'status':'complete','csv_sha256':_sha(target.read_bytes()),'rows':500500,'puzzles':1000,
           'parent_csv_sha256':INCREMENTAL_MANIFEST['parent_csv_sha256'],
           'patch_sha256':INCREMENTAL_MANIFEST['patch_sha256'],
           'changed_rows':INCREMENTAL_MANIFEST['changed_rows'],
           'changed_puzzles':INCREMENTAL_MANIFEST['changed_puzzles'],
           'unchanged_rows_sha256':INCREMENTAL_MANIFEST['unchanged_rows_sha256'],
           'official_score':INCREMENTAL_MANIFEST['official_score'],
           'transport_scaling_applied':False,'fresh_geometry_evaluations':0,
           'certificate_reuse':'Exact previously certified SAFE-CSV bytes; no coordinate reserialization.',
           'competition_submission_performed':False,'seconds':time.monotonic()-started}
    (root/'export_manifest.json').write_text(json.dumps(INCREMENTAL_MANIFEST,indent=2)+'\n')
    (root/'incremental_export_proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    signal.alarm(0);print(json.dumps(proof),flush=True)
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def runtime_namespace():
    namespace={}
    exec(compile(RUNTIME,'<exact-safe-row-patch>','exec'),namespace)
    return namespace


def notebook_metadata(slug):
    # Kaggle may derive the actual slug from title even when id is supplied.
    return dict(id=slug,title=slug.split('/')[-1].replace('-',' '),code_file='export.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=False,enable_tpu=False,enable_internet=False,
        dataset_sources=[],competition_sources=[],kernel_sources=[PARENT_REF])


def validate_proofs(csv_path,report_path,transport_path):
    raw=Path(csv_path).read_bytes();report_raw=Path(report_path).read_bytes()
    report=json.loads(report_raw);transport_raw=Path(transport_path).read_bytes();transport=json.loads(transport_raw)
    if not (report['valid'] and report['invalid_count']==0 and report['puzzles']==1000 and report['rows']==500500
            and report['sha256']==sha(raw) and report['metric_sha256']==METRIC_SHA):
        raise ValueError('Complete matching official CSV proof required')
    if not (transport['safe_sha256']==sha(raw) and transport['safe_official_report_sha256']==sha(report_raw)
            and transport['safe_invalid_count']==transport['roundtrip_invalid_count']==0
            and transport['safe_case_coverage']==transport['roundtrip_case_coverage']==1000
            and transport['scores_agree_within_1e_10'] and transport['metric_sha256']==METRIC_SHA):
        raise ValueError('Matching SAFE-CSV and ordinary-roundtrip transport proof required')
    return raw,report,dict(official_report_sha256=sha(report_raw),transport_proof_sha256=sha(transport_raw))


def build(args):
    if args.out.exists():raise ValueError('Use a fresh incremental export directory')
    parent,parent_report,parent_proofs=validate_proofs(args.parent,args.parent_report,args.parent_transport)
    target,target_report,target_proofs=validate_proofs(args.target,args.target_report,args.target_transport)
    completion_raw=(args.parent_export_job/'completion-proof.json').read_bytes();completion=json.loads(completion_raw)
    if not (sha(parent)==PARENT_SHA and completion['output_sha256']==PARENT_SHA and
            completion['ref']+'/1'==PARENT_REF and completion['version']==1 and
            completion['output_file']=='submission.csv' and completion['status']=='complete' and completion['is_private']):
        raise ValueError('Exact previously verified private parent export required')
    ns=runtime_namespace();old=ns['_validate_csv'](parent);new=ns['_validate_csv'](target)
    changed={i-1 for i,(a,b)in enumerate(zip(old,new)) if i and a!=b}
    patch_raw=json.dumps({'rows':[[rid,new[rid+1].decode('ascii')]for rid in sorted(changed)]},separators=(',',':')).encode()
    compressed=lzma.compress(patch_raw,preset=6);encoded=base64.b64encode(compressed).decode()
    export_raw=(args.parent_export_job/'export_manifest.json').read_bytes();parent_export=json.loads(export_raw)
    if parent_export['csv_sha256']!=PARENT_SHA:raise ValueError('Parent export provenance differs')
    manifest=dict(format_version=1,kind='exact_safe_csv_row_patch',
        parent_notebook=PARENT_REF,parent_output_file='submission.csv',parent_csv_sha256=sha(parent),parent_csv_bytes=len(parent),
        csv_sha256=sha(target),csv_bytes=len(target),rows=500500,puzzles=1000,
        schema=['id','n','square_id','x','y','angle'],line_ending='CRLF',
        patch_sha256=sha(patch_raw),patch_bytes=len(patch_raw),patch_compressed_sha256=sha(compressed),
        patch_compressed_bytes=len(compressed),changed_rows=len(changed),unchanged_rows=500500-len(changed),
        changed_puzzles=sorted({int(new[rid+1].split(b',')[1])for rid in changed}),
        changed_parent_rows_sha256=ns['_line_digest'](old,changed,True),
        changed_target_rows_sha256=ns['_line_digest'](new,changed,True),
        unchanged_rows_sha256=ns['_line_digest'](old,changed,False),
        official_score=target_report['score'],parent_official_score=parent_report['score'],metric_sha256=METRIC_SHA,
        parent_proofs=parent_proofs,target_proofs=target_proofs,parent_remote_completion_sha256=sha(completion_raw),
        parent_export_manifest_sha256=sha(export_raw),transport_scaling_applied=False,
        source_notices=parent_export.get('source_notices'),
        inherited_sources=[{k:v for k,v in row.items()if k!='puzzles'}for row in parent_export.get('sources',[])],
        inherited_certificates=parent_export.get('certificates',[]),
        local_geometry_provenance='Existing target portfolio proofs and repository notices; exporter makes no new mathematical discovery.',
        runtime_sha256=sha(RUNTIME.encode()),certificate_policy='Reuse only exact previously certified parent/target CSV bytes.')
    additional_path=getattr(args,'additional_provenance',None)
    if additional_path is not None:
        additional_raw=Path(additional_path).read_bytes()
        manifest['additional_source_provenance']=json.loads(additional_raw)
        manifest['additional_source_provenance_sha256']=sha(additional_raw)
    if ns['_line_digest'](new,changed,False)!=manifest['unchanged_rows_sha256']:
        raise ValueError('Unchanged byte sequence differs')
    rebuilt=ns['apply_safe_row_patch'](parent,encoded,manifest)
    if rebuilt!=target:raise ValueError('Local exact-byte reconstruction failed')
    manifest_encoding={'encoding':'literal_python_mapping'}
    if getattr(args,'compress_manifest',False):
        manifest_raw=json.dumps(manifest,separators=(',',':'),ensure_ascii=False).encode('utf8')
        manifest_compressed=lzma.compress(manifest_raw,preset=6)
        manifest_encoded=base64.b64encode(manifest_compressed).decode()
        parameters=(manifest_encoded,len(manifest_raw),sha(manifest_raw),sha(manifest_compressed))
        check={};exec(compile(COMPRESSED_MANIFEST_RUNTIME,'<manifest-codec>','exec'),check)
        if check['_decode_embedded_manifest'](*parameters)!=manifest:
            raise ValueError('Embedded manifest exact reconstruction failed')
        loader=COMPRESSED_MANIFEST_RUNTIME+'\nINCREMENTAL_MANIFEST = _decode_embedded_manifest(*'+repr(parameters)+')\n'
        manifest_encoding=dict(encoding='exact_json_lzma_base64',raw_bytes=len(manifest_raw),
            raw_sha256=sha(manifest_raw),compressed_bytes=len(manifest_compressed),
            compressed_sha256=sha(manifest_compressed),decoder_sha256=sha(COMPRESSED_MANIFEST_RUNTIME.encode()))
    else:
        loader='INCREMENTAL_MANIFEST = '+repr(manifest)+'\n'
    loader+='INCREMENTAL_PATCH = '+repr(encoded)+'\n'+RUNTIME
    source=loader+ENTRYPOINT;compile(source,'export.py','exec')
    if len(source.encode())>=1_000_000:raise ValueError('Incremental source exceeds Kaggle1MB')
    args.out.mkdir(parents=True)
    metadata=notebook_metadata(args.slug)
    report=dict(script_sha256=sha(source.encode()),script_bytes=len(source.encode()),
        parent_csv_sha256=sha(parent),target_csv_sha256=sha(target),changed_rows=len(changed),
        changed_puzzles=manifest['changed_puzzles'],patch_compressed_bytes=len(compressed),
        local_exact_byte_reconstruction=True,transport_scaling_applied=False,launched=False,
        manifest_encoding=manifest_encoding)
    for name,value in [('export_manifest.json',manifest),('kernel-metadata.json',metadata),('build_report.json',report)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    (args.out/'incremental_loader.py').write_text(loader);(args.out/'export.py').write_text(source)
    print(json.dumps(report,indent=2));return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent',type=Path,default=ROOT/'artifacts/submission-fq-full-basin-v1-safe.csv')
    parser.add_argument('--parent-report',type=Path,default=ROOT/'artifacts/submission-fq-full-basin-v1-safe-official.json')
    parser.add_argument('--parent-transport',type=Path,default=ROOT/'artifacts/submission-fq-full-basin-v1-safe.transport-validation.json')
    parser.add_argument('--parent-export-job',type=Path,default=ROOT/'artifacts/portfolio-8cd7c023ab18-export-job')
    parser.add_argument('--target',type=Path,default=ROOT/'artifacts/submission-cpu-bottleneck-v2-safe.csv')
    parser.add_argument('--target-report',type=Path,default=ROOT/'artifacts/submission-cpu-bottleneck-v2-safe-official.json')
    parser.add_argument('--target-transport',type=Path,default=ROOT/'artifacts/submission-cpu-bottleneck-v2-safe.transport-validation.json')
    parser.add_argument('--additional-provenance',type=Path,
                        help='Public source notices and per-case bindings embedded in the export manifest')
    parser.add_argument('--compress-manifest',action='store_true',
                        help='Losslessly compress embedded provenance with exact raw/compressed hash guards')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-portfolio-5cba3bdac3cf-incremental')
    build(parser.parse_args())


if __name__=='__main__':main()
