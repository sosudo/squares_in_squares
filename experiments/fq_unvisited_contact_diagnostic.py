"""One bounded CPU diagnostic of previously unvisited current whole packings."""
import time
STARTED=time.monotonic()
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
for key in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import fq_full_local_campaign as full
from fq_dual_cage_soft import retaining_stage_source
from fq_joint_seed_check import persistent_native_run,BINARY_SHA
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from compose_gadgets import normalize

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'artifacts/public-freshness/notebooks-20261024T092136Z/public-per-puzzle-reference.json'
CONTACT=['--no-alm','--loosen','1','--pit','20','--flip-top','0']
RIGID=['--loosen','1','--outer','45','--pit','20','--flip-top','0']


def prepare(out):
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pointer=json.loads(pointer_path.read_text());raw=pointer['raw']
    source=Path(raw['path']);report_path=Path(raw['official_report'])
    assert full.fq.digest(source)==raw['sha256']and full.fq.digest(report_path)==raw['official_report_sha256']
    report=json.loads(report_path.read_text());assert report['valid']and report['puzzles']==1000 and report['sha256']==raw['sha256']and report['metric_sha256']==full.fq.OFFICIAL_SHA256
    official={r['n']:r for r in report['results']};target={r['n']:r for r in json.loads(TARGET.read_text())}
    excluded={147,299,335};exposure=[]
    for folder in('fq-full-contact-v1','fq-full-pilot-v1','fq-full-basin-v1','fq-full-local-v1'):
        path=ROOT/'artifacts'/folder/'manifest.json';record=json.loads(path.read_text());ids=set()
        ids.update(record.get('cases',[]));ids.update(r['n']for r in record.get('selection',[]))
        ids.update(map(int,record.get('selected',{})));ids.update(map(int,record.get('initial_geometry',{})))
        excluded.update(ids);exposure.append(dict(path=str(path),sha256=full.fq.digest(path),excluded_case_ids=sorted(ids)))
    fresh_path=ROOT/'artifacts/public-v29/incremental-donors/new-donors.npz'
    assert full.fq.digest(fresh_path)=='9114946850852b098e75ff1f41bd9f0aed8bc599b16b3918e2b3480cf0b467fe'
    with np.load(fresh_path,allow_pickle=False)as z:fresh={int(re.search(r'_n(\d+)$',key).group(1))for key in z.files}
    ranking=[]
    for n,row in official.items():
        gap=(float(row['side'])-float(target[n]['L']))/math.sqrt(n)
        if gap>1e-8:ranking.append(dict(n=n,canonical_side=row['side'],target_side=target[n]['L'],score_headroom=gap,
            side_headroom=float(row['side'])-float(target[n]['L']),fresh_public29=n in fresh,excluded_by_prior_case_list=n in excluded))
    ranking.sort(key=lambda r:-r['score_headroom'])
    selected=[r for r in ranking if r['n']in fresh and r['n']not in excluded]
    selected += [r for r in ranking if r['n']not in excluded and r['n']not in{q['n']for q in selected}][:30-len(selected)]
    selected.sort(key=lambda r:-r['score_headroom']);wanted={r['n']for r in selected};rows={n:[]for n in wanted};csv_hash={n:hashlib.sha256()for n in wanted}
    with source.open()as stream:
        for row in csv.DictReader(stream):
            n=int(row['n'])
            if n in wanted:
                rows[n].append((int(row['square_id']),[float(row[k])for k in('x','y','angle')]))
                csv_hash[n].update(json.dumps(row,sort_keys=True,separators=(',',':')).encode()+b'\n')
    poses={n:np.array([p for _,p in sorted(rows[n])],dtype=np.float64)for n in wanted}
    assert all(p.shape==(n,3)and np.isfinite(p).all()for n,p in poses.items())
    for row in selected:
        p=poses[row['n']];row.update(raw_current_geometry_sha256=geometry_sha(p),normalized_geometry_sha256=geometry_sha(normalize(p)),
            exact_source_case_rows_sha256=csv_hash[row['n']].hexdigest())
    # Interleave the newly imported geometries with the untouched high-gap cases.
    fresh_order=[r['n']for r in selected if r['fresh_public29']];other=[r['n']for r in selected if not r['fresh_public29']];order=[]
    while fresh_order or other:
        if fresh_order:order.append(fresh_order.pop(0))
        if other:order.append(other.pop(0))
    audit=dict(source_raw=raw,source_pointer_sha256=full.fq.digest(pointer_path),target_path=str(TARGET),target_sha256=full.fq.digest(TARGET),
        exposure_manifests=exposure,selected=selected,execution_order=order,fresh_public29_count=sum(r['fresh_public29']for r in selected),
        total_factual_score_headroom=sum(r['score_headroom']for r in selected),
        exposure_scope='Conservative explicit complete-case campaign lists; no exhaustive historical replay. N+1 structural starts are different geometries, so412/454 remain eligible.',
        target_scope='Released factual scalar target table; no coordinate availability or attainability claim.',
        pose_scope='Exact float64 parsing of current RAW decimal rows, with source CSV/row hashes; not a new certificate for the NPZ.')
    atomic_npz(out/'inputs/current-poses.npz',{str(n):p for n,p in poses.items()});atomic_json(out/'exposure-audit.json',audit)
    return poses,official,audit


def campaign(args):
    signal.signal(signal.SIGTERM,full.alarm);out=args.out;out.mkdir(parents=True,exist_ok=False)
    for name in('inputs','source','trials','retained','raw-returned'):(out/name).mkdir()
    poses,official,audit=prepare(out)
    binary=out/'inputs/fq';shutil.copyfile(args.binary,binary);binary.chmod(0o500);assert full.fq.digest(binary)==BINARY_SHA
    source_paths=[Path(__file__),Path(full.__file__),ROOT/'experiments/fq_dual_cage_soft.py',ROOT/'experiments/fq_joint_seed_check.py',
        ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_coherent_clusters.py',ROOT/'experiments/fq_variant_campaign.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/validate_submission.py',
        ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/src/fq.rs']
    for path in source_paths:shutil.copyfile(path,out/'source'/path.name)
    stage_path=out/'source/retaining_run_stage.py';stage_path.write_text(retaining_stage_source())
    namespace=dict(full.__dict__);namespace['grouped_run']=persistent_native_run
    exec(compile(stage_path.read_text(),str(stage_path),'exec'),namespace);stage=namespace['run_stage']
    manifest=dict(baseline=audit['source_raw'],audit_sha256=full.fq.digest(out/'exposure-audit.json'),binary_sha256=BINARY_SHA,
        source_commit=full.fq.SOURCE_COMMIT,source_hashes={str(p):full.fq.digest(p)for p in source_paths},
        native_options={'contact20':CONTACT,'rigid_after_gain':RIGID},trial_inclusive_cap_seconds=8.,workers=1,maximum_total_seconds=180,
        rigid_policy='Only after a fully certified material contact20 gain; contact pass finishes before optional rigid followups.',
        no_submission=True,no_canonical_mutation=True)
    atomic_json(out/'manifest.json',manifest);records=[];donors={};candidates={};queue=[]
    def checkpoint(status):
        atomic_json(out/'results.json',records);atomic_npz(out/'donors.npz',donors);atomic_json(out/'candidates.json',candidates)
        summary=dict(status=status,seconds=time.monotonic()-STARTED,trials=len(records),certified_geometries=len(donors),
            improved_cases=len(candidates),cases=sorted(map(int,candidates)),score_gain=sum(float(r['score_gain'])for r in candidates.values()),
            source_hashes_unchanged=all(full.fq.digest(p)==h for p,h in manifest['source_hashes'].items()),
            donors_sha256=full.fq.digest(out/'donors.npz'),candidates_sha256=full.fq.digest(out/'candidates.json'),
            results_sha256=full.fq.digest(out/'results.json'),manifest_sha256=full.fq.digest(out/'manifest.json'))
        atomic_json(out/'summary.json',summary);return summary
    print(json.dumps(dict(stage='selected',cases=audit['execution_order'],fresh=audit['fresh_public29_count'],headroom=audit['total_factual_score_headroom'])),flush=True)
    jobs=[(n,'contact20',poses[n],CONTACT)for n in audit['execution_order']]
    cursor=0
    while cursor<len(jobs)and time.monotonic()<args.deadline-2:
        n,mode,p,options=jobs[cursor];cursor+=1;canonical=official[n]['side']
        record,q=stage(p.copy(),float(canonical),mode,options,9350000+len(records),binary.resolve(),(out/'trials').resolve(),8.,args.deadline)
        record.update(canonical_raw_side=canonical,current_raw_geometry_sha256=geometry_sha(poses[n]),fresh_public29=n in{r['n']for r in audit['selected']if r['fresh_public29']})
        command=record.get('command',[])
        if '--out'in command:
            native_path=Path(command[command.index('--out')+1])
            if native_path.exists():
                # Preserve native decimal bytes even if gate/clearance timed out.
                record['native_output_sha256']=full.fq.digest(native_path)
                lines=native_path.read_text().splitlines();raw=np.array([[float(x)for x in line.split()]for line in lines[1:]],dtype=np.float64)
                if raw.shape==(n,3):
                    raw[:,2]=np.radians(raw[:,2]);path=out/'raw-returned'/f'n{n}-{mode}-{len(records):03d}.npz'
                    atomic_npz(path,{'pose':raw});record['raw_returned']=dict(path=str(path),archive_sha256=full.fq.digest(path),geometry_sha256=geometry_sha(raw),verified=False,original_decimal_file=str(native_path))
        if q is not None:
            identity=geometry_sha(q);key=f'{n}__unvisited_{mode}_{identity}';donors[key]=q
            record['archive_key']=key;path=out/'retained'/(identity+'.npz')
            if not path.exists():
                atomic_npz(path,{key:q});atomic_json(path.with_suffix('.json'),dict(record=record,archive_sha256=full.fq.digest(path)))
                path.chmod(0o444);path.with_suffix('.json').chmod(0o444)
            length=record['certificate']['independent_raw']['side_upper']
            if Decimal(length)<Decimal(canonical)-Decimal('1e-8'):
                old=candidates.get(str(n))
                if old is None or Decimal(length)<Decimal(old['side']):
                    candidates[str(n)]=dict(side=length,squares=[[f'{v:.17g}'for v in row]for row in q],certificate=record['certificate'],
                        source='Bounded current-geometry whole-puzzle contact diagnostic',provenance=dict(trial=len(records),mode=mode,parent_geometry_sha256=record['parent_geometry_sha256']),
                        score_gain=(float(canonical)-float(length))/math.sqrt(n))
                if mode=='contact20':queue.append((n,'rigid_after_gain',q,RIGID))
        records.append(record);checkpoint('running')
        print(json.dumps(dict(n=n,mode=mode,status=record['status'],side=record.get('side'),gain=record.get('side_gain'),seconds=record.get('elapsed_seconds'))),flush=True)
        if cursor==len(jobs)and queue:
            jobs.extend(queue);queue=[]
    print(json.dumps(checkpoint('complete'if cursor==len(jobs)else'deadline_partial')),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq')
    parser.add_argument('--child',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.child:return campaign(args)
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child','--deadline',str(STARTED+173.)],start_new_session=True)
    forced=False
    try:process.wait(timeout=max(.01,STARTED+177.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=1.)
    receipt=dict(returncode=process.returncode,seconds=time.monotonic()-STARTED,workers=1,maximum_total_seconds=180,hard_deadline_enforced=forced)
    if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.returncode and not forced:raise SystemExit(process.returncode)


if __name__=='__main__':main()
