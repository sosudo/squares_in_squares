"""Read-only geometry/headroom census for a proposed momentum-hardening control.

No optimizer, solver, certificate, network or portfolio mutation is called.
Bands and angle-family thresholds are diagnostics, not topology invariants.
"""
from __future__ import annotations
import csv
from decimal import Decimal,localcontext
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(p):
    angles=np.mod(p[:,2],math.pi/2);fold=np.minimum(angles,math.pi/2-angles)
    ids=np.flatnonzero(fold>math.radians(1.));xy=p[ids,:2]
    components=[]
    if len(ids):
        distances=np.square(xy[:,None,:]-xy[None,:,:]).sum(2)
        graph=distances<1.6**2;seen=np.zeros(len(ids),bool)
        for i in range(len(ids)):
            if seen[i]:continue
            stack=[i];seen[i]=True;group=[]
            while stack:
                j=stack.pop();group.append(int(ids[j]))
                for k in np.flatnonzero(graph[j]&~seen):seen[k]=True;stack.append(int(k))
            if len(group)>=5:components.append(sorted(group))
    components.sort(key=lambda a:(-len(a),a))
    sorted_angles=np.sort(np.degrees(fold[ids]));cuts=np.flatnonzero(np.diff(sorted_angles)>=2.5)+1
    families=[a for a in np.split(sorted_angles,cuts)if len(a)>=5]
    signed=np.where(angles>math.pi/4,angles-math.pi/2,angles)
    return dict(tilted_over_one_degree=len(ids),bands=[len(a)for a in components],
        band_ids=components,angle_family_sizes=sorted([len(a)for a in families],reverse=True),
        angle_family_ranges_degrees=[[float(a.min()),float(a.max())]for a in families],
        positive_tilt_count=int((signed>math.radians(1.)).sum()),
        negative_tilt_count=int((signed<-math.radians(1.)).sum()),
        geometry_sha256=hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest())


def main():
    begin=time.monotonic();deadline=begin+85.
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pointer_bytes=pointer_path.read_bytes();pointer=json.loads(pointer_bytes)
    raw=Path(pointer['raw']['path']);official=Path(pointer['raw']['official_report']);reference=ROOT/'research/data/public_puzzle_reference_v10.json'
    assert sha(raw)==pointer['raw']['sha256']and sha(official)==pointer['raw']['official_report_sha256']
    targets={r['n']:Decimal(r['L'])for r in json.loads(reference.read_bytes())}
    actual={r['n']:Decimal(r['side'])for r in json.loads(official.read_bytes())['results']}
    with localcontext()as context:
        context.prec=80
        gaps={n:(side-targets[n])/Decimal(n).sqrt()for n,side in actual.items()if side-targets[n]>Decimal('1e-8')}
    poses={n:[]for n in gaps}
    with raw.open(newline='')as stream:
        for row in csv.DictReader(stream):
            n=int(row['n'])
            if n in poses:poses[n].append([float(row[k])for k in ['x','y','angle']])
    records=[]
    for n in sorted(gaps):
        if time.monotonic()>deadline:raise TimeoutError('85second read-only census cap')
        p=np.asarray(poses[n],dtype=np.float64);assert p.shape==(n,3)
        d=describe(p)
        records.append(dict(n=n,current_side=str(actual[n]),dated_reference_side=str(targets[n]),
            conditional_score_gap=str(gaps[n]),candidate_multiple_bands=len(d['bands'])>=2,
            candidate_multiple_angle_families=len(d['angle_family_sizes'])>=2,**d))
    def group(rows):
        return dict(cases=len(rows),case_ids=[r['n']for r in rows],
            conditional_gap_sum=str(sum((Decimal(r['conditional_score_gap'])for r in rows),Decimal(0))))
    candidates=[r for r in records if r['candidate_multiple_bands']or r['candidate_multiple_angle_families']]
    ranked=sorted(records,key=lambda r:-Decimal(r['conditional_score_gap']))
    groups={'all_material_positive_dated_gaps':group(records),'multiple_band_or_angle_family':group(candidates),
        'multiple_band_or_angle_family_above324':group([r for r in candidates if r['n']>324]),
        'all_above324':group([r for r in records if r['n']>324]),
        'largest90':group(ranked[:90])}
    report=dict(status='read_only_structural_candidate_census',seconds=time.monotonic()-begin,
        sources={str(p.relative_to(ROOT)):sha(p)for p in [raw,official,reference]},
        pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(),baseline_safe_score=pointer['safe']['score'],
        threshold='strictly below22.24',required_score_gain=str(Decimal(str(pointer['safe']['score']))-Decimal('22.24')),
        diagnostic_conventions=dict(tilt_degrees=1.,center_link=1.6,minimum_group=5,angle_gap_degrees=2.5),
        groups=groups,top20_band_candidates=sorted(candidates,key=lambda r:-Decimal(r['conditional_score_gap']))[:20],
        records=records,no_solver=True,no_optimizer=True,no_new_certification=True,no_network=True,
        limits='Dated scalar targets are neither lower bounds nor coordinate witnesses. Band thresholds are selection features, not topology/basin proof. No achievable gain is inferred.')
    out=ROOT/'artifacts/strategy-scout-v1';out.mkdir(exist_ok=True)
    (out/'geometry-census.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k]for k in ['status','seconds','baseline_safe_score','required_score_gain']}))
    print(json.dumps(groups,indent=2))


if __name__=='__main__':main()
