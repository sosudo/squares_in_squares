#!/usr/bin/env python3
"""Replay frozen public staircase recipes with new certified component donors.

Uses the unchanged attributed public stitch/border functions without importing
CUDA. A small CPU chain DP chooses compatible incoming/outgoing profiles; full
official and independent raw/default-pandas certificates decide every export.
"""
from __future__ import annotations

import time
ENTRY_STARTED = time.monotonic()

import argparse
import ast
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import signal
import sys

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'

import numpy as np
from scipy.spatial import cKDTree
from compose_gadgets import extents,legalize,normalize,read_baseline,side
from extract_broad_active_frontier import profiles,orient,geometry_sha
from fq_capacity_probe import full_certificate

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path,value):
    temporary=path.with_suffix(path.suffix+'.incoming')
    temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)


def public_functions(source_dir):
    """Compile only unchanged CPU functions; never import CuPy or initialize GPU."""
    scope={'np':np,'math':math,'GAP':2e-7}
    for filename,names in [('solver.py',{'normalize','side'}),
                           ('gpu_fault_composition.py',{'stitch'}),
                           ('packing_pipeline.py',{'border_expand'})]:
        path=source_dir/filename
        nodes=[node for node in ast.parse(path.read_text()).body
               if isinstance(node,ast.FunctionDef)and node.name in names]
        if {node.name for node in nodes}!=names:
            raise ValueError('Pinned public function not found')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return scope['stitch'],scope['border_expand']


def cross_block_separated(previous_pose,current_pose,previous_width,current_height,mode):
    """Exact unit-square SAT at the unchanged stitch-relative block offsets.

    Binary64 contacts receive a 1e-12 proposal tolerance; complete-puzzle
    official/interval checks remain the strict acceptance authority.
    """
    shifted=current_pose.copy()
    shifted[:,:2]+=[previous_width+(mode==1),-current_height-(mode==2)]
    pairs=cKDTree(previous_pose[:,:2]).query_ball_tree(cKDTree(shifted[:,:2]),1.5)
    first=[];second=[]
    for i,neighbors in enumerate(pairs):
        first.extend([i]*len(neighbors));second.extend(neighbors)
    if not first:return True
    a=previous_pose[np.asarray(first)];b=shifted[np.asarray(second)]
    delta=b[:,:2]-a[:,:2]
    projection=np.maximum.reduce([abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t))
        for t in (a[:,2],a[:,2]+np.pi/2,b[:,2],b[:,2]+np.pi/2)])
    radius=.5*(1+abs(np.cos(a[:,2]-b[:,2]))+abs(np.sin(a[:,2]-b[:,2])))
    return bool(np.all(projection-radius>=-1e-12))


def compatible(previous,current,mode,join_check='bins',previous_stage=None,current_stage=None):
    if join_check=='sat':
        return cross_block_separated(previous['pose'],current['pose'],previous_stage['w'],current_stage['h'],mode)
    if mode in (1,2):return True
    if join_check=='continuous':
        a,b=previous['profile'],current['profile']
        if abs(a['outgoing_degrees']-b['incoming_degrees'])>1e-12:
            raise ValueError('Continuous join requires the same saved normal')
        return a['outgoing_br_support']<=b['incoming_tl_support']
    return previous['profile']['br_bin']<=current['profile']['tl_bin']


def select_chain(options,recipe,join_check='bins'):
    states=[(option['f'],[i])for i,option in enumerate(options[0])]
    for stage in range(1,len(options)):
        new=[]
        ordered=sorted(states,key=lambda item:item[0])
        for index,option in enumerate(options[stage]):
            # The first compatible predecessor minimizes max(prefix_f,option_f).
            # This avoids a quadratic SAT sweep when low-cost branches agree.
            for cost,path in ordered:
                if compatible(options[stage-1][path[-1]],option,recipe[stage]['mode'],join_check,
                              recipe[stage-1],recipe[stage]):
                    new.append((max(cost,option['f']),path+[index]))
                    break
        if not new:return None
        states=new
    _,path=min(states,key=lambda x:x[0])
    return [options[i][index]for i,index in enumerate(path)]


def campaign(args):
    os.setsid();deadline=ENTRY_STARTED+args.seconds-3
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/'inputs').mkdir();(args.out/'source').mkdir()
    active=json.loads((args.active/'active_manifest.json').read_text())
    portfolio_report=json.loads(args.portfolio_report.read_text())
    if not portfolio_report['valid']or portfolio_report['sha256']!=digest(args.portfolio):
        raise ValueError('Latest portfolio certificate hash mismatch')
    base_path=Path(active['baseline'])
    if digest(base_path)!=active['baseline_sha256']:
        raise ValueError('Original recipe source baseline hash mismatch')
    base=read_baseline(base_path);current=read_baseline(args.portfolio)
    summary=json.loads((args.results/'dual_composition_summary.json').read_text())
    reports={name:json.loads((args.results/name/'composition_candidates.report.json').read_text())['groups']['all_certified_donors']
             for name in summary['profiles']}
    for name in reports:
        if digest(args.results/name/'composition_candidates.report.json')!=active['report_sha256'][name]:
            raise ValueError('Frozen recipe report changed')
    banks=[];input_sources=[]
    for index,path in enumerate(args.bank):
        snapshot=args.out/'inputs'/f'bank-{index:02d}.npz';shutil.copyfile(path,snapshot);snapshot.chmod(0o444)
        sha=digest(snapshot);input_sources.append({'original_path':str(path),'snapshot':str(snapshot),'sha256':sha})
        with np.load(snapshot,allow_pickle=False)as z:
            for key in z.files:
                w,h,d=map(int,key.split('__')[0].split('_'));p=np.asarray(z[key],dtype=float)
                if p.shape!=(w*h+d,3)or not np.isfinite(p).all():raise ValueError('Invalid donor type')
                banks.append((w,h,d,p,{'archive_sha256':sha,'array_key':key,'geometry_sha256':geometry_sha(p)}))
    vendor=ROOT/'vendor/lightning_ftmc'
    source_paths=[Path(__file__),ROOT/'experiments/extract_broad_active_frontier.py',
                  ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/fq_capacity_probe.py',
                  ROOT/'experiments/fq_active_pilot.py',ROOT/'scripts/score_official.py',
                  ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py',
                  vendor/'solver.py',vendor/'gpu_fault_composition.py',vendor/'packing_pipeline.py']
    source_hashes={}
    for i,path in enumerate(source_paths):
        snapshot=args.out/'source'/f'{i:02d}-{path.name}';shutil.copyfile(path,snapshot);snapshot.chmod(0o444)
        source_hashes[str(path.relative_to(ROOT))]=digest(snapshot)
    stitch,border_expand=public_functions(vendor)
    command=[sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]]
    manifest={'sources':source_hashes,'banks':input_sources,'portfolio':str(args.portfolio),
              'portfolio_sha256':digest(args.portfolio),'portfolio_report_sha256':digest(args.portfolio_report),
              'active_manifest_sha256':digest(args.active/'active_manifest.json'),
              'recipe_baseline_sha256':active['baseline_sha256'],
              'command':command,'command_sha256':hashlib.sha256(json.dumps(command,separators=(',',':')).encode()).hexdigest(),
              'seconds':args.seconds,'workers':1,'no_gpu':True,'no_submission':True,'join_check':args.join_check,
              'max_chains':args.max_chains,
              'method':'Exact public stitch with fixed modes,dimensions and separator angles. '
                       'Finite D4 donor choices are joined by the explicitly frozen CPU minimax join rule. '
                       'Original crop wall phase is retained; only centers translate/reflect, unit squares do not scale.'}
    atomic_json(args.out/'manifest.json',manifest)
    cache={}

    def original_crop(g,report):
        match=re.fullmatch(r'(.+):T=(True|False):(-?1),(-?1)',g['origin'])
        source,trans,sx,sy=match.groups()
        if source.startswith('Public frontier:'):
            p=base[int(source.split(':')[-1])]
        else:
            ref=report['details']['_donor_sources'][int(source.split(':')[-1])]
            label=ref['label']
            if label.startswith('certified baseline n='):p=base[int(label.split('=')[-1])]
            else:
                name,key=label.split(':',1)
                if (name,key)not in cache:
                    info=active['sources'][name];path=Path(info['path'])
                    if digest(path)!=info['sha256']:raise ValueError('Original donor archive hash mismatch')
                    with np.load(path,allow_pickle=False)as z:p=legalize(z[key])
                    cache[name,key]=p
                p=cache[name,key]
            if geometry_sha(p)!=ref['array_sha256']:raise ValueError('Original donor geometry hash mismatch')
        p=orient(p,trans=='True',int(sx),int(sy));_,hi=extents(p)
        r=np.maximum.reduce((hi[:,0]-g['w'],hi[:,1]-g['h'],np.zeros(len(p))))
        ids=np.argsort(r,kind='stable')[:g['w']*g['h']+g['dm']]
        return p[ids].copy()

    trials=[];candidates={};control_done=False;option_cache={}

    def checkpoint(status):
        atomic_json(args.out/'candidates.json',candidates)
        atomic_json(args.out/'report.json',{'status':status,'manifest_sha256':digest(args.out/'manifest.json'),
            'candidates_sha256':digest(args.out/'candidates.json'),'elapsed_seconds':time.monotonic()-ENTRY_STARTED,
            'trials':trials,'certified_improvements':len(candidates),
            'estimated_score_gain':sum(t.get('certified_gain',0.)for t in trials)})

    checkpoint('configured')
    # Start with chains whose limiting family has the highest saved headroom.
    order=sorted(active['accepted_chains'],key=lambda n:-max(active['family_joint_conditional_gain'].get(g['family'],0.)
                 for g in active['accepted_chains'][n]['stages']))
    if args.max_chains:order=order[:args.max_chains]
    for n_text in order:
        if time.monotonic()>=deadline-1:break
        n=int(n_text);profile=summary['winning_profile'][n_text];report=reports[profile]
        record=next(r for r in report['details']['adaptive']['records']if r['n']==n)
        recipe=record['chain'];options=[];originals=[]
        for stage,g in enumerate(recipe):
            raw=original_crop(g,report);lo,_=extents(raw);phase=lo.min(0)
            cache_key=(g['w'],g['h'],g['dm'],geometry_sha(raw),g['f'],g['incoming_degrees'],g['outgoing_degrees'],
                       report['bins'],max(v['f']for v in recipe))
            if cache_key in option_cache:
                choices=option_cache[cache_key];originals.append(choices[0]);options.append(choices)
                continue
            pf=profiles(raw,g['w'],g['h'],g['incoming_degrees'],g['outgoing_degrees'],report['bins'])
            original={'pose':raw,'f':g['f'],'profile':pf,'source':{'kind':'original','origin':g['origin'],
                       'geometry_sha256':geometry_sha(raw)},'replacement':False}
            choices=[original];originals.append(original)
            seen={geometry_sha(raw)}
            for w,h,d,p,source in banks:
                if d!=g['dm']:continue
                for transpose in (False,True):
                    if ((h,w)if transpose else(w,h))!=(g['w'],g['h']):continue
                    for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
                        q=orient(p,transpose,sx,sy);q[:,:2]+=phase
                        sha=geometry_sha(q)
                        if sha in seen:continue
                        seen.add(sha);_,hi=extents(q)
                        actual=float(max(hi.max(0)-[g['w'],g['h']]))
                        f=math.ceil((actual+3e-8)*1e9)*1e-9
                        if f>=1 or f>=max(v['f']for v in recipe):continue
                        pf=profiles(q,g['w'],g['h'],g['incoming_degrees'],g['outgoing_degrees'],report['bins'])
                        choices.append({'pose':q,'f':f,'profile':pf,'source':dict(source,transpose=transpose,
                            reflection_x=sx,reflection_y=sy,phase=phase.tolist(),geometry_sha256=sha),'replacement':True})
            options.append(choices);option_cache[cache_key]=choices

        def build(selected):
            gadgets=[dict(g,donor=i,f=selected[i]['f'])for i,g in enumerate(recipe)]
            q,k=stitch([(i,g['mode'])for i,g in enumerate(recipe)],gadgets,[(v['pose'],'frozen/replacement')for v in selected])
            if k<math.isqrt(n):q=border_expand(q,math.isqrt(n)-k)
            if len(q)!=n:raise ValueError('Stitched count mismatch')
            return q

        control=build(originals)
        if abs(side(control)-record['after'])>1e-9:raise ValueError('Exact original recipe replay failed positive control')
        trial={'n':n,'profile':profile,'before_side':side(current[n]),'original_replay_side':side(control),
               'recipe_after':record['after'],'options_per_stage':list(map(len,options)),
               'original_maximum_bloat':max(g['f']for g in recipe)}
        if not control_done:
            certified_control=legalize(control)
            trial['positive_control_certificate']=full_certificate(certified_control)
            if not trial['positive_control_certificate']['valid']:raise ValueError('Original whole-puzzle replay failed certificates')
            control_done=True
        selected=select_chain(options,recipe,args.join_check)
        if selected is None:trial['status']='no_compatible_chain'
        else:
            trial.update(new_maximum_bloat=max(v['f']for v in selected),
                         replacements=sum(v['replacement']for v in selected),
                         selected=[{'f':v['f'],'profile':v['profile'],'source':v['source']}for v in selected])
            q=legalize(build(selected))
            if q is None:trial['status']='rejected_more_than_rounding_overlap'
            elif side(q)>=side(current[n])-1e-9:trial.update(status='no_full_side_gain',candidate_side=side(q))
            elif time.monotonic()>=deadline-1:trial['status']='uncertified_deadline'
            else:
                cert=full_certificate(q);trial['certificate']=cert
                if cert['valid']:
                    length=cert['independent_raw']['side_upper'];gain=(side(current[n])-float(length))/math.sqrt(n)
                    if gain>1e-10:
                        candidates[n_text]={'side':length,'squares':[[f'{v:.17g}'for v in row]for row in q],
                            'source':'CPU replay of frozen broad recipe with profile-compatible FQ replacements',
                            'provenance':{'manifest_sha256':digest(args.out/'manifest.json'),'n':n,'selected':trial['selected']}}
                        trial.update(status='certified_improvement',certified_gain=gain,geometry_sha256=geometry_sha(q))
                    else:trial['status']='no_certified_gain'
                else:trial['status']='rejected_official_or_independent_geometry'
        trials.append(trial);checkpoint('running')
        print(json.dumps({'n':n,'status':trial['status'],'gain':trial.get('certified_gain',0.),
                          'replacements':trial.get('replacements',0),'elapsed_seconds':time.monotonic()-ENTRY_STARTED}),flush=True)
    checkpoint('complete')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--active',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--bank',type=Path,action='append',required=True)
    parser.add_argument('--portfolio',type=Path,required=True)
    parser.add_argument('--portfolio-report',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=300.)
    parser.add_argument('--join-check',choices=['bins','continuous','sat'],default='bins')
    parser.add_argument('--max-chains',type=int,default=0,help='Optional bounded smoke subset; zero uses all saved chains')
    args=parser.parse_args()
    if args.out.exists()or not 5<args.seconds<=300 or args.max_chains<0:
        parser.error('Require new output directory,5<seconds<=300 and nonnegative max-chains')
    process=mp.get_context('fork').Process(target=campaign,args=(args,));process.start()
    process.join(timeout=max(0.,args.seconds-1.5-(time.monotonic()-ENTRY_STARTED)))
    enforced=process.is_alive()
    if enforced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:process.kill()
        process.join(timeout=.4)
    receipt={'status':'hard_deadline_enforced'if enforced else'exited','exitcode':process.exitcode,
             'elapsed_seconds':time.monotonic()-ENTRY_STARTED,'configured_seconds':args.seconds,'workers':1,'no_gpu':True}
    if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.exitcode and not enforced:raise SystemExit(process.exitcode)


if __name__=='__main__':main()
