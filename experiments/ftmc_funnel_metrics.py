"""Observe released FTMC stages without changing inputs or returned results.

The caller owns lifecycle and may call ``flush()`` in a checkpoint hook/finally.
CUDA result summaries transfer only one short row per replica, plus a boolean
coordinate-finiteness mask. This synchronizes pending kernels for measurement.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path
import time

import numpy as np


THRESHOLDS = (1e-6, 3e-5, 1e-4, 1e-3, .01, .1)


class FunnelMetrics:
    def __init__(self, worker, output_path, flush_seconds=15):
        self.worker = worker
        self.output_path = Path(output_path)
        self.flush_seconds = flush_seconds
        self.started = time.monotonic()
        self.last_flush = self.started
        self.state = {
            'schema_version': 1,
            'note': 'Observation only; thresholds describe returned optimizer residuals, not geometry certificates.',
            'stages': {},
            'rect_lp': {'calls': 0, 'exceptions': 0, 'returned_none': 0,
                        'returned_finite': 0, 'returned_nonfinite': 0,
                        'strict_bloat_decreases': 0, 'positive_gap': 0,
                        'bloat_decrease_sum': 0., 'wall_seconds': 0.},
            'certify': {'calls': 0, 'accepted': 0, 'rejected': 0,
                        'exceptions': 0, 'wall_seconds': 0.},
        }
        self.originals = {}
        self.wrappers = {}

    def _host(self, a):
        if isinstance(a, np.ndarray):
            return a
        return np.asarray(self.worker.cp.asnumpy(a))

    def _observe_quench(self, name, result, wall_seconds):
        q, out = result
        out = self._host(out)
        if out.ndim != 2 or out.shape[1] < 2:
            raise ValueError('Expected FTMC output shape (replicas, >=2).')
        finite_out = np.isfinite(out).all(axis=1)
        if isinstance(q, np.ndarray):
            finite_q = np.isfinite(q).all(axis=(1, 2))
        else:
            finite_q = self._host(self.worker.cp.isfinite(q).all(axis=(1, 2)))
        finite = finite_out & finite_q
        residual = out[:, 1]
        s = self.state['stages'].setdefault(name, {
            'calls': 0, 'rows': 0, 'finite_output_rows': 0,
            'finite_coordinate_rows': 0, 'finite_rows': 0,
            'eligible_for_next_stage': 0,
            'residual_at_most': {str(t): 0 for t in THRESHOLDS},
            'residual_min': None, 'residual_max': None,
            'wall_seconds': 0.,
        })
        s['calls'] += 1
        s['rows'] += len(out)
        s['finite_output_rows'] += int(finite_out.sum())
        s['finite_coordinate_rows'] += int(finite_q.sum())
        s['finite_rows'] += int(finite.sum())
        s['wall_seconds'] += wall_seconds
        for t in THRESHOLDS:
            s['residual_at_most'][str(t)] += int(np.sum(finite & (residual <= t)))
        gate = .01 if name == 'core_fp32' else 3e-5 if name == 'full_fp64' else None
        if gate is not None:
            s['eligibility_threshold'] = gate
            s['eligible_for_next_stage'] += int(np.sum(finite & (residual <= gate)))
        if finite.any():
            lo, hi = float(residual[finite].min()), float(residual[finite].max())
            s['residual_min'] = lo if s['residual_min'] is None else min(lo, s['residual_min'])
            s['residual_max'] = hi if s['residual_max'] is None else max(hi, s['residual_max'])

    def _maybe_flush(self):
        if time.monotonic() - self.last_flush >= self.flush_seconds:
            self.flush()

    def snapshot(self):
        return json.loads(json.dumps({**self.state, 'elapsed_seconds': time.monotonic() - self.started}))

    def flush(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.output_path.with_suffix(self.output_path.suffix + '.tmp')
        temp.write_text(json.dumps(self.snapshot(), indent=2), encoding='utf8')
        temp.replace(self.output_path)
        self.last_flush = time.monotonic()

    def install(self):
        for name in ('explore', 'precise'):
            original = getattr(self.worker, name)
            self.originals[name] = original

            def make_quench(original, name):
                @functools.wraps(original)
                def observed(*args, **kwargs):
                    start = time.monotonic()
                    result = original(*args, **kwargs)
                    # Host conversion inside observation includes completion of
                    # asynchronous CUDA work; do not alter the returned arrays.
                    stage = 'full_fp64' if name == 'precise' else (
                        'core_fp32' if kwargs.get('steps', args[2] if len(args) > 2 else 350) == 500
                        else 'full_fp32')
                    self._observe_quench(stage, result, 0.)
                    self.state['stages'][stage]['wall_seconds'] += time.monotonic() - start
                    self._maybe_flush()
                    return result
                return observed

            self.wrappers[name] = make_quench(original, name)

        original_lp = self.worker.rect_lp
        self.originals['rect_lp'] = original_lp

        @functools.wraps(original_lp)
        def observed_lp(p, w, h, *args, **kwargs):
            s = self.state['rect_lp']
            s['calls'] += 1
            start = time.monotonic()
            try:
                q = original_lp(p, w, h, *args, **kwargs)
            except Exception:
                s['exceptions'] += 1
                raise
            finally:
                s['wall_seconds'] += time.monotonic() - start
            if q is None:
                s['returned_none'] += 1
            elif not np.isfinite(q).all():
                s['returned_nonfinite'] += 1
            else:
                s['returned_finite'] += 1
                delta = self.worker.excess(p, w, h) - self.worker.excess(q, w, h)
                s['bloat_decrease_sum'] += float(delta)
                s['strict_bloat_decreases'] += int(delta > 2e-7)
                s['positive_gap'] += int(self.worker.gaps(q) > 1e-10)
            self._maybe_flush()
            return q

        self.wrappers['rect_lp'] = observed_lp
        if hasattr(self.worker, 'certify'):
            original_certify = self.worker.certify
            self.originals['certify'] = original_certify

            @functools.wraps(original_certify)
            def observed_certify(*args, **kwargs):
                s = self.state['certify']
                s['calls'] += 1
                start = time.monotonic()
                try:
                    result = original_certify(*args, **kwargs)
                except Exception:
                    s['exceptions'] += 1
                    raise
                finally:
                    s['wall_seconds'] += time.monotonic() - start
                s['accepted' if result else 'rejected'] += 1
                self._maybe_flush()
                return result
            self.wrappers['certify'] = observed_certify

        for name, wrapper in self.wrappers.items():
            setattr(self.worker, name, wrapper)
        return self

    def restore(self):
        """Restore only wrappers still owned by this observer; preserve later hooks."""
        self.flush()
        for name, wrapper in self.wrappers.items():
            if getattr(self.worker, name) is wrapper:
                setattr(self.worker, name, self.originals[name])


def install_metrics(worker, output_path, flush_seconds=15):
    return FunnelMetrics(worker, output_path, flush_seconds).install()
