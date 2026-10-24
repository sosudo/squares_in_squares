"""Audit immutable full-local outputs by exact certificate bindings, without reruns."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

METRIC_SHA = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest()


def analyze(directory):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    manifest_sha=sha(directory/'manifest.json')
    stored={};records=[]
    for path in sorted((directory/'retained').glob('*.json')):
        record=json.loads(path.read_text());archive_path=path.with_suffix('.npz')
        if record['manifest_sha256']!=manifest_sha or record['archive_sha256']!=sha(archive_path):
            raise ValueError('Retained immutable source binding mismatch')
        with np.load(archive_path,allow_pickle=False) as archive:
            if len(archive.files)!=1:raise ValueError('Expected one immutable pose')
            q=archive[archive.files[0]]
        if geometry_sha(q)!=record['geometry_sha256'] or q.shape!=(record['n'],3):
            raise ValueError('Retained geometry identity mismatch')
        c=record['certificate'];shared=c['shared_official_gate']
        if not (record['status']=='certified' and c['valid'] and shared['valid'] and
                shared['metric_sha256']==METRIC_SHA and shared['raw_reason']==shared['roundtrip_reason']=='ok'
                and c['ordinary_pandas_official_reason']=='ok' and
                c['independent_raw']['valid'] and c['independent_roundtrip']['valid']):
            raise ValueError('Complete immutable certificate missing')
        if record['mode']=='local' and not record['rigid_return_trace']['valid']:
            raise ValueError('Retained local pose lacks rigid return')
        stored[record['geometry_sha256']]=q;records.append(record)
    for record in records:
        if record['mode']=='release' and record['source_local_geometry_sha256'] not in stored:
            raise ValueError('Released pose lost its already-certified local intermediate')
    with np.load(directory/'donors.npz',allow_pickle=False) as archive:
        aggregate={geometry_sha(archive[name]) for name in archive.files}
    if aggregate!=set(stored):
        raise ValueError('Aggregate donor archive differs from immutable certified records')
    candidates=json.loads((directory/'candidates.json').read_text())
    for n,candidate in candidates.items():
        p=candidate['provenance'];record_path=Path(p['record_path'])
        if sha(record_path)!=p['record_sha256'] or p['geometry_sha256'] not in stored:
            raise ValueError('Candidate immutable record binding missing')
        q=np.asarray(candidate['squares'],dtype=float)
        if geometry_sha(q)!=p['geometry_sha256'] or len(q)!=int(n):
            raise ValueError('Candidate text differs from certified geometry')
        if candidate['squares']!=[[format(float(v),'.17g')for v in row]for row in q]:
            raise ValueError('Candidate export differs from certified raw decimal text')
    trials=json.loads((directory/'results.json').read_text())
    families=defaultdict(list)
    for r in records:families[r['n']].append(r)
    coverage=defaultdict(list)
    for r in trials:
        if r['mode']=='local':
            coverage[r['n']].append(dict(trial=r['trial'],free_count=r['selection']['requested_free_count'],
                amplitude=r['amplitude'],hold=r['hold'],status=r['status']))
    stop_path=directory/'intentional-stop.json'
    analysis=dict(manifest_sha256=manifest_sha,certification_rerun=False,
        status='intentionally_stopped_after_method_coverage' if stop_path.exists() else 'finished',
        intentional_stop_sha256=sha(stop_path) if stop_path.exists() else None,
        donors_sha256=sha(directory/'donors.npz'),coverage=dict(coverage),
        immutable_certified_variants=len(records),distinct_candidate_cases=len(candidates),
        candidates_sha256=sha(directory/'candidates.json'),
        stages=len(trials),statuses=dict(Counter(r['status']for r in trials)),
        actual_certified_local_stages=sum(r['mode']=='local'for r in records),
        actual_certified_release_stages=sum(r['mode']=='release'for r in records),
        changed_contact_variants=sum(bool(r.get('geometry_change',{}).get('contacts_lost')or
                r.get('geometry_change',{}).get('contacts_gained'))for r in records),
        max_free_position_change=max((r.get('geometry_change',{}).get('free_position_max',0.)for r in records),default=0.),
        max_free_angle_change_degrees=max((r.get('geometry_change',{}).get('free_angle_max_degrees',0.)for r in records),default=0.),
        cases={str(n):dict(variants=len(rr),best_side=min(r['side']for r in rr),
            best_side_gain=max(r['side_gain']for r in rr),
            changed_contacts=sum(bool(r.get('geometry_change',{}).get('contacts_lost')or
                r.get('geometry_change',{}).get('contacts_gained'))for r in rr))for n,rr in families.items()},
        limitation='Candidate gains compare to the frozen source baseline; current portfolio merging and whole-CSV validation remain separate.')
    return analysis


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    args=parser.parse_args();analysis=analyze(args.directory)
    (args.directory/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
    print(json.dumps(analysis))
