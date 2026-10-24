#!/usr/bin/env python3
"""Merge per-puzzle candidates using interval validation and exact CSV text.

The baseline must be complete. A cached baseline certificate is used only when
its SHA-256 matches. Candidate coordinates retain their original decimal text.
Every replacement must be independently certified valid and strictly improve
the certified side bound. No unverified candidate is emitted.
"""
from __future__ import annotations
import argparse
import csv
from fractions import Fraction
import hashlib
import json
import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from validate_submission import Square, decimal, read_submission, validate_puzzle, _fraction_decimal


def quick_side(squares):
    q = np.asarray([[float(s.x), float(s.y), float(s.angle)] for s in squares])
    h = (np.abs(np.cos(q[:, 2])) + np.abs(np.sin(q[:, 2]))) / 2
    return float(((q[:, :2] + h[:, None]).max(axis=0) -
                  (q[:, :2] - h[:, None]).min(axis=0)).max())


def candidate_file(path):
    """Read partial candidate CSV/JSON, preserving decimals and rejecting bad IDs."""
    if path.suffix == '.json':
        raw = json.loads(path.read_text())
        result = {}
        for key, value in raw.items():
            n = int(key)
            squares = [Square(*(decimal(str(v)) for v in q)) for q in value['squares']]
            if 1 <= n <= 1000 and len(squares) == n:
                result[n] = squares
        return result
    groups = {}
    bad = set()
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            n = int(row['n'])
            if not 1 <= n <= 1000:
                continue
            try:
                sid = int(row['square_id'])
                group = groups.setdefault(n, {})
                if sid in group or not 0 <= sid < n:
                    raise ValueError('duplicate or invalid square_id')
                group[sid] = Square(*(decimal(row[k]) for k in ('x', 'y', 'angle')))
            except (ValueError, KeyError, TypeError):
                bad.add(n)
    return {n: [group[k] for k in range(n)] for n, group in groups.items()
            if n not in bad and set(group) == set(range(n))}


def choose_one(job):
    n, incumbent, certificate, alternatives = job
    if certificate is None:
        certificate = validate_puzzle(n, incumbent)
    if not certificate['valid']:
        raise ValueError(f'Baseline puzzle {n} invalid: {certificate}')
    source = 'baseline'
    rejected = []
    # The approximate side is ordering only; final replacement uses certified intervals.
    for _, candidate_source, candidate in sorted(alternatives, key=lambda r: r[0]):
        candidate_certificate = validate_puzzle(n, candidate)
        if not candidate_certificate['valid']:
            rejected.append({'source': candidate_source, 'certificate': candidate_certificate})
            continue
        if Fraction(candidate_certificate['side_upper']) < Fraction(certificate['side_lower']):
            incumbent, certificate, source = candidate, candidate_certificate, candidate_source
    return n, incumbent, certificate, source, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('candidates', nargs='*', type=Path)
    parser.add_argument('--baseline-report', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    base = read_submission(args.baseline)
    with args.baseline.open('rb') as stream:
        baseline_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    certificates = {}
    if args.baseline_report:
        report = json.loads(args.baseline_report.read_text())
        if report.get('valid') and report.get('sha256') == baseline_digest:
            certificates = {r['n']: r for r in report['results']}
            print('Reusing SHA-256 matched baseline certificate', flush=True)
        else:
            print('Baseline certificate mismatch; recomputing', flush=True)
    approximate = {n: quick_side(squares) for n, squares in base.items()}
    candidates = {n: [] for n in base}
    input_metadata = []
    for path in args.candidates:
        source = str(path)
        data = candidate_file(path)
        considered = 0
        for n, squares in data.items():
            side = quick_side(squares)
            if side < approximate[n] - 1e-11:
                candidates[n].append((side, source, squares))
                considered += 1
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        input_metadata.append({'path': source, 'sha256': digest, 'puzzles': len(data), 'considered': considered})
        print(f'{source}: {considered} promising puzzles', flush=True)
    jobs = [(n, q, certificates.get(n), candidates[n]) for n, q in base.items()]
    results = {}
    with Pool(args.workers) as pool:
        for n, squares, certificate, source, rejected in pool.imap_unordered(choose_one, jobs, chunksize=4):
            results[n] = (squares, certificate, source, rejected)
            if len(results) % 100 == 0:
                print(f'Processed {len(results)}/1000 puzzles', flush=True)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    temporary = args.output.with_suffix('.part')
    with temporary.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['id', 'n', 'square_id', 'x', 'y', 'angle'])
        rid = 0
        for n in sorted(results):
            for sid, q in enumerate(results[n][0]):
                writer.writerow([rid, n, sid, q.x, q.y, q.angle])
                rid += 1
    temporary.replace(args.output)
    with args.output.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    certs = [results[n][1] for n in sorted(results)]
    score_low = sum(Fraction(r['score_lower']) for r in certs)
    score_high = sum(Fraction(r['score_upper']) for r in certs)
    sources = {str(n): results[n][2] for n in sorted(results)}
    rejected = {str(n): results[n][3] for n in sorted(results) if results[n][3]}
    report = {'submission': str(args.output), 'sha256': digest, 'valid': True,
              'baseline': {'path': str(args.baseline), 'sha256': baseline_digest,
                           'certificate': str(args.baseline_report) if args.baseline_report else None},
              'puzzles': len(results), 'rows': rid, 'invalid': [], 'results': certs,
              'score_lower': _fraction_decimal(score_low, False),
              'score_upper': _fraction_decimal(score_high, True),
              'sources': sources, 'inputs': input_metadata, 'rejected_candidates': rejected}
    args.output.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    changed = sum(s != 'baseline' for s in sources.values())
    print(f'CERTIFIED MERGE: {changed} improvements; {len(rejected)} cases had rejected candidates; '
          f'score {float((score_low+score_high)/2):.12f}', flush=True)


if __name__ == '__main__':
    main()
