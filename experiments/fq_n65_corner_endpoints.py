#!/usr/bin/env python3
"""Finite, exact contact-boundary starts for a bounded n65 FQ experiment.

Göbel construction and exact arithmetic are loaded from a hashed public MIT
snapshot by Joshua Levy. Research attribution: the squares project,
https://github.com/jlevy/squares (CC BY4.0 reports). No optimum is asserted.
Only exact-verified changed-contact states enter search. All retained floating
poses additionally pass independent interval and official raw/pandas gates.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
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

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'experiments'))
from fq_active_pilot import bloat, digest
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha
from extract_broad_active_frontier import certify_array
from compose_gadgets import legalize


class PhaseLimit(Exception):pass


@contextmanager
def phase_alarm(seconds):
    def expired(signum,frame):raise PhaseLimit('Hard phase deadline')
    previous=signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)


def sign(value):
    return value.sign() if hasattr(value, 'sign') else int(value>0)-int(value<0)


def axes(square):
    return [(square[k+1][1]-square[k][1], square[k][0]-square[k+1][0]) for k in (0,1)]


def projection(square, axis):
    values = [x*axis[0]+y*axis[1] for x,y in square]
    return min(values), max(values)


def separation(left, right):
    """Exact SAT: 1 strictly separated, 0 touching, None overlapping."""
    touching = False
    for axis in axes(left)+axes(right):
        lo, hi = projection(left,axis); other_lo,other_hi = projection(right,axis)
        gap = max(sign(lo-other_hi),sign(other_lo-hi))
        if gap>0:return 1
        if gap==0:touching=True
    return 0 if touching else None


def collision_interval(left, right, direction):
    """Open t interval of interior overlap during left+t*direction, exactly."""
    lower=upper=None
    for axis in axes(left)+axes(right):
        lo,hi=projection(left,axis); a,b=projection(right,axis)
        velocity=direction[0]*axis[0]+direction[1]*axis[1]
        s=sign(velocity)
        if not s:
            if sign(hi-a)<=0 or sign(b-lo)<=0:return None
            continue
        bounds=((a-hi)/velocity,(b-lo)/velocity)
        low,high=bounds if s>0 else bounds[::-1]
        lower=low if lower is None else max(lower,low)
        upper=high if upper is None else min(upper,high)
        if lower is not None and upper is not None and sign(upper-lower)<=0:return None
    return lower,upper


def first_block(squares, side, index, direction):
    candidates=[]; square=squares[index]
    for axis in (0,1):
        velocity=direction[axis]
        if sign(velocity)>0:candidates.append(((side-max(p[axis]for p in square))/velocity,('wall',axis,1)))
        elif sign(velocity)<0:candidates.append((min(p[axis]for p in square)/-velocity,('wall',axis,0)))
    for other, polygon in enumerate(squares):
        if other==index:continue
        interval=collision_interval(square,polygon,direction)
        if interval is None:continue
        lo,hi=interval
        if hi is not None and sign(hi)<=0:continue
        if lo is None or sign(lo)<0:raise ValueError('Initial geometry overlaps on a proposed slide')
        candidates.append((lo,('square',other)))
    end=min(value for value,_ in candidates)
    return end,[label for value,label in candidates if value==end]


def move(squares, changes):
    result=list(squares)
    for index,(direction,distance)in changes.items():
        result[index]=[(x+distance*direction[0],y+distance*direction[1])for x,y in squares[index]]
    return result


def changed_pairs(squares, indices):
    return {(min(i,j),max(i,j)) for i in indices for j in range(len(squares)) if i!=j}


def check_changed(squares, side, pairs, indices):
    return (all(sign(v)>=0 and sign(side-v)>=0 for i in indices for p in squares[i]for v in p)
            and all(separation(squares[i],squares[j])is not None for i,j in pairs))


def contacts(squares, pairs):
    return {pair for pair in pairs if separation(squares[pair[0]],squares[pair[1]])==0}


def materialize(squares):
    rows=[]
    for square in squares:
        cx=sum(p[0]for p in square)/4;cy=sum(p[1]for p in square)/4
        edge=(square[1][0]-square[0][0],square[1][1]-square[0][1])
        rows.append((float(cx),float(cy),math.atan2(float(edge[1]),float(edge[0]))))
    return legalize(np.array(rows),clearance=2e-9)


def graph(pose, indices):
    # Full angle-aware SAT gap, with a numerical active-contact tolerance only
    # for checking that the certified materialized start retains the transition.
    angle=pose[:,2]
    unit=np.stack((np.stack((np.cos(angle),np.sin(angle)),1),
                   np.stack((-np.sin(angle),np.cos(angle)),1)),1)
    delta=pose[None,:,:2]-pose[:,None,:2]
    own=np.abs(np.einsum('ijd,ikd->ijk',delta,unit))
    other=.5*np.abs(np.einsum('ikd,jld->ijkl',unit,unit)).sum(3)
    unilateral=(own-.5-other).max(2)
    gap=np.maximum(unilateral,unilateral.T)
    return {(i,j)for i,j in changed_pairs(pose,indices)if abs(gap[i,j])<=1e-7}


def exact_encoding(squares):
    return [[[[str(c)for c in value.coeffs]for value in point]for point in square]for square in squares]


def controls(args, out):
    started=time.monotonic(); deadline=started+args.control_seconds
    public=out/'public'; public.mkdir()
    files=['LICENSE','packing/cases/gobel_family/packing.py','packing/cases/gobel40/packing.py',
           'packing/src/sqpack/field.py','packing/src/sqpack/verify.py',
           'packing/witnesses/known-best/n-065.yaml']
    source_hashes={}
    for name in files:
        target=public/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(args.public_root/name,target);target.chmod(0o444)
        source_hashes[name]=digest(target)
    sys.path[:0]=[str(public/'packing'),str(public/'packing/src')]
    from cases.gobel_family.packing import build
    from sqpack.verify import verify_packing,exact_sign
    import yaml
    reports={}
    for a,b in ((1,1),(3,4),(4,5)):
        squares,side,field=build(a,b)
        report=verify_packing(squares,side,sign=exact_sign)
        if not report.valid:raise ValueError('Exact Göbel positive control failed')
        duplicate=verify_packing([*squares,squares[0]],side,sign=exact_sign)
        if duplicate.valid:raise ValueError('Exact duplicate-square negative control failed')
        pose=materialize(squares)
        _,floating=certify_array((str(len(pose)),pose))
        if not floating['valid']:raise ValueError('Materialized Göbel full certificate failed')
        reports[str(len(squares))]={'exact':asdict(report),'duplicate_rejected':not duplicate.valid,'floating':floating}
    squares,side,field=build(4,5)
    witness=yaml.safe_load((public/'packing/witnesses/known-best/n-065.yaml').read_text())['witness']
    centers=np.array([[float(sum(p[k]for p in square)/4)for k in(0,1)]for square in squares])
    ids=(43,51,55,63); selected=[]
    for witness_id in ids:
        row=next(item for item in witness['squares']if item['id']==witness_id)
        center=np.array(list(map(float,row['center'])))
        index=int(np.argmin(np.linalg.norm(centers-center,axis=1)))
        if np.linalg.norm(centers[index]-center)>1e-12:raise ValueError('Witness-to-builder identity mismatch')
        direction=tuple((field.alpha/2)*(1 if value>float(side)/2 else -1)for value in center)
        end,blockers=first_block(squares,side,index,direction)
        expected=field.alpha/2-field.rational(1)/2
        if end!=expected or sign(end)<=0:raise ValueError('Claimed first-blocking interval not recovered exactly')
        pairs=changed_pairs(squares,[index])
        middle=move(squares,{index:(direction,end/2)})
        beyond=move(squares,{index:(direction,end+field.rational(1)/10000)})
        if not check_changed(middle,side,pairs,[index])or check_changed(beyond,side,pairs,[index]):
            raise ValueError('Slide interior/beyond-end controls failed')
        selected.append({'witness_id':witness_id,'index':index,'direction':direction,'end':end,'blockers':blockers})
    indices=[item['index']for item in selected]; pairs=changed_pairs(squares,indices)
    initial_contacts=contacts(squares,pairs); initial_pose=materialize(squares)
    numeric_initial=graph(initial_pose,indices)
    states=list(itertools.product((0,1),repeat=4))
    for i in range(4):
        for rest in itertools.product((0,1),repeat=3):
            state=list(rest);state.insert(i,.5);states.append(tuple(state))
    seeds={};certificates={};state_records=[]
    for state in states:
        if not any(state):continue
        if time.monotonic()>=deadline:raise TimeoutError('Finite endpoint control deadline')
        changes={item['index']:(item['direction'],item['end']*field.rational(str(fraction)))
                 for item,fraction in zip(selected,state)if fraction}
        candidate=move(squares,changes)
        if not check_changed(candidate,side,pairs,indices):
            state_records.append({'state':state,'status':'exact-infeasible'});continue
        active=contacts(candidate,pairs); delta=active.symmetric_difference(initial_contacts)
        if not delta:continue
        pose=materialize(candidate)
        if pose is None:raise ValueError('Exact feasible endpoint could not be materialized')
        identity='8_8_1__endpoint_'+geometry_sha(pose)
        _,certificate=certify_array((identity,pose))
        if not certificate['valid']:raise ValueError('Endpoint full floating gates failed')
        numeric_delta=graph(pose,indices).symmetric_difference(numeric_initial)
        if not numeric_delta:raise ValueError('Exact transition lost during materialization')
        seeds[identity]=pose;certificates[identity]=certificate
        record={'state':state,'status':'certified_changed_contact','archive_key':identity,
                'geometry_sha256':geometry_sha(pose),'bloat':bloat(pose,8,8),
                'exact_contact_edges_removed':sorted(initial_contacts-active),
                'exact_contact_edges_added':sorted(active-initial_contacts),
                'numeric_contact_delta':sorted(numeric_delta),'changed_source_indices':sorted(changes)}
        state_records.append(record)
    if not seeds:raise ValueError('No certified changed-contact endpoint starts')
    atomic_npz(out/'endpoint_seeds.npz',seeds)
    atomic_json(out/'endpoint_certificates.json',certificates)
    atomic_json(out/'endpoint_states.json',state_records)
    atomic_json(out/'exact_construction.json',{'coordinate_field':'Q(sqrt2)','side_coefficients':[str(c)for c in side.coeffs],
        'corners':exact_encoding(squares),'slide_corner_mapping':[{'witness_id':r['witness_id'],'builder_index':r['index'],
        'direction':[[str(c)for c in d.coeffs]for d in r['direction']],
        'first_block_coefficients':[str(c)for c in r['end'].coeffs],'blockers':r['blockers']}for r in selected]})
    proof={'valid':True,'seconds':time.monotonic()-started,'source_hashes':source_hashes,
           'gobel_controls':reports,'verified_endpoint_states':len(seeds),'attempted_states':47,
           'endpoint_archive_sha256':digest(out/'endpoint_seeds.npz'),
           'certificates_sha256':digest(out/'endpoint_certificates.json'),
           'state_records_sha256':digest(out/'endpoint_states.json'),
           'exact_construction_sha256':digest(out/'exact_construction.json'),
           'slide_controls':'All four exact first blocks equal sqrt2/2-1/2; middle feasible, beyond end infeasible.',
           'graph_contract':'Exact SAT contact-edge changes incident to the four translated pieces; all unchanged pairs reused from the complete exact baseline proof.'}
    atomic_json(out/'controls.json',proof)
    return seeds,state_records,certificates


def search(args,out,seeds,state_records,certificates):
    import fq_soft_campaign as soft
    rigid_trial=soft._ordinary_trial
    started=time.monotonic();deadline=started+args.seconds
    binary=out/'fq';shutil.copyfile(args.binary,binary);binary.chmod(0o500)
    trials=out/'trials';trials.mkdir()
    with np.load(args.reference,allow_pickle=False)as archive:reference=archive['8_8_1']
    baseline=bloat(reference,8,8)
    source_paths=[Path(__file__),ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_multiscale_campaign.py',
                  ROOT/'experiments/fq_soft_campaign.py',ROOT/'experiments/extract_broad_active_frontier.py',
                  ROOT/'research/official_metric_v17.py']
    source_hashes={str(p):digest(p)for p in source_paths}
    manifest={'source_repository':'https://github.com/evand/square-packing','source_commit':'659ee62e4a9d39542a1146e8b011cc3ab6407ede',
        'license':'MIT Evan Daniel; exact builder MIT Joshua Levy, notices retained under public/LICENSE',
        'binary_sha256':digest(binary),'reference_path':str(args.reference),'reference_sha256':digest(args.reference),
        'frozen_baseline_bloat':baseline,'seconds':args.seconds,'workers':1,'trial_cap_seconds':8,
        'control_sha256':digest(out/'controls.json'),'source_hashes':source_hashes,
        'method':'Certified exact corner-contact transitions, then direct rigid polish, square-only shrink, or local aspect release; no upright refill.'}
    atomic_json(out/'manifest.json',manifest)
    records=[];donors=dict(seeds);proofs=dict(certificates);min_f=baseline
    snapshots=out/'certified_snapshots';snapshots.mkdir()
    def publish(q,certificate,origin):
        """Publish a full-gated rigid pose before any subsequent native stage."""
        nonlocal min_f
        identity='8_8_1__endpoint_native_'+geometry_sha(q)
        geometry=geometry_sha(q)
        target=snapshots/(geometry+'.npy')
        if not target.exists():
            incoming=target.with_suffix('.npy.incoming')
            with incoming.open('wb')as stream:np.save(stream,q,allow_pickle=False)
            incoming.replace(target);target.chmod(0o444)
        else:
            with target.open('rb')as stream:previous=np.load(stream,allow_pickle=False)
            if not np.array_equal(previous,q):raise ValueError('Immutable geometry collision')
        certificate_path=snapshots/(geometry+'.json')
        if not certificate_path.exists():
            atomic_json(certificate_path,{'archive_key':identity,'geometry_sha256':geometry,
                'npy_sha256':digest(target),'certificate':certificate,'origin':origin})
            certificate_path.chmod(0o444)
        donors[identity]=q;proofs[identity]=certificate
        min_f=min(min_f,bloat(q,8,8))
        return identity
    names=[r['archive_key']for r in state_records if r['status']=='certified_changed_contact']
    plans=[(name,mode)for name in names for mode in('rigid','shrink','local_aspect')]
    for count,(name,mode)in enumerate(plans):
        if time.monotonic()>=deadline-2:break
        pose=seeds[name];seed=655100+count;job=('8_8_1',pose,'endpoint_'+mode,str(binary.resolve()),str(trials.resolve()),seed,8.,deadline-1)
        if mode=='local_aspect':
            state=next(r for r in state_records if r.get('archive_key')==name)
            centers=pose[state['changed_source_indices'],:2]
            distances=np.linalg.norm(pose[:,None,:2]-centers[None],axis=2).min(axis=1)
            free=np.argsort(distances,kind='stable')[:min(36,12*len(centers))]
            frozen=sorted(set(range(65))-set(map(int,free)))
            options=['--loosen','1','--soft-compress','--soft-a0','.3','--soft-steps','8','--soft-kick','0',
                     '--hold-f','1','--outer','30','--pit','70','--flip-top','16','--v','--freeze',','.join(map(str,frozen))]
            first,donor=soft.traced_trial(job,options)
            record={'key':'8_8_1','mode':'endpoint_local_aspect','status':first['status'],
                    'soft_stage_record':first,'frozen_indices':frozen,'seed':seed}
            if donor is not None:
                q=donor[1]
                _,certificate=certify_array((name,q))
                if certificate['valid']:
                    identity=publish(q,certificate,{'stage':'rigid_return_intermediate','endpoint_source':name,
                        'native_stage_record':first})
                    record['certified_intermediate']={'archive_key':identity,'geometry_sha256':geometry_sha(q),
                        'after':bloat(q,8,8),'certificate':certificate}
                else:donor=None
                # This is an algorithm-scope guard, separate from feasibility.
                # Keep its original strict tolerance, record/reject the local
                # treatment when final native repair exceeds it, and retain any
                # independently certified rigid geometry with honest provenance.
                drift=first['fq'].get('frozen_dmax',float('inf'))
                record['frozen_motion_guard']={'tolerance':1e-12,'reported_dmax':drift,'passed':drift<=1e-12}
                if drift>1e-12:
                    record['status']='local_frozen_guard_rejected';donor=None
                elif donor is not None and deadline-time.monotonic()>2:
                    release=('8_8_1',q,'endpoint_release',str(binary.resolve()),str(trials.resolve()),seed,
                             min(4.,max(.1,deadline-time.monotonic()-1)),deadline-1)
                    released,finished=rigid_trial(release,['--loosen','0.99994','--outer','40','--pit','100','--flip-top','24'])
                    record['release_stage_record']=released
                    if finished is not None:donor=finished
        else:
            options=(['--no-alm','--loosen','1','--pit','160','--flip-top','32']if mode=='rigid'else
                     ['--loosen','1','--shrink','--d0','.0005','--dmin','.000005','--hops','0','--pit','100','--flip-top','24'])
            record,donor=rigid_trial(job,options)
        record.update(endpoint_source=name,source_geometry_sha256=geometry_sha(pose),frozen_baseline_bloat=baseline)
        if donor is not None:
            q=donor[1];identity='8_8_1__endpoint_native_'+geometry_sha(q)
            _,certificate=certify_array((identity,q))
            if certificate['valid']:
                identity=publish(q,certificate,{'stage':'final_rigid_pose','endpoint_source':name,'mode':mode,'seed':seed})
                f=bloat(q,8,8)
                # Final fields all describe this exact retained geometry. The
                # preceding stages remain separately named records above.
                record.update(retained_key=identity,geometry_sha256=geometry_sha(q),after=f,
                              certificate=certificate,after_full_gate=f,gain_vs_frozen_reference=baseline-f)
                min_f=min(min_f,f)
            else:record['full_gate_rejected']=True
        records.append(record)
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',proofs);atomic_json(out/'results.json',records)
        if count%10==0:print(json.dumps({'stage':'endpoint_search','completed':len(records),'seconds':time.monotonic()-started,'best_excess':min_f}),flush=True)
    unchanged=all(digest(path)==expected for path,expected in source_hashes.items())
    report={'status':'complete'if unchanged else'source_changed_quarantine','search_seconds':time.monotonic()-started,
        'search_limit_seconds':args.seconds,'trials_completed':len(records),'trials_planned':len(plans),
        'endpoint_starts':len(seeds),'retained_certified_geometries':len(donors),
        'baseline_excess':baseline,'minimum_excess':min_f,'strict_gain':max(0.,baseline-min_f),
        'source_hashes_unchanged':unchanged,'donors_sha256':digest(out/'donors.npz'),
        'certificates_sha256':digest(out/'certificates.json'),'results_sha256':digest(out/'results.json'),
        'manifest_sha256':digest(out/'manifest.json'),'full_puzzle_gain_claimed':False}
    atomic_json(out/'summary.json',report)
    print(json.dumps({'stage':'endpoint_search_complete',**report}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--public-root',type=Path,default=Path('/tmp/squares-research/jlevy'))
    parser.add_argument('--reference',type=Path,default=ROOT/'artifacts/n65-fq-input-v1/reference.npz')
    parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq')
    parser.add_argument('--seconds',type=float,default=300.)
    parser.add_argument('--control-seconds',type=float,default=120.)
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not 0<args.seconds<=300 or not 0<args.control_seconds<=120:raise ValueError('Require bounded control/search ceilings')
    if args.child:
        args.out.mkdir(parents=True,exist_ok=False)
        phase='controls'
        try:
            with phase_alarm(args.control_seconds):seeds,states,certificates=controls(args,args.out)
            print(json.dumps({'stage':'endpoint_controls_passed','states':len(seeds)}),flush=True)
            phase='search'
            with phase_alarm(args.seconds):search(args,args.out,seeds,states,certificates)
        except PhaseLimit:
            atomic_json(args.out/'phase_timeout.json',{'status':'hard_phase_limit','phase':phase,
                'partial_complete_certificates_preserved':True})
        return
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child'],start_new_session=True)
    try:raise SystemExit(process.wait(timeout=args.control_seconds+args.seconds+5))
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=2)
        atomic_json(args.out/'supervisor_timeout.json',{'status':'outer_bound','limit_seconds':args.control_seconds+args.seconds+5,
            'partial_certificates_preserved':True})
        raise SystemExit(2)


if __name__=='__main__':main()
