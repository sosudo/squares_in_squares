#!/usr/bin/env python3
"""Bounded N+1 insertion and N-1 interior deletion with independent fq repair.

No inherited near-parent bloat filter: a new surplus type is admitted whenever
its geometry is certified and its interval-certified rectangular excess is <1.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
import fq_active_pilot as fq
from fq_coherent_clusters import Deadline, alarm, grouped_run, transpose, atom_json, atom_npz, EXTRA_BANKS
from compose_gadgets import normalize

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_submission import (Square,validate_puzzle,_geometry,_iv_min,_iv_max,_endpoint_text)

PARENTS=((5,17,7),(7,19,13),(7,20,14),(10,23,14),(9,20,12))
OPTIONS={
 'insert_alm':['--loosen','1.001','--outer','60','--pit','100','--flip-top','12'],
 'insert_soft':['--loosen','1.001','--soft-a0','.12','--soft-compress','--soft-steps','10',
                '--hold-f','1','--outer','45','--pit','80','--flip-top','12'],
 'delete_alm':['--loosen','1','--outer','45','--pit','100','--flip-top','16'],
}


def load_banks(focus):
    current=json.loads((focus/'current.json').read_text());snapshot=Path(current['snapshot'])
    if fq.digest(snapshot/'analysis.json')!=current['analysis_sha256']:raise ValueError('Focus checkpoint hash')
    analysis=json.loads((snapshot/'analysis.json').read_text())
    sources=[(snapshot/'best_bank.npz',analysis['best_bank_sha256'])]
    sources += [(ROOT/name,sha)for name,sha in EXTRA_BANKS]
    sources += [(ROOT/'artifacts/fq-coherent-v1/donors.npz','3ac366321c97e1ad6d66eef6d0bf51645a96db5dde0b9ac8d1faddc60d0b679e')]
    bank={};proof=[]
    for path,expected in sources:
        if fq.digest(path)!=expected:raise ValueError('Input bank hash mismatch')
        proof.append({'path':str(path.resolve()),'sha256':expected})
        with np.load(path,allow_pickle=False)as z:
            for name in z.files:
                w,h,d=map(int,name.split('__')[0].split('_'));p=np.asarray(z[name],float)
                if p.shape!=(w*h+d,3)or not np.isfinite(p).all():raise ValueError('Input geometry')
                if w>h:w,h=h,w;p=transpose(p)
                else:p=normalize(p)
                key=f'{w}_{h}_{d}';f=fq.bloat(p,w,h)
                if key not in bank or f<bank[key]['excess']:
                    bank[key]={'p':p,'excess':f,'source':str(path.resolve()),'archive_key':name}
    return bank,proof


def candidate_angles(p):
    folded=(p[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
    values,counts=np.unique(np.round(folded,4),return_counts=True)
    peaks=values[np.argsort(-counts)[:5]]
    angles=np.r_[0.,math.pi/4,-math.pi/4,peaks,-peaks]
    return np.unique(np.round((angles+math.pi/4)%(math.pi/2)-math.pi/4,12))


def insertion_sites(p,w,h,step=.25,keep=4):
    """Rank wall-feasible centres by sum of positive SAT penetrations."""
    f=fq.bloat(p,w,h);W,H=w+f,h+f;ct,st=np.cos(p[:,2]),np.sin(p[:,2]);ranked=[]
    for a in candidate_angles(p):
        ca,sa=math.cos(a),math.sin(a);e=.5*(abs(ca)+abs(sa))
        xs=np.unique(np.r_[np.arange(e,W-e+1e-10,step),W/2,W-e])
        ys=np.unique(np.r_[np.arange(e,H-e+1e-10,step),H/2,H-e])
        xy=np.stack(np.meshgrid(xs,ys,indexing='ij'),-1).reshape(-1,2)
        radius=.5*(1+abs(np.cos(p[:,2]-a))+abs(np.sin(p[:,2]-a)))
        for begin in range(0,len(xy),512):
            centres=xy[begin:begin+512];dx=centres[:,None,0]-p[None,:,0];dy=centres[:,None,1]-p[None,:,1]
            gap=np.maximum.reduce([abs(dx*ca+dy*sa),abs(-dx*sa+dy*ca),
                                   abs(dx*ct+dy*st),abs(-dx*st+dy*ct)])-radius
            penetration=np.maximum(-gap,0);total=penetration.sum(1);peak=penetration.max(1)
            for i in np.argsort(total,kind='stable')[:16]:
                ranked.append((float(total[i]),float(peak[i]),float(centres[i,0]),float(centres[i,1]),float(a)))
    ranked.sort();selected=[]
    for score,peak,x,y,a in ranked:
        if any(math.hypot(x-s['x'],y-s['y'])<.6 and abs(((a-s['angle']+math.pi/4)%(math.pi/2))-math.pi/4)<.15 for s in selected):continue
        selected.append({'x':x,'y':y,'angle':a,'sat_penetration_sum':score,'maximum_pair_penetration':peak})
        if len(selected)>=keep:break
    return selected


def delete_junction(p,w,h):
    f=fq.bloat(p,w,h);e=.5*(abs(np.cos(p[:,2]))+abs(np.sin(p[:,2])))
    slack=np.minimum.reduce((p[:,0]-e,p[:,1]-e,w+f-p[:,0]-e,h+f-p[:,1]-e))
    folded=(p[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
    degree=np.zeros(len(p));interfaces=np.zeros(len(p))
    for i,j in cKDTree(p[:,:2]).query_pairs(1.55):
        degree[i]+=1;degree[j]+=1
        if abs(((folded[i]-folded[j]+math.pi/4)%(math.pi/2))-math.pi/4)>.05:
            interfaces[i]+=1;interfaces[j]+=1
    eligible=np.flatnonzero((abs(folded)>.02)&(slack>.05))
    if not len(eligible):eligible=np.flatnonzero(abs(folded)>.02)
    if not len(eligible):raise ValueError('No tilted junction')
    index=int(max(eligible,key=lambda i:(interfaces[i],degree[i],slack[i])))
    return index,{'index':index,'wall_slack':float(slack[index]),'near_neighbors':int(degree[index]),
                  'orientation_interfaces':int(interfaces[index]),'square':p[index].tolist()}


def certify(p,w,h,metric):
    squares=[Square(*(format(float(v),'.17g')for v in row))for row in p]
    independent=validate_puzzle(len(p),squares)
    if not independent['valid']:return {'valid':False,'independent':independent}
    g=_geometry(squares,100)
    spans=[_iv_max([q[axis]+q[4]for q in g])-_iv_min([q[axis]-q[4]for q in g])for axis in(0,1)]
    excess=_iv_max([spans[0]-w,spans[1]-h])
    rectangle={'excess_lower':_endpoint_text(excess.a,False),'excess_upper':_endpoint_text(excess.b,True),
               'strictly_below_one':bool(excess.b<1)}
    rows=[dict(n=str(len(p)),square_id=str(i),x=s.x,y=s.y,angle=s.angle)for i,s in enumerate(squares)]
    raw=metric._evaluate_puzzle_worker((len(p),rows))
    numeric=pd.read_csv(io.StringIO(pd.DataFrame(rows).to_csv(index=False)))
    rounded=metric._evaluate_puzzle_worker((len(p),list(csv.DictReader(io.StringIO(numeric.to_csv(index=False))))))
    return {'valid':rectangle['strictly_below_one']and raw[3]==rounded[3]=='ok'and abs(raw[1]-rounded[1])<=1e-10,
            'independent':independent,'rectangle':rectangle,'official_raw':raw,'ordinary_roundtrip':rounded}


def run_one(p,w,h,d,mode,tag,binary,out,metric,cap,deadline):
    if len(p)!=w*h+d:raise ValueError('New-type count mismatch')
    text,offsets=fq.encode(p,w,h);inp=out/(tag+'.in');dst=out/(tag+'.out');inp.write_text(text)
    command=[str(binary),'quench','--in',str(inp),'--out',str(dst),'--rect-dx',str(offsets[0]),
             '--rect-dy',str(offsets[1]),'--seed','1441001']+OPTIONS[mode]
    record={'type':f'{w}_{h}_{d}','count':len(p),'mode':mode,'command':command,'input_sha256':fq.digest(inp)}
    def finish(status,pose=None):
        record['status']=status
        return record,pose
    start=time.monotonic();previous=signal.getsignal(signal.SIGALRM);signal.signal(signal.SIGALRM,alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL,max(.01,min(cap,deadline-start)))
        result=grouped_run(command,timeout=max(.01,min(cap,deadline-start)))
        (out/(tag+'.log')).write_text(result.stdout+'\n'+result.stderr)
        if result.returncode or not dst.exists():return finish('fq-failed')
        record['fq']=json.loads(result.stdout.strip().splitlines()[-1]);q=fq.decode(dst,len(p))
        if q is None:return finish('failed-clearance')
        record['excess']=fq.bloat(q,w,h)
        if record['excess']>=1:return finish('excess-at-least-one')
        record['certificate']=certify(q,w,h,metric)
        if not record['certificate']['valid']:return finish('failed-certificate')
        record.update(status='certified',geometry_sha256=__import__('hashlib').sha256(q.astype('<f8').tobytes()).hexdigest())
        return record,q
    except (Deadline,subprocess.TimeoutExpired):return finish('whole-trial-timeout')
    except Exception as exc:
        record.update(error_type=type(exc).__name__,error=str(exc)[:200])
        return finish('error')
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        record['elapsed_seconds']=time.monotonic()-start


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--focus',type=Path,default=ROOT/'artifacts/fq-focus-v1')
    ap.add_argument('--seconds',type=float,default=240)
    ap.add_argument('--trial-seconds',type=float,default=18)
    ap.add_argument('--smoke',action='store_true')
    args=ap.parse_args()
    if not 0<args.seconds<=280 or not 0<args.trial_seconds<=25:ap.error('Bounded one-worker pilot only')
    start=time.monotonic();deadline=start+args.seconds;args.out.mkdir(parents=True,exist_ok=False)
    binary=args.out/'fq';shutil.copy2(args.focus/'inputs/fq',binary);binary.chmod(0o500);binary_sha=fq.digest(binary)
    if binary_sha!=json.loads((args.focus/'manifest.json').read_text())['binary_sha256']:raise ValueError('Binary snapshot hash')
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    for name in ['fq_active_pilot.py','fq_coherent_clusters.py','compose_gadgets.py']:
        shutil.copy2(ROOT/'experiments'/name,args.out/name)
    metric=fq.load_metric(ROOT/'research/official_metric_v17.py')
    if args.smoke:
        control_csv=ROOT/'artifacts/submission-fq-broad-polish-v1-safe.csv';rows=[]
        with control_csv.open()as stream:
            for row in csv.DictReader(stream):
                if int(row['n'])>5:break
                if int(row['n'])==5:rows.append([float(row[k])for k in('x','y','angle')])
        known=normalize(np.array(rows));index=int(np.argmax(abs((known[:,2]+math.pi/4)%(math.pi/2)-math.pi/4)))
        parent=np.delete(known,index,axis=0);sites=insertion_sites(parent,2,2);site=sites[0]
        augmented=np.vstack((parent,[site['x'],site['y'],site['angle']]))
        record,q=run_one(augmented,2,2,1,'insert_alm','recover-five',binary.resolve(),args.out.resolve(),metric,args.trial_seconds,deadline)
        proof={'removed_square_index':index,'known_five_sha256':__import__('hashlib').sha256(known.astype('<f8').tobytes()).hexdigest(),
               'chosen_site':site,'count_recovered':len(q)if q is not None else None,'record':record,
               'passed':q is not None and len(q)==5 and record['excess']<fq.bloat(known,2,2)+1e-6}
        atom_json(args.out/'smoke.json',proof);print(json.dumps(proof),flush=True)
        if not proof['passed']:raise SystemExit(1)
        return
    bank,provenance=load_banks(args.focus)
    for i,item in enumerate(provenance):shutil.copy2(item['path'],args.out/f'reference-{i}.npz')
    parents={f'{w}_{h}_{d}':bank[f'{w}_{h}_{d}']['p']for w,h,d in PARENTS};atom_npz(args.out/'parents.npz',parents)
    manifest={'workers':1,'binary_sha256':binary_sha,'source_sha256':fq.digest(Path(__file__)),
              'source_commit':fq.SOURCE_COMMIT,'source_license':'MIT; vendor/fq/NOTICE','references':provenance,
              'options':OPTIONS,'seconds':args.seconds,'complete_trial_seconds':args.trial_seconds,
              'site_grid_step':.25,'site_ranking':'sum of positive separating-axis penetrations',
              'acceptance':'independent and raw/default-pandas official valid; interval rectangle excess<1; no parent-bloat comparison'}
    atom_json(args.out/'manifest.json',manifest);jobs=[]
    for j,(w,h,d)in enumerate(PARENTS):
        p=parents[f'{w}_{h}_{d}'];sites=insertion_sites(p,w,h)
        for k in range(2 if j<3 else 1):
            site=sites[k];augmented=np.vstack((p,[site['x'],site['y'],site['angle']]))
            jobs.append((augmented,w,h,d+1,'insert_alm'if k==0 else'insert_soft',{'parent_type':f'{w}_{h}_{d}','edit':'insert','site':site}))
    for w,h,d in PARENTS[:4]:
        p=parents[f'{w}_{h}_{d}'];index,selection=delete_junction(p,w,h)
        jobs.append((np.delete(p,index,axis=0),w,h,d-1,'delete_alm',{'parent_type':f'{w}_{h}_{d}','edit':'delete','selection':selection}))
    records=[];donors={};inserts={};deletes={}
    print(json.dumps({'stage':'start','planned':len(jobs),'workers':1,'seconds':args.seconds}),flush=True)
    for i,(p,w,h,d,mode,edit)in enumerate(jobs):
        if time.monotonic()>deadline-2:break
        record,q=run_one(p,w,h,d,mode,f'trial-{i:02d}',binary.resolve(),args.out.resolve(),metric,args.trial_seconds,deadline)
        record.update(trial_id=i,**edit)
        if q is not None:
            target=f'{w}_{h}_{d}';reference=bank.get(target);record['matching_new_type_reference_excess']=reference['excess']if reference else None
            record['gain_vs_matching_new_type']=reference['excess']-record['excess']if reference else None
            key=target+'__'+edit['edit']+'_'+record['geometry_sha256'][:24];donors[key]=q
            (inserts if edit['edit']=='insert'else deletes)[key]=q
        records.append(record);atom_json(args.out/'results.json',records)
        for name,poses in [('donors',donors),('insert-donors',inserts),('delete-donors',deletes)]:atom_npz(args.out/(name+'.npz'),poses)
        print(json.dumps({k:record.get(k)for k in('trial_id','edit','type','status','excess','gain_vs_matching_new_type')}),flush=True)
    if fq.digest(binary)!=binary_sha:raise ValueError('Executable snapshot changed')
    summary={'elapsed_seconds':time.monotonic()-start,'planned':len(jobs),'attempted':len(records),
             'certified_insertions':len(inserts),'certified_deletions':len(deletes),
             'new_types_without_reference':sorted({r['type']for r in records if r['status']=='certified'and r['matching_new_type_reference_excess']is None}),
             'improved_known_new_types':sorted({r['type']for r in records if r.get('gain_vs_matching_new_type',0)is not None and r.get('gain_vs_matching_new_type',0)>1e-7}),
             'status_counts':{s:sum(r['status']==s for r in records)for s in sorted({r['status']for r in records})},
             'donors_sha256':fq.digest(args.out/'donors.npz')}
    atom_json(args.out/'summary.json',summary);print(json.dumps({'stage':'complete',**summary}),flush=True)


if __name__=='__main__':main()
