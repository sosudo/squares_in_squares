#!/usr/bin/env python3
"""Assemble an immutable private fixture upload; no network calls."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from build_rectangular_persistent_job import validate_fixture

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')

def prepare(args):
 if args.out.exists():raise ValueError('Fresh immutable dataset staging directory required')
 config,proof=validate_fixture(args.inputs)
 args.out.mkdir(parents=True);local=args.out/'local-fixture';shutil.copytree(args.inputs,local)
 extras=[]
 for path in args.extra_evidence:
  if not path.is_file():raise ValueError('Additional evidence must be an exact file')
  dst=local/'additional-provenance'/path.name
  if dst.exists():raise ValueError('Conflicting evidence filenames')
  dst.parent.mkdir(exist_ok=True);shutil.copyfile(path,dst);extras.append(dict(source=str(path),path=str(dst.relative_to(local)),sha256=sha(dst)))
 for directory in args.extra_directory:
  if not directory.is_dir():raise ValueError('Additional evidence directory missing')
  for path in sorted(directory.rglob('*')):
   if not path.is_file()or '__pycache__'in path.parts:continue
   dst=local/'additional-provenance'/directory.name/path.relative_to(directory)
   if dst.exists():raise ValueError('Conflicting evidence path')
   dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dst);extras.append(dict(source=str(path),path=str(dst.relative_to(local)),sha256=sha(dst)))
 ref=args.ref or 'sos54352/squares-rectangle-fixtures-'+config['inputs_sha256'][:12]
 if len(ref.split('/'))!=2 or any(c in ref for c in '?&#'):raise ValueError('Private owner/slug required')
 files={str(p.relative_to(local)):dict(sha256=sha(p),bytes=p.stat().st_size)for p in sorted(local.rglob('*'))if p.is_file()}
 manifest=dict(ref=ref,version=1,is_private_required=True,inputs_sha256=config['inputs_sha256'],input_proof_sha256=sha(local/'rectangular-input-proof.json'),
  input_config_sha256=sha(local/'rectangular-input-config.json'),files=files,additional_evidence=extras,preparer_sha256=sha(__file__),
  license_scope='Inherited source-specific terms, all exact notices retained. Other is not a new blanket license.',no_upload=True)
 write(args.out/'fixture-manifest.json',manifest)
 upload=args.out/'upload';upload.mkdir()
 with zipfile.ZipFile(upload/'fixture.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as z:
  for name in files:z.write(local/name,name)
 metadata=dict(id=ref,title=ref.split('/')[-1].replace('-',' '),licenses=[dict(name='other')],
  description='Private immutable version1 rectangular discovery fixtures. Sixteen full-certified unit-square rectangle starts plus exact original arrays, decimal bounds, source certificates and attribution. No portfolio gain or new license grant is claimed. Source-specific mixed license texts and notices are preserved byte-for-byte in fixture.zip. No coordinate rescaling or conversion. Must remain private; no credentials, connection details or signed URLs.')
 write(upload/'dataset-metadata.json',metadata)
 write(args.out/'upload-proof.json',dict(fixture_manifest_sha256=sha(args.out/'fixture-manifest.json'),zip_sha256=sha(upload/'fixture.zip'),zip_bytes=(upload/'fixture.zip').stat().st_size,
  metadata_sha256=sha(upload/'dataset-metadata.json'),members=len(files),inputs_sha256=config['inputs_sha256'],private_create_required=True))
 print(json.dumps(dict(ref=ref,members=len(files),zip_bytes=(upload/'fixture.zip').stat().st_size,fixture_manifest_sha256=sha(args.out/'fixture-manifest.json'))))

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--ref');ap.add_argument('--extra-evidence',type=Path,action='append',default=[]);ap.add_argument('--extra-directory',type=Path,action='append',default=[]);prepare(ap.parse_args())
