import os,stat,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent
ref='sos54352/squares-rectangle-fixtures-1c2d92e19f8c'
os.environ.setdefault('KAGGLE_CONFIG_DIR','/tmp/squares-kaggle-auth')
if not os.environ.get('KAGGLE_API_TOKEN'):
 p=Path(os.environ.get('KAGGLE_TOKEN_FILE','/tmp/squares-kaggle-auth/token'))
 if stat.S_IMODE(p.stat().st_mode)&0o077:raise RuntimeError('Protected runtime authentication required')
 os.environ['KAGGLE_API_TOKEN']=p.read_text().strip()
import kagglesdk.kaggle_env as kaggle_env
kaggle_env._env_to_endpoint[kaggle_env.KaggleEnv.PROD]='https://www.kaggle.com/api'
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.datasets.types.dataset_api_service import ApiGetDatasetRequest,ApiGetDatasetStatusRequest
api=KaggleApi();api.authenticate();owner,slug=ref.split('/')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
try:
 with api.build_kaggle_client()as client:
  req=ApiGetDatasetRequest();req.owner_slug=owner;req.dataset_slug=slug
  info=client.datasets.dataset_api_client.get_dataset(req)
  req=ApiGetDatasetStatusRequest();req.owner_slug=owner;req.dataset_slug=slug
  status=client.datasets.dataset_api_client.get_dataset_status(req).status.name
 metadata=dict(ref=ref,is_private=info.is_private,current_version_number=info.current_version_number,status=status,verified_at=datetime.now(timezone.utc).isoformat())
 (root/'remote-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
 assert metadata['is_private']is True and metadata['current_version_number']==1
 if status!='READY':print(json.dumps(metadata));raise SystemExit(3)
 destination=root/'download'
 if not destination.exists():
  destination.mkdir();api.dataset_download_files(ref+'/1',path=str(destination),quiet=True,unzip=True,force=True)
 manifest=json.loads((root/'fixture-manifest.json').read_text())
 candidates=[p.parent for p in destination.rglob('rectangular-inputs.npz')if sha(p)==manifest['inputs_sha256']and all((p.parent/name).is_file()for name in manifest['files'])]
 assert len(candidates)==1;folder=candidates[0];actual={}
 for name,r in manifest['files'].items():
  path=folder/name;assert path.resolve().is_relative_to(folder.resolve())
  actual[name]=sha(path);assert actual[name]==r['sha256']and path.stat().st_size==r['bytes']
 receipt=dict(ref=ref,version=1,is_private=True,status='complete',actual_service_status=status,verified_at=datetime.now(timezone.utc).isoformat(),
  inputs_sha256=manifest['inputs_sha256'],input_proof_sha256=manifest['input_proof_sha256'],fixture_manifest_sha256=sha(root/'fixture-manifest.json'),
  downloaded_files=actual,downloaded_members=len(actual),download_directory=str(folder),remote_metadata_sha256=sha(root/'remote-metadata.json'),
  uploaded_zip_sha256=sha(root/'upload/fixture.zip'),geometry_conversions=0,competition_submission_performed=False)
 (root/'completion-proof.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(dict(ref=ref+'/1',is_private=True,status='complete',verified_members=len(actual),receipt_sha256=sha(root/'completion-proof.json'))))
except SystemExit:raise
except Exception as e:
 print(json.dumps(dict(error_type=type(e).__name__,status_code=getattr(getattr(e,'response',None),'status_code',None))),flush=True)
 raise SystemExit(1)
