"""Offline dual-GPU supervisor with a mandatory both-device CUDA barrier."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile

for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
os.chdir('/kaggle/working');root=Path.cwd();started=time.monotonic();workers={};logs={}
if Path('preflight-approved.json').exists():raise ValueError('Stale CUDA preflight approval forbidden')


def atomic_json(path,value):
    p=Path(path);temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(p)


def stop_all():
    for p in workers.values():
        if p.poll()is None:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
    for p in workers.values():
        try:p.wait(timeout=2)
        except subprocess.TimeoutExpired:pass


def outer_alarm(signum,frame):
    stop_all();atomic_json('hard_timeout.json',dict(elapsed_seconds=time.monotonic()-started,limit=CONFIG['wall_seconds']))
    raise TimeoutError('Whole notebook wall limit reached')


signal.signal(signal.SIGALRM,outer_alarm);signal.alarm(CONFIG['wall_seconds']-5)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD)))as archive:
    for item in archive.infolist():
        target=root/item.filename
        assert target.resolve().is_relative_to(root)
        data=archive.read(item);assert hashlib.sha256(data).hexdigest()==CONFIG['embedded_sha256'][item.filename]
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
sys.path[:0]=[str(root/'experiments'),str(root/'scripts'),str(root/'public_solver')]
import cupy as cp
assert cp.cuda.runtime.getDeviceCount()>=2
hardware=[]
for device in (0,1):
    props=cp.cuda.runtime.getDeviceProperties(device);name=props['name'];name=name.decode()if isinstance(name,bytes)else name
    assert'T4'in name
    hardware.append(dict(device=device,name=name,memory_bytes=int(props['totalGlobalMem'])))
atomic_json('job_manifest.json',dict(CONFIG,hardware=hardware,cupy_version=cp.__version__))
Path('artifacts').mkdir(exist_ok=True)
environment=os.environ.copy();environment['PYTHONPATH']=os.pathsep.join(sys.path[:3])
for device in (0,1):
    if Path(f'artifacts/full_structural_device{device}').exists():raise ValueError('Fresh worker output directory required')
    logs[device]=open(f'full_structural_worker{device}.log','w')
    workers[device]=subprocess.Popen([sys.executable,'-u','experiments/full_structural_gpu_worker.py','--device',str(device)],
                                    stdout=logs[device],stderr=subprocess.STDOUT,env=environment,start_new_session=True)
failures=[];approved=False;search_started=None;search_deadline_enforced=False
try:
    while any(p.poll()is None for p in workers.values()):
        status={};preflight={}
        for device,p in workers.items():
            folder=Path(f'artifacts/full_structural_device{device}')
            for name,destination in [('status.json',status),('preflight.json',preflight)]:
                try:destination[str(device)]=json.loads((folder/name).read_text())
                except (OSError,json.JSONDecodeError):pass
            if p.poll()not in(None,0):failures.append(dict(device=device,exitcode=p.returncode))
        if failures:break
        if not approved and all(preflight.get(str(d),{}).get('passed')for d in (0,1)):
            approved=True;search_started=time.monotonic()
            atomic_json('preflight-approved.json',dict(passed=True,devices=[0,1],elapsed_seconds=search_started-started))
            print(json.dumps(dict(stage='all_live_CUDA_controls_passed',elapsed_seconds=search_started-started)),flush=True)
        if not approved and time.monotonic()-started>CONFIG['preflight_seconds']:
            failures.append(dict(reason='live-preflight-time-limit'));break
        if approved and time.monotonic()-search_started>=CONFIG['search_seconds']:
            search_deadline_enforced=True;break
        heartbeat=dict(stage='workers',seconds=time.monotonic()-started,preflight_approved=approved,
                       devices={d:{k:v for k,v in s.items()if k in('status','arm','seconds','stats','best_sides')}for d,s in status.items()})
        atomic_json('heartbeat.json',heartbeat);print(json.dumps(heartbeat),flush=True)
        remaining=(CONFIG['search_seconds']-(time.monotonic()-search_started))if approved else(CONFIG['preflight_seconds']-(time.monotonic()-started))
        time.sleep(max(.01,min(10,remaining)))
finally:
    stop_all()
    for stream in logs.values():stream.close()

import numpy as np
from fq_active_pilot import digest
from full_structural_gpu_moves import geometry_sha
from fq_coherent_clusters import atom_npz
all_poses={};records=[];candidates={};binding=[]
for device in (0,1):
    folder=Path(f'artifacts/full_structural_device{device}')
    if not(folder/'current.json').exists():continue
    current=json.loads((folder/'current.json').read_text());snapshot=Path(current['snapshot'])
    assert digest(snapshot/'summary.json')==current['summary_sha256']
    summary=json.loads((snapshot/'summary.json').read_text())
    for name,sha in summary['files'].items():assert digest(snapshot/name)==sha
    rr=json.loads((snapshot/'records.json').read_text())
    with np.load(snapshot/'certified.npz',allow_pickle=False)as archive:
        for r in rr:
            p=archive[r['name']];assert geometry_sha(p)==r['geometry_sha256']and r['certificate']['valid']
            all_poses[r['name']]=p;records.append(dict(r,device=device))
            if r['side_gain']>1e-9 and r['side']<candidates.get(str(r['n']),{}).get('side',float('inf')):
                candidates[str(r['n'])]=dict(side=r['side'],squares=[[f'{v:.17g}'for v in row]for row in p],
                    certificate=r['certificate'],provenance=dict(device=device,geometry_sha256=r['geometry_sha256'],mutation=r['mutation']))
    # Recover completed per-pose publications even if a deadline interrupted a
    # later stage before the next aggregate snapshot was written.
    already={r['name']for r in rr}
    for entry in sorted((folder/'entries').glob('*.json')):
        r=json.loads(entry.read_text())
        if r['name']in already:continue
        path=entry.with_suffix('.npz');assert digest(path)==r['entry_npz_sha256']
        with np.load(path,allow_pickle=False)as z:p=z['pose']
        assert geometry_sha(p)==r['geometry_sha256']and r['certificate']['valid']
        all_poses[r['name']]=p;records.append(dict(r,device=device,recovered_intermediate=True))
        if r['side_gain']>1e-9 and r['side']<candidates.get(str(r['n']),{}).get('side',float('inf')):
            candidates[str(r['n'])]=dict(side=r['side'],squares=[[f'{v:.17g}'for v in row]for row in p],
                certificate=r['certificate'],provenance=dict(device=device,geometry_sha256=r['geometry_sha256'],mutation=r['mutation']))
    binding.append(dict(device=device,snapshot=str(snapshot),summary_sha256=current['summary_sha256']))
atom_npz(Path('artifacts/full_structural_certified.npz'),all_poses)
atomic_json('full_structural_records.json',records);atomic_json('full_structural_candidates.json',candidates)
final=dict(preflight_passed=approved,failures=failures,elapsed_seconds=time.monotonic()-started,
           search_deadline_enforced=search_deadline_enforced,
           certified_variants=len(all_poses),improved_cases=len(candidates),binding=binding,
           archive_sha256=digest(Path('artifacts/full_structural_certified.npz')))
atomic_json('full_structural_summary.json',final);print(json.dumps(final),flush=True)
signal.alarm(0)
if failures or not approved:raise RuntimeError('Full structural pilot did not complete all mandatory controls/budgets')
