"""Record surplus refill capacity as explicitly unvalidated exploratory cores.

The released refill kernel reports uncapped capacity but returns only the
requested number of coordinates. This observer preserves promising cores before
that truncation, without changing any source-worker inputs, outputs or admission.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np


def potential_targets(w, h, surplus, fractional_side, baseline_sides, max_extra=2):
    """Single-rectangle embedding estimates; no separator assumptions are used."""
    result = []
    for extra in range(1, max_extra+1):
        for k in range(max(w, h), 32):
            n = k*k+surplus+extra
            if n > 1000 or str(n) not in baseline_sides:
                continue
            target = float(baseline_sides[str(n)])
            loose_gain = max(0., target-k-fractional_side)/math.sqrt(n)
            relaxed_gain = max(0., target-k-max(0., fractional_side-.04))/math.sqrt(n)
            if relaxed_gain > 1e-9:
                result.append({'n': n, 'k': k, 'extra': extra, 'baseline_side': target,
                    'gain_at_loose_box': loose_gain, 'gain_after_hypothetical_04_shrink': relaxed_gain})
    return result


class OverflowCapture:
    def __init__(self, worker, prefix, baseline_sides, max_records=128,
                 per_key_limit=12, flush_seconds=15):
        self.worker = worker
        self.prefix = Path(prefix)
        self.baseline_sides = baseline_sides
        self.max_records = max_records
        self.per_key_limit = per_key_limit
        self.flush_seconds = flush_seconds
        self.started = self.last_flush = time.monotonic()
        self.records = {}
        self.cores = {}
        self.context = None
        self.core_outputs = None
        self.originals = {}
        self.wrappers = {}
        self.stats = {'schema_version': 1, 'refill_calls': 0, 'row_families': 0,
            'capacity_at_least_requested': 0, 'overflow_row_families': 0,
            'overflow_cores': 0, 'overflow_cores_residual_at_most_01': 0,
            'nonfinite_overflow_cores': 0, 'max_surplus_capacity': 0,
            'deduplicated_updates': 0, 'evicted': 0, 'by_key': {},
            'status': 'exploratory_unvalidated',
            'note': 'Reported capacity uses soft overlaps. These cores are not feasible packings, certificates, or achieved score gains.'}

    def host(self, value):
        return value if isinstance(value, np.ndarray) else np.asarray(self.worker.cp.asnumpy(value))

    @staticmethod
    def quality(record):
        targets = record['potential_targets']
        loose = max((x['gain_at_loose_box'] for x in targets), default=0.)
        relaxed = max((x['gain_after_hypothetical_04_shrink'] for x in targets), default=0.)
        return (record['core_residual'] <= .01, loose, relaxed,
                min(record['reported_capacity']-record['requested_count'], 2),
                -record['core_residual'])

    def observe(self, cores, w, h, f, total, soft, counts):
        counts = np.asarray(counts, dtype=int)
        if self.context is None:
            return
        if counts.shape != (2*len(cores),):
            raise ValueError('Unexpected row-family capacity shape')
        if (w, h, total) != (self.context['w'], self.context['h'], self.context['requested_count']):
            raise ValueError('Mutation context and refill rectangle differ')
        key = self.context['source_key']
        per_key = self.stats['by_key'].setdefault(key, {'calls': 0, 'row_families': 0,
            'capacity_at_least_requested': 0, 'overflow_row_families': 0,
            'overflow_cores': 0, 'max_surplus_capacity': 0})
        self.stats['refill_calls'] += 1
        per_key['calls'] += 1
        for label, value in [('row_families', len(counts)),
            ('capacity_at_least_requested', int(np.count_nonzero(counts >= total))),
            ('overflow_row_families', int(np.count_nonzero(counts > total)))]:
            self.stats[label] += value
            per_key[label] += value
        extra = max(0, int(counts.max(initial=0))-total)
        self.stats['max_surplus_capacity'] = max(self.stats['max_surplus_capacity'], extra)
        per_key['max_surplus_capacity'] = max(per_key['max_surplus_capacity'], extra)
        selected = np.flatnonzero(counts.reshape(-1, 2).max(axis=1) > total)
        self.stats['overflow_cores'] += len(selected)
        per_key['overflow_cores'] += len(selected)
        if not len(selected):
            self.maybe_flush()
            return
        host_cores = self.host(cores[selected]).astype(float, copy=False)
        if self.core_outputs is None or len(self.core_outputs) != len(cores):
            raise ValueError('Missing matching core-quench observations')
        targets = potential_targets(w, h, total-w*h, f, self.baseline_sides)
        for local, replica in enumerate(selected):
            core = host_cores[local]
            output = self.core_outputs[int(replica)]
            if not np.isfinite(core).all() or not np.isfinite(output).all():
                self.stats['nonfinite_overflow_cores'] += 1
                continue
            residual = float(output[1])
            self.stats['overflow_cores_residual_at_most_01'] += int(residual <= .01)
            # Keep absolute position: reflected or shifted cores can refill
            # differently against a given rectangle's wall-anchored row family.
            signature_data = np.column_stack((core[:, :2], np.cos(4*core[:, 2]), np.sin(4*core[:, 2])))
            quantized = np.rint(signature_data*1e4).astype('<i8')
            order = np.lexsort(tuple(quantized[:, i] for i in range(3, -1, -1)))
            identity = key+'__'+hashlib.sha256(quantized[order].tobytes()).hexdigest()[:20]
            capacity_pair = counts[2*int(replica):2*int(replica)+2]
            families = [int(i) for i in np.flatnonzero(capacity_pair > total)]
            record = {**self.context, 'id': identity, 'w': int(w), 'h': int(h),
                'loose_fractional_side': float(f), 'requested_count': int(total),
                'reported_capacity': int(capacity_pair.max()),
                'row_family_capacities': capacity_pair.tolist(), 'overflow_families': families,
                'soft_overlap_tolerance': float(soft), 'core_count': len(core),
                'core_energy': float(output[0]), 'core_residual': residual,
                'core_sha256': hashlib.sha256(core.astype('<f8').tobytes()).hexdigest(),
                'potential_targets': targets, 'status': 'exploratory_unvalidated',
                'observed_seconds': time.monotonic()-self.started}
            old = self.records.get(identity)
            if old is None or self.quality(record) > self.quality(old):
                self.records[identity] = record
                self.cores[identity] = core.copy()
                self.stats['deduplicated_updates'] += 1
        by_key = {}
        for identity, record in sorted(self.records.items(), key=lambda kv: self.quality(kv[1]), reverse=True):
            by_key.setdefault(record['source_key'], []).append(identity)
        keep = []
        for ids in by_key.values():
            keep.extend(ids[:self.per_key_limit])
        keep = sorted(keep, key=lambda identity: self.quality(self.records[identity]), reverse=True)[:self.max_records]
        removed = set(self.records)-set(keep)
        self.stats['evicted'] += len(removed)
        for identity in removed:
            del self.records[identity]
            del self.cores[identity]
        self.maybe_flush()

    def maybe_flush(self):
        if time.monotonic()-self.last_flush >= self.flush_seconds:
            self.flush()

    def flush(self):
        self.prefix.parent.mkdir(parents=True, exist_ok=True)
        array_path = self.prefix.with_suffix('.npz')
        temporary = array_path.with_suffix('.npz.tmp')
        with temporary.open('wb') as stream:
            np.savez_compressed(stream, **self.cores)
        temporary.replace(array_path)
        manifest = {**self.stats, 'retained_cores': len(self.cores),
            'elapsed_seconds': time.monotonic()-self.started,
            'archive_sha256': hashlib.sha256(array_path.read_bytes()).hexdigest(),
            'records': self.records}
        report_path = self.prefix.with_suffix('.json')
        temporary = report_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(manifest, indent=2)+'\n')
        temporary.replace(report_path)
        self.last_flush = time.monotonic()

    def install(self):
        self.originals = {name: getattr(self.worker, name) for name in ('mutations', 'explore', 'refill_batch')}

        @functools.wraps(self.originals['mutations'])
        def mutations(p, w, h, d, rng, B, mode, archive):
            self.context = {'source_key': f'{w}_{h}_{d}', 'w': int(w), 'h': int(h),
                'source_surplus': int(d), 'requested_count': int(w*h+d), 'mode': int(mode),
                'source_geometry_sha256': hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()}
            self.core_outputs = None
            return self.originals['mutations'](p, w, h, d, rng, B, mode, archive)

        @functools.wraps(self.originals['explore'])
        def explore(*args, **kwargs):
            result = self.originals['explore'](*args, **kwargs)
            steps = kwargs.get('steps', args[2] if len(args) > 2 else 350)
            if steps == 500:
                self.core_outputs = self.host(result[1]).copy()
            return result

        @functools.wraps(self.originals['refill_batch'])
        def refill(cores, w, h, f, total, soft=.008):
            result = self.originals['refill_batch'](cores, w, h, f, total, soft=soft)
            self.observe(cores, w, h, f, total, soft, self.host(result[1]))
            return result

        self.wrappers = {'mutations': mutations, 'explore': explore, 'refill_batch': refill}
        for name, function in self.wrappers.items():
            setattr(self.worker, name, function)
        return self

    def restore(self):
        self.flush()
        for name, function in self.wrappers.items():
            if getattr(self.worker, name) is function:
                setattr(self.worker, name, self.originals[name])


def install_capture(worker, prefix, baseline_sides, **kwargs):
    return OverflowCapture(worker, prefix, baseline_sides, **kwargs).install()
