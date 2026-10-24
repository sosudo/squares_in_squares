"""Bounded actual controls for64 connected free squares and original ALM release."""
import argparse
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
import fq_large_region_campaign as large
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_cpu_followup_controls import displacement
from fq_full_structural import descendants


def worker(out):
    started=time.monotonic();deadline=started+85;out.mkdir(exist_ok=False);(out/'trials').mkdir()
    bank=Path('artifacts/fq-remote-cpu-minima-v1/best_bank.npz');binary=Path('/tmp/squares-fq-portable-target/release/fq')
    assert fq.digest(bank)=='ef78f8119597fc5be01af55565fd097d35a1289bb4d8fc4a6a755620530f4f16'
    assert fq.digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
    with np.load(bank,allow_pickle=False)as z:p=z['8_20_12']
    transposed=p.copy();transposed[:,:2]=transposed[:,[1,0]];transposed[:,2]=-transposed[:,2]
    inputs={'8_20_12':p,'20_8_12':transposed};atomic_npz(out/'inputs.npz',inputs)
    options=productive.local.aggressive.options('.3','12','1.001')+['--kick','.06']
    release=['--loosen','1','--outer','45','--pit','100','--flip-top','16']
    productive.local.RELEASE_OPTIONS=list(release);fq.trial=remote.strict_trial
    certificates={key:full_certificate(q)for key,q in inputs.items()}
    assert all(c['valid']for c in certificates.values())
    manifest=dict(binary_sha256=fq.digest(binary),reference_archive_sha256=fq.digest(bank),
        input_certificates=certificates,input_geometry={key:geometry_sha(q)for key,q in inputs.items()},
        options=options,release_options=release,requested_free_count=64,whole_trial_seconds=20,
        source_hashes={path:fq.digest(path)for path in [__file__,remote.__file__,large.__file__,productive.__file__]})
    atomic_json(out/'manifest.json',manifest);records=[]
    for i,key in enumerate(['8_20_12','20_8_12']*2):
        job=(key,inputs[key],'large_064_soft_030',str(binary.resolve()),str((out/'trials').resolve()),14111001+i,20.,deadline)
        record,_=large.large_trial(job,options);records.append(record);atomic_json(out/'trials.json',records)
        print(json.dumps(dict(key=key,status=record['status'],after=record.get('after'),free=record.get('local_selection',{}).get('actual_free_count'))),flush=True)
    aggregate=remote.collect(out);diagnostics=[]
    with np.load(out/'remote-certified/donors.npz',allow_pickle=False)as z:
        for name in z.files:
            key=name.split('__')[0];q=z[name];w,h,_=map(int,key.split('_'));diagnostics.append(dict(key=key,
                geometry_sha256=geometry_sha(q),excess=fq.bloat(q,w,h),gain=fq.bloat(inputs[key],w,h)-fq.bloat(q,w,h),
                movement=displacement(inputs[key],q)))
    report=dict(seconds=time.monotonic()-started,trials=len(records),aggregate=aggregate,diagnostics=diagnostics,
        manifest_sha256=fq.digest(out/'manifest.json'),no_full_score_claim=True)
    atomic_json(out/'control_report.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if args.worker:worker(args.out)
    else:
        begin=time.monotonic();process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),'--worker'],start_new_session=True);forced=False
        try:process.wait(timeout=95)
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
