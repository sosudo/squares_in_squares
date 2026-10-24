#!/usr/bin/env python3
"""Matched position/bond-release LP ablations for the frozen n299 strip.

The completed original scan is unchanged. This wrapper changes only the
variable tying and explicit fixed angles, retaining its wall/SAT constraints.
Full independent and official raw/default-pandas gates decide every donor.
"""
from __future__ import annotations
import argparse
import copy
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

import period5_column_lp as base
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest
from extract_broad_active_frontier import certify_array


_ordinary_mapping=base.mapping


def preset_mapping(t,angle_offsets,phase_offsets):
    C,offset,angles,z,warm=_ordinary_mapping(t,angle_offsets,phase_offsets)
    if 'upright_angles'in t:
        angles[t['upright']]=t['upright_angles']
        warm[:,2]=angles
    return C,offset,angles,z,warm


def relaxed_template(t,p,free_uprights=False,split_columns=()):
    result=copy.deepcopy(t)
    if free_uprights:
        count=len(t['upright']);result['gx']=np.arange(count);result['gy']=np.arange(count)
        result['x']=p[t['upright'],0].copy();result['y']=p[t['upright'],1].copy()
    components=[];uv=[];slots=[];original=[]
    split=set(split_columns);by_column={}
    for k,(column,slot)in enumerate(zip(t['column'],t['slot'])):
        label=(int(column),int(slot))if int(column)in split else(int(column),None)
        if label not in by_column:
            by_column[label]=len(uv)
            uv.append((t['u'][column],t['v'][column]+(slot if int(column)in split else 0)))
            original.append(int(column))
        components.append(by_column[label]);slots.append(0 if int(column)in split else slot)
    result['column']=np.array(components);result['slot']=np.array(slots)
    result['u']=np.array([a for a,b in uv]);result['v']=np.array([b for a,b in uv])
    result['original_column_by_component']=original
    result['relaxation']={'free_uprights':free_uprights,'split_original_columns':sorted(split)}
    return result


def dimensions(t):return len(t['x'])+len(t['y'])+2*len(t['u'])


def selected_uprights(t,p):
    groups=[]
    for column in(0,5,10,15,21):
        center=p[t['core'][t['column']==column],:2].mean(0)
        distance=np.linalg.norm(p[t['upright'],:2]-center,axis=1)
        groups.append({'source_column':column,'upright_indices':t['upright'][np.argsort(distance,kind='stable')[:2]].tolist()})
    return groups,sorted({index for row in groups for index in row['upright_indices']})


def run(args):
    started=time.monotonic();deadline=started+args.seconds-5
    signal.signal(signal.SIGALRM,lambda a,b:(_ for _ in()).throw(base.RunLimit()))
    signal.setitimer(signal.ITIMER_REAL,args.seconds-2)
    args.out.mkdir(parents=True,exist_ok=False);out=args.out
    for path in(Path(__file__),Path(base.__file__)):
        dest=out/('source-'+path.name);shutil.copyfile(path,dest);dest.chmod(0o444)
    baseline_sha=digest(args.baseline);report=json.loads(args.official.read_text())
    if not(report['valid']and report['sha256']==baseline_sha and report['invalid_count']==0):raise ValueError('Baseline proof mismatch')
    p=base.read_baseline(args.baseline)[299];t=base.template(p);initial=base.side(p)
    split=[0,4,8,12,16,20]
    models={'original':relaxed_template(t,p),
            'A_individual_uprights':relaxed_template(t,p,True),
            'B_selected_dimers_split':relaxed_template(t,p,False,split),
            'AB_selected':relaxed_template(t,p,True,split),
            'AB_all_position_free':relaxed_template(t,p,True,range(22))}
    groups,selected=selected_uprights(t,p)
    source_paths=[Path(__file__),Path(base.__file__),
        base.ROOT/'experiments/compose_gadgets.py',base.ROOT/'experiments/extract_broad_active_frontier.py',
        base.ROOT/'experiments/fq_variant_campaign.py',base.ROOT/'experiments/fq_active_pilot.py',
        base.ROOT/'scripts/validate_submission.py',base.ROOT/'scripts/score_official.py',
        base.ROOT/'research/official_metric_v17.py']
    helper_directory=out/'source_helpers';helper_directory.mkdir()
    for path in source_paths[2:]:
        target=helper_directory/path.name;shutil.copyfile(path,target);target.chmod(0o444)
    manifest={'baseline':str(args.baseline),'baseline_sha256':baseline_sha,'official_report_sha256':digest(args.official),
        'reference_geometry_sha256':geometry_sha(p),'n':299,'source_hashes':{str(path):digest(path)for path in source_paths},
        'seconds':args.seconds,'workers':1,'fixed_count':299,'theta_offsets_degrees':[0.,-.25,-.5,-1.,-2.],
        'models':{name:{'position_variables':dimensions(model),'free_uprights':model['relaxation']['free_uprights'],
                       'split_columns':model['relaxation']['split_original_columns'],'rigid_groups':len(model['u'])}for name,model in models.items()},
        'upright_angle_selection':groups,'selected_upright_indices':selected,
        'same_constraint_engine':'Original period5_column_lp solve: bounded center trust, all walls, sparse distance-safe SAT branches, fresh full gates.',
        'angle_adapter':'Only explicit preset upright angles change; unit square dimensions and center variables remain unchanged.'}
    atomic_json(out/'manifest.json',manifest);atomic_npz(out/'reference.npz',{'299':p})
    donors={};certificates={};records=[];best=initial;status='running';controls=[]
    base.mapping=preset_mapping

    def attempt(model_name,offset,angle_preset=None,control=False):
        nonlocal best
        model=copy.deepcopy(models[model_name])
        if angle_preset is not None:
            model['upright_angles']=np.zeros(len(model['upright']))
            lookup={int(index):k for k,index in enumerate(model['upright'])}
            for index,degrees in angle_preset.items():model['upright_angles'][lookup[index]]=math.radians(degrees)
        size=len(model['u']);zero=np.zeros(size)
        record={'model':model_name,'theta_offset_degrees':offset,'upright_angle_preset':angle_preset,
                'position_variables':dimensions(model),'control':control}
        C,o,a,z,reconstructed=preset_mapping(model,zero,zero)
        record['reference_center_reconstruction_error']=float(np.max(abs(reconstructed[:,:2]-p[:,:2])))
        q,trace=base.solve(model,np.full(size,math.radians(offset)),zero,initial,deadline)
        record.update(trace=trace,status='no_feasible_lp')
        if q is not None:
            q=base.legalize(q,clearance=2e-9)
            if q is not None:
                L=base.side(q);name='299__ablation_'+geometry_sha(q)
                record.update(status='exploratory_lp',side=L,full_sat_minimum=base.sat(q),geometry_sha256=geometry_sha(q))
                if name in donors:
                    certificate=certificates[name]
                    record['certificate_reuse_for_exact_array']=True
                else:
                    _,certificate=certify_array((name,q))
                if certificate['valid']:
                    donors[name]=q;certificates[name]=certificate;best=min(best,L)
                    record.update(status='certified',archive_key=name,gain_vs_frozen=initial-L)
                    snapshots=out/'certified_snapshots';snapshots.mkdir(exist_ok=True)
                    target=snapshots/(geometry_sha(q)+'.npz')
                    if not target.exists():
                        atomic_npz(target,{name:q});target.chmod(0o444)
                        proof_path=target.with_suffix('.json')
                        atomic_json(proof_path,{'archive_key':name,'archive_sha256':digest(target),'geometry_sha256':geometry_sha(q),
                            'certificate':certificate,'configuration':record});proof_path.chmod(0o444)
                    atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',certificates)
        records.append(record);atomic_json(out/'results.json',records)
        return record

    try:
        for name in models:
            record=attempt(name,0.,control=True)
            if (record['status']!='certified' or record['reference_center_reconstruction_error']>1e-6
                    or record['side']>initial+1e-6):raise ValueError('Matched recoverable positive control failed')
            controls.append({'model':name,'side':record['side'],'certificate_archive_key':record['archive_key'],
                             'position_variables':record['position_variables']})
        duplicate=p.copy();duplicate[0]=duplicate[1]
        if base.sat(duplicate)>-.9:raise ValueError('Duplicate negative control failed')
        atomic_json(out/'controls.json',{'passed':True,'models':controls,'duplicate_negative_gap':base.sat(duplicate),
                                        'fixed_count':299,'original_full_gate_proof':'Fresh certificates keyed by each exact output array.'})
        print(json.dumps({'stage':'matched_column_controls_passed','models':len(models),'variables':{k:dimensions(v)for k,v in models.items()}}),flush=True)
        for offset,name in itertools.product((-.25,-.5,-1.,-2.),models):
            if time.monotonic()>=deadline:raise base.RunLimit()
            result=attempt(name,offset)
            print(json.dumps({'stage':'matched_position','model':name,'offset':offset,'side':result.get('side'),'best':best}),flush=True)
        positions_gain=max(0.,initial-best)
        if positions_gain<=1e-8:
            presets=[]
            for amplitude in(.5,1.,2.):
                presets.extend([{index:amplitude for index in selected},
                    {index:-amplitude for index in selected},
                    {index:amplitude*(1 if i%2 else -1)for i,index in enumerate(selected)},
                    {index:amplitude*(1 if i<len(selected)/2 else -1)for i,index in enumerate(selected)}])
            for offset,preset in itertools.product((-.25,-.5,-1.),presets):
                if time.monotonic()>=deadline:raise base.RunLimit()
                result=attempt('AB_all_position_free',offset,preset)
                if len(records)%5==0:print(json.dumps({'stage':'upright_angle','completed':len(records),'side':result.get('side'),'best':best}),flush=True)
        status='complete'
    except base.RunLimit:status='hard_deadline'
    except Exception:
        status='failed';raise
    finally:
        base.mapping=_ordinary_mapping;signal.setitimer(signal.ITIMER_REAL,0)
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',certificates);atomic_json(out/'results.json',records)
        summary={'status':status,'seconds':time.monotonic()-started,'limit_seconds':args.seconds,
            'configurations_completed':len(records),'certified_poses':len(donors),'initial_side':initial,'best_side':best,
            'strict_side_gain':max(0.,initial-best),'strict_full_score_gain':max(0.,initial-best)/math.sqrt(299),
            'manifest_sha256':digest(out/'manifest.json'),'donors_sha256':digest(out/'donors.npz'),
            'certificates_sha256':digest(out/'certificates.json'),'results_sha256':digest(out/'results.json'),
            'source_hashes_unchanged':all(digest(path)==value for path,value in manifest['source_hashes'].items()),
            'baseline_unchanged':digest(args.baseline)==baseline_sha,'full_portfolio_merge_performed':False}
        atomic_json(out/'summary.json',summary);print(json.dumps({'stage':'matched_column_complete',**summary}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=base.ROOT/'artifacts/merged-omitted-donor-pair-v1.csv')
    parser.add_argument('--official',type=Path,default=base.ROOT/'artifacts/merged-omitted-donor-pair-v1-official.json')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=290.)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if not 1<args.seconds<=295:raise ValueError('Total outer bound must remain below300seconds')
    if args.child:return run(args)
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child'],start_new_session=True)
    try:raise SystemExit(process.wait(timeout=args.seconds+3))
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=2)
        atomic_json(args.out/'supervisor_timeout.json',{'status':'outer_limit','seconds':args.seconds+3});raise SystemExit(2)


if __name__=='__main__':main()
