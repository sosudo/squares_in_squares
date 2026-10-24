"""One anchor-preserving arm with a bounded optional whole-row screening fix."""
import argparse
import time

import gpu_ftmc_refill as worker
from ftmc_anchor_mutations import install_anchor_mutations
from ftmc_funnel_metrics import install_metrics
from ftmc_refill_gate import install_refill_gate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=int, default=0)
    parser.add_argument('--seconds', type=float, default=300.)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--anchor-policy', choices=['incumbent'], default='incumbent')
    parser.add_argument('--refill-policy', choices=['row_gate', 'bounded_general'], default='row_gate')
    args = parser.parse_args()
    anchor_audit = install_anchor_mutations(worker, enabled=True)
    metrics = install_metrics(worker, f'research/worker{args.device}_funnel.json')
    counters = {'calls': 0, 'returned_packing': 0, 'returned_none': 0,
                'timeouts': 0, 'other_errors': 0, 'seconds': 0.}
    original_refill = worker.refill
    original_json = worker.atom_json

    def observed_refill(*parameters, **keywords):
        counters['calls'] += 1
        started = time.monotonic()
        try:
            result = original_refill(*parameters, **keywords)
            counters['returned_packing' if result[0] is not None else 'returned_none'] += 1
            return result
        except TimeoutError:
            counters['timeouts'] += 1
            raise
        except Exception:
            counters['other_errors'] += 1
            raise
        finally:
            counters['seconds'] += time.monotonic()-started

    def observed_json(path, value):
        if str(path).endswith(f'worker{args.device}_status.json'):
            value = {**value, 'milp_refill_observer': dict(counters)}
            original_json(f'research/worker{args.device}_milp_refill.json', counters)
        original_json(path, value)

    worker.refill = observed_refill
    worker.atom_json = observed_json
    gate_audit = install_refill_gate(worker, enabled=args.refill_policy == 'bounded_general')
    original_json(f'research/worker{args.device}_gate_adapter.json',
                  {'anchor': anchor_audit, 'row_gate': gate_audit})
    try:
        worker.worker(args.device, args.seconds, args.replicas, args.seed)
    finally:
        original_json(f'research/worker{args.device}_milp_refill.json', counters)
        metrics.restore()


if __name__ == '__main__':
    main()
