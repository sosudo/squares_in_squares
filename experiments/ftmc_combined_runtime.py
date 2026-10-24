"""Self-contained 30-minute productive dual-T4 runtime; builder embeds inputs."""
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

for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[name] = '1'
os.chdir('/kaggle/working')
root = Path.cwd()
manifest = CONFIG
started = time.monotonic()
processes, logs = {}, {}
for directory in ['artifacts','research']:
    (root/directory).mkdir(exist_ok=True)


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def stop_children():
    for process in processes.values():
        if process.poll() is None:
            process.terminate()
    # Most final work is bounded aggregate writing; preserve immutable files
    # even if an interrupted library call prevents a graceful checkpoint.
    for process in processes.values():
        if process.poll() is None:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def hard_timeout(signum, frame):
    # Finishing grace belongs to the earlier worker deadline, not this final
    # parent alarm. Do not add another 30-second wait per device here.
    for process in processes.values():
        if process.poll() is None:
            process.kill()
    for process in processes.values():
        if process.poll() is None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
    atomic_json('hard_timeout.json', {'wall_seconds': time.monotonic()-started,
        'limit_seconds': manifest['wall_seconds'], 'immutable_checkpoints_preserved': True})
    raise TimeoutError('Combined campaign wall limit reached')


signal.signal(signal.SIGALRM, hard_timeout)
signal.alarm(manifest['wall_seconds'])
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as archive:
    for entry in archive.infolist():
        target = root/entry.filename
        assert target.resolve().is_relative_to(root), entry.filename
        payload = archive.read(entry)
        assert hashlib.sha256(payload).hexdigest() == manifest['embedded_sha256'][entry.filename]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
# The released worker can resume a legacy checkpoint automatically. This run
# has explicit per-device initial banks, so refuse any reused working outputs
# before starting CUDA or workers instead of silently changing those inputs.
stale = []
for device in manifest['devices']:
    for pattern in [f'artifacts/worker{device}_*', f'artifacts/certified_device{device}*',
                    f'artifacts/exploratory_device{device}*', f'research/worker{device}_*.json']:
        stale.extend(str(path.relative_to(root)) for path in root.glob(pattern))
if stale:
    raise RuntimeError('Fresh campaign working directory required; existing outputs: '+repr(sorted(stale)))
sys.path.insert(0, str(root))
import numpy as np
import cupy as cp
from gpu_ftmc_refill import excess, atom_npz
from upright_refill import check as refill_check
from gpu_topology import check as square_check
from gpu_rect_optimizer import check as rectangle_check
from gpu_rect_explore import check as exploration_check
from gpu_upright_rows import check as row_check
from ftmc_combined_export import read_certified_checkpoint, recover_certified_checkpoint

assert cp.cuda.runtime.getDeviceCount() > max(manifest['devices'])
hardware, preflight = [], {}
for device in manifest['devices']:
    cp.cuda.Device(device).use()
    properties = cp.cuda.runtime.getDeviceProperties(device)
    name = properties['name']
    name = name.decode() if isinstance(name, bytes) else name
    assert 'T4' in name, name
    hardware.append({'device': device, 'name': name, 'memory_bytes': int(properties['totalGlobalMem'])})
    checks = {}
    for label, check in [('upright_refill',refill_check), ('square_cuda',square_check),
                         ('rectangle_cuda',rectangle_check), ('fp32_vs_fp64',exploration_check),
                         ('gpu_row_refill',row_check)]:
        result = check()
        checks[label] = {'passed': True, 'result': result}
        preflight[str(device)] = checks
        atomic_json('preflight.json', preflight)
        print(json.dumps({'stage': 'preflight', 'device': device, 'check': label, 'result': result}), flush=True)
    cp.get_default_memory_pool().free_all_blocks()
manifest.update(hardware=hardware, cupy_version=cp.__version__, numpy_version=np.__version__)
atomic_json('job_manifest.json', manifest)
baseline, initial_by_device = {}, {}
with np.load('prepared_bank.npz') as archive:
    bank = {key: archive[key] for key in archive.files}
for key, q in bank.items():
    baseline[key] = excess(q, *map(int, key.split('_')[:2]))
for device in manifest['devices']:
    with np.load(f'prepared_bank_device{device}.npz') as archive:
        initial = {key: archive[key] for key in archive.files}
    assert set(initial) == set(bank)
    atom_npz(f'artifacts/device{device}_initial_bank.npz', initial)
    initial_by_device[str(device)] = {key: excess(q, *map(int, key.split('_')[:2])) for key, q in initial.items()}
with np.load('prepared_variants.npz') as archive:
    variants = {key: archive[key] for key in archive.files}
atom_npz('artifacts/night_seed_variants.npz', variants)
Path('research/night_priorities.json').write_bytes(Path('prepared_priorities.json').read_bytes())
atomic_json('campaign_incumbents.json', {'original_bank': baseline, 'device_initial_bloats': initial_by_device})

worker_started = time.monotonic()
deadline = worker_started+manifest['search_seconds']+manifest['grace_seconds']
timed_out, failures = False, []
try:
    for device in manifest['devices']:
        cfg = manifest['device_configs'][str(device)]
        command = [sys.executable, '-u', 'ftmc_combined_worker.py', '--device', str(device),
            '--seconds', str(manifest['search_seconds']), '--replicas', str(cfg['replicas']), '--seed', str(cfg['seed'])]
        logs[device] = open(f'ftmc_worker{device}.log', 'w')
        processes[device] = subprocess.Popen(command, stdout=logs[device], stderr=subprocess.STDOUT)
    while any(process.poll() is None for process in processes.values()):
        heartbeat = {'stage': 'workers', 'elapsed': time.monotonic()-worker_started, 'devices': {}}
        for device, process in processes.items():
            path = Path(f'research/worker{device}_status.json')
            try:
                status = json.loads(path.read_text()) if path.exists() else {}
            except (OSError, json.JSONDecodeError):
                status = {}
            heartbeat['devices'][str(device)] = {key: status.get(key) for key in
                ['seconds','batches','core_trials','refill_success','full_quenches','accepted','cuda_seconds']}
            heartbeat['devices'][str(device)]['returncode'] = process.poll()
            if process.poll() not in (None, 0):
                failures.append({'device': device, 'returncode': process.returncode})
        atomic_json('heartbeat.json', heartbeat)
        print(json.dumps(heartbeat), flush=True)
        if failures or time.monotonic() > deadline:
            timed_out = not failures
            stop_children()
            break
        time.sleep(20)
finally:
    stop_children()
    for log in logs.values():
        log.close()

all_poses, records, per_device, statuses, funnels, budgets, binding_checks = {}, {}, {}, {}, {}, {}, {}
for device in manifest['devices']:
    for directory, stem, result in [('research','worker{}_status',statuses),
            ('research','combined_funnel_device{}',funnels), ('research','combined_refill_budget_device{}',budgets)]:
        path = Path(directory)/(stem.format(device)+'.json')
        result[str(device)] = json.loads(path.read_text()) if path.exists() else {'missing': True}
    prefix = f'artifacts/certified_device{device}'
    if not Path(prefix+'_snapshots').exists():
        failures.append({'device': device, 'missing_certified_snapshots': True})
        continue
    try:
        poses, certificates, binding = read_certified_checkpoint(prefix)
    except (ValueError, KeyError, OSError) as interrupted:
        try:
            poses, certificates, binding = recover_certified_checkpoint(prefix)
            binding['interrupted_checkpoint_error'] = str(interrupted)
        except (ValueError, KeyError, OSError) as corrupt:
            failures.append({'device': device, 'certificate_recovery_failed': str(corrupt)})
            continue
    binding_checks[str(device)] = binding
    improved_device = 0
    for name, q in poses.items():
        cert = certificates[name]
        key = cert['key']
        f = excess(q, *map(int, key.split('_')[:2]))
        assert abs(f-cert['bloat']) < 1e-12
        old = initial_by_device[str(device)][key]
        improved_device += int(f < old-2e-7)
        if name not in records:
            all_poses[name] = q
            records[name] = {'key': key, 'bloat': f, 'original_seed_bloat': baseline[key],
                'gain_from_original': baseline[key]-f, 'official_raw_and_roundtrip': True,
                'exact_geometry_certificate': cert, 'sources': [],
                'active_join_compatibility': 'not assessed; composition must verify actual joins'}
        records[name]['sources'].append({'device': device, 'initial_bloat': old,
            'gain_from_device_initial': old-f})
    per_device[str(device)] = {'certified_variants': len(poses), 'strict_variants_vs_device_initial': improved_device,
        'initial_bank_label': manifest['device_configs'][str(device)]['initial_bank_label']}
strict, best = {}, {}
for name, q in all_poses.items():
    rec = records[name]
    if rec['gain_from_original'] > 2e-7:
        strict[name] = q
    key = rec['key']
    if key not in best or rec['bloat'] < records[best[key]]['bloat']:
        best[key] = name
atom_npz('artifacts/campaign_gadgets.npz', all_poses)
atom_npz('artifacts/campaign_strict_gadgets.npz', strict)
atom_npz('artifacts/campaign_best_gadgets.npz', {key: all_poses[name] for key, name in best.items()})
atomic_json('ftmc_candidates.json', records)
summary = {'stage': 'failed' if failures else 'complete', 'wall_seconds': time.monotonic()-started,
    'parallel_search_wall_seconds': time.monotonic()-worker_started, 'bounded_worker_timeout': timed_out,
    'failures': failures, 'candidate_variants': len(all_poses), 'strict_variants_vs_original': len(strict),
    'best_by_key': {key: {'variant': name, 'bloat': records[name]['bloat'],
        'gain_from_original': records[name]['gain_from_original']} for key, name in best.items()},
    'per_device': per_device, 'status': statuses, 'funnels': funnels, 'refill_budgets': budgets,
    'certificate_binding_checks': binding_checks, 'preflight': preflight,
    'campaign_archive_sha256': hashlib.sha256(Path('artifacts/campaign_gadgets.npz').read_bytes()).hexdigest(),
    'note': 'Rectangle gains require full-puzzle composition. Exact post-gate certificates reused by byte identity; final full CSV needs independent raw and roundtrip validation.'}
atomic_json('ftmc_summary.json', summary)
signal.alarm(0)
print(json.dumps(summary), flush=True)
if failures:
    raise RuntimeError('Combined worker failure; successful immutable archives retained')
