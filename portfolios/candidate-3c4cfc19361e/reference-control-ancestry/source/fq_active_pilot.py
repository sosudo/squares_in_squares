"""Bounded CPU trials of Evan Daniel's MIT-licensed fq on active rectangles.

The external executable is built from a pinned public source. Its smooth
separator ALM and contact-branch polish are a distinct search path from the
CUDA SAT optimizer. Every retained geometry passes official raw and ordinary
pandas-roundtrip checks; component improvements still require composition.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from score_official import load_metric, OFFICIAL_SHA256
from compose_gadgets import legalize, normalize

SOURCE_COMMIT = '659ee62e4a9d39542a1146e8b011cc3ab6407ede'
MODES = {
    'polish': ['--no-alm', '--loosen', '1', '--pit', '160', '--flip-top', '32'],
    'kick': ['--loosen', '1.001', '--kick', '.008', '--outer', '35', '--pit', '60', '--flip-top', '8'],
    'round': ['--loosen', '1', '--round-r0', '.15', '--round-compress',
              '--round-steps', '12', '--round-kick', '.01', '--outer', '30', '--pit', '60', '--flip-top', '8'],
}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bloat(p, w, h):
    e = .5 * (abs(np.cos(p[:, 2])) + abs(np.sin(p[:, 2])))
    spans = (p[:, :2] + e[:, None]).max(0) - (p[:, :2] - e[:, None]).min(0)
    return float(max(spans - [w, h]))


def encode(p, w, h):
    q = normalize(p)
    # fq minimizes s in (s+dx,s+dy). Keeping one offset zero avoids an
    # artificial sub-unit s while retaining exactly the desired rectangle.
    small = min(w, h)
    s = small + bloat(q, w, h)
    lines = [f'{len(q)} {s:.17g}']
    lines.extend(f'{x:.17g} {y:.17g} {math.degrees(a):.17g}' for x, y, a in q)
    return '\n'.join(lines) + '\n', [w-small, h-small]


def decode(path, expected_n):
    lines = Path(path).read_text().splitlines()
    if int(lines[0].split()[0]) != expected_n or len(lines) != expected_n + 1:
        raise ValueError('fq output count mismatch')
    q = np.array([[float(x) for x in line.split()] for line in lines[1:]])
    if q.shape != (expected_n, 3) or not np.isfinite(q).all():
        raise ValueError('Invalid fq coordinates')
    q[:, 2] = np.radians(q[:, 2])
    return legalize(q, clearance=2e-9)


def certify(p):
    metric = load_metric(ROOT / 'research/official_metric_v17.py')
    rows = [dict(n=str(len(p)), square_id=str(i), x=f'{x:.17g}', y=f'{y:.17g}', angle=f'{a:.17g}')
            for i, (x, y, a) in enumerate(p)]
    raw = metric._evaluate_puzzle_worker((len(p), rows))
    frame = pd.read_csv(io.StringIO(pd.DataFrame(rows).to_csv(index=False)))
    numeric = list(csv.DictReader(io.StringIO(frame.to_csv(index=False, float_format='%.17g'))))
    rounded = metric._evaluate_puzzle_worker((len(p), numeric))
    return {'metric_sha256': OFFICIAL_SHA256, 'raw_reason': raw[3], 'roundtrip_reason': rounded[3],
            'raw_side': raw[2], 'roundtrip_side': rounded[2],
            'valid': raw[3] == rounded[3] == 'ok' and abs(raw[1]-rounded[1]) < 1e-10}


def trial(job):
    key, p, mode, binary, out, seed, cap, deadline = job
    w, h, d = map(int, key.split('_'))
    if len(p) != w*h+d:
        raise ValueError('Rectangle dimensions/count mismatch')
    remaining = deadline-time.monotonic()
    record = {'key': key, 'mode': mode, 'seed': seed, 'before': bloat(p, w, h)}
    if remaining <= 1:
        return {**record, 'status': 'budget-skipped'}, None
    name = f'{key}-{mode}-{seed}'
    inp, dst = Path(out)/f'{name}.in', Path(out)/f'{name}.out'
    text, offsets = encode(p, w, h)
    inp.write_text(text)
    command = [binary, 'quench', '--in', str(inp), '--out', str(dst),
               '--rect-dx', str(offsets[0]), '--rect-dy', str(offsets[1]),
               '--seed', str(seed)] + MODES[mode]
    start = time.monotonic()
    try:
        run = subprocess.run(command, capture_output=True, text=True, timeout=min(cap, remaining))
    except subprocess.TimeoutExpired:
        return {**record, 'status': 'timeout', 'seconds': time.monotonic()-start}, None
    record.update(seconds=time.monotonic()-start, returncode=run.returncode)
    (Path(out)/f'{name}.log').write_text(run.stdout + '\n' + run.stderr)
    if run.returncode != 0 or not dst.exists():
        return {**record, 'status': 'failed'}, None
    try:
        report = json.loads(run.stdout.strip().splitlines()[-1])
        if not isinstance(report, dict):
            raise ValueError('Optimizer report must be an object')
        # Python accepts nonstandard NaN/Infinity and overflowing exponents
        # by default. Reject them before strict checkpoint serialization.
        json.dumps(report, allow_nan=False)
        record['fq'] = report
    except (ValueError, IndexError):
        return {**record, 'status': 'invalid-optimizer-report'}, None
    try:
        q = decode(dst, len(p))
    except (ValueError, IndexError, OSError):
        return {**record, 'status': 'invalid-optimizer-coordinates'}, None
    if q is None:
        return {**record, 'status': 'failed-clearance'}, None
    record['after'] = bloat(q, w, h)
    record['gain'] = record['before'] - record['after']
    if record['after'] > record['before'] + .002:
        return {**record, 'status': 'outside-near-best-band'}, None
    record['certificate'] = certify(q)
    if not record['certificate']['valid']:
        return {**record, 'status': 'failed-official'}, None
    sha = hashlib.sha256(q.astype('<f8').tobytes()).hexdigest()
    record.update(status='certified', geometry_sha256=sha,
                  strict_improvement=record['gain'] > 5e-9)
    return record, (f'{key}__fq_{sha[:20]}', q)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--bank', type=Path, required=True)
    ap.add_argument('--priorities', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--keys', type=int, default=6)
    ap.add_argument('--seconds', type=float, default=300)
    ap.add_argument('--trial-seconds', type=float, default=40)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--modes', choices=list(MODES), nargs='+', default=list(MODES))
    args = ap.parse_args()
    if min(args.seconds, args.trial_seconds, args.workers, args.keys) <= 0:
        ap.error('Budgets/counts must be positive')
    args.out.mkdir(parents=True, exist_ok=False)
    frozen_binary = args.out/'fq'
    shutil.copy2(args.binary, frozen_binary)
    frozen_binary.chmod(0o500)
    if digest(frozen_binary) != digest(args.binary):
        raise ValueError('Executable changed while freezing the run')
    priorities = json.loads(args.priorities.read_text())
    with np.load(args.bank, allow_pickle=False) as archive:
        keys = sorted(archive.files, key=lambda k: -priorities[k])[:args.keys]
        bank = {k: archive[k] for k in keys}
    manifest = {'source_repository': 'https://github.com/evand/square-packing',
                'source_commit': SOURCE_COMMIT, 'license': 'MIT; copyright2026 Evan Daniel',
                'binary_sha256': digest(frozen_binary), 'bank_sha256': digest(args.bank),
                'priorities_sha256': digest(args.priorities), 'keys': keys,
                'modes': {name: MODES[name] for name in args.modes},
                'seconds': args.seconds, 'trial_seconds': args.trial_seconds, 'workers': args.workers}
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    deadline = time.monotonic()+args.seconds
    jobs = [(k, bank[k], mode, str(frozen_binary.resolve()), str(args.out.resolve()), 431001+i,
             args.trial_seconds, deadline) for i, (mode, k) in enumerate(
                 (mode, key) for mode in args.modes for key in keys)]
    records, donors = [], {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(trial, job): job for job in jobs}
        for future in as_completed(pending):
            try:
                record, donor = future.result()
            except Exception as exc:
                job = pending[future]
                # Preserve completed candidates and account for every failed
                # trial. Never turn an exceptional worker into geometry.
                record = {'key': job[0], 'mode': job[2], 'seed': job[5],
                          'status': 'worker-error', 'error_type': type(exc).__name__}
                donor = None
            records.append(record)
            if donor:
                donors[donor[0]] = donor[1]
                with (args.out/'donors.npz.incoming').open('wb') as stream:
                    np.savez_compressed(stream, **donors)
                (args.out/'donors.npz.incoming').replace(args.out/'donors.npz')
            (args.out/'results.json.incoming').write_text(json.dumps(records, indent=2)+'\n')
            (args.out/'results.json.incoming').replace(args.out/'results.json')
            print(json.dumps({k: v for k, v in record.items() if k not in ('fq', 'certificate')}), flush=True)


if __name__ == '__main__':
    main()
