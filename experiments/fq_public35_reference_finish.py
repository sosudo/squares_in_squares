"""Finite native finishing of eighteen newly adopted public35 geometries."""
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
CASES=(978,983,863,804,509,602,753,867,705,651,985,984,465,652,809,423,706,754)
sys.path.insert(0,str(ROOT/'scripts'))
import build_fq_restart_hop_job as input_builder
INPUT_BUILDER_SHA='42207fe5db2dd6156128f6f917f91e6d607ff9d37767a6a71f7bc010ca829b03'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generated_trial_source():
    assert sha(original.__file__)==ORIGINAL_SHA
    source=inspect.getsource(original._finish_slot)
    old='UNVERIFIED exact committed BEST array';assert source.count(old)==1
    return source.replace(old,'Exact current original reference with recorded translation only; output requires all full gates')


def trial(payload):
    out,slot,pose,case,deadline=payload
    namespace=dict(vars(original),NATIVE_SECONDS=60.,CERTIFICATE_SECONDS=8.)
    exec(compile(generated_trial_source(),'<fixed public35 newly adopted reference native finish>','exec'),namespace)
    record,q=namespace['_finish_slot'](Path(out),dict(slot,arm=slot['role'],delta=.002,chain=slot['slot']),
        pose,dict(case,n=slot['n'],source_key=slot['key']),BINARY,deadline)
    record['source_role']=slot['role'];record['source_key']=slot['key']
    if 'command' in record:assert record['command'][record['command'].index('--seed')+1]=='9710000'
    return record,q


def run(args):
    os.setsid();cpus=sorted(os.sched_getaffinity(0));assert len(cpus)>=2
    os.sched_setaffinity(0,set(cpus[:2]));deadline=STARTED+640.
    assert sha(original.__file__)==ORIGINAL_SHA and sha(BINARY)==original.BINARY_SHA
    assert sha(input_builder.__file__)==INPUT_BUILDER_SHA
    assert json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text())['raw']['sha256']=='b39204c7f52f71cb7781c4f7f6bfb15ddc7ee801b62302a7e921680a0a858f23'
    namespace=dict(vars(input_builder),CASES=CASES)
    prepare=types.FunctionType(input_builder.prepare_inputs.__code__,namespace)
    prepare(ROOT/'artifacts/current-best-portfolio.json',args.out/'inputs')
    config=json.loads((args.out/'inputs/restart-config.json').read_text())
    proof=json.loads((args.out/'inputs/restart-input-proof.json').read_text())
    with np.load(args.out/'inputs/restart-inputs.npz',allow_pickle=False) as archive:
        bank={f'reference_{n}':archive[f'reference_{n}'].copy() for n in CASES}
    slots=[]
    for i,n in enumerate(CASES):
        pose=bank[f'reference_{n}'];encoded,_=original.fq.encode(pose,math.isqrt(n),math.isqrt(n))
        slots.append(dict(slot=i,n=n,key=f'reference_{n}',role='original_reference',
            geometry_sha256=original.geometry_sha(pose),seed=9710000,
            native_encoded_input_sha256=hashlib.sha256(encoded.encode()).hexdigest()))
    manifest=dict(cases=config['cases'],slots=slots,baseline=config['baseline'],
        inputs_sha256=proof['inputs_sha256'],input_proof_sha256=sha(args.out/'inputs/restart-input-proof.json'),
        preparation_builder_sha256=INPUT_BUILDER_SHA,preparation_cases_override=list(CASES),
        input_status='Original canonical arrays translated only; no perturbation, compression or rescaling.',
        inherited_gpu_defaults_unused=True)
    original.atomic_json(args.out/'input-manifest.json',manifest)
    input_manifest_sha256=sha(args.out/'input-manifest.json')
    assert len(slots)==18 and set(bank)=={r['key'] for r in slots}
    for row in slots:
        p=bank[row['key']];n=row['n']
        assert p.shape==(n,3) and np.isfinite(p).all() and p.dtype==np.dtype('<f8')
        assert original.geometry_sha(p)==row['geometry_sha256'] and row['seed']==9710000
        encoded,offsets=original.fq.encode(p,math.isqrt(n),math.isqrt(n));assert offsets==[0,0]
        assert hashlib.sha256(encoded.encode()).hexdigest()==row['native_encoded_input_sha256']
    thresholds,pointer=current_thresholds(args.out/'comparison-initial')
    source=args.out/'source';source.mkdir()
    paths=[Path(__file__),Path(input_builder.__file__),Path(original.__file__),Path(original.fq.__file__),
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_variant_campaign.py',
        ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/recover_broad_native_returns.py',
        ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/LICENSE']
    for p in paths:shutil.copyfile(p,source/p.name)
    (source/'generated-trial.py').write_text(generated_trial_source())
    execution=dict(input_manifest_sha256=input_manifest_sha256,input_sha256=manifest['inputs_sha256'],
        input_slots=slots,source_hashes={p.name:sha(p) for p in source.iterdir()},
        binary_sha256=original.BINARY_SHA,source_commit=original.fq.SOURCE_COMMIT,
        options=original.OPTIONS,seed=9710000,workers=2,native_seconds=60,certificate_seconds=8,
        work_seconds=640,whole_seconds=660,all_eighteen_are_newly_adopted_public35_references=True,
        input_status='Eighteen newly adopted public35 references, translated only; prior global exposure is not asserted absent.',
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
                source='Native completion of newly adopted public35 reference',source_role=row['source_role'],
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
    process.join(max(0.,650.-(time.monotonic()-STARTED)));forced=process.is_alive()
    if forced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.join(timeout=max(0.,659.-(time.monotonic()-STARTED)))
    original.atomic_json(args.out/'supervisor.json',dict(returncode=process.exitcode,forced=forced,
        seconds=time.monotonic()-STARTED,whole_seconds=660,workers=2))
