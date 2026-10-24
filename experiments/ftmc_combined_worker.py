"""Bounded productive FTMC worker with immutable post-certificate retention."""
import argparse
import json
from pathlib import Path
import signal
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', type=int, default=0)
    parser.add_argument('--seconds', type=float, default=1800)
    parser.add_argument('--replicas', type=int, default=64)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    import gpu_ftmc_refill as upstream
    from ftmc_adaptive_angles import install_angle_adaptive
    from ftmc_anchor_mutations import install_anchor_mutations
    from ftmc_funnel_metrics import install_metrics
    from ftmc_refill_budget import GeneralRefillBudget
    from ftmc_certified_archive import CertifiedArchive
    from ftmc_exploratory_archive import ExploratoryArchive
    from ftmc_combined_policy import install_combined_policy

    upstream.cp.cuda.Device(args.device).use()
    original_rows = upstream.refill_batch
    original_refill = upstream.refill
    original_json = upstream.atom_json
    original_npz = upstream.atom_npz
    angle_audit = install_angle_adaptive(upstream, enabled=True, local_fraction=.75)
    anchor_audit = install_anchor_mutations(upstream, enabled=True, policy='incumbent')
    metrics = install_metrics(upstream, f'research/combined_funnel_device{args.device}.json')
    refill_policy = GeneralRefillBudget(upstream, original_rows, max_fraction=.18,
        attempt_seconds=.5, startup_credit_seconds=0., deficit_margin=2,
        output_path=f'research/combined_refill_budget_device{args.device}.json')
    upstream.refill = refill_policy.wrap_refill(original_refill)
    keeper = CertifiedArchive(f'artifacts/certified_device{args.device}',
        certify=upstream.certify, fingerprint=upstream.fingerprint, flush_seconds=30)
    exploratory = ExploratoryArchive(upstream, refill_policy,
        f'artifacts/exploratory_device{args.device}').install()
    state = {'bank': None, 'wins': None, 'path': None, 'last_npz': -float('inf'),
             'last_json': -float('inf'), 'status_path': None, 'status': None}

    def checkpoint(bank, wins, path):
        state.update(bank=bank, wins=wins, path=path)
        keeper.flush(bank=bank)
        if time.monotonic()-state['last_npz'] >= 30:
            original_npz(path, wins)
            state['last_npz'] = time.monotonic()

    def checkpoint_json(path, value):
        if str(path).endswith(f'worker{args.device}_status.json'):
            state.update(status_path=path, status=value)
            if time.monotonic()-state['last_json'] < 15:
                return
            state['last_json'] = time.monotonic()
            metrics.flush()
            refill_policy.flush()
            exploratory.flush()
        return original_json(path, value)

    def terminated(signum, frame):
        raise SystemExit('Bounded combined worker stopped; immutable certificates retained')

    signal.signal(signal.SIGTERM, terminated)
    upstream.atom_json = checkpoint_json
    policy_audit = install_combined_policy(upstream, keeper, refill_policy, checkpoint)
    Path(f'policy_device{args.device}.json').write_text(json.dumps(
        {'angles': angle_audit, 'anchors': anchor_audit, 'worker': policy_audit}, indent=2)+'\n')
    try:
        upstream.worker(args.device, args.seconds, args.replicas, args.seed)
    finally:
        keeper.finalflush(bank=state['bank'])
        if state['path'] is not None:
            original_npz(state['path'], state['wins'])
        if state['status_path'] is not None:
            original_json(state['status_path'], state['status'])
        refill_policy.flush()
        exploratory.restore()
        metrics.restore()
        upstream.refill = original_refill
        upstream.atom_json = original_json


if __name__ == '__main__':
    main()
