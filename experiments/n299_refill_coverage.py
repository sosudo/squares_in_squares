#!/usr/bin/env python3
"""A bounded matched 4-phase/9-phase finite-candidate coverage ablation."""
from __future__ import annotations
import argparse
import itertools
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import warnings
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import n299_direct_refill as original
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest


def augment_pool(old_pool,core,L,hints,depth):
    extra=np.vstack([hints[:,:2]-[dx,dy]for dx,dy in itertools.product((0.,depth/2,depth),repeat=2)])
    extra=extra[(extra>=.5).all(1)&(extra<=L-.5).all(1)]
    extra=extra[original.refill.sat_gaps(extra,core)>=0.]
    both=np.vstack((old_pool,extra));_,ids=np.unique(np.round(both,12),axis=0,return_index=True)
    result=both[np.sort(ids)]
    old_bytes={row.tobytes()for row in old_pool};new_bytes={row.tobytes()for row in result}
    if not old_bytes<=new_bytes:raise ValueError('Nine-phase pool lost an old exact candidate')
    return result


def run(args):
    started=time.monotonic();deadline=started+args.seconds-3
    signal.signal(signal.SIGALRM,lambda a,b:(_ for _ in()).throw(original.TrialLimit()))
    signal.setitimer(signal.ITIMER_REAL,args.seconds-1)
    args.out.mkdir(parents=True,exist_ok=False);out=args.out
    source_manifest=json.loads((args.source/'manifest.json').read_text())
    p=np.load(args.source/'reference.npz')['299']
    if geometry_sha(p)!=source_manifest['reference_geometry_sha256']:raise ValueError('Reference array changed')
    mask=abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018;core=p[mask];up=p[~mask];ids=np.flatnonzero(mask)
    central=np.array([int(np.flatnonzero(ids==i)[0])for i in(276,277)]);L0=original.side(p)
    zero={'global_angle_degrees':0.,'central_transverse_shift':0.,'central_cant_degrees':0.}
    cases=[('exact_identity',0.,zero,True),('near_zero_identity',1e-8,zero,False),
        ('unchanged_angle_shrink',.002,zero,False),
        ('lower_angle_minus_shift',.002,{'global_angle_degrees':-.25,'central_transverse_shift':-.06,'central_cant_degrees':0.},False),
        ('lower_angle_plus_shift',.002,{'global_angle_degrees':-.25,'central_transverse_shift':.06,'central_cant_degrees':0.},False)]
    paths=[Path(__file__),Path(original.__file__),Path(original.refill.__file__)]
    manifest={'source_run':str(args.source),'source_manifest_sha256':digest(args.source/'manifest.json'),
        'source_summary_sha256':digest(args.source/'summary.json'),'source_hashes':{str(p):digest(p)for p in paths},
        'seconds':args.seconds,'workers':1,'cases':[{'name':n,'depth':d,'spec':s,'unchanged_core':u}for n,d,s,u in cases],
        'comparison':'Old four-phase pool is an exact byte subset of each new nine-phase pool; all other geometry and conflict rules match.',
        'scope':'Only a proved finite graph optimum is an exact finite-set capacity. No continuous infeasibility claim.'}
    atomic_json(out/'manifest.json',manifest)
    original_milp=original.refill.milp
    def one_thread(*a,**kw):
        options=dict(kw.get('options')or{});options['threads']=1;kw['options']=options
        with warnings.catch_warnings():warnings.simplefilter('ignore');return original_milp(*a,**kw)
    original.refill.milp=one_thread
    records=[];geometries={};proofs={};status='running'
    try:
        for name,depth,spec,unchanged in cases:
            if time.monotonic()>=deadline:raise original.TrialLimit()
            L=L0-depth
            if unchanged:actual=core.copy();core_info={'unchanged_source_core':True}
            else:actual,core_info=original.core_lp(original.changed_core(core,central,spec,depth),L,deadline)
            if actual is None:raise ValueError('Matched core LP failed before coverage comparison')
            atomic_npz(out/(name+'-core.npz'),{'tilted43':actual})
            pool,_=original.candidates(actual,L,up,depth);expanded=augment_pool(pool,actual,L,up,depth)
            case={'name':name,'target_depth':depth,'box_side':L,'core_info':core_info,
                  'core_geometry_sha256':geometry_sha(actual),'modes':{}}
            for mode,xy in(('four_phase',pool),('nine_phase',expanded)):
                if time.monotonic()>=deadline:raise original.TrialLimit()
                selected,info=original.refill.maximum_independent_set(original.refill.conflict_graph(xy,margin=0.),time_limit=.2)
                q=np.vstack((actual,np.column_stack((xy[selected],np.zeros(len(selected))))))
                key=name+'__'+mode;geometries[key]=q
                fixed,certificate=original.gate(q);proofs[key]=certificate
                result={'candidate_count':len(xy),'uprights_selected':len(selected),'actual_total_count':len(q),
                    'finite_exact_upper_bound':len(selected)if info['finite_set_optimal']else None,
                    'finite_optimal':info['finite_set_optimal'],'info':info,
                    'geometry_valid':fixed is not None,'geometry_actual_n':len(q),
                    'recovers_299_count':len(selected)>=256,'source_array_sha256':geometry_sha(q)}
                if fixed is not None:
                    geometries[key+'__certified']=fixed;result['certified_side']=original.side(fixed)
                    result['certified_geometry_sha256']=geometry_sha(fixed)
                case['modes'][mode]=result
                atomic_npz(out/'geometries.npz',geometries);atomic_json(out/'geometry_proofs.json',proofs)
            old=case['modes']['four_phase']['uprights_selected'];new=case['modes']['nine_phase']['uprights_selected']
            case.update(recovered_slots=new-old,remaining_shortfall=max(0,256-new),
                materially_improved_changed_core=(depth>=.002 and(new>=256 or new-old>=max(5,int(np.ceil((256-old)/2))))))
            records.append(case);atomic_json(out/'results.json',records)
            print(json.dumps({'stage':'coverage_case','name':name,'old':old,'new':new,'seconds':time.monotonic()-started}),flush=True)
        status='complete'
    except original.TrialLimit:status='hard_deadline'
    except Exception:status='failed';raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);original.refill.milp=original_milp
        atomic_npz(out/'geometries.npz',geometries);atomic_json(out/'geometry_proofs.json',proofs);atomic_json(out/'results.json',records)
        summary={'status':status,'seconds':time.monotonic()-started,'limit_seconds':args.seconds,'completed_cases':len(records),
            'corrected_pass_warranted':status=='complete'and any(r['materially_improved_changed_core']for r in records),
            'source_hashes_unchanged':all(digest(p)==v for p,v in manifest['source_hashes'].items()),
            'manifest_sha256':digest(out/'manifest.json'),'results_sha256':digest(out/'results.json'),
            'geometries_sha256':digest(out/'geometries.npz'),'geometry_proofs_sha256':digest(out/'geometry_proofs.json'),
            'warning':'Partial counts such as282 are geometry diagnostics, not299-square candidates.'}
        atomic_json(out/'summary.json',summary);print(json.dumps({'stage':'coverage_complete',**summary}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=original.ROOT/'artifacts/n299-direct-refill-v1')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=55.)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if not 1<args.seconds<=57:raise ValueError('Outer process bound must remain below60seconds')
    if args.child:return run(args)
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child'],start_new_session=True)
    try:raise SystemExit(child.wait(timeout=args.seconds+2))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=1)
        atomic_json(args.out/'supervisor_timeout.json',{'status':'outer_limit','seconds':args.seconds+2});raise SystemExit(2)


if __name__=='__main__':main()
