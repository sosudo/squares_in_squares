"""Finish only explicit full-lambda1 births using the unchanged native gate."""
from __future__ import annotations
import hashlib,json,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import numpy as np
import fq_restart_hop_finish as original
ORIGINAL_SHA='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'

def _trial(payload):
    out,slot,p,case,binary,deadline=payload
    assert hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()==ORIGINAL_SHA
    assert hashlib.sha256(Path(binary).read_bytes()).hexdigest()==original.BINARY_SHA
    original.NATIVE_SECONDS=60.;original.CERTIFICATE_SECONDS=8.
    return original._finish_slot(Path(out),slot,p,case,Path(binary),deadline)

def finish(out,full_states,full_energy,design,case,binary,deadline):
    out.mkdir(exist_ok=False);groups=sorted({r['group']for r in design});assert len(groups)==4
    assert len(full_states)==len(full_energy)and all(a.shape==(32,case['n'],3)for a in full_states)
    selected=[];seen=set()
    for group in groups:
        options=[]
        for cycle,(poses,energy)in enumerate(zip(full_states,full_energy)):
            for row in design:
                i=row['chain'];p=poses[i]
                if row['group']!=group or not np.isfinite(energy[i])or not np.isfinite(p).all():continue
                digest=hashlib.sha256(p.tobytes()).hexdigest()
                if digest not in seen:options.append((float(energy[i]),cycle,i,digest))
        if not options:continue
        energy,cycle,i,digest=min(options);seen.add(digest)
        slot=dict(slot=len(selected),arm='birth',delta=.002,chain=i,group=group,
            source_cycle=cycle,physical_energy_at_lambda1=energy,explicit_birth_size=1.,
            full_lambda1_geometry_sha256=digest,source_design=design[i])
        selected.append((slot,full_states[cycle][i].copy()))
    original.atomic_json(out/'selection.json',[r for r,p in selected])
    records=[];certified={}
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork'))as pool:
        futures=[pool.submit(_trial,(str(out),slot,p,dict(case,source_key=slot['group']),str(binary),deadline))for slot,p in selected]
        for future in futures:
            record,q=future.result();records.append(record)
            if q is not None:certified[f"birth_{case['n']}_slot{record['slot']}"]=q
            original.atomic_json(out/'results.json',records);original.atomic_npz(out/'certified.npz',certified)
    summary=dict(slots=len(selected),certified=len(certified),workers=2,native_seconds=60,gate_seconds=8,
        strict_winners=[r['slot']for r in records if r.get('strict_improvement')],
        selection='One lowest fresh full-lambda1 physical energy per fixed source/box stratum; no cross-size ranking.',
        comparison_scope='Frozen current reference only; parent must compare actual transported sides against latest canonical before admission.',
        no_submission=True,no_canonical_mutation=True)
    original.atomic_json(out/'summary.json',summary);return summary
