"""One distinct buffered n335 construction and one <=30s rigid FQ control."""
import ast
import base64
import io
import itertools
import json
import math
from pathlib import Path
import shutil
import time
import zipfile

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
import fq_active_pilot as fq
import fq_remote_cpu_search as remote
from compose_gadgets import normalize, side
from cpu_recipe_replay import public_functions
from extract_broad_active_frontier import orient
from fq_bottleneck_campaign import contact_geometry
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha
from scalar_sat_staircase import build

ROOT = Path(__file__).resolve().parents[1]


def signature(p):
    gap, distance = contact_geometry(p)
    result = {}
    for tolerance in (1e-6,1e-5,1e-4):
        edges=np.triu((gap<=tolerance)&(distance<=1.6),1)
        degrees=edges.sum(0)+edges.sum(1)
        result[str(tolerance)]=dict(edges=int(edges.sum()),degree_histogram=np.bincount(degrees).tolist())
    angles=abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)
    return dict(tilted_over_one_degree=int(sum(angles>np.pi/180)),contacts=result)


def novelty(p,bank):
    p=normalize(p);tree=cKDTree(p[:,:2]);sig=signature(p);rows=[]
    for name,q in bank.items():
        if len(q)!=len(p):continue
        best=float('inf');transformation=None
        for trans,sx,sy in itertools.product((False,True),(-1,1),(-1,1)):
            r=orient(q,trans,sx,sy)
            r[:,:2]+=p[:,:2].mean(0)-r[:,:2].mean(0)
            value=max(float(tree.query(r[:,:2])[0].max()),float(cKDTree(r[:,:2]).query(p[:,:2])[0].max()))
            if value<best:best=value;transformation=[trans,sx,sy]
        qs=signature(q)
        rows.append(dict(source=name,geometry_sha256=geometry_sha(q),
            minimum_centroid_aligned_D4_center_Hausdorff=best,d4=transformation,
            tilted_over_one_degree=qs['tilted_over_one_degree'],
            contact_degree_histogram_differs={t:sig['contacts'][t]['degree_histogram']!=v['degree_histogram']for t,v in qs['contacts'].items()}))
    rows.sort(key=lambda row:row['minimum_centroid_aligned_D4_center_Hausdorff'])
    return dict(signature=sig,compared_335_poses=len(rows),comparisons=rows,
        material_geometry_difference=bool(rows and rows[0]['minimum_centroid_aligned_D4_center_Hausdorff']>.01),
        note='Centroid-aligned D4 Hausdorff and threshold-contact graph degree histograms are permutation invariant. No general geometric-topology equivalence claim.')


def main():
    began=time.monotonic();out=ROOT/'artifacts/n335-buffered-seed-v1';out.mkdir(exist_ok=False)
    audit_path=ROOT/'artifacts/n335-composition-coverage-v1/report.json';audit=json.loads(audit_path.read_text())
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text());raw=pointer['raw']
    assert raw['sha256']==audit['baseline_sha256']==fq.digest(raw['path'])
    recipe=next(r for r in audit['nearest_two_block']if r['width']<18 or r['height']<18)
    selected=[audit['types'][i]for i in recipe['type_ids']]
    frame=pd.read_csv(raw['path'],float_precision='round_trip');options=[]
    for item in selected:
        assert item['source'].startswith('current_raw:')
        n=int(item['source'].split(':')[1]);p=frame[frame.n==n].sort_values('square_id')[['x','y','angle']].to_numpy(float)
        p=orient(normalize(p),item['transposed'],1,1)
        assert geometry_sha(p)==item['geometry_sha256']
        options.append(dict(item,pose=p))
    stitch,_=public_functions(ROOT/'vendor/lightning_ftmc')
    p=build(options,[0,1],18,stitch)
    assert p is not None and len(p)==335
    source=ROOT/'artifacts/full-structural-gpu-v2-final-job-v2/search.py'
    vals={n.targets[0].id:ast.literal_eval(n.value)for n in ast.parse(source.read_text()).body
        if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id in('CONFIG','PAYLOAD')}
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(vals['PAYLOAD'])))as z:
        blob=z.read('prepared_variants.npz');assert fq.hashlib.sha256(blob).hexdigest()==vals['CONFIG']['embedded_sha256']['prepared_variants.npz']
        with np.load(io.BytesIO(blob),allow_pickle=False)as arrays:bank={k:arrays[k].copy()for k in arrays.files}
        assert len(bank)==81
        with np.load(io.BytesIO(z.read('prepared_references.npz')),allow_pickle=False)as arrays:
            bank.update({'reference_'+k:arrays[k].copy()for k in arrays.files})
    before=novelty(p,bank);atomic_json(out/'initial_novelty.json',before)
    if not before['material_geometry_difference']:raise ValueError('No material new D4 geometry; skip native work')
    certificate=full_certificate(p);assert certificate['valid']
    atomic_npz(out/'initial-certified.npz',{'18_18_11__buffered':p})
    atomic_json(out/'initial-certificate.json',certificate)
    binary=out/'fq';original=Path('/tmp/squares-fq-portable-target/release/fq')
    assert fq.digest(original)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
    shutil.copyfile(original,binary);binary.chmod(0o500)
    mode='n335_buffered_rigid';fq.MODES[mode]=['--loosen','1','--outer','45','--pit','100','--flip-top','16']
    trial=out/'trials';trial.mkdir()
    manifest=dict(baseline=raw,source_sha256=fq.digest(__file__),audit_report_sha256=fq.digest(audit_path),
        source_recipe=selected,stitch_modes=[0,1],box=[18,18],count=335,
        gpu_comparison_source_sha256=fq.digest(source),gpu_alternative_count=81,
        initial_geometry_sha256=geometry_sha(p),initial_archive_sha256=fq.digest(out/'initial-certified.npz'),
        initial_certificate_sha256=fq.digest(out/'initial-certificate.json'),binary_sha256=fq.digest(binary),
        command_options=fq.MODES[mode],native_stage_inclusive_ceiling_seconds=30,
        source_notices=['vendor/fq/LICENSE','vendor/fq/NOTICE','vendor/lightning_ftmc/SOURCE_MANIFEST.json'])
    atomic_json(out/'manifest.json',manifest)
    started=time.monotonic()
    record,_=remote.strict_trial(('18_18_11',p,mode,str(binary),str(trial),17335001,30.,started+30.))
    atomic_json(out/'trial-record.json',record)
    q=None
    if record.get('stage_archive'):
        with np.load(record['stage_archive'],allow_pickle=False)as z:q=z[z.files[0]].copy()
    if q is not None:
        atomic_json(out/'final_novelty.json',novelty(q,bank))
    candidates={'18_18_11__initial_'+geometry_sha(p):p}
    if q is not None:candidates['18_18_11__rigid_'+geometry_sha(q)]=q
    atomic_npz(out/'retained-seeds.npz',candidates)
    result=dict(seconds=time.monotonic()-began,native_stage_seconds=time.monotonic()-started,
        initial_side=float(certificate['independent_raw']['side_upper']),actual_current_side=audit['current_n335_side'],
        trial_status=record['status'],final_side=float(record['certificate']['independent_raw']['side_upper'])if q is not None else None,
        initial_novelty=before['material_geometry_difference'],
        retained_archive_sha256=fq.digest(out/'retained-seeds.npz'),retained_poses=len(candidates),
        manifest_sha256=fq.digest(out/'manifest.json'),no_submission=True)
    atomic_json(out/'report.json',result);(out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
