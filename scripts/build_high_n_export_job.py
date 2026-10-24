#!/usr/bin/env python3
"""Package a bounded private CPU exporter for hash-pinned public crop donors."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = r'''
import base64,hashlib,io,json,os,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
working=Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()
root=Path(tempfile.mkdtemp(prefix='high-n-export-',dir=working))
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as archive:
    for name in archive.namelist():
        destination=root/name
        assert destination.resolve().is_relative_to(root.resolve())
        data=archive.read(name);assert hashlib.sha256(data).hexdigest()==CONFIG['files'][name]
        destination.write_bytes(data)
output=working/'high_n_donors.npz';report=working/'high_n_donors.source_report.json'
if output.exists() or report.exists():raise RuntimeError('Refuse to overwrite a prior donor export')
command=[sys.executable,'-u',str(root/'load_high_n_donors.py'),
         '--descriptor',str(root/'descriptor.json.zlib'),'--descriptor-sha256',CONFIG['descriptor_sha256'],
         '--validator',str(root/'validate_submission.py'),'--output',str(output),'--report',str(report),
         '--cache','/tmp/squares-high-n-certificates','--workers','3']
started=time.monotonic();summary={'configuration':CONFIG}
with (working/'high_n_export.log').open('w') as log:
    try:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=CONFIG['wall_seconds'])
        summary.update(returncode=result.returncode,timed_out=False)
    except subprocess.TimeoutExpired:
        summary.update(returncode=None,timed_out=True)
summary['seconds']=time.monotonic()-started
summary['success']=summary['returncode']==0 and not summary['timed_out'] and output.is_file() and report.is_file()
if summary['success']:
    evidence=json.loads(report.read_text())
    assert evidence['valid'] and evidence['invalid_count']==0 and evidence['donors']==CONFIG['donors']
    assert evidence['canonical_pose_sha256']==CONFIG['canonical_pose_sha256']
    actual=hashlib.sha256(output.read_bytes()).hexdigest();assert actual==evidence['archive_sha256']
    summary['archive_sha256']=actual;summary['canonical_pose_sha256']=evidence['canonical_pose_sha256']
(working/'high_n_export_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
if not summary['success']:
    print((working/'high_n_export.log').read_text(errors='replace')[-4000:])
    raise RuntimeError('Bounded public-source donor export failed')
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank',type=Path,default=ROOT/'artifacts/high-n-donors')
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts/high-n-export-job')
    parser.add_argument('--wall-seconds',type=float,default=600.)
    args=parser.parse_args()
    summary=json.loads((args.bank/'loader_descriptor.summary.json').read_text())
    payload={'descriptor.json.zlib':(args.bank/'loader_descriptor.json.zlib').read_bytes(),
             'load_high_n_donors.py':(ROOT/'experiments/load_high_n_donors.py').read_bytes(),
             'validate_submission.py':(ROOT/'scripts/validate_submission.py').read_bytes()}
    for name,data in payload.items():
        if b'KGAT_' in data:raise ValueError('Credential-shaped content in source bundle')
        if name.endswith('.py'):compile(data,name,'exec')
    if hashlib.sha256(payload['descriptor.json.zlib']).hexdigest()!=summary['compressed_sha256']:
        raise ValueError('Descriptor summary/archive mismatch')
    if hashlib.sha256(payload['validate_submission.py']).hexdigest()!=summary['validator_sha256']:
        raise ValueError('Descriptor pins a different interval validator')
    config={**summary,'wall_seconds':args.wall_seconds,
            'files':{name:hashlib.sha256(data).hexdigest()for name,data in payload.items()}}
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED)as stream:
        for name,data in payload.items():stream.writestr(name,data)
    script='CONFIG = '+repr(config)+'\nPAYLOAD = '+repr(base64.b64encode(archive.getvalue()).decode())+'\n'+RUNTIME
    compile(script,'export.py','exec')
    if len(script.encode())>=1000000:raise ValueError('Kaggle source limit exceeded')
    identifier=summary['descriptor_sha256'][:12]
    metadata={'id':'sos54352/squares-highn-'+identifier,'title':'Squares Highn '+identifier,
              'code_file':'export.py','language':'python','kernel_type':'script','is_private':True,
              'enable_gpu':False,'enable_tpu':False,'enable_internet':True,
              'dataset_sources':[],'kernel_sources':[],'competition_sources':[]}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'export.py').write_text(script)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report={'script_bytes':len(script.encode()),'script_sha256':hashlib.sha256(script.encode()).hexdigest(),
            'notebook_ref':metadata['id'],'configuration':config,'launch_performed':False}
    (args.out/'build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k!='configuration'}))


if __name__=='__main__':main()
