#!/usr/bin/env python3
"""Freeze the two selected LP100 returns and exact inherited SAFE provenance."""
from pathlib import Path
from decimal import Decimal
import argparse
import json
import math
import shutil
import prepare_timeout_all_export as a
from prepare_polish_restart_export import case_digests, read_cases
from compose_gadgets import normalize, side
import fq_active_pilot as fq
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'portfolios/candidate-fb3d0bae17af'
PARENT_RAW = ROOT/'artifacts/merged-fq-gpu-polish-final-v1.csv'
SOURCE = ROOT/'artifacts/fq-newton-finish-pilot-v1'
SAFE_SHA = '631b3114e7f3afeb0da5411115b69a41995a916bb04a72c46350115501514d60'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pointer', type=Path, required=True)
    args = parser.parse_args()
    pointer = json.loads(args.pointer.read_bytes())
    raw, safe = Path(pointer['raw']['path']), Path(pointer['safe']['path'])
    assert a.sha(raw) == pointer['raw']['sha256']
    assert a.sha(safe) == pointer['safe']['sha256'] == SAFE_SHA
    assert a.sha(pointer['canonical_proof']) == pointer['canonical_proof_sha256']
    assert pointer['safe']['score'] < 22.3 and pointer['roundtrip']['score'] < 22.3
    review = json.loads((SOURCE/'completion-review.json').read_bytes())
    assert review['status'] == 'complete' and review['controls_passed']
    for name in ('candidates', 'results', 'manifest'):
        assert a.sha(SOURCE/(name+'.json')) == review[name+'_sha256']
    candidates = json.loads((SOURCE/'candidates.json').read_bytes())
    records = json.loads((SOURCE/'results.json').read_bytes())
    manifest = json.loads((SOURCE/'manifest.json').read_bytes())
    assert manifest['baseline']['sha256'] == a.sha(PARENT_RAW)
    old, new = case_digests(PARENT_RAW), case_digests(raw)
    assert set(old) == set(new)
    changed = {n for n in new if new[n] != old[n]}
    assert changed == set(candidates) == {'761', '995'}
    rows = read_cases(raw, changed)
    assert all(rows[n] == [[Decimal(v) for v in row] for row in candidates[n]['squares']] for n in changed)
    recipe = ROOT/('portfolios/candidate-'+SAFE_SHA[:12])
    recipe.mkdir(exist_ok=False); a.RECIPE = recipe
    dest = recipe/'new-native-ancestry'
    files = {name:a.copy(SOURCE/name, dest/name) for name in
             ('completion-review.json', 'candidates.json', 'results.json', 'manifest.json',
              'summary.json', 'comparisons.json', 'controls.json', 'supervisor.json')}
    numerical = {path:a.copy(path, dest/'source'/Path(path).name, digest)
                 for path,digest in manifest['source_hashes'].items()}
    assert a.sha(SOURCE/'inputs/fq') == manifest['binary_sha256']
    files['parent_poses'] = a.copy(SOURCE/'inputs/poses.npz', dest/'inputs/poses.npz', manifest['poses_sha256'])
    with np.load(SOURCE/'inputs/poses.npz', allow_pickle=False) as z:
        parents = {n:z[n].copy() for n in changed}
    parent_rows = read_cases(PARENT_RAW, changed)
    assert all(np.array_equal(parents[n], np.asarray(parent_rows[n], dtype=np.float64)) for n in changed)
    selection, bindings = {}, []
    for n in sorted(changed, key=int):
        candidate = candidates[n]; provenance = candidate['provenance']
        record = next(r for r in records if r['n'] == int(n) and r['mode'] == provenance['selected_arm'])
        assert record['status'] == 'certified' and record['certificate'] == candidate['certificate']
        assert not provenance['newton_attribution'] and not record['activation']['actual_finish_path_observed']
        assert provenance['source_manifest_sha256'] == a.sha(SOURCE/'manifest.json')
        assert provenance['source_results_sha256'] == a.sha(SOURCE/'results.json')
        trial = SOURCE/'trials'/('n'+n+'-'+record['mode'])
        q = a.one_pose(trial/'certified.npz')
        a.candidate_check(candidate, q, record['geometry_sha256'])
        assert a.sha(trial/'certified.npz') == record['certified_archive_sha256'] == provenance['retained_archive_sha256']
        assert a.geometry_sha(parents[n]) == record['parent_geometry_sha256'] == manifest['geometry_sha256'][n]
        start = normalize(parents[n]); encoded, offsets = fq.encode(start, math.floor(side(start)), math.floor(side(start)))
        assert offsets == [0,0] and encoded.encode() == (trial/'native.in').read_bytes()
        assert (trial/'native.in').read_bytes() == (SOURCE/'inputs'/('n'+n+'.in')).read_bytes()
        expected = {'native.in':record['native_input_sha256'], 'native.out':record['native_output_sha256'],
                    'native.stdout':record['stdout_sha256'], 'native.stderr':record['stderr_sha256'],
                    'raw-returned.npz':record['raw_returned_archive_sha256'],
                    'certified.npz':record['certified_archive_sha256']}
        assert expected['native.out'] == provenance['native_output_sha256']
        assert a.geometry_sha(a.one_pose(trial/'raw-returned.npz')) == record['raw_returned_geometry_sha256']
        assert np.array_equal(a.one_pose(trial/'pending-certificate.npz'), q)
        decoded = fq.decode(trial/'native.out', int(n))
        assert decoded is not None and np.array_equal(decoded, q)
        selected = {p.name:a.copy(p, dest/'selected'/('n'+n)/p.name, expected.get(p.name))
                    for p in sorted(trial.iterdir()) if p.is_file()}
        bindings.append(dict(n=int(n), selected_record=record, files=selected,
                             exact_parent_input_reproduced=True, exact_native_decode_reproduced=True))
        selection[n] = 'LP100; paired Newton option inactive and identical on these targets'
    parent = json.loads((PARENT/'export_manifest.json').read_bytes())
    assert a.sha(PARENT/'additional-source-provenance.json') == parent['additional_source_provenance_sha256']
    a.copy(PARENT/'additional-source-provenance.json', recipe/'inherited-fb3d-provenance.json')
    for directory in sorted(PARENT.glob('source-notices-*')):
        shutil.copytree(directory, recipe/directory.name)
    additional = dict(kind='two_exact_LP100_returns', inherited_parent_recipe='../candidate-fb3d0bae17af/',
        inherited_parent_export_version=1, inherited_parent_additional_provenance=parent['additional_source_provenance'],
        inherited_parent_additional_provenance_sha256=parent['additional_source_provenance_sha256'],
        manifest=manifest, completion_review=review, files=files, numerical_sources=numerical,
        selected_native_bindings=bindings, actual_final_case_source_selection=selection,
        actual_final_raw_csv_sha256=a.sha(raw), actual_final_safe_csv_sha256=a.sha(safe),
        scope='Two selected LP100 improvements. Newton was inactive on all real targets; paired output geometries equal. '
              'Exact inherited notices and lineage retained. Export performs no numerical conversion, scaling or new geometry certification.')
    a.save(recipe/'additional-source-provenance.json', additional)
    a.save(recipe/'actual-final-case-source-selection.json', selection)
    for source,name in [(pointer['raw']['official_report'],'raw-official.json'),
        (pointer['safe']['official_report'],'safe-official.json'), (pointer['roundtrip']['official_report'],'roundtrip-official.json'),
        (pointer['independent_report']['path'],'independent-validation.json'),
        (pointer['canonical_proof'],'transport-validation.json'), (args.pointer,'current-best-portfolio.json')]:
        a.copy(source, recipe/name)
    a.copy(Path(__file__), recipe/'prepare-provenance.py')
    a.copy(Path(a.__file__), recipe/'prepare-ancestry-helper.py')
    print(json.dumps(dict(recipe=str(recipe), selected_cases=selection,
                         additional_sha256=a.sha(recipe/'additional-source-provenance.json'))))


if __name__ == '__main__': main()
