"""Bounded native rigid finishes of four explicitly unverified GPU compression states."""
import time
STARTED=time.monotonic()
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_active_pilot as fq
import fq_remote_cpu_search as remote
from fq_full_structural import descendants
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/fq-torch-alm-native-handoff-v1/raw_states.npz'
SOURCE_SHA='158997c79816cb1c3b4e47d58d42d818d0de66ae64dd1eef7910eea731512314'
KEYS=['n335_stage0039_replica00','n335_stage0039_replica01','n335_stage0039_replica10','n335_stage0039_replica03']


def recorded_run(command,timeout,**kwargs):
    output=Path(command[command.index('--out')+1]);stdout=output.with_suffix('.native-stdout');stderr=output.with_suffix('.native-stderr')
    with stdout.open('w')as out,stderr.open('w')as err:
        process=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True)
        try:process.wait(timeout=timeout)
        except BaseException:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=1);raise
    return subprocess.CompletedProcess(command,process.returncode,stdout.read_text(),stderr.read_text())


def worker(out,deadline):
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir();binary=Path('/tmp/squares-fq-portable-target/release/fq')
    if fq.digest(SOURCE)!=SOURCE_SHA:raise ValueError('Exact GPU raw-state archive differs')
    if fq.digest(binary)!='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d':raise ValueError('Portable native binary differs')
    metadata_path=SOURCE.parent/'analysis.json';metadata=json.loads(metadata_path.read_text())
    if metadata['raw_states_sha256']!=SOURCE_SHA:raise ValueError('Source metadata archive identity differs')
    provenance={r['key']:r for r in metadata['rows']if r['key']in KEYS}
    inputs={}
    with np.load(SOURCE,allow_pickle=False)as z:
        for name in KEYS:
            p=z[name].copy();r=provenance[name]
            if p.shape!=(335,3)or not np.isfinite(p).all()or geometry_sha(p)!=r['geometry_sha256']:
                raise ValueError('Exact raw GPU geometry differs')
            if r['verified']or r['phase']!='explore-rigid-compression':raise ValueError('Expected explicitly unverified compressed starts')
            if fq.digest(ROOT/r['raw_path'])!=r['raw_archive_sha256']:raise ValueError('Source packet identity differs')
            inputs[name]=p
    atomic_npz(out/'unverified_inputs.npz',inputs)
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text());current=pointer['raw']
    report_path=Path(current['official_report'])
    if fq.digest(report_path)!=current['official_report_sha256']:raise ValueError('Current report differs')
    current_side=next(r['side']for r in json.loads(report_path.read_text())['results']if r['n']==335)
    options=['--loosen','1','--outer','45','--pit','100','--flip-top','16','--v']
    manifest=dict(raw_archive=str(SOURCE),raw_archive_sha256=SOURCE_SHA,raw_metadata_sha256=fq.digest(metadata_path),
        input_sha256=fq.digest(out/'unverified_inputs.npz'),input_provenance=provenance,
        binary_sha256=fq.digest(binary),native_commit=fq.SOURCE_COMMIT,license='MIT; Evan Daniel',
        executed_source_sha256=fq.digest(Path(__file__)),helper_hashes={str(p.relative_to(ROOT)):fq.digest(p)for p in [
            Path(remote.__file__),Path(fq.__file__),ROOT/'experiments/compose_gadgets.py',
            ROOT/'experiments/fq_capacity_probe.py',ROOT/'research/official_metric_v17.py']},
        options=options,workers=1,whole_seconds=90,per_trial_seconds=18,current_raw=current,current_raw_side=current_side,
        input_status='UNVERIFIED and overlapping. Raw spans/optimized boxes are initializer measurements, not feasible sides. Encode only translates these raw coordinates before free rigid ALM.',
        gain_semantics='Only terminal full certificates compared against the current official RAW side are admissible.',
        no_gpu_job=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest);records=[];remote.grouped_run=recorded_run
    for i,name in enumerate(KEYS):
        p=inputs[name];mode='gpu_raw_finish_'+name.rsplit('replica',1)[1];seed=20147001+i;fq.MODES[mode]=options
        begin=time.monotonic();record,_=remote.strict_trial(('18_18_11',p,mode,str(binary),str(trials.resolve()),seed,18.,deadline-4))
        record.update(raw_input_key=name,raw_input_verified=False,input_provenance=provenance[name],
            raw_initializer_span=18+fq.bloat(p,18,18),observed_trial_seconds=time.monotonic()-begin)
        if record.get('certificate',{}).get('valid'):
            terminal=record['certificate']['shared_official_gate']['raw_side']
            record.update(terminal_official_side=terminal,current_raw_side=current_side,
                terminal_side_gain_vs_current=float(current_side)-float(terminal))
        records.append(record);atomic_json(out/'results.json',records)
        print(json.dumps({k:record.get(k)for k in ['raw_input_key','status','observed_trial_seconds','terminal_official_side','terminal_side_gain_vs_current']}),flush=True)
    aggregate=remote.collect(out)
    atomic_json(out/'summary.json',dict(trials=len(records),aggregate=aggregate,workers=1,
        statuses={s:sum(r['status']==s for r in records)for s in set(r['status']for r in records)},
        terminal_sides={r['raw_input_key']:r.get('terminal_official_side')for r in records},
        strict_current_side_gains={r['raw_input_key']:r['terminal_side_gain_vs_current']for r in records if r.get('terminal_side_gain_vs_current',0)>0},
        current_raw_side=current_side,manifest_sha256=fq.digest(out/'manifest.json'),results_sha256=fq.digest(out/'results.json'),
        whole_worker_seconds=time.monotonic()-STARTED,no_raw_initializer_gain_claim=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        if args.out.exists():raise ValueError('Fresh output required')
        source=args.out.with_name(args.out.name+'-source');source.mkdir();(source/'executed_source.py').write_bytes(Path(__file__).read_bytes())
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+86)],start_new_session=True);forced=False
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
        receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,maximum_seconds=90,
            hard_deadline_enforced=forced,workers=1,source_sha256=fq.digest(Path(__file__)))
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
