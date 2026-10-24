"""Explicit angle-library adaptation of the public Lightning v21 FTMC worker.

The vendored Apache-2.0 source remains unchanged. An AST copy replaces exactly
one assignment: the fixed list of rational-slope angles inside ``mutations``.
All mutation mechanics and admission checks remain those of the public worker.
Disabled mode returns the original function without wrapping or RNG draws.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import math

import numpy as np


PUBLIC_ANGLES = np.radians([26.565051, 28.072487, 33.690068, 36.869898,
                           40., 45., -26.565051, -33.690068])


def folded(a):
    return (np.asarray(a) + np.pi / 4) % (np.pi / 2) - np.pi / 4


def adaptive_angles(p, local_fraction=.75):
    """Incumbent angle peaks/near rational slopes, with broad original coverage.

    Repeated local entries express sampling weights in the unchanged upstream
    indexing policy. The function is deterministic and consumes no random draws.
    """
    if not 0 <= local_fraction < 1:
        raise ValueError('local_fraction must lie in [0,1).')
    if local_fraction == 0:
        return PUBLIC_ANGLES.copy()
    a = folded(np.asarray(p)[:, 2])
    a = a[abs(a) > .018]
    if len(a) < 4:
        return PUBLIC_ANGLES.copy()
    centre = float(folded(.25 * np.angle(np.mean(np.exp(4j * a)))))
    # Half-degree bins identify distinct populated orientation families. A
    # boundary +/-45-degree family is compared using square-angle periodicity.
    ids = np.rint(np.degrees(a) * 2).astype(int)
    values, counts = np.unique(ids, return_counts=True)
    peaks = [centre]
    for i in np.argsort(-counts, kind='stable'):
        if counts[i] < max(2, .1 * len(a)):
            continue
        candidate = float(np.radians(values[i] / 2))
        if all(abs(float(folded(candidate - peak))) > np.radians(1.5) for peak in peaks):
            peaks.append(candidate)
        if len(peaks) >= 3:
            break
    rationals = np.array(sorted({round(sign * math.atan(p / q), 14)
                                for q in range(1, 9) for p in range(1, q + 1)
                                if math.gcd(p, q) == 1 for sign in (-1, 1)}))
    local = []
    for peak in peaks:
        # Keep the actual incumbent orientation and nearby rational lattices;
        # angles farther away remain covered by the original global library.
        near = np.argsort(abs(folded(rationals - peak)), kind='stable')[:3]
        local.append(peak)
        local.extend(float(rationals[j]) for j in near
                     if abs(float(folded(rationals[j] - peak))) <= np.radians(3))
    local = np.asarray(local)
    count = max(1, round(len(PUBLIC_ANGLES) * local_fraction / (1 - local_fraction)))
    return np.r_[np.resize(local, count), PUBLIC_ANGLES]


def make_mutations(worker, enabled=False, local_fraction=.75, source_text=None):
    """Return (function, audit metadata), refusing unexpected source structure."""
    original = worker.mutations
    source = inspect.getsource(original) if source_text is None else source_text
    digest = hashlib.sha256(source.encode()).hexdigest()
    audit = {'enabled': bool(enabled), 'original_mutations_sha256': digest,
             'local_fraction': local_fraction if enabled else 0.,
             'modification': 'angle-library assignment only' if enabled else 'none',
             'public_source': 'lightningv08 public v21; Apache-2.0; see vendor/lightning_ftmc/NOTICE'}
    if not enabled:
        return original, audit
    tree = ast.parse(source)
    matches = [node for node in ast.walk(tree)
               if isinstance(node, ast.Assign)
               and len(node.targets) == 1
               and isinstance(node.targets[0], ast.Name)
               and node.targets[0].id == 'angles']
    if len(matches) != 1:
        raise ValueError('Expected exactly one public angles assignment.')
    assignment = matches[0]
    expected = ast.parse('angles=np.radians([26.565051,28.072487,33.690068,36.869898,40.,45.,-26.565051,-33.690068])').body[0]
    if ast.dump(assignment.value, include_attributes=False) != ast.dump(expected.value, include_attributes=False):
        raise ValueError('Public angle library changed; review the adaptation before running.')
    assignment.value = ast.Call(func=ast.Name(id='_ftmc_incumbent_angle_library', ctx=ast.Load()),
                                args=[ast.Name(id='p', ctx=ast.Load())], keywords=[])
    ast.fix_missing_locations(tree)
    namespace = dict(original.__globals__)
    namespace['_ftmc_incumbent_angle_library'] = lambda p: adaptive_angles(p, local_fraction)
    compiled_source = ast.unparse(tree)
    audit['adapted_mutations_sha256'] = hashlib.sha256(compiled_source.encode()).hexdigest()
    exec(compile(tree, '<explicit-ftmc-angle-adaptation>', 'exec'), namespace)
    return namespace[original.__name__], audit


def install_angle_adaptive(worker, enabled=False, local_fraction=.75, source_text=None):
    fn, audit = make_mutations(worker, enabled, local_fraction, source_text)
    worker.mutations = fn
    return audit
