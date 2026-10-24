"""One bounded FTMC arm with an optional rigid core-anchor initializer."""
import argparse
import json
from pathlib import Path

import gpu_ftmc_refill as worker
from ftmc_anchor_mutations import install_anchor_mutations
from ftmc_funnel_metrics import install_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=int, default=0)
    parser.add_argument('--seconds', type=float, default=300.)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--anchor-policy', choices=['unchanged', 'incumbent'], default='unchanged')
    args = parser.parse_args()
    audit = install_anchor_mutations(worker, enabled=args.anchor_policy != 'unchanged')
    Path('research').mkdir(exist_ok=True)
    worker.atom_json(f'research/worker{args.device}_anchor_adapter.json', audit)
    metrics = install_metrics(worker, f'research/worker{args.device}_funnel.json')
    try:
        worker.worker(args.device, args.seconds, args.replicas, args.seed)
    finally:
        metrics.restore()


if __name__ == '__main__':
    main()
