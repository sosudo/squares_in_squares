#!/usr/bin/env python3
"""Finite joint selection of tilted and upright unit poses, with strict gates.

Default screen mode builds bounded pools/graphs and validates the source299
witness. Solver support is intentionally separate from the initial screening.
No tilted-count restriction, GPU or competition submission is involved.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'experiments')]
from compose_gadgets import read_baseline,normalize,side
from extract_broad_active_frontier import certify_array
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_active_pilot import digest
from fq_active_pilot import OFFICIAL_SHA256
from period5_branch_lp import data
from validate_submission import Square,check_pair,_geometry

EPS=2e-11


def decimal_square(row):return Square(*(format(float(value),'.17g')for value in row))


def inside(row,L):
    e=.5*(abs(math.cos(row[2]))+abs(math.sin(row[2])))
    lower=row[:2]-e;upper=L-row[:2]-e
    if lower.min()>1e-9 and upper.min()>1e-9:return True
    square=decimal_square(row)
    if Fraction(square.angle)==0:
        half=Fraction(1,2);bound=Fraction(format(float(L),'.17g'))
        return all(half<=Fraction(value)<=bound-half for value in(square.x,square.y))
    import mpmath as mp
    for dps in(50,100,200):
        x,y,c,s,h=_geometry([square],dps)[0];bound=mp.iv.mpf(format(float(L),'.17g'))
        gaps=(x-h,y-h,bound-x-h,bound-y-h)
        if all(value.a>=0 for value in gaps):return True
        if any(value.b<0 for value in gaps):return False
    return False


def pool(sources,nominal,source_phases=None,primary_label='current299'):
    """Preserve exact posed units, with explicit source-wide translations."""
    box=nominal+4*EPS;rows=[];provenance=[];lookup={};current_ids=[];counts={}
    def add(row,origin):
        if not inside(row,box):return None
        identity=np.asarray(row,dtype='<f8').tobytes()
        if identity in lookup:
            index=lookup[identity];provenance[index].append(origin);return index
        index=len(rows);lookup[identity]=index;rows.append(np.asarray(row,dtype='<f8'));provenance.append([origin]);return index
    for label,p in sources.items():
        q=normalize(p);source_side=side(q);delta=source_side-nominal
        phases=(source_phases[label] if source_phases is not None else
                ((0.,.5,1.)if label in('current299','alternative41','alternative42')else(0.,1.)))
        if not phases or any(not 0<=float(phase)<=1 for phase in phases):raise ValueError('Invalid source wall phase')
        count=0
        for phase in phases:
            shifted=q.copy();translation=np.array([EPS-phase*delta,EPS-phase*delta]);shifted[:,:2]+=translation
            for sid,row in enumerate(shifted):
                index=add(row,{'source':label,'square_id':sid,'phase':phase,'translation':translation.tolist()})
                if index is not None:
                    count+=1
                    if label==primary_label and phase==0.:current_ids.append(index)
        counts[label]=count
    # A plain unit grid, anchored to each wall. It contributes new selectable
    # uprights without treating any of the tilted alternatives as mandatory.
    size=int(math.floor(nominal));left=.5+EPS+np.arange(size)
    right=nominal-.5-EPS-np.arange(size)
    wall_count=0
    for x,y in itertools_product(np.r_[left,right],np.r_[left,right]):
        if add(np.array([x,y,0.]),{'source':'fresh_wall_grid'})is not None:wall_count+=1
    return np.array(rows),provenance,current_ids,{'source_vertices_before_exact_dedup':counts,
        'wall_vertices_before_exact_dedup':wall_count,'unique_vertices':len(rows),'nominal_box':nominal,
        'working_box':box,'explicit_numeric_wall_padding':4*EPS}


def itertools_product(a,b):
    for x in a:
        for y in b:yield x,y


def conflict_graph(poses):
    pairs=cKDTree(poses[:,:2]).query_pairs(math.sqrt(2)+1e-8,output_type='ndarray')
    graph=[set()for _ in poses];stats={'broad_pairs':len(pairs),'fast_overlap_edges':0,'robust_pairs':0,
        'robust_separated':0,'robust_overlap_edges':0,'unresolved_conservative_edges':0}
    if not len(pairs):return graph,stats
    _,_,_,gaps,_=data(poses,pairs);maximum=gaps.max(1);squares=[decimal_square(row)for row in poses]
    unresolved=[]
    for k,(i,j)in enumerate(pairs):
        value=maximum[k]
        if value>1e-10:continue
        if value < -1e-10:edge=True;stats['fast_overlap_edges']+=1
        else:
            stats['robust_pairs']+=1;verdict=check_pair(squares[i],squares[j])
            edge=verdict is not True
            if verdict is True:stats['robust_separated']+=1
            elif verdict is False:stats['robust_overlap_edges']+=1
            else:
                stats['unresolved_conservative_edges']+=1;unresolved.append([int(i),int(j)])
        if edge:graph[int(i)].add(int(j));graph[int(j)].add(int(i))
    stats.update(edges=sum(map(len,graph))//2,maximum_degree=max(map(len,graph),default=0),
        unresolved_pairs=unresolved,
        graph_scope='Every tight pair uses interval/exact arithmetic; unresolved pairs are explicit conservative exclusions, never silently treated as zero-clearance conflicts.')
    return graph,stats


def clique_cover(graph):
    """Partition all vertices into actual graph cliques: valid finite upper bound."""
    active=set(range(len(graph)));cover=[]
    while active:
        vertex=max(active,key=lambda i:(len(graph[i]&active),-i))
        clique=[vertex];candidates=graph[vertex]&active
        while candidates:
            nxt=max(candidates,key=lambda i:(len(graph[i]&candidates),-i))
            clique.append(nxt);candidates&=graph[nxt]
        if any(j not in graph[i]for k,i in enumerate(clique)for j in clique[k+1:]):raise ValueError('Invalid clique bound')
        cover.append(clique);active.difference_update(clique)
    return cover


def load_sources(pointer_path,alternatives):
    pointer=json.loads(pointer_path.read_text());source=Path(pointer['safe']['path'])
    if digest(source)!=pointer['safe']['sha256']:raise ValueError('Current certified CSV changed')
    report=Path(pointer['safe']['official_report']);evidence=json.loads(report.read_text())
    if not(digest(report)==pointer['safe']['official_report_sha256']and evidence['sha256']==digest(source)
            and evidence['valid']and evidence['invalid_count']==0):raise ValueError('Current official proof mismatch')
    full=read_baseline(source);sources={'current299':full[299],'current300':full[300],'current301':full[301]}
    proof=json.loads((alternatives/'source-proof.json').read_text())
    if digest(alternatives/'alternatives.npz')!=proof['archive_sha256']:raise ValueError('Alternative archive changed')
    with np.load(alternatives/'alternatives.npz',allow_pickle=False)as archive:
        for row in proof['selected']:
            q=archive[row['source_key']]
            if geometry_sha(q)!=row['geometry_sha256']or not row['full_source_provenance_and_certificate']['certificate']['valid']:
                raise ValueError('Alternative exact source certificate mismatch')
            sources['alternative'+str(row['tilted'])]=q
    if set(sources)!={'current299','current300','current301','alternative41','alternative42'}:raise ValueError('Incomplete source family')
    return sources,{'csv':str(source),'csv_sha256':digest(source),'official_report_sha256':digest(report),
        'alternatives_sha256':digest(alternatives/'alternatives.npz'),'alternative_proof_sha256':digest(alternatives/'source-proof.json')}


def load_source_spec(path):
    """Load a frozen, explicitly phased source bank with exact pose certificates."""
    proof=json.loads(path.read_text());archive_path=Path(proof['archive_path'])
    if digest(archive_path)!=proof['archive_sha256']:raise ValueError('Source-spec archive changed')
    for source,identity in proof['parent_hashes'].items():
        if digest(source)!=identity:raise ValueError('Source-spec parent changed')
    sources={}
    with np.load(archive_path,allow_pickle=False)as archive:
        if set(archive.files)!=set(proof['sources']):raise ValueError('Source-spec labels differ from archive')
        for label,row in proof['sources'].items():
            q=archive[label].copy();certificate=row['certificate']
            if(q.shape!=(row['n'],3)or not np.isfinite(q).all()
                    or geometry_sha(q)!=row['geometry_sha256']
                    or not certificate['valid']or certificate['geometry_sha256']!=geometry_sha(q)
                    or certificate['official_metric_sha256']!=OFFICIAL_SHA256):
                raise ValueError('Source-spec exact geometry/certificate mismatch')
            sources[label]=q
    n=int(proof['target_n']);primary=proof['primary_label'];phases=proof['source_phases']
    if not 2<=n<=1000:raise ValueError('Invalid requested competition count')
    if primary not in sources or len(sources[primary])!=n or 0. not in phases[primary]:
        raise ValueError('Original-box source witness unavailable')
    if set(phases)!=set(sources):raise ValueError('Missing explicit source phases')
    return sources,{'source_spec_path':str(path),'source_spec_sha256':digest(path),**proof},n,primary,phases


def screen(args):
    started=time.monotonic();args.out.mkdir(parents=True,exist_ok=False)
    if args.source_spec is None:
        sources,source_proof=load_sources(args.portfolio,args.alternatives)
        n=299;primary='current299';phases=None
    else:sources,source_proof,n,primary,phases=load_source_spec(args.source_spec)
    L0=side(sources[primary]);depths=tuple(args.depths)if args.depths is not None else(0.,.002,.010,.020)
    if not depths or depths[0]!=0. or any(depth<0 for depth in depths)or len(set(depths))!=len(depths):
        raise ValueError('Unique nonnegative depths must start with the original-box control')
    atomic_npz(args.out/'sources.npz',sources)
    paths=[Path(__file__),ROOT/'scripts/validate_submission.py',ROOT/'experiments/period5_branch_lp.py',
        ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/extract_broad_active_frontier.py']
    (args.out/'source').mkdir()
    for path in paths:shutil.copyfile(path,args.out/'source'/path.name)
    manifest={'source_proof':source_proof,'sources_sha256':digest(args.out/'sources.npz'),
        'source_geometry_sha256':{k:geometry_sha(v)for k,v in sources.items()},'initial_side':L0,
        'source_hashes':{str(p):digest(p)for p in paths},'node_cap':5000,'edge_cap':1000000,
        'broad_radius':math.sqrt(2)+1e-8,'tilted_count_restriction':None,'required_selected_count':n,
        'primary_source_label':primary,'source_phases':phases,'depths':depths,
        'rigorous_tight_pairs':'Independent interval/exact check_pair, including exact rational zero-angle contacts.'}
    atomic_json(args.out/'manifest.json',manifest);reports=[]
    for depth in depths:
        poses,origin,current,info=pool(sources,L0-depth,phases,primary)
        case=args.out/f'box-{depth:.3f}';case.mkdir()
        atomic_npz(case/'candidates.npz',{'unit_poses':poses});atomic_json(case/'provenance.json',origin)
        report={'depth':depth,**info,'candidate_geometry_sha256':geometry_sha(poses),
                'candidate_archive_sha256':digest(case/'candidates.npz'),'provenance_sha256':digest(case/'provenance.json')}
        if len(poses)>5000:report['status']='node_budget';reports.append(report);continue
        graph,stats=conflict_graph(poses);report.update(graph=stats)
        if stats['edges']>1000000:report['status']='edge_budget';reports.append(report);continue
        cover=clique_cover(graph);upper=len(cover)
        edges=np.array([(i,j)for i,g in enumerate(graph)for j in g if i<j],dtype=np.int32).reshape(-1,2)
        np.save(case/'edges.npy',edges,allow_pickle=False);atomic_json(case/'cliques.json',cover)
        report.update(status='screened',clique_cover_upper_bound=upper,
            area_upper_bound=math.floor(info['working_box']**2),estimated_graph_and_milp_bytes=len(poses)*320+stats['edges']*160,
            edges_sha256=digest(case/'edges.npy'),cliques_sha256=digest(case/'cliques.json'))
        if depth==0.:
            if len(current)!=n or any(graph[i]&set(current)for i in current):raise ValueError('Original source witness lost to graph/filter')
            witness=poses[current];_,certificate=certify_array((str(n)+'-original-box-control',witness))
            if not certificate['valid']:raise ValueError('Original-box full certificate failed')
            if upper<n:raise ValueError('Clique upper bound contradicts actual independent witness')
            atomic_npz(case/'control.npz',{str(n):witness});atomic_json(case/'control.json',{'selected':current,'certificate':certificate})
            report['original_'+str(n)+'_control_passed']=True
        reports.append(report);atomic_json(args.out/'screen-results.json',reports)
        print(json.dumps({'stage':'joint_screen','depth':depth,'nodes':len(poses),'edges':stats['edges'],
            'clique_upper':upper,'unresolved_edges':stats['unresolved_conservative_edges'],'seconds':time.monotonic()-started}),flush=True)
    summary={'status':'screen_complete','seconds':time.monotonic()-started,'manifest_sha256':digest(args.out/'manifest.json'),
        'results_sha256':digest(args.out/'screen-results.json'),'cases':reports,'milp_started':False}
    atomic_json(args.out/'summary.json',summary)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portfolio',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--alternatives',type=Path,default=ROOT/'artifacts/joint-mis-inputs-v1')
    parser.add_argument('--source-spec',type=Path,help='Explicit frozen source poses, phases and exact certificates; overrides legacy299 loader.')
    parser.add_argument('--depths',type=float,nargs='+',help='Start with0, followed by strictly positive side reductions.')
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();screen(args)


if __name__=='__main__':main()
