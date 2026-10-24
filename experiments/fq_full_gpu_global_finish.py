"""Complete exactly24 globally selected raw v2 states; reuse unchanged controls.

No GPU work, canonical mutation, repeated controls, or adaptive extra trials.
"""
from __future__ import annotations
import time
STARTED = time.monotonic()
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import csv
import hashlib
import json
import math
import multiprocessing as mp
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from decimal import Decimal
from pathlib import Path
import shutil
import signal
import numpy as np
import fq_full_gpu_v2_native_finish as base

ROOT = Path(__file__).resolve().parents[1]
CASES = (147, 299, 335)
BASE_SHA = '8ea639b6a29ebb4dceeded24f2104ed37a12539239664d238d5ad91ef5e8a7ee'
SELECT = ROOT/'artifacts/full-raw-selection-1974-results-v1'
SELECT_PROOF_SHA = 'c2a6745212d2c83a3dd6749c381fa7e7293e996701ed4027bfe9d8404153fe35'
PREVIOUS = ROOT/'artifacts/fq-full-gpu-v2-native-finish-v1'
PREVIOUS_RESULTS_SHA = '1967f751836a95dc3c270ee5db3630a5a27c7eb27136d52b217417c6f3fdd4a3'
EXCLUDED = ROOT/'artifacts/full-gpu-v2-native-handoff-v1/selected-rows.json'
EXCLUDED_SHA = '628c79fb6928f83700a86817efe2aef1c9588d3802946402e52bdc6a72799715'
sha = base.sha
atomic_json = base.original.atomic_json
atomic_npz = base.original.atomic_npz


def encoded_hash(p, n):
    text, offsets = base.original.fq.encode(p, math.isqrt(n), math.isqrt(n))
    assert offsets == [0, 0]
    return hashlib.sha256(text.encode()).hexdigest()


def current_references(directory):
    thresholds, pointer = base.current_thresholds(directory)
    rows = {n: [] for n in CASES}
    with Path(pointer['raw']['path']).open(newline='') as stream:
        for row in csv.DictReader(stream):
            n = int(row['n'])
            if n in rows:
                assert int(row['square_id']) == len(rows[n])
                rows[n].append([float(row[k]) for k in ('x', 'y', 'angle')])
    poses = {n: np.asarray(p, dtype='<f8') for n, p in rows.items()}
    assert all(p.shape == (n, 3) and np.isfinite(p).all() for n, p in poses.items())
    official = json.loads(Path(pointer['raw']['official_report']).read_text())
    cases = {str(n): dict(n=n, reference_side=next(r['side'] for r in official['results'] if r['n']==n),
                         reference_interval_lower=str(thresholds[n])) for n in CASES}
    return poses, cases, pointer


def prepare(out):
    assert sha(base.__file__) == BASE_SHA
    assert sha(base.original.__file__) == base.ORIGINAL_SHA
    assert sha(base.BINARY) == base.original.BINARY_SHA
    assert sha(SELECT/'completion-proof.json') == SELECT_PROOF_SHA
    proof = json.loads((SELECT/'completion-proof.json').read_text())
    assert proof['status']=='complete' and proof['metadata_packets_scanned']==proof['full_packet_hashes_verified']==1974
    receipt = json.loads((SELECT/'download-receipt.json').read_text())
    assert sha(SELECT/'download-receipt.json') == proof['download_receipt_sha256']
    assert receipt['status']=='complete' and receipt['private_source_verified'] and receipt['source_sha256']==proof['source_sha256']
    for name, record in receipt['files'].items():
        assert sha(SELECT/'outputs'/name)==record['sha256']
    selection = SELECT/'outputs/selection'
    for name, field in [('selection-report.json','report_sha256'), ('selected-rows.json','selected_rows_sha256'),
                        ('selected-raw-states.npz','selected_archive_sha256')]:
        assert sha(selection/name)==proof[field]
    rows = json.loads((selection/'selected-rows.json').read_text())
    report = json.loads((selection/'selection-report.json').read_text())
    assert report['selected']==rows and len(rows)==24 and report['all_packet_hashes_verified']
    index_path=ROOT/'artifacts/full-structural-gpu-v2-results/outputs/full_structural_v2_raw_index.json'
    assert sha(index_path)==report['index_sha256']
    index=json.loads(index_path.read_text())
    entries={r['path']:r for rr in index['files'].values() for r in rr}
    audit=json.loads((selection/'full-packet-hash-audit.json').read_text())
    assert audit=={p:r['sha256'] for p,r in entries.items()} and len(audit)==1974
    assert sha(selection/'full-packet-hash-audit.json')==report['full_packet_hash_audit_sha256']
    assert sha(EXCLUDED)==EXCLUDED_SHA
    old=json.loads(EXCLUDED.read_text())
    excluded_geometry={r['geometry_sha256'] for r in old}
    excluded_input={r['native_encoded_input_sha256'] for r in old}
    assert len(old)==6
    with np.load(selection/'selected-raw-states.npz', allow_pickle=False) as archive:
        bank={k:archive[k].copy() for k in archive.files}
    assert set(bank)=={k for r in rows for k in (r['key'],r['key']+'__source_input')}
    for n in CASES:
        group=[r for r in rows if r['n']==n]
        assert len(group)==8 and len({r['source_id'] for r in group})==8
    for row in rows:
        p=bank[row['key']];origin=bank[row['key']+'__source_input'];n=row['n'];entry=entries[row['packet']]
        assert p.shape==origin.shape==(n,3) and p.dtype==origin.dtype==np.dtype('<f8') and np.isfinite(p).all()
        assert base.original.geometry_sha(p)==row['geometry_sha256'] not in excluded_geometry
        assert base.original.geometry_sha(origin)==row['input_geometry_sha256']==row['row']['mutation']['input_geometry_sha256']
        assert encoded_hash(p,n)==row['native_encoded_input_sha256'] not in excluded_input
        assert row['packet_sha256']==entry['sha256'] and row['input_array_sha256']==entry['input_sha256']
        assert row['stage'] in entry['stages'] and row['row']['n']==n and row['row']['source_id']==row['source_id']
        assert len(row['stage_array_sha256'])==64 and 0<=row['replica']<32 and row['verified_geometry'] is False
    assert len({r['geometry_sha256'] for r in rows})==24
    out.mkdir(parents=True,exist_ok=False)
    references,cases,pointer=current_references(out/'comparison')
    assert sha(PREVIOUS/'results.json')==PREVIOUS_RESULTS_SHA
    previous=json.loads((PREVIOUS/'results.json').read_text())
    controls=[];control_dir=out/'reused-controls';control_dir.mkdir()
    for n in CASES:
        record=next(r for r in previous if r['n']==n and r['source_role']=='matched_current_original_control')
        assert record['status']=='certified' and record['certificate']['valid']
        assert encoded_hash(references[n],n)==record['input_sha256']==record['native_encoded_input_sha256']
        assert base.original.geometry_sha(references[n])==record['selected_geometry_sha256']
        assert base.original.worst_certificate_side(record['certificate'])[0]==record['worst_certified_side']
        assert record['command'][record['command'].index('--seed')+1]=='9710000'
        copied={}
        for key,hashkey in [('selected_archive','selected_archive_sha256'),('native_output_path','native_output_sha256'),
                            ('certified_archive','certified_archive_sha256')]:
            path=Path(record[key]);assert sha(path)==record[hashkey]
            target=control_dir/path.name;shutil.copyfile(path,target);copied[target.name]=sha(target)
        input_path=Path(record['command'][record['command'].index('--in')+1]);assert sha(input_path)==record['input_sha256']
        shutil.copyfile(input_path,control_dir/input_path.name);copied[input_path.name]=sha(input_path)
        with np.load(record['certified_archive'],allow_pickle=False) as z:
            assert base.original.geometry_sha(z[z.files[0]])==record['geometry_sha256']
        controls.append(dict(n=n,current_reference_geometry_sha256=base.original.geometry_sha(references[n]),
            unchanged_native_encoded_input_sha256=record['input_sha256'],prior_result=record,copied_files=copied))
    atomic_json(out/'reused-controls.json',controls)
    atomic_npz(out/'current-references.npz',{str(n):p for n,p in references.items()})
    # Round-robin the fixed per-case ranking. No state is selected adaptively.
    ordered=[next(r for r in rows if r['n']==n and r['key']==f'n{n}_{rank:02d}') for rank in range(8) for n in CASES]
    slots=[dict(slot=i,n=r['n'],key=r['key'],role='globally_selected_raw_v2',geometry_sha256=r['geometry_sha256'],
        native_encoded_input_sha256=r['native_encoded_input_sha256'],seed=9710000,origin=r) for i,r in enumerate(ordered)]
    shutil.copyfile(selection/'selected-raw-states.npz',out/'inputs.npz')
    shutil.copyfile(selection/'selected-rows.json',out/'selected-rows.json')
    for name in ('completion-proof.json','download-receipt.json','verify_completion.py'):
        shutil.copyfile(SELECT/name,out/name)
    manifest=dict(status='frozen_exact24_global_raw_native_completions',slots=slots,cases=cases,baseline=pointer,
        inputs_sha256=sha(out/'inputs.npz'),selected_rows_sha256=sha(out/'selected-rows.json'),
        selection_completion_sha256=SELECT_PROOF_SHA,reused_controls_sha256=sha(out/'reused-controls.json'),
        current_references_sha256=sha(out/'current-references.npz'),excluded_rows_sha256=EXCLUDED_SHA,
        source_sha256=sha(__file__),trial_adapter_sha256=BASE_SHA,native_helper_sha256=base.ORIGINAL_SHA,
        binary_sha256=base.original.BINARY_SHA,workers=3,native_seconds=60,certificate_seconds=8,
        work_seconds=585,whole_seconds=600,extra_trials_allowed=False,
        packet_membership_scope='Pinned remote complete scanner verified full selected packet/input/stage/row hashes before retaining these arrays; locally rechecked complete receipt, index/hash-audit, selected/source arrays and all24 native encodings.',
        repeated_native_controls=False,geometries_are_unverified=True)
    atomic_json(out/'manifest.json',manifest)
    for path in out.rglob('*'):
        if path.is_file():path.chmod(0o444)
    print(json.dumps(dict(manifest_sha256=sha(out/'manifest.json'),inputs_sha256=manifest['inputs_sha256'],
                         canonical_raw=pointer['raw']['sha256'],slots=24,reused_controls=3)),flush=True)


def run(args):
    os.setsid();cpus=sorted(os.sched_getaffinity(0));assert len(cpus)>=3
    os.sched_setaffinity(0,set(cpus[:3]));deadline=STARTED+585.
    assert sha(base.__file__)==BASE_SHA and sha(base.original.__file__)==base.ORIGINAL_SHA
    assert sha(base.BINARY)==base.original.BINARY_SHA and sha(args.inputs/'manifest.json')==args.manifest_sha256
    manifest=json.loads((args.inputs/'manifest.json').read_text())
    assert sha(__file__)==manifest['source_sha256'] and sha(args.inputs/'inputs.npz')==manifest['inputs_sha256']
    assert sha(args.inputs/'reused-controls.json')==manifest['reused_controls_sha256']
    references,cases,pointer=current_references(args.out/'comparison-initial')
    controls=json.loads((args.inputs/'reused-controls.json').read_text())
    assert len(controls)==3
    for control in controls:
        n=control['n'];assert encoded_hash(references[n],n)==control['unchanged_native_encoded_input_sha256']
        assert control['prior_result']['status']=='certified' and control['prior_result']['certificate']['valid']
    with np.load(args.inputs/'inputs.npz',allow_pickle=False) as z:bank={r['key']:z[r['key']].copy() for r in manifest['slots']}
    slots=manifest['slots'];assert len(slots)==24 and [s['slot'] for s in slots]==list(range(24))
    for slot in slots:
        p=bank[slot['key']];assert base.original.geometry_sha(p)==slot['geometry_sha256']
        assert encoded_hash(p,slot['n'])==slot['native_encoded_input_sha256']
    shutil.copytree(args.inputs,args.out/'inputs')
    source=args.out/'source';source.mkdir()
    paths=[Path(__file__),Path(base.__file__),Path(base.original.__file__),Path(base.original.fq.__file__),
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_variant_campaign.py',ROOT/'experiments/compose_gadgets.py',
        ROOT/'experiments/recover_broad_native_returns.py',ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',
        ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/LICENSE']
    for path in paths:shutil.copyfile(path,source/path.name)
    (source/'generated-trial.py').write_text(base.generated_trial_source())
    atomic_json(args.out/'execution-manifest.json',dict(input_manifest_sha256=args.manifest_sha256,source_hashes={p.name:sha(p) for p in source.iterdir()},
        binary_sha256=base.original.BINARY_SHA,options=base.original.OPTIONS,seed=9710000,workers=3,native_seconds=60,
        certificate_seconds=8,work_seconds=585,whole_seconds=600,controls_reused=3,controls_rerun=0,
        no_gpu=True,no_submission=True,no_canonical_mutation=True))
    trials=args.out/'trials';trials.mkdir();records={};certified={}
    atomic_npz(args.out/'certified.npz',certified)
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('fork')) as pool:
        cursor=0;pending={}
        while cursor<len(slots) or pending:
            while len(pending)<3 and cursor<len(slots):
                slot=slots[cursor];cursor+=1
                if deadline-time.monotonic()<.2:
                    records[slot['slot']]=dict(slot,status='deadline_before_native');continue
                pending[pool.submit(base.trial,(str(trials),slot,bank[slot['key']].copy(),cases[str(slot['n'])],deadline))]=slot
            if not pending:continue
            done,_=wait(pending,timeout=.2,return_when=FIRST_COMPLETED)
            for future in done:
                slot=pending.pop(future)
                try:record,q=future.result()
                except Exception as error:record=dict(slot,status='trial_error',error_type=type(error).__name__);q=None
                records[slot['slot']]=record
                if q is not None:certified[slot['key']]=q
                atomic_json(args.out/'results.json',[records[i] for i in sorted(records)])
                atomic_npz(args.out/'certified.npz',certified)
                print(json.dumps(dict(slot=slot['slot'],n=slot['n'],status=record['status'],side=record.get('worst_certified_side'),
                    native_seconds=record.get('native_seconds'),elapsed=time.monotonic()-STARTED)),flush=True)
    final,current=base.current_thresholds(args.out/'comparison-final');candidates={}
    for row in records.values():
        if row.get('status')!='certified':continue
        n=row['n'];side=Decimal(row['worst_certified_side']);row['latest_canonical_lower']=str(final[n]);row['strict_vs_latest_canonical']=side<final[n]
        if side<final[n] and (str(n) not in candidates or side<Decimal(candidates[str(n)]['side'])):
            q=certified[row['source_key']]
            candidates[str(n)]=dict(side=str(side),squares=[[f'{v:.17g}' for v in r] for r in q],certificate=row['certificate'],
                source='Fixed completion of globally selected structural-v2 raw states',
                provenance=dict(slot=row['slot'],input_manifest_sha256=args.manifest_sha256,selected_geometry_sha256=row['selected_geometry_sha256'],
                    geometry_sha256=row['geometry_sha256'],native_input_sha256=row['input_sha256'],native_output_sha256=row['native_output_sha256']))
    atomic_json(args.out/'results.json',[records[i] for i in sorted(records)]);atomic_json(args.out/'candidates.json',candidates)
    summary=dict(status='complete' if len(records)==24 and all(r['status']=='certified' for r in records.values()) else 'bounded_partial',
        trials=len(records),certified=len(certified),improved_cases=list(candidates),seconds=time.monotonic()-STARTED,
        canonical_raw_sha256=current['raw']['sha256'],results_sha256=sha(args.out/'results.json'),
        candidates_sha256=sha(args.out/'candidates.json'),certified_archive_sha256=sha(args.out/'certified.npz'),
        controls_reused=3,controls_rerun=0,workers=3,closed_without_extra_trials=True)
    atomic_json(args.out/'summary.json',summary)
    for path in args.out.rglob('*'):
        if path.is_file():path.chmod(0o444)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',type=Path)
    parser.add_argument('--inputs',type=Path);parser.add_argument('--manifest-sha256');parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.prepare:prepare(args.prepare.resolve())
    else:
        assert args.inputs and args.manifest_sha256 and args.out
        args.inputs=args.inputs.resolve();args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
        process=mp.get_context('fork').Process(target=run,args=(args,));process.start()
        process.join(max(0.,595.-(time.monotonic()-STARTED)));forced=process.is_alive()
        if forced:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.join(timeout=max(0.,599.-(time.monotonic()-STARTED)))
        atomic_json(args.out/'supervisor.json',dict(returncode=process.exitcode,forced=forced,
            seconds=time.monotonic()-STARTED,whole_seconds=600,workers=3))
        if process.exitcode:raise SystemExit(process.exitcode)
