#!/usr/bin/env python3
"""Freeze exact-hash certificate bindings and finite n147 coverage diagnostics."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import numpy as np
from fq_variant_campaign import geometry_sha
from fq_active_pilot import digest
from fq_coherent_clusters import atom_json,atom_npz
from compose_gadgets import side


def edges(p):
    i,j=np.triu_indices(len(p),1);d=p[j,:2]-p[i,:2];ai=p[i,2];aj=p[j,2]
    gap=np.full(len(i),-np.inf);radius=.5*(1+abs(np.cos(ai-aj))+abs(np.sin(ai-aj)))
    for a in(ai,ai+math.pi/2,aj,aj+math.pi/2):
        gap=np.maximum(gap,abs(d[:,0]*np.cos(a)+d[:,1]*np.sin(a))-radius)
    return set(zip(map(int,i[abs(gap)<1e-6]),map(int,j[abs(gap)<1e-6])))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
    run=args.run;report=json.loads((run/'report.json').read_text());supervisor=json.loads((run/'supervisor.json').read_text())
    assert supervisor['exitcode']==0 and not supervisor['forced']
    manifest=json.loads((run/'manifest.json').read_text());records=json.loads((run/'records.json').read_text())
    certificates=json.loads((run/'certificates.json').read_text());bank=np.load(run/'donors.npz');source=np.load(run/'inputs/reference.npz')
    assert report['donors_sha256']==digest(run/'donors.npz')and report['certificates_sha256']==digest(run/'certificates.json')
    assert all(digest(Path(path))==sha for path,sha in manifest['source_hashes'].items())
    by_key={r['archive_key']:r for r in records if r['status']=='certified'};proofs={};eligible={};diagnostics=[]
    for key in bank.files:
        p=bank[key];record=by_key[key];certificate=certificates[key]
        assert len(p)==147 and certificate['valid']and geometry_sha(p)==record['geometry_sha256']and certificate==record['certificate']
        proofs[key]=dict(geometry_sha256=geometry_sha(p),certificate=certificate,record=record)
        if side(p)<13:eligible['12_12_3__'+geometry_sha(p)]=p
        if 'removed_source_id'not in record:continue
        initial=np.delete(source['148'],record['removed_source_id'],axis=0)
        offset=np.median(p[:,:2]-initial[:,:2],axis=0)
        angles=(p[:,2]-initial[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
        diagnostics.append(dict(archive_key=key,removed_source_id=record['removed_source_id'],
            mode=record['structural_mode'],side=record['side'],
            position_change_after_translation=float(np.linalg.norm(p[:,:2]-initial[:,:2]-offset,axis=1).max()),
            max_angle_change_mod_quarter_turn=float(abs(angles).max()),
            changed_contact_edges=len(edges(p)^edges(initial))))
    out=run/'final';out.mkdir(exist_ok=False);atom_npz(out/'composition-eligible.npz',eligible);atom_json(out/'proofs.json',proofs)
    atom_json(out/'geometry-diagnostics.json',diagnostics)
    result=dict(supervisor=supervisor,all_deletions_completed=report['completed_deletions']==148,
        strict_geometries=len(bank.files),composition_eligible=len(eligible),fresh_certificates_during_finalization=0,
        exact_geometry_certificates_reused=len(bank.files),stages_by_mode=dict(Counter(r.get('structural_mode','baseline-control')for r in records)),
        stages_by_status=dict(Counter(r['status']for r in records)),reference_side=manifest['reference147_side'],
        best_side=report['best_side'],achieved_score_gain=report['score_gain'],public_target_side=manifest['public_target_side'],
        changed_contact_graph_geometries=sum(r['changed_contact_edges']>0 for r in diagnostics),
        maximum_changed_contact_edges=max(r['changed_contact_edges']for r in diagnostics),
        contact_graph_tolerance=1e-6,contact_graph_is_diagnostic_not_identity_or_feasibility_proof=True,
        input_manifest_sha256=digest(run/'manifest.json'),source_report_sha256=digest(run/'report.json'),
        source_records_sha256=digest(run/'records.json'),donors_sha256=digest(run/'donors.npz'),
        eligible_sha256=digest(out/'composition-eligible.npz'),proofs_sha256=digest(out/'proofs.json'),
        finalizer_source_sha256=digest(Path(__file__)),portfolio_changed=False,submission_performed=False)
    atom_json(out/'summary.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
