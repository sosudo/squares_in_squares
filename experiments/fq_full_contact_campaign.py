#!/usr/bin/env python3
"""One-CPU staged contact-LP polishing, with immutable early certificates."""
from __future__ import annotations
import time
ENTRY_STARTED = time.monotonic()
import argparse
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
import fq_active_pilot as fq
import fq_full_basin_pilot as basin
from compose_gadgets import normalize, read_baseline
from fq_coherent_clusters import alarm, atom_json, atom_npz

ROOT = Path(__file__).resolve().parents[1]
PHASES = [('lp20', 20, 20.), ('lp100', 100, 35.), ('lp150', 150, 40.)]


def campaign(args):
    signal.signal(signal.SIGTERM, alarm)
    deadline = ENTRY_STARTED+args.seconds-8
    args.out.mkdir(parents=True, exist_ok=False)
    for name in ('inputs', 'source', 'trials'):
        (args.out/name).mkdir()
    baseline_sha = fq.digest(args.baseline)
    report = json.loads(args.baseline_report.read_text())
    assert report['valid'] and report['sha256'] == baseline_sha and report['puzzles'] == 1000
    interval = {r['n']:r for r in report['results']}
    candidate_source = json.loads(args.case_source.read_text())
    cases = sorted(map(int, candidate_source))
    assert len(cases) == 20 and len(set(cases)) == 20 and 702 in cases
    poses = read_baseline(args.baseline)
    best = {n:normalize(poses[n]) for n in cases}
    selected = {n:dict(side_lower=interval[n]['side_lower'], side_upper=interval[n]['side_upper'],
        score_upper=interval[n]['score_upper'], geometry_sha256=basin.geom_sha(best[n])) for n in cases}
    best_side = {n:float(selected[n]['side_upper']) for n in cases}
    source_proofs = [dict(path=str(p), sha256=fq.digest(p)) for p in
                     (args.baseline, args.baseline_report, args.case_source)]
    shutil.copy2(args.baseline_report, args.out/'inputs/baseline-report.json')
    shutil.copy2(args.case_source, args.out/'inputs/case-source.json')
    atom_npz(args.out/'inputs/initial-poses.npz', {str(n):p for n,p in best.items()})
    binary = (args.out/'inputs/fq').resolve()
    shutil.copy2(args.binary, binary)
    binary.chmod(0o500)
    assert fq.digest(binary) == fq.digest(args.binary)
    sources = [Path(__file__), ROOT/'experiments/fq_full_basin_pilot.py', ROOT/'experiments/fq_active_pilot.py',
        ROOT/'experiments/fq_coherent_clusters.py', ROOT/'experiments/fq_capacity_probe.py',
        ROOT/'experiments/compose_gadgets.py', ROOT/'scripts/validate_submission.py',
        ROOT/'scripts/score_official.py', ROOT/'research/official_metric_v17.py']
    for source in sources:
        shutil.copy2(source, args.out/'source'/source.name)
    # Change only this worker's imported option dictionary; no source files change.
    for mode, steps, cap in PHASES:
        basin.MODES[mode] = ['--no-alm', '--loosen', '1', '--pit', str(steps), '--flip-top', '0']
    basin.MODES['control'] = basin.MODES['lp20'][:]
    manifest = dict(inputs=source_proofs, selected=selected, cases=cases,
        binary_sha256=fq.digest(binary), source_commit=fq.SOURCE_COMMIT,
        source_hashes={str(p):fq.digest(p) for p in sources},
        initial_poses_sha256=fq.digest(args.out/'inputs/initial-poses.npz'),
        phases=[dict(mode=mode, steps=steps, inclusive_cap=cap, flags=basin.MODES[mode]) for mode,steps,cap in PHASES],
        workers=1, seconds=args.seconds, max_trials=60,
        priority='20 steps for every case; 100 steps in observed-gain order; 150 steps only for cases with a certified gain',
        admission='Independent interval plus official raw and ordinary pandas certificates; side gain >1e-8',
        command=[sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]], no_submission=True)
    atom_json(args.out/'manifest.json', manifest)
    records, candidates, donors = [], {}, {}
    scores = {n:0. for n in cases}
    def snapshot(status, final=False):
        directory = args.out/('complete' if final else f'snapshot-{len(records):05d}')
        directory.mkdir(exist_ok=False)
        atom_json(directory/'results.json', records)
        atom_json(directory/'candidates.json', candidates)
        atom_npz(directory/'donors.npz', donors)
        summary = dict(status=status, elapsed_seconds=time.monotonic()-ENTRY_STARTED, trials=len(records),
            improved_cases=len(candidates), cases=sorted(map(int,candidates)),
            total_score_gain=sum((float(selected[int(n)]['side_upper'])-float(c['side']))/math.sqrt(int(n)) for n,c in candidates.items()),
            statuses={s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})},
            candidates_sha256=fq.digest(directory/'candidates.json'), donors_sha256=fq.digest(directory/'donors.npz'),
            results_sha256=fq.digest(directory/'results.json'), manifest_sha256=fq.digest(args.out/'manifest.json'))
        atom_json(directory/'analysis.json', summary)
        atom_json(args.out/'current.json', dict(snapshot=str(directory), analysis_sha256=fq.digest(directory/'analysis.json'), status=status))
        return summary
    print(json.dumps(dict(stage='start', cases=cases, seconds=args.seconds, workers=1)), flush=True)
    for phase, (mode, steps, cap) in enumerate(PHASES):
        order = ([702]+[n for n in cases if n != 702]) if phase == 0 else sorted(cases, key=lambda n:(-scores[n], -float(selected[n]['score_upper']), n))
        if phase == 2:
            order = [n for n in order if str(n) in candidates]
        for n in order:
            if time.monotonic() >= deadline-3:
                break
            effective_mode = 'control' if not records else mode
            record, p = basin.run_one(best[n], best_side[n], effective_mode, 9273000+len(records), binary,
                (args.out/'trials').resolve(), cap, deadline)
            record.update(phase=phase, requested_steps=steps, original_side=selected[n]['side_upper'])
            if not records:
                atom_json(args.out/'positive-control.json', record)
                if p is None:
                    raise ValueError('Latest n702 full-puzzle contact-LP control failed')
            if p is not None and record['side_gain'] > 1e-8:
                length = record['certificate']['independent_raw']['side_upper']
                best[n], best_side[n] = p, float(length)
                scores[n] = (float(selected[n]['side_upper'])-float(length))/math.sqrt(n)
                key = record['key']+'__contact_'+record['geometry_sha256']
                donors[key] = p
                candidates[str(n)] = dict(side=length, squares=[[f'{v:.17g}' for v in row] for row in p],
                    source='Staged complete-puzzle contact-LP refinement', certificate=record['certificate'],
                    provenance=dict(manifest_sha256=fq.digest(args.out/'manifest.json'), trial=len(records),
                        parent_geometry_sha256=record['parent_geometry_sha256'], phase=phase, steps=steps))
                record['score_gain_vs_frozen_baseline'] = scores[n]
            elif p is not None:
                record['status'] = 'positive-control-valid-no-gain'
            records.append(record)
            summary = snapshot('running')
            print(json.dumps({k:v for k,v in record.items() if k not in ('fq','certificate','command')}), flush=True)
        if time.monotonic() >= deadline-3:
            break
    for proof in source_proofs:
        assert fq.digest(proof['path']) == proof['sha256']
    assert fq.digest(binary) == manifest['binary_sha256']
    print(json.dumps(snapshot('complete', final=True)), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--baseline-report', type=Path, required=True)
    ap.add_argument('--case-source', type=Path, required=True)
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seconds', type=float, default=885)
    args = ap.parse_args()
    if args.out.exists() or not 60 <= args.seconds <= 890:
        ap.error('New output directory and 60–890s total required; exactly one worker')
    process = mp.get_context('fork').Process(target=campaign, args=(args,))
    process.start()
    process.join(max(0, args.seconds-(time.monotonic()-ENTRY_STARTED)))
    enforced = process.is_alive()
    if enforced:
        process.terminate()
        process.join(1)
        if process.is_alive():
            process.kill()
            process.join(.5)
    receipt = dict(elapsed_seconds=time.monotonic()-ENTRY_STARTED, exitcode=process.exitcode,
        hard_deadline_enforced=enforced, workers=1)
    if args.out.exists():
        atom_json(args.out/'supervisor.json', receipt)
    print(json.dumps(receipt), flush=True)
    if process.exitcode:
        raise SystemExit(process.exitcode)


if __name__ == '__main__':
    main()
