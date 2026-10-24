#!/usr/bin/env python3
"""Exact SAFE row patches over the verified 680e version1; no new scaling."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from types import FunctionType
import build_incremental_safe_export_job as base

ROOT = Path(__file__).resolve().parents[1]
PARENT_REF = 'sos54352/squares-portfolio-680e332bc6bc-incremental/1'
PARENT_SHA = '680e332bc6bc5bb7d741505b9460ca18fb410ce11929342e67fb2262b20a2d74'
PARENT_JOB = 'artifacts/portfolio-680e332bc6bc-incremental-export-job'
PARENT_CSV = 'artifacts/submission-fq-timeout-all-v1-safe.csv'
PINS = {
    'scripts/build_incremental_safe_export_job.py': '477ef6ddcce7675e7e603678e488b3235b4de5988180adffe1c38e2b13131f0b',
    PARENT_CSV: PARENT_SHA,
    PARENT_CSV.replace('.csv', '-official.json'): '558427933ed9977b098f7378187ba64363b9a8d33a9d1da276b5951f0c83d326',
    PARENT_CSV.replace('.csv', '.transport-validation.json'): '635aa9f44538930c89fb3595fabac91c807e094699d71604dea2f95521a60d2c',
    PARENT_JOB+'/completion-proof.json': 'd427ff816575fea9e303d360e6c74a459b44aa4619c8931dc79bf5dc38c33f72',
    PARENT_JOB+'/export_manifest.json': 'c4680b9936b556f0e7501f65626407523ab94360c31c689baebf5b2dc3efe90c',
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
