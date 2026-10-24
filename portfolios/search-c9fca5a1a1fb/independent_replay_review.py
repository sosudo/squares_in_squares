"""Independent exact local checkpoint replay and evidence binding; no metrics."""
from pathlib import Path
import hashlib,importlib.util,io,json,lzma,shutil,subprocess,sys,tempfile,time
import numpy as np
ROOT=Path('/workspace/squares_in_squares');D=ROOT/'portfolios/search-c9fca5a1a1fb';OUT=Path(__file__).parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
h=lambda b:hashlib.sha256(b).hexdigest()
m=json.loads((D/'manifest.json').read_bytes())
assert sha(D/'manifest.json')=='336d74302a52df481ad786773a2cc76e367a50a8080c368c003d576ce8b63b03'
assert sha(D/'restore.py')==sha(ROOT/'scripts/local_checkpoint_bytes.py')=='f91bf9b6023090e8d50c28ef95fbf69377b4d8ad221b44b53435d6be0be24681'
assert sha(ROOT/'scripts/build_local_search_checkpoint.py')=='b4f55785271340fb19d02e73ea81b9e00a8157dacc5051ee0fcbc9f955e9928b'
assert m['kind']=='local_only_exact_byte_checkpoint'and m['no_remote_export']and m['no_queue']and m['no_submission']
assert m['user_submission_threshold']=='22.24'and not m['eligible_under_user_policy']
assert len(m['files'])==1560 and len(m['evidence'])==1555
for name,b in m['files'].items():
 p=(D/name).resolve();assert p.is_relative_to(D)and not p.is_symlink()
 assert sha(p)==b['sha256']and p.stat().st_size==b['bytes'],name
def evidence(name):
 b=m['evidence'][name];p=D/b['stored_path'];raw=p.read_bytes()
 if b['compression']=='xz':raw=lzma.decompress(raw)
 else:assert b['compression']=='none'
 assert len(raw)==b['bytes']and h(raw)==b['sha256'],name
 return raw
for name in m['evidence']:evidence(name)
for name,b in m['parent_recipe_references'].items():assert sha(ROOT/name)==b['sha256']and (ROOT/name).stat().st_size==b['bytes']
pointer=json.loads((D/'canonical-pointer.json').read_bytes());assert sha(D/'canonical-pointer.json')==m['canonical_pointer_sha256']
policy=json.loads(evidence('artifacts/submissions/authorization-policy.json'))
assert policy['submission_score_must_be_strictly_below']=='22.24'and policy['strict_improvement_required']and policy['minimum_interval_seconds']==3600
assert h(evidence('artifacts/submissions/authorization-policy.json'))==m['policy_sha256']==pointer['authorization_policy']['sha256']
proofname=Path(pointer['canonical_proof']).relative_to(ROOT).as_posix();proof=json.loads(evidence(proofname));assert h(evidence(proofname))==pointer['canonical_proof_sha256']
assert proof['metric_sha256']==pointer['metric_sha256']=='312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'
for label,b in m['targets'].items():
 assert b['target_sha256']==pointer[label]['sha256']==proof[label+'_sha256']and b['official_score']==pointer[label]['score']==proof[label+'_score']
 reportname=Path(pointer[label]['official_report']).relative_to(ROOT).as_posix();report=json.loads(evidence(reportname))
 assert h(evidence(reportname))==pointer[label]['official_report_sha256']==proof[label+'_official_report_sha256']
 assert report['valid']and report['invalid_count']==0 and report['puzzles']==1000 and report['rows']==500500 and report['sha256']==b['target_sha256']and report['metric_sha256']==proof['metric_sha256']
 poses=0
for label,b in m['certified_banks'].items():
 raw=evidence(b['path']);assert h(raw)==b['sha256']
 with np.load(io.BytesIO(raw),allow_pickle=False)as z:
  assert len(z.files)==b['poses']==len(b['arrays'])
  for key,meta in b['arrays'].items():
   q=z[key];assert q.dtype.str==meta['dtype']=='<f8'and list(q.shape)==meta['shape']and h(q.tobytes())==meta['sha256']
  poses+=len(z.files)
 assert h(evidence(m['candidate_files'][label]['path']))==m['candidate_files'][label]['sha256']
assert poses==m['certified_geometry_count']==144
parent=ROOT/'artifacts/portfolio-f1b5c18e95fa-remote-results-v1/outputs/submission.csv'
assert sha(parent)==m['parent_csv_sha256']=='f1b5c18e95fa637e93795102f892a160b972ad1fa13789b2e7d737b5b44a1494'
spec=importlib.util.spec_from_file_location('independent_local_restore',D/'restore.py');codec=importlib.util.module_from_spec(spec);spec.loader.exec_module(codec)
parent_bytes=parent.read_bytes();wrong=parent_bytes[:-1]+bytes([parent_bytes[-1]^1]);negatives=[]
for label,b in m['targets'].items():
 patch=(D/b['patch_file']).read_bytes()
 for name,source,packed in [('wrong_parent',wrong,patch),('corrupted_patch',parent_bytes,patch[:-1]+bytes([patch[-1]^1])),('truncated_patch',parent_bytes,patch[:-1])]:
  try:codec.apply_patch(source,packed,b)
  except ValueError:negatives.append(label+':'+name)
  else:raise AssertionError((label,name))
with tempfile.TemporaryDirectory(prefix='independent-local-c9fca5-',dir='/tmp')as temporary:
 temp=Path(temporary);started=time.monotonic()
 command=['python','-I',str(D/'restore.py'),'--parent',str(parent),'--out',str(temp/'restored')]
 result=subprocess.run(command,capture_output=True,text=True,check=True,timeout=60)
 elapsed=time.monotonic()-started;restored=json.loads(result.stdout)
 for label,b in m['targets'].items():
  p=temp/'restored'/b['output_file'];assert p.read_bytes()==Path(b['original_path']).read_bytes()
  assert sha(p)==b['target_sha256']==restored[label]['sha256']and p.stat().st_size==b['target_bytes']
 wrongfile=temp/'wrong-parent.csv';wrongfile.write_bytes(wrong)
 failed=subprocess.run(['python','-I',str(D/'restore.py'),'--parent',str(wrongfile),'--out',str(temp/'wrong')],capture_output=True,text=True,timeout=60)
 assert failed.returncode!=0 and 'wrong_parent_bytes_or_hash'in failed.stderr and not (temp/'wrong').exists()
 (temp/'restored'/'raw.csv').write_bytes(b'preserve existing different bytes')
 failed=subprocess.run(command,capture_output=True,text=True,timeout=60)
 assert failed.returncode!=0 and 'existing_destination_differs'in failed.stderr and (temp/'restored'/'raw.csv').read_bytes()==b'preserve existing different bytes'
test=subprocess.run(['python','tests/test_local_checkpoint_bytes.py'],cwd=ROOT,capture_output=True,text=True,check=True,timeout=30)
supplemental={}
for stem in ['fq-public35-alternative-finish-v1','fq-fresh-current-alm-finish-v1']:
 source=ROOT/'artifacts/native-two-batch-independent-review-v1'/(stem+'.json');destination=D/('independent-'+stem+'.json')
 if destination.exists():assert destination.read_bytes()==source.read_bytes()
 else:shutil.copyfile(source,destination)
 supplemental[destination.name]=sha(destination)
assert sha(D/'manifest.json')=='336d74302a52df481ad786773a2cc76e367a50a8080c368c003d576ce8b63b03'
receipt=dict(status='GREEN_independent_exact_local_checkpoint',manifest_sha256=sha(D/'manifest.json'),restore_source_sha256=sha(D/'restore.py'),builder_source_sha256=sha(ROOT/'scripts/build_local_search_checkpoint.py'),owner_local_proof_sha256=sha(D/'local-proof.json'),parent_sha256=sha(parent),verified_stored_files=1560,verified_original_evidence_files=1555,verified_certified_arrays=144,target_hashes={k:v['target_sha256']for k,v in m['targets'].items()},target_bytes={k:v['target_bytes']for k,v in m['targets'].items()},actual_system_python_isolated_cli_seconds=elapsed,all_three_actual_target_bytes_exact=True,wrong_parent_cli_rejected_before_output=True,existing_different_destination_preserved=True,per_target_negative_controls=negatives,codec_unit_tests=3,codec_test_source_sha256=sha(ROOT/'tests/test_local_checkpoint_bytes.py'),supplemental_terminal_reviews=supplemental,scope='All RAW/SAFE/roundtrip bytes restored by standalone stdlib copy/literal decoder; full stored and decompressed evidence hashes checked; all144 certified arrays and source/candidate/proof bindings retained. Parent recipe inherited notices referenced by exact committed hashes. Geometry certificates reused, never rerun.',no_numerical_transform=True,no_new_certificates=True,no_optimization=True,no_network=True,no_export_or_submission=True)
(D/'independent_replay_review.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(receipt_sha256=sha(D/'independent_replay_review.json'),seconds=elapsed,files=1560,evidence=1555,poses=144)))
