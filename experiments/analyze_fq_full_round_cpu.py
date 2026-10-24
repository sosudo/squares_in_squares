"""Audit held-full CPU outputs, native return traces and immutable start identities."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from decimal import Decimal
import hashlib
import inspect
import json
from pathlib import Path
import re

import numpy as np
import fq_active_pilot as fq
import fq_full_round_cpu_search as worker
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_multiscale_campaign import diversity_bucket
from analyze_fq_remote_cpu import raw_text_sha


def audit_native_return(r,trial,checked,read):
    options=r['command_options']
    command=r['command']
    if command[-len(options):]!=options or int(command[command.index('--seed')+1])!=r['seed']:
        raise ValueError('Actual native command differs from recorded options/seed')
    inp=checked(trial+'.in');output=checked(trial+'.out')
    stdout=checked(trial+'.native-stdout');stderr=checked(trial+'.native-stderr')
    trace=read(trial+'.radius-trace.json')
    if (fq.digest(inp)!=r['input_sha256']or fq.digest(output)!=r['output_sha256']
        or fq.digest(stdout)!=trace['stdout_sha256']or fq.digest(stderr)!=trace['stderr_sha256']):
        raise ValueError('Native trace/output/input hash differs')
    native=json.loads(stdout.read_text().strip().splitlines()[-1])
    if native!=r['fq']:raise ValueError('Native scalar report differs')
    radii=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',stderr.read_text())]
    radius=float(options[options.index('--round-r0')+1]);count=int(options[options.index('--round-steps')+1])
    expected=[radius*(1-j/count)**2 for j in range(1,count+1)]
    held=float(inp.read_text().splitlines()[0].split()[1]);rounding=native['round']
    if (count!=12 or not trace['valid']or trace['reported_radii']!=radii or len(radii)!=12 or radii[-1]!=0.
        or max(abs(a-b)for a,b in zip(radii,expected))>5.01e-5 or rounding['r0']!=radius
        or max(abs(rounding[k]-held)for k in ('s_soft','s_hold'))>1e-10):
        raise ValueError('Actual-held zero-radius return failed')
    return dict(radius=radius,input_side=held,actual_held_side=rounding['s_hold'],final_radius=radii[-1])


def analyze(remote,job,out):
    remote,job,out=map(Path,(remote,job,out));manifest=json.loads((job/'job_manifest.json').read_text())
    receipt=json.loads((remote/'download_receipt.json').read_text())
    source_sha=fq.digest(job/'search.py')
    if (receipt['source_sha256']!=source_sha or receipt['status']!='COMPLETE' or not receipt['complete']
        or not receipt['is_private']or receipt['enable_gpu']):raise ValueError('Completed exact private CPU source required')
    for name,entry in receipt['files'].items():
        path=remote/name
        if not path.resolve().is_relative_to(remote.resolve())or fq.digest(path)!=entry['sha256']:
            raise ValueError('Downloaded bytes differ from exact receipt')
    consumed=set()
    def checked(name):
        if name not in receipt['files']:raise ValueError('Receipt omits consumed output: '+name)
        consumed.add(name);return remote/name
    def read(name):return json.loads(checked(name).read_text())
    if read('job_manifest.json')!=manifest:raise ValueError('Frozen remote package differs')
    for name,function in [('experiments/fq_active_pilot.py',fq.bloat),
            ('experiments/compose_gadgets.py',fq.decode.__globals__['legalize']),
            ('experiments/fq_variant_campaign.py',geometry_sha),('experiments/fq_multiscale_campaign.py',diversity_bucket),
            ('experiments/fq_full_round_cpu_search.py',worker.select_mode)]:
        if fq.digest(Path(inspect.getsourcefile(function)))!=manifest['files'][name]:
            raise ValueError('Current numerical/scheduling helper differs from frozen worker')
    config=manifest['campaign']
    for name,expected in config['input_hashes'].items():
        p=job/name
        if not p.resolve().is_relative_to(job.resolve())or fq.digest(p)!=expected:raise ValueError('Frozen input differs')
    supervision=read('supervisor.json')
    if supervision['returncode']or supervision['collector_returncode']or supervision['workers']!=4:
        raise ValueError('Normal four-worker completion required for this full audit')
    initial=read('campaign/manifest.json');final=read('campaign/final.json')
    snapshot=Path(final['snapshot']).name
    if not snapshot.startswith('snapshot-')or not snapshot[9:].isdigit():raise ValueError('Invalid snapshot path')
    report=read('campaign/'+snapshot+'/analysis.json')
    if fq.digest(checked('campaign/'+snapshot+'/analysis.json'))!=final['analysis_sha256']:
        raise ValueError('Final analysis hash differs')
    results=read('campaign/'+snapshot+'/results.json')
    if fq.digest(checked('campaign/'+snapshot+'/results.json'))!=report['results_sha256']:
        raise ValueError('Final trial records hash differs')
    policy=initial['restart_policy']
    if (policy['original_current_fraction']!=.25 or policy['immutable_control_fraction']!=.25
        or policy['incumbent_fraction']!=.5 or policy['input_side_cutoff']is not None
        or policy['generated_runtime_sha256']!=config['generated_runtime_sha256']):
        raise ValueError('Wrong source selection policy')
    runtime,generated,_=worker.build_runtime(config)
    if (hashlib.sha256(generated.encode()).hexdigest()!=config['generated_runtime_sha256']
        or initial['mode_options']!=runtime.__globals__['KICK_OPTIONS']
        or initial['mode_slots']!=runtime.__globals__['MODE_SLOTS']
        or initial['priority_weights']!=config['weights']):raise ValueError('Executed numerical policy differs')
    reference={};catalog={};pools=defaultdict(dict)
    for filename in ['reference.npz','donors.npz']:
        with np.load(job/'inputs'/filename,allow_pickle=False)as z:
            for name in z.files:
                p=z[name].copy();sha=geometry_sha(p);catalog[sha]=p;key=name.split('__')[0]
                if filename=='reference.npz':reference[key]=p
                else:pools[key][sha]=dict(pose=p,geometry_sha256=sha,source_archive='donor_0',source_name=name,
                    bucket=sha,excess=fq.bloat(p,*map(int,key.split('_')[:2])))
    for key,p in reference.items():
        if geometry_sha(p)!=initial['reference_geometry_sha256_by_key'][key]:raise ValueError('Actual original input differs')
    frozen=worker.freeze_start_sources(reference,pools,config['alternative_geometry_hashes'])
    initial_buckets={diversity_bucket(p)for p in catalog.values()}
    prefix='campaign/remote-certified/';summary=read(prefix+'summary.json');proofs=read(prefix+'provenance.json')
    for name,label in [('donors.npz','donors_sha256'),('provenance.json','provenance_sha256'),('best_bank.npz','best_bank_sha256')]:
        if fq.digest(checked(prefix+name))!=summary[label]:raise ValueError('Aggregate hash differs')
    poses={};best={};official_best={};stages={};outside=0;trace_rows=[]
    with np.load(checked(prefix+'donors.npz'),allow_pickle=False)as z:
        if set(z.files)!=set(proofs):raise ValueError('Pose/proof inventory differs')
        for name in z.files:
            p=z[name].copy();key=name.split('__')[0];w,h,d=map(int,key.split('_'));sha=geometry_sha(p)
            if p.shape!=(w*h+d,3)or not np.isfinite(p).all()or name!=key+'__strict_'+sha:
                raise ValueError('Exact pose identity differs')
            value=fq.bloat(p,w,h);text=raw_text_sha(p)
            if not proofs[name]:raise ValueError('Missing retained-stage proof')
            for entry in proofs[name]:
                r=entry['record'];c=r['certificate'];g=c['shared_official_gate']
                if (r['key']!=key or r['geometry_sha256']!=sha or abs(r['after']-value)>1e-12
                    or r['binary_sha256']!=manifest['binary_sha256']or c['raw_csv_sha256']!=text
                    or not c['valid']or not g['valid']or g['metric_sha256']!=fq.OFFICIAL_SHA256
                    or g['raw_reason']!='ok'or g['roundtrip_reason']!='ok'or c['ordinary_pandas_official_reason']!='ok'
                    or any(not c[part]['valid']or c[part]['n']!=len(p)for part in ('independent_raw','independent_roundtrip'))):
                    raise ValueError('Exact geometry/decimal/full-certificate binding failed')
                stem=f"{key}-{r['mode']}-{r['seed']}";stage='campaign/strict-stages/'+stem
                if fq.digest(checked(stage+'.json'))!=entry['proof_sha256']or read(stage+'.json')!=r:
                    raise ValueError('Immutable stage proof differs')
                if fq.digest(checked(stage+'.npz'))!=r['stage_archive_sha256']:raise ValueError('Immutable pose archive differs')
                options=r['command_options'];options_expected=initial['mode_options'][r['mode']]
                if options!=options_expected or '--round-compress'in options or options[options.index('--hold-f')+1]!='1':
                    raise ValueError('Unexpected rounded continuation options')
                trace_result=audit_native_return(r,'campaign/trials/'+stem,checked,read)
                decoded=fq.decode(checked('campaign/trials/'+stem+'.out'),len(p))
                if decoded is None or geometry_sha(decoded)!=sha:
                    raise ValueError('Native decoded geometry differs from its certified archive')
                identity=(key,r['mode'],r['seed'])
                if identity in stages:raise ValueError('Repeated immutable trial identity')
                stages[identity]=r;outside+=not r['eligible_for_search']
                if key not in official_best or Decimal(g['raw_side'])<Decimal(official_best[key]['raw_side']):
                    official_best[key]=dict(raw_side=g['raw_side'],ordinary_pandas_side=c['ordinary_pandas_official_side'],
                        geometry_sha256=sha,archive_key=name)
                trace_rows.append(dict(key=key,seed=r['seed'],mode=r['mode'],geometry_sha256=sha,**trace_result))
            poses[name]=p;catalog[sha]=p
            if key not in best or value<best[key]['excess']:best[key]=dict(excess=value,geometry_sha256=sha,archive_key=name)
    visits=Counter();roles=defaultdict(Counter);source_modes=defaultdict(set);bound=0
    keys=sorted(reference,key=lambda key:(-config['weights'][key],key));offsets={key:i for i,key in enumerate(keys)}
    for index,record in enumerate(sorted(results,key=lambda r:r['trial_id'])):
        parent=record['parent'];key=parent['key'];visit=visits[key]
        if record['trial_id']!=index+1 or record['seed']!=config['seed']+index:
            raise ValueError('Trial/seed sequence differs')
        scheduled=min(keys,key=lambda k:(visits[k]/config['weights'][k],-config['weights'][k],k))
        if key!=scheduled:raise ValueError('Weighted case schedule differs')
        expected_mode=worker.select_mode(key,visit,offsets[key],frozen,list(initial['mode_options']))
        if record['mode']!=expected_mode:raise ValueError('Per-source mode schedule differs')
        source=parent['geometry_sha256']
        if source not in catalog:raise ValueError('Native start lacks an exact input or certified parent')
        p=catalog[source]
        w,h,d=map(int,key.split('_'))
        if p.shape!=(w*h+d,3)or record['key']!=key or parent['mode']!=record['mode']or parent['seed']!=record['seed']:
            raise ValueError('Parent case/mode/seed identity differs')
        if visit%4 in (1,3):
            q,expected=worker.choose_start(key,visit,reference,frozen)
            if source!=geometry_sha(q)or parent['selection']!=expected['selection']:
                raise ValueError('Immutable original/control selection differs')
        elif parent['selection']!='incumbent':raise ValueError('Unexpected incumbent phase')
        stem=f"{key}-{record['mode']}-{record['seed']}";name='campaign/trials/'+stem+'.in'
        if 'input_sha256'in record:
            if record['parent_geometry_sha256']!=source:raise ValueError('Worker received another parent geometry')
            encoded,_=fq.encode(p,*map(int,key.split('_')[:2]));data=checked(name).read_bytes()
            if data!=encoded.encode()or hashlib.sha256(data).hexdigest()!=record['input_sha256']:
                raise ValueError('Selected parent and actual native input differ')
            bound+=1
        identity=(key,record['mode'],record['seed'])
        if record['status']in ('certified','certified_outside_search_band'):
            if identity not in stages or stages[identity]['geometry_sha256']!=record['geometry_sha256']:
                raise ValueError('Completed certified trial missing from immutable retention')
        roles[key][parent['selection']]+=1;source_modes[(key,parent['selection'],source)].add(record['mode']);visits[key]+=1
    if len(stages)!=summary['complete_stage_records']or len(poses)!=summary['certified_variants']:
        raise ValueError('Retained stage/pose count differs')
    if len(results)!=report['trials_completed']or dict(visits)!=report['visits']:raise ValueError('Final trial count differs')
    reference_values={key:fq.bloat(p,*map(int,key.split('_')[:2]))for key,p in reference.items()}
    wins={key:dict(row,reference_excess=reference_values[key],gain=reference_values[key]-row['excess'])
          for key,row in best.items()if reference_values[key]-row['excess']>5e-9}
    pointer_path=Path(__file__).resolve().parents[1]/'artifacts/current-best-portfolio.json'
    pointer_bytes=pointer_path.read_bytes();pointer=json.loads(pointer_bytes);current=pointer['raw']
    current_report_path=Path(current['official_report']);current_report=json.loads(current_report_path.read_text())
    if (fq.digest(current_report_path)!=current['official_report_sha256']or not current_report['valid']
        or current_report['sha256']!=current['sha256']or current_report['metric_sha256']!=fq.OFFICIAL_SHA256
        or fq.digest(Path(current['path']))!=current['sha256']):raise ValueError('Current official incumbent proof differs')
    current_sides={int(row['n']):row['side']for row in current_report['results']if row['reason']=='ok'}
    current_comparison={}
    for key,row in official_best.items():
        w,h,d=map(int,key.split('_'));n=w*h+d
        gain=Decimal(current_sides[n])-Decimal(row['raw_side'])
        current_comparison[key]=dict(n=n,current_raw_side=current_sides[n],emitted_raw_side=row['raw_side'],
            physical_side_gain=str(gain),strict_raw_side_improvement=gain>0,
            geometry_sha256=row['geometry_sha256'],archive_key=row['archive_key'])
    near={};buckets=defaultdict(set)
    for name,p in poses.items():
        key=name.split('__')[0]
        if fq.bloat(p,*map(int,key.split('_')[:2]))<=reference_values[key]+.005:
            near[name]=p;buckets[key].add(diversity_bucket(p))
    out.mkdir(parents=True,exist_ok=False)
    atomic_npz(out/'best_bank.npz',{key:poses[row['archive_key']]for key,row in best.items()})
    atomic_npz(out/'near_reference_donors.npz',near)
    atomic_json(out/'native_return_audit.json',trace_rows)
    result=dict(status='exact_bindings_and_native_return_verified',source_sha256=source_sha,
        analyzer_sha256=fq.digest(Path(__file__)),raw_text_helper_sha256=fq.digest(Path(inspect.getsourcefile(raw_text_sha))),
        aggregate_sha256=summary['donors_sha256'],provenance_sha256=summary['provenance_sha256'],
        downloaded_receipt_sha256=fq.digest(remote/'download_receipt.json'),consumed_files=len(consumed),
        trials=len(results),visits=dict(visits),roles={k:dict(v)for k,v in roles.items()},native_parent_bindings=bound,
        certified_poses=len(poses),certified_stages=len(stages),outside_search_band_stages=outside,
        near_reference_poses=len(near),near_reference_sha256=fq.digest(out/'near_reference_donors.npz'),
        near_reference_buckets_by_key={key:len(v)for key,v in buckets.items()},
        new_near_reference_buckets_by_key={key:len(v-initial_buckets)for key,v in buckets.items()},
        diversity_note='Rounded coordinate/angle buckets measure pose diversity, not a proof of distinct unlabeled contact topology; all exact certified poses remain retained.',
        source_mode_coverage=[dict(key=k,role=role,geometry_sha256=sha,modes=sorted(modes))
            for (k,role,sha),modes in sorted(source_modes.items())],
        best_by_key=best,reference_excess=reference_values,strict_case_improvements=wins,
        official_physical_side_minima=official_best,current_official_comparison=current_comparison,
        current_incumbent_proof=dict(pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(),raw=current),
        comparison_note='Gains compare to exact legalized frozen control inputs; any competition-score claim requires comparison and full merge against the current official CSV.',
        statuses=dict(Counter(r['status']for r in results)),supervisor=supervision,
        best_bank_sha256=fq.digest(out/'best_bank.npz'),full_geometry_certifications_repeated=0)
    atomic_json(out/'analysis.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('remote','job','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(analyze(args.remote,args.job,args.out),indent=2))
