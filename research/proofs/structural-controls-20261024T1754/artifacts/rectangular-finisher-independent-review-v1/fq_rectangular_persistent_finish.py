"""Bounded fixed-slot native finishes and conservative rectangular donor proofs.

Low-energy GPU states are UNVERIFIED. Full unit-square certificates are retained
even when a subsequent rectangular enclosure proof fails or exhausts its budget.
"""
from __future__ import annotations
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import csv
from decimal import Decimal, localcontext, ROUND_FLOOR
import hashlib
import io
import json
import math
import multiprocessing as mp
from pathlib import Path
import signal
import time

import numpy as np
import pandas as pd
import fq_restart_hop_finish as terminal
import validate_submission as validator

TERMINAL_SHA = 'aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
CUTS = (.002, .01, .03, .06)
STATE_KEYS = ('current_after', 'best_after', 'boxes', 'next_energy', 'best_energy_after')
NATIVE_SECONDS = 60.
CERTIFICATE_SECONDS = 8.
NATIVE_SEED = 9710000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_helper():
    if sha(terminal.__file__) != TERMINAL_SHA:
        raise ValueError('frozen_terminal_helper_changed')


def rectangular_certificate(pose, w, h):
    """Outward interval spans of the same three exact decimal transports.

This is an enclosure proof, not a replacement for full unit-square nonoverlap
certification. The caller must retain/pass the unchanged full certificate too.
    """
    p = np.asarray(pose, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all() or w <= 0 or h <= 0:
        raise ValueError('invalid_rectangle_geometry')
    rows = [dict(n=str(len(p)), square_id=str(i), x=f'{x:.17g}', y=f'{y:.17g}', angle=f'{a:.17g}')
            for i, (x, y, a) in enumerate(p)]
    raw_text = pd.DataFrame(rows).to_csv(index=False)
    numeric = pd.read_csv(io.StringIO(raw_text))
    variants = dict(raw=raw_text, pandas_17g=numeric.to_csv(index=False, float_format='%.17g'),
                    pandas_default=numeric.to_csv(index=False))
    previous_dps = (validator.mp.mp.dps, validator.mp.iv.dps)
    reports = {}
    try:
        for name, text in variants.items():
            rr = list(csv.DictReader(io.StringIO(text)))
            if len(rr) != len(p) or any(int(r['n']) != len(p) or int(r['square_id']) != i for i, r in enumerate(rr)):
                raise ValueError('rectangle_transport_count_mismatch')
            squares = [validator.Square(*(validator.decimal(r[k]) for k in ('x', 'y', 'angle'))) for r in rr]
            geom = validator._geometry(squares, 80)
            left = validator._iv_min([x-e for x,y,c,s,e in geom])
            right = validator._iv_max([x+e for x,y,c,s,e in geom])
            bottom = validator._iv_min([y-e for x,y,c,s,e in geom])
            top = validator._iv_max([y+e for x,y,c,s,e in geom])
            width, height = right-left, top-bottom
            excess = validator._iv_max([width-w, height-h])
            record = dict(csv_sha256=hashlib.sha256(text.encode()).hexdigest(), n=len(p),
                          width_lower=validator._endpoint_text(width.a, False),
                          width_upper=validator._endpoint_text(width.b, True),
                          height_lower=validator._endpoint_text(height.a, False),
                          height_upper=validator._endpoint_text(height.b, True),
                          f_lower=validator._endpoint_text(excess.a, False),
                          f_upper=validator._endpoint_text(excess.b, True))
            if any(not Decimal(record[k]).is_finite() for k in ('width_lower','width_upper','height_lower','height_upper','f_lower','f_upper')):
                raise ValueError('nonfinite_rectangle_bound')
            if min(Decimal(record['width_lower']), Decimal(record['height_lower'])) <= 0:
                raise ValueError('nonpositive_rectangle_span')
            reports[name] = record
    finally:
        validator.mp.mp.dps, validator.mp.iv.dps = previous_dps
    upper = max(Decimal(r['f_upper']) for r in reports.values())
    lower = min(Decimal(r['f_lower']) for r in reports.values())
    return dict(valid=True, w=w, h=h, n=len(p), transports=reports,
                f_lower=str(lower), f_upper=str(upper), fits_subunit_excess=upper < 1,
                meaning='Translation-invariant unit-square spans; pair nonoverlap requires the separate full certificate.')


def histogram_orbit(pose, box):
    """D2 reflections preserve the ordered rectangle; no 90-degree swapping."""
    p = np.asarray(pose, dtype=np.float64); box = np.asarray(box, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3 or box.shape != (2,) or not np.isfinite(p).all() or not np.isfinite(box).all() or np.min(box) <= 0:
        raise ValueError('invalid_rectangle_histogram_input')
    result = []
    for sx, sy in ((1,1), (-1,1), (1,-1), (-1,-1)):
        xy = (p[:,:2]-box/2)*[sx,sy]+box/2
        angle = p[:,2]*(sx*sy)
        position = np.floor(np.round(xy/box*8,12)).astype(np.int64).clip(0,7)
        angular = np.floor(np.round(np.mod(angle,math.pi/2)/(math.pi/2)*8+.5,12)).astype(np.int64)%8
        key = (position[:,0]*8+position[:,1])*8+angular
        result.append(np.bincount(key,minlength=512).astype(np.float64)/len(p))
    return np.asarray(result)


def histogram_distance(a, b):
    return float(np.sqrt(np.square(a[:,None,:]-b[None,:,:]).sum(2).min()))


def select_slots(design, best, energy, boxes):
    if len(design) != 64 or sorted(r['chain'] for r in design) != list(range(64)):
        raise ValueError('rectangular_chain_inventory_mismatch')
    rows = {r['chain']:r for r in design}
    if any(r['arm'] != 'rectangular' or r['delta'] not in CUTS for r in design):
        raise ValueError('unsupported_rectangle_arm_or_cut')
    slots = []
    for delta in CUTS:
        group = [i for i,r in rows.items() if r['delta']==delta]
        if len(group) != 16:
            raise ValueError('rectangle_requires_sixteen_chains_per_cut')
        indices = sorted((i for i in group if math.isfinite(float(energy[i])) and float(energy[i]) >= 0),
                         key=lambda i:(float(energy[i]),i))
        first = indices[0] if indices else None
        slots.append(dict(slot=len(slots),delta=delta,kind='lowest_best_energy',chain=first,
                          status='selected' if first is not None else 'no_finite_state'))
        second = None; distance = None; threshold = None; duplicates=[]; eligible=[]; fallback=False
        if first is not None:
            first_hash = terminal.geometry_sha(best[first])
            duplicates = [i for i in indices if i != first and terminal.geometry_sha(best[i])==first_hash]
            alternatives = [i for i in indices if i != first and i not in duplicates]
            threshold = max(4*float(energy[first]),float(energy[first])+1e-8)
            eligible = [i for i in alternatives if float(energy[i]) <= threshold]
            if eligible:
                reference = histogram_orbit(best[first],boxes[first])
                distances = {i:histogram_distance(reference,histogram_orbit(best[i],boxes[i])) for i in eligible}
                second = min(eligible,key=lambda i:(-distances[i],float(energy[i]),i));distance=distances[second]
            elif alternatives:
                second=alternatives[0];fallback=True
                distance=histogram_distance(histogram_orbit(best[first],boxes[first]),histogram_orbit(best[second],boxes[second]))
        slots.append(dict(slot=len(slots),delta=delta,kind='coarse_diverse_best',chain=second,
                          status='selected' if second is not None else 'no_exactly_distinct_finite_alternative',
                          near_best_energy_threshold=threshold,eligible_alternatives=eligible,
                          exact_duplicate_alternatives_excluded=duplicates,histogram_distance=distance,
                          positive_histogram_diversity=distance is not None and distance>0,
                          fallback_next_lowest_energy=fallback,
                          diversity_claim='Coarse D2 occupancy/angle diversity only, not topology.'))
    for slot in slots:
        if slot['chain'] is not None:slot['design']=rows[slot['chain']]
    return slots


def _contained(root, value):
    path=Path(value)
    if path.is_absolute():raise ValueError('state_origin_must_be_relative')
    resolved=(root/path).resolve()
    if not resolved.is_relative_to(root):raise ValueError('state_origin_outside_family')
    return resolved


def load_committed(root, case):
    root=Path(root).resolve()
    recovery_path=root/'recovery.json';design_path=root/'chain-design.json';config_path=root/'family-config.json'
    recovery=json.loads(recovery_path.read_text());design=json.loads(design_path.read_text())
    if not recovery['completed'] or recovery['status'] not in ('complete','recovered_head'):
        raise ValueError('no_committed_rectangle_state')
    if sha(design_path)!=recovery['design_sha256'] or sha(config_path)!=recovery['family_config_sha256']:
        raise ValueError('rectangle_design_or_config_changed')
    stored_case=json.loads(config_path.read_text())
    for key in ('key','w','h','d','n','reference_f_lower','reference_f_upper','seed_keys','batch_size'):
        if case[key]!=stored_case[key]:raise ValueError('supplied_family_config_mismatch:'+key)
    origin=recovery['state_origin']
    if origin['kind'] not in ('sampled_terminal_packet','durable_head'):
        raise ValueError('unsupported_state_origin')
    packet=_contained(root,origin['path']);final=_contained(root,recovery['final_archive'])
    if sha(packet)!=origin['sha256'] or sha(final)!=recovery['final_archive_sha256']:
        raise ValueError('recovered_rectangle_archive_changed')
    with np.load(packet,allow_pickle=False)as z,np.load(final,allow_pickle=False)as f:
        metadata=json.loads(z['metadata_json'].tobytes())
        if metadata['round']!=origin['round'] or metadata['design_sha256']!=recovery['design_sha256'] or metadata['family_config_sha256']!=recovery['family_config_sha256']:
            raise ValueError('committed_rectangle_metadata_mismatch')
        members=set(z.files)-{'metadata_json'}
        if set(metadata['array_sha256'])!=members or set(origin['array_sha256'])!=members:
            raise ValueError('committed_rectangle_member_inventory_mismatch')
        for name in members:
            digest=hashlib.sha256(z[name].tobytes()).hexdigest()
            if digest!=metadata['array_sha256'][name] or digest!=origin['array_sha256'][name]:
                raise ValueError('committed_rectangle_member_changed')
        arrays={name:f[name].copy()for name in STATE_KEYS}
        if any(arrays[name].dtype!=z[name].dtype or arrays[name].shape!=z[name].shape or arrays[name].tobytes()!=z[name].tobytes() for name in STATE_KEYS):
            raise ValueError('final_rectangle_state_not_exact_committed_state')
    B=case['batch_size'];n=case['n']
    if B!=64 or n!=case['w']*case['h']+case['d'] or len(design)!=B or len(case['seed_keys'])!=4:
        raise ValueError('invalid_family_count_or_seed_inventory')
    if any(arrays[name].shape!=(B,n,3) or arrays[name].dtype!=np.float64 or not np.isfinite(arrays[name]).all() for name in ('best_after','current_after')):
        raise ValueError('invalid_rectangle_full_unit_arrays')
    if arrays['boxes'].shape!=(B,2) or not np.isfinite(arrays['boxes']).all() or np.min(arrays['boxes'])<=0:
        raise ValueError('invalid_rectangle_boxes')
    if any(arrays[name].shape!=(B,) or not np.isfinite(arrays[name]).all() or np.min(arrays[name])<0 for name in ('next_energy','best_energy_after')):
        raise ValueError('invalid_rectangle_energies')
    for row in design:
        i=row['chain'];group=row['seed_group']
        if not 0<=i<B or not isinstance(group,int) or not 0<=group<4 or row['source_key']!=case['seed_keys'][group]:
            raise ValueError('rectangle_chain_source_binding_mismatch')
        if row['target_f']!=float(case['reference_f_upper'])-row['delta']:
            raise ValueError('rectangle_target_not_incumbent_minus_cut')
        if row['width']!=case['w']+row['target_f'] or row['height']!=case['h']+row['target_f']:
            raise ValueError('rectangle_width_height_excess_mismatch')
        if not np.array_equal(arrays['boxes'][i],np.asarray([row['width'],row['height']],dtype=np.float64)):
            raise ValueError('rectangle_fixed_box_mismatch')
    return arrays,design,dict(recovery_sha256=sha(recovery_path),state_origin=origin,
                             final_archive_sha256=sha(final),design_sha256=sha(design_path),
                             family_config_sha256=sha(config_path),retention_scope='Exact selected committed state; no assertion that every transition was archived.')


def _finish_slot(payload):
    out,slot,pose,case,binary,deadline=payload
    out=Path(out);binary=Path(binary);check_helper()
    base=out/f"slot-{slot['slot']:02d}-{slot['kind']}"
    n=case['n'];w=case['w'];h=case['h']
    record=dict(slot,n=n,family_key=case['key'],w=w,h=h,d=case['d'],
                reference_f_lower=str(case['reference_f_lower']),reference_f_upper=str(case['reference_f_upper']),
                source_key=slot['design']['source_key'],selected_geometry_sha256=terminal.geometry_sha(pose),
                input_status='UNVERIFIED exact committed BEST',native_seconds_cap=60,certificate_seconds_cap=8)
    terminal.atomic_json(base.with_suffix('.record.json'),record)
    if deadline-time.monotonic()<.2:return dict(record,status='deadline_before_native'),None
    encoded,offsets=terminal.fq.encode(pose,w,h)
    if offsets!=[w-min(w,h),h-min(w,h)]:raise ValueError('incorrect_native_rectangle_offsets')
    base.with_suffix('.in').write_text(encoded)
    header=encoded.splitlines()[0].split();small=float(header[1])
    command=[str(binary),'quench','--in',str(base.with_suffix('.in')),'--out',str(base.with_suffix('.out')),
             '--rect-dx',str(offsets[0]),'--rect-dy',str(offsets[1]),'--seed',str(NATIVE_SEED),*terminal.OPTIONS]
    record.update(command=command,input_sha256=sha(base.with_suffix('.in')),native_offsets=offsets,
                  encoded_box=[small+offsets[0],small+offsets[1]],
                  encoding_note='Translation-only normalization; physical input enclosure may exceed the GPU target rectangle.',
                  command_sha256=hashlib.sha256(json.dumps(command,separators=(',',':')).encode()).hexdigest())
    begin=time.monotonic();allowance=min(NATIVE_SECONDS,max(.001,deadline-begin-min(8.,max(0.,deadline-begin-.2))))
    record['effective_native_seconds_cap']=allowance
    try:record.update(terminal._recorded_native(command,base,allowance))
    finally:
        record['native_seconds']=time.monotonic()-begin
        for suffix in ('stdout','stderr'):
            path=base.with_suffix('.'+suffix)
            if path.exists():record[suffix+'_sha256']=sha(path)
        terminal.atomic_json(base.with_suffix('.record.json'),record)
    native=base.with_suffix('.out')
    if not native.exists():return dict(record,status='no_native_output'),None
    record.update(native_output_path=str(native),native_output_sha256=sha(native))
    try:
        raw=terminal._pose_from_output(native,n)
        returned_header=native.read_text().splitlines()[0].split();returned_s=float(returned_header[1])
        if not math.isfinite(returned_s) or returned_s<=0:raise ValueError('invalid_native_box')
    except (ValueError,IndexError):return dict(record,status='malformed_native_output'),None
    raw_path=base.with_suffix('.raw.npz');terminal.atomic_npz(raw_path,{'pose':raw});raw_path.chmod(0o444)
    record.update(status='saved_native_before_certificate',returned_native_box=[returned_s+offsets[0],returned_s+offsets[1]],
                  raw_returned=dict(path=str(raw_path),sha256=sha(raw_path),geometry_sha256=terminal.geometry_sha(raw),verified=False))
    terminal.atomic_json(base.with_suffix('.record.json'),record)
    remaining=deadline-time.monotonic()
    if remaining<.2:return dict(record,status='saved_return_certificate_budget_exhausted'),None
    old_handler=signal.signal(signal.SIGALRM,terminal._alarm);old_timer=signal.getitimer(signal.ITIMER_REAL)
    begin=time.monotonic();signal.setitimer(signal.ITIMER_REAL,min(CERTIFICATE_SECONDS,remaining,old_timer[0] if old_timer[0]>0 else math.inf))
    certified=None
    try:
        q=terminal.fq.decode(native,n)
        if q is None or q.shape!=(n,3) or not np.isfinite(q).all():return dict(record,status='failed_bounded_clearance'),None
        decoded=base.with_suffix('.decoded.npz');terminal.atomic_npz(decoded,{'pose':q});decoded.chmod(0o444)
        record['decoded_returned']=dict(path=str(decoded),sha256=sha(decoded),geometry_sha256=terminal.geometry_sha(q))
        cert=terminal.full_certificate(q);record['certificate']=cert
        if not cert['valid']:return dict(record,status='failed_full_gates'),None
        if cert['independent_raw']['n']!=n or cert['independent_roundtrip']['n']!=n:raise ValueError('certificate_count_mismatch')
        # Mark validity before any subsequent publication/proof can time out.
        # The timer-free finally block completes this small durable write.
        certified=q
        worst,sides=terminal.worst_certificate_side(cert)
        target=base.with_suffix('.certified.npz');terminal.atomic_npz(target,{'pose':q});target.chmod(0o444)
        record.update(status='certified_rectangle_pending',geometry_sha256=terminal.geometry_sha(q),
                      worst_certified_square_side=worst,certified_square_sides=sides,
                      certified_archive=str(target),certified_archive_sha256=sha(target),
                      strict_component_improvement=False,usable_rectangular_donor=False)
        terminal.atomic_json(base.with_suffix('.certificate.json'),record)
        rect=rectangular_certificate(q,w,h);record['rectangular_certificate']=rect
        upper=Decimal(rect['f_upper']);reference=Decimal(str(case['reference_f_lower']))
        with localcontext()as context:
            context.prec=160;context.rounding=ROUND_FLOOR
            gain_lower=reference-upper
        record.update(status='certified',f_upper=str(upper),f_lower=rect['f_lower'],
                      component_f_gain_lower=str(gain_lower),strict_component_improvement=upper<reference,
                      usable_rectangular_donor=bool(rect['valid'] and rect['fits_subunit_excess']),
                      no_full_portfolio_gain_claim=True)
        terminal.atomic_json(base.with_suffix('.certificate.json'),record)
        return record,certified
    except terminal.CertificateDeadline:
        record['status']='certified_rectangle_timeout' if certified is not None else 'saved_return_certificate_timeout'
        return record,certified
    except Exception as error:
        record.update(status='certified_rectangle_error' if certified is not None else 'saved_return_certificate_error',error_type=type(error).__name__)
        return record,certified
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old_handler)
        if old_timer[0]>0:signal.setitimer(signal.ITIMER_REAL,max(.001,old_timer[0]-(time.monotonic()-begin)),old_timer[1])
        terminal.atomic_json(base.with_suffix('.record.json'),record)
        if certified is not None:
            target=base.with_suffix('.certified.npz')
            if not target.exists():terminal.atomic_npz(target,{'pose':certified});target.chmod(0o444)
            record.update(geometry_sha256=terminal.geometry_sha(certified),certified_archive=str(target),certified_archive_sha256=sha(target))
            record.setdefault('strict_component_improvement',False);record.setdefault('usable_rectangular_donor',False)
            terminal.atomic_json(base.with_suffix('.record.json'),record)
            terminal.atomic_json(base.with_suffix('.certificate.json'),record)


def finish_family(root:Path,family_config:dict,deadline:float)->dict:
    """Eight immutable BEST slots, two workers; caller owns the outer group cap."""
    check_helper();root=Path(root).resolve();case=dict(family_config)
    for key in ('w','h','d','n','batch_size'):
        if not isinstance(case[key],int):raise ValueError('noninteger_family_parameter')
    if case['w']<=0 or case['h']<=0 or case['n']<=0 or case['key']!=f"{case['w']}_{case['h']}_{case['d']}":
        raise ValueError('invalid_family_key_or_dimensions')
    lower=Decimal(str(case['reference_f_lower']));upper=Decimal(str(case['reference_f_upper']))
    if not lower.is_finite() or not upper.is_finite() or lower>upper or not math.isfinite(deadline):
        raise ValueError('invalid_reference_excess_or_deadline')
    binary=Path(case['binary_path']);binary=binary if binary.is_absolute()else root/binary
    if sha(binary)!=terminal.BINARY_SHA:raise ValueError('native_binary_sha256_mismatch')
    binary.chmod(binary.stat().st_mode|0o100)
    arrays,design,bindings=load_committed(root,case)
    slots=select_slots(design,arrays['best_after'],arrays['best_energy_after'],arrays['boxes'])
    out=root/'finish';out.mkdir(exist_ok=False)
    for slot in slots:
        if slot['chain'] is None:continue
        i=slot['chain'];pose=arrays['best_after'][i]
        path=out/f"slot-{slot['slot']:02d}-selected.npz";terminal.atomic_npz(path,{'pose':pose});path.chmod(0o444)
        slot.update(committed_best_energy=float(arrays['best_energy_after'][i]),
                    current_energy_not_selected=float(arrays['next_energy'][i]),fixed_gpu_box=arrays['boxes'][i].tolist(),
                    selected_geometry_sha256=terminal.geometry_sha(pose),
                    selected_before_submission=dict(path=str(path),sha256=sha(path)))
    manifest=dict(family_config=case,deadline_monotonic=deadline,source_sha256=sha(__file__),
                  terminal_helper_sha256=TERMINAL_SHA,binary_sha256=terminal.BINARY_SHA,native_source_commit=terminal.fq.SOURCE_COMMIT,
                  options=terminal.OPTIONS,native_seed=NATIVE_SEED,workers=2,max_slots=8,native_seconds_cap=60,certificate_seconds_cap=8,
                  fixed_slots=slots,bindings=bindings,selection='Per-cut minBEST plus near-best-band coarse D2 diverse BEST; exact duplicates excluded; fixed slots never reallocated.',
                  helper_hashes={str(path):sha(path)for path in (Path(terminal.__file__),Path(terminal.fq.__file__),
                    terminal.ROOT/'experiments/fq_capacity_probe.py',terminal.ROOT/'experiments/compose_gadgets.py',
                    terminal.ROOT/'scripts/score_official.py',Path(validator.__file__),terminal.ROOT/'research/official_metric_v17.py')},
                  gain_scope='Component excess only; full portfolio improvement requires separate exact composition.')
    terminal.atomic_json(out/'manifest.json',manifest)
    records={};certified={};donors={};pending={};cursor=0
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork'),initializer=check_helper)as pool:
        while cursor<len(slots)or pending:
            while len(pending)<2 and cursor<len(slots):
                slot=slots[cursor];cursor+=1
                if slot['chain'] is None:records[slot['slot']]=dict(slot);continue
                if deadline-time.monotonic()<.2:records[slot['slot']]=dict(slot,status='deadline_before_native');continue
                payload=(str(out),slot,arrays['best_after'][slot['chain']].copy(),case,str(binary),deadline)
                pending[pool.submit(_finish_slot,payload)]=slot
            if not pending:continue
            done,_=wait(pending,timeout=.2,return_when=FIRST_COMPLETED)
            for future in done:
                slot=pending.pop(future)
                try:record,q=future.result()
                except Exception as error:
                    record=dict(slot,status='finish_error',error_type=type(error).__name__,
                                preserved_artifacts={str(p):sha(p)for p in out.glob(f"slot-{slot['slot']:02d}-*")if p.is_file()});q=None
                records[slot['slot']]=record
                if q is not None:
                    key=f"{case['key']}__slot{slot['slot']}__{terminal.geometry_sha(q)}";certified[key]=q
                    if record.get('usable_rectangular_donor'):donors[key]=q
                terminal.atomic_json(out/'results.json',[records[i]for i in sorted(records)])
                terminal.atomic_npz(out/'certified.npz',certified);terminal.atomic_npz(out/'rectangular-donors.npz',donors)
    ordered=[records[i]for i in sorted(records)];terminal.atomic_json(out/'results.json',ordered)
    terminal.atomic_npz(out/'certified.npz',certified);terminal.atomic_npz(out/'rectangular-donors.npz',donors)
    bounds=[Decimal(r['f_upper'])for r in ordered if r.get('usable_rectangular_donor')]
    summary=dict(status='complete' if len(ordered)==8 and not any(r.get('status')=='deadline_before_native'for r in ordered)else'partial',
                 family_key=case['key'],slots=ordered,certified=len(certified),usable_rectangular_donors=len(donors),
                 processed_slots=len(ordered),native_attempted=sum('command'in r for r in ordered),
                 native_returned=sum(r.get('native_status')=='returned'for r in ordered),
                 native_timeouts=sum(r.get('native_status')=='timeout'for r in ordered),
                 full_certificate_timeouts=sum(r.get('status')=='saved_return_certificate_timeout'for r in ordered),
                 certified_rectangle_unproven=sum(r.get('certified_archive')is not None and not r.get('rectangular_certificate',{}).get('valid')for r in ordered),
                 deadline_skipped=sum(r.get('status')=='deadline_before_native'for r in ordered),
                 completeness_scope='Processed fixed slots; individual native/certificate/rectangle outcomes remain explicit.',
                 best_f_upper=str(min(bounds))if bounds else None,strict_component_improvements=sum(bool(r.get('strict_component_improvement'))for r in ordered),
                 manifest_sha256=sha(out/'manifest.json'),results_sha256=sha(out/'results.json'),
                 certified_archive_sha256=sha(out/'certified.npz'),rectangular_donors_sha256=sha(out/'rectangular-donors.npz'),
                 no_full_portfolio_gain_claim=True,no_canonical_mutation=True,no_submission=True)
    terminal.atomic_json(out/'summary.json',summary)
    for path in out.iterdir():
        if path.is_file():path.chmod(0o444)
    return summary
