"""Two exact current fullN matched native controls before birth target freeze."""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import hashlib,json,multiprocessing as mp,signal,sys,time,types
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import fq_full_gpu_v2_native_finish as finish
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_fq_restart_hop_job as builder

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(out):
    os.setsid();began=time.monotonic();out.mkdir(exist_ok=False)
    inputs=out/'inputs'
    prepare=types.FunctionType(builder.prepare_inputs.__code__,dict(vars(builder),CASES=(498,587)))
    prepare(ROOT/'artifacts/current-best-portfolio.json',inputs)
    config=json.loads((inputs/'restart-config.json').read_text());records=[];bank={}
    trials=out/'trials';trials.mkdir()
    with np.load(inputs/'restart-inputs.npz',allow_pickle=False)as z:poses={k:z[k]for k in z.files}
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork'))as pool:
        pending=[]
        for slot,n in enumerate((498,587)):
            case=config['cases'][str(n)]
            spec=dict(slot=slot,n=n,key=case['source_key'],role='matched_original_control')
            pending.append(pool.submit(finish.trial,(str(trials),spec,poses[case['source_key']],case,began+72.)))
        for future in pending:
            record,q=future.result();records.append(record)
            if q is not None:bank[record['source_key']]=q
            finish.original.atomic_json(out/'results.json',records)
            finish.original.atomic_npz(out/'certified.npz',bank)
    report=dict(status='complete',seconds=time.monotonic()-began,workers=2,whole_seconds=80,
        native_seconds=60,gate_seconds=8,baseline=config['baseline'],source_sha256=sha(__file__),
        parent_finish_sha256=sha(finish.__file__),native_trial_sha256=finish.ORIGINAL_SHA,
        results_sha256=sha(out/'results.json'),certified_sha256=sha(out/'certified.npz'),
        all_certified=all(r['status']=='certified'for r in records),
        strict_winners=[r['n']for r in records if r.get('strict_improvement')],
        no_canonical_mutation=True,no_submission=True)
    finish.original.atomic_json(out/'summary.json',report)
    for p in out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps(report),flush=True)

if __name__=='__main__':
    out=ROOT/'artifacts/birth-original-controls-v1'
    child=mp.get_context('fork').Process(target=run,args=(out,));child.start();child.join(77.)
    forced=child.is_alive()
    if forced:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.join(2.)
    finish.original.atomic_json(out/'supervisor.json',dict(returncode=child.exitcode,forced=forced,whole_seconds=80))
