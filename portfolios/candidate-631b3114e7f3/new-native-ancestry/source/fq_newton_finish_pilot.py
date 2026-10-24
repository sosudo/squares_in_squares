"""Matched bounded Newton-finish pilot on fresh certified contact-polish tails."""
import time
STARTED = time.monotonic()
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from decimal import Decimal, localcontext
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import numpy as np
import fq_active_pilot as fq
from fq_capacity_probe import full_certificate
from fq_coherent_clusters import Deadline, alarm, atom_json, atom_npz
from compose_gadgets import normalize, side

ROOT = Path(__file__).resolve().parents[1]
BINARY_SHA = '10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
TARGETS = [761, 920, 981, 995]
COMMON = ['--no-alm', '--loosen', '1', '--pit', '100', '--flip-top', '0', '--stag-w', '0', '--v']


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()


def activation(log, finish):
    projections = [line for line in log.splitlines() if line.lstrip().startswith('gn round ')]
    kkt = [line for line in log.splitlines() if line.lstrip().startswith('kkt |A| ')]
    accepted = [int(m[1]) for line in log.splitlines()
                if (m := re.search(r'tr (\d+) .* acc true', line))]
    return dict(finish_requested=finish, accepted_steps=accepted,
        gauss_newton_calls=projections, kkt_steps=kkt,
        actual_finish_path_observed=bool(projections or kkt),
        evidence='Pinned source emits FQ_FIN gn/kkt lines only inside newton_finish; a request alone is not activation.')


def certified_side(certificate):
    shared = certificate['shared_official_gate']
    values = [shared['raw_side'], shared['roundtrip_side'], certificate['ordinary_pandas_official_side'],
              certificate['independent_raw']['side_upper'], certificate['independent_roundtrip']['side_upper']]
    numbers = [Decimal(str(value)) for value in values]
    assert all(value.is_finite() for value in numbers)
    return max(numbers)


def worker(job):
    out, n, mode, control, deadline = job
    out = Path(out); directory = out/'trials'/f'n{n}-{mode}'
    directory.mkdir()
    manifest = json.loads((out/'manifest.json').read_text())
    with np.load(out/'inputs/poses.npz', allow_pickle=False) as archive:
        p = archive[str(n)].copy()
    assert geometry_sha(p) == manifest['geometry_sha256'][str(n)]
    options = COMMON+(['--finish'] if mode == 'finish' else [])
    encoded = (out/'inputs'/f'n{n}.in').read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == manifest['native_input_sha256'][str(n)]
    inp, dst = directory/'native.in', directory/'native.out'
    inp.write_bytes(encoded)
    command = [str((out/'inputs/fq').resolve()), 'quench', '--in', str(inp.resolve()),
               '--out', str(dst.resolve()), '--rect-dx', '0', '--rect-dy', '0', '--seed', str(9480000+n), *options]
    record = dict(n=n, mode=mode, control=control, command=command,
        parent_geometry_sha256=geometry_sha(p), native_input_sha256=fq.digest(inp),
        reference_side=manifest['sides'][str(n)], status='started')
    environment = {k:v for k,v in os.environ.items() if not k.startswith('FQ_')}
    environment.update(FQ_TR='1', FQ_LPT='1', FQ_LP_IPM='1', FQ_LP_IR='0', FQ_FIN='1')
    started = time.monotonic(); q = None
    stdout, stderr = directory/'native.stdout', directory/'native.stderr'
    process = None
    try:
        remaining = min(60., deadline-time.monotonic())
        if remaining < .2:
            record['status'] = 'budget-skipped'; return record, None
        with stdout.open('w') as stream, stderr.open('w') as errors:
            process = subprocess.Popen(command, stdout=stream, stderr=errors, env=environment)
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=1.)
                record['status'] = 'native-timeout'
        record.update(native_seconds=time.monotonic()-started, native_returncode=process.returncode,
            stdout_sha256=fq.digest(stdout), stderr_sha256=fq.digest(stderr))
        record['activation'] = activation(stderr.read_text(), mode == 'finish')
        if not dst.exists():
            record.setdefault('status', 'native-no-return')
            if record['status'] == 'started': record['status'] = 'native-no-return'
            return record, None
        # Original decimal bytes are durable before parsing or any geometry gate.
        record['native_output_sha256'] = fq.digest(dst)
        record['native_output_path'] = str(dst)
        atom_json(directory/'native-return.json', record)
        lines = dst.read_text().splitlines()
        assert int(lines[0].split()[0]) == n and len(lines) == n+1
        raw = np.array([[float(x) for x in row.split()] for row in lines[1:]], dtype=np.float64)
        assert raw.shape == (n,3) and np.isfinite(raw).all()
        raw[:,2] = np.radians(raw[:,2])
        atom_npz(directory/'raw-returned.npz', {'pose':raw})
        record['raw_returned_geometry_sha256'] = geometry_sha(raw)
        record['raw_returned_archive_sha256'] = fq.digest(directory/'raw-returned.npz')
        atom_json(directory/'native-return.json', record)
        if process.returncode:
            record['status'] = 'native-nonzero-return'; return record, None
        remaining = min(8., deadline-time.monotonic())
        if remaining < .2:
            record['status'] = 'certificate-not-attempted'; return record, None
        previous = signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, remaining)
        cert_started = time.monotonic()
        try:
            q = fq.decode(dst, n)
            if q is None:
                record['status'] = 'failed-rounding-repair'; return record, None
            atom_npz(directory/'pending-certificate.npz', {'pose':q})
            record['pending_geometry_sha256'] = geometry_sha(q)
            certificate = full_certificate(q)
            record['certificate'] = certificate
            if not certificate['valid']:
                record['status'] = 'failed-certificate'; return record, None
            assert certificate['independent_raw']['n'] == n
            with localcontext() as context:
                context.prec = 70
                length = certified_side(certificate); reference = Decimal(record['reference_side'])
                gain = reference-length
                record.update(status='certified', geometry_sha256=geometry_sha(q), side=str(length),
                    side_gain=str(gain), strict_improvement=gain>Decimal('1e-8'),
                    score_gain=str(gain/Decimal(n).sqrt()))
            archive = directory/'certified.npz'; atom_npz(archive, {'pose':q})
            record['certified_archive_sha256'] = fq.digest(archive)
            return record, q
        except Deadline:
            record['status'] = 'certificate-timeout'; return record, None
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, previous)
            record['certification_seconds'] = time.monotonic()-cert_started
    except Exception as error:
        record.update(status='error', error_type=type(error).__name__)
        return record, None
    finally:
        if process is not None and process.poll() is None:
            process.kill(); process.wait(timeout=1.)
        record['elapsed_seconds'] = time.monotonic()-started
        atom_json(directory/'result.json', record)


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    for name in ('inputs','source','trials'): (out/name).mkdir()
    pointer_path = ROOT/'artifacts/current-best-portfolio.json'
    pointer = json.loads(pointer_path.read_text()); baseline = pointer['raw']
    assert fq.digest(baseline['path']) == baseline['sha256']
    assert fq.digest(baseline['official_report']) == baseline['official_report_sha256']
    report = json.loads(Path(baseline['official_report']).read_text())
    assert report['valid'] and report['puzzles'] == 1000 and report['sha256'] == baseline['sha256']
    assert report['metric_sha256'] == fq.OFFICIAL_SHA256
    selected = [17]+TARGETS; rows = {n:[] for n in selected}
    with open(baseline['path']) as stream:
        for row in csv.DictReader(stream):
            n = int(row['n'])
            if n in rows: rows[n].append((int(row['square_id']), [float(row[k]) for k in ('x','y','angle')]))
    poses = {n:np.array([q for _,q in sorted(values)],dtype=np.float64) for n,values in rows.items()}
    assert all(p.shape == (n,3) and np.isfinite(p).all() for n,p in poses.items())
    sides = {str(r['n']):r['side'] for r in report['results'] if r['n'] in selected}
    native_hashes = {}
    for n,p in poses.items():
        start = normalize(p)
        if n == 17: start[:,:2] *= 1.0005
        encoded, offsets = fq.encode(start, math.floor(side(start)), math.floor(side(start)))
        assert offsets == [0,0]
        path = out/'inputs'/f'n{n}.in'; path.write_text(encoded); native_hashes[str(n)] = fq.digest(path)
    atom_npz(out/'inputs/poses.npz', {str(n):p for n,p in poses.items()})
    shutil.copyfile(ROOT/'artifacts/fq-n65-small-v1/inputs/fq', out/'inputs/fq')
    (out/'inputs/fq').chmod(0o500); assert fq.digest(out/'inputs/fq') == BINARY_SHA
    sources = [Path(__file__), ROOT/'experiments/fq_active_pilot.py', ROOT/'experiments/fq_capacity_probe.py',
        ROOT/'experiments/fq_coherent_clusters.py', ROOT/'experiments/compose_gadgets.py',
        ROOT/'experiments/refill_capacity.py', ROOT/'experiments/refill_search.py',
        ROOT/'scripts/score_official.py', ROOT/'scripts/validate_submission.py',
        ROOT/'research/official_metric_v17.py', ROOT/'vendor/fq/src/fq.rs', ROOT/'vendor/fq/src/lpipm.rs', ROOT/'experiments/fq_sqp_pilot.py', ROOT/'vendor/fq/LICENSE', ROOT/'vendor/fq/NOTICE']
    for source in sources:
        destination = out/'source'/source.name; shutil.copyfile(source,destination); destination.chmod(0o444)
    manifest = dict(baseline=baseline, pointer_sha256=fq.digest(pointer_path), targets=TARGETS,
        source_hashes={str(path):fq.digest(path) for path in sources}, binary_sha256=BINARY_SHA,
        poses_sha256=fq.digest(out/'inputs/poses.npz'), geometry_sha256={str(n):geometry_sha(p) for n,p in poses.items()},
        sides=sides, native_input_sha256=native_hashes, common_options=COMMON,
        treatment_extra=['--finish'], workers=2, maximum_seconds=360, native_cap_seconds=60,
        separate_certificate_cap_seconds=8, control=dict(n=17, center_dilation=1.0005, maximum_side_excess=1e-6),
        environment_overrides=dict(FQ_TR='1',FQ_LPT='1',FQ_LP_IPM='1',FQ_LP_IR='0', FQ_FIN='1'),
        other_FQ_environment_removed=True, no_pointer_mutation=True, no_submission=True)
    atom_json(out/'manifest.json', manifest)


def campaign(out, deadline):
    manifest = json.loads((out/'manifest.json').read_text())
    assert all(fq.digest(path) == identity for path,identity in manifest['source_hashes'].items())
    assert fq.digest(out/'inputs/fq') == BINARY_SHA and fq.digest(out/'inputs/poses.npz') == manifest['poses_sha256']
    records=[]; donors={}
    def retain(record,q):
        records.append(record)
        if q is not None: donors[f"{record['n']}__{record['mode']}_{geometry_sha(q)}"] = q
        atom_json(out/'results.json',records); atom_npz(out/'donors.npz',donors)
        print(json.dumps({key:record.get(key) for key in ('n','mode','status','side_gain','elapsed_seconds')}),flush=True)
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork')) as pool:
        controls = [pool.submit(worker,(str(out),17,mode,True,deadline)) for mode in ('lp','finish')]
        for future in as_completed(controls): retain(*future.result())
        passed = all(r['status']=='certified' and Decimal(r['side']) <= Decimal(r['reference_side'])+Decimal('1e-6') for r in records)
        finish_control = next(r for r in records if r['mode']=='finish')
        passed = passed and finish_control.get('activation',{}).get('actual_finish_path_observed',False)
        atom_json(out/'controls.json',dict(passed=passed,records=records.copy()))
        if not passed: return dict(status='control-failed',trials=len(records),score_gain=0.)
        futures = [pool.submit(worker,(str(out),n,mode,False,deadline)) for n in TARGETS for mode in ('lp','finish')]
        for future in as_completed(futures): retain(*future.result())
    comparisons = []
    for n in TARGETS:
        pair = {r['mode']:r for r in records if r['n']==n}
        valid = {mode:Decimal(r['side']) for mode,r in pair.items() if r['status']=='certified'}
        baseline = Decimal(manifest['sides'][str(n)])
        best = min([baseline]+list(valid.values()))
        comparisons.append(dict(n=n, sides={k:str(v) for k,v in valid.items()}, baseline=str(baseline),
            score_gain=float((baseline-best)/Decimal(n).sqrt()),
            finish_better_than_lp=(valid['finish']<valid['lp']-Decimal('1e-8')) if len(valid)==2 else None,
            finish_path_observed=pair['finish'].get('activation',{}).get('actual_finish_path_observed',False)))
    atom_json(out/'comparisons.json',comparisons)
    return dict(status='complete',trials=len(records),certified_geometries=len(donors),
        score_gain=sum(r['score_gain'] for r in comparisons),comparisons=comparisons,
        sources_unchanged=all(fq.digest(path)==identity for path,identity in manifest['source_hashes'].items()),
        donors_sha256=fq.digest(out/'donors.npz'),results_sha256=fq.digest(out/'results.json'))


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--prepare',action='store_true'); parser.add_argument('--child',action='store_true')
    parser.add_argument('--deadline',type=float); args=parser.parse_args(); out=args.out.resolve()
    if args.prepare: return prepare(out)
    if args.child:
        result=campaign(out,args.deadline); atom_json(out/'summary.json',result); print(json.dumps(result),flush=True); return
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(out),'--child',
                              '--deadline',str(STARTED+348)],start_new_session=True)
    forced=False
    try: process.wait(timeout=max(.01,STARTED+357-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=1)
    receipt=dict(returncode=process.returncode,seconds=time.monotonic()-STARTED,forced=forced,maximum_seconds=360,workers=2)
    atom_json(out/'supervisor.json',receipt); print(json.dumps(receipt),flush=True)
    if process.returncode and not forced: raise SystemExit(process.returncode)


if __name__=='__main__':main()
