"""Local junction aspect deformation with frozen surroundings and rigid release.

Strong global aspect continuation erased tilted bands in its real controls.
This separate method preserves the certified surroundings while melting a
small neighborhood, then releases every square for an ordinary rigid quench.
Both intermediate and final retained poses pass the unchanged official gate.
"""
import hashlib
import json
from pathlib import Path
import time

import numpy as np

import fq_soft_aggressive_campaign as aggressive
from fq_active_pilot import bloat, digest
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha

campaign = aggressive.campaign
campaign.KICK_OPTIONS = {
    'local_soft_030': aggressive.options('.3', '12', '1.001')+['--kick', '.06'],
    'local_soft_030_relaxed': aggressive.options('.3', '12', '1.005')+['--kick', '.06'],
    'local_soft_060': aggressive.options('.6', '16', '1.001')+['--kick', '.1'],
    'local_soft_060_relaxed': aggressive.options('.6', '16', '1.005')+['--kick', '.1'],
}
campaign.MODE_SLOTS = ['local_soft_030', 'local_soft_060_relaxed',
                       'local_soft_030_relaxed', 'local_soft_060']
RELEASE_OPTIONS = ['--loosen', '1', '--outer', '45', '--pit', '100', '--flip-top', '16']
_soft_trial = aggressive.soft.traced_trial
_rigid_trial = aggressive.soft._ordinary_trial


def neighborhood(pose, seed, amplitude):
    angles = (pose[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4
    plus = np.flatnonzero(angles > np.radians(5))
    minus = np.flatnonzero(angles < -np.radians(5))
    tilted = np.flatnonzero(abs(angles) > np.radians(.5))
    random = np.random.default_rng(seed)
    if len(plus) >= 10 and len(minus) >= 10 and seed % 3 != 2:
        distances = ((pose[plus, None, :2]-pose[None, minus, :2])**2).sum(axis=2)
        i, j = np.unravel_index(np.argmin(distances), distances.shape)
        center = .5*(pose[plus[i], :2]+pose[minus[j], :2])
        center_kind = 'opposite_tilt_band_junction'
    elif len(tilted):
        index = int(random.choice(tilted))
        center = pose[index, :2].copy()
        center_kind = 'seeded_tilted_square'
    else:
        center = pose[:, :2].mean(axis=0)
        center_kind = 'pose_centroid'
    count = min(len(pose), 24 if amplitude < .5 else 40)
    free = np.argsort(((pose[:, :2]-center)**2).sum(axis=1), kind='stable')[:count]
    mask = np.ones(len(pose), dtype=bool); mask[free] = False
    frozen = np.flatnonzero(mask)
    return frozen, {'center': center.tolist(), 'center_kind': center_kind,
                    'free_indices': free.tolist(), 'frozen_indices': frozen.tolist()}


def local_trial(job, options):
    key, pose, mode, binary, directory, seed, cap, deadline = job
    started = time.monotonic()
    # One composite attempt shares the original20-second ceiling. The native
    # soft stage receives12seconds; rigid release receives the remainder.
    local_deadline = min(deadline, started+cap)
    amplitude = float(options[options.index('--soft-a0')+1])
    frozen, selection = neighborhood(pose, seed, amplitude)
    actual_options = list(options)
    if len(frozen):
        actual_options += ['--freeze', ','.join(str(int(x)) for x in frozen)]
    first_job = (key, pose, mode, binary, directory, seed, min(12., cap), local_deadline)
    first, intermediate = _soft_trial(first_job, actual_options)
    first['local_selection'] = selection
    first['configured_options'] = list(options)
    if intermediate is None:
        return first, None
    _, q = intermediate
    # Keep every strict intermediate even if the release later fails.
    intermediate_sha = geometry_sha(q)
    intermediate_path = Path(directory)/f'{key}-{mode}-{seed}-strict-intermediate.npz'
    atomic_npz(intermediate_path, {key+'__local_'+intermediate_sha: q})
    provenance = {'geometry_sha256': intermediate_sha, 'archive_path': str(intermediate_path),
        'archive_sha256': digest(intermediate_path), 'certificate': first['certificate'],
        'rigid_return_trace': first['rigid_return_trace'], 'command_options': actual_options,
        'local_selection': selection, 'source_geometry_sha256': geometry_sha(pose),
        'key': key, 'mode': mode, 'seed': seed}
    atomic_json(intermediate_path.with_suffix('.json'), provenance)
    remaining = local_deadline-time.monotonic()
    if remaining <= 1:
        return {**first, 'strict_intermediate': provenance, 'release_status': 'deadline-skipped',
                'seconds': time.monotonic()-started}, intermediate
    release_mode = mode+'_rigid_release'
    second_job = (key, q, release_mode, binary, directory, seed, remaining, local_deadline)
    second, finished = _rigid_trial(second_job, RELEASE_OPTIONS)
    if finished is None:
        return {**first, 'strict_intermediate': provenance,
                'release_status': second['status'], 'release_record': second,
                'seconds': time.monotonic()-started}, intermediate
    w, h, _ = map(int, key.split('_'))
    result = {**second, 'mode': mode, 'before': bloat(pose, w, h),
        'gain': bloat(pose, w, h)-second['after'],
        'strict_improvement': bloat(pose, w, h)-second['after'] > 5e-9,
        'seconds': time.monotonic()-started,
        'command_options': actual_options, 'configured_options': list(options),
        'release_command_options': list(RELEASE_OPTIONS), 'release_status': second['status'],
        'strict_intermediate': provenance, 'local_selection': selection,
        'rigid_return_trace': first['rigid_return_trace'],
        'soft_stage': first.get('fq'), 'rigid_release_certificate_valid': second['certificate']['valid']}
    return result, finished


campaign.configured_trial = local_trial

_ordinary_campaign = campaign.campaign


def campaign_with_all_strict_variants(args):
    _ordinary_campaign(args)
    # This collection remains inside the existing outer supervised process.
    # The runtime reserves twelve seconds for final output and shutdown.
    pointer = json.loads((args.out/'final.json').read_text())
    final = Path(pointer['snapshot'])
    report = json.loads((final/'analysis.json').read_text())
    if digest(final/'donors.npz') != report['donors_sha256']:
        raise ValueError('Primary donor archive changed before strict-variant collection')
    records = json.loads((final/'results.json').read_text())
    primary_records = {record['archive_key']: record for record in records if record['status'] == 'certified'}
    poses, provenance = {}, {}
    with np.load(final/'donors.npz', allow_pickle=False) as archive:
        for name in archive.files:
            q = archive[name]
            identity = name.split('__')[0]+'__strict_'+geometry_sha(q)
            poses[identity] = q.copy()
            provenance.setdefault(identity, []).append({'origin': 'primary', 'record': primary_records[name]})
    for path in sorted((args.out/'trials').glob('*-strict-intermediate.json')):
        proof = json.loads(path.read_text())
        archive_path = Path(proof['archive_path'])
        if (not proof['certificate']['valid'] or not proof['rigid_return_trace']['valid']
                or digest(archive_path) != proof['archive_sha256']):
            raise ValueError('Strict intermediate proof mismatch')
        with np.load(archive_path, allow_pickle=False) as archive:
            if len(archive.files) != 1:
                raise ValueError('Strict intermediate must contain exactly one pose')
            q = archive[archive.files[0]]
        if geometry_sha(q) != proof['geometry_sha256']:
            raise ValueError('Strict intermediate geometry mismatch')
        identity = proof['key']+'__strict_'+proof['geometry_sha256']
        poses[identity] = q.copy()
        provenance.setdefault(identity, []).append({'origin': 'strict_intermediate', 'proof': proof,
                                'proof_path': str(path), 'proof_sha256': digest(path)})
    target = args.out/'all-strict'; target.mkdir()
    atomic_npz(target/'donors.npz', poses)
    atomic_json(target/'provenance.json', provenance)
    atomic_json(target/'analysis.json', {'primary_snapshot': str(final),
        'primary_analysis_sha256': digest(final/'analysis.json'),
        'strict_variants': len(poses), 'donors_sha256': digest(target/'donors.npz'),
        'provenance_sha256': digest(target/'provenance.json'),
        'note': 'Includes every strict local intermediate and every primary rigid result. All geometry identities use full SHA256; each entry carries its official certificate and exact source/option provenance.'})
    for path in target.iterdir():
        path.chmod(0o444)


campaign.campaign = campaign_with_all_strict_variants

if __name__ == '__main__':
    campaign.main()
