"""Four separately traced raw whole-row constructions, one CPU, 80s inclusive.

Reuse the unchanged MIT FQ binary, actual-held-radius checks and full gates.
Raw starts are overlapping; only completed terminal certificates admit poses.
"""
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

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/jam-row-evacuation-v1/raw_states.npz'
SOURCE_SHA='13554a44ba81d924b57d83917d7cddc1464d598b16502342bebf8db9b784528c'
PROOF=SOURCE.with_name('report.json')
PROOF_SHA='5c19e63cacbac3eebd883fea7458037f71499f045a76dcd9c6ccf48a06400b28'
PLAN=['raw335_row_all18_positive','raw335_column_all18_negative',
      'raw335_row_train17_hole1_negative','raw335_column_train17_hole1_positive']
BINARY_SHA='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
OPTIONS=['--loosen','1','--round-r0','.49','--round-steps','12','--round-p','1',
         '--round-kick','.004','--hold-f','1','--outer','45','--pit','100','--flip-top','16','--v']


def worker(out,deadline):
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir()
    binary=Path('/tmp/squares-fq-portable-target/release/fq')
    if fq.digest(binary)!=BINARY_SHA or fq.digest(SOURCE)!=SOURCE_SHA or fq.digest(PROOF)!=PROOF_SHA:
        raise ValueError('Frozen binary/input/provenance hash mismatch')
    proof=json.loads(PROOF.read_text());inputs={}
    with np.load(SOURCE,allow_pickle=False) as z:
        for name in PLAN:
            p=z[name].copy();row=proof['records'][name]
            if p.shape!=(335,3)or geometry_sha(p)!=row['array_sha256']or row['status']!='UNVERIFIED_RAW_NOT_A_PACKING':
                raise ValueError('Raw source count/geometry/status differs')
            inputs[name]=p
    atomic_npz(out/'unverified-inputs.npz',inputs)
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text())
    current=pointer['raw'];report=Path(current['official_report'])
    if fq.digest(report)!=current['official_report_sha256']or fq.digest(current['path'])!=current['sha256']:
        raise ValueError('Current canonical raw/report hash mismatch')
    current_side=next(r['side']for r in json.loads(report.read_text())['results']if r['n']==335)
    helpers=['experiments/fq_active_pilot.py','experiments/fq_remote_cpu_search.py',
             'experiments/fq_full_round_cpu_search.py','experiments/fq_full_round_control.py',
             'experiments/fq_capacity_probe.py','experiments/compose_gadgets.py',
             'experiments/fq_coherent_clusters.py','research/official_metric_v17.py']
    manifest=dict(source=str(SOURCE),source_sha256=SOURCE_SHA,proof_sha256=PROOF_SHA,selected=PLAN,
        input_sha256=fq.digest(out/'unverified-inputs.npz'),
        input_geometry_sha256={k:geometry_sha(p)for k,p in inputs.items()},
        source_code_sha256=fq.digest(Path(__file__)),binary_sha256=BINARY_SHA,
        native_source_commit=fq.SOURCE_COMMIT,license='MIT; Evan Daniel',
        helpers={p:fq.digest(ROOT/p)for p in helpers},options=OPTIONS,workers=1,
        maximum_seconds=80,per_trial_inclusive_seconds=16,requested_initial_radius=.49,
        expected_first_actual_radius=.49*11/12,expected_final_radius=0.,
        hold_semantics='Each raw source physical envelope, not its tighter18.807 diagnostic box. No round-compress, hold-f1, no new initial kick; all units free.',
        current_raw=current,current_raw_side=current_side,no_gpu=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest)
    remote.grouped_run=actual_held_run;records=[]
    for i,name in enumerate(PLAN):
        mode='row_repair_'+str(i);fq.MODES[mode]=OPTIONS.copy();seed=3358101+i
        p=inputs[name];begin=time.monotonic()
        record,_=remote.strict_trial(('18_18_11',p,mode,str(binary),str(trials.resolve()),seed,16.,deadline-3))
        record.update(raw_source_key=name,raw_source_verified=False,raw_source_record=proof['records'][name],
                      inclusive_seconds=time.monotonic()-begin,encoded_initial_side=18+fq.bloat(p,18,18))
        stderr=trials/f'18_18_11-{mode}-{seed}.native-stderr'
        if stderr.exists():
            radii=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',stderr.read_text())]
            record.update(actual_reported_radii=radii,actual_first_radius=radii[0]if radii else None,
                          actual_last_radius=radii[-1]if radii else None,native_stderr_sha256=fq.digest(stderr))
        if record.get('certificate',{}).get('valid'):
            if len(record.get('actual_reported_radii',[]))!=12 or record['actual_last_radius']!=0.:
                raise ValueError('Admitted stage lacks complete exact-zero return')
            side=record['certificate']['shared_official_gate']['raw_side']
            record.update(terminal_official_side=side,side_gain_vs_current=float(current_side)-float(side))
        records.append(record);atomic_json(out/'results.json',records)
        print(json.dumps({k:record.get(k)for k in ('raw_source_key','status','inclusive_seconds','actual_first_radius','actual_last_radius','terminal_official_side','side_gain_vs_current')}),flush=True)
    aggregate=remote.collect(out)
    atomic_json(out/'summary.json',dict(records=len(records),aggregate=aggregate,
        certified_count=sum(r.get('certificate',{}).get('valid',False)for r in records),
        current_raw_side=current_side,terminal_sides={r['raw_source_key']:r.get('terminal_official_side')for r in records},
        current_improvements={r['raw_source_key']:r['side_gain_vs_current']for r in records if r.get('side_gain_vs_current',0)>0},
        manifest_sha256=fq.digest(out/'manifest.json'),results_sha256=fq.digest(out/'results.json'),
        whole_worker_seconds=time.monotonic()-STARTED,workers=1))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--worker',action='store_true');ap.add_argument('--deadline',type=float);args=ap.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        if args.out.exists():raise ValueError('Fresh output required')
        source=args.out.with_name(args.out.name+'-source');source.mkdir()
        (source/'executed_source.py').write_bytes(Path(__file__).read_bytes())
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+76)],start_new_session=True);forced=False
        try:process.wait(timeout=max(.01,STARTED+78-time.monotonic()))
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
        receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,
            maximum_seconds=80,workers=1,hard_deadline_enforced=forced,source_sha256=fq.digest(Path(__file__)))
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
