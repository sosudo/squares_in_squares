"""Bounded scalar staircase proposals followed by exact finite-palette SAT joins.

No separating-line profile restricts proposals. Failed joins are learned only
when every retained pose pair for that directed type edge fails exact SAT.
The finite beam/palette is heuristic; final raw/default-pandas official and
interval checks remain mandatory. No GPU or competition submission.
"""
import time
ENTRY_STARTED = time.monotonic()
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[var] = '1'
import numpy as np
import pandas as pd
from compose_gadgets import extents, normalize, legalize, side
from cpu_recipe_replay import cross_block_separated, public_functions
from extract_broad_active_frontier import orient
from ftmc_certified_archive import _fingerprint
from fq_capacity_probe import full_certificate
ROOT = Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def array_sha(p): return hashlib.sha256(np.asarray(p, dtype='<f8').tobytes()).hexdigest()
def atom(path, data):
    temp = path.with_suffix(path.suffix+'.incoming')
    temp.write_text(json.dumps(data, indent=2)+'\n'); temp.replace(path)


def proposals(binary, types, blocked, queries, remaining):
    text = f'{len(types)} {len(blocked)} {len(queries)}\n'
    text += ''.join(f"{t['w']} {t['h']} {t['d']} {t['f']:.17g}\n" for t in types)
    text += ''.join(f'{a} {b}\n' for a, b in sorted(blocked))
    text += ''.join(f'{n} {math.isqrt(n)} {n-math.isqrt(n)**2}\n' for n in queries)
    result = subprocess.run([str(binary)], input=text, text=True, capture_output=True,
                            timeout=max(.1, min(25., remaining)), check=True)
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def build(selected, modes, k, stitch):
    gadgets = [dict(w=x['w'], h=x['h'], dm=x['d'], f=x['f'], donor=i)
               for i, x in enumerate(selected)]
    p, _ = stitch(list(enumerate(modes)), gadgets,
                  [(x['pose'], x['source']) for x in selected], box=(k, k))
    expected = k*k+sum(x['d'] for x in selected)
    if len(p) != expected: raise ValueError('Staircase count mismatch')
    return legalize(p)


def positive_control(binary, stitch):
    L = 2+math.sqrt(.5)
    q = legalize(np.array([[.5,.5,0.], [L-.5,.5,0.], [.5,L-.5,0.],
                           [L-.5,L-.5,0.], [L/2,L/2,np.pi/4]]))
    t = dict(w=2,h=2,d=1,f=side(q)-2)
    pp = proposals(binary, [t], set(), [18,27], 10.)
    selected = [dict(t,pose=q,source='five-square control')]*2
    assert not cross_block_separated(q,q,2,2,0)
    usable = next(p for p in pp if p['n']==27 and len(p['chain'])==2
                  and p['chain'][1][1] in (1,2))
    constructed = build(selected,[m for _,m in usable['chain']],5,stitch)
    certificate = full_certificate(constructed)
    if not certificate['valid']: raise ValueError('Known buffered chain control failed')
    return {'valid': True, 'native_scalar_proposals':len(pp),
            'unseparated_n18_rejected_by_sat':True, 'buffered_n27_count':len(constructed),
            'full_certificate':certificate}


def palette(base, banks, high_descriptor, cap=8):
    raw = defaultdict(dict); inputs = []
    def one(w,h,d,p,source):
        if not (1<=w<=31 and 1<=h<=31 and 1<=d<=63) or p.shape!=(w*h+d,3): return
        q=normalize(p); f=side(q)-max(w,h)
        _,hi=extents(q); f=float(max(hi.max(0)-[w,h]))
        if not np.isfinite(q).all() or not 0<f<.999999: return
        signature=_fingerprint(q)
        old=raw[w,h,d].get(signature)
        if old is None or f<old['f']:
            raw[w,h,d][signature]=dict(w=w,h=h,d=d,pose=q,f=f,source=source)
    for n,p in base.items():
        k=math.isqrt(n); one(k,k,n-k*k,p,'baseline:'+str(n))
    meta=json.loads(high_descriptor.read_text())['donors'] if high_descriptor else {}
    for path in banks:
        digest=sha(path); inputs.append({'path':str(path),'sha256':digest})
        with np.load(path,allow_pickle=False) as z:
            for key in z.files:
                p=np.asarray(z[key],dtype=float)
                try: w,h,d=map(int,key.split('__')[0].split('_'))
                except ValueError:
                    if key in meta:
                        m=meta[key]['original_crop_metadata']; w,h,d=m['nominal_width'],m['nominal_height'],m['surplus']
                    else:
                        w=h=math.isqrt(len(p)); d=len(p)-w*h
                one(w,h,d,p,str(path)+':'+key)
    oriented=defaultdict(list)
    for values in raw.values():
        # Two independent coarse families; all four reflections are retained.
        for item in sorted(values.values(),key=lambda p:p['f'])[:2]:
            for trans in (False,True):
                w,h=(item['h'],item['w']) if trans else (item['w'],item['h'])
                for sx,sy in [(1,1),(-1,1),(1,-1),(-1,-1)]:
                    q=orient(item['pose'],trans,sx,sy); _,hi=extents(q)
                    f=math.ceil((float(max(hi.max(0)-[w,h]))+3e-8)*1e9)*1e-9
                    if f>=1: continue
                    oriented[w,h,item['d']].append(dict(w=w,h=h,d=item['d'],f=f,pose=q,
                        source=item['source'],transform=[trans,sx,sy],geometry_sha256=array_sha(q)))
    types=[];options={};uid=0
    for dimensions,values in sorted(oriented.items()):
        chosen=[];seen=set()
        for p in sorted(values,key=lambda q:q['f']):
            key=hashlib.sha256(np.round(p['pose'],8).tobytes()).hexdigest()
            if key in seen: continue
            seen.add(key); p['uid']=uid;uid+=1;chosen.append(p)
            if len(chosen)>=cap: break
        if not chosen: continue
        tid=len(types);w,h,d=dimensions
        types.append(dict(w=w,h=h,d=d,f=min(p['f']for p in chosen)))
        options[tid]=chosen
    return types,options,inputs


def campaign(args):
    os.setsid(); deadline=ENTRY_STARTED+args.seconds-5
    args.out.mkdir(parents=True,exist_ok=False)
    report=json.loads(args.official_report.read_text())
    if not report['valid'] or report['sha256']!=sha(args.baseline): raise ValueError('Baseline proof mismatch')
    frame=pd.read_csv(args.baseline,float_precision='round_trip')
    base={int(n):g.sort_values('square_id')[['x','y','angle']].to_numpy(float)for n,g in frame.groupby('n')}
    if set(base)!=set(range(1,1001)): raise ValueError('Incomplete baseline')
    before={r['n']:float(r['side'])for r in report['results']};best=dict(before)
    native=Path(__file__).with_suffix('.cpp');binary=args.out/'proposal_dp'
    subprocess.run(['g++','-std=c++17','-O3',str(native),'-o',str(binary)],check=True,timeout=20,capture_output=True)
    stitch,_=public_functions(ROOT/'vendor/lightning_ftmc')
    control=positive_control(binary,stitch); atom(args.out/'positive-control.json',control)
    types,options,inputs=palette(base,args.bank,args.high_descriptor,args.options)
    manifest={'baseline_sha256':report['sha256'],'baseline_report_sha256':sha(args.official_report),
        'banks':inputs,'source_sha256':sha(Path(__file__)),'native_sha256':sha(native),
        'helper_source_sha256':{name:sha(ROOT/name)for name in [
            'experiments/compose_gadgets.py','experiments/cpu_recipe_replay.py',
            'experiments/extract_broad_active_frontier.py','experiments/ftmc_certified_archive.py',
            'experiments/fq_capacity_probe.py','experiments/fq_active_pilot.py',
            'scripts/score_official.py','scripts/validate_submission.py',
            'research/official_metric_v17.py','vendor/lightning_ftmc/solver.py',
            'vendor/lightning_ftmc/gpu_fault_composition.py','vendor/lightning_ftmc/packing_pipeline.py']},
        'binary_sha256':sha(binary),'types':types,'option_counts':{str(k):len(v)for k,v in options.items()},
        'finite_pose_options':sum(map(len,options.values())),'workers':1,'seconds':args.seconds,
        'scope':'Whole-donor rectangles, reflected/transpose variants, scalar6-beam DP, then exact adjacent-block SAT. No continuous/profile optimality claim.',
        'no_gpu':True,'no_submission':True}
    atom(args.out/'manifest.json',manifest)
    blocked=set();sat_cache={};stats=Counter();candidates={};records=[];seen_traces=set()
    def compatible(a,b,mode):
        if mode in (1,2):return True
        key=(a['uid'],b['uid'],mode)
        if key not in sat_cache:
            sat_cache[key]=cross_block_separated(a['pose'],b['pose'],a['w'],b['h'],mode)
            stats['exact_sat_pose_pairs']+=1
        return sat_cache[key]
    def realize(chain):
        first=chain[0][0];states=[(p['f'],[p])for p in options[first]]
        for stage,(tid,mode)in enumerate(chain[1:],1):
            new=[]
            for p in options[tid]:
                for cost,path in sorted(states,key=lambda v:v[0]):
                    if compatible(path[-1],p,mode):new.append((max(cost,p['f']),path+[p]));break
            if not new:
                prev=chain[stage-1][0]
                if not any(compatible(a,b,mode)for a in options[prev]for b in options[tid]):
                    blocked.add((prev,tid)); stats['finite_type_edges_forbidden']+=1
                else:stats['globally_inconsistent_option_chain']+=1
                return None
            states=new
        return min(states,key=lambda v:v[0])[1]
    def checkpoint(status):
        atom(args.out/'candidates.json',candidates)
        atom(args.out/'report.json',{'status':status,'elapsed_seconds':time.monotonic()-ENTRY_STARTED,
            'manifest_sha256':sha(args.out/'manifest.json'),'stats':dict(stats),'blocked_edges':sorted(blocked),
            'certified_cases':len(candidates),'score_gain':sum((before[int(n)]-float(c['side']))/math.sqrt(int(n))for n,c in candidates.items()),
            'candidates_sha256':sha(args.out/'candidates.json'),'records':records})
    checkpoint('prepared')
    for iteration in range(args.rounds):
        if time.monotonic()>=deadline-3:break
        proposals_all=proposals(binary,types,blocked,[n for n in range(5,1001)if n!=math.isqrt(n)**2],deadline-time.monotonic())
        stats['dp_rounds']+=1;todo=[]
        for p in proposals_all:
            n=p['n'];gain=(best[n]-math.isqrt(n)-p['f'])/math.sqrt(n)
            if gain>1e-8:todo.append((gain,p))
        stats['optimistic_case_proposals']+=len(todo)
        atom(args.out/f'optimistic-round-{iteration}.json',{'proposals':todo,'blocked':sorted(blocked)})
        old_blocked=len(blocked)
        for estimated,p in sorted(todo,key=lambda v:-v[0]):
            if time.monotonic()>=deadline-2:break
            n=p['n'];k=math.isqrt(n);chain=p['chain'];identity=(n,tuple(map(tuple,chain)))
            if identity in seen_traces:continue
            seen_traces.add(identity);stats['chain_realization_attempts']+=1
            selected=realize(chain)
            if selected is None:stats['unrealizable_scalar_chains']+=1;continue
            if k+max(q['f']for q in selected)>=best[n]-1e-8:continue
            q=build(selected,[mode for _,mode in chain],k,stitch);stats['full_layouts_built']+=1
            if q is None or side(q)>=best[n]-1e-8:continue
            certificate=full_certificate(q);stats['full_case_certifications']+=1
            if not certificate['valid']:stats['full_case_rejections']+=1;continue
            length=certificate['independent_raw']['side_upper']
            if float(length)>=best[n]-1e-8:continue
            best[n]=float(length)
            recipe=[{key:value for key,value in item.items()if key!='pose'}for item in selected]
            rec={'n':n,'side':length,'recipe':recipe,'modes':[m for _,m in chain],
                 'certificate':certificate,'optimistic_gain':estimated,'gain_vs_baseline':(before[n]-float(length))/math.sqrt(n)}
            candidates[str(n)]={'side':length,'squares':[[format(float(v),'.17g')for v in row]for row in q],
                'source':'Scalar staircase DP with exact finite-palette SAT joins',
                'provenance':{'manifest_sha256':sha(args.out/'manifest.json'),'recipe':recipe,'modes':rec['modes']},'certificate':certificate}
            records.append(rec);checkpoint('running')
            print(json.dumps({'n':n,'gain':rec['gain_vs_baseline'],'iteration':iteration,'seconds':time.monotonic()-ENTRY_STARTED}),flush=True)
        checkpoint('running')
        if len(blocked)==old_blocked:break
    checkpoint('bounded_complete')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--official-report',type=Path,required=True)
    ap.add_argument('--bank',type=Path,action='append',default=[])
    ap.add_argument('--high-descriptor',type=Path)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--seconds',type=float,default=295.)
    ap.add_argument('--rounds',type=int,default=8);ap.add_argument('--options',type=int,default=8)
    args=ap.parse_args()
    if args.out.exists()or not 10<args.seconds<=300 or not 1<=args.rounds<=12 or not 1<=args.options<=16:raise ValueError('Invalid bounded experiment')
    process=mp.get_context('fork').Process(target=campaign,args=(args,));process.start()
    process.join(max(0.,args.seconds-1.5-(time.monotonic()-ENTRY_STARTED)))
    enforced=process.is_alive()
    if enforced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:process.kill()
        process.join(.4)
    receipt={'exitcode':process.exitcode,'hard_deadline_enforced':enforced,
        'seconds':time.monotonic()-ENTRY_STARTED,'bound_seconds':args.seconds,'workers':1}
    if args.out.exists():atom(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if process.exitcode and not enforced:raise SystemExit(process.exitcode)


if __name__=='__main__':main()
