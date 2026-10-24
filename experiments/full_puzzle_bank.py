"""Select diverse current full-puzzle packings for bounded FTMC experiments.

Every seed is the complete current packing for n = k*k+d in a (k+f) square.
There is no composition interface to preserve. The ranking estimates the gain
from a hypothetical side reduction and L-frame propagation, not achieved gain.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def geometry(p):
    p = np.array(p, dtype=float, copy=True)
    extent = .5 * (np.abs(np.cos(p[:, 2])) + np.abs(np.sin(p[:, 2])))
    p[:, :2] -= (p[:, :2] - extent[:, None]).min(axis=0)
    dimensions = ((p[:, :2] + extent[:, None]).max(axis=0)
                  - (p[:, :2] - extent[:, None]).min(axis=0))
    return p, float(dimensions.max())


def core_signature(p):
    """D4/translation invariant duplicate detector for existing tilted cores.

    Quantization is only a sampling heuristic. It is never a geometry certificate.
    """
    a = (p[:, 2] + np.pi / 4) % (np.pi / 2) - np.pi / 4
    core = p[np.abs(a) > .018]
    variants = []
    for transpose in (False, True):
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            q = core.copy()
            if transpose:
                q[:, :2] = q[:, [1, 0]]
                q[:, 2] = np.pi / 2 - q[:, 2]
            q[:, 0] *= sx
            q[:, 1] *= sy
            q[:, 2] *= sx * sy
            q[:, :2] -= q[:, :2].min(axis=0)
            # The fourth-angle circle represents orientation modulo pi/2 and
            # avoids a discontinuity when a numerical angle straddles pi/4.
            values = np.column_stack((q[:, :2], np.cos(4*q[:, 2]), np.sin(4*q[:, 2])))
            integers = np.rint(values * 1e6).astype('<i8')
            order = np.lexsort(tuple(integers[:, i] for i in range(3, -1, -1)))
            variants.append(integers[order].tobytes())
    return hashlib.sha256(min(variants)).hexdigest()


def read_packings(csv_path):
    frame = pd.read_csv(csv_path, usecols=['n', 'square_id', 'x', 'y', 'angle'])
    packings = {}
    for n, group in frame.groupby('n', sort=True):
        n = int(n)
        if (len(group) != n or sorted(group.square_id.tolist()) != list(range(n))):
            raise ValueError('Incomplete or duplicate puzzle: ' + str(n))
        q = group.sort_values('square_id')[['x', 'y', 'angle']].to_numpy(float)
        if not np.isfinite(q).all():
            raise ValueError('Nonfinite pose: ' + str(n))
        packings[n] = geometry(q)
    if set(packings) != set(range(1, 1001)):
        raise ValueError('A complete n=1..1000 current baseline is required')
    return packings


def select_targets(packings, min_n=80, max_n=324, count=24,
                   max_core=100, hypothetical_reduction=.01):
    """Return balanced, nonduplicate targets and an auditable exclusion record."""
    ranked = []
    rejected = {}
    # Remove exact L-extensions of the same core, even if the smaller exemplar
    # lies outside the experiment range. Their shared motif needs only one arm.
    smallest_core = {}
    for n in sorted(packings):
        q, side = packings[n]
        a = (q[:, 2] + np.pi/4) % (np.pi/2) - np.pi/4
        core_count = int(np.count_nonzero(np.abs(a) > .018))
        if core_count < 4 or core_count > max_core:
            continue
        signature = core_signature(q)
        smallest_core.setdefault(signature, n)
        if not min_n <= n <= max_n:
            continue
        k = math.isqrt(n)
        d = n-k*k
        f = side-k
        if d == 0 or not .12 < f < .999999:
            rejected[str(n)] = 'perfect square or unsupported fractional side'
            continue
        if smallest_core[signature] != n:
            rejected[str(n)] = {'duplicate_tilted_core_of_n': smallest_core[signature]}
            continue
        # Known single-angle lattice constructions are poor exploratory controls
        # for this small pilot; keep the more diverse contact topologies.
        tilted_angles = a[np.abs(a) > .018]
        orientation_spread = abs(np.mean(np.exp(4j*tilted_angles)))
        if orientation_spread > 1-1e-7:
            rejected[str(n)] = 'uniform-angle core; excluded from diverse-topology pilot'
            continue
        targets = []
        for target_k in range(k, 32):
            target_n = target_k*target_k+d
            if target_n > 1000:
                continue
            target_side = packings[target_n][1]
            candidate_side = target_k+max(0., f-hypothetical_reduction)
            gain = max(0., target_side-candidate_side)/math.sqrt(target_n)
            targets.append({'n': target_n, 'baseline_side': target_side,
                            'hypothetical_score_gain': gain})
        potential = sum(t['hypothetical_score_gain'] for t in targets)
        # Rough size scaling is only a scheduling prior until GPU throughput is
        # measured. The report retains unscaled potential and source dimensions.
        work_proxy = (n/100.)**1.3+(core_count/40.)**1.3
        ranked.append({'n': n, 'key': f'{k}_{k}_{d}', 'w': k, 'h': k, 'surplus': d,
                       'side': side, 'bloat': f, 'core_count': core_count,
                       'core_signature': signature, 'orientation_spread': float(orientation_spread),
                       'hypothetical_reduction': hypothetical_reduction,
                       'hypothetical_score_gain': potential, 'targets': targets,
                       'work_proxy': work_proxy, 'ranking_value': potential/work_proxy})
    ranked.sort(key=lambda r: (-r['ranking_value'], r['n']))
    # Spread selections across five equal n intervals, then fill any empty slots.
    selected = []
    edges = np.linspace(min_n, max_n+1, 6)
    quota = count//5
    for low, high in zip(edges[:-1], edges[1:]):
        selected.extend([r for r in ranked if low <= r['n'] < high][:quota])
    seen = {r['n'] for r in selected}
    selected.extend([r for r in ranked if r['n'] not in seen][:max(0, count-len(selected))])
    selected = sorted(selected[:count], key=lambda r: r['n'])
    if not selected:
        raise ValueError('No supported diverse full-puzzle targets')
    return selected, {'eligible': len(ranked), 'selected': selected, 'rejected': rejected,
                      'ranked': ranked, 'selection': {'min_n': min_n, 'max_n': max_n,
                          'count': count, 'max_core': max_core,
                          'hypothetical_reduction': hypothetical_reduction,
                          'note': 'Hypothetical gains are scheduling estimates, not achieved improvements.'}}


def build_full_puzzle_bank(csv_path, **selection):
    path = Path(csv_path)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    packings = read_packings(path)
    selected, report = select_targets(packings, **selection)
    bank = {}
    variants = {}
    provenance = {}
    priorities = {}
    peak = max(r['ranking_value'] for r in selected)
    for record in selected:
        key, n = record['key'], record['n']
        q = packings[n][0]
        bank[key] = q
        variants[key+'__current'] = q
        provenance[key] = {'source': 'complete current competition packing',
            'n': n, 'baseline_sha256': source_hash, 'initial_bloat': record['bloat'],
            'core_count': record['core_count'], 'core_signature': record['core_signature']}
        priorities[key] = record['ranking_value']/peak
    report.update(baseline_sha256=source_hash, target_types=len(bank),
                  worker_sampling_priorities=priorities, history_resume_disabled=True)
    return bank, variants, provenance, priorities, report


def load_prepared_bank(directory='.'):
    root = Path(directory)
    def arrays(name):
        with np.load(root/name) as z:
            return {k: z[k] for k in z.files}
    return (arrays('full_bank.npz'), arrays('full_variants.npz'),
            json.loads((root/'full_provenance.json').read_text()), {},
            json.loads((root/'full_priorities.json').read_text()),
            json.loads((root/'full_targeting.json').read_text()))
