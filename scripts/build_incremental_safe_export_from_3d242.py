#!/usr/bin/env python3
"""Build exact SAFE row patches over the immutable, verified 3d242 export.

Only the imported builder's two parent constants change, temporarily in this
process. The reviewed runtime, codec, original builder and old recipes stay exact.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import build_incremental_safe_export_job as base

ROOT = Path(__file__).resolve().parents[1]
PARENT_REF = 'sos54352/squares-portfolio-3d242df4547e-incremental/1'
PARENT_SHA = '3d242df4547e32775bdaca393927a43ff2b2c46650e35fafafe13be5d75a3c32'
PARENT_JOB = 'artifacts/portfolio-3d242df4547e-incremental-export-job'
PINS = {
    'scripts/build_incremental_safe_export_job.py': '477ef6ddcce7675e7e603678e488b3235b4de5988180adffe1c38e2b13131f0b',
    'artifacts/submission-fq-broad-gain28-safe.csv': PARENT_SHA,
    'artifacts/submission-fq-broad-gain28-safe-official.json': '902a1b56d152c943eafa1d9743b05de631ae4004367a62fc9f7d03dbe759f6f3',
    'artifacts/submission-fq-broad-gain28-safe.transport-validation.json': 'a5adccc130dbc5596e7103391b9432a0658453df72e6990ca2d004ac01ab2cdd',
    PARENT_JOB+'/completion-proof.json': '3a73a4f1b49e18c8e2483c9b3f453669d728c6f4942850cc0a5a0a775661d1a4',
    PARENT_JOB+'/export_manifest.json': 'cbe2d927674e4f35c4daf93b360109f3b252660781ec2ee6346e1ad71c1c1773',
}


def checked_bytes(path, expected):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Pinned parent/source bytes differ: {path}')
    return data


def verify_parent_and_inheritance(additional_path):
    pinned = {path: checked_bytes(ROOT/path, digest) for path, digest in PINS.items()}
    parent = json.loads(pinned[PARENT_JOB+'/export_manifest.json'])
    additional = json.loads(Path(additional_path).read_bytes())
    if (additional.get('inherited_parent_additional_provenance') != parent['additional_source_provenance']
            or additional.get('inherited_parent_additional_provenance_sha256') != parent['additional_source_provenance_sha256']):
        raise ValueError('Complete exact parent additional provenance and notices required')


def build(args):
    verify_parent_and_inheritance(args.additional_provenance)
    args.parent = ROOT/'artifacts/submission-fq-broad-gain28-safe.csv'
    args.parent_report = ROOT/'artifacts/submission-fq-broad-gain28-safe-official.json'
    args.parent_transport = ROOT/'artifacts/submission-fq-broad-gain28-safe.transport-validation.json'
    args.parent_export_job = ROOT/PARENT_JOB
    previous = base.PARENT_REF, base.PARENT_SHA
    try:
        base.PARENT_REF, base.PARENT_SHA = PARENT_REF, PARENT_SHA
        return base.build(args)
    finally:
        base.PARENT_REF, base.PARENT_SHA = previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('target', 'target-report', 'target-transport', 'additional-provenance', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--compress-manifest', action='store_true')
    build(parser.parse_args())


if __name__ == '__main__':
    main()
