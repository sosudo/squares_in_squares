#!/usr/bin/env python3
"""Build exact SAFE row patches over the immutable, verified 41b46 export.

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
PARENT_REF = 'sos54352/squares-portfolio-41b46b2ebe5d-incremental/1'
PARENT_SHA = '41b46b2ebe5dc5181f8b2e50493d80de24effdbff17cd769dd04220150fa24ec'
PARENT_JOB = 'artifacts/portfolio-41b46b2ebe5d-incremental-export-job'
PINS = {
    'scripts/build_incremental_safe_export_job.py': '477ef6ddcce7675e7e603678e488b3235b4de5988180adffe1c38e2b13131f0b',
    'artifacts/submission-fq-broad-lightning19-v1-safe.csv': PARENT_SHA,
    'artifacts/submission-fq-broad-lightning19-v1-safe-official.json': '21b3e6d21a862d6849c4dfff2373b2b57ba504bd990e34b1d67bc78550b7aa62',
    'artifacts/submission-fq-broad-lightning19-v1-safe.transport-validation.json': '8aff17c0e02904d9f132570cac581e5ab6e559b8cc732dd8705cd75c4186b368',
    PARENT_JOB+'/completion-proof.json': 'd1d85c90e16d519c56a96a7080f8046073cfbb9a44d79b4679670f0a7a047193',
    PARENT_JOB+'/export_manifest.json': 'e04789016afe4484d79d558343d52e7597b70e4f0c7ee1421241352f56cff0e5',
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
    args.parent = ROOT/'artifacts/submission-fq-broad-lightning19-v1-safe.csv'
    args.parent_report = ROOT/'artifacts/submission-fq-broad-lightning19-v1-safe-official.json'
    args.parent_transport = ROOT/'artifacts/submission-fq-broad-lightning19-v1-safe.transport-validation.json'
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
