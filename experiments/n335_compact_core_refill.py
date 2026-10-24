"""One-minute finite compact-lattice/upright-refill screen for n335.

Cold FTMC band mutations did not cover these dense m-by-m or m-by-(m+1)
blocks. Strict finite refill capacity is a lower bound on continuous capacity;
only a complete official certificate can admit a new335-square packing.
"""
import time
STARTED=time.monotonic()
import argparse
import csv
from decimal import Decimal
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from compose_gadgets import normalize,side,legalize
from refill_search import fill_rect,sat_gaps,generate_candidates
from fq_capacity_probe import full_certificate,digest,atomic_json,geometry_sha
from period5_branch_lp import data

ROOT=Path(__file__).resolve().parents[1]
L=18.807
PITCH=1.+4e-9
MARGIN=1e-9


class CallLimit(Exception):pass
def expired(signum,frame):raise CallLimit()


def load_case(path,n):
    with path.open()as stream:rows=[r for r in csv.DictReader(stream)if int(r['n'])==n]
    rows.sort(key=lambda r:int(r['square_id']))
    if [int(r['square_id'])for r in rows]!=list(range(n)):raise ValueError('Source case identity mismatch')
    return np.array([[float(r[k])for k in ('x','y','angle')]for r in rows]),rows


def wall_grids(L):
    left=.5+MARGIN+np.arange(int(L))*PITCH;right=L-.5-MARGIN-np.arange(int(L))*PITCH
    return [np.array(np.meshgrid(x,y)).reshape(2,-1).T for x in (left,right)for y in (left,right)]


def block(spec):
    m,n=spec['m'],spec['n'];a=math.radians(spec['angle_degrees']);c,s=math.cos(a),math.sin(a)
    uv=np.array([(i-(m-1)/2,j-(n-1)/2)for i in range(m)for j in range(n)])*PITCH
    xy=uv@np.array([[c,s],[-s,c]])+np.array(spec['center'])
    return np.column_stack((xy,np.full(len(xy),a)))


def block_grid_count(grid,m,n,a,center):
    """A conservative constructive grid count using the block's convex hull.

    The tiny positive lattice pitch gives internal clearance. The convex hull
    contains that entire core, so disjointness from it implies strict separation
    from every individual core square. This is a lower bound, not an upper bound.
    """
    c,s=math.cos(a),math.sin(a);w=1+(m-1)*PITCH;h=1+(n-1)*PITCH
    d=grid-center
    gaps=np.column_stack((abs(d[:,0])-.5*(1+w*abs(c)+h*abs(s)),
        abs(d[:,1])-.5*(1+w*abs(s)+h*abs(c)),
        abs(d[:,0]*c+d[:,1]*s)-.5*(w+abs(c)+abs(s)),
        abs(-d[:,0]*s+d[:,1]*c)-.5*(h+abs(c)+abs(s))))
    return int(np.count_nonzero(gaps.max(1)>=MARGIN))


def ranked_specs():
    grids=wall_grids(L);ranked=[];pruned=[]
    angles=[math.degrees(math.atan(.5))+d for d in (0.,-.5,.5)]+[45.,44.5,45.5]
    for m in range(3,15):
        for n in (m,m+1):
            for angle in angles:
                a=math.radians(angle);c,s=abs(math.cos(a)),abs(math.sin(a))
                w,h=1+(m-1)*PITCH,1+(n-1)*PITCH;bw,bh=w*c+h*s,w*s+h*c
                if max(bw,bh)>L-2*MARGIN:
                    pruned.append(dict(m=m,n=n,angle_degrees=angle,reason='rotated_bounding_box_exceeds_L',width=bw,height=bh));continue
                # Centered fractional phases, plus four wall/corner anchors.
                centers={(L/2+dx,L/2+dy)for dx in (-.5,-.25,0.,.25,.5)for dy in (-.5,-.25,0.,.25,.5)}
                centers.update((x,y)for x in (bw/2+MARGIN,L-bw/2-MARGIN)for y in (bh/2+MARGIN,L-bh/2-MARGIN))
                for center in sorted(centers):
                    if any(center[k]-[bw,bh][k]/2<MARGIN-1e-12 or center[k]+[bw,bh][k]/2>L-MARGIN+1e-12 for k in (0,1)):continue
                    counts=[block_grid_count(grid,m,n,a,np.array(center))for grid in grids]
                    ranked.append(dict(m=m,n=n,angle_degrees=angle,center=list(center),core_count=m*n,
                        block_bbox=[bw,bh],wall_grid_upright_counts=counts,constructive_count=m*n+max(counts)))
    ranked.sort(key=lambda r:(-r['constructive_count'],-r['core_count'],r['angle_degrees'],r['center']))
    # First cover distinct shape/angle groups, then their second-best phases.
    buckets={}
    for spec in ranked:buckets.setdefault((spec['m'],spec['n'],spec['angle_degrees']),[]).append(spec)
    selected=[]
    for depth in (0,1):
        layer=[rows[depth]for rows in buckets.values()if len(rows)>depth]
        layer.sort(key=lambda r:(-r['constructive_count'],-r['core_count'],r['angle_degrees']))
        selected.extend(layer)
    return ranked,pruned,selected


def near_seed(core,uprights,grids,deadline):
    """Only retain335-count proposals if greedy added units overlap at most.05."""
    q=np.vstack((core,uprights))
    if not 330<=len(q)<335 or deadline-time.monotonic()<1:return None,None
    candidates=generate_candidates(L,L,core,None,depth=2,margin=MARGIN,soft=.05)
    candidates=np.vstack([*grids,candidates])
    _,unique=np.unique(np.round(candidates,10),axis=0,return_index=True);candidates=candidates[np.sort(unique)]
    additions=[]
    while len(q)<335:
        gaps=sat_gaps(candidates,q);i=int(np.argmax(gaps));gap=float(gaps[i])
        if gap<-.05:return None,{'failure':'minimum available overlap exceeds.05','next_minimum_gap':gap}
        additions.append(dict(center=candidates[i].tolist(),minimum_gap=gap))
        q=np.vstack((q,[*candidates[i],0.]));candidates=np.delete(candidates,i,axis=0)
    return q,{'status':'UNVERIFIED335-square exploratory seed','added_units':additions,
              'maximum_added_overlap':max(0.,max(-r['minimum_gap']for r in additions))}


def worker(args):
    os.setsid();deadline=STARTED+args.seconds-4.;out=args.out
    available=os.sched_getaffinity(0);os.sched_setaffinity(0,{min(available)})
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text());raw=Path(pointer['raw']['path'])
    if digest(raw)!=pointer['raw']['sha256']:raise ValueError('Canonical RAW source mismatch')
    original,rows=load_case(raw,335);original=normalize(original)
    report_path=Path(pointer['raw']['official_report'])
    if digest(report_path)!=pointer['raw']['official_report_sha256']:raise ValueError('Canonical report differs')
    report=json.loads(report_path.read_text())
    if not report['valid']or report['sha256']!=pointer['raw']['sha256']:raise ValueError('Canonical certificate binding failed')
    baseline=next(r['side']for r in report['results']if r['n']==335)
    hints=original[abs((original[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)<1e-8].copy();hints[:,2]=0.
    # Hints have no authority: fill_rect filters every center against this new
    # core and the actual target box before constructing the conflict graph.
    atomic_json(out/'source335-rows.json',rows)
    source=out/'source';source.mkdir();hashes={}
    for path in [Path(__file__),ROOT/'experiments/refill_search.py',ROOT/'experiments/compose_gadgets.py',
                 ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_active_pilot.py',
                 ROOT/'experiments/period5_branch_lp.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py']:
        target=source/path.name;shutil.copyfile(path,target);hashes[str(path.relative_to(ROOT))]=digest(target)
    # Existing refill method's known five-square diamond is a cheap actual control.
    control_L=2+1/math.sqrt(2)+1e-5;control=np.array([[control_L/2,control_L/2,np.pi/4]])
    up,info=fill_rect(control_L,control_L,control,time_limit=.1,margin=MARGIN,soft=0.)
    if len(up)!=4 or info['requires_repair']:raise ValueError('Strict diamond refill control failed')
    ranked,pruned,selected=ranked_specs()
    if args.selection=='dense_complement':
        groups={}
        for spec in ranked:
            if spec['m']<8 or not any(abs(spec['angle_degrees']-a)<1e-10 for a in (45.,math.degrees(math.atan(.5)))):continue
            if any(abs(v-L/2)>.50000001 for v in spec['center']):continue
            groups.setdefault((spec['m'],spec['n'],spec['angle_degrees']),spec)
        selected=sorted(groups.values(),key=lambda r:(r['n']-r['m'],r['angle_degrees']!=45.,r['m']))
    atomic_json(out/'ranking.json',ranked);atomic_json(out/'analytic-prunes.json',pruned)
    atomic_json(out/'selected-specs.json',selected[:40])
    manifest=dict(kind='finite_compact_rotated_core_n335_refill',L=L,target_count=335,source_raw=pointer['raw'],
        source_rows_sha256=digest(out/'source335-rows.json'),source_hashes=hashes,
        pure_upright_capacity=18*18,required_net_gain_over_upright_grid=11,
        area_upper_bound=math.floor(L*L),compact_core_shapes='m×m and m×(m+1), m3..14',
        core_lattice_pitch=PITCH,angle_families='atan(1/2)±.5degrees,45±.5degrees',
        phases='5×5 centered offsets, plus four wall/corner anchors when inside',
        ranked_specs=len(ranked),analytic_pruned_shape_angles=len(pruned),maximum_refill_calls=min(40,len(selected)),
        selection=args.selection,
        source_upright_hints=len(hints),hint_policy='Coordinates only; wall/SAT filter under each new core before use.',
        refill_depth=3,refill_margin=MARGIN,soft=0.,milp_component_seconds=.12,call_alarm_seconds=1.4,
        whole_seconds=args.seconds,workers=1,cpu_affinity=list(os.sched_getaffinity(0)),positive_control=info,
        limitation='Finite candidate refill optimum only; constructive grid counts are lower bounds. No unrestricted upper bound claimed.')
    atomic_json(out/'manifest.json',manifest);results=[];partials={};seeds={};valid={};grids=wall_grids(L)
    previous=signal.signal(signal.SIGALRM,expired)
    for index,spec in enumerate(selected[:40]):
        if deadline-time.monotonic()<4:break
        core=block(spec);record={'index':index,**spec,'status':'started'};begin=time.monotonic()
        pairs=np.column_stack(np.triu_indices(len(core),1));_,_,_,gaps,_=data(core,pairs)
        extent=.5*(abs(np.cos(core[:,2]))+abs(np.sin(core[:,2])))
        record.update(core_geometry_sha256=geometry_sha(core),core_min_pair_gap=float(gaps.max(1).min()),
            core_min_wall_gap=float(min((core[:,:2]-extent[:,None]).min(),(L-core[:,:2]-extent[:,None]).min())))
        if record['core_min_pair_gap']<=0 or record['core_min_wall_gap']<-.5e-9:raise ValueError('Constructed core is not strictly separated')
        signal.setitimer(signal.ITIMER_REAL,min(1.4,max(.01,deadline-time.monotonic()-2)))
        try:
            upright,refill=fill_rect(L,L,core,hints,depth=3,time_limit=.12,margin=MARGIN,soft=0.)
            record.update(status='completed',refill=refill,upright_count=len(upright),full_count=len(core)+len(upright))
        except CallLimit:record['status']='call_timeout';upright=None
        finally:signal.setitimer(signal.ITIMER_REAL,0)
        if upright is not None:
            q=np.vstack((core,upright));partials[f'case{index:03d}_count{len(q)}']=q
            record['geometry_sha256']=geometry_sha(q);record['status_label']='UNVERIFIED partial/full strict-refill output'
            if len(q)>=335:
                proposal=np.vstack((core,upright[:335-len(core)]));fixed=legalize(proposal)
                if fixed is not None and side(fixed)<float(baseline):
                    certificate=full_certificate(fixed);record['certificate']=certificate
                    if certificate['valid']and all(Decimal(value)<Decimal(baseline)for value in
                            (certificate['shared_official_gate']['raw_side'],certificate['ordinary_pandas_official_side'])):
                        valid[f'335__{geometry_sha(fixed)}']=fixed;record['status_label']='fully_certified_prospective_gain'
            else:
                seed,seedinfo=near_seed(core,upright,grids,deadline);record['near_seed']=seedinfo
                if seed is not None:seeds[f'case{index:03d}_UNVERIFIED335']=seed
        record['elapsed_seconds']=time.monotonic()-begin;results.append(record)
        np.savez_compressed(out/'strict-refill-unvalidated.npz',**partials)
        np.savez_compressed(out/'near-feasible-UNVERIFIED335.npz',**seeds)
        np.savez_compressed(out/'certified335.npz',**valid)
        atomic_json(out/'results.json',results)
    signal.signal(signal.SIGALRM,previous)
    completed=[r for r in results if r['status']=='completed']
    summary=dict(completed=True,elapsed_seconds=time.monotonic()-STARTED,ranked_specs=len(ranked),
        best_constructive_grid_count=ranked[0]['constructive_count'],attempted_refills=len(results),
        completed_refills=len(completed),timed_out=len(results)-len(completed),
        finite_optima_proved=sum(r['refill']['finite_set_optimal']for r in completed),
        best_strict_refill_count=max((r['full_count']for r in completed),default=None),
        near_feasible335_seeds=len(seeds),certified335_prospective_gains=len(valid),
        results_sha256=digest(out/'results.json'),manifest_sha256=digest(out/'manifest.json'),
        scope='Only recorded dense-block dimensions/angles/phases and finite upright candidates; no continuous impossibility claim.')
    atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=60.);parser.add_argument('--selection',choices=['grid_rank','dense_complement'],default='grid_rank')
    args=parser.parse_args()
    if not 10<=args.seconds<=60:raise ValueError('At most60seconds authorized')
    args.out.mkdir(parents=True,exist_ok=False)
    process=mp.get_context('fork').Process(target=worker,args=(args,));process.start()
    process.join(max(0.,args.seconds-1.-(time.monotonic()-STARTED)));forced=process.is_alive()
    if forced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.join(timeout=max(0.,args.seconds-(time.monotonic()-STARTED)))
    atomic_json(args.out/'supervisor.json',dict(exitcode=process.exitcode,forced_kill=forced,elapsed_seconds=time.monotonic()-STARTED,outer_seconds=args.seconds,workers=1))
    if forced or process.exitcode:raise SystemExit(1)
