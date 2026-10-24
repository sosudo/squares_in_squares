#!/usr/bin/env python3
"""Bounded single-CPU joint pose MIS from a frozen, fully screened graph.

Graph/MILP incumbents are distinct from strict geometry certificates. Lower
counts are retained as explicitly numbered diagnostics, never299 candidates.
"""
from __future__ import annotations
import argparse
import heapq
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import warnings
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp
from scipy.sparse import coo_matrix
import joint_pose_mis as joint
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest
from compose_gadgets import legalize,side
from extract_broad_active_frontier import certify_array


def graph_from_edges(n,edges):
    result=[set()for _ in range(n)]
    for i,j in edges:result[int(i)].add(int(j));result[int(j)].add(int(i))
    return result


def independent(graph,chosen):
    keep=set(map(int,chosen))
    return len(keep)==len(chosen)and all(not(graph[v]&keep)for v in keep)


def greedy(graph,seed=0,initial=()):
    if not independent(graph,initial):raise ValueError('Initial graph witness conflicts')
    n=len(graph);active=np.ones(n,dtype=bool);selected=list(map(int,initial))
    for v in selected:
        active[v]=False
        for u in graph[v]:active[u]=False
    degree=np.array([sum(active[u]for u in row)for row in graph],dtype=int)
    order=np.random.default_rng(seed).permutation(n);heap=[(int(degree[v]),int(order[v]),v)for v in range(n)if active[v]]
    heapq.heapify(heap)
    while heap:
        d,_,v=heapq.heappop(heap)
        if not active[v]or d!=degree[v]:continue
        selected.append(v);removed=[v]+[u for u in graph[v]if active[u]]
        for r in removed:active[r]=False
        for r in removed:
            for u in graph[r]:
                if active[u]:degree[u]-=1;heapq.heappush(heap,(int(degree[u]),int(order[u]),u))
    if not independent(graph,selected):raise ValueError('Greedy graph incumbent conflicts')
    return np.array(selected,dtype=int)


def strengthening_cliques(graph,cover):
    unique={tuple(sorted(row))for row in cover if len(row)>2}
    for v in range(len(graph)):
        clique=[v];candidates=set(graph[v])
        while candidates:
            u=max(candidates,key=lambda u:(len(graph[u]&candidates),-u))
            clique.append(u);candidates&=graph[u]
        if len(clique)>2:unique.add(tuple(sorted(clique)))
    for clique in unique:
        if any(j not in graph[i]for k,i in enumerate(clique)for j in clique[k+1:]):raise ValueError('Invalid clique inequality')
    return sorted(unique)


def solve_mis(n,edges,cliques,area_upper,seconds):
    rows=[];columns=[];values=[];upper=[];row=0
    for i,j in edges:
        rows.extend((row,row));columns.extend((int(i),int(j)));values.extend((1.,1.));upper.append(1.);row+=1
    for clique in cliques:
        rows.extend([row]*len(clique));columns.extend(clique);values.extend([1.]*len(clique));upper.append(1.);row+=1
    rows.extend([row]*n);columns.extend(range(n));values.extend([1.]*n);upper.append(float(area_upper));row+=1
    matrix=coo_matrix((values,(rows,columns)),shape=(row,n)).tocsc()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        result=milp(-np.ones(n),integrality=np.ones(n),bounds=Bounds(0,1),
            constraints=LinearConstraint(matrix,-np.inf,np.array(upper)),
            options={'threads':1,'time_limit':max(.01,seconds),'mip_rel_gap':0.})
    chosen=None
    if result.x is not None and np.isfinite(result.x).all()and np.max(abs(result.x-np.rint(result.x)))<1e-6:
        chosen=np.flatnonzero(result.x>.5)
    def finite(value):return float(value)if value is not None and math.isfinite(float(value))else None
    return chosen,{'status':int(result.status),'selected_count':len(chosen)if chosen is not None else None,
        'reported_cardinality_upper':(-finite(result.mip_dual_bound)if finite(getattr(result,'mip_dual_bound',None))is not None else None),
        'reported_relative_gap':finite(getattr(result,'mip_gap',None)),
        'node_count':int(result.mip_node_count)if getattr(result,'mip_node_count',None)is not None else None,
        'finite_graph_optimal':bool(result.status==0 and chosen is not None),'constraint_rows':row,
        'matrix_nonzeros':matrix.nnz,'timeout_is_not_infeasibility':True}


def gate(q):
    _,raw=certify_array((str(len(q)),q))
    if raw['valid']:return q,{'raw':raw,'actual':raw,'clearance_applied':False}
    fixed=legalize(q,clearance=2e-9)
    if fixed is None:return None,{'raw':raw,'clearance_failed':True}
    _,certificate=certify_array((str(len(q)),fixed))
    return(fixed if certificate['valid']else None),{'raw':raw,'actual':certificate,'clearance_applied':True,
        'clearance_side_increase':side(fixed)-side(q)}


def run(args):
    started=time.monotonic();deadline=started+args.seconds-5
    args.out.mkdir(parents=True,exist_ok=False);out=args.out
    summary=json.loads((args.screen/'summary.json').read_text());screen_manifest=json.loads((args.screen/'manifest.json').read_text())
    if summary['status']!='screen_complete'or digest(args.screen/'screen-results.json')!=summary['results_sha256']:
        raise ValueError('Screen output identity mismatch')
    control=json.loads((args.screen/'box-0.000/control.json').read_text())
    p0=np.load(args.screen/'box-0.000/candidates.npz')['unit_poses'][control['selected']]
    if len(p0)!=299 or not control['certificate']['valid']or geometry_sha(p0)!=control['certificate']['geometry_sha256']:
        raise ValueError('Actual original-box299 control missing')
    paths=[Path(__file__),Path(joint.__file__),joint.ROOT/'experiments/compose_gadgets.py',
        joint.ROOT/'experiments/extract_broad_active_frontier.py',joint.ROOT/'scripts/validate_submission.py',
        joint.ROOT/'scripts/score_official.py',joint.ROOT/'research/official_metric_v17.py']
    (out/'source').mkdir()
    for path in paths:shutil.copyfile(path,out/'source'/path.name)
    manifest={'screen_path':str(args.screen),'screen_summary_sha256':digest(args.screen/'summary.json'),
        'screen_manifest_sha256':digest(args.screen/'manifest.json'),'original_control_sha256':digest(args.screen/'box-0.000/control.json'),
        'source_hashes':{str(p):digest(p)for p in paths},'seconds':args.seconds,'workers':1,
        'maximum_nodes':5000,'maximum_edges':1000000,'initial_side':screen_manifest['initial_side'],
        'model':'Maximize joint independent count; no fixed tilted count or source-identity exclusivity. Valid overlapping graph cliques strengthen pair inequalities.',
        'acceptance':'Only fresh full-gated actual count>=299 can be a win; smaller incumbents retain explicit actual-n diagnostic labels.'}
    atomic_json(out/'manifest.json',manifest)
    records=[];donors={};certificates={};wins=[];status='running'
    def preserve(poses,chosen,record,origin):
        if len(chosen)<2:return
        q=poses[chosen];fixed,certificate=gate(q)
        result={'origin':origin,'selected_count':len(q),'source_candidate_indices':list(map(int,chosen)),
                'raw_geometry_sha256':geometry_sha(q),'full_gate_valid':fixed is not None}
        if fixed is not None:
            n=len(fixed);identity=str(n)+'__joint_mis_'+geometry_sha(fixed)
            donors[identity]=fixed;certificates[identity]=certificate
            result.update(archive_key=identity,actual_n=n,actual_certified_side=side(fixed),
                tilted_count=int(np.sum(abs((fixed[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018)),
                is_299_candidate=n==299,nominal_target_side=record['nominal_target_side'])
            snapshots=out/'retained';snapshots.mkdir(exist_ok=True);path=snapshots/(geometry_sha(fixed)+'.npz')
            if not path.exists():
                atomic_npz(path,{identity:fixed});path.chmod(0o444)
                atomic_json(path.with_suffix('.json'),{'archive_key':identity,'certificate':certificate,'selection':result,
                    'archive_sha256':digest(path),'graph_case':record['case']})
            if n==299 and side(fixed)<manifest['initial_side']-1e-8:
                wins.append(result)
                atomic_json(out/'wins.json',wins)
                print(json.dumps({'stage':'new_certified_299','side':side(fixed),'archive_key':identity,
                                  'nominal_target_side':record['nominal_target_side']}),flush=True)
            atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',certificates)
        record.setdefault('geometry_results',[]).append(result)
    try:
        # A real tiny MILP control checks clique/cardinality construction.
        small,proof=solve_mis(4,np.array([[0,1],[0,2],[1,2]]),[[0,1,2]],4,2.)
        if small is None or len(small)!=2:raise ValueError('Synthetic joint MIS control failed')
        atomic_json(out/'solver-control.json',proof)
        for report in summary['cases']:
            if time.monotonic()>=deadline-3:status='deadline';break
            depth=report['depth'];case=args.screen/f'box-{depth:.3f}'
            if report['status']!='screened':continue
            if report['graph']['unresolved_conservative_edges']:raise ValueError('Unresolved graph edges need explicit review before bounds/solve')
            for name,key in(('candidates.npz','candidate_archive_sha256'),('edges.npy','edges_sha256'),('cliques.json','cliques_sha256'),('provenance.json','provenance_sha256')):
                if digest(case/name)!=report[key]:raise ValueError('Frozen graph input changed')
            poses=np.load(case/'candidates.npz')['unit_poses'];edges=np.load(case/'edges.npy');cover=json.loads((case/'cliques.json').read_text())
            if len(poses)>5000 or len(edges)>1000000:raise ValueError('Graph resource bound exceeded')
            graph=graph_from_edges(len(poses),edges);origin=json.loads((case/'provenance.json').read_text())
            record={'case':str(case),'depth':depth,'nominal_target_side':report['nominal_box'],'working_box':report['working_box'],
                'nodes':len(poses),'edges':len(edges),'clique_cover_upper_bound':len(cover),'area_upper_bound':report['area_upper_bound']}
            groups={}
            for vertex,items in enumerate(origin):
                for item in items:
                    if item['source']!='fresh_wall_grid':groups.setdefault((item['source'],item['phase']),set()).add(vertex)
            starts=[()] +[sorted(value)for value in groups.values()if independent(graph,sorted(value))]
            best=np.array([],dtype=int)
            for seed,initial in enumerate(starts):
                selected=greedy(graph,seed,initial)
                if len(selected)>len(best):best=selected
            record['best_greedy_count']=len(best);preserve(poses,best,record,'source-seeded_greedy')
            if len(best)>299:preserve(poses,best[:299],record,'299_subset_of_greedy')
            cliques=strengthening_cliques(graph,cover);record['strengthening_cliques']=len(cliques)
            cap=15. if depth==0 else 70.
            remaining=max(.01,min(cap,deadline-time.monotonic()-2))
            selected,mip=solve_mis(len(poses),edges,cliques,report['area_upper_bound'],remaining)
            record['milp']=mip
            if selected is not None:
                if not independent(graph,selected):raise ValueError('MILP incumbent violates graph')
                preserve(poses,selected,record,'milp_incumbent')
                if len(selected)>299:preserve(poses,selected[:299],record,'299_subset_of_milp')
            records.append(record);atomic_json(out/'results.json',records)
            print(json.dumps({'stage':'joint_mis_case','depth':depth,'greedy_count':len(best),'milp':mip,
                'certified_299_wins':len(wins),'seconds':time.monotonic()-started}),flush=True)
        if status=='running':status='complete'
    except Exception:status='failed';raise
    finally:
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',certificates);atomic_json(out/'results.json',records);atomic_json(out/'wins.json',wins)
        unchanged=all(digest(p)==v for p,v in manifest['source_hashes'].items())
        result={'status':status if unchanged else'source_changed_quarantine','seconds':time.monotonic()-started,
            'limit_seconds':args.seconds,'cases_completed':len(records),'certified_actual_count_poses':len(donors),
            'certified_299_wins':len(wins),'source_hashes_unchanged':unchanged,'manifest_sha256':digest(out/'manifest.json'),
            'donors_sha256':digest(out/'donors.npz'),'certificates_sha256':digest(out/'certificates.json'),
            'results_sha256':digest(out/'results.json'),'wins_sha256':digest(out/'wins.json'),
            'scope':'Finite source-pose graph only. Timeouts are not infeasibility. Partial counts are explicitly numbered diagnostics.',
            'full_portfolio_merge_performed':False}
        atomic_json(out/'summary.json',result);print(json.dumps({'stage':'joint_mis_complete',**result}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screen',type=Path,default=joint.ROOT/'artifacts/joint-mis-screen-v1')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=290.)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if not 1<args.seconds<=295:raise ValueError('Outer total must stay below300seconds')
    if args.child:return run(args)
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child'],start_new_session=True)
    try:raise SystemExit(child.wait(timeout=args.seconds+3))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=2)
        atomic_json(args.out/'supervisor_timeout.json',{'status':'outer_limit','seconds':args.seconds+3});raise SystemExit(2)


if __name__=='__main__':main()
