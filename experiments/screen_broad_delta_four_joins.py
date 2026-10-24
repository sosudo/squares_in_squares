"""Four frozen new-whole-donor joins, all D4/order choices; no optimization."""
import time
START=time.monotonic()
from pathlib import Path
import os,sys,json,math,shutil,signal
from decimal import Decimal
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'experiments'))
from fq_active_pilot import digest
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from extract_broad_active_frontier import orient,profiles
from compose_gadgets import extents,side
from cpu_recipe_replay import public_functions,cross_block_separated
from exact_pair_composition import build_pair,positive_control
from fq_capacity_probe import full_certificate
class GateDeadline(BaseException):pass
def alarm(*_):raise GateDeadline()
OUT=ROOT/'artifacts/broad-delta-four-joins-v1';OUT.mkdir(exist_ok=False)
for directory in ('inputs','source','proposals','certified'):(OUT/directory).mkdir()
base=ROOT/'artifacts/merged-fq-broad-final-v2.csv';report=ROOT/'artifacts/merged-fq-broad-final-v2-official.json';EXPECTED='3855c47798708e4bfb9f053024e6542b0a2a5021824bfd310290e4e7ab1ff9ea'
assert digest(base)==EXPECTED;official=json.loads(report.read_text());assert official['valid']and official['puzzles']==1000 and official['sha256']==EXPECTED
lengths={r['n']:r['side']for r in official['results']};target={494:587,637:742,639:744,798:915};candidate_paths=[ROOT/'artifacts'/p for p in ('fq-broad-contact-v1/complete/candidates.json','fq-broad-contact-recovery-v1/candidates.json','fq-broad-final-native-recovery-v1/candidates.json')]
selected={};inputs=[]
for i,path in enumerate(candidate_paths):
 frozen=OUT/'inputs'/f'candidates-{i}.json';shutil.copyfile(path,frozen);frozen.chmod(0o444);inputs.append({'path':str(path),'sha256':digest(frozen)})
 for ns,row in json.loads(frozen.read_text()).items():
  n=int(ns)
  if n in target and(n not in selected or Decimal(row['side'])<Decimal(selected[n]['side'])):selected[n]={**row,'source_path':str(path),'source_sha256':digest(frozen)}
assert len(selected)==4
bank=ROOT/'artifacts/targeted-partners-v2/partners.npz';assert digest(bank)=='e961ca3ac4b18d6e0ee2460cf819fef3da4f718f60c2dde7a32f26392bbb1e2c'
with np.load(bank,allow_pickle=False)as z:partners={key:z[key]for key in z.files if key.startswith('2_2_1__')}
assert len(partners)==2
atomic_npz(OUT/'inputs/classic-partners.npz',partners);atomic_npz(OUT/'inputs/new-whole-donors.npz',{str(n):np.array(row['squares'],float)for n,row in selected.items()})
vendor=ROOT/'vendor/lightning_ftmc';stitch,_=public_functions(vendor)
sources=[Path(__file__),ROOT/'experiments/exact_pair_composition.py',ROOT/'experiments/cpu_recipe_replay.py',ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/extract_broad_active_frontier.py',ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_active_pilot.py',ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py',vendor/'solver.py',vendor/'gpu_fault_composition.py',vendor/'packing_pipeline.py']
source_hashes={}
for i,path in enumerate(sources):
 dst=OUT/'source'/f'{i:02d}-{path.name}';shutil.copyfile(path,dst);dst.chmod(0o444);source_hashes[str(path)]=digest(dst)
manifest={'baseline':str(base),'baseline_sha256':EXPECTED,'baseline_official_sha256':digest(report),'sources':source_hashes,'candidate_sources':inputs,'partner_palette_sha256':digest(bank),'targets':target,'workers':1,'maximum_seconds':120,'mode':0,'orientations':'all eight D4 per block, both block orders','scope':'Finite four-hypothesis screen only. SAT1e-12 is a proposal tolerance; full official raw/pandas and independent interval gates alone admit layouts. No optimizer/GPU/submission.'}
atomic_json(OUT/'manifest.json',manifest)
control=positive_control(stitch);assert control['certificate']['valid'];atomic_json(OUT/'positive-control.json',control)
# A coincident pair is a mandatory negative SAT control.
assert not cross_block_separated(np.array([[.5,.5,0.]]),np.array([[-.5,1.5,0.]]),1,1,0)
rows=[];donors={};candidates={};counts={'sat_tests':0,'sat_pass':0,'full_builds':0,'bounded_clearance_rejected':0,'actual_side_promising':0,'full_certificates':0,'valid_retained':0};complete=True
signal.signal(signal.SIGALRM,alarm)
def variants(p,w,h,d,label):
 result=[]
 for trans in(False,True):
  for sx,sy in((1,1),(-1,1),(1,-1),(-1,-1)):
   q=orient(p,trans,sx,sy);ww,hh=(h,w)if trans else(w,h);lo,hi=extents(q);f=float(max(hi.max(0)-[ww,hh]));f=math.ceil((f+3e-8)*1e9)*1e-9
   result.append({'w':ww,'h':hh,'d':d,'f':f,'pose':q,'label':label,'transform':[trans,sx,sy],'geometry_sha256':geometry_sha(q),'profiles':[profiles(q,ww,hh,a,a,32)for a in(30,45,60)]})
 return result
partner_variants=[r for key,p in partners.items()for r in variants(p,2,2,1,key)]
for n,row in sorted(selected.items()):
 if not complete:break
 p=np.array(row['squares'],float);k0=math.isqrt(n);new_variants=variants(p,k0,k0,n-k0*k0,f'canonical_n{n}')
 for a in new_variants:
  if not complete:break
  for b in partner_variants:
   for reverse in(False,True):
    if time.monotonic()-START>108:complete=False;break
    first,second=(b,a)if reverse else(a,b);nt=target[n];k=math.isqrt(nt);assert k*k+a['d']+b['d']==nt
    counts['sat_tests']+=1;passed=cross_block_separated(first['pose'],second['pose'],first['w'],second['h'],0)
    rec={'source_n':n,'target_n':nt,'new_transform':a['transform'],'partner':b['label'],'partner_transform':b['transform'],'reverse':reverse,'new_geometry_sha256':a['geometry_sha256'],'partner_geometry_sha256':b['geometry_sha256'],'sat_pass':passed,'profile_compatible_degrees':[(30,45,60)[i]for i in range(3)if first['profiles'][i]['br_bin']<=second['profiles'][i]['tl_bin']]}
    if not passed:rows.append(rec);continue
    counts['sat_pass']+=1;q=build_pair(first,second,0,k,stitch);counts['full_builds']+=1
    if q is None:counts['bounded_clearance_rejected']+=1;rec['status']='failed_bounded_clearance';rows.append(rec);continue
    identity=geometry_sha(q);proposal=OUT/'proposals'/f'{len(rows):04d}-n{nt}-{identity}.npz';atomic_npz(proposal,{'pose':q});rec.update(proposal=str(proposal),proposal_sha256=digest(proposal),actual_float_side=side(q))
    if side(q)+1e-9>=float(lengths[nt]):rec['status']='actual_side_not_promising';rows.append(rec);continue
    counts['actual_side_promising']+=1
    try:
     signal.setitimer(signal.ITIMER_REAL,min(6.,max(.01,112.-(time.monotonic()-START))));certificate=full_certificate(q);rec['certificate']=certificate;counts['full_certificates']+=1
    except GateDeadline:rec['status']='certificate_timeout';rows.append(rec);continue
    finally:signal.setitimer(signal.ITIMER_REAL,0)
    if not certificate['valid']:rec['status']='failed_full_gates';rows.append(rec);continue
    key=f'{k}_{k}_{nt-k*k}__four_join_{identity}';donors[key]=q;counts['valid_retained']+=1;rec['status']='certified';rec['archive_key']=key
    path=OUT/'certified'/f'{identity}.npz'
    if not path.exists():atomic_npz(path,{key:q});atomic_json(path.with_suffix('.json'),rec);path.chmod(0o444);path.with_suffix('.json').chmod(0o444)
    actual=certificate['independent_raw']['side_upper'];rec['actual_certified_side']=actual
    if Decimal(actual)<Decimal(lengths[nt])-Decimal('1e-8'):
     old=candidates.get(str(nt))
     if old is None or Decimal(actual)<Decimal(old['side']):candidates[str(nt)]={'side':actual,'squares':[[f'{v:.17g}'for v in rr]for rr in q],'certificate':certificate,'source':'Finite new broad whole-donor plus classic2x2+1 corner join','provenance':{**{key:rec[key]for key in ('source_n','new_transform','partner','partner_transform','reverse','new_geometry_sha256','partner_geometry_sha256')},'manifest_sha256':digest(OUT/'manifest.json')},'score_gain':float(Decimal(lengths[nt])-Decimal(actual))/math.sqrt(nt)}
    rows.append(rec)
atomic_json(OUT/'results.json',rows);atomic_json(OUT/'candidates.json',candidates);atomic_npz(OUT/'donors.npz',donors)
summary={'status':'complete'if complete else'bounded_partial','seconds':time.monotonic()-START,'counts':counts,'certified_winning_cases':list(map(int,candidates)),'score_gain':sum(r['score_gain']for r in candidates.values()),'candidates_sha256':digest(OUT/'candidates.json'),'donors_sha256':digest(OUT/'donors.npz'),'manifest_sha256':digest(OUT/'manifest.json'),'source_hashes_unchanged':all(digest(path)==sha for path,sha in source_hashes.items())}
atomic_json(OUT/'summary.json',summary)
for path in OUT.rglob('*'):
 if path.is_file():path.chmod(0o444)
print(json.dumps(summary),flush=True)
