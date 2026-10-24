#!/usr/bin/env python3
"""Two bounded native checks of the exact mixed-source n299 seed.

The held treatment keeps the encoded incumbent box throughout the rounded
return. It has an initial all-square kick, no rounded compression, and ends at
zero corner radius before the ordinary rigid finish. Every certified output is
retained, including a scalar-worse result or an invalid experimental trace.
"""
import time
ENTRY_STARTED = time.monotonic()
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
import fq_full_local_campaign as full
from fq_dual_cage_soft import retaining_stage_source
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha

ROOT = Path(__file__).resolve().parents[1]
BINARY_SHA = '10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
RIGID = ['--loosen', '1', '--outer', '45', '--pit', '100', '--flip-top', '16']
HELD = RIGID + ['--round-r0', '.15', '--round-steps', '12', '--round-p', '2',
                '--round-kick', '.004', '--hold-f', '1', '--kick', '.04', '--v']


def held_trace(options, encoded_side, report, logs):
    radii = [float(value) for value in re.findall(r'round r ([0-9.eE+-]+) hold', logs)]
    def number(option):
        return float(options[options.index(option)+1])
    trace = report.get('round', {})
    valid = ('--round-compress' not in options and number('--hold-f') == 1.
             and number('--kick') == .04 and number('--round-r0') == .15
             and len(radii) == int(number('--round-steps')) and bool(radii)
             and radii[-1] == 0. and all(a >= b >= 0. for a, b in zip(radii, radii[1:]))
             and trace.get('r0') == .15
             and max(abs(trace.get('s_soft', math.inf)-encoded_side),
                     abs(trace.get('s_hold', math.inf)-encoded_side)) <= 1e-10)
    return dict(valid=valid, reported_radii=radii, encoded_box_side=encoded_side,
                native_round=trace, no_round_compress='--round-compress' not in options,
                requested_initial_kick=number('--kick'), hold_factor=number('--hold-f'),
                box_tolerance=1e-10,
                native_source_invariant='No round-compress: sa=s; hold-f1: sh=s; '
                    '12 fixed-side relaxations lower r to exact0; set_rnd(0) precedes rigid finish.')


def persistent_native_run(command, capture_output=True, text=True, timeout=None):
    """Native inherits the supervised group; preserve logs even on timeout."""
    target = Path(command[command.index('--out')+1])
    stdout, stderr = target.with_suffix('.native-stdout'), target.with_suffix('.native-stderr')
    with stdout.open('w') as out, stderr.open('w') as err:
        process = subprocess.Popen(command, stdout=out, stderr=err)
        try:
            process.wait(timeout=timeout)
        except BaseException:
            process.kill()
            process.wait(timeout=1.)
            raise
    return subprocess.CompletedProcess(command, process.returncode, stdout.read_text(), stderr.read_text())


def run(args):
    signal.signal(signal.SIGTERM, full.alarm)
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    for name in ('source', 'inputs', 'trials', 'retained'):
        (out/name).mkdir()
    proof_path = args.seed/'proof.json'
    proof = json.loads(proof_path.read_text())
    seed_path = args.seed/'seed.npz'
    certificate_path = args.seed/'certificate.json'
    if (full.fq.digest(seed_path) != proof['seed_sha256']
            or full.fq.digest(certificate_path) != proof['certificate_sha256']):
        raise ValueError('Exact seed or its certificate changed')
    with np.load(seed_path, allow_pickle=False) as archive:
        p = archive['299'].copy()
    actual = json.loads(certificate_path.read_text())['actual']
    if (p.shape != (299, 3) or geometry_sha(p) != proof['geometry_sha256']
            or not actual['valid'] or actual['geometry_sha256'] != geometry_sha(p)
            or actual['official_metric_sha256'] != full.fq.OFFICIAL_SHA256):
        raise ValueError('Seed does not match the fully certified exact geometry')
    pointer = json.loads(args.portfolio.read_text())
    report_path = Path(pointer['safe']['official_report'])
    if full.fq.digest(report_path) != pointer['safe']['official_report_sha256']:
        raise ValueError('Canonical official report changed')
    report = json.loads(report_path.read_text())
    if not (report['sha256'] == pointer['safe']['sha256'] and report['valid']
            and report['invalid_count'] == 0 and report['puzzles'] == 1000
            and report['metric_sha256'] == full.fq.OFFICIAL_SHA256):
        raise ValueError('Canonical full official proof mismatch')
    canonical = next(float(row['side']) for row in report['results'] if row['n'] == 299)
    binary = out/'inputs/fq'
    shutil.copyfile(args.binary, binary)
    binary.chmod(0o500)
    if full.fq.digest(binary) != BINARY_SHA:
        raise ValueError('Unreviewed native binary')
    shutil.copyfile(seed_path, out/'inputs/seed.npz')
    shutil.copyfile(proof_path, out/'inputs/seed-proof.json')
    shutil.copyfile(certificate_path, out/'inputs/seed-certificate.json')
    sources = [Path(__file__), Path(full.__file__), ROOT/'experiments/fq_dual_cage_soft.py',
               ROOT/'experiments/fq_active_pilot.py', ROOT/'experiments/fq_capacity_probe.py',
               ROOT/'experiments/fq_coherent_clusters.py', ROOT/'experiments/fq_variant_campaign.py',
               ROOT/'experiments/compose_gadgets.py', ROOT/'scripts/validate_submission.py',
               ROOT/'research/official_metric_v17.py', ROOT/'vendor/fq/src/fq.rs']
    for source in sources:
        shutil.copyfile(source, out/'source'/source.name)
    stage_path = out/'source/retaining_run_stage.py'
    stage_path.write_text(retaining_stage_source())
    namespace = dict(full.__dict__)
    namespace['grouped_run'] = persistent_native_run
    exec(compile(stage_path.read_text(), str(stage_path), 'exec'), namespace)
    stage = namespace['run_stage']
    manifest = dict(seed_sha256=full.fq.digest(seed_path), seed_proof_sha256=full.fq.digest(proof_path),
        seed_certificate_sha256=full.fq.digest(certificate_path), seed_geometry_sha256=geometry_sha(p),
        seed_side=proof['actual_side'], canonical_side=canonical,
        canonical_report_sha256=full.fq.digest(report_path), canonical_csv_sha256=report['sha256'],
        binary_sha256=BINARY_SHA, source_commit=full.fq.SOURCE_COMMIT, source_license='MIT; Evan Daniel',
        source_hashes={str(path):full.fq.digest(path) for path in sources},
        retaining_stage_sha256=full.fq.digest(stage_path),
        modifications='Only scalar-band discard removed; native inherits supervised process group; full gates unchanged.',
        options={'rigid':RIGID, 'held_box':HELD}, caps_seconds={'rigid':22., 'held_box':28.},
        maximum_total_seconds=60, workers=1, no_gpu=True, no_submission=True,
        comparison='Actual certified side versus current canonical n299, never versus seed clearance.',
        independent_starts='Both native commands start from identical exact seed geometry.')
    atomic_json(out/'manifest.json', manifest)
    records, donors, certificates = [], {}, {}
    for index, (mode, options, cap) in enumerate((('rigid', RIGID, 22.), ('held_box', HELD, 28.))):
        record, q = stage(p.copy(), canonical, mode, options, 2993800+index, binary.resolve(),
                          (out/'trials').resolve(), cap, args.deadline)
        if mode == 'held_box' and 'fq' in record:
            inp = Path(record['command'][record['command'].index('--in')+1])
            encoded_side = float(inp.read_text().splitlines()[0].split()[1])
            logs = inp.with_suffix('.native-stderr').read_text()
            record['held_box_trace'] = held_trace(options, encoded_side, record['fq'], logs)
        if q is not None:
            name = '299__joint38_'+mode+'_'+geometry_sha(q)
            donors[name] = q
            certificates[name] = record['certificate']
            record['retained_key'] = name
            record['strict_canonical_gain'] = record['side'] < canonical
            target = out/'retained'/(geometry_sha(q)+'.npz')
            atomic_npz(target, {name:q})
            atomic_json(target.with_suffix('.json'), dict(archive_sha256=full.fq.digest(target), record=record))
            target.chmod(0o444)
            target.with_suffix('.json').chmod(0o444)
        records.append(record)
        atomic_json(out/'results.json', records)
        atomic_npz(out/'donors.npz', donors)
        atomic_json(out/'certificates.json', certificates)
        print(json.dumps(dict(mode=mode, status=record['status'], side=record.get('side'),
                              seconds=record.get('elapsed_seconds'))), flush=True)
    unchanged = all(full.fq.digest(path) == identity for path, identity in manifest['source_hashes'].items())
    summary = dict(status='complete' if unchanged else 'source_changed_quarantine', workers=1,
        seconds=time.monotonic()-ENTRY_STARTED, stages=len(records), certified_variants=len(donors),
        canonical_side=canonical, input_side=proof['actual_side'],
        best_side=min([canonical]+[r['side'] for r in records if r.get('status') == 'certified']),
        strict_gains=sum(bool(r.get('strict_canonical_gain')) for r in records),
        source_hashes_unchanged=unchanged, manifest_sha256=full.fq.digest(out/'manifest.json'),
        results_sha256=full.fq.digest(out/'results.json'), donors_sha256=full.fq.digest(out/'donors.npz'),
        certificates_sha256=full.fq.digest(out/'certificates.json'))
    atomic_json(out/'summary.json', summary)
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, default=ROOT/'artifacts/joint-mis-seed38-v1')
    parser.add_argument('--portfolio', type=Path, default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--binary', type=Path, default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--deadline', type=float, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        return run(args)
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:],
        '--child', '--deadline', str(ENTRY_STARTED+55.)], start_new_session=True)
    forced = False
    try:
        process.wait(timeout=max(.01, ENTRY_STARTED+57.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=1.)
    receipt = dict(returncode=process.returncode, seconds=time.monotonic()-ENTRY_STARTED,
                   workers=1, hard_deadline_enforced=forced, maximum_total_seconds=60)
    if args.out.exists():
        atomic_json(args.out/'supervisor.json', receipt)
    print(json.dumps(receipt), flush=True)
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
