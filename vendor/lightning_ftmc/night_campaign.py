"""Checkpointed public Kaggle T4 campaign; no local numerical execution."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import argparse,json,time,shutil,subprocess,sys,hashlib,datetime
from pathlib import Path
import numpy as np

def write_json(path,value):
    p=Path(path);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value,indent=2),encoding='utf8');t.replace(p)
def snapshot_npz(path,bank):
    p=Path(path);t=p.with_suffix(p.suffix+'.tmp')
    with t.open('wb')as f:np.savez_compressed(f,**bank)
    t.replace(p)
def execute(args,name,timeout=1800,env=None,required=True):
    start=time.perf_counter()
    with open(name+'.log','w')as log:
        p=subprocess.run([sys.executable,'-u',*map(str,args)],stdout=log,stderr=subprocess.STDOUT,timeout=timeout,env=env)
    if p.returncode and required:raise RuntimeError(name+' failed:\n'+Path(name+'.log').read_text(errors='replace')[-5500:])
    print(json.dumps(dict(stage=name,exit_code=p.returncode,seconds=time.perf_counter()-start,log=name+'.log')),flush=True)
    return p.returncode
def certify_csv(csv,tag):
    import pandas as pd
    execute(['research/validate_candidate.py',csv,'research/'+tag+'_validation.json'],tag+'_raw',timeout=600)
    pd.read_csv(csv).to_csv('roundtrip.csv',index=False,float_format='%.17g')
    execute(['research/validate_candidate.py','roundtrip.csv','research/'+tag+'_roundtrip.json'],tag+'_rt',timeout=600)
    raw=json.loads(Path('research/'+tag+'_validation.json').read_text());rt=json.loads(Path('research/'+tag+'_roundtrip.json').read_text())
    assert not raw['rejected']and not rt['rejected']and abs(raw['score']-rt['score'])<1e-10
    return raw
def latest_status(device):
    p=Path(f'research/worker{device}_status.json')
    try:return json.loads(p.read_text())if p.exists()else {}
    except (OSError,json.JSONDecodeError):return {}
def launch(device,seconds,cycle):
    log=open(f'worker{device}_cycle{cycle}.log','w')
    p=subprocess.Popen([sys.executable,'-u','gpu_ftmc_refill.py','--device',str(device),'--seconds',str(seconds),'--replicas','192','--seed',str(cycle*10007)],stdout=log,stderr=subprocess.STDOUT)
    return p,log
def heartbeat(start,phase,processes):
    workers={}
    for device,(p,_)in processes.items():
        s=latest_status(device);workers[str(device)]={k:s.get(k)for k in ['seconds','batches','core_trials','refill_success','full_quenches','accepted','cuda_seconds','last_batch']};workers[str(device)]['process_running']=p.poll()is None;workers[str(device)]['exit_code']=p.poll()
    r=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seconds=time.perf_counter()-start,phase=phase,workers=workers)
    write_json('research/night_heartbeat.json',r)
    print(json.dumps({**r,'workers':{k:{a:b for a,b in v.items()if a!='last_batch'}for k,v in workers.items()}}),flush=True)
def composition(index,device,baseline,atlas,current):
    donors={}
    paths=[Path('artifacts/night_seed_gadgets.npz')]+list(Path('artifacts').glob('worker*_gadgets.npz'))
    for path in paths:
        if path.exists():
            with np.load(path)as z:
                for k in z.files:donors[path.stem+'_'+k]=z[k]
    snapshot_npz('artifacts/tip_frontier1_gadgets.npz',donors)
    shutil.copyfile(atlas/'pressure_crystal_gadgets.npz','artifacts/crystal_polished1_gadgets.npz')
    tag=f'night_compose_{index}';env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=str(device)
    try:
        rc=execute(['gpu_adaptive_seams.py','--baseline',baseline,'--seconds','900','--bins','40','--tag',tag],tag,timeout=1500,env=env,required=False)
        if rc:
            print(Path(tag+'.log').read_text(errors='replace')[-3000:],flush=True)
            rc=execute(['gpu_adaptive_seams.py','--baseline',baseline,'--seconds','600','--bins','32','--tag',tag],tag+'_fallback',timeout=1200,env=env,required=False)
        if rc:return current,None
    except subprocess.TimeoutExpired:
        print('Composition time budget exhausted; previous certified CSV preserved.',flush=True);return current,None
    execute(['research/top1-refresh/admit.py','--baseline',baseline,'--sources',f'artifacts/{tag}_packings.npz','--include-new','--tag',tag],tag+'_admit',timeout=900)
    candidate=Path(f'artifacts/{tag}_submission.csv');valid=certify_csv(candidate,tag)
    if valid['score']<current['score']-1e-11:
        temporary=Path('submission.csv.tmp');shutil.copyfile(candidate,temporary);temporary.replace('submission.csv')
        shutil.copyfile(candidate,'artifacts/night_current_submission.csv');current=valid
    stage=json.loads(Path(f'research/{tag}.json').read_text());write_json('research/night_current.json',current)
    print(json.dumps(dict(stage='certified portfolio checkpoint',cycle=index,score=current['score'],gain=stage['gain'],sha256=current['sha256'])),flush=True)
    return current,stage

def main(hours=6.):
    start=time.perf_counter();budget=hours*3600;Path('artifacts').mkdir(exist_ok=True);Path('research').mkdir(exist_ok=True)
    import cupy as cp
    devices=cp.cuda.runtime.getDeviceCount();names=[]
    for device in range(devices):
        name=cp.cuda.runtime.getDeviceProperties(device)['name'];name=name.decode()if isinstance(name,bytes)else name;names.append(name)
    assert devices>=1 and all('T4'in n for n in names),('T4 required by this experiment',names)
    print(json.dumps(dict(stage='T4 hardware confirmed',devices=devices,names=names,search_hours=hours)),flush=True)
    atlas=next(Path('/kaggle/input').rglob('pressure_manifest.json')).parent
    examples=next(Path('/kaggle/input').rglob('gadgets_39_and_baselines.npz'));external=examples.parent/'submission.csv'
    original=atlas/'pressure_submission.csv';assert hashlib.sha256(original.read_bytes()).hexdigest()=='8692aac5710cd93ca5b2dc648007a8295be3a8364571d26408abf8a088e98d8d'
    shutil.copyfile(original,'submission.csv')
    sources=dict(previous_version=17,previous_score=22.360587196217377,previous_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),deotte_dataset='cdeotte/squares-in-squares-22-315-data',deotte_dataset_version=2,deotte_submission_sha256=hashlib.sha256(external.read_bytes()).hexdigest(),example_archive_sha256=hashlib.sha256(examples.read_bytes()).hexdigest(),hardware=names,search_hours=hours)
    write_json('research/night_sources.json',sources)
    execute(['research/top1-refresh/admit.py','--baseline',original,'--sources',external,'--include-new','--tag','night_start'],'night_start_admit',timeout=900)
    baseline=Path('artifacts/night_start_submission.csv');current=certify_csv(baseline,'night_start');shutil.copyfile(baseline,'submission.csv');shutil.copyfile(baseline,'artifacts/night_current_submission.csv');write_json('research/night_current.json',current)
    print(json.dumps(dict(stage='certified public starting point',score=current['score'],sha256=current['sha256'])),flush=True)
    for name in ['fault_source_donors.npz','fault_source_labels.json']:shutil.copyfile(atlas/name,Path('artifacts')/name)
    try:execute(['gpu_ftmc_refill.py','--library','--device','0','--baseline',baseline,'--examples',examples],'night_crop_library',timeout=1500)
    except (RuntimeError,subprocess.TimeoutExpired):
        assert Path('artifacts/night_seed_gadgets.npz').exists();print('Using published gadget examples; crop extraction log retained.',flush=True)
    processes={};stages=[];cycle=0;deadline=start+budget-1500
    if devices>=2:
        processes[0]=launch(0,max(60,deadline-time.perf_counter()),cycle)
    while time.perf_counter()<deadline:
        device=1 if devices>=2 else 0;remaining=deadline-time.perf_counter();chunk=min(240 if cycle==0 else 1200,max(0,remaining-1500))
        if chunk<60:break
        processes[device]=launch(device,chunk,cycle);worker,log=processes[device]
        while worker.poll()is None:
            heartbeat(start,'core search',processes)
            # A failed independent worker must be visible, not silently idle.
            if devices>=2 and processes[0][0].poll()not in [None,0]:
                raise RuntimeError('GPU0 worker failed; inspect worker0_cycle0.log')
            time.sleep(30)
        log.close()
        if worker.returncode:
            tail=Path(f'worker{device}_cycle{cycle}.log').read_text(errors='replace')[-7000:]
            raise RuntimeError('GPU worker failed:\n'+tail)
        heartbeat(start,'CUDA recomposition',processes)
        current,stage=composition(cycle,device,'artifacts/night_current_submission.csv',atlas,current)
        if stage:stages.append(stage)
        cycle+=1
        write_json('research/night_campaign.json',dict(sources=sources,current=current,stages=stages,seconds=time.perf_counter()-start))
    for device,(p,log)in processes.items():
        if p.poll()is None:
            try:p.wait(timeout=max(1,deadline-time.perf_counter()+120))
            except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=30)
        log.close()
    current,stage=composition(cycle,0,'artifacts/night_current_submission.csv',atlas,current)
    if stage:stages.append(stage)
    final=certify_csv('submission.csv','night_final');assert final['score']<=current['score']+1e-10
    result=dict(sources=sources,starting_score=json.loads(Path('research/night_start_validation.json').read_text())['score'],final=final,stages=stages,seconds=time.perf_counter()-start,workers={str(d):latest_status(d)for d in range(min(devices,2))})
    write_json('research/night_campaign.json',result);print(json.dumps(dict(stage='campaign complete',score=final['score'],seconds=result['seconds'],sha256=final['sha256'])),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--hours',type=float,default=6.);a=ap.parse_args();main(a.hours)
