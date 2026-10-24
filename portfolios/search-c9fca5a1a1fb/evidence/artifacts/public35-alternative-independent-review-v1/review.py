"""Read-only24-input/source/runner review; no optimizer or fresh geometry gate."""
from pathlib import Path
import csv,hashlib,inspect,json,math,sys
import numpy as np
ROOT=Path('/workspace/squares_in_squares');sys.path.insert(0,str(ROOT/'experiments'))
import fq_public35_alternative_finish as runner
DIR=ROOT/'artifacts/public35-alternative-inputs-v1';OUT=Path(__file__).parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();gh=lambda q:hashlib.sha256(q.astype('<f8').tobytes()).hexdigest();read=lambda p:json.loads(Path(p).read_bytes())
assert sha(runner.__file__)=='32d62da2670880e7267a8d78922a8acf6ff18e2798e9615d6994c5848c7ea61b'
assert sha(DIR/'manifest.json')=='7a6a403ba514258f84b6753ee56a25948e85b76f9888ab678ff9d8745473d265'
m=read(DIR/'manifest.json');assert sha(DIR/'inputs.npz')==m['inputs_sha256']=='350a35e27a6cd2920127bf0e2d2292b5a80de8a2d173190466f6c928d8920f81'
assert sha(DIR/'preparation.py')==m['preparation_source_sha256']
assert sha(runner.parent.__file__)==runner.PARENT_SHA=='6c56fa97513e53642ef360fe914f6700dd086dd1eba211a66097b9b71d5e149a'
assert sha(runner.parent.original.__file__)==runner.parent.ORIGINAL_SHA=='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
assert sha(runner.parent.BINARY)==runner.parent.original.BINARY_SHA
assert runner.generated_trial_source()==inspect.getsource(runner.parent.original._finish_slot).replace('UNVERIFIED exact committed BEST array','Exact released public35 changed alternative pose; no pre-native validity claim, final output requires all full gates')
assert runner.parent.original.OPTIONS==m['options']==['--loosen','1','--outer','45','--pit','100','--flip-top','16']
assert m['workers']==2 and m['cpu_affinity']==[0,1]and m['work_seconds']==880 and m['whole_seconds']==900 and m['native_seconds']==60 and m['gate_seconds']==8 and m['seed']==9710000
for p,h in m['evidence_sha256'].items():assert sha(DIR/p)==h
assert sha(DIR/'exact-public35-input-rows.csv')==m['exact_literal_csv_sha256']
assert sha(m['baseline']['path'])==m['baseline']['sha256']=='051bbbe869bd4c2c1d70c42b6bf110f8414253d9537338442c30c88c1626715d'
assert sha(m['baseline']['official_report'])==m['baseline']['official_report_sha256']
official=read(m['baseline']['official_report']);assert official['valid']and official['sha256']==m['baseline']['sha256']and official['puzzles']==1000
sides={r['n']:r['side']for r in official['results']}
screen=read(DIR/'source-evidence/geometry-comparison.json');assert sha(DIR/'source-evidence/geometry-comparison.json')==m['selection_report_sha256']
assert screen['alternate_count']==145 and not screen['exact_exposure_cases']
for p,h in screen['exposure_sources'].items():assert sha(ROOT/p)==h
source=ROOT/'artifacts/public-v35/files/submission.csv';assert sha(source)==m['source_csv_sha256']==screen['source35']['sha256']
download=read(DIR/'source-evidence/download-proof.json');assert download['version']==35 and download['members']['submission.csv']['sha256']==m['source_csv_sha256']
source_review=ROOT/'artifacts/portfolio-7a30c35d28f5-incremental-export-job/independent_export_review.json';assert sha(source_review)=='054c46baf5ab6048dc0c9965f0efbe9488fcd4a0620b67378e3456f7d6360f59'
slots=m['slots'];assert len(slots)==24 and [s['slot']for s in slots]==list(range(24))
cases={s['n']for s in slots};assert len(cases)==24
excluded={412,544,742,591,744,641,411,462,978,541,629,341,65,147,179,299,335,453,693,803,861,498,587}|set(screen['already_adopted_excluded']);assert not cases&excluded
assert [s['selection_stratum']for s in slots]==['closest16']*16+['datedheadroom8_within_observed_q75_cost']*8
def literals(path):
 result={n:{}for n in cases}
 with Path(path).open(newline='')as f:
  for row in csv.DictReader(f):
   n=int(row['n']);i=int(row['square_id'])
   if n in result:
    assert i not in result[n] and 0<=i<n;result[n][i]=row
 return {n:[rows[i]for i in range(n)]for n,rows in result.items()}
public=literals(source);retained=literals(DIR/'exact-public35-input-rows.csv');assert public==retained
rows=[]
with np.load(DIR/'inputs.npz',allow_pickle=False)as z:
 assert set(z.files)=={s['key']for s in slots}
 for s in slots:
  n=s['n'];p=z[s['key']];r=s['source_case'];tokens=[[v[k]for k in('x','y','angle')]for v in public[n]]
  assert p.shape==(n,3)and p.dtype==np.dtype('<f8')and np.isfinite(p).all()and np.array_equal(p,np.array(tokens,dtype=np.float64))
  assert gh(p)==s['geometry_sha256']==r['public35']['geometry_sha256']
  assert hashlib.sha256(json.dumps(tokens,separators=(',',':')).encode()).hexdigest()==r['literal35_sha256']
  text,offsets=runner.parent.original.fq.encode(p,math.isqrt(n),math.isqrt(n));assert offsets==[0,0]
  assert hashlib.sha256(text.encode()).hexdigest()==s['native_encoded_input_sha256']==r['public35']['encoded_input_sha256']
  assert r['exact_native_input_changed']and r['public31']['encoded_input_sha256']!=s['native_encoded_input_sha256']and not r['prior_exact_native_input_exposures']
  assert m['cases'][str(n)]['reference_side']==sides[n]and r['public35']['side']>=float(sides[n])-1e-10
  rows.append(dict(n=n,key=s['key'],geometry_sha256=gh(p),native_input_sha256=s['native_encoded_input_sha256'],literal_rows_sha256=r['literal35_sha256']))
result=dict(status='GREEN_finite_public35_alternative_native_runner_review',review_script_sha256=sha(__file__),runner_sha256=sha(runner.__file__),input_manifest_sha256=sha(DIR/'manifest.json'),inputs_sha256=sha(DIR/'inputs.npz'),parent_runner_sha256=runner.PARENT_SHA,numerical_helper_sha256=runner.parent.ORIGINAL_SHA,binary_sha256=runner.parent.original.BINARY_SHA,baseline_sha256=m['baseline']['sha256'],selected=rows,selection_strata=[16,8],bounded_exposure_archive_count=len(screen['exposure_sources']),exposure_scope='Only pinned screen corpus; zero exact encoded-input matches there, not a universal historical assertion.',native_source_public_provenance_review_sha256=sha(source_review),source_and_exact_literal_rows_and_native_encoding_verified=True,review_notes=['Parent18 runner numerical trial reused; only descriptive input-status text changes. No pre-native validity claim is made.','Fixed24 unique inputs,2CPU0/1,seed9710000,60s native+8s certificate; process group inherits all native descendants and outer supervisor kills/waits by900s.','Exact input/native/raw/decoded outputs are retained before full gates through unchangedaab5 helper. All valid worse poses retained in certified archive.','Live candidate comparison uses initial canonical interval lower; final candidate comparison refreshes current canonical interval lower and uses maximum of five certificate sides. No canonical mutation/submission.'],no_optimizer=True,no_fresh_geometry_certifications=True,no_gpu=True,no_submission=True)
(OUT/'review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(review_sha256=sha(OUT/'review.json'),cases=len(rows),exposure_archives=len(screen['exposure_sources']))))
