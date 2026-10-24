#!/usr/bin/env python3
"""Compare a dated public rendered table with a hash-bound official report.

The table contains reported bounds, not coordinates. A gap is targeting
evidence, not a packing, proof of optimality or guaranteed attainable gain.
This reader does not access the notebook's private input dataset.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import re

SOURCE = ('https://www.kaggle.com/code/inversion/'
          'squares-in-squares-per-puzzle-leaderboard?scriptVersionId=361620939')
RENDERED_SHA256 = '440d8f2a3827851a09325c0f42b96c4b0bdf2d9bfcb467ca59a0d54257ac7c45'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reference_rows(rendered_html):
    matches = []
    for match in re.finditer(r'const DATA\s*=\s*', rendered_html):
        try:
            rows, _ = json.JSONDecoder().raw_decode(rendered_html[match.end():])
        except json.JSONDecodeError:
            continue
        if isinstance(rows, list) and len(rows) == 1000:
            matches.append(rows)
    if len(matches) != 1:
        raise ValueError('Expected exactly one complete rendered 1000-case table')
    rows = matches[0]
    if sorted(row['n'] for row in rows) != list(range(1, 1001)):
        raise ValueError('Public reference has missing or duplicated cases')
    for row in rows:
        side = Decimal(row['L'])
        if not side.is_finite() or side <= 0 or side * side < row['n'] - Decimal('1e-40'):
            raise ValueError('Public side fails finite/positive/area sanity')
        if not all(isinstance(row[k], str) for k in ('L', 'team', 'date')):
            raise ValueError('Reference decimal text or attribution missing')
    return rows


def compare(rows, pointer_path, source_html):
    if digest(source_html) != RENDERED_SHA256:
        raise ValueError('Rendered bytes differ from the pinned public v10 reference')
    pointer = json.loads(pointer_path.read_text())
    raw = pointer['raw']
    official_path = Path(raw['official_report'])
    if digest(official_path) != raw['official_report_sha256']:
        raise ValueError('Official report changed after certification')
    official = json.loads(official_path.read_text())
    if (not official['valid'] or official['invalid_count'] != 0
            or official['sha256'] != raw['sha256'] or official['puzzles'] != 1000):
        raise ValueError('Current portfolio lacks complete official coverage')
    details_path = Path(raw['path']).with_name(Path(raw['path']).stem + '-official-details.csv')
    with details_path.open() as stream:
        current_rows = list(csv.DictReader(stream))
    current = {int(row['n']): row['L'] for row in current_rows}
    if len(current_rows) != 1000 or set(current) != set(range(1, 1001)):
        raise ValueError('Official details coverage differs')
    certified_sides = {int(row['n']): row['side'] for row in official['results']}
    if current != certified_sides:
        raise ValueError('Per-case decimal sides differ from the hash-bound report')
    gaps = []
    with localcontext() as context:
        context.prec = 80
        score = sum(Decimal(current[n]) / Decimal(n).sqrt() - 1 for n in current)
        if abs(score - Decimal(str(raw['score']))) > Decimal('1e-10'):
            raise ValueError('Official detail score differs from certified report')
        for row in rows:
            n = row['n']
            delta = Decimal(current[n]) - Decimal(row['L'])
            gaps.append({**row, 'current_L': current[n], 'side_gap': str(delta),
                         'score_gap': str(delta / Decimal(n).sqrt())})
        gaps.sort(key=lambda row: Decimal(row['score_gap']), reverse=True)
        positive_sum = sum(max(Decimal(0), Decimal(row['score_gap'])) for row in gaps)
    return {'kind': 'dated_public_reference_not_coordinates_or_attainability_proof',
            'public_source': SOURCE, 'version': 10, 'session_id': 361620939,
            'reference_evaluated_at': '2026-10-24T00:02:02.353Z',
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'rendered_sha256': digest(source_html), 'current_raw_sha256': raw['sha256'],
            'official_details_sha256': digest(details_path),
            'reference_rows': len(rows), 'sum_positive_gap': str(positive_sum),
            'material_gap_case_count': sum(Decimal(r['score_gap']) > Decimal('1e-8') for r in gaps),
            'gaps': gaps}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, required=True)
    parser.add_argument('--pointer', type=Path, default=Path('artifacts/current-best-portfolio.json'))
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--reference-output', type=Path)
    args = parser.parse_args()
    if args.report.exists() or (args.reference_output and args.reference_output.exists()):
        parser.error('Choose fresh outputs to preserve dated evidence')
    rows = reference_rows(args.html.read_text())
    report = compare(rows, args.pointer, args.html)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    if args.reference_output:
        args.reference_output.parent.mkdir(parents=True, exist_ok=True)
        args.reference_output.write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('reference_rows', 'material_gap_case_count',
                                           'sum_positive_gap', 'current_raw_sha256')}))
