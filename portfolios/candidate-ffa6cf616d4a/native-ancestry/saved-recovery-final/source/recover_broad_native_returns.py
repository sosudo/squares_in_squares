"""Recover already-saved native outputs after the bounded broad CPU campaign.

No native executable or optimizer is run. Only decoded side-promising returns
receive the unchanged full raw/default-pandas/independent certificates.
"""
import time
STARTED=time.monotonic()
import argparse
from decimal import Decimal
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from fq_active_pilot import decode,encode,digest,SOURCE_COMMIT
from fq_capacity_probe import full_certificate
from compose_gadgets import side
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha

ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=ROOT/'artifacts/fq-broad-contact-v1'
EXCLUDED={12,26,69}


def readonly_copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);target.chmod(0o444)
    return dict(original=str(source),path=str(target),sha256=digest(target),bytes=target.stat().st_size)


def current_thresholds(directory):
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pointer=json.loads(pointer_path.read_text())
    raw=pointer['raw'];ind=pointer['independent_report']
    for path,expected in [(Path(raw['path']),raw['sha256']),(Path(raw['official_report']),raw['official_report_sha256']),
                          (Path(ind['path']),ind['sha256'])]:
        if digest(path)!=expected:raise ValueError('Current canonical comparison bytes differ')
    independent=json.loads(Path(ind['path']).read_text())
    if not independent['valid']or independent['sha256']!=raw['sha256']:raise ValueError('Canonical interval proof mismatch')
    directory.mkdir(parents=True,exist_ok=True)
    readonly_copy(pointer_path,directory/'canonical-pointer.json')
    readonly_copy(Path(raw['official_report']),directory/'canonical-official.json')
    readonly_copy(Path(ind['path']),directory/'canonical-independent.json')
    return {int(r['n']):Decimal(r['side_lower'])for r in independent['results']},pointer


def add_certified_thresholds(thresholds,candidates):
    for n,r in candidates.items():
        cert=r['certificate']
        if not cert['valid']:raise ValueError('Comparison candidate lacks successful full certificate')
        bound=Decimal(cert['independent_raw']['side_lower'])
        thresholds[int(n)]=min(thresholds[int(n)],bound)


def cap_expired(*_):raise TimeoutError('Saved-output full certificate cap')


def worker(args):
    os.setsid();os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    deadline=STARTED+174;out=args.out;frozen=out/'comparison';frozen.mkdir()
    original_final=CAMPAIGN/'complete'
    supervisor=json.loads((CAMPAIGN/'supervisor.json').read_text())
    if supervisor['returncode']!=0:raise ValueError('Expected finalized broad campaign')
    snapshots={}
    for name in ['results.json','candidates.json','summary.json','manifest.json']:
        if digest(CAMPAIGN/name)!=digest(original_final/name):raise ValueError('Broad final snapshot is not stable')
        snapshots[name]=readonly_copy(original_final/name,frozen/name)
    snapshots['supervisor.json']=readonly_copy(CAMPAIGN/'supervisor.json',frozen/'supervisor.json')
    broad=json.loads((frozen/'candidates.json').read_text());records=json.loads((frozen/'results.json').read_text())
    final_summary=json.loads((frozen/'summary.json').read_text());campaign_manifest=json.loads((frozen/'manifest.json').read_text())
    if final_summary['results_sha256']!=snapshots['results.json']['sha256']or final_summary['candidates_sha256']!=snapshots['candidates.json']['sha256']:
        raise ValueError('Broad final summary hash mismatch')
    thresholds,pointer=current_thresholds(frozen/'initial-canonical');add_certified_thresholds(thresholds,broad)
    old_recovery=ROOT/'artifacts/fq-broad-contact-recovery-v1/candidates.json'
    old_candidates=json.loads(old_recovery.read_text());add_certified_thresholds(thresholds,old_candidates)
    snapshots['prior_recovery_candidates']=readonly_copy(old_recovery,frozen/'prior-recovery-candidates.json')
    sources=out/'source';sources.mkdir();source_hashes={}
    for path in [Path(__file__),ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_capacity_probe.py',
                 ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',
                 ROOT/'research/official_metric_v17.py',ROOT/'artifacts/fq-broad-contact-recovery-v1/source/recover_broad_returns.py']:
        source_hashes[str(path)]=readonly_copy(path,sources/path.name)['sha256']
    # Reconstruct parent identities from the campaign's immutable starting bank
    # and already-certified retained stages; never recompute their certificates.
    parent_lookup={}
    parent_bank=CAMPAIGN/'inputs/current-poses.npz'
    with np.load(parent_bank,allow_pickle=False)as z:
        for name in z.files:
            p=z[name];parent_lookup[geometry_sha(p)]=(parent_bank,name)
    for r in records:
        if r.get('retained_archive')and r.get('geometry_sha256'):
            parent_lookup[r['geometry_sha256']]=(Path(r['retained_archive']),r['archive_key'])
    by_output={}
    for r in records:
        command=r.get('command',[])
        if '--out'in command:
            name=Path(command[command.index('--out')+1]).name
            if name in by_output:raise ValueError('Duplicate native output identity')
            by_output[name]=r
    inputs=out/'inputs';inputs.mkdir();screen=[];pending=[];inventory=[];seen_geometry=set()
    outputs=sorted((CAMPAIGN/'trials').glob('*.out'))
    for path in outputs:
        r=by_output.get(path.name)
        item=dict(path=str(path),sha256=digest(path),bytes=path.stat().st_size,
                  job=r.get('job')if r else None,n=r.get('n')if r else None)
        inventory.append(item)
        if r is None:raise ValueError('Unmapped saved native return; cannot silently omit it')
        if r.get('native_output_sha256')and item['sha256']!=r['native_output_sha256']:raise ValueError('Native return changed')
        if r.get('certificate',{}).get('valid'):
            item['screen']='already_successfully_certified';continue
        if r['job']in EXCLUDED:
            item['screen']='excluded_already_recovered_job';continue
        n=int(r['n']);folder=inputs/f"job-{r['job']:04d}-n{n}";folder.mkdir()
        item['files']={};item['files']['native.out']=readonly_copy(path,folder/'native.out')
        atomic_json(folder/'original-record.json',r);(folder/'original-record.json').chmod(0o444)
        item['original_record_sha256']=digest(folder/'original-record.json')
        command=r['command'];inp=Path(command[command.index('--in')+1])
        if digest(inp)!=r['input_sha256']:raise ValueError('Original native input changed')
        item['files']['native.in']=readonly_copy(inp,folder/'native.in')
        for suffix in ['.log','.native-stdout','.native-stderr']:
            source=path.with_suffix(suffix)
            if source.exists():item['files'][suffix]=readonly_copy(source,folder/('native'+suffix))
        entry=dict(n=n,job=r['job'],original_status=r['status'],native_output_sha256=item['sha256'],
            original_record_sha256=item['original_record_sha256'],parent_geometry_sha256=r['parent_geometry_sha256'],
            stronger_side_threshold=str(thresholds[n]),source_files=item['files'],
            native_command_for_lineage_only=command,no_native_execution=True)
        try:
            lines=(folder/'native.out').read_text().splitlines()
            if len(lines)!=n+1 or int(lines[0].split()[0])!=n:raise ValueError('Incomplete native output count')
            raw=np.array([[float(v)for v in row.split()]for row in lines[1:]])
            if raw.shape!=(n,3)or not np.isfinite(raw).all():raise ValueError('Incomplete/nonfinite native output')
            raw[:,2]=np.radians(raw[:,2]);entry['raw_geometry_sha256']=geometry_sha(raw)
            saved=r.get('raw_returned')
            if saved:
                raw_path=Path(saved['path'])
                if digest(raw_path)!=saved['sha256']:raise ValueError('Saved raw-returned archive changed')
                with np.load(raw_path,allow_pickle=False)as z:
                    if not np.array_equal(raw,z['pose'])or geometry_sha(raw)!=saved['geometry_sha256']:
                        raise ValueError('Native text/raw-returned exact geometry mismatch')
                entry['raw_returned']=readonly_copy(raw_path,folder/'raw-returned.npz')
            parent_path,parent_key=parent_lookup[r['parent_geometry_sha256']]
            with np.load(parent_path,allow_pickle=False)as z:parent=z[parent_key].copy()
            if geometry_sha(parent)!=r['parent_geometry_sha256']:raise ValueError('Parent geometry identity mismatch')
            encoded,_=encode(parent,math.floor(side(parent)),math.floor(side(parent)))
            if hashlib.sha256(encoded.encode()).hexdigest()!=r['input_sha256']:raise ValueError('Parent-to-native-input exact text mismatch')
            atomic_npz(folder/'parent.npz',{'pose':parent});(folder/'parent.npz').chmod(0o444)
            entry['parent_verified']=True;entry['parent_archive_source']=dict(path=str(parent_path),key=parent_key,sha256=digest(parent_path))
            q=decode(folder/'native.out',n)
            if q is None:entry['status']='failed_bounded_rounding_clearance'
            else:
                entry.update(decoded_geometry_sha256=geometry_sha(q),decoded_side=side(q))
                if Decimal(str(side(q)))>=thresholds[n]:entry['status']='dominated_after_decode'
                elif geometry_sha(q)in seen_geometry:entry['status']='duplicate_decoded_geometry'
                else:
                    entry['status']='pending_full_certificate';seen_geometry.add(geometry_sha(q))
                    entry['estimated_score_gain']=(float(thresholds[n])-side(q))/math.sqrt(n)
                    pending.append((entry,q))
                    atomic_npz(folder/'decoded-UNVERIFIED.npz',{'pose':q});(folder/'decoded-UNVERIFIED.npz').chmod(0o444)
        except (ValueError,KeyError,IndexError)as error:
            entry.update(status='saved_return_rejected',error_type=type(error).__name__,error=str(error))
        item['screen']=entry['status'];screen.append(entry)
    raw_inventory=[dict(path=str(p),sha256=digest(p))for p in sorted((CAMPAIGN/'raw-returned').glob('*.npz'))]
    if {Path(r['raw_returned']['path']).resolve()for r in records if r.get('raw_returned')}!={Path(r['path']).resolve()for r in raw_inventory}:
        raise ValueError('Unaccounted raw-returned archive')
    atomic_json(out/'native-return-inventory.json',inventory);atomic_json(out/'raw-returned-inventory.json',raw_inventory)
    atomic_json(out/'screen.json',screen)
    freeze=dict(final_campaign_snapshots=snapshots,canonical_pointer=pointer,excluded_jobs=sorted(EXCLUDED),
        total_native_returns=len(outputs),already_certified=sum(i['screen']=='already_successfully_certified'for i in inventory),
        screened_unrecovered=len(screen),side_promising=len(pending),all_raw_returned_archives_accounted=True,
        initial_parent_bank_sha256=digest(parent_bank),source_hashes=source_hashes,
        native_binary_sha256=campaign_manifest['binary_sha256'],source_commit=SOURCE_COMMIT,
        native_inventory_sha256=digest(out/'native-return-inventory.json'),screen_sha256=digest(out/'screen.json'),
        maximum_seconds=180,workers=1,no_native_execution=True,no_campaign_mutation=True)
    atomic_json(out/'freeze.json',freeze)
    print(json.dumps(dict(stage='screen_complete',total_returns=len(outputs),screened=len(screen),promising=len(pending),
        cases=[r['n']for r,q in sorted(pending,key=lambda x:-x[0]['estimated_score_gain'])])),flush=True)
    results=[];donors={};candidates={};previous=signal.signal(signal.SIGALRM,cap_expired)
    for record,q in sorted(pending,key=lambda x:-x[0]['estimated_score_gain']):
        if deadline-time.monotonic()<3:break
        n=record['n'];record=dict(record)
        if Decimal(str(side(q)))>=thresholds[n]:record['status']='dominated_by_recovered_result';results.append(record);continue
        begin=time.monotonic();signal.setitimer(signal.ITIMER_REAL,min(30.,deadline-time.monotonic()-2))
        try:
            certificate=full_certificate(q);record['certificate']=certificate
            record['status']='certified'if certificate['valid']else'failed_full_gates'
            if certificate['valid']:
                upper=max(Decimal(certificate['independent_raw']['side_upper']),Decimal(certificate['independent_roundtrip']['side_upper']))
                record['side_upper']=str(upper);key=f"{n}__recovered_job{record['job']}_{geometry_sha(q)}";donors[key]=q
                archive=out/f"job-{record['job']:04d}-n{n}-certified.npz";atomic_npz(archive,{key:q});archive.chmod(0o444)
                record['certified_archive']=str(archive);record['certified_archive_sha256']=digest(archive)
                record['strict_gain_vs_stronger_comparison']=upper<thresholds[n]
                if upper<thresholds[n]:
                    gain=(float(thresholds[n])-float(upper))/math.sqrt(n)
                    candidates[str(n)]=dict(side=str(upper),squares=[[f'{v:.17g}'for v in row]for row in q],
                        certificate=certificate,source='Final broad saved native output recovery; no optimizer',score_gain=gain,
                        provenance=dict(original_job=record['job'],native_output_sha256=record['native_output_sha256'],
                            raw_geometry_sha256=record['raw_geometry_sha256'],geometry_sha256=geometry_sha(q),
                            parent_geometry_sha256=record['parent_geometry_sha256'],original_record_sha256=record['original_record_sha256'],
                            recovery_source_sha256=digest(Path(__file__)),source_commit=SOURCE_COMMIT,
                            native_binary_sha256=campaign_manifest['binary_sha256']))
                    thresholds[n]=upper
        except TimeoutError:record['status']='certificate_timeout'
        finally:signal.setitimer(signal.ITIMER_REAL,0)
        record['certification_seconds']=time.monotonic()-begin;results.append(record)
        proof=out/f"job-{record['job']:04d}-n{n}-result.json";atomic_json(proof,record);proof.chmod(0o444)
        atomic_json(out/'results.json',results);atomic_json(out/'candidates.json',candidates);atomic_npz(out/'donors.npz',donors)
        print(json.dumps(dict(n=n,job=record['job'],status=record['status'],side=record.get('side_upper'),
            strict_gain=record.get('strict_gain_vs_stronger_comparison'),seconds=time.monotonic()-STARTED)),flush=True)
    signal.signal(signal.SIGALRM,previous)
    latest,new_pointer=current_thresholds(frozen/'final-canonical');add_certified_thresholds(latest,broad);add_certified_thresholds(latest,old_candidates)
    candidates={n:r for n,r in candidates.items()if Decimal(r['side'])<latest[int(n)]}
    for n,r in candidates.items():r['score_gain']=(float(latest[int(n)])-float(r['side']))/math.sqrt(int(n))
    atomic_json(out/'results.json',results);atomic_json(out/'candidates.json',candidates);atomic_npz(out/'donors.npz',donors)
    summary=dict(status='complete'if len(results)==len(pending)else'deadline_partial',seconds=time.monotonic()-STARTED,
        total_native_returns=len(outputs),screened_uncertified_returns=len(screen),excluded_jobs=sorted(EXCLUDED),
        side_promising=len(pending),full_certificates_completed=sum('certificate'in r for r in results),
        retained_certified_geometries=len(donors),improved_cases=sorted(map(int,candidates)),
        score_gain_vs_stronger_final_comparison=sum(r['score_gain']for r in candidates.values()),
        final_canonical_raw_sha256=new_pointer['raw']['sha256'],freeze_sha256=digest(out/'freeze.json'),
        candidates_sha256=digest(out/'candidates.json'),donors_sha256=digest(out/'donors.npz'),results_sha256=digest(out/'results.json'),
        no_native_execution=True,no_campaign_mutation=True)
    atomic_json(out/'summary.json',summary)
    for path in out.rglob('*'):
        if path.is_file():path.chmod(0o444)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);process=mp.get_context('fork').Process(target=worker,args=(args,));process.start()
    process.join(max(0.,178.-(time.monotonic()-STARTED)));forced=process.is_alive()
    if forced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.join(timeout=max(0.,180.-(time.monotonic()-STARTED)))
    atomic_json(args.out/'supervisor.json',dict(exitcode=process.exitcode,forced_kill=forced,seconds=time.monotonic()-STARTED,
        maximum_seconds=180,workers=1,no_native_execution=True))
    if forced or process.exitcode:raise SystemExit(1)
