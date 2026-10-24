"""One35s test of slower linear rehardening from the new moderate299 basin."""
import time
STARTED=time.monotonic()
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_active_pilot as fq
import fq_remote_cpu_search as remote
from fq_full_round_cpu_search import actual_held_run
from fq_full_structural import descendants
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from review_full_round_control import alignment

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/fq-full-round-aggressive-control-v1/strict-stages/17_17_10-aggressive_round_4_original-18147003.npz'
SOURCE_SHA='04f537c7126ddf86ba3a21989d30de2c537976e34c952f57b9225ab7cd2a8559'
CERT_SHA='b5e237eb818457f5373c4ff2b9d0e64bd3faf71e68146cb8f4bcb5f01b990c8d'


def worker(out,deadline):
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir();binary=Path('/tmp/squares-fq-portable-target/release/fq')
    if fq.digest(binary)!='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d':raise ValueError('Binary differs')
    if fq.digest(SOURCE)!=SOURCE_SHA or fq.digest(SOURCE.with_suffix('.json'))!=CERT_SHA:raise ValueError('Source differs')
    cert=json.loads(SOURCE.with_suffix('.json').read_text())
    with np.load(SOURCE)as z:p=z[z.files[0]].copy()
    if geometry_sha(p)!=cert['geometry_sha256']or not cert['certificate']['valid']:raise ValueError('Input certificate differs')
    key='17_17_10';mode='held_linear24_049_k004';seed=19147001
    options=['--loosen','1','--round-r0','.49','--round-steps','24','--round-p','1',
        '--round-kick','.004','--hold-f','1','--outer','45','--pit','100','--flip-top','16','--v','--kick','.04']
    atomic_npz(out/'inputs.npz',{key:p})
    atomic_json(out/'manifest.json',dict(source=str(SOURCE),source_sha256=SOURCE_SHA,certificate_sha256=CERT_SHA,
        source_geometry_sha256=geometry_sha(p),source_side=cert['certificate']['shared_official_gate']['raw_side'],
        source_code_sha256=fq.digest(Path(__file__)),binary_sha256=fq.digest(binary),source_commit=fq.SOURCE_COMMIT,
        license='MIT; Evan Daniel',options=options,workers=1,maximum_seconds=35,
        hold_semantics='Own selected-parent box17.82375558; not the tighter incumbent box.',
        hypothesis='Smaller initial jitter plus24 linear steps may preserve density while starting at actualradius.46958.',
        requested_initial_radius=.49,first_relaxed_radius=.49*23/24,return_steps=24,final_radius=0.))
    fq.MODES[mode]=options;remote.grouped_run=actual_held_run
    record,_=remote.strict_trial((key,p,mode,str(binary),str(trials.resolve()),seed,30.,deadline-1))
    stderr=trials/f'{key}-{mode}-{seed}.native-stderr'
    if stderr.exists():
        radii=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',stderr.read_text())]
        record['reported_radii']=radii
        record['complete_linear_return']=len(radii)==24 and radii[-1]==0. and max(abs(a-.49*(1-j/24))for j,a in enumerate(radii,1))<5.01e-5
    atomic_json(out/'results.json',[record]);aggregate=remote.collect(out);diagnostic=None
    if record.get('stage_archive'):
        if not record['complete_linear_return']:raise ValueError('Unexpected native radius trajectory')
        with np.load(record['stage_archive'])as z:q=z[z.files[0]].copy()
        diagnostic=dict(side=record['certificate']['shared_official_gate']['raw_side'],
            source_side=cert['certificate']['shared_official_gate']['raw_side'],D4_unlabeled_alignment=alignment(p,q))
    atomic_json(out/'summary.json',dict(status=record['status'],aggregate=aggregate,diagnostic=diagnostic,
        manifest_sha256=fq.digest(out/'manifest.json'),results_sha256=fq.digest(out/'results.json'),
        seconds=time.monotonic()-STARTED,no_competition_gain_claim=True))
    print(json.dumps(dict(status=record['status'],after=record.get('after'),diagnostic=diagnostic,aggregate=aggregate)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        if args.out.exists():raise ValueError('Fresh output required')
        source=args.out.with_name(args.out.name+'-source');source.mkdir();(source/'executed_source.py').write_bytes(Path(__file__).read_bytes())
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+33)],start_new_session=True);forced=False
        try:process.wait(timeout=max(.01,STARTED+33.5-time.monotonic()))
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
        receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,maximum_seconds=35,
            hard_deadline_enforced=forced,workers=1,source_sha256=fq.digest(Path(__file__)))
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
