#!/usr/bin/env python3
"""Exact SAFE row patches over the verified 631b version1; no new scaling."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from types import FunctionType
import build_incremental_safe_export_job as base

ROOT = Path(__file__).resolve().parents[1]
PARENT_REF = 'sos54352/squares-portfolio-631b3114e7f3-incremental/1'
PARENT_SHA = '631b3114e7f3afeb0da5411115b69a41995a916bb04a72c46350115501514d60'
PARENT_JOB = 'artifacts/portfolio-631b3114e7f3-incremental-export-job'
PARENT_CSV = 'artifacts/submission-fq-lp100-final-v1-safe.csv'
PINS = {'scripts/build_incremental_safe_export_job.py': '477ef6ddcce7675e7e603678e488b3235b4de5988180adffe1c38e2b13131f0b',
 'artifacts/submission-fq-lp100-final-v1-safe.csv': '631b3114e7f3afeb0da5411115b69a41995a916bb04a72c46350115501514d60',
 'artifacts/submission-fq-lp100-final-v1-safe-official.json': 'f34c06f54f8ebc87e42357e33b23f028384a22fab8bec26f4dcc3c3a8ad0873e',
 'artifacts/submission-fq-lp100-final-v1-safe.transport-validation.json': 'dc64dffbd2fa4300055c86f28d6fbcef73bf1b91d9875640d7a64342a6c30213',
 'artifacts/portfolio-631b3114e7f3-incremental-export-job/completion-proof.json': '9573d399d9ddd2519e2c9841d83ede1d7ae768436ec9b8465076b8f022553e01',
 'artifacts/portfolio-631b3114e7f3-incremental-export-job/export_manifest.json': '4f6ee80b2b29fdb01542b8376d3b6f88f8552912ffe4101868b80ca7bac07c60'}


def checked_bytes(path, expected):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Pinned parent/source bytes differ: {path}')
    return data


def verify_parent_and_inheritance(additional_path):
    pinned = {p: checked_bytes(ROOT/p, digest) for p, digest in PINS.items()}
    parent = json.loads(pinned[PARENT_JOB+'/export_manifest.json'])
    completion = json.loads(pinned[PARENT_JOB+'/completion-proof.json'])
    if not (completion['version'] == 1 and completion['ref']+'/1' == PARENT_REF
            and completion['output_sha256'] == PARENT_SHA and completion['is_private']
            and completion['status'] == 'complete' and completion['competition_sources'] == ['squares-in-squares']
            and not any(completion[k] for k in ('enable_gpu', 'enable_tpu', 'enable_internet'))):
        raise ValueError('Exact private offline competition-attached parent required')
    additional = json.loads(Path(additional_path).read_bytes())
    if (additional.get('inherited_parent_additional_provenance') != parent['additional_source_provenance']
            or additional.get('inherited_parent_additional_provenance_sha256') != parent['additional_source_provenance_sha256']):
        raise ValueError('Complete exact parent additional provenance and notices required')


def notebook_metadata(slug):
    metadata = base.notebook_metadata(slug)
    metadata['kernel_sources'] = [PARENT_REF]
    metadata['competition_sources'] = ['squares-in-squares']
    return metadata


def isolated_builder():
    namespace = dict(base.build.__globals__)
    namespace.update(PARENT_REF=PARENT_REF, PARENT_SHA=PARENT_SHA, notebook_metadata=notebook_metadata)
    return FunctionType(base.build.__code__, namespace, base.build.__name__, base.build.__defaults__, base.build.__closure__)


def build(args):
    verify_parent_and_inheritance(args.additional_provenance)
    args.parent = ROOT/PARENT_CSV
    args.parent_report = ROOT/PARENT_CSV.replace('.csv', '-official.json')
    args.parent_transport = ROOT/PARENT_CSV.replace('.csv', '.transport-validation.json')
    args.parent_export_job = ROOT/PARENT_JOB
    report = isolated_builder()(args)
    (args.out/'wrapper-proof.json').write_text(json.dumps(dict(
        wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), parent_pins=PINS,
        parent_notebook=PARENT_REF, parent_version=1, builder_code_object_unchanged=True,
        original_builder_globals_unchanged=True, competition_sources=['squares-in-squares'],
        runtime_sha256=hashlib.sha256(base.RUNTIME.encode()).hexdigest(),
        manifest_decoder_sha256=hashlib.sha256(base.COMPRESSED_MANIFEST_RUNTIME.encode()).hexdigest()), indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('target', 'target-report', 'target-transport', 'additional-provenance', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--compress-manifest', action='store_true')
    build(parser.parse_args())
