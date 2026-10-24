"""Two whole-packing aspect-continuation controls, one CPU and <=90s total."""
import time
STARTED=time.monotonic()
import argparse
import json
import math
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
from fq_full_structural import descendants
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from review_full_round_control import alignment

ROOT=Path(__file__).resolve().parents[1]
OPTIONS=['--loosen','1','--soft-a0','.6','--soft-steps','16','--soft-p','2',
    '--soft-kick','0','--hold-f','1','--kick','.04','--outer','45','--pit','100','--flip-top','16','--v']
TRACE=re.compile(r'soft eps ([0-9.eE+-]+) hold ([0-9.eE+-]+) viol ([0-9.eE+-]+) amax_actual ([0-9.eE+-]+) deformed (\d+) aspect_variables (\d+)')


def observed_aspect_run(command,timeout,**kwargs):
    """Established bounded native-session runner, with persistent aspect logs."""
    output=Path(command[command.index('--out')+1])
    stdout=output.with_suffix('.native-stdout');stderr=output.with_suffix('.native-stderr')
    with stdout.open('w')as out,stderr.open('w')as err:
        process=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True)
        try:process.wait(timeout=timeout)
        except BaseException:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=1);raise
    text=stdout.read_text();logs=stderr.read_text()
    if process.returncode==0:
        head=Path(command[command.index('--in')+1]).read_text().splitlines()[0].split()
        n,held=int(head[0]),float(head[1]);native=json.loads(text.strip().splitlines()[-1]);soft=native['soft']
        rows=[dict(epsilon=float(e),held_side=float(h),violation=float(v),actual_max_abs_log_aspect=float(a),
            deformed_over_1e6=int(d),aspect_variables=int(b))for e,h,v,a,d,b in TRACE.findall(logs)]
        expected=[.6*(1-k/16)**2 for k in range(1,17)]
        valid=('--freeze'not in command and '--soft-compress'not in command and '--round-r0'not in command
            and command[command.index('--hold-f')+1]=='1'and 'frozen'not in native
            and soft['a0']==.6 and len(rows)==16
            and max(abs(soft[k]-held)for k in ('s_soft','s_hold'))<1e-10)
        if valid:
            valid=(all(abs(r['epsilon']-e)<=5.01e-5 and abs(r['held_side']-held)<5.1e-9
                and 0<=r['actual_max_abs_log_aspect']<=e+1e-12 for r,e in zip(rows,expected))
                and all(r['aspect_variables']==n for r in rows[:-1])
                and rows[-1]['epsilon']==0 and rows[-1]['actual_max_abs_log_aspect']==0
                and rows[-1]['aspect_variables']==0)
        observed=max((r['actual_max_abs_log_aspect']for r in rows),default=0.)
        atomic_json(output.with_suffix('.aspect-trace.json'),dict(valid=valid,n=n,free_squares=n,
            input_and_held_side=held,rows=rows,maximum_observed_log_aspect=observed,
            maximum_observed_width=math.exp(observed/2),minimum_observed_height=math.exp(-observed/2),
            maximum_observed_aspect_ratio=math.exp(observed),native_pre_continuation_amax=soft['amax'],
            exact_zero_return=bool(rows and rows[-1]['aspect_variables']==0),
            stdout_sha256=fq.digest(stdout),stderr_sha256=fq.digest(stderr),
            observation_scope='Actual sixteen phase endpoints, not every internal L-BFGS iterate. Native JSON am ax is pre-continuation and is not the observed maximum.'))
        if not valid:raise ValueError('Global held-box or measured exact aspect return failed')
    return subprocess.CompletedProcess(command,process.returncode,text,logs)


def worker(out,deadline):
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir()
    source=ROOT/'artifacts/fq-full-global-soft-v1-source';build=json.loads((source/'build-proof.json').read_text())
    binary=source/'fq_trace';assert fq.digest(binary)==build['instrumented_binary_sha256']
    prior=ROOT/'artifacts/fq-full-round-control-v1';proof=json.loads((prior/'manifest.json').read_text())
    assert fq.digest(prior/'inputs.npz')==proof['input_sha256']
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text())
    assert proof['baseline_sha256']==pointer['safe']['sha256']
    official=json.loads(Path(pointer['raw']['official_report']).read_text())
    assert official['valid']and official['sha256']==pointer['raw']['sha256']
    physical={r['n']:float(r['side'])for r in official['results']}
    with np.load(prior/'inputs.npz',allow_pickle=False)as z:inputs={k:z[k].copy()for k in ('18_18_11','17_17_10')}
    for n in (335,299):
        row=proof['selected'][str(n)];p=inputs[row['key']]
        assert geometry_sha(p)==row['geometry_sha256']and proof['input_certificates'][row['key']]['valid']
    atomic_npz(out/'inputs.npz',inputs)
    paths=[Path(__file__),Path(remote.__file__),Path(fq.__file__),ROOT/'experiments/fq_capacity_probe.py',
        ROOT/'research/official_metric_v17.py',source/'src/fq.rs',source/'telemetry.diff']
    manifest=dict(source_hashes={str(p):fq.digest(p)for p in paths},build_proof_sha256=fq.digest(source/'build-proof.json'),
        binary_sha256=fq.digest(binary),original_binary_sha256=build['original_binary_sha256'],
        input_archive_sha256=fq.digest(out/'inputs.npz'),prior_input_manifest_sha256=fq.digest(prior/'manifest.json'),
        input_certificates={k:proof['input_certificates'][k]for k in inputs},input_geometry={k:geometry_sha(p)for k,p in inputs.items()},
        canonical_portfolio=pointer,options=OPTIONS,workers=1,whole_seconds=90,per_trial_inclusive_seconds=39,
        plan=[335,299],frozen_squares=0,initial_log_aspect_bound=.6,
        actual_first_relaxation_bound=.6*(15/16)**2,shape='exp(a/2) by exp(-a/2), area1',
        no_soft_compression=True,held_factor=1,exact_rigid_return='Final k=16 sets eps0, clears b, then set_soft(0) before rigid ALM45/polish100.',
        telemetry_only_native_diff=True,license='MIT; Evan Daniel',no_gpu=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest)
    remote.grouped_run=observed_aspect_run;mode='global_aspect_06_held';fq.MODES[mode]=OPTIONS
    records=[];diagnostics=[]
    for index,n in enumerate((335,299)):
        key='18_18_11'if n==335 else'17_17_10';p=inputs[key]
        record,_=remote.strict_trial((key,p,mode,str(binary),str(trials),18335001+index,39.,deadline-3))
        record.update(n=n,actual_incumbent_side=physical[n]);records.append(record)
        atomic_json(out/'results.json',records)
        if record.get('stage_archive'):
            with np.load(record['stage_archive'],allow_pickle=False)as z:q=z[z.files[0]].copy()
            stem=f'{key}-{mode}-{record["seed"]}'
            trace=json.loads((trials/(stem+'.aspect-trace.json')).read_text())
            diagnostics.append(dict(n=n,side=float(record['certificate']['independent_raw']['side_upper']),
                incumbent_side=physical[n],side_gain=physical[n]-float(record['certificate']['independent_raw']['side_upper']),
                geometry_sha256=geometry_sha(q),trace=trace,comparison=alignment(p,q)))
        print(json.dumps(dict(n=n,status=record['status'],seconds=record.get('seconds'))),flush=True)
    aggregate=remote.collect(out)
    atomic_json(out/'report.json',dict(trials=len(records),diagnostics=diagnostics,aggregate=aggregate,
        manifest_sha256=fq.digest(out/'manifest.json'),elapsed_seconds=time.monotonic()-STARTED,
        new_output_full_certifications=len(diagnostics),input_certificates_reused_by_exact_hash=True,
        full_score_changed=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+87)],start_new_session=True);forced=False
        try:child.wait(timeout=max(.01,STARTED+88-time.monotonic()))
        except subprocess.TimeoutExpired:
            forced=True
            try:os.kill(child.pid,signal.SIGSTOP)
            except ProcessLookupError:pass
            for pid in descendants(child.pid):
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait(timeout=1)
        receipt=dict(returncode=child.returncode,whole_seconds=time.monotonic()-STARTED,workers=1,
            hard_deadline_enforced=forced,maximum_seconds=90)
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if child.returncode:raise SystemExit(child.returncode)
