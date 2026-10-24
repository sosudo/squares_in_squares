"""One120s/one-CPU pilot of near-circular full-case rehardening and larger jitter."""
import time
STARTED=time.monotonic()
import argparse
import json
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
from fq_full_round_cpu_search import actual_held_run
from fq_full_structural import descendants
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from review_full_round_control import alignment

ROOT=Path(__file__).resolve().parents[1]
PLAN=[('18_18_11','original','.49','.30',28.),
      ('18_18_11','compressed','.49','.30',28.),
      ('17_17_10','original','.4','.15',22.),
      ('17_17_10','original','.49','.30',22.)]
COMPRESSED='21d1ef41bc338110d8aaa47771365beed6591c70166b49d468b78b5761b9b966'


def worker(out,deadline):
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir()
    job=ROOT/'artifacts/fq-full-round-cpu-job-v1';manifest=json.loads((job/'job_manifest.json').read_text())
    for name,expected in manifest['campaign']['input_hashes'].items():
        if fq.digest(job/name)!=expected:raise ValueError('Reviewed exact input changed')
    for relative in ['experiments/fq_full_round_cpu_search.py','experiments/fq_full_round_control.py',
                     'experiments/fq_remote_cpu_search.py','experiments/fq_active_pilot.py',
                     'experiments/fq_capacity_probe.py','experiments/compose_gadgets.py','research/official_metric_v17.py']:
        if fq.digest(ROOT/relative)!=manifest['files'][relative]:raise ValueError('Reviewed numerical helper changed')
    binary=Path('/tmp/squares-fq-portable-target/release/fq')
    if fq.digest(binary)!=manifest['binary_sha256']:raise ValueError('Exact portable binary required')
    inputs={}
    with np.load(job/'inputs/reference.npz')as z:
        for key in ['17_17_10','18_18_11']:inputs[key+'__original']=z[key].copy()
    with np.load(job/'inputs/donors.npz')as z:
        selected=[z[name].copy()for name in z.files if geometry_sha(z[name])==COMPRESSED]
        if len(selected)!=1:raise ValueError('Exact compressed335 alternative missing')
        inputs['18_18_11__compressed']=selected[0]
    atomic_npz(out/'inputs.npz',inputs)
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text());current=pointer['raw']
    if fq.digest(Path(current['official_report']))!=current['official_report_sha256']:raise ValueError('Incumbent report differs')
    rows=json.loads(Path(current['official_report']).read_text())['results'];sides={r['n']:r['side']for r in rows if r['n']in(299,335)}
    description=dict(plan=PLAN,workers=1,whole_seconds=120,binary_sha256=fq.digest(binary),
        native_source_commit=fq.SOURCE_COMMIT,license='MIT; Evan Daniel',
        input_sha256=fq.digest(out/'inputs.npz'),input_geometry_sha256={key:geometry_sha(p)for key,p in inputs.items()},
        reused_input_proof=str(job/'inputs/input_proof.json'),reused_input_proof_sha256=fq.digest(job/'inputs/input_proof.json'),
        source_sha256=fq.digest(Path(__file__)),helper_hashes={name:manifest['files'][name]for name in manifest['files']if name.startswith('experiments/')},
        reference=current,current_raw_sides=sides,
        treatment='No round-compress; selected box held exactly; initial jitter plus12 quadratic radius-return steps; rigid ALM45/polish100/flip16.',
        radius_049_supported='Native half-edge H-r remains.01>0; no source restriction excludes this radius.',
        no_gpu=True,no_remote_job=True,no_submission=True)
    atomic_json(out/'manifest.json',description);records=[];diagnostics=[];remote.grouped_run=actual_held_run
    for i,(key,source,radius,kick,cap)in enumerate(PLAN):
        p=inputs[key+'__'+source];mode='aggressive_round_'+radius.replace('.','')+'_'+source
        options=['--loosen','1','--round-r0',radius,'--round-steps','12','--round-p','2',
            '--round-kick','.004','--hold-f','1','--outer','45','--pit','100','--flip-top','16','--v','--kick',kick]
        fq.MODES[mode]=options;seed=18147001+i;begin=time.monotonic()
        record,donor=remote.strict_trial((key,p,mode,str(binary),str(trials.resolve()),seed,cap,deadline-4))
        record.update(n=len(p),input_name=key+'__'+source,requested_radius=float(radius),initial_jitter=float(kick),
            inclusive_cap_seconds=cap,observed_trial_seconds=time.monotonic()-begin)
        stderr=trials/f'{key}-{mode}-{seed}.native-stderr'
        if stderr.exists():
            radii=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',stderr.read_text())]
            record.update(completed_return_steps=len(radii),last_reported_radius=radii[-1]if radii else None,
                native_stderr_sha256=fq.digest(stderr))
        records.append(record);atomic_json(out/'results.json',records)
        print(json.dumps({k:record.get(k)for k in ['n','input_name','requested_radius','initial_jitter','status','observed_trial_seconds','after','completed_return_steps','last_reported_radius']}),flush=True)
    aggregate=remote.collect(out)
    for record in records:
        if record.get('certificate',{}).get('valid')and record.get('stage_archive'):
            with np.load(record['stage_archive'])as z:q=z[z.files[0]].copy()
            p=inputs[record['input_name']];side=record['certificate']['shared_official_gate']['raw_side']
            diagnostics.append(dict(n=len(q),source=record['input_name'],mode=record['mode'],seed=record['seed'],
                geometry_sha256=geometry_sha(q),raw_official_side=side,ordinary_pandas_side=record['certificate']['ordinary_pandas_official_side'],
                current_raw_side=sides[len(q)],side_gain_vs_current=float(sides[len(q)])-float(side),
                D4_unlabeled_alignment=alignment(p,q)))
    atomic_json(out/'summary.json',dict(trials=len(records),certified_stages=aggregate['complete_stage_records'],
        aggregate=aggregate,diagnostics=diagnostics,manifest_sha256=fq.digest(out/'manifest.json'),
        results_sha256=fq.digest(out/'results.json'),workers=1,whole_worker_seconds=time.monotonic()-STARTED,
        status_counts={status:sum(r['status']==status for r in records)for status in set(r['status']for r in records)},
        no_competition_score_claim=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        if args.out.exists():raise ValueError('Fresh frozen output required')
        source=args.out.with_name(args.out.name+'-source');source.mkdir()
        (source/'executed_source.py').write_bytes(Path(__file__).read_bytes())
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+116)],start_new_session=True);forced=False
        try:process.wait(timeout=max(.01,STARTED+118-time.monotonic()))
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
        receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,workers=1,
            hard_deadline_enforced=forced,maximum_seconds=120,source_sha256=fq.digest(Path(__file__)))
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
