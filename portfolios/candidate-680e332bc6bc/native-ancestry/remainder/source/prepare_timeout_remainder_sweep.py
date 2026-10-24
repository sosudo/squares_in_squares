"""Freeze28 same-parent timeout controls plus2 freshly changed public poses."""
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


def prepare(out):
    pointer_path = ROOT/'artifacts/fq-timeout-extension-inputs-v1/pointer.json'
    pointer_bytes = pointer_path.read_bytes(); pointer = json.loads(pointer_bytes); raw = pointer['raw']
    assert raw['sha256'] == EXPECTED_RAW and sha(raw['path']) == EXPECTED_RAW
    assert sha(raw['official_report']) == raw['official_report_sha256']
    official = json.loads(Path(raw['official_report']).read_text())
    assert official['valid'] and official['puzzles'] == 1000 and official['sha256'] == EXPECTED_RAW
    assert official['metric_sha256'] == OFFICIAL_SHA256 and sha(official['metric']) == OFFICIAL_SHA256
    sides = {r['n']: r['side'] for r in official['results']}
    previous = ROOT/'artifacts/fq-current-rigid-v1/complete/results.json'
    completed_path = ROOT/'artifacts/fq-timeout-extension-v1/complete/results.json'
    completed = json.loads(completed_path.read_text())
    assert len(completed) == 16 and all(r['status'] == 'certified' for r in completed)
    completed_n = {r['n'] for r in completed}
    records = json.loads(previous.read_text())
    timed = [r for r in records if r.get('native_status') == 'timeout' and r['status'] == 'no_native_output']
    assert len(timed) == 47
    remaining = [r for r in timed if r['n'] != 858 and r['n'] not in completed_n]
    assert len(remaining) == 30 and {802, 928} <= {r['n'] for r in remaining}
    target_path = ROOT/'artifacts/public-freshness/notebooks-20261024T092136Z/public-per-puzzle-reference.json'
    targets = {r['n']: r for r in json.loads(target_path.read_text())}
    poses = {r['n']: [] for r in remaining}
    with open(raw['path']) as stream:
        for row in csv.DictReader(stream):
            n = int(row['n'])
            if n in poses:
                poses[n].append((int(row['square_id']), [float(row[k]) for k in ('x', 'y', 'angle')]))
    current = {n: np.array([row for _, row in sorted(values)], dtype=np.float64) for n, values in poses.items()}
    queue = []; sources = {str(previous): sha(previous), str(completed_path): sha(completed_path)}
    for r in remaining:
        n = r['n']; command = r['command']; native = Path(command[command.index('--out')+1])
        parent = native.with_suffix('.parent.npz'); inp = Path(command[command.index('--in')+1])
        assert sha(parent) == r['parent_archive_sha256'] and sha(inp) == r['input_sha256']
        with np.load(parent, allow_pickle=False) as archive:
            original = archive['pose']
        assert original.shape == (n, 3) and geometry_sha(original) == r['parent_geometry_sha256']
        p = current[n]; assert p.shape == (n, 3) and np.isfinite(p).all()
        unchanged = np.array_equal(p, original)
        assert unchanged == (n not in (802, 928)), 'Unexpected extra changed or unchanged parent'
        text, offsets = encode(p, math.isqrt(n), math.isqrt(n)); assert offsets == [0, 0]
        expected = hashlib.sha256(text.encode()).hexdigest()
        if unchanged:
            assert expected == r['input_sha256']
        seed = int(command[command.index('--seed')+1])
        assert command[command.index('--seed')+2:] == ['--loosen','1','--outer','45','--pit','20','--flip-top','0']
        headroom = (float(sides[n])-float(targets[n]['L']))/math.sqrt(n)
        assert headroom > 1e-8
        sources.update({str(parent): sha(parent), str(inp): sha(inp)})
        queue.append(dict(n=n, category='unchanged_parent_timeout_remainder' if unchanged else 'FRESH_CURRENT_PUBLIC_CHANGED',
            same_parent_timeout_control=unchanged, headroom=headroom, geometry_sha256=geometry_sha(p),
            original_geometry_sha256=geometry_sha(original), original_job=r['job'], original_seed=seed,
            original_input_sha256=r['input_sha256'], expected_input_sha256=expected,
            original_command=command, original_parent_path=str(parent), original_parent_archive_sha256=sha(parent),
            original_record=r, canonical_raw_side=sides[n], target=targets[n],
            legacy_history='Same original10s parent/seed' if unchanged else 'Fresh public31 current parent; originalseed reused, no same-parent causal claim.'))
    queue.sort(key=lambda r: (-r['headroom'], r['n']))
    assert len(queue) == 30 and len({r['n'] for r in queue}) == 30
    assert sum(r['same_parent_timeout_control'] for r in queue) == 28
    out.mkdir(parents=True, exist_ok=False); (out/'inputs').mkdir()
    audit = dict(pointer=pointer, frozen_pointer_path=str(pointer_path), pointer_sha256=sha(pointer_path),
        target_path=str(target_path), target_sha256=sha(target_path), source_files=sources,
        excluded858=True, excluded_completed16=sorted(completed_n), finite_queue=queue,
        same_parent_controls=28, fresh_current_public_changed=[802, 928],
        scope='Frozenfc931 prior baseline avoids current-pointer merge race.30 finite sources; originalseeds/numericflags,30s native+6s gate,3CPU420s.802/928 explicitly fresh,not same-parent timeout controls. No optimization during preparation.')
    (out/'audit.json').write_text(json.dumps(audit, indent=2)+'\n'); (out/'pointer.json').write_bytes(pointer_bytes)
    with (out/'inputs/current-poses.npz').open('wb') as stream:
        np.savez(stream, **{str(row['n']): current[row['n']] for row in queue})
    freeze = dict(files={name: sha(out/name) for name in ('audit.json','pointer.json','inputs/current-poses.npz')},
        preparer_sha256=sha(__file__), baseline=raw, queue_count=30, no_optimization=True)
    (out/'freeze.json').write_text(json.dumps(freeze, indent=2)+'\n')
    for path in out.rglob('*'):
        if path.is_file(): path.chmod(0o444)
    print(json.dumps(dict(queue=[r['n'] for r in queue], controls=28, fresh=[802,928],
        freeze_sha256=sha(out/'freeze.json'), baseline=raw), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); prepare(args.out)
