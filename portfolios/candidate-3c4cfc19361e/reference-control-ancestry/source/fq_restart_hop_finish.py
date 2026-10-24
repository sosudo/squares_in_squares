"""Fixed-slot native finishes of committed GPU control/reset BEST states.

Initializer arrays are UNVERIFIED. Only unchanged full raw/default-pandas and
independent interval gates establish feasibility; every valid output is kept.
"""
from __future__ import annotations
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import signal
import subprocess
import time
import numpy as np

import fq_active_pilot as fq
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json, atomic_npz, geometry_sha

ROOT = Path(__file__).resolve().parents[1]
BINARY_SHA = '10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
OPTIONS = ['--loosen', '1', '--outer', '45', '--pit', '100', '--flip-top', '16']
NATIVE_SECONDS = 12.
CERTIFICATE_SECONDS = 8.
ARMS = ('control', 'reset')
DELTAS = (.002, .008)
STATE_KEYS = ('current_after', 'best_after', 'sides', 'next_energy', 'best_energy_after')


class CertificateDeadline(BaseException):
    pass


def _alarm(*_):
    raise CertificateDeadline()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pose_from_output(path, n):
    lines = Path(path).read_text().splitlines()
    if len(lines) != n+1 or int(lines[0].split()[0]) != n:
        raise ValueError('native_count_mismatch')
    q = np.array([[float(v) for v in line.split()] for line in lines[1:]], dtype=np.float64)
    if q.shape != (n, 3) or not np.isfinite(q).all():
        raise ValueError('invalid_native_coordinates')
    q[:, 2] = np.radians(q[:, 2])
    return q


def worst_certificate_side(certificate):
    """Conservative comparison across exact text and both pandas transports."""
    if not certificate['valid']:
        raise ValueError('invalid_full_certificate')
    shared = certificate['shared_official_gate']
    values = dict(official_raw=shared['raw_side'], official_17g_pandas=shared['roundtrip_side'],
        official_default_pandas=certificate['ordinary_pandas_official_side'],
        interval_raw=certificate['independent_raw']['side_upper'],
        interval_default_pandas=certificate['independent_roundtrip']['side_upper'])
    decimals = {key: Decimal(str(value)) for key, value in values.items()}
    if not all(value.is_finite() and value > 0 for value in decimals.values()):
        raise ValueError('invalid_certified_side')
    return str(max(decimals.values())), {key: str(value) for key, value in decimals.items()}


def select_slots(design, energy):
    """One lowest-energy chain per declared arm×delta; ties use chain index."""
    if len(design) != len(energy) or sorted(r['chain'] for r in design) != list(range(len(design))):
        raise ValueError('chain_inventory_mismatch')
    rows = {r['chain']: r for r in design}
    if any(r['arm'] not in ARMS or r['delta'] not in DELTAS for r in design):
        raise ValueError('unsupported_arm_or_delta')
    result = []
    # Interleaved arms avoid giving one arm a prefix advantage near a deadline.
    for delta in DELTAS:
        for arm in ARMS:
            indices = [i for i, r in rows.items() if r['arm'] == arm and r['delta'] == delta
                       and math.isfinite(float(energy[i])) and float(energy[i]) >= 0]
            chain = min(indices, key=lambda i: (float(energy[i]), i)) if indices else None
            result.append(dict(slot=len(result), arm=arm, delta=delta, chain=chain,
                status='selected' if chain is not None else 'no_finite_state',
                design=rows[chain] if chain is not None else None))
    return result


def _recorded_native(command, base, timeout):
    """Native inherits the caller's bounded group; always kill/wait if interrupted."""
    process = None
    with base.with_suffix('.stdout').open('wb') as stdout, base.with_suffix('.stderr').open('wb') as stderr:
        try:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
            try:
                process.wait(timeout=timeout)
                return dict(native_status='returned', returncode=process.returncode)
            except subprocess.TimeoutExpired:
                return dict(native_status='timeout', returncode=None)
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=1.)


def _finish_slot(out, slot, pose, case, binary, deadline):
    n = case['n']; base = out/f"slot-{slot['slot']:02d}-{slot['arm']}-{slot['delta']}"
    record = dict(slot, n=n, source_key=case['source_key'], reference_side=str(case['reference_side']),
        selected_geometry_sha256=geometry_sha(pose), input_status='UNVERIFIED exact committed BEST array',
        native_seconds_cap=NATIVE_SECONDS, certificate_seconds_cap=CERTIFICATE_SECONDS)
    parent = base.with_suffix('.selected.npz'); atomic_npz(parent, {'pose': pose}); parent.chmod(0o444)
    record['selected_archive'] = str(parent); record['selected_archive_sha256'] = _sha(parent)
    atomic_json(base.with_suffix('.record.json'), record)
    if deadline-time.monotonic() < .2:
        return dict(record, status='deadline_before_native'), None
    encoded, offsets = fq.encode(pose, math.isqrt(n), math.isqrt(n))
    assert offsets == [0, 0]
    base.with_suffix('.in').write_text(encoded)
    command = [str(binary), 'quench', '--in', str(base.with_suffix('.in')), '--out', str(base.with_suffix('.out')),
        '--rect-dx', '0', '--rect-dy', '0', '--seed', str(9710000+DELTAS.index(slot['delta'])), *OPTIONS]
    record.update(command=command, input_sha256=_sha(base.with_suffix('.in')),
        command_sha256=hashlib.sha256(json.dumps(command, separators=(',', ':')).encode()).hexdigest())
    begin = time.monotonic()
    try:
        record.update(_recorded_native(command, base, min(NATIVE_SECONDS, max(.001, deadline-begin))))
    finally:
        record['native_seconds'] = time.monotonic()-begin
        for suffix in ('stdout', 'stderr'):
            path = base.with_suffix('.'+suffix)
            if path.exists(): record[suffix+'_sha256'] = _sha(path)
        if base.with_suffix('.stdout').exists() and base.with_suffix('.stderr').exists():
            base.with_suffix('.log').write_bytes(base.with_suffix('.stdout').read_bytes()+b'\n'+base.with_suffix('.stderr').read_bytes())
            record['log_sha256'] = _sha(base.with_suffix('.log'))
        atomic_json(base.with_suffix('.record.json'), record)
    native = base.with_suffix('.out')
    if not native.exists():
        return dict(record, status='no_native_output'), None
    record['native_output_path'] = str(native); record['native_output_sha256'] = _sha(native)
    try:
        raw = _pose_from_output(native, n)
    except (ValueError, IndexError):
        return dict(record, status='malformed_native_output'), None
    raw_path = base.with_suffix('.raw.npz'); atomic_npz(raw_path, {'pose': raw}); raw_path.chmod(0o444)
    record['raw_returned'] = dict(path=str(raw_path), sha256=_sha(raw_path), geometry_sha256=geometry_sha(raw), verified=False)
    record['status'] = 'saved_native_before_certificate'; atomic_json(base.with_suffix('.record.json'), record)
    remaining = deadline-time.monotonic()
    if remaining < .2:
        return dict(record, status='saved_return_certificate_budget_exhausted'), None
    begin = time.monotonic(); previous_handler = signal.signal(signal.SIGALRM, _alarm)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    allowance = min(CERTIFICATE_SECONDS, remaining, previous_timer[0] if previous_timer[0] > 0 else math.inf)
    signal.setitimer(signal.ITIMER_REAL, allowance)
    try:
        q = fq.decode(native, n)
        if q is None or q.shape != (n, 3) or not np.isfinite(q).all():
            return dict(record, status='failed_bounded_clearance'), None
        decoded = base.with_suffix('.decoded.npz'); atomic_npz(decoded, {'pose': q}); decoded.chmod(0o444)
        record['decoded_returned'] = dict(path=str(decoded), sha256=_sha(decoded), geometry_sha256=geometry_sha(q))
        certificate = full_certificate(q); record['certificate'] = certificate
        if not certificate['valid']:
            return dict(record, status='failed_full_gates'), None
        worst, sides = worst_certificate_side(certificate)
        # Publish every certified geometry, including wider/worse outcomes.
        record.update(status='certified', geometry_sha256=geometry_sha(q), worst_certified_side=worst,
            certified_sides=sides, side_gain=str(Decimal(str(case['reference_side']))-Decimal(worst)))
        record['strict_improvement'] = Decimal(record['side_gain']) > 0
        target = base.with_suffix('.certified.npz'); atomic_npz(target, {'pose': q}); target.chmod(0o444)
        record['certified_archive'] = str(target); record['certified_archive_sha256'] = _sha(target)
        atomic_json(base.with_suffix('.certificate.json'), record); base.with_suffix('.certificate.json').chmod(0o444)
        return record, q
    except CertificateDeadline:
        return dict(record, status='saved_return_certificate_timeout'), None
    except Exception as error:
        return dict(record, status='saved_return_certificate_error', error_type=type(error).__name__), None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, max(.001, previous_timer[0]-(time.monotonic()-begin)), previous_timer[1])


def finish_case(root: Path, case_config: dict, deadline: float) -> dict:
    """Finish <=4 fixed slots sequentially; deadline is absolute monotonic time."""
    root = Path(root).resolve(); out = root/'finish'; out.mkdir(exist_ok=False)
    case = dict(case_config); n = int(case['n']); case['n'] = n
    reference = Decimal(str(case['reference_side']))
    if not reference.is_finite() or reference <= 0 or not math.isfinite(deadline):
        raise ValueError('invalid_reference_or_deadline')
    binary = Path(case['binary_path']); binary = binary if binary.is_absolute() else root/binary
    if _sha(binary) != BINARY_SHA:
        raise ValueError('native_binary_sha256_mismatch')
    design_path = root/'chain-design.json'; final_path = root/'final-current-best.npz'; index_path = root/'raw-index.json'
    design = json.loads(design_path.read_text()); index = json.loads(index_path.read_text())
    completed = [entry for entry in index['packets'] if entry['status'] == 'completed']
    if not completed:
        summary = dict(status='no_completed_packet', slots=[], certified=0, no_submission=True, no_canonical_mutation=True)
        atomic_json(out/'summary.json', summary); return summary
    origin = completed[-1]; packet = Path(origin['path']); packet = packet if packet.is_absolute() else root/packet
    if _sha(packet) != origin['sha256']:
        raise ValueError('last_completed_packet_sha256_mismatch')
    with np.load(final_path, allow_pickle=False) as final, np.load(packet, allow_pickle=False) as previous:
        arrays = {name: final[name].copy() for name in STATE_KEYS}
        if any(not np.array_equal(arrays[name], previous[name]) for name in STATE_KEYS):
            raise ValueError('recovered_final_differs_from_last_committed_packet')
        metadata = json.loads(previous['metadata_json'].tobytes())
        if metadata['status'] != 'completed' or metadata['design'] != design:
            raise ValueError('committed_design_mismatch')
        for name in STATE_KEYS:
            if hashlib.sha256(previous[name].tobytes()).hexdigest() != metadata['array_sha256'][name]:
                raise ValueError('committed_array_hash_mismatch')
    B = len(design)
    if arrays['best_after'].shape != (B, n, 3) or not np.isfinite(arrays['best_after']).all():
        raise ValueError('invalid_full_count_best_arrays')
    if any(row['n'] != n or row['source_key'] != case['source_key'] for row in design):
        raise ValueError('case_source_design_mismatch')
    if arrays['best_energy_after'].shape != (B,) or arrays['sides'].shape != (B,):
        raise ValueError('invalid_energy_or_box_arrays')
    if any(float(arrays['sides'][row['chain']]) != float(row['side']) for row in design):
        raise ValueError('committed_fixed_box_mismatch')
    slots = select_slots(design, arrays['best_energy_after'])
    helpers = [Path(__file__), Path(fq.__file__), ROOT/'experiments/fq_capacity_probe.py',
        ROOT/'experiments/fq_variant_campaign.py', ROOT/'experiments/compose_gadgets.py',
        ROOT/'scripts/score_official.py', ROOT/'scripts/validate_submission.py', ROOT/'research/official_metric_v17.py']
    manifest = dict(case_config=case, deadline_monotonic=deadline, fixed_slots=slots, options=OPTIONS,
        binary_sha256=BINARY_SHA, native_source_commit=fq.SOURCE_COMMIT, official_metric_sha256=fq.OFFICIAL_SHA256,
        final_archive_sha256=_sha(final_path), design_sha256=_sha(design_path), index_sha256=_sha(index_path),
        last_completed_packet=dict(origin, resolved_path=str(packet)), helper_hashes={str(path): _sha(path) for path in helpers},
        selection='One minimum committed best_energy_after perarm×delta; missing/deadline slots stay empty without reallocation.',
        input_status='UNVERIFIED exact BEST states; low physical energy is not feasibility.',
        native_seconds_cap=NATIVE_SECONDS, certificate_seconds_cap=CERTIFICATE_SECONDS)
    atomic_json(out/'manifest.json', manifest); records = []; certified = {}
    for slot in slots:
        if slot['chain'] is None:
            record = dict(slot)
        else:
            chain = slot['chain']; pose = arrays['best_after'][chain].copy()
            slot = dict(slot, committed_best_energy=float(arrays['best_energy_after'][chain]),
                current_energy_not_selected=float(arrays['next_energy'][chain]), fixed_box=float(arrays['sides'][chain]),
                last_completed_packet_sha256=origin['sha256'])
            record, q = _finish_slot(out, slot, pose, case, binary, deadline)
            if q is not None:
                certified[f"n{n}_{slot['arm']}_delta{slot['delta']}_chain{chain}"] = q
        records.append(record); atomic_json(out/'results.json', records)
    atomic_npz(out/'certified.npz', certified)
    per_arm = {}
    for arm in ARMS:
        rows = [r for r in records if r['arm'] == arm and r.get('status') == 'certified']
        lengths = [Decimal(r['worst_certified_side']) for r in rows]
        per_arm[arm] = dict(selected_slots=2, attempted=sum(r['arm'] == arm and 'command' in r for r in records),
            certified=len(rows), best_side=str(min(lengths)) if lengths else None,
            worst_side=str(max(lengths)) if lengths else None,
            strict_improvements=sum(r['strict_improvement'] for r in rows))
    summary = dict(status='complete' if len(records) == 4 else 'partial', n=n, slots=records,
        certified=len(certified), per_arm=per_arm, reference_side=str(reference),
        manifest_sha256=_sha(out/'manifest.json'), results_sha256=_sha(out/'results.json'),
        certified_archive_sha256=_sha(out/'certified.npz'), no_submission=True, no_canonical_mutation=True)
    atomic_json(out/'summary.json', summary)
    for path in out.iterdir():
        if path.is_file(): path.chmod(0o444)
    return summary
