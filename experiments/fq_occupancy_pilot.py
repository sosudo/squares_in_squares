#!/usr/bin/env python3
"""Four changed-occupancy335 starts, one CPU,130s inclusive supervisor."""
import time
STARTED=time.monotonic()
import argparse
import inspect
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from types import SimpleNamespace
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_full_local_campaign as full
from fq_dual_cage_soft import retaining_stage_source
from fq_joint_seed_check import persistent_native_run,BINARY_SHA,RIGID
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha

ROOT=Path(__file__).resolve().parents[1]
TARGET=18.803
OPTIONS=RIGID+['--round-r0','.4','--round-steps','12','--round-p','2','--round-kick','.004',
               '--hold-f','1','--kick','.04','--v']
KEYS=['335_from_338_stress','335_from_340_stress','335_from_338_forced_tilt','335_from_340_forced_tilt']


def fixed_box_encode(p,w,h):
    """Native read_cfg accepts infeasible coordinates; keep the nominal box."""
    if w!=h or p.shape!=(335,3)or not np.isfinite(p).all():raise ValueError('Full335 finite raw pose required')
    lines=[f'335 {TARGET:.17g}']
    lines.extend(f'{x:.17g} {y:.17g} {math.degrees(a):.17g}'for x,y,a in p)
    return '\n'.join(lines)+'\n',[0,0]


def held_trace(report,logs):
    radii=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',logs)]
    native=report.get('round',{})
    valid=(len(radii)==12 and radii[-1]==0. and all(a>=b>=0. for a,b in zip(radii,radii[1:]))
        and native.get('r0')==.4 and max(abs(native.get('s_soft',math.inf)-TARGET),
            abs(native.get('s_hold',math.inf)-TARGET))<=1e-10)
    return dict(valid=valid,radii=radii,nominal_encoded_box=TARGET,native_round=native,
        initial_kick=.04,hold_factor=1.,no_round_compress=True,
        native_source_invariant='read_cfg reads supplied side/coordinates without legalization; '
            'no compression gives sa=s;hold-f1 gives sh=s;final radius0 precedes rigid finish.')


def run(args):
    signal.signal(signal.SIGTERM,full.alarm)
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    for name in('inputs','source','trials','retained'):(out/name).mkdir()
    source_manifest=json.loads((args.inputs/'manifest.json').read_text())
    archive=args.inputs/'optimizer-seeds.npz';screen_path=args.inputs/'screen.json'
    if(full.fq.digest(archive)!=source_manifest['seeds_sha256']
        or full.fq.digest(screen_path)!=source_manifest['screen_sha256']or source_manifest['seed_count']!=8
        or source_manifest['nominal_target']!=TARGET):raise ValueError('Frozen occupancy inputs changed')
    screen={r['key']:r for r in json.loads(screen_path.read_text())}
    with np.load(archive,allow_pickle=False)as bank:poses={key:bank[key].copy()for key in KEYS}
    if any(geometry_sha(q)!=screen[key]['seed_geometry_sha256']for key,q in poses.items()):raise ValueError('Seed identity mismatch')
    canonical=source_manifest['canonical335_side']
    atomic_npz(out/'inputs/seeds.npz',poses)
    shutil.copyfile(args.inputs/'manifest.json',out/'inputs/seed-manifest.json')
    shutil.copyfile(screen_path,out/'inputs/seed-screen.json')
    binary=out/'inputs/fq';shutil.copyfile(args.binary,binary);binary.chmod(0o500)
    if full.fq.digest(binary)!=BINARY_SHA:raise ValueError('Unreviewed native binary')
    paths=[Path(__file__),Path(full.__file__),ROOT/'experiments/occupancy_seed_screen.py',
        ROOT/'experiments/fq_joint_seed_check.py',ROOT/'experiments/fq_dual_cage_soft.py',
        ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_capacity_probe.py',
        ROOT/'experiments/fq_coherent_clusters.py',ROOT/'experiments/fq_variant_campaign.py',
        ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/validate_submission.py',
        ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/src/fq.rs']
    for path in paths:shutil.copyfile(path,out/'source'/path.name)
    stage_path=out/'source/retaining_run_stage.py';stage_path.write_text(retaining_stage_source())
    (out/'source/fixed_box_encode.py').write_text(inspect.getsource(fixed_box_encode))
    fq_space=dict(full.fq.__dict__);fq_space['encode']=fixed_box_encode
    namespace=dict(full.__dict__);namespace['fq']=SimpleNamespace(**fq_space);namespace['grouped_run']=persistent_native_run
    exec(compile(stage_path.read_text(),str(stage_path),'exec'),namespace);stage=namespace['run_stage']
    manifest=dict(source_manifest_sha256=full.fq.digest(args.inputs/'manifest.json'),
        source_archive_sha256=full.fq.digest(archive),source_screen_sha256=full.fq.digest(screen_path),
        source_hashes={str(path):full.fq.digest(path)for path in paths},binary_sha256=BINARY_SHA,
        source_commit=full.fq.SOURCE_COMMIT,license='MIT; Evan Daniel',canonical335_side=canonical,
        nominal_encoded_box=TARGET,initial_geometry_status='Intentional overlaps/wall violations; optimizer inputs only.',
        maximum_total_seconds=130,workers=1,inclusive_per_stage_seconds=25.,
        options=OPTIONS,keys=KEYS,no_gpu=True,no_submission=True,
        retaining_stage_sha256=full.fq.digest(stage_path),writer_sha256=full.fq.digest(out/'source/fixed_box_encode.py'))
    atomic_json(out/'manifest.json',manifest)
    records=[];donors={};proofs={}
    for index,key in enumerate(KEYS):
        p=poses[key]
        record,q=stage(p,canonical,key,OPTIONS,3353380+index,binary.resolve(),(out/'trials').resolve(),25.,args.deadline)
        record.update(source_key=key,occupancy=screen[key],encoded_box=TARGET,
            raw_input_claim='No initial validity claim; count335 and unchanged individual unit angles only.')
        if'fq'in record:
            inp=Path(record['command'][record['command'].index('--in')+1])
            record['held_box_trace']=held_trace(record['fq'],inp.with_suffix('.native-stderr').read_text())
        if q is not None:
            identity=geometry_sha(q);name='18_18_11__occupancy_'+key+'_'+identity
            donors[name]=q;proofs[name]=record['certificate'];record['archive_key']=name
            record['strict_canonical_gain']=record['side']<canonical
            record['final_tilted_count']=int((abs((q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018).sum())
            path=out/'retained'/(identity+'.npz');atomic_npz(path,{name:q});atomic_json(path.with_suffix('.json'),record)
            path.chmod(0o444);path.with_suffix('.json').chmod(0o444)
        records.append(record);atomic_json(out/'results.json',records)
        atomic_npz(out/'donors.npz',donors);atomic_json(out/'certificates.json',proofs)
        print(json.dumps(dict(key=key,status=record['status'],side=record.get('side'),
            seconds=record.get('elapsed_seconds'),tilted=record.get('final_tilted_count'))),flush=True)
    unchanged=all(full.fq.digest(path)==identity for path,identity in manifest['source_hashes'].items())
    summary=dict(status='complete'if unchanged else'source_changed_quarantine',seconds=time.monotonic()-STARTED,
        workers=1,trials=len(records),certified_variants=len(donors),canonical335_side=canonical,
        strict_gains=sum(bool(r.get('strict_canonical_gain'))for r in records),source_hashes_unchanged=unchanged,
        donors_sha256=full.fq.digest(out/'donors.npz'),certificates_sha256=full.fq.digest(out/'certificates.json'),
        results_sha256=full.fq.digest(out/'results.json'),manifest_sha256=full.fq.digest(out/'manifest.json'))
    atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=ROOT/'artifacts/occupancy-seed-screen-v2')
    parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--deadline',type=float,help=argparse.SUPPRESS);args=parser.parse_args()
    if args.child:return run(args)
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child',
        '--deadline',str(STARTED+123.)],start_new_session=True);forced=False
    try:child.wait(timeout=max(.01,STARTED+127.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=1.)
    receipt=dict(returncode=child.returncode,seconds=time.monotonic()-STARTED,maximum_total_seconds=130,
        workers=1,hard_deadline_enforced=forced)
    if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True);raise SystemExit(child.returncode)


if __name__=='__main__':main()
