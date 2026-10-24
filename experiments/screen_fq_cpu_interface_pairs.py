"""Finite new-corner-profile screen; this does not certify complete layouts."""
import argparse
import os,time,json,hashlib,sys,math
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';started=time.monotonic()
import numpy as np
sys.path.insert(0,'experiments')
from compose_gadgets import extents
from extract_broad_active_frontier import orient,profiles,geometry_sha
from pinwheel_interlock import cross_gap
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--profiles',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args();root=args.out;root.mkdir(parents=True,exist_ok=False)
source=args.profiles;records=json.loads(source.read_text());ptr=json.loads(Path('artifacts/current-best-portfolio.json').read_text());base=json.loads(Path(ptr['safe']['official_report']).read_text());before={r['n']:float(r['side'])for r in base['results']}
bank=Path('artifacts/targeted-partners-v2/partners.npz');newbank=Path('artifacts/fq-cpu-followup-analysis-v2/donors.npz');oldbank=Path('artifacts/fq-cpu-followup-job-v3/inputs/reference.npz');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
profile_report=json.loads(source.with_name('report.json').read_text())
assert sha(source)==profile_report['profile_records_sha256']
assert sha(newbank)==profile_report['inputs']['new']['sha256']
assert sha(oldbank)==profile_report['inputs']['old']['sha256']
assert sha(bank)=='e961ca3ac4b18d6e0ee2460cf819fef3da4f718f60c2dde7a32f26392bbb1e2c'
assert sha(Path(ptr['safe']['official_report']))==ptr['safe']['official_report_sha256']
assert base['sha256']==ptr['safe']['sha256']
state={}
for r in records['new']:
 key=(r['w'],r['h'],tuple(r['br']),tuple(r['tl']))
 if key not in state or r['f']<state[key]['f']:state[key]=r
old={w:[r for r in records['old']if r['w']==w]for w in(8,20)}
oldBR={w:[min(r['br'][a]for r in old[w])for a in range(3)]for w in old};oldTL={w:[max(r['tl'][a]for r in old[w])for a in range(3)]for w in old}
partner_count=profile_pass=scalar_pass=0;jobs={};complete=True
with np.load(bank,allow_pickle=False)as z:
 for name in z.files:
  if time.monotonic()-started>65:complete=False;break
  w0,h0,d=map(int,name.split('__')[0].split('_'));p=z[name]
  for swap in (False,True):
   w,h=(h0,w0)if swap else(w0,h0)
   if not any(max(w+r['w'],h+r['h'])<=31 for r in state.values()):continue
   for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
    q=orient(p,swap,sx,sy);lo,hi=extents(q);f=float(max(hi.max(0)-lo.min(0)-[w,h]));pp=[profiles(q,w,h,a,a,32)for a in(30,45,60)];partner_count+=1
    for r in state.values():
     km=max(w+r['w'],h+r['h']);cost=max(f,r['f'])+5e-8
     ns=[(k,k*k+12+d)for k in range(km,32)if k*k+12+d<=1000 and before[k*k+12+d]>k+cost+1e-8]
     if not ns:continue
     for role in('new_first','new_second'):
      angles=[i for i in range(3)if (r['br'][i]<=pp[i]['tl_bin']<oldBR[r['w']][i] if role=='new_first' else oldTL[r['w']][i]<pp[i]['br_bin']<=r['tl'][i])]
      if not angles:continue
      profile_pass+=1;scalar_pass+=len(ns)
      identity=(r['geometry_sha256'],geometry_sha(q),role)
      jobs[identity]=dict(new=r,partner=dict(key=name,transform=[swap,sx,sy],w=w,h=h,d=d,f=f,geometry_sha256=geometry_sha(q)),role=role,angles=[(30,45,60)[i]for i in angles],targets=ns)

def gap(previous,current,width,height):
 q=current.copy();q[:,:2]+=[width,-height];return cross_gap(previous,q)
results=[]
with np.load(newbank,allow_pickle=False)as nz,np.load(oldbank,allow_pickle=False)as oz,np.load(bank,allow_pickle=False)as pz:
 for j in jobs.values():
  r=j['new'];p=j['partner'];new=orient(nz[r['source_key']],*r['transform']);partner=orient(pz[p['key']],*p['transform']);assert geometry_sha(new)==r['geometry_sha256']and geometry_sha(partner)==p['geometry_sha256']
  oldposes=[orient(oz[o['source_key']],*o['transform'])for o in old[r['w']]]
  if j['role']=='new_first':
   currentgap=gap(new,partner,r['w'],p['h']);oldgaps=[gap(o,partner,r['w'],p['h'])for o in oldposes]
  else:
   currentgap=gap(partner,new,p['w'],r['h']);oldgaps=[gap(partner,o,p['w'],r['h'])for o in oldposes]
  results.append({**j,'new_pair_sat_gap':currentgap,'best_old_pair_sat_gap':max(oldgaps),'measured_old_fail_new_pass':currentgap>=-1e-12 and max(oldgaps)<-1e-10})
report={'status':'complete'if complete else'bounded_partial','seconds':time.monotonic()-started,'new_profile_states':len(state),'oriented_partner_states':partner_count,'new_profile_compatible_jobs':profile_pass,'scalar_promising_containers':scalar_pass,'unique_pair_jobs':len(jobs),'measured_old_fail_new_pass':sum(r['measured_old_fail_new_pass']for r in results),'baseline':ptr['safe'],'sources':{str(p):sha(p)for p in(source,bank,newbank,oldbank,Path(__file__),source.with_name('report.json'),Path('experiments/compose_gadgets.py'),Path('experiments/extract_broad_active_frontier.py'),Path('experiments/pinwheel_interlock.py'))},'rows':results,'scope':'Whole-donor new discrete bins only,502 finite partners,30/45/60deg,mode0,all fitting k<=31; no crop/arbitrary-separator completeness claim.','no_gpu':True,'no_new_geometry_certification':True,'no_submission':True}
(root/'report.json').write_text(json.dumps(report,indent=2)+'\n');(root/'executed-source.py').write_bytes(Path(__file__).read_bytes());print(json.dumps({k:v for k,v in report.items()if k not in('rows','sources','baseline')},indent=2))
