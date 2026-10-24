"""Freeze the two-case restart-hop experiment over exact reviewed GPU/native code.

Builds private offline source only. Never launches a notebook or submits.
"""
from __future__ import annotations
import argparse
import ast
import base64
import csv
import hashlib
import io
import json
import lzma
from pathlib import Path
import zipfile
import numpy as np
from build_fq_fused_hop_job import unpack, add_local_import_closure

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'artifacts/fq-fused-hop-job-v2/search.py'
PARENT_SHA = 'e608718a725a16fc241a5ad69f711a0533e9b5cfdb699c983d1765d36a7cf1d7'
NATIVE = ROOT/'artifacts/fq-cpu-readiness-job-v2/readiness.py'
NATIVE_SHA = 'a43315643e2e1475212d3cffbdea88e278100493e29dae2a60cb2448c0d48170'
BINARY_SHA = '10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
CASES = (453, 693)
EXTRA_DEPENDENCY = 'experiments/fq_variant_campaign.py'
EXTRA_DEPENDENCY_SHA = 'a6cc4f2b41f78350fd52fa5d8c29a44152791322000fbb007c7fea85ad8ed825'


def sha(data): return hashlib.sha256(data).hexdigest()


def write_json(path, value): path.write_text(json.dumps(value, indent=2)+'\n')


def prepare_inputs(pointer_path, out):
    if out.exists(): raise ValueError('Use a fresh input freeze directory')
    pointer_bytes = pointer_path.read_bytes(); pointer = json.loads(pointer_bytes)
    raw = Path(pointer['raw']['path']).read_bytes()
    report_bytes = Path(pointer['raw']['official_report']).read_bytes()
    independent_bytes = Path(pointer['independent_report']['path']).read_bytes()
    assert sha(raw) == pointer['raw']['sha256']
    assert sha(report_bytes) == pointer['raw']['official_report_sha256']
    assert sha(independent_bytes) == pointer['independent_report']['sha256']
    report = json.loads(report_bytes); independent = json.loads(independent_bytes)
    assert report['valid'] and independent['valid']
    assert report['sha256'] == independent['sha256'] == sha(raw)
    rows = {n: [] for n in CASES}; row_text = {n: [] for n in CASES}
    for row in csv.DictReader(io.StringIO(raw.decode('ascii'), newline='')):
        n = int(row['n'])
        if n in rows:
            assert int(row['square_id']) == len(rows[n])
            text = [row[k] for k in ('x', 'y', 'angle')]
            rows[n].append([float(x) for x in text]); row_text[n].append(text)
    bank = {}; bindings = {}; case_config = {}
    for device, n in enumerate(CASES):
        original = np.asarray(rows[n], dtype='<f8')
        assert original.shape == (n, 3) and np.isfinite(original).all()
        extent = .5*(np.abs(np.cos(original[:, 2]))+np.abs(np.sin(original[:, 2])))
        shift = np.min(original[:, :2]-extent[:, None], axis=0)
        reference = original.copy(); reference[:, :2] -= shift
        original_key, key = f'original_{n}', f'reference_{n}'
        bank[original_key] = original; bank[key] = reference
        official = next(r for r in report['results'] if r['n'] == n)
        interval = next(r for r in independent['results'] if r['n'] == n)
        bindings[str(n)] = dict(original_key=original_key, reference_key=key,
            original_geometry_sha256=sha(original.tobytes()),
            reference_geometry_sha256=sha(reference.tobytes()),
            original_coordinate_text_sha256=sha(json.dumps(row_text[n], separators=(',', ':')).encode()),
            translation_subtracted=shift.tolist(), scaling_applied=False,
            original_case_official=official, original_case_interval=interval,
            normalized_float_geometry_claim='Source-bound translation only; actual CUDA/full-shape controls remain mandatory.')
        case_config[str(n)] = dict(n=n, reference_side=str(official['side']), source_key=key,
            device=device, source_geometry_sha256=sha(reference.tobytes()))
    out.mkdir(parents=True)
    np.savez_compressed(out/'restart-inputs.npz', **bank)
    inputs_bytes = (out/'restart-inputs.npz').read_bytes()
    proof = dict(baseline=pointer['raw'], pointer_sha256=sha(pointer_bytes),
        official_report_sha256=sha(report_bytes), independent_report_sha256=sha(independent_bytes),
        inputs_sha256=sha(inputs_bytes), cases=bindings,
        arrays={k: dict(shape=list(a.shape), dtype=a.dtype.str, sha256=sha(a.tobytes())) for k, a in bank.items()},
        preparation_source_sha256=sha(Path(__file__).read_bytes()))
    config = dict(cases=case_config, inputs_sha256=sha(inputs_bytes), baseline=pointer['raw'],
        seed=94833501, search_seconds=600, cooling_seconds=150,
        max_packets=3000, max_bytes=6*1024**3, quench_steps=2000,
        cuda_options=['--std=c++17', '--fmad=false'])
    write_json(out/'restart-input-proof.json', proof)
    write_json(out/'restart-config.json', config)
    (out/'portfolio-pointer.json').write_bytes(pointer_bytes)
    print(json.dumps(dict(inputs_sha256=proof['inputs_sha256'], cases=case_config), indent=2))


def native_payload():
    source = NATIVE.read_bytes()
    if sha(source) != NATIVE_SHA: raise ValueError('Frozen native readiness source changed')
    values = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(source).body[:2]}
    with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b64decode(values['PAYLOAD'])))) as z:
        if set(z.namelist()) != set(values['CONFIG']['files']): raise ValueError('Native file inventory differs')
        files = {name: z.read(name) for name in z.namelist()}
    for name, data in files.items():
        if sha(data) != values['CONFIG']['files'][name]: raise ValueError('Native source/license hash differs')
    if sha(files['bin/fq']) != BINARY_SHA: raise ValueError('Native executable differs')
    selected = {name: data for name, data in files.items()
                if name.startswith(('vendor/', 'bin/', 'provenance/', 'controls/'))}
    return values['CONFIG'], selected


def build(args):
    if args.out.exists(): raise ValueError('Use a fresh source freeze directory')
    source, parent, files = unpack(PARENT, PARENT_SHA, 'xz85')
    original = {name: sha(data) for name, data in files.items()}
    native_config, native_files = native_payload()
    for name, data in native_files.items():
        if name in files and files[name] != data: raise ValueError('Conflicting frozen native helper: '+name)
        files[name] = data
    extra = (ROOT/'artifacts/fq-broad-contact-v1/source/fq_variant_campaign.py').read_bytes()
    if sha(extra) != EXTRA_DEPENDENCY_SHA: raise ValueError('Frozen atomic retention helper changed')
    files[EXTRA_DEPENDENCY] = extra
    config_bytes = args.config.read_bytes(); config = json.loads(config_bytes)
    input_bytes = args.inputs.read_bytes(); proof_bytes = args.input_proof.read_bytes(); proof = json.loads(proof_bytes)
    if sha(input_bytes) != config['inputs_sha256'] or sha(input_bytes) != proof['inputs_sha256']:
        raise ValueError('Exact input archive differs')
    if set(config['cases']) != {str(n) for n in CASES}: raise ValueError('Expected two authorized cases')
    for device, n in enumerate(CASES):
        row = config['cases'][str(n)]; bound = proof['cases'][str(n)]
        if (row['n'] != n or row['device'] != device or row['source_key'] != bound['reference_key']
                or row['source_geometry_sha256'] != bound['reference_geometry_sha256']
                or row['reference_side'] != str(bound['original_case_official']['side'])):
            raise ValueError('Case source/control binding differs')
    if not (config['search_seconds'] == 600 and config['cooling_seconds'] == 150
            and config['quench_steps'] == 2000 and config['max_packets'] <= 3000
            and 0 < config['max_bytes'] <= 6*1024**3
            and config['cuda_options'] == ['--std=c++17', '--fmad=false']):
        raise ValueError('Unreviewed search/resource configuration')
    with np.load(io.BytesIO(input_bytes), allow_pickle=False) as z:
        if set(z.files) != set(proof['arrays']): raise ValueError('Input inventory differs')
        for key in z.files:
            a=z[key]; record=proof['arrays'][key]
            if list(a.shape)!=record['shape'] or a.dtype.str!=record['dtype'] or sha(a.tobytes())!=record['sha256']:
                raise ValueError('Exact input geometry differs')
    for name, data in [('restart-config.json', config_bytes), ('restart-inputs.npz', input_bytes),
                       ('restart-input-proof.json', proof_bytes)]: files[name] = data
    for name in ('experiments/fq_restart_hop_pilot.py', 'experiments/fq_restart_hop_finish.py'):
        files[name] = (ROOT/name).read_bytes()
    dependency_additions = add_local_import_closure(files, native_files)
    if add_local_import_closure(dict(files), native_files): raise ValueError('Import closure incomplete')
    # A local module absent from the immutable inventory must not be mistaken
    # for an external dependency and then fail only on the remote worker.
    for name, data in files.items():
        if not name.endswith('.py'): continue
        for node in ast.walk(ast.parse(data)):
            modules = ([a.name for a in node.names] if isinstance(node, ast.Import)
                       else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for module in modules:
                relative = module.replace('.', '/')+'.py'
                paths = [str(Path(name).parent/relative), 'experiments/'+relative,
                         'scripts/'+relative, 'public_solver/'+relative, relative]
                if not any(p in files for p in paths) and any((ROOT/p).is_file() for p in paths):
                    raise ValueError('Unfrozen local import: '+name+' -> '+module)
    for name, digest in original.items():
        if sha(files[name]) != digest: raise ValueError('Reviewed parent payload mutated: '+name)
    for name, data in files.items():
        if name.endswith('.py'): compile(data, name, 'exec')
        if b'KGAT_' in data: raise ValueError('Credential-shaped bytes forbidden')
    supervisor = source.decode().split('\n', 2)[2]
    replacements = {"'experiments/fq_fused_hop_pilot.py'": "'experiments/fq_restart_hop_pilot.py'",
                    'worker.wait(timeout=300)': 'worker.wait(timeout=850)',
                    'signal.alarm(475)': 'signal.alarm(895)'}
    for old, new in replacements.items():
        if supervisor.count(old) != 1: raise ValueError('Ambiguous supervisor bound/entrypoint')
        supervisor = supervisor.replace(old, new, 1)
    # The new driver owns the two device process groups inside this one bounded child.
    manifest = dict(kind='Paired persistent versus own-best hot reset, two full cases',
        parent_source_sha256=PARENT_SHA, native_source_sha256=NATIVE_SHA, native_binary_sha256=BINARY_SHA,
        exact_preserved_parent_file_count=len(original),
        parent_file_inventory_sha256=sha(json.dumps(original, sort_keys=True, separators=(',', ':')).encode()),
        native_payload_file_count=len(native_files),
        native_file_inventory_sha256=sha(json.dumps({name:sha(data) for name,data in native_files.items()},
            sort_keys=True, separators=(',', ':')).encode()),
        additional_frozen_dependency={EXTRA_DEPENDENCY: EXTRA_DEPENDENCY_SHA},
        files={name: sha(data) for name, data in files.items()}, configuration=config,
        input_proof_sha256=sha(proof_bytes), baseline=proof['baseline'],
        builder_sha256=sha(Path(__file__).read_bytes()), transitive_dependency_additions=dependency_additions,
        supervisor_delta=replacements, worker_seconds=850, whole_seconds=900, parent_alarm_seconds=895,
        server_timeout_seconds=1200, devices_used=2, no_submission=True,
        native_dependency_license_count=native_config['dependency_license_count'],
        licenses='All exact original GPU/native source and dependency notices retained.')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, data in files.items(): z.writestr(name, data)
    encoded=base64.b85encode(lzma.compress(stream.getvalue(), preset=9)).decode()
    frozen='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(encoded)+'\n'+supervisor
    compile(frozen, 'search.py', 'exec')
    if len(frozen.encode()) >= 1_000_000: raise ValueError('Kaggle source limit exceeded: '+str(len(frozen.encode())))
    args.out.mkdir(parents=True); (args.out/'search.py').write_text(frozen)
    metadata=dict(id=args.slug, title=args.slug.split('/')[-1].replace('-', ' '), code_file='search.py',
        language='python', kernel_type='script', is_private=True, enable_gpu=True, enable_tpu=False,
        enable_internet=False, dataset_sources=[], kernel_sources=[], competition_sources=[], machine_shape='NvidiaTeslaT4')
    report=dict(source_sha256=sha(frozen.encode()), source_bytes=len(frozen.encode()), payload_files=len(files),
        configuration=manifest, launched=False)
    write_json(args.out/'kernel-metadata.json', metadata); write_json(args.out/'build_report.json', report)
    print(json.dumps({k:v for k,v in report.items() if k!='configuration'}, indent=2)); return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-inputs', action='store_true')
    parser.add_argument('--pointer', type=Path, default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--config', type=Path); parser.add_argument('--inputs', type=Path)
    parser.add_argument('--input-proof', type=Path); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--slug', default='sos54352/squares-paired-restart-hop-453-693')
    args=parser.parse_args()
    if args.prepare_inputs: prepare_inputs(args.pointer, args.out)
    else:
        if any(getattr(args, k) is None for k in ('config', 'inputs', 'input_proof')):
            parser.error('Build requires config, inputs and input-proof')
        build(args)


if __name__ == '__main__': main()
