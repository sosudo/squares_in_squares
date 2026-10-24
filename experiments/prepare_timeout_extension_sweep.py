"""Freeze sixteen exact unchanged parents for a finite10s→30s timeout control."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
sys.path.insert(0, str(ROOT/'scripts'))
from fq_active_pilot import encode
from fq_variant_campaign import geometry_sha
from score_official import OFFICIAL_SHA256

EXPECTED_RAW = 'fc931068f0f4accb37c8ed8b33ea59607e4690440d7c3f98b4b79fbb8c34cffc'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(out, pointer_path):
    pointer_bytes = pointer_path.read_bytes(); pointer = json.loads(pointer_bytes); raw = pointer['raw']
    assert raw['sha256'] == EXPECTED_RAW and sha(raw['path']) == EXPECTED_RAW
    assert sha(raw['official_report']) == raw['official_report_sha256']
    official = json.loads(Path(raw['official_report']).read_text())
    assert official['valid'] and official['puzzles'] == 1000 and official['sha256'] == EXPECTED_RAW
    assert official['metric_sha256'] == OFFICIAL_SHA256 and sha(official['metric']) == OFFICIAL_SHA256
    sides = {r['n']: r['side'] for r in official['results']}
    previous = ROOT/'artifacts/fq-current-rigid-v1/complete/results.json'
    records = json.loads(previous.read_text())
    timed = [r for r in records if r.get('native_status') == 'timeout' and r['status'] == 'no_native_output']
    assert len(timed) == 47 and len({r['n'] for r in timed}) == 47
    target_path = ROOT/'artifacts/public-freshness/notebooks-20261024T092136Z/public-per-puzzle-reference.json'
    targets = {r['n']: r for r in json.loads(target_path.read_text())}
    poses = {r['n']: [] for r in timed}
    with open(raw['path']) as stream:
        for row in csv.DictReader(stream):
            n = int(row['n'])
            if n in poses:
                poses[n].append((int(row['square_id']), [float(row[k]) for k in ('x', 'y', 'angle')]))
    current = {n: np.array([row for _, row in sorted(values)], dtype=np.float64) for n, values in poses.items()}
    eligible = []; excluded = []; source_files = {str(previous): sha(previous)}
    for r in timed:
        n = r['n']
        if n == 858:
            excluded.append(dict(n=n, reason='explicitly_excluded858')); continue
        command = r['command']; native_output = Path(command[command.index('--out')+1])
        parent = native_output.with_suffix('.parent.npz'); inp = Path(command[command.index('--in')+1])
        assert sha(parent) == r['parent_archive_sha256'] and sha(inp) == r['input_sha256']
        with np.load(parent, allow_pickle=False) as archive:
            original = archive['pose']
        assert original.shape == (n, 3) and geometry_sha(original) == r['parent_geometry_sha256']
        p = current[n]
        assert p.shape == (n, 3) and np.isfinite(p).all()
        if not np.array_equal(p, original):
            excluded.append(dict(n=n, reason='current_parent_changed', current_geometry_sha256=geometry_sha(p),
                original_geometry_sha256=geometry_sha(original), original_job=r['job'])); continue
        text, offsets = encode(p, math.isqrt(n), math.isqrt(n))
        assert offsets == [0, 0] and hashlib.sha256(text.encode()).hexdigest() == r['input_sha256']
        seed = int(command[command.index('--seed')+1])
        assert command[command.index('--seed')+2:] == ['--loosen','1','--outer','45','--pit','20','--flip-top','0']
        headroom = (float(sides[n])-float(targets[n]['L']))/math.sqrt(n)
        if headroom <= 1e-8:
            excluded.append(dict(n=n, reason='no_material_current_headroom')); continue
        source_files.update({str(parent): sha(parent), str(inp): sha(inp)})
        eligible.append(dict(n=n, category='unchanged_parent_timeout_extension', headroom=headroom,
            geometry_sha256=geometry_sha(p), original_job=r['job'], original_seed=seed,
            original_input_sha256=r['input_sha256'], original_command=command,
            original_parent_path=str(parent), original_parent_archive_sha256=sha(parent),
            original_record=r, canonical_raw_side=sides[n], target=targets[n],
            legacy_history='Exact same current/previous parent; original10s no-output timeout, observational30s extension only.'))
    eligible.sort(key=lambda r: (-r['headroom'], r['n'])); queue = eligible[:16]
    assert len(queue) == 16 and not {147,299,335,858} & {r['n'] for r in queue}
    out.mkdir(parents=True, exist_ok=False); (out/'inputs').mkdir()
    audit = dict(pointer=pointer, pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(),
        pointer_changed_during_audit=pointer_path.read_bytes() != pointer_bytes,
        previous_results_path=str(previous), previous_results_sha256=sha(previous),
        target_path=str(target_path), target_sha256=sha(target_path), source_files=source_files,
        original_no_output_timeouts=47, excluded=excluded, eligible_count=len(eligible), finite_queue=queue,
        scope='Finite highest-headroom16 unchanged ordered poses; identical original input/seed/numericflags;30s native+6s gate,3CPU240s. No858 rerun. No optimization during preparation.')
    assert not audit['pointer_changed_during_audit']
    (out/'audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    (out/'pointer.json').write_bytes(pointer_bytes)
    with (out/'inputs/current-poses.npz').open('wb') as stream:
        np.savez(stream, **{str(row['n']): current[row['n']] for row in queue})
    freeze = dict(files={name: sha(out/name) for name in ('audit.json','pointer.json','inputs/current-poses.npz')},
        preparer_sha256=sha(__file__), baseline=raw, queue_count=16, no_optimization=True)
    (out/'freeze.json').write_text(json.dumps(freeze, indent=2)+'\n')
    for path in out.rglob('*'):
        if path.is_file(): path.chmod(0o444)
    print(json.dumps(dict(queue=[r['n'] for r in queue], eligible=len(eligible), excluded=excluded,
        freeze_sha256=sha(out/'freeze.json'), baseline=raw), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pointer', type=Path, default=ROOT/'artifacts/current-best-portfolio.json')
    args = parser.parse_args(); prepare(args.out, args.pointer)
