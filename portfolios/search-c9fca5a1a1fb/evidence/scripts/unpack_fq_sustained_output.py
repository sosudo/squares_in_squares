"""Verify a separately downloaded CPU extractor bundle without changing ancestry."""
import argparse,ast,hashlib,json,stat,zipfile
from pathlib import Path,PurePosixPath
PARENT='dc6950e858285433d1975f537431e375bae95584ab314807a3ae08b79baa0451'
EXTRACTOR='75f5a14ff4f1d27e923241f47ff2e9e3369423fc36aab477d63a4b5b94a12e2b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
p=argparse.ArgumentParser();p.add_argument('--download',type=Path,required=True);p.add_argument('--job',type=Path,required=True);p.add_argument('--parent-job',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
assert sha(a.job/'extract.py')==EXTRACTOR and sha(a.parent_job/'search.py')==PARENT
r=read(a.download/'download-receipt.json');assert r['source_sha256']==EXTRACTOR and r['private_source_verified'] and not r['enable_gpu'] and r['status']=='complete'
assert r['notebook']=='sos54352/squares-sustained-output-extractor' and r['version']==1
for name,row in r['files'].items():assert sha(a.download/'outputs'/name)==row['sha256']
needed=['extractor-job-manifest.json','extractor-summary.json','extracted/inventory.json','extracted/selected-output.zip']
assert set(needed)<=set(r['files'])
m=read(a.download/'outputs/extractor-job-manifest.json');expected=ast.literal_eval(ast.parse((a.job/'extract.py').read_text()).body[0].value);assert m==expected
summary=read(a.download/'outputs/extractor-summary.json');assert summary['returncode']==0 and not summary['timed_out'] and summary['gpu']==False
inventory_path=a.download/'outputs/extracted/inventory.json';inv=read(inventory_path);bundle=a.download/'outputs/extracted/selected-output.zip'
assert sha(inventory_path)==summary['inventory_sha256'] and sha(bundle)==summary['zip_sha256']==inv['zip_sha256']
assert inv['status']=='complete' and inv['parent_source_sha256']==PARENT and inv['parent_notebook']=='sos54352/squares-sustained-cold-12case/1'
assert inv['parent_manifest_sha256']==m['parent_manifest_sha256'] and inv['parent_config_sha256']==m['parent_config_sha256']
assert inv['extractor_worker_sha256']==m['worker_sha256'] and inv['extractor_builder_sha256']==m['builder_sha256']
assert inv['zip_bytes']==bundle.stat().st_size<=512*1024**2 and inv['uncompressed_bytes']<=500*1024**2
parentproof=read(a.parent_job/'remote-source-proof.json');assert parentproof['source_sha256']==PARENT and parentproof['private'] and parentproof['gpu']
completion_path=a.parent_job/'completion-status-proof.json';completion=read(completion_path)
assert completion['source_sha256']==PARENT and completion['status']=='COMPLETE'
a.out.mkdir(parents=True,exist_ok=False);files={};total=0
with zipfile.ZipFile(bundle)as z:
 assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(inv['files'])
 for name in z.namelist():
  pure=PurePosixPath(name);assert not pure.is_absolute() and '..'not in pure.parts and str(pure)==name
  info=z.getinfo(name);assert not stat.S_ISLNK(info.external_attr>>16)
  assert info.file_size==inv['files'][name]['bytes'];data=z.read(name)
  assert hashlib.sha256(data).hexdigest()==inv['files'][name]['sha256']
  total+=len(data);assert total<=500*1024**2
  dst=a.out/'outputs'/name;assert dst.resolve().is_relative_to(a.out.resolve());dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
  files[name]=dict(inv['files'][name])
assert total==inv['uncompressed_bytes'] and len(files)==inv['file_count']
assert sha(a.out/'outputs/job_manifest.json')==inv['parent_manifest_sha256'] and sha(a.out/'outputs/sustained-config.json')==inv['parent_config_sha256']
receipt=dict(kind='verified_private_cpu_extraction_chain',status='complete',parent_source_sha256=PARENT,parent_notebook=inv['parent_notebook'],extractor_source_sha256=EXTRACTOR,
 extractor_notebook=r['notebook']+'/1',extractor_download_receipt=dict(path=str((a.download/'download-receipt.json').resolve()),sha256=sha(a.download/'download-receipt.json')),
 parent_source_proof=dict(path=str((a.parent_job/'remote-source-proof.json').resolve()),sha256=sha(a.parent_job/'remote-source-proof.json')),
 parent_completion_proof=dict(path=str(completion_path.resolve()),sha256=sha(completion_path)),
 inventory=dict(path=str(inventory_path.resolve()),sha256=sha(inventory_path)),bundle=dict(path=str(bundle.resolve()),sha256=sha(bundle)),
 extractor_job=str(a.job.resolve()),parent_job=str(a.parent_job.resolve()),files=files,file_count=len(files),bytes=total,
 case_status=inv['case_status'],missing_optional=inv['missing_optional'],unpacker_sha256=sha(__file__),
 ancestry='Files were copied through a separate exact private CPU notebook; this is not a direct GPU-output download receipt.')
(a.out/'extraction-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(status='complete',files=len(files),bytes=total)))
