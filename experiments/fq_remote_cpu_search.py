"""Four-core private FQ campaign with exact certified stage retention."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
import fq_active_pilot as fq
from fq_capacity_probe import full_certificate
from fq_coherent_clusters import Deadline, alarm, grouped_run
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha
import fq_productive_campaign as productive


def strict_trial(job):
    """Keep the original native method, adding full gates and bounded groups."""
    key, pose, mode, binary, directory, seed, cap, deadline=job
    started=time.monotonic();w,h,d=map(int,key.split('_'))
    if pose.shape!=(w*h+d,3):raise ValueError('Invalid rectangle dimensions')
    options=list(fq.MODES[mode]);remaining=min(cap,deadline-started)
    record=dict(key=key,mode=mode,seed=seed,before=fq.bloat(pose,w,h),
        parent_geometry_sha256=geometry_sha(pose),command_options=options)
    if remaining<=1:return dict(record,status='budget-skipped'),None
    directory=Path(directory);name=f'{key}-{mode}-{seed}'
    inp,dst,log=(directory/(name+suffix)for suffix in ('.in','.out','.log'))
    previous=signal.signal(signal.SIGALRM,alarm)
    signal.setitimer(signal.ITIMER_REAL,remaining)
    try:
        encoded,offsets=fq.encode(pose,w,h);inp.write_text(encoded)
        command=[str(binary),'quench','--in',str(inp),'--out',str(dst),
            '--rect-dx',str(offsets[0]),'--rect-dy',str(offsets[1]),'--seed',str(seed),*options]
        record.update(command=command,input_sha256=fq.digest(inp),binary_sha256=fq.digest(binary))
        result=grouped_run(command,timeout=max(.01,remaining-(time.monotonic()-started)),text=True)
        log.write_text(result.stdout+'\n'+result.stderr)
        record.update(returncode=result.returncode,log_sha256=fq.digest(log))
        if result.returncode or not dst.exists():return dict(record,status='native-failed'),None
        native=json.loads(result.stdout.strip().splitlines()[-1]);json.dumps(native,allow_nan=False)
        record['fq']=native
        if '--soft-a0'in options:
            eps=[float(x)for x in re.findall(r'soft eps ([0-9.eE+-]+) hold',result.stderr)]
            count=int(options[options.index('--soft-steps')+1]);amplitude=float(options[options.index('--soft-a0')+1])
            valid=(len(eps)==count and eps[-1]==0. and all(a>=b>=0 for a,b in zip(eps,eps[1:]))
                   and native.get('soft',{}).get('a0')==amplitude)
            record['rigid_return_trace']=dict(valid=valid,reported_aspect_epsilons=eps,final_reported_epsilon=eps[-1]if eps else None)
            if not valid:return dict(record,status='rejected_soft_return_trace'),None
        q=fq.decode(dst,len(pose))
        if q is None:return dict(record,status='failed-clearance'),None
        certificate=full_certificate(q);record['certificate']=certificate
        if not certificate['valid']:return dict(record,status='failed-full-certificate'),None
        after=fq.bloat(q,w,h);sha=geometry_sha(q)
        record.update(status='certified',after=after,gain=record['before']-after,
            strict_improvement=record['before']-after>5e-9,geometry_sha256=sha,
            output_sha256=fq.digest(dst),eligible_for_search=after<=record['before']+.002)
        # Commit every fully gated stage before another native stage can start.
        retained=directory.parent/'strict-stages';retained.mkdir(exist_ok=True)
        archive=retained/(name+'.npz');proof=retained/(name+'.json')
        if archive.exists()or proof.exists():raise ValueError('Immutable stage identity already exists')
        atomic_npz(archive,{key+'__strict_'+sha:q});archive.chmod(0o444)
        record.update(stage_archive=str(archive),stage_archive_sha256=fq.digest(archive),seconds=time.monotonic()-started)
        atomic_json(proof,record);proof.chmod(0o444)
        if not record['eligible_for_search']:
            return dict(record,status='certified_outside_search_band'),None
        return record,(key+'__strict_'+sha,q)
    except (Deadline,subprocess.TimeoutExpired):return dict(record,status='whole-stage-timeout'),None
    except Exception as error:return dict(record,status='exception',error_type=type(error).__name__,error=str(error)[:240]),None
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)


def collect(root):
    """Recover only complete immutable stages, including archive-only variants."""
    root=Path(root);poses={};proofs={};ignored_orphans=0
    for path in sorted((root/'strict-stages').glob('*.json')):
        record=json.loads(path.read_text());archive=Path(record['stage_archive'])
        if not archive.resolve().is_relative_to((root/'strict-stages').resolve()):raise ValueError('Stage archive escaped its directory')
        if fq.digest(archive)!=record['stage_archive_sha256']or not record['certificate']['valid']:
            raise ValueError('Certified stage proof mismatch')
        if '--soft-a0'in record['command_options']and not record['rigid_return_trace']['valid']:
            raise ValueError('Soft stage lacks an exact rigid return')
        with np.load(archive,allow_pickle=False)as z:
            if len(z.files)!=1:raise ValueError('Expected one pose per immutable stage')
            q=z[z.files[0]];key=record['key'];w,h,d=map(int,key.split('_'))
            if q.shape!=(w*h+d,3)or not np.isfinite(q).all()or geometry_sha(q)!=record['geometry_sha256']:
                raise ValueError('Stage geometry differs from its full certificate')
            identity=key+'__strict_'+record['geometry_sha256'];poses[identity]=q.copy()
            proofs.setdefault(identity,[]).append(dict(record=record,proof_sha256=fq.digest(path)))
    for path in (root/'strict-stages').glob('*.npz'):
        if not path.with_suffix('.json').exists():ignored_orphans+=1
    target=root/'remote-certified';target.mkdir(exist_ok=True)
    atomic_npz(target/'donors.npz',poses);atomic_json(target/'provenance.json',proofs)
    best={}
    for name,q in poses.items():
        key=name.split('__')[0];w,h,_=map(int,key.split('_'))
        if key not in best or fq.bloat(q,w,h)<fq.bloat(best[key],w,h):best[key]=q
    atomic_npz(target/'best_bank.npz',best)
    summary=dict(certified_variants=len(poses),complete_stage_records=sum(map(len,proofs.values())),ignored_orphan_archives=ignored_orphans,
        donors_sha256=fq.digest(target/'donors.npz'),provenance_sha256=fq.digest(target/'provenance.json'),best_bank_sha256=fq.digest(target/'best_bank.npz'),
        best_excess_by_key={key:fq.bloat(q,*map(int,key.split('_')[:2]))for key,q in best.items()})
    atomic_json(target/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=1140)
    parser.add_argument('--workers',type=int,default=4);parser.add_argument('--max-trials',type=int,default=0)
    parser.add_argument('--collect-only',action='store_true');args=parser.parse_args()
    if args.collect_only:
        print(json.dumps(collect(args.out)),flush=True);return
    if not 15<args.seconds<=1140 or not 1<=args.workers<=4:raise ValueError('Authorized remote CPU bounds exceeded')
    config=json.loads((args.package/'campaign_config.json').read_text())
    if fq.digest(args.binary)!=config['binary_sha256']:raise ValueError('Exact ready binary required')
    for name,sha in config['input_hashes'].items():
        if fq.digest(args.package/name)!=sha:raise ValueError('Frozen campaign input changed')
    fq.trial=strict_trial
    productive.campaign.FOCUS=config['weights']
    generated=productive.install()
    if fq.hashlib.sha256(generated.encode()).hexdigest()!=config['generated_runtime_sha256']:
        raise ValueError('Audited generated scheduler changed')
    args.reference=[args.package/'inputs/reference.npz'];args.donors=[args.package/'inputs/donors.npz']
    args.priorities=args.package/'inputs/priorities.json';args.trial_seconds=20.;args.seed=config['seed']
    productive.campaign.campaign(args)
    print(json.dumps(dict(stage='remote_certified_collection',**collect(args.out))),flush=True)


if __name__=='__main__':main()
