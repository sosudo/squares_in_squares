"""Compare actual CUDA whole-row capacity with strict 2D refill on known seeds."""
import hashlib
import math
import time

import cupy as cp
import numpy as np
from gpu_upright_rows import refill_batch
from refill_search import fill_rect


def run(bank):
    cp.cuda.Device(0).use()
    records = []
    for key, p in bank.items():
        started = time.monotonic()
        w, h, d = map(int, key.split('_'))
        extent = .5*(abs(np.cos(p[:, 2]))+abs(np.sin(p[:, 2])))
        dimensions = (p[:, :2]+extent[:, None]).max(0)-(p[:, :2]-extent[:, None]).min(0)
        f0 = float(np.max(dimensions-[w, h]))
        loose = min(.995, f0+.035)
        tilt = abs((p[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4) > .018
        core = p[tilt]
        _, row_counts = refill_batch(core[None], w, h, loose, len(p), soft=.008)
        capacities = cp.asnumpy(row_counts).tolist()
        upright, info = fill_rect(w+loose, h+loose, core, p[~tilt],
                                  time_limit=.5, margin=0., soft=0.)
        strict_capacity = len(core)+len(upright)
        missed = max(capacities) < len(p)-4 and strict_capacity >= len(p)
        record = {'key': key, 'n': len(p), 'core_count': len(core), 'f0': f0, 'loose': loose,
            'source_array_sha256': hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest(),
            'actual_cuda_row_capacities': capacities, 'original_gate_threshold': len(p)-4,
            'strict_2d_refill_capacity': strict_capacity, 'finite_set_optimal': info['finite_set_optimal'],
            'eligible_2d_seed_skipped_by_original_gate': missed,
            'strict_float_min_upright_core_gap': info['upright_core_min_gap'],
            'seconds': time.monotonic()-started}
        records.append(record)
        print(__import__('json').dumps({'stage': 'refill_gate_preflight', **record}), flush=True)
    demonstrated = sum(r['eligible_2d_seed_skipped_by_original_gate'] for r in records)
    if demonstrated == 0:
        raise AssertionError('No known feasible 2D refill was screened out; re-examine hypothesis before search')
    return {'cases': records, 'demonstrated_gate_misses': demonstrated,
        'note': 'Whole-row capacity is a lower bound. Strict finite-set refill demonstrates missed opportunities; exact-contact floating outputs are diagnostic, not newly certified submissions.'}
