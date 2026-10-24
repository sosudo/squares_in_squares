"""Bind a completed local FQ archive to saved certificates and exact sources.

This audits the existing official evaluations rather than repeating them. It
also takes exact minima over every retained local intermediate and primary
output, so a worse global release cannot hide a better certified local pose.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import signal

import numpy as np

import fq_active_pilot as fq
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha


def require(value, message):
    if not value:
        raise ValueError(message)


def check_pose(key, pose, sha):
    w, h, d = map(int, key.split('_'))
    require(pose.shape == (w*h+d, 3) and np.isfinite(pose).all(), 'Invalid shape or finite coordinates')
    require(geometry_sha(pose) == sha, 'Exact geometry hash mismatch')
    value = fq.bloat(pose, w, h)
    require(0 <= value < 1, 'Certified rectangle is outside the required excess range')
    return value


def check_saved_proof(run, item, sha):
    certificate = item['certificate']
    require(certificate.get('valid') is True and certificate.get('raw_reason') == 'ok'
            and certificate.get('roundtrip_reason') == 'ok'
            and certificate.get('metric_sha256') == fq.OFFICIAL_SHA256,
            'Official certificate is missing or invalid')
    require(item['geometry_sha256'] == sha, 'Proof geometry hash mismatch')
    trace = item['rigid_return_trace']
    log = run/'trials'/f"{item['key']}-{item['mode']}-{item['seed']}.log"
    require(fq.digest(log) == trace['log_sha256'], 'Continuation log hash mismatch')
    values = [float(x) for x in re.findall(r'soft eps ([0-9.eE+-]+) hold', log.read_text())]
    require(trace.get('valid') is True and len(values) == trace['expected_steps']
            and values == trace['reported_aspect_epsilons'] and values[-1] == 0.
            and all(a >= b >= 0 for a, b in zip(values, values[1:])),
            'Saved continuation did not demonstrably return to zero aspect')


def verify(run, output):
    require(not output.exists(), 'Verification output already exists')
    final_pointer = json.loads((run/'final.json').read_text())
    primary = Path(final_pointer['snapshot'])
    analysis = json.loads((primary/'analysis.json').read_text())
    require(fq.digest(primary/'analysis.json') == final_pointer['analysis_sha256'], 'Final pointer mismatch')
    for name in ['best_bank', 'donors', 'results']:
        path = primary/(name+('.json' if name == 'results' else '.npz'))
        require(fq.digest(path) == analysis[name+'_sha256'], 'Primary snapshot hash mismatch')
    manifest = json.loads((run/'manifest.json').read_text())
    require(fq.digest(run/'manifest.json') == analysis['manifest_sha256'], 'Manifest changed')
    require(fq.digest(Path(manifest['frozen_binary_path'])) == manifest['binary_sha256'], 'Binary changed')
    known_sources = set()
    for item in manifest['inputs'].values():
        path = Path(item['snapshot'])
        require(fq.digest(path) == item['sha256'], 'Frozen input changed')
        if path.suffix == '.npz':
            with np.load(path, allow_pickle=False) as archive:
                known_sources.update(geometry_sha(archive[name]) for name in archive.files)
    reference_path = run/'inputs/combined_reference.npz'
    require(fq.digest(reference_path) == manifest['reference_sha256'], 'Frozen reference changed')
    with np.load(reference_path, allow_pickle=False) as archive:
        best = {name: archive[name].copy() for name in archive.files}
    baseline = dict(manifest['reference_excess_by_key'])
    best_values = dict(baseline)
    for key, pose in best.items():
        require(geometry_sha(pose) == manifest['reference_geometry_sha256_by_key'][key], 'Reference geometry changed')
        require(abs(fq.bloat(pose, *map(int, key.split('_')[:2]))-baseline[key]) < 1e-12,
                'Reference objective mismatch')
    complete = run/'all-strict'
    complete_analysis = json.loads((complete/'analysis.json').read_text())
    require(fq.digest(complete/'donors.npz') == complete_analysis['donors_sha256'], 'Complete donor archive changed')
    require(fq.digest(complete/'provenance.json') == complete_analysis['provenance_sha256'], 'Complete provenance changed')
    provenance = json.loads((complete/'provenance.json').read_text())
    with np.load(complete/'donors.npz', allow_pickle=False) as archive:
        poses = {name: archive[name].copy() for name in archive.files}
    require(set(poses) == set(provenance), 'Some retained geometry has no lineage')
    known_sources.update(geometry_sha(pose) for pose in poses.values())
    primary_hashes, intermediate_proofs, best_origins = set(), set(), {}
    lineage_counts = Counter()
    for name, pose in poses.items():
        key = name.split('__')[0]; sha = geometry_sha(pose)
        require(name == key+'__strict_'+sha, 'Stored exact identity does not match its geometry')
        value = check_pose(key, pose, sha)
        for lineage in provenance[name]:
            origin = lineage['origin']; lineage_counts[origin] += 1
            if origin == 'primary':
                item = lineage['record']
                require(item['status'] == 'certified' and abs(item['after']-value) < 1e-12,
                        'Primary output objective/certificate mismatch')
                source = item['parent']['geometry_sha256']
                primary_hashes.add((key, sha))
            elif origin == 'strict_intermediate':
                item = lineage['proof']
                proof_path = Path(lineage['proof_path'])
                require(fq.digest(proof_path) == lineage['proof_sha256'], 'Intermediate proof changed')
                require(json.loads(proof_path.read_text()) == item, 'Intermediate proof content mismatch')
                path = Path(item['archive_path'])
                require(fq.digest(path) == item['archive_sha256'], 'Intermediate archive changed')
                with np.load(path, allow_pickle=False) as archive:
                    require(len(archive.files) == 1 and geometry_sha(archive[archive.files[0]]) == sha,
                            'Intermediate geometry mismatch')
                source = item['source_geometry_sha256']
                intermediate_proofs.add(proof_path.resolve())
            else:
                raise ValueError('Unknown certificate lineage')
            require(item['key'] == key and source in known_sources, 'Unknown or mismatched source geometry')
            check_saved_proof(run, item, sha)
        if value < best_values[key]:
            best[key], best_values[key], best_origins[key] = pose.copy(), value, name
    with np.load(primary/'donors.npz', allow_pickle=False) as archive:
        expected = {(name.split('__')[0], geometry_sha(archive[name])) for name in archive.files}
    require(primary_hashes == expected, 'Primary outputs were omitted from the complete union')
    expected_proofs = {path.resolve() for path in (run/'trials').glob('*-strict-intermediate.json')}
    require(intermediate_proofs == expected_proofs, 'Certified local intermediates were omitted')
    output.mkdir(parents=True)
    shutil.copyfile(complete/'donors.npz', output/'donors.npz')
    shutil.copyfile(complete/'provenance.json', output/'provenance.json')
    atomic_npz(output/'best_bank.npz', best)
    report = {
        'run': str(run), 'primary_snapshot': str(primary),
        'primary_analysis_sha256': fq.digest(primary/'analysis.json'),
        'complete_analysis_sha256': fq.digest(complete/'analysis.json'),
        'reference_sha256': manifest['reference_sha256'],
        'verification_source_sha256': fq.digest(__file__),
        'exact_variants': len(poses), 'lineage_counts': dict(lineage_counts),
        'best_origins': best_origins,
        'improvements': {key: {'reference_excess': baseline[key], 'best_excess': best_values[key],
                              'gain': baseline[key]-best_values[key], 'geometry_sha256': geometry_sha(best[key])}
                         for key in best if baseline[key]-best_values[key] > 5e-9},
        'donors_sha256': fq.digest(output/'donors.npz'),
        'best_bank_sha256': fq.digest(output/'best_bank.npz'),
        'provenance_sha256': fq.digest(output/'provenance.json'),
        'note': 'All exact source/archive/geometry/log hashes and saved official raw+pandas certificates audited. Official calculations were not repeated. Exact minima include every certified local intermediate and primary output; opposing orientations remain separate keys.'}
    atomic_json(output/'verification.json', report)
    for path in output.iterdir():
        path.chmod(0o444)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    # The audit is one CPU and has its own hard deadline after search ends.
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Bundle audit exceeded60s')))
    signal.alarm(60)
    try:
        report = verify(args.run, args.out)
    finally:
        signal.alarm(0)
    print(json.dumps({key: value for key, value in report.items() if key != 'best_origins'}))


if __name__ == '__main__':
    main()
