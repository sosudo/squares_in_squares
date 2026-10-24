"""Verify both CPU lanes' retained exact certificate bindings, without recertifying."""
from __future__ import annotations
import argparse
from collections import Counter
import inspect
import json
from pathlib import Path

import numpy as np
import fq_active_pilot as fq
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_multiscale_campaign import diversity_bucket
from analyze_fq_remote_cpu import raw_text_sha


def snapshot_directory(root):
    pointer=json.loads((root/'final.json').read_text())
    name=Path(pointer['snapshot']).name
    if not name.startswith('snapshot-')or not name[9:].isdigit():
        raise ValueError('Unexpected frozen checkpoint path')
    return root/name,pointer


def audit_lane(root,job,lane):
    root=Path(root);job=Path(job)
    config=json.loads((job/'job_manifest.json').read_text())
    for relative,function in [('experiments/fq_active_pilot.py',fq.bloat),
            ('experiments/fq_variant_campaign.py',geometry_sha),
            ('experiments/fq_multiscale_campaign.py',diversity_bucket)]:
        if fq.digest(Path(inspect.getsourcefile(function)))!=config['files'][relative]:
            raise ValueError('Current analysis geometry helper differs from the frozen worker')
    policy=config['lanes'][lane];expected_steps=16 if lane=='productive' else 12
    expected_amplitude=.6 if lane=='productive' else .3
    for name,expected in policy['input_hashes'].items():
        path=job/name
        if not path.resolve().is_relative_to(job.resolve())or fq.digest(path)!=expected:
            raise ValueError('Frozen lane input bytes changed')
    aggregate=root/'remote-certified';summary=json.loads((aggregate/'summary.json').read_text())
    for filename,label in [('donors.npz','donors_sha256'),('provenance.json','provenance_sha256'),('best_bank.npz','best_bank_sha256')]:
        if fq.digest(aggregate/filename)!=summary[label]:raise ValueError('Changed aggregate bytes')
    proofs=json.loads((aggregate/'provenance.json').read_text())
    manifest=json.loads((root/'manifest.json').read_text())
    snapshot,pointer=snapshot_directory(root)
    if fq.digest(snapshot/'analysis.json')!=pointer['analysis_sha256']:raise ValueError('Changed final analysis')
    analysis=json.loads((snapshot/'analysis.json').read_text())
    if fq.digest(snapshot/'results.json')!=analysis['results_sha256']:raise ValueError('Changed final trial records')
    results=json.loads((snapshot/'results.json').read_text())
    if manifest['binary_sha256']!=config['binary_sha256'] or manifest['restart_policy']['immutable_input_fraction']!=.25:
        raise ValueError('Wrong native source or immutable-start policy')
    poses={};catalog={};reference={};input_buckets=set()
    with np.load(job/'inputs/reference.npz',allow_pickle=False)as z:
        for key in z.files:
            p=z[key];w,h,_=map(int,key.split('_'));reference[key]=fq.bloat(p,w,h)
            if geometry_sha(p)!=manifest['reference_geometry_sha256_by_key'][key]:raise ValueError('Actual initial minimum changed')
    with np.load(job/'inputs/donors.npz',allow_pickle=False)as z:
        for name in z.files:
            catalog[geometry_sha(z[name])]=z[name];input_buckets.add(diversity_bucket(z[name]))
    stages=outside=0;stage_by_trial={};best={};near={};near_buckets=set();new_buckets=set()
    with np.load(aggregate/'donors.npz',allow_pickle=False)as z:
        if set(z.files)!=set(proofs):raise ValueError('Pose/proof inventory mismatch')
        for name in z.files:
            p=z[name];key=name.split('__')[0];w,h,d=map(int,key.split('_'))
            if p.shape!=(w*h+d,3)or not np.isfinite(p).all():raise ValueError('Invalid pose dimensions')
            sha=geometry_sha(p);text=raw_text_sha(p);value=fq.bloat(p,w,h)
            if name!=key+'__strict_'+sha:raise ValueError('Aggregate name differs from its exact geometry identity')
            if not proofs[name]:raise ValueError('Missing full stage proof')
            for item in proofs[name]:
                r=item['record'];c=r['certificate'];g=c['shared_official_gate']
                if (r['key']!=key or r['geometry_sha256']!=sha or c['raw_csv_sha256']!=text
                    or abs(r['after']-value)>1e-12 or r['binary_sha256']!=config['binary_sha256']
                    or g['metric_sha256']!=fq.OFFICIAL_SHA256 or not c['valid']or not g['valid']
                    or g['raw_reason']!='ok' or g['roundtrip_reason']!='ok'
                    or c['ordinary_pandas_official_reason']!='ok'
                    or not c['independent_raw']['valid']or not c['independent_roundtrip']['valid']
                    or c['independent_raw']['n']!=len(p)or c['independent_roundtrip']['n']!=len(p)):
                    raise ValueError('Exact stage/full-certificate binding failed')
                options=r['command_options']
                if '--soft-a0'in options:
                    trace=r['rigid_return_trace'];eps=trace['reported_aspect_epsilons']
                    if (not trace['valid']or len(eps)!=expected_steps or eps[-1]!=0.
                            or int(options[options.index('--soft-steps')+1])!=expected_steps
                            or float(options[options.index('--soft-a0')+1])!=expected_amplitude
                            or not all(a>=b>=0 for a,b in zip(eps,eps[1:]))):
                        raise ValueError('Soft stage lacks configured exact-zero aspect return')
                    stage_by_trial[(key,r['mode'],r['seed'])]=r
                elif options!=policy['release']:raise ValueError('Unexpected rigid release policy')
                stages+=1;outside+=not r['eligible_for_search']
            poses[name]=p.copy();catalog[sha]=p.copy()
            if key not in best or value<best[key]['excess']:best[key]=dict(excess=value,archive_key=name,geometry_sha256=sha)
            if value<=reference[key]+.005 and value<1:
                near[name]=p.copy();bucket=diversity_bucket(p);near_buckets.add(bucket)
                if bucket not in input_buckets:new_buckets.add(bucket)
    checked_parents=0
    for record in results:
        parent=record['parent'];key=record['key'];sha=parent['geometry_sha256']
        if sha not in catalog:raise ValueError('Trial parent is not an exact initial or retained pose')
        stage=stage_by_trial.get((key,record['mode'],record['seed']))
        if stage:
            encoded,_=fq.encode(catalog[sha],*map(int,key.split('_')[:2]))
            if stage['parent_geometry_sha256']!=sha or fq.hashlib.sha256(encoded.encode()).hexdigest()!=stage['input_sha256']:
                raise ValueError('Initial native input differs from selected parent')
            checked_parents+=1
    if len(poses)!=summary['certified_variants']or stages!=summary['complete_stage_records']:
        raise ValueError('Complete aggregate counts differ')
    report=dict(lane=lane,policy=policy['policy'],trials=len(results),status_counts=dict(Counter(r['status']for r in results)),
        immutable_starts=sum(r['parent']['selection']=='immutable_input'for r in results),
        native_initial_parent_bindings_verified=checked_parents,certified_variants=len(poses),strict_stage_records=stages,
        outside_band_stages=outside,near_reference_variants=len(near),near_reference_buckets=len(near_buckets),
        new_near_reference_buckets=len(new_buckets),best_by_key=best,initial_reference=reference,
        aggregate_sha256=summary['donors_sha256'],provenance_sha256=summary['provenance_sha256'],
        elapsed_seconds=analysis['elapsed_seconds'],geometry_recertification_performed=False)
    return report,poses,near,proofs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote',type=Path,required=True);parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    receipt=json.loads((args.remote/'download_receipt.json').read_text())
    if (receipt['source_sha256']!=fq.digest(args.job/'search.py')or receipt['status']!='COMPLETE'
            or not receipt['is_private']or receipt['enable_gpu']or not receipt['complete']):
        raise ValueError('Completed exact private CPU download proof required')
    for name,record in receipt['files'].items():
        path=args.remote/name
        if not path.resolve().is_relative_to(args.remote.resolve())or fq.digest(path)!=record['sha256']:
            raise ValueError('Downloaded bytes changed or escaped the receipt root')
    required={'job_manifest.json'}
    for lane in ['productive','large']:
        prefix='campaign_'+lane+'/'
        required.update(prefix+name for name in ['manifest.json','final.json','remote-certified/summary.json',
            'remote-certified/donors.npz','remote-certified/provenance.json','remote-certified/best_bank.npz'])
        snapshot,_=snapshot_directory(args.remote/('campaign_'+lane))
        required.update(prefix+snapshot.name+'/'+name for name in ['analysis.json','results.json'])
    if not required<=set(receipt['files']):raise ValueError('Receipt omits consumed remote evidence')
    if json.loads((args.remote/'job_manifest.json').read_text())!=json.loads((args.job/'job_manifest.json').read_text()):
        raise ValueError('Remote frozen job manifest differs')
    args.out.mkdir(parents=True,exist_ok=False)
    reports={};poses={};near={};provenance={}
    for lane in ['productive','large']:
        report,all_poses,useful,proofs=audit_lane(args.remote/('campaign_'+lane),args.job,lane)
        reports[lane]=report;poses.update(all_poses);near.update(useful)
        for name,records in proofs.items():
            provenance.setdefault(name,[]).extend(dict(lane=lane,**item)for item in records)
    atomic_npz(args.out/'donors.npz',poses);atomic_npz(args.out/'near_reference_donors.npz',near)
    atomic_json(args.out/'provenance.json',provenance)
    minima={}
    for name,p in poses.items():
        key=name.split('__')[0];w,h,d=map(int,key.split('_'));family=f'{min(w,h)}_{max(w,h)}_{d}';value=fq.bloat(p,w,h)
        if family not in minima or value<minima[family]['excess']:
            minima[family]=dict(archive_key=name,geometry_sha256=geometry_sha(p),excess=value,
                gain=reports['productive']['initial_reference'][key]-value)
    report=dict(status='all_exact_bindings_verified',lanes=reports,best_by_family=minima,
        complete_unique_poses=len(poses),near_reference_poses=len(near),
        donors_sha256=fq.digest(args.out/'donors.npz'),near_reference_sha256=fq.digest(args.out/'near_reference_donors.npz'),
        provenance_sha256=fq.digest(args.out/'provenance.json'),source_sha256=fq.digest(args.job/'search.py'),
        full_competition_score_claim=False,geometry_recertification_performed=False)
    atomic_json(args.out/'analysis.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
