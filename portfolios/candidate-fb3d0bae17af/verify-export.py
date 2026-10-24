from pathlib import Path
import hashlib,json,runpy,shutil,os,subprocess,tempfile
R=Path('/workspace/squares_in_squares');j=R/'artifacts/portfolio-fb3d0bae17af-incremental-export-job';r=R/'portfolios/candidate-fb3d0bae17af'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
parent=R/'artifacts/submission-fq-timeout-all-v1-safe.csv';target=R/'artifacts/submission-fq-gpu-polish-final-v1-safe.csv'
out=j/'local-runtime';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='exact-safe-mount-')as tmp:
 mount=Path(tmp);(mount/'exact').mkdir();shutil.copyfile(parent,mount/'exact/submission.csv');(mount/'wrong').mkdir();(mount/'wrong/submission.csv').write_bytes(b'incorrect input')
 env=dict(os.environ,INCREMENTAL_INPUT_ROOT=str(mount),INCREMENTAL_OUTPUT_ROOT=str(out));env.pop('INCREMENTAL_PARENT_PATH',None)
 proc=subprocess.run([str(R/'.venv/bin/python'),str(j/'export.py')],env=env,capture_output=True,text=True,timeout=120,check=True)
 (j/'local-execution.stdout').write_text(proc.stdout);(j/'local-execution.stderr').write_text(proc.stderr)
assert (out/'submission.csv').read_bytes()==target.read_bytes()
assert (out/'export_manifest.json').read_bytes()==(j/'export_manifest.json').read_bytes()
ns=runpy.run_path(str(j/'export.py'),run_name='inspection');m=json.loads((j/'export_manifest.json').read_bytes());assert ns['INCREMENTAL_MANIFEST']==m
rejected=[]
for label,raw,payload,manifest in [('parent',parent.read_bytes()[:-1]+b'X',ns['INCREMENTAL_PATCH'],m),('patch',parent.read_bytes(),'!'+ns['INCREMENTAL_PATCH'][1:],m)]:
 try:ns['apply_safe_row_patch'](raw,payload,manifest)
 except ValueError:rejected.append(label)
 else:raise AssertionError('tamper accepted '+label)
assert rejected==['parent','patch']
old=json.loads((R/'portfolios/candidate-680e332bc6bc/export_manifest.json').read_bytes());add=m['additional_source_provenance'];assert add['inherited_parent_additional_provenance']==old['additional_source_provenance'];assert add['inherited_parent_additional_provenance_sha256']==old['additional_source_provenance_sha256']
metadata=json.loads((j/'kernel-metadata.json').read_bytes());assert metadata['competition_sources']==['squares-in-squares'];assert metadata['kernel_sources']==['sos54352/squares-portfolio-680e332bc6bc-incremental/1']
proof=dict(status='passed',source_sha256=sha(j/'export.py'),source_bytes=(j/'export.py').stat().st_size,csv_sha256=sha(target),csv_bytes=target.stat().st_size,full_executable_reconstruction_exact=True,manifest_exact=True,parent_additional_provenance_exact=True,wrong_content_mount_ignored=True,runtime_scaling=False,actual_generated_source_tamper_rejections=rejected,wrapper_sha256=sha(R/'scripts/build_incremental_safe_export_from_680e.py'),base_builder_sha256=sha(R/'scripts/build_incremental_safe_export_job.py'),local_runtime_proof_sha256=sha(out/'incremental_export_proof.json'),check_source_sha256=sha(__file__))
save(j/'local_verification.json',proof)
for name in ('export.py','incremental_loader.py','export_manifest.json','build_report.json','kernel-metadata.json','local_verification.json','wrapper-proof.json'):shutil.copyfile(j/name,r/name)
shutil.copyfile(out/'incremental_export_proof.json',r/'local-runtime-proof.json');shutil.copyfile(__file__,r/'verify-export.py');shutil.copyfile(R/'scripts/build_incremental_safe_export_from_680e.py',r/'builder-wrapper.py')
print(json.dumps(proof,indent=2))
