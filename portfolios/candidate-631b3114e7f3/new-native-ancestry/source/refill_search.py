"""Upright-square refill around a fixed tilted core.

Independent implementation inspired by the public FTMC/MILP method described at
https://www.kaggle.com/code/cdeotte/squares-in-squares-ftmc-milp-refill-22-311 .
It constructs a finite candidate set, then solves maximum independent set on its
axis-aligned overlap graph. The answer is optimal on that finite set, not a
certificate of the continuous packing optimum. Every exported improvement must
still pass the official interval metric.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree


def sat_gaps(centers, tilted):
    """Minimum SAT separation of each upright candidate from the entire core."""
    centers = np.asarray(centers, dtype=float).reshape(-1, 2)
    tilted = np.asarray(tilted, dtype=float).reshape(-1, 3)
    if not len(tilted):
        return np.full(len(centers), np.inf)
    result = np.full(len(centers), np.inf)
    # Bound temporary arrays when this is applied to a full competition puzzle.
    for begin in range(0, len(centers), 1024):
        delta = centers[begin:begin + 1024, None, :] - tilted[None, :, :2]
        c, s = np.cos(tilted[:, 2]), np.sin(tilted[:, 2])
        r = .5 * (1 + np.abs(c) + np.abs(s))
        a = np.abs(delta[:, :, 0])
        b = np.abs(delta[:, :, 1])
        u = np.abs(delta[:, :, 0] * c + delta[:, :, 1] * s)
        v = np.abs(-delta[:, :, 0] * s + delta[:, :, 1] * c)
        result[begin:begin + 1024] = (np.maximum.reduce([a, b, u, v]) - r).min(1)
    return result


def forbidden_interval(fixed, square, fixed_axis=1, margin=1e-9):
    """Open interval of the free center coordinate colliding with one core square.

    Intersect the four separating-axis slabs analytically. This is a horizontal
    or vertical section of the exact octagonal Minkowski-sum exclusion region.
    """
    x, y, angle = square
    c, s = math.cos(angle), math.sin(angle)
    radius = .5 * (1 + abs(c) + abs(s)) + margin
    center = (x, y)
    delta = fixed - center[fixed_axis]
    lo, hi = -math.inf, math.inf
    for axis in ((1., 0.), (0., 1.), (c, s), (-s, c)):
        free = axis[1 - fixed_axis]
        offset = axis[fixed_axis] * delta
        if abs(free) < 1e-14:
            if abs(offset) >= radius:
                return None
            continue
        a, b = (-radius - offset) / free, (radius - offset) / free
        lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
        if lo >= hi:
            return None
    return center[1 - fixed_axis] + lo, center[1 - fixed_axis] + hi


def generate_candidates(W, H, tilted, incumbents=None, depth=4, margin=1e-9, soft=0.):
    tilted = np.asarray(tilted, dtype=float).reshape(-1, 3)
    pitch = 1. + 4 * margin
    xs = np.r_[.5 + margin + np.arange(max(0, int(W))) * pitch,
               W - .5 - margin - np.arange(max(0, int(W))) * pitch]
    ys = np.r_[.5 + margin + np.arange(max(0, int(H))) * pitch,
               H - .5 - margin - np.arange(max(0, int(H))) * pitch]
    points = []
    if len(xs) and len(ys):
        gx, gy = np.meshgrid(xs, ys)
        points.extend(np.column_stack([gx.ravel(), gy.ravel()]))
    if incumbents is not None:
        old = np.asarray(incumbents, dtype=float).reshape(-1, 3)
        points.extend(old[:, :2])
    # The wall lattice determines one coordinate. Contacts with exclusion edges
    # determine the other, and integer steps walk along the upright staircase.
    for fixed_axis, anchors in ((1, ys), (0, xs)):
        for square in tilted:
            for fixed in anchors:
                interval = forbidden_interval(fixed, square, fixed_axis, 2 * margin - soft)
                if interval is None:
                    continue
                for edge, direction in zip(interval, (-1., 1.)):
                    for step in range(depth + 1):
                        free = edge + direction * (margin + step * pitch)
                        points.append((free, fixed) if fixed_axis == 1 else (fixed, free))
    if not points:
        return np.empty((0, 2))
    candidates = np.asarray(points, dtype=float)
    inside = ((candidates[:, 0] >= .5 - 1e-12) &
              (candidates[:, 0] <= W - .5 + 1e-12) &
              (candidates[:, 1] >= .5 - 1e-12) &
              (candidates[:, 1] <= H - .5 + 1e-12))
    candidates = candidates[inside]
    if not len(candidates):
        return candidates
    candidates = candidates[sat_gaps(candidates, tilted) >= .5 * margin - soft]
    # Coalesce numerical copies without moving any actual candidate coordinate.
    _, unique = np.unique(np.round(candidates, 8), axis=0, return_index=True)
    return candidates[np.sort(unique)]


def conflict_graph(centers, margin=1e-9):
    centers = np.asarray(centers, dtype=float).reshape(-1, 2)
    graph = [set() for _ in centers]
    pairs = cKDTree(centers).query_pairs(math.sqrt(2) * (1 + margin), output_type='ndarray')
    if len(pairs):
        delta = np.abs(centers[pairs[:, 0]] - centers[pairs[:, 1]])
        pairs = pairs[np.all(delta < 1 + .5 * margin, axis=1)]
        for i, j in pairs:
            graph[int(i)].add(int(j)); graph[int(j)].add(int(i))
    return graph


def maximum_independent_set(graph, time_limit=1.):
    """Safe simplicial reduction followed by independent component MILPs.

    A vertex with clique neighborhood can be included in some maximum solution.
    The reduction preserves the finite graph optimum. MILP timeouts return a
    feasible incumbent and explicitly report that optimality was not proved.
    """
    active = set(range(len(graph)))
    chosen = []
    reduced = 0
    while active:
        found = False
        for v in sorted(active, key=lambda k: len(graph[k] & active)):
            neighbors = graph[v] & active
            if all((neighbors - {u}) <= graph[u] for u in neighbors):
                chosen.append(v)
                active.difference_update(neighbors | {v})
                reduced += 1
                found = True
                break
        if not found:
            break
    components = []
    unseen = set(active)
    while unseen:
        todo = [unseen.pop()]
        component = []
        while todo:
            v = todo.pop(); component.append(v)
            adjacent = graph[v] & unseen
            unseen.difference_update(adjacent); todo.extend(adjacent)
        components.append(component)
    optimal = True
    for component in sorted(components, key=len):
        index = {v: k for k, v in enumerate(component)}
        edges = [(index[v], index[u]) for v in component for u in graph[v]
                 if u in index and u > v]
        rows = np.repeat(np.arange(len(edges)), 2)
        columns = np.asarray(edges, dtype=int).ravel()
        A = coo_matrix((np.ones(len(columns)), (rows, columns)),
                       shape=(len(edges), len(component))).tocsr()
        result = milp(-np.ones(len(component)), integrality=np.ones(len(component)),
                      bounds=Bounds(0, 1), constraints=LinearConstraint(A, -np.inf, 1),
                      options={'time_limit': max(.01, time_limit), 'mip_rel_gap': 0.})
        if result.x is not None:
            selected = [component[k] for k in np.flatnonzero(result.x > .5)]
            assert all(not (graph[v] & set(selected)) for v in selected)
            chosen.extend(selected)
        else:
            # Deterministic feasible fallback for a timeout without an incumbent.
            remaining = set(component)
            while remaining:
                v = min(remaining, key=lambda k: len(graph[k] & remaining))
                chosen.append(v); remaining.difference_update(graph[v] | {v})
        optimal &= result.status == 0
    return chosen, {'simplicial_selected': reduced, 'milp_components': list(map(len, components)),
                    'finite_set_optimal': bool(optimal)}


def fill_rect(W, H, tilted, incumbents=None, depth=4, time_limit=1., margin=1e-9, soft=0.):
    """Return (upright poses, info) around a fixed tilted core in W by H.

    With soft>0, bounded overlaps with the core are permitted as *search seeds*;
    the return value is then explicitly unsuitable for export until repaired.
    Upright/upright conflicts remain strict regardless of soft.
    """
    if soft < 0:
        raise ValueError('soft overlap tolerance must be nonnegative')
    started = time.monotonic()
    candidates = generate_candidates(W, H, tilted, incumbents, depth, margin, soft)
    graph = conflict_graph(candidates, margin)
    selected, info = maximum_independent_set(graph, time_limit)
    upright = np.column_stack([candidates[selected], np.zeros(len(selected))])
    core_gap = float(sat_gaps(upright[:, :2], tilted).min()) if len(upright) and len(tilted) else None
    info.update(candidates=len(candidates), selected=len(selected), elapsed=time.monotonic() - started,
                soft_core_tolerance=soft, upright_core_min_gap=core_gap,
                requires_repair=bool(soft or (core_gap is not None and core_gap <= 0)))
    return upright, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gadgets', default='artifacts/public/gadgets_39_and_baselines.npz')
    parser.add_argument('--indices', default='0,6,7,27,30')
    parser.add_argument('--shrink', type=float, default=0.)
    parser.add_argument('--time-limit', type=float, default=1.)
    parser.add_argument('--out', default='artifacts/candidates/refill-gadgets.json')
    args = parser.parse_args()
    data = np.load(args.gadgets)
    results = {}
    for i in map(int, args.indices.split(',')):
        w, h, dm, before, after, delta = data['meta_39'][i]
        source = data[f'after_{i}'].copy()
        half = .5 * (np.abs(np.cos(source[:, 2])) + np.abs(np.sin(source[:, 2])))
        source[:, :2] -= (source[:, :2] - half[:, None]).min(0)
        W, H = w + after - args.shrink, h + after - args.shrink
        angle = np.abs((source[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4)
        cutoff = np.deg2rad(1.)
        tilted = source[angle > cutoff].copy()
        tilted[:, :2] -= args.shrink / 2
        upright, info = fill_rect(W, H, tilted, source[angle <= cutoff], time_limit=args.time_limit)
        info.update(index=i, w=w, h=h, surplus=dm, bloat=after - args.shrink,
                    tilted=len(tilted), total=len(tilted) + len(upright), required=len(source))
        print(json.dumps(info), flush=True)
        results[str(i)] = {'tilted': tilted.tolist(), 'upright': upright.tolist(), 'info': info}
    output = Path(args.out); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results))


if __name__ == '__main__':
    main()
