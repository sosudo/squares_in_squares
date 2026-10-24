"""One frozen full-n335 native Metropolis pilot; exact raw states stay unverified."""
import time
STARTED=time.monotonic()
import argparse
import csv
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import fq_active_pilot as fq
from fq_capacity_probe import full_certificate
from fq_full_structural import descendants
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from review_full_round_control import alignment

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/packer-hop-335-v1-source'
HOP_OPTIONS=['--seed','335019','--iters','1000000000','--temp','.3','--amp','1',
             '--maxit','3000','--descend','.0001','--linepen','0']


def run_native(command,stem,seconds,trace=None):
    env=dict(os.environ)
    if trace is not None:env['PACKER_TRACE_DIR']=str(trace)
    else:env.pop('PACKER_TRACE_DIR',None)
    start=time.monotonic();timed_out=False
    with stem.with_suffix('.stdout').open('w')as stdout,stem.with_suffix('.stderr').open('w')as stderr:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr,env=env,start_new_session=True)
        try:child.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            timed_out=True
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait(timeout=1)
    record=dict(command=command,returncode=child.returncode,timeout=timed_out,
                seconds=time.monotonic()-start,process_group_reaped=True,
                stdout_sha256=fq.digest(stem.with_suffix('.stdout')),
                stderr_sha256=fq.digest(stem.with_suffix('.stderr')))
    atomic_json(stem.with_suffix('.run.json'),record)
    return record


def raw_pose(path):
    lines=path.read_text().splitlines();head=lines[0].split()
    p=np.asarray([[float(a)for a in row.split()]for row in lines[1:]],dtype=float)
    assert int(head[0])==335 and p.shape==(335,3)and np.isfinite(p).all()
    return p,float(head[1])


def worker(out,deadline):
    out.mkdir(exist_ok=False);traces=out/'raw-chain';traces.mkdir()
    build=json.loads((SOURCE/'build-proof.json').read_text());binary=SOURCE/'packer_trace'
    assert fq.digest(binary)==build['builds'][1]['binary_sha256']
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text())
    prior=ROOT/'artifacts/fq-full-round-control-v1';proof=json.loads((prior/'manifest.json').read_text())
    assert proof['baseline_sha256']==pointer['safe']['sha256']
    assert fq.digest(prior/'inputs.npz')==proof['input_sha256']
    with np.load(prior/'inputs.npz',allow_pickle=False)as z:p=z['18_18_11'].copy()
    assert len(p)==335 and geometry_sha(p)==proof['selected']['335']['geometry_sha256']
    assert proof['input_certificates']['18_18_11']['valid']
    report=json.loads(Path(pointer['raw']['official_report']).read_text())
    assert report['valid']and report['sha256']==pointer['raw']['sha256']
    baseline=float(next(r['side']for r in report['results']if r['n']==335))
    text,offsets=fq.encode(p,18,18);assert offsets==[0,0]
    inp=out/'start.in';inp.write_text(text);atomic_npz(out/'inputs.npz',{'18_18_11':p})
    manifest=dict(source_manifest_sha256=fq.digest(SOURCE/'source-manifest.json'),
        build_proof_sha256=fq.digest(SOURCE/'build-proof.json'),binary_sha256=fq.digest(binary),
        script_sha256=fq.digest(Path(__file__)),input_sha256=fq.digest(inp),input_geometry_sha256=geometry_sha(p),
        prior_input_manifest_sha256=fq.digest(prior/'manifest.json'),input_certificate=proof['input_certificates']['18_18_11'],
        canonical_portfolio=pointer,actual_incumbent_side=baseline,hop_options=HOP_OPTIONS,
        helper_sha256=fq.digest(ROOT/'artifacts/public-alex-v19/starter-v7/hop_search.py'),
        numerical_helper_hashes={str(path.relative_to(ROOT)):fq.digest(path)for path in
            [Path(fq.__file__),ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',
             ROOT/'research/official_metric_v17.py',ROOT/'scripts/validate_submission.py']},
        whole_seconds=180,hop_seconds=130,workers=1,source_is_pinned_upstream=True,
        original_input_is_legalized_search_copy=True,no_gpu=True,no_submission=True,
        raw_chain_status='UNVERIFIED; exact native float64 radians, never admitted without full gates')
    atomic_json(out/'manifest.json',manifest)
    control=out/'control.out'
    run=run_native([str(binary),'relax','--in',str(inp),'--out',str(control),'--maxit','100'],out/'control',10.)
    assert run['returncode']==0 and control.exists()
    q=fq.decode(control,335);assert q is not None
    certificate=full_certificate(q);assert certificate['valid']
    atomic_npz(out/'control-certified.npz',{'18_18_11':q})
    atomic_json(out/'control-certificate.json',dict(certificate=certificate,geometry_sha256=geometry_sha(q),
        native_output_sha256=fq.digest(control),count=335,physical_unit_squares=True))
    best=out/'best.out'
    search=run_native([str(binary),'hop','--in',str(inp),'--out',str(best),*HOP_OPTIONS],out/'hop',
        min(130.,max(.1,deadline-time.monotonic()-20)),traces)
    events=[];event_path=traces/'events.tsv'
    if event_path.exists():
        for row in csv.reader(event_path.open(),delimiter='\t'):
            assert len(row)==9
            event,it,kind,side,old,proposal,accepted_e,accept,raw=row
            rec=dict(event=event,iteration=int(it),kind=int(kind),side=float(side),before_energy=float(old),
                proposal_energy=float(proposal),accepted_energy=float(accepted_e),accepted=accept=='true',raw_file=raw)
            if raw!='-':
                pose,box=raw_pose(traces/raw);assert box==rec['side']
                rec.update(raw_sha256=fq.digest(traces/raw),geometry_sha256=geometry_sha(pose))
            if event=='hop':
                expected=rec['proposal_energy']if rec['accepted']else rec['before_energy']
                assert expected==rec['accepted_energy']
            events.append(rec)
    atomic_json(out/'events.json',events)
    hops=[r for r in events if r['event']=='hop'];accepted=[r for r in hops if r['accepted']]
    uphill=[r for r in accepted if r['proposal_energy']>r['before_energy']and r['proposal_energy']>1e-26]
    modes={str(k):dict(proposed=sum(r['kind']==k for r in hops),accepted=sum(r['kind']==k for r in accepted),
        uphill=sum(r['kind']==k for r in uphill))for k in range(9)}
    final=None
    if best.exists()and time.monotonic()<deadline-7:
        q=fq.decode(best,335)
        if q is not None:
            certificate=full_certificate(q)
            final=dict(certificate=certificate,geometry_sha256=geometry_sha(q),native_sha256=fq.digest(best),
                actual_incumbent_side=baseline)
            if certificate['valid']:
                side=float(certificate['independent_raw']['side_upper'])
                final.update(side=side,side_gain=baseline-side,score_gain=(baseline-side)/np.sqrt(335),
                    actual_improvement=side<baseline-1e-9,comparison=alignment(p,q))
                atomic_npz(out/'certified-best.npz',{'18_18_11':q})
            atomic_json(out/'best-certificate.json',final)
    atomic_json(out/'report.json',dict(manifest_sha256=fq.digest(out/'manifest.json'),native_search=search,
        completed_hops=len(hops),accepted_hops=len(accepted),uphill_infeasible_acceptances=len(uphill),
        mutation_counts=modes,raw_snapshots=sum(r['raw_file']!='-'for r in events),
        raw_chain_full_count_and_finite_checks=True,certified_final=final,
        raw_poses_are_unverified=True,elapsed_seconds=time.monotonic()-STARTED,
        partial_native_terminal_due_to_hard_time_cap=search['timeout']))
    print(json.dumps(dict(hops=len(hops),accepted=len(accepted),uphill=len(uphill),
        final_side=None if final is None else final.get('side'),elapsed=time.monotonic()-STARTED)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+176)],start_new_session=True);forced=False
        try:child.wait(timeout=max(.01,STARTED+177-time.monotonic()))
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
            hard_deadline_enforced=forced,maximum_seconds=180)
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if child.returncode:raise SystemExit(child.returncode)
