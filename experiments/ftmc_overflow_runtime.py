"""Self-contained parent for bounded A/B capture and certified overflow repair."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile

for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']:
    os.environ[key] = '1'
os.chdir('/kaggle/working')
root = Path.cwd()
started = time.monotonic()
processes = {}
manifest = CONFIG


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def stop_children():
    for process in processes.values():
        if process.poll() is None:
            process.terminate()
    for process in processes.values():
        if process.poll() is None:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def hard_timeout(signum, frame):
    stop_children()
    atomic_json('hard_timeout.json', {'wall_seconds': time.monotonic()-started,
        'limit_seconds': manifest['wall_seconds'], 'checkpoints_preserved': True})
    raise TimeoutError('Bounded A/B experiment reached its parent limit')


signal.signal(signal.SIGALRM, hard_timeout)
signal.alarm(manifest['wall_seconds'])
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as archive:
    for entry in archive.infolist():
        target = root/entry.filename
        if not target.resolve().is_relative_to(root):
            raise ValueError('Unsafe embedded payload path')
        data = archive.read(entry)
        if hashlib.sha256(data).hexdigest() != manifest['embedded_sha256'][entry.filename]:
            raise ValueError('Embedded payload hash mismatch')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
sys.path.insert(0, str(root))
import cupy as cp
import numpy as np
import gpu_ftmc_refill as upstream
from upright_refill import check as refill_check
from gpu_topology import check as square_check
from gpu_rect_optimizer import check as rectangle_check
from gpu_rect_explore import check as exploration_check
from gpu_upright_rows import check as rows_check

preflights = {}
hardware = {}
assert cp.cuda.runtime.getDeviceCount() > max(manifest['devices'])
for device in manifest['devices']:
    cp.cuda.Device(device).use()
    properties = cp.cuda.runtime.getDeviceProperties(device)
    name = properties['name']
    name = name.decode() if isinstance(name, bytes) else name
    assert 'T4' in name, name
    hardware[str(device)] = {'name': name, 'memory_bytes': int(properties['totalGlobalMem'])}
    checks = {}
    for label, check in [('upright_refill', refill_check), ('square_cuda', square_check),
                         ('rectangle_cuda', rectangle_check), ('fp32_vs_fp64', exploration_check),
                         ('gpu_row_refill', rows_check)]:
        checks[label] = {'passed': True, 'result': check()}
    empty_core = np.empty((1, 0, 3))
    packed8, count8 = upstream.refill_batch(empty_core, 3, 3, .2, 8, soft=0.)
    assert packed8.shape == (2, 8, 3) and np.all(cp.asnumpy(count8) == 9)
    packed9, count9 = upstream.refill_batch(empty_core, 3, 3, .2, 9, soft=0.)
    assert np.all(cp.asnumpy(count9) == 9)
    q32, result32 = upstream.explore(cp.asnumpy(packed9[:1]), np.array([[3.05, 3.05]]), steps=50)
    q64, result64 = upstream.precise(cp.asnumpy(q32), np.array([[3.05, 3.05]]), steps=50)
    polished = upstream.rect_lp(cp.asnumpy(q64)[0], 3, 3)
    assert polished is not None and upstream.gaps(polished) > 0 and upstream.certify(polished)
    assert upstream.excess(polished, 3, 3) < .001
    checks['overflow_replay_n8_to_n9'] = {'passed': True, 'reported_capacity': 9,
        'requested_before': 8, 'repaired_count': 9, 'official_raw_and_roundtrip': True,
        'note': 'Functional control, not a new competition improvement.'}
    preflights[str(device)] = checks
    atomic_json('overflow_preflight.json', preflights)
    print(json.dumps({'stage': 'preflight_passed', 'device': device}), flush=True)
    cp.get_default_memory_pool().free_all_blocks()
manifest.update(hardware=hardware, cupy_version=cp.__version__, numpy_version=np.__version__)
atomic_json('job_manifest.json', manifest)


def run_phase(phase):
    global processes
    processes = {}
    logs = {}
    phase_started = time.monotonic()
    seconds = manifest[phase+'_seconds']
    deadline = phase_started+seconds+manifest['grace_seconds']
    result = {'phase': phase, 'timed_out': False, 'failures': []}
    try:
        for device in manifest['devices']:
            config = manifest['device_configs'][str(device)]
            if phase == 'capture':
                command = [sys.executable, '-u', 'ftmc_overflow_worker.py', '--device', str(device),
                    '--seconds', str(seconds), '--replicas', str(manifest['replicas']),
                    '--seed', str(config['capture_seed'])]
                if config['angle_aware']:
                    command.append('--angle-aware')
            else:
                command = [sys.executable, '-u', 'ftmc_overflow_repair.py', '--device', str(device),
                    '--seconds', str(seconds), '--max-cores', str(manifest['repair_max_cores']),
                    '--copies', str(manifest['repair_copies']), '--seed', str(config['repair_seed'])]
            logs[device] = open(f'{phase}_device{device}.log', 'w')
            processes[device] = subprocess.Popen(command, stdout=logs[device], stderr=subprocess.STDOUT)
        while any(process.poll() is None for process in processes.values()):
            if time.monotonic() >= deadline:
                result['timed_out'] = True
                stop_children()
                break
            failures = [{'device': device, 'returncode': process.returncode}
                for device, process in processes.items() if process.poll() not in (None, 0)]
            if failures:
                result['failures'] = failures
                stop_children()
                break
            heartbeat = {'phase': phase, 'elapsed_seconds': time.monotonic()-phase_started, 'devices': {}}
            for device, process in processes.items():
                path = (Path(f'research/worker{device}_status.json') if phase == 'capture'
                        else Path(f'overflow_repair_summary_device{device}.json'))
                try:
                    status = json.loads(path.read_text()) if path.exists() else {}
                except (OSError, json.JSONDecodeError):
                    status = {}
                heartbeat['devices'][str(device)] = {key: status.get(key) for key in
                    ['batches', 'core_trials', 'refill_success', 'full_quenches', 'accepted',
                     'cores_attempted', 'certified_variants', 'direct_improved_puzzles']}
                heartbeat['devices'][str(device)]['returncode'] = process.poll()
            atomic_json('heartbeat.json', heartbeat)
            print(json.dumps(heartbeat), flush=True)
            time.sleep(min(15, max(.1, deadline-time.monotonic())))
    finally:
        stop_children()
        for log in logs.values():
            log.close()
    result['elapsed_seconds'] = time.monotonic()-phase_started
    result['returncodes'] = {str(device): process.returncode for device, process in processes.items()}
    if not result['timed_out']:
        result['failures'] = [{'device': int(device), 'returncode': code}
            for device, code in result['returncodes'].items() if code != 0]
    atomic_json(phase+'_phase.json', result)
    return result


capture = run_phase('capture')
if capture['failures']:
    raise RuntimeError('Capture arm failed; retained outputs require review before continuing')
repair = run_phase('repair')

baseline_sides = json.loads(Path('baseline_sides.json').read_text())
all_certified = {}
provenance = {}
direct = {}
for device in manifest['devices']:
    for source_name, kind in [(f'artifacts/worker{device}_gadgets.npz', 'ordinary_ftmc'),
                              (f'artifacts/overflow_repaired_device{device}.npz', 'overflow_repair')]:
        path = Path(source_name)
        if not path.exists():
            continue
        with np.load(path) as archive:
            for name in archive.files:
                p = archive[name]
                key = name.split('__')[0]
                w, h, surplus = map(int, key.split('_'))
                assert p.shape == (w*h+surplus, 3) and np.isfinite(p).all()
                sha = hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()
                identity = key+'__'+sha[:20]
                if identity not in all_certified:
                    assert upstream.gaps(p) > 0 and upstream.certify(p), identity
                    all_certified[identity] = p
                    provenance[identity] = {'key': key, 'geometry_sha256': sha,
                        'official_raw_and_roundtrip': True, 'sources': []}
                provenance[identity]['sources'].append({'device': device, 'kind': kind, 'variant': name})
                n = len(p)
                side = float(upstream.dimensions(p).max())
                previous = direct.get(str(n), {}).get('side', float(baseline_sides[str(n)]))
                if side < previous-1e-9:
                    direct[str(n)] = {'side': side, 'squares': p.tolist(),
                        'source': 'certified angle/overflow FTMC A/B pilot', 'variant': identity}
upstream.atom_npz('artifacts/overflow_all_certified_gadgets.npz', all_certified)
atomic_json('overflow_certified_provenance.json', provenance)
atomic_json('overflow_full_puzzle_candidates.json', direct)
summary = {'stage': 'failed' if repair['failures'] else 'complete',
    'wall_seconds': time.monotonic()-started, 'capture': capture, 'repair': repair,
    'certified_variants': len(all_certified), 'direct_improved_puzzles': len(direct),
    'preflight': preflights, 'devices': {}}
for device in manifest['devices']:
    paths = {'capture': f'artifacts/overflow_device{device}.json',
        'worker': f'research/worker{device}_status.json',
        'funnel': f'research/overflow_capture_metrics_device{device}.json',
        'repair': f'overflow_repair_summary_device{device}.json'}
    summary['devices'][str(device)] = {}
    for label, filename in paths.items():
        path = Path(filename)
        record = json.loads(path.read_text()) if path.exists() else {'missing': True}
        summary['devices'][str(device)][label] = {k: v for k, v in record.items()
            if k not in ['records', 'last_batch', 'latest']}
atomic_json('overflow_summary.json', summary)
signal.alarm(0)
print(json.dumps({'stage': summary['stage'], 'wall_seconds': summary['wall_seconds'],
    'certified_variants': len(all_certified), 'direct_improved_puzzles': len(direct)}), flush=True)
if repair['failures']:
    raise RuntimeError('One or more repair workers failed; certified checkpoints retained')
