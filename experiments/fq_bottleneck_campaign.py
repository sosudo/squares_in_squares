"""Targeted strong-aspect search with circular and contact-connected regions.

All source geometries remain intact. Only the choice of unfrozen squares
changes between the region policies; soft continuation, exact rigid return,
official certification and the supervised runtime come from the proven local
campaign. Contact regions use the unit-square separating-axis gap, not a
coarse fingerprint or a claim that a larger core capacity is feasible.
"""
import heapq

import numpy as np

import fq_local_soft_campaign as local

campaign = local.campaign
campaign.FOCUS = {
    '7_21_15': 6, '21_7_15': 6,
    '8_20_12': 5, '20_8_12': 5,
    '6_22_16': 3, '22_6_16': 3,
    '10_23_14': 3, '23_10_14': 3,
    '9_22_16': 3, '22_9_16': 3,
}
_base_options = dict(campaign.KICK_OPTIONS)
campaign.KICK_OPTIONS = dict(_base_options)
campaign.KICK_OPTIONS.update({name.replace('local_', 'contact_'): value
                             for name, value in _base_options.items()})
campaign.MODE_SLOTS = [
    'local_soft_030', 'contact_soft_030',
    'local_soft_060_relaxed', 'contact_soft_060_relaxed',
    'local_soft_030_relaxed', 'contact_soft_030_relaxed',
    'local_soft_060', 'contact_soft_060',
]
_circular_neighborhood = local.neighborhood


def contact_geometry(pose):
    """Return symmetric exact-axis separation and center distances."""
    angles = pose[:, 2]
    axes = np.stack((np.stack((np.cos(angles), np.sin(angles)), axis=1),
                     np.stack((-np.sin(angles), np.cos(angles)), axis=1)), axis=1)
    delta = pose[None, :, :2]-pose[:, None, :2]
    own_projection = np.abs(np.einsum('ijd,ikd->ijk', delta, axes))
    other_support = .5*np.abs(np.einsum('ikd,jld->ijkl', axes, axes)).sum(axis=3)
    gap_on_own_axes = (own_projection-.5-other_support).max(axis=2)
    gap = np.maximum(gap_on_own_axes, gap_on_own_axes.T)
    return gap, np.linalg.norm(delta, axis=2)


def contact_neighborhood(pose, seed, amplitude):
    """Grow a connected region from a seeded tilted-band contact."""
    gap, distance = contact_geometry(pose)
    contact = (gap <= .035) & (distance <= 1.6)
    np.fill_diagonal(contact, False)
    angle = (pose[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4
    plus = angle > np.radians(5)
    minus = angle < -np.radians(5)
    candidates = np.argwhere(contact & plus[:, None] & minus[None, :])
    rng = np.random.default_rng(seed)
    if len(candidates):
        i, j = map(int, candidates[int(rng.integers(len(candidates)))])
        seeds = [i, j]
        center_kind = 'seeded_opposite_tilt_contact'
    else:
        tilted = np.flatnonzero(abs(angle) > np.radians(.5))
        seeds = [int(rng.choice(tilted if len(tilted) else len(pose)))]
        center_kind = 'seeded_tilted_contact_component'
    center = pose[seeds, :2].mean(axis=0)
    count = min(len(pose), 24 if amplitude < .5 else 40)
    queue = [(0., index) for index in seeds]
    heapq.heapify(queue)
    best = {index: 0. for index in seeds}
    free = []
    selected = set()
    while queue and len(free) < count:
        cost, index = heapq.heappop(queue)
        if index in selected or cost != best[index]:
            continue
        selected.add(index); free.append(index)
        for neighbor in np.flatnonzero(contact[index]):
            neighbor = int(neighbor)
            if neighbor in selected:
                continue
            next_cost = cost+1.+.1*distance[index, neighbor]
            if next_cost < best.get(neighbor, float('inf')):
                best[neighbor] = next_cost
                heapq.heappush(queue, (next_cost, neighbor))
    connected_count = len(free)
    if len(free) < count:
        for index in np.argsort(((pose[:, :2]-center)**2).sum(axis=1), kind='stable'):
            if int(index) not in selected:
                free.append(int(index)); selected.add(int(index))
            if len(free) == count:
                break
    frozen = np.array([i for i in range(len(pose)) if i not in selected], dtype=int)
    return frozen, {
        'center': center.tolist(), 'center_kind': center_kind,
        'seed_indices': seeds, 'free_indices': free, 'frozen_indices': frozen.tolist(),
        'region_policy': 'contact_connected', 'sat_gap_threshold': .035,
        'center_distance_threshold': 1.6, 'connected_free_count': connected_count,
        'fallback_nearest_count': count-connected_count,
        'opposite_tilt_contact_choices': len(candidates),
    }


def targeted_trial(job, options):
    contact = job[2].startswith('contact_')
    # Each worker executes one trial at a time; restore the module hook even
    # when a native or certificate failure raises an exception.
    previous = local.neighborhood
    local.neighborhood = contact_neighborhood if contact else _circular_neighborhood
    try:
        record, donor = local.local_trial(job, options)
    finally:
        local.neighborhood = previous
    record['region_policy'] = 'contact_connected' if contact else 'circular'
    return record, donor


campaign.configured_trial = targeted_trial

if __name__ == '__main__':
    campaign.main()
