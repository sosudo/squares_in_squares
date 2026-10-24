"""Certify three frozen native returns; no optimizer is executed."""
from pathlib import Path
import sys,json,hashlib,math,signal,time,shutil
from decimal import Decimal
import numpy as np
ROOT=Path('/workspace/squares_in_squares');sys.path.insert(0,str(ROOT/'experiments'));sys.path.insert(0,str(ROOT/'scripts'))
from fq_active_pilot import decode,digest
from fq_capacity_probe import full_certificate
from fq_variant_campaign import geometry_sha,atomic_json,atomic_npz
OUT=ROOT/'artifacts/fq-broad-contact-recovery-v1';START=time.monotonic()
def timeout(*_):raise TimeoutError('Bounded saved-output certification timeout')
signal.signal(signal.SIGALRM,timeout);signal.alarm(150)
freeze=json.loads((OUT/'freeze.json').read_text());parents=np.load(OUT/'inputs/parent-poses.npz',allow_pickle=False)
assert digest(OUT/'inputs/parent-poses.npz')==freeze['parent_poses_sha256']
source_paths=[Path(__file__),ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py']
(OUT/'source').mkdir(exist_ok=True);sources={}
for p in source_paths:
 dst=OUT/'source'/p.name;shutil.copyfile(p,dst);dst.chmod(0o444);sources[str(p)]=digest(dst)
interval=json.loads((OUT/'comparison/canonical-independent.json').read_text());base={r['n']:r for r in interval['results']};records=[];donors={};candidates={}
for item in freeze['selected']:
 n=item['n'];folder=ROOT/item['folder'];r=json.loads((folder/'original-record.json').read_text())
 for name,meta in item['files'].items():assert digest(folder/name)==meta['sha256']
 assert geometry_sha(parents[str(n)])==r['parent_geometry_sha256']
 lines=(folder/'native.out').read_text().splitlines();assert int(lines[0].split()[0])==n and len(lines)==n+1
 raw=np.array([[float(v)for v in line.split()]for line in lines[1:]]);assert raw.shape==(n,3) and np.isfinite(raw).all();raw[:,2]=np.radians(raw[:,2])
 with np.load(folder/'raw-returned.npz',allow_pickle=False)as z:assert np.array_equal(z['pose'],raw)
 assert geometry_sha(raw)==r['raw_returned']['geometry_sha256']
 q=decode(folder/'native.out',n)
 rec={'n':n,'job':item['job'],'original_record_sha256':digest(folder/'original-record.json'),'raw_geometry_sha256':geometry_sha(raw),'native_output_sha256':digest(folder/'native.out'),'parent_geometry_sha256':r['parent_geometry_sha256'],'decode':'fq_active_pilot.decode: count/finite check, degrees to radians, bounded rounding-clearance legalize2e-9; no optimizer','canonical_raw_side_lower':base[n]['side_lower'],'native_command_for_lineage_only':r['command']}
 if q is None:rec['status']='failed-bounded-clearance';records.append(rec);continue
 rec['geometry_sha256']=geometry_sha(q);rec['certificate']=full_certificate(q);rec['status']='certified' if rec['certificate']['valid']else'failed-full-gates'
 if rec['certificate']['valid']:
  side=rec['certificate']['independent_raw']['side_upper'];rec['side_upper']=side;rec['gain_vs_canonical_side']=str(Decimal(base[n]['side_lower'])-Decimal(side));rec['score_gain_vs_canonical']=float(Decimal(rec['gain_vs_canonical_side']))/math.sqrt(n)
  key=f'{math.isqrt(n)}_{math.isqrt(n)}_{n-math.isqrt(n)**2}__recovered_{rec["geometry_sha256"]}'
  donors[key]=q;rec['archive_key']=key
  atomic_npz(OUT/f'n{n}-certified.npz',{key:q});rec['pose_npz_sha256']=digest(OUT/f'n{n}-certified.npz')
  if Decimal(side)<Decimal(base[n]['side_lower']):
   candidates[str(n)]={'side':side,'squares':[[f'{v:.17g}'for v in row]for row in q],'source':'Saved native broad contact20 output, recovered full certification only','certificate':rec['certificate'],'provenance':{'original_job':item['job'],'native_output_sha256':rec['native_output_sha256'],'original_record_sha256':rec['original_record_sha256'],'raw_geometry_sha256':rec['raw_geometry_sha256'],'geometry_sha256':rec['geometry_sha256'],'parent_geometry_sha256':rec['parent_geometry_sha256'],'source_commit':freeze['source_commit'],'native_binary_sha256':freeze['native_binary_sha256']},'score_gain':rec['score_gain_vs_canonical']}
 atomic_json(OUT/f'n{n}-result.json',rec);records.append(rec);atomic_json(OUT/'results.json',records);atomic_json(OUT/'candidates.json',candidates);atomic_npz(OUT/'donors.npz',donors)
 print(json.dumps({'n':n,'status':rec['status'],'side':rec.get('side_upper'),'side_gain':rec.get('gain_vs_canonical_side'),'score_gain':rec.get('score_gain_vs_canonical'),'seconds':time.monotonic()-START}),flush=True)
# Record a fresh immutable broad comparison only after certifying the saved returns.
ptr_path=ROOT/'artifacts/fq-broad-contact-v1/latest-immutable.json';ptr=json.loads(ptr_path.read_text());snapshot=ROOT/ptr['path'];bs=snapshot/'candidates.json';assert digest(bs)==ptr['candidate_sha256'];broad=json.loads(bs.read_text());shutil.copyfile(bs,OUT/'comparison/broad-candidates-after-certification.json');atomic_json(OUT/'comparison/broad-pointer-after-certification.json',ptr)
live_path=ROOT/'artifacts/fq-broad-contact-v1/results.json';live_bytes=live_path.read_bytes();live=json.loads(live_bytes);(OUT/'comparison/broad-results-after-certification.json').write_bytes(live_bytes)
for rec in records:
 n=rec['n'];side=rec.get('side_upper');old=broad.get(str(n));rec['latest_broad_side']=old.get('side')if old else None;rec['strict_gain_vs_latest_broad']=bool(side and (old is None or Decimal(side)<Decimal(old['side'])))
 rec['later_campaign_certifications_same_case']=[{'job':r.get('job'),'geometry_sha256':r.get('geometry_sha256'),'side':r.get('side')}for r in live if r.get('n')==n and r.get('certificate',{}).get('valid')]
 atomic_json(OUT/f'n{n}-result.json',rec)
atomic_json(OUT/'results.json',records)
summary={'status':'complete','seconds':time.monotonic()-START,'certified':sum(r['status']=='certified'for r in records),'retained_geometries':len(donors),'canonical_comparison_sha256':freeze['canonical_raw']['sha256'],'strict_gains_vs_canonical':sorted(map(int,candidates)),'strict_gains_vs_latest_broad':[r['n']for r in records if r.get('strict_gain_vs_latest_broad')],'canonical_score_gain':sum(c['score_gain']for c in candidates.values()),'source_hashes':sources,'freeze_sha256':digest(OUT/'freeze.json'),'candidates_sha256':digest(OUT/'candidates.json'),'donors_sha256':digest(OUT/'donors.npz'),'results_sha256':digest(OUT/'results.json'),'latest_broad_snapshot':ptr,'no_native_execution':True,'no_campaign_mutation':True}
atomic_json(OUT/'summary.json',summary)
for p in OUT.rglob('*'):
 if p.is_file():p.chmod(0o444)
print(json.dumps(summary),flush=True)
