#!/usr/bin/env python3
"""Finite chevron/checkerboard diamond-core modes, with actual SAT repair.

Prescribed cluster angles and tangential phase shifts define each start.
All centers are then LP variables; omitted source corner disjunctions receive
fresh violated-pair cuts. Only strict final geometry can become a candidate.
"""
import time
ENTRY = time.monotonic()
import argparse
import csv
import inspect
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import warnings
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree
import fq_full_local_campaign as full
from fq_dual_cage_soft import retaining_stage_source
from fq_joint_seed_check import persistent_native_run, BINARY_SHA, RIGID
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha
from compose_gadgets import normalize, side, legalize
from period5_branch_lp import data, corner_pairs

ROOT = Path(__file__).resolve().parents[1]


def lattice(p):
    core = np.flatnonzero(abs(p[:, 2]) > .1)
    outer = np.setdiff1d(np.arange(len(p)), core)
    u = np.array([1., -1.])/math.sqrt(2)
    v = np.array([1., 1.])/math.sqrt(2)
    uv = (p[core, :2]-p[core, :2].mean(0)) @ np.stack((u, v)).T
    rc = np.rint(uv+3.5).astype(int)
    if len(core) != 64 or len(outer) != 83 or np.max(abs(uv-(rc-3.5))) > 1e-8:
        raise ValueError('Expected exact 8x8 diamond lattice and83-frame layout')
    if len({tuple(row) for row in rc}) != 64:
        raise ValueError('Lattice identities are not unique')
    distance, nearest = cKDTree(p[core, :2]).query(p[outer, :2])
    keep = distance < 1.35
    return core, outer, rc, u, v, outer[keep], nearest[keep]


def mode_pose(p, model, family, degrees, shear, frame_coupling):
    core, outer, rc, u, v, neighbors, nearest = model
    r, c = rc.T
    if family == 'chevron_rows':
        groups = r//4
        signs = 1.-2.*groups
    elif family == 'chevron_cols':
        groups = c//4
        signs = 1.-2.*groups
    elif family == 'checker_quadrants':
        groups = 2*(r//4)+(c//4)
        signs = (-1.)**((r//4)+(c//4))
    elif family == 'alternating_rows':
        groups = r
        signs = (-1.)**r
    elif family == 'alternating_cols':
        groups = c
        signs = (-1.)**c
    else:
        raise ValueError(family)
    q = p.copy()
    shifts = math.radians(degrees)*signs
    rigid_residual = 0.
    for group in np.unique(groups):
        local = np.flatnonzero(groups == group)
        ids = core[local]
        center = p[ids, :2].mean(0)
        a = float(shifts[local[0]])
        rotation = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        if family == 'checker_quadrants':
            rb, cb = divmod(int(group), 2)
            translation = shear*((-1.)**rb*v+(-1.)**cb*u)/math.sqrt(2)
        else:
            tangent = u if family.endswith('cols') else v
            translation = shear*signs[local[0]]*tangent
        q[ids, :2] = (p[ids, :2]-center)@rotation.T+center+translation
        q[ids, 2] += shifts[local]
        before = np.linalg.norm(p[ids, None, :2]-p[None, ids, :2], axis=-1)
        after = np.linalg.norm(q[ids, None, :2]-q[None, ids, :2], axis=-1)
        rigid_residual = max(rigid_residual, float(abs(before-after).max()))
    q[neighbors, 2] -= frame_coupling*shifts[nearest]
    if rigid_residual > 1e-12 or q.shape != (147, 3):
        raise ValueError('Coherent cluster rigid/count control failed')
    return q, {'family':family, 'degrees':degrees, 'shear':shear,
               'frame_coupling':frame_coupling, 'coupled_frame_ids':neighbors.tolist(),
               'maximum_cluster_distance_change':rigid_residual}


def solve(p, warm, pairs, omitted, deadline):
    n = len(p)
    angles = warm[:, 2]
    ux, uy, projection, gaps, radii = data(warm, pairs)
    branch = gaps.argmax(1)
    sign = np.where(projection[np.arange(len(pairs)), branch] >= 0., 1., -1.)
    selected = np.ones(len(pairs), dtype=bool)
    for index, pair in enumerate(pairs):
        if tuple(pair) in omitted:
            selected[index] = False
    extent = .5*(abs(np.cos(angles))+abs(np.sin(angles)))
    bounds = [(float(x)-.7, float(x)+.7) for x in warm[:, :2].ravel()]
    bounds.append((math.sqrt(n), side(p)+.7))
    trace = []
    q = None
    for iteration in range(6):
        if deadline-time.monotonic() < .3:
            break
        ids = np.flatnonzero(selected)
        i, j = pairs[ids].T
        vx = sign[ids]*ux[ids, branch[ids]]
        vy = sign[ids]*uy[ids, branch[ids]]
        rows = np.repeat(np.arange(len(ids)), 4).tolist()
        cols = np.column_stack((2*i, 2*i+1, 2*j, 2*j+1)).ravel().tolist()
        values = np.column_stack((vx, vy, -vx, -vy)).ravel().tolist()
        rhs = (-radii[ids]-2e-9).tolist()
        for square in range(n):
            for dim in (0, 1):
                row = len(rhs)
                rows.append(row); cols.append(2*square+dim); values.append(-1.)
                rhs.append(-extent[square]-2e-9)
                row = len(rhs)
                rows.extend((row, row)); cols.extend((2*square+dim, 2*n)); values.extend((1., -1.))
                rhs.append(-extent[square]-2e-9)
        A = coo_matrix((values, (rows, cols)), shape=(len(rhs), 2*n+1)).tocsr()
        rhs = np.asarray(rhs)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            fit = linprog(np.r_[np.zeros(2*n), 1.], A_ub=A, b_ub=rhs, bounds=bounds,
                method='highs', options={'threads':1, 'time_limit':min(1.5, max(.05, deadline-time.monotonic())),
                    'primal_feasibility_tolerance':1e-9, 'dual_feasibility_tolerance':1e-9})
        record = {'iteration':iteration, 'status':int(fit.status), 'success':bool(fit.success),
                  'active_pair_constraints':len(ids)}
        if not fit.success:
            trace.append(record)
            break
        q = np.column_stack((fit.x[:-1].reshape(n, 2), angles))
        _, _, current_projection, current_gaps, _ = data(q, pairs)
        maximum = current_gaps.max(1)
        bad = np.flatnonzero(maximum < -2e-8)
        wall = float(min((q[:, :2]-extent[:, None]).min(),
                         (fit.x[-1]-q[:, :2]-extent[:, None]).min()))
        record.update(lp_side=float(fit.x[-1]), physical_side=side(q), minimum_pair_gap=float(maximum.min()),
                      minimum_wall_gap=wall, violating_pairs=len(bad),
                      maximum_lp_violation=float(max(0., (A@fit.x-rhs).max())))
        if not len(bad) and wall >= -2e-8:
            record['all_pair_numerical_screen_passed'] = True
            trace.append(record)
            break
        new = bad[~selected[bad]]
        if not len(new):
            trace.append(record)
            break
        # Use the disjunct selected by the coherent warm geometry, rather than
        # letting an arbitrary extreme provisional LP placement choose a new
        # corner registration. Every restored cut is still an exact unit SAT
        # branch at the prescribed angles; full all-pair checks remain final.
        selected[new] = True
        record['new_exact_sat_disjuncts'] = len(new)
        trace.append(record)
    return q, {'trace':trace, 'numerically_feasible':bool(trace and trace[-1].get('all_pair_numerical_screen_passed')),
               'source_corner_omissions':len(omitted), 'added_corner_constraints':int(selected.sum()-(len(pairs)-len(omitted)))}


def run(args):
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    for name in ('source', 'raw', 'native'):
        (out/name).mkdir()
    pointer = json.loads(args.pointer.read_text())
    raw = Path(pointer['raw']['path']); official = Path(pointer['raw']['official_report'])
    if full.fq.digest(raw) != pointer['raw']['sha256'] or full.fq.digest(official) != pointer['raw']['official_report_sha256']:
        raise ValueError('Canonical source changed')
    report = json.loads(official.read_text())
    if not report['valid'] or report['invalid_count'] or report['sha256'] != full.fq.digest(raw):
        raise ValueError('Canonical official proof mismatch')
    canonical = float(next(r['side'] for r in report['results'] if r['n'] == 147))
    with raw.open(newline='') as handle:
        rows = [r for r in csv.DictReader(handle) if r['n'] == '147']
    rows.sort(key=lambda r:int(r['square_id']))
    p = normalize(np.array([[float(r[k]) for k in ('x', 'y', 'angle')] for r in rows]))
    model = lattice(p); core = model[0]
    pairs = np.column_stack(np.triu_indices(147, 1))
    omitted = corner_pairs(p)
    slide, _ = mode_pose(p, model, 'alternating_rows', 0., .3, 0.)
    core_pairs = np.column_stack(np.triu_indices(64, 1))
    slide_gap = float(data(slide[core], core_pairs)[3].max(1).min())
    duplicate = p.copy(); duplicate[1] = duplicate[0]
    duplicate_gap = float(data(duplicate, pairs)[3].max(1).min())
    if slide_gap < -1e-9 or duplicate_gap > -.5:
        raise ValueError('Row-slide or duplicate negative geometry control failed')
    paths = [Path(__file__), ROOT/'experiments/n147_uniform_core_lp.py', ROOT/'experiments/period5_branch_lp.py',
        ROOT/'experiments/fq_full_local_campaign.py', ROOT/'experiments/fq_dual_cage_soft.py',
        ROOT/'experiments/fq_joint_seed_check.py', ROOT/'experiments/fq_capacity_probe.py',
        ROOT/'experiments/fq_coherent_clusters.py', ROOT/'experiments/fq_variant_campaign.py',
        ROOT/'experiments/compose_gadgets.py', ROOT/'experiments/fq_active_pilot.py',
        ROOT/'scripts/validate_submission.py', ROOT/'scripts/score_official.py',
        ROOT/'research/official_metric_v17.py', ROOT/'vendor/fq/src/fq.rs']
    for path in paths:
        shutil.copyfile(path, out/'source'/path.name)
    atomic_npz(out/'reference.npz', {'147':p})
    control, diagnostic = solve(p, p, pairs, set(), args.deadline)
    if control is None or not diagnostic['numerically_feasible']:
        raise ValueError('Source LP/corner-cut control failed')
    repaired = legalize(control)
    if repaired is None:
        raise ValueError('Source LP needs non-rounding repair')
    certificate = full_certificate(repaired)
    atomic_npz(out/'control-poses.npz', {'source':p, 'lp':control, 'repaired':repaired})
    atomic_json(out/'control-certificate.json', certificate)
    if not certificate['valid'] or abs(side(repaired)-canonical) > 1e-6:
        raise ValueError('Source LP full-gate control failed')
    atomic_json(out/'controls.json', {'row_slide_core_sat_minimum':slide_gap, 'duplicate_negative_sat':duplicate_gap,
        'source_corner_count':len(omitted), 'source_lp':diagnostic, 'full_certificate':certificate})
    specs = []
    families = ['chevron_rows', 'chevron_cols', 'checker_quadrants', 'alternating_rows', 'alternating_cols']
    for family in families:
        for degrees in (-.5, .5, -1.5, 1.5, -4., 4.):
            for shear in (0., .3):
                specs.append((family, degrees, shear, .15))
    for family in families[:3]:
        for degrees in (-1.5, 1.5):
            for shear in (0., .3):
                specs.append((family, degrees, shear, 0.))
    specs += [(family, 0., shear, 0.) for family in families[-2:] for shear in (-.3, .3)]
    manifest = {'raw_path':str(raw), 'raw_sha256':full.fq.digest(raw), 'official_sha256':full.fq.digest(official),
        'reference_geometry_sha256':geometry_sha(p), 'canonical147_side':canonical,
        'source_hashes':{str(path):full.fq.digest(path) for path in paths}, 'specs':specs,
        'core_count':64, 'upright_count':83, 'coupled_interface_frame_count':len(model[5]),
        'independent_lp_center_variables':294, 'trust_about_structured_warm_center':.7,
        'source_corner_disjuncts_initially_omitted':len(omitted), 'maximum_cut_rounds':6,
        'restored_cut_branch_policy':'Exact branch selected from each structured warm start, not from arbitrary provisional LP overlap.',
        'workers':1, 'maximum_total_seconds':90, 'native_finish_limit':6,
        'native_binary_sha256':BINARY_SHA, 'native_source_commit':full.fq.SOURCE_COMMIT,
        'native_source_license':'MIT; Evan Daniel',
        'scope':'Finite prescribed nonuniform angles, coherent block/shear starts and local SAT-branch LPs. '
                'Provisional LP states are not geometry claims; actual final sides and full gates decide gains.'}
    atomic_json(out/'manifest.json', manifest)
    print(json.dumps({'stage':'controls_passed', 'row_slide_gap':slide_gap, 'frame_neighbors':len(model[5]), 'specs':len(specs)}), flush=True)
    records = []; raw_states = {}; possible = []; winners = {}; best_certified = canonical
    lp_deadline = min(args.deadline-27., ENTRY+54.)
    for index, spec in enumerate(specs):
        if lp_deadline-time.monotonic() < .4:
            break
        warm, description = mode_pose(p, model, *spec)
        q, diagnostic = solve(p, warm, pairs, omitted, lp_deadline)
        record = {'index':index, **description, 'diagnostic':diagnostic, 'status':'no_lp_state'}
        if q is not None:
            label = f'lp_{index:03d}'
            raw_states[label] = q
            atomic_npz(out/'raw'/(label+'.npz'), {'warm':warm, 'lp':q})
            record.update(status='raw_unvalidated', raw_geometry_sha256=geometry_sha(q), physical_side=side(q))
            possible.append((not diagnostic['numerically_feasible'], side(q), label, spec[0]))
            if diagnostic['numerically_feasible'] and side(q) < canonical-1e-7:
                fixed = legalize(q)
                proof = full_certificate(fixed) if fixed is not None else {'valid':False}
                record['full_certificate'] = proof
                actual = float(proof['independent_raw']['side_upper']) if proof['valid'] else math.inf
                if actual < best_certified-1e-9:
                    best_certified = actual
                    identity = geometry_sha(fixed)
                    winners[str(147)] = {'side':proof['independent_raw']['side_upper'],
                        'squares':[[format(float(v), '.17g') for v in row] for row in fixed],
                        'source':'Coordinated n147 structural-angle LP', 'provenance':record}
                    atomic_npz(out/'raw'/('certified_'+identity+'.npz'), {'147':fixed})
        records.append(record)
        atomic_json(out/'lp-results.json', records)
    atomic_npz(out/'raw-lp-states.npz', raw_states)
    stage_path = out/'source/retaining_run_stage.py'; stage_path.write_text(retaining_stage_source())
    scope = dict(full.__dict__); scope['grouped_run'] = persistent_native_run
    exec(compile(stage_path.read_text(), str(stage_path), 'exec'), scope)
    stage = scope['run_stage']
    binary = out/'source/fq'; shutil.copyfile(args.binary, binary); binary.chmod(0o500)
    if full.fq.digest(binary) != BINARY_SHA:
        raise ValueError('Unreviewed native binary')
    selected = []; seen_family = set()
    for row in sorted(possible):
        if row[1] > canonical+.08:
            continue
        if row[3] not in seen_family:
            selected.append(row); seen_family.add(row[3])
    for row in sorted(possible):
        if len(selected) >= 6:
            break
        if row not in selected and row[1] <= canonical+.08:
            selected.append(row)
    native = []; certified = {}; native_proofs = {}
    for index, (_, _, label, family) in enumerate(selected[:6]):
        if args.deadline-time.monotonic() < 1.:
            break
        record, q = stage(raw_states[label], canonical, 'coordinated_'+str(index), RIGID, 1476000+index,
            binary.resolve(), (out/'native').resolve(), 4.3, args.deadline)
        record.update(parent_lp_label=label, mode_family=family)
        if q is not None:
            key='147__coordinated_'+geometry_sha(q); certified[key]=q; native_proofs[key]=record['certificate']
            record['archive_key']=key
            if record['side'] < best_certified-1e-9:
                best_certified = record['side']
                winners['147']={'side':record['certificate']['independent_raw']['side_upper'],
                    'squares':[[format(float(v), '.17g') for v in row] for row in q],
                    'source':'Coordinated n147 structural start plus native finish', 'provenance':record}
        native.append(record); atomic_json(out/'native-results.json', native)
        atomic_npz(out/'certified-native.npz', certified); atomic_json(out/'native-certificates.json', native_proofs)
    atomic_json(out/'candidates.json', winners)
    summary={'status':'complete' if len(records)==len(specs) else 'bounded_partial', 'seconds':time.monotonic()-ENTRY,
        'requested_lp_trials':len(specs), 'completed_lp_trials':len(records), 'raw_lp_states':len(raw_states),
        'numerically_feasible_lp_states':sum(r.get('diagnostic', {}).get('numerically_feasible', False) for r in records),
        'native_trials':len(native), 'fully_certified_native':len(certified), 'certified_improved_cases':len(winners),
        'best_raw_lp_side':min((side(q) for q in raw_states.values()), default=None),
        'canonical147_side':canonical, 'source_hashes_unchanged':all(full.fq.digest(path)==identity for path,identity in manifest['source_hashes'].items()),
        'best_certified_side':best_certified, 'full_score_gain':(canonical-best_certified)/math.sqrt(147),
        'manifest_sha256':full.fq.digest(out/'manifest.json'), 'lp_results_sha256':full.fq.digest(out/'lp-results.json'),
        'candidates_sha256':full.fq.digest(out/'candidates.json'), 'no_gpu':True, 'no_submission':True}
    atomic_json(out/'summary.json', summary); print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pointer', type=Path, default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--binary', type=Path, default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--child', action='store_true'); parser.add_argument('--deadline', type=float)
    args=parser.parse_args()
    if args.child:
        run(args)
    else:
        process=subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:],
            '--child', '--deadline', str(ENTRY+72.)], start_new_session=True)
        forced=False
        try:
            process.wait(timeout=max(.01, ENTRY+78.-time.monotonic()))
        except subprocess.TimeoutExpired:
            forced=True
            try:os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=.5)
        result={'seconds':time.monotonic()-ENTRY, 'returncode':process.returncode, 'workers':1,
                'maximum_seconds':80, 'outer_limit_enforced':forced}
        if args.out.exists():atomic_json(args.out/'supervisor.json', result)
        print(json.dumps(result), flush=True)
        raise SystemExit(process.returncode)
