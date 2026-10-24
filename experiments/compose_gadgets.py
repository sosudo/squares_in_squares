#!/usr/bin/env python3
"""Compose rectangular square-packing motifs and certify improving full puzzles.

The CPU implementation uses conservative empty-corner staircase joins inspired
by Chris Deotte's public multi-gadget fault construction. The optional GPU
adapter runs Vladislav Lavrentev's released corner/separator DP implementations
in an isolated work directory, with explicit current-portfolio and fresh-donor
inputs. It never overwrites the incumbent CSV. Original source notices apply.
"""
from __future__ import annotations

import argparse
import atexit
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

_GPU_SOURCE_CACHE = {}

BOUNDED_INDEX_HELPER = '''
def _bounded_active_indices(best, chunk_size=8388608):
    """Same sorted finite-state indices, with bounded temporary scan buffers."""
    if chunk_size < 1:
        raise ValueError('Index chunk size must be positive')
    flat=best.ravel();parts=[]
    for start in range(0,flat.size,chunk_size):
        local=cp.flatnonzero(flat[start:start+chunk_size]!=np.uint64(0xffffffffffffffff))
        if local.size:
            parts.append(local+np.int64(start))
    return cp.concatenate(parts) if parts else cp.empty(0,dtype=cp.int64)

'''


def compatible_gpu_sources(source_dir):
    """Preserve originals; make the unsigned sentinel explicit for modern CuPy.

    A Python integer 2**64-1 is otherwise inferred as signed by some CuPy
    comparison kernels and raises OverflowError. The uint64 value is unchanged.
    Sources remain alive for the process because the public modules hash their
    own __file__ during later calls, including after preflight has completed.
    """
    source_dir = source_dir.resolve()
    if str(source_dir) in _GPU_SOURCE_CACHE:
        return _GPU_SOURCE_CACHE[str(source_dir)]
    destination = Path(tempfile.mkdtemp(prefix='squares-gpu-source-compat-'))
    shutil.copytree(source_dir, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    old = 'best!=np.iinfo(np.uint64).max'
    new = 'best!=np.uint64(0xffffffffffffffff)'
    patches = []
    for name in ['gpu_seam_profiles.py', 'gpu_adaptive_seams.py']:
        path = destination/name
        original = path.read_bytes()
        text = original.decode()
        if text.count(old) != 1:
            raise ValueError(f'Unexpected public comparison source in {name}')
        changed_text = text.replace(old, new)
        bounded = name == 'gpu_adaptive_seams.py'
        if bounded:
            expression = 'cp.flatnonzero(best!=np.uint64(0xffffffffffffffff))'
            if changed_text.count(expression)!=1 or changed_text.count('def pareto(best,nb):')!=1:
                raise ValueError('Unexpected public adaptive compaction source')
            changed_text=changed_text.replace(expression,'_bounded_active_indices(best)')
            changed_text=changed_text.replace('def pareto(best,nb):',BOUNDED_INDEX_HELPER+'def pareto(best,nb):')
            old_donors='donors=fresh+donors+legacy'
            if changed_text.count(old_donors)!=1:
                raise ValueError('Unexpected public donor assembly source')
            changed_text=changed_text.replace(old_donors,
                'donors=[(p,label) for p,label in fresh+donors+legacy if np.any(p[:,2]!=0.)]')
        changed = changed_text.encode()
        path.write_bytes(changed)
        patches.append({'file': name, 'reason': 'CuPy uint64 sentinel type compatibility',
                        'original_sha256': hashlib.sha256(original).hexdigest(),
                        'runtime_sha256': hashlib.sha256(changed).hexdigest(),
                        'old_expression': old, 'new_expression': new,
                        'bounded_index_compaction': bounded,
                        'skip_exact_zero_angle_donors':bounded,
                        'index_chunk_size':8388608 if bounded else None})
    atexit.register(shutil.rmtree, destination, ignore_errors=True)
    _GPU_SOURCE_CACHE[str(source_dir)] = (destination, patches)
    return destination, patches


def extents(p):
    h = .5 * (np.abs(np.cos(p[:, 2])) + np.abs(np.sin(p[:, 2])))
    return p[:, :2] - h[:, None], p[:, :2] + h[:, None]


def normalize(p):
    p = np.asarray(p, dtype=float).copy()
    lo, _ = extents(p)
    p[:, :2] -= lo.min(axis=0)
    return p


def side(p):
    lo, hi = extents(p)
    return float((hi.max(axis=0) - lo.min(axis=0)).max())


def legalize(p, clearance=2e-9):
    """Outward center dilation repairs rounding only; large overlaps are rejected."""
    p = normalize(p)
    if not np.isfinite(p).all():
        return None
    pairs = cKDTree(p[:, :2]).query_pairs(1.5, output_type='ndarray')
    if len(pairs):
        i, j = pairs.T
        delta = p[j, :2] - p[i, :2]
        a, b = p[i, 2], p[j, 2]
        projection = np.maximum.reduce([
            np.abs(delta[:, 0] * np.cos(t) + delta[:, 1] * np.sin(t))
            for t in (a, a + math.pi / 2, b, b + math.pi / 2)])
        radius = .5 * (1 + np.abs(np.cos(a - b)) + np.abs(np.sin(a - b)))
        factor = max(1., float(np.max((radius + clearance) / np.maximum(projection, 1e-30))))
        if factor > 1.000001:
            return None
        p[:, :2] *= factor
    return normalize(p)


def read_baseline(path):
    df = pd.read_csv(path)
    result = {int(n): q.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
              for n, q in df.groupby('n', sort=True)}
    if set(result) != set(range(1, 1001)) or any(len(p) != n for n, p in result.items()):
        raise ValueError('Expected complete baseline for n=1..1000')
    return result


def read_donors(paths):
    donors = []
    for path in paths:
        with np.load(path, allow_pickle=False) as archive:
            for key in archive.files:
                p = np.asarray(archive[key], dtype=float)
                if p.ndim != 2 or p.shape[1] != 3 or not len(p):
                    raise ValueError(f'Invalid pose array: {path}:{key}')
                q = legalize(p)
                if q is not None:
                    donors.append((q, f'{path.name}:{key}'))
    return donors


def orientations(p):
    seen = set()
    for swap in (False, True):
        q = p.copy()
        if swap:
            q[:, :2] = q[:, [1, 0]]
            q[:, 2] = math.pi / 2 - q[:, 2]
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            r = q.copy()
            r[:, 0] *= sx
            r[:, 1] *= sy
            r[:, 2] *= sx * sy
            r = normalize(r)
            digest = hashlib.sha256(np.round(r, 8).tobytes()).digest()
            if digest not in seen:
                seen.add(digest)
                yield r, (swap, sx, sy)


@dataclass
class Gadget:
    w: int
    h: int
    d: int
    br: int
    tl: int
    f: float
    p: np.ndarray
    source: str


def extract_gadgets(donors, seconds=60.):
    """Vectorized crop order statistics; retain the best of each corner type."""
    started = time.monotonic()
    best = {}
    visited = 0
    for p, label in donors:
        for q, transform in orientations(p):
            lo, hi = extents(q)
            spans = hi.max(axis=0)
            maxw, maxh = np.minimum(31, np.floor(spans + 1e-7).astype(int))
            wh = np.array([(w, h) for w in range(1, maxw + 1)
                           for h in range(1, maxh + 1) if w * h < len(q)], dtype=int)
            if not len(wh):
                continue
            r = np.maximum(np.maximum(hi[None, :, 0] - wh[:, None, 0],
                                      hi[None, :, 1] - wh[:, None, 1]), 0.)
            order = np.argsort(r, axis=1, kind='stable')
            sorted_r = np.take_along_axis(r, order, axis=1)
            sizes = np.arange(1, len(q) + 1)[None, :]
            surplus = sizes - (wh[:, 0] * wh[:, 1])[:, None]
            mask = ((surplus > 0) & (surplus <= 63) &
                    (sorted_r > 1e-10) & (sorted_r < 1. - 1e-7))
            br_bad = (hi[None, :, 0] > wh[:, None, 0] + 1e-10) & (lo[None, :, 1] < 1. + 1e-10)
            tl_bad = (lo[None, :, 0] < 1. + 1e-10) & (hi[None, :, 1] > wh[:, None, 1] + 1e-10)
            br_bad = np.maximum.accumulate(np.take_along_axis(br_bad, order, axis=1), axis=1)
            tl_bad = np.maximum.accumulate(np.take_along_axis(tl_bad, order, axis=1), axis=1)
            for row, last in np.argwhere(mask):
                w, h = map(int, wh[row])
                d = int(surplus[row, last])
                br, tl = int(not br_bad[row, last]), int(not tl_bad[row, last])
                f = float(sorted_r[row, last]) + 3e-8
                key = (w, h, d, br, tl)
                if key not in best or f < best[key].f - 1e-10:
                    best[key] = Gadget(w, h, d, br, tl, f,
                                       q[order[row, :last + 1]].copy(),
                                       f'{label}:D4={transform}:crop={w},{h},{d}')
            visited += 1
            if visited % 100 == 0:
                print(json.dumps({'stage': 'crop', 'orientations': visited,
                                  'gadgets': len(best), 'seconds': time.monotonic() - started}), flush=True)
            if time.monotonic() - started >= seconds:
                return sorted(best.values(), key=lambda g: g.f)
    return sorted(best.values(), key=lambda g: g.f)


def staircase_dp(gadgets, rounds=4):
    """Minimax over rectangular fault chains, including one-cell X/Y buffers."""
    shape = (32, 32, 64, 2)
    value = np.full(shape, np.inf)
    last = np.full(shape, -1, dtype=np.int32)
    mode = np.full(shape, -1, dtype=np.int8)
    predecessor_br = np.full(shape, -1, dtype=np.int8)
    for i, g in enumerate(gadgets):
        idx = (g.w, g.h, g.d, g.br)
        if g.f < value[idx]:
            value[idx], last[idx], mode[idx] = g.f, i, 3
    for iteration in range(rounds):
        changes = 0
        for gi, g in enumerate(gadgets):
            for join in range(3):
                dx, dy = g.w + (join == 1), g.h + (join == 2)
                if dx >= 31 or dy >= 31 or g.d >= 63:
                    continue
                source = value[1:32 - dx, 1:32 - dy, 1:64 - g.d]
                if join != 0 or g.tl:
                    pb = (source[..., 1] < source[..., 0]).astype(np.int8)
                    previous = np.minimum(source[..., 0], source[..., 1])
                else:
                    pb = np.ones(source.shape[:-1], dtype=np.int8)
                    previous = source[..., 1]
                candidate = np.maximum(g.f, previous)
                destination = (slice(dx + 1, 32), slice(dy + 1, 32),
                               slice(g.d + 1, 64), g.br)
                improve = candidate < value[destination] - 1e-12
                count = int(improve.sum())
                if count:
                    value[destination][improve] = candidate[improve]
                    last[destination][improve] = gi
                    mode[destination][improve] = join
                    predecessor_br[destination][improve] = pb[improve]
                    changes += count
        print(json.dumps({'stage': 'cpu-dp', 'round': iteration + 1,
                          'state_improvements': changes, 'gadgets': len(gadgets)}), flush=True)
        if not changes:
            break
    return value, last, mode, predecessor_br


def recover_chain(index, gadgets, last, mode, predecessor_br):
    w, h, d, b = map(int, index)
    chain = []
    while True:
        idx = (w, h, d, b)
        gi, join = int(last[idx]), int(mode[idx])
        if gi < 0:
            raise ValueError('Broken staircase predecessor')
        chain.append((gi, join))
        if join == 3:
            return list(reversed(chain))
        g = gadgets[gi]
        b = int(predecessor_br[idx])
        w -= g.w + (join == 1)
        h -= g.h + (join == 2)
        d -= g.d
        if min(w, h, d) <= 0:
            raise ValueError('Invalid staircase predecessor dimensions')


def stitch(chain, gadgets, k):
    width = sum(gadgets[i].w for i, _ in chain) + sum(m == 1 for _, m in chain[1:])
    height = sum(gadgets[i].h for i, _ in chain) + sum(m == 2 for _, m in chain[1:])
    if width > k or height > k:
        raise ValueError('Chain exceeds target square')
    f = max(gadgets[i].f for i, _ in chain)
    blocks, spans = [], []
    x, y = 0, height
    previous_width = 0
    for j, (i, join) in enumerate(chain):
        g = gadgets[i]
        if j:
            x += previous_width + (join == 1)
        y -= g.h + (join == 2)
        q = g.p.copy()
        q[:, :2] += [x, y]
        blocks.append(q)
        spans.append((x, y, g.w, g.h))
        previous_width = g.w
    fill = []
    for column in range(k):
        span = next((s for s in spans if s[0] <= column < s[0] + s[2]), None)
        if span:
            cut, occupied_height = span[1], span[3]
        else:
            following = next((s for s in spans if s[0] > column), None)
            cut, occupied_height = (following[1] + following[3] if following else 0), 0
        for row in range(k):
            if span and cut <= row < cut + occupied_height:
                continue
            shift = 0. if row < cut else f
            fill.append((column + .5 + shift, row + .5 + shift, 0.))
    p = np.vstack([np.asarray(fill).reshape(-1, 3), *blocks])
    expected = k * k + sum(gadgets[i].d for i, _ in chain)
    if len(p) != expected:
        raise ValueError(f'Composition count {len(p)} != {expected}')
    return legalize(p)


def cpu_compose(base, donors, seconds, rounds):
    gadgets = extract_gadgets(donors, seconds)
    if not gadgets:
        return {}, {'gadgets': 0}
    value, last, mode, predecessor = staircase_dp(gadgets, rounds)
    candidates, recipes = {}, {}
    for n in range(5, 1001):
        k = math.isqrt(n)
        d = n - k * k
        if not d:
            continue
        slab = value[1:k + 1, 1:k + 1, d]
        idx = np.unravel_index(np.argmin(slab), slab.shape)
        if k + slab[idx] >= side(base[n]) - 1e-7:
            continue
        state = (idx[0] + 1, idx[1] + 1, d, idx[2])
        chain = recover_chain(state, gadgets, last, mode, predecessor)
        p = stitch(chain, gadgets, k)
        if p is not None and side(p) < side(base[n]) - 1e-8:
            candidates[n] = p
            recipes[str(n)] = [{'source': gadgets[i].source, 'w': gadgets[i].w,
                               'h': gadgets[i].h, 'surplus': gadgets[i].d,
                               'bloat': gadgets[i].f, 'join_mode': m} for i, m in chain]
    return candidates, {'gadgets': len(gadgets), 'recipes': recipes}


def border_expand(p, t):
    p = normalize(p)
    if t == 0:
        return p
    L = side(p)
    k = int(math.floor(L + 1e-10))
    right = [(L + i + .5, j + .5, 0.) for i in range(t) for j in range(k)]
    top = [(i + .5, L + j + .5, 0.) for j in range(t) for i in range(k + t)]
    return np.vstack([p, right, top])


def closure(base, candidates, seconds=60., offsets=(-.5, 0., .5), min_donor_n=1):
    """L-frame and central-subset closure across the current union of portfolios."""
    started = time.monotonic()
    lengths = np.array([side(candidates.get(n, base[n])) for n in range(1, 1001)])
    result, labels = dict(candidates), {}
    donors = [(p, f'composed:{n}') for n, p in candidates.items()]
    donors += [(p, f'baseline:{n}') for n, p in base.items()
               if n >= min_donor_n and side(p) < math.ceil(math.sqrt(n)) - 1e-7]
    for p, source in donors:
        L = side(p)
        for t in range(max(0, int(math.floor(32. - L))) + 1):
            q = border_expand(p, t)
            lo, hi = extents(q)
            center = (lo.min(axis=0) + hi.max(axis=0)) / 2
            for dx in offsets:
                for dy in offsets:
                    c = center + [dx, dy]
                    radial = np.maximum(np.max(hi - c, axis=1), np.max(c - lo, axis=1))
                    order = np.argsort(radial, kind='stable')[:1000]
                    lower = np.minimum.accumulate(lo[order], axis=0)
                    upper = np.maximum.accumulate(hi[order], axis=0)
                    sides = (upper - lower).max(axis=1)
                    improve = np.flatnonzero(sides < lengths[:len(sides)] - 1e-7)
                    for idx in improve:
                        n = int(idx + 1)
                        result[n] = q[order[:n]].copy()
                        lengths[idx] = sides[idx]
                        labels[str(n)] = {'source': source, 'border': t, 'subset_shift': [dx, dy]}
            if time.monotonic() - started >= seconds:
                return result, labels
    return result, labels


def gpu_compose(base, baseline, donors, source_dir, output_dir, method, seconds, bins,
                degrees=(30,45,60)):
    """Stage public inputs and the explicit unsigned-sentinel compatibility patch."""
    runtime_sources, compatibility = compatible_gpu_sources(source_dir)
    oriented_upper_bound=8*(len(donors)+sum(len(p)>4 for p in base.values()))
    if oriented_upper_bound*(31*31*63)>2**32:
        raise ValueError('Adaptive oriented donor identifiers would overflow the public uint32 encoding')
    sys.path.insert(0, str(runtime_sources))
    import gpu_fault_composition as fault
    # Replace only the legacy file-loading entry point; geometry/kernels unchanged.
    fault.inputs = lambda: (base, {n: 'current certified portfolio' for n in base}, donors)
    import gpu_seam_profiles as seam
    seam.inputs = fault.inputs
    import gpu_adaptive_seams as adaptive
    previous = Path.cwd()
    all_candidates, reports = {}, {'_source_compatibility': compatibility,
        '_adaptive_oriented_upper_bound':oriented_upper_bound,
        '_donor_sources': [{'index': index, 'label': label,
                           'array_sha256': hashlib.sha256(p.tobytes()).hexdigest()}
                          for index, (p, label) in enumerate(donors)]}
    with tempfile.TemporaryDirectory(prefix='composition-', dir=output_dir) as directory:
        work = Path(directory)
        (work / 'artifacts').mkdir()
        (work / 'research/latest').mkdir(parents=True)
        shutil.copy2(baseline, work / 'research/latest/kirill.csv')
        np.savez_compressed(work / 'artifacts/fault_source_donors.npz')
        (work / 'artifacts/fault_source_labels.json').write_text('{}')
        # The names below are compatibility inputs expected by the public module;
        # their actual source labels and hashes are recorded in this adapter's report.
        np.savez_compressed(work / 'artifacts/tip_frontier1_gadgets.npz',
                            **{str(i): p for i, (p, _) in enumerate(donors)})
        np.savez_compressed(work / 'artifacts/crystal_polished1_gadgets.npz')
        methods = ('corner', 'seam', 'adaptive') if method == 'all' else (method,)
        try:
            os.chdir(work)
            for selected in methods:
                tag = 'compose_' + selected
                if selected == 'corner':
                    fault.run(seconds=seconds, tag=tag, transpose=True)
                elif selected == 'seam':
                    seam.run(seconds=seconds, tag=tag, bins=bins, transpose=True)
                else:
                    adaptive.run(str(baseline), tag=tag, seconds=seconds, bins=bins,degrees=tuple(degrees))
                path = work / 'artifacts' / (tag + '_packings.npz')
                with np.load(path, allow_pickle=False) as archive:
                    for key in archive.files:
                        n, p = int(key), archive[key]
                        if n not in all_candidates or side(p) < side(all_candidates[n]):
                            all_candidates[n] = p.copy()
                reports[selected] = json.loads((work / 'research' / (tag + '.json')).read_text())
                shutil.copy2(path, output_dir / path.name)
                import cupy as cp
                cp.get_default_memory_pool().free_all_blocks()
        finally:
            os.chdir(previous)
    return all_candidates, reports


def certify_candidates(base, candidates):
    project_scripts = Path(__file__).resolve().parents[1] / 'scripts'
    sys.path.insert(0, str(project_scripts))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_submission import Square, validate_puzzle
    result, rejected = {}, {}
    for n, p in sorted(candidates.items()):
        q = legalize(p)
        if q is None or side(q) >= side(base[n]) - 1e-8:
            continue
        rows = [[format(float(v), '.17g') for v in row] for row in q]
        certificate = validate_puzzle(n, [Square(*row) for row in rows])
        if certificate['valid']:
            result[str(n)] = {'side': certificate['side_upper'], 'squares': rows,
                              'source': 'gadget-composition', 'certificate': certificate}
        else:
            rejected[str(n)] = certificate
    return result, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--gadgets', nargs='*', type=Path, default=[])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--backend', choices=['cpu', 'gpu', 'closure'], default='cpu')
    parser.add_argument('--method', choices=['corner', 'seam', 'adaptive', 'all'], default='all')
    parser.add_argument('--source-dir', type=Path, default=Path('vendor/lightning_ftmc'))
    parser.add_argument('--baseline-donors', type=int, default=64)
    parser.add_argument('--seconds', type=float, default=60.,
                        help='Crop/extraction budget per composer; DP and certification add time')
    parser.add_argument('--closure-seconds', type=float, default=60.)
    parser.add_argument('--closure-offsets', type=float, nargs='+', default=[-.5,0.,.5])
    parser.add_argument('--closure-min-n', type=int, default=1)
    parser.add_argument('--rounds', type=int, default=4)
    parser.add_argument('--bins', type=int, default=16)
    parser.add_argument('--degrees', type=float, nargs='+', default=[30,45,60],
                        help='Adaptive separator normals; every value must be strictly between0 and90 degrees')
    args = parser.parse_args()
    if args.seconds <= 0 or args.closure_seconds < 0 or args.rounds < 1 or args.baseline_donors < 0:
        parser.error('Budgets/donor counts must be nonnegative; seconds and rounds must be positive')
    if not 2 <= args.bins <= 32:
        parser.error('Separator bins must be between 2 and 32')
    if not args.degrees or len(set(args.degrees))!=len(args.degrees) or any(not 0<d<90 for d in args.degrees):
        parser.error('Adaptive separator normals must be distinct and strictly between0 and90 degrees')
    args.baseline = args.baseline.resolve()
    args.output = args.output.resolve()
    args.output.parent.mkdir(exist_ok=True, parents=True)
    started = time.monotonic()
    base = read_baseline(args.baseline)
    donors = read_donors(args.gadgets)
    fresh = len(donors)
    eligible = [(p, f'certified baseline n={n}') for n, p in base.items()
                if n >= 5 and side(p) < math.ceil(math.sqrt(n)) - 1e-7]
    donors += eligible[:args.baseline_donors]
    if args.backend == 'cpu':
        candidates, details = cpu_compose(base, donors, args.seconds, args.rounds)
    elif args.backend == 'gpu':
        candidates, details = gpu_compose(base, args.baseline, donors, args.source_dir,
                                          args.output.parent, args.method, args.seconds, args.bins,args.degrees)
    else:
        candidates, details = {}, {}
    if args.closure_seconds > 0:
        candidates, closure_labels = closure(base, candidates, args.closure_seconds,
                                             args.closure_offsets, args.closure_min_n)
    else:
        closure_labels = {}
    result, rejected = certify_candidates(base, candidates)
    args.output.write_text(json.dumps(result) + '\n')
    gain = sum((side(base[int(n)]) - float(r['side'])) / math.sqrt(int(n)) for n, r in result.items())
    report = {'baseline': str(args.baseline),
              'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              'gadgets': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                          for p in args.gadgets],
              'backend': args.backend, 'fresh_donors': fresh, 'total_donors': len(donors),
              'degrees': args.degrees, 'bins':args.bins,
              'closure_offsets': args.closure_offsets, 'closure_min_n': args.closure_min_n,
              'seconds': time.monotonic() - started, 'improvements': len(result),
              'estimated_score_gain': gain, 'rejected': rejected,
              'details': details, 'closure': closure_labels}
    args.output.with_suffix('.report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('details', 'closure', 'rejected')}), flush=True)


if __name__ == '__main__':
    main()
