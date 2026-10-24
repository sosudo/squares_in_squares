"""Bounded native rigid finishes of exact retained BEST fused-GPU hop states.

Inputs remain overlapping and unverified until the unchanged full terminal
gate succeeds. Neither low hop energy nor an initializer span is a score.
"""
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
SOURCE=ROOT/'artifacts/fq-fused-hop-finish-handoff-v1/states.npz'
SOURCE_SHA='49a1c3dccb73e359c5f341693083e08ce2147137f190c015c1c560dd7b4a876a'
BINDINGS=SOURCE.parent/'manifest.json'
BINDINGS_SHA='13d23338daf6b2d369b8e50bae5dfe1918114f52800b5d3c5e8f4d770271dec8'
FINAL=ROOT/'artifacts/fq-fused-hop-results-v1/outputs/final-current-best.npz'
FINAL_SHA='1d8b8d46fb56f649eb72043cff18e5be336c70a39902bd90b7b969388c4b2af2'
RECEIPT=FINAL.parent.parent/'download-receipt.json'
RECEIPT_SHA='a2a71a5baef8cc55c7f84f48e8ad4db156751b621206d2cafad6b58824c1cf04'
TERMINAL=ROOT/'artifacts/fq-fused-hop-terminal-packets-v1/outputs/raw-hop/packet-0675.npz'
GPU_SOURCE_SHA='e608718a725a16fc241a5ad69f711a0533e9b5cfdb699c983d1765d36a7cf1d7'
CHAINS=[1,7,15,28]
KEYS=[f'chain{i}'for i in CHAINS]
CURRENT_RAW_SHA='a0dad731adc6cacc9c882082aaf9464c7c7fc755ce4eabba6f711b1c31b969bc'
CURRENT_SAFE_SHA='6764e4b48e5218b42f4ddaae83c8e38a81168e74c573404c5e3ee961141a06f0'


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
    available=os.sched_getaffinity(0);os.sched_setaffinity(0,{min(available)})
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir();binary=Path('/tmp/squares-fq-portable-target/release/fq')
    if fq.digest(SOURCE)!=SOURCE_SHA:raise ValueError('Exact GPU raw-state archive differs')
    if fq.digest(binary)!='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d':raise ValueError('Portable native binary differs')
    if fq.digest(BINDINGS)!=BINDINGS_SHA or fq.digest(RECEIPT)!=RECEIPT_SHA:
        raise ValueError('Exact hop state bindings or authenticated download receipt differ')
    metadata=json.loads(BINDINGS.read_text());receipt=json.loads(RECEIPT.read_text())
    if metadata['states_sha256']!=SOURCE_SHA or metadata['source_sha256']!=GPU_SOURCE_SHA:
        raise ValueError('Hop bindings source/archive mismatch')
    if receipt['source_sha256']!=GPU_SOURCE_SHA or not receipt['private_source_verified'] or receipt['files'][FINAL.name]['sha256']!=FINAL_SHA:
        raise ValueError('Private remote source/output identity mismatch')
    if fq.digest(FINAL)!=FINAL_SHA or metadata['original_final_archive_sha256']!=FINAL_SHA:
        raise ValueError('Frozen final best-state archive mismatch')
    if fq.digest(TERMINAL)!=metadata['last_completed_packet']['sha256']:
        raise ValueError('Last completed raw packet mismatch')
    rows={r['chain']:r for r in metadata['selected']}
    if list(rows)!=CHAINS or [r['key']for r in metadata['selected']]!=KEYS:
        raise ValueError('Frozen selected chain inventory differs')
    source_input=ROOT/metadata['source_input_path']
    if fq.digest(source_input)!=metadata['source_input_sha256']:
        raise ValueError('Original source geometry archive differs')
    inputs={};provenance={}
    with np.load(FINAL,allow_pickle=False)as z,np.load(SOURCE,allow_pickle=False)as selected,np.load(source_input,allow_pickle=False)as source_bank:
        if z['best_after'].shape!=(32,335,3)or set(selected.files)!=set(KEYS):raise ValueError('Unexpected final/selected state inventory')
        with np.load(TERMINAL,allow_pickle=False)as previous:
            if not np.array_equal(z['best_after'],previous['best_after']):
                raise ValueError('Recovered final best states differ from last completed packet')
        for chain,name in zip(CHAINS,KEYS):
            p=selected[name].copy();r=rows[chain]
            if p.shape!=(335,3)or not np.isfinite(p).all()or geometry_sha(p)!=r['geometry_sha256']:
                raise ValueError('Exact raw GPU geometry differs')
            if not np.array_equal(p,z['best_after'][chain]):raise ValueError('Selection differs from the exact retained best state')
            if geometry_sha(source_bank[r['design']['source_key']])!=r['source_geometry_sha256']:
                raise ValueError('Source geometry binding differs')
            if r['verified']or not r['full_gate_pending']or not np.isclose(float(z['best_energy_after'][chain]),r['physical_energy'],atol=1e-12,rtol=0)or float(z['sides'][chain])!=r['box']:
                raise ValueError('Best-state energy/box/unverified binding differs')
            inputs[name]=p;provenance[name]={**r,'array_key':'best_after','array_index':chain,
                'current_energy_not_selected':float(z['next_energy'][chain]),'distinct_from_current':not np.array_equal(p,z['current_after'][chain])}
    atomic_npz(out/'unverified_inputs.npz',inputs)
    (out/'unverified_inputs.npz').chmod(0o444)
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text());current=pointer['raw']
    if current['sha256']!=CURRENT_RAW_SHA or pointer['safe']['sha256']!=CURRENT_SAFE_SHA:
        raise ValueError('Canonical source6764/current RAW changed before the frozen control')
    if fq.digest(Path(current['path']))!=CURRENT_RAW_SHA or fq.digest(Path(pointer['safe']['path']))!=CURRENT_SAFE_SHA:
        raise ValueError('Current full CSV bytes differ')
    report_path=Path(current['official_report'])
    if fq.digest(report_path)!=current['official_report_sha256']:raise ValueError('Current report differs')
    current_side=next(r['side']for r in json.loads(report_path.read_text())['results']if r['n']==335)
    options=['--loosen','1','--outer','45','--pit','100','--flip-top','16','--v']
    manifest=dict(raw_archive=str(SOURCE),raw_archive_sha256=SOURCE_SHA,raw_metadata_sha256=BINDINGS_SHA,
        bindings_path=str(BINDINGS),authenticated_download_receipt_sha256=RECEIPT_SHA,
        gpu_source_sha256=GPU_SOURCE_SHA,current_safe_sha256=CURRENT_SAFE_SHA,
        selected_best_chains=CHAINS,selection='Chains1/7 best per target box, chain15 buffered37 source, chain28 hot reference-source distinct topology.',
        final_archive_sha256=FINAL_SHA,terminal_packet_sha256=fq.digest(TERMINAL),cpu_affinity=list(os.sched_getaffinity(0)),
        input_sha256=fq.digest(out/'unverified_inputs.npz'),input_provenance=provenance,
        binary_sha256=fq.digest(binary),native_commit=fq.SOURCE_COMMIT,license='MIT; Evan Daniel',
        executed_source_sha256=fq.digest(Path(__file__)),helper_hashes={str(p.relative_to(ROOT)):fq.digest(p)for p in [
            Path(remote.__file__),Path(fq.__file__),ROOT/'experiments/compose_gadgets.py',
            ROOT/'experiments/fq_capacity_probe.py',ROOT/'research/official_metric_v17.py']},
        options=options,workers=1,whole_seconds=85,per_trial_seconds=18,current_raw=current,current_raw_side=current_side,
        input_status='UNVERIFIED and overlapping retained best_after states. Raw spans/optimized boxes are initializer measurements, not feasible sides. Encode only translates these raw coordinates before free rigid ALM.',
        gain_semantics='Only terminal full certificates compared against the current official RAW side are admissible.',
        no_gpu_job=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest);records=[];remote.grouped_run=recorded_run
    for i,name in enumerate(KEYS):
        p=inputs[name];mode='gpu_fused_best_finish_'+str(CHAINS[i]);seed=24147001+i;fq.MODES[mode]=options
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
            '--worker','--deadline',str(STARTED+81)],start_new_session=True);forced=False
        try:process.wait(timeout=max(.01,STARTED+83-time.monotonic()))
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
        receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,maximum_seconds=85,
            hard_deadline_enforced=forced,workers=1,source_sha256=fq.digest(Path(__file__)))
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
