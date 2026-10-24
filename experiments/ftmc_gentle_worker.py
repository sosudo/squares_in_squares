"""Run one observed angle-aware FTMC arm with optional gentle full targets."""
import argparse
import json
from pathlib import Path
import signal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', type=int, default=0)
    parser.add_argument('--seconds', type=float, default=300)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--gentle', action='store_true')
    args = parser.parse_args()
    import gpu_ftmc_refill as upstream
    from ftmc_adaptive_angles import install_angle_adaptive
    from ftmc_funnel_metrics import install_metrics
    from ftmc_gentle_targets import install_gentle_targets
    angle_audit = install_angle_adaptive(upstream, enabled=True, local_fraction=.75)
    metrics = install_metrics(upstream, f'research/gentle_funnel_device{args.device}.json')
    original_json = upstream.atom_json

    def checkpoint_json(path, value):
        if str(path).endswith(f'worker{args.device}_status.json'):
            metrics.flush()
        return original_json(path, value)

    def terminated(signum, frame):
        raise SystemExit('Bounded gentle-target worker stopped; certified checkpoints retained')
    signal.signal(signal.SIGTERM, terminated)
    upstream.atom_json = checkpoint_json
    target_audit = install_gentle_targets(upstream, enabled=args.gentle)
    Path(f'policy_device{args.device}.json').write_text(json.dumps(
        {'angles': angle_audit, 'targets': target_audit}, indent=2)+'\n')
    try:
        upstream.worker(args.device, args.seconds, args.replicas, args.seed)
    finally:
        metrics.restore()
        upstream.atom_json = original_json


if __name__ == '__main__':
    main()
