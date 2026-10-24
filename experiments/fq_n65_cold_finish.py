"""Eight fixed source-group-stratified n65 BEST finishes, full existing gates."""
from __future__ import annotations
import hashlib
import inspect
import math
from pathlib import Path
import numpy as np
import fq_cold_hop_finish as cold
import fq_restart_hop_finish as original

COLD_SHA='17f0fdf314fbe652f193e76b4101c1e14e688a0632642bd7b180f695959aafb9'
ORIGINAL_SHA='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
DELTAS=(.0005,.002)
GROUP_BINS=((0,1,2,3),(4,5,6,7),(8,9,10,11),(12,13,14,15))
NATIVE_SECONDS=60.
CERTIFICATE_SECONDS=8.


def select_slots(design,best,energy,sides):
    """Four bins at each box; second cut must use different source groups.

    Energy ranks only chains with the same target box. The source groups are
    the frozen geometric-cover groups, not a claim about final optimizer basins.
    """
    if len(design)!=32 or sorted(r['chain'] for r in design)!=list(range(32)):
        raise ValueError('n65_chain_inventory_mismatch')
    if np.shape(best)!=(32,65,3) or np.shape(energy)!=(32,) or np.shape(sides)!=(32,):
        raise ValueError('n65_state_shape_mismatch')
    rows={r['chain']:r for r in design}
    expected={(delta,group) for delta in DELTAS for group in range(16)}
    if {(r['delta'],r['source_group']) for r in design}!=expected or any(r['arm']!='cold' for r in design):
        raise ValueError('n65_group_box_design_mismatch')
    slots=[];selected_groups=set()
    for delta in DELTAS:
        for group_bin in GROUP_BINS:
            eligible=[i for i,r in rows.items() if r['delta']==delta and r['source_group'] in group_bin
                and r['source_group'] not in selected_groups and math.isfinite(float(energy[i])) and energy[i]>=0]
            chosen=min(eligible,key=lambda i:(float(energy[i]),i)) if eligible else None
            if chosen is not None:selected_groups.add(rows[chosen]['source_group'])
            slots.append(dict(slot=len(slots),arm='cold',delta=delta,kind='source_group_stratum_best',
                source_group_bin=list(group_bin),chain=chosen,status='selected' if chosen is not None else 'no_finite_unused_source_group',
                design=rows[chosen] if chosen is not None else None,
                selection_scope='Lowest BEST physical energy within this fixed box and source-group stratum; second box excludes already-selected groups.'))
    return slots


def _configure_worker():
    if cold._sha(original.__file__)!=ORIGINAL_SHA:raise ValueError('frozen_terminal_helper_changed')
    original.NATIVE_SECONDS=NATIVE_SECONDS;original.CERTIFICATE_SECONDS=CERTIFICATE_SECONDS
    # The numerical function is unchanged; the two new box labels select the
    # same two matched native seeds9710000/9710001 as the original helper.
    original.DELTAS=DELTAS


def generated_finish_source():
    if cold._sha(cold.__file__)!=COLD_SHA:raise ValueError('frozen_cold_finish_changed')
    source=inspect.getsource(cold.finish_case)
    changes=[
        ('n not in (803,861)','n != 65'),
        ("any(r['n'] != n or r['source_key'] != case['source_key'] for r in design)",
         "any(r['n'] != n or r['source_group'] not in range(16) or r['source_key'] != case['source_keys'][r['source_group']] for r in design)"),
        ('workers=2,max_slots=4','workers=4,max_slots=8'),
        ('with ProcessPoolExecutor(max_workers=2','with ProcessPoolExecutor(max_workers=4'),
        ('while len(pending) < 2','while len(pending) < 4'),
        ('n=n,slots=ordered,workers=2','n=n,slots=ordered,workers=4'),
        ('Same native seed for best/diverse states at a given delta; no adaptive crosscase allocation.',
         'Same native seed for all four fixed group strata at each delta;9710000/9710001. Four workers, no adaptive allocation.'),
        ('Perbox minimumBESTenergy plus nearbest-band maximum coarse D4 histogram distance; explicit nextlowest fallback. No topology claim.',
         'Eight predeclared source-group strata: four group bins per target box, no source-group reuse across the two boxes. Energies never rank across target boxes. No final basin claim.'),
    ]
    for before,after in changes:
        if source.count(before)!=1:raise ValueError('ambiguous_finish_adapter:'+before)
        source=source.replace(before,after,1)
    return source


def finish_case(root:Path,case_config:dict,deadline:float)->dict:
    namespace=dict(vars(cold))
    namespace.update(__file__=__file__,DELTAS=DELTAS,select_slots=select_slots,
        _configure_worker=_configure_worker,NATIVE_SECONDS=NATIVE_SECONDS,CERTIFICATE_SECONDS=CERTIFICATE_SECONDS)
    source=generated_finish_source()
    exec(compile(source,'<n65 eight fixed group-stratified finishes>','exec'),namespace)
    return namespace['finish_case'](root,case_config,deadline)
