def _finish_slot(out, slot, pose, case, binary, deadline):
    n = case['n']; base = out/f"slot-{slot['slot']:02d}-{slot['arm']}-{slot['delta']}"
    record = dict(slot, n=n, source_key=case['source_key'], reference_side=str(case['reference_side']),
        selected_geometry_sha256=geometry_sha(pose), input_status='Exact released public35 changed alternative pose; no pre-native validity claim, final output requires all full gates',
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
