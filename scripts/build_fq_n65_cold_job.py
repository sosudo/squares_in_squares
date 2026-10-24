#!/usr/bin/env python3
"""Freeze the separate bounded n65 cold-chain pilot; never launch it.

All original numerical code, native binary and dependency notices come from
the exact reviewed paired payload. Only inactive root fixture data is removed.
The new driver and finishing policy are independently hash-pinned additions.
Kaggle's supported NvidiaTeslaT4 shape allocates two GPUs; this pilot uses
device zero and accounts for both allocated devices in its resource manifest.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import zipfile

import numpy as np

from build_fq_fused_hop_job import add_local_import_closure, unpack


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'artifacts/fq-restart-hop-job-v2/search.py'
PARENT_SHA = 'd350aebf10c9bcd07eab3088fd33778cb2e9b55e114eb95bbf0b51a9883f070f'
COLD_PARENT = ROOT/'artifacts/fq-cold-transfer-job-v1/search.py'
COLD_PARENT_SHA = '34ea1497cf6e24560eff8da939b3288b08029519640ba1eb8907acc1353d1292'
BINARY_SHA = '10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
METRIC_SHA = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'
ENTRYPOINT = 'experiments/fq_n65_cold_pilot.py'
FINISH_SOURCE = 'experiments/fq_n65_cold_finish.py'
REMOVED_DATA = ('pilot-inputs.npz', 'pilot-config.json', 'hop-config.json',
                'restart-inputs.npz', 'restart-config.json', 'restart-input-proof.json')
INPUT_NAMES = ('n65-cold-config.json', 'n65-cold-inputs.npz', 'n65-cold-input-proof.json')
LOCAL_AUDIT_LEDGER = 'proofs/01-records.json'
SHAPE = 'NvidiaTeslaT4'
SHAPE_EVIDENCE = {
    'package': 'kaggle', 'version': '2.2.5', 'path': 'kaggle/cli.py',
    'sha256': '4a349f0cf2a8f2d622d73fa02b907a3d9baca6182c1cfb6b616ba13a4da2421b',
    'documented_shape': "'NvidiaTeslaT4' for GPU T4 x2",
    'single_t4_shape_found': False,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def _pinned_source(path, expected, name):
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError('An explicit reviewed SHA256 is required for '+name)
    data = path.read_bytes()
    if sha(data) != expected:
        raise ValueError('Reviewed new source changed: '+name)
    compile(data, name, 'exec')
    return data


def validate_inputs(config_bytes, inputs, proof_bytes):
    """Check the exact finite n65 inputs and authorized numerical/resource caps."""
    config = json.loads(config_bytes)
    proof = json.loads(proof_bytes)
    if sha(inputs) != config['inputs_sha256'] or sha(inputs) != proof['inputs_sha256']:
        raise ValueError('Exact n65 input archive differs')
    if set(config['cases']) != {'65'} or set(proof['cases']) != {'65'}:
        raise ValueError('Only the authorized n65 case is permitted')
    case = config['cases']['65']
    record = proof['cases']['65']
    if not (case['n'] == 65 and case['device'] == 0
            and case['source_key'] == record['reference_key']
            and case['source_geometry_sha256'] == record['reference_geometry_sha256']
            and str(case['reference_side']) == str(record['reference_side'])):
        raise ValueError('n65 current-reference binding differs')
    sources = case['source_keys']
    if not (len(sources) == 16 and len(set(sources)) == 16 and sources == record['source_keys']
            and case['source_key'] not in sources
            and set(proof['arrays']) == set(sources) | {case['source_key']}):
        raise ValueError('Expected exactly sixteen bound initializer groups and one separate current reference')
    if not (config['search_seconds'] == 300 and config['cooling_seconds'] == 100
            and config['chains'] == 32 and config['temperature'] == .3
            and config['quench_steps'] == 2000 and config['cuts'] == [.0005, .002]
            and config['amplitudes'] == [1.] and config['seed'] == 116506501
            and config['finish_native_seconds'] == 60 and config['finish_certificate_seconds'] == 8
            and config['finish_workers_per_case'] == 4 and config['finish_slots_per_case'] == 8
            and config['max_packets'] == 2000 and config['max_bytes'] == 2*1024**3
            and config['cuda_options'] == ['--std=c++17', '--fmad=false']):
        raise ValueError('Unreviewed n65 numerical or resource configuration')
    if 'baseline' in config and config['baseline'] != proof['baseline']:
        raise ValueError('Configuration and proof baseline differ')
    if set(proof['input_certificates']) != set(proof['arrays']):
        raise ValueError('All seventeen exact inputs require fresh full certificates')
    with np.load(io.BytesIO(inputs), allow_pickle=False) as archive:
        if set(archive.files) != set(proof['arrays']):
            raise ValueError('Input array inventory differs')
        for name in archive.files:
            value = archive[name]
            bound = proof['arrays'][name]
            if not (value.shape == (65, 3) and list(value.shape) == bound['shape']
                    and value.dtype == np.dtype('<f8') and value.dtype.str == bound['dtype']
                    and sha(value.tobytes()) == bound['sha256'] and np.isfinite(value).all()):
                raise ValueError('Exact full-65 input geometry differs: '+name)
            certificate_record = proof['input_certificates'][name]
            certificate = certificate_record['certificate']
            shared = certificate['shared_official_gate']
            if not (certificate_record['geometry_sha256'] == bound['sha256']
                    and certificate['valid'] is True and shared['valid'] is True
                    and shared['metric_sha256'] == METRIC_SHA
                    and shared['raw_reason'] == shared['roundtrip_reason'] == 'ok'
                    and certificate['ordinary_pandas_official_reason'] == 'ok'
                    and certificate['independent_raw']['valid'] is True
                    and certificate['independent_roundtrip']['valid'] is True
                    and certificate['independent_raw']['n'] == certificate['independent_roundtrip']['n'] == 65):
                raise ValueError('Exact n65 certificate binding or full gate differs: '+name)
        if case['source_key'] not in archive.files:
            raise ValueError('Current reference missing from frozen arrays')
        if sha(archive[case['source_key']].tobytes()) != case['source_geometry_sha256']:
            raise ValueError('Current reference array hash differs')
    return config, proof


def retain_source_evidence(files, proof_path, proof):
    """Verify all evidence; transport all except the authorized full audit ledger.

    The complete historical ledger exceeds Kaggle's source cap. Its exact
    selected fifteen records already appear inside retained lineage.json; those
    records are compared with the full local ledger before omitting transport.
    The immutable input proof and its full source inventory remain unchanged.
    """
    root = proof_path.parent/'source-evidence'
    expected = proof['retained_source_evidence']
    if not isinstance(expected, dict) or not expected:
        raise ValueError('A complete retained seed evidence inventory is required')
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Expected a real retained seed evidence directory')
    paths = list(root.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise ValueError('Symlinks are not accepted in retained source evidence')
    actual = {path.relative_to(root).as_posix(): path for path in paths if path.is_file()}
    if set(actual) != set(expected):
        raise ValueError('Retained seed evidence inventory differs')
    added = {}
    omitted = {}
    for relative, digest in sorted(expected.items()):
        data = actual[relative].read_bytes()
        if sha(data) != digest:
            raise ValueError('Retained seed evidence hash differs: '+relative)
        if relative == LOCAL_AUDIT_LEDGER:
            ledger = json.loads(data)
            lineage = json.loads(actual['lineage.json'].read_bytes())
            by_key = {row['key']: row for row in lineage}
            selected = []
            for key in proof['cases']['65']['source_keys'][:15]:
                source_key = proof['bindings'][key]['source_key']
                row = by_key[source_key]
                index = row['audit_record_index']
                if not (len(ledger) == 5465 and isinstance(index, int) and 0 <= index < len(ledger)
                        and row['audit_record'] == ledger[index]
                        and ledger[index]['geometry_sha256'] == proof['arrays'][key]['sha256']
                        and row['geometry_sha256'] == proof['arrays'][key]['sha256']):
                    raise ValueError('Selected seed lineage differs from full historical ledger: '+key)
                selected.append({'input_key': key, 'source_key': source_key,
                                 'audit_record_index': index, 'geometry_sha256': row['geometry_sha256']})
            omitted[relative] = dict(
                sha256=digest, bytes=len(data), local_path=str(actual[relative]),
                complete_local_inventory_verified=True, selected_exact_record_count=len(selected),
                selected_records_carried_in='provenance/n65-seeds/lineage.json', selected_records=selected,
                rationale='Complete 5465-array audit ledger remains local and immutable. Its exact fifteen selected source records are carried unchanged in lineage.json, alongside the coarse-group summary, all licenses and seventeen fresh full certificates. Only this ledger is omitted from remote transport to meet the one-million-byte source limit.')
            continue
        name = 'provenance/n65-seeds/'+relative
        if name in files:
            raise ValueError('Retained evidence destination already exists: '+name)
        files[name] = data
        added[name] = digest
    return added, omitted


def _check_imports(files, available):
    additions = add_local_import_closure(files, available)
    if add_local_import_closure(dict(files), available):
        raise ValueError('Import closure incomplete')
    for name, data in files.items():
        if name.endswith('.py'):
            compile(data, name, 'exec')
            for node in ast.walk(ast.parse(data)):
                modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                           else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                for module in modules:
                    relative = module.replace('.', '/')+'.py'
                    candidates = [str(Path(name).parent/relative), 'experiments/'+relative,
                                  'scripts/'+relative, 'public_solver/'+relative, relative]
                    if not any(p in files for p in candidates) and any((ROOT/p).is_file() for p in candidates):
                        raise ValueError('Unfrozen local import: '+name+' -> '+module)
        if b'KGAT_' in data:
            raise ValueError('Credential-shaped bytes forbidden')
    return additions


def supervisor_source(source):
    supervisor = source.decode().split('\n', 2)[2]
    replacements = {
        "'experiments/fq_restart_hop_pilot.py'": repr(ENTRYPOINT),
        'worker.wait(timeout=850)': 'worker.wait(timeout=570)',
        'signal.alarm(895)': 'signal.alarm(595)',
    }
    for old, new in replacements.items():
        if supervisor.count(old) != 1:
            raise ValueError('Ambiguous supervisor entrypoint or process bound: '+old)
        supervisor = supervisor.replace(old, new, 1)
    compile(supervisor, '<n65 supervisor>', 'exec')
    return supervisor, replacements


def build(args):
    if args.out.exists():
        raise ValueError('Use a fresh source freeze directory')
    entrypoint = Path(args.entrypoint)
    entrypoint = entrypoint if entrypoint.is_absolute() else ROOT/entrypoint
    if entrypoint.resolve() != (ROOT/ENTRYPOINT).resolve():
        raise ValueError('Only the exact n65 pilot entrypoint is permitted')
    source, parent, files = unpack(PARENT, PARENT_SHA, 'xz85')
    _, _, cold_files = unpack(COLD_PARENT, COLD_PARENT_SHA, 'xz85')
    for name in set(files) & set(cold_files):
        if files[name] != cold_files[name]:
            raise ValueError('Conflicting immutable cold dependency: '+name)
    original = {name: sha(data) for name, data in files.items()}
    removed = {name: {'sha256': sha(files[name]), 'bytes': len(files[name])} for name in REMOVED_DATA}
    for name in REMOVED_DATA:
        del files[name]
    if sha(files['bin/fq']) != BINARY_SHA:
        raise ValueError('Frozen native executable differs')
    config_bytes = args.config.read_bytes()
    inputs = args.inputs.read_bytes()
    proof_bytes = args.input_proof.read_bytes()
    config, proof = validate_inputs(config_bytes, inputs, proof_bytes)
    files.update(dict(zip(INPUT_NAMES, (config_bytes, inputs, proof_bytes))))
    files[ENTRYPOINT] = _pinned_source(entrypoint, args.entrypoint_sha256, ENTRYPOINT)
    files[FINISH_SOURCE] = _pinned_source(ROOT/FINISH_SOURCE, args.finish_sha256, FINISH_SOURCE)
    preparation = args.preparation_source.read_bytes()
    if sha(preparation) != proof['preparation_source_sha256']:
        raise ValueError('Frozen input preparation source differs')
    files['provenance/prepare-n65-cold-inputs.py'] = preparation
    seed_evidence, omitted_evidence = retain_source_evidence(files, args.input_proof, proof)
    dependencies = _check_imports(files, cold_files)
    for name, digest in original.items():
        if name not in REMOVED_DATA and sha(files[name]) != digest:
            raise ValueError('Reviewed numerical/source/native/notice bytes changed: '+name)
    supervisor, replacements = supervisor_source(source)
    manifest = dict(
        kind='Independent persistent cold full-n65 pilot; 32 chains on device zero',
        parent_source_sha256=PARENT_SHA, native_binary_sha256=BINARY_SHA,
        frozen_cold_dependency_parent_sha256=COLD_PARENT_SHA,
        frozen_dependency_additions={name: sha(files[name]) for name in dependencies},
        original_file_inventory_sha256=sha(json.dumps(original, sort_keys=True, separators=(',', ':')).encode()),
        original_file_count=len(original), preserved_original_file_count=len(original)-len(removed),
        replaced_inactive_root_data=removed,
        data_replacement_scope='Only unused original root fixtures removed; every original numerical/source/native/license byte remains exact.',
        files={name: sha(data) for name, data in files.items()}, configuration=config,
        input_proof_sha256=sha(proof_bytes), builder_sha256=sha(Path(__file__).read_bytes()),
        retained_seed_evidence=seed_evidence,
        local_only_seed_evidence=omitted_evidence,
        exact_entrypoint=ENTRYPOINT, entrypoint_sha256=sha(files[ENTRYPOINT]),
        finish_source_sha256=sha(files[FINISH_SOURCE]), transitive_dependency_additions=dependencies,
        supervisor_delta=replacements, parent_worker_seconds=560, worker_seconds=570,
        parent_alarm_seconds=595, whole_seconds=600, server_timeout_seconds=720,
        devices_used=1, used_device_indices=[0], devices_allocated=2, machine_shape=SHAPE,
        accelerator_shape_evidence=SHAPE_EVIDENCE,
        allocated_gpu_seconds_budget=1200, server_fail_safe_allocated_gpu_seconds=1440,
        accelerator_accounting='NvidiaTeslaT4 is documented as T4 x2 by the installed Kaggle CLI. No supported single-T4 shape was found; count both allocated devices despite using only device zero.',
        finish_cpu_workers=4, finish_slots_cap=8, native_seconds_per_slot=60,
        certificate_seconds_per_slot=8, no_submission=True,
        native_dependency_license_count=parent['native_dependency_license_count'],
        licenses='All exact original GPU/native source and dependency notices retained.')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            # Fixed timestamps make repeat freezes of the same inputs reproducible.
            archive.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), data)
    payload = base64.b85encode(lzma.compress(stream.getvalue(), preset=9)).decode()
    frozen = 'CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(payload)+'\n'+supervisor
    compile(frozen, 'search.py', 'exec')
    frozen_bytes = frozen.encode()
    if len(frozen_bytes) >= 1_000_000:
        raise ValueError('Kaggle source limit exceeded: '+str(len(frozen_bytes)))
    metadata = dict(id=args.slug, title=args.slug.split('/')[-1].replace('-', ' '),
                    code_file='search.py', language='python', kernel_type='script',
                    is_private=True, enable_gpu=True, enable_tpu=False, enable_internet=False,
                    dataset_sources=[], kernel_sources=[], competition_sources=[], machine_shape=SHAPE)
    report = dict(source_sha256=sha(frozen_bytes), source_bytes=len(frozen_bytes),
                  payload_files=len(files), configuration=manifest, launched=False)
    args.out.mkdir(parents=True)
    (args.out/'search.py').write_bytes(frozen_bytes)
    save(args.out/'kernel-metadata.json', metadata)
    save(args.out/'build_report.json', report)
    print(json.dumps({key: value for key, value in report.items() if key != 'configuration'}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'inputs', 'input-proof', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--entrypoint', type=Path, default=Path(ENTRYPOINT))
    parser.add_argument('--entrypoint-sha256', required=True)
    parser.add_argument('--finish-sha256', required=True)
    parser.add_argument('--preparation-source', type=Path, required=True)
    parser.add_argument('--slug', default='sos54352/squares-n65-persistent-cold')
    build(parser.parse_args())


if __name__ == '__main__':
    main()
