#!/usr/bin/env python3
"""Freeze exact public-v35 rows, certificates and notices for SAFE export."""
from pathlib import Path
from decimal import Decimal
import argparse
import csv
import hashlib
import io
import json
import shutil
import zipfile
import prepare_timeout_all_export as a
from prepare_polish_restart_export import case_digests, read_cases

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'portfolios/candidate-3c4cfc19361e'
PARENT_RAW = ROOT/'artifacts/merged-fq-sustained-controls-v1.csv'
SOURCE = ROOT/'artifacts/public-v35'
SAFE_SHA = '7a30c35d28f5df9f5cde6de6f831f1d4a76cd8cfbb87cc747bed395d84599e72'
PROVENANCE_SHA = '7c854ec129522515f8764197b0d89a4f0beec63a73af91053415fa5b2feef378'
CANDIDATES_SHA = '91b6e4b1a3d988afd6ccde68dec456e558993e88397125a6da17a2cbd1fbf076'


def token_cases(stream, wanted):
    result = {}
    for row in csv.DictReader(stream):
        if row['n'] in wanted:
            result.setdefault(row['n'], []).append([row[k] for k in ('x', 'y', 'angle')])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pointer', type=Path, required=True)
    args = parser.parse_args()
    pointer = json.loads(args.pointer.read_bytes())
    raw, safe = Path(pointer['raw']['path']), Path(pointer['safe']['path'])
    assert a.sha(raw) == pointer['raw']['sha256'] and raw.name == 'merged-kmmm35-v1.csv'
    assert a.sha(safe) == pointer['safe']['sha256'] == SAFE_SHA
    assert a.sha(pointer['canonical_proof']) == pointer['canonical_proof_sha256']
    assert pointer['safe']['score'] < 22.3 and pointer['roundtrip']['score'] < 22.3
    for name in ('raw', 'safe', 'roundtrip'):
        assert a.sha(pointer[name]['official_report']) == pointer[name]['official_report_sha256']
    assert a.sha(pointer['independent_report']['path']) == pointer['independent_report']['sha256']
    provenance_path = SOURCE/'certified-provenance.json'
    assert a.sha(provenance_path) == PROVENANCE_SHA
    provenance = json.loads(provenance_path.read_bytes())
    assert provenance['dataset'] == 'kmmmvs/squares-in-squares-best-packings' and provenance['dataset_version'] == 35
    for name in ('download_proof', 'archive', 'original_csv', 'exact_decimal_subset', 'certification_script'):
        assert a.sha(ROOT/provenance[name]['path']) == provenance[name]['sha256']
    download = json.loads((SOURCE/'download-proof.json').read_bytes())
    assert download['version'] == 35 and download['archive_sha256'] == provenance['archive']['sha256']
    cert = SOURCE/'certified'
    for name, expected in provenance['outputs'].items():
        assert a.sha(cert/name) == expected['sha256'] and (cert/name).stat().st_size == expected['bytes']
    summary = json.loads((cert/'certification-summary.json').read_bytes())
    candidates = json.loads((cert/'winning-candidates.json').read_bytes())
    intervals = json.loads((cert/'independent-certificates.json').read_bytes())
    officials = json.loads((cert/'official-winning-cases.json').read_bytes())
    assert a.sha(cert/'winning-candidates.json') == summary['candidate_json_sha256'] == CANDIDATES_SHA
    assert summary['status'] == 'complete' and not summary['rejections'] and len(candidates) == 18
    assert {str(n) for n in summary['fully_certified_cases']} == set(candidates) == set(intervals)
    assert all(r['valid'] and r['raw_official']['reason'] == r['roundtrip_official']['reason'] == 'ok'
               and r['roundtrip_independent']['valid'] for r in officials)
    assert all(r['valid'] for r in intervals.values())
    assert summary['baseline_sha256'] == provenance['baseline_sha256'] == a.sha(PARENT_RAW)
    old, new = case_digests(PARENT_RAW), case_digests(raw)
    assert set(old) == set(new)
    changed = {n for n in new if new[n] != old[n]}
    assert changed == set(candidates)
    current = read_cases(raw, changed)
    assert all(current[n] == [[Decimal(v) for v in row] for row in candidates[n]['squares']] for n in changed)
    with (SOURCE/'files/submission.csv').open() as stream:
        original = token_cases(stream, changed)
    with (SOURCE/'promising-exact-rows.csv').open() as stream:
        subset = token_cases(stream, changed)
    assert original == subset == {n: candidates[n]['squares'] for n in changed}
    # Verify every retained original member and the immutable archive, without
    # executing downloaded code or transforming coordinates.
    with zipfile.ZipFile(SOURCE/'dataset-v35.zip') as archive:
        members = [row for row in archive.infolist() if not row.is_dir()]
        assert {row.filename for row in members} == set(download['members'])
        for row in members:
            expected = download['members'][row.filename]
            data = archive.read(row)
            assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
            assert a.sha(SOURCE/'files'/row.filename) == expected['sha256']
        with io.TextIOWrapper(archive.open('submission.csv'), encoding='utf8', newline='') as stream:
            assert token_cases(stream, changed) == original
    recipe = ROOT/('portfolios/candidate-'+SAFE_SHA[:12]); recipe.mkdir(exist_ok=False); a.RECIPE = recipe
    evidence = {}
    paths = [provenance_path, SOURCE/'download-proof.json', SOURCE/'screen-pointer.json',
             SOURCE/'actual-side-screen.json', SOURCE/'promising-exact-rows.csv',
             SOURCE/'promising-exact-rows.source.json', *sorted(cert.glob('*'))]
    for source in paths:
        if source.is_file():
            relative = source.relative_to(SOURCE)
            evidence[str(relative)] = a.copy(source, recipe/'public-v35-proof'/relative)
    certification_source = ROOT/provenance['certification_script']['path']
    evidence['certification_source'] = a.copy(certification_source, recipe/'public-v35-proof/source'/certification_source.name)
    notices = {}
    for source in sorted((SOURCE/'files').rglob('*')):
        if source.is_file() and any(word in source.name.lower() for word in ('license', 'notice')):
            relative = source.relative_to(SOURCE/'files')
            expected = download['members'][str(relative)]['sha256']
            notices[str(relative)] = dict(**a.copy(source, recipe/'source-notices-kmmm35'/relative, expected), content=source.read_text())
    assert len(notices) == 45
    parent = json.loads((PARENT/'export_manifest.json').read_bytes())
    assert a.sha(PARENT/'additional-source-provenance.json') == parent['additional_source_provenance_sha256']
    a.copy(PARENT/'additional-source-provenance.json', recipe/'inherited-3c4-provenance.json')
    for directory in sorted(PARENT.glob('source-notices-*')):
        shutil.copytree(directory, recipe/directory.name)
    selection = {n: 'public_KMMM_dataset_version35_exact_decimal_rows' for n in sorted(changed, key=int)}
    additional = dict(kind='eighteen_certified_public_KMMM35_updates',
        inherited_parent_recipe='../candidate-3c4cfc19361e/', inherited_parent_export_version=1,
        inherited_parent_additional_provenance=parent['additional_source_provenance'],
        inherited_parent_additional_provenance_sha256=parent['additional_source_provenance_sha256'],
        public_source_provenance=provenance, public_source_provenance_sha256=PROVENANCE_SHA,
        public_download_proof=download, public_archive_member_count=len(download['members']),
        exact_public_archive_and_extracted_members_verified=True, exact_coordinate_token_chain_verified=True,
        public_certification_summary=summary, public_certified_evidence=evidence, KMMM35_notices=notices,
        actual_final_case_source_selection=selection, actual_final_raw_csv_sha256=a.sha(raw), actual_final_safe_csv_sha256=SAFE_SHA,
        attribution='These eighteen updates are copied from the publicly released KMMM best-packings dataset version35; '
                    'all original authors retain credit. This export makes no new discovery or algorithmic attribution.',
        scope='Exact public source tokens, raw/pandas/interval certificates, download/archive/member hashes and all45 notice files retained. '
              'The original47.6MB archive remains at its immutable provenance path; selected exact rows are included in this portable recipe. '
              'Exporter performs no optimization, geometry certification, additional scaling or coordinate reserialization.')
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
    print(json.dumps(dict(recipe=str(recipe), selected_cases=sorted(map(int, changed)), notices=len(notices),
                         source_members=len(download['members']), additional_bytes=(recipe/'additional-source-provenance.json').stat().st_size,
                         additional_sha256=a.sha(recipe/'additional-source-provenance.json'))))


if __name__ == '__main__':
    main()
