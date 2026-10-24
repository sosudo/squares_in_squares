"""One-worker reconstruction/certification of all retained pinned higher-n crops.

Raw historical crop bytes and the complete historical provenance JSON are
reconstructed and checked independently of the legalized output geometry.
Public source caches remain under /tmp; only the donor bank, compressed full
provenance and compact validation/binding report are exported.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import zlib

import numpy as np

from load_high_n_donors import (
    array_sha, certify, download_sources, file_sha, read_descriptor, read_xy,
    reconstruct, value, vector)


def pinned_manifest(d, cache):
    path = Path(cache)/'manifest.json'
    if not path.exists():
        url = ('https://raw.githubusercontent.com/franciscouzo/square-packing/'
               +d['source_commit']+'/certificates/best/manifest.json')
        temporary = path.with_suffix('.incoming')
        total = 0
        h = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as f:
            while chunk := response.read(1024*1024):
                total += len(chunk)
                if total > 32*1024*1024:
                    raise ValueError('Unexpectedly large public certificate manifest')
                h.update(chunk)
                f.write(chunk)
        if h.hexdigest() != d['source_manifest_sha256']:
            temporary.unlink(missing_ok=True)
            raise ValueError('Public certificate manifest hash mismatch')
        temporary.replace(path)
    if file_sha(path) != d['source_manifest_sha256']:
        raise ValueError('Cached public manifest hash mismatch')
    return json.loads(path.read_text())['witnesses']


def verify_originals_and_metadata(d, paths, witnesses):
    xy = {k: read_xy(paths[k], s['n']) for k, s in d['sources'].items()}
    digests, metadata = {}, {}
    for key, recipe in sorted(d['donors'].items(), key=lambda item: int(item[0].split('_')[1])):
        skey = str(recipe['source_n'])
        source = d['sources'][skey]
        ids = [i for start, stop in recipe['source_square_id_ranges'] for i in range(start, stop)]
        original, crop = vector(source['source_offset_bits']), vector(recipe['crop_offset_bits'])
        rows = []
        for i in ids:
            x, y = xy[skey][i]
            x = x-original[0]
            y = y-original[1]
            x = x-crop[0]
            y = y-crop[1]
            a = value(source['angle_bits'][str(i)]) if str(i) in source['angle_bits'] else 0.
            rows.append((x, y, a))
        q = np.asarray(rows, dtype='<f8')
        actual = array_sha(q)
        if actual != recipe['raw_array_sha256']:
            raise ValueError('Original raw crop geometry hash differs: '+key)
        digests[key] = actual
        witness = witnesses[skey]
        if witness['certificate_sha256'] != source['sha256'] or witness['certificate'] != source['path']:
            raise ValueError('Inherited source manifest provenance differs')
        m = recipe['original_crop_metadata']
        # Original insertion order matters for the historical JSON byte hash.
        metadata[key] = {'source_n': recipe['source_n'], 'certificate': source['path'],
            'certificate_sha256': source['sha256'], 'credit': source['credit'],
            'source_repository': source['source_repository'], 'manifest_record': witness,
            'tilted_component_ids': m['tilted_component_ids'], 'window_start': m['window_start'],
            'window_shape': m['window_shape'], 'source_square_ids': ids,
            'nominal_width': m['nominal_width'], 'nominal_height': m['nominal_height'],
            'surplus': m['surplus'], 'bloat': m['bloat']}
    canonical = hashlib.sha256()
    for key, digest in sorted(digests.items()):
        canonical.update(key.encode()+b'\0'+str(d['donors'][key]['rows']).encode()+b'\0')
        canonical.update(bytes.fromhex(digest))
    if canonical.hexdigest() != d['raw_canonical_pose_sha256']:
        raise ValueError('Historical raw bank canonical hash mismatch')
    data = (json.dumps(metadata, indent=2)+'\n').encode()
    if hashlib.sha256(data).hexdigest() != d['original_provenance_sha256']:
        raise ValueError('Full inherited original crop provenance bytes differ')
    return data, digests


def reuse_certificates(path, d, poses, hashes):
    """Reuse a frozen interval proof only for exactly identical array bytes."""
    data = Path(path).read_bytes()
    report = json.loads(zlib.decompress(data) if str(path).endswith('.zlib') else data)
    if (report.get('status') != 'complete' or report.get('valid') is not True
            or report.get('independent_interval_certification') is not True
            or report.get('invalid_count') != 0
            or report.get('validator_sha256') != d['validator_sha256']
            or report.get('canonical_pose_sha256') != d['canonical_pose_sha256']
            or report.get('raw_canonical_pose_sha256') != d['raw_canonical_pose_sha256']
            or report.get('array_sha256') != hashes
            or set(report.get('validation', {})) != set(poses)
            or any(r.get('valid') is not True for r in report['validation'].values())):
        raise ValueError('Frozen interval certificates do not bind these exact source arrays')
    return report['validation'], hashlib.sha256(data).hexdigest()


def load_bank(args):
    started = time.monotonic()
    d = read_descriptor(args.descriptor, args.descriptor_sha256)
    paths = download_sources(d, args.cache, workers=1)
    print(f'Hash-verified {len(paths)} pinned public certificates', flush=True)
    witnesses = pinned_manifest(d, args.cache)
    provenance, raw_hashes = verify_originals_and_metadata(d, paths, witnesses)
    poses, hashes, canonical = reconstruct(d, paths)
    print(f'Exactly reconstructed {len(poses)} raw and legalized arrays plus full inherited provenance', flush=True)
    if file_sha(args.validator) != d['validator_sha256']:
        raise ValueError('Pinned interval validator source changed')
    if args.reuse_report:
        certificates, reused_sha = reuse_certificates(args.reuse_report, d, poses, hashes)
    else:
        certificates = certify(poses, args.validator, d['validator_sha256'])
        reused_sha = None
    for path in (args.output, args.report, args.provenance):
        if path.exists():
            raise ValueError('Refuse to overwrite a previous full-bank export: '+str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.npz.incoming')
    with temporary.open('wb') as f:
        np.savez_compressed(f, **poses)
    temporary.replace(args.output)
    args.provenance.write_bytes(zlib.compress(provenance, 9))
    result = {'status': 'complete', 'valid': True, 'independent_interval_certification': True,
        'independent_interval_rerun_performed': not bool(args.reuse_report),
        'reused_exact_array_certificate_report_sha256': reused_sha,
        'official_metric_certification_performed': False, 'invalid_count': 0,
        'source_repo': d['source_repo'], 'source_commit': d['source_commit'],
        'descriptor_sha256': args.descriptor_sha256, 'source_manifest_sha256': d['source_manifest_sha256'],
        'source_certificates': len(paths), 'donors': len(poses),
        'squares': sum(len(p) for p in poses.values()), 'canonical_pose_sha256': canonical,
        'raw_canonical_pose_sha256': d['raw_canonical_pose_sha256'],
        'historical_raw_archive_sha256': d['original_archive_sha256'],
        'all_export_array_hashes_match': True, 'all_raw_array_hashes_match': True,
        'array_sha256': hashes, 'raw_array_sha256': raw_hashes,
        'archive_sha256': file_sha(args.output),
        'original_full_provenance_sha256': d['original_provenance_sha256'],
        'compressed_provenance_sha256': file_sha(args.provenance),
        'validator_sha256': d['validator_sha256'], 'validation': certificates,
        'source_sha256': {k: s['sha256'] for k, s in d['sources'].items()},
        'elapsed_seconds': time.monotonic()-started, 'licenses': d['licenses'],
        'note': 'Historical raw crops are retained by hash/provenance. Independently interval-certified '
                'export arrays receive only recorded rounding-clearance center dilation. Final full-puzzle '
                'CSV still requires official raw and numeric-roundtrip evaluation.'}
    args.report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items()
                     if k not in ('validation', 'array_sha256', 'raw_array_sha256', 'source_sha256', 'licenses')}), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--descriptor', type=Path, required=True)
    ap.add_argument('--descriptor-sha256', required=True)
    ap.add_argument('--cache', type=Path, default=Path('/tmp/all-high-n-certificates'))
    ap.add_argument('--output', type=Path, default=Path('all_high_n_donors.npz'))
    ap.add_argument('--provenance', type=Path, default=Path('all_high_n_provenance.json.zlib'))
    ap.add_argument('--report', type=Path, default=Path('all_high_n_donors.source_report.json'))
    ap.add_argument('--validator', type=Path, default=Path('scripts/validate_submission.py'))
    ap.add_argument('--reuse-report', type=Path,
                    help='Frozen interval report; admissible only for byte-identical arrays and pinned validator')
    args = ap.parse_args()
    load_bank(args)


if __name__ == '__main__':
    main()
