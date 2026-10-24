"""Offline byte/hash verification only; never executes the embedded notebook."""
import ast,base64,hashlib,io,json,lzma,pathlib,zipfile
ROOT=pathlib.Path(__file__).resolve().parent
REPOSITORY=ROOT.parents[2]
sha=lambda b:hashlib.sha256(b).hexdigest()
def contained(root,name):
 p=(root/name).resolve()
 if not p.is_relative_to(root.resolve()):raise ValueError('Outside declared proof root: '+name)
 return p
m=json.loads((ROOT/'manifest.json').read_bytes())
for name,r in m['files'].items():
 b=contained(ROOT,name).read_bytes()
 assert len(b)==r['bytes']and sha(b)==r['sha256'],name
for name,r in m['repository_references'].items():
 b=contained(REPOSITORY,name).read_bytes()
 assert len(b)==r['bytes']and sha(b)==r['sha256'],name
source=(ROOT/'job/search.py').read_bytes()
assert sha(source)==m['source_sha256']and len(source)==m['source_bytes']
values={n.targets[0].id:ast.literal_eval(n.value)for n in ast.parse(source).body if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)and n.targets[0].id in('CONFIG','PAYLOAD')}
config=values['CONFIG']
with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(values['PAYLOAD']))))as z:
 assert set(z.namelist())==set(config['files'])and len(z.namelist())==len(set(z.namelist()))
 embedded={name:z.read(name)for name in z.namelist()}
assert len(embedded)==m['embedded_payload_files']
assert all(sha(data)==config['files'][name]for name,data in embedded.items())
for name,want in m['source_manifest'].items():assert sha(embedded[name])==want
for name,r in m['dataset_member_storage'].items():
 loc=r['storage']
 if loc['kind']=='snapshot':data=contained(ROOT,loc['path']).read_bytes()
 elif loc['kind']=='repository':data=contained(REPOSITORY,loc['path']).read_bytes()
 elif loc['kind']=='embedded_job':data=embedded[loc['member']]
 else:raise ValueError('Unknown member storage kind')
 assert len(data)==r['bytes']and sha(data)==r['sha256'],name
assert len(m['dataset_member_storage'])==m['fixture_members']==125
assert {k:r['sha256']for k,r in m['dataset_member_storage'].items()}=={k:r['sha256']for k,r in config['fixture_files'].items()}
remote=json.loads((ROOT/'job/remote-source-proof.json').read_bytes())
assert remote['source_sha256']==m['source_sha256']and remote['notebook']==m['notebook']and remote['version']==m['version']==1
assert remote['private']and remote['gpu']and not remote['internet']
assert remote['local_metadata_sha256']==sha((ROOT/'job/kernel-metadata.json').read_bytes())
startup=json.loads((ROOT/'startup/proof.json').read_bytes());events=json.loads((ROOT/'startup/events.json').read_bytes())
assert startup['source_sha256']==m['source_sha256']and startup['events_sha256']==sha((ROOT/'startup/events.json').read_bytes())
assert len(events)==4
assert {r['event']['family']for r in events if r['event']['stage']=='rectangular_preflight'and r['event']['passed']}==set(m['first_wave']['preflights_passed'])
assert {r['event']['family']for r in events if r['event']['stage']=='rectangular_search'and r['event']['rounds']==0}==set(m['first_wave']['round_zero_seen'])
actual={str(p.relative_to(ROOT))for p in ROOT.rglob('*')if p.is_file()}
assert actual==set(m['files'])|{'manifest.json'},'Unlisted or missing snapshot file'
print(json.dumps(dict(status='GREEN_OFFLINE_LAUNCH_SNAPSHOT',manifest_sha256=sha((ROOT/'manifest.json').read_bytes()),snapshot_files=len(m['files']),copied_bytes=sum(r['bytes']for r in m['files'].values()),repository_references=len(m['repository_references']),embedded_payload_files=len(embedded),dataset_members=125,source_sha256=m['source_sha256'],first_wave_preflights=m['first_wave']['preflights_passed'],no_job_execution=True),indent=2))
