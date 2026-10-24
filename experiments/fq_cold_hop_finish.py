"""Four fixed cold-state finishes per case, using the frozen full terminal gates.

Diversity is a coarse spatial/angle histogram diagnostic, not a topology proof.
Both native workers stay in the caller's bounded process group.
"""
from __future__ import annotations
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from decimal import Decimal
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import time
import numpy as np
import fq_restart_hop_finish as original

ORIGINAL_SHA = 'aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
DELTAS = (.002, .008)
NATIVE_SECONDS = 60.
CERTIFICATE_SECONDS = 8.


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def histogram_orbit(pose, side):
    """Eight fixed-box D4 occupancy×angle histograms; unit-row invariant."""
    pose = np.asarray(pose, dtype=np.float64)
    if pose.ndim != 2 or pose.shape[1] != 3 or not np.isfinite(pose).all() or not math.isfinite(side) or side <= 0:
        raise ValueError('invalid_histogram_pose')
    result = []
    for swap in (False, True):
        for sx, sy in ((1,1), (-1,1), (1,-1), (-1,-1)):
            xy = pose[:,:2]-side/2; angle = pose[:,2].copy()
            if swap:
                xy = xy[:,::-1]; angle = math.pi/2-angle
            xy = xy*np.array([sx,sy])+side/2; angle *= sx*sy
            # Rounding stabilizes diagnostic bin boundaries under float D4
            # compositions. It changes no retained coordinates or gate input.
            position = np.floor(np.round(xy/side*8, 12)).astype(np.int64).clip(0,7)
            angular = np.floor(np.round((np.mod(angle,math.pi/2)/(math.pi/2)*8+.5),12)).astype(np.int64)%8
            keys = (position[:,0]*8+position[:,1])*8+angular
            result.append(np.bincount(keys,minlength=512).astype(np.float64)/len(pose))
    return np.array(result)


def histogram_distance(first, second):
    """Minimum over both histogram orbits; invariant to D4 and row order."""
    return float(np.sqrt(np.square(first[:,None,:]-second[None,:,:]).sum(2).min()))


def select_slots(design, best, energy, sides):
    B = len(design)
    if sorted(r['chain'] for r in design) != list(range(B)) or len(energy) != B or len(best) != B:
        raise ValueError('cold_chain_inventory_mismatch')
    rows = {r['chain']:r for r in design}
    if any(r['arm'] != 'cold' or r['delta'] not in DELTAS for r in design):
        raise ValueError('unsupported_cold_arm_or_box')
    result = []
    for delta in DELTAS:
        indices = [i for i,r in rows.items() if r['delta'] == delta and math.isfinite(float(energy[i])) and float(energy[i]) >= 0]
        indices.sort(key=lambda i:(float(energy[i]),i))
        first = indices[0] if indices else None
        result.append(dict(slot=len(result),arm='cold',delta=delta,kind='lowest_best_energy',chain=first,
            status='selected' if first is not None else 'no_finite_state',design=rows[first] if first is not None else None))
        second = None; distance = None; threshold = None; eligible = []; fallback = False; duplicates = []
        if first is not None:
            threshold = max(4*float(energy[first]),float(energy[first])+1e-8)
            first_hash = original.geometry_sha(best[first])
            duplicates = [i for i in indices if i != first and original.geometry_sha(best[i]) == first_hash]
            alternatives = [i for i in indices if i != first and i not in duplicates]
            eligible = [i for i in alternatives if float(energy[i]) <= threshold]
            if eligible:
                reference = histogram_orbit(best[first],float(sides[first]))
                distances = {i:histogram_distance(reference,histogram_orbit(best[i],float(sides[i]))) for i in eligible}
                second = min(eligible,key=lambda i:(-distances[i],float(energy[i]),i)); distance = distances[second]
            elif alternatives:
                second = alternatives[0]; fallback = True
                distance = histogram_distance(histogram_orbit(best[first],float(sides[first])),histogram_orbit(best[second],float(sides[second])))
        result.append(dict(slot=len(result),arm='cold',delta=delta,kind='coarse_diverse_best',chain=second,
            status='selected' if second is not None else ('no_exactly_distinct_alternative' if duplicates else 'no_finite_alternative'),design=rows[second] if second is not None else None,
            near_best_energy_threshold=threshold,eligible_alternatives=eligible,histogram_distance=distance,
            exact_duplicate_alternatives_excluded=duplicates,positive_histogram_diversity=distance is not None and distance > 0,
            fallback_next_lowest_energy=fallback,diversity_claim='Positive coarse D4 spatial/angle histogram distance only; not topology or basin proof.' if distance is not None and distance > 0 else 'No positive coarse histogram diversity claimed.'))
    return result


def _configure_worker():
    if _sha(original.__file__) != ORIGINAL_SHA:
        raise ValueError('frozen_terminal_helper_changed')
    original.NATIVE_SECONDS = NATIVE_SECONDS
    original.CERTIFICATE_SECONDS = CERTIFICATE_SECONDS


def _finish_slot(payload):
    out, slot, pose, case, binary, deadline = payload
    # The exact selected chain's source identity remains visible even when
    # cold initializer labels differ within one puzzle.
    case = dict(case,source_key=slot['design']['source_key'])
    return original._finish_slot(Path(out),slot,pose,case,Path(binary),deadline)


def finish_case(root:Path,case_config:dict,deadline:float)->dict:
    root = Path(root).resolve(); out = root/'finish'; out.mkdir(exist_ok=False)
    if _sha(original.__file__) != ORIGINAL_SHA:
        raise ValueError('frozen_terminal_helper_changed')
    case = dict(case_config); n = int(case['n']); case['n'] = n
    reference = Decimal(str(case['reference_side']))
    if n not in (803,861) or not reference.is_finite() or reference <= 0 or not math.isfinite(deadline):
        raise ValueError('unsupported_case_reference_or_deadline')
    binary = Path(case['binary_path']); binary = binary if binary.is_absolute() else root/binary
    if _sha(binary) != original.BINARY_SHA:
        raise ValueError('native_binary_sha256_mismatch')
    design_path = root/'chain-design.json'; final_path = root/'final-current-best.npz'; index_path = root/'raw-index.json'
    design = json.loads(design_path.read_text()); index = json.loads(index_path.read_text())
    entries = [entry for entry in index['packets'] if entry['status'] == 'completed']
    if not entries:
        summary = dict(status='no_completed_packet',slots=[],certified=0,no_submission=True,no_canonical_mutation=True)
        original.atomic_json(out/'summary.json',summary); return summary
    origin = entries[-1]; packet = Path(origin['path']); packet = packet if packet.is_absolute() else root/packet
    if _sha(packet) != origin['sha256'] or ('bytes' in origin and packet.stat().st_size != origin['bytes']):
        raise ValueError('last_completed_packet_identity_mismatch')
    with np.load(final_path,allow_pickle=False) as final,np.load(packet,allow_pickle=False) as previous:
        arrays = {name:final[name].copy() for name in original.STATE_KEYS}
        if any(not np.array_equal(arrays[name],previous[name]) for name in original.STATE_KEYS):
            raise ValueError('recovered_final_differs_from_committed_packet')
        metadata = json.loads(previous['metadata_json'].tobytes())
        if metadata['status'] != 'completed' or metadata['design'] != design:
            raise ValueError('committed_design_mismatch')
        for name in original.STATE_KEYS:
            if hashlib.sha256(previous[name].tobytes()).hexdigest() != metadata['array_sha256'][name]:
                raise ValueError('committed_array_hash_mismatch')
    B = len(design)
    if B != 32 or any(r['n'] != n or r['source_key'] != case['source_key'] for r in design):
        raise ValueError('cold_case_or_source_design_mismatch')
    if any(float(r['side']) != float(reference)-float(r['delta']) for r in design):
        raise ValueError('cold_reference_minus_delta_box_mismatch')
    if any(arrays[name].shape != (B,n,3) or not np.isfinite(arrays[name]).all() for name in ('best_after','current_after')):
        raise ValueError('invalid_full_count_state_arrays')
    if any(arrays[name].shape != (B,) for name in ('sides','next_energy','best_energy_after')):
        raise ValueError('invalid_scalar_state_arrays')
    if any(float(arrays['sides'][r['chain']]) != float(r['side']) for r in design):
        raise ValueError('committed_fixed_box_mismatch')
    if any(sum(r['delta'] == delta for r in design) != 16 for delta in DELTAS):
        raise ValueError('cold_box_chain_counts_mismatch')
    slots = select_slots(design,arrays['best_after'],arrays['best_energy_after'],arrays['sides'])
    for slot in slots:
        if slot['chain'] is None:
            continue
        i = slot['chain']; pose = arrays['best_after'][i]
        slot.update(committed_best_energy=float(arrays['best_energy_after'][i]),current_energy_not_selected=float(arrays['next_energy'][i]),
            fixed_box=float(arrays['sides'][i]),selected_geometry_sha256=original.geometry_sha(pose),last_completed_packet_sha256=origin['sha256'])
        path = out/f"slot-{slot['slot']:02d}-selected.npz"
        original.atomic_npz(path,{'pose':pose}); path.chmod(0o444)
        slot['selected_before_submission'] = dict(path=str(path),sha256=_sha(path))
    manifest = dict(case_config=case,deadline_monotonic=deadline,workers=2,max_slots=4,native_seconds_cap=60,certificate_seconds_cap=8,
        options=original.OPTIONS,seed_policy='Same native seed for best/diverse states at a given delta; no adaptive crosscase allocation.',
        fixed_slots=slots,final_archive_sha256=_sha(final_path),design_sha256=_sha(design_path),index_sha256=_sha(index_path),
        last_completed_packet=dict(origin,resolved_path=str(packet)),frozen_terminal_helper_sha256=ORIGINAL_SHA,
        source_sha256=_sha(__file__),binary_sha256=original.BINARY_SHA,
        helper_hashes={str(path):_sha(path) for path in [Path(original.__file__),Path(original.fq.__file__),
            original.ROOT/'experiments/fq_capacity_probe.py',original.ROOT/'experiments/fq_variant_campaign.py',
            original.ROOT/'experiments/compose_gadgets.py',original.ROOT/'scripts/score_official.py',
            original.ROOT/'scripts/validate_submission.py',original.ROOT/'research/official_metric_v17.py']},
        selection='Perbox minimumBESTenergy plus nearbest-band maximum coarse D4 histogram distance; explicit nextlowest fallback. No topology claim.',
        input_status='UNVERIFIED exact committed BEST arrays; physical energy is not feasibility.')
    original.atomic_json(out/'manifest.json',manifest); records = {}; certified = {}; pending = {}; cursor = 0
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork'),initializer=_configure_worker) as pool:
        while cursor < len(slots) or pending:
            while len(pending) < 2 and cursor < len(slots):
                slot = slots[cursor]; cursor += 1
                if slot['chain'] is None:
                    records[slot['slot']] = dict(slot); continue
                if deadline-time.monotonic() < .2:
                    records[slot['slot']] = dict(slot,status='deadline_before_native'); continue
                payload = (str(out),slot,arrays['best_after'][slot['chain']].copy(),case,str(binary),deadline)
                pending[pool.submit(_finish_slot,payload)] = slot
            if not pending:
                continue
            done,_ = wait(pending,timeout=.2,return_when=FIRST_COMPLETED)
            for future in done:
                slot = pending.pop(future)
                try:
                    record,q = future.result()
                except Exception as error:
                    # One native/IO failure must not discard unrelated fixed
                    # slots. Exact selected bytes already precede submission.
                    record = dict(slot,status='finish_error',error_type=type(error).__name__,
                        preserved_artifacts={str(path):_sha(path) for path in out.glob(f"slot-{slot['slot']:02d}-*") if path.is_file()})
                    q = None
                records[slot['slot']] = record
                if q is not None:
                    certified[f"n{n}_{slot['kind']}_delta{slot['delta']}_chain{slot['chain']}"] = q
                original.atomic_json(out/'results.json',[records[i] for i in sorted(records)])
    ordered = [records[i] for i in sorted(records)]; original.atomic_json(out/'results.json',ordered)
    original.atomic_npz(out/'certified.npz',certified)
    rows = [r for r in ordered if r.get('status') == 'certified']; lengths = [Decimal(r['worst_certified_side']) for r in rows]
    summary = dict(status='complete' if all(r.get('status') != 'deadline_before_native' for r in ordered) else 'deadline_partial',
        n=n,slots=ordered,workers=2,certified=len(certified),reference_side=str(reference),
        best_side=str(min(lengths)) if lengths else None,worst_side=str(max(lengths)) if lengths else None,
        strict_improvements=sum(r['strict_improvement'] for r in rows),manifest_sha256=_sha(out/'manifest.json'),
        results_sha256=_sha(out/'results.json'),certified_archive_sha256=_sha(out/'certified.npz'),
        no_submission=True,no_canonical_mutation=True)
    original.atomic_json(out/'summary.json',summary)
    for path in out.iterdir():
        if path.is_file():
            path.chmod(0o444)
    return summary
