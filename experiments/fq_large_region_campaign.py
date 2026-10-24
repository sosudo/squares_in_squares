"""Prepared larger connected-region continuation with distant walls fixed.

This is a separate follow-up configuration, not an update to the running
bottleneck search. A reviewed frozen two-orientation 7x21+15 input bank and
separate launch authorization are required before running the campaign.
"""
import heapq

import numpy as np

import fq_bottleneck_campaign as target

local = target.local
campaign = target.campaign
campaign.FOCUS = {'7_21_15': 1, '21_7_15': 1}
campaign.KICK_OPTIONS = {
    f'large_{count:03d}_soft_{label}': local.aggressive.options(amplitude, steps, hold)+['--kick', kick]
    for count in [64, 96]
    for label, amplitude, steps, hold, kick in [('030', '.3', '12', '1.001', '.06')]
}
# Four real .6 controls failed the quality band. Their executed configuration
# is frozen under the smoke artifact; production uses the two validated modes.
campaign.MODE_SLOTS = ['large_064_soft_030', 'large_096_soft_030']
local.RELEASE_OPTIONS = ['--no-alm', '--loosen', '1', '--pit', '20', '--flip-top', '0']


def large_neighborhood(pose, seed, amplitude, count):
    _, initial = target.contact_neighborhood(pose, seed, amplitude)
    center = np.asarray(initial['center'])
    seeds = initial['seed_indices']
    gap, distance = target.contact_geometry(pose)
    half = .5*(abs(np.cos(pose[:, 2]))+abs(np.sin(pose[:, 2])))
    lower, upper = pose[:, :2]-half[:, None], pose[:, :2]+half[:, None]
    wall_clearance = np.minimum(lower-lower.min(axis=0), upper.max(axis=0)-upper).min(axis=1)
    center_distance = np.linalg.norm(pose[:, :2]-center, axis=1)
    distant_wall = (wall_clearance <= .05) & (center_distance > 6.)
    allowed = ~distant_wall
    contact = (gap <= .035) & (distance <= 1.6) & allowed[:, None] & allowed[None, :]
    np.fill_diagonal(contact, False)
    desired = min(count, int(allowed.sum()))
    queue = [(0., i) for i in seeds if allowed[i]]
    heapq.heapify(queue)
    best = {index: cost for cost, index in queue}
    free, selected = [], set()
    while queue and len(free) < desired:
        cost, index = heapq.heappop(queue)
        if index in selected or cost != best[index]:
            continue
        free.append(index); selected.add(index)
        for neighbor in np.flatnonzero(contact[index]):
            neighbor = int(neighbor)
            next_cost = cost+1.+.1*distance[index, neighbor]
            if neighbor not in selected and next_cost < best.get(neighbor, float('inf')):
                best[neighbor] = next_cost
                heapq.heappush(queue, (next_cost, neighbor))
    connected_count = len(free)
    if connected_count < desired:
        for index in np.argsort(center_distance, kind='stable'):
            if allowed[index] and int(index) not in selected:
                free.append(int(index)); selected.add(int(index))
            if len(free) == desired:
                break
    frozen = np.array([i for i in range(len(pose)) if i not in selected], dtype=int)
    return frozen, {
        **initial, 'region_policy': 'large_contact_connected_with_distant_walls_fixed',
        'free_indices': free, 'frozen_indices': frozen.tolist(),
        'requested_free_count': count, 'actual_free_count': len(free),
        'connected_free_count': connected_count, 'fallback_nearest_count': desired-connected_count,
        'preserved_distant_wall_indices': np.flatnonzero(distant_wall).tolist(),
        'wall_clearance_threshold': .05, 'distant_wall_radius': 6.,
    }


def large_trial(job, options):
    count = int(job[2].split('_')[1])
    previous = local.neighborhood
    local.neighborhood = lambda pose, seed, amplitude: large_neighborhood(pose, seed, amplitude, count)
    try:
        record, donor = local.local_trial(job, options)
    finally:
        local.neighborhood = previous
    record['region_policy'] = 'large_contact_connected_with_distant_walls_fixed'
    return record, donor


campaign.configured_trial = large_trial

if __name__ == '__main__':
    campaign.main()
