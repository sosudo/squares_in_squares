"""Check exact remote certified-array bindings without repeating geometry work."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import fq_active_pilot as fq
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from fq_multiscale_campaign import diversity_bucket


def raw_text_sha(p):
    stream=io.StringIO();writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(['n','square_id','x','y','angle'])
    for i,(x,y,a)in enumerate(p):writer.writerow([str(len(p)),str(i),f'{x:.17g}',f'{y:.17g}',f'{a:.17g}'])
    return hashlib.sha256(stream.getvalue().encode()).hexdigest()


def analyze(remote,job,out,comparisons=()):
    remote=Path(remote);job=Path(job);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((job/'job_manifest.json').read_text());source_sha=fq.digest(job/'search.py')
    receipt=json.loads((remote/'download_receipt.json').read_text())
    if receipt['source_sha256']!=source_sha or receipt['status']!='COMPLETE' or not receipt['is_private']:
        raise ValueError('Exact completed private source proof required')
    if json.loads((remote/'job_manifest.json').read_text())!=manifest:
        raise ValueError('Remote package manifest differs from the frozen job')
    for name,proof in receipt['files'].items():
        if fq.digest(remote/name)!=proof['sha256']:raise ValueError('Downloaded file changed')
    folder=remote/'campaign/remote-certified';summary=json.loads((folder/'summary.json').read_text())
    for name,label in [('donors.npz','donors_sha256'),('provenance.json','provenance_sha256'),('best_bank.npz','best_bank_sha256')]:
        if fq.digest(folder/name)!=summary[label]:raise ValueError('Certified aggregate/index mismatch')
    reference={};comparison_proof=[]
    for path in [job/'inputs/reference.npz',*map(Path,comparisons)]:
        comparison_proof.append(dict(path=str(path),sha256=fq.digest(path)))
        with np.load(path,allow_pickle=False)as z:
            for name in z.files:
                w,h,d=map(int,name.split('__')[0].split('_'));family=f'{min(w,h)}_{max(w,h)}_{d}'
                p=z[name]
                if p.shape!=(w*h+d,3)or not np.isfinite(p).all():raise ValueError('Invalid comparison pose')
                reference[family]=min(reference.get(family,float('inf')),fq.bloat(p,w,h))
    initial_buckets={}
    with np.load(job/'inputs/donors.npz',allow_pickle=False)as z:
        for name in z.files:initial_buckets.setdefault(name.split('__')[0],set()).add(diversity_bucket(z[name]))
    provenance=json.loads((folder/'provenance.json').read_text());poses={};near={};best={};records=0;outside=0
    near_buckets={};new_buckets={}
    with np.load(folder/'donors.npz',allow_pickle=False)as z:
        if set(z.files)!=set(provenance):raise ValueError('Provenance/geometry key inventory differs')
        for name in z.files:
            p=z[name];key=name.split('__')[0];w,h,d=map(int,key.split('_'));family=f'{min(w,h)}_{max(w,h)}_{d}'
            if p.shape!=(w*h+d,3)or not np.isfinite(p).all():raise ValueError('Invalid certified pose')
            sha=geometry_sha(p);value=fq.bloat(p,w,h);text_sha=raw_text_sha(p)
            if not provenance[name]:raise ValueError('Pose lacks a complete stage proof')
            for item in provenance[name]:
                record=item['record'];certificate=record['certificate'];official=certificate['shared_official_gate']
                if (record['key']!=key or record['geometry_sha256']!=sha or abs(record['after']-value)>1e-12
                    or record['binary_sha256']!=manifest['binary_sha256']or not certificate['valid']
                    or certificate['raw_csv_sha256']!=text_sha or official['metric_sha256']!=fq.OFFICIAL_SHA256
                    or official['raw_reason']!='ok'or official['roundtrip_reason']!='ok'
                    or certificate['ordinary_pandas_official_reason']!='ok'
                    or not certificate['independent_raw']['valid']or not certificate['independent_roundtrip']['valid']):
                    raise ValueError('Stage array/full-gate binding failed')
                if '--soft-a0'in record['command_options']:
                    trace=record['rigid_return_trace'];eps=trace['reported_aspect_epsilons']
                    if not trace['valid']or len(eps)!=16 or eps[-1]!=0 or not all(a>=b>=0 for a,b in zip(eps,eps[1:])):
                        raise ValueError('Soft stage lacks exact zero-aspect return')
                records+=1;outside+=not record['eligible_for_search']
            poses[name]=p.copy()
            if family in reference and value<1 and value<=reference[family]+.005:
                near[name]=p.copy();bucket=diversity_bucket(p)
                near_buckets.setdefault(key,set()).add(bucket)
                if bucket not in initial_buckets.get(key,set()):new_buckets.setdefault(key,set()).add(bucket)
            if family not in best or value<best[family]['excess']:
                best[family]=dict(excess=value,archive_key=name,geometry_sha256=sha)
    if len(poses)!=summary['certified_variants']or records!=summary['complete_stage_records']:
        raise ValueError('Complete retained stage count differs')
    atomic_npz(out/'near_reference_donors.npz',near)
    wins={family:{**record,'reference_excess':reference[family],'gain':reference[family]-record['excess']}
        for family,record in best.items()if family in reference and reference[family]-record['excess']>5e-9}
    result=dict(status='exact_bindings_verified',source_sha256=source_sha,binary_sha256=manifest['binary_sha256'],
        complete_certified_variants=len(poses),complete_stage_records=records,archive_only_stage_records=outside,
        useful_near_reference_variants=len(near),near_reference_archive_sha256=fq.digest(out/'near_reference_donors.npz'),
        near_reference_buckets_by_key={key:len(values)for key,values in near_buckets.items()},
        new_near_reference_buckets_by_key={key:len(values)for key,values in new_buckets.items()},
        diversity_note='Rounded buckets are diagnostics only; complete exact certified geometries remain retained.',
        comparison_sources=comparison_proof,orientation_fair_reference=reference,best_by_family=best,
        best_bank_note='Best emitted poses only; incumbents must be preserved unless a strict comparison passes.',
        strict_family_improvements=wins,aggregate_sha256=summary['donors_sha256'],
        provenance_sha256=summary['provenance_sha256'],download_receipt_sha256=fq.digest(remote/'download_receipt.json'),
        geometry_recertification_performed=False,full_competition_score_claim=False)
    atomic_json(out/'analysis.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--remote',type=Path,required=True)
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--comparison',type=Path,action='append',default=[]);args=parser.parse_args()
    print(json.dumps(analyze(args.remote,args.job,args.out,args.comparison),indent=2))
