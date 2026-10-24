"""One inclusive90s CPU control of larger-radius complete-puzzle continuation."""
import time
STARTED=time.monotonic()
import argparse
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import pandas as pd
import fq_active_pilot as fq
import fq_remote_cpu_search as remote
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_bottleneck_campaign import contact_geometry
from fq_full_structural import descendants
from compose_gadgets import legalize,side

ROOT=Path(__file__).resolve().parents[1]
BINARY_SHA='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
SAFE_SHA='2e6e39f36a7cdf54416fd3241b2daa2d161997f235f93961f945751f0510b958'
PLAN=[(147,'.45',22.),(299,'.3',29.),(335,'.3',29.)]


def rounded_run(command,timeout,**kwargs):
    """Preserve partial progress on timeout, require exact rigid return on success."""
    output=Path(command[command.index('--out')+1]);stdout=output.with_suffix('.native-stdout')
    stderr=output.with_suffix('.native-stderr')
    with stdout.open('w')as out,stderr.open('w')as err:
        process=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True)
        try:process.wait(timeout=timeout)
        except BaseException:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=1)
            raise
    text=stdout.read_text();logs=stderr.read_text()
    if process.returncode==0:
        radius=float(command[command.index('--round-r0')+1]);steps=int(command[command.index('--round-steps')+1])
        values=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',logs)]
        report=json.loads(text.strip().splitlines()[-1])
        valid=(len(values)==steps and values[-1]==0. and all(a>=b>=0 for a,b in zip(values,values[1:]))
               and report.get('round',{}).get('r0')==radius)
        atomic_json(output.with_suffix('.radius-trace.json'),dict(valid=valid,requested_radius=radius,
            steps=steps,reported_radii=values,stderr_sha256=fq.digest(stderr),stdout_sha256=fq.digest(stdout)))
        if not valid:raise ValueError('Rounded-square stage did not complete the audited zero-radius return')
    return subprocess.CompletedProcess(command,process.returncode,text,logs)


def worker(out,deadline):
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir()
    binary=Path('/tmp/squares-fq-portable-target/release/fq')
    baseline=ROOT/'artifacts/submission-fq-cpu-followup-v2-safe.csv'
    assert fq.digest(binary)==BINARY_SHA and fq.digest(baseline)==SAFE_SHA
    frame=pd.read_csv(baseline)
    inputs={};certificates={};sources={}
    for n,_,_ in PLAN:
        p=frame[frame.n==n].sort_values('square_id')[['x','y','angle']].to_numpy(float)
        original=geometry_sha(p);p=legalize(p)
        if p is None:raise ValueError('Input clearance legalization failed')
        cert=full_certificate(p)
        if not cert['valid']:raise ValueError('Input failed full unit-square gate')
        w=math.floor(side(p));key=f'{w}_{w}_{n-w*w}';inputs[key]=p;certificates[key]=cert
        sources[n]=dict(key=key,parsed_geometry_sha256=original,geometry_sha256=geometry_sha(p),
            legalized=original!=geometry_sha(p),reference_side=float(cert['independent_raw']['side_upper']))
    atomic_npz(out/'inputs.npz',inputs)
    manifest=dict(baseline=str(baseline),baseline_sha256=SAFE_SHA,binary_sha256=BINARY_SHA,
        source_commit=fq.SOURCE_COMMIT,license='MIT; Evan Daniel',plan=PLAN,workers=1,whole_ceiling_seconds=90,
        source_hashes={str(path):fq.digest(path)for path in [Path(__file__),Path(remote.__file__),Path(fq.__file__),
            ROOT/'vendor/fq/src/fq.rs',ROOT/'experiments/fq_capacity_probe.py',ROOT/'research/official_metric_v17.py']},
        input_sha256=fq.digest(out/'inputs.npz'),input_certificates=certificates,selected=sources,
        rounding_invariant='Pinned native source lowers r=r0*(1-k/K)^2, then calls set_rnd(0.0) before rigid ALM/polish.',
        no_remote_campaign=True,no_gpu=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest);records=[];remote.grouped_run=rounded_run
    for i,(n,radius,cap)in enumerate(PLAN):
        key=sources[n]['key'];p=inputs[key];mode='full_round_'+radius.replace('.','')
        options=['--loosen','1','--round-r0',radius,'--round-compress','--round-steps','12','--round-p','2',
            '--round-kick','.004','--hold-f','1.001','--outer','45','--pit','100','--flip-top','16','--v']
        fq.MODES[mode]=options;seed=16147001+i
        record,donor=remote.strict_trial((key,p,mode,str(binary),str(trials.resolve()),seed,cap,deadline-3))
        record.update(n=n,requested_radius=float(radius),whole_trial_cap=cap)
        stderr=trials/f'{key}-{mode}-{seed}.native-stderr'
        if stderr.exists():
            logs=stderr.read_text();radii=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',logs)]
            record.update(completed_return_steps=len(radii),last_reported_radius=radii[-1]if radii else None,
                native_stderr_sha256=fq.digest(stderr))
        records.append(record);atomic_json(out/'results.json',records)
        print(json.dumps({k:record.get(k)for k in ['n','status','seconds','completed_return_steps','last_reported_radius']}),flush=True)
    aggregate=remote.collect(out);diagnostics=[]
    with np.load(out/'remote-certified/donors.npz',allow_pickle=False)as z:
        for name in z.files:
            key=name.split('__')[0];p=inputs[key];q=z[name]
            gap,distance=contact_geometry(p);new_gap,new_distance=contact_geometry(q)
            before=np.triu((gap<=1e-5)&(distance<=1.6),1);after=np.triu((new_gap<=1e-5)&(new_distance<=1.6),1)
            diagnostics.append(dict(key=key,n=len(q),geometry_sha256=geometry_sha(q),side=side(q),
                reference_side=side(p),side_gain=side(p)-side(q),within_reference_plus_002=side(q)<=side(p)+.002,
                maximum_center_displacement=float(np.linalg.norm(q[:,:2]-p[:,:2],axis=1).max()),
                changed_near_contact_edges=int(np.count_nonzero(before!=after)),
                maximum_angle_change_degrees=float(np.degrees(abs((q[:,2]-p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)).max())))
    atomic_json(out/'control_report.json',dict(trials=len(records),aggregate=aggregate,diagnostics=diagnostics,
        manifest_sha256=fq.digest(out/'manifest.json'),results_sha256=fq.digest(out/'results.json'),no_full_score_claim=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+87)],start_new_session=True);forced=False
        try:process.wait(timeout=max(.01,STARTED+88-time.monotonic()))
        except subprocess.TimeoutExpired:
            forced=True
            try:os.kill(process.pid,signal.SIGSTOP)
            except ProcessLookupError:pass
            for pid in descendants(process.pid):
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=1)
        receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,workers=1,
            hard_deadline_enforced=forced,maximum_seconds=90)
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
