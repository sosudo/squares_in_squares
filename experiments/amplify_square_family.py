"""Amplify one certified square packing through buffered copies and L-frames.

Defaults target n65 (8x8+1). A single improved seed can feed surplus1/2/3
families. Every emitted full case passes official raw, ordinary pandas, and
independent interval gates. No search, GPU, submission, or square resizing.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import signal
import sys
import time

import numpy as np

from compose_gadgets import legalize, side
from cpu_recipe_replay import public_functions
from fq_capacity_probe import full_certificate

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_seed(path, n, key=None):
    path = Path(path)
    if path.suffix == '.npz':
        with np.load(path, allow_pickle=False) as z:
            if key is None:
                k = math.isqrt(n)
                choices = [name for name in (str(n), f'{k}_{k}_{n-k*k}') if name in z.files]
                if not choices and len(z.files) == 1:
                    choices = z.files
                if len(choices) != 1:
                    raise ValueError('Provide --key for an ambiguous seed archive')
                key = choices[0]
            q = np.array(z[key], dtype=float, copy=True)
    elif path.suffix == '.json':
        d = json.loads(path.read_text())
        if isinstance(d, dict) and str(n) in d:
            d = d[str(n)]
        q = np.asarray(d['squares'] if isinstance(d, dict) else d, dtype=float)
    elif path.suffix == '.csv':
        with path.open() as f:
            rows = [r for r in csv.DictReader(f) if int(r['n']) == n]
        rows.sort(key=lambda r: int(r['square_id']))
        q = np.asarray([[float(r[x]) for x in ('x', 'y', 'angle')] for r in rows])
    else:
        raise ValueError('Use an already decoded radians NPZ, JSON, or CSV seed')
    if q.shape != (n, 3) or not np.isfinite(q).all():
        raise ValueError('Seed count or finite coordinates differ')
    return q


def layout(seed, copies, k, stitch):
    base = math.isqrt(len(seed))
    surplus = len(seed)-base*base
    f = side(seed)-base
    if not 0 < f < 1 or surplus < 1:
        raise ValueError('A non-grid seed below its next integer side is required')
    # Half the joins consume a horizontal unit buffer; the rest a vertical one.
    horizontal = (copies-1)//2
    modes = [3]+[1]*horizontal+[2]*(copies-1-horizontal)
    width = copies*base+horizontal
    height = copies*base+copies-1-horizontal
    if k < max(width, height):
        raise ValueError('Container is smaller than the buffered chain')
    conservative = math.ceil((f+3e-8)*1e9)*1e-9
    gadgets = [dict(w=base, h=base, dm=surplus, f=conservative, donor=i)
               for i in range(copies)]
    q, _ = stitch(list(enumerate(modes)), gadgets,
                  [(seed, 'same certified source seed') for _ in range(copies)], box=(k, k))
    if len(q) != k*k+copies*surplus:
        raise ValueError('Buffered chain/L-frame count differs')
    return legalize(q, clearance=2e-9), {'copies': copies, 'modes': modes,
        'nominal_width': width, 'nominal_height': height, 'container_k': k,
        'surplus': copies*surplus, 'expected_count': k*k+copies*surplus,
        'conservative_recipe_bloat': conservative}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seed', type=Path, required=True)
    ap.add_argument('--key')
    ap.add_argument('--base-n', type=int, default=65)
    ap.add_argument('--baseline-report', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seconds', type=float, default=30.)
    ap.add_argument('--control', action='store_true', help='Certify the minimum container of each multiplicity')
    args = ap.parse_args()
    if args.out.exists() or not 0 < args.seconds <= 120:
        raise ValueError('Require a new output directory and bounded positive seconds<=120')
    report = json.loads(args.baseline_report.read_text())
    if not report.get('valid') or report.get('puzzles') != 1000 or report.get('invalid_count') != 0:
        raise ValueError('Complete valid baseline official report required')
    base_sides = {r['n']: float(r['side']) for r in report['results']}
    args.out.mkdir(parents=True)
    candidates, records = {}, []
    started = time.monotonic()
    def expired(signum, frame):
        raise TimeoutError('Amplification validation deadline reached')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, args.seconds)
    status = 'complete'
    try:
        seed = legalize(load_seed(args.seed, args.base_n, args.key), clearance=2e-9)
        if seed is None:
            raise ValueError('Seed requires more than rounding repair')
        seed_certificate = full_certificate(seed)
        if not seed_certificate['valid']:
            raise ValueError('Seed fails exact raw/default-pandas geometry gates')
        stitch, _ = public_functions(ROOT/'vendor/lightning_ftmc')
        base = math.isqrt(args.base_n)
        surplus = args.base_n-base*base
        if not 0 < side(seed)-base < 1 or surplus < 1:
            raise ValueError('Seed must have positive surplus and fractional side in(0,1)')
        for copies in range(1, 32):
            minimum = copies*base+math.ceil((copies-1)/2)
            if minimum > 31 or copies*surplus > 63:
                break
            for k in range(minimum, 32):
                n = k*k+copies*surplus
                if n > 1000:
                    break
                if args.control and k != minimum:
                    continue
                if not args.control and k+side(seed)-base >= base_sides[n]-1e-8:
                    continue
                q, construction = layout(seed, copies, k, stitch)
                rec = {'n': n, 'construction': construction}
                if q is None:
                    rec['status'] = 'rounding_repair_rejected'
                elif not args.control and side(q) >= base_sides[n]-1e-8:
                    rec['status'] = 'no_full_case_gain_after_clearance'
                else:
                    certificate = full_certificate(q)
                    rec['certificate'] = certificate
                    rec['valid'] = certificate['valid']
                    if not certificate['valid']:
                        rec['status'] = 'full_geometry_or_transport_rejected'
                    else:
                        length = certificate['independent_raw']['side_upper']
                        rec.update(status='control_passed' if args.control else 'certified_improvement',
                                   side=length, score_gain=(base_sides[n]-float(length))/math.sqrt(n))
                        if not args.control:
                            candidates[str(n)] = {'side': length,
                                'squares': [[format(float(v), '.17g') for v in row] for row in q],
                                'source': f'Buffered replication and L-frame expansion of n{args.base_n}',
                                'provenance': {'seed_sha256': sha(args.seed), **construction}}
                records.append(rec)
                (args.out/'candidates.json').write_text(json.dumps(candidates)+'\n')
                (args.out/'progress.json').write_text(json.dumps(records, indent=2)+'\n')
    except TimeoutError:
        status = 'bounded_partial'
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    (args.out/'candidates.json').write_text(json.dumps(candidates)+'\n')
    summary = {'status': status, 'control': args.control, 'base_n': args.base_n,
        'seed': str(args.seed), 'seed_sha256': sha(args.seed),
        'baseline_report_sha256': sha(args.baseline_report), 'baseline_sha256': report['sha256'],
        'constructor_sha256': sha(Path(__file__)), 'seconds': time.monotonic()-started,
        'records': records, 'certified_candidates': len(candidates),
        'total_score_gain': sum(r.get('score_gain', 0.) for r in records) if not args.control else None,
        'no_submission': True}
    (args.out/'amplification_report.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}), flush=True)


if __name__ == '__main__':
    main()
