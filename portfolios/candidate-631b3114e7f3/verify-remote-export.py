from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil,sys
R=Path('/workspace/squares_in_squares');sys.path.insert(0,str(R/'scripts'))
from submission_scheduler import KaggleGateway
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest,ApiGetKernelSessionStatusRequest
j=R/'artifacts/portfolio-631b3114e7f3-incremental-export-job';d=R/'artifacts/portfolio-631b3114e7f3-incremental-export-results-v1';r=R/'portfolios/candidate-631b3114e7f3';ref='sos54352/squares-portfolio-631b3114e7f3-incremental'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
m=json.loads((j/'export_manifest.json').read_bytes());build=json.loads((j/'build_report.json').read_bytes());runtime=json.loads((d/'outputs/incremental_export_proof.json').read_bytes());receipt=json.loads((d/'download-receipt.json').read_bytes())
assert receipt['status']=='complete' and receipt['private_source_verified'] and not receipt['enable_gpu'] and receipt['version']==1
assert sha(j/'export.py')==build['script_sha256']==receipt['source_sha256']
assert sha(d/'outputs/submission.csv')==m['csv_sha256']==runtime['csv_sha256'];assert (d/'outputs/submission.csv').read_bytes()==(R/'artifacts/submission-fq-lp100-final-v1-safe.csv').read_bytes();assert (d/'outputs/export_manifest.json').read_bytes()==(j/'export_manifest.json').read_bytes();assert runtime['status']=='complete' and not runtime['transport_scaling_applied'] and runtime['fresh_geometry_evaluations']==0
with KaggleGateway()as g:
 owner,slug=ref.split('/');api=g.client.kernels.kernels_api_client;q=ApiGetKernelRequest();q.user_name=owner;q.kernel_slug=slug;q.version_label='v1';k=api.get_kernel(q)
 assert k.metadata.current_version_number==1 and k.metadata.is_private and not k.metadata.enable_gpu and not k.metadata.enable_tpu and not k.metadata.enable_internet
 assert list(k.metadata.competition_data_sources)==['squares-in-squares']
 assert list(k.metadata.kernel_data_sources)==['sos54352/squares-portfolio-fb3d0bae17af-incremental']
 assert hashlib.sha256(k.blob.source.encode()).hexdigest()==build['script_sha256']
 q=ApiGetKernelSessionStatusRequest();q.user_name=owner;q.kernel_slug=slug;q.version_label='v1';status=api.get_kernel_session_status(q).status.name;assert status=='COMPLETE',status
verification=dict(ref=ref,version=1,status=status,is_private=True,enable_gpu=False,enable_tpu=False,enable_internet=False,competition_sources=['squares-in-squares'],kernel_sources_actual=list(k.metadata.kernel_data_sources),source_sha256=build['script_sha256'],verified_at=datetime.now(timezone.utc).isoformat())
save(j/'remote-source-verification.json',verification)
review=j/'independent_export_review.json';assert review.exists()
proof=dict(ref=ref,version=1,output_file='submission.csv',output_sha256=m['csv_sha256'],output_bytes=m['csv_bytes'],status='complete',is_private=True,verified_at=datetime.now(timezone.utc).isoformat(),enable_gpu=False,enable_tpu=False,enable_internet=False,competition_sources=['squares-in-squares'],kernel_sources_actual=verification['kernel_sources_actual'],source_sha256=build['script_sha256'],source_bytes=build['script_bytes'],server_timeout_seconds=180,worker_timeout_seconds=120,remote_runtime_seconds=runtime['seconds'],competition_submission_performed=False,transport_scaling_applied=False,remote_export_manifest_sha256=sha(d/'outputs/export_manifest.json'),remote_runtime_proof_sha256=sha(d/'outputs/incremental_export_proof.json'),download_receipt_sha256=sha(d/'download-receipt.json'),remote_source_verification_sha256=sha(j/'remote-source-verification.json'),local_runtime_proof_sha256=sha(j/'local-runtime/incremental_export_proof.json'),canonical_transport_proof_sha256=sha(r/'transport-validation.json'),additional_source_provenance_sha256=m['additional_source_provenance_sha256'],independent_source_review_sha256=sha(review),exact_source_notices_preserved=True,fresh_geometry_evaluations_by_exporter=0,parent_notebook=m['parent_notebook'],parent_csv_sha256=m['parent_csv_sha256'],parent_remote_completion_sha256=m['parent_remote_completion_sha256'],official_score=m['official_score'],roundtrip_score=json.loads((r/'roundtrip-official.json').read_bytes())['score'],threshold_eligible=True)
assert proof['official_score']<22.3 and proof['roundtrip_score']<22.3
for p in (j,d,r):save(p/'completion-proof.json',proof)
for src,name in [(d/'outputs/incremental_export_proof.json','remote-runtime-proof.json'),(d/'download-receipt.json','download-receipt.json'),(j/'remote-source-verification.json','remote-source-verification.json'),(review,'independent_export_review.json')]:shutil.copyfile(src,r/name)
recipe=json.loads((r/'recipe.json').read_bytes());recipe.update(status='Private CPU version1 COMPLETE and remotely verified; competition attached; no submission by exporter',completion_proof_sha256=sha(r/'completion-proof.json'));save(r/'recipe.json',recipe)
shutil.copyfile(__file__,r/'verify-remote-export.py')
print(json.dumps(proof,indent=2));print('completion_proof_sha256',sha(r/'completion-proof.json'))
