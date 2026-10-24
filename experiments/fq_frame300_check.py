#!/usr/bin/env python3
"""Certify the uncovered300+L-frame335 seed, then two native checks in<60s."""
import time
STARTED=time.monotonic()
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_full_local_campaign as full
from fq_dual_cage_soft import retaining_stage_source
from fq_joint_seed_check import persistent_native_run,BINARY_SHA,RIGID
from joint_pose_mis_solve import gate
from compose_gadgets import border_expand,normalize,read_baseline,side
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha

ROOT=Path(__file__).resolve().parents[1]
HELD=RIGID+['--round-r0','.4','--round-steps','12','--round-p','2','--round-kick','.004',
            '--hold-f','1','--kick','.15','--v']


def held_trace(options,encoded_side,report,logs):
    radii=[float(value)for value in re.findall(r'round r ([0-9.eE+-]+) hold',logs)]
    trace=report.get('round',{})
    valid=('--round-compress'not in options and options[options.index('--hold-f')+1]=='1'
        and len(radii)==12 and radii[-1]==0. and all(a>=b>=0. for a,b in zip(radii,radii[1:]))
        and trace.get('r0')==.4 and max(abs(trace.get('s_soft',math.inf)-encoded_side),
            abs(trace.get('s_hold',math.inf)-encoded_side))<=1e-10)
    return dict(valid=valid,radii=radii,encoded_side=encoded_side,native_round=trace,
        initial_kick=.15,no_round_compress=True,hold_factor=1.,
        source_invariant='No compression:sa=s;hold-f1:sh=s;quadratic12step return ends at exact0 before rigid finish.')


def run(args):
    signal.signal(signal.SIGTERM,full.alarm)
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    for name in('source','inputs','trials','retained'):(out/name).mkdir()
    pointer=json.loads(args.portfolio.read_text());source=Path(pointer['safe']['path'])
    official=Path(pointer['safe']['official_report'])
    if(full.fq.digest(source)!=pointer['safe']['sha256']
        or full.fq.digest(official)!=pointer['safe']['official_report_sha256']):raise ValueError('Current source changed')
    report=json.loads(official.read_text())
    if not(report['valid']and report['invalid_count']==0 and report['puzzles']==1000
        and report['sha256']==pointer['safe']['sha256']and report['metric_sha256']==full.fq.OFFICIAL_SHA256):
        raise ValueError('Matching complete source certificate required')
    canonical=next(float(row['side'])for row in report['results']if row['n']==335)
    parent=normalize(read_baseline(source)[300]);raw=border_expand(parent,1)
    if raw.shape!=(335,3)or not np.array_equal(raw[:300],parent):raise ValueError('Frame count/parent attribution failed')
    atomic_npz(out/'inputs/parent300.npz',{'300':parent})
    atomic_npz(out/'inputs/frame335-raw.npz',{'335':raw})
    p,certificate=gate(raw)
    atomic_json(out/'inputs/seed-certificate.json',certificate)
    if p is None:raise ValueError('New frame seed failed full gates')
    atomic_npz(out/'inputs/seed335.npz',{'335':p})
    seed_proof=dict(status='fully_certified_frame_seed',parent_n=300,target_n=335,border_width=1,
        added_count=35,parent_rows=list(range(300)),added_frame_rows=list(range(300,335)),
        parent_geometry_sha256=geometry_sha(parent),raw_geometry_sha256=geometry_sha(raw),
        seed_geometry_sha256=geometry_sha(p),raw_side=side(raw),actual_side=side(p),canonical335_side=canonical,
        source_csv_sha256=pointer['safe']['sha256'],source_official_report_sha256=full.fq.digest(official),
        parent_archive_sha256=full.fq.digest(out/'inputs/parent300.npz'),
        raw_archive_sha256=full.fq.digest(out/'inputs/frame335-raw.npz'),
        seed_archive_sha256=full.fq.digest(out/'inputs/seed335.npz'),
        certificate_sha256=full.fq.digest(out/'inputs/seed-certificate.json'),
        row_identity='Original normalized300 unchanged first;35 exact unit frame rows appended; optional centre-only clearance preserves order/angles.',
        seed_tilted_count=int((abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018).sum()),score_gain_claimed=False)
    atomic_json(out/'inputs/seed-proof.json',seed_proof)
    print(json.dumps({'stage':'frame_seed_certified','side':side(p),'tilted_count':seed_proof['seed_tilted_count'],
                      'seed_sha256':seed_proof['seed_archive_sha256']}),flush=True)
    binary=out/'inputs/fq';shutil.copyfile(args.binary,binary);binary.chmod(0o500)
    if full.fq.digest(binary)!=BINARY_SHA:raise ValueError('Unreviewed native binary')
    paths=[Path(__file__),Path(full.__file__),ROOT/'experiments/fq_joint_seed_check.py',
        ROOT/'experiments/fq_dual_cage_soft.py',ROOT/'experiments/fq_active_pilot.py',
        ROOT/'experiments/fq_coherent_clusters.py',ROOT/'experiments/fq_capacity_probe.py',
        ROOT/'experiments/fq_variant_campaign.py',ROOT/'experiments/joint_pose_mis_solve.py',
        ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/extract_broad_active_frontier.py',
        ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/src/fq.rs']
    for path in paths:shutil.copyfile(path,out/'source'/path.name)
    stage_path=out/'source/retaining_run_stage.py';stage_path.write_text(retaining_stage_source())
    namespace=dict(full.__dict__);namespace['grouped_run']=persistent_native_run
    exec(compile(stage_path.read_text(),str(stage_path),'exec'),namespace);stage=namespace['run_stage']
    manifest=dict(parent_source_csv=str(source),parent_csv_sha256=full.fq.digest(source),
        canonical335_side=canonical,seed_proof_sha256=full.fq.digest(out/'inputs/seed-proof.json'),
        binary_sha256=BINARY_SHA,source_commit=full.fq.SOURCE_COMMIT,license='MIT; Evan Daniel',
        source_hashes={str(path):full.fq.digest(path)for path in paths},retaining_stage_sha256=full.fq.digest(stage_path),
        options={'rigid':RIGID,'held_box':HELD},stage_caps_seconds={'rigid':15.,'held_box':30.},
        workers=1,maximum_total_seconds=60,independent_starts=True,no_gpu=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest)
    records=[];donors={};proofs={}
    for index,(mode,options,cap)in enumerate((('rigid',RIGID,15.),('held_box',HELD,30.))):
        record,q=stage(p.copy(),canonical,mode,options,3353000+index,binary.resolve(),
            (out/'trials').resolve(),cap,args.deadline)
        if mode=='held_box'and'fq'in record:
            inp=Path(record['command'][record['command'].index('--in')+1])
            encoded=float(inp.read_text().splitlines()[0].split()[1])
            record['held_box_trace']=held_trace(options,encoded,record['fq'],inp.with_suffix('.native-stderr').read_text())
        if q is not None:
            key='18_18_11__frame300_'+mode+'_'+geometry_sha(q)
            donors[key]=q;proofs[key]=record['certificate'];record['archive_key']=key
            record['strict_canonical_gain']=record['side']<canonical
            target=out/'retained'/(geometry_sha(q)+'.npz')
            atomic_npz(target,{key:q});atomic_json(target.with_suffix('.json'),record)
            target.chmod(0o444);target.with_suffix('.json').chmod(0o444)
        records.append(record);atomic_json(out/'results.json',records)
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',proofs)
        print(json.dumps({'stage':'frame_native','mode':mode,'status':record['status'],'side':record.get('side'),
            'seconds':record.get('elapsed_seconds')}),flush=True)
    unchanged=all(full.fq.digest(path)==identity for path,identity in manifest['source_hashes'].items())
    summary=dict(status='complete'if unchanged else'source_changed_quarantine',seconds=time.monotonic()-STARTED,
        workers=1,canonical335_side=canonical,seed_side=side(p),certified_native_variants=len(donors),
        strict_gains=sum(bool(record.get('strict_canonical_gain'))for record in records),source_hashes_unchanged=unchanged,
        donors_sha256=full.fq.digest(out/'donors.npz'),certificates_sha256=full.fq.digest(out/'certificates.json'),
        results_sha256=full.fq.digest(out/'results.json'),manifest_sha256=full.fq.digest(out/'manifest.json'))
    atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portfolio',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--deadline',type=float,help=argparse.SUPPRESS);args=parser.parse_args()
    if args.child:return run(args)
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child',
        '--deadline',str(STARTED+55.)],start_new_session=True);forced=False
    try:child.wait(timeout=max(.01,STARTED+57.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=1.)
    result=dict(returncode=child.returncode,seconds=time.monotonic()-STARTED,maximum_total_seconds=60,
        workers=1,hard_deadline_enforced=forced)
    if args.out.exists():atomic_json(args.out/'supervisor.json',result)
    print(json.dumps(result),flush=True);raise SystemExit(child.returncode)


if __name__=='__main__':main()
