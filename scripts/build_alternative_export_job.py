"""Package a bounded private CPU exporter for diverse public alternative layouts."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=r'''
import base64,hashlib,io,json,os,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
working=Path('/kaggle/working')if Path('/kaggle/working').is_dir()else Path.cwd()
root=Path(tempfile.mkdtemp(prefix='alternative-export-',dir=working))
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD)))as z:
    for name in z.namelist():
        path=root/name
        if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe bundle path')
        data=z.read(name)
        if hashlib.sha256(data).hexdigest()!=CONFIG['files'][name]:raise ValueError('Bundle file SHA mismatch')
        path.write_bytes(data)
output=working/'alternative_donors.npz';report=working/'alternative_donors.source_report.json'
if output.exists()or report.exists():raise RuntimeError('Refuse to overwrite prior donor output')
command=[sys.executable,'-u',str(root/'alternative_csv_loader.py'),'--descriptor',str(root/'descriptor.json.zlib'),
 '--descriptor-sha256',CONFIG['descriptor_sha256'],'--download','--cache','/tmp/squares-alternative-public-csvs',
 '--output',str(output),'--report',str(report),'--validator',str(root/'validate_submission.py')]
if CONFIG.get('embedded_sha256'):
    command+=['--embedded-poses',str(root/'embedded_poses.npz'),'--embedded-sha256',CONFIG['embedded_sha256']]
started=time.monotonic();summary={'configuration':CONFIG}
with (working/'alternative_export.log').open('w')as log:
    try:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=CONFIG['wall_seconds'])
        summary.update(returncode=result.returncode,timed_out=False)
    except subprocess.TimeoutExpired:summary.update(returncode=None,timed_out=True)
summary['seconds']=time.monotonic()-started
summary['success']=summary['returncode']==0 and not summary['timed_out']and output.is_file()and report.is_file()
if summary['success']:
    proof=json.loads(report.read_text())
    assert proof['valid']and proof['invalid_count']==0 and proof['donors']==CONFIG['donors']
    assert proof['all_array_hashes_match']is True
    assert proof['canonical_pose_sha256']==CONFIG['canonical_pose_sha256']
    actual=hashlib.sha256(output.read_bytes()).hexdigest();assert actual==proof['archive_sha256']
    summary.update(archive_sha256=actual,canonical_pose_sha256=proof['canonical_pose_sha256'])
(working/'alternative_export_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
if not summary['success']:
    print((working/'alternative_export.log').read_text(errors='replace')[-4000:])
    raise RuntimeError('Bounded public alternative export failed')
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bank',type=Path,default=ROOT/'artifacts/alternative-public-donors')
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/alternative-public-export-job-v1')
    ap.add_argument('--wall-seconds',type=float,default=600.)
    ap.add_argument('--embedded-poses',type=Path)
    args=ap.parse_args()
    if args.out.exists():raise ValueError('Choose a fresh immutable bundle directory')
    summary=json.loads((args.bank/'loader_descriptor.summary.json').read_text())
    descriptor=(args.bank/'loader_descriptor.json.zlib').read_bytes();d=json.loads(zlib.decompress(descriptor))
    if hashlib.sha256(zlib.decompress(descriptor)).hexdigest()!=summary['descriptor_sha256']:
        raise ValueError('Descriptor summary mismatch')
    payload={'descriptor.json.zlib':descriptor,
        'alternative_csv_loader.py':(ROOT/'experiments/alternative_csv_loader.py').read_bytes(),
        'validate_submission.py':(ROOT/'scripts/validate_submission.py').read_bytes(),
        'SOURCE_NOTICES.md':(ROOT/'vendor/notices/alternative-public-donors/SOURCE.md').read_bytes(),
        'INHERITED_KMMM_NOTICES.md':(ROOT/'vendor/notices/kmmmvs-v24/SOURCE_NOTICES.md').read_bytes(),
        'DARIUSH_DATASET_NOTICES.md':(ROOT/'vendor/notices/dariush-v11/DATASET_DESCRIPTION.md').read_bytes(),
        'LICENSE-APACHE-2.0.txt':(ROOT/'vendor/notices/alternative-public-donors/LICENSE-APACHE-2.0.txt').read_bytes()}
    if args.embedded_poses:
        payload['embedded_poses.npz']=args.embedded_poses.read_bytes()
        payload['FROZEN_POSE_PROVENANCE.json']=args.embedded_poses.with_suffix('.provenance.json').read_bytes()
    for name,data in payload.items():
        if b'KGAT_'in data:raise ValueError('Credential-shaped content in source bundle')
        if name.endswith('.py'):compile(data,name,'exec')
    if hashlib.sha256(payload['validate_submission.py']).hexdigest()!=d['validator_sha256']:
        raise ValueError('Pinned validator mismatch')
    config={**summary,'wall_seconds':args.wall_seconds,'validator_sha256':d['validator_sha256'],
        'files':{name:hashlib.sha256(data).hexdigest()for name,data in payload.items()},
        'competition_submissions_allowed':False,'purpose':'Private CPU donor export only'}
    if args.embedded_poses:
        proof=json.loads(payload['FROZEN_POSE_PROVENANCE.json'])
        actual=hashlib.sha256(payload['embedded_poses.npz']).hexdigest()
        if actual!=proof['sha256']or proof['canonical_bank_sha256']!=d['canonical_pose_sha256']:
            raise ValueError('Frozen embedded pose provenance mismatch')
        config.update(embedded_sha256=actual,embedded_donors=proof['donors'])
    identity=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:12]
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED)as z:
        for name,data in payload.items():z.writestr(name,data)
    script='CONFIG = '+repr(config)+'\nPAYLOAD = '+repr(base64.b64encode(buf.getvalue()).decode())+'\n'+RUNTIME
    compile(script,'export.py','exec')
    if len(script.encode())>=1000000:raise ValueError('Source-size limit exceeded')
    metadata={'id':'sos54352/squares-alternative-'+identity,'title':'Squares Alternative '+identity,
        'code_file':'export.py','language':'python','kernel_type':'script','is_private':True,
        'enable_gpu':False,'enable_tpu':False,'enable_internet':True,
        'dataset_sources':[],'kernel_sources':[],'competition_sources':[]}
    args.out.mkdir(parents=True)
    (args.out/'export.py').write_text(script)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report={'notebook_ref':metadata['id'],'script_bytes':len(script.encode()),
        'script_sha256':hashlib.sha256(script.encode()).hexdigest(),'configuration':config,
        'launch_performed':False,'competition_submission_performed':False}
    (args.out/'build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k!='configuration'}))

if __name__=='__main__':main()
