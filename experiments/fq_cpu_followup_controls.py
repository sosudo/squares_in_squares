"""Actual controls for the new minimum and the confirmed n498 donor corner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[variable]='1'
import numpy as np
import fq_active_pilot as fq
import fq_remote_cpu_search as remote
import fq_productive_campaign as productive
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_bottleneck_campaign import contact_geometry
from compose_gadgets import extents
from interface_junction_diagnostic import overlap_edges
from fq_full_structural import descendants

ROOT=Path(__file__).resolve().parents[1]


def corner_neighborhood(p,seed,amplitude):
    center=p[82,:2].copy();free=np.argsort(((p[:,:2]-center)**2).sum(1),kind='stable')[:40]
    frozen=np.setdiff1d(np.arange(len(p)),free)
    return frozen,dict(center=center.tolist(),center_kind='confirmed_n498_colliding_square82',
        free_indices=free.tolist(),frozen_indices=frozen.tolist(),critical_source_square=82)


def junction(first,second,target_f):
    _,a=extents(first);_,b=extents(second)
    if np.max(a.max(0)-[5,17])>target_f or np.max(b.max(0)-[17,5])>target_f:
        return dict(potentially_useful_size=False)
    ay=max(0.,target_f-(a[:,1].max()-17));bx=max(0.,target_f-(b[:,0].max()-17))
    pa=first.copy();pb=second.copy();pa[:,:2]+=[0,5+ay];pb[:,:2]+=[5+bx,0]
    pairs,depths=overlap_edges(pa,pb)
    return dict(potentially_useful_size=True,maximum_cross_penetration=max(depths,default=0.),
        squared_cross_penetration=sum(d*d for d in depths),overlap_pairs=pairs,
        phase_offsets=[[0,5+ay],[5+bx,0]],diagnostic_only=True)


def displacement(p,q):
    gap,dist=contact_geometry(p);after,after_dist=contact_geometry(q)
    old=np.triu((gap<=1e-5)&(dist<=1.6),1);new=np.triu((after<=1e-5)&(after_dist<=1.6),1)
    angles=(q[:,2]-p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
    return dict(critical82_displacement=(q[82,:2]-p[82,:2]).tolist(),
        critical82_displacement_norm=float(np.linalg.norm(q[82,:2]-p[82,:2])),
        critical82_angle_change_degrees=float(np.degrees(angles[82])),
        maximum_center_displacement=float(np.linalg.norm(q[:,:2]-p[:,:2],axis=1).max()),
        changed_contact_edges=int(np.count_nonzero(old!=new)))


def worker(out):
    started=time.monotonic();deadline=started+125;out.mkdir(exist_ok=False);(out/'trials').mkdir()
    binary=Path('/tmp/squares-fq-portable-target/release/fq')
    if fq.digest(binary)!='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d':raise ValueError('Portable binary changed')
    bank=ROOT/'artifacts/fq-remote-cpu-minima-v1/best_bank.npz'
    if fq.digest(bank)!='ef78f8119597fc5be01af55565fd097d35a1289bb4d8fc4a6a755620530f4f16':raise ValueError('Verified new minimum changed')
    corners=ROOT/'artifacts/fractional-junction-diagnostic-v1/certified-components.npz'
    if fq.digest(corners)!='9bc30ed55d7a93cd9db539f00ac3c0ea3650dde66940cb8428aac04810ca2b05':raise ValueError('Verified corner seeds changed')
    reportpath=corners.parent/'report.json';diagnostic=json.loads(reportpath.read_text());case=next(x for x in diagnostic['results']if x['n']==498)
    with np.load(bank,allow_pickle=False)as z:a=z['8_20_12'];at=a.copy();at[:,:2]=at[:,[1,0]];at[:,2]=-at[:,2]
    with np.load(corners,allow_pickle=False)as z:first=z['5_17_7__n498_first'];second=z['17_5_7__n498_second']
    inputs={'8_20_12':a,'20_8_12':at,'5_17_7':first,'17_5_7':second}
    certificates={key:full_certificate(p)for key,p in inputs.items()}
    if not all(c['valid']for c in certificates.values()):raise ValueError('Input control pose failed full gate')
    atomic_npz(out/'inputs.npz',inputs)
    initial=junction(first,second,case['target_side']-22)
    if abs(initial['maximum_cross_penetration']-case['maximum_cross_penetration'])>1e-8:
        raise ValueError('Confirmed corner target was not reproduced')
    manifest=dict(binary_sha256=fq.digest(binary),minimum_archive_sha256=fq.digest(bank),
        corners_archive_sha256=fq.digest(corners),corner_report_sha256=fq.digest(reportpath),
        control_source_sha256=fq.digest(__file__),strict_stage_source_sha256=fq.digest(remote.__file__),
        productive_source_sha256=fq.digest(productive.__file__),input_certificates=certificates,
        input_geometry={key:geometry_sha(p)for key,p in inputs.items()},initial_junction=initial,
        target_full_side=case['target_side'],candidate_full_start_used=False,trial_cap=20,workers=1)
    atomic_json(out/'manifest.json',manifest);fq.trial=remote.strict_trial
    plan=[('8_20_12','productive_circle_060'),('20_8_12','productive_contact_060'),
          ('5_17_7','corner40_soft_060'),('17_5_7','corner40_soft_060'),
          ('5_17_7','corner40_soft_060'),('17_5_7','corner40_soft_060')]
    records=[]
    for i,(key,mode)in enumerate(plan):
        if time.monotonic()>deadline-2:break
        seed=14110001+i;job=(key,inputs[key],mode,str(binary),str((out/'trials').resolve()),seed,20.,deadline)
        if mode.startswith('corner'):
            previous=productive.local.neighborhood;productive.local.neighborhood=corner_neighborhood
            try:record,_=productive.local.local_trial(job,productive.OPTIONS)
            finally:productive.local.neighborhood=previous
        else:record,_=productive.productive_trial(job,productive.OPTIONS)
        records.append(record);atomic_json(out/'trials.json',records)
        print(json.dumps(dict(key=key,mode=mode,status=record['status'],seconds=record.get('seconds'))),flush=True)
    aggregate=remote.collect(out);details=[]
    with np.load(out/'remote-certified/donors.npz',allow_pickle=False)as z:
        for name in z.files:
            key=name.split('__')[0];q=z[name];w,h,_=map(int,key.split('_'));entry=dict(key=key,geometry_sha256=geometry_sha(q),excess=fq.bloat(q,w,h))
            if key in ('5_17_7','17_5_7'):
                entry['movement']=displacement(inputs[key],q)
                entry['junction']=junction(q,second,case['target_side']-22)if key=='5_17_7'else junction(first,q,case['target_side']-22)
            details.append(entry)
    result=dict(seconds=time.monotonic()-started,trials=len(records),aggregate=aggregate,certified_stage_diagnostics=details,
        manifest_sha256=fq.digest(out/'manifest.json'),no_full_score_claim=True)
    atomic_json(out/'control_report.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if args.worker:worker(args.out)
    else:
        begin=time.monotonic();process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),'--worker'],start_new_session=True)
        forced=False
        try:process.wait(timeout=135)
        except subprocess.TimeoutExpired:
            forced=True
            try:os.kill(process.pid,signal.SIGSTOP)
            except ProcessLookupError:pass
            for pid in descendants(process.pid):
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=2)
        receipt=dict(returncode=process.returncode,hard_deadline_enforced=forced,seconds=time.monotonic()-begin,workers=1)
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
