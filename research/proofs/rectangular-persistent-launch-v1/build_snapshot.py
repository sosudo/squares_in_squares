"""Copy the already-running launch proof; no network or numerical execution."""
import ast,base64,datetime,hashlib,io,json,lzma,pathlib,shutil,zipfile
R=pathlib.Path.cwd();O=R/'research/proofs/rectangular-persistent-launch-v1'
SOURCE='fb878006be0daa5bc1c6ce622c3dc58bf39f2b3171d45704f56260368e1df7b9'
sha=lambda b:hashlib.sha256(b).hexdigest()
def read(p):return(R/p).read_bytes()
def load(p):return json.loads(read(p))
assert not O.exists(), 'Fresh immutable snapshot required'
job='artifacts/rectangular-persistent-job-v1'
job_source=read(job+'/search.py');assert sha(job_source)==SOURCE
values={n.targets[0].id:ast.literal_eval(n.value)for n in ast.parse(job_source).body if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)and n.targets[0].id in('CONFIG','PAYLOAD')}
config=values['CONFIG']
with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(values['PAYLOAD']))))as z:embedded={name:z.read(name)for name in z.namelist()}
assert set(embedded)==set(config['files'])and len(embedded)==155
assert all(sha(data)==config['files'][name]for name,data in embedded.items())
for name,digest in config['source_manifest'].items():assert sha(read(name))==digest==sha(embedded[name])
remote=load(job+'/remote-source-proof.json');assert remote['source_sha256']==SOURCE and remote['version']==1 and remote['private']and remote['gpu']and not remote['internet']
assert remote['local_metadata_sha256']==sha(read(job+'/kernel-metadata.json'))
assert load(job+'/local_import_review.json')['source_sha256']==SOURCE
assert load(job+'/independent_runtime_review.json')['source_sha256']==SOURCE
startup='artifacts/rectangular-live-startup-v1';sp=load(startup+'/proof.json');events=load(startup+'/events.json')
assert sp['source_sha256']==SOURCE and sp['events_sha256']==sha(read(startup+'/events.json'))and sp['event_count']==len(events)==4
assert {x['event']['family']for x in events if x['event']['stage']=='rectangular_preflight'and x['event']['passed']}=={'5_17_7','7_19_13'}
assert {x['event']['family']for x in events if x['event']['stage']=='rectangular_search'and x['event']['rounds']==0}=={'5_17_7','7_19_13'}
assert sha(read('scripts/read_rectangular_live.py'))==sp['reader_sha256']
inputroot='artifacts/rectangular-persistent-inputs-v2';proof=load(inputroot+'/rectangular-input-proof.json')
assert sha(read(inputroot+'/rectangular-inputs.npz'))==proof['inputs_sha256']==config['inputs_sha256']
assert sha(read(inputroot+'/rectangular-input-proof.json'))==config['input_proof_sha256']
assert sha(read(inputroot+'/rectangular-input-config.json'))==proof['config_sha256']==config['input_config_sha256']
datasetroot='artifacts/rectangular-fixture-dataset-v1';dataset=load(datasetroot+'/completion-proof.json');dm=load(datasetroot+'/fixture-manifest.json')
assert dataset['status']=='complete'and dataset['is_private']and dataset['version']==1
assert dataset['fixture_manifest_sha256']==sha(read(datasetroot+'/fixture-manifest.json'))
assert dataset['downloaded_files']=={k:v['sha256']for k,v in config['fixture_files'].items()}and config['fixture_files']==dm['files']and len(dm['files'])==125
closedroot='research/proofs/structural-controls-20261024T1754';closed=load(closedroot+'/manifest.json')
closed_by_hash={}
for item in closed['files']:
 path=closedroot+'/'+item['snapshot']
 if (R/path).is_file():
  data=read(path)
  assert sha(data)==item['sha256']and len(data)==item['bytes'],path
  closed_by_hash.setdefault(item['sha256'],dict(path=path,bytes=len(data)))
O.mkdir(parents=True);files={};stored_by_hash={};external={}
def copy_bytes(origin,dest,expected=None):
 data=read(origin)
 if expected:assert sha(data)==expected,origin
 target=O/dest;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 files[dest]=dict(source=origin,sha256=sha(data),bytes=len(data));stored_by_hash.setdefault(sha(data),dest)
 return data
for p in sorted((R/job).iterdir()):
 if p.is_file():copy_bytes(str(p.relative_to(R)),'job/'+p.name)
for p in sorted((R/inputroot).rglob('*')):
 if p.is_file()and'__pycache__'not in p.parts:copy_bytes(str(p.relative_to(R)),'inputs/'+str(p.relative_to(R/inputroot)))
for p in sorted((R/'artifacts/rectangular-persistent-protocol-v1').iterdir()):
 if p.is_file():copy_bytes(str(p.relative_to(R)),'protocol/'+p.name)
for name in('completion-proof.json','fixture-manifest.json','remote-metadata.json','upload-proof.json','verify-remote.py'):
 copy_bytes(datasetroot+'/'+name,'dataset/'+name)
for name in('proof.json','events.json','sanitized.log'):copy_bytes(startup+'/'+name,'startup/'+name)
for path in('scripts/build_rectangular_persistent_job.py','scripts/build_fq_fused_hop_job.py','scripts/check_rectangular_bundle.py','scripts/prepare_rectangular_fixture_dataset.py','scripts/read_rectangular_live.py'):
 copy_bytes(path,'sources/'+path)
for path in('artifacts/rectangular-runtime-local-review-v1/wall-fixtures.json','artifacts/rectangular-runtime-local-review-v1/prepare-replay.json','artifacts/rectangular-runtime-independent-review-v1/review_bundle.py'):
 copy_bytes(path,'reviews/'+pathlib.Path(path).name)
for p in sorted((R/'tests').glob('*rectangular*.py')):copy_bytes(str(p.relative_to(R)),'source-tests/'+p.name)
for name,digest in config['source_manifest'].items():
 # Numerical source is already stored exactly inside job/search.py; this table
 # binds the live stable files without another duplicate plaintext copy.
 assert sha(read(name))==digest
embedded_by_hash={}
for name,data in embedded.items():embedded_by_hash.setdefault(sha(data),name)
members={}
for name,item in dm['files'].items():
 data=read(datasetroot+'/download/'+name);h=sha(data);assert h==item['sha256']and len(data)==item['bytes']
 if h in stored_by_hash:where=dict(kind='snapshot',path=stored_by_hash[h])
 elif h in embedded_by_hash:where=dict(kind='embedded_job',member=embedded_by_hash[h])
 elif h in closed_by_hash:
  record=closed_by_hash[h];external[record['path']]=dict(sha256=h,bytes=record['bytes']);where=dict(kind='repository',path=record['path'])
 else:
  dest='dataset/unique-members/'+name;copy_bytes(datasetroot+'/download/'+name,dest,h);where=dict(kind='snapshot',path=dest)
 members[name]=dict(sha256=h,bytes=len(data),storage=where)
external[closedroot+'/manifest.json']=dict(sha256=sha(read(closedroot+'/manifest.json')),bytes=len(read(closedroot+'/manifest.json')))
# Retain the independent closed reviews by reference when the root already copied them.
for path in ['artifacts/rectangular-inputs-independent-review-v1/review.json','artifacts/rectangular-finisher-independent-review-v1/review.json','artifacts/rectangular-reference-independent-review-v1/review.json']:
 h=sha(read(path));match=closed_by_hash.get(h)
 if match:external[match['path']]=dict(sha256=h,bytes=match['bytes'])
 else:copy_bytes(path,'reviews/'+path.split('/')[-2]+'.json',h)
manifest=dict(schema_version=1,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Immutable launch and first-wave startup proof only; campaign remains running. No terminal result, packing improvement, optimizer rerun, current-job mutation, git commit or submission.',
 notebook=remote['notebook'],version=1,source_sha256=SOURCE,source_bytes=len(job_source),source_manifest=config['source_manifest'],embedded_payload_files=155,
 fixture_ref=config['fixture_transport']['ref'],fixture_members=125,fixture_input_archive_sha256=config['inputs_sha256'],fixture_input_proof_sha256=config['input_proof_sha256'],
 first_wave=dict(captured_utc=sp['utc'],preflights_passed=['5_17_7','7_19_13'],round_zero_seen=['5_17_7','7_19_13'],second_wave_not_yet_observed=True,scope='Hash-bound parent-relayed live event summaries; full numerical output artifacts will be audited after return.'),
 files=files,dataset_member_storage=members,repository_references=external,closed_proof_manifest_sha256=sha(read(closedroot+'/manifest.json')),
 deduplication='One v2 fixture tree. Repeated private-dataset members resolve to the same copied bytes, embedded frozen-job members, or exact files in the separately retained closed-controls proof. No duplicate upload/download trees or archive ZIP.')
(O/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(snapshot=str(O.relative_to(R)),copied_files=len(files),copied_bytes=sum(r['bytes']for r in files.values()),external_refs=len(external),dataset_members=125,manifest_sha256=sha((O/'manifest.json').read_bytes())),indent=2))
