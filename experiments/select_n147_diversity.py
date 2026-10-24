#!/usr/bin/env python3
"""Select materially distinct certified n147 starts; never re-score numerical variants as gains."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import json
import math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from compose_gadgets import normalize
from extract_broad_active_frontier import orient
from fq_variant_campaign import geometry_sha
from fq_active_pilot import digest
from fq_coherent_clusters import atom_json,atom_npz
from finalize_n147_structural import edges


def spectrum(p):return np.sort(abs((p[:,2]+math.pi/4)%(math.pi/2)-math.pi/4))


def d4_center_separation(p,q):
    q=normalize(q);tree=cKDTree(q[:,:2]);best=math.inf
    for trans in(False,True):
        for sx in(-1,1):
            for sy in(-1,1):
                r=orient(p,trans,sx,sy)
                forward=tree.query(r[:,:2])[0].max();backward=cKDTree(r[:,:2]).query(q[:,:2])[0].max()
                best=min(best,float(max(forward,backward)))
    return best


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
    run=args.run;manifest=json.loads((run/'manifest.json').read_text());final=json.loads((run/'final/summary.json').read_text())
    assert final['donors_sha256']==digest(run/'donors.npz')
    records=json.loads((run/'records.json').read_text());proofs=json.loads((run/'final/proofs.json').read_text())
    bank=np.load(run/'donors.npz');reference=np.load(run/'inputs/reference.npz')['147'];refspec=spectrum(reference)
    rows=[]
    for key in bank.files:
        p=bank[key];s=spectrum(p)
        noncanonical=np.minimum(s,math.pi/4-s)
        rows.append(dict(key=key,max_angle_distance_from_upright_or_45=float(noncanonical.max()),
            intermediate_angle_count=int(np.sum(noncanonical>.005)),tilted_count=int(np.sum(s>.01)),
            spectrum_distance_from_reference=float(abs(s-refspec).max())))
    rows.sort(key=lambda r:(-r['max_angle_distance_from_upright_or_45'],-r['spectrum_distance_from_reference'],r['key']))
    selected={};details=[]
    for row in rows:
        p=bank[row['key']];s=spectrum(p)
        if selected:
            angular=[float(abs(s-spectrum(q)).max())for q in selected.values()]
            distances=[d4_center_separation(p,q)for q in selected.values()]
            # Either a substantial angle-spectrum difference or at least
            # 0.01 center-set separation after every D4 alignment is required.
            if not all(a>.0025 or d>.01 for a,d in zip(angular,distances)):continue
        else:angular=[];distances=[]
        proof=proofs[row['key']];assert proof['geometry_sha256']==geometry_sha(p)and proof['certificate']['valid']
        contact=edges(p);degree=np.zeros(len(p),int)
        for i,j in contact:degree[i]+=1;degree[j]+=1
        key='12_12_3__'+geometry_sha(p);selected[key]=p
        details.append(dict(row,archive_key=key,geometry_sha256=geometry_sha(p),
            source_record=proof['record'],certificate=proof['certificate'],
            prior_selected_angle_spectrum_distances=angular,prior_selected_D4_center_separations=distances,
            reference_D4_center_separation=d4_center_separation(p,reference),
            contact_edges=len(contact),contact_degree_histogram=np.bincount(degree).tolist()))
        if len(selected)==12:break
    out=run/'diversity-handoff';out.mkdir(exist_ok=False)
    atom_npz(out/'donors.npz',selected);atom_json(out/'proofs.json',details)
    summary=dict(selected=len(selected),all_strict_near_reference=True,
        raw_reference=manifest['pointer']['raw'],safe_reference=manifest['pointer']['safe'],
        original_seed_archive=str(run/'inputs/reference.npz'),original_seed_sha256=digest(run/'inputs/reference.npz'),
        full_source_bank=str(run/'donors.npz'),full_source_bank_sha256=digest(run/'donors.npz'),
        donors_sha256=digest(out/'donors.npz'),proofs_sha256=digest(out/'proofs.json'),
        source_manifest_sha256=digest(run/'manifest.json'),source_proofs_sha256=digest(run/'final/proofs.json'),
        source_sha256=digest(Path(__file__)),actual_score_gain=0.,
        scope='Selection requires pairwise angle-spectrum difference>0.0025rad or D4-normalized center-set separation>0.01. '
              'Near-contact graph at1e-6 is diagnostic only; no global graph-isomorphism claim or new feasibility certificates.',
        cases=[{k:v for k,v in row.items()if k not in ('source_record','certificate')}for row in details])
    atom_json(out/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items()if k not in ('cases','raw_reference','safe_reference')}),flush=True)


if __name__=='__main__':main()
