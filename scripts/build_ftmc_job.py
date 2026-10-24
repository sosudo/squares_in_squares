"""Package a private, bounded CUDA FTMC pilot from attributed public source.

No credentials or external downloads are embedded. A validated source snapshot,
published gadget fixtures, and this job's exact configuration are hashed into the
manifest. The job uses one GPU, runs preflight checks, then a bounded worker.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

RUNTIME=r'''
import base64, hashlib, io, json, os, subprocess, sys, time, zipfile
from pathlib import Path
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[name]='1'
os.chdir('/kaggle/working')
root=Path.cwd()
for directory in ['artifacts','research']:(root/directory).mkdir(exist_ok=True)
manifest=CONFIG
started=time.monotonic()
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as archive:
    for entry in archive.infolist():
        target=root/entry.filename
        assert target.resolve().is_relative_to(root), entry.filename
        data=archive.read(entry)
        assert hashlib.sha256(data).hexdigest()==manifest['embedded_sha256'][entry.filename]
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
sys.path.insert(0,str(root))
import numpy as np
import cupy as cp
assert cp.cuda.runtime.getDeviceCount()>=1,'CUDA unavailable; stop before numerical search'
cp.cuda.Device(0).use()
properties=cp.cuda.runtime.getDeviceProperties(0)
gpu_name=properties['name']
if isinstance(gpu_name,bytes):gpu_name=gpu_name.decode()
manifest.update(gpu=gpu_name,gpu_count=cp.cuda.runtime.getDeviceCount(),cupy_version=cp.__version__,numpy_version=np.__version__)
Path('job_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'stage':'manifest',**manifest}),flush=True)

from gpu_ftmc_refill import dimensions,excess,certify,atom_npz,atom_json
from solver import normalize
from upright_refill import check as refill_check,gaps
from gpu_topology import check as square_check
from gpu_rect_optimizer import check as rectangle_check
from gpu_rect_explore import check as exploration_check
from gpu_upright_rows import check as row_check

# These checks can fail for incorrect CUDA gradients, rectangular geometry,
# precision conversion, refill counts, or compilation/runtime incompatibility.
preflight={}
for label,check in [('upright_refill',refill_check),('square_cuda',square_check),
                    ('rectangle_cuda',rectangle_check),('fp32_vs_fp64',exploration_check),
                    ('gpu_row_refill',row_check)]:
    result=check();preflight[label]={'passed':True,'result':result}
    atom_json('preflight.json',preflight)
    print(json.dumps({'stage':'preflight','check':label,'result':result}),flush=True)

z=np.load('examples.npz');bank={};variants={};provenance={}
for idx in manifest['gadget_ids']:
    w,h,d=map(int,z['meta_39'][idx,:3])
    for stage in ['before','after']:
        source=z[f'{stage}_{idx}']
        assert source.shape==(w*h+d,3) and np.isfinite(source).all()
        for transpose in [False,True]:
            p=source.copy();ww,hh=w,h
            if transpose:
                p[:,:2]=p[:,[1,0]];p[:,2]=np.pi/2-p[:,2];ww,hh=h,w
            p=normalize(p,0);key=f'{ww}_{hh}_{d}'
            variants[f'{key}__{stage}{idx}']=p
            if key not in bank or excess(p,ww,hh)<excess(bank[key],ww,hh):
                bank[key]=p;provenance[key]={'dataset':'cdeotte/squares-in-squares-22-315-data',
                    'fixture':f'{stage}_{idx}','transpose':transpose,'initial_bloat':excess(p,ww,hh)}
atom_npz('artifacts/night_seed_gadgets.npz',bank)
atom_npz('artifacts/night_seed_variants.npz',variants)
atom_json('research/night_seed_provenance.json',provenance)
atom_json('research/night_priorities.json',{})
print(json.dumps({'stage':'seed_bank','gadgets':len(bank),'variants':len(variants)}),flush=True)

command=[sys.executable,'-u','gpu_ftmc_refill.py','--device','0','--seconds',str(manifest['search_seconds']),
         '--replicas',str(manifest['replicas']),'--seed',str(manifest['seed'])]
worker_started=time.monotonic();timed_out=False
with open('ftmc_worker.log','w') as log:
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
    deadline=worker_started+manifest['search_seconds']+manifest['grace_seconds']
    while process.poll() is None:
        if time.monotonic()>deadline:
            timed_out=True;process.terminate()
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            break
        status_path=Path('research/worker0_status.json')
        try:status=json.loads(status_path.read_text()) if status_path.exists() else {}
        except (OSError,json.JSONDecodeError):status={}
        heartbeat={'stage':'worker','elapsed':time.monotonic()-worker_started,
                   'batches':status.get('batches'),'accepted':status.get('accepted'),
                   'core_trials':status.get('core_trials'),'refill_success':status.get('refill_success')}
        atom_json('heartbeat.json',heartbeat);print(json.dumps(heartbeat),flush=True)
        time.sleep(20)

if process.returncode and not timed_out:
    print(Path('ftmc_worker.log').read_text(errors='replace')[-10000:],flush=True)
    raise RuntimeError(f'FTMC worker exited with status {process.returncode}')

candidates={};improved=0;checkpoint=Path('artifacts/worker0_gadgets.npz')
if checkpoint.exists():
    with np.load(checkpoint) as wins:
        for name in wins.files:
            key=name.split('__')[0];w,h,d=map(int,key.split('_'));p=wins[name]
            f=excess(p,w,h);old=excess(bank[key],w,h)
            assert p.shape==(w*h+d,3) and np.isfinite(p).all()
            gap=gaps(p);official=certify(p)
            assert gap>0 and official,(name,gap,official)
            is_improved=f<old-2e-7;improved+=int(is_improved)
            candidates[name]={'w':w,'h':h,'surplus':d,'bloat':f,'seed_bloat':old,
                'strict_improvement':is_improved,'minimum_gap':gap,'official_raw_and_roundtrip':official,
                'squares':p.tolist(),'source':'lightningv08 public v21 FTMC; this private pilot',
                'seed_provenance':provenance[key]}
atom_json('ftmc_candidates.json',candidates)
status_path=Path('research/worker0_status.json')
status=json.loads(status_path.read_text()) if status_path.exists() else {}
summary={'stage':'complete','wall_seconds':time.monotonic()-started,
         'worker_seconds':time.monotonic()-worker_started,'worker_returncode':process.returncode,
         'bounded_timeout':timed_out,'candidate_variants':len(candidates),'strict_improvements':improved,
         'status':status,'preflight':preflight,'note':'Gadgets require composition and full-CSV official validation before competition submission.'}
atom_json('ftmc_summary.json',summary)
print(json.dumps(summary),flush=True)
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-dir',type=Path,default=ROOT/'vendor/lightning_ftmc')
    ap.add_argument('--examples',type=Path,default=ROOT/'artifacts/public/gadgets_39_and_baselines.npz')
    ap.add_argument('--ids',default='all')
    ap.add_argument('--slug',default='sos54352/squares-ftmc-pilot')
    ap.add_argument('--title',default='Squares FTMC Pilot')
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/ftmc-pilot')
    ap.add_argument('--seconds',type=int,default=600)
    ap.add_argument('--grace-seconds',type=int,default=180)
    ap.add_argument('--replicas',type=int,default=64)
    ap.add_argument('--seed',type=int,default=317)
    args=ap.parse_args()
    if args.seconds<=0 or args.grace_seconds<0 or not 1<=args.replicas<=512:
        raise ValueError('Invalid worker budget or replica count')
    fixtures=np.load(args.examples)
    ids=list(range(len(fixtures['meta_39']))) if args.ids=='all' else [int(i)for i in args.ids.split(',')]
    if not ids or any(i<0 or i>=len(fixtures['meta_39'])for i in ids):raise ValueError('Invalid gadget fixture index')
    data={}
    for path in sorted(args.source_dir.rglob('*')):
        if not path.is_file() or '__pycache__'in path.parts:continue
        key=str(path.relative_to(args.source_dir));payload=path.read_bytes()
        if key.endswith('.py'):compile(payload,key,'exec')
        data[key]=payload
    data['examples.npz']=args.examples.read_bytes()
    required=['gpu_ftmc_refill.py','gpu_rect_optimizer.py','gpu_rect_explore.py',
              'gpu_topology.py','gpu_upright_rows.py','upright_refill.py','research/official_metric.py',
              'LICENSE','NOTICE','SOURCE_MANIFEST.json']
    assert all(name in data for name in required)
    for name,payload in data.items():
        if b'KGAT_'in payload:raise ValueError(f'Credential-shaped content forbidden in payload: {name}')
    manifest={'source':'lightningv08/squares-in-squares-cuda-packing-search','source_version':21,
              'source_license':'Apache-2.0','gadget_ids':ids,'search_seconds':args.seconds,
              'grace_seconds':args.grace_seconds,'replicas':args.replicas,'seed':args.seed,
              'slug':args.slug,'embedded_sha256':{k:hashlib.sha256(v).hexdigest()for k,v in data.items()},
              'validation':'GPU analytic-gradient/refill preflight; per-gadget official metric; full composition still required.'}
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,payload in data.items():z.writestr(name,payload)
    encoded=base64.b64encode(archive.getvalue()).decode()
    script='# Private bounded FTMC search. No credentials embedded.\nCONFIG = '+repr(manifest)+'\nPAYLOAD = '+repr(encoded)+'\n'+RUNTIME
    compile(script,'search.py','exec')
    metadata={'id':args.slug,'title':args.title,'code_file':'search.py','language':'python',
              'kernel_type':'script','is_private':True,'enable_gpu':True,'enable_internet':False,
              'enable_tpu':False,'dataset_sources':[],'kernel_sources':[],
              'competition_sources':['squares-in-squares'],'machine_shape':'NvidiaTeslaT4'}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'search.py').write_text(script)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (args.out/'job_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'built':str(args.out),'code_bytes':len(script),'fixtures':len(ids),
                      'search_seconds':args.seconds,'grace_seconds':args.grace_seconds,
                      'sources':len(data),'private':True}))


if __name__=='__main__':main()
