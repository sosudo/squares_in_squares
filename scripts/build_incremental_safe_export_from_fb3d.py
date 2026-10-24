#!/usr/bin/env python3
"""Exact SAFE row patches over the verified fb3d version1; no new scaling."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from types import FunctionType
import build_incremental_safe_export_job as base

ROOT = Path(__file__).resolve().parents[1]
PARENT_REF = 'sos54352/squares-portfolio-fb3d0bae17af-incremental/1'
PARENT_SHA = 'fb3d0bae17af84aa941cdc2ad9f8db942b1f2bd2940d063d79d6e1a28c350e8d'
PARENT_JOB = 'artifacts/portfolio-fb3d0bae17af-incremental-export-job'
PARENT_CSV = 'artifacts/submission-fq-gpu-polish-final-v1-safe.csv'
PINS = {
    'scripts/build_incremental_safe_export_job.py': '477ef6ddcce7675e7e603678e488b3235b4de5988180adffe1c38e2b13131f0b',
    PARENT_CSV: PARENT_SHA,
    PARENT_CSV.replace('.csv', '-official.json'): '35a41212d5ba478b8049816bcdb95046147eb81f3de93c87e4471bd8b9e1627b',
    PARENT_CSV.replace('.csv', '.transport-validation.json'): 'ad2bb871b4039524542b46c5773e83bf2a8912b1a4ea2905e804594b844da406',
    PARENT_JOB+'/completion-proof.json': '813abe4ab11d3e53f205c5fcd089540ed7db768d05775e5d165ebe4b4beb7ae7',
    PARENT_JOB+'/export_manifest.json': 'ca931fe73d23b85c0019c4fd7be9d44bd14943f46d0820f015edaed39cffe8c4',
}


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
