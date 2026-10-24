"""Single-source public delta screen with exact text and changed-case gates.

Reuse hash-bound incumbent certificates. Do not merge or mutate the canonical
portfolio. Every emitted winner passes raw and ordinary-pandas official and
independent interval checks, without coordinate modification.
"""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import csv
from fractions import Fraction
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'experiments')]
import pandas as pd
from fq_active_pilot import digest
from fq_variant_campaign import atomic_json
from merge_candidates import candidate_file,quick_side
from score_official import load_metric,OFFICIAL_SHA256,puzzle_hashes
from validate_submission import Square,read_submission,validate_puzzle


def run(source,out):
    started=time.monotonic();out.mkdir(parents=True,exist_ok=False)
    pointer_path=ROOT/'artifacts/current-best-portfolio.json'
    pointer=json.loads(pointer_path.read_text());basepath=Path(pointer['raw']['path'])
    independent=Path(pointer['independent_report']['path']);official=Path(pointer['raw']['official_report'])
    assert digest(basepath)==pointer['raw']['sha256']
    assert digest(independent)==pointer['independent_report']['sha256']
    assert digest(official)==pointer['raw']['official_report_sha256']
    certdata=json.loads(independent.read_text());officialdata=json.loads(official.read_text())
    assert certdata['valid']and officialdata['valid']and certdata['sha256']==officialdata['sha256']==digest(basepath)
    certs={r['n']:r for r in certdata['results']};baseofficial={r['n']:r for r in officialdata['results']}
    base=read_submission(basepath);data=candidate_file(source)
    with source.open(newline='')as stream:
        supplied={int(row['n'])for row in csv.DictReader(stream)}
    if not supplied or not supplied<=set(range(1,1001)) or set(data)!=supplied:
        raise ValueError('Public source has malformed or incomplete supplied case groups')
    missing=sorted(set(base)-supplied)
    rows=[];promising=[]
    for n,squares in sorted(data.items()):
        length=quick_side(squares);current=float(baseofficial[n]['side']);same=squares==base[n]
        row=dict(n=n,candidate_float_side=length,incumbent_official_side=current,exact_coordinate_text_equal=same,
                 estimated_score_gain=(current-length)/math.sqrt(n),screened_promising=not same and length<current-1e-11)
        rows.append(row)
        if row['screened_promising']:promising.append(n)
    screen=dict(source_path=str(source),source_sha256=digest(source),baseline_path=str(basepath),baseline_sha256=digest(basepath),
        pointer_sha256=digest(pointer_path),baseline_independent_report=str(independent),baseline_independent_sha256=digest(independent),
        baseline_official_report=str(official),baseline_official_sha256=digest(official),
        comparison_count=len(data),baseline_cases=1000,source_missing_cases=missing,
        missing_case_policy='No proposal; retain incumbent unchanged.',screen_margin=1e-11,promising=promising,
        estimated_score_gain=sum(r['estimated_score_gain']for r in rows if r['screened_promising']),
        comparisons=rows,source_code_sha256=digest(__file__))
    atomic_json(out/'side-screen.json',screen)
    print(json.dumps(dict(stage='screen',promising=promising,estimated_score_gain=screen['estimated_score_gain'],
                          source_sha256=screen['source_sha256'],seconds=time.monotonic()-started)),flush=True)
    candidates={};raw_certs={};rejected={}
    for n in promising:
        cert=validate_puzzle(n,data[n]);reason=None
        if not cert['valid']:reason='independent_invalid'
        elif Fraction(cert['side_upper'])>=Fraction(certs[n]['side_lower']):reason='not_interval_strict'
        if reason:rejected[str(n)]=dict(reason=reason,certificate=cert)
        else:
            candidates[str(n)]=dict(side=cert['side_upper'],squares=[[q.x,q.y,q.angle]for q in data[n]],
                source=str(source),provenance=dict(source_csv_sha256=screen['source_sha256'],baseline_csv_sha256=screen['baseline_sha256']))
            raw_certs[str(n)]=cert
        atomic_json(out/'independent-candidates.json',candidates);atomic_json(out/'independent-certificates.json',raw_certs)
        print(json.dumps(dict(stage='independent',n=n,valid=cert['valid'],rejection=reason)),flush=True)
    # Ordinary transport is applied only to a separate audit copy.
    raw=out/'winning-candidates.csv';numeric=out/'winning-candidates-roundtrip.csv'
    with raw.open('w',newline='')as stream:
        writer=csv.writer(stream);writer.writerow(['id','n','square_id','x','y','angle']);rid=0
        for key,value in sorted(candidates.items(),key=lambda x:int(x[0])):
            for sid,pose in enumerate(value['squares']):writer.writerow([rid,int(key),sid,*pose]);rid+=1
    records=[];final={}
    if candidates:
        pd.read_csv(raw).to_csv(numeric,index=False)
        metric=load_metric(ROOT/'research/official_metric_v17.py')
        def parse(path):
            frame=pd.read_csv(path,dtype=str,keep_default_na=False)
            return metric._parse_submission_csv(frame.drop(columns=['id']).to_csv(index=False))
        groups=parse(raw);roundtrip=parse(numeric)
        raw_hashes=puzzle_hashes(groups);round_hashes=puzzle_hashes(roundtrip)
        for n,group in sorted(groups.items()):
            a=metric._evaluate_puzzle_worker((n,group));b=metric._evaluate_puzzle_worker((n,roundtrip[n]))
            cert=validate_puzzle(n,[Square(*(r[k]for k in('x','y','angle')))for r in roundtrip[n]])
            row=dict(n=n,raw_official=dict(score=a[1],side=a[2],reason=a[3]),
                roundtrip_official=dict(score=b[1],side=b[2],reason=b[3]),roundtrip_independent=cert,
                raw_row_hash=raw_hashes[n],roundtrip_row_hash=round_hashes[n],
                raw_score_gain=baseofficial[n]['score']-a[1],valid=a[3]==b[3]=='ok'and cert['valid'])
            records.append(row)
            if row['valid']:final[str(n)]=candidates[str(n)]
            else:rejected[str(n)]=dict(reason='official_or_transport_gate_failure',record=row)
            atomic_json(out/'official-winning-cases.json',records);atomic_json(out/'winning-candidates.json',final)
            print(json.dumps(dict(stage='full_changed_case_gates',n=n,valid=row['valid'],score_gain=row['raw_score_gain'])),flush=True)
    else:
        numeric.write_bytes(raw.read_bytes());atomic_json(out/'official-winning-cases.json',records)
        atomic_json(out/'winning-candidates.json',final)
        atomic_json(out/'independent-certificates.json',raw_certs)
    gain=sum(r['raw_score_gain']for r in records if r['valid'])
    summary=dict(status='complete',source_path=str(source),source_sha256=digest(source),
        baseline_path=str(basepath),baseline_sha256=digest(basepath),baseline_official_score=pointer['raw']['score'],
        compared_supplied_cases=len(data),baseline_cases=1000,source_missing_cases=missing,
        promising_cases=promising,fully_certified_cases=sorted(map(int,final)),
        fresh_raw_official_evaluations=len(records),fresh_roundtrip_official_evaluations=len(records),
        fresh_raw_interval_evaluations=len(promising),fresh_roundtrip_interval_evaluations=len(records),
        raw_score_gain=gain,predicted_raw_merged_score=pointer['raw']['score']-gain,rejections=rejected,
        candidate_json_sha256=digest(out/'winning-candidates.json'),raw_interval_report_sha256=digest(out/'independent-certificates.json'),
        raw_csv_sha256=digest(raw),roundtrip_csv_sha256=digest(numeric),official_case_report_sha256=digest(out/'official-winning-cases.json'),
        official_metric_sha256=OFFICIAL_SHA256,source_code_sha256=digest(__file__),seconds=time.monotonic()-started,
        scope='Changed source cases only; root owns full merged portfolio, transport-safe proof and canonical pointer. No submission or canonical mutation.')
    atomic_json(out/'certification-summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    run(args.source.resolve(),args.out.resolve())
