"""Freeze exact donors and orientation-fair references for three target families."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

import numpy as np

import fq_active_pilot as fq
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha, load_poses


FAMILIES = {(5, 17, 7), (7, 19, 13), (7, 20, 14)}


def family(key):
    w, h, d = map(int, key.split('__')[0].split('_'))
    return (*sorted((w, h)), d)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, action='append', required=True)
    parser.add_argument('--priorities', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    source_directory = args.out/'sources'; source_directory.mkdir()
    source_manifest, donors, records, best_family = {}, {}, {}, {}
    for index, original in enumerate(args.source):
        source = source_directory/f'{index:02d}.npz'
        shutil.copyfile(original, source); source.chmod(0o444)
        source_manifest[str(index)] = {'original': str(original), 'snapshot': str(source), 'sha256': fq.digest(source)}
        for name, pose in load_poses(source).items():
            key = name.split('__')[0]; group = family(key)
            if group not in FAMILIES: continue
            w, h, _ = map(int, key.split('_'))
            excess = fq.bloat(pose, w, h); sha = geometry_sha(pose)
            identity = key+'__focus_'+sha
            donors[identity] = pose
            record = {'key': key, 'source_archive': str(index), 'source_name': name,
                      'geometry_sha256': sha, 'excess': excess, 'transformation': 'identity'}
            records.setdefault(identity, record)
            if group not in best_family or excess < best_family[group]['excess']:
                best_family[group] = {'pose': pose, 'excess': excess, 'record': record}
    if set(best_family) != FAMILIES:
        raise ValueError('A target family has no supplied geometry')
    reference, reference_records = {}, {}
    for (small, large, d), winner in sorted(best_family.items()):
        source_w, source_h, _ = map(int, winner['record']['key'].split('_'))
        for w, h in [(small, large), (large, small)]:
            key = f'{w}_{h}_{d}'; pose = winner['pose'].copy()
            transformation = 'identity'
            if (w, h) != (source_w, source_h):
                pose[:, :2] = pose[:, [1, 0]]
                pose[:, 2] = -pose[:, 2]
                transformation = 'reflect_xy_axes; angle=-angle (quarter-turn square symmetry)'
            certificate = fq.certify(pose)
            if not certificate['valid']:
                raise ValueError(f'Family reference fails official checks: {key}')
            reference[key] = pose
            sha = geometry_sha(pose)
            reference_records[key] = {'geometry_sha256': sha, 'excess': fq.bloat(pose, w, h),
                'family': f'{small}_{large}_{d}', 'parent_geometry_sha256': winner['record']['geometry_sha256'],
                'parent_source': winner['record'], 'transformation': transformation, 'certificate': certificate}
            identity = key+'__focus_'+sha
            donors[identity] = pose.copy()
            records.setdefault(identity, reference_records[key])
    priorities = json.loads(args.priorities.read_text())
    selected_priorities = {key: max(priorities.get(f'{w}_{h}_{d}', 0.), priorities.get(f'{h}_{w}_{d}', 0.))
                           for key in reference for w, h, d in [tuple(map(int, key.split('_')))]}
    atomic_npz(args.out/'reference.npz', reference)
    atomic_npz(args.out/'donors.npz', donors)
    atomic_json(args.out/'priorities.json', selected_priorities)
    atomic_json(args.out/'provenance.json', records)
    manifest = {'source_manifest': source_manifest, 'families': [list(x) for x in sorted(FAMILIES)],
        'reference_sha256': fq.digest(args.out/'reference.npz'), 'donors_sha256': fq.digest(args.out/'donors.npz'),
        'priorities_sha256': fq.digest(args.out/'priorities.json'), 'provenance_sha256': fq.digest(args.out/'provenance.json'),
        'reference_records': reference_records, 'retained_exact_donors': len(donors),
        'donors_by_orientation': dict(Counter(k.split('__')[0] for k in donors)),
        'note': 'Each orientation starts from the best known geometry in its canonical family, with any transpose explicitly recorded and officially recertified. This prevents counting a known transposed family result as a new gain. Exact original oriented/reflected donor poses are retained independently. Shared family priorities are selection weights, not additive score predictions.'}
    atomic_json(args.out/'manifest.json', manifest)
    for path in args.out.iterdir():
        if path.is_file(): path.chmod(0o444)
    print(json.dumps({'reference_sha256': manifest['reference_sha256'],
        'retained_exact_donors': len(donors), 'types': list(reference),
        'excess': {key: value['excess'] for key, value in reference_records.items()}}), flush=True)


if __name__ == '__main__':
    main()
