"""Embedded bounded dual-GPU runtime; CONFIG and PAYLOAD are supplied by builder.

This wrapper preserves the public CUDA sources. Resume bookkeeping, supervision,
deduplication and reporting are local additions.
"""
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

for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
os.chdir('/kaggle/working')
root=Path.cwd();manifest=CONFIG;started=time.monotonic();processes={};logs={}
for directory in ['artifacts','research']:(root/directory).mkdir(exist_ok=True)


def atomic_json(path,value):
    p=Path(path);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(p)


def stop_children():
    for process in processes.values():
        if process.poll() is None:process.terminate()
    for process in processes.values():
        if process.poll() is None:
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait()


def hard_timeout(signum,frame):
    stop_children()
    atomic_json('hard_timeout.json',{'wall_seconds':time.monotonic()-started,
                                    'limit_seconds':manifest['wall_seconds'],
                                    'checkpoints_preserved':True})
    raise TimeoutError('Bounded campaign overall wall limit reached; checkpoints retained.')


signal.signal(signal.SIGALRM,hard_timeout)
signal.alarm(manifest['wall_seconds'])
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as archive:
    for entry in archive.infolist():
        target=root/entry.filename
        assert target.resolve().is_relative_to(root),entry.filename
        data=archive.read(entry)
        assert hashlib.sha256(data).hexdigest()==manifest['embedded_sha256'][entry.filename]
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
sys.path.insert(0,str(root))
import numpy as np
import cupy as cp
from ftmc_seed_bank import build_seed_bank
from gpu_ftmc_refill import excess,certify,atom_npz
from upright_refill import check as refill_check,gaps
from gpu_topology import check as square_check
from gpu_rect_optimizer import check as rectangle_check
from gpu_rect_explore import check as exploration_check
from gpu_upright_rows import check as row_check

assert cp.cuda.runtime.getDeviceCount()>max(manifest['devices']), 'Requested CUDA devices unavailable'
hardware=[];preflight={}
for device in manifest['devices']:
    cp.cuda.Device(device).use();properties=cp.cuda.runtime.getDeviceProperties(device)
    name=properties['name'];name=name.decode() if isinstance(name,bytes) else name
    assert 'T4' in name,('This campaign targets T4 arithmetic',name)
    hardware.append({'device':device,'name':name,'memory_bytes':int(properties['totalGlobalMem'])})
    checks={}
    for label,check in [('upright_refill',refill_check),('square_cuda',square_check),
                        ('rectangle_cuda',rectangle_check),('fp32_vs_fp64',exploration_check),
                        ('gpu_row_refill',row_check)]:
        result=check();checks[label]={'passed':True,'result':result}
        preflight[str(device)]=checks;atomic_json('preflight.json',preflight)
        print(json.dumps({'stage':'preflight','device':device,'check':label,'result':result}),flush=True)
    cp.get_default_memory_pool().free_all_blocks()
manifest.update(hardware=hardware,cupy_version=cp.__version__,numpy_version=np.__version__)
atomic_json('job_manifest.json',manifest)

bank,variants,provenance,resume=build_seed_bank('examples.npz',manifest['resume_files'],manifest['gadget_ids'])
atom_npz('artifacts/night_seed_gadgets.npz',bank)
atom_npz('artifacts/night_seed_variants.npz',variants)
atomic_json('research/night_seed_provenance.json',provenance)
atomic_json('research/night_priorities.json',{})
baseline={key:excess(p,*map(int,key.split('_')[:2])) for key,p in bank.items()}
atomic_json('campaign_incumbents.json',baseline)
for device in manifest['devices']:
    # Each source worker recognizes and resumes this exact checkpoint layout.
    atom_npz(f'artifacts/worker{device}_gadgets.npz',resume)
    cfg=manifest['device_configs'][str(device)]
    atomic_json(f'device{device}_manifest.json',{**cfg,'hardware':hardware[manifest['devices'].index(device)],
                'seed_gadgets':len(bank),'seed_variants':len(variants),'resume_variants':len(resume),
                'incumbent_sha256':hashlib.sha256(Path('campaign_incumbents.json').read_bytes()).hexdigest()})
print(json.dumps({'stage':'resume_bank','gadgets':len(bank),'variants':len(variants),'resume_variants':len(resume)}),flush=True)

worker_started=time.monotonic();deadline=worker_started+manifest['search_seconds']+manifest['grace_seconds']
timed_out=False;failures=[]
try:
    for device in manifest['devices']:
        cfg=manifest['device_configs'][str(device)]
        command=[sys.executable,'-u','gpu_ftmc_refill.py','--device',str(device),
                 '--seconds',str(manifest['search_seconds']),'--replicas',str(cfg['replicas']),
                 '--seed',str(cfg['seed'])]
        logs[device]=open(f'ftmc_worker{device}.log','w')
        processes[device]=subprocess.Popen(command,stdout=logs[device],stderr=subprocess.STDOUT)
    while any(p.poll() is None for p in processes.values()):
        heartbeat={'stage':'workers','elapsed':time.monotonic()-worker_started,'devices':{}}
        for device,p in processes.items():
            status_file=Path(f'research/worker{device}_status.json')
            try:status=json.loads(status_file.read_text()) if status_file.exists() else {}
            except (OSError,json.JSONDecodeError):status={}
            heartbeat['devices'][str(device)]={k:status.get(k) for k in ['seconds','batches','core_trials','refill_success','full_quenches','accepted','cuda_seconds']}
            heartbeat['devices'][str(device)]['returncode']=p.poll()
            if p.poll() not in (None,0):failures.append({'device':device,'returncode':p.returncode})
        atomic_json('heartbeat.json',heartbeat);print(json.dumps(heartbeat),flush=True)
        if failures:stop_children();break
        if time.monotonic()>deadline:timed_out=True;stop_children();break
        time.sleep(20)
finally:
    stop_children()
    for log in logs.values():log.close()
search_elapsed=time.monotonic()-worker_started

# Identical resumed/checkpointed coordinates on two GPUs are checked once.
# Every *new* source-worker admission also passed its unchanged raw/roundtrip
# official checks before reaching its checkpoint.
unique={};statuses={}
for device in manifest['devices']:
    status_path=Path(f'research/worker{device}_status.json')
    statuses[str(device)]=json.loads(status_path.read_text()) if status_path.exists() else {}
    checkpoint=Path(f'artifacts/worker{device}_gadgets.npz')
    if not checkpoint.exists():continue
    with np.load(checkpoint) as z:
        for name in z.files:
            key=name.split('__')[0];p=z[name];digest=hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest()
            identity=f'{key}__{digest[:16]}'
            if identity not in unique:unique[identity]={'root':key,'squares':p,'worker_variants':[]}
            unique[identity]['worker_variants'].append({'device':device,'name':name})
candidates={};all_npz={};strict_npz={};best={};per_device={str(d):{'unique_strict_variants':0,'best_keys':set()}for d in manifest['devices']}
for name,rec in unique.items():
    key=rec['root'];w,h,d=map(int,key.split('_'));p=rec['squares'];old=baseline[key]
    assert p.shape==(w*h+d,3) and np.isfinite(p).all()
    f=excess(p,w,h);gap=gaps(p);official=certify(p)
    assert gap>0 and official,(name,gap,official)
    improved=f<old-2e-7
    all_npz[name]=p
    if improved:
        strict_npz[name]=p
        if key not in best or f<best[key]['bloat']:best[key]={'bloat':f,'seed_bloat':old,'gain':old-f,'variant':name}
        for device in {v['device']for v in rec['worker_variants']}:
            per_device[str(device)]['unique_strict_variants']+=1;per_device[str(device)]['best_keys'].add(key)
    candidates[name]={'w':w,'h':h,'surplus':d,'bloat':f,'seed_bloat':old,
        'strict_improvement':improved,'minimum_gap':gap,'official_raw_and_roundtrip':official,
        'squares':p.tolist(),'worker_variants':rec['worker_variants'],'seed_provenance':provenance[key],
        'source':'lightningv08 public v21 FTMC; private resumed dual-T4 campaign'}
for device,info in per_device.items():
    info['distinct_improved_keys']=len(info.pop('best_keys'))
    s=statuses[device];elapsed=s.get('seconds') or search_elapsed
    info.update(core_trials=s.get('core_trials',0),accepted_events=s.get('accepted',0),
                core_trials_per_second=s.get('core_trials',0)/max(1,elapsed),
                cuda_seconds=s.get('cuda_seconds',0),worker_seconds=elapsed)
atom_npz('artifacts/campaign_gadgets.npz',all_npz)
atom_npz('artifacts/campaign_strict_gadgets.npz',strict_npz)
atomic_json('ftmc_candidates.json',candidates)
summary={'stage':'failed' if failures else 'complete','wall_seconds':time.monotonic()-started,
         'parallel_search_wall_seconds':search_elapsed,'bounded_worker_timeout':timed_out,'failures':failures,
         'candidate_variants':len(candidates),'strict_improved_variants':len(strict_npz),
         'distinct_improved_keys':len(best),'best_by_key':best,'per_device':per_device,
         'status':statuses,'preflight':preflight,'expected_device_hours':manifest['quota_expectation']['nominal_device_hours'],
         'note':'Strict gains are measured against the published+pilot+transposed incumbent at campaign start; full-puzzle composition remains required.'}
atomic_json('ftmc_summary.json',summary)
signal.alarm(0)
print(json.dumps(summary),flush=True)
if failures:raise RuntimeError('One or more FTMC workers failed; successful checkpoints and analysis were preserved.')
