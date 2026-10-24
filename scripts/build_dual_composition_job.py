#!/usr/bin/env python3
"""Prepare two bounded, isolated GPU adaptive-composition profiles; never launch."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    {'name': 'bins32_angles3', 'device': 0, 'bins': 32, 'degrees': [30,45,60]},
    {'name': 'bins16_angles7', 'device': 1, 'bins': 16, 'degrees': [15,22.5,30,45,60,67.5,75]},
    {'name': 'bins32_shifted3', 'device': 1, 'bins': 32, 'degrees': [22.5,45,67.5]},
    {'name': 'bins64_angles2', 'device': 1, 'bins': 64, 'degrees': [30,45]},
]
DEFAULT_PROFILES = ['bins32_angles3','bins16_angles7']

RUNTIME = r'''
import base64,copy,hashlib,io,json,os,shutil,subprocess,sys,tempfile,threading,time,zipfile
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
working=Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()
started=time.monotonic();deadline=started+CONFIG['wall_seconds']
print(json.dumps({'stage':'dual_composition_worker_started','utc':datetime.now(timezone.utc).isoformat(),
                  'wall_limit_seconds':CONFIG['wall_seconds'],'profiles':CONFIG['profiles']}),flush=True)
import cupy as cp
required_devices=1+max(profile['device']for profile in CONFIG['profiles'])
assert cp.cuda.runtime.getDeviceCount()>=required_devices,'Insufficient allocated CUDA devices'
payload=base64.b64decode(PAYLOAD);jobs=[]
def pump(process,log_path,label):
    with log_path.open('w') as log:
        for line in process.stdout:
            log.write(line);log.flush()
            print('['+label+'] '+line.rstrip(),flush=True)
for profile in CONFIG['profiles']:
    root=Path(tempfile.mkdtemp(prefix=profile['name']+'-',dir=working))
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for entry in archive.infolist():
            destination=root/entry.filename
            assert destination.resolve().is_relative_to(root.resolve())
            data=archive.read(entry);assert hashlib.sha256(data).hexdigest()==CONFIG['embedded_sha256'][entry.filename]
            destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
    config=copy.deepcopy(CONFIG)
    config.update(method='adaptive',bins=profile['bins'],preflight_bins=profile['bins'],degrees=profile['degrees'])
    config['gadget_paths']=[]
    (root/'composition_config.json').write_text(json.dumps(config,indent=2)+'\n')
    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=str(profile['device'])
    command=[sys.executable,'-u',str(root/'pipeline/driver.py'),'--config',str(root/'composition_config.json'),'--root',str(root)]
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,cwd=root,env=env)
    thread=threading.Thread(target=pump,args=(process,root/'composition.log',profile['name']),daemon=True);thread.start()
    jobs.append({'profile':profile,'root':root,'process':process,'thread':thread,'timed_out':False})
next_heartbeat=started+60
while any(job['process'].poll() is None for job in jobs):
    now=time.monotonic()
    if now>=deadline:
        for job in jobs:
            if job['process'].poll() is None:
                job['timed_out']=True;job['process'].kill()
        break
    if now>=next_heartbeat:
        print(json.dumps({'stage':'dual_composition_heartbeat','seconds':now-started,
                          'profiles':{j['profile']['name']:j['process'].poll() for j in jobs}}),flush=True)
        next_heartbeat=now+60
    time.sleep(.5)
merged={};origins={};results={};baseline=None
for job in jobs:
    process=job['process'];process.wait(timeout=30);job['thread'].join(timeout=5)
    root=job['root'];label=job['profile']['name'];destination=working/label
    if destination.exists():raise RuntimeError('Refuse to overwrite prior profile output')
    destination.mkdir()
    for path in sorted(root.glob('composition*')):
        if path.is_file() and path.suffix in ('.json','.log'):
            shutil.copyfile(path,destination/path.name)
    preflight_path=root/'composition_preflight.json';report_path=root/'composition_candidates.report.json'
    preflight=json.loads(preflight_path.read_text()) if preflight_path.exists() else {}
    report=json.loads(report_path.read_text()) if report_path.exists() else {}
    candidate_path=root/'composition_candidates.json'
    success=process.returncode==0 and not job['timed_out'] and preflight.get('passed') is True and candidate_path.is_file()
    coverage={}
    for group,value in report.get('groups',{}).items():
        detail=value.get('details',{}).get('adaptive',{})
        coverage[group]={'oriented_done':detail.get('oriented_done'),
                         'oriented_planned':detail.get('oriented_planned'),
                         'complete':detail.get('oriented_done')==detail.get('oriented_planned')}
    results[label]={'profile':job['profile'],'returncode':process.returncode,'timed_out':job['timed_out'],
                    'success':success,'coverage':coverage,'report':report,
                    'preflight':preflight,'output_directory':str(destination)}
    if success:
        baseline=root/'inputs/baseline.csv'
        for n,row in json.loads(candidate_path.read_text()).items():
            if n not in merged or Decimal(row['side'])<Decimal(merged[n]['side']):
                merged[n]=row;origins[n]=label
(working/'composition_candidates.json').write_text(json.dumps(merged)+'\n')
gain=None
if baseline:
    sys.path.insert(0,str(jobs[0]['root']/'pipeline'))
    from compose_gadgets import read_baseline,side
    import math
    base=read_baseline(baseline)
    gain=sum((side(base[int(n)])-float(row['side']))/math.sqrt(int(n))for n,row in merged.items())
summary={'configuration':CONFIG,'seconds':time.monotonic()-started,'profiles':results,
         'success':all(r['success'] for r in results.values()),'improvements':len(merged),
         'estimated_score_gain':gain,'winning_profile':origins,
         'baseline_sha256':CONFIG['baseline_sha256'],
         'coverage_note':'Incomplete extraction must be reported as budget-limited; it is not an exhaustive comparison.'}
(working/'dual_composition_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('configuration','profiles')}),flush=True)
if not summary['success']:raise RuntimeError('One or more bounded GPU profiles failed; certified successful-profile outputs were retained')
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--attached-inputs',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=1200.)
    parser.add_argument('--wall-seconds',type=float,default=1800.)
    parser.add_argument('--slug',default='sos54352/squares-broad-composition')
    parser.add_argument('--profiles',nargs='+',choices=[p['name']for p in PROFILES],
                        default=DEFAULT_PROFILES)
    args=parser.parse_args()
    if args.seconds<=0 or args.wall_seconds<=0 or args.wall_seconds>1800:
        parser.error('Positive search budgets and a maximum1800-second overall cap are required')
    if len(set(args.profiles))!=len(args.profiles):
        parser.error('A profile can only be selected once')
    selected=[p for p in PROFILES if p['name']in args.profiles]
    if len({p['device']for p in selected})!=len(selected):
        parser.error('Select at most one profile for each CUDA device')
    args.out.mkdir(parents=True,exist_ok=True)
    attached=json.loads(args.attached_inputs.read_text())
    attached['groups']={'all_certified_donors':list(attached.get('gadgets',{}))}
    descriptor=args.out/'attached-inputs.json';descriptor.write_text(json.dumps(attached,indent=2)+'\n')
    common=args.out/'common-build'
    command=[sys.executable,str(ROOT/'scripts/build_composition_job.py'),'--baseline',str(args.baseline),
             '--attached-inputs',str(descriptor),'--method','adaptive','--bins','32','--degrees','30','45','60',
             '--preflight-full-profile','--seconds',str(args.seconds),'--wall-seconds',str(args.wall_seconds),
             '--closure-seconds','0','--out',str(common),'--slug',args.slug]
    subprocess.run(command,check=True)
    tree=ast.parse((common/'search.py').read_text())
    config=ast.literal_eval(tree.body[0].value);payload=ast.literal_eval(tree.body[1].value)
    config['profiles']=[{**p,'table_bytes':32*32*64*len(p['degrees'])**2*(p['bins']+1)**2*8}
                        for p in selected]
    source='CONFIG = '+repr(config)+'\nPAYLOAD = '+repr(payload)+'\n'+RUNTIME
    compile(source,'search.py','exec')
    if len(source.encode())>=1000000:raise ValueError('Dual source exceeds Kaggle1MB limit')
    (args.out/'search.py').write_text(source)
    metadata=json.loads((common/'kernel-metadata.json').read_text())
    metadata['machine_shape']='NvidiaTeslaT4'
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (args.out/'job_manifest.json').write_text(json.dumps(config,indent=2)+'\n')
    report={'output':str(args.out),'script_bytes':len(source.encode()),
            'script_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'profiles':config['profiles'],'wall_seconds':args.wall_seconds,'launch_performed':False}
    (args.out/'build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
