"""Two fixed335 native chains with weighted moves and40s heating/70s cooling."""
import time
STARTED=time.monotonic()
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import packer_hop_pilot as base
from packer_hop_physical_energy import read_raw_pose,physical_energy

SOURCE=base.ROOT/'artifacts/packer-hop-cooled-v1-source'


def native_chain(job):
    directory,warm,seed,deadline=job;traces=directory/'raw-chain';traces.mkdir()
    binary=SOURCE/'packer_cooled';best=directory/'best.out'
    options=['--s','18.807','--seed',str(seed),'--iters','1000000000','--temp',str(warm),'--cool-temp','.1',
        '--cool-after','40','--amp','1.5','--maxit','3000','--descend','0','--linepen','0']
    run=base.run_native([str(binary),'hop','--in',str(directory/'start.in'),'--out',str(best),*options],
        directory/'hop',min(110.,max(.1,deadline-time.monotonic()-20)),traces)
    decisions={}
    if(traces/'decisions.tsv').exists():
        for row in csv.reader((traces/'decisions.tsv').open(),delimiter='\t'):
            if len(row)!=6:continue
            iteration,kind,changed,elapsed,temp,accepted=row
            r=dict(iteration=int(iteration),kind=int(kind),changed=int(changed),elapsed=float(elapsed),temperature=float(temp),accepted=accepted=='true')
            assert r['changed']>0 and r['kind']in(0,3,4,6)
            assert r['temperature']==(.1 if r['elapsed']>=40 else warm)
            decisions[r['iteration']]=r
    events=[];partial=[]
    if(traces/'events.tsv').exists():
        lines=(traces/'events.tsv').read_text().splitlines()
        for line_number,line in enumerate(lines):
            row=next(csv.reader([line],delimiter='\t'))
            if len(row)!=9:
                assert line_number==len(lines)-1;partial.append(line);continue
            event,it,kind,side,old,proposal,current,accepted,raw=row
            r=dict(event=event,iteration=int(it),kind=int(kind),side=float(side),before_energy=float(old),proposal_energy=float(proposal),accepted_energy=float(current),accepted=accepted=='true',raw_file=raw)
            if raw!='-':
                p,s=read_raw_pose(traces/raw,335);assert s==r['side'];r['raw_sha256']=base.fq.digest(traces/raw)
            if event=='hop':
                assert r['accepted_energy']==(r['proposal_energy']if r['accepted']else r['before_energy'])
                if r['iteration']in decisions:
                    decision=decisions[r['iteration']];assert decision['kind']==r['kind']and decision['accepted']==r['accepted'];r['decision']=decision
                else:r['decision']='unpublished_at_timeout'
            events.append(r)
    base.atomic_json(directory/'events.json',events)
    sample=[r for r in events if r['raw_file']!='-'and r['event']!='feasible_best'];audits=[]
    for i in sorted(set(np.linspace(0,len(sample)-1,min(7,len(sample)),dtype=int).tolist()))if sample else []:
        r=sample[i];p,s=read_raw_pose(traces/r['raw_file'],335);measured=physical_energy(p,s)
        error=abs(measured['energy']-r['accepted_energy']);assert error<1e-12
        audits.append(dict(iteration=r['iteration'],measured=measured,absolute_error=error))
    counts={}
    for phase in('warm','cool'):
        rows=[r for r in events if r['event']=='hop'and isinstance(r.get('decision'),dict)and (r['decision']['elapsed']>=40)==(phase=='cool')]
        accepted=[r for r in rows if r['accepted']]
        counts[phase]=dict(proposed=len(rows),accepted=len(accepted),uphill=sum(r['proposal_energy']>r['before_energy']for r in accepted),
            operators={str(k):dict(proposed=sum(r['kind']==k for r in rows),accepted=sum(r['kind']==k for r in accepted))for k in(0,3,4,6)},
            first_decision_elapsed=min((r['decision']['elapsed']for r in rows),default=None),
            last_decision_elapsed=max((r['decision']['elapsed']for r in rows),default=None))
    raw_states=[r for r in events if r['raw_file']!='-'];report=dict(warm_temperature=warm,cool_temperature=.1,seed=seed,native_run=run,
        counts=counts,actual_temperature_boundary_verified=True,raw_states=len(raw_states),sampled_physical_energy=audits,
        partial_terminal_rows=partial,unpublished_decisions=sum(r.get('decision')=='unpublished_at_timeout'for r in events),
        best_observed_energy=min((r['accepted_energy']for r in raw_states),default=None),
        initial_energy=raw_states[0]['accepted_energy']if raw_states else None,
        terminal_energy=raw_states[-1]['accepted_energy']if raw_states else None,
        best_feasible_exists=best.exists(),best_infeasible_exists=Path(str(best)+'.inf').exists(),
        zero_move_skips=directory.joinpath('hop.stdout').read_text().count('SKIP_ZERO_MOVE'),raw_status='UNVERIFIED')
    base.atomic_json(directory/'report.json',report);return directory,report


def worker(out,deadline):
    out.mkdir(exist_ok=False);build=json.loads((SOURCE/'build-control-proof.json').read_text())
    binary=SOURCE/'packer_cooled';assert base.fq.digest(binary)==build['builds'][0]['binary_sha256']and build['focused_rust_tests_passed']==2
    prior=base.ROOT/'artifacts/packer-hop-335-v1';old_manifest=json.loads((prior/'manifest.json').read_text())
    assert base.fq.digest(prior/'start.in')==old_manifest['input_sha256']
    control=json.loads((prior/'control-certificate.json').read_text());assert control['certificate']['valid']and control['count']==335
    pointer=json.loads((base.ROOT/'artifacts/current-best-portfolio.json').read_text());report_path=Path(pointer['raw']['official_report'])
    assert base.fq.digest(report_path)==pointer['raw']['official_report_sha256']
    official=json.loads(report_path.read_text());assert official['valid']and official['sha256']==pointer['raw']['sha256']
    old=json.loads(Path(old_manifest['canonical_portfolio']['raw']['official_report']).read_text())
    assert official['puzzle_hashes']['335']==old['puzzle_hashes']['335'];baseline=float(next(r['side']for r in official['results']if r['n']==335))
    shutil.copyfile(Path(__file__),out/'executed-source.py')
    manifest=dict(script_sha256=base.fq.digest(Path(__file__)),source_manifest_sha256=base.fq.digest(SOURCE/'source-manifest.json'),
        build_control_proof_sha256=base.fq.digest(SOURCE/'build-control-proof.json'),binary_sha256=base.fq.digest(binary),
        prior_full335_control_sha256=base.fq.digest(prior/'control-certificate.json'),exact_control_reused=True,
        input_sha256=old_manifest['input_sha256'],canonical_pointer=pointer,incumbent_side=baseline,
        native_seconds_per_chain=110,maximum_native_workers=2,whole_seconds=160,warm_seconds=40,cool_temperature=.1,
        amplitude=1.5,fixed_initial_box=18.807,no_submission=True)
    base.atomic_json(out/'manifest.json',manifest);jobs=[]
    for index,warm in enumerate((3.,1.)):
        d=out/f'chain-{index}';d.mkdir();shutil.copyfile(prior/'start.in',d/'start.in');jobs.append((d,warm,335401+index,deadline))
    with ThreadPoolExecutor(max_workers=2)as pool:results=list(pool.map(native_chain,jobs))
    # mpmath contexts are process-global: run final physical certificates serially.
    gates=[]
    for directory,report in results:
        for name in('best.out','best.out.inf'):
            path=directory/name
            if not path.exists()or time.monotonic()>deadline-7:continue
            q=base.fq.decode(path,335)
            if q is None:gates.append(dict(chain=directory.name,path=name,valid=False,reason='Exceeds bounded rounding repair'));continue
            cert=base.full_certificate(q);r=dict(chain=directory.name,path=name,native_sha256=base.fq.digest(path),certificate=cert)
            if cert['valid']:
                side=float(cert['independent_raw']['side_upper']);r.update(side=side,side_gain=baseline-side,strict_improvement=side<baseline-1e-9)
                target=directory/(name+'.certified.npz');base.atomic_npz(target,{'335':q});r['archive_sha256']=base.fq.digest(target)
            gates.append(r)
    base.atomic_json(out/'summary.json',dict(chains=[r for _,r in results],gates=gates,manifest_sha256=base.fq.digest(out/'manifest.json'),
        elapsed_seconds=time.monotonic()-STARTED,maximum_native_workers=2,no_submission=True))
    print(json.dumps(dict(chains=2,gates=len(gates),elapsed=time.monotonic()-STARTED)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--worker',action='store_true');p.add_argument('--deadline',type=float);args=p.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),'--worker','--deadline',str(STARTED+156)],start_new_session=True);forced=False
        try:child.wait(timeout=max(.01,STARTED+157-time.monotonic()))
        except subprocess.TimeoutExpired:
            forced=True
            try:os.kill(child.pid,signal.SIGSTOP)
            except ProcessLookupError:pass
            for pid in base.descendants(child.pid):
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait(timeout=1)
        receipt=dict(returncode=child.returncode,whole_seconds=time.monotonic()-STARTED,maximum_seconds=160,maximum_native_workers=2,forced=forced)
        if args.out.exists():base.atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if child.returncode:raise SystemExit(child.returncode)
