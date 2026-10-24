"""Freeze only three unreturned pit80 jobs for a longer wall-clock completion."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
sys.path.insert(0, str(ROOT/'scripts'))
from fq_active_pilot import encode
from fq_variant_campaign import geometry_sha
from score_official import OFFICIAL_SHA256

CASES = (997, 981, 995)
RAW_SHA = 'add7c0ee1599b97bb229f279dd0ee927c502ad6710940faccd92dca7c7658a53'
FLAGS = ['--no-alm','--loosen','1','--pit','80','--flip-top','0','--v']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(out):
    prior_inputs = ROOT/'artifacts/fq-selective-polish-inputs-v1'
    freeze_path = prior_inputs/'freeze.json'; frozen = json.loads(freeze_path.read_text())
    for name, digest in frozen['files'].items():
        assert sha(prior_inputs/name) == digest
    pointer_bytes = (prior_inputs/'pointer.json').read_bytes(); pointer = json.loads(pointer_bytes); raw = pointer['raw']
    assert raw['sha256'] == RAW_SHA and sha(raw['path']) == RAW_SHA
    assert sha(raw['official_report']) == raw['official_report_sha256']
    report = json.loads(Path(raw['official_report']).read_text())
    assert report['valid'] and report['puzzles'] == 1000 and report['sha256'] == RAW_SHA
    assert report['metric_sha256'] == OFFICIAL_SHA256 and sha(report['metric']) == OFFICIAL_SHA256
    sides = {r['n']: r['side'] for r in report['results']}
    records_path = ROOT/'artifacts/fq-selective-polish-v1/complete/results.json'
    records = json.loads(records_path.read_text())
    remaining = {r['n']: r for r in records if r['status'] == 'no_native_output' and r['native_status'] == 'timeout'}
    assert set(remaining) == set(CASES)
    source_files = {str(records_path): sha(records_path), str(freeze_path): sha(freeze_path)}
    poses = {}; queue = []
    with np.load(prior_inputs/'inputs/current-poses.npz', allow_pickle=False) as initial:
        for n in CASES:
            r = remaining[n]; command = r['command']; native = Path(command[command.index('--out')+1])
            parent = native.with_suffix('.parent.npz'); inp = Path(command[command.index('--in')+1])
            assert not native.exists() and sha(parent) == r['parent_archive_sha256'] and sha(inp) == r['input_sha256']
            with np.load(parent, allow_pickle=False) as archive:
                p = archive['pose'].copy()
            assert np.array_equal(p, initial[str(n)]) and p.shape == (n, 3) and np.isfinite(p).all()
            assert geometry_sha(p) == r['parent_geometry_sha256']
            text, offsets = encode(p, math.isqrt(n), math.isqrt(n)); assert offsets == [0, 0]
            assert hashlib.sha256(text.encode()).hexdigest() == r['input_sha256']
            seed = int(command[command.index('--seed')+1])
            assert seed == 9610000+r['job'] and command[command.index('--seed')+2:] == FLAGS
            source_files.update({str(parent): sha(parent), str(inp): sha(inp),
                str(native.with_suffix('.stderr')): sha(native.with_suffix('.stderr'))})
            poses[n] = p
            queue.append(dict(n=n, geometry_sha256=geometry_sha(p), original_job=r['job'], original_seed=seed,
                original_input_sha256=r['input_sha256'], expected_input_sha256=r['input_sha256'],
                original_parent_path=str(parent), original_parent_archive_sha256=sha(parent), original_command=command,
                category='same_input_pit80_wallclock_completion_only', canonical_raw_side=sides[n],
                legacy_history='Exact prior40s no-output pit80 input/seed;75s cap and3vs2CPU concurrency differ. Same max80iterations and numericflags; no extra iterations or successful-result repeat.'))
    out.mkdir(parents=True, exist_ok=False); (out/'inputs').mkdir()
    audit = dict(pointer=pointer, pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(), finite_queue=queue,
        source_files=source_files, original_flags=FLAGS, previous_workers=2, workers=3,
        previous_native_cap=40, native_cap=75, certificate_cap=8, whole_seconds=100,
        scope='Three unreturned jobs only; exact old680 parents/encodedinputs/seeds/pit80 numericflags. Wallcap and concurrency differ; no universal convergence claim. No optimizer/certificate during preparation.')
    (out/'audit.json').write_text(json.dumps(audit, indent=2)+'\n'); (out/'pointer.json').write_bytes(pointer_bytes)
    with (out/'inputs/current-poses.npz').open('wb') as stream:
        np.savez(stream, **{str(n): poses[n] for n in CASES})
    freeze = dict(files={name: sha(out/name) for name in ('audit.json','pointer.json','inputs/current-poses.npz')},
        preparer_sha256=sha(__file__), baseline=raw, queue_count=3, no_optimization=True)
    (out/'freeze.json').write_text(json.dumps(freeze, indent=2)+'\n')
    for path in out.rglob('*'):
        if path.is_file(): path.chmod(0o444)
    print(json.dumps(dict(cases=CASES, freeze_sha256=sha(out/'freeze.json'), seeds={r['n']:r['original_seed'] for r in queue}), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); prepare(args.out)
