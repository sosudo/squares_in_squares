"""Bind five winning sustained-run poses; no native solve or new certificate."""
from pathlib import Path
import json,hashlib,sys,math
from decimal import Decimal,localcontext
import numpy as np
ROOT=Path('/workspace/squares_in_squares');sys.path.insert(0,str(ROOT/'experiments'))
import fq_restart_hop_finish as native
from fq_sustained_hop_finish import select_slots
from analyze_fq_sustained_cold import certificate_side
DIR=ROOT/'artifacts/fq-sustained-analysis-v1';EXT=ROOT/'artifacts/fq-sustained-extracted-v1';OUT=Path(__file__).parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();gh=lambda q:hashlib.sha256(q.astype('<f8').tobytes()).hexdigest();read=lambda p:json.loads(Path(p).read_bytes())
assert sha(DIR/'candidates.json')=='cc8398494089f5ccc5b2272c948bf5eca056e5a371cb272f042027f6dbbad760'
assert sha(DIR/'analysis.json')=='87696e46a8733767766e317b746e45e4ea7720b2a8ac6a1127089e283b5e02a6'
a=read(DIR/'analysis.json');c=read(DIR/'candidates.json');assert set(c)=={'411','462','544','641','742'}
assert sha(DIR/'certified.npz')==a['certified_sha256']=='c2821f58c3dd45862bc543acb038680710282050cb025725cd8354c93e47a16e'
assert sha(DIR/'bindings.json')==a['bindings_sha256'];bindings=read(DIR/'bindings.json')
receipt=read(EXT/'extraction-receipt.json');assert sha(EXT/'extraction-receipt.json')==a['receipts'][0]['sha256']
assert receipt['kind']=='verified_private_cpu_extraction_chain'and receipt['status']=='complete'and len(receipt['files'])==1183
assert receipt['parent_source_sha256']==a['source_sha256']=='dc6950e858285433d1975f537431e375bae95584ab314807a3ae08b79baa0451'
assert receipt['extractor_source_sha256']=='75f5a14ff4f1d27e923241f47ff2e9e3369423fc36aab477d63a4b5b94a12e2b'
for key in('extractor_download_receipt','parent_source_proof','parent_completion_proof','inventory','bundle'):
 p=receipt[key];assert sha(p['path'])==p['sha256']
cpu=read(receipt['extractor_download_receipt']['path']);assert cpu['source_sha256']==receipt['extractor_source_sha256']and cpu['private_source_verified']and not cpu['enable_gpu']and cpu['status']=='complete'
assert cpu['files']['extracted/inventory.json']['sha256']==receipt['inventory']['sha256']and cpu['files']['extracted/selected-output.zip']['sha256']==receipt['bundle']['sha256']
inv=read(receipt['inventory']['path']);assert inv['files']==receipt['files']and inv['zip_sha256']==receipt['bundle']['sha256']
assert read(receipt['parent_completion_proof']['path'])['status']=='COMPLETE'
consumed={}
def path(name):
 name=str(name)
 if name.startswith('/kaggle/working/'):name=name[len('/kaggle/working/'):]
 assert name in receipt['files'];p=EXT/'outputs'/name;entry=receipt['files'][name]
 assert sha(p)==entry['sha256']and p.stat().st_size==entry['bytes'];consumed[name]=entry['sha256'];return p
manifest=read(path('job_manifest.json'));assert sha(path('bin/fq'))==native.BINARY_SHA==manifest['files']['bin/fq']
for name in('experiments/fq_restart_hop_finish.py','experiments/fq_active_pilot.py','experiments/fq_sustained_hop_finish.py','research/official_metric_v17.py'):
 assert sha(ROOT/name)==sha(path(name))==manifest['files'][name]
comparison=read(DIR/'comparison/canonical-independent.json');pointer=read(DIR/'comparison/canonical-pointer.json')
assert sha(DIR/'comparison/canonical-independent.json')==pointer['independent_report']['sha256']
assert comparison['valid']and comparison['sha256']==a['canonical_raw_sha256']==pointer['raw']['sha256']=='051bbbe869bd4c2c1d70c42b6bf110f8414253d9537338442c30c88c1626715d'
thresholds={r['n']:Decimal(r['side_lower'])for r in comparison['results']}
rows=[];gain=Decimal(0)
with np.load(DIR/'certified.npz',allow_pickle=False)as aggregate:
 for ns,candidate in c.items():
  n=int(ns);pr=candidate['provenance'];binding=pr['binding'];assert binding==bindings[pr['archive_key']]
  r=binding['record'];q=aggregate[pr['archive_key']];assert gh(q)==pr['geometry_sha256']==r['geometry_sha256']
  assert candidate['squares']==[[f'{v:.17g}'for v in row]for row in q]and candidate['certificate']==binding['certificate']==r['certificate']
  side=certificate_side(q,candidate['certificate']);assert side==Decimal(candidate['side'])==Decimal(r['worst_certified_side'])<thresholds[n]
  assert r['status']=='certified'and r['native_status']=='returned'and r['returncode']==0 and r['native_seconds']<60
  prefix=f'case-{n}/';recovery=read(path(prefix+'recovery.json'));entry=recovery['last_completed_packet']
  packet=path(prefix+entry['path']);assert sha(packet)==entry['sha256']==binding['terminal_packet_sha256']==r['last_completed_packet_sha256']
  design=read(path(prefix+'chain-design.json'))
  with np.load(packet,allow_pickle=False)as z:
   meta=json.loads(z['metadata_json'].tobytes());assert meta['design']==design and meta['status']=='completed'
   for name in z.files:
    if name!='metadata_json':assert hashlib.sha256(z[name].tobytes()).hexdigest()==meta['array_sha256'][name]
   best=z['best_after'].copy();energy=z['best_energy_after'].copy();sides=z['sides'].copy()
  expected=select_slots(design,best,energy,sides)[r['slot']]
  assert expected['status']=='selected' and r['status']=='certified'
  for key,value in expected.items():
   if key!='status':assert r[key]==value,(n,key)
  selected=best[r['chain']];assert gh(selected)==r['selected_geometry_sha256']
  with np.load(path(r['selected_archive']),allow_pickle=False)as z:assert np.array_equal(z['pose'],selected)
  assert sha(path(r['selected_archive']))==r['selected_archive_sha256']
  cmd=r['command'];inp=path(cmd[cmd.index('--in')+1]);out=path(r['native_output_path']);text,offset=native.fq.encode(selected,math.isqrt(n),math.isqrt(n));assert offset==[0,0]
  assert inp.read_bytes()==text.encode()and sha(inp)==r['input_sha256']and sha(out)==r['native_output_sha256']
  assert cmd[-len(native.OPTIONS):]==native.OPTIONS and cmd[cmd.index('--seed')+1]=='9710000'and all(cmd[cmd.index(k)+1]=='0'for k in('--rect-dx','--rect-dy'))
  stem=Path(r['native_output_path']).with_suffix('')
  for suffix in('stdout','stderr','log'):assert sha(path(str(stem)+'.'+suffix))==r[suffix+'_sha256']
  assert path(str(stem)+'.log').read_bytes()==path(str(stem)+'.stdout').read_bytes()+b'\n'+path(str(stem)+'.stderr').read_bytes()
  for field in('raw_returned','decoded_returned'):
   p=path(r[field]['path']);assert sha(p)==r[field]['sha256']
   with np.load(p,allow_pickle=False)as z:v=z['pose'].copy()
   assert gh(v)==r[field]['geometry_sha256']
   expected_pose=native._pose_from_output(out,n)if field=='raw_returned'else native.fq.decode(out,n)
   assert np.array_equal(v,expected_pose)
  assert np.array_equal(q,expected_pose)
  certpath=path(r['certified_archive']);assert sha(certpath)==r['certified_archive_sha256']==binding['archive_sha256']
  with np.load(certpath,allow_pickle=False)as z:assert np.array_equal(z['pose'],q)
  assert read(path(str(stem)+'.certificate.json'))==r
  with localcontext()as ctx:
   ctx.prec=70;contribution=(thresholds[n]-side)/Decimal(n).sqrt();gain+=contribution
  rows.append(dict(n=n,slot=r['slot'],chain=r['chain'],geometry_sha256=gh(q),terminal_packet_sha256=sha(packet),native_input_sha256=sha(inp),native_output_sha256=sha(out),side=str(side),baseline_interval_lower=str(thresholds[n]),conservative_score_gain=str(contribution)))
result=dict(status='GREEN_five_sustained_winner_lineage_review',review_script_sha256=sha(__file__),analysis_sha256=sha(DIR/'analysis.json'),candidates_sha256=sha(DIR/'candidates.json'),certified_archive_sha256=sha(DIR/'certified.npz'),extraction_receipt_sha256=sha(EXT/'extraction-receipt.json'),canonical_comparison_sha256=pointer['raw']['sha256'],winning_cases=rows,conservative_aggregate_score_gain=str(gain),consumed_hash_bound_files=consumed,scope='Five winners only; complete1183-file/execution96certificate audit reused through exact analysis/receipt hashes. Fixed selection recomputed, all terminal members and native/decimal/certificate links independently checked. No causal claim beyond this GPU-plus-native pipeline.',no_new_certificates=True,no_optimizer=True,no_submission=True)
(OUT/'review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(review_sha256=sha(OUT/'review.json'),score_gain=str(gain),files=len(consumed))))
