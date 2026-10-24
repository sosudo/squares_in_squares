"""Finite three-CPU timeout-cap extension of16 frozen, unchanged whole poses.

Native return bytes are retained before separately bounded decoding/certification.
No canonical files, competition submissions, or GPU resources are modified.
"""
from __future__ import annotations
import time
STARTED=time.monotonic()
import argparse
from concurrent.futures import FIRST_COMPLETED,ProcessPoolExecutor,wait
from decimal import Decimal
import hashlib,json,math,multiprocessing as mp,os
from pathlib import Path
import shutil,signal,subprocess,sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from fq_active_pilot import SOURCE_COMMIT,decode,digest,encode
from fq_capacity_probe import full_certificate
from fq_joint_seed_check import BINARY_SHA
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from score_official import OFFICIAL_SHA256
ROOT=Path(__file__).resolve().parents[1]
RIGID_FLAGS=['--loosen','1','--outer','45','--pit','20','--flip-top','0']
NATIVE_SECONDS=30.;CERTIFICATE_SECONDS=6.


class CertificateDeadline(BaseException):
    """Escapes metric exception handlers so the certificate clock stays bounded."""


def _alarm(*_):raise CertificateDeadline('separate_certificate_deadline')


def parsed_output(path,n):
    lines=path.read_text().splitlines()
    if not lines or int(lines[0].split()[0])!=n or len(lines)!=n+1:raise ValueError('native_count_mismatch')
    q=np.array([[float(v)for v in line.split()]for line in lines[1:]],dtype=np.float64)
    if q.shape!=(n,3)or not np.isfinite(q).all():raise ValueError('invalid_native_coordinates')
    q[:,2]=np.radians(q[:,2]);return q


def worker(job):
    n,p,canonical,entry,index,binary,root,deadline=job
    root=Path(root);base=root/'trials'/f'n{n}-rigid-{index:04d}';record=dict(n=n,job=index,mode='rigid_current',
        category=entry['category'],original_job=entry['original_job'],original_seed=entry['original_seed'],legacy_history=entry.get('legacy_history','uncertain_outside_recent_pinned_archives'),
        parent_geometry_sha256=geometry_sha(p),canonical_raw_side=canonical,native_seconds_cap=NATIVE_SECONDS,
        certificate_seconds_cap=CERTIFICATE_SECONDS)
    atomic_npz(base.with_suffix('.parent.npz'),{'pose':p});record['parent_archive_sha256']=digest(base.with_suffix('.parent.npz'))
    text,offsets=encode(p,math.isqrt(n),math.isqrt(n));base.with_suffix('.in').write_text(text)
    record['input_sha256']=digest(base.with_suffix('.in'))
    assert record['input_sha256']==entry['original_input_sha256'],'Encoded parent changed from original timeout'
    command=[binary,'quench','--in',str(base.with_suffix('.in')),'--out',str(base.with_suffix('.out')),
        '--rect-dx',str(offsets[0]),'--rect-dy',str(offsets[1]),'--seed',str(entry['original_seed']),*RIGID_FLAGS,'--v']
    record['command']=command;record['command_sha256']=hashlib.sha256(json.dumps(command,separators=(',',':')).encode()).hexdigest()
    native_begin=time.monotonic();remaining=deadline-native_begin
    if remaining<1.:record['status']='deadline_before_native';return record,None
    stdout=stderr=b''
    try:
        environment=os.environ.copy()
        assert not {key for key in environment if key.startswith('FQ_')and key not in {'FQ_TR','FQ_LPT'}},'Unexpected inherited numeric native options'
        environment.update(FQ_TR='1',FQ_LPT='1')
        run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment,timeout=min(NATIVE_SECONDS,remaining))
        stdout,stderr=run.stdout,run.stderr;record['returncode']=run.returncode;record['native_status']='returned'
    except subprocess.TimeoutExpired as error:
        stdout=error.stdout or b'';stderr=error.stderr or b'';record['native_status']='timeout';record['returncode']=None
    finally:
        record['native_seconds']=time.monotonic()-native_begin
        base.with_suffix('.stdout').write_bytes(stdout);base.with_suffix('.stderr').write_bytes(stderr)
        base.with_suffix('.log').write_bytes(stdout+b'\n'+stderr)
        for name in ('stdout','stderr','log'):record[name+'_sha256']=digest(base.with_suffix('.'+name))
        trace_lines=stderr.decode(errors='replace').splitlines()
        record['trace_phase_counts']={'outer':sum(line.startswith('outer ')for line in trace_lines),'slp':sum(line.strip().startswith('slp ')for line in trace_lines),'trust_region':sum(line.startswith('tr ')for line in trace_lines)}
        record['last_phase_lines']=[line for line in trace_lines if line.startswith('outer ')or line.strip().startswith('slp ')or line.startswith('tr ')][-6:]
    try:
        value=json.loads(stdout.decode().strip().splitlines()[-1]);json.dumps(value,allow_nan=False)
        if isinstance(value,dict):record['fq']=value
    except (ValueError,IndexError,UnicodeError):pass
    dst=base.with_suffix('.out')
    if not dst.exists():record['status']='no_native_output';atomic_json(base.with_suffix('.record.json'),record);return record,None
    record['native_output_path']=str(dst);record['native_output_sha256']=digest(dst)
    try:raw=parsed_output(dst,n)
    except (ValueError,IndexError,OSError):
        record['status']='malformed_native_output';atomic_json(base.with_suffix('.record.json'),record);return record,None
    returned=root/'raw-returned'/f'{index:04d}-n{n}.npz';atomic_npz(returned,{'pose':raw})
    record['raw_returned']=dict(path=str(returned),sha256=digest(returned),geometry_sha256=geometry_sha(raw),verified=False)
    record['status']='saved_native_return_before_certificate';atomic_json(base.with_suffix('.record.json'),record)
    remaining=deadline-time.monotonic()
    if remaining<.2:record['status']='saved_return_certificate_budget_exhausted';return record,None
    begin=time.monotonic();old_handler=signal.signal(signal.SIGALRM,_alarm);signal.setitimer(signal.ITIMER_REAL,min(CERTIFICATE_SECONDS,remaining))
    try:
        q=decode(dst,n)
        if q is None:record['status']='failed_bounded_clearance';return record,None
        decoded=root/'decoded'/f'{index:04d}-n{n}.npz';atomic_npz(decoded,{'pose':q})
        record['decoded_returned']=dict(path=str(decoded),sha256=digest(decoded),geometry_sha256=geometry_sha(q))
        certificate=full_certificate(q);record['certificate']=certificate
        if not certificate['valid']:record['status']='failed_full_gates';return record,None
        identity=geometry_sha(q);key=f'{n}__current_rigid_{identity}';record.update(status='certified',geometry_sha256=identity,archive_key=key,
            side=certificate['independent_raw']['side_upper'])
        record['side_gain']=str(Decimal(canonical)-Decimal(record['side']));record['score_gain']=float(Decimal(record['side_gain']))/math.sqrt(n)
        target=root/'retained'/f'{index:04d}-{identity}.npz';atomic_npz(target,{key:q})
        record['retained_archive']=str(target);record['retained_archive_sha256']=digest(target)
        atomic_json(target.with_suffix('.json'),dict(record=record,archive_sha256=digest(target)))
        target.chmod(0o444);target.with_suffix('.json').chmod(0o444)
        return record,q
    except CertificateDeadline:record['status']='saved_return_certificate_timeout';return record,None
    except Exception as error:record.update(status='saved_return_certificate_error',error_type=type(error).__name__);return record,None
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old_handler)
        record['certificate_seconds']=time.monotonic()-begin;atomic_json(base.with_suffix('.record.json'),record)


def campaign(args):
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','source','trials','raw-returned','decoded','retained','snapshots'):(out/name).mkdir()
    frozen=json.loads((args.inputs/'freeze.json').read_text())
    for name,sha in frozen['files'].items():assert digest(args.inputs/name)==sha
    audit=json.loads((args.inputs/'audit.json').read_text());baseline=audit['pointer']['raw']
    assert baseline['sha256']=='fc931068f0f4accb37c8ed8b33ea59607e4690440d7c3f98b4b79fbb8c34cffc'
    assert digest(baseline['path'])==baseline['sha256']and digest(baseline['official_report'])==baseline['official_report_sha256']
    official=json.loads(Path(baseline['official_report']).read_text())
    assert official['valid']and official['puzzles']==1000 and official['sha256']==baseline['sha256']and official['metric_sha256']==OFFICIAL_SHA256
    sides={r['n']:r['side']for r in official['results']};queue=audit['finite_queue'];assert len(queue)<=16
    assert len({r['n']for r in queue})==len(queue)and not {147,299,335,858}&{r['n']for r in queue}
    assert all(r['category']not in ('redundant_completed_rigid_result','redundant_completed_rigid_current_input')for r in queue)
    with np.load(args.inputs/'inputs/current-poses.npz',allow_pickle=False)as archive:poses={int(k):archive[k]for k in archive.files}
    assert all(geometry_sha(poses[r['n']])==r['geometry_sha256']for r in queue)
    for name in ('audit.json','freeze.json','pointer.json'):shutil.copyfile(args.inputs/name,out/'inputs'/name)
    shutil.copyfile(args.inputs/'inputs/current-poses.npz',out/'inputs/current-poses.npz')
    binary=out/'inputs/fq';shutil.copyfile(args.binary,binary);binary.chmod(0o500);assert digest(binary)==BINARY_SHA
    source_paths=[Path(__file__),ROOT/'experiments/prepare_timeout_extension_sweep.py',ROOT/'experiments/fq_current_rigid_campaign.py',ROOT/'experiments/fq_active_pilot.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_joint_seed_check.py',ROOT/'experiments/fq_variant_campaign.py',ROOT/'experiments/compose_gadgets.py',
        ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py']
    source_hashes={}
    for p in source_paths:
        destination=out/'source'/p.name;shutil.copyfile(p,destination);destination.chmod(0o444);source_hashes[str(p)]=digest(destination)
    manifest=dict(baseline=baseline,input_freeze_sha256=digest(args.inputs/'freeze.json'),input_audit_sha256=digest(args.inputs/'audit.json'),
        binary_sha256=BINARY_SHA,source_commit=SOURCE_COMMIT,metric_sha256=OFFICIAL_SHA256,source_hashes=source_hashes,
        workers=3,maximum_total_seconds=240,native_seconds_cap=NATIVE_SECONDS,certificate_seconds_cap=CERTIFICATE_SECONDS,
        numeric_flags=RIGID_FLAGS,observational_flag='--v',trace_environment_overrides={'FQ_TR':'1','FQ_LPT':'1'},queue=queue,no_canonical_mutation=True,no_submission=True,
        artifact_policy='Exact native output/stdout/stderr/log/parent and parsed raw array are saved before separate certification; no unchanged-result retry. Same original parents/seeds; only timeout budget and observational logging change.')
    atomic_json(out/'manifest.json',manifest);records=[];donors={};candidates={};snapshot_count=0
    def checkpoint(status,gain=False):
        nonlocal snapshot_count
        atomic_json(out/'results.json',records);atomic_json(out/'candidates.json',candidates)
        summary=dict(status=status,seconds=time.monotonic()-STARTED,trials=len(records),queue_count=len(queue),
            certified_geometries=len(donors),improved_cases=len(candidates),score_gain=sum(r['score_gain']for r in candidates.values()),
            candidates_sha256=digest(out/'candidates.json'),results_sha256=digest(out/'results.json'),manifest_sha256=digest(out/'manifest.json'),
            source_hashes_unchanged=all(digest(p)==sha for p,sha in source_hashes.items()))
        atomic_json(out/'summary.json',summary)
        if gain:
            snapshot_count+=1;snapshot=out/'snapshots'/f'gain-{snapshot_count:04d}';snapshot.mkdir()
            for name in ('candidates.json','results.json','summary.json'):shutil.copyfile(out/name,snapshot/name);(snapshot/name).chmod(0o444)
            atomic_json(out/'latest-immutable.json',dict(path=str(snapshot),candidate_sha256=digest(snapshot/'candidates.json'),results_sha256=digest(snapshot/'results.json'),summary_sha256=digest(snapshot/'summary.json')))
        return summary
    checkpoint('prepared');pending={};cursor=0
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('fork'))as pool:
        while cursor<len(queue)or pending:
            while len(pending)<3 and cursor<len(queue)and time.monotonic()<args.deadline-2:
                entry=queue[cursor];cursor+=1;n=entry['n'];future=pool.submit(worker,(n,poses[n],sides[n],entry,cursor,str(binary.resolve()),str(out.resolve()),args.deadline));pending[future]=n
            if not pending:break
            ready,_=wait(pending,timeout=.25,return_when=FIRST_COMPLETED)
            for future in ready:
                pending.pop(future);record,q=future.result();gain=False
                if q is not None:
                    donors[record['archive_key']]=q
                    if Decimal(record['side'])<Decimal(sides[record['n']])-Decimal('1e-8'):
                        ns=str(record['n']);candidates[ns]=dict(side=record['side'],squares=[[f'{v:.17g}'for v in row]for row in q],
                            certificate=record['certificate'],score_gain=record['score_gain'],source='Finite longer-budget native timeout continuation with unchanged parent and seed',
                            provenance=dict(job=record['job'],original_job=record['original_job'],original_seed=record['original_seed'],parent_geometry_sha256=record['parent_geometry_sha256'],native_output_sha256=record['native_output_sha256'],
                                raw_geometry_sha256=record['raw_returned']['geometry_sha256'],command_sha256=record['command_sha256'],archive_key=record['archive_key']));gain=True
                records.append(record);summary=checkpoint('running',gain)
                print(json.dumps(dict(n=record['n'],status=record['status'],side_gain=record.get('side_gain'),total_gain=summary['score_gain'],trials=len(records))),flush=True)
            if time.monotonic()>=args.deadline+1:break
    atomic_npz(out/'donors.npz',donors);summary=checkpoint('complete'if len(records)==len(queue)else'deadline_partial')
    final=out/'complete';final.mkdir()
    for name in ('candidates.json','results.json','summary.json','manifest.json','donors.npz'):shutil.copyfile(out/name,final/name);(final/name).chmod(0o444)
    print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq');parser.add_argument('--child',action='store_true');parser.add_argument('--deadline',type=float)
    args=parser.parse_args()
    if args.child:return campaign(args)
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child','--deadline',str(STARTED+226.)],start_new_session=True)
    forced=False
    try:process.wait(timeout=max(.01,STARTED+237.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=1.)
    receipt=dict(returncode=process.returncode,seconds=time.monotonic()-STARTED,workers=3,maximum_total_seconds=240,hard_deadline_enforced=forced)
    if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.returncode and not forced:raise SystemExit(process.returncode)


if __name__=='__main__':main()
