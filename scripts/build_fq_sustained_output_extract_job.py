#!/usr/bin/env python3
"""Prepare a private offline CPU extractor; never upload, execute or submit it."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/fq-sustained-cold-job-v1/search.py'
PARENT_SHA='dc6950e858285433d1975f537431e375bae95584ab314807a3ae08b79baa0451'
PARENT_REF='sos54352/squares-sustained-cold-12case/1'
MANIFEST_SHA='228ea112d2c30ab20d8d42704e086c6b4be30197e52d94dbb1e636ad3c5bdb45'
POLICY_SHA='c7429eb1b2ac4ee4f82972f09df77d497904218a1c622119ab521854b0088330'
WORKER='experiments/fq_sustained_output_extract.py'
CASES=(341,411,412,462,541,544,591,629,641,742,744,978)


def sha(data):return hashlib.sha256(data).hexdigest()
def encoded_json(value):return (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()


def parent_identity():
    data=PARENT.read_bytes()
    if sha(data)!=PARENT_SHA:raise ValueError('Exact launched parent source required')
    tree=ast.parse(data);manifest=ast.literal_eval(tree.body[0].value)
    payload=ast.literal_eval(tree.body[1].value)
    if sha(encoded_json(manifest))!=MANIFEST_SHA:raise ValueError('Parent runtime manifest differs')
    with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(payload)))) as archive:
        if set(archive.namelist())!=set(manifest['files']):raise ValueError('Parent payload inventory differs')
        for name,expected in manifest['files'].items():
            if sha(archive.read(name))!=expected:raise ValueError('Parent payload changed: '+name)
        policy=archive.read('sustained-config.json')
        if sha(policy)!=POLICY_SHA:raise ValueError('Parent config differs')
        if json.loads(policy)!=manifest['configuration']:raise ValueError('Parent config/manifest mismatch')
    if sorted(map(int,manifest['configuration']['cases']))!=list(CASES):raise ValueError('Parent case inventory differs')
    return manifest


SUPERVISOR=r'''
import base64,hashlib,io,json,lzma,os,signal,subprocess,sys,time,zipfile
from pathlib import Path
started=time.monotonic();worker=None;root=Path('/kaggle/working');os.chdir(root)
def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def stop(signum,frame):
    if worker is not None and worker.poll() is None:
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    raise TimeoutError('Extractor whole deadline240seconds')
signal.signal(signal.SIGALRM,stop);signal.alarm(235)
packed=base64.b85decode(PAYLOAD)
assert hashlib.sha256(packed).hexdigest()==CONFIG['payload_sha256']
raw=lzma.decompress(packed)
assert len(raw)==CONFIG['payload_raw_bytes']
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    assert set(archive.namelist())==set(CONFIG['files'])
    for name,expected in CONFIG['files'].items():
        path=root/name;assert path.resolve().is_relative_to(root)
        data=archive.read(name);assert hashlib.sha256(data).hexdigest()==expected
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
Path('extractor-job-manifest.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
with open('extractor-worker.log','w') as log:
    worker=subprocess.Popen([sys.executable,'-u','experiments/fq_sustained_output_extract.py',
        '--config','extract-config.json','--out','extracted'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    timed_out=False
    try:worker.wait(timeout=min(180,max(.001,started+220-time.monotonic())))
    except subprocess.TimeoutExpired:
        timed_out=True
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        worker.wait(timeout=2)
summary=dict(returncode=worker.returncode,timed_out=timed_out,seconds=time.monotonic()-started,
    worker_seconds=180,whole_seconds=240,server_seconds=300,gpu=False,optimizer=False,certification=False,
    parent_notebook=CONFIG['parent_notebook'],parent_source_sha256=CONFIG['parent_source_sha256'])
inventory=root/'extracted/inventory.json'
if inventory.is_file():
    report=json.loads(inventory.read_bytes());archive=root/'extracted/selected-output.zip'
    assert archive.is_file() and digest(archive)==report['zip_sha256']
    summary.update(inventory_sha256=digest(inventory),zip_sha256=report['zip_sha256'],
        zip_bytes=archive.stat().st_size,file_count=report['file_count'],terminal_packets_copied=report['terminal_packets_copied'])
total=sum(path.stat().st_size for path in root.rglob('*') if path.is_file())
summary['actual_output_bytes']=total
assert total<=768*1024**2,'Extractor total output cap exceeded'
Path('extractor-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
signal.alarm(0)
assert worker.returncode==0 and not timed_out and inventory.is_file()
'''


def build(args):
    if args.out.exists():raise ValueError('Fresh output directory required')
    parent=parent_identity();worker=(ROOT/WORKER).read_bytes();compile(worker,WORKER,'exec')
    config=dict(parent_notebook=PARENT_REF,parent_source_sha256=PARENT_SHA,parent_manifest_sha256=MANIFEST_SHA,
        parent_config_sha256=POLICY_SHA,parent_files=parent['files'],cases=list(CASES),worker_sha256=sha(worker),
        builder_sha256=sha(Path(__file__).read_bytes()),max_files=20000,max_uncompressed_bytes=500*1024**2,
        max_zip_bytes=512*1024**2,max_inventory_bytes=8*1024**2,max_output_bytes=700*1024**2,
        no_optimizer=True,no_certification=True,no_gpu=True)
    files={WORKER:worker,'extract-config.json':encoded_json(config)}
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,data in files.items():archive.writestr(name,data)
    packed=lzma.compress(stream.getvalue(),preset=9)
    manifest=dict(kind='Exact finite sustained output extraction; no numerical work',parent_notebook=PARENT_REF,
        parent_source_sha256=PARENT_SHA,parent_manifest_sha256=MANIFEST_SHA,parent_config_sha256=POLICY_SHA,
        files={name:sha(data) for name,data in files.items()},payload_sha256=sha(packed),payload_raw_bytes=len(stream.getvalue()),
        worker_seconds=180,whole_seconds=240,server_seconds=300,worker_sha256=sha(worker),
        builder_sha256=sha(Path(__file__).read_bytes()),no_optimizer=True,no_certification=True,no_gpu=True,no_submission=True,
        output_schema='extracted/selected-output.zip and extracted/inventory.json; original parent paths inside ZIP; separate extraction-chain receipt required')
    source='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(base64.b85encode(packed).decode())+'\n'+SUPERVISOR
    compile(source,'extract.py','exec')
    if len(source.encode())>=1000000:raise ValueError('Extractor source exceeds1MB')
    slug=args.slug
    metadata=dict(id=slug,title=slug.split('/')[-1].replace('-',' '),code_file='extract.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=False,enable_tpu=False,enable_internet=False,
        dataset_sources=[],kernel_sources=[PARENT_REF],competition_sources=[])
    args.out.mkdir(parents=True)
    (args.out/'extract.py').write_text(source)
    for name,value in [('kernel-metadata.json',metadata),('job_manifest.json',manifest),('extract-config.json',config)]:
        (args.out/name).write_bytes(encoded_json(value))
    report=dict(source_sha256=sha(source.encode()),source_bytes=len(source.encode()),parent_source_sha256=PARENT_SHA,
        parent_manifest_sha256=MANIFEST_SHA,parent_config_sha256=POLICY_SHA,parent_files=len(parent['files']),
        embedded_files=len(files),worker_sha256=sha(worker),builder_sha256=sha(Path(__file__).read_bytes()),launched=False)
    (args.out/'build_report.json').write_bytes(encoded_json(report));print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-sustained-output-extractor')
    build(parser.parse_args())
