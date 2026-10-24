"""Three-worker finite whole-packing coverage over the current certified RAW."""
import time
STARTED=time.monotonic()
import argparse
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import csv
from decimal import Decimal
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_unvisited_contact_diagnostic as prior
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from compose_gadgets import normalize

ROOT=Path(__file__).resolve().parents[1]
PHASES={'contact20':(prior.CONTACT,8.),'contact100':(['--no-alm','--loosen','1','--pit','100','--flip-top','0'],12.),
        'rigid_winner':(prior.RIGID,10.),'rigid_no_lp_gain':(prior.RIGID,10.)}
_STAGE=None


def worker(job):
    global _STAGE
    n,p,canonical,mode,index,binary,out,deadline=job
    if _STAGE is None:
        namespace=dict(prior.full.__dict__);namespace['grouped_run']=prior.persistent_native_run
        source=Path(out)/'source/retaining_run_stage.py'
        exec(compile(source.read_text(),str(source),'exec'),namespace);_STAGE=namespace['run_stage']
    flags,cap=PHASES[mode]
    record,q=_STAGE(p,float(canonical),mode,flags,9470000+index,Path(binary),Path(out)/'trials',cap,deadline)
    record.update(job=index,canonical_raw_side=canonical)
    command=record.get('command',[])
    if '--out'in command:
        path=Path(command[command.index('--out')+1])
        if path.exists():
            record['native_output_sha256']=prior.full.fq.digest(path)
            lines=path.read_text().splitlines();raw=np.array([[float(x)for x in line.split()]for line in lines[1:]],dtype=np.float64)
            if raw.shape==(n,3):
                raw[:,2]=np.radians(raw[:,2]);target=Path(out)/'raw-returned'/f'n{n}-{mode}-{index:04d}.npz'
                atomic_npz(target,{'pose':raw});record['raw_returned']=dict(path=str(target),sha256=prior.full.fq.digest(target),
                    geometry_sha256=geometry_sha(raw),original_decimal_path=str(path),verified=False)
    if q is not None:
        identity=geometry_sha(q);key=f'{n}__broad_{mode}_{identity}';record['archive_key']=key
        target=Path(out)/'retained'/f'{index:04d}-{identity}.npz'
        atomic_npz(target,{key:q});atomic_json(target.with_suffix('.json'),dict(record=record,archive_sha256=prior.full.fq.digest(target)))
        target.chmod(0o444);target.with_suffix('.json').chmod(0o444)
        record['retained_archive']=str(target);record['retained_archive_sha256']=prior.full.fq.digest(target)
    return record,q


def prepare(out):
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pointer=json.loads(pointer_path.read_text());baseline=pointer['raw']
    assert prior.full.fq.digest(baseline['path'])==baseline['sha256']and prior.full.fq.digest(baseline['official_report'])==baseline['official_report_sha256']
    report=json.loads(Path(baseline['official_report']).read_text())
    assert report['valid']and report['puzzles']==1000 and report['sha256']==baseline['sha256']and report['metric_sha256']==prior.full.fq.OFFICIAL_SHA256
    official={r['n']:r for r in report['results']};target={r['n']:r for r in json.loads(prior.TARGET.read_text())}
    ranked=sorted([dict(n=n,canonical_side=r['side'],target_side=target[n]['L'],headroom=(float(r['side'])-float(target[n]['L']))/math.sqrt(n))
        for n,r in official.items()if(float(r['side'])-float(target[n]['L']))/math.sqrt(n)>1e-8],key=lambda r:-r['headroom'])
    rows={r['n']:[]for r in ranked}
    with open(baseline['path'])as stream:
        for row in csv.DictReader(stream):
            n=int(row['n'])
            if n in rows:rows[n].append((int(row['square_id']),[float(row[k])for k in('x','y','angle')]))
    poses={n:np.array([p for _,p in sorted(values)],dtype=np.float64)for n,values in rows.items()}
    assert all(p.shape==(n,3)and np.isfinite(p).all()for n,p in poses.items())
    current={n:normalize(p)for n,p in poses.items()};covered={};rigid_covered=set();exposure=[]
    archives=[('fq-full-contact-v1/inputs/initial-poses.npz',False),('fq-full-contact-v1/complete/donors.npz',False),
        ('fq-full-contact-union-v1/donors.npz',False),('fq-full-pilot-v1/donors.npz',True),
        ('fq-full-basin-v1/donors.npz',True),('fq-full-local-v1/inputs/initial-poses.npz',False),('fq-full-local-v1/donors.npz',True)]
    for relative,had_rigid in archives:
        path=ROOT/'artifacts'/relative
        if not path.exists():continue
        exposure.append(dict(path=str(path),sha256=prior.full.fq.digest(path),rigid_history=had_rigid))
        with np.load(path,allow_pickle=False)as archive:
            for key in archive.files:
                q=archive[key]
                if q.ndim!=2 or q.shape[1]!=3 or len(q)not in current:continue
                n=len(q);q=normalize(q);delta=float(abs(q[:,:2]-current[n][:,:2]).max())
                angle=float(abs((q[:,2]-current[n][:,2]+np.pi/4)%(np.pi/2)-np.pi/4).max())
                if delta<=1e-7 and angle<=1e-10:
                    covered.setdefault(n,[]).append(dict(path=str(path),key=key,geometry_sha256=geometry_sha(q),max_center_difference=delta,max_angle_difference=angle))
                    if had_rigid:rigid_covered.add(n)
    last=json.loads((ROOT/'artifacts/fq-unvisited-contact-v1/exposure-audit.json').read_text())
    just_attempted={r['n']for r in last['selected']};excluded={147,299,335}|just_attempted|set(covered)
    selected=[r for r in ranked if r['n']not in excluded]
    audit=dict(baseline=baseline,pointer_sha256=prior.full.fq.digest(pointer_path),target_path=str(prior.TARGET),target_sha256=prior.full.fq.digest(prior.TARGET),
        material_ranked=ranked,selected=selected,selected_count=len(selected),excluded_recent30=sorted(just_attempted),
        equivalent_historical_coverage=covered,rigid_covered=sorted(rigid_covered),exposure_archives=exposure,
        comparison='Ordered normalized coordinates; exact hashes recorded.<=1e-7 position/1e-10 angle groups precision-clearance equivalents conservatively. Uncertain cases stay eligible.',
        target_scope='Public factual scalar bounds; no attainability or available-coordinate claim.')
    atomic_npz(out/'inputs/current-poses.npz',{str(n):p for n,p in poses.items()});atomic_json(out/'exposure-audit.json',audit)
    return poses,official,audit


def campaign(args):
    out=args.out;out.mkdir(parents=True,exist_ok=False)
    for name in('inputs','source','trials','retained','raw-returned','snapshots'):(out/name).mkdir()
    frozen=json.loads((args.inputs/'freeze.json').read_text())
    for name in('exposure-audit.json','inputs/current-poses.npz'):
        assert prior.full.fq.digest(args.inputs/name)==frozen['files'][name]
    audit=json.loads((args.inputs/'exposure-audit.json').read_text());baseline=audit['baseline']
    assert prior.full.fq.digest(baseline['path'])==baseline['sha256']and prior.full.fq.digest(baseline['official_report'])==baseline['official_report_sha256']
    official={r['n']:r for r in json.loads(Path(baseline['official_report']).read_text())['results']}
    with np.load(args.inputs/'inputs/current-poses.npz',allow_pickle=False)as archive:poses={int(k):archive[k]for k in archive.files}
    shutil.copyfile(args.inputs/'inputs/current-poses.npz',out/'inputs/current-poses.npz')
    shutil.copyfile(args.inputs/'exposure-audit.json',out/'exposure-audit.json')
    shutil.copyfile(args.inputs/'freeze.json',out/'inputs/freeze.json')
    binary=out/'inputs/fq';shutil.copyfile(args.binary,binary);binary.chmod(0o500);assert prior.full.fq.digest(binary)==prior.BINARY_SHA
    sources=[Path(__file__),Path(prior.__file__),Path(prior.full.__file__),ROOT/'experiments/fq_dual_cage_soft.py',ROOT/'experiments/fq_joint_seed_check.py',
        ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_coherent_clusters.py',ROOT/'experiments/fq_variant_campaign.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/validate_submission.py',
        ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/src/fq.rs']
    for path in sources:shutil.copyfile(path,out/'source'/path.name)
    (out/'source/retaining_run_stage.py').write_text(prior.retaining_stage_source())
    manifest=dict(baseline=audit['baseline'],audit_sha256=prior.full.fq.digest(out/'exposure-audit.json'),binary_sha256=prior.BINARY_SHA,
        source_commit=prior.full.fq.SOURCE_COMMIT,source_hashes={str(p):prior.full.fq.digest(p)for p in sources},
        workers=3,maximum_total_seconds=720,phases={key:dict(flags=v[0],inclusive_cap=v[1])for key,v in PHASES.items()},
        selected_cases=[r['n']for r in audit['selected']],rigid_no_lp_gain_limit=20,
        phase_policy='LP20 coverage; interleaved rigid-winner,top20 high-gap no-LP-gain rigid,LP100-winner queues. At most one concurrent job percase.',
        no_canonical_mutation=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest)
    records=[];candidates={};donors={};best={n:p for n,p in poses.items()};snapshot_count=0;job_index=0
    def checkpoint(status,new_gain=False,aggregate=False):
        nonlocal snapshot_count
        atomic_json(out/'results.json',records);atomic_json(out/'candidates.json',candidates)
        if aggregate:atomic_npz(out/'donors.npz',donors)
        summary=dict(status=status,seconds=time.monotonic()-STARTED,trials=len(records),certified_geometries=len(donors),improved_cases=len(candidates),
            cases=sorted(map(int,candidates)),score_gain=sum(x['score_gain']for x in candidates.values()),
            phase_counts={mode:sum(r['mode']==mode for r in records)for mode in PHASES},
            source_hashes_unchanged=all(prior.full.fq.digest(p)==h for p,h in manifest['source_hashes'].items()),
            candidates_sha256=prior.full.fq.digest(out/'candidates.json'),results_sha256=prior.full.fq.digest(out/'results.json'),manifest_sha256=prior.full.fq.digest(out/'manifest.json'))
        atomic_json(out/'summary.json',summary)
        if new_gain:
            snapshot_count+=1;directory=out/'snapshots'/f'gain-{snapshot_count:04d}';directory.mkdir()
            atomic_json(directory/'candidates.json',candidates);atomic_json(directory/'summary.json',summary)
            for path in directory.iterdir():path.chmod(0o444)
            atomic_json(out/'latest-immutable.json',dict(path=str(directory),candidate_sha256=prior.full.fq.digest(directory/'candidates.json'),summary_sha256=prior.full.fq.digest(directory/'summary.json')))
        return summary
    def receive(record,q):
        gain=False;n=record['n']
        if q is not None:
            donors[record['archive_key']]=q;length=record['certificate']['independent_raw']['side_upper'];canonical=official[n]['side']
            if Decimal(length)<Decimal(canonical)-Decimal('1e-8'):
                old=candidates.get(str(n))
                if old is None or Decimal(length)<Decimal(old['side']):
                    best[n]=q;candidates[str(n)]=dict(side=length,squares=[[f'{v:.17g}'for v in row]for row in q],certificate=record['certificate'],
                        source='Bounded broad native whole-packing continuation',provenance=dict(job=record['job'],mode=record['mode'],parent_geometry_sha256=record['parent_geometry_sha256']),
                        score_gain=(float(canonical)-float(length))/math.sqrt(n));gain=True
        records.append(record);summary=checkpoint('running',gain)
        print(json.dumps(dict(n=n,mode=record['mode'],status=record['status'],side=record.get('side'),gain=record.get('side_gain'),
            total_gain=summary['score_gain'],trials=len(records),seconds=time.monotonic()-STARTED)),flush=True)
    def run_queue(pool,jobs):
        nonlocal job_index
        pending={};queue=list(jobs)
        while queue or pending:
            if time.monotonic()>=args.deadline-2:break
            busy={n for n,_ in pending.values()}
            while len(pending)<3 and queue and time.monotonic()<args.deadline-2:
                k=next((i for i,(n,mode)in enumerate(queue)if n not in busy),None)
                if k is None:break
                n,mode=queue.pop(k);job_index+=1
                payload=(n,best[n],official[n]['side'],mode,job_index,str(binary.resolve()),str(out.resolve()),args.deadline)
                future=pool.submit(worker,payload);pending[future]=(n,mode);busy.add(n)
            if not pending:break
            ready,_=wait(pending,timeout=min(1.,max(.01,args.deadline-time.monotonic())),return_when=FIRST_COMPLETED)
            for future in ready:
                pending.pop(future);record,q=future.result();receive(record,q)
        for future in list(pending):
            try:record,q=future.result(timeout=max(.01,args.deadline+2-time.monotonic()));receive(record,q)
            except TimeoutError:future.cancel()
        return not queue
    print(json.dumps(dict(stage='freeze',cases=len(audit['selected']),headroom=sum(r['headroom']for r in audit['selected']),
        raw=audit['baseline']['sha256'],workers=3)),flush=True)
    checkpoint('prepared',aggregate=True)
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('fork'))as pool:
        covered=run_queue(pool,[(row['n'],'contact20')for row in audit['selected']]);checkpoint('coverage_complete'if covered else'coverage_deadline',aggregate=True)
        if covered and time.monotonic()<args.deadline-5:
            winners=sorted(map(int,candidates),key=lambda n:-candidates[str(n)]['score_gain'])
            no_gain=[row['n']for row in audit['material_ranked']if row['n']not in winners and row['n']not in{147,299,335}
                     and row['n']not in audit['rigid_covered']][:20]
            atomic_json(out/'refinement-plan.json',dict(winners=winners,rigid_no_lp_gain=no_gain))
            a=[(n,'rigid_winner')for n in winners];b=[(n,'rigid_no_lp_gain')for n in no_gain];c=[(n,'contact100')for n in winners];jobs=[]
            while a or b or c:
                for queue in(a,b,c):
                    if queue:jobs.append(queue.pop(0))
            run_queue(pool,jobs)
    summary=checkpoint('complete'if time.monotonic()<args.deadline else'deadline_partial',aggregate=True)
    directory=out/'complete';directory.mkdir()
    for name in('candidates.json','donors.npz','results.json','manifest.json','summary.json','exposure-audit.json'):
        shutil.copyfile(out/name,directory/name);(directory/name).chmod(0o444)
    print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq')
    parser.add_argument('--inputs',type=Path,default=ROOT/'artifacts/fq-broad-contact-inputs-v1')
    parser.add_argument('--child',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.child:return campaign(args)
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child','--deadline',str(STARTED+708.)],start_new_session=True)
    forced=False
    try:process.wait(timeout=max(.01,STARTED+717.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=1.)
    receipt=dict(returncode=process.returncode,seconds=time.monotonic()-STARTED,workers=3,maximum_total_seconds=720,hard_deadline_enforced=forced)
    if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.returncode and not forced:raise SystemExit(process.returncode)


if __name__=='__main__':main()
