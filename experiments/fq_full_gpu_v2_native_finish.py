"""Nine fixed full-GPU-v2/reference native finishes; no GPU or portfolio edits."""
from __future__ import annotations
import time
STARTED=time.monotonic()
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,inspect,json,math,multiprocessing as mp,shutil,signal
from concurrent.futures import ProcessPoolExecutor,FIRST_COMPLETED,wait
from decimal import Decimal
from pathlib import Path
import numpy as np
import fq_restart_hop_finish as original
from recover_broad_native_returns import current_thresholds

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL_SHA='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
BINARY=Path('/tmp/squares-fq-portable-target/release/fq')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generated_trial_source():
    assert sha(original.__file__)==ORIGINAL_SHA
    source=inspect.getsource(original._finish_slot)
    old='UNVERIFIED exact committed BEST array';assert source.count(old)==1
    return source.replace(old,'Exact retained full-GPU-v2 proposal or matched current reference; output requires all full gates')


def trial(payload):
    out,slot,pose,case,deadline=payload
    namespace=dict(vars(original),NATIVE_SECONDS=60.,CERTIFICATE_SECONDS=8.)
    exec(compile(generated_trial_source(),'<fixed fullGPUv2 native finish>','exec'),namespace)
    record,q=namespace['_finish_slot'](Path(out),dict(slot,arm=slot['role'],delta=.002,chain=slot['slot']),
        pose,dict(case,n=slot['n'],source_key=slot['key']),BINARY,deadline)
    record['source_role']=slot['role'];record['source_key']=slot['key']
    if 'command' in record:assert record['command'][record['command'].index('--seed')+1]=='9710000'
    return record,q


def run(args):
    os.setsid();cpus=sorted(os.sched_getaffinity(0));assert len(cpus)>=2
    os.sched_setaffinity(0,set(cpus[:2]));deadline=STARTED+345.
    assert sha(original.__file__)==ORIGINAL_SHA and sha(BINARY)==original.BINARY_SHA
    assert sha(args.input/'manifest.json')==args.manifest_sha256
    manifest=json.loads((args.input/'manifest.json').read_text())
    assert sha(args.input/'inputs.npz')==manifest['inputs_sha256']
    with np.load(args.input/'inputs.npz',allow_pickle=False) as archive:bank={k:archive[k].copy() for k in archive.files}
    slots=manifest['slots'];assert len(slots)==9 and [r['slot'] for r in slots]==list(range(9))
    assert sorted(r['n'] for r in slots[:3])==[147,299,335]
    assert sorted(r['n'] for r in slots[3:])==[147,147,299,299,335,335]
    assert {r['key'] for r in slots[:3]}=={'current_147','current_299','current_335'}
    assert len({r['key'] for r in slots})==9 and set(bank)=={r['key'] for r in slots}
    for row in slots:
        p=bank[row['key']];n=row['n']
        assert p.shape==(n,3) and np.isfinite(p).all() and p.dtype==np.dtype('<f8')
        assert original.geometry_sha(p)==row['geometry_sha256'] and row['seed']==9710000
        encoded,offsets=original.fq.encode(p,math.isqrt(n),math.isqrt(n));assert offsets==[0,0]
        assert hashlib.sha256(encoded.encode()).hexdigest()==row['native_encoded_input_sha256']
    thresholds,pointer=current_thresholds(args.out/'comparison-initial')
    shutil.copytree(args.input,args.out/'inputs')
    source=args.out/'source';source.mkdir()
    paths=[Path(__file__),Path(original.__file__),Path(original.fq.__file__),
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_variant_campaign.py',
        ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/recover_broad_native_returns.py',
        ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/LICENSE']
    for p in paths:shutil.copyfile(p,source/p.name)
    (source/'generated-trial.py').write_text(generated_trial_source())
    execution=dict(input_manifest_sha256=args.manifest_sha256,input_sha256=manifest['inputs_sha256'],
        input_slots=slots,source_hashes={p.name:sha(p) for p in source.iterdir()},
        binary_sha256=original.BINARY_SHA,source_commit=original.fq.SOURCE_COMMIT,
        options=original.OPTIONS,seed=9710000,workers=2,native_seconds=60,certificate_seconds=8,
        work_seconds=345,whole_seconds=360,matched_controls_first_barrier=True,
        input_status='Six unverified retained proposals and three current reference controls; only final full gates establish candidate validity.',
        no_gpu=True,no_submission=True,no_canonical_mutation=True)
    original.atomic_json(args.out/'execution-manifest.json',execution)
    trial_dir=args.out/'trials';trial_dir.mkdir();records={};certified={}
    # Three controls finish before any GPU-derived initializer is submitted.
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork')) as pool:
        for phase_index,phase_slots in enumerate((slots[:3],slots[3:])):
            if phase_index and any(records.get(s['slot'],{}).get('status')!='certified' for s in slots[:3]):
                for slot in phase_slots:records[slot['slot']]=dict(slot,status='skipped_failed_reference_control')
                original.atomic_json(args.out/'results.json',[records[i] for i in sorted(records)])
                break
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
                source='Fixed native full-GPU-v2/reference completion',source_role=row['source_role'],
                provenance=dict(slot=row['slot'],key=row['source_key'],input_manifest_sha256=args.manifest_sha256,
                    source_geometry_sha256=row['selected_geometry_sha256'],geometry_sha256=row['geometry_sha256'],
                    native_input_sha256=row['input_sha256'],native_output_sha256=row['native_output_sha256']))
    original.atomic_json(args.out/'results.json',[records[i] for i in sorted(records)])
    original.atomic_json(args.out/'candidates.json',candidates)
    control_failed=any(records.get(s['slot'],{}).get('status')!='certified' for s in slots[:3])
    status='control_failure' if control_failed else ('complete' if all(r.get('status')=='certified' for r in records.values()) else 'bounded_partial')
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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--manifest-sha256',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.input=args.input.resolve();args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
    process=mp.get_context('fork').Process(target=run,args=(args,));process.start()
    process.join(max(0.,355.-(time.monotonic()-STARTED)));forced=process.is_alive()
    if forced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.join(timeout=max(0.,359.-(time.monotonic()-STARTED)))
    original.atomic_json(args.out/'supervisor.json',dict(returncode=process.exitcode,forced=forced,
        seconds=time.monotonic()-STARTED,whole_seconds=360,workers=2))
