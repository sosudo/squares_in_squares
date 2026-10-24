"""Build an offline FTMC pilot aimed at current-chain bottlenecks.

Source code, active crop arrays, certified baseline provenance and precomputed
targeting evidence are embedded. The full baseline CSV is not a runtime input:
this worker optimizes the embedded crops and does not compose complete puzzles.
Historical scalar-bloat winners are never substituted for active chain poses.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from ftmc_frontier_bank import build_frontier_bank
from ftmc_profile_guard import compatible_uses


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,default=ROOT/'artifacts/submission-safe.csv')
    ap.add_argument('--baseline-certificate',type=Path,default=ROOT/'artifacts/submission-safe-official.json')
    ap.add_argument('--active-dir',type=Path,default=ROOT/'artifacts/active-frontier')
    ap.add_argument('--pilot-results',type=Path,default=ROOT/'artifacts/ftmc-pilot-results')
    ap.add_argument('--source-dir',type=Path,default=ROOT/'vendor/lightning_ftmc')
    ap.add_argument('--baseline-source',default='sos54352/squares-certified-portfolio-source-export/2')
    ap.add_argument('--pilot-source',default='sos54352/squares-ftmc-pilot/1')
    ap.add_argument('--slug',default='sos54352/squares-active-frontier-pilot')
    ap.add_argument('--title',default='Squares Active Frontier Pilot')
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/active-frontier-job')
    ap.add_argument('--seconds',type=int,default=900)
    ap.add_argument('--replicas',type=int,default=128)
    ap.add_argument('--seeds',default='63013,73019')
    ap.add_argument('--grace-seconds',type=int,default=120)
    ap.add_argument('--wall-seconds',type=int,default=1500)
    ap.add_argument('--min-priority',type=float,default=1e-6)
    ap.add_argument('--max-code-bytes',type=int,default=1_000_000)
    a=ap.parse_args()
    seeds=[int(s)for s in a.seeds.split(',')]
    if len(seeds)!=2 or seeds[0]==seeds[1]:raise ValueError('Two distinct worker seeds required')
    if a.seconds<=0 or a.wall_seconds<a.seconds+a.grace_seconds+30:raise ValueError('Insufficient wall budget')
    for ref in [a.baseline_source,a.pilot_source]:
        fields=ref.split('/')
        if len(fields)!=3 or not fields[-1].isdigit():raise ValueError('Versioned notebook source required: '+ref)
    active=a.active_dir/'active_seed_variants.npz';priorities=a.active_dir/'active_priorities.json'
    targets=a.active_dir/'active_targets.json';baseline_hash=sha(a.baseline)
    certificate=json.loads(a.baseline_certificate.read_text())
    if certificate.get('sha256')!=baseline_hash or not certificate.get('valid') or certificate.get('invalid_count')!=0 or certificate.get('puzzles')!=1000:
        raise ValueError('A passing complete official certificate matching the local baseline is required')
    current_targets=json.loads(targets.read_text())
    needed={int(use['n'])for entry in current_targets.values()for use in entry['uses']}
    frame=pd.read_csv(a.baseline,usecols=['n','x','y','angle'])
    actual_bloat={}
    for n,g in frame[frame.n.isin(needed)].groupby('n'):
        poses=g[['x','y','angle']].to_numpy(float)
        if len(poses)!=int(n):raise ValueError('Incomplete target case '+str(n))
        extent=.5*(np.abs(np.cos(poses[:,2]))+np.abs(np.sin(poses[:,2])))
        side=float(np.max((poses[:,:2]+extent[:,None]).max(0)-(poses[:,:2]-extent[:,None]).min(0)))
        actual_bloat[int(n)]=side-math.isqrt(int(n))
    if set(actual_bloat)!=needed:raise ValueError('Missing current baseline target cases')
    current_priorities={}
    for key,entry in current_targets.items():
        priority=0.
        for use in entry['uses']:
            use['original_recipe_target_bloat']=use['target_bloat']
            use['target_bloat']=actual_bloat[int(use['n'])]
            use['campaign_baseline_sha256']=baseline_hash
            gain=max(0.,use['target_bloat']-max(entry['seed_bloat']-.01,use['partner_bloat']))/math.sqrt(int(use['n']))
            use['single_stage_hypothetical_gain']=gain;priority+=gain
        entry['hypothetical_gain']=priority;current_priorities[key]=priority
    bank,variants,provenance,resume,weights,review=build_frontier_bank(active,[],current_priorities,current_targets,baseline_hash,a.min_priority)
    if resume:raise AssertionError('Historical archives must not be resumed into active families')
    profiles={}
    for key,p in bank.items():
        w,h,d=map(int,key.split('_'));uses=compatible_uses(p,w,h,review['targets'])
        if not uses:raise ValueError('Active seed failed its own recorded support profile: '+key)
        profiles[key]=uses
    data={}
    for path in sorted(a.source_dir.rglob('*')):
        if not path.is_file()or '__pycache__'in path.parts:continue
        name=str(path.relative_to(a.source_dir));payload=path.read_bytes()
        if name.endswith('.py'):compile(payload,name,'exec')
        data[name]=payload
    for name in ['ftmc_seed_bank.py','ftmc_frontier_bank.py','ftmc_profile_guard.py','ftmc_guarded_worker.py']:
        data[name]=(ROOT/'experiments'/name).read_bytes();compile(data[name],name,'exec')
    data['active_bank.npz']=active.read_bytes()
    data['active_priorities.json']=json.dumps(current_priorities,indent=2).encode()
    data['active_targets.json']=json.dumps(current_targets,indent=2).encode()
    data['active_manifest.json']=(a.active_dir/'active_manifest.json').read_bytes()
    data['active_seed_validation.json']=(a.active_dir/'active_seed_validation.json').read_bytes()
    source_provenance=[
        {'basename':'submission.csv','destination':'current_baseline.csv','sha256':baseline_hash,
         'source':a.baseline_source,'purpose':'Local certified portfolio used to precompute embedded targets; not required at runtime'},
        {'basename':'examples.npz','destination':'historical_examples.npz','sha256':sha(a.pilot_results/'examples.npz'),
         'source':a.pilot_source,'purpose':'Historical provenance only; not an input to active search'},
        {'basename':'worker0_gadgets.npz','destination':'historical_worker0_gadgets.npz',
         'sha256':sha(a.pilot_results/'artifacts/worker0_gadgets.npz'),
         'source':a.pilot_source,'purpose':'Historical provenance only; excluded from active worker resume'}]
    data['baseline_provenance.json']=json.dumps({
        'baseline_sha256':baseline_hash,'baseline_bytes':a.baseline.stat().st_size,
        'official_certificate_sha256':sha(a.baseline_certificate),
        'official_certificate_summary':{k:certificate[k]for k in ['metric_version','metric_sha256','mpmath_version','pandas_version','max_n','rows','puzzles','score','valid','invalid_count']},
        'source_references':source_provenance,
        'runtime_dependency':'None: the active crop coordinates and numerical target thresholds are embedded and independently hashed.'},indent=2).encode()
    manifest={'source':'lightningv08/squares-in-squares-cuda-packing-search','source_version':21,
        'source_license':'Apache-2.0 with retained notices','frontier_mode':'active_chains','profile_guard':True,
        'profile_guard_description':'A/B: GPU0 adapter requires all recorded active separator profiles before incumbent update, retaining certified incompatible results separately. GPU1 uses unchanged upstream admission. Public solver/metric sources unchanged.',
        'profile_bins':16,'baseline_sha256':baseline_hash,
        'active_recipe_baseline_sha256':json.loads(data['active_manifest.json'])['baseline_sha256'],
        'active_seed_types':len(bank),'min_priority':a.min_priority,
        'targeting_note':'Priorities are hypothetical gain from a .01 bloat reduction holding partners fixed, not achieved leaderboard gain.',
        'devices':[0,1],'gadget_ids':[],'resume_files':[],'historical_resume_disabled':True,
        'search_seconds':a.seconds,'grace_seconds':a.grace_seconds,'wall_seconds':a.wall_seconds,
        'replicas':a.replicas,'device_configs':{str(d):{'device':d,'replicas':a.replicas,'seed':s,
                'source_rng_seed':20261024+s+d*19937,'search_seconds':a.seconds,'resume_files':[],
                'profile_guard':d==0,'arm':'all-active-profiles'if d==0 else 'unrestricted-active-seeds'}for d,s in enumerate(seeds)},
        'quota_expectation':{'nominal_search_wall_hours':a.seconds/3600,'nominal_device_hours':2*a.seconds/3600,
                'hard_wall_hours':a.wall_seconds/3600,'hard_device_hours':2*a.wall_seconds/3600,
                'note':'Arithmetic device-hours; inspect actual Kaggle quota accounting separately.'},
        'slug':a.slug,'input_attachments':[],'source_provenance':source_provenance,
        'removed_unused_runtime_inputs':'v1 required audit-only CSV/examples/checkpoint mounts before search. v2 embeds certified provenance and targets, requiring no external runtime input.',
        'embedded_sha256':{name:hashlib.sha256(blob).hexdigest()for name,blob in data.items()}}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as z:
        for name,blob in data.items():
            if b'KGAT_'in blob:raise ValueError('Credential-shaped content forbidden in '+name)
            z.writestr(name,blob)
    runtime=(ROOT/'experiments/ftmc_campaign_runtime.py').read_text()
    script='# Private active-frontier FTMC pilot. No credentials embedded.\nCONFIG = '+repr(manifest)+'\nPAYLOAD = '+repr(base64.b64encode(buf.getvalue()).decode())+'\n'+runtime
    compile(script,'search.py','exec');size=len(script.encode())
    if size>=a.max_code_bytes:raise ValueError(f'Source {size} bytes must be below {a.max_code_bytes}')
    metadata={'id':a.slug,'title':a.title,'code_file':'search.py','language':'python','kernel_type':'script',
        'is_private':True,'enable_gpu':True,'enable_internet':False,'enable_tpu':False,'dataset_sources':[],
        'kernel_sources':[],'competition_sources':['squares-in-squares'],
        'machine_shape':'NvidiaTeslaT4'}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'search.py').write_text(script)
    (a.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (a.out/'job_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (a.out/'targeting_review.json').write_text(json.dumps({**review,'validated_seed_profiles':profiles,'code_bytes':size,'launched':False},indent=2)+'\n')
    print(json.dumps({'built':str(a.out),'code_bytes':size,'active_types':len(bank),'devices':[0,1],
                      'seconds_per_device':a.seconds,'replicas':a.replicas,'input_sources':metadata['kernel_sources'],
                      'historical_resume':False,'all_active_profile_checks_passed':True,'launched':False}))


if __name__=='__main__':main()
