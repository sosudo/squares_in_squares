"""Verify exact post-gate certificate bindings without rerunning the metric.

Only outputs produced by the pinned combined worker are eligible. This is not
an independent geometry validator; final composed submissions require their own
full raw and numeric-roundtrip official evaluation.
"""
import hashlib
import io
import json
from pathlib import Path

import numpy as np

from ftmc_certified_archive import CertifiedArchive, PUBLIC_METRIC_SHA256


def recover_certified_checkpoint(prefix, metric_path='research/official_metric.py'):
    """Rebuild interrupted aggregates from complete verified immutable pairs.

    Orphan NPY files have no certificate and are ignored by CertifiedArchive.
    A corrupt complete pair fails closed. No unseen geometry is certified or
    inferred from the interrupted mutable aggregate.
    """
    keeper = CertifiedArchive(prefix, metric_path=metric_path)
    keeper.finalflush()
    poses, records, binding = read_certified_checkpoint(prefix, metric_path)
    binding['recovered_from_immutable_snapshots'] = True
    return poses, records, binding


def read_certified_checkpoint(prefix, metric_path='research/official_metric.py'):
    prefix = Path(prefix)
    if hashlib.sha256(Path(metric_path).read_bytes()).hexdigest() != PUBLIC_METRIC_SHA256:
        raise ValueError('Metric bytes changed')
    index = json.loads(Path(str(prefix)+'.json').read_text())
    if (index.get('status') != 'certified_geometry'
            or index.get('official_metric_sha256') != PUBLIC_METRIC_SHA256
            or index.get('certification_contract') != 'keep_only_after_unchanged_public_certify'):
        raise ValueError('Unexpected certified archive contract')
    path = Path(str(prefix)+'.npz')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if index['aggregate_sha256'].get(path.name) != digest:
        raise ValueError('Aggregate archive bytes changed')
    snapshot_dir = Path(str(prefix)+'_snapshots')
    complete_record_names = {record.stem for record in snapshot_dir.glob('*.json')}
    if complete_record_names != set(index['records']):
        raise ValueError('Immutable certificate records are newer than the aggregate index')
    poses, records = {}, {}
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(index['records']):
            raise ValueError('Aggregate records and geometry disagree')
        for name in archive.files:
            q = archive[name]
            record = index['records'][name]
            key = record['key']
            w, h, d = map(int, key.split('_'))
            buffer = io.BytesIO()
            np.save(buffer, q, allow_pickle=False)
            payload = buffer.getvalue()
            geometry_sha = hashlib.sha256(payload).hexdigest()
            if (q.shape != (w*h+d, 3) or q.dtype.kind != 'f' or not np.isfinite(q).all()
                    or name != key+'__'+geometry_sha
                    or record.get('geometry_sha256') != geometry_sha
                    or record.get('npy_sha256') != geometry_sha
                    or record.get('official_metric_sha256') != PUBLIC_METRIC_SHA256
                    or record.get('shape') != list(q.shape) or record.get('dtype') != q.dtype.str
                    or record.get('status') != 'certified_geometry'
                    or any(record.get(label) is not True for label in ['raw','roundtrip','official_raw_and_pandas'])
                    or record.get('certification_contract') != 'unchanged_public_certify_exact_geometry'):
                raise ValueError('Exact geometry certificate binding failed: '+name)
            immutable = snapshot_dir/(name+'.json')
            snapshot = snapshot_dir/(geometry_sha+'.npy')
            if (json.loads(immutable.read_text()) != record or snapshot.read_bytes() != payload):
                raise ValueError('Immutable snapshot and aggregate disagree: '+name)
            poses[name], records[name] = q, record
    return poses, records, {'aggregate_sha256': digest, 'index_sha256': hashlib.sha256(
        Path(str(prefix)+'.json').read_bytes()).hexdigest(), 'verified_poses': len(poses),
        'certification_reused_for_identical_bytes': True, 'independent_metric_rerun': False}
