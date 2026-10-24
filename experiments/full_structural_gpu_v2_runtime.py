"""Bounded GPU search followed by a distinct bounded CPU certification drain."""
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
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
os.chdir('/kaggle/working');root=Path.cwd();started=time.monotonic();processes={};logs={}
if Path('preflight-approved-v2.json').exists():raise ValueError('Stale preflight barrier')


def atomic_json(path,value):
    p=Path(path);t=p.with_suffix('.incoming');t.write_text(json.dumps(value,indent=2)+'\n');t.replace(p)


def stop_all():
    for p in processes.values():
        if p.poll()is None:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
    for p in processes.values():
        try:p.wait(timeout=1)
        except subprocess.TimeoutExpired:pass


def hard_timeout(signum,frame):
    stop_all();atomic_json('hard_timeout.json',dict(seconds=time.monotonic()-started))
    raise TimeoutError('Whole notebook deadline')


signal.signal(signal.SIGALRM,hard_timeout);signal.alarm(CONFIG['wall_seconds']-5)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD)))as archive:
    for item in archive.infolist():
        path=root/item.filename;assert path.resolve().is_relative_to(root)
        data=archive.read(item);assert hashlib.sha256(data).hexdigest()==CONFIG['embedded_sha256'][item.filename]
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
sys.path[:0]=[str(root/'experiments'),str(root/'scripts'),str(root/'public_solver')]
import numpy as np
import cupy as cp
assert cp.cuda.runtime.getDeviceCount()>=2
hardware=[]
for d in(0,1):
    p=cp.cuda.runtime.getDeviceProperties(d);name=p['name'];name=name.decode()if isinstance(name,bytes)else name
    assert'T4'in name;hardware.append(dict(device=d,name=name))
atomic_json('job_manifest.json',dict(CONFIG,hardware=hardware))
Path('artifacts').mkdir(exist_ok=True)
environment=os.environ.copy();environment['PYTHONPATH']=os.pathsep.join(sys.path[:3])


def launch(mode):
    for d in(0,1):
        key=f'{mode}{d}';logs[key]=open(f'full_structural_v2_{key}.log','w')
        processes[key]=subprocess.Popen([sys.executable,'-u','experiments/full_structural_gpu_v2_worker.py',
            '--device',str(d),'--mode',mode],stdout=logs[key],stderr=subprocess.STDOUT,
            env=environment,start_new_session=True)


launch('search');approved=False;search_started=None;failures=[];enforced=False;drain={}
try:
    while any(processes[f'search{d}'].poll()is None for d in(0,1)):
        status={};preflight={}
        for d in(0,1):
            folder=Path(f'artifacts/full_structural_v2_device{d}')
            for file,target in [('status.json',status),('preflight.json',preflight)]:
                try:target[str(d)]=json.loads((folder/file).read_text())
                except(OSError,json.JSONDecodeError):pass
            code=processes[f'search{d}'].poll()
            if code not in(None,0):failures.append(dict(device=d,exitcode=code))
        if failures:break
        if not approved and all(preflight.get(str(d),{}).get('passed')for d in(0,1)):
            approved=True;search_started=time.monotonic()
            atomic_json('preflight-approved-v2.json',dict(passed=True,seconds=search_started-started))
            print(json.dumps(dict(stage='all_live_CUDA_controls_passed',seconds=search_started-started)),flush=True)
        if not approved and time.monotonic()-started>CONFIG['preflight_seconds']:
            failures.append(dict(reason='preflight-time-limit'));break
        if approved and time.monotonic()-search_started>=CONFIG['search_seconds']:
            enforced=True;break
        heartbeat=dict(stage='search',seconds=time.monotonic()-started,preflight_passed=approved,
                       devices={d:{k:v for k,v in s.items()if k in('phase','seconds','stats','throughput_control_passed')}for d,s in status.items()})
        atomic_json('heartbeat.json',heartbeat);print(json.dumps(heartbeat),flush=True)
        remaining=CONFIG['search_seconds']-(time.monotonic()-search_started)if approved else CONFIG['preflight_seconds']-(time.monotonic()-started)
        time.sleep(max(.01,min(10,remaining)))
finally:stop_all()
search_exitcodes={str(d):processes[f'search{d}'].returncode for d in(0,1)}
if not failures and not enforced:
    failures.extend(dict(device=int(d),exitcode=code)for d,code in search_exitcodes.items()if code!=0)
if approved and not failures:
    launch('certify');drain_started=time.monotonic()
    drain_budget=max(0.,min(CONFIG['certification_seconds'],CONFIG['wall_seconds']-(drain_started-started)-60))
    while any(processes[f'certify{d}'].poll()is None for d in(0,1)):
        if time.monotonic()-drain_started>drain_budget:break
        time.sleep(2)
    stop_all()
    for d in(0,1):
        folder=Path(f'artifacts/full_structural_v2_device{d}')
        drain[str(d)]=dict(returncode=processes[f'certify{d}'].returncode,
                           parent_budget_seconds=drain_budget,
                           elapsed_seconds=time.monotonic()-drain_started,
                           timeout_or_kill=processes[f'certify{d}'].returncode<0)
        if(folder/'certification-summary.json').exists():
            drain[str(d)]['summary']=json.loads((folder/'certification-summary.json').read_text())
        if(folder/'pending.npz').exists():
            with np.load(folder/'pending.npz',allow_pickle=False)as z:
                drain[str(d)]['selected_pending_count']=len(z.files)-1
for stream in logs.values():stream.close()
from fq_active_pilot import digest
from full_structural_gpu_moves import geometry_sha
from fq_coherent_clusters import atom_npz
poses={};records=[];candidates={};statuses={};raw_files={};paired_inputs={}
for d in(0,1):
    folder=Path(f'artifacts/full_structural_v2_device{d}')
    if(folder/'status.json').exists():statuses[str(d)]=json.loads((folder/'status.json').read_text())
    raw_files[str(d)]=[];paired_inputs[str(d)]={}
    for p in sorted((folder/'raw').glob('*.npz')):
        with np.load(p,allow_pickle=False)as z:
            meta=json.loads(z['metadata_json'].tobytes());inputs=z['input']
        input_sha=geometry_sha(inputs);assert input_sha==meta['array_sha256']['input']
        actual_rows=[geometry_sha(q)for q in inputs]
        assert actual_rows==[r['mutation']['input_geometry_sha256']for r in meta['rows']]
        signature=dict(n=meta['n'],input_sha256=input_sha,rows=[dict(source_id=r['source_id'],
            source_geometry_sha256=r['mutation']['source_geometry_sha256'],
            input_geometry_sha256=h,seed=r['mutation']['seed'])for r,h in zip(meta['rows'],actual_rows)])
        paired_inputs[str(d)][p.name]=signature
        raw_files[str(d)].append(dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p),
            input_sha256=input_sha,dispatch_state=meta['dispatch_state'],stages=[r['label']for r in meta['stages']]))
    for entry in sorted((folder/'certified_entries').glob('*.json')):
        r=json.loads(entry.read_text());assert r['validated']and r['certificate']['valid']
        npz=entry.with_suffix('.npz');assert digest(npz)==r['pose_npz_sha256']
        with np.load(npz,allow_pickle=False)as z:p=z['pose']
        sha=geometry_sha(p);assert sha==r['geometry_sha256'];poses[sha]=p;records.append(dict(r,device=d))
        n=str(r['n'])
        if r['gain']>1e-9 and r['side']<candidates.get(n,{}).get('side',float('inf')):
            candidates[n]=dict(side=r['side'],squares=[[f'{v:.17g}'for v in row]for row in p],certificate=r['certificate'],provenance=r['row'])
atom_npz(Path('artifacts/full_structural_v2_certified.npz'),poses)
atomic_json('full_structural_v2_records.json',records);atomic_json('full_structural_v2_candidates.json',candidates)
atomic_json('full_structural_v2_raw_index.json',dict(validated=False,files=raw_files))
common=sorted(set(paired_inputs['0'])&set(paired_inputs['1']))
mismatches=[name for name in common if paired_inputs['0'][name]!=paired_inputs['1'][name]]
pairing=dict(common_batches=len(common),matching_batches=len(common)-len(mismatches),mismatches=mismatches,
             matching_common_input_bytes=bool(common)and not mismatches,
             scope='Saved common input packets; actual stage completion is reported separately in the raw index.',
             arm_comparison='paired_common_inputs'if common and not mismatches else'unpaired_or_no_common_inputs',
             unmatched_batches={d:len(v)-len(common)for d,v in paired_inputs.items()})
atomic_json('full_structural_v2_pairing.json',dict(summary=pairing,actual_inputs=paired_inputs))
summary=dict(preflight_passed=approved,failures=failures,search_deadline_enforced=enforced,search_exitcodes=search_exitcodes,certification_drain=drain,
             seconds=time.monotonic()-started,certified=len(poses),improved_cases=len(candidates),statuses=statuses,
             archive_sha256=digest(Path('artifacts/full_structural_v2_certified.npz')),actual_paired_input_check=pairing)
atomic_json('full_structural_v2_summary.json',summary)
print(json.dumps({k:v for k,v in summary.items()if k!='statuses'}),flush=True);signal.alarm(0)
if failures or not approved:raise RuntimeError('Mandatory search controls failed')
