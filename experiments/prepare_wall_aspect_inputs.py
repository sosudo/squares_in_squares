"""Construct cold335 rigid-square starts for a future rectangular-wall homotopy.

This file never optimizes, launches a job, certifies a square packing, or changes
the incumbent. Positive rectangular clearances are numerical input controls.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np
from packer_hop_physical_energy import physical_energy
from analyze_jam_row_evacuation import jam_lines

ROOT = Path(__file__).resolve().parents[1]
SIDE = 18.807
WIDTH = 19.2
AREA = SIDE*SIDE
HEIGHT = AREA/WIDTH
PATTERNS = {
    'diagonal': [(2+2*k, 2+2*k) for k in range(7)],
    'right_edge_segment': [(18, 5+k) for k in range(7)],
    'alternating_central_seam': [(9+k%2, 2+2*k) for k in range(7)],
    'horizontal_channel': [(6+k, 9) for k in range(7)],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def rectangular_control(p, width, height):
    # Pair energy is independent of the containing box; use the established
    # dense unit-square oracle and compute the four rectangular walls directly.
    pair = physical_energy(p, max(width, height))
    a = p[:, 2]
    extent = .5*(abs(np.cos(a))+abs(np.sin(a)))
    gaps = np.c_[p[:, 0]-extent, p[:, 1]-extent,
                 width-p[:, 0]-extent, height-p[:, 1]-extent]
    wall_energy = float((np.maximum(-gaps, 0.)**2).sum())
    i, j = np.triu_indices(len(p), 1)
    d = p[j, :2]-p[i, :2]
    radius = .5*(1+abs(np.cos(a[i]-a[j]))+abs(np.sin(a[i]-a[j])))
    projection = np.maximum.reduce([abs(d[:, 0]*np.cos(t)+d[:, 1]*np.sin(t))
                                   for t in (a[i], a[i]+np.pi/2, a[j], a[j]+np.pi/2)])
    return dict(pair_energy=pair['pair_energy'], wall_energy=wall_energy,
                energy=pair['pair_energy']+wall_energy,
                minimum_pair_gap=float((projection-radius).min()),
                minimum_wall_gap=float(gaps.min()), count=len(p),
                status='Numerical rectangular input check; not a square-packing certificate')


def prepare(out):
    started = time.monotonic()
    out.mkdir(parents=True, exist_ok=False)
    maximum_angle = math.radians(.15)
    extent_bound = .5*(math.cos(maximum_angle)+math.sin(maximum_angle))
    border = extent_bound+.005
    xs = np.linspace(border, WIDTH-border, 19)
    ys = np.linspace(border, HEIGHT-border, 18)
    grid = np.array([[x, y, 0.] for y in ys for x in xs])
    cell_ids = np.array([[i, j] for j in range(18) for i in range(19)])
    inputs, originals, records = {}, {}, {}
    for index, (name, holes) in enumerate(PATTERNS.items()):
        assert len(set(holes)) == 7
        removed = np.array([i+19*j for i, j in holes])
        keep = np.ones(342, dtype=bool)
        keep[removed] = False
        original = grid[keep].copy()
        p = original.copy()
        rng = np.random.default_rng(33562001+index)
        p[:, :2] += rng.uniform(-.001, .001, size=(335, 2))
        p[:, 2] = rng.uniform(-maximum_angle, maximum_angle, size=335)
        assert p.shape == (335, 3) and np.isfinite(p).all()
        control = rectangular_control(p, WIDTH, HEIGHT)
        assert control['energy'] == 0. and control['minimum_pair_gap'] > .005
        assert control['minimum_wall_gap'] > .003
        inputs[name] = p
        originals[name] = original
        _, target_detector = jam_lines(p, SIDE)
        records[name] = dict(holes=[list(x) for x in holes], removed_flat_grid_ids=removed.tolist(),
            retained_grid_cell_ids=cell_ids[keep].tolist(), seed=33562001+index,
            geometry_sha256=geometry_sha(p), original_geometry_sha256=geometry_sha(original),
            count=335, rectangular_control=control,
            same_geometry_target_square_energy=physical_energy(p, SIDE),
            target_square_jam_detector=target_detector,
            note='The square-target detector describes a deliberately incompatible initializer, not a feasible square packing.')
    np.savez_compressed(out/'cold335-inputs.npz', **inputs)
    np.savez_compressed(out/'unperturbed335-grids.npz', **originals)
    schedule = []
    for step in range(33):
        width = WIDTH+(SIDE-WIDTH)*step/32
        height = AREA/width
        schedule.append(dict(step=step, width=width, height=height, area=width*height,
            recenter_delta=[0., 0.] if step == 0 else
            [(width-schedule[-1]['width'])/2, (height-schedule[-1]['height'])/2]))
    assert schedule[-1]['width'] == SIDE and abs(schedule[-1]['height']-SIDE) < 1e-14
    pointer = json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text())
    manifest = dict(kind='Prepared cold rigid-square rectangular-wall continuation inputs; no search',
        starting_width=WIDTH, starting_height=HEIGHT, target_square_side=SIDE, constant_area=AREA,
        source_grid_shape=[19, 18], source_grid_count=342, removed_count=7, final_count=335,
        initial_center_jitter_bound=.001, initial_angle_jitter_bound_degrees=.15,
        lattice_spacing=[float(xs[1]-xs[0]), float(ys[1]-ys[0])],
        inputs_sha256=sha(out/'cold335-inputs.npz'), originals_sha256=sha(out/'unperturbed335-grids.npz'),
        records=records, proposed_schedule=schedule, canonical_reference=pointer['raw'],
        current_pointer_sha256=sha(ROOT/'artifacts/current-best-portfolio.json'),
        source_sha256=sha(__file__), helper_hashes={str(path.relative_to(ROOT)):sha(path) for path in
            [ROOT/'experiments/packer_hop_physical_energy.py', ROOT/'experiments/analyze_jam_row_evacuation.py',
             ROOT/'vendor/fq/src/fq.rs', ROOT/'vendor/lightning_ftmc/gpu_rect_optimizer.py']},
        native_limitation='CLI rect offsets hold W-H, but quench/polish optimize s; final repair can enlarge walls. No standalone fixed-box raw-return CLI is exposed.',
        supported_interface='Corrected gpu_rect_optimizer.quench(q, boxes[B,2], steps=400, tau=0), symmetric ties and --fmad=false unchanged.',
        coordinate_transition='Translate all centers by half the wall-dimension change to align box centers. Do not rescale centers, change unit sides, or reset square angles.',
        proposed_controls=['Initial rectangle full-count energy zero with independent all-pair/four-wall oracle.',
            'Actual asymmetric-box kernel energy/gradient control.',
            'Full335 corner pair and wall negative controls at each endpoint.',
            'Recompute physical energy with current W/H at each step; never compare energies across different boxes for acceptance.',
            'Preserve every raw stage and its actual W/H; only final equal-wall geometry may enter square admission.'],
        optimizer_calls=0, remote_jobs=0, fresh_geometry_certificates=0, elapsed_seconds=time.monotonic()-started,
        status='Prepared inputs only. No score or feasibility improvement claimed.')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (out/'executed-source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(input_sha256=manifest['inputs_sha256'], manifest_sha256=sha(out/'manifest.json'),
        starting_box=[WIDTH, HEIGHT], seconds=manifest['elapsed_seconds'],
        target_jam_lines={name:record['target_square_jam_detector']['line_count'] for name, record in records.items()})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    prepare(parser.parse_args().out.resolve())
