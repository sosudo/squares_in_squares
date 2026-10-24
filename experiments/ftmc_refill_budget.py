"""Measured refill eligibility and cumulative wall-time accounting for FTMC.

Whole-row refill is a restricted exploratory family, not an upper bound for 2D
capacity. Compare each mutation with its feasible source's measured row count,
then permit only a bounded share of general-refill work. The caller retains the
per-attempt alarm, one-attempt-per-batch limit and all official admission gates.
"""
from __future__ import annotations

from collections import OrderedDict
import functools
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np


class GeneralRefillBudget:
    """Single-worker policy; no reservation is consumed by eligibility checks.

An allowed attempt reserves ``attempt_seconds`` conceptually before invocation;
the wrapper rechecks and charges its actual duration even when it raises. The
default startup credit is zero, so ordinary calls bounded by that reservation
stay at or below ``max_fraction`` of cumulative elapsed time. A native solver
that returns after its external alarm can overshoot; that debt is recorded and
blocks new attempts until the cumulative allowance catches up.
"""

    def __init__(self, worker, original_refill_batch, *, max_fraction=.18,
                 attempt_seconds=.5, startup_credit_seconds=0., deficit_margin=2,
                 output_path=None, clock=time.monotonic, max_cache_entries=256,
                 flush_seconds=15.):
        if (not 0 < max_fraction < 1 or not math.isfinite(max_fraction)
                or not math.isfinite(attempt_seconds) or attempt_seconds <= 0
                or not math.isfinite(startup_credit_seconds) or startup_credit_seconds < 0
                or type(deficit_margin) is not int or deficit_margin < 0
                or type(max_cache_entries) is not int or max_cache_entries < 1
                or not math.isfinite(flush_seconds) or flush_seconds <= 0):
            raise ValueError('Invalid refill budget settings')
        self.worker = worker
        self.original_refill_batch = original_refill_batch
        self.max_fraction = float(max_fraction)
        self.attempt_seconds = float(attempt_seconds)
        self.startup_credit_seconds = float(startup_credit_seconds)
        self.deficit_margin = deficit_margin
        self.output_path = Path(output_path) if output_path is not None else None
        self.clock = clock
        self.started = self.clock()
        self.last_flush = self.started
        self.flush_seconds = float(flush_seconds)
        self.max_cache_entries = max_cache_entries
        self.cache = OrderedDict()
        self.inflight = False
        self.stats = {
            'reference_cache_hits': 0, 'reference_cache_misses': 0,
            'reference_cache_evictions': 0, 'reference_seconds': 0.,
            'reference_deficit_by_key': {}, 'reference_capacity_by_key': {},
            'reference_source_sha256_by_key': {}, 'reference_loose_by_key': {},
            'eligibility_checks': 0, 'quality_denials': 0, 'budget_denials': 0,
            'invalid_row_count_denials': 0, 'wrapper_budget_denials': 0,
            'refill_calls': 0, 'refill_returned_packing': 0, 'refill_returned_none': 0,
            'refill_timeouts': 0, 'refill_other_errors': 0, 'refill_seconds': 0.,
            'attempt_overruns': 0, 'attempt_overrun_seconds': 0.,
            'maximum_budget_excess_seconds': 0., 'last_decision': None,
        }

    def _elapsed(self, now=None):
        return max(0., (self.clock() if now is None else now)-self.started)

    def _allowance(self, now=None):
        return self.max_fraction*self._elapsed(now)+self.startup_credit_seconds

    def budget_available(self):
        return (not self.inflight
                and self.stats['refill_seconds']+self.attempt_seconds <= self._allowance()+1e-12)

    def reference_capacity(self, w, h, d, source_pose, loose):
        """Cache actual source row capacity; this method never consumes refill tokens."""
        dimensions = tuple(int(v) for v in (w, h, d))
        if any(float(v) != i for v, i in zip((w, h, d), dimensions)):
            raise ValueError('Gadget dimensions and surplus must be integers')
        w, h, d = dimensions
        total = w*h+d
        loose = float(loose)
        source = np.asarray(source_pose, dtype='<f8')
        if (not 1 <= w <= 31 or not 1 <= h <= 31 or total <= 0
                or not math.isfinite(loose) or not 0 <= loose < 1
                or source.shape != (total, 3) or not np.isfinite(source).all()):
            raise ValueError('Invalid source geometry for measured refill reference')
        source_sha = hashlib.sha256(np.ascontiguousarray(source).tobytes()).hexdigest()
        identity = (w, h, d, loose.hex(), source_sha)
        if identity in self.cache:
            self.stats['reference_cache_hits'] += 1
            capacity = self.cache.pop(identity)
            self.cache[identity] = capacity
        else:
            self.stats['reference_cache_misses'] += 1
            core = source[np.abs((source[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4) > .018]
            if len(core) > 192:
                raise ValueError('Reference core exceeds the public CUDA row capacity')
            begin = self.clock()
            try:
                _, result = self.original_refill_batch(core[None], w, h, loose, total, soft=.008)
                counts = np.asarray(self.worker.cp.asnumpy(result))
                if (counts.shape != (2,) or not np.issubdtype(counts.dtype, np.integer)
                        or np.any(counts < 0)):
                    raise ValueError('Unexpected CUDA source row capacities')
                capacity = int(counts.max())
            finally:
                self.stats['reference_seconds'] += max(0., self.clock()-begin)
            self.cache[identity] = capacity
            if len(self.cache) > self.max_cache_entries:
                self.cache.popitem(last=False)
                self.stats['reference_cache_evictions'] += 1
        key = f'{w}_{h}_{d}'
        self.stats['reference_deficit_by_key'][key] = max(0, total-capacity)
        self.stats['reference_capacity_by_key'][key] = capacity
        self.stats['reference_source_sha256_by_key'][key] = source_sha
        self.stats['reference_loose_by_key'][key] = loose
        return capacity

    def allow_refill(self, row_capacity, w, h, d, source_pose, loose):
        """Require a source-relative row count and an available full attempt allowance."""
        self.stats['eligibility_checks'] += 1
        value = float(row_capacity)
        if not math.isfinite(value) or value < 0 or int(value) != value:
            self.stats['invalid_row_count_denials'] += 1
            self.stats['last_decision'] = {'allowed': False, 'reason': 'invalid row count'}
            self._maybe_flush()
            return False
        measured = self.reference_capacity(w, h, d, source_pose, loose)
        total = int(w)*int(h)+int(d)
        deficit = max(0, total-measured)
        threshold = total-(deficit+self.deficit_margin)
        quality = int(value) >= threshold
        available = self.budget_available()
        allowed = quality and available
        if not quality:
            self.stats['quality_denials'] += 1
        elif not available:
            self.stats['budget_denials'] += 1
        self.stats['last_decision'] = {'allowed': bool(allowed),
            'reason': 'allowed' if allowed else 'row count below source margin' if not quality else 'time budget',
            'key': f'{int(w)}_{int(h)}_{int(d)}', 'row_capacity': int(value),
            'reference_capacity': measured, 'reference_deficit': deficit, 'threshold': threshold}
        self._maybe_flush()
        return bool(allowed)

    def wrap_refill(self, original):
        """Preserve ordinary results/errors, charging actual time even on timeout."""
        @functools.wraps(original)
        def measured(*args, **kwargs):
            # Eligibility can be checked before another residual/finite gate.
            # Recheck here rather than reserving tokens in allow_refill, so a
            # skipped candidate cannot leave an outstanding reservation.
            if not self.budget_available():
                self.stats['wrapper_budget_denials'] += 1
                self._maybe_flush()
                return None, {'reason': 'general refill time allowance exhausted', 'budget_blocked': True}
            self.inflight = True
            self.stats['refill_calls'] += 1
            begin = self.clock()
            try:
                result = original(*args, **kwargs)
                field = 'refill_returned_packing' if result[0] is not None else 'refill_returned_none'
                self.stats[field] += 1
                return result
            except TimeoutError:
                self.stats['refill_timeouts'] += 1
                raise
            except Exception:
                self.stats['refill_other_errors'] += 1
                raise
            finally:
                now = self.clock()
                duration = max(0., now-begin)
                self.stats['refill_seconds'] += duration
                overrun = max(0., duration-self.attempt_seconds)
                if overrun > 1e-9:
                    self.stats['attempt_overruns'] += 1
                    self.stats['attempt_overrun_seconds'] += overrun
                excess = max(0., self.stats['refill_seconds']-self._allowance(now))
                self.stats['maximum_budget_excess_seconds'] = max(
                    self.stats['maximum_budget_excess_seconds'], excess)
                self.inflight = False
                self._maybe_flush()
        return measured

    def snapshot(self):
        elapsed = self._elapsed()
        spent = self.stats['refill_seconds']
        data = {**self.stats, 'elapsed_seconds': elapsed,
                'reference_cache_entries': len(self.cache),
                'max_fraction': self.max_fraction, 'attempt_seconds': self.attempt_seconds,
                'startup_credit_seconds': self.startup_credit_seconds,
                'deficit_margin': self.deficit_margin,
                'available_seconds': self._allowance()-spent,
                'observed_refill_fraction': spent/elapsed if elapsed else 0.,
                'current_budget_excess_seconds': max(0., spent-self._allowance()),
                'inflight': self.inflight,
                'note': 'Measured restricted-family source counts guide sampling; they are not upper bounds. Actual refill time is charged. Native calls may return after an external alarm; any excess is retained as debt.'}
        return json.loads(json.dumps(data))

    def flush(self):
        report = self.snapshot()
        if self.output_path is not None:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.output_path.with_suffix(self.output_path.suffix+'.tmp')
            temporary.write_text(json.dumps(report, indent=2)+'\n')
            temporary.replace(self.output_path)
        self.last_flush = self.clock()
        return report

    def _maybe_flush(self):
        if self.output_path is not None and self.clock()-self.last_flush >= self.flush_seconds:
            self.flush()


GeneralRefillPolicy = GeneralRefillBudget
