"""Freeze six exact fresh-current feasible poses for a no-ALM contact tail."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
sys.path.insert(0, str(ROOT/'scripts'))
from fq_variant_campaign import geometry_sha
from score_official import OFFICIAL_SHA256

EXPECTED_RAW = 'add7c0ee1599b97bb229f279dd0ee927c502ad6710940faccd92dca7c7658a53'
EXPECTED_SAFE = '680e332bc6bc5bb7d741505b9460ca18fb410ce11929342e67fb2262b20a2d74'
CASES = (761, 920, 997, 868, 981, 995)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(out, pointer_path):
    pointer_bytes = pointer_path.read_bytes(); pointer = json.loads(pointer_bytes)
    assert pointer['raw']['sha256'] == EXPECTED_RAW and pointer['safe']['sha256'] == EXPECTED_SAFE
    for kind in ('raw', 'safe', 'roundtrip'):
        entry = pointer[kind]
        assert sha(entry['path']) == entry['sha256'] and sha(entry['official_report']) == entry['official_report_sha256']
        report = json.loads(Path(entry['official_report']).read_text())
        assert report['valid'] and report['puzzles'] == 1000 and report['sha256'] == entry['sha256']
        assert report['metric_sha256'] == OFFICIAL_SHA256 and sha(report['metric']) == OFFICIAL_SHA256
    assert sha(pointer['canonical_proof']) == pointer['canonical_proof_sha256']
    raw = pointer['raw']; official = json.loads(Path(raw['official_report']).read_text())
    sides = {r['n']: r['side'] for r in official['results']}
    rows = {n: [] for n in CASES}
    with open(raw['path']) as stream:
        for row in csv.DictReader(stream):
            n = int(row['n'])
            if n in rows:
                rows[n].append((int(row['square_id']), [float(row[k]) for k in ('x', 'y', 'angle')]))
    poses = {}
    for n, entries in rows.items():
        assert sorted(i for i, _ in entries) == list(range(n))
        poses[n] = np.array([row for _, row in sorted(entries)], dtype=np.float64)
        assert poses[n].shape == (n, 3) and np.isfinite(poses[n]).all()
    queue = [dict(n=n, category='fresh_feasible_no_alm_tail_followup', geometry_sha256=geometry_sha(poses[n]),
        canonical_raw_side=sides[n], current_raw_sha256=EXPECTED_RAW,
        legacy_history='Fresh exact current feasible RAW; prior rigid lineage is inherited in the canonical proof. This finite no-ALM pit80 tail is a different treatment, not a claim that the case was never tested.') for n in CASES]
    out.mkdir(parents=True, exist_ok=False); (out/'inputs').mkdir()
    audit = dict(pointer=pointer, pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(),
        pointer_changed_during_audit=pointer_path.read_bytes() != pointer_bytes, finite_queue=queue,
        scope='Six fresh-current feasible sources only; noALM loosen1 pit80 fliptop0 with observationaltrace, native40s/gate8s,2CPU180s. Preparation executes no optimizer or certificate.')
    assert not audit['pointer_changed_during_audit']
    (out/'audit.json').write_text(json.dumps(audit, indent=2)+'\n'); (out/'pointer.json').write_bytes(pointer_bytes)
    with (out/'inputs/current-poses.npz').open('wb') as stream:
        np.savez(stream, **{str(n): poses[n] for n in CASES})
    freeze = dict(files={name: sha(out/name) for name in ('audit.json','pointer.json','inputs/current-poses.npz')},
        preparer_sha256=sha(__file__), baseline=raw, queue_count=6, no_optimization=True)
    (out/'freeze.json').write_text(json.dumps(freeze, indent=2)+'\n')
    for path in out.rglob('*'):
        if path.is_file(): path.chmod(0o444)
    print(json.dumps(dict(cases=CASES, freeze_sha256=sha(out/'freeze.json'), baseline=raw,
        pointer_changed=False), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pointer', type=Path, default=ROOT/'artifacts/current-best-portfolio.json')
    args = parser.parse_args(); prepare(args.out, args.pointer)
