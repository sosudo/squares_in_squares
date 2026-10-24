"""Bounded CPU control for the position of an unchanged FTMC tilted core.

The public mutation initializer centers the stripped core in its original full
box. This control isolates that translation from angle changes and GPU quench.
Finite-set capacities are exploratory evidence, not submitted packing proofs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import signal
import time

import numpy as np

from refill_search import fill_rect


def bounds(p):
    radius = .5 * (np.abs(np.cos(p[:, 2])) + np.abs(np.sin(p[:, 2])))
    return ((p[:, :2] - radius[:, None]).min(0),
            (p[:, :2] + radius[:, None]).max(0))


def run(bank_path, selected, out_path, case_seconds=8):
    started = time.monotonic()
    records = []
    def timeout(signum, frame):
        raise TimeoutError('Bounded CPU refill control')
    previous = signal.signal(signal.SIGALRM, timeout)
    try:
        with np.load(bank_path) as bank:
            for key in bank.files:
                p = bank[key]
                if len(p) not in selected:
                    continue
                w, h, surplus = map(int, key.split('_'))
                lo, hi = bounds(p)
                f = float(np.max(hi-lo-[w, h]))
                loose = min(.995, f+.035)
                tilt = np.abs((p[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4) > .018
                core = p[tilt].copy()
                low, high = bounds(core)
                centered = core.copy()
                shift = (np.array([w+f, h+f])-(high-low))/2-low
                centered[:, :2] += shift
                record = {'key': key, 'n': len(p), 'core_count': len(core),
                          'original_fractional_side': f, 'loose_fractional_side': loose,
                          'initializer_centering_shift': shift.tolist(), 'results': {}}
                for soft in (0., .008):
                    for label, geometry in [('original', core), ('centered_at_f0', centered)]:
                        begin = time.monotonic()
                        try:
                            signal.setitimer(signal.ITIMER_REAL, case_seconds)
                            upright, info = fill_rect(w+loose, h+loose, geometry,
                                p[~tilt], time_limit=.5, margin=0., soft=soft)
                            result = {'capacity': len(geometry)+len(upright),
                                      'finite_set_optimal': info['finite_set_optimal'],
                                      'upright_core_min_gap': info['upright_core_min_gap'],
                                      'candidates': info['candidates'], 'timeout': False}
                        except TimeoutError:
                            result = {'timeout': True}
                        finally:
                            signal.setitimer(signal.ITIMER_REAL, 0)
                        result['seconds'] = time.monotonic()-begin
                        record['results'][f'{label}_soft_{soft}'] = result
                records.append(record)
                print(json.dumps(record), flush=True)
    finally:
        signal.signal(signal.SIGALRM, previous)
    report = {'source_bank': str(bank_path),
              'source_sha256': hashlib.sha256(Path(bank_path).read_bytes()).hexdigest(),
              'note': 'Same unchanged core and original upright candidates; centering exactly uses f0, then both variants refill in f0+.035 capped at .995. Soft=0 forbids interior overlap in the finite candidate model, but boundary floats still require certification. No GPU quench and no score gain claimed.',
              'seconds': time.monotonic()-started, 'cases': records}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', type=Path, default=Path('artifacts/full-puzzle-ftmc-results/full_bank.npz'))
    parser.add_argument('--ns', default='83,86,106,129,171,205,259,302')
    parser.add_argument('--out', type=Path, default=Path('artifacts/core-anchor-control.json'))
    parser.add_argument('--case-seconds', type=float, default=8.)
    args = parser.parse_args()
    run(args.bank, {int(n) for n in args.ns.split(',')}, args.out, args.case_seconds)
