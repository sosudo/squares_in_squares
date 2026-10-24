#!/usr/bin/env python3
"""Verify frozen structural-search provenance and compare surviving topologies."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from compose_gadgets import normalize, side
from fq_active_pilot import digest, encode
from fq_coherent_clusters import atom_json


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest()


def alignment(candidate, reference):
    best = None
    for reflected in (False,True):
        for k in range(4):
            q = candidate.copy()
            if reflected:
                q[:,0] *= -1; q[:,2] = math.pi-q[:,2]
            angle = k*math.pi/2; c,s = math.cos(angle),math.sin(angle)
            q[:,:2] = q[:,:2]@np.array([[c,s],[-s,c]])
            q[:,2] += angle; q = normalize(q)
            displacement2 = np.sum((q[:,None,:2]-reference[None,:,:2])**2,axis=-1)
            angular = (q[:,None,2]-reference[None,:,2]+np.pi/4)%(np.pi/2)-np.pi/4
            rows,cols = linear_sum_assignment(displacement2+.25*angular**2)
            rms = float(np.sqrt(np.mean(displacement2[rows,cols])))
            value = dict(reflected=reflected,quarter_turns=k,rms_center_distance=rms,
                         maximum_center_distance=float(np.sqrt(displacement2[rows,cols]).max()),
                         rms_angle_degrees=float(np.degrees(np.sqrt(np.mean(angular[rows,cols]**2)))),
                         maximum_angle_degrees=float(np.degrees(abs(angular[rows,cols]).max())))
            if best is None or rms < best['rms_center_distance']: best = value
    return best


def analyze(run):
    manifest = json.loads((run/'manifest.json').read_text())
    current = json.loads((run/'current.json').read_text()); snapshot = Path(current['snapshot'])
    assert digest(snapshot/'summary.json') == current['summary_sha256']
    summary = json.loads((snapshot/'summary.json').read_text())
    for name,sha in summary['output_hashes'].items(): assert digest(snapshot/name) == sha
    selected = run/'inputs/selected.npz'; assert digest(selected) == manifest['selected_sha256']
    assert digest(run/'inputs/fq') == manifest['binary_sha256']
    records = json.loads((snapshot/'results.json').read_text())
    outcomes = []
    with np.load(selected,allow_pickle=False) as inputs, np.load(snapshot/'donors.npz',allow_pickle=False) as archive:
        for record in records:
            if 'mutation' not in record: continue
            folder = Path(record['folder']); mutation = record['mutation']; n = record['n']
            source = inputs[str(n+1)]; deleted = np.delete(source,mutation['deleted_index'],axis=0)
            assert geometry_sha(source) == mutation['ancestor_geometry_sha256']
            assert geometry_sha(deleted) == mutation['feasible_seed_geometry_sha256']
            assert digest(folder/'input.npz') == record['input_npz_sha256']
            with np.load(folder/'input.npz',allow_pickle=False) as z: q = z['pose']
            assert geometry_sha(q) == mutation['optimizer_input_geometry_sha256']
            w = math.floor(side(q))
            encoded,offsets = encode(q,w,w)
            assert offsets == [0,0]
            assert hashlib.sha256(encoded.encode()).hexdigest() == record['native_input_sha256']
            assert digest(folder/'input.txt') == record['native_input_sha256']
            if record['status'] != 'certified': continue
            assert record['certificate']['valid']
            assert digest(folder/'certified.npz') == record['certified_npz_sha256']
            with np.load(folder/'certified.npz',allow_pickle=False) as z: p = z['pose']
            sha = geometry_sha(p); assert sha == record['geometry_sha256']
            assert np.array_equal(archive[f'{n}__{sha}'],p)
            folded = (p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
            result = dict(n=n,trial_index=record['trial_index'],mode=mutation['mode'],
                          deleted_index=mutation['deleted_index'],side=record['side'],side_gain=record['side_gain'],
                          geometry_sha256=sha,tilted_count=int(np.count_nonzero(abs(folded)>.018)),
                          contact_edges_changed=record['changed_contact_edges'])
            # Only competitive survivors warrant the O(n^3) D4 assignment diagnostic.
            if record['side_gain'] > -.005:
                result['alignment_to_current'] = alignment(p,inputs[str(n)])
            outcomes.append(result)
    report = dict(kind='frozen native-input and certified-archive audit',run=str(run),snapshot=str(snapshot),
                  manifest_sha256=digest(run/'manifest.json'),summary=summary,
                  all_recorded_native_inputs_verified=True,all_certified_geometries_verified=True,
                  cases={n:dict(trials=sum(r.get('n')==n for r in records),
                                distinct_deletions=sorted({r['mutation']['deleted_index'] for r in records if r.get('n')==n}),
                                best_side=min((r['side'] for r in outcomes if r['n']==n),default=None))
                         for n in (299,335,412,454)},outcomes=outcomes)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    args = parser.parse_args(); destination = args.run/'analysis.json'
    if destination.exists(): parser.error('Analysis already exists')
    report = analyze(args.run); atom_json(destination,report);destination.chmod(0o444)
    print(json.dumps({k:v for k,v in report.items() if k != 'outcomes'}))
