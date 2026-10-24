#!/usr/bin/env python3
"""Exact SAFE row patches over the verified competition-attached ffa6 version2.

The frozen original builder/runtime stays unchanged. A counted source edit only
accepts the actual version2 parent; initial metadata attaches the competition.
"""
from __future__ import annotations
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import build_incremental_safe_export_job as base

ROOT = Path(__file__).resolve().parents[1]
PARENT_REF = 'sos54352/squares-portfolio-ffa6cf616d4a-incremental/2'
PARENT_SHA = 'ffa6cf616d4ae0fbe0f27dd655e0b31e624b7c014e82537700c71fca78eb563c'
PARENT_JOB = 'artifacts/portfolio-ffa6cf616d4a-incremental-export-job-v2'
PINS = {
    'scripts/build_incremental_safe_export_job.py': '477ef6ddcce7675e7e603678e488b3235b4de5988180adffe1c38e2b13131f0b',
    'artifacts/submission-fq-broad-final-v2-safe.csv': PARENT_SHA,
    'artifacts/submission-fq-broad-final-v2-safe-official.json': '6d91d6e89192b52e566a369a6c217700690d041692707a4f2d4da40afa7a7668',
    'artifacts/submission-fq-broad-final-v2-safe.transport-validation.json': 'bef9ee511de163b58609f24f19c9c2e785b6b5e383f6cbd2452a5fa6ffbc8480',
    PARENT_JOB+'/completion-proof.json': 'e0abff8b8461174f37347950bf3ca258acc9433e374f56fa8b0c797aae4b6ee2',
    PARENT_JOB+'/export_manifest.json': 'e38b5e4df4a5311c66c2220dab7f5026bc929d05677a1860a8f1ea7d68f892aa',
}


def verify_parent_and_inheritance(additional_path):
    pinned = {}
    for path, expected in PINS.items():
        data = (ROOT/path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Pinned parent/source bytes differ: {path}')
        pinned[path] = data
    parent = json.loads(pinned[PARENT_JOB+'/export_manifest.json'])
    completion = json.loads(pinned[PARENT_JOB+'/completion-proof.json'])
    if (completion['version'] != 2 or completion['ref']+'/2' != PARENT_REF
            or completion['competition_sources'] != ['squares-in-squares']
            or completion['enable_gpu'] or completion['enable_tpu'] or completion['enable_internet']):
        raise ValueError('Expected exact private offline competition-attached version2 parent')
    additional = json.loads(Path(additional_path).read_bytes())
    if (additional.get('inherited_parent_additional_provenance') != parent['additional_source_provenance']
            or additional.get('inherited_parent_additional_provenance_sha256') != parent['additional_source_provenance_sha256']):
        raise ValueError('Complete exact parent additional provenance and notices required')


def notebook_metadata(slug):
    metadata = base.notebook_metadata(slug)
    metadata['kernel_sources'] = [PARENT_REF]
    metadata['competition_sources'] = ['squares-in-squares']
    return metadata


def adapted_builder():
    source = inspect.getsource(base.build)
    before = "completion['ref']+'/1'==PARENT_REF and completion['version']==1"
    after = "completion['ref']+'/'+str(completion['version'])==PARENT_REF and completion['version']==2"
    if source.count(before) != 1:
        raise ValueError('Expected exactly one frozen parent-version check')
    source = source.replace(before, after)
    namespace = dict(base.__dict__)
    namespace.update(PARENT_REF=PARENT_REF, PARENT_SHA=PARENT_SHA, notebook_metadata=notebook_metadata)
    exec(compile(source, '<exact-ffa6-version2-parent-builder>', 'exec'), namespace)
    return namespace['build'], source


def build(args):
    verify_parent_and_inheritance(args.additional_provenance)
    args.parent = ROOT/'artifacts/submission-fq-broad-final-v2-safe.csv'
    args.parent_report = ROOT/'artifacts/submission-fq-broad-final-v2-safe-official.json'
    args.parent_transport = ROOT/'artifacts/submission-fq-broad-final-v2-safe.transport-validation.json'
    args.parent_export_job = ROOT/PARENT_JOB
    implementation, source = adapted_builder()
    report = implementation(args)
    (args.out/'adapted-build-function.py').write_text(source)
    (args.out/'wrapper-proof.json').write_text(json.dumps(dict(
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        parent_pins=PINS, parent_notebook=PARENT_REF, parent_version=2,
        counted_builder_edits=1, competition_sources=['squares-in-squares'],
        runtime_sha256=hashlib.sha256(base.RUNTIME.encode()).hexdigest(),
        manifest_decoder_sha256=hashlib.sha256(base.COMPRESSED_MANIFEST_RUNTIME.encode()).hexdigest(),
        adapted_function_sha256=hashlib.sha256(source.encode()).hexdigest(),
        original_builder_unchanged=True), indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('target', 'target-report', 'target-transport', 'additional-provenance', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--compress-manifest', action='store_true')
    build(parser.parse_args())
