"""Bounded native rigid finishes of exact retained BEST persistent-hop states.

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
SOURCE=ROOT/'artifacts/fq-torch-hop-selected-raw-v1/outputs/final-current-best.npz'
SOURCE_SHA='7c72b4fc73cdd159676e911ef3af7081d0438275b31fe8b5d8dd3c615c0ff228'
BINDINGS=ROOT/'artifacts/fq-torch-hop-results-v1/selected-state-bindings.json'
BINDINGS_SHA='de2ffc4cba7911c816dda953121d818e857e3ae075edfc1527768935875f9bf9'
RECEIPT=SOURCE.parent.parent/'download-receipt.json'
RECEIPT_SHA='de3166a13f05f6c4fb64ab68727846f9835cbf5e24bb3895bdbdfe3588a49e26'
GPU_SOURCE_SHA='a57ae191b9c61aee32b9a505a963de1bd585dfe815bf103d83e827b067a7e3b1'
CHAINS=[8,11,28,10]
KEYS=[f'best_after_chain{i:02d}'for i in CHAINS]
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
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir();binary=Path('/tmp/squares-fq-portable-target/release/fq')
    if fq.digest(SOURCE)!=SOURCE_SHA:raise ValueError('Exact GPU raw-state archive differs')
    if fq.digest(binary)!='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d':raise ValueError('Portable native binary differs')
    if fq.digest(BINDINGS)!=BINDINGS_SHA or fq.digest(RECEIPT)!=RECEIPT_SHA:
        raise ValueError('Exact hop state bindings or authenticated download receipt differ')
    metadata=json.loads(BINDINGS.read_text());receipt=json.loads(RECEIPT.read_text())
    if metadata['final_archive_sha256']!=SOURCE_SHA or metadata['source_sha256']!=GPU_SOURCE_SHA:
        raise ValueError('Hop bindings source/archive mismatch')
    if receipt['source_sha256']!=GPU_SOURCE_SHA or not receipt['private_source_verified'] or receipt['files'][SOURCE.name]['sha256']!=SOURCE_SHA:
        raise ValueError('Private remote source/output identity mismatch')
    if not metadata['all_states_unverified']:raise ValueError('Expected explicitly unverified input bank')
    rows={r['chain']:r for r in metadata['best_states']}
    if min((r for r in rows.values()if r['source']=='source_37'),key=lambda r:r['energy'])['chain']!=10:
        raise ValueError('Fourth selected state is not the distinct-source lowest-energy best')
    packet=SOURCE.parent/'raw-hop/packet-0038.npz'
    if fq.digest(packet)!=receipt['files']['raw-hop/packet-0038.npz']['sha256']:
        raise ValueError('Last completed raw packet mismatch')
    inputs={};provenance={}
    with np.load(SOURCE,allow_pickle=False)as z:
        if z['best_after'].shape!=(32,335,3):raise ValueError('Expected32 retained335-square best states')
        with np.load(packet,allow_pickle=False)as previous:
            if not np.array_equal(z['best_after'],previous['best_after']):
                raise ValueError('Recovered final best states differ from last completed packet')
        for chain,name in zip(CHAINS,KEYS):
            p=z['best_after'][chain].copy();r=rows[chain]
            if p.shape!=(335,3)or not np.isfinite(p).all()or geometry_sha(p)!=r['geometry_sha256']:
                raise ValueError('Exact raw GPU geometry differs')
            if r['verified']or float(z['best_energy_after'][chain])!=r['energy']or float(z['sides'][chain])!=r['target']:
                raise ValueError('Best-state energy/box/unverified binding differs')
            if np.array_equal(p,z['current_after'][chain]):raise ValueError('Expected distinct retained best, not current state')
            inputs[name]=p;provenance[name]={**r,'array_key':'best_after','array_index':chain,
                'current_energy_not_selected':float(z['next_energy'][chain]),'distinct_from_current':True}
    atomic_npz(out/'unverified_inputs.npz',inputs)
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
        selected_best_chains=CHAINS,selection='Chains8/11 best per target box, chain28 second-best18.807 despite bad current; chain10 lowest-energy source_37 best.',
        input_sha256=fq.digest(out/'unverified_inputs.npz'),input_provenance=provenance,
        binary_sha256=fq.digest(binary),native_commit=fq.SOURCE_COMMIT,license='MIT; Evan Daniel',
        executed_source_sha256=fq.digest(Path(__file__)),helper_hashes={str(p.relative_to(ROOT)):fq.digest(p)for p in [
            Path(remote.__file__),Path(fq.__file__),ROOT/'experiments/compose_gadgets.py',
            ROOT/'experiments/fq_capacity_probe.py',ROOT/'research/official_metric_v17.py']},
        options=options,workers=1,whole_seconds=90,per_trial_seconds=18,current_raw=current,current_raw_side=current_side,
        input_status='UNVERIFIED and overlapping retained best_after states. Raw spans/optimized boxes are initializer measurements, not feasible sides. Encode only translates these raw coordinates before free rigid ALM.',
        gain_semantics='Only terminal full certificates compared against the current official RAW side are admissible.',
        no_gpu_job=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest);records=[];remote.grouped_run=recorded_run
    for i,name in enumerate(KEYS):
        p=inputs[name];mode='gpu_hop_best_finish_'+str(CHAINS[i]);seed=22147001+i;fq.MODES[mode]=options
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
