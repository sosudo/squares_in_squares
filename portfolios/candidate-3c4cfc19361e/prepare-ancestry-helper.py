#!/usr/bin/env python3
"""Preserve exact timeout-return ancestry for the frozen 680e SAFE portfolio."""
from pathlib import Path
from decimal import Decimal
import csv
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

PARENT = ROOT/'portfolios/candidate-b84f2ff20f3e'
RECIPE = ROOT/'portfolios/candidate-680e332bc6bc'
RAW = ROOT/'artifacts/merged-fq-timeout-all-v1.csv'
SAFE = ROOT/'artifacts/submission-fq-timeout-all-v1-safe.csv'
RAW_SHA = 'add7c0ee1599b97bb229f279dd0ee927c502ad6710940faccd92dca7c7658a53'
SAFE_SHA = '680e332bc6bc5bb7d741505b9460ca18fb410ce11929342e67fb2262b20a2d74'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, indent=2)+'\n')


def copy(source, target, expected=None):
    source, target = Path(source), Path(target)
    digest = sha(source)
    if expected is not None and digest != expected:
        raise ValueError(f'Exact source differs: {source}')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != source.read_bytes(): raise ValueError(f'Frozen target differs: {target}')
    else: shutil.copyfile(source, target)
    return dict(path=str(target.relative_to(RECIPE)), sha256=digest, bytes=target.stat().st_size)


def one_pose(path):
    with np.load(path, allow_pickle=False) as z:
        if len(z.files) != 1: raise ValueError('Expected exact single-pose archive')
        return z[z.files[0]]


def parent_check(path, n, expected_geometry, native_input):
    p = one_pose(path)
    assert p.shape == (n, 3) and geometry_sha(p) == expected_geometry
    text, _ = encode(p, math.isqrt(n), math.isqrt(n))
    assert text.encode() == Path(native_input).read_bytes()


def candidate_check(candidate, pose, digest):
    assert geometry_sha(pose) == digest
    assert candidate['certificate']['valid']
    assert candidate['squares'] == [[f'{v:.17g}' for v in row] for row in pose]


def main():
    assert sha(RAW) == RAW_SHA and sha(SAFE) == SAFE_SHA
    RECIPE.mkdir(exist_ok=False)
    groups, evidence = {}, {}
    for label, dirname, expected_count in [
        ('timeout16', 'fq-timeout-extension-v1', 7),
        ('remainder', 'fq-timeout-remainder-v1', 21),
    ]:
        campaign = ROOT/'artifacts'/dirname; complete = campaign/'complete'
        out = RECIPE/'native-ancestry'/label; out.mkdir(parents=True)
        summary = json.loads((complete/'summary.json').read_bytes())
        assert summary['status'] == 'complete' and summary['improved_cases'] == expected_count
        for name in ('candidates', 'results', 'manifest'):
            assert sha(complete/(name+'.json')) == summary[name+'_sha256']
        manifest = json.loads((complete/'manifest.json').read_bytes())
        records = json.loads((complete/'results.json').read_bytes())
        candidates = json.loads((complete/'candidates.json').read_bytes())
        assert len(candidates) == expected_count
        frozen = {name: copy(complete/name, out/name) for name in ('summary.json','manifest.json','results.json','candidates.json')}
        sources = {path: copy(path, out/'source'/Path(path).name, digest)
                   for path,digest in manifest['source_hashes'].items()}
        selected, bindings = [], []
        for n,candidate in sorted(candidates.items(), key=lambda x:int(x[0])):
            record = next(r for r in records if r['job'] == candidate['provenance']['job'])
            assert record['n'] == int(n) and record['certificate'] == candidate['certificate']
            assert record['parent_geometry_sha256'] == candidate['provenance']['parent_geometry_sha256']
            archive = Path(record['retained_archive'])
            with np.load(archive, allow_pickle=False) as z: pose = z[record['archive_key']]
            candidate_check(candidate, pose, record['geometry_sha256'])
            command = record['command']; inp = Path(command[command.index('--in')+1]); native_out = Path(command[command.index('--out')+1])
            parent = inp.with_suffix('.parent.npz')
            parent_check(parent, int(n), record['parent_geometry_sha256'], inp)
            files = []
            for path,digest in [(inp,record['input_sha256']), (parent,record['parent_archive_sha256']),
                    (native_out,record['native_output_sha256']), (native_out.with_suffix('.log'),record['log_sha256']),
                    (native_out.with_suffix('.stdout'),record['stdout_sha256']), (native_out.with_suffix('.stderr'),record['stderr_sha256']),
                    (archive,record['retained_archive_sha256'])]:
                files.append(copy(path,out/'selected'/path.name,digest))
            files.append(copy(archive.with_suffix('.json'),out/'selected'/archive.with_suffix('.json').name))
            for key in ('raw_returned','decoded_returned'):
                item=record[key]; path=Path(item['path'])
                with np.load(path,allow_pickle=False) as z:
                    assert any(geometry_sha(z[k]) == item['geometry_sha256'] for k in z.files)
                files.append(copy(path,out/key/path.name,item['sha256']))
            selected.append(record)
            bindings.append(dict(n=int(n),job=record['job'],geometry_sha256=record['geometry_sha256'],
                parent_geometry_sha256=record['parent_geometry_sha256'],parent_input_exact=True,files=files))
        save(out/'selected-records.json',selected);save(out/'selected-bindings.json',bindings)
        groups[label] = candidates
        evidence[label] = dict(summary=summary,manifest=manifest,frozen_evidence=frozen,
            numerical_sources=sources,selected_trial_records=selected,selected_native_bindings=bindings)

    for n in (858,995):
        label = f'trace{n}'; source=ROOT/f'artifacts/fq-rigid-timeout-trace-n{n}-v1'; out=RECIPE/'native-ancestry'/label
        manifest=json.loads((source/'manifest.json').read_bytes())
        result=json.loads((source/('certification.json' if n==858 else 'result.json')).read_bytes())
        candidates=json.loads((source/'candidates.json').read_bytes());candidate=candidates[str(n)]
        assert result['valid'] and result['certificate'] == candidate['certificate']
        assert sha(source/'manifest.json') == result['manifest_sha256']
        assert sha(source/'candidates.json') == result['candidates_sha256']
        assert sha(source/'native.out') == result['native_output_sha256']
        assert sha(source/'certified.npz') == result['certified_npz_sha256']
        assert sha(source/'native.in') == manifest['input_sha256']
        assert sha(source/'parent.npz') == manifest['parent_archive_sha256']
        assert sha(source/'fq') == manifest['binary_sha256']
        assert sha(source/'diagnostic.py') == manifest['diagnostic_source_sha256']
        parent_check(source/'parent.npz',n,manifest['parent_geometry_sha256'],source/'native.in')
        candidate_check(candidate,one_pose(source/'certified.npz'),result['geometry_sha256'])
        observed=json.loads((source/('summary.json' if n==858 else 'result.json')).read_bytes())
        for name,digest in observed['files'].items(): assert sha(source/name) == digest
        files={p.name:copy(p,out/p.name) for p in sorted(source.iterdir()) if p.is_file() and p.name!='fq'}
        groups[label]=candidates
        evidence[label]=dict(manifest=manifest,result=result,observed_execution=observed,files=files,
            binary_sha256=manifest['binary_sha256'],parent_input_exact=True,
            timing_scope=('995 returned in 27.04627368299407 seconds under lighter observed load and a 60-second cap; '
                'this does not establish that the 60-second cap caused the gain.' if n==995 else
                '858 returned in 12.403579212004843 seconds with unchanged numerical settings and observational tracing.'))

    all_cases=set().union(*(set(c) for c in groups.values()));assert len(all_cases)==30
    rows={n:[] for n in all_cases}
    with RAW.open(newline='') as stream:
        for row in csv.DictReader(stream):
            if row['n'] in rows: rows[row['n']].append([Decimal(row[k])for k in ('x','y','angle')])
    selection={}
    for n,values in rows.items():
        matching=[label for label,c in groups.items() if n in c and values == [[Decimal(str(v))for v in q]for q in c[n]['squares']]]
        assert len(matching)==1,(n,matching)
        selection[n]=matching[0]
    save(RECIPE/'actual-final-case-source-selection.json',selection)
    parent_manifest=json.loads((PARENT/'export_manifest.json').read_bytes())
    assert sha(PARENT/'additional-source-provenance.json')==parent_manifest['additional_source_provenance_sha256']
    copy(PARENT/'additional-source-provenance.json',RECIPE/'inherited-b84f-provenance.json')
    for directory in sorted(PARENT.glob('source-notices-*')): shutil.copytree(directory,RECIPE/directory.name)
    native_notices={}
    for name in ('LICENSE','NOTICE','SOURCE_MANIFEST.json'):
        path=ROOT/'vendor/fq'/name
        if path.exists(): native_notices[name]=dict(**copy(path,RECIPE/'native-notices'/name),content=path.read_bytes().decode('utf8'))
    additional=dict(kind='complete_timeout_return_native_ancestry',
        inherited_parent_recipe='../candidate-b84f2ff20f3e/',inherited_parent_export_version=1,
        inherited_parent_additional_provenance=parent_manifest['additional_source_provenance'],
        inherited_parent_additional_provenance_sha256=parent_manifest['additional_source_provenance_sha256'],
        native_source_commit='659ee62e4a9d39542a1146e8b011cc3ab6407ede',native_notices=native_notices,
        groups=evidence,actual_final_case_source_selection=selection,
        actual_final_raw_csv_sha256=sha(RAW),actual_final_safe_csv_sha256=sha(SAFE),
        scope='Thirty selected certified cases:858 trace,7 timeout16,21 remainder,995 trace. '
              'Exact inherited notices and source ancestry retained. No exporter optimization, certification or scaling.')
    save(RECIPE/'additional-source-provenance.json',additional)
    for source,target in [('merged-fq-timeout-all-v1.validation.json','independent-validation.json'),
        ('merged-fq-timeout-all-v1-official.json','raw-official.json'),
        ('submission-fq-timeout-all-v1-safe-official.json','safe-official.json'),
        ('submission-fq-timeout-all-v1-safe-roundtrip-official.json','roundtrip-official.json'),
        ('submission-fq-timeout-all-v1-safe.transport-validation.json','transport-validation.json'),
        ('current-best-portfolio.json','current-best-portfolio.json')]: copy(ROOT/'artifacts'/source,RECIPE/target)
    assert json.loads((RECIPE/'current-best-portfolio.json').read_bytes())['safe']['sha256']==SAFE_SHA
    copy(Path(__file__),RECIPE/'prepare-provenance.py')
    print(json.dumps(dict(recipe=str(RECIPE),selected_cases=len(selection),
        additional_bytes=(RECIPE/'additional-source-provenance.json').stat().st_size,
        additional_sha256=sha(RECIPE/'additional-source-provenance.json'))))


if __name__=='__main__': main()
