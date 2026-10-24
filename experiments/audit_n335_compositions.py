"""Cheap finite-library n335 staircase bounds and nearest-pair seam diagnostics.

This audits existing poses only. It does not optimize, certify, or submit a
packing. The scalar screen permits every zero-buffer order, which is a lower
bound for the existing buffered staircase modes as well.
"""
import itertools
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd
from compose_gadgets import extents, normalize, side
from extract_broad_active_frontier import orient
from interface_junction_diagnostic import overlap_edges
from scalar_sat_staircase import array_sha, atom, sha

ROOT = Path(__file__).resolve().parents[1]
BANKS = [
    'artifacts/night-composition-partners-v1/typed_donors.npz',
    'artifacts/donor-retention-audit-v1/inventory-corrected/current-typed-bank.npz',
    'artifacts/fq-night-seeds-v1/final/donors.npz',
    'artifacts/fq-local-soft-v1/all-strict/donors.npz',
    'artifacts/fq-bottleneck-v1/snapshot-00073/donors.npz',
    'artifacts/fq-productive-v1/snapshot-00053/donors.npz',
    'artifacts/fq-cpu-followup-analysis-v2/donors.npz',
    'artifacts/fq-cpu-followup-controls-v1/remote-certified/donors.npz',
    'artifacts/all-high-n-export-results-v1/all_high_n_donors.npz',
    'artifacts/alternative-public-export-results-v2/alternative_donors.npz',
    'artifacts/active-frontier/active_seed_variants.npz',
]


def main():
    began = time.monotonic()
    out = ROOT/'artifacts/n335-composition-coverage-v1'
    out.mkdir(exist_ok=False)
    pointer_path = ROOT/'artifacts/current-best-portfolio.json'
    pointer = json.loads(pointer_path.read_text())
    raw = pointer['raw']; official = json.loads(Path(raw['official_report']).read_text())
    assert official['valid'] and official['sha256'] == raw['sha256'] == sha(raw['path'])
    baseline = next(float(row['side']) for row in official['results'] if row['n'] == 335)
    best, poses, inputs = {}, {}, []
    counts = dict(arrays_inspected=0, arrays_in_relevant_dimensions=0)

    def accept(w, h, d, p, source):
        counts['arrays_inspected'] += 1
        if not (0 < w < 18 and 0 < h < 18 and 0 < d < 11):
            return
        assert p.shape == (w*h+d, 3) and np.isfinite(p).all()
        counts['arrays_in_relevant_dimensions'] += 1
        q = normalize(p)
        lo, hi = extents(q)
        spans = hi.max(0)-lo.min(0)
        f = float(max(spans-[w,h]))
        if not 0 < f < 1:
            return
        for trans in (False, True):
            ww, hh = (h,w) if trans else (w,h)
            key = (ww,hh,d)
            if key not in best or f < best[key]['f']:
                r = orient(q, trans, 1, 1)
                poses[key] = r
                best[key] = dict(w=ww,h=hh,d=d,f=f,source=source,
                    transposed=trans,geometry_sha256=array_sha(r))

    frame = pd.read_csv(raw['path'], float_precision='round_trip')
    for n, group in frame[frame.n <= 335].groupby('n', sort=True):
        k = math.isqrt(int(n))
        accept(k,k,int(n)-k*k,group.sort_values('square_id')[['x','y','angle']].to_numpy(float),
            'current_raw:'+str(n))
    descriptor = ROOT/'artifacts/all-high-n-donors-v1/loader_descriptor.json'
    metadata = json.loads(descriptor.read_text())['donors']
    for name in BANKS:
        path = ROOT/name
        if not path.exists():
            raise ValueError('Missing explicitly selected archive: '+name)
        with np.load(path, allow_pickle=False) as z:
            inputs.append(dict(path=name,sha256=sha(path),arrays=len(z.files)))
            for key in z.files:
                try:
                    w,h,d = map(int,key.split('__')[0].split('_'))
                except ValueError:
                    if key in metadata:
                        m = metadata[key]['original_crop_metadata']
                        w,h,d = m['nominal_width'],m['nominal_height'],m['surplus']
                    else:
                        p = z[key];w=h=math.isqrt(len(p));d=len(p)-w*h
                if 0<w<18 and 0<h<18 and 0<d<11:
                    accept(w,h,d,z[key],name+':'+key)
                else:
                    counts['arrays_inspected'] += 1
    types = [best[k] for k in sorted(best)]
    byd = {}
    for i,t in enumerate(types):
        byd.setdefault(t['d'],[]).append(i)
    pairs, triples = [], []
    for i,a in enumerate(types):
        for j in byd.get(11-a['d'],[]):
            if j < i:
                continue
            b = types[j];w=a['w']+b['w'];h=a['h']+b['h']
            if w<=18 and h<=18:
                pairs.append(dict(f=max(a['f'],b['f']),type_ids=[i,j],width=w,height=h))
        for j in range(i,len(types)):
            b=types[j];w=a['w']+b['w'];h=a['h']+b['h']
            if w>=18 or h>=18:
                continue
            for k in byd.get(11-a['d']-b['d'],[]):
                if k<j:
                    continue
                c=types[k]
                if w+c['w']<=18 and h+c['h']<=18:
                    triples.append(dict(f=max(a['f'],b['f'],c['f']),type_ids=[i,j,k],
                        width=w+c['w'],height=h+c['h']))
    for rows in (pairs,triples):
        rows.sort(key=lambda r:(r['f'],r['type_ids']))
        for r in rows:
            r['optimistic_side']=18+r['f'];r['side_above_current']=18+r['f']-baseline
    diagnostics=[]
    for recipe in pairs[:3]:
        choices=[]
        for order in (recipe['type_ids'],recipe['type_ids'][::-1]):
            a,b=(types[i] for i in order)
            pa,pb=(poses[(t['w'],t['h'],t['d'])] for t in (a,b))
            for sx,sy,tx,ty in itertools.product((-1,1),repeat=4):
                aa=orient(pa,False,sx,sy);bb=orient(pb,False,tx,ty)
                bb[:,:2]+=[a['w'],-b['h']]
                edges,depths=overlap_edges(aa,bb)
                choices.append(dict(type_order=order,reflections=[sx,sy,tx,ty],
                    overlaps=len(edges),maximum_penetration=max(depths,default=0.),
                    squared_penetration=sum(d*d for d in depths),pairs=edges,depths=depths))
        choices.sort(key=lambda r:(r['squared_penetration'],r['maximum_penetration'],r['overlaps']))
        diagnostics.append(dict(recipe=recipe,source_pair_reflection_cases=len(choices),
            passing_nominal_cross_sat=sum(r['overlaps']==0 for r in choices),best=choices[0],
            scope='Binary64 all four SAT axes; counts gaps below-1e-8, no strict geometry certificate.'))
    history=[]
    for p in sorted((ROOT/'artifacts').glob('*scalar*/optimistic-round-*.json')):
        j=json.loads(p.read_text());rows=[r for r in j.get('proposals',[]) if r[1]['n']==335]
        history.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),n335_proposals=len(rows)))
    phase=ROOT/'artifacts/fractional-interface-v1/report.json'
    phase_report=json.loads(phase.read_text())
    report=dict(status='finite_scalar_and_nearest_seam_audit_complete',seconds=time.monotonic()-began,
        source_sha256=sha(__file__),pointer_sha256=sha(pointer_path),baseline_sha256=raw['sha256'],
        official_report_sha256=sha(raw['official_report']),current_n335_side=baseline,
        inputs=inputs,high_crop_descriptor_sha256=sha(descriptor),counts=counts,types=types,
        relevant_types=len(types),two_block_multisets=len(pairs),three_block_multisets=len(triples),
        improving_two_block_multisets=sum(r['side_above_current'] < -1e-8 for r in pairs),
        improving_three_block_multisets=sum(r['side_above_current'] < -1e-8 for r in triples),
        nearest_two_block=pairs[:20],nearest_three_block=triples[:20],nearest_seam_diagnostics=diagnostics,
        prior_scalar_rounds=history,prior_fractional_report_sha256=sha(phase),
        prior_n335_phase_models=sum(r.get('n')==335 for r in phase_report['records']),
        scope='Finite minimum-per-exact-nominal-type library, both orientations. All2/3-component multisets with surplus11 and summed integer width/height<=18; zero buffers give a lower bound for all public staircase buffer modes. No arbitrary interlocking/overlapping nominal boxes, new crops, rotations, or shape repair exhaustiveness claim.',
        new_optimizations=0,new_full_certifications=0,submission=False)
    atom(out/'report.json',report)
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    np.savez_compressed(out/'closest-source-poses.npz',**{'_'.join(map(str,k)):v for k,v in poses.items()
        if best[k] in [types[i]for r in pairs[:3]for i in r['type_ids']]})
    print(json.dumps({k:report[k]for k in ['seconds','relevant_types','two_block_multisets','three_block_multisets',
        'improving_two_block_multisets','improving_three_block_multisets','current_n335_side']}))
    for r in diagnostics:
        print(json.dumps(r))


if __name__=='__main__':
    main()
