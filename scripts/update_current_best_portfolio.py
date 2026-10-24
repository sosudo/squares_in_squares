#!/usr/bin/env python3
"""Atomically publish an already certified portfolio; never submit it."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

METRIC_SHA = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def certified_record(proof_path):
    proof_path = Path(proof_path).resolve()
    proof = json.loads(proof_path.read_text())
    if proof.get('schema_version') != 2 or proof.get('metric_sha256') != METRIC_SHA:
        raise ValueError('Canonical schema2 proof with the unchanged official metric required')
    if not proof.get('scores_agree_within_1e_10'):
        raise ValueError('Ordinary numeric transport proof failed')
    record = {'schema_version': 1, 'updated_at': datetime.now(timezone.utc).isoformat(),
              'canonical_proof': str(proof_path), 'canonical_proof_sha256': digest(proof_path),
              'metric_sha256': METRIC_SHA, 'competition_submission_performed': False}
    for role, path_key in [('raw', 'raw_source'), ('safe', 'safe_submission'),
                           ('roundtrip', 'roundtrip_submission')]:
        csv_path = Path(proof[path_key]).resolve()
        report_path = csv_path.with_name(csv_path.stem + '-official.json')
        report = json.loads(report_path.read_text())
        if digest(csv_path) != proof[role + '_sha256'] or report.get('sha256') != proof[role + '_sha256']:
            raise ValueError(f'{role} CSV hash differs from its proof')
        if digest(report_path) != proof[role + '_official_report_sha256']:
            raise ValueError(f'{role} official report hash differs')
        if not (report.get('valid') and report.get('invalid_count') == 0
                and report.get('puzzles') == 1000 and report.get('rows') == 500500
                and report.get('metric_sha256') == METRIC_SHA
                and report.get('score') == proof[role + '_score']
                and math.isfinite(report['score'])):
            raise ValueError(f'{role} lacks complete matching official coverage')
        record[role] = {'path': str(csv_path), 'sha256': report['sha256'],
                        'score': report['score'], 'official_report': str(report_path),
                        'official_report_sha256': digest(report_path), 'reuse': report['reuse']}
    difference = abs(record['safe']['score'] - record['roundtrip']['score'])
    if difference > 1e-10 or difference != proof['absolute_score_difference']:
        raise ValueError('Numeric transport score difference is inconsistent')
    interval = proof['composition_merge_provenance']
    if digest(interval['path']) != interval['sha256']:
        raise ValueError('Independent interval merge report changed')
    merged = json.loads(Path(interval['path']).read_text())
    if not merged.get('valid') or merged.get('sha256') != record['raw']['sha256']:
        raise ValueError('Independent interval proof does not match the raw CSV')
    record['independent_report'] = interval
    record['user_submission_score_threshold'] = 22.3
    record['eligible_under_user_score_threshold'] = all(record[k]['score'] < 22.3 for k in ('raw', 'safe', 'roundtrip'))
    return record


def update(proof_path, destination):
    record = certified_record(proof_path)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if destination.exists():
            previous = json.loads(destination.read_text())
            if any(record[k]['score'] > previous[k]['score'] for k in ('raw', 'safe', 'roundtrip')):
                raise ValueError('Refuse to replace the current best with a score regression')
            if all(record[k]['sha256'] == previous[k]['sha256'] for k in ('raw', 'safe', 'roundtrip')):
                return previous
        with tempfile.NamedTemporaryFile('w', dir=destination.parent,
                                         prefix=destination.name + '.', suffix='.incoming', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        try:
            os.replace(temporary, destination)
            descriptor = os.open(destination.parent, os.O_DIRECTORY)
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('canonical_proof', type=Path)
    parser.add_argument('--output', type=Path, default=Path('artifacts/current-best-portfolio.json'))
    args = parser.parse_args()
    result = update(args.canonical_proof, args.output)
    print(json.dumps({'pointer': str(args.output), 'safe_sha256': result['safe']['sha256'],
                      'safe_score': result['safe']['score'], 'roundtrip_score': result['roundtrip']['score']}))
