#!/usr/bin/env python3
"""Recover current-portfolio crops from actual adaptive-composition recipes.

The geometric crop/order and D4 conventions follow the attributed public
gpu_adaptive_seams/gpu_fault_composition sources. This CPU tool exports seeds
and estimates targets; it never submits or claims hypothetical gains are real.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

from compose_gadgets import extents, legalize, normalize, read_baseline, read_donors, side


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def orient(p, transpose, sx, sy):
    q = p.copy()
    if transpose:
        q[:, :2] = q[:, [1, 0]]
        q[:, 2] = math.pi / 2 - q[:, 2]
    q[:, 0] *= sx
    q[:, 1] *= sy
    q[:, 2] *= sx * sy
    return normalize(q)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--composition-report', type=Path, required=True)
    ap.add_argument('--gadgets', type=Path, nargs='*', default=[])
    ap.add_argument('--baseline-donors', type=int, default=64)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--hypothetical-reduction', type=float, default=.01)
    args = ap.parse_args()
    if args.out.exists():
        raise ValueError('Output directory exists; preserve previous extraction')
    report = json.loads(args.composition_report.read_text())
    if digest(args.baseline) != report['baseline_sha256']:
        raise ValueError('Recipe/baseline hash mismatch')
    base = read_baseline(args.baseline)
    fresh = read_donors(args.gadgets)
    donors = fresh + [(p, f'baseline n={n}') for n, p in base.items()
                      if n >= 5 and side(p) < math.ceil(math.sqrt(n)) - 1e-7][:args.baseline_donors]
    records = report['details']['adaptive']['records']
    seeds, variants, metadata, chains = {}, {}, {}, []
    for record in records:
        n, chain = record['n'], record['chain']
        target = side(base[n]) - math.isqrt(n)
        chain_out = {'n': n, 'target_bloat': target, 'recorded_bloat': max(g['f'] for g in chain),
                     'stages': []}
        for i, g in enumerate(chain):
            m = re.fullmatch(r'(.+):T=(True|False):(-?1),(-?1)', g['origin'])
            if not m:
                raise ValueError(f'Unrecognized D4 provenance: {g["origin"]}')
            origin, trans, sx, sy = m.groups()
            if origin.startswith('Public frontier:'):
                source_n = int(origin.split(':')[-1])
                p, provenance = base[source_n], f'current portfolio n={source_n}'
            elif origin.startswith('FTMC donor (provenance in night files):'):
                p, provenance = donors[int(origin.split(':')[-1])]
            else:
                raise ValueError(f'Unknown donor: {origin}')
            p = orient(p, trans == 'True', int(sx), int(sy))
            w, h, d = g['w'], g['h'], g['dm']
            _, hi = extents(p)
            required = np.maximum(np.maximum(hi[:, 0] - w, hi[:, 1] - h), 0)
            ids = np.argsort(required, kind='stable')[:w * h + d]
            q = legalize(p[ids])
            if q is None:
                raise ValueError(f'Non-rounding crop overlap: {g}')
            lo, hi = extents(q)
            f = float(np.max(hi.max(0) - lo.min(0) - [w, h]))
            if f > g['f'] + 1e-6:
                raise ValueError(f'Crop no longer matches recipe: {f} vs {g["f"]}')
            key = f'{w}_{h}_{d}'
            signature = hashlib.sha256(q.tobytes()).hexdigest()[:16]
            variant_key = key + '__' + signature
            variants[variant_key] = q
            if key not in seeds or f < metadata[key]['seed_bloat']:
                seeds[key] = q
                metadata.setdefault(key, {})['seed_bloat'] = f
            other = max((r['f'] for j, r in enumerate(chain) if j != i), default=0.)
            projected = max(g['f'] - args.hypothetical_reduction, other)
            potential = max(0., target - projected) / math.sqrt(n)
            entry = metadata[key]
            entry.setdefault('variants', {})[variant_key] = {
                'bloat': f, 'origin': g['origin'], 'source': provenance,
                'crop_square_ids': ids.tolist(), 'raw_array_sha256': hashlib.sha256(q.tobytes()).hexdigest()}
            entry.setdefault('uses', []).append({
                'n': n, 'stage': i, 'target_bloat': target, 'partner_bloat': other,
                'recipe_bloat': g['f'], 'single_stage_hypothetical_gain': potential,
                'incoming_degrees': g['incoming_degrees'], 'outgoing_degrees': g['outgoing_degrees'],
                'br': g['br'], 'tl': g['tl'], 'mode': g['mode'], 'variant': variant_key})
            chain_out['stages'].append({'key': key, 'variant': variant_key, 'recipe_bloat': g['f'],
                                        'partner_bloat': other, 'single_stage_hypothetical_gain': potential})
        chains.append(chain_out)
    priorities = {}
    for key, value in metadata.items():
        unique = {}
        for use in value['uses']:
            unique[use['n']] = max(unique.get(use['n'], 0.), use['single_stage_hypothetical_gain'])
        value['hypothetical_gain'] = sum(unique.values())
        value['target_cases'] = sorted(unique)
        p = seeds[key]
        a = (p[:, 2] + math.pi / 4) % (math.pi / 2) - math.pi / 4
        value['tilted_squares'] = int((np.abs(a) > .018).sum())
        value['worker_core_size_supported'] = 4 <= value['tilted_squares'] <= 160
        priorities[key] = value['hypothetical_gain']
    args.out.mkdir(parents=True)
    np.savez_compressed(args.out / 'active_seed_gadgets.npz', **seeds)
    np.savez_compressed(args.out / 'active_seed_variants.npz', **variants)
    (args.out / 'active_priorities.json').write_text(json.dumps(priorities, indent=2) + '\n')
    targets = {key: {'seed_bloat': value['seed_bloat'],
                     'affected_ns': value['target_cases'], 'uses': value['uses'],
                     'hypothetical_gain': value['hypothetical_gain'],
                     'tilted_squares': value['tilted_squares'],
                     'worker_core_size_supported': value['worker_core_size_supported']}
               for key, value in metadata.items()}
    (args.out / 'active_targets.json').write_text(json.dumps(targets, indent=2) + '\n')
    manifest = {
        'baseline': str(args.baseline), 'baseline_sha256': digest(args.baseline),
        'composition_report': str(args.composition_report), 'composition_report_sha256': digest(args.composition_report),
        'hypothetical_reduction': args.hypothetical_reduction,
        'warning': 'Priorities assume original separator compatibility and fixed partner bloat. '
                   'Every optimized crop must be recomposed and the complete puzzle recertified.',
        'attribution': 'Current portfolio sources in baseline certificate; crop/D4 convention from '
                       'Vladislav Lavrentev public adaptive seams and Chris Deotte multi-gadget faults.',
        'seed_types': len(seeds), 'variants': len(variants), 'chains': chains,
        'gadgets': dict(sorted(metadata.items(), key=lambda kv: -kv[1]['hypothetical_gain'])),
    }
    manifest['outputs'] = {p.name: digest(p) for p in args.out.iterdir() if p.is_file()}
    (args.out / 'active_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'seed_types': len(seeds), 'variants': len(variants), 'chains': len(chains),
                      'top': [(k, v['hypothetical_gain'], v['tilted_squares'])
                              for k, v in list(manifest['gadgets'].items())[:12]]}, indent=2))


if __name__ == '__main__':
    main()
