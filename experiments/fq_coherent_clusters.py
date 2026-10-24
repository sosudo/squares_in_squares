#!/usr/bin/env python3
"""Coherent, deliberately infeasible cluster moves followed by bounded fq ALM.

One sequential worker; only independently and officially certified repaired
poses enter donor archives. References are compared across both orientations.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
import fq_active_pilot as fq
from compose_gadgets import normalize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from validate_submission import Square, validate_puzzle

FAMILIES = ((5,17,7), (7,19,13), (7,20,14))
KINDS = ('cluster_rotate', 'cluster_translate', 'band_slide', 'angle_reflect',
         'band_shear', 'cluster_rotate_large')
OPTIONS = ['--loosen', '1.001', '--outer', '45', '--pit', '80', '--flip-top', '12']
EXTRA_BANKS = [
    ('artifacts/fq-multiscale-v1/snapshot-00099/best_bank.npz',
     '5d8de5063a8c1c1559dc5a73b0f24c7bd6166609a1cabde99fd7d5ee7f38e0f7'),
    ('artifacts/fq-broad-active-polish-v1/improved-types.npz',
     '1652171f65d83a63953269734ff3d7885308c4caff23f072e745fb9abd42bf4f'),
]


class Deadline(BaseException):
    pass


def alarm(signum, frame):
    raise Deadline()


def grouped_run(command, capture_output=True, text=True, timeout=None):
    """Kill the complete owned process group on any timeout or interruption."""
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=text, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
    except BaseException:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise


def transpose(p):
    q = p.copy()
    q[:, :2] = q[:, [1, 0]]
    q[:, 2] = math.pi/2-q[:, 2]
    return normalize(q)


def reference_banks(focus):
    current = json.loads((focus/'current.json').read_text())
    snapshot = Path(current['snapshot'])
    analysis_path = snapshot/'analysis.json'
    if fq.digest(analysis_path) != current['analysis_sha256']:
        raise ValueError('Focus checkpoint changed or has an invalid hash')
    analysis = json.loads(analysis_path.read_text())
    paths = [(snapshot/'best_bank.npz', analysis['best_bank_sha256'])]
    paths += [(ROOT/name, sha) for name, sha in EXTRA_BANKS]
    best, provenance = {}, []
    for path, expected in paths:
        if fq.digest(path) != expected:
            raise ValueError(f'Reference hash mismatch: {path}')
        provenance.append({'path': str(path.resolve()), 'sha256': expected})
        with np.load(path, allow_pickle=False) as z:
            for name in z.files:
                w, h, d = map(int, name.split('__')[0].split('_'))
                canonical = (min(w,h), max(w,h), d)
                if canonical not in FAMILIES:
                    continue
                p = np.array(z[name], dtype=float, copy=True)
                if p.shape != (w*h+d, 3) or not np.isfinite(p).all():
                    raise ValueError('Invalid reference geometry shape')
                p = normalize(p) if w<=h else transpose(p)
                excess = fq.bloat(p, canonical[0], canonical[1])
                key = '_'.join(map(str, canonical))
                if key not in best or excess < best[key]['excess']:
                    best[key] = {'p': p, 'excess': excess, 'source': str(path.resolve()),
                                 'archive_key': name}
        if fq.digest(path) != expected:
            raise ValueError('Reference changed while loading')
    if len(best) != 3:
        raise ValueError('Missing a canonical family')
    return best, provenance


def connected_subset(p, rng, limit=12):
    angle = (p[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
    tilted = np.flatnonzero(abs(angle)>.02)
    if len(tilted)<2:
        raise ValueError('No nontrivial tilted cluster')
    neighbors = cKDTree(p[tilted,:2]).query_ball_tree(cKDTree(p[tilted,:2]), 1.55)
    eligible=[i for i,near in enumerate(neighbors)if len(near)>1]
    seed = int(rng.choice(eligible))if eligible else int(rng.integers(len(tilted)))
    queue, seen = [seed], {seed}
    for i in queue:
        for j in rng.permutation(neighbors[i]):
            j=int(j)
            if j not in seen and len(queue)<limit:
                seen.add(j);queue.append(j)
    return tilted[queue]


def mutate(p, w, h, kind, seed):
    rng=np.random.default_rng(seed)
    q=p.copy();indices=connected_subset(p,rng,12 if kind!='cluster_rotate_large' else 24)
    sign=1 if rng.integers(2)else-1
    details={'kind':kind,'seed':seed,'selected':indices.tolist()}
    if kind in ('cluster_rotate','cluster_rotate_large'):
        delta=sign*(.025 if kind=='cluster_rotate'else.075)
        centre=q[indices,:2].mean(0);c,s=math.cos(delta),math.sin(delta)
        rotation=np.array([[c,-s],[s,c]])
        q[indices,:2]=(q[indices,:2]-centre)@rotation.T+centre
        q[indices,2]+=delta
        details.update(angle_delta=delta,centre=centre.tolist())
    elif kind=='cluster_translate':
        theta=.25*np.angle(np.mean(np.exp(4j*q[indices,2])))
        shift=sign*.12*np.array([math.cos(theta+math.pi/2),math.sin(theta+math.pi/2)])
        q[indices,:2]+=shift;details['shift']=shift.tolist()
    elif kind=='angle_reflect':
        q[indices,2]=-q[indices,2]
        details['angle_map']='a -> -a on selected tilted subset'
    else:
        long_axis=1 if h>w else 0;short_axis=1-long_axis
        centre=float(np.quantile(p[:,long_axis],rng.uniform(.2,.8)))
        indices=np.flatnonzero(abs(p[:,long_axis]-centre)<1.65)
        shift=sign*.16
        if kind=='band_slide':q[indices,short_axis]+=shift
        elif kind=='band_shear':q[indices,short_axis]+=shift*np.sign(p[indices,long_axis]-centre)
        else:raise ValueError(kind)
        details.update(selected=indices.tolist(),long_axis=long_axis,centre=centre,shift=shift)
    details['input_geometry_sha256']=hashlib.sha256(p.astype('<f8').tobytes()).hexdigest()
    details['mutated_geometry_sha256']=hashlib.sha256(q.astype('<f8').tobytes()).hexdigest()
    return q,details


def atom_json(path,value):
    temp=path.with_suffix(path.suffix+'.incoming');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)


def atom_npz(path,poses):
    temp=path.with_suffix(path.suffix+'.incoming')
    with temp.open('wb')as f:np.savez_compressed(f,**poses)
    temp.replace(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--focus',type=Path,default=ROOT/'artifacts/fq-focus-v1')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=240)
    ap.add_argument('--trial-seconds',type=float,default=10)
    ap.add_argument('--max-trials',type=int,default=36)
    args=ap.parse_args()
    if not 0<args.seconds<=280 or not 0<args.trial_seconds<=15:
        ap.error('Use at most280s total and15s per complete trial')
    start=time.monotonic();deadline=start+args.seconds
    args.out.mkdir(parents=True,exist_ok=False);(args.out/'trials').mkdir()
    references,source_banks=reference_banks(args.focus)
    for i,entry in enumerate(source_banks):shutil.copy2(entry['path'],args.out/f'reference-{i}.npz')
    binary=args.out/'fq';shutil.copy2(args.focus/'inputs/fq',binary);binary.chmod(0o500)
    binary_sha=fq.digest(binary)
    if binary_sha!=json.loads((args.focus/'manifest.json').read_text())['binary_sha256']:
        raise ValueError('Executable snapshot hash mismatch')
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    (args.out/'fq_active_pilot.py').write_bytes(Path(fq.__file__).read_bytes())
    manifest={'source_commit':fq.SOURCE_COMMIT,'source_license':'MIT; vendor/fq/NOTICE',
              'binary_sha256':binary_sha,'source_sha256':fq.digest(Path(__file__)),
              'trial_api_sha256':fq.digest(Path(fq.__file__)),'source_banks':source_banks,
              'references':{k:{x:v for x,v in r.items()if x!='p'}for k,r in references.items()},
              'mutations':KINDS,'repair_options':OPTIONS,'seconds':args.seconds,
              'complete_trial_seconds':args.trial_seconds,'workers':1,
              'material_gain_threshold':1e-5,'no_additional_gaussian_kick':True}
    atom_json(args.out/'manifest.json',manifest)
    metric=fq.load_metric(ROOT/'research/official_metric_v17.py')
    fq.MODES['coherent_repair']=OPTIONS;fq.subprocess.run=grouped_run
    previous=signal.getsignal(signal.SIGALRM);signal.signal(signal.SIGALRM,alarm)
    records=[];donors={};near={};best={}
    jobs=[(kind,canonical,swap)for kind in KINDS for canonical in FAMILIES for swap in(False,True)]
    print(json.dumps({'stage':'start','references':{k:v['excess']for k,v in references.items()},
                      'selected':min(args.max_trials,len(jobs)),'workers':1}),flush=True)
    try:
        for i,(kind,canonical,swap)in enumerate(jobs[:args.max_trials]):
            if time.monotonic()>deadline-2:break
            w,h,d=canonical;family='_'.join(map(str,canonical));p=references[family]['p']
            if swap:w,h=h,w;p=transpose(p)
            key=f'{w}_{h}_{d}';seed=1193001+i*97
            original=p.copy();q,mutation=mutate(p,w,h,kind,seed)
            begin=time.monotonic();name=f'{key}-coherent_repair-{seed}'
            command=[str(binary.resolve()),'quench','--in',str((args.out/'trials'/f'{name}.in').resolve()),
                     '--out',str((args.out/'trials'/f'{name}.out').resolve()),'--rect-dx',str(w-min(w,h)),
                     '--rect-dy',str(h-min(w,h)),'--seed',str(seed)]+OPTIONS
            record={'trial_id':i,'key':key,'canonical':family,'mutation':mutation,'command':command}
            try:
                signal.setitimer(signal.ITIMER_REAL,min(args.trial_seconds,deadline-time.monotonic()))
                outcome,donor=fq.trial((key,q,'coherent_repair',str(binary.resolve()),str((args.out/'trials').resolve()),
                                        seed,args.trial_seconds,deadline))
                record.update(outcome)
                if donor is not None:
                    _,pose=donor
                    squares=[Square(*(format(float(v),'.17g')for v in row))for row in pose]
                    certificate=validate_puzzle(len(pose),squares);record['independent_certificate']=certificate
                    rows=[dict(n=str(len(pose)),square_id=str(j),x=s.x,y=s.y,angle=s.angle)for j,s in enumerate(squares)]
                    frame=pd.read_csv(io.StringIO(pd.DataFrame(rows).to_csv(index=False)))
                    ordinary=list(csv.DictReader(io.StringIO(frame.to_csv(index=False))))
                    transport=metric._evaluate_puzzle_worker((len(pose),ordinary));record['ordinary_roundtrip']=transport
                    if not certificate['valid']or transport[3]!='ok':
                        record['status']='failed-independent-or-ordinary-transport'
                    else:
                        f=fq.bloat(pose,w,h);gain=references[family]['excess']-f
                        record.update(reference_excess=references[family]['excess'],gain_vs_fair_reference=gain,
                                      repair_contraction_from_mutated_box=record.get('gain'),
                                      strict_improvement=gain>1e-7,material_improvement=gain>1e-5,
                                      strict_improvement_reference='orientation-fair frozen reference')
                        geom=hashlib.sha256(pose.astype('<f8').tobytes()).hexdigest()
                        archive_key=f'{key}__coherent_{geom[:24]}'
                        donors[archive_key]=pose
                        if gain>=-.02:near[archive_key]=pose
                        if family not in best or f<best[family]['excess']:
                            best[family]={'excess':f,'key':archive_key,'trial_id':i}
                assert np.array_equal(p,original)
            except Deadline:record['status']='whole-trial-timeout'
            except Exception as exc:record.update(status='error',error_type=type(exc).__name__,error=str(exc)[:200])
            finally:signal.setitimer(signal.ITIMER_REAL,0)
            record['whole_trial_seconds']=time.monotonic()-begin;records.append(record)
            atom_json(args.out/'results.json',records)
            atom_npz(args.out/'donors.npz',donors);atom_npz(args.out/'near-best-donors.npz',near)
            print(json.dumps({k:record.get(k)for k in('trial_id','key','status','gain_vs_fair_reference','whole_trial_seconds')},default=str),flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
    latest,latest_provenance=reference_banks(args.focus)
    comparison={family:{**value,'latest_reference_excess':latest[family]['excess'],
                'gain_vs_latest_fair_reference':latest[family]['excess']-value['excess']}for family,value in best.items()}
    summary={'elapsed_seconds':time.monotonic()-start,'attempted':len(records),'certified_donors':len(donors),
             'near_best_donors':len(near),'material_gain_threshold':1e-5,
             'material_families':sum(v['gain_vs_latest_fair_reference']>1e-5 for v in comparison.values()),
             'comparison':comparison,'latest_reference_provenance':latest_provenance,
             'status_counts':{s:sum(r['status']==s for r in records)for s in sorted({r['status']for r in records})},
             'donors_sha256':fq.digest(args.out/'donors.npz'),'near_best_donors_sha256':fq.digest(args.out/'near-best-donors.npz')}
    if fq.digest(binary)!=binary_sha:raise ValueError('Frozen executable changed')
    atom_json(args.out/'summary.json',summary);print(json.dumps({'stage':'complete',**summary}),flush=True)


if __name__=='__main__':main()
