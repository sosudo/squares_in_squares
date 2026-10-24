"""Two fixed small-case persistent native hop controls, one CPU and <=320 seconds."""
import time
STARTED=time.monotonic()
import argparse
import csv
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import packer_hop_pilot as base
from compose_gadgets import normalize

BINARY_SHA='39e7699fc507a67d4acfc75465a476b69a5647058c60bd90832ce6996dc3cf25'
OPTIONS=['--iters','1000000000','--temp','.3','--amp','1','--maxit','3000','--descend','.0001','--linepen','0']


def raw_pose(path,n):
    lines=path.read_text().splitlines();header=lines[0].split()
    p=np.asarray([[float(a)for a in row.split()]for row in lines[1:]],dtype=float)
    assert int(header[0])==n and p.shape==(n,3) and np.isfinite(p).all()
    return p,float(header[1])


def summarize_trace(directory,n):
    traces=directory/'raw-chain';events=[];partial=[]
    path=traces/'events.tsv'
    if path.exists():
        lines=path.read_text().splitlines()
        for index,line in enumerate(lines):
            row=next(csv.reader([line],delimiter='\t'))
            if len(row)!=9:
                if index!=len(lines)-1:raise ValueError('Malformed nonterminal telemetry row')
                partial.append(dict(line=index,text=line));continue
            event,it,kind,side,old,proposal,accepted_e,accept,raw=row
            record=dict(event=event,iteration=int(it),kind=int(kind),side=float(side),before_energy=float(old),
                proposal_energy=float(proposal),accepted_energy=float(accepted_e),accepted=accept=='true',raw_file=raw)
            assert all(math.isfinite(record[k])for k in ('side','before_energy','proposal_energy','accepted_energy'))
            if raw!='-':
                assert Path(raw).name==raw
                p,box=raw_pose(traces/raw,n);assert box==record['side']
                record.update(raw_sha256=base.fq.digest(traces/raw),geometry_sha256=base.geometry_sha(p))
            if event=='hop':
                assert record['accepted_energy']==(record['proposal_energy']if record['accepted']else record['before_energy'])
            events.append(record)
    base.atomic_json(directory/'events.json',events)
    snapshots={p.name:dict(sha256=base.fq.digest(p),bytes=p.stat().st_size)for p in traces.glob('*.raw')}
    base.atomic_json(directory/'raw-index.json',dict(status='UNVERIFIED native exact-radian states',files=snapshots))
    hops=[r for r in events if r['event']=='hop'];accepted=[r for r in hops if r['accepted']]
    uphill=[r for r in accepted if r['proposal_energy']>r['before_energy']and r['proposal_energy']>1e-26]
    return dict(completed_hops=len(hops),accepted_hops=len(accepted),uphill_infeasible_acceptances=len(uphill),
        per_operator={str(k):dict(proposed=sum(r['kind']==k for r in hops),accepted=sum(r['kind']==k for r in accepted),
            uphill=sum(r['kind']==k for r in uphill))for k in range(9)},
        raw_snapshots=len(snapshots),partial_terminal_rows=partial,events_sha256=base.fq.digest(directory/'events.json'),
        raw_index_sha256=base.fq.digest(directory/'raw-index.json'))


def certificate_file(directory,tag,p,n,baseline):
    certificate=base.full_certificate(p)
    assert p.shape==(n,3) and certificate['independent_raw']['n']==n
    result=dict(valid=certificate['valid'],certificate=certificate,geometry_sha256=base.geometry_sha(p))
    if certificate['valid']:
        side=float(certificate['independent_raw']['side_upper'])
        result.update(side=side,side_gain_vs_current_raw=baseline-side,
            score_gain_vs_current_raw=(baseline-side)/math.sqrt(n),strict_improvement=side<baseline-1e-9)
        target=directory/(tag+'.npz');base.atomic_npz(target,{str(n):p});target.chmod(0o444)
        result.update(archive_sha256=base.fq.digest(target),archive=str(target))
    target=directory/(tag+'.json');base.atomic_json(target,result);target.chmod(0o444)
    return result


def worker(args):
    out=args.out;selection=json.loads((out/'selection.json').read_text())
    assert base.fq.digest(out/'parents.npz')==selection['parents_sha256']
    assert base.fq.digest(out/'packer_trace')==BINARY_SHA
    reports=[];binary=out/'packer_trace'
    with np.load(out/'parents.npz',allow_pickle=False)as z:parents={k:z[k].copy()for k in z.files}
    for case_index,case in enumerate(selection['cases']):
        n=case['n'];source=parents[str(n)];p=normalize(source)
        directory=out/f'n{n}';directory.mkdir(exist_ok=False);traces=directory/'raw-chain';traces.mkdir()
        input_certificate=base.full_certificate(p)
        assert input_certificate['valid'] and input_certificate['independent_raw']['n']==n
        w=int(math.floor(float(input_certificate['independent_raw']['side_upper'])))
        text,offsets=base.fq.encode(p,w,w);assert offsets==[0,0]
        inp=directory/'start.in';inp.write_text(text);inp.chmod(0o444)
        native_box=float(text.splitlines()[0].split()[1])
        options=['--seed',str(27147001+case_index),*OPTIONS]
        options[options.index('--temp')+1]=str(case['temperature'])
        base.atomic_json(directory/'manifest.json',dict(case=case,input_geometry_sha256=base.geometry_sha(p),
            source_geometry_sha256=base.geometry_sha(source),input_certificate=input_certificate,
            normalization='Translation only; valid current safe pose normalized to [0,S]^2 before degree serialization',
            input_text_sha256=base.fq.digest(inp),native_box=native_box,options=options,
            source_bindings_sha256=base.fq.digest(out/'source-bindings.json'),selection_sha256=base.fq.digest(out/'selection.json'),
            raw_telemetry_units='Radians; UNVERIFIED until complete fresh physical gates',hop_seconds=130,workers=1))
        control=directory/'control.out'
        run=base.run_native([str(binary),'relax','--in',str(inp),'--out',str(control),'--maxit','100'],directory/'control',10.)
        assert run['returncode']==0 and control.exists()
        q=base.fq.decode(control,n);assert q is not None
        positive=certificate_file(directory,'control-certified',q,n,case['current_raw_side']);assert positive['valid']
        best=directory/'best.out'
        seconds=min(130.,max(.1,args.deadline-time.monotonic()-20))
        search=base.run_native([str(binary),'hop','--in',str(inp),'--out',str(best),*options],directory/'hop',seconds,traces)
        trace=summarize_trace(directory,n);final=None
        if best.exists() and time.monotonic()<args.deadline-6:
            q=base.fq.decode(best,n)
            if q is not None:
                final=certificate_file(directory,'best-certified',q,n,case['current_raw_side'])
                final['native_output_sha256']=base.fq.digest(best)
        report=dict(n=n,native_search=search,positive_control=positive,final=final,trace=trace,
            current_raw_side=case['current_raw_side'],public_reference_side=case['public_side'],
            raw_chain_is_unverified=True,manifest_sha256=base.fq.digest(directory/'manifest.json'))
        base.atomic_json(directory/'report.json',report);reports.append(report)
        base.atomic_json(out/'results.json',reports)
        print(json.dumps(dict(n=n,**{k:trace[k]for k in ('completed_hops','accepted_hops','uphill_infeasible_acceptances')},
            final_side=None if final is None else final.get('side'),actual_score_gain=None if final is None else final.get('score_gain_vs_current_raw'))),flush=True)
    gains=[max(0.,r['final']['score_gain_vs_current_raw'])for r in reports if r['final']and r['final']['valid']]
    base.atomic_json(out/'summary.json',dict(cases=len(reports),positive_controls_passed=len(reports),
        certified_finals=sum(bool(r['final']and r['final']['valid'])for r in reports),actual_fullscore_gain=sum(gains),
        results_sha256=base.fq.digest(out/'results.json'),elapsed_seconds=time.monotonic()-STARTED,
        scope='Contribution of these individually fully certified replacements; portfolio not merged or submitted'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args);return
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
        '--worker','--deadline',str(STARTED+315)],start_new_session=True);forced=False
    try:child.wait(timeout=max(.01,STARTED+317-time.monotonic()))
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
    receipt=dict(returncode=child.returncode,whole_seconds=time.monotonic()-STARTED,workers=1,
        hard_deadline_enforced=forced,maximum_seconds=320)
    base.atomic_json(args.out/'supervisor.json',receipt);print(json.dumps(receipt),flush=True)
    if child.returncode:raise SystemExit(child.returncode)


if __name__=='__main__':main()
