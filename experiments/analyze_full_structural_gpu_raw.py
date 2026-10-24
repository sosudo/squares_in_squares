"""Bounded metadata-only audit of immutable full-packing raw stage packets."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import signal
import time
import zipfile
import numpy as np


def digest(path):
    with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def summarize(root,index_sha256):
    root=Path(root).resolve();index_path=root/'full_structural_v2_raw_index.json'
    assert digest(index_path)==index_sha256
    index=json.loads(index_path.read_text());assert index['validated']is False
    config=json.loads((root/'prepared_config.json').read_text());groups={};packets=[];started=time.monotonic()
    for device,files in index['files'].items():
        for record in files:
            path=(root/record['path']).resolve();assert path.is_relative_to(root)
            assert path.stat().st_size==record['bytes']and digest(path)==record['sha256']
            with zipfile.ZipFile(path)as archive:
                metadata=json.loads(np.load(io.BytesIO(archive.read('metadata_json.npy')),allow_pickle=False).tobytes())
            n=int(metadata['n']);assert metadata['validated']is False
            assert len(metadata['rows'])==config['replicas']
            packets.append(dict(device=device,path=record['path'],sha256=record['sha256'],stages=len(metadata['stages'])))
            for stage in metadata['stages']:
                label=stage['label'];assert label in metadata['array_sha256']
                for i,row in enumerate(metadata['rows']):
                    key=f"{device}/{n}/{label}/{row['target_depth']}"
                    group=groups.setdefault(key,dict(device=int(device),n=n,label=label,target_depth=row['target_depth'],
                        poses=0,finite_metrics=0,residual_below_1e_minus7=0,residual_below_1e_minus6=0,
                        residual_below_1e_minus4=0,residual_below_1e_minus3=0,below_current_floating_side=0,
                        below_stage_box_floating_side=0,positive_residual_small_gradient=0,
                        positive_residual_gradient_below_1e_minus6=0,positive_residual_gradient_below_1e_minus4=0,
                        iterations_at_limit=0,iterations_below10=0,minimum_residual=None,minimum_floating_side=None,
                        maximum_gradient_norm=None,minimum_gradient_norm=None,iteration_sum=0.,
                        best_residual_source=None))
                    group['poses']+=1
                    residual=stage['exact_residuals'][i];length=stage['floating_sides'][i]
                    gradient=stage['fresh_gradient_norms'][i];iterations=stage['native_iterations'][i]
                    if any(v is None or not math.isfinite(v)for v in(residual,length,gradient,iterations)):continue
                    group['finite_metrics']+=1;group['iteration_sum']+=iterations
                    for threshold,suffix in((1e-7,'7'),(1e-6,'6'),(1e-4,'4'),(1e-3,'3')):
                        group['residual_below_1e_minus'+suffix]+=int(residual<threshold)
                    group['below_current_floating_side']+=int(length<config['reference_sides'][str(n)])
                    group['below_stage_box_floating_side']+=int(length<=stage['box_sides'][i])
                    group['positive_residual_small_gradient']+=int(residual>1e-5 and gradient<1e-8)
                    group['positive_residual_gradient_below_1e_minus6']+=int(residual>1e-5 and gradient<1e-6)
                    group['positive_residual_gradient_below_1e_minus4']+=int(residual>1e-5 and gradient<1e-4)
                    group['iterations_at_limit']+=int(iterations>=stage['steps']-1)
                    group['iterations_below10']+=int(iterations<10)
                    if group['minimum_residual']is None or residual<group['minimum_residual']:
                        group['minimum_residual']=residual
                        group['best_residual_source']=dict(packet=record['path'],packet_sha256=record['sha256'],replica=i,
                            array_sha256=metadata['array_sha256'][label],source_id=row['source_id'],
                            source_visit=row['source_visit'],mode=row['mode'],amplitude=row['amplitude'],
                            stage=label,side=length,gradient_norm=gradient,iterations=iterations,
                            input_geometry_sha256=row['mutation']['input_geometry_sha256'],validated=False)
                    group['minimum_floating_side']=min(group['minimum_floating_side']if group['minimum_floating_side']is not None else math.inf,length)
                    group['minimum_gradient_norm']=min(group['minimum_gradient_norm']if group['minimum_gradient_norm']is not None else math.inf,gradient)
                    group['maximum_gradient_norm']=max(group['maximum_gradient_norm']if group['maximum_gradient_norm']is not None else 0.,gradient)
    for group in groups.values():
        group['mean_native_iterations']=group['iteration_sum']/max(1,group['finite_metrics'])
    return dict(kind='Hash-bound raw-stage metadata audit; no geometry is certified by this report.',
        index_sha256=index_sha256,packet_count=len(packets),packet_bytes=sum(r['bytes']for fs in index['files'].values()for r in fs),
        seconds=time.monotonic()-started,groups=groups,packets=packets,
        limitations=['Native iteration count does not identify line-search stop reason.',
                    'Residual and floating side thresholds are diagnostics, not feasibility certificates.',
                    'Minimum side and minimum residual may refer to different poses.'],
        search_performed=False,competition_submission_performed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--index-sha256',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    def expired(signum,frame):raise TimeoutError('120-second metadata audit bound')
    signal.signal(signal.SIGALRM,expired);signal.alarm(120)
    report=summarize(args.root,args.index_sha256)
    temporary=args.out.with_suffix('.incoming');temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(args.out)
    print(json.dumps({k:v for k,v in report.items()if k not in('groups','packets')}));signal.alarm(0)


if __name__=='__main__':main()
