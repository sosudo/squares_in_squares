#!/usr/bin/env python3
"""Freeze one bounded private CPU scan of the completed structural-v2 raw bank."""
import argparse
import ast
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_fq_fused_hop_job import unpack


def sha(data):return hashlib.sha256(data).hexdigest()
def digest(path):return sha(Path(path).read_bytes())
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def native_formatter():
    paths=[ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/fq_active_pilot.py']
    wanted=[('extents','normalize'),('bloat','encode')];parts=['import math\nimport numpy as np\n'];proof={}
    for path,names in zip(paths,wanted):
        text=path.read_text();nodes={n.name:n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        proof[str(path)]=digest(path)
        for name in names:
            segment=ast.get_source_segment(text,nodes[name]);parts.append(segment+'\n')
    source='\n'.join(parts).encode();compile(source,'native_input_format.py','exec')
    return source,proof


SUPERVISOR=r'''
import base64,hashlib,io,json,lzma,os,signal,subprocess,sys,time,zipfile
from pathlib import Path
os.chdir('/kaggle/working');started=time.monotonic();worker=None
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
def expired(signum,frame):
    if worker is not None and worker.poll()is None:
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    raise TimeoutError('180-second whole raw selection bound')
signal.signal(signal.SIGALRM,expired);signal.alarm(175)
with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(PAYLOAD))))as archive:
    assert set(archive.namelist())==set(CONFIG['files'])
    for name in archive.namelist():
        path=Path(name);assert path.resolve().is_relative_to(Path.cwd())
        data=archive.read(name);assert hashlib.sha256(data).hexdigest()==CONFIG['files'][name]
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
def digest(path):
    with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
indices=[p for p in Path('/kaggle/input').rglob('full_structural_v2_raw_index.json')if digest(p)==CONFIG['analysis']['index_sha256']]
assert len(indices)==1
root=indices[0].parent;assert digest(root/'job_manifest.json')==CONFIG['analysis']['parent_manifest_sha256']
Path('reader_manifest.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
with Path('analysis.log').open('w')as log:
    worker=subprocess.Popen([sys.executable,'-u','select_full_structural_gpu_raw.py','--root',str(root),
        '--config','analysis-config.json','--out','selection','--deadline',str(started+165.)],
        stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    timed_out=False
    try:worker.wait(timeout=max(.01,started+170-time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out=True
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        worker.wait(timeout=2)
summary=dict(returncode=worker.returncode,timed_out=timed_out,seconds=time.monotonic()-started,
    cpu_only=True,optimization=False,geometry_certification=False,competition_submission=False)
if Path('selection/selection-report.json').exists():
    report=json.loads(Path('selection/selection-report.json').read_bytes())
    summary.update(status=report['status'],metadata_scan_complete=report['metadata_scan_complete'],
        selected_counts=report.get('selected_counts',{}),report_sha256=digest('selection/selection-report.json'))
Path('supervisor-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
signal.alarm(0)
if worker.returncode:raise SystemExit(worker.returncode)
'''


def build(args):
    if args.out.exists():raise ValueError('Fresh job directory required')
    receipt=json.loads((args.results/'download-receipt.json').read_bytes());parent_root=args.results/'outputs'
    assert receipt['status']=='complete' and receipt['private_source_verified'] and receipt['version']==2
    assert receipt['notebook']=='sos54352/squares-full-packing-structural-repair-v2'
    for name in ('full_structural_v2_raw_index.json','job_manifest.json'):
        assert digest(parent_root/name)==receipt['files'][name]['sha256']
    index=json.loads((parent_root/'full_structural_v2_raw_index.json').read_bytes())
    assert {str(k):len(v)for k,v in index['files'].items()}=={'0':1081,'1':893}
    pointer=json.loads(args.pointer.read_bytes());baseline=pointer['raw']
    assert digest(baseline['official_report'])==baseline['official_report_sha256']
    official=json.loads(Path(baseline['official_report']).read_bytes())
    assert official['valid'] and official['puzzles']==1000 and official['sha256']==baseline['sha256']
    assert digest(pointer['canonical_proof'])==pointer['canonical_proof_sha256']
    references={str(r['n']):r['side']for r in official['results']if int(r['n'])in(147,299,335)}
    excluded=json.loads((args.exclude/'selected-rows.json').read_bytes());assert len(excluded)==6
    exclusion_manifest=json.loads((args.exclude/'manifest.json').read_bytes())
    assert digest(args.exclude/'inputs.npz')==exclusion_manifest['inputs_sha256']
    formatter,format_sources=native_formatter()
    analysis=dict(parent_ref=receipt['notebook']+'/2',parent_source_sha256=receipt['source_sha256'],
        index_sha256=digest(parent_root/'full_structural_v2_raw_index.json'),parent_manifest_sha256=digest(parent_root/'job_manifest.json'),
        expected_packet_count=1974,current_reference_sides=references,
        current_reference_proof=dict(pointer_sha256=digest(args.pointer),raw=baseline,canonical_proof_sha256=pointer['canonical_proof_sha256']),
        excluded_rows=excluded,exclusion_rows_sha256=digest(args.exclude/'selected-rows.json'),
        maximum_selected_per_case=8,minimum_contraction='.001',analysis_seconds=165,
        native_formatter_source_hashes=format_sources,source_admission=False)
    data={'select_full_structural_gpu_raw.py':(ROOT/'experiments/select_full_structural_gpu_raw.py').read_bytes(),
        'packer_hop_physical_energy.py':(ROOT/'experiments/packer_hop_physical_energy.py').read_bytes(),
        'native_input_format.py':formatter,'analysis-config.json':json.dumps(analysis,indent=2).encode(),
        'provenance/parent-download-receipt.json':(args.results/'download-receipt.json').read_bytes(),
        'provenance/excluded-rows.json':(args.exclude/'selected-rows.json').read_bytes(),
        'provenance/exclusion-manifest.json':(args.exclude/'manifest.json').read_bytes(),
        'provenance/current-pointer.json':args.pointer.read_bytes()}
    for path in format_sources:data['provenance/native-format-source/'+Path(path).name]=Path(path).read_bytes()
    # The exact completed parent is independently source-verified in the receipt.
    source_paths=list((ROOT/'artifacts').glob('full-structural-gpu-v2*job*/search.py'))
    matching=[p for p in source_paths if digest(p)==receipt['source_sha256']]
    if not matching:raise ValueError('Exact completed parent source not found locally')
    _,_,parent_files=unpack(matching[0],receipt['source_sha256'],'zip64')
    for name,value in parent_files.items():
        if any(k in Path(name).name.lower()for k in('license','notice','source_manifest'))or'vendor/notices/'in name:
            data['inherited/'+name]=value
    for name,value in data.items():
        if name.endswith('.py'):compile(value,name,'exec')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,value in data.items():archive.writestr(name,value)
    config=dict(analysis=analysis,files={name:sha(value)for name,value in data.items()},builder_sha256=digest(__file__),
        worker_seconds=170,parent_alarm_seconds=175,whole_seconds=180,server_timeout_seconds=240,gpu=False,optimization=False)
    source='CONFIG='+repr(config)+'\nPAYLOAD='+repr(base64.b85encode(lzma.compress(stream.getvalue(),preset=9)).decode())+'\n'+SUPERVISOR
    compile(source,'search.py','exec');assert len(source.encode())<1_000_000
    args.out.mkdir(parents=True);(args.out/'search.py').write_text(source)
    slug='sos54352/squares-full-raw-selection-1974'
    meta=dict(id=slug,title=slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',kernel_type='script',
        is_private=True,enable_gpu=False,enable_tpu=False,enable_internet=False,kernel_sources=[analysis['parent_ref']],dataset_sources=[],competition_sources=[])
    save(args.out/'kernel-metadata.json',meta);save(args.out/'build_report.json',dict(source_sha256=sha(source.encode()),source_bytes=len(source.encode()),configuration=config,launched=False))
    replay=args.out/'local-replay';replay.mkdir()
    for name,value in data.items():
        path=replay/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
    print(json.dumps(dict(out=str(args.out),source_sha256=sha(source.encode()),source_bytes=len(source.encode()),launched=False)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=ROOT/'artifacts/full-structural-gpu-v2-results')
    parser.add_argument('--pointer',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--exclude',type=Path,default=ROOT/'artifacts/full-gpu-v2-native-handoff-v1')
    parser.add_argument('--out',type=Path,required=True);build(parser.parse_args())
