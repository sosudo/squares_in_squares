"""Restore a tilted core's wall position after public FTMC initialization.

The Apache-2.0 Lightning v21 mutation function remains unchanged. This optional
adapter translates each returned core rigidly within the original rectangular
box, preserving its original fractional wall clearance. Angles, relative square
positions, target side lengths and final admission checks are unchanged. It is
an exploratory initializer, not a geometry certificate.
"""
from __future__ import annotations

import functools
import hashlib
import inspect

import numpy as np


def bounds(p):
    p = np.asarray(p, dtype=float)
    radius = .5*(np.abs(np.cos(p[:, 2]))+np.abs(np.sin(p[:, 2])))
    return ((p[:, :2]-radius[:, None]).min(0),
            (p[:, :2]+radius[:, None]).max(0))


def incumbent_anchor(p, w, h):
    """Return source box and fractional free space below its tilted core."""
    p = np.asarray(p, dtype=float)
    mask = np.abs((p[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4) > .018
    if not mask.any():
        raise ValueError('A source tilted core is required')
    full_low, full_high = bounds(p)
    low, high = bounds(p[mask])
    f = float(np.max(full_high-full_low-[w, h]))
    box = np.array([w+f, h+f], dtype=float)
    free = box-(high-low)
    anchor = np.full(2, .5)
    np.divide(low-full_low, free, out=anchor, where=free > 1e-10)
    return box, np.clip(anchor, 0., 1.)


def reanchor(q, box, anchor):
    """Apply only a rigid translation; oversized exploration cores may overhang."""
    result = np.array(q, dtype=float, copy=True)
    low, high = bounds(result)
    desired_low = np.asarray(anchor)*(np.asarray(box)-(high-low))
    shift = desired_low-low
    result[:, :2] += shift
    return result, shift


def make_mutations(worker, enabled=False, policy='incumbent'):
    """Return a reviewed optional adapter without consuming additional RNG draws."""
    if policy not in ('incumbent', 'mixed_walls'):
        raise ValueError('Unknown anchor policy')
    original = worker.mutations
    try:
        source_hash = hashlib.sha256(inspect.getsource(original).encode()).hexdigest()
    except (OSError, TypeError):
        source_hash = None
    audit = {'enabled': bool(enabled), 'policy': policy if enabled else 'unchanged',
             'original_mutations_sha256': source_hash,
             'modification': 'rigid post-initialization core translation only' if enabled else 'none',
             'extra_rng_draws': 0,
             'public_source': 'Lightning v21, Apache-2.0; see vendor/lightning_ftmc/NOTICE'}
    if not enabled:
        return original, audit

    @functools.wraps(original)
    def anchored(p, w, h, d, rng, B, mode, archive):
        seeds, targets, recipes = original(p, w, h, d, rng, B, mode, archive)
        if not seeds:
            return seeds, targets, recipes
        box, original_anchor = incumbent_anchor(p, w, h)
        output, metadata = [], []
        walls = np.array([[0., 0.], [1., 0.], [0., 1.], [1., 1.]])
        for index, (q, recipe) in enumerate(zip(seeds, recipes)):
            anchor = original_anchor
            if policy == 'mixed_walls' and index % 8 >= 4:
                anchor = walls[index % 8-4]
            moved, shift = reanchor(q, box, anchor)
            output.append(moved)
            metadata.append({**recipe, 'anchor_policy': policy,
                             'anchor_fraction': anchor.tolist(),
                             'anchor_translation': shift.tolist()})
        if len(output) != len(seeds):
            raise ValueError('Public mutation recipe count differs from its seeds')
        return output, targets, metadata

    return anchored, audit


def install_anchor_mutations(worker, enabled=False, policy='incumbent'):
    function, audit = make_mutations(worker, enabled, policy)
    worker.mutations = function
    return audit
