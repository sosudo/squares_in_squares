#!/usr/bin/env python3
"""Bounded local aspect continuation at the n299 dual cage and n335 kink.

The original whole-case stage adapter is frozen with its scalar-band discard
removed. Every valid intermediate is retained before the ALM45 rigid release.
Nonzero-aspect states are never exported as unit-square candidates.
"""
from __future__ import annotations
import argparse
from collections import Counter
import inspect
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_full_local_campaign as full
from fq_active_pilot import digest
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha

ROOT=Path(__file__).resolve().parents[1]
RELEASE=['--loosen','1','--outer','45','--pit','100','--flip-top','16']


def retaining_stage_source():
    text=inspect.getsource(full.run_stage)
    old='if q is None or side(q) > original_side+.005:'
    if text.count(old)!=1:raise ValueError('Unexpected inherited band condition')
    text=text.replace(old,'if q is None:')
    if text.count("status='outside-near-best-band'")!=1:raise ValueError('Unexpected inherited status')
    return text.replace("status='outside-near-best-band'","status='failed-clearance'")


def inherited_group_run(command,capture_output=True,text=True,timeout=None):
    # Native FQ is a single process. Inherit the supervised campaign group so
    # even the outer kill reaches it; subprocess.run also kills it on signals.
    return subprocess.run(command,capture_output=capture_output,text=text,timeout=timeout)


def cage_selection(p,n,count):
    if n==299:seeds=[112,127,276,277];kind='mapped_dual_cage'
    else:
        edges=full.contact_edges(p,range(n),tolerance=.035)
        angle=(p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
        choices=[(abs((angle[i]-angle[j]+np.pi/4)%(np.pi/2)-np.pi/4),i,j)for i,j in edges
                 if abs(angle[i])>.05 and abs(angle[j])>.05]
        if not choices:raise ValueError('No actual tilted kink contact')
        _,i,j=max(choices);seeds=[int(i),int(j)];kind='largest_tilt_difference_contact'
    center=p[seeds,:2].mean(0);free=list(seeds)
    for index in np.argsort(((p[:,:2]-center)**2).sum(1),kind='stable'):
        if int(index)not in free:free.append(int(index))
        if len(free)>=count:break
    frozen=sorted(set(range(n))-set(free))
    return np.array(frozen),{'kind':kind,'source_seed_ids':seeds,'center':center.tolist(),
        'free_indices':free,'frozen_indices':frozen,'free_count':len(free)}


def run(args):
    started=time.monotonic();deadline=started+args.seconds-5
    signal.signal(signal.SIGTERM,full.alarm)
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    for name in('source','trials','retained'): (out/name).mkdir()
    pointer=json.loads(args.portfolio.read_text());source=Path(pointer['safe']['path'])
    if digest(source)!=pointer['safe']['sha256']:raise ValueError('Current certified source changed')
    official=Path(pointer['safe']['official_report'])
    if digest(official)!=pointer['safe']['official_report_sha256']:raise ValueError('Official source proof changed')
    official_data=json.loads(official.read_text())
    if not(official_data['sha256']==pointer['safe']['sha256'] and official_data['valid']
           and official_data['invalid_count']==0 and official_data['puzzles']==1000
           and official_data['metric_sha256']==full.fq.OFFICIAL_SHA256):
        raise ValueError('Complete official source certificate mismatch')
    poses=full.read_baseline(source);poses={n:full.normalize(poses[n])for n in(299,335)}
    lengths={n:full.side(p)for n,p in poses.items()}
    binary=out/'fq';shutil.copyfile(args.binary,binary);binary.chmod(0o500)
    stage_path=out/'source/retaining_run_stage.py';stage_path.write_text(retaining_stage_source());stage_path.chmod(0o444)
    namespace=dict(full.__dict__);namespace['grouped_run']=inherited_group_run
    exec(compile(stage_path.read_text(),str(stage_path),'exec'),namespace);stage=namespace['run_stage']
    sources=[Path(__file__),Path(full.__file__),ROOT/'experiments/fq_active_pilot.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_coherent_clusters.py',
        ROOT/'experiments/fq_local_soft_campaign.py',ROOT/'experiments/compose_gadgets.py',
        ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py']
    for path in sources:
        dest=out/'source'/path.name;shutil.copyfile(path,dest);dest.chmod(0o444)
    prior_path=ROOT/'artifacts/fq-full-local-v1/manifest.json';prior=json.loads(prior_path.read_text())
    if 299 in prior['target_order'] or 335 in prior['target_order']:raise ValueError('Earlier full local campaign already covered this case')
    structural_path=ROOT/'artifacts/fq-full-structural-v1/manifest.json'
    structural=json.loads(structural_path.read_text())
    if any('--soft' in str(value) for value in structural['modes']):
        raise ValueError('Earlier structural experiment used a soft mode; review coverage first')
    manifest={'source_csv':str(source),'source_csv_sha256':digest(source),'source_official_report_sha256':digest(official),
        'binary_sha256':digest(binary),'fq_source_commit':'659ee62e4a9d39542a1146e8b011cc3ab6407ede','source_license':'MIT; Evan Daniel',
        'source_hashes':{str(path):digest(path)for path in sources},'retaining_stage_sha256':digest(stage_path),
        'retaining_stage_modification':'Remove only scalar near-best discard; no geometry/trace gate change. Native inherits the campaign process group.',
        'previous_full_local_manifest_sha256':digest(prior_path),'previous_full_local_cases':prior['target_order'],
        'previous_structural_manifest_sha256':digest(structural_path),'previous_structural_options':structural['modes'],
        'cases':[299,335],'reference_geometry_sha256':{str(n):geometry_sha(p)for n,p in poses.items()},
        'reference_sides':lengths,'seconds':args.seconds,'workers':1,'maximum_composites':24,
        'local_inclusive_cap_seconds':8.,'release_inclusive_cap_seconds':6.,'release_options':RELEASE,
        'matrix':'n299 dual cage:2seeds x40/64free x.3/.6aspect x1.001/1.005hold; n335 kink:1seed x same8modes.',
        'retention':'Every fully certified intermediate and release, including scalar-worse poses, published immutably before next stage.'}
    atomic_json(out/'manifest.json',manifest);atomic_npz(out/'reference.npz',{str(n):p for n,p in poses.items()})
    records=[];donors={};proofs={};best=dict(lengths);status='running'
    def retain(record,q):
        if q is None:return
        n=len(q);name=str(n)+'__dual_cage_'+geometry_sha(q);donors[name]=q;proofs[name]=record['certificate']
        if record['side']<best[n]:best[n]=record['side']
        target=out/'retained'/(geometry_sha(q)+'.npz')
        if not target.exists():
            atomic_npz(target,{name:q});target.chmod(0o444)
            atomic_json(target.with_suffix('.json'),{'archive_key':name,'geometry_sha256':geometry_sha(q),
                'archive_sha256':digest(target),'record':record,'manifest_sha256':digest(out/'manifest.json')})
            target.with_suffix('.json').chmod(0o444)
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',proofs)
        record['retained_key']=name
    def save(record,q):
        retain(record,q);records.append(record);atomic_json(out/'results.json',records)
    try:
        # Rigid reproduction is a genuine native/control path, not a code-only check.
        control,q=stage(poses[299],lengths[299],'rigid_control',['--no-alm','--loosen','1','--pit','40','--flip-top','0'],
            2995100,binary.resolve(),(out/'trials').resolve(),6.,deadline)
        save(control,q)
        if q is None or control['side']>lengths[299]+1e-6:raise ValueError('Actual n299 rigid control failed')
        frozen,selection=cage_selection(poses[299],299,40)
        options=full.soft_options(.3,1.001,frozen)
        control_soft,qsoft=stage(poses[299],lengths[299],'soft_control',options,2995101,binary.resolve(),
            (out/'trials').resolve(),8.,deadline)
        control_soft['selection']=selection;save(control_soft,qsoft)
        if(qsoft is None or not control_soft.get('rigid_return_trace',{}).get('valid')
                or control_soft['fq'].get('frozen_dmax',float('inf'))>1e-8):
            raise ValueError('Actual local-aspect/zero-return/frozen control failed')
        atomic_json(out/'controls.json',{'passed':True,'rigid_record_geometry':control['geometry_sha256'],
            'soft_record_geometry':control_soft['geometry_sha256'],'soft_trace':control_soft['rigid_return_trace'],
            'frozen_native_dmax':control_soft['fq']['frozen_dmax'],'algorithm_frozen_guard':1e-8,
            'strict_geometry_gates':'Unchanged interval+officialraw/defaultpandas, independently of the neighborhood guard.'})
        print(json.dumps({'stage':'dual_cage_controls_passed','rigid_side':control['side'],'soft_side':control_soft['side']}),flush=True)
        configurations=list(itertools.product((40,64),(.3,.6),(1.001,1.005)))
        jobs=[(299,config,rep)for rep in(0,1)for config in configurations]
        jobs.extend((335,config,0)for config in configurations)
        for index,(n,(count,amplitude,hold),rep)in enumerate(jobs):
            if time.monotonic()>=deadline-2:status='deadline';break
            p=poses[n];frozen,selection=cage_selection(p,n,count);seed=2995200+index
            local_options=full.soft_options(amplitude,hold,frozen)
            record,q=stage(p,lengths[n],'local_'+str(index),local_options,seed,binary.resolve(),
                (out/'trials').resolve(),8.,deadline)
            record.update(selection=selection,amplitude=amplitude,hold=hold,replicate=rep,composite=index)
            if q is not None:
                record['geometry_change']=full.displacement(p,q,selection)
                drift=record['fq'].get('frozen_dmax',float('inf'))
                record['frozen_neighborhood_guard']={'limit':1e-8,'reported':drift,'passed':drift<=1e-8}
            save(record,q)
            if q is not None and record['frozen_neighborhood_guard']['passed'] and time.monotonic()<deadline-1:
                released,final=stage(q,lengths[n],'release_'+str(index),RELEASE,seed,binary.resolve(),
                    (out/'trials').resolve(),6.,deadline)
                released.update(composite=index,source_local_geometry_sha256=geometry_sha(q),selection=selection)
                save(released,final)
            print(json.dumps({'stage':'dual_cage_trial','completed':index+1,'n':n,'local_status':record['status'],
                'best_side':best[n],'seconds':time.monotonic()-started}),flush=True)
        if status=='running':status='complete'
    except Exception:status='failed';raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',proofs);atomic_json(out/'results.json',records)
        unchanged=(all(digest(p)==v for p,v in manifest['source_hashes'].items())
                   and digest(source)==manifest['source_csv_sha256'] and digest(binary)==manifest['binary_sha256'])
        summary={'status':status if unchanged else'source_changed_quarantine','seconds':time.monotonic()-started,
            'limit_seconds':args.seconds,'stages':len(records),'certified_poses':len(donors),'reference_sides':lengths,'best_sides':best,
            'score_gain':sum(max(0.,lengths[n]-best[n])/math.sqrt(n)for n in best),
            'statuses':dict(Counter(r['status']for r in records)),'source_hashes_unchanged':unchanged,
            'manifest_sha256':digest(out/'manifest.json'),'donors_sha256':digest(out/'donors.npz'),
            'certificates_sha256':digest(out/'certificates.json'),'results_sha256':digest(out/'results.json'),
            'full_portfolio_merge_performed':False}
        atomic_json(out/'summary.json',summary);print(json.dumps({'stage':'dual_cage_complete',**summary}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portfolio',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=290.)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if not 1<args.seconds<=295:raise ValueError('Total process bound must remain below300seconds')
    if args.child:return run(args)
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child'],start_new_session=True)
    try:raise SystemExit(child.wait(timeout=args.seconds+3))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=2)
        atomic_json(args.out/'supervisor_timeout.json',{'status':'outer_limit','seconds':args.seconds+3});raise SystemExit(2)


if __name__=='__main__':main()
