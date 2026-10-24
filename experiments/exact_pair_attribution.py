#!/usr/bin/env python3
"""Controlled n599 donor substitution with the successful join held fixed."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
from compose_gadgets import extents
from extract_broad_active_frontier import orient, geometry_sha
from exact_pair_composition import build_pair
from cpu_recipe_replay import public_functions
from fq_capacity_probe import full_certificate

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pair-run', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    started = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.pair_run/'manifest.json').read_text())
    original = json.loads((args.pair_run/'candidates.json').read_text())['599']
    recipe = original['provenance']['pair']
    assert recipe['mode'] == 1 and (recipe['first']['w'], recipe['first']['h'], recipe['first']['d']) == (7, 20, 14)
    by_sha = {entry['sha256']:entry for entry in manifest['inputs']}
    for entry in by_sha.values():
        assert digest(entry['snapshot']) == entry['sha256']
    second = recipe['second']
    source = second['sources'][0]
    with np.load(by_sha[source['archive_sha256']]['snapshot']) as archive:
        p = archive[source['array_key']]
    b = dict(second, pose=orient(p, second['transpose'], second['reflection_x'], second['reflection_y']))
    controls = {}
    for bank in manifest['inputs']:
        if bank['is_new']:
            continue
        with np.load(bank['snapshot']) as archive:
            for key in archive.files:
                w, h, d = map(int, key.split('__')[0].split('_'))
                if d != 14 or (w, h) not in ((7, 20), (20, 7)):
                    continue
                q = orient(archive[key], w > h, 1, 1)
                _, hi = extents(q)
                excess = float(max(hi.max(0)-[7, 20]))
                orientation = f'{w}_{h}'
                if orientation not in controls or excess < controls[orientation]['actual_excess']:
                    controls[orientation] = dict(pose=q, actual_excess=excess, w=7, h=20, d=14,
                        f=math.ceil((excess+3e-8)*1e9)*1e-9,
                        source=dict(archive_sha256=bank['sha256'], archive_key=key,
                                    geometry_sha256=geometry_sha(archive[key])))
    assert set(controls) == {'7_20', '20_7'}
    stitch, _ = public_functions(ROOT/'vendor/lightning_ftmc')
    results = []
    for orientation, a in controls.items():
        q = build_pair(a, b, 1, 24, stitch)
        assert q is not None and len(q) == 599
        certificate = full_certificate(q)
        entry = dict(original_source_orientation=orientation,
            substitute={k:v for k,v in a.items() if k != 'pose'},
            fixed_second={k:v for k,v in b.items() if k != 'pose'},
            count=len(q), geometry_sha256=geometry_sha(q), certificate=certificate)
        if certificate['valid']:
            entry['side'] = certificate['independent_raw']['side_upper']
            entry['side_minus_original'] = float(entry['side'])-float(original['side'])
            entry['ties_original_within_1e_10'] = abs(entry['side_minus_original']) <= 1e-10
        results.append(entry)
    result = dict(elapsed_seconds=time.monotonic()-started, original_side=original['side'],
        pair_candidates_sha256=digest(args.pair_run/'candidates.json'),
        pair_manifest_sha256=digest(args.pair_run/'manifest.json'), source_sha256=digest(__file__),
        recipe_unchanged=dict(n=599, k=24, mode=1, second_source=source), results=results,
        profile_essential_claim_supported=False if any(r.get('ties_original_within_1e_10') for r in results) else None,
        no_submission=True)
    (args.out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:v for k,v in result.items() if k != 'results'}))
    for r in results:
        print(json.dumps({k:v for k,v in r.items() if k in ('original_source_orientation','side','side_minus_original','ties_original_within_1e_10')}))


if __name__ == '__main__':
    main()
