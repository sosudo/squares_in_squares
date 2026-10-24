"""Two independently configured CPU lanes continuing the new8x20 minimum."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import fq_remote_cpu_search as remote
import fq_productive_campaign as productive
import fq_large_region_campaign as large

RELEASE = ['--loosen', '1', '--outer', '45', '--pit', '100', '--flip-top', '16']


def configure_lane(config):
    """Set the actual trial hook before the one audited scheduler copy."""
    policy = config['policy']
    campaign = productive.campaign
    if policy == 'productive40_060':
        options = productive.local.aggressive.options('.6', '16', '1.001')+['--kick', '.1']
        campaign.MODE_SLOTS = ['productive_circle_060', 'productive_contact_060']
        campaign.configured_trial = productive.productive_trial
    elif policy == 'connected64_030':
        options = productive.local.aggressive.options('.3', '12', '1.001')+['--kick', '.06']
        campaign.MODE_SLOTS = ['large_064_soft_030']
        campaign.configured_trial = large.large_trial
    else:
        raise ValueError('Only the two actually controlled treatments are allowed')
    campaign.KICK_OPTIONS = {mode:list(options) for mode in campaign.MODE_SLOTS}
    campaign.FOCUS = config['weights']
    productive.local.RELEASE_OPTIONS = list(RELEASE)
    remote.fq.trial = remote.strict_trial
    generated = productive.install()
    if remote.fq.hashlib.sha256(generated.encode()).hexdigest() != config['generated_runtime_sha256']:
        raise ValueError('Audited immutable scheduler source changed')
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--lane', choices=['productive', 'large'], required=True)
    parser.add_argument('--seconds', type=float, default=1200)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--max-trials', type=int, default=0)
    parser.add_argument('--collect-only', action='store_true')
    args = parser.parse_args()
    if args.collect_only:
        print(json.dumps(remote.collect(args.out)), flush=True)
        return
    if not 15 < args.seconds <= 1200 or not 1 <= args.workers <= 2 or args.max_trials < 0:
        raise ValueError('Per-lane CPU bounds exceeded')
    config = json.loads((args.package/'lanes'/f'{args.lane}.json').read_text())
    if config['lane'] != args.lane or config['workers'] != 2:
        raise ValueError('Exact frozen lane allocation required')
    if remote.fq.digest(args.binary) != config['binary_sha256']:
        raise ValueError('Exact readiness binary required')
    for name, expected in config['input_hashes'].items():
        path = args.package/name
        if not path.resolve().is_relative_to(args.package.resolve()) or remote.fq.digest(path) != expected:
            raise ValueError('Frozen input file changed')
    configure_lane(config)
    args.reference = [args.package/'inputs/reference.npz']
    args.donors = [args.package/'inputs/donors.npz']
    args.priorities = args.package/'inputs/priorities.json'
    args.trial_seconds = 20.
    args.seed = config['seed']
    productive.campaign.campaign(args)
    print(json.dumps(dict(stage='lane_certified_collection',lane=args.lane,**remote.collect(args.out))),flush=True)


if __name__ == '__main__':
    main()
