#!/usr/bin/env python3
"""Audit high-precision packing cases after ordinary pandas numeric CSV I/O."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

from score_official import digest, load_metric, OFFICIAL_SHA256, ROOT


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('submission', type=Path)
    ap.add_argument('--official-report', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=2)
    args = ap.parse_args()
    exact = pd.read_csv(args.submission, dtype=str, keep_default_na=False)
    raw_report = json.loads(args.official_report.read_text())
    input_hash = digest(args.submission)
    if input_hash != raw_report['sha256'] or raw_report['metric_sha256'] != OFFICIAL_SHA256:
        raise ValueError('mismatched official source/input report')
    selected = sorted(exact.loc[exact[['x','y','angle']].map(len).max(axis=1) > 50, 'n'].astype(int).unique().tolist())
    numeric = pd.read_csv(args.submission)
    metric = load_metric(ROOT / 'research/official_metric_v17.py')
    metric.KAGGLE_CORES = args.workers
    numeric = numeric[numeric['n'].isin(selected)]
    puzzles = metric._parse_submission_csv(numeric.drop(columns=['id']).to_csv(index=False))
    print(f'Checking {len(selected)} high-precision cases after pandas float64 roundtrip', flush=True)
    roundtrip_score, outcomes = metric._evaluate_puzzles_parallel(puzzles, set(selected))
    raw = {r['n']: r for r in raw_report['results']}
    raw_selected = sum(raw[n]['score'] for n in selected)
    invalid = []
    results = []
    for n, score, side, reason in outcomes:
        result = {'n':n,'raw_score':raw[n]['score'],'roundtrip_score':score,
                  'side':side,'reason':reason,'score_penalty':score-raw[n]['score']}
        results.append(result)
        if side is None:
            invalid.append(result)
    penalty = roundtrip_score-raw_selected
    report = {'input':str(args.submission),'sha256':input_hash,'metric_sha256':OFFICIAL_SHA256,
              'pandas_version':pd.__version__,'selected_cases':selected,'selected_count':len(selected),
              'numeric_dtypes':{k:str(v) for k,v in numeric.dtypes.items()},
              'invalid_count':len(invalid),'invalid':invalid,'results':results,
              'raw_selected_score':raw_selected,'roundtrip_selected_score':roundtrip_score,
              'score_penalty':penalty,'raw_full_score':raw_report['score'],
              'full_score_if_only_these_cases_roundtrip':raw_report['score']+penalty}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Roundtrip invalid {len(invalid)}/{len(selected)}; score penalty {penalty:.15f}',flush=True)
    print('Invalid cases:',[r['n'] for r in invalid])
    print('Report:',args.report)


if __name__ == '__main__':
    main()
