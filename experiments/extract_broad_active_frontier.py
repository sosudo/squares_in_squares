#!/usr/bin/env python3
"""Recover certified, phase-preserving crop targets from completed broad recipes.

The crop/D4/profile conventions come from the attributed Apache-2.0 Lightning
sources. Estimates are conditional on retaining both separator profiles; only
complete-puzzle recomposition and certification can establish a score gain.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from compose_gadgets import extents, legalize, normalize, read_baseline, side
from score_official import load_metric, OFFICIAL_SHA256
from validate_submission import Square, validate_puzzle


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def family(stage):
    return f"{min(stage['w'], stage['h'])}_{max(stage['w'], stage['h'])}_{stage['dm']}"


def key(stage):
    return f"{stage['w']}_{stage['h']}_{stage['dm']}"


def orient(p, transpose, sx, sy):
    q = p.copy()
    if transpose:
        q[:, :2] = q[:, [1, 0]]
        q[:, 2] = np.pi / 2 - q[:, 2]
    q[:, 0] *= sx
    q[:, 1] *= sy
    q[:, 2] *= sx * sy
    return normalize(q)


def clip(poly, axis, bound, sign):
    result = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        da, db = sign * (a[axis] - bound), sign * (b[axis] - bound)
        if da >= 0:
            result.append(a)
        if (da < 0) != (db < 0):
            result.append(a + da / (da - db) * (b - a))
    return result


def clipped_values(p, offset, degrees):
    x, y, a = p
    x, y = x - offset[0], y - offset[1]
    co, si = .5 * math.cos(a), .5 * math.sin(a)
    poly = [np.array(v) for v in ((x+co-si, y+si+co), (x-co-si, y-si+co),
                                  (x-co+si, y-si-co), (x+co+si, y+si-co))]
    for axis, bound, sign in ((0, -2e-8, 1), (0, 1.00000002, -1),
                               (1, -2e-8, 1), (1, 1.00000002, -1)):
        poly = clip(poly, axis, bound, sign)
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [c*v[0] - s*v[1] for v in poly]


def profiles(p, w, h, incoming, outgoing, bins):
    """CPU transcription of clipped support profiles, with original wall phase."""
    lo, hi = extents(p)
    br, tl = -2., 2.
    for i, row in enumerate(p):
        if hi[i, 0] > w - 2e-8 and lo[i, 1] < 1.00000002:
            values = clipped_values(row, (w, 0), outgoing)
            if values:
                br = max(br, max(values))
        if lo[i, 0] < 1.00000002 and hi[i, 1] > h - 2e-8:
            values = clipped_values(row, (0, h), incoming)
            if values:
                tl = min(tl, min(values))
    b = 0 if br < -1.5 else max(0, min(bins, math.ceil((br + 1) * bins/2 + 2e-6)))
    t = bins if tl > 1.5 else max(0, min(bins, math.floor((tl + 1) * bins/2 - 2e-6)))
    return {'incoming_degrees': incoming, 'outgoing_degrees': outgoing,
            'outgoing_br_support': br, 'incoming_tl_support': tl,
            'br_bin': b, 'tl_bin': t, 'bins': bins}


def conditional_gain(chain, selected, reduction, n):
    """Joint gain for selected occurrences, avoiding double-counted tied stages."""
    before = max(g['f'] for g in chain)
    after = max(g['f'] - (reduction if i in selected else 0.) for i, g in enumerate(chain))
    return max(0., before-after) / math.sqrt(n)


def certify_array(item):
    name, p = item
    rows = [dict(n=str(len(p)), square_id=str(i), x=f'{x:.17g}', y=f'{y:.17g}', angle=f'{a:.17g}')
            for i, (x, y, a) in enumerate(p)]
    raw_csv = pd.DataFrame(rows).to_csv(index=False)
    numeric_csv = pd.read_csv(io.StringIO(raw_csv)).to_csv(index=False)
    numeric = list(csv.DictReader(io.StringIO(numeric_csv)))
    metric = load_metric(ROOT / 'research/official_metric_v17.py')
    official = [metric._evaluate_puzzle_worker((len(p), rr)) for rr in (rows, numeric)]
    independent = [validate_puzzle(len(p), [Square(r['x'], r['y'], r['angle']) for r in rr])
                   for rr in (rows, numeric)]
    valid = all(r[3] == 'ok' for r in official) and all(r['valid'] for r in independent)
    return name, {'valid': valid, 'geometry_sha256': geometry_sha(p),
                  'raw_csv_sha256': hashlib.sha256(raw_csv.encode()).hexdigest(),
                  'ordinary_pandas_csv_sha256': hashlib.sha256(numeric_csv.encode()).hexdigest(),
                  'official_metric_sha256': OFFICIAL_SHA256,
                  'official_raw': {'reason': official[0][3], 'side': official[0][2]},
                  'official_roundtrip': {'reason': official[1][3], 'side': official[1][2]},
                  'independent_raw': independent[0], 'independent_roundtrip': independent[1]}


def default_sources():
    return {'alternative_donors.npz': ROOT / 'artifacts/alternative-public-export-results-v2/alternative_donors.npz',
            'fq_active.npz': ROOT / 'artifacts/fq-active-v1/donors.npz',
            'fq_variant_best.npz': ROOT / 'artifacts/fq-variant-v1/snapshot-00034/best_bank.npz',
            'fq_additional_active.npz': ROOT / 'artifacts/fq-additional-active-v1/best-frozen-first.npz'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True, help='Exact source baseline used by GPU recipes')
    ap.add_argument('--portfolio', type=Path, required=True, help='Latest merged raw portfolio')
    ap.add_argument('--portfolio-report', type=Path, required=True)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--input-manifest', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--source-map', type=Path)
    ap.add_argument('--previous-targets', type=Path, default=ROOT / 'artifacts/active-frontier/active_targets.json')
    ap.add_argument('--hypothetical-reduction', type=float, default=.01)
    ap.add_argument('--workers', type=int, default=2)
    args = ap.parse_args()
    if args.out.exists() or not 1 <= args.workers <= 2 or not 0 < args.hypothetical_reduction < .1:
        raise ValueError('Require a new output directory,1–2 workers and reduction in(0,.1)')
    summary = json.loads((args.results / 'dual_composition_summary.json').read_text())
    descriptor = json.loads(args.input_manifest.read_text())
    validation = json.loads(args.portfolio_report.read_text())
    if not validation['valid'] or validation['sha256'] != digest(args.portfolio):
        raise ValueError('Latest portfolio certificate/hash mismatch')
    if digest(args.baseline) != summary['baseline_sha256'] or digest(args.baseline) != descriptor['baseline']['sha256']:
        raise ValueError('Recipe/source baseline hash mismatch')
    candidate_path = args.results / 'composition_candidates.json'
    if not any(i['sha256'] == digest(candidate_path) for i in validation['inputs']):
        raise ValueError('Merged certificate does not bind the broad candidate source')
    active = {int(n) for n, source in validation['sources'].items()
              if source != 'baseline' and Path(source).name == candidate_path.name}
    base, current = read_baseline(args.baseline), read_baseline(args.portfolio)
    reports = {name: json.loads((args.results / name / 'composition_candidates.report.json').read_text())['groups']['all_certified_donors']
               for name in summary['profiles']}
    local = default_sources()
    if args.source_map:
        local.update({k: Path(v) for k, v in json.loads(args.source_map.read_text()).items()})
    descriptor_hashes = {v['sha256'] for v in descriptor['gadgets'].values()}
    expected = {}
    for report in reports.values():
        for archive in report['gadgets']:
            if archive['sha256'] not in descriptor_hashes:
                raise ValueError('Recipe archive is absent from the frozen input descriptor')
            filename = Path(archive['path']).name
            if filename in expected and expected[filename] != archive['sha256']:
                raise ValueError('Conflicting archive aliases across profile recipes')
            expected[filename] = archive['sha256']
    source_cache, used_sources = {}, {}

    def resolve(origin, report):
        match = re.fullmatch(r'(.+):T=(True|False):(-?1),(-?1)', origin)
        if not match:
            raise ValueError(f'Unknown D4 origin:{origin}')
        source, transpose, sx, sy = match.groups()
        reference = None
        if source.startswith('Public frontier:'):
            n = int(source.split(':')[-1])
            p = base[n]
            meta = {'kind': 'source_baseline', 'n': n, 'file_sha256': digest(args.baseline)}
        else:
            index = int(source.split(':')[-1])
            reference = report['details']['_donor_sources'][index]
            label = reference['label']
            if label.startswith('certified baseline n='):
                n = int(label.split('=')[-1]); p = base[n]
                meta = {'kind': 'source_baseline', 'n': n, 'file_sha256': digest(args.baseline)}
            else:
                filename, array_key = label.split(':', 1)
                cache_key = filename, array_key
                if cache_key not in source_cache:
                    path = local[filename]
                    sha = digest(path)
                    if sha != expected[filename]:
                        raise ValueError(f'Archive source hash mismatch:{filename}')
                    with np.load(path, allow_pickle=False) as archive:
                        original = archive[array_key].copy()
                    p = legalize(original)
                    if p is None:
                        raise ValueError('Source donor fails rounding-only legalization')
                    meta = {'kind': 'archive', 'file': str(path), 'file_sha256': sha,
                            'array_key': array_key, 'original_array_sha256': geometry_sha(original),
                            'composer_array_sha256': geometry_sha(p)}
                    source_cache[cache_key] = p, meta
                    used_sources[filename] = {'path': str(path), 'sha256': sha}
                p, meta = source_cache[cache_key]
            if geometry_sha(p) != reference['array_sha256']:
                raise ValueError(f'Composer source geometry hash mismatch:{reference["label"]}')
        return orient(p, transpose == 'True', int(sx), int(sy)), dict(meta,
            transpose=transpose == 'True', reflection_x=int(sx), reflection_y=int(sy),
            donor_reference=reference)

    chains, stage_metadata, phase_arrays = {}, {}, {}
    by_type, by_family = {}, {}
    for n in sorted(active):
        profile = summary['winning_profile'][str(n)]
        report = reports[profile]
        record = next(r for r in report['details']['adaptive']['records'] if r['n'] == n)
        chain = record['chain']
        maximum = max(g['f'] for g in chain)
        # Latest merged candidate may carry subsequent conservative decimal dilation.
        if abs(side(current[n]) - record['after']) > 1e-5:
            raise ValueError(f'Winning chain does not match current n={n}')
        chain_meta = {'n': n, 'profile': profile, 'current_side': side(current[n]),
                      'recipe_maximum_bloat': maximum, 'stages': []}
        for i, g in enumerate(chain):
            p, source = resolve(g['origin'], report)
            _, upper = extents(p)
            required = np.maximum.reduce((upper[:, 0]-g['w'], upper[:, 1]-g['h'], np.zeros(len(p))))
            ids = np.argsort(required, kind='stable')[:g['w']*g['h']+g['dm']]
            raw = p[ids].copy()  # Keep phase; do not normalize this exact stitched crop.
            extraction_f = float(required[ids[-1]] + 3e-8)
            if abs(math.ceil(extraction_f*1e9)*1e-9 - g['f']) > 2e-9:
                raise ValueError('Crop order statistic no longer matches fixed-point recipe')
            profile_ids = np.flatnonzero(required <= extraction_f-2e-8)
            original_profile = profiles(p[profile_ids], g['w'], g['h'], g['incoming_degrees'],
                                        g['outgoing_degrees'], report['bins'])
            if (original_profile['br_bin'], original_profile['tl_bin']) != (g['br'], g['tl']):
                raise ValueError(f'CPU/GPU separator profile mismatch:n={n},stage={i}')
            sha = geometry_sha(raw)
            variant = key(g)+'__'+sha[:20]
            phase_arrays[variant] = raw
            single = conditional_gain(chain, {i}, args.hypothetical_reduction, n)
            use = {'n': n, 'stage': i, 'profile_configuration': profile,
                   'recipe': g, 'source': source, 'oriented_source_sha256': geometry_sha(p),
                   'crop_square_ids': ids.tolist(), 'profile_square_ids': profile_ids.tolist(),
                   'raw_phase_geometry_sha256': sha, 'separator_profiles': original_profile,
                   'crop_only_profiles': profiles(raw, g['w'], g['h'], g['incoming_degrees'],
                                                 g['outgoing_degrees'], report['bins']),
                   'single_stage_conditional_gain': single,
                   'partner_bloat': max((v['f'] for j,v in enumerate(chain) if i != j), default=0.),
                   'is_maximum_bloat': maximum-g['f'] < 1e-12, 'variant': variant}
            stage_metadata.setdefault(variant, {'key': key(g), 'family': family(g), 'uses': []})['uses'].append(use)
            chain_meta['stages'].append({'key': key(g), 'family': family(g), 'variant': variant,
                                        'bloat': g['f'], 'is_maximum_bloat': use['is_maximum_bloat']})
        chains[n] = chain_meta
        for typ in {key(g) for g in chain}:
            indices = {i for i,g in enumerate(chain) if key(g) == typ}
            gain = conditional_gain(chain, indices, args.hypothetical_reduction, n)
            by_type.setdefault(typ, {})[n] = gain
        for fam in {family(g) for g in chain}:
            indices = {i for i,g in enumerate(chain) if family(g) == fam}
            gain = conditional_gain(chain, indices, args.hypothetical_reduction, n)
            by_family.setdefault(fam, {})[n] = gain
    useful_families = {fam for fam,gains in by_family.items() if sum(gains.values()) > 1e-9}
    # Include every orientation of a useful family: tied transposes need joint improvement.
    selected_types = {v['key'] for v in stage_metadata.values() if v['family'] in useful_families}
    selected = {k:v for k,v in stage_metadata.items() if v['key'] in selected_types}
    seeds, raw_phase, targets, priorities = {}, {}, {}, {}
    previous = json.loads(args.previous_targets.read_text()) if args.previous_targets.exists() else {}
    previous_families = {f'{min(map(int,k.split("_")[:2]))}_{max(map(int,k.split("_")[:2]))}_{k.split("_")[2]}' for k in previous}
    for variant, metadata in selected.items():
        raw = phase_arrays[variant]
        q = legalize(raw, clearance=2e-9)
        if q is None:
            raise ValueError('Selected crop requires more than a rounding repair')
        metadata['seed_geometry_sha256'] = geometry_sha(q)
        lo, hi = extents(raw)
        x = raw[:, :2] - raw[0, :2]; y = q[:, :2] - q[0, :2]
        alpha = float((x*y).sum()/(x*x).sum()) if (x*x).sum() else 1.
        translation = q[0, :2] - alpha*raw[0, :2]
        if not np.allclose(q[:, :2], alpha*raw[:, :2]+translation, rtol=0, atol=1e-12):
            raise ValueError('Unexpected legalization transform')
        metadata['phase_to_seed_transform'] = {'center_scale': alpha, 'translation': translation.tolist(),
            'angle_changed': False, 'original_left_bottom_margins': lo.min(0).tolist(),
            'warning': 'Optimization seed phase differs; original phase/profile witnesses retained separately.'}
        folded = (q[:, 2]+math.pi/4) % (math.pi/2) - math.pi/4
        metadata['tilted_squares'] = int((abs(folded) > .018).sum())
        metadata['gpu_160_core_supported'] = 4 <= metadata['tilted_squares'] <= 160
        metadata['fq_cpu_has_no_160_core_cap'] = True
        metadata['previous_active_type'] = metadata['key'] in previous
        metadata['previous_active_family'] = metadata['family'] in previous_families
        metadata['type_conditional_gain'] = sum(by_type[metadata['key']].values())
        metadata['family_joint_conditional_gain'] = sum(by_family[metadata['family']].values())
        seeds[variant], raw_phase[variant] = q, raw
    for typ in selected_types:
        variants = [k for k,v in selected.items() if v['key'] == typ]
        # Prefer a limiting occurrence; choosing smallest bloat can select an irrelevant geometry.
        primary = max(variants, key=lambda k:(sum(u['single_stage_conditional_gain'] for u in selected[k]['uses']),
                                              sum(u['is_maximum_bloat'] for u in selected[k]['uses'])))
        targets[typ] = {'primary_variant': primary, 'variants': variants,
                        'family': selected[primary]['family'],
                        'single_type_conditional_gain': sum(by_type[typ].values()),
                        'family_joint_conditional_gain': selected[primary]['family_joint_conditional_gain'],
                        'tilted_squares': selected[primary]['tilted_squares'],
                        'previous_active_type': typ in previous,
                        'previous_active_family': selected[primary]['previous_active_family']}
        priorities[typ] = targets[typ]['family_joint_conditional_gain']
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        certificates = dict(pool.map(certify_array, seeds.items()))
    if not all(v['valid'] for v in certificates.values()):
        raise ValueError('A selected seed failed independent/raw/numeric-roundtrip certification')
    args.out.mkdir(parents=True)
    np.savez_compressed(args.out/'active_seed_gadgets.npz', **{k:seeds[v['primary_variant']] for k,v in targets.items()})
    np.savez_compressed(args.out/'active_seed_variants.npz', **seeds)
    np.savez_compressed(args.out/'raw_phase_variants.npz', **raw_phase)
    for name, value in [('active_targets.json', targets), ('active_priorities.json', priorities),
                         ('active_seed_validation.json', certificates)]:
        (args.out/name).write_text(json.dumps(value, indent=2)+'\n')
    manifest = {'schema_version': 1, 'baseline': str(args.baseline), 'baseline_sha256': digest(args.baseline),
                'portfolio': str(args.portfolio), 'portfolio_sha256': digest(args.portfolio),
                'portfolio_report_sha256': digest(args.portfolio_report),
                'candidate_source_sha256': digest(candidate_path), 'input_manifest_sha256': digest(args.input_manifest),
                'report_sha256': {n:digest(args.results/n/'composition_candidates.report.json') for n in reports},
                'sources': used_sources, 'extractor_sha256': digest(Path(__file__)),
                'hypothetical_reduction': args.hypothetical_reduction,
                'conditional_estimate_warning': 'Not achieved gains. Requires every indicated occurrence to improve '
                    'while preserving both incoming and outgoing separator profiles, followed by whole-puzzle '
                    'recomposition and independent raw/numeric-roundtrip certification. Family estimates overlap; do not sum them.',
                'accepted_chains': chains, 'targets': targets, 'variants': selected,
                'family_joint_conditional_gain': {k:sum(v.values()) for k,v in by_family.items() if k in useful_families},
                'attribution': 'Inherited Lightning Apache-2.0 crop/D4/clipped separator conventions; source licenses and '
                    'public geometry provenance retained in the pinned broad-composition input manifest.'}
    manifest['outputs'] = {p.name:digest(p) for p in args.out.iterdir() if p.is_file()}
    (args.out/'active_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'types': len(targets), 'variants': len(seeds), 'accepted_chains': len(chains),
                      'certified': len(certificates), 'top_families': sorted(manifest['family_joint_conditional_gain'].items(), key=lambda x:-x[1])[:10]}, indent=2))


if __name__ == '__main__':
    main()
