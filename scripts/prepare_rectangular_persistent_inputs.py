#!/usr/bin/env python3
"""Freeze exact certified rectangular starts; bounded geometry audit, no optimizer."""
from __future__ import annotations
import os
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_name]='1'
import argparse,hashlib,io,json,math,re,shutil,sys,time
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from compose_gadgets import normalize,extents
from fq_active_pilot import bloat,encode
from extract_broad_active_frontier import profiles
FAMILIES=((5,17,7),(7,19,13),(7,20,14),(8,21,13))
BASELINE='9d18b33ca0efb4c55c0afac2c159f413676d76aae37fb3cbcc6ec93a43975396'
SPECS=[
 ('coherent','artifacts/fq-coherent-v1/donors.npz','artifacts/fq-coherent-v1/results.json','records'),
 ('broad','artifacts/active-broad-frontier-v1/active_seed_variants.npz','artifacts/active-broad-frontier-v1/active_seed_validation.json','broad'),
 ('variant','artifacts/fq-variant-v1/snapshot-00093/donors.npz','artifacts/fq-variant-v1/snapshot-00093/results.json','records'),
 ('multiscale','artifacts/fq-multiscale-v1/snapshot-00099/donors.npz','artifacts/fq-multiscale-v1/snapshot-00099/results.json','records'),
 ('focus','artifacts/fq-focus-v1/snapshot-00083/donors.npz','artifacts/fq-focus-v1/snapshot-00083/results.json','records'),
 ('soft','artifacts/fq-soft-v1/snapshot-00045/donors.npz','artifacts/fq-soft-v1/snapshot-00045/results.json','records'),
 ('local_soft','artifacts/fq-local-soft-v1/all-strict/donors.npz','artifacts/fq-local-soft-v1/all-strict/provenance.json','local'),
 ('combined','artifacts/combined-ftmc-results/artifacts/campaign_gadgets.npz','artifacts/combined-ftmc-results/ftmc_candidates.json','combined'),
]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gh(q):return hashlib.sha256(np.asarray(q,dtype='<f8').tobytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def npysha(q):
 s=io.BytesIO();np.save(s,q,allow_pickle=False);return hashlib.sha256(s.getvalue()).hexdigest()
def family(key):
 m=re.match(r'^(\d+)_(\d+)_(\d+)(?:__|$)',key)
 if not m:return None
 w,h,d=map(int,m.groups());return (min(w,h),max(w,h),d),(w,h,d)
def canonical(p,typ):
 w,h,d=typ;q=np.array(p,dtype=np.float64,copy=True)
 transposed=w>h
 if transposed:q[:,:2]=q[:,[1,0]];q[:,2]=math.pi/2-q[:,2]
 lo,_=extents(q);shift=-lo.min(0);q[:,:2]+=shift
 return q,dict(transpose=transposed,angle_rule='pi/2-angle'if transposed else'unchanged',translation=shift.tolist(),row_order='unchanged',no_scaling=True)
def mirrors(q):
 a=q.copy();a[:,:2]-=a[:,:2].mean(0)
 for sx,sy in((1,1),(1,-1),(-1,1),(-1,-1)):
  b=a.copy();b[:,0]*=sx;b[:,1]*=sy;b[:,2]*=sx*sy
  yield b

def descriptor(q):
 values=[]
 for a in mirrors(q):
  v=np.column_stack((np.rint(a[:,:2]/.10),np.rint((a[:,2]%(math.pi/2))/math.radians(2.))))
  v=v[np.lexsort((v[:,2],v[:,1],v[:,0]))].astype('<i4')
  values.append(v.tobytes())
 return hashlib.sha256(min(values)).hexdigest()

def assignment_distance(q,p):
 a=q.copy();a[:,:2]-=a[:,:2].mean(0);best=None
 for idx,b in enumerate(mirrors(p)):
  angle=(a[:,None,2]-b[None,:,2]+math.pi/4)%(math.pi/2)-math.pi/4
  centers=cdist(a[:,:2],b[:,:2],'sqeuclidean');cost=centers+.25**2*angle**2
  ii,jj=linear_sum_assignment(cost);rms=float(np.sqrt(np.mean(centers[ii,jj])));ar=float(np.sqrt(np.mean(angle[ii,jj]**2)));score=float(np.sqrt(np.mean(cost[ii,jj])))
  value=dict(score=score,center_rms=rms,center_max=float(np.sqrt(centers[ii,jj]).max()),angle_rms_radians=ar,angle_max_radians=float(abs(angle[ii,jj]).max()),reflection_index=idx)
  if best is None or score<best['score']:best=value
 return best

def source_record(kind,data,key,p):
 raw=gh(p)
 if kind=='broad':
  c=data[key];assert c['valid']and c['geometry_sha256']==raw
  return dict(certificate=c,source_record=c,geometry_binding='raw_little_endian_float64')
 if kind=='combined':
  r=data[key];c=r['exact_geometry_certificate'];assert c['official_raw_and_pandas']and c['status']=='certified_geometry'and c['npy_sha256']==npysha(p)
  return dict(certificate=c,source_record=r,geometry_binding='NPY_file_sha256; independent raw-array SHA also recorded')
 if kind=='local':
  options=data[key]
  for o in options:
   r=o.get('record',o.get('proof',{}));c=r.get('certificate',{})
   if r.get('geometry_sha256')==raw and c.get('valid'):return dict(certificate=c,source_record=o,geometry_binding='raw_little_endian_float64')
  raise ValueError('No exact local certificate '+key)
 records=data if isinstance(data,list)else list(data.values())
 for r in records:
  if r.get('geometry_sha256')==raw and r.get('certificate',{}).get('valid'):
   return dict(certificate=r['certificate'],source_record=r,geometry_binding='raw_little_endian_float64')
 raise ValueError('No exact record '+key)

def collect():
 candidates={f:[]for f in FAMILIES};sources=[];hist=[]
 for label,npzname,proofname,kind in SPECS:
  p=ROOT/npzname;proof=ROOT/proofname;assert p.exists()and proof.exists(),(p,proof)
  data=json.loads(proof.read_text());records=data if isinstance(data,list)else[]
  hist.extend(dict(source_label=label,root=str(Path(npzname).parent.parent),record=r)for r in records)
  meta=dict(label=label,archive=npzname,archive_sha256=sha(p),proof=proofname,proof_sha256=sha(proof),kind=kind)
  count=0
  with np.load(p,allow_pickle=False)as z:
   for key in z.files:
    ft=family(key)
    if not ft or ft[0]not in candidates:continue
    fam,typ=ft;q=z[key];assert q.dtype==np.dtype('float64')and q.shape==(typ[0]*typ[1]+typ[2],3)and np.isfinite(q).all()
    record=source_record(kind,data,key,q);normal,transform=canonical(q,typ)
    f=bloat(normal,*fam[:2]);assert f<1 and f>=0
    candidates[fam].append(dict(source_label=label,source_key=key,source_type=list(typ),source_archive=npzname,source_archive_sha256=meta['archive_sha256'],source_proof=proofname,source_proof_sha256=meta['proof_sha256'],source_geometry_sha256=gh(q),source_npy_sha256=npysha(q),source_pose=q,pose=normal,geometry_sha256=gh(normal),transform=transform,f=f,descriptor=descriptor(normal),**record));count+=1
  meta['eligible_arrays']=count;sources.append(meta)
 return candidates,sources,hist

def select(candidates,deadline):
 chosen={};audit={}
 for fam,rows in candidates.items():
  # Exact original type+bytes duplicates retain source aliases; no geometry collapse.
  unique={}
  for r in rows:
   k=(tuple(r['source_type']),r['source_geometry_sha256'])
   if k not in unique:unique[k]=r
   else:unique[k].setdefault('aliases',[]).append({k:r[k]for k in('source_label','source_key','source_archive','source_archive_sha256','source_proof','source_proof_sha256')})
  rows=list(unique.values());rows.sort(key=lambda r:(r['f'],r['source_label'],r['source_key']));best=rows[0];limit=best['f']+.06
  reps={}
  for r in rows:
   if r['f']<=limit:reps.setdefault(r['descriptor'],r)
  pool=sorted(reps.values(),key=lambda r:(r['f'],r['source_key']))
  # At most96 geometry-descriptor representatives; original recipe sources forced in.
  if len(pool)>96:pool=[pool[i]for i in np.unique(np.rint(np.linspace(0,len(pool)-1,96)).astype(int))]
  for r in rows:
   if r['source_label']=='broad'and all(r is not x for x in pool):pool.append(r)
  selected=[best];comparisons={};minimum={}
  def update(last):
   for i,r in enumerate(pool):
    if time.monotonic()>deadline:raise TimeoutError('Bounded diversity audit exceeded its declared deadline')
    dist=assignment_distance(last['pose'],r['pose']);comparisons[f'{len(selected)-1}:{i}']=dist
    if i not in minimum or dist['score']<minimum[i]['score']:minimum[i]=dist
  update(best)
  # Prefer an actual old compatible-profile pose if it is geometrically distinct.
  old=[i for i,r in enumerate(pool)if r['source_label']=='broad'and minimum[i]['score']>.01]
  if old:
   i=max(old,key=lambda j:minimum[j]['score']);selected.append(pool[i]);update(pool[i])
  while len(selected)<4:
   ranked=[i for i,r in enumerate(pool)if all(r is not x for x in selected)]
   i=max(ranked,key=lambda j:minimum[j]['score']);selected.append(pool[i]);update(pool[i])
  matrix=[]
  for i,a in enumerate(selected):
   for j in range(i):matrix.append(dict(left=j,right=i,**assignment_distance(a['pose'],selected[j]['pose'])))
  groups=[]
  for i,a in enumerate(selected):
   close=next((g for g in groups if assignment_distance(a['pose'],selected[g[0]]['pose'])['score']<=.01),None)
   if close is None:groups.append([i])
   else:close.append(i)
  key='_'.join(map(str,fam));chosen[key]=selected
  audit[key]=dict(audited_source_arrays=len(candidates[fam]),exact_type_array_unique=len(rows),lowest_f=best['f'],source_of_lowest={k:best[k]for k in('source_label','source_key','source_archive','source_geometry_sha256')},near_reference_band=.06,coarse_descriptor_groups=len(reps),bounded_assignment_panel=len(pool),selected_pairwise_assignments=matrix,selected_coarse_geometry_groups=groups,geometry_group_threshold=.01,geometry_group_scope='Minimum centered four-reflection assignment RMS in combined center/0.25*angle metric, unit angles modulo pi/2. Descriptor only bounds panel selection; no optimizer-basin/topology proof.',complete_source_minimum_scan=True,assignment_search_scope='Finite descriptor panel only; not all-pair clustering of every source.',seed_reasons=['orientation_fair_minimum']+['geometry_and_profile_alternative']*(len(selected)-1))
 return chosen,audit

def public_meta(r):return{k:v for k,v in r.items()if k not in('pose','source_pose')}

def rectangle_bounds(q,w,h):
 from validate_submission import Square,_geometry,_iv_min,_iv_max,_endpoint_text
 from decimal import Decimal
 g=_geometry([Square(*(f'{v:.17g}' for v in row))for row in q],80)
 def endpoints(v):return dict(lower=_endpoint_text(v.a,False),upper=_endpoint_text(v.b,True))
 xmin=_iv_min([a[0]-a[4]for a in g]);xmax=_iv_max([a[0]+a[4]for a in g])
 ymin=_iv_min([a[1]-a[4]for a in g]);ymax=_iv_max([a[1]+a[4]for a in g])
 xs=xmax-xmin;ys=ymax-ymin;f=_iv_max([xs-w,ys-h])
 bounds=dict(x_min=endpoints(xmin),x_max=endpoints(xmax),y_min=endpoints(ymin),y_max=endpoints(ymax),x_span=endpoints(xs),y_span=endpoints(ys),x_excess=endpoints(xs-w),y_excess=endpoints(ys-h),f=endpoints(f),decimal_serialization='.17g',interval_precision_digits=80)
 assert 0<Decimal(bounds['f']['lower'])<=Decimal(bounds['f']['upper'])<1
 return bounds

def contact_diagnostics(q,w,h):
 n=len(q);theta=q[:,2];u=np.column_stack((np.cos(theta),np.sin(theta)));v=np.column_stack((-np.sin(theta),np.cos(theta)))
 ii,jj=np.triu_indices(n,1);delta=q[jj,:2]-q[ii,:2];gaps=[]
 for axes in(u[ii],v[ii],u[jj],v[jj]):
  radii=.5*(abs(np.sum(u[ii]*axes,1))+abs(np.sum(v[ii]*axes,1))+abs(np.sum(u[jj]*axes,1))+abs(np.sum(v[jj]*axes,1)))
  gaps.append(abs(np.sum(delta*axes,1))-radii)
 gap=np.max(gaps,axis=0);contacts={}
 for tol in(1e-6,1e-5,1e-4):
  mask=abs(gap)<=tol;degree=np.bincount(np.r_[ii[mask],jj[mask]],minlength=n)
  contacts[str(tol)]=dict(edges=int(mask.sum()),degree_histogram=np.bincount(degree).tolist())
 angles=abs((theta+math.pi/4)%(math.pi/2)-math.pi/4)
 prof=[]
 for rid,p in enumerate(mirrors(q)):
  p=normalize(p)
  prof.append(dict(reflection_index=rid,profiles=[profiles(p,w,h,a,b,32)for a in(30,45,60)for b in(30,45,60)]))
 return dict(tilted_over_one_degree=int((angles>math.pi/180).sum()),angle_degrees_quantiles=np.quantile(np.degrees(angles),[0,.25,.5,.75,1]).tolist(),contacts=contacts,profiles=prof,scope='Finite contact/profile diagnostics; no topology or optimizer-basin equivalence claim. Reflections are diagnostic only.')

def finalize_inventory(inventory_path,out,reuse=None):
 from fq_capacity_probe import full_certificate
 from decimal import Decimal
 started=time.monotonic();inventory_path=inventory_path.resolve();inv=json.loads(inventory_path.read_text());bank=inventory_path.parent/'selected-provisional.npz'
 assert sha(bank)==inv['provisional_inputs_sha256']
 assert inv['baseline']['raw']['sha256']==BASELINE
 for section in('raw','safe'):
  r=inv['baseline'][section];assert sha(ROOT/r['path'])==r['sha256']
 for source in inv['sources']:
  assert sha(ROOT/source['archive'])==source['archive_sha256'];assert sha(ROOT/source['proof'])==source['proof_sha256']
 out.mkdir(parents=True,exist_ok=False);(out/'certificates').mkdir();(out/'native-reference-inputs').mkdir();(out/'evidence').mkdir()
 arrays={};config_families={};certs={};seedproof={};reusable={}
 if reuse:
  prior=json.loads((reuse/'rectangular-input-proof.json').read_text())
  for k,r in prior['selected'].items():
   c=r['certificate'];path=reuse/c['path']
   assert sha(path)==c['sha256']
   reusable[c['geometry_sha256']]=(path,json.loads(path.read_text()))
 with np.load(bank,allow_pickle=False)as z:
  for family_key,rows in inv['selection'].items():
   w,h,d=map(int,family_key.split('_'));seeds=[]
   for row in rows:
    key=row['input_key'];q=z[key];original=z[key+'__original'];assert gh(q)==row['geometry_sha256']and gh(original)==row['source_geometry_sha256']
    reproduced,transform=canonical(original,row['source_type']);assert np.array_equal(reproduced,q)and reproduced.tobytes()==q.tobytes()and transform==row['transform']
    assert q.shape==(w*h+d,3)and np.isfinite(q).all()
    reused=reusable.get(gh(q));cert=reused[1]if reused else full_certificate(q);save(out/'certificates'/f'{key}.json',cert)
    if not cert['valid']:raise ValueError('Exact transformed geometry failed full gates: '+key)
    bounds=rectangle_bounds(q,w,h);diagnostics=contact_diagnostics(q,w,h)
    arrays[key]=q;arrays[key+'__original']=original
    encoded,offsets=encode(q,w,h);native_path=out/'native-reference-inputs'/f'{key}.in';native_path.write_text(encoded)
    certs[key]=dict(path=f'certificates/{key}.json',sha256=sha(out/'certificates'/f'{key}.json'),geometry_sha256=gh(q),exact_reuse_from=str(reused[0])if reused else None)
    seeds.append(dict(key=key,source_key=row['source_key'],source_label=row['source_label'],geometry_sha256=gh(q),original_geometry_sha256=gh(original),original_key=key+'__original',f_lower=bounds['f']['lower'],f_upper=bounds['f']['upper'],rectangle_bounds=bounds,certificate=certs[key],native_input=dict(path=f'native-reference-inputs/{key}.in',sha256=sha(native_path),rect_offsets=offsets,executed=False)))
    seedproof[key]=dict(source=row,rectangle_bounds=bounds,diagnostics=diagnostics,certificate=certs[key],source_profile_scope='Original source pose and its byte hash retained. Canonical optimization seed can change wall phase through the recorded transpose/translation. Old exact recipe profiles are retained separately in the broad manifest; compatibility must be rechecked after search.')
    print(json.dumps(dict(stage='exact_seed_certified',key=key,f=bounds['f'])),flush=True)
   best=min(seeds,key=lambda x:Decimal(x['f_upper']))
   config_families[family_key]=dict(w=w,h=h,d=d,n=w*h+d,reference_key=best['key'],reference_source_key=best['source_key'],reference_f_lower=best['f_lower'],reference_f_upper=best['f_upper'],seeds=seeds)
 np.savez_compressed(out/'rectangular-inputs.npz',**arrays)
 # Copy exact attribution bytes rather than narrowing inherited mixed-source notices.
 evidence_paths=[Path('artifacts/active-broad-frontier-v1/active_manifest.json')]
 evidence_paths += [p.relative_to(ROOT)for base in('vendor/notices','vendor/fq','vendor/lightning_ftmc')for p in(ROOT/base).rglob('*')if p.is_file()and (('notice'in p.name.lower()or'license'in p.name.lower()or p.name=='SOURCE_MANIFEST.json')and p.stat().st_size<2000000)]
 evidence=[]
 for relative in sorted(set(evidence_paths)):
  source=ROOT/relative;target=out/'evidence'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);evidence.append(dict(path=str(Path('evidence')/relative),source_path=str(relative),sha256=sha(source),bytes=source.stat().st_size))
 shutil.copyfile(inventory_path,out/'evidence/inventory.json');shutil.copyfile(__file__,out/'prepare-source.py')
 config=dict(schema_version=1,inputs_sha256=sha(out/'rectangular-inputs.npz'),baseline=inv['baseline'],families=config_families,no_native_control_execution=True,policy='Input data only; campaign protocol is separately frozen. Every actual composed full-puzzle output must pass the current canonical merge gates.')
 save(out/'rectangular-input-config.json',config)
 proof=dict(schema_version=1,inputs_sha256=config['inputs_sha256'],config_sha256=sha(out/'rectangular-input-config.json'),inventory_sha256=sha(inventory_path),provisional_inputs_sha256=sha(bank),prepare_source_sha256=sha(__file__),sources=inv['sources'],selected=seedproof,diversity=inv['diversity'],evidence=evidence,baseline=inv['baseline'],array_hashes={k:gh(v)for k,v in arrays.items()},all_transformed_gates_passed=True,no_native_execution=True,no_optimizer=True,seconds=time.monotonic()-started)
 save(out/'rectangular-input-proof.json',proof)
 print(json.dumps(dict(status='frozen_exact_inputs',inputs_sha256=config['inputs_sha256'],config_sha256=sha(out/'rectangular-input-config.json'),proof_sha256=sha(out/'rectangular-input-proof.json'),arrays=len(arrays),seconds=time.monotonic()-started)),flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--audit-seconds',type=float,default=90);ap.add_argument('--inventory-only',action='store_true');ap.add_argument('--finalize-inventory',type=Path);ap.add_argument('--reuse-certificates',type=Path);args=ap.parse_args()
 if args.finalize_inventory:
  finalize_inventory(args.finalize_inventory,args.out.resolve(),args.reuse_certificates);return
 started=time.monotonic();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
 pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text());assert pointer['raw']['sha256']==BASELINE
 candidates,sources,hist=collect();chosen,audit=select(candidates,time.monotonic()+args.audit_seconds)
 selected={};arrays={}
 for key,rows in chosen.items():
  selected[key]=[]
  for i,r in enumerate(rows):
   name=f'{key}__seed{i}';arrays[name]=r['pose'];arrays[name+'__original']=r['source_pose'];selected[key].append(dict(input_key=name,**public_meta(r)))
 np.savez_compressed(out/'selected-provisional.npz',**arrays)
 save(out/'inventory.json',dict(sources=sources,selection=selected,diversity=audit,baseline=pointer,provisional_inputs_sha256=sha(out/'selected-provisional.npz'),preparation_source_sha256=sha(__file__),seconds=time.monotonic()-started,status='selected_requires_exact_transformed_gates_and_final_proof',no_optimizer=True,no_native_run=True))
 shutil.copyfile(__file__,out/'prepare-source.py')
 print(json.dumps(dict(status='provisional_selection',inventory_sha256=sha(out/'inventory.json'),seconds=time.monotonic()-started,diversity={k:{a:v for a,v in d.items()if a not in('selected_pairwise_assignments',)}for k,d in audit.items()}),indent=2))
if __name__=='__main__':main()
