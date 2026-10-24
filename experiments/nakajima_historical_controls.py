"""Bounded, faithful historical controls of the public MIT momentum hardener.

No GPU, large-case search, parameter retuning, canonical write or submission.
The original Rust source is compiled unchanged into a separate artifact path.
"""
from __future__ import annotations
import time
STARTED=time.monotonic()
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=Path('/tmp/squares-research/evand')
COMMIT='659ee62e4a9d39542a1146e8b011cc3ab6407ede'
RUSTC=Path('/tmp/squares-rustup/toolchains/1.99.1-x86_64-unknown-linux-gnu/bin/rustc')
FQ=Path('/tmp/squares-fq-portable-target/release/fq')
FQ_SHA='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
CELLS=((8000,'.008',1),(30000,'.004',1),(8000,'.008',2),(30000,'.004',2))


class ControlDeadline(BaseException):pass
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.incoming')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temporary.replace(path)
def expire(*_):raise ControlDeadline()


def command(argv,base,seconds,deadline):
    remaining=deadline-time.monotonic()
    if remaining<.2:return dict(status='budget_skipped',command=argv)
    process=None;began=time.monotonic();timed_out=False
    stdout_path=Path(str(base)+'.stdout');stderr_path=Path(str(base)+'.stderr')
    with stdout_path.open('wb')as stdout,stderr_path.open('wb')as stderr:
        try:
            process=subprocess.Popen(argv,stdout=stdout,stderr=stderr)
            try:process.wait(timeout=min(seconds,remaining))
            except subprocess.TimeoutExpired:timed_out=True
        finally:
            if process is not None and process.poll()is None:
                process.kill();process.wait(timeout=1.)
    return dict(status='timeout'if timed_out else'complete'if process.returncode==0 else'failed',
        returncode=process.returncode,command=argv,seconds=time.monotonic()-began,limit_seconds=seconds,
        stdout_path=str(stdout_path),stderr_path=str(stderr_path),
        stdout_sha256=sha(stdout_path),stderr_sha256=sha(stderr_path))


def load_pose(path):
    lines=path.read_text().splitlines();n=int(lines[0].split()[0]);side=lines[0].split()[1]
    if len(lines)!=n+1:raise ValueError('Native full count required')
    p=np.array([[float(v)for v in row.split()]for row in lines[1:]],dtype=np.float64)
    if p.shape!=(n,3)or not np.isfinite(p).all():raise ValueError('Invalid native full pose')
    p[:,2]=np.radians(p[:,2]);return p,side


def certify_output(path,label,out,deadline):
    """Preserve exact native text and float array BEFORE bounded unchanged gates."""
    import fq_active_pilot as fq
    from fq_capacity_probe import full_certificate
    from fq_restart_hop_finish import worst_certificate_side
    raw,declared=load_pose(path);raw_path=out/(label+'-raw-unverified.npz')
    np.savez(raw_path,pose=raw)
    record=dict(native_path=str(path),native_sha256=sha(path),native_declared_side=declared,
        raw_array_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),raw_archive_sha256=sha(raw_path),
        n=len(raw),input_status='Native text/raw arrays UNVERIFIED until unchanged gates pass')
    if deadline-time.monotonic()<.2:return dict(record,status='gate_budget_skipped'),None
    previous=signal.getitimer(signal.ITIMER_REAL);old=signal.signal(signal.SIGALRM,expire)
    start=time.monotonic();signal.setitimer(signal.ITIMER_REAL,min(4.,deadline-start,previous[0]if previous[0]>0 else math.inf))
    try:
        q=fq.decode(path,len(raw))
        if q is None:return dict(record,status='bounded_clearance_failed'),None
        certificate=full_certificate(q)
        if not certificate['valid']:return dict(record,status='full_gates_failed',certificate=certificate),None
        side,sides=worst_certificate_side(certificate);target=out/(label+'-certified.npz');np.savez(target,pose=q)
        record.update(status='certified',worst_certified_side=side,certified_sides=sides,certificate=certificate,
            geometry_sha256=hashlib.sha256(q.tobytes()).hexdigest(),certified_archive_sha256=sha(target),
            decoded_differs_from_raw=not np.array_equal(q,raw),
            clearance_policy='Unchanged fq_active_pilot.decode/compose_gadgets.legalize; output validity applies to exact retained decoded .17g geometry, not an unchecked native header.')
        save(out/(label+'-certificate.json'),record);return record,q
    except ControlDeadline:return dict(record,status='gate_deadline_raw_preserved'),None
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
        if previous[0]>0:signal.setitimer(signal.ITIMER_REAL,max(.001,previous[0]-(time.monotonic()-start)))


def worker(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    cpus=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpus[0]})
    deadline=STARTED+175.;signal.signal(signal.SIGALRM,expire);signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
    source=out/'source';source.mkdir();(out/'bin').mkdir();trials=out/'trials';trials.mkdir()
    records=[];banks={};result=dict(status='started',no_gpu=True,no_submission=True,no_canonical_mutation=True)
    try:
        if subprocess.check_output(['git','-C',str(PUBLIC),'rev-parse','HEAD'],text=True).strip()!=COMMIT:raise ValueError('Public source commit differs')
        selected=['LICENSE','search/packer/src/harden.rs','search/packer/harden.py','search/packer/PACKER.md',
            'search/packer/HANDOFF-2026-10-14.md','search/packer/CLAIMS.md','search/packer/pk/bands.py',
            'search/exact/batch/inputs/n-211.txt']
        source_hashes={}
        for name in selected:
            p=PUBLIC/name;target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);source_hashes[name]=sha(p)
        if subprocess.check_output(['git','-C',str(PUBLIC),'status','--porcelain','--',*selected],text=True).strip():raise ValueError('Public selected source is modified')
        if sha(FQ)!=FQ_SHA:raise ValueError('Pinned native finisher differs')
        p0,side=load_pose(source/'search/exact/batch/inputs/n-211.txt');assert len(p0)==211
        manifest=dict(public_repository='https://github.com/evand/square-packing',commit=COMMIT,source_hashes=source_hashes,
            historical_input_side=side,historical_input_sha256=source_hashes['search/exact/batch/inputs/n-211.txt'],
            n=211,cells=[dict(hold=h,noise=noise,seed=seed,r0='.2')for h,noise,seed in CELLS],
            fixed_defaults=dict(pre=2000,release=4000,settle=3000,hold_f=1.,lr=.04,mu=.02,beta=.85,velocity_cap=.03),
            rustc_path=str(RUSTC),rustc_sha256=sha(RUSTC),fq_path=str(FQ),fq_sha256=FQ_SHA,
            source_unchanged=True,unit_sizes_final=1.,missing_176_seed='Exact13.808663 source not located; not substituted.',
            work_seconds=180,whole_seconds=210,workers=1,no_quiet_parameter_retuning=True,
            source_caveats=['Disk endpoint h0 in fresh is not exercised.','Box force versus symmetric-resize derivative may reflect normalization/preconditioning; unchanged source is benchmarked, not silently corrected.'],
            published_limit='Prior author reports0newrecords across109≤324 packings plus multi-band negatives; historical reproduction is a mechanism control, not score gain evidence.')
        save(out/'manifest.json',manifest)
        compiler=[str(RUSTC),'--edition','2021','-O',str(source/'search/packer/src/harden.rs'),'-o',str(out/'bin/harden')]
        build=command(compiler,out/'build',15.,deadline);result['build']=build
        if build['status']!='complete':raise ValueError('Bounded separate build did not complete')
        result['hardener_sha256']=sha(out/'bin/harden')
        test=command([str(out/'bin/harden'),'test'],out/'gradient-test',20.,deadline);result['gradient_test']=test
        if test['status']!='complete':raise ValueError('Bounded public force/gradient checks did not complete')
        reports=[json.loads(line)for line in (out/'gradient-test.stdout').read_text().splitlines()if line.startswith('{')]
        if len(reports)!=2 or reports[0]['grad_err_gt_1e-5'].split('/')[0]!='0' or reports[1]['energy_grad_bad']!='0/90':
            raise ValueError('Public force/gradient controls failed; no parameter retuning')
        result['force_controls']=reports
        # Identical original historical decimal input goes directly to harden.
        # Native finisher follows the public wrapper's POLISH (noALM/loosen1).
        for i,(hold,noise,seed)in enumerate(CELLS):
            if deadline-time.monotonic()<34.:
                records.append(dict(slot=i,status='skipped_fixed_budget',hold=hold,noise=noise,seed=seed));continue
            base=trials/f'slot-{i:02d}';raw=base.with_suffix('.harden.out');pol=base.with_suffix('.polish.out')
            argv=[str(out/'bin/harden'),'reharden','--in',str(source/'search/exact/batch/inputs/n-211.txt'),
                '--out',str(raw),'--seed',str(seed),'--r0','.2','--noise',noise,'--hold',str(hold)]
            row=dict(slot=i,hold=hold,noise=noise,seed=seed,source_input_sha256=manifest['historical_input_sha256'])
            row['hardener']=command(argv,base.with_suffix('.harden'),18.,deadline)
            if raw.exists():
                row['raw_hardener_output_sha256']=sha(raw)
                row['hardener_certificate'],q=certify_output(raw,f'slot-{i:02d}-harden',trials,deadline)
                if q is not None:banks[f'slot_{i}_harden']=q
                argv=[str(FQ),'quench','--in',str(raw),'--out',str(pol),'--loosen','1','--no-alm','--seed',str(seed)]
                row['native_polish']=command(argv,base.with_suffix('.polish'),10.,deadline)
                if pol.exists():
                    row['polish_certificate'],q=certify_output(pol,f'slot-{i:02d}-polish',trials,deadline)
                    if q is not None:banks[f'slot_{i}_polish']=q
            records.append(row);save(out/'results.json',records);np.savez_compressed(out/'certified.npz',**banks)
            print(json.dumps(dict(slot=i,hardener_status=row['hardener']['status'],polish_side=row.get('polish_certificate',{}).get('worst_certified_side'),elapsed=time.monotonic()-STARTED)),flush=True)
        lengths=[Decimal(c['worst_certified_side'])for row in records for key in ['hardener_certificate','polish_certificate']if(c:=row.get(key,{})).get('status')=='certified']
        best=min(lengths)if lengths else None
        result.update(status='complete',trials=len(records),certified=len(banks),best_certified_side=str(best)if best else None,
            historical_seed_side=side,historical_improvement=bool(best is not None and best<Decimal(side)-Decimal('1e-8')),
            published_first_211_side_reproduced=bool(best is not None and best<=Decimal('14.9937')),
            interpretation='Finite fixed published cells/seeds only; timeout/no-hit is not a reproduction of the full432-run published effort. No largeN or present-record gain claim.')
    except ControlDeadline:result.update(status='deadline_partial')
    except Exception as error:result.update(status='failed_closed',error_type=type(error).__name__,error=str(error)[:180])
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        save(out/'results.json',records);np.savez_compressed(out/'certified.npz',**banks)
        result.update(seconds=time.monotonic()-STARTED,source_sha256=sha(__file__),manifest_sha256=sha(out/'manifest.json')if(out/'manifest.json').exists()else None,
            certified_archive_sha256=sha(out/'certified.npz'),results_sha256=sha(out/'results.json'))
        save(out/'summary.json',result);print(json.dumps(result,allow_nan=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if args.worker:return worker(args.out)
    child=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'--worker','--out',str(args.out.resolve())],start_new_session=True)
    forced=False
    try:child.wait(timeout=max(.1,STARTED+200.-time.monotonic()))
    except subprocess.TimeoutExpired:forced=True
    finally:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=2.)
    args.out.mkdir(parents=True,exist_ok=True)
    save(args.out/'supervisor.json',dict(returncode=child.returncode,forced=forced,seconds=time.monotonic()-STARTED,
        worker_seconds=180,whole_seconds=210,no_gpu=True,no_submission=True))


if __name__=='__main__':main()
