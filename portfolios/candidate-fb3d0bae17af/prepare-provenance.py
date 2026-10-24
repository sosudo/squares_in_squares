#!/usr/bin/env python3
"""Freeze selected LP-return and GPU/native ancestry after canonical adoption."""
from pathlib import Path
from decimal import Decimal
import argparse
import ast
import base64
import csv
import hashlib
import io
import json
import lzma
import shutil
import sys
import zipfile
import prepare_timeout_all_export as a

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'portfolios/candidate-680e332bc6bc'
PARENT_RAW = ROOT/'artifacts/merged-fq-timeout-all-v1.csv'


def read_cases(path, wanted=None):
    result = {}
    with path.open(newline='') as stream:
        for row in csv.DictReader(stream):
            if wanted is None or row['n'] in wanted:
                result.setdefault(row['n'], []).append([Decimal(row[k]) for k in ('x','y','angle')])
    return result


def case_digests(path):
    result={}
    with path.open('rb')as stream:
        next(stream)
        for line in stream:
            n=line.split(b',',2)[1].decode('ascii')
            result.setdefault(n,hashlib.sha256()).update(line)
    return {n:h.hexdigest()for n,h in result.items()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pointer',type=Path,required=True)
    p.add_argument('--campaign',action='append',type=Path,required=True)
    p.add_argument('--gpu-finish',type=Path,required=True)
    args=p.parse_args()
    pointer=json.loads(args.pointer.read_bytes());raw=Path(pointer['raw']['path']);safe=Path(pointer['safe']['path'])
    assert a.sha(raw)==pointer['raw']['sha256'] and a.sha(safe)==pointer['safe']['sha256']
    assert a.sha(pointer['canonical_proof'])==pointer['canonical_proof_sha256']
    assert pointer['eligible_under_user_score_threshold'] and pointer['safe']['score']<22.3 and pointer['roundtrip']['score']<22.3
    recipe=ROOT/('portfolios/candidate-'+pointer['safe']['sha256'][:12]);recipe.mkdir(exist_ok=False);a.RECIPE=recipe
    groups={}
    for path in args.campaign:
        candidates=json.loads((path/'candidates.json').read_bytes());summary=json.loads((path/'summary.json').read_bytes())
        assert summary['status']=='complete' and a.sha(path/'candidates.json')==summary['candidates_sha256']
        groups[path.parent.name]=dict(root=path,candidates=candidates,gpu=False)
    gpu=args.gpu_finish;summary=json.loads((gpu/'summary.json').read_bytes())
    assert summary['status']=='complete' and a.sha(gpu/'candidates.json')==summary['candidates_sha256']
    groups['gpu-native-finish']=dict(root=gpu,candidates=json.loads((gpu/'candidates.json').read_bytes()),gpu=True)
    all_cases=set().union(*(set(x['candidates'])for x in groups.values()))
    old=case_digests(PARENT_RAW);new=case_digests(raw);assert set(old)==set(new)
    changed={n for n in new if new[n]!=old[n]};current=read_cases(raw,changed)
    assert changed and changed<=all_cases
    selection={}
    for n in changed:
        matches=[label for label,x in groups.items()if n in x['candidates'] and current[n]==[
            [Decimal(str(v))for v in row]for row in x['candidates'][n]['squares']]]
        assert len(matches)==1,(n,matches);selection[n]=matches[0]
    evidence={}
    for label,group in groups.items():
        source=group['root'];selected_cases=[n for n in selection if selection[n]==label]
        if not selected_cases:continue
        out=recipe/'new-native-ancestry'/label
        summary=json.loads((source/'summary.json').read_bytes());manifest=json.loads((source/'manifest.json').read_bytes())
        assert a.sha(source/'manifest.json')==summary['manifest_sha256']
        assert a.sha(source/'results.json')==summary['results_sha256']
        records=json.loads((source/'results.json').read_bytes())
        files={name:a.copy(source/name,out/name)for name in ('candidates.json','results.json','summary.json','manifest.json')}
        selected=[];bindings=[]
        for n in selected_cases:
            candidate=group['candidates'][n];identifier='slot'if group['gpu']else'job'
            record=next(r for r in records if r[identifier]==candidate['provenance'][identifier])
            assert record['n']==int(n) and record['certificate']==candidate['certificate']
            archive=Path(record['certified_archive']if group['gpu']else record['retained_archive'])
            digest=record['certified_archive_sha256']if group['gpu']else record['retained_archive_sha256']
            a.candidate_check(candidate,a.one_pose(archive),record['geometry_sha256'])
            command=record['command'];inp=Path(command[command.index('--in')+1]);native=Path(command[command.index('--out')+1])
            parent=Path(record['selected_archive'])if group['gpu']else inp.with_suffix('.parent.npz')
            parent_digest=record['selected_archive_sha256']if group['gpu']else record['parent_archive_sha256']
            parent_geometry=record['selected_geometry_sha256']if group['gpu']else record['parent_geometry_sha256']
            a.parent_check(parent,int(n),parent_geometry,inp)
            bound=[]
            for path,expected in [(parent,parent_digest),(inp,record['input_sha256']),(native,record['native_output_sha256']),
                (native.with_suffix('.log'),record['log_sha256']),(native.with_suffix('.stdout'),record['stdout_sha256']),
                (native.with_suffix('.stderr'),record['stderr_sha256']),(archive,digest)]:
                bound.append(a.copy(path,out/'selected'/path.name,expected))
            certpath=native.with_suffix('.certificate.json')if group['gpu']else archive.with_suffix('.json')
            if certpath.exists():bound.append(a.copy(certpath,out/'selected'/certpath.name))
            for key in ('raw_returned','decoded_returned'):
                item=record[key];path=Path(item['path']);assert a.geometry_sha(a.one_pose(path))==item['geometry_sha256']
                bound.append(a.copy(path,out/key/path.name,item['sha256']))
            selected.append(record);bindings.append(dict(n=int(n),identifier=identifier,value=record[identifier],files=bound,parent_input_exact=True))
        numerical={};notices={}
        if group['gpu']:
            for name,item in manifest['numerical_sources'].items():numerical[name]=a.copy(item['path'],out/'source'/name,item['sha256'])
            for row in manifest['exact_original_slots']:
                if row['slot']['slot']not in [r['slot']for r in selected]:continue
                for kind in ('selected','input','original_record'):
                    item=row[kind];path=Path(item['path']);files[path.name]=a.copy(path,out/'original-selected'/path.name,item['sha256'])
            for name in ('aggregate-download-receipt.json','selected-download-receipt.json','original-finish-manifest.json','original-finish-results.json','independent-winner-lineage-review.json'):
                files[name]=a.copy(source/name,out/name)
            job=ROOT/'artifacts/fq-restart-hop-job-v2'
            files['frozen-gpu-source']=a.copy(job/'search.py',out/'gpu-source.py',manifest['source_sha256'])
            packed={node.targets[0].id:ast.literal_eval(node.value)for node in ast.parse((job/'search.py').read_bytes()).body[:2]}
            with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(packed['PAYLOAD']))))as z:
                for name in z.namelist():
                    if not (any(k in Path(name).name.lower()for k in ('license','notice','source_manifest'))or'vendor/notices/'in name):continue
                    data=z.read(name);digest=hashlib.sha256(data).hexdigest();assert digest==packed['CONFIG']['files'][name]
                    dest=out/'gpu-source-notices'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
                    notices[name]=dict(path=str(dest.relative_to(recipe)),sha256=digest,content=data.decode('utf8'))
            for name in ('build_report.json','independent_delta_review.json','local_import_review.json'):
                files['gpu-'+name]=a.copy(job/name,out/('gpu-'+name))
            packet=ROOT/'artifacts/fq-restart-hop-packet-audit-v1/outputs/case-693/raw-hop/packet-0296.npz'
            files['committed-packet']=a.copy(packet,out/'packet-0296.npz',manifest['last_completed_packet']['sha256'])
        else:
            for path,digest in manifest['source_hashes'].items():numerical[path]=a.copy(path,out/'source'/Path(path).name,digest)
        evidence[label]=dict(summary=summary,manifest=manifest,files=files,numerical_sources=numerical,new_source_notices=notices,selected_trial_records=selected,selected_native_bindings=bindings)
    parent=json.loads((PARENT/'export_manifest.json').read_bytes())
    assert a.sha(PARENT/'additional-source-provenance.json')==parent['additional_source_provenance_sha256']
    a.copy(PARENT/'additional-source-provenance.json',recipe/'inherited-680e-provenance.json')
    for directory in sorted(PARENT.glob('source-notices-*')):shutil.copytree(directory,recipe/directory.name)
    additional=dict(kind='selected_contact_polish_and_retained_GPU_best_native_finish',
        inherited_parent_recipe='../candidate-680e332bc6bc/',inherited_parent_export_version=1,
        inherited_parent_additional_provenance=parent['additional_source_provenance'],
        inherited_parent_additional_provenance_sha256=parent['additional_source_provenance_sha256'],
        groups=evidence,actual_final_case_source_selection=selection,actual_final_raw_csv_sha256=a.sha(raw),actual_final_safe_csv_sha256=a.sha(safe),
        scope='Exact selected certified outputs only. GPU source states remain UNVERIFIED until the retained native-output gates; no claim that proxy energy implies feasibility. No exporter numerical changes or scaling.')
    a.save(recipe/'additional-source-provenance.json',additional);a.save(recipe/'actual-final-case-source-selection.json',selection)
    for source,name in [(pointer['raw']['official_report'],'raw-official.json'),(pointer['safe']['official_report'],'safe-official.json'),
        (pointer['roundtrip']['official_report'],'roundtrip-official.json'),(pointer['independent_report']['path'],'independent-validation.json'),
        (pointer['canonical_proof'],'transport-validation.json'),(args.pointer,'current-best-portfolio.json')]:a.copy(source,recipe/name)
    a.copy(Path(__file__),recipe/'prepare-provenance.py');a.copy(Path(a.__file__),recipe/'prepare-ancestry-helper.py')
    print(json.dumps(dict(recipe=str(recipe),safe_sha256=a.sha(safe),selected_cases=selection,
        additional_sha256=a.sha(recipe/'additional-source-provenance.json'))))


if __name__=='__main__':main()
