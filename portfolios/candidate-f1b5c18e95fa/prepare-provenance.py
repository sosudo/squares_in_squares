#!/usr/bin/env python3
"""Preserve eighteen native returns from exact public35 reference poses."""
from pathlib import Path
from decimal import Decimal
import argparse
import json
import math
import shutil
import prepare_timeout_all_export as a
from prepare_polish_restart_export import case_digests, read_cases
import fq_active_pilot as fq
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'portfolios/candidate-7a30c35d28f5'
PARENT_RAW = ROOT/'artifacts/merged-kmmm35-v1.csv'
SOURCE = ROOT/'artifacts/fq-public35-reference-finish-v1'
CANDIDATES_SHA = '9d28a4fd42398612789cbd7f3e23a9f218359f21efc0d38c3e223b138fb9ea50'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pointer', type=Path, required=True)
    parser.add_argument('--expected-safe-sha256', required=True)
    args = parser.parse_args()
    pointer = json.loads(args.pointer.read_bytes())
    raw, safe = Path(pointer['raw']['path']), Path(pointer['safe']['path'])
    RAW_SHA, SAFE_SHA = pointer['raw']['sha256'], args.expected_safe_sha256
    assert raw.name == 'merged-kmmm35-native-v1.csv'
    assert a.sha(raw) == pointer['raw']['sha256'] == RAW_SHA
    assert a.sha(safe) == pointer['safe']['sha256'] == SAFE_SHA
    assert a.sha(pointer['canonical_proof']) == pointer['canonical_proof_sha256']
    assert pointer['safe']['score'] < 22.3 and pointer['roundtrip']['score'] < 22.3
    for name in ('raw', 'safe', 'roundtrip'):
        assert a.sha(pointer[name]['official_report']) == pointer[name]['official_report_sha256']
    assert a.sha(pointer['independent_report']['path']) == pointer['independent_report']['sha256']
    summary = json.loads((SOURCE/'summary.json').read_bytes())
    manifest = json.loads((SOURCE/'execution-manifest.json').read_bytes())
    inputs = json.loads((SOURCE/'input-manifest.json').read_bytes())
    proof = json.loads((SOURCE/'inputs/restart-input-proof.json').read_bytes())
    candidates = json.loads((SOURCE/'candidates.json').read_bytes())
    records = json.loads((SOURCE/'results.json').read_bytes())
    assert summary['status'] == 'complete' and summary['trials'] == summary['certified'] == len(records) == 18
    assert set(summary['improved_cases']) == set(candidates) and len(candidates) == 18
    assert a.sha(SOURCE/'candidates.json') == summary['candidates_sha256'] == CANDIDATES_SHA
    assert a.sha(SOURCE/'results.json') == summary['results_sha256']
    assert a.sha(SOURCE/'execution-manifest.json') == summary['manifest_sha256']
    assert a.sha(SOURCE/'certified.npz') == summary['certified_archive_sha256']
    assert a.sha(SOURCE/'input-manifest.json') == manifest['input_manifest_sha256']
    assert a.sha(SOURCE/'inputs/restart-inputs.npz') == manifest['input_sha256'] == inputs['inputs_sha256'] == proof['inputs_sha256']
    assert a.sha(SOURCE/'inputs/restart-input-proof.json') == inputs['input_proof_sha256']
    assert inputs['baseline']['sha256'] == a.sha(PARENT_RAW) == summary['canonical_raw_sha256']
    assert a.sha(fq.__file__) == manifest['source_hashes']['fq_active_pilot.py']
    for name, digest in manifest['source_hashes'].items():
        assert a.sha(SOURCE/'source'/name) == digest
    old, new = case_digests(PARENT_RAW), case_digests(raw)
    assert set(old) == set(new)
    changed = {n for n in new if new[n] != old[n]}
    assert changed == set(candidates)
    new_rows, old_rows = read_cases(raw, changed), read_cases(PARENT_RAW, changed)
    assert all(new_rows[n] == [[Decimal(v) for v in row] for row in candidates[n]['squares']] for n in changed)
    bindings = []
    with np.load(SOURCE/'inputs/restart-inputs.npz', allow_pickle=False) as archive:
        for n in sorted(changed, key=int):
            candidate = candidates[n]
            record = next(r for r in records if r['slot'] == candidate['provenance']['slot'])
            assert record['n'] == int(n) and record['status'] == 'certified' and record['strict_vs_latest_canonical']
            assert record['certificate'] == candidate['certificate']
            witness = proof['cases'][n]
            original, parent = archive[witness['original_key']], archive[witness['reference_key']]
            assert np.array_equal(original, np.asarray(old_rows[n], dtype=np.float64))
            translated = original.copy(); translated[:, :2] -= witness['translation_subtracted']
            assert np.array_equal(translated, parent) and not witness['scaling_applied']
            assert a.geometry_sha(parent) == witness['reference_geometry_sha256'] == record['selected_geometry_sha256']
            selected = Path(record['selected_archive'])
            assert a.sha(selected) == record['selected_archive_sha256']
            assert np.array_equal(a.one_pose(selected), parent)
            command = record['command']
            native_in, native_out = Path(command[command.index('--in')+1]), Path(command[command.index('--out')+1])
            encoded, offsets = fq.encode(parent, math.isqrt(int(n)), math.isqrt(int(n)))
            assert offsets == [0, 0] and encoded.encode() == native_in.read_bytes()
            assert a.sha(native_in) == record['input_sha256'] == candidate['provenance']['native_input_sha256']
            assert a.sha(native_out) == record['native_output_sha256'] == candidate['provenance']['native_output_sha256']
            q = a.one_pose(record['certified_archive'])
            a.candidate_check(candidate, q, record['geometry_sha256'])
            assert a.sha(record['certified_archive']) == record['certified_archive_sha256']
            assert np.array_equal(fq.decode(native_out, int(n)), q)
            for key in ('raw_returned', 'decoded_returned'):
                item = record[key]
                assert a.sha(item['path']) == item['sha256']
                assert a.geometry_sha(a.one_pose(item['path'])) == item['geometry_sha256']
            bindings.append(dict(n=int(n), record=record, input_witness=witness,
                                 exact_original_rows=True, exact_translation_only=True,
                                 exact_native_input=True, exact_native_decode=True))
    # Preserve every finite control's native bytes, including every certified returned geometry.
    for record in records:
        assert record['status'] == 'certified' and record['native_status'] == 'returned'
        native = Path(record['native_output_path'])
        for path, digest in [(native, record['native_output_sha256']),
                (native.with_suffix('.in'), record['input_sha256']),
                (native.with_suffix('.log'), record['log_sha256']),
                (native.with_suffix('.stdout'), record['stdout_sha256']),
                (native.with_suffix('.stderr'), record['stderr_sha256']),
                (Path(record['selected_archive']), record['selected_archive_sha256']),
                (Path(record['certified_archive']), record['certified_archive_sha256'])]:
            assert a.sha(path) == digest
    recipe = ROOT/('portfolios/candidate-'+SAFE_SHA[:12]); recipe.mkdir(exist_ok=False); a.RECIPE = recipe
    inventory = {}
    for source in sorted(SOURCE.rglob('*')):
        if source.is_file() and '__pycache__' not in source.parts:
            relative = source.relative_to(SOURCE)
            inventory[str(relative)] = a.copy(source, recipe/'reference-control-ancestry'/relative)
    parent = json.loads((PARENT/'export_manifest.json').read_bytes())
    assert a.sha(PARENT/'additional-source-provenance.json') == parent['additional_source_provenance_sha256']
    a.copy(PARENT/'additional-source-provenance.json', recipe/'inherited-7a30-provenance.json')
    for directory in sorted(PARENT.glob('source-notices-*')):
        shutil.copytree(directory, recipe/directory.name)
    native_notices = {}
    for name in ('LICENSE', 'NOTICE', 'SOURCE_MANIFEST.json'):
        source = ROOT/'vendor/fq'/name
        if source.exists():
            native_notices[name] = dict(**a.copy(source, recipe/'native-notices'/name), content=source.read_text())
    selection = {n: 'matched_original_reference_ALM45_pit100_flip16' for n in sorted(changed, key=int)}
    additional = dict(kind='eighteen_native_returns_from_public35_reference_poses',
        inherited_parent_recipe='../candidate-7a30c35d28f5/', inherited_parent_export_version=1,
        inherited_parent_additional_provenance=parent['additional_source_provenance'],
        inherited_parent_additional_provenance_sha256=parent['additional_source_provenance_sha256'],
        reference_control_summary=summary, execution_manifest=manifest, input_manifest=inputs,
        retained_control_files=inventory, selected_native_bindings=bindings, native_notices=native_notices,
        actual_final_case_source_selection=selection, actual_final_raw_csv_sha256=RAW_SHA,
        actual_final_safe_csv_sha256=SAFE_SHA,
        scope='Eighteen native improvements from exact public35 reference poses. All eighteen control inputs, native returns, raw/decoded/certified poses, '
              'logs and source snapshots are retained. No GPU-initializer attribution. Exact inherited source notices and ancestry retained. '
              'Export performs no optimization, geometry certification, scaling or coordinate reserialization.')
    a.save(recipe/'additional-source-provenance.json', additional)
    a.save(recipe/'actual-final-case-source-selection.json', selection)
    for source, name in [(pointer['raw']['official_report'], 'raw-official.json'),
            (pointer['safe']['official_report'], 'safe-official.json'),
            (pointer['roundtrip']['official_report'], 'roundtrip-official.json'),
            (pointer['independent_report']['path'], 'independent-validation.json'),
            (pointer['canonical_proof'], 'transport-validation.json'), (args.pointer, 'current-best-portfolio.json')]:
        a.copy(source, recipe/name)
    a.copy(Path(__file__), recipe/'prepare-provenance.py')
    a.copy(Path(a.__file__), recipe/'prepare-ancestry-helper.py')
    print(json.dumps(dict(recipe=str(recipe), selected_cases=selection, retained_control_files=len(inventory),
                         additional_bytes=(recipe/'additional-source-provenance.json').stat().st_size,
                         additional_sha256=a.sha(recipe/'additional-source-provenance.json'))))


if __name__ == '__main__':
    main()
