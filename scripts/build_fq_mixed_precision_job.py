#!/usr/bin/env python3
"""Package the finite mixed-precision diagnostic; never upload or launch it."""
from __future__ import annotations
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
import numpy as np
from build_fq_fused_hop_job import unpack

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
import full_structural_gpu_ties as ties

PARENT = ROOT/'artifacts/fq-cold-transfer-job-v1/search.py'
PARENT_SHA = '34ea1497cf6e24560eff8da939b3288b08029519640ba1eb8907acc1353d1292'
RUNTIME_FILES = ('fq_mixed_precision_adapter.py', 'fq_mixed_precision_controls.py', 'fq_mixed_precision_diagnostic.py',
                 'full_structural_gpu_ties.py', 'fq_torch_hop.py')


def sha(data): return hashlib.sha256(data).hexdigest()
def save(path, value): path.write_text(json.dumps(value, indent=2)+'\n')


def corrected_source(topology, rectangular):
    """Interpret only literal upstream string replacements, without imports."""
    values = [node.value for node in ast.parse(topology).body if isinstance(node, ast.Assign)
              and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id == 'CUDA']
    if len(values) != 1: raise ValueError('Ambiguous upstream CUDA declaration')
    original = ast.literal_eval(values[0])
    if not isinstance(original, str): raise ValueError('Expected literal CUDA')
    current = None
    def literal_replace(node):
        if isinstance(node, ast.Name) and node.id == 'src' and current is not None:
            return current
        if (isinstance(node, ast.Attribute) and node.attr == 'CUDA'
                and isinstance(node.value, ast.Name) and node.value.id == 'square'):
            return original
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'replace' and not node.keywords and len(node.args) == 2):
            args = [ast.literal_eval(arg) for arg in node.args]
            if not all(isinstance(arg, str) for arg in args): raise ValueError('Nonliteral source adaptation')
            return literal_replace(node.func.value).replace(*args)
        raise ValueError('Unexpected upstream CUDA construction')
    replacements = 0
    for node in ast.parse(rectangular).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'src'):
            current = literal_replace(node.value); replacements += 1
    if current is None: raise ValueError('No rectangular CUDA construction')
    patched, audit = ties.patch_cuda(current)
    ties.audit_patched(patched)
    return patched.encode(), dict(audit, literal_string_assignments=replacements,
                                 topology_file_sha256=sha(topology), rectangular_file_sha256=sha(rectangular))


SUPERVISOR = r'''
import base64,hashlib,io,json,lzma,os,signal,subprocess,sys,time,zipfile
from pathlib import Path
os.chdir('/kaggle/working');root=Path.cwd();started=time.monotonic();worker=None
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
def expired(signum,frame):
    if worker is not None and worker.poll() is None:
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    raise TimeoutError('Mixed diagnostic whole deadline')
signal.signal(signal.SIGALRM,expired);signal.alarm(295)
packed=base64.b85decode(PAYLOAD)
assert hashlib.sha256(packed).hexdigest()==CONFIG['compressed_sha256']
decoder=lzma.LZMADecompressor(memlimit=256*1024*1024)
raw=decoder.decompress(packed,max_length=CONFIG['payload_raw_bytes']+1)
assert decoder.eof and not decoder.unused_data and len(raw)==CONFIG['payload_raw_bytes']
assert hashlib.sha256(raw).hexdigest()==CONFIG['payload_raw_sha256']
with zipfile.ZipFile(io.BytesIO(raw))as archive:
    assert set(archive.namelist())==set(CONFIG['files'])
    for name in archive.namelist():
        path=root/name;assert path.resolve().is_relative_to(root)
        data=archive.read(name);assert hashlib.sha256(data).hexdigest()==CONFIG['files'][name]
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
if CONFIG['fixture_transport']['kind']=='private_dataset':
    found=None
    for path in sorted(Path('/kaggle/input').rglob('mixed-inputs.npz')):
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()==CONFIG['inputs_sha256']:
            found=data;break
    if found is None:raise ValueError('Exact private fixture archive absent')
    (root/'mixed-inputs.npz').write_bytes(found)
assert hashlib.sha256((root/'mixed-inputs.npz').read_bytes()).hexdigest()==CONFIG['inputs_sha256']
(root/'job_manifest.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
with (root/'diagnostic.log').open('w')as log:
    worker=subprocess.Popen([sys.executable,'-u','fq_mixed_precision_diagnostic.py',
        '--config','mixed-config.json','--out','diagnostic','--deadline',str(started+280.),
        '--parent-started',str(started)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    timed_out=False
    try:worker.wait(timeout=min(280.,max(.01,started+290-time.monotonic())))
    except subprocess.TimeoutExpired:
        timed_out=True
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        worker.wait(timeout=3.)
summary=dict(returncode=worker.returncode,timed_out=timed_out,seconds=time.monotonic()-started,
    whole_seconds=300,child_seconds=280,exploration_campaign=False,competition_submission_performed=False)
(root/'supervisor-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True);signal.alarm(0)
if worker.returncode:raise SystemExit(worker.returncode)
'''


def build(args):
    if args.out.exists(): raise ValueError('Fresh output directory required')
    _, parent, frozen = unpack(PARENT, PARENT_SHA, 'xz85')
    topology = frozen['public_solver/gpu_topology.py']
    rectangular = frozen['public_solver/gpu_rect_optimizer.py']
    if ties.__file__ is None or sha(Path(ties.__file__).read_bytes()) != sha(frozen['experiments/full_structural_gpu_ties.py']):
        raise ValueError('Reviewed tie adapter changed')
    cuda, cuda_proof = corrected_source(topology, rectangular)
    config_bytes = (args.fixtures/'mixed-config.json').read_bytes(); config = json.loads(config_bytes)
    inputs = (args.fixtures/'mixed-inputs.npz').read_bytes()
    proof_bytes = (args.fixtures/'input-proof.json').read_bytes(); proof = json.loads(proof_bytes)
    if not (sha(inputs) == config['inputs_sha256'] == proof['inputs_sha256']
            and config['corrected_fp64_cuda_path'] == 'corrected-fp64.cu'
            and config['corrected_fp64_cuda_sha256'] == sha(cuda)
            and config['inputs_path'] == 'mixed-inputs.npz' and 0 < config['work_seconds'] <= 240):
        raise ValueError('Exact diagnostic fixtures/configuration required')
    batches = config['batches']
    if len(batches) != 4 or sorted((int(x['n']), x['epoch']) for x in batches) != [
            (803,'early'),(803,'late'),(861,'early'),(861,'late')]:
        raise ValueError('Four predeclared actual-case batches required')
    early803 = next(x['key'] for x in batches if int(x['n']) == 803 and x['epoch'] == 'early')
    if config['occupancy'] != dict(enabled=True, steps=2000, batch_sizes=[32,64,128], fixture_key=early803):
        raise ValueError('Expected predeclared exact-duplicate FP64 occupancy control')
    with np.load(io.BytesIO(inputs), allow_pickle=False) as archive:
        if set(archive.files) != set(proof['arrays']): raise ValueError('Fixture array inventory differs')
        for key in archive.files:
            value=archive[key]; record=proof['arrays'][key]
            if not (value.dtype.str == record['dtype'] == '<f8' and list(value.shape) == record['shape']
                    and sha(value.tobytes()) == record['sha256'] and np.isfinite(value).all()):
                raise ValueError('Fixture array bytes differ')
        for batch in batches:
            if archive[batch['pose_key']].shape != (32,int(batch['n']),3): raise ValueError('Actual full-N B32 required')
            if archive[batch['boxes_key']].shape != (32,): raise ValueError('Exact per-chain box required')
    data={name:(ROOT/'experiments'/name).read_bytes() for name in RUNTIME_FILES}
    for name in ('full_structural_gpu_ties.py','fq_torch_hop.py'):
        if data[name] != frozen['experiments/'+name]: raise ValueError('Reviewed helper changed')
    data.update({'corrected-fp64.cu':cuda, 'mixed-config.json':config_bytes, 'input-proof.json':proof_bytes,
                 'provenance/original-gpu-topology.py':topology,
                 'provenance/original-gpu-rect-optimizer.py':rectangular,
                 'provenance/cuda-reconstruction.json':json.dumps(cuda_proof,indent=2).encode()})
    # Retain all inherited notice text without importing or shipping native binaries.
    for name,value in frozen.items():
        if any(part in Path(name).name.lower() for part in ('license','notice','source_manifest')) or 'vendor/notices/' in name:
            data['inherited/'+name]=value
    for path in sorted((args.fixtures/'provenance').rglob('*')):
        if path.is_file(): data['fixture-provenance/'+str(path.relative_to(args.fixtures/'provenance'))]=path.read_bytes()
    transport={'kind':'embedded'}
    if args.dataset_ref:
        receipt=json.loads(args.dataset_proof.read_bytes())
        if not (args.dataset_ref.count('/')==2 and args.dataset_ref.endswith('/1')
                and receipt['ref']+'/1'==args.dataset_ref and receipt['version']==1
                and receipt['is_private'] and receipt['status']=='complete'
                and receipt['inputs_sha256']==sha(inputs) and receipt['input_proof_sha256']==sha(proof_bytes)
                and receipt['downloaded_archive_sha256']==sha(inputs)):
            raise ValueError('Exact private version1 fixture receipt required')
        transport={'kind':'private_dataset','ref':args.dataset_ref,'verification_sha256':sha(args.dataset_proof.read_bytes())}
        data['provenance/private-fixture-verification.json']=args.dataset_proof.read_bytes()
    else: data['mixed-inputs.npz']=inputs
    for name,value in data.items():
        if name.endswith('.py'): compile(value,name,'exec')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,value in data.items(): archive.writestr(name,value)
    raw=stream.getvalue(); packed=lzma.compress(raw,preset=9)
    manifest=dict(kind='Finite same-proposal precision diagnostic; no search campaign or native finishing',
        parent_source_sha256=PARENT_SHA, inputs_sha256=sha(inputs), input_proof_sha256=sha(proof_bytes),
        fixture_transport=transport, configuration=config, cuda_reconstruction=cuda_proof,
        builder_sha256=sha(Path(__file__).read_bytes()), files={name:sha(value) for name,value in data.items()},
        compressed_sha256=sha(packed), payload_raw_sha256=sha(raw), payload_raw_bytes=len(raw),
        worker_seconds=280,parent_alarm_seconds=295,whole_seconds=300,server_timeout_seconds=480,
        competition_submission_performed=False)
    source='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(base64.b85encode(packed).decode())+'\n'+SUPERVISOR
    compile(source,'search.py','exec')
    if len(source.encode())>=1_000_000:
        raise ValueError('Exact embedded source exceeds1MB: '+str(len(source.encode()))+' bytes; freeze a private fixture dataset if authorized')
    args.out.mkdir(parents=True); (args.out/'search.py').write_text(source)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,
        dataset_sources=[args.dataset_ref] if args.dataset_ref else [],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
    report=dict(source_sha256=sha(source.encode()),source_bytes=len(source.encode()),payload_files=len(data),configuration=manifest,launched=False)
    save(args.out/'kernel-metadata.json',metadata); save(args.out/'build_report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='configuration'},indent=2)); return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--dataset-ref')
    parser.add_argument('--dataset-proof',type=Path)
    parser.add_argument('--slug',default='sos54352/squares-mixed-precision-diagnostic')
    args=parser.parse_args()
    if bool(args.dataset_ref)!=bool(args.dataset_proof): parser.error('Dataset reference and exact proof are paired')
    build(args)
