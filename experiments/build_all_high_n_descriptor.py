"""Prepare all retained high-n layouts without changing the historical donor banks.

The historical all_crops archive precedes rounding legalization. Preserve its
exact array hashes and full original provenance while preparing separately
hash-bound, minimally dilated export arrays. This builder does not certify them.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zlib

import numpy as np

from build_high_n_loader_descriptor import (
    array_sha, bits, load_raw, ranges, record_legalize, vector_bits)
from compose_gadgets import extents


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bank', type=Path, default=Path('artifacts/high-n-donors'))
    ap.add_argument('--catalogue', type=Path, default=Path('/tmp/squares-research/couzo'))
    ap.add_argument('--out', type=Path, default=Path('artifacts/all-high-n-donors-v1'))
    ap.add_argument('--validator', type=Path, default=Path('scripts/validate_submission.py'))
    args = ap.parse_args()
    if args.out.exists():
        raise ValueError('Preserve previous all-crops exports; require a new output directory')
    manifest_bytes = (args.bank/'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    provenance_bytes = (args.bank/'all_crops.provenance.json').read_bytes()
    provenance = json.loads(provenance_bytes)
    raw_archive = args.bank/'all_crops.npz'
    if sha(raw_archive.read_bytes()) != manifest['all_crops_archive_sha256']:
        raise ValueError('Historical all_crops archive hash mismatch')
    source_manifest = args.catalogue/'certificates/best/manifest.json'
    if sha(source_manifest.read_bytes()) != manifest['manifest_sha256']:
        raise ValueError('Pinned public certificate manifest changed')
    source_rows, sources, recipes, outputs = {}, {}, {}, {}
    with np.load(raw_archive, allow_pickle=False) as z:
        if set(z.files) != set(provenance) or len(z.files) != manifest['candidate_crops']:
            raise ValueError('All-crops archive and provenance disagree')
        for key in z.files:
            meta = provenance[key]
            n = meta['source_n']
            skey = str(n)
            if n not in source_rows:
                path = args.catalogue/meta['certificate']
                if sha(path.read_bytes()) != meta['certificate_sha256']:
                    raise ValueError('Source certificate bytes changed')
                raw = load_raw(path)
                lo, _ = extents(raw)
                offset = lo.min(axis=0)
                source_rows[n] = raw, offset
                sources[skey] = {'path': meta['certificate'], 'sha256': meta['certificate_sha256'],
                    'n': n, 'source_offset_bits': vector_bits(offset), 'angle_bits': {},
                    'credit': meta['credit'], 'source_repository': meta['source_repository']}
            raw, source_offset = source_rows[n]
            ids = meta['source_square_ids']
            q = raw[ids].copy()
            q[:, :2] -= source_offset
            lo, _ = extents(q)
            crop_offset = lo.min(axis=0)
            q[:, :2] -= crop_offset
            if not np.array_equal(q, z[key]):
                raise ValueError('Historical raw crop reconstruction differs: '+key)
            exported, legal_offset, factor, final_offset = record_legalize(q)
            for i in ids:
                if raw[i, 2] != 0:
                    sources[skey]['angle_bits'][str(i)] = bits(raw[i, 2])
            # The public manifest is downloaded by immutable commit/hash at export
            # time, avoiding repeated large inherited records in notebook source.
            compact_meta = {k: v for k, v in meta.items()
                            if k not in ('manifest_record', 'source_square_ids', 'certificate',
                                         'certificate_sha256', 'credit', 'source_repository')}
            recipes[key] = {'source_n': n, 'source_square_id_ranges': ranges(ids), 'rows': len(ids),
                'crop_offset_bits': vector_bits(crop_offset),
                'legalize_offset_bits': vector_bits(legal_offset),
                'dilation_factor_bits': bits(factor), 'final_offset_bits': vector_bits(final_offset),
                'raw_array_sha256': array_sha(q), 'array_sha256': array_sha(exported),
                'original_crop_metadata': compact_meta}
            outputs[key] = exported
    canonical = hashlib.sha256()
    raw_canonical = hashlib.sha256()
    for key, rec in sorted(recipes.items()):
        for h, label in ((canonical, 'array_sha256'), (raw_canonical, 'raw_array_sha256')):
            h.update(key.encode()+b'\0'+str(rec['rows']).encode()+b'\0')
            h.update(bytes.fromhex(rec[label]))
    licenses = {p.name: p.read_text() for p in Path('vendor/notices/high-n-donors').glob('LICENSE-*.txt')}
    descriptor = {'schema_version': 1, 'source_repo': 'franciscouzo/square-packing',
        'source_commit': manifest['catalogue_commit'],
        'source_manifest_sha256': manifest['manifest_sha256'],
        'sources': sources, 'donors': recipes, 'licenses': licenses,
        'canonical_pose_sha256': canonical.hexdigest(),
        'raw_canonical_pose_sha256': raw_canonical.hexdigest(),
        'original_archive_sha256': manifest['all_crops_archive_sha256'],
        'original_provenance_sha256': sha(provenance_bytes),
        'original_selection_manifest_sha256': sha(manifest_bytes),
        'validator_sha256': sha(args.validator.read_bytes()),
        'note': 'All 1,243 historical layouts retained. Export arrays use separately recorded rounding-only '
                'center dilation; original raw arrays and every metadata field remain hash-bound. '
                'No certification claim is made by this descriptor builder.'}
    args.out.mkdir(parents=True)
    data = json.dumps(descriptor, sort_keys=True, separators=(',', ':')).encode()
    compressed = zlib.compress(data, 9)
    (args.out/'loader_descriptor.json').write_bytes(data)
    (args.out/'loader_descriptor.json.zlib').write_bytes(compressed)
    with (args.out/'prepared_donors.npz').open('wb') as f:
        np.savez_compressed(f, **outputs)
    summary = {'sources': len(sources), 'donors': len(recipes),
        'squares': sum(rec['rows'] for rec in recipes.values()),
        'descriptor_bytes': len(data), 'compressed_bytes': len(compressed),
        'descriptor_sha256': sha(data), 'compressed_sha256': sha(compressed),
        'canonical_pose_sha256': canonical.hexdigest(),
        'raw_canonical_pose_sha256': raw_canonical.hexdigest(),
        'original_archive_sha256': descriptor['original_archive_sha256'],
        'original_provenance_sha256': descriptor['original_provenance_sha256'],
        'prepared_archive_sha256': sha((args.out/'prepared_donors.npz').read_bytes()),
        'validator_sha256': descriptor['validator_sha256'], 'certification_performed': False}
    (args.out/'loader_descriptor.summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
