#!/usr/bin/env python3
"""Package a one-worker, bounded private CPU exporter for all high-n crops."""
import argparse
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = r'''
import base64,hashlib,io,json,lzma,os,signal,subprocess,sys,tempfile,time,zipfile,zlib
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
started=time.monotonic()
working=Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()
root=Path(tempfile.mkdtemp(prefix='all-high-n-source-',dir='/tmp'))
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as archive:
    assert set(archive.namelist())==set(CONFIG['files'])
    for name in archive.namelist():
        target=root/name
        assert target.resolve().is_relative_to(root.resolve())
        b=archive.read(name);assert hashlib.sha256(b).hexdigest()==CONFIG['files'][name]
        target.write_bytes(b)
packed=json.loads(lzma.decompress((root/'transport.json.xz').read_bytes()))
table=packed.pop('_angle_table')
for source in packed['sources'].values():
    source['angle_bits']={key:table[index] for key,index in source['angle_bits'].items()}
descriptor=json.dumps(packed,sort_keys=True,separators=(',',':')).encode()
assert hashlib.sha256(descriptor).hexdigest()==CONFIG['descriptor_sha256']
(root/'descriptor.json.zlib').write_bytes(zlib.compress(descriptor,9))
output=working/'all_high_n_donors.npz'
report=working/'all_high_n_donors.source_report.json'
provenance=working/'all_high_n_provenance.json.zlib'
if any(p.exists() for p in (output,report,provenance)):
    raise RuntimeError('Refuse to replace prior all-high-n export outputs')
command=[sys.executable,'-u',str(root/'load_all_high_n_donors.py'),
    '--descriptor',str(root/'descriptor.json.zlib'),'--descriptor-sha256',CONFIG['descriptor_sha256'],
    '--cache','/tmp/squares-all-high-n-certificates','--validator',str(root/'validate_submission.py'),
    '--output',str(output),'--report',str(report),'--provenance',str(provenance)]
if CONFIG['reuse_frozen_interval_report']:
    command.extend(['--reuse-report',str(root/'frozen_interval_report.json.zlib')])
summary={'configuration':CONFIG,'workers':1}
with (working/'all_high_n_export.log').open('w') as log:
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        process.wait(timeout=max(.1,CONFIG['wall_seconds']-(time.monotonic()-started)))
        summary.update(returncode=process.returncode,timed_out=False)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL)
        process.wait(timeout=3)
        summary.update(returncode=process.returncode,timed_out=True)
summary['seconds']=time.monotonic()-started
summary['success']=summary['returncode']==0 and not summary['timed_out'] and all(p.is_file() for p in (output,report,provenance))
if summary['success']:
    evidence=json.loads(report.read_text())
    assert evidence['valid'] is True and evidence['invalid_count']==0
    assert evidence['donors']==CONFIG['donors'] and evidence['squares']==CONFIG['squares']
    assert evidence['canonical_pose_sha256']==CONFIG['canonical_pose_sha256']
    assert evidence['raw_canonical_pose_sha256']==CONFIG['raw_canonical_pose_sha256']
    assert evidence['all_export_array_hashes_match'] and evidence['all_raw_array_hashes_match']
    actual=hashlib.sha256(output.read_bytes()).hexdigest()
    assert actual==evidence['archive_sha256']
    assert hashlib.sha256(zlib.decompress(provenance.read_bytes())).hexdigest()==CONFIG['original_provenance_sha256']
    summary.update(archive_sha256=actual,canonical_pose_sha256=evidence['canonical_pose_sha256'],
        independent_interval_certified_donors=evidence['donors'],official_metric_certification_performed=False)
    summary['independent_interval_rerun_performed']=evidence['independent_interval_rerun_performed']
(working/'all_high_n_export_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
if not summary['success']:raise RuntimeError('Bounded all-high-n source export failed')
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bank', type=Path, default=ROOT/'artifacts/all-high-n-donors-v1')
    ap.add_argument('--out', type=Path, default=ROOT/'artifacts/all-high-n-export-job-v1')
    ap.add_argument('--wall-seconds', type=float, default=900.)
    ap.add_argument('--reuse-report', type=Path,
                    help='Optional completed frozen local interval report for exact-array proof reuse')
    args = ap.parse_args()
    if args.out.exists() or not 30 <= args.wall_seconds <= 1200:
        raise ValueError('Require a new bundle directory and bounded wall seconds in[30,1200]')
    summary = json.loads((args.bank/'loader_descriptor.summary.json').read_text())
    data = (args.bank/'loader_descriptor.json').read_bytes()
    if hashlib.sha256(data).hexdigest() != summary['descriptor_sha256']:
        raise ValueError('Descriptor bytes changed')
    packed = json.loads(data)
    table = sorted({bits for source in packed['sources'].values() for bits in source['angle_bits'].values()})
    lookup = {bits: i for i, bits in enumerate(table)}
    for source in packed['sources'].values():
        source['angle_bits'] = {k: lookup[bits] for k, bits in source['angle_bits'].items()}
    packed['_angle_table'] = table
    transport = lzma.compress(json.dumps(packed, separators=(',', ':'), sort_keys=True).encode(), preset=9)
    payload = {'transport.json.xz': transport,
        'load_all_high_n_donors.py': (ROOT/'experiments/load_all_high_n_donors.py').read_bytes(),
        'load_high_n_donors.py': (ROOT/'experiments/load_high_n_donors.py').read_bytes(),
        'validate_submission.py': (ROOT/'scripts/validate_submission.py').read_bytes()}
    if args.reuse_report:
        evidence_bytes = args.reuse_report.read_bytes()
        evidence = json.loads(evidence_bytes)
        if (evidence.get('valid') is not True or evidence.get('status') != 'complete'
                or evidence.get('independent_interval_certification') is not True
                or evidence.get('invalid_count') != 0
                or evidence.get('canonical_pose_sha256') != summary['canonical_pose_sha256']
                or evidence.get('validator_sha256') != summary['validator_sha256']
                or len(evidence.get('validation', {})) != summary['donors']):
            raise ValueError('Local interval report does not bind completed full bank')
        payload['frozen_interval_report.json.zlib'] = zlib.compress(evidence_bytes, 9)
    if hashlib.sha256(payload['validate_submission.py']).hexdigest() != summary['validator_sha256']:
        raise ValueError('Interval validator differs from prepared descriptor')
    for name, value in payload.items():
        if b'KGAT_' in value:
            raise ValueError('Credential-shaped content in export payload')
        if name.endswith('.py'):
            compile(value, name, 'exec')
    config = {**summary, 'wall_seconds': args.wall_seconds,
        'reuse_frozen_interval_report': bool(args.reuse_report),
        'transport_compressed_bytes': len(transport), 'unique_angle_bitpatterns': len(table),
        'runtime_sha256': hashlib.sha256(RUNTIME.encode()).hexdigest(),
        'files': {k: hashlib.sha256(v).hexdigest() for k, v in payload.items()}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in payload.items():
            z.writestr(name, value)
    script = 'CONFIG = '+repr(config)+'\nPAYLOAD = '+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+RUNTIME
    compile(script, 'export.py', 'exec')
    if len(script.encode()) >= 1000000:
        raise ValueError('Kaggle source limit exceeded: '+str(len(script.encode())))
    slug = 'sos54352/squares-all-highn-'+summary['descriptor_sha256'][:12]
    metadata = {'id': slug, 'title': 'Squares All Highn '+summary['descriptor_sha256'][:12],
        'code_file': 'export.py', 'language': 'python', 'kernel_type': 'script',
        'is_private': True, 'enable_gpu': False, 'enable_tpu': False, 'enable_internet': True,
        'dataset_sources': [], 'kernel_sources': [], 'competition_sources': []}
    args.out.mkdir(parents=True)
    (args.out/'export.py').write_text(script)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    report = {'notebook_ref': slug, 'script_bytes': len(script.encode()),
        'script_sha256': hashlib.sha256(script.encode()).hexdigest(), 'configuration': config,
        'launch_performed': False}
    (args.out/'build_report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'configuration'}), flush=True)


if __name__ == '__main__':
    main()
