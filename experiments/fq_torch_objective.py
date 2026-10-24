"""Minimal batched transcription of FQ's lifted separating-line objective.

Adapted from Evan Daniel's MIT-licensed square-packing, commit
659ee62e4a9d39542a1146e8b011cc3ab6407ede, vendor/fq/src/fq.rs::Prob.
This module is an objective/coverage prototype, not a packing validator or
optimizer. All 3N pose coordinates, side, and 2P free line variables remain.
"""
import math
import numpy as np
from scipy.spatial import cKDTree
import torch


def rounded_offsets(poses, radius):
    """Four inner corners; Minkowski disk radius is applied in constraints."""
    if not 0 <= radius <= .5:
        raise ValueError('Corner radius must be in [0,.5]')
    signs = poses.new_tensor([[1, 1], [-1, 1], [-1, -1], [1, -1]])
    c, s = poses[..., 2].cos()[..., None], poses[..., 2].sin()[..., None]
    x = (.5 - radius) * (c * signs[:, 0] - s * signs[:, 1])
    y = (.5 - radius) * (s * signs[:, 0] + c * signs[:, 1])
    return torch.stack((x, y), dim=-1)


def constraints(poses, sides, lines, pairs, radius=0., rect=(0., 0.), fix_side=False):
    """Return [B,N,4,4] wall and [B,P,8] pair inequalities, g<=0.

    poses [B,N,3], sides [B], lines [B,P,2]=(phi,d). This minimal version
    shares one pair list across a batch; future diverse lists require padding
    and masks or grouping. No center/angle/line variables are eliminated.
    """
    offset = rounded_offsets(poses, radius)
    corners = poses[..., :2, None].transpose(-1, -2) + offset
    width = (sides.detach() if fix_side else sides) + rect[0]
    height = (sides.detach() if fix_side else sides) + rect[1]
    x, y = corners[..., 0], corners[..., 1]
    walls = torch.stack((-x + radius, x - width[:, None, None] + radius,
                         -y + radius, y - height[:, None, None] + radius), dim=-1)
    i, j = pairs[:, 0], pairs[:, 1]
    half_delta = (poses[:, i, :2] - poses[:, j, :2]) * .5
    normal = torch.stack((lines[..., 0].cos(), lines[..., 0].sin()), dim=-1)
    first = ((half_delta[:, :, None, :] + offset[:, i]) * normal[:, :, None, :]).sum(-1)
    second = ((-half_delta[:, :, None, :] + offset[:, j]) * normal[:, :, None, :]).sum(-1)
    pair = torch.cat((first - lines[..., 1, None] + radius,
                      lines[..., 1, None] - second + radius), dim=-1)
    return walls, pair


def objective(poses, sides, lines, pairs, wall_lambda, pair_lambda, mu,
              radius=0., rect=(0., 0.), fix_side=False):
    walls, pair = constraints(poses, sides, lines, pairs, radius, rect, fix_side)
    def term(g, lam):
        return .5 * mu * torch.relu(g + lam / mu).square() - lam.square() / (2 * mu)
    # Keep a zero dependency so fixed-side autograd returns exactly zero.
    value = sides * 0 if fix_side else sides
    return value + term(walls, wall_lambda).flatten(1).sum(1) + term(pair, pair_lambda).flatten(1).sum(1)


def multiplier_update(walls, pair, wall_lambda, pair_lambda, mu):
    return torch.clamp_min(wall_lambda + mu * walls, 0), torch.clamp_min(pair_lambda + mu * pair, 0)


def near_pairs(poses, skin=.3):
    """Conservative list valid for every rotation and radius in [0,.5].

    The largest circumradius is sqrt(.5), attained at radius zero. A pair
    omitted at center distance >sqrt(2)+skin cannot overlap while each
    center moves at most skin/2 from this exact list-build state. Check this
    BEFORE every objective/line-search trial, not only at an outer iteration.
    """
    if skin <= 0:
        raise ValueError('Positive skin required')
    cutoff = np.nextafter(math.sqrt(2) + skin, math.inf)
    return np.asarray(sorted(cKDTree(np.asarray(poses)[:, :2]).query_pairs(cutoff)), dtype=np.int64).reshape(-1, 2)


def guard_pair_list(reference, trial, skin=.3):
    """Reject a stale list before evaluating a trial; rotation/radius are free."""
    displacement = np.linalg.norm(np.asarray(trial)[..., :2] - np.asarray(reference)[..., :2], axis=-1)
    maximum = float(displacement.max(initial=0.))
    # A small guard covers binary64 norms at the threshold. FP32 code must
    # likewise compare an outward bound or use a conservative safety margin.
    if 2 * maximum >= skin - 1e-12:
        raise ValueError('Verlet list expired; rebuild before this trial evaluation')
    return maximum


def initial_lines(poses, pairs, radius=0.):
    """FQ init_sep face/center candidates, preserving independent phi and d."""
    p = np.asarray(poses, dtype=np.float64)
    signs = np.array([[1, 1], [-1, 1], [-1, -1], [1, -1]])
    result = []
    for i, j in pairs:
        delta = p[j, :2] - p[i, :2]
        candidates = [p[i, 2], p[i, 2] + math.pi / 2, p[j, 2], p[j, 2] + math.pi / 2,
                      math.atan2(delta[1], delta[0])]
        best = None
        for angle in candidates:
            for phi in (angle, angle + math.pi):
                u = np.array([math.cos(phi), math.sin(phi)])
                if delta @ u < 0:
                    continue
                values = []
                for index, half in ((i, -.5 * delta), (j, .5 * delta)):
                    c, s = math.cos(p[index, 2]), math.sin(p[index, 2])
                    corners = (.5 - radius) * signs @ np.array([[c, s], [-s, c]])
                    values.append((corners + half) @ u)
                hi, lo = values[0].max(), values[1].min()
                candidate = (lo - hi, phi, .5 * (lo + hi))
                if best is None or candidate[0] > best[0]:
                    best = candidate
        result.append(best[1:])
    return np.asarray(result).reshape(-1, 2)
