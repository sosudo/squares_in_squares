"""One-off reviewed attachment repair; does not submit or automatically retry."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import fcntl,hashlib,json,sys
sys.path.insert(0,'scripts')
import submission_scheduler as s
SHA='ffa6cf616d4ae0fbe0f27dd655e0b31e624b7c014e82537700c71fca78eb563c'
REF='sos54352/squares-portfolio-ffa6cf616d4a-incremental'
root=Path('artifacts/submissions'); statepath=root/'scheduler-state.json'; queuepath=root/'queue.json'
completion=Path('artifacts/portfolio-ffa6cf616d4a-incremental-export-job-v2/completion-proof.json')
delta=completion.with_name('metadata_delta_proof.json')
assert s.digest(completion)=='e0abff8b8461174f37347950bf3ca258acc9433e374f56fa8b0c797aae4b6ee2'
assert s.digest(delta)=='fc40f34d27d21f272e1932fa50d3e4237d43e20b43814b9b70aa5334764c3856'
proof=json.loads(completion.read_text()); change=json.loads(delta.read_text())
assert proof['output_sha256']==SHA and proof['competition_sources']==[s.COMPETITION] and proof['version']==2
assert change['metadata_diff']=={'competition_sources':{'old':[],'new':[s.COMPETITION]}}
with statepath.with_suffix('.lock').open('a')as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 state=json.loads(statepath.read_text()); queue=json.loads(queuepath.read_text()); pending=deepcopy(state['pending'])
 assert pending['candidate']['id']==SHA and pending['candidate']['notebook']=={'ref':REF,'version':1,'output_file':'submission.csv'}
 assert pending['error_type']=='HTTPError' and SHA not in state['submitted']
 old=next(c for c in queue['candidates']if c['id']==SHA); assert old['notebook']['version']==1
 with s.KaggleGateway()as gateway:
  before=gateway.snapshot()
  def absent(snapshot):
   assert {r['ref']for r in snapshot['history']}=={57583210,57584666}
   assert all(r['status']=='complete'and pending['marker']not in r['description']for r in snapshot['history'])
   assert snapshot['limits']=={'num_today':2,'num_total':2,'num_allowed_now':8}
  absent(before)
  corrected=deepcopy(old);corrected['notebook']['version']=2
  corrected['completion']=gateway.verify_notebook(corrected['notebook'],SHA)
  s.validate_candidate(corrected)
  after=gateway.snapshot();absent(after)
 now=datetime.now(timezone.utc); assert (now-s.utc(pending['request_started_at'])).total_seconds()>=240
 evidence={'resolved_at':now.isoformat(),'resolution':'Manually inferred rejected request after repeated unchanged complete history and quota; correct missing competition attachment before a separate explicit controller execution. Original HTTP status/body were not recorded, so this is not a claimed server error message.', 'original_pending_intent':pending,'before':before,'after':after,'corrected_completion':corrected['completion'],'attachment_completion_proof':str(completion),'attachment_completion_proof_sha256':s.digest(completion),'metadata_delta_sha256':s.digest(delta),'source_and_csv_unchanged':True,'competition_submission_performed':False}
 destination=root/'ffa6cf-failed-v1-review'/'manual-attachment-recovery.json';assert not destination.exists()
 s.atomic_json(destination,evidence)
 state.setdefault('failed_attempts',[]).append({'candidate_id':SHA,'request_started_at':pending['request_started_at'],'notebook':pending['candidate']['notebook'],'error_type':pending['error_type'],'resolution_proof':str(destination),'resolution_proof_sha256':s.digest(destination)})
 state['pending']=None
 queue['candidates']=[corrected if c['id']==SHA else c for c in queue['candidates']]
 s.atomic_json(queuepath,queue);s.save_state(statepath,state)
 print(json.dumps({'action':'attachment_repaired_without_submission','candidate_id':SHA,'version':2,'history_count':len(after['history']),'proof_sha256':s.digest(destination)}))
