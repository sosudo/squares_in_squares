#!/usr/bin/env python3
"""Audit downloaded v2 aggregates without treating raw GPU stages as certified."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'experiments'))
from full_structural_gpu_moves import geometry_sha


def digest(path):
    with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def analyze(folder):
    receipt=json.loads((folder/'download-receipt.json').read_text());assert receipt['status']=='complete'
    assert receipt['private_source_verified'];out=folder/'outputs'
    for name,record in receipt['files'].items():assert digest(out/name)==record['sha256']
    load=lambda name:json.loads((out/name).read_text())
    summary=load('full_structural_v2_summary.json');manifest=load('job_manifest.json');config=load('prepared_config.json')
    assert config==manifest['configuration']and config['cuda_options']==['--std=c++17','--fmad=false']
    assert manifest['variants']==sum(map(len,config['source_order'].values()))==81
    with np.load(out/'artifacts/full_structural_v2_certified.npz',allow_pickle=False)as z:poses={k:z[k]for k in z.files}
    assert digest(out/'artifacts/full_structural_v2_certified.npz')==summary['archive_sha256']
    records=load('full_structural_v2_records.json');certified_by_stage=defaultdict(set);best={}
    for record in records:
        sha=record['geometry_sha256'];p=poses[sha];n=int(record['n']);certificate=record['certificate']
        assert p.shape==(n,3)and p.dtype==np.float64 and np.isfinite(p).all()and geometry_sha(p)==sha
        assert record['validated']and certificate['valid']
        assert certificate['independent_raw']['valid']and certificate['independent_roundtrip']['valid']
        assert int(certificate['independent_raw']['n'])==int(certificate['independent_roundtrip']['n'])==n
        assert certificate['shared_official_gate']['valid']and certificate['ordinary_pandas_official_reason']=='ok'
        assert certificate['shared_official_gate']['metric_sha256']=='312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'
        side=float(certificate['independent_raw']['side_upper']);assert abs(side-record['side'])<1e-12
        assert re.fullmatch('[0-9a-f]{64}',record['raw_bundle_sha256'])
        assert record['raw_input_geometry_sha256']==record['row']['mutation']['input_geometry_sha256']
        key=f"{record['device']}/{n}/{record['stage']}";certified_by_stage[key].add(sha)
        if side<best.get(str(n),{}).get('side',math.inf):
            gain=config['reference_sides'][str(n)]-side
            best[str(n)]=dict(side=side,side_gain=gain,score_gain=gain/math.sqrt(n),geometry_sha256=sha,device=record['device'],stage=record['stage'])
    assert set(poses)=={r['geometry_sha256']for r in records}
    index=load('full_structural_v2_raw_index.json');assert index['validated']is False
    pairing=load('full_structural_v2_pairing.json');inputs=pairing['actual_inputs']
    common=set(inputs['0'])&set(inputs['1']);mismatches=sorted(name for name in common if inputs['0'][name]!=inputs['1'][name])
    assert mismatches==pairing['summary']['mismatches']
    assert len(common)==pairing['summary']['common_batches']
    devices={}
    for d in('0','1'):
        status=summary['statuses'][d];stats=status['stats'];prefix=f'artifacts/full_structural_v2_device{d}/'
        controls=load(prefix+'gradient_controls.json');preflight=load(prefix+'preflight.json')
        assert controls['passed']and controls['compiler_options']==config['cuda_options']
        assert preflight['passed']and set(preflight['full_cases'])=={'147','299','335'}
        control_records=load(prefix+'preflight_packing_records.json')
        assert digest(out/(prefix+'preflight_packings.npz'))==preflight['certified_control_packings_sha256']==control_records['archive_sha256']
        assert digest(out/(prefix+'preflight_packing_records.json'))==preflight['certified_control_records_sha256']
        with np.load(out/(prefix+'preflight_packings.npz'),allow_pickle=False)as bank:
            assert set(bank.files)==set(control_records['records'])
            for name in bank.files:
                p=bank[name];r=control_records['records'][name]
                assert geometry_sha(p)==r['geometry_sha256']and r['certificate']['valid']
                assert int(r['certificate']['independent_raw']['n'])==len(p)
            preflight_retained=len(bank.files)
        raw=index['files'][d];assert all(re.fullmatch('[0-9a-f]{64}',r['sha256'])for r in raw)
        coverage={}
        for n,source_ids in config['source_order'].items():
            visits=Counter();source_modes=defaultdict(Counter);source_combinations=defaultdict(set)
            for key,count in status['dispatched_source_visits'].items():
                pieces=key.split('/')
                if pieces[0]==n:
                    visits[pieces[1]]+=count;source_modes[pieces[1]][pieces[2]]+=count
                    source_combinations[pieces[1]].add(tuple(pieces[2:]))
            assert set(visits)<=set(source_ids)|{f'current_{n}'}
            coverage[n]=dict(alternatives_available=len(source_ids),alternatives_dispatched=len(set(visits)&set(source_ids)),
                missing_alternatives=sorted(set(source_ids)-set(visits)),reference_starts=visits[f'current_{n}'],
                total_dispatched_starts=sum(visits.values()),
                starts_by_source_and_mode={name:dict(v)for name,v in source_modes.items()},
                observed_parameter_combinations_by_source={name:len(v)for name,v in source_combinations.items()},
                minimum_alternative_parameter_combinations=min(len(source_combinations[name])for name in source_ids))
        devices[d]=dict(arm=status['arm'],seconds=status['seconds'],stats=stats,
            quench_duty=stats['quench_wall_seconds']/max(status['seconds'],1e-9),
            cuda_and_transfer_fraction=stats['cuda_seconds']/max(status['seconds'],1e-9),
            stage_totals=status['stage_totals'],source_coverage=coverage,
            raw_packets=len(raw),raw_bytes=sum(r['bytes']for r in raw),
            preflight_certified_control_poses=preflight_retained,
            raw_dispatch_states=dict(Counter(r['dispatch_state']for r in raw)),
            certification_drain=summary['certification_drain'].get(d,{}),
            complete_source_matrix_scope='first-stage completion only; full-stage totals are separate')
    positive_gain=sum(max(0.,r['score_gain'])for r in best.values())
    return dict(source_sha256=receipt['source_sha256'],notebook=receipt['notebook'],version=receipt['version'],
        scope='Receipt/aggregate geometry and existing certificate audit; raw packets not downloaded or independently recertified here.',
        seconds=summary['seconds'],failures=summary['failures'],preflight_passed=summary['preflight_passed'],
        devices=devices,actual_pairing=pairing['summary'],certified_geometries=len(poses),
        selected_certified_counts_by_origin_stage={k:len(v)for k,v in certified_by_stage.items()},
        best_certified_by_n=best,provisional_positive_score_gain=positive_gain,
        frozen_baseline_score=config['baseline']['score'],provisional_score=config['baseline']['score']-positive_gain,
        all_raw_candidates_certified=False,competition_submission_performed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path);args=parser.parse_args()
    report=analyze(args.folder);path=args.folder/'analysis.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in('devices',)}))
