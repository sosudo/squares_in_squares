"""Exact translated-window subset search with a bounded one-CPU sweep worker.

The sweep is exact for its binary64 bbox constraints. Every retained subset must
also pass independent interval geometry and unchanged official raw/pandas gates.
Selected source coordinates are preserved, without translation or legalization.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[name] = '1'
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_submission import Square, validate_puzzle
METRIC_SHA = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def boxes(q):
    q = np.asarray(q,dtype=float)
    r = .5*(np.abs(np.cos(q[:,2]))+np.abs(np.sin(q[:,2])))
    return np.column_stack((q[:,:2]-r[:,None],q[:,:2]+r[:,None]))


def side(q):
    b = boxes(q)
    return float(max(b[:,2:].max(0)-b[:,:2].min(0)))


def compile_solver(output):
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    source = Path(__file__).with_suffix('.cpp')
    subprocess.run(['g++','-std=c++17','-O3','-DNDEBUG',str(source),'-o',str(output)],
        check=True,timeout=45,capture_output=True)
    return {'source_sha256':sha(source),'binary_sha256':sha(output),'binary':str(output)}


class WindowSolver:
    def __init__(self,binary,timeout=2.):
        self.timeout = float(timeout)
        self.process = subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,bufsize=1)

    def exchange(self,message,timeout=None):
        self.process.stdin.write(message)
        self.process.stdin.flush()
        ready,_,_ = select.select([self.process.stdout],[],[],self.timeout if timeout is None else timeout)
        if not ready:
            self.close()
            raise TimeoutError('Exact-window worker query deadline')
        line = self.process.stdout.readline()
        if not line:
            error = self.process.stderr.read()[:300]
            raise RuntimeError('Exact-window worker exited: '+error)
        return json.loads(line)

    def load(self,q):
        b = boxes(q)
        if b.ndim!=2 or b.shape[1]!=4 or not np.isfinite(b).all():
            raise ValueError('Finite square geometry required')
        message = 'LOAD '+str(len(b))+'\n'+''.join(' '.join(format(v,'.17g') for v in row)+'\n' for row in b)
        reply = self.exchange(message)
        if reply != {'loaded':len(b)}:
            raise ValueError('Source load acknowledgement differs')

    def query(self,length,timeout=None):
        return self.exchange('QUERY '+format(float(length),'.17g')+'\n',timeout)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        for stream in [self.process.stdin,self.process.stdout,self.process.stderr]:
            if stream is not None and not stream.closed:stream.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def metric_module():
    path = ROOT/'research/official_metric_v17.py'
    if sha(path)!=METRIC_SHA:raise ValueError('Official metric source changed')
    spec = importlib.util.spec_from_file_location('window_official_metric',path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def coordinate_text(q):
    return [[format(float(v),'.17g') for v in row] for row in q]


def certify(q,metric):
    n = len(q)
    text = coordinate_text(q)
    interval = validate_puzzle(n,[Square(*row) for row in text])
    if not interval['valid']:return None
    rows = [dict(n=str(n),square_id=str(i),x=r[0],y=r[1],angle=r[2]) for i,r in enumerate(text)]
    raw = metric._evaluate_puzzle_worker((n,rows))
    buffer = io.StringIO()
    frame = pd.read_csv(io.StringIO(pd.DataFrame(rows).to_csv(index=False)))
    frame.to_csv(buffer,index=False,float_format='%.17g')
    roundtrip = metric._evaluate_puzzle_worker((n,list(csv.DictReader(io.StringIO(buffer.getvalue())))))
    default_rows = list(csv.DictReader(io.StringIO(frame.to_csv(index=False))))
    default_interval = validate_puzzle(n,[Square(row['x'],row['y'],row['angle']) for row in default_rows])
    default_roundtrip = metric._evaluate_puzzle_worker((n,default_rows))
    if (not default_interval['valid'] or any(result[3]!='ok' for result in [raw,roundtrip,default_roundtrip])
            or max(abs(raw[1]-result[1]) for result in [roundtrip,default_roundtrip])>1e-10):return None
    return {'interval':interval,'raw':raw,'roundtrip':roundtrip,
        'default_roundtrip':default_roundtrip,'default_interval':default_interval,'metric_sha256':METRIC_SHA}


def atomic_json(path,value):
    path = Path(path);tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--baseline-report',type=Path,required=True)
    parser.add_argument('--source-npz',type=Path,action='append',default=[])
    parser.add_argument('--exclude-portfolio',action='store_true',help='Use baseline only as target; avoid re-querying prior portfolio sources')
    parser.add_argument('--all-counts',action='store_true',help='Try every n=2..min(source_count-1,1000)')
    parser.add_argument('--exclude-target-counts',type=Path,help='JSON list of previously completed counts to skip')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=300)
    parser.add_argument('--nearest',type=int,default=120)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=451021)
    args = parser.parse_args()
    if not 0<args.seconds<=600 or not 1<=args.nearest<=1000:raise ValueError('Invalid bounded one-CPU search')
    start = time.monotonic();deadline = start+args.seconds
    if args.out.exists():raise ValueError('Use a new immutable experiment output directory')
    args.out.mkdir(parents=True)
    (args.out/'source_wrapper.py').write_bytes(Path(__file__).read_bytes())
    (args.out/'source_sweep.cpp').write_bytes(Path(__file__).with_suffix('.cpp').read_bytes())
    excluded_counts = set()
    if args.exclude_target_counts:
        values = json.loads(args.exclude_target_counts.read_text())
        if not isinstance(values,list) or any(type(n) is not int or not 1<=n<=1000 for n in values):
            raise ValueError('Excluded counts must be a JSON list of n=1..1000 integers')
        excluded_counts = set(values)
    baseline_hash = sha(args.baseline)
    report = json.loads(args.baseline_report.read_text())
    if not (report.get('sha256')==baseline_hash and report.get('valid') is True
            and report.get('invalid_count')==0 and report.get('puzzles')==1000
            and report.get('metric_sha256')==METRIC_SHA):raise ValueError('Matching official baseline certificate required')
    frame = pd.read_csv(args.baseline,float_precision='round_trip',usecols=['n','square_id','x','y','angle'])
    base = {int(n):g.sort_values('square_id')[['x','y','angle']].to_numpy(float) for n,g in frame.groupby('n')}
    if set(base)!=set(range(1,1001)) or any(len(q)!=n for n,q in base.items()):raise ValueError('Incomplete baseline')
    incumbent = {n:side(q) for n,q in base.items()}
    groups = [[('portfolio_n'+str(n),q,False) for n,q in base.items()
        if not args.exclude_portfolio and n>4 and side(q)<math.ceil(math.sqrt(n))-1e-6]]
    sources = [{'path':str(args.baseline),'sha256':baseline_hash,'kind':'current portfolio'}]
    for path in args.source_npz:
        with np.load(path,allow_pickle=False) as archive:
            group = [(str(path)+':'+name,archive[name].copy(),True) for name in archive.files
                if archive[name].ndim==2 and archive[name].shape[1]==3 and len(archive[name])>4]
        if any(not np.isfinite(q).all() for _,q,_ in group):raise ValueError('Nonfinite donor geometry')
        groups.append(group);sources.append({'path':str(path),'sha256':sha(path),'poses':len(group)})
    rng = np.random.default_rng(args.seed)
    for group in groups:rng.shuffle(group)
    # Round-robin the three source classes so a large portfolio cannot consume
    # the entire bounded pass before novel larger crops are tried.
    order = [group[i] for i in range(max(map(len,groups))) for group in groups if i<len(group)]
    manifest = {'sources':sources,'binary_sha256':sha(args.binary),'source_sha256':sha(Path(__file__).with_suffix('.cpp')),
        'baseline_sha256':baseline_hash,'baseline_score':report['score'],'seconds':args.seconds,'workers':1,
        'source_poses':len(order),'nearest_counts':args.nearest,'seed':args.seed,'coordinate_translation':False,
        'portfolio_used_as_source':not args.exclude_portfolio,'wrapper_sha256':sha(__file__),
        'all_counts':args.all_counts,'excluded_target_counts':sorted(excluded_counts),
        'excluded_target_counts_sha256':sha(args.exclude_target_counts) if args.exclude_target_counts else None,
        'target_schedule':'Nearest counts for portfolio; half nearest plus evenly spaced full-range bands for external sources; perfect-area targets skipped.'}
    atomic_json(args.out/'manifest.json',manifest)
    metric = metric_module()
    candidates,proofs,coverage = {},{},{}
    stats = {'queries':0,'sources_visited':0,'feasible_threshold_queries':0,'accepted':0,'rejected':0,
             'max_count_checked':0,'target_windows':0,'timed_out':False}

    def checkpoint():
        atomic_json(args.out/'candidates.json',candidates)
        atomic_json(args.out/'certificates.json',proofs)
        atomic_json(args.out/'coverage.json',coverage)
        atomic_json(args.out/'progress.json',{**stats,'elapsed_seconds':time.monotonic()-start,
            'distinct_improved_puzzles':len(candidates),'expected_score_gain':sum(
                (side(base[int(n)])-v['side'])/math.sqrt(int(n)) for n,v in candidates.items())})

    def timeout(signum,frame):raise TimeoutError('Bounded exact-window campaign')
    previous = signal.signal(signal.SIGALRM,timeout)
    signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
    try:
        with WindowSolver(args.binary) as solver:
            for label,q,wide in order:
                if time.monotonic()>=deadline:break
                solver.load(q);stats['sources_visited']+=1;m=len(q)
                coverage[label] = {'source_count':m,'tested_counts':[],'source_schedule_completed':False}
                targets = list(range(max(2,min(m-1,1000)-args.nearest+1),min(m-1,1000)+1))
                if args.all_counts:
                    targets = list(range(2,min(m-1,1000)+1))
                elif wide:
                    # Cover the complete target range in bounded, evenly spaced
                    # bands; nearest counts still receive half the available slots.
                    broader = np.linspace(2,min(m-1,1000),max(2,args.nearest//2)).astype(int).tolist()
                    targets = sorted(set(targets[args.nearest//2:]+broader))
                targets = [n for n in targets if n not in excluded_counts]
                targets.sort(key=lambda n:-(incumbent[n]/math.sqrt(n)-1))
                for n in targets:
                    upper = incumbent[n]-1e-6
                    if upper<=math.sqrt(n):continue
                    stats['queries']+=1;stats['target_windows']+=1
                    result=solver.query(upper,timeout=max(.001,min(2.,deadline-time.monotonic())))
                    coverage[label]['tested_counts'].append(n)
                    stats['max_count_checked']=max(stats['max_count_checked'],result['count'])
                    if result['count']<n:continue
                    stats['feasible_threshold_queries']+=1;lower=math.sqrt(n)
                    for _ in range(24):
                        if upper-lower<1e-7 or time.monotonic()>=deadline:break
                        middle=(lower+upper)/2;stats['queries']+=1
                        trial=solver.query(middle,timeout=max(.001,min(2.,deadline-time.monotonic())))
                        if trial['count']>=n:upper,result=middle,trial
                        else:lower=middle
                    ids=result['ids'][:n];selected=np.array(q[ids],copy=True)
                    measured=side(selected)
                    if measured>=incumbent[n]-5e-7:continue
                    certificate=certify(selected,metric)
                    if certificate is None:stats['rejected']+=1;continue
                    measured=float(certificate['raw'][2])
                    if measured>=incumbent[n]-5e-7:continue
                    gain=(incumbent[n]-measured)/math.sqrt(n);incumbent[n]=measured
                    proofs[str(n)]={**certificate,'source_label':label,'source_count':m,'source_indices':ids,
                        'source_geometry_sha256':hashlib.sha256(np.asarray(q,dtype='<f8').tobytes()).hexdigest(),
                        'window_lower_left':[result['x'],result['y']],'window_side_upper':upper,
                        'exact_source_coordinates_preserved':True}
                    candidates[str(n)]={'side':measured,'squares':coordinate_text(selected),'source':'exact translated-window subset '+label}
                    stats['accepted']+=1;checkpoint()
                    print(json.dumps({'stage':'certified window gain','n':n,'source_count':m,'side':measured,'score_gain':gain}),flush=True)
                coverage[label]['source_schedule_completed'] = True
                if stats['sources_visited']%20==0:checkpoint()
    except TimeoutError:
        stats['timed_out']=True
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous);checkpoint()
    print(json.dumps(json.loads((args.out/'progress.json').read_text())),flush=True)


if __name__=='__main__':main()
