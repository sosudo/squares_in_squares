"""Local FTMC launcher with observation and optional incumbent-angle proposals."""
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
    parser.add_argument('--angle-aware', action='store_true')
    args = parser.parse_args()
    import gpu_ftmc_refill as upstream
    from ftmc_adaptive_angles import install_angle_adaptive
    from ftmc_funnel_metrics import install_metrics
    from ftmc_overflow_capture import install_capture
    from ftmc_sampling_cap import install_sampling_cap
    audit = install_angle_adaptive(upstream, enabled=args.angle_aware, local_fraction=.75)
    Path(f'angle_policy_device{args.device}.json').write_text(json.dumps(audit, indent=2)+'\n')
    metrics = install_metrics(upstream, f'research/overflow_capture_metrics_device{args.device}.json')
    capture = install_capture(upstream, f'artifacts/overflow_device{args.device}',
        json.loads(Path('baseline_sides.json').read_text()))
    original_json = upstream.atom_json

    def checkpoint_json(path, value):
        if str(path).endswith(f'worker{args.device}_status.json'):
            capture.maybe_flush()
            metrics.flush()
        return original_json(path, value)

    def terminated(signum, frame):
        raise SystemExit('Bounded overflow capture terminated; checkpoints retained')
    signal.signal(signal.SIGTERM, terminated)
    upstream.atom_json = checkpoint_json
    controls = json.loads(Path('full_control_keys.json').read_text())
    sampling_audit = install_sampling_cap(upstream, controls, cap=.1)
    Path(f'sampling_policy_device{args.device}.json').write_text(json.dumps(sampling_audit, indent=2)+'\n')
    capture.flush()
    try:
        upstream.worker(args.device, args.seconds, args.replicas, args.seed)
    finally:
        capture.restore()
        metrics.restore()
        upstream.atom_json = original_json


if __name__ == '__main__':
    main()
