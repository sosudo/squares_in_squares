"""Read-only reranking of a pinned exposure audit toward new ALM treatment.

No native program, GPU, optimizer, or geometry certificate is invoked.
"""
import os
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np
from fq_active_pilot import encode
from prepare_current_full_alm_exposure import gsha, sha, save

REPORT_SHA = 'e7a5ee469de5b03fc6780b5aba4c76179f1ab042ede304415b7678aef04bf463'


def classify(row):
    alm = [h for h in row['history'] if h['treatment'] in
           ('rigid_ALM45_LP20_flip0', 'full_ALM45_LP100_flip16', 'modified_ALM', 'other_ALM')]
    exact = [h for h in alm if h['exact_encoded_input_match'] or h['exact_parent_geometry_match']]
    equivalent = [h for h in alm if h['ordered_D4_input_equivalence']]
    matching = list({(h['path'],h['index']): h for h in exact + equivalent}.values())
    returned = [h for h in matching if h['native_returned']]
    certified = [h for h in returned if h['status'] == 'certified']
    output = [h for h in alm if h['exact_output_geometry_match']]
    if returned:
        category = 'matching_ALM_input_native_returned'
    elif matching:
        category = 'matching_ALM_input_attempt_no_return'
    elif output:
        category = 'current_is_prior_ALM_output_only'
    elif alm:
        category = 'current_unexposed_but_other_pose_ALM_history'
    else:
        category = 'no_same_case_ALM_command_in_corpus'
    return dict(category=category, exact_ALM_input_rows=len(exact), conservative_D4_ALM_input_rows=len(equivalent),
                matching_ALM_native_returned=len(returned), matching_ALM_certified=len(certified),
                matching_ALM_uncertified_returned=len(returned)-len(certified),
                matching_ALM_attempt_no_return=len(matching)-len(returned), exact_ALM_output_rows=len(output),
                same_case_ALM_rows=len(alm))


def main(args):
    started = time.monotonic(); assert sha(args.audit) == REPORT_SHA
    audit = json.loads(args.audit.read_text())
    for entry in audit['corpus']:
        if entry.get('missing'): continue
        assert sha(entry['path']) == entry['sha256']
        for manifest in entry['manifests']:
            assert sha(manifest['path']) == manifest['sha256']
    raw = audit['baseline']; assert sha(raw['path']) == raw['sha256']
    assert sha(raw['official_report']) == raw['official_report_sha256']
    args.out.mkdir(parents=True, exist_ok=False); (args.out/'inputs').mkdir()
    categories = Counter(); rows = []
    for original in audit['all_positive_rows']:
        row = dict(original); row['ALM_exposure'] = classify(row)
        if not row['exclusions']:
            categories[row['ALM_exposure']['category']] += 1
        rows.append(row)
    selected = [r for r in rows if not r['exclusions'] and r['ALM_exposure']['category'] == 'no_same_case_ALM_command_in_corpus'][:24]
    assert len(selected) == 24 and all(not any('ALM' in h['treatment'] for h in r['history']) for r in selected)
    selected_n = {r['n'] for r in selected}; poses = {n: [] for n in selected_n}
    row_hashes = {n: hashlib.sha256() for n in selected_n}
    with Path(raw['path']).open(newline='') as stream:
        header=stream.readline()
        n_column=next(csv.reader([header])).index('n')
        for line in stream:
            n=int(next(csv.reader([line]))[n_column])
            if n not in selected_n: continue
            r=next(csv.DictReader([header,line])); poses[n].append((int(r['square_id']),[float(r[k]) for k in ('x','y','angle')]))
            row_hashes[n].update(line.encode())
    poses={n:np.asarray([q for _,q in sorted(values)],dtype='<f8') for n,values in poses.items()}
    for row in selected:
        n=row['n']; assert poses[n].shape==(n,3) and gsha(poses[n])==row['geometry_sha256']
        assert row_hashes[n].hexdigest()==row['raw_case_rows_sha256']
        encoded,offset=encode(poses[n],math.isqrt(n),math.isqrt(n)); assert offset==[0,0]
        path=args.out/'inputs'/f'n{n}.in';path.write_text(encoded)
        assert sha(path)==row['native_input_sha256']
        for h in row['history']:
            if h['actual_input_sha256']:
                assert sha(h['input_path'])==h['actual_input_sha256']
    np.savez_compressed(args.out/'inputs/current-poses.npz',**{str(n):p for n,p in poses.items()})
    prior_outputs=[r['n'] for r in rows if not r['exclusions'] and r['ALM_exposure']['category']=='current_is_prior_ALM_output_only']
    other_poses=[r['n'] for r in rows if not r['exclusions'] and r['ALM_exposure']['category']=='current_unexposed_but_other_pose_ALM_history']
    report=dict(kind='read_only_new_ALM_treatment_proposal', baseline=raw, pointer_sha256=audit['pointer_sha256'],
        parent_audit_path=str(args.audit),parent_audit_sha256=REPORT_SHA,source_sha256=sha(__file__),
        history_trials=audit['history_trials'],corpus=audit['corpus'],scopes=audit['scopes'],
        selection_rule='Positive dated headroom; exclude active/closed/fresh18/concurrent alternative24; prioritize no same-case ALM command in the explicit corpus, then descending dated headroom.',
        nonexcluded_category_counts=dict(categories), current_unexposed_without_ALM_output=categories['no_same_case_ALM_command_in_corpus']+categories['current_unexposed_but_other_pose_ALM_history'],
        prior_ALM_output_only_cases=prior_outputs,other_pose_ALM_history_cases=other_poses,
        selected=[r for r in selected], selection=[r['n'] for r in selected],
        selected_dated_score_gap=str(sum(Decimal(r['score_gap']) for r in selected)),
        inputs_archive_sha256=sha(args.out/'inputs/current-poses.npz'),all_positive_rows=rows,
        proposed_flags=['--loosen','1','--outer','45','--pit','100','--flip-top','16'],proposed_seed=9710000,
        proposed_workers=2,proposed_affinity=[2,3],proposed_native_seconds=60,proposed_certificate_seconds=8,
        proposed_work_seconds=880,proposed_whole_seconds=900,proposal_not_authorization=True,
        no_optimization=True,no_geometry_certificates=True,no_gpu=True,seconds=time.monotonic()-started)
    save(args.out/'report.json',report)
    save(args.out/'selection.json',{k:report[k]for k in ('baseline','pointer_sha256','parent_audit_sha256','source_sha256','scopes','selection_rule','nonexcluded_category_counts','selected','selection','selected_dated_score_gap','inputs_archive_sha256')})
    save(args.out/'completion.json',dict(report_sha256=sha(args.out/'report.json'),selection_sha256=sha(args.out/'selection.json'),inputs_sha256=report['inputs_archive_sha256'],seconds=report['seconds'],no_optimization=True))
    for path in args.out.rglob('*'):
        if path.is_file():path.chmod(0o444)
    print(json.dumps(dict(selection=report['selection'],counts=report['nonexcluded_category_counts'],gap=report['selected_dated_score_gap'],seconds=report['seconds'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',type=Path,default=Path('artifacts/current-full-alm-exposure-v1/report.json'))
    parser.add_argument('--out',type=Path,required=True)
    main(parser.parse_args())
