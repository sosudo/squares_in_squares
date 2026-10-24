"""One fixed-deep native335 chain; unchanged solver, 110s search/150s total."""
import time
STARTED=time.monotonic()
import argparse
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

OPTIONS=['--s','18.807','--seed','335031','--iters','1000000000','--temp','3','--amp','1.5',
         '--maxit','3000','--descend','0','--linepen','0']


def worker(out,deadline):
    out.mkdir(exist_ok=False);traces=out/'raw-chain';traces.mkdir()
    prior=base.ROOT/'artifacts/packer-hop-335-v1';previous=json.loads((prior/'manifest.json').read_text())
    binary=base.SOURCE/'packer_trace';assert base.fq.digest(binary)==previous['binary_sha256']
    assert base.fq.digest(prior/'start.in')==previous['input_sha256']
    control=json.loads((prior/'control-certificate.json').read_text());assert control['certificate']['valid']and control['count']==335
    assert base.fq.digest(prior/'control.out')==control['native_output_sha256']
    pointer=json.loads((base.ROOT/'artifacts/current-best-portfolio.json').read_text())
    old=json.loads(Path(previous['canonical_portfolio']['raw']['official_report']).read_text())
    report_path=Path(pointer['raw']['official_report']);assert base.fq.digest(report_path)==pointer['raw']['official_report_sha256']
    report=json.loads(report_path.read_text());assert report['valid']and report['sha256']==pointer['raw']['sha256']
    assert old['puzzle_hashes']['335']==report['puzzle_hashes']['335']
    baseline=float(next(r['side']for r in report['results']if r['n']==335))
    inp=out/'start.in';shutil.copyfile(prior/'start.in',inp);inp.chmod(0o444)
    shutil.copyfile(Path(__file__),out/'executed-source.py')
    manifest=dict(script_sha256=base.fq.digest(Path(__file__)),binary_sha256=base.fq.digest(binary),
        prior_manifest_sha256=base.fq.digest(prior/'manifest.json'),prior_full335_control_sha256=base.fq.digest(prior/'control-certificate.json'),
        exact_control_reused=True,input_sha256=base.fq.digest(inp),options=OPTIONS,canonical_pointer=pointer,
        incumbent_side=baseline,whole_seconds=150,native_seconds=110,workers=1,
        helper_hashes={str(p):base.fq.digest(p)for p in (Path(base.__file__),base.ROOT/'experiments/packer_hop_physical_energy.py')},
        native_semantics='Fixed18.807 while infeasible; if feasible native squeeze may decrease side, then descend0 holds new best.',
        raw_status='UNVERIFIED accepted and record-low states; no submission')
    base.atomic_json(out/'manifest.json',manifest);best=out/'best.out'
    run=base.run_native([str(binary),'hop','--in',str(inp),'--out',str(best),*OPTIONS],out/'hop',
        min(110.,max(.1,deadline-time.monotonic()-20)),traces)
    events=[];partial=[]
    if (traces/'events.tsv').exists():
        lines=(traces/'events.tsv').read_text().splitlines()
        for line_number,line in enumerate(lines):
            row=next(csv.reader([line],delimiter='\t'))
            if len(row)!=9:
                assert line_number==len(lines)-1;partial.append(line);continue
            event,it,kind,side,old_e,proposal,accepted_e,accepted,raw=row
            r=dict(event=event,iteration=int(it),kind=int(kind),side=float(side),before_energy=float(old_e),
                proposal_energy=float(proposal),accepted_energy=float(accepted_e),accepted=accepted=='true',raw_file=raw)
            if raw!='-':
                p,s=read_raw_pose(traces/raw,335);assert s==r['side'];r['raw_sha256']=base.fq.digest(traces/raw)
            if event=='hop':assert r['accepted_energy']==(r['proposal_energy']if r['accepted']else r['before_energy'])
            events.append(r)
    base.atomic_json(out/'events.json',events)
    rows=[r for r in events if r['event']=='hop'];accepted=[r for r in rows if r['accepted']]
    sample=[r for r in events if r['raw_file']!='-'and r['event']!='feasible_best'];audit=[]
    for index in sorted(set(np.linspace(0,len(sample)-1,min(9,len(sample)),dtype=int).tolist()))if sample else []:
        r=sample[index];p,s=read_raw_pose(traces/r['raw_file'],335);measured=physical_energy(p,s)
        difference=abs(measured['energy']-r['accepted_energy']);assert difference<1e-12
        audit.append(dict(iteration=r['iteration'],raw_file=r['raw_file'],absolute_difference=difference,measured=measured))
    certificates=[]
    for path in (best,Path(str(best)+'.inf')):
        if not path.exists()or time.monotonic()>deadline-7:continue
        q=base.fq.decode(path,335)
        if q is None:certificates.append(dict(native_file=path.name,reason='Too much residual for bounded rounding-only legalization'));continue
        certificate=base.full_certificate(q);r=dict(native_file=path.name,native_sha256=base.fq.digest(path),certificate=certificate)
        if certificate['valid']:
            side=float(certificate['independent_raw']['side_upper']);r.update(side=side,side_gain=baseline-side,
                strict_improvement=side<baseline-1e-9,score_gain=(baseline-side)/np.sqrt(335))
            target=out/(path.name+'.certified.npz');base.atomic_npz(target,{'335':q});r['archive_sha256']=base.fq.digest(target)
        certificates.append(r)
    base.atomic_json(out/'report.json',dict(manifest_sha256=base.fq.digest(out/'manifest.json'),native_run=run,
        completed_hops=len(rows),accepted_hops=len(accepted),uphill_accepts=sum(r['proposal_energy']>r['before_energy']for r in accepted),
        max_uphill_ratio=max((r['proposal_energy']/r['before_energy']for r in accepted if r['before_energy']>0),default=None),
        per_operator={str(k):dict(proposed=sum(r['kind']==k for r in rows),accepted=sum(r['kind']==k for r in accepted))for k in range(9)},
        raw_states=sum(r['raw_file']!='-'for r in events),partial_terminal_lines=partial,energy_sample=audit,
        best_feasible_exists=best.exists(),best_infeasible_exists=Path(str(best)+'.inf').exists(),certificates=certificates,
        elapsed_seconds=time.monotonic()-STARTED,no_submission=True))
    print(json.dumps(dict(hops=len(rows),accepted=len(accepted),best_exists=best.exists(),certificates=len(certificates))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+146)],start_new_session=True);forced=False
        try:child.wait(timeout=max(.01,STARTED+147-time.monotonic()))
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
        receipt=dict(returncode=child.returncode,whole_seconds=time.monotonic()-STARTED,maximum_seconds=150,workers=1,forced=forced)
        if args.out.exists():base.atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if child.returncode:raise SystemExit(child.returncode)
