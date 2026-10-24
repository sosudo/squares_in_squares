#!/usr/bin/env python3
"""Bounded corner crops from only the newly adopted18 public layouts."""
import time
ENTRY=time.monotonic()
import argparse,json,math,os
from pathlib import Path
import signal,subprocess,sys
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
from compose_gadgets import extents
from extract_broad_active_frontier import orient,profiles,geometry_sha
from fq_active_pilot import digest
from fq_variant_campaign import atomic_json,atomic_npz

ROOT=Path(__file__).resolve().parents[1]


def prefix_costs(path):
    result=np.full((32,32,64),np.inf)
    with np.load(path,allow_pickle=False)as bank:
        for key in bank.files:
            w,h,d=map(int,key.split('__')[0].split('_'));p=bank[key];lo,hi=extents(p)
            f=float(max(hi.max(0)-lo.min(0)-[w,h]))
            result[w,h,d]=min(result[w,h,d],f);result[h,w,d]=min(result[h,w,d],f)
    return np.minimum.accumulate(np.minimum.accumulate(result,axis=0),axis=1)


def run(args):
    started=time.monotonic();args.out.mkdir(parents=True,exist_ok=False)
    old=prefix_costs(args.partners);states={};coverage=[];counts={'scalar_candidates':0,'profiled_candidates':0}
    (args.out/'source-at-execution.py').write_bytes(Path(__file__).read_bytes())
    with np.load(args.new,allow_pickle=False)as archive:
        priority=[415,501,698,752]
        def source_order(key):
            n=int(key.split('_n')[-1])
            return(priority.index(n)if n in priority else len(priority),n)
        keys=sorted(archive.files,key=source_order)
        stopped=False
        for source in keys:
            if stopped:break
            p=archive[source];n=int(source.split('_n')[-1]);source_sha=geometry_sha(p)
            for trans in(False,True):
                if stopped:break
                for sx,sy in((1,1),(-1,1),(1,-1),(-1,-1)):
                    if time.monotonic()>=args.deadline:stopped=True;break
                    q=orient(p,trans,sx,sy);lo,hi=extents(q);maxw,maxh=np.minimum(31,np.floor(hi.max(0)+1e-7).astype(int))
                    wh=np.array([(w,h)for w in range(1,maxw+1)for h in range(1,maxh+1)if w*h<len(q)],dtype=int)
                    radius=np.maximum(np.maximum(hi[None,:,0]-wh[:,None,0],hi[None,:,1]-wh[:,None,1]),0.)
                    order=np.argsort(radius,axis=1,kind='stable');values=np.take_along_axis(radius,order,axis=1)
                    surplus=np.arange(1,len(q)+1)[None,:]-(wh[:,0]*wh[:,1])[:,None]
                    valid=(surplus>0)&(surplus<=63)&(values>1e-10)&(values<1.-1e-7)
                    bound=old[wh[:,0,None],wh[:,1,None],np.clip(surplus,0,63)]
                    valid&=values+3e-8<bound-1e-9
                    done=0;pending=np.argwhere(valid);counts['scalar_candidates']+=len(pending)
                    for index,(row,last)in enumerate(pending):
                        if index%32==0 and time.monotonic()>=args.deadline:stopped=True;break
                        w,h=map(int,wh[row]);d=int(surplus[row,last]);ids=order[row,:last+1]
                        crop=q[ids].copy();f=float(values[row,last])+3e-8
                        ps=[profiles(crop,w,h,a,a,32)for a in(30,45,60)];counts['profiled_candidates']+=1
                        br=tuple(x['br_bin']for x in ps);tl=tuple(x['tl_bin']for x in ps);state=(w,h,d,br,tl)
                        if state in states and f>=states[state]['f']-1e-11:continue
                        identity=geometry_sha(crop);states[state]={'pose':crop,'f':f,'w':w,'h':h,'d':d,
                            'source_n':n,'source_key':source,'source_geometry_sha256':source_sha,
                            'transform':[trans,sx,sy],'selected_source_ids':list(map(int,ids)),
                            'wall_phase':extents(crop)[0].min(0).tolist(),'geometry_sha256':identity,
                            'profiles':ps,'previous_prefix_cost':float(bound[row,last])if np.isfinite(bound[row,last])else None}
                        done+=1
                    coverage.append({'n':n,'transform':[trans,sx,sy],'available_scalar_candidates':len(pending),
                        'retained_updates':done,'orientation_complete':not stopped})
                    atomic_json(args.out/'progress.json',{'counts':counts,'coverage':coverage,
                        'retained_profile_states':len(states),'status':'bounded_partial'if stopped else'running'})
                    if stopped:break
    bank={};rows=[]
    for row in states.values():
        key=f"{row['w']}_{row['h']}_{row['d']}__public29_n{row['source_n']}_{row['geometry_sha256']}"
        bank[key]=row['pose'];rows.append({'key':key,**{k:v for k,v in row.items()if k!='pose'}})
    atomic_npz(args.out/'crops.npz',bank);atomic_json(args.out/'provenance.json',rows)
    manifest={'status':'bounded_partial'if stopped else'complete','seconds':time.monotonic()-started,
        'source_archive':str(args.new),'source_archive_sha256':digest(args.new),'partners_sha256':digest(args.partners),
        'source_sha256':digest(__file__),'crop_archive_sha256':digest(args.out/'crops.npz'),
        'provenance_sha256':digest(args.out/'provenance.json'),'retained_profile_states':len(bank),
        'canonical_types':len({(r['w'],r['h'],r['d'])for r in rows}),'source_cases':sorted({r['source_n']for r in rows}),
        'counts':counts,'coverage':coverage,'workers':1,'no_gpu':True,'no_submission':True,
        'scope':'Only18 public29 deltas; corner-prefix selected units/D4/wallphase preserved; '
                'cost beats finite private prefix minima; separate32-bin BR/TL triples at30/45/60degrees retained. '
                'Subset proposals only, no fresh emit-format certificate claimed; full new layouts must pass all gates.'}
    atomic_json(args.out/'manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items()if k not in('coverage','scope')}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--new',type=Path,default=ROOT/'artifacts/public-v29/incremental-donors/new-donors.npz')
    parser.add_argument('--partners',type=Path,default=ROOT/'artifacts/targeted-partners-v2/partners.npz')
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--deadline',type=float,help=argparse.SUPPRESS);args=parser.parse_args()
    if args.child:return run(args)
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child',
        '--deadline',str(ENTRY+14.)],start_new_session=True);forced=False
    try:process.wait(timeout=max(.01,ENTRY+24.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=.5)
    result={'seconds':time.monotonic()-ENTRY,'returncode':process.returncode,'workers':1,
        'maximum_seconds':25,'outer_limit_enforced':forced}
    if args.out.exists():atomic_json(args.out/'supervisor.json',result)
    print(json.dumps(result),flush=True);raise SystemExit(process.returncode)


if __name__=='__main__':main()
