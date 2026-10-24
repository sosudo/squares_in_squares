#!/usr/bin/env python3
"""Freeze concrete rigid180/KMMM31 ancestry for the certified b84f SAFE export.

Copies exact existing evidence; runs no optimization or geometry certificate.
"""
from pathlib import Path
import csv
from decimal import Decimal
import hashlib
import json
import math
import os
import shutil
import sys
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
import numpy as np
from fq_active_pilot import encode
from fq_variant_campaign import geometry_sha
from compose_gadgets import side

RECIPE = ROOT/'portfolios/candidate-b84f2ff20f3e'
PARENT = ROOT/'portfolios/candidate-ffa6cf616d4a'
CAMPAIGN = ROOT/'artifacts/fq-current-rigid-v1'
COMPLETE = CAMPAIGN/'complete'
KMMM = ROOT/'artifacts/public-kmmm31'
RAW = ROOT/'artifacts/merged-fq-rigid180-kmmm31-v1.csv'
SAFE = ROOT/'artifacts/submission-fq-rigid180-kmmm31-v1-safe.csv'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def copy(source, target, expected=None):
    if expected and sha(source) != expected:
        raise ValueError(f'Exact source differs: {source}')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != source.read_bytes():
            raise ValueError(f'Existing immutable recipe differs: {target}')
    else:
        shutil.copyfile(source, target)
    return {'path': str(target.relative_to(RECIPE)), 'sha256': sha(target), 'bytes': target.stat().st_size}


def main():
    assert sha(RAW) == 'fc931068f0f4accb37c8ed8b33ea59607e4690440d7c3f98b4b79fbb8c34cffc'
    assert sha(SAFE) == 'b84f2ff20f3eec7dfadc6a9645dbb01a628629fb18ba7395421243a2d7770fe8'
    RECIPE.mkdir(exist_ok=False)
    ancestry = RECIPE/'rigid-native-ancestry'; ancestry.mkdir()
    summary = json.loads((COMPLETE/'summary.json').read_bytes())
    assert summary['status'] == 'complete' and summary['trials'] == 180 and summary['improved_cases'] == 31
    for name in ('candidates', 'results', 'manifest'):
        assert sha(COMPLETE/(name+'.json')) == summary[name+'_sha256']
    frozen = {}
    for name in ('candidates.json','results.json','manifest.json','summary.json'):
        frozen[name] = copy(COMPLETE/name, ancestry/name)
    records = json.loads((COMPLETE/'results.json').read_bytes())
    candidates = json.loads((COMPLETE/'candidates.json').read_bytes())
    with np.load(CAMPAIGN/'inputs/current-poses.npz', allow_pickle=False) as bank:
        parent_poses = {geometry_sha(bank[k]): bank[k] for k in bank.files}
    selected = []; bindings = []; selected_parents = {}
    for n,candidate in sorted(candidates.items(), key=lambda kv:int(kv[0])):
        record = next(r for r in records if r['job'] == candidate['provenance']['job'])
        assert record['n'] == int(n) and record['certificate']['valid'] and record['certificate'] == candidate['certificate']
        assert record['parent_geometry_sha256'] == candidate['provenance']['parent_geometry_sha256']
        parent = parent_poses[record['parent_geometry_sha256']]
        native_input,_ = encode(parent,math.floor(side(parent)),math.floor(side(parent)))
        assert hashlib.sha256(native_input.encode()).hexdigest() == record['input_sha256']
        selected_parents[n] = parent
        archive = Path(record['retained_archive'])
        assert sha(archive) == record['retained_archive_sha256']
        with np.load(archive,allow_pickle=False) as bank:
            pose = bank[record['archive_key']]
        assert geometry_sha(pose) == record['geometry_sha256']
        assert candidate['squares'] == [[f'{v:.17g}' for v in row] for row in pose]
        command = record['command']; inp = Path(command[command.index('--in')+1]); out = Path(command[command.index('--out')+1])
        files = []
        for path,digest in ((inp,record['input_sha256']), (out,record['native_output_sha256']), (out.with_suffix('.log'),record['log_sha256'])):
            files.append(copy(path,ancestry/'selected-native-files'/path.name,digest))
        files.append(copy(archive,ancestry/'selected-certified'/archive.name,record['retained_archive_sha256']))
        files.append(copy(archive.with_suffix('.json'),ancestry/'selected-certified'/archive.with_suffix('.json').name))
        for label in ('raw_returned','decoded_returned'):
            item = record[label]; path = Path(item['path'])
            files.append(copy(path,ancestry/label/path.name,item['sha256']))
        selected.append(record)
        bindings.append(dict(n=int(n),job=record['job'],geometry_sha256=record['geometry_sha256'],
                             parent_geometry_sha256=record['parent_geometry_sha256'],parent_input_exact=True,files=files))
    np.savez_compressed(ancestry/'selected-parents.npz', **selected_parents)
    save(ancestry/'selected-trial-records.json',selected); save(ancestry/'selected-native-bindings.json',bindings)
    native_manifest = json.loads((COMPLETE/'manifest.json').read_bytes())
    numerical_sources = {}
    for path,digest in native_manifest['source_hashes'].items():
        path = Path(path); source = path if path.is_absolute() else ROOT/path
        numerical_sources[str(path)] = copy(source,ancestry/'source'/source.name,digest)
    copy(ROOT/'vendor/fq/LICENSE',ancestry/'FQ-LICENSE')

    proof = json.loads((KMMM/'completion-proof.json').read_bytes())
    kmmm_candidates_path = ROOT/proof['candidate_json']; assert sha(kmmm_candidates_path) == proof['candidate_json_sha256']
    kmmm_candidates = json.loads(kmmm_candidates_path.read_bytes()); assert sorted(map(int,kmmm_candidates)) == [802,928]
    kmmm_folder = RECIPE/'kmmm31-proof'; kmmm_folder.mkdir()
    for path in [KMMM/'completion-proof.json',kmmm_candidates_path,*sorted((KMMM/'certified-screen-v1').glob('*'))]:
        if path.is_file():copy(path,kmmm_folder/path.name)
    notices = {}
    for name,digest in proof['notice_files'].items():
        path = ROOT/'vendor/notices/kmmm-v31'/name
        info = copy(path,RECIPE/'source-notices-kmmm31'/name,digest)
        notices[name] = dict(**info,content=path.read_text())
    source_candidates = {'rigid180':candidates,'kmmm31':kmmm_candidates}; groups = {}
    with RAW.open(newline='') as stream:
        for row in csv.DictReader(stream):
            if any(row['n'] in c for c in source_candidates.values()):
                groups.setdefault(row['n'],[]).append([Decimal(row[k])for k in ('x','y','angle')])
    selection = {}
    for n,rows in groups.items():
        matches = [label for label,c in source_candidates.items() if n in c and rows == [[Decimal(str(v)) for v in q]for q in c[n]['squares']]]
        assert len(matches) == 1,(n,matches)
        selection[n] = matches[0]
    assert len(selection) == 33 and list(selection.values()).count('rigid180') == 31
    save(RECIPE/'actual-final-case-source-selection.json',selection)
    parent_manifest = json.loads((PARENT/'export_manifest.json').read_bytes())
    assert sha(PARENT/'additional-source-provenance.json') == parent_manifest['additional_source_provenance_sha256']
    copy(PARENT/'additional-source-provenance.json',RECIPE/'inherited-ffa6-provenance.json')
    for name in ('source-notices-kmmm29','source-notices-lightning19'):
        shutil.copytree(PARENT/name,RECIPE/name)
    additional = dict(kind='completed_current_source_rigid180_plus_public_KMMM31',
        inherited_parent_recipe='../candidate-ffa6cf616d4a/',inherited_parent_export_version=2,
        inherited_parent_additional_provenance=parent_manifest['additional_source_provenance'],
        inherited_parent_additional_provenance_sha256=parent_manifest['additional_source_provenance_sha256'],
        native_source_commit=native_manifest['source_commit'],native_license_text=(ROOT/'vendor/fq/LICENSE').read_text(),
        rigid_final_summary=summary,rigid_final_manifest=native_manifest,rigid_frozen_evidence=frozen,
        rigid_selected_trial_records=selected,rigid_selected_native_bindings=bindings,
        rigid_selected_parents_npz_sha256=sha(ancestry/'selected-parents.npz'),rigid_numerical_sources=numerical_sources,
        KMMM31_completion=proof,KMMM31_completion_sha256=sha(KMMM/'completion-proof.json'),KMMM31_notices=notices,
        actual_final_case_source_selection=selection,actual_final_raw_csv_sha256=sha(RAW),actual_final_safe_csv_sha256=sha(SAFE),
        scope='Exact31 completed rigid winners and two certified public KMMM31 updates. Full prior provenance/notices inherited. No geometry optimization, certification, scaling or coordinate reserialization by exporter.')
    save(RECIPE/'additional-source-provenance.json',additional)
    for source,target in [
        ('merged-fq-rigid180-kmmm31-v1.validation.json','independent-validation.json'),
        ('merged-fq-rigid180-kmmm31-v1-official.json','raw-official.json'),
        ('submission-fq-rigid180-kmmm31-v1-safe-official.json','safe-official.json'),
        ('submission-fq-rigid180-kmmm31-v1-safe-roundtrip-official.json','roundtrip-official.json'),
        ('submission-fq-rigid180-kmmm31-v1-safe.transport-validation.json','transport-validation.json'),
        ('current-best-portfolio.json','current-best-portfolio.json')]:
        copy(ROOT/'artifacts'/source,RECIPE/target)
    current = json.loads((RECIPE/'current-best-portfolio.json').read_bytes()); assert current['safe']['sha256'] == sha(SAFE)
    copy(Path(__file__),RECIPE/'prepare-provenance.py')
    print(json.dumps(dict(recipe=str(RECIPE),cases=len(selection),native_records=len(selected),
                         additional_bytes=(RECIPE/'additional-source-provenance.json').stat().st_size,
                         additional_sha256=sha(RECIPE/'additional-source-provenance.json'))))


if __name__ == '__main__': main()
