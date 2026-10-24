"""Bounded translated-rectangle mining of exact source-coordinate subsets.

Queries W=w+f,H=h+f for current donor types. This is not a square-window repeat.
No source coordinate or angle is changed. Every exported subset passes the
unchanged official raw/default-pandas and independent interval gates.
"""
import time
ENTRY_STARTED=time.monotonic()
import argparse
from collections import Counter
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import signal
import subprocess
import sys
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import numpy as np
import pandas as pd
from exact_square_window import WindowSolver,boxes
from fq_capacity_probe import full_certificate
from compose_gadgets import extents
ROOT=Path(__file__).resolve().parents[1]
FIVE={(7,21,15),(8,20,12),(6,22,16),(10,23,14),(9,22,16)}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def array_sha(p):return hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest()
def atom(path,value):
    temp=path.with_suffix(path.suffix+'.incoming');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)
def atom_npz(path,values):
    temp=path.with_suffix('.npz.incoming')
    with temp.open('wb')as f:np.savez_compressed(f,**values)
    temp.replace(path)


class RectangleSolver(WindowSolver):
    def query(self,width,height,timeout=None):
        return self.exchange(f'QUERY {float(width):.17g} {float(height):.17g}\n',timeout)


def compile_solver(path):
    source=Path(__file__).with_suffix('.cpp')
    subprocess.run(['g++','-std=c++17','-O3',str(source),'-o',str(path)],
                   check=True,capture_output=True,timeout=20)
    return {'source_sha256':sha(source),'binary_sha256':sha(path)}


def brute(p,width,height):
    b=boxes(p);valid=(b[:,2]-b[:,0]<=width)&(b[:,3]-b[:,1]<=height);b=b[valid]
    if not len(b):return 0
    low=b[:,2:]-[width,height];high=b[:,:2]
    xs=np.unique(np.r_[low[:,0],high[:,0]]);ys=np.unique(np.r_[low[:,1],high[:,1]])
    return max(int(((low[:,0]<=x)&(high[:,0]>=x)&(low[:,1]<=y)&(high[:,1]>=y)).sum())
               for x in xs for y in ys)


def controls(binary):
    grid=np.array([[x+.5,y+.5,0.]for x in range(3)for y in range(2)])
    tests=[]
    with RectangleSolver(binary)as solver:
        solver.load(grid)
        for width,height,count in [(3.,2.,6),(2.,3.,4),(3.,1.,3),(2.999,2.,4)]:
            r=solver.query(width,height);assert r['count']==count,(width,height,r)
            tests.append({'width':width,'height':height,'count':count})
        rng=np.random.default_rng(652271)
        for trial in range(20):
            p=rng.uniform(-2,5,(12,3));p[:,2]=rng.uniform(-.75,.75,12)
            width,height=rng.uniform(1.4,4.3,2);solver.load(p)
            r=solver.query(width,height);expected=brute(p,width,height)
            assert r['count']==expected,(trial,r,expected)
            b=boxes(p[r['ids']]);assert len(b)==r['count']
            if len(b):
                assert np.all(b[:,0]>=r['x']-1e-12)and np.all(b[:,2]<=r['x']+width+1e-12)
                assert np.all(b[:,1]>=r['y']-1e-12)and np.all(b[:,3]<=r['y']+height+1e-12)
    cert=full_certificate(grid)
    assert cert['valid']
    return {'valid':True,'non_square_and_closed_boundary_controls':tests,
            'random_rectangular_brute_force_comparisons':20,'grid_raw_default_pandas_interval':cert,
            'binary_sha256':sha(binary),'cpp_sha256':sha(Path(__file__).with_suffix('.cpp'))}


def references(args):
    targets=set()
    with np.load(args.target_bank,allow_pickle=False)as z:
        for key in z.files:
            w,h,d=map(int,key.split('__')[0].split('_'));targets.add((min(w,h),max(w,h),d))
    targets|=FIVE|{(9,22,11)}
    best={};inputs=[]
    for path in args.reference:
        digest=sha(path);inputs.append({'path':str(path),'sha256':digest})
        with np.load(path,allow_pickle=False)as z:
            for key in z.files:
                try:w,h,d=map(int,key.split('__')[0].split('_'))
                except ValueError:continue
                family=(min(w,h),max(w,h),d)
                if family not in targets:continue
                q=np.asarray(z[key],dtype=float)
                if q.shape!=(w*h+d,3)or not np.isfinite(q).all():raise ValueError('Reference geometry invalid')
                lo,hi=extents(q);f=float(max(hi.max(0)-lo.min(0)-[w,h]))
                if not 0<f<1:continue
                rec={'family':list(family),'bloat':f,'source':str(path),'archive_sha256':digest,
                     'array_key':key,'array_sha256':array_sha(q),'original_orientation':[w,h,d]}
                if family not in best or f<best[family]['bloat']:best[family]=rec
    missing=targets-set(best)
    if missing:raise ValueError('Missing current family references:'+str(sorted(missing)))
    ordered=sorted(best,key=lambda key:(key not in FIVE,key!=(9,22,11),key))
    return best,ordered,inputs


def campaign(args):
    os.setsid();deadline=ENTRY_STARTED+args.seconds-5
    args.out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();stats=Counter();records=[];donors={};updates={}
    def expired(signum,frame):raise TimeoutError('Bounded rectangle campaign')
    previous=signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
    try:
        control=json.loads(args.control.read_text())
        if not control['valid']or control['binary_sha256']!=sha(args.binary):raise ValueError('Passing exact binary control required')
        best,ordered,ref_inputs=references(args);fbest={k:r['bloat']for k,r in best.items()}
        full_manifest=json.loads(args.full_manifest.read_text())
        if sha(args.full_sources)!=full_manifest['archive_sha256']:raise ValueError('Whole witness source hash mismatch')
        groups=[];source_records=[]
        for path in [args.full_sources,*args.source_npz,*args.reference]:
            digest=sha(path)
            with np.load(path,allow_pickle=False)as z:
                poses=[(str(path)+':'+key,np.array(z[key],dtype=float,copy=True),key,digest,str(path))for key in z.files]
            for _,q,_,_,_ in poses:
                if q.ndim!=2 or q.shape[1]!=3 or not np.isfinite(q).all():raise ValueError('Source pose invalid')
            groups.append(poses);source_records.append({'path':str(path),'sha256':digest,'poses':len(poses)})
        if args.portfolio:
            frame=pd.read_csv(args.portfolio,float_precision='round_trip')
            portfolio_sha=sha(args.portfolio)
            poses=[('portfolio:'+str(n),g.sort_values('square_id')[['x','y','angle']].to_numpy(float),str(n),portfolio_sha,str(args.portfolio))
                   for n,g in frame.groupby('n')if len(g)>4]
            groups.append(poses);source_records.append({'path':str(args.portfolio),'sha256':sha(args.portfolio),'poses':len(poses)})
        rng=np.random.default_rng(793367)
        for group in groups:rng.shuffle(group)
        sources=[group[i]for i in range(max(map(len,groups)))for group in groups if i<len(group)]
        manifest={'sources':source_records,'full_public_manifest':str(args.full_manifest),
                  'full_public_manifest_sha256':sha(args.full_manifest),'source_commit':full_manifest['source_commit'],
                  'reference_inputs':ref_inputs,'initial_orientation_fair_references':{str(k):v for k,v in best.items()},
                  'binary_sha256':sha(args.binary),'cpp_sha256':sha(Path(__file__).with_suffix('.cpp')),
                  'python_sha256':sha(Path(__file__)),'control_sha256':sha(args.control),'seconds':args.seconds,'workers':1,
                  'source_pose_count':len(sources),'target_families':len(ordered),'requested_margin':1e-6,
                  'square_queries':False,'coordinate_changes':False,'no_gpu':True,'no_submission':True}
        atom(args.out/'manifest.json',manifest)
        def checkpoint(status):
            atom_npz(args.out/'donors.npz',donors)
            atom(args.out/'report.json',{'status':status,'manifest_sha256':sha(args.out/'manifest.json'),
                'elapsed_seconds':time.monotonic()-ENTRY_STARTED,'stats':dict(stats),'records':records,
                'orientation_fair_best_bloats':{str(k):v for k,v in fbest.items()},'reference_updates':updates,
                'certified_variants':len(donors),'donors_sha256':sha(args.out/'donors.npz')})
        checkpoint('configured');seen=set()
        with RectangleSolver(args.binary)as solver:
            for label,q,source_key,source_sha,source_path in sources:
                if time.monotonic()>=deadline-2:break
                source_array_sha=array_sha(q);solver.load(q);stats['source_poses_visited']+=1
                for family in ordered:
                    w,h,d=family;m=w*h+d
                    if len(q)<m:continue
                    for transpose in (False,True):
                        W0,H0=(h,w)if transpose else(w,h);upper=fbest[family]-1e-6
                        if upper<=0:continue
                        stats['threshold_queries']+=1
                        result=solver.query(W0+upper,H0+upper,timeout=max(.001,min(2.,deadline-time.monotonic())))
                        if result['count']<m:continue
                        stats['threshold_hits']+=1
                        initial_result,initial_upper=result,upper
                        lower=max(0.,(-(w+h)+math.sqrt((w-h)**2+4*m))/2)
                        for _ in range(24):
                            if upper-lower<1e-7 or time.monotonic()>=deadline-2:break
                            middle=(upper+lower)/2;stats['refinement_queries']+=1
                            trial=solver.query(W0+middle,H0+middle,timeout=max(.001,min(2.,deadline-time.monotonic())))
                            if trial['count']>=m:upper,result=middle,trial
                            else:lower=middle
                        variants=[(result['ids'][:m],result,upper)]
                        if initial_result['count']>m and initial_result['count']-W0*H0<=63:
                            variants.append((initial_result['ids'],initial_result,initial_upper))
                        for ids,window,window_f in variants:
                            selected=np.array(q[ids],copy=True);geometry=array_sha(selected)
                            if geometry in seen:continue
                            seen.add(geometry);lo,hi=extents(selected);f=float(max(hi.max(0)-lo.min(0)-[W0,H0]))
                            surplus=len(selected)-W0*H0
                            if not 1<=surplus<=63 or f>=best[family]['bloat']-1e-7:continue
                            certificate=full_certificate(selected);stats['full_certifications']+=1
                            if not certificate['valid']:stats['geometry_or_transport_rejected']+=1;continue
                            identity=f'{W0}_{H0}_{surplus}__rectwindow_'+geometry[:20]
                            donors[identity]=selected
                            rec={'donor_key':identity,'family':list(family),'orientation':[W0,H0],
                                 'count':len(selected),'surplus':surplus,'bloat':f,'reference_bloat':best[family]['bloat'],
                                 'source_label':label,'source_path':source_path,'source_archive_sha256':source_sha,
                                 'source_array_key':source_key,'source_array_sha256':source_array_sha,
                                 'source_square_ids':ids,'geometry_sha256':geometry,'exact_source_coordinates_preserved':True,
                                 'window_lower_left':[window['x'],window['y']],'window_dimensions':[W0+window_f,H0+window_f],
                                 'certificate':certificate}
                            records.append(rec);stats['certified_variants']+=1
                            if len(selected)==m and f<fbest[family]:
                                fbest[family]=f;updates[str(family)]=identity
                            checkpoint('running')
                            print(json.dumps({'family':family,'count':len(selected),'bloat':f,'old':best[family]['bloat'],
                                              'seconds':time.monotonic()-ENTRY_STARTED}),flush=True)
                stats['completed_source_poses']+=1
                if stats['source_poses_visited']%25==0:checkpoint('running')
        stats['all_sources_scanned']=int(stats['completed_source_poses']==len(sources));checkpoint('bounded_complete')
    except TimeoutError:
        stats['timed_out']=1
        if (args.out/'manifest.json').exists():checkpoint('bounded_partial')
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--controls-only',action='store_true');ap.add_argument('--control',type=Path)
    ap.add_argument('--target-bank',type=Path);ap.add_argument('--reference',type=Path,action='append',default=[])
    ap.add_argument('--full-sources',type=Path);ap.add_argument('--full-manifest',type=Path)
    ap.add_argument('--source-npz',type=Path,action='append',default=[]);ap.add_argument('--portfolio',type=Path)
    ap.add_argument('--seconds',type=float,default=295.)
    args=ap.parse_args()
    if args.out.exists():raise ValueError('Require a new immutable result directory')
    if args.controls_only:
        args.out.mkdir(parents=True);compile_solver(args.binary);r=controls(args.binary);atom(args.out/'controls.json',r)
        print(json.dumps({k:v for k,v in r.items()if k!='grid_raw_default_pandas_interval'}));return
    if not 10<args.seconds<=300 or not all([args.control,args.target_bank,args.reference,args.full_sources,args.full_manifest]):raise ValueError('Missing bounded production arguments')
    process=mp.get_context('fork').Process(target=campaign,args=(args,));process.start()
    process.join(max(0.,args.seconds-1.5-(time.monotonic()-ENTRY_STARTED)));enforced=process.is_alive()
    if enforced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:process.kill()
        process.join(.4)
    receipt={'seconds':time.monotonic()-ENTRY_STARTED,'bound_seconds':args.seconds,'exitcode':process.exitcode,
             'hard_deadline_enforced':enforced,'workers':1}
    if args.out.exists():atom(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt))
    if process.exitcode and not enforced:raise SystemExit(process.exitcode)


if __name__=='__main__':main()
