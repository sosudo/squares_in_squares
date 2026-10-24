"""Finite arbitrary-angle contact candidates for one-defect packing junctions.

Every unit remains a unit square. The outside is fixed during the finite MIS;
only full ordinary-pandas/official/interval gates can admit a new packing.
"""
from __future__ import annotations
import time
STARTED = time.monotonic()
import argparse
from concurrent.futures import ProcessPoolExecutor, FIRST_COMPLETED, wait
from decimal import Decimal
import hashlib, json, math, multiprocessing as mp, os
from pathlib import Path
import shutil, signal, subprocess, sys
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
from scipy.spatial import ConvexHull, cKDTree
from compose_gadgets import extents, legalize, normalize, side
from fq_active_pilot import digest
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha
from prepare_junction_cavity import gaps
from joint_pose_mis import clique_cover
from joint_pose_mis_solve import graph_from_edges, greedy, independent, solve_mis
ROOT = Path(__file__).resolve().parents[1]
GRAPH_CLEARANCE = 1e-10
CONTACT_CLEARANCE = 2e-8
NODE_CAP = 1800
EDGE_CAP = 800000


class Deadline(BaseException):
    pass


def alarm(*_):
    raise Deadline()


def corners(angle):
    c, s = .5 * math.cos(angle), .5 * math.sin(angle)
    return np.array([[c-s, s+c], [-c-s, -s+c], [-c+s, -s-c], [c+s, s-c]])


def obstacle(square, angle, margin):
    points = (corners(square[2])[:, None, :] + corners(angle)[None, :, :]).reshape(-1, 2)
    points = np.unique(np.round(points, 12), axis=0)
    polygon = points[ConvexHull(points).vertices]
    edge = np.roll(polygon, -1, axis=0) - polygon
    normal = np.column_stack([edge[:, 1], -edge[:, 0]]) / np.linalg.norm(edge, axis=1)[:, None]
    bound = np.sum(normal * polygon, axis=1) + margin
    expanded = []
    for i in range(len(normal)):
        matrix = np.array([normal[i-1], normal[i]])
        expanded.append(np.linalg.solve(matrix, [bound[i-1], bound[i]]))
    return np.asarray(expanded) + square[:2]


def arrangement_points(polygons, lower, upper):
    rectangle = np.array([[lower[0], lower[1]], [upper[0], lower[1]],
                          [upper[0], upper[1]], [lower[0], upper[1]]])
    polygons = [*polygons, rectangle]
    a = np.vstack(polygons)
    b = np.vstack([np.roll(p, -1, axis=0) for p in polygons])
    delta = b - a
    i, j = np.triu_indices(len(a), 1)
    r, s = delta[i], delta[j]
    difference = a[j] - a[i]
    cross = lambda x, y: x[:, 0] * y[:, 1] - x[:, 1] * y[:, 0]
    denominator = cross(r, s)
    valid = abs(denominator) > 1e-12
    t = np.zeros(len(i)); u = np.zeros(len(i))
    t[valid] = cross(difference[valid], s[valid]) / denominator[valid]
    u[valid] = cross(difference[valid], r[valid]) / denominator[valid]
    valid &= (t >= -1e-10) & (t <= 1+1e-10) & (u >= -1e-10) & (u <= 1+1e-10)
    intersections = a[i[valid]] + t[valid, None] * r[valid]
    points = np.vstack([a, .5*(a+b), intersections])
    points = points[np.all(points >= lower-1e-10, axis=1) & np.all(points <= upper+1e-10, axis=1)]
    _, indices = np.unique(np.round(points, 9), axis=0, return_index=True)
    return points[np.sort(indices)]


def valid_against_outside(poses, outside, box, clearance=GRAPH_CLEARANCE):
    if len(poses) == 0:
        return np.zeros(0, dtype=bool)
    extent = .5 * (abs(np.cos(poses[:, 2])) + abs(np.sin(poses[:, 2])))
    keep = np.all(poses[:, :2] - extent[:, None] >= -1e-11, axis=1)
    keep &= np.all(box - poses[:, :2] - extent[:, None] >= -1e-11, axis=1)
    if not len(outside):
        return keep
    neighbors = cKDTree(poses[:, :2]).query_ball_tree(cKDTree(outside[:, :2]), 1.5)
    pairs = np.array([(i, j+len(poses)) for i, values in enumerate(neighbors) for j in values], dtype=int)
    if len(pairs):
        all_poses = np.vstack([poses, outside])
        values = gaps(all_poses, pairs)
        keep[np.unique(pairs[values < clearance, 0])] = False
    return keep


def candidate_pool(scaffold, raw, center, radius, box, cap=NODE_CAP):
    local = np.flatnonzero(abs(scaffold[:, :2]-center).max(1) <= radius)
    outer = np.flatnonzero(abs(scaffold[:, :2]-center).max(1) > radius)
    outside = scaffold[outer].copy()
    initial = scaffold[local].copy()
    if not valid_against_outside(initial, outside, box).all():
        raise ValueError('Certified local witness rejected by numerical pool guard')
    anchors = scaffold[abs(scaffold[:, :2]-center).max(1) <= radius+1.5]
    hint_centers = raw[abs(raw[:, :2]-center).max(1) <= radius, :2]
    degrees = [0., -5., 5., -15., 15., -24.295189, 24.295189, -30., 30., 45.]
    folded = (initial[:, 2]+np.pi/4) % (np.pi/2)-np.pi/4
    groups = {}
    for a in folded:
        groups.setdefault(round(math.degrees(a)), []).append(float(a))
    for _, values in sorted(groups.items(), key=lambda item: -len(item[1]))[:4]:
        angle = float(np.median(values))
        if all(abs(angle-math.radians(d)) > 1e-5 for d in degrees):
            degrees.append(math.degrees(angle))
    poses = [p.copy() for p in initial]
    origins = [{'kind': 'certified_incumbent', 'scaffold_row': int(i)} for i in local]
    exact = {np.asarray(p, dtype='<f8').tobytes() for p in poses}
    raw_local_ids = np.flatnonzero(abs(raw[:, :2]-center).max(1) <= radius)
    raw_local = raw[raw_local_ids]
    raw_hint_keep = valid_against_outside(raw_local, outside, box)
    for source_id, row in zip(raw_local_ids[raw_hint_keep], raw_local[raw_hint_keep]):
        identity = np.asarray(row, dtype='<f8').tobytes()
        if identity not in exact:
            exact.add(identity); poses.append(row.copy())
            origins.append({'kind': 'original_raw_local', 'raw_row': int(source_id)})
    coverage = []
    quota = max(1, (cap-len(poses)) // len(degrees))
    for number, degree in enumerate(degrees):
        angle = math.radians(degree)
        extent = .5*(abs(math.cos(angle))+abs(math.sin(angle)))
        lower = np.maximum(center-radius, extent+CONTACT_CLEARANCE)
        upper = np.minimum(center+radius, box-extent-CONTACT_CLEARANCE)
        if np.any(lower > upper):
            continue
        polygons = [obstacle(p, angle, CONTACT_CLEARANCE) for p in anchors]
        points = arrangement_points(polygons, lower, upper)
        points = np.vstack([points, hint_centers])
        rows = np.column_stack([points, np.full(len(points), angle)])
        keep = valid_against_outside(rows, outside, box)
        rows = rows[keep]
        # Deterministic angle-balanced spatial coverage; no coordinate rounding
        # is applied to retained poses. Cell labels only choose representatives.
        rng = np.random.default_rng(7183+number)
        order = rng.permutation(len(rows))
        occupied = set(); chosen = []
        for i in order:
            cell = tuple(np.floor((rows[i, :2]-center)/.10).astype(int))
            if cell not in occupied:
                occupied.add(cell); chosen.append(int(i))
        chosen = chosen[:quota]
        added = 0
        for i in chosen:
            row = rows[i]; identity = np.asarray(row, dtype='<f8').tobytes()
            if identity in exact:
                continue
            exact.add(identity); poses.append(row)
            origins.append({'kind': 'new_contact_candidate', 'angle_degrees': degree,
                            'arrangement_row': i, 'anchor_scope': 'fixed outside plus unforced original local units'})
            added += 1
        coverage.append({'angle_degrees': degree, 'raw_positions': len(points),
                         'outside_feasible_positions': len(rows), 'retained': added})
    poses = np.asarray(poses)
    if len(poses) > cap:
        raise ValueError('Candidate node cap exceeded')
    return poses, outside, np.arange(len(initial)), origins, {'local_scaffold_rows': local.tolist(),
        'fixed_outside_rows': outer.tolist(), 'fixed_outside_geometry_sha256': geometry_sha(outside),
        'required_local_count': len(initial)+1, 'radius': radius, 'window_center': center.tolist(),
        'window_definition': 'Candidate centers within L-infinity radius; bodies may cross window boundary but must avoid every fixed outside unit.',
        'contact_clearance': CONTACT_CLEARANCE, 'graph_clearance': GRAPH_CLEARANCE,
        'angles': degrees, 'coverage': coverage, 'nodes': len(poses),
        'raw_local_hints_total': len(raw_local), 'raw_local_hints_outside_feasible': int(raw_hint_keep.sum()),
        'scope': 'Finite angle/arrangement-vertex/edge-midpoint/source-center proposals; incomplete continuous coverage.'}


def graph_for(poses):
    pairs = cKDTree(poses[:, :2]).query_pairs(math.sqrt(2)+1e-8, output_type='ndarray')
    values = gaps(poses, pairs) if len(pairs) else np.zeros(0)
    edges = pairs[values < GRAPH_CLEARANCE]
    return edges, {'broad_pairs': len(pairs), 'edges': len(edges),
                   'scope': 'Clearance-restricted floating SAT graph; bounds apply only to this finite model, never global packing feasibility.'}


def controls():
    # New contact generation recovers a deleted diamond between four corners.
    L = 2+math.sqrt(.5)
    original = np.array([[.5, .5, 0.], [L-.5, .5, 0.], [.5, L-.5, 0.],
                         [L-.5, L-.5, 0.], [L/2, L/2, math.pi/4]])
    original[:, :2] *= 1.00001
    original = normalize(original); box = side(original)+1e-7
    fixed = original[:4]
    angle = math.pi/4; extent = math.sqrt(.5)
    lower = np.full(2, extent+CONTACT_CLEARANCE); upper = np.full(2, box-extent-CONTACT_CLEARANCE)
    points = arrangement_points([obstacle(p, angle, CONTACT_CLEARANCE) for p in fixed], lower, upper)
    poses = np.column_stack([points, np.full(len(points), angle)])
    poses = poses[valid_against_outside(poses, fixed, box)]
    if not len(poses):
        raise ValueError('Contact-generated five-square recovery control failed')
    q = np.vstack([fixed, poses[:1]])
    certificate = full_certificate(q)
    if not certificate['valid']:
        raise ValueError('Contact recovery full gate failed')
    duplicate = np.vstack([q, q[-1]])
    edges, _ = graph_for(duplicate)
    if not any(set(pair) == {4, 5} for pair in edges):
        raise ValueError('Duplicate-square graph negative failed')
    chosen, proof = solve_mis(4, np.array([[0, 1], [0, 2], [1, 2]]), [[0, 1, 2]], 4, 2.)
    if chosen is None or len(chosen) != 2:
        raise ValueError('MILP control failed')
    return {'new_contact_recovery': certificate, 'recovered_geometry_sha256': geometry_sha(q),
            'duplicate_negative': True, 'tiny_milp': proof}


def worker(job):
    inputs, output, n, radius, box_kind, deadline = job
    inputs, output = Path(inputs), Path(output)
    name = f'n{n}-r{radius:.2f}-{box_kind}'; out = output/name; out.mkdir()
    record = {'n': n, 'radius': radius, 'box_kind': box_kind, 'status': 'started'}
    signal.signal(signal.SIGALRM, alarm)
    local_deadline = min(deadline-2, time.monotonic()+85.)
    signal.setitimer(signal.ITIMER_REAL, max(.1, local_deadline-time.monotonic()))
    retained = None
    try:
        cases = json.loads((inputs/'cases.json').read_text()); case = next(r for r in cases if r['n'] == n)
        variant = next(v for v in case['variants'] if v['valid'])
        with np.load(inputs/'scaffolds.npz', allow_pickle=False) as z:
            scaffold = z[variant['archive_key']].copy()
        with np.load(inputs/'scaffolds'/f'n{n}-raw-invalid.npz', allow_pickle=False) as z:
            raw = z['pose'].copy()
        box = side(scaffold)+5e-8 if box_kind == 'nominal' else float(case['canonical_side'])-.015
        if box < side(scaffold):
            raise ValueError('Box excludes certified scaffold')
        record.update(canonical_side=case['canonical_side'], box=box,
                      scaffold_geometry_sha256=geometry_sha(scaffold))
        begin = time.monotonic()
        poses, outside, witness, provenance, coverage = candidate_pool(scaffold, raw,
            np.array(variant['collision_center']), radius, box)
        atomic_npz(out/'pool.npz', {'poses': poses, 'outside': outside, 'incumbent': witness})
        atomic_json(out/'provenance.json', provenance); record['coverage'] = coverage
        record['candidate_seconds'] = time.monotonic()-begin
        edges, statistics = graph_for(poses)
        if len(edges) > EDGE_CAP:
            record['status'] = 'edge_cap'; return record, None
        with (out/'edges.npy').open('wb') as stream:
            np.save(stream, edges)
        graph = graph_from_edges(len(poses), edges)
        if not independent(graph, witness):
            raise ValueError('Known valid local incumbent conflicts in finite graph')
        record['incumbent_count'] = len(witness); record['graph'] = statistics
        need = coverage['required_local_count']; cover = clique_cover(graph)
        atomic_json(out/'cliques.json', cover); record['finite_clique_cover_upper'] = len(cover)
        best = witness
        for seed in range(4):
            candidate = greedy(graph, seed)
            if len(candidate) > len(best):
                best = candidate
            if len(best) >= need:
                break
        record['greedy_count'] = len(best)
        if len(best) < need and len(cover) >= need and time.monotonic() < local_deadline-12:
            chosen, proof = solve_mis(len(poses), edges, cover, need,
                                     min(30., max(.1, local_deadline-time.monotonic()-12)))
            record['milp'] = proof
            if chosen is not None and len(chosen) > len(best):
                best = chosen
        if not independent(graph, best):
            raise ValueError('Solver integral incumbent conflicts')
        best = np.asarray(best[:need], dtype=int)
        q = np.vstack([outside, poses[best]])
        if geometry_sha(q[:len(outside)]) != coverage['fixed_outside_geometry_sha256']:
            raise ValueError('Fixed outside changed before certification')
        atomic_npz(out/'selected-raw.npz', {'pose': q, 'indices': best})
        record.update(selected_local_count=len(best), actual_count=len(q),
                      raw_geometry_sha256=geometry_sha(q), count_restored=len(q) == n)
        try:
            signal.setitimer(signal.ITIMER_REAL, min(8., max(.1, local_deadline-time.monotonic())))
            certificate = full_certificate(q)
        except (Deadline, Exception) as error:
            record['raw_gate_error_type'] = type(error).__name__; certificate = {'valid': False}
        finally:
            signal.setitimer(signal.ITIMER_REAL, max(.1, local_deadline-time.monotonic()))
        record['raw_certificate'] = certificate
        if not certificate['valid']:
            repaired = legalize(q, clearance=2e-9)
            if repaired is not None:
                try:
                    signal.setitimer(signal.ITIMER_REAL, min(8., max(.1, local_deadline-time.monotonic())))
                    certificate = full_certificate(repaired)
                except (Deadline, Exception) as error:
                    record['repair_gate_error_type'] = type(error).__name__; certificate = {'valid': False}
                finally:
                    signal.setitimer(signal.ITIMER_REAL, max(.1, local_deadline-time.monotonic()))
                record['clearance_outside_max_move'] = float(abs(repaired[:len(outside)]-outside).max(initial=0))
                q = repaired
        record['certificate'] = certificate
        if certificate['valid']:
            record.update(status='certified', geometry_sha256=geometry_sha(q),
                actual_side=str(max(Decimal(str(value)) for value in (certificate['independent_raw']['side_upper'], certificate['independent_roundtrip']['side_upper'], certificate['shared_official_gate']['raw_side'], certificate['shared_official_gate']['roundtrip_side'], certificate['ordinary_pandas_official_side']))))
            key = f'{len(q)}__junction_{geometry_sha(q)}'
            atomic_npz(out/'certified.npz', {key: q}); record['archive_key'] = key
            record['certified_npz_sha256'] = digest(out/'certified.npz'); retained = q
        else:
            record['status'] = 'failed_full_gates'
        return record, retained
    except Deadline:
        record['status'] = 'bounded_worker_deadline'; return record, None
    except Exception as error:
        record.update(status='error', error_type=type(error).__name__); return record, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        atomic_json(out/'result.json', record)


def campaign(args):
    out = args.out; out.mkdir(parents=True, exist_ok=False)
    (out/'source').mkdir()
    manifest = json.loads((args.inputs/'manifest.json').read_text())
    assert digest(args.inputs/'cases.json') == manifest['cases_sha256']
    assert digest(args.inputs/'scaffolds.npz') == manifest['scaffolds_sha256']
    paths = [Path(__file__), ROOT/'experiments/prepare_junction_cavity.py',
             ROOT/'experiments/joint_pose_mis.py', ROOT/'experiments/joint_pose_mis_solve.py',
             ROOT/'experiments/fq_capacity_probe.py', ROOT/'experiments/compose_gadgets.py',
             ROOT/'scripts/score_official.py', ROOT/'scripts/validate_submission.py', ROOT/'research/official_metric_v17.py']
    source_hashes = {}
    for p in paths:
        shutil.copyfile(p, out/'source'/p.name); source_hashes[str(p)] = digest(p)
    cases = sorted(r['n'] for r in json.loads((args.inputs/'cases.json').read_text()) if r['status'] == 'certified_one_defect')
    jobs = [(str(args.inputs.resolve()), str(out.resolve()), n, radius, box, args.deadline)
            for radius in (2.25, 3.25) for box in ('nominal', 'gain015') for n in cases]
    protocol = {'baseline': manifest['baseline'], 'input_manifest_sha256': digest(args.inputs/'manifest.json'),
        'source_hashes': source_hashes, 'workers': 2, 'maximum_total_seconds': 360,
        'worker_seconds': 85, 'milp_seconds': 30, 'node_cap': NODE_CAP, 'edge_cap': EDGE_CAP,
        'cases': cases, 'jobs': len(jobs), 'no_native_or_gpu': True,
        'no_canonical_or_submission_mutation': True,
        'command': [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        'started_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
    atomic_json(out/'manifest.json', protocol)
    atomic_json(out/'controls.json', controls())
    records = []; donors = {}; candidates = {}; cursor = 0; pending = {}; snapshots = 0
    def checkpoint(status):
        atomic_json(out/'results.json', records); atomic_npz(out/'donors.npz', donors)
        atomic_json(out/'candidates.json', candidates)
        summary = {'status': status, 'seconds': time.monotonic()-STARTED, 'trials': len(records),
            'jobs': len(jobs), 'certified_geometries': len(donors), 'winning_cases': list(candidates),
            'candidates_sha256': digest(out/'candidates.json'), 'donors_sha256': digest(out/'donors.npz'),
            'source_hashes_unchanged': all(digest(p) == sha for p, sha in source_hashes.items())}
        atomic_json(out/'summary.json', summary); return summary
    checkpoint('prepared')
    with ProcessPoolExecutor(max_workers=2, mp_context=mp.get_context('fork')) as pool:
        while cursor < len(jobs) or pending:
            while len(pending) < 2 and cursor < len(jobs) and time.monotonic() < args.deadline-5:
                job = jobs[cursor]; cursor += 1; pending[pool.submit(worker, job)] = job
            if not pending:
                break
            ready, _ = wait(pending, timeout=.25, return_when=FIRST_COMPLETED)
            for future in ready:
                pending.pop(future); record, pose = future.result(); records.append(record)
                if pose is not None:
                    donors[record['archive_key']] = pose
                    if record['actual_count'] == record['n'] and Decimal(record['actual_side']) < Decimal(record['canonical_side'])-Decimal('1e-8'):
                        ns = str(record['n']); old = candidates.get(ns)
                        if old is None or Decimal(record['actual_side']) < Decimal(old['side']):
                            candidates[ns] = {'side': record['actual_side'], 'squares': [[f'{v:.17g}' for v in row] for row in pose],
                                'certificate': record['certificate'], 'source': 'Finite arbitrary-angle junction cavity count restoration',
                                'provenance': {'trial': str(args.out/f"n{record['n']}-r{record['radius']:.2f}-{record['box_kind']}"),
                                               'input_manifest_sha256': protocol['input_manifest_sha256']}}
                            snapshots += 1; snap = out/f'gain-{snapshots:04d}'; snap.mkdir()
                            atomic_json(snap/'candidates.json', candidates); atomic_json(snap/'record.json', record)
                            for path in snap.iterdir(): path.chmod(0o444)
                            atomic_json(out/'latest-immutable.json', {'path': str(snap), 'candidates_sha256': digest(snap/'candidates.json')})
                summary = checkpoint('running'); print(json.dumps({'n': record['n'], 'status': record['status'], 'restored': record.get('count_restored'), 'selected': record.get('selected_local_count'), 'need': record.get('coverage', {}).get('required_local_count')}), flush=True)
            if time.monotonic() >= args.deadline:
                break
    summary = checkpoint('complete' if len(records) == len(jobs) else 'bounded_partial')
    for p in out.rglob('*'):
        if p.is_file(): p.chmod(0o444)
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--child', action='store_true'); parser.add_argument('--deadline', type=float)
    args = parser.parse_args()
    if args.child:
        return campaign(args)
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], '--child', '--deadline', str(STARTED+345.)], start_new_session=True)
    forced = False
    try:
        child.wait(timeout=max(.1, STARTED+357.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced = True
        try: os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        child.wait(timeout=1.)
    if args.out.exists(): atomic_json(args.out/'supervisor.json', {'returncode': child.returncode, 'seconds': time.monotonic()-STARTED, 'workers': 2, 'maximum_seconds': 360, 'forced': forced})
    if child.returncode and not forced: raise SystemExit(child.returncode)


if __name__ == '__main__':
    main()
