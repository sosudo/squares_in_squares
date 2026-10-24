"""Keep bounded near-capacity cores and near-feasible full poses for later repair.

Every entry is explicitly exploratory. This observer changes neither public
optimizer outputs nor geometry admission and never labels capacity as a proof.
"""
from __future__ import annotations

import functools
import hashlib
import json
from pathlib import Path
import time

import numpy as np


class ExploratoryArchive:
    def __init__(self, worker, policy, prefix, *, cores_per_key=8, full_per_key=16,
                 flush_seconds=30):
        self.worker = worker
        self.policy = policy
        self.prefix = Path(prefix)
        self.cores_per_key = cores_per_key
        self.full_per_key = full_per_key
        self.flush_seconds = flush_seconds
        self.started = self.last_flush = time.monotonic()
        self.context = None
        self.core_outputs = None
        self.core_records, self.core_arrays = {}, {}
        self.full_records, self.full_arrays = {}, {}
        self.stats = {'status': 'exploratory_unvalidated', 'core_rows_observed': 0,
            'near_capacity_core_rows': 0, 'full_rows_observed': 0,
            'near_feasible_full_rows': 0, 'note': 'No stored entry has passed final certification merely by being captured here.'}
        self.originals = {}
        self.wrappers = {}

    def host(self, value):
        return value if isinstance(value, np.ndarray) else np.asarray(self.worker.cp.asnumpy(value))

    @staticmethod
    def geometry_sha(q):
        return hashlib.sha256(np.asarray(q, dtype='<f8').tobytes()).hexdigest()

    def retain(self, records, arrays, q, record, limit, quality):
        signature = self.worker.fingerprint(q)
        identity = record['source_key']+'__'+signature
        record = {**record, 'id': identity, 'fingerprint': signature,
            'geometry_sha256': self.geometry_sha(q), 'status': 'exploratory_unvalidated'}
        previous = records.get(identity)
        if previous is not None and quality(record) <= quality(previous):
            return
        records[identity] = record
        arrays[identity] = np.array(q, dtype=float, copy=True)
        same_key = [key for key, value in records.items() if value['source_key'] == record['source_key']]
        same_key.sort(key=lambda key: quality(records[key]), reverse=True)
        for key in same_key[limit:]:
            del records[key]
            del arrays[key]

    def observe_refill(self, cores, w, h, loose, total, soft, capacities):
        if self.context is None or self.core_outputs is None:
            return
        capacities = np.asarray(capacities, dtype=int).reshape(-1, 2)
        if len(capacities) != len(cores) or len(self.core_outputs) != len(cores):
            raise ValueError('Exploratory refill observations have inconsistent batch sizes')
        source = self.context['source_pose']
        reference = self.policy.reference_capacity(w, h, total-w*h, source, loose)
        residual = self.core_outputs[:, 1]
        maximum = capacities.max(axis=1)
        eligible = np.flatnonzero(np.isfinite(self.core_outputs).all(axis=1)
            & (residual <= .01) & (maximum >= reference-2))
        self.stats['core_rows_observed'] += len(cores)
        self.stats['near_capacity_core_rows'] += len(eligible)
        # Keep a bounded sample per batch; priority is capacity, then residual.
        eligible = sorted(eligible, key=lambda i: (int(maximum[i]), -float(residual[i])), reverse=True)[:2]
        if eligible:
            host_cores = self.host(cores[np.asarray(eligible, dtype=int)])
            for q, replica in zip(host_cores, eligible):
                if not np.isfinite(q).all():
                    continue
                record = {key: value for key, value in self.context.items() if key != 'source_pose'}
                record.update(kind='near_capacity_core', w=int(w), h=int(h), count=len(q),
                    requested_count=int(total), loose_fractional_side=float(loose),
                    reference_row_capacity=int(reference), row_capacities=capacities[replica].tolist(),
                    reported_capacity=int(maximum[replica]), core_residual=float(residual[replica]),
                    soft_overlap_tolerance=float(soft), captured_seconds=time.monotonic()-self.started)
                self.retain(self.core_records, self.core_arrays, q, record, self.cores_per_key,
                    lambda r: (r['reported_capacity'], -r['core_residual']))
        self.flush()

    def observe_full(self, poses, outcomes, boxes):
        if self.context is None:
            return
        outcomes = self.host(outcomes)
        boxes = np.asarray(boxes, dtype=float)
        self.stats['full_rows_observed'] += len(outcomes)
        eligible = np.flatnonzero(np.isfinite(outcomes).all(axis=1) & (outcomes[:, 1] <= .003))
        self.stats['near_feasible_full_rows'] += len(eligible)
        eligible = eligible[np.argsort(outcomes[eligible, 1])[:4]]
        if not len(eligible):
            return
        host_poses = self.host(poses[eligible])
        for q, replica in zip(host_poses, eligible):
            if not np.isfinite(q).all():
                continue
            record = {key: value for key, value in self.context.items() if key != 'source_pose'}
            record.update(kind='near_feasible_full_pose', count=len(q),
                full_residual=float(outcomes[replica, 1]), full_energy=float(outcomes[replica, 0]),
                target_box=boxes[replica].tolist(), captured_seconds=time.monotonic()-self.started)
            self.retain(self.full_records, self.full_arrays, q, record, self.full_per_key,
                lambda r: (-r['full_residual'], -r['full_energy']))
        self.flush()

    def flush(self, force=False):
        if not force and time.monotonic()-self.last_flush < self.flush_seconds:
            return
        self.prefix.parent.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for suffix, arrays in [('_cores.npz', self.core_arrays), ('_full.npz', self.full_arrays)]:
            path = Path(str(self.prefix)+suffix)
            temporary = path.with_suffix(path.suffix+'.tmp')
            with temporary.open('wb') as stream:
                np.savez_compressed(stream, **arrays)
            temporary.replace(path)
            hashes[suffix] = hashlib.sha256(path.read_bytes()).hexdigest()
        report = {**self.stats, 'elapsed_seconds': time.monotonic()-self.started,
            'archive_hashes': hashes, 'core_records': self.core_records, 'full_records': self.full_records}
        path = Path(str(self.prefix)+'.json')
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, indent=2)+'\n')
        temporary.replace(path)
        self.last_flush = time.monotonic()

    def install(self):
        self.originals = {name: getattr(self.worker, name)
            for name in ['mutations', 'explore', 'precise', 'refill_batch']}

        @functools.wraps(self.originals['mutations'])
        def mutations(p, w, h, d, rng, B, mode, archive):
            self.context = {'source_key': f'{w}_{h}_{d}', 'w': int(w), 'h': int(h),
                'source_surplus': int(d), 'mode': int(mode), 'source_pose': np.array(p, copy=True),
                'source_geometry_sha256': self.geometry_sha(p)}
            self.core_outputs = None
            return self.originals['mutations'](p, w, h, d, rng, B, mode, archive)

        @functools.wraps(self.originals['explore'])
        def explore(*args, **kwargs):
            result = self.originals['explore'](*args, **kwargs)
            if kwargs.get('steps', args[2] if len(args) > 2 else 350) == 500:
                self.core_outputs = self.host(result[1]).copy()
            return result

        @functools.wraps(self.originals['precise'])
        def precise(*args, **kwargs):
            result = self.originals['precise'](*args, **kwargs)
            boxes = args[1] if len(args) > 1 else kwargs['boxes']
            self.observe_full(result[0], result[1], boxes)
            return result

        @functools.wraps(self.originals['refill_batch'])
        def refill(cores, w, h, f, total, soft=.008):
            result = self.originals['refill_batch'](cores, w, h, f, total, soft=soft)
            self.observe_refill(cores, w, h, f, total, soft, self.host(result[1]))
            return result

        self.wrappers = {'mutations': mutations, 'explore': explore, 'precise': precise,
                         'refill_batch': refill}
        for name, function in self.wrappers.items():
            setattr(self.worker, name, function)
        return self

    def restore(self):
        self.flush(force=True)
        for name, function in self.wrappers.items():
            if getattr(self.worker, name) is function:
                setattr(self.worker, name, self.originals[name])
