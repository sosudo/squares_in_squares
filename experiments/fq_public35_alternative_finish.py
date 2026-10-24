"""One finite two-worker native pass on24 frozen changed public alternatives."""
from __future__ import annotations
import time
STARTED=time.monotonic()
import os
for name in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse,hashlib,inspect,json,math,multiprocessing as mp,shutil,signal,types
from concurrent.futures import ProcessPoolExecutor,FIRST_COMPLETED,wait
from decimal import Decimal
from pathlib import Path
import numpy as np
import fq_public35_reference_finish as parent
from recover_broad_native_returns import current_thresholds
ROOT=Path(__file__).resolve().parents[1]
PARENT_SHA='6c56fa97513e53642ef360fe914f6700dd086dd1eba211a66097b9b71d5e149a'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def generated_trial_source():
    assert sha(parent.original.__file__)==parent.ORIGINAL_SHA
    source=inspect.getsource(parent.original._finish_slot)
    old='UNVERIFIED exact committed BEST array';assert source.count(old)==1
    return source.replace(old,'Exact released public35 changed alternative pose; no pre-native validity claim, final output requires all full gates')

def trial(payload):
    assert sha(parent.__file__)==PARENT_SHA
    function=types.FunctionType(parent.trial.__code__,dict(vars(parent),generated_trial_source=generated_trial_source))
    return function(payload)

def candidate(row,q,manifest_sha):
    return dict(side=row['worst_certified_side'],squares=[[f'{v:.17g}'for v in r]for r in q],certificate=row['certificate'],
        source='Unchanged native completion of a changed released public35 alternative',
        provenance=dict(slot=row['slot'],key=row['source_key'],input_manifest_sha256=manifest_sha,
            source_geometry_sha256=row['selected_geometry_sha256'],geometry_sha256=row['geometry_sha256'],
            native_input_sha256=row['input_sha256'],native_output_sha256=row['native_output_sha256']))

def run(args):
    os.setsid();os.sched_setaffinity(0,{0,1});deadline=STARTED+880.
    original=parent.original
    assert sha(parent.__file__)==PARENT_SHA and sha(original.__file__)==parent.ORIGINAL_SHA
    assert sha(parent.BINARY)==original.BINARY_SHA and sha(args.inputs/'manifest.json')==args.manifest_sha256
    manifest=json.loads((args.inputs/'manifest.json').read_text());slots=manifest['slots']
    assert len(slots)==24 and [s['slot']for s in slots]==list(range(24))and len({s['n']for s in slots})==24
    assert manifest['workers']==2 and manifest['cpu_affinity']==[0,1]and manifest['work_seconds']==880 and manifest['whole_seconds']==900
    assert sha(args.inputs/'inputs.npz')==manifest['inputs_sha256']
    with np.load(args.inputs/'inputs.npz',allow_pickle=False)as z:bank={k:z[k].copy()for k in z.files}
    assert set(bank)=={s['key']for s in slots}
    for s in slots:
        q=bank[s['key']];n=s['n'];assert q.shape==(n,3)and q.dtype==np.dtype('<f8')and np.isfinite(q).all()
        assert original.geometry_sha(q)==s['geometry_sha256']and s['seed']==9710000
        encoded,offsets=original.fq.encode(q,math.isqrt(n),math.isqrt(n));assert offsets==[0,0]
        assert hashlib.sha256(encoded.encode()).hexdigest()==s['native_encoded_input_sha256']
    shutil.copytree(args.inputs,args.out/'inputs')
    initial,pointer=current_thresholds(args.out/'comparison-initial')
    source=args.out/'source';source.mkdir()
    paths=[Path(__file__),Path(parent.__file__),Path(original.__file__),Path(original.fq.__file__),
           ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_variant_campaign.py',ROOT/'experiments/compose_gadgets.py',
           ROOT/'experiments/recover_broad_native_returns.py',ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',
           ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/LICENSE']
    for p in paths:shutil.copyfile(p,source/p.name)
    (source/'generated-trial.py').write_text(generated_trial_source())
    execution=dict(input_manifest_sha256=args.manifest_sha256,input_sha256=manifest['inputs_sha256'],
        source_hashes={p.name:sha(p)for p in source.iterdir()},parent_source_sha256=PARENT_SHA,
        numerical_trial_sha256=parent.ORIGINAL_SHA,binary_sha256=original.BINARY_SHA,
        options=original.OPTIONS,seed=9710000,workers=2,cpu_affinity=[0,1],work_seconds=880,whole_seconds=900,
        native_seconds=60,certificate_seconds=8,no_gpu=True,no_submission=True,no_canonical_mutation=True)
    original.atomic_json(args.out/'execution-manifest.json',execution)
    trials=args.out/'trials';trials.mkdir();records={};certified={};pending={};cursor=0
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork'))as pool:
        while cursor<len(slots)or pending:
            while len(pending)<2 and cursor<len(slots):
                slot=slots[cursor];cursor+=1
                if deadline-time.monotonic()<.2:
                    records[slot['slot']]=dict(slot,status='deadline_before_native');continue
                case=manifest['cases'][str(slot['n'])]
                pending[pool.submit(trial,(str(trials),slot,bank[slot['key']].copy(),case,deadline))]=slot
            if not pending:continue
            done,_=wait(pending,timeout=.2,return_when=FIRST_COMPLETED)
            for future in done:
                slot=pending.pop(future)
                try:record,q=future.result()
                except Exception as error:record=dict(slot,status='trial_error',error_type=type(error).__name__);q=None
                records[slot['slot']]=record
                if q is not None:certified[slot['key']]=q
                original.atomic_json(args.out/'results.json',[records[i]for i in sorted(records)])
                original.atomic_npz(args.out/'certified.npz',certified)
                early={str(r['n']):candidate(r,certified[r['source_key']],args.manifest_sha256)for r in records.values()
                       if r.get('status')=='certified'and Decimal(r['worst_certified_side'])<initial[r['n']]}
                original.atomic_json(args.out/'candidates-live.json',early)
                print(json.dumps(dict(n=slot['n'],slot=slot['slot'],status=record['status'],side=record.get('worst_certified_side'),
                    strict_vs_initial=bool(str(slot['n'])in early),native_seconds=record.get('native_seconds'),elapsed=time.monotonic()-STARTED)),flush=True)
    final,current=current_thresholds(args.out/'comparison-final');candidates={}
    for r in records.values():
        if r.get('status')!='certified':continue
        r['latest_canonical_lower']=str(final[r['n']]);r['strict_vs_latest_canonical']=Decimal(r['worst_certified_side'])<final[r['n']]
        if r['strict_vs_latest_canonical']:candidates[str(r['n'])]=candidate(r,certified[r['source_key']],args.manifest_sha256)
    original.atomic_json(args.out/'results.json',[records[i]for i in sorted(records)])
    original.atomic_json(args.out/'candidates.json',candidates)
    summary=dict(status='complete'if len(records)==24 and all(r.get('status')=='certified'for r in records.values())else'bounded_partial',
        trials=len(records),certified=len(certified),improved_cases=list(candidates),seconds=time.monotonic()-STARTED,
        canonical_raw_sha256=current['raw']['sha256'],results_sha256=sha(args.out/'results.json'),
        certified_archive_sha256=sha(args.out/'certified.npz'),candidates_sha256=sha(args.out/'candidates.json'),
        execution_manifest_sha256=sha(args.out/'execution-manifest.json'),no_submission=True,no_canonical_mutation=True)
    original.atomic_json(args.out/'summary.json',summary)
    for p in args.out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps(summary),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--manifest-sha256',required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    args.inputs=args.inputs.resolve();args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
    process=mp.get_context('fork').Process(target=run,args=(args,));process.start()
    process.join(max(0.,890.-(time.monotonic()-STARTED)));forced=process.is_alive()
    if forced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.join(timeout=max(0.,899.-(time.monotonic()-STARTED)))
    parent.original.atomic_json(args.out/'supervisor.json',dict(returncode=process.exitcode,forced=forced,
        seconds=time.monotonic()-STARTED,whole_seconds=900,workers=2,cpu_affinity=[0,1]))
