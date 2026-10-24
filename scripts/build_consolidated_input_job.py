#!/usr/bin/env python3
"""Package an offline CPU notebook that consolidates hash-pinned GPU inputs.

No numerical search, geometry changes, GPU launch or competition submission.
The output retains exact array values/order and original source attribution.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile


RUNTIME = r'''
import hashlib,io,json,os,shutil,subprocess,sys,tempfile,time,zipfile,base64
from pathlib import Path
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
working=Path(os.environ.get('COMPOSITION_OUTPUT_ROOT','/kaggle/working' if Path('/kaggle/working').is_dir() else str(Path.cwd())))
working.mkdir(parents=True,exist_ok=True)
def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def worker():
    import numpy as np
    started=time.monotonic()
    print(json.dumps({'stage':'consolidation_worker_started','gpu':False}),flush=True)
    with tempfile.TemporaryDirectory(prefix='composition-input-consolidation-') as temporary:
        root=Path(temporary)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as archive:
            for entry in archive.infolist():
                path=root/entry.filename
                assert path.resolve().is_relative_to(root.resolve())
                data=archive.read(entry)
                assert hashlib.sha256(data).hexdigest()==CONFIG['embedded_sha256'][entry.filename]
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        sys.path.insert(0,str(root/'pipeline'))
        from attached_composition_inputs import resolve_inputs
        resolved=resolve_inputs(CONFIG['attached_inputs'],os.environ.get('COMPOSITION_INPUT_ROOT','/kaggle/input'),root)
        print(json.dumps({'stage':'all_inputs_hash_verified','count':len(resolved['inputs'])}),flush=True)
        baseline=working/'baseline.csv';shutil.copyfile(resolved['inputs']['baseline']['path'],baseline)
        assert digest(baseline)==CONFIG['baseline_sha256']
        arrays={};records=[];canonical=hashlib.sha256()
        for label in CONFIG['attached_inputs']['gadgets']:
            item=resolved['inputs'][label]
            with np.load(item['path'],allow_pickle=False) as source:
                for key in source.files:
                    pose=np.asarray(source[key])
                    assert pose.dtype==np.float64 and pose.ndim==2 and pose.shape[1]==3
                    assert len(pose) and np.isfinite(pose).all()
                    name=f'{label}__{len(arrays):05d}__{key}'
                    array_sha=hashlib.sha256(np.asarray(pose,dtype='<f8').tobytes()).hexdigest()
                    arrays[name]=pose.copy()
                    canonical.update((name+'\0'+array_sha+'\n').encode())
                    records.append({'output_key':name,'source_label':label,'source_key':key,
                                    'source_archive_sha256':item['sha256'],'array_sha256':array_sha,
                                    'squares':len(pose)})
        assert len(arrays)==CONFIG['consolidation_expected_arrays']
        archive=working/'composition_donors.npz'
        np.savez_compressed(archive,**arrays)
        with np.load(archive,allow_pickle=False) as restored:
            assert restored.files==list(arrays)
            for record in records:
                assert hashlib.sha256(np.asarray(restored[record['output_key']],dtype='<f8').tobytes()).hexdigest()==record['array_sha256']
        proof={'baseline_sha256':digest(baseline),'archive_sha256':digest(archive),
               'canonical_array_digest':canonical.hexdigest(),'donors':len(records),
               'squares':sum(r['squares']for r in records),'seconds':time.monotonic()-started,
               'array_values_and_order_preserved':True,'fresh_geometry_evaluations':0,
               'certificate_policy':'Reuse existing per-pose source certificates only for exact array bytes; all future composed puzzles still require full certification.',
               'source_configuration':CONFIG,'resolved_source_hashes':{k:v['sha256']for k,v in resolved['inputs'].items()},
               'records':records,'competition_submission_performed':False}
        (working/'consolidation_report.json').write_text(json.dumps(proof,indent=2)+'\n')
        notices=dict(CONFIG['attached_inputs'].get('source_notices',{}))
        for name,record in CONFIG['attached_inputs'].get('source_notice_files',{}).items():
            path=(root/record['path']).resolve()
            assert path.is_relative_to(root.resolve())
            data=path.read_bytes()
            assert hashlib.sha256(data).hexdigest()==record['sha256']
            assert name not in notices
            notices[name]=data.decode('utf-8')
        (working/'source_notices.json').write_text(json.dumps(notices,indent=2)+'\n')
        print(json.dumps({k:v for k,v in proof.items()if k not in ('records','source_configuration','resolved_source_hashes')}),flush=True)
if '--worker' in sys.argv:
    worker()
else:
    started=time.monotonic();timed_out=False
    try:
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker'],timeout=300)
        code=result.returncode
    except subprocess.TimeoutExpired:
        code=-9;timed_out=True
    (working/'bounded_summary.json').write_text(json.dumps({'seconds':time.monotonic()-started,'returncode':code,'timed_out':timed_out,'worker_seconds':300,'gpu':False},indent=2)+'\n')
    if code:raise RuntimeError('Bounded CPU input consolidation did not complete')
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--extra-bank', type=Path, required=True)
    parser.add_argument('--extra-label', default='bottleneck_snapshot38')
    parser.add_argument('--expected-arrays', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--slug', required=True)
    args = parser.parse_args()
    tree = ast.parse((args.bundle / 'search.py').read_text())
    config = ast.literal_eval(tree.body[0].value)
    encoded = ast.literal_eval(tree.body[1].value)
    data = args.extra_bank.read_bytes()
    extra_sha = hashlib.sha256(data).hexdigest()
    extra_path = f'inputs/consolidation_extra/{args.extra_label}.npz'
    config['embedded_sha256'][extra_path] = extra_sha
    proof_hashes = {name: hashlib.sha256((args.extra_bank.parent / name).read_bytes()).hexdigest()
                    for name in ('analysis.json', 'results.json', 'provenance.json')
                    if (args.extra_bank.parent / name).is_file()}
    config['attached_inputs']['gadgets'][args.extra_label] = {
        'embedded_path': extra_path, 'file': args.extra_label + '.npz', 'sha256': extra_sha,
        'provenance': {'original_path': str(args.extra_bank), 'source_proof_sha256': proof_hashes,
                       'certificate_scope': 'Frozen officially raw/default-pandas certified best bank; exact values retained.'}}
    config['attached_inputs']['groups'] = {'all_certified_donors': list(config['attached_inputs']['gadgets'])}
    config['consolidation_expected_arrays'] = args.expected_arrays
    config['consolidation_parent_source_sha256'] = hashlib.sha256((args.bundle / 'search.py').read_bytes()).hexdigest()
    packed = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as old, zipfile.ZipFile(packed, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as new:
        for entry in old.infolist():
            raw = old.read(entry)
            assert hashlib.sha256(raw).hexdigest() == config['embedded_sha256'][entry.filename]
            new.writestr(entry.filename, raw)
        new.writestr(extra_path, data)
    source = 'CONFIG = ' + repr(config) + '\nPAYLOAD = ' + repr(base64.b64encode(packed.getvalue()).decode()) + '\n' + RUNTIME
    compile(source, 'export.py', 'exec')
    if len(source.encode()) >= 1_000_000:
        raise ValueError('Consolidation source exceeds Kaggle1MB limit')
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'export.py').write_text(source)
    metadata = json.loads((args.bundle / 'kernel-metadata.json').read_text())
    metadata.update(id=args.slug, title=args.slug.split('/')[-1].replace('-', ' ').title(),
                    code_file='export.py', enable_gpu=False, enable_tpu=False, enable_internet=False)
    metadata.pop('machine_shape', None)
    (args.out / 'kernel-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (args.out / 'job_manifest.json').write_text(json.dumps(config, indent=2) + '\n')
    report = {'script_sha256': hashlib.sha256(source.encode()).hexdigest(), 'script_bytes': len(source.encode()),
              'expected_arrays': args.expected_arrays, 'extra_bank_sha256': extra_sha,
              'parent_bundle': str(args.bundle), 'launch_performed': False}
    (args.out / 'build_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
