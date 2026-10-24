"""Finite native finishing of24 current cases with no ALM command in the pinned history."""
from __future__ import annotations
import time
STARTED=time.monotonic()
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,inspect,json,math,multiprocessing as mp,shutil,signal,sys,types
from concurrent.futures import ProcessPoolExecutor,FIRST_COMPLETED,wait
from decimal import Decimal
from pathlib import Path
import numpy as np
import fq_restart_hop_finish as original
from recover_broad_native_returns import current_thresholds

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL_SHA='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
BINARY=Path('/tmp/squares-fq-portable-target/release/fq')
CASES=(604,796,811,371,540,304,507,875,333,450,182,420,707,810,463,935,817,603,930,491,292,793,700,912)
EXPOSURE=ROOT/'artifacts/current-fresh-alm-exposure-v2'
EXPOSURE_SHA='fc33143da53729f9fa94614e614d44b2d39cab9ddae8aaa4ede60d721c152bfb'
RAW_SHA='051bbbe869bd4c2c1d70c42b6bf110f8414253d9537338442c30c88c1626715d'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generated_trial_source():
    assert sha(original.__file__)==ORIGINAL_SHA
    source=inspect.getsource(original._finish_slot)
    old='UNVERIFIED exact committed BEST array';assert source.count(old)==1
    return source.replace(old,'Exact current original RAW pose; native encoding translates only; output requires all full gates')


def trial(payload):
    out,slot,pose,case,deadline=payload
    namespace=dict(vars(original),NATIVE_SECONDS=60.,CERTIFICATE_SECONDS=8.)
    exec(compile(generated_trial_source(),'<fixed fresh-case current native finish>','exec'),namespace)
    record,q=namespace['_finish_slot'](Path(out),dict(slot,arm=slot['role'],delta=.002,chain=slot['slot']),
        pose,dict(case,n=slot['n'],source_key=slot['key']),BINARY,deadline)
    record['source_role']=slot['role'];record['source_key']=slot['key']
    if 'command' in record:assert record['command'][record['command'].index('--seed')+1]=='9710000'
    return record,q


def run(args):
    os.setsid();assert {2,3} <= os.sched_getaffinity(0)
    os.sched_setaffinity(0,{2,3});deadline=STARTED+880.
    assert sha(original.__file__)==ORIGINAL_SHA and sha(BINARY)==original.BINARY_SHA
    assert sha(EXPOSURE/'report.json')==EXPOSURE_SHA
    exposure=json.loads((EXPOSURE/'report.json').read_text())
    assert exposure['baseline']['sha256']==RAW_SHA and sha(exposure['baseline']['path'])==RAW_SHA
    assert tuple(exposure['selection'])==CASES
    assert sha(EXPOSURE/'inputs/current-poses.npz')==exposure['inputs_archive_sha256']
    original.atomic_json(args.out/'exposure-proof.json',exposure)
    inputs=args.out/'inputs';inputs.mkdir()
    shutil.copyfile(EXPOSURE/'inputs/current-poses.npz',inputs/'current-poses.npz')
    with np.load(inputs/'current-poses.npz',allow_pickle=False) as archive:
        bank={f'reference_{n}':archive[str(n)].copy() for n in CASES}
    selected={r['n']:r for r in exposure['selected']}
    config=dict(baseline=exposure['baseline'],cases={str(n):dict(n=n,source_key=f'reference_{n}',
        reference_side=selected[n]['side'],baseline_sha256=RAW_SHA) for n in CASES})
    proof=dict(inputs_sha256=exposure['inputs_archive_sha256'],exposure_sha256=EXPOSURE_SHA)
    for n in CASES:
        row=selected[n]
        assert row['ALM_exposure']['category']=='no_same_case_ALM_command_in_corpus'
        assert not row['exclusions'] and original.geometry_sha(bank[f'reference_{n}'])==row['geometry_sha256']
        encoded,_=original.fq.encode(bank[f'reference_{n}'],math.isqrt(n),math.isqrt(n))
        assert hashlib.sha256(encoded.encode()).hexdigest()==row['native_input_sha256']
        assert sha(EXPOSURE/'inputs'/f'n{n}.in')==row['native_input_sha256']
        shutil.copyfile(EXPOSURE/'inputs'/f'n{n}.in',inputs/f'n{n}.in')
    slots=[]
    for i,n in enumerate(CASES):
        pose=bank[f'reference_{n}'];encoded,_=original.fq.encode(pose,math.isqrt(n),math.isqrt(n))
        slots.append(dict(slot=i,n=n,key=f'reference_{n}',role='original_reference',
            geometry_sha256=original.geometry_sha(pose),seed=9710000,
            native_encoded_input_sha256=hashlib.sha256(encoded.encode()).hexdigest()))
    manifest=dict(cases=config['cases'],slots=slots,baseline=config['baseline'],
        inputs_sha256=proof['inputs_sha256'],exposure_report_sha256=EXPOSURE_SHA,
        source_case_rows={str(n):selected[n]['raw_case_rows_sha256'] for n in CASES},
        input_status='Exact original canonical RAW arrays; native encoder translates only. No perturbation, compression or rescaling.',
        exposure_scope=exposure['scopes'],novelty='No ALM command for these24cases in21 explicit histories; not a global never-tried claim.')
    original.atomic_json(args.out/'input-manifest.json',manifest)
    input_manifest_sha256=sha(args.out/'input-manifest.json')
    assert len(slots)==24 and set(bank)=={r['key'] for r in slots}
    for row in slots:
        p=bank[row['key']];n=row['n']
        assert p.shape==(n,3) and np.isfinite(p).all() and p.dtype==np.dtype('<f8')
        assert original.geometry_sha(p)==row['geometry_sha256'] and row['seed']==9710000
        encoded,offsets=original.fq.encode(p,math.isqrt(n),math.isqrt(n));assert offsets==[0,0]
        assert hashlib.sha256(encoded.encode()).hexdigest()==row['native_encoded_input_sha256']
    thresholds,pointer=current_thresholds(args.out/'comparison-initial')
    source=args.out/'source';source.mkdir()
    paths=[Path(__file__),ROOT/'experiments/prepare_fresh_case_alm_exposure.py',ROOT/'experiments/prepare_current_full_alm_exposure.py',Path(original.__file__),Path(original.fq.__file__),
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_variant_campaign.py',
        ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/recover_broad_native_returns.py',
        ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/LICENSE']
    for p in paths:shutil.copyfile(p,source/p.name)
    (source/'generated-trial.py').write_text(generated_trial_source())
    execution=dict(input_manifest_sha256=input_manifest_sha256,input_sha256=manifest['inputs_sha256'],
        input_slots=slots,source_hashes={p.name:sha(p) for p in source.iterdir()},
        binary_sha256=original.BINARY_SHA,source_commit=original.fq.SOURCE_COMMIT,
        options=original.OPTIONS,seed=9710000,workers=2,native_seconds=60,certificate_seconds=8,
        work_seconds=880,whole_seconds=900,affinity=[2,3],all_twenty_four_have_no_ALM_case_command_in_pinned_corpus=True,
        input_status='Twenty-four exact current RAW references; only the explicitly pinned corpus establishes absent ALM case history.',
        no_gpu=True,no_submission=True,no_canonical_mutation=True)
    original.atomic_json(args.out/'execution-manifest.json',execution)
    trial_dir=args.out/'trials';trial_dir.mkdir();records={};certified={}
    # No GPU-derived initializer is used in this bounded original-only control.
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork')) as pool:
        for phase_slots in (slots,):
            pending={};cursor=0
            while cursor<len(phase_slots) or pending:
                while len(pending)<2 and cursor<len(phase_slots):
                    slot=phase_slots[cursor];cursor+=1
                    if deadline-time.monotonic()<.2:
                        records[slot['slot']]=dict(slot,status='deadline_before_native');continue
                    case=manifest['cases'][str(slot['n'])]
                    payload=(str(trial_dir),slot,bank[slot['key']].copy(),case,deadline)
                    pending[pool.submit(trial,payload)]=slot
                if not pending:continue
                done,_=wait(pending,timeout=.2,return_when=FIRST_COMPLETED)
                for future in done:
                    slot=pending.pop(future)
                    try:record,q=future.result()
                    except Exception as error:
                        record=dict(slot,status='trial_error',error_type=type(error).__name__);q=None
                    records[slot['slot']]=record
                    if q is not None:certified[slot['key']]=q
                    original.atomic_json(args.out/'results.json',[records[i] for i in sorted(records)])
                    original.atomic_npz(args.out/'certified.npz',certified)
                    print(json.dumps(dict(slot=slot['slot'],n=slot['n'],role=slot['role'],status=record['status'],
                        side=record.get('worst_certified_side'),native_seconds=record.get('native_seconds'),elapsed=time.monotonic()-STARTED)),flush=True)
    final,current=current_thresholds(args.out/'comparison-final');candidates={}
    for row in records.values():
        if row.get('status')!='certified':continue
        n=row['n'];side=Decimal(row['worst_certified_side']);row['strict_vs_latest_canonical']=side<final[n]
        row['latest_canonical_lower']=str(final[n]);q=certified[row['source_key']]
        if side<final[n] and (str(n) not in candidates or side<Decimal(candidates[str(n)]['side'])):
            candidates[str(n)]=dict(side=str(side),squares=[[f'{v:.17g}' for v in r] for r in q],certificate=row['certificate'],
                source='First ALM treatment of current reference in pinned case history',source_role=row['source_role'],
                provenance=dict(slot=row['slot'],key=row['source_key'],input_manifest_sha256=input_manifest_sha256,
                    source_geometry_sha256=row['selected_geometry_sha256'],geometry_sha256=row['geometry_sha256'],
                    native_input_sha256=row['input_sha256'],native_output_sha256=row['native_output_sha256']))
    original.atomic_json(args.out/'results.json',[records[i] for i in sorted(records)])
    original.atomic_json(args.out/'candidates.json',candidates)
    control_failed=any(records.get(s['slot'],{}).get('status')!='certified' for s in slots)
    status='bounded_partial' if control_failed else 'complete'
    summary=dict(status=status,trials=len(records),certified=len(certified),improved_cases=list(candidates),
        seconds=time.monotonic()-STARTED,canonical_raw_sha256=current['raw']['sha256'],
        results_sha256=sha(args.out/'results.json'),certified_archive_sha256=sha(args.out/'certified.npz'),
        candidates_sha256=sha(args.out/'candidates.json'),manifest_sha256=sha(args.out/'execution-manifest.json'),
        no_gpu=True,no_submission=True,no_canonical_mutation=True)
    original.atomic_json(args.out/'summary.json',summary)
    for p in args.out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
    process=mp.get_context('fork').Process(target=run,args=(args,));process.start()
    process.join(max(0.,890.-(time.monotonic()-STARTED)));forced=process.is_alive()
    if forced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.join(timeout=max(0.,899.-(time.monotonic()-STARTED)))
    original.atomic_json(args.out/'supervisor.json',dict(returncode=process.exitcode,forced=forced,
        seconds=time.monotonic()-STARTED,whole_seconds=900,workers=2,affinity=[2,3]))
