"""Bounded repair of exploratory overflow cores; no capacity claim is a proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import signal
import time

import numpy as np

from ftmc_overflow_capture import OverflowCapture


def minimum_fractional_side(w, h, count):
    """Area lower bound for count unit squares in (w+f) by (h+f)."""
    return max(0., (math.sqrt((w-h)**2+4*count)-w-h)/2)


def select_records(records, max_cores=16):
    ranked = sorted(records.values(), key=OverflowCapture.quality, reverse=True)
    families = {}
    for record in ranked:
        if record['core_residual'] > .01:
            continue
        if minimum_fractional_side(record['w'], record['h'], record['requested_count']+1) > record['loose_fractional_side']+1e-7:
            continue
        families.setdefault(record['source_key'], []).append(record)
    selected = []
    for layer in range(max((len(v) for v in families.values()), default=0)):
        for values in families.values():
            if layer < len(values):
                selected.append(values[layer])
                if len(selected) >= max_cores:
                    return selected
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', type=int, default=0)
    parser.add_argument('--seconds', type=float, default=300)
    parser.add_argument('--max-cores', type=int, default=16)
    parser.add_argument('--copies', type=int, default=8)
    parser.add_argument('--seed', type=int, default=91003)
    args = parser.parse_args()
    import cupy as cp
    import gpu_ftmc_refill as upstream
    from ftmc_funnel_metrics import install_metrics
    cp.cuda.Device(args.device).use()
    started = time.monotonic()
    deadline = started+args.seconds
    rng = np.random.default_rng(args.seed)
    prefix = Path(f'artifacts/overflow_device{args.device}')
    report = json.loads(prefix.with_suffix('.json').read_text())
    archive_data = prefix.with_suffix('.npz').read_bytes()
    if hashlib.sha256(archive_data).hexdigest() != report['archive_sha256']:
        raise ValueError('Exploratory core archive/report hash mismatch')
    with np.load(prefix.with_suffix('.npz')) as data:
        cores = {key: data[key] for key in data.files}
    baseline_sides = json.loads(Path('baseline_sides.json').read_text())
    selected = select_records(report['records'], args.max_cores)
    metrics = install_metrics(upstream, f'research/overflow_repair_metrics_device{args.device}.json')
    accepted, metadata, direct = {}, {}, {}
    stats = {'stage': 'running', 'status': 'no_accepted_results_yet', 'device': args.device,
        'selected_cores': len(selected), 'cores_attempted': 0, 'area_impossible_targets': 0,
        'refill_calls': 0, 'refill_ready_families': 0, 'full_quench_replicas': 0,
        'fp64_replicas': 0, 'lp_candidates': 0, 'official_rejected': 0,
        'certified_variants': 0, 'direct_improved_puzzles': 0,
        'archive_sha256': report['archive_sha256'], 'seconds_budget': args.seconds,
        'note': 'Only accepted variants passed complete official raw and pandas-roundtrip checks. Source overflow capacities remain exploratory.'}

    def checkpoint():
        stats.update(elapsed_seconds=time.monotonic()-started, certified_variants=len(accepted),
                     direct_improved_puzzles=len(direct))
        upstream.atom_npz(f'artifacts/overflow_repaired_device{args.device}.npz', accepted)
        upstream.atom_json(f'overflow_repair_device{args.device}.json', metadata)
        upstream.atom_json(f'overflow_direct_device{args.device}.json', direct)
        upstream.atom_json(f'overflow_repair_summary_device{args.device}.json', stats)
        metrics.flush()

    def terminated(signum, frame):
        raise SystemExit('Bounded overflow repair terminated; checkpoints retained')
    signal.signal(signal.SIGTERM, terminated)
    checkpoint()
    try:
        for record in selected:
            if time.monotonic() >= deadline:
                break
            core = cores[record['id']]
            if (not np.isfinite(core).all() or core.shape != (record['core_count'], 3)
                    or hashlib.sha256(core.astype('<f8').tobytes()).hexdigest() != record['core_sha256']):
                raise ValueError('Exploratory core geometry does not match its manifest')
            stats['cores_attempted'] += 1
            w, h = record['w'], record['h']
            loose = record['loose_fractional_side']
            for extra in (1, 2):
                if time.monotonic() >= deadline:
                    break
                count = record['requested_count']+extra
                if record['reported_capacity'] < count:
                    continue
                area_min = minimum_fractional_side(w, h, count)
                if count > 1000 or area_min > loose+1e-7:
                    stats['area_impossible_targets'] += 1
                    continue
                packed, capacities = upstream.refill_batch(cp.asarray(core[None]), w, h, loose,
                    count, soft=record['soft_overlap_tolerance'])
                capacities = cp.asnumpy(capacities)
                packed = cp.asnumpy(packed).astype(float)
                stats['refill_calls'] += 1
                good = [family for family in record['overflow_families'] if capacities[family] >= count]
                stats['refill_ready_families'] += len(good)
                if not good:
                    checkpoint()
                    continue
                batch = np.repeat(packed[good], args.copies, axis=0)
                fractional = []
                for i in range(len(batch)):
                    fractional.append(max(area_min+1e-7, loose-[0., .002, .01, .025][i % 4]))
                    if i % args.copies:
                        tilted = np.abs((batch[i, :, 2]+np.pi/4) % (np.pi/2)-np.pi/4) > .018
                        batch[i, tilted, :2] += rng.normal(0., .0003, (int(tilted.sum()), 2))
                        batch[i, tilted, 2] += rng.normal(0., .0004, int(tilted.sum()))
                fractional = np.asarray(fractional)
                q32, out = upstream.explore(batch, np.column_stack((w+fractional, h+fractional)), steps=1800)
                out = cp.asnumpy(out)
                q32 = cp.asnumpy(q32)
                stats['full_quench_replicas'] += len(batch)
                finite = np.isfinite(out).all(axis=1) & np.isfinite(q32).all(axis=(1, 2))
                chosen = np.flatnonzero(finite)
                chosen = chosen[np.argsort(out[chosen, 1])[:8]]
                if not len(chosen):
                    checkpoint()
                    continue
                q64, out64 = upstream.precise(q32[chosen],
                    np.column_stack((w+fractional[chosen]+2e-5, h+fractional[chosen]+2e-5)), steps=1100)
                q64, out64 = cp.asnumpy(q64), cp.asnumpy(out64)
                stats['fp64_replicas'] += len(chosen)
                for pose, outcome in zip(q64, out64):
                    if time.monotonic() >= deadline:
                        break
                    if not np.isfinite(pose).all() or not np.isfinite(outcome).all() or outcome[1] > 3e-5:
                        continue
                    stats['lp_candidates'] += 1
                    polished = upstream.rect_lp(pose, w, h)
                    if polished is None or not np.isfinite(polished).all():
                        continue
                    f = upstream.excess(polished, w, h)
                    gap = upstream.gaps(polished)
                    if not 0 <= f < .999999 or gap <= 1e-10:
                        continue
                    key = f'{w}_{h}_{count-w*h}'
                    identity = key+'__'+upstream.fingerprint(polished)
                    old = accepted.get(identity)
                    if old is not None and f >= upstream.excess(old, w, h)-2e-7:
                        continue
                    if not upstream.certify(polished):
                        stats['official_rejected'] += 1
                        continue
                    accepted[identity] = polished
                    metadata[identity] = {'source_core': record['id'], 'source_key': record['source_key'],
                        'source_mode': record['mode'], 'source_core_sha256': record['core_sha256'],
                        'w': w, 'h': h, 'surplus': count-w*h, 'count': count,
                        'additional_squares': extra, 'fractional_side': f, 'minimum_gap': gap,
                        'official_raw_and_roundtrip': True, 'status': 'certified_geometry',
                        'squares': polished.tolist(), 'hypothetical_targets': record['potential_targets']}
                    side = max(w, h)+f
                    previous = direct.get(str(count), {}).get('side', float(baseline_sides[str(count)]))
                    if side < previous-1e-9:
                        direct[str(count)] = {'side': side, 'squares': polished.tolist(),
                            'source': 'certified FTMC overflow repair', 'variant': identity,
                            'source_key': record['source_key'], 'additional_squares': extra}
                    print(json.dumps({'stage': 'certified_overflow', 'device': args.device,
                        'key': key, 'additional_squares': extra, 'fractional_side': f,
                        'direct_puzzle_improvement': side < float(baseline_sides[str(count)])-1e-9}), flush=True)
                checkpoint()
            checkpoint()
        stats['stage'] = 'complete'
        stats['status'] = 'certified_results' if accepted else 'no_certified_results'
    finally:
        checkpoint()
        metrics.restore()
    print(json.dumps(stats), flush=True)


if __name__ == '__main__':
    main()
