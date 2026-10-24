"""Bounded read-only exact-public35 versus31 alternative-pose inventory."""
from __future__ import annotations
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import csv,hashlib,json,math,signal,time
from pathlib import Path
import numpy as np
from fq_active_pilot import encode
from compose_gadgets import normalize
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gen(path):
    # Public35 interleaves some replacement cases/rows. Group by the explicit
    # n/square_id keys, preserving coordinate literals, never file adjacency.
    groups={}
    with path.open(newline='')as f:
        for row in csv.DictReader(f):
            n=int(row['n']);i=int(row['square_id']);assert 1<=n<=1000 and 0<=i<n
            if n not in groups:groups[n]=[None]*n
            assert groups[n][i]is None
            groups[n][i]=[row[k]for k in('x','y','angle')]
    assert set(groups)==set(range(1,1001))
    for n in range(1,1001):
        rows=groups.pop(n);assert all(r is not None for r in rows);yield n,rows

def pose(rows):
    q=np.array(rows,dtype=np.float64);assert np.isfinite(q).all()
    return q

def info(p):
    extent=.5*(abs(np.cos(p[:,2]))+abs(np.sin(p[:,2])))
    side=float(((p[:,:2]+extent[:,None]).max(0)-(p[:,:2]-extent[:,None]).min(0)).max())
    encoded,offset=encode(p,math.isqrt(len(p)),math.isqrt(len(p)));assert offset==[0,0]
    folded=(p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
    return dict(side=side,geometry_sha256=hashlib.sha256(p.tobytes()).hexdigest(),
                encoded_input_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
                tilted_count=int((abs(folded)>.018).sum()))

def signatures(p):
    """Quantized numerical descriptors only, never basin/equivalence proofs."""
    coarse=[];fine=[]
    for transpose in(False,True):
        for sx,sy in((1,1),(-1,1),(1,-1),(-1,-1)):
            q=p.copy()
            if transpose:q[:,:2]=q[:,[1,0]];q[:,2]=np.pi/2-q[:,2]
            q[:,0]*=sx;q[:,1]*=sy;q[:,2]=np.arctan2(sy*np.sin(q[:,2]),sx*np.cos(q[:,2]))
            q=normalize(q);e=.5*(abs(np.cos(q[:,2]))+abs(np.sin(q[:,2])));L=float((q[:,:2]+e[:,None]).max())
            folded=(q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4;folded[abs(folded)<1e-6]=0.
            histogram=np.histogramdd(np.column_stack((q[:,:2]/L,folded)),bins=(16,16,8),range=((0,1),(0,1),(-np.pi/4,np.pi/4)))[0].astype('<i4')
            coarse.append(hashlib.sha256(histogram.tobytes()).hexdigest())
            fields=np.column_stack((q[:,:2],np.cos(4*q[:,2]),np.sin(4*q[:,2]))).round(6)
            fields=fields[np.lexsort(fields.T[::-1])];fine.append(hashlib.sha256(fields.tobytes()).hexdigest())
    return dict(coarse_D4_histogram=min(coarse),quantized_pose_D4_1e6=min(fine),descriptor_only=True)

def main():
    def alarm(*_):raise RuntimeError('90-second read-only screen ceiling')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(90);started=time.monotonic()
    out=ROOT/'artifacts/public-v35/alternate-screen-v3';out.mkdir(exist_ok=False)
    p31=ROOT/'artifacts/public-kmmm31/kmmmvs__squares-in-squares-best-packings.csv'
    p35=ROOT/'artifacts/public-v35/files/submission.csv'
    assert sha(p31)=='0dca84e8b18a0de1ec2f3f1bb8c1bd00a529c893a2591138f13231ec9109e799'
    assert sha(p35)=='b8be571167c0d51693cdce9ac07187098a0d38bceef0d9e25d347d067e4eb6b9'
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pb=pointer_path.read_bytes();pointer=json.loads(pb)
    official_path=Path(pointer['raw']['official_report']);assert sha(official_path)==pointer['raw']['official_report_sha256']
    official=json.loads(official_path.read_text());assert official['valid']and official['sha256']==pointer['raw']['sha256']
    current={r['n']:float(r['side'])for r in official['results']}
    dated={r['n']:float(r['L'])for r in json.loads((ROOT/'research/data/public_puzzle_reference_v10.json').read_text())}
    imported=set(map(int,json.loads((ROOT/'artifacts/public-v35/certified/winning-candidates.json').read_text())))
    publisher={int(r['n']):r for r in csv.DictReader((ROOT/'artifacts/public-v35/files/per_puzzle.csv').open(newline=''))}
    # Bounded exact input exposure inventory from the completed major native
    # sweeps, not an unbounded scan of every historical trial file.
    folders=['fq-broad-contact-v1/complete','fq-current-rigid-v1/complete','fq-public35-reference-finish-v1',
             'fq-selective-polish-v1','fq-selective-polish-completion-v1','birth-original-controls-v1']
    folders += [p.name for p in(ROOT/'artifacts').iterdir()if p.is_dir()and ('timeout' in p.name or 'trace-n' in p.name)]
    exposures={};exposure_sources={}
    for folder in sorted(set(folders)):
        path=ROOT/'artifacts'/folder/'results.json'
        if not path.exists():continue
        value=json.loads(path.read_text());records=value if isinstance(value,list)else value.get('records',value.get('results',[]))
        if isinstance(records,dict):records=list(records.values())
        if not isinstance(records,list):continue
        exposure_sources[str(path.relative_to(ROOT))]=sha(path)
        for r in records:
            if not isinstance(r,dict):continue
            command=r.get('command',[]);profile={}
            for option in('--outer','--pit','--flip-top','--loosen','--seed','--round-r0'):
                if option in command:profile[option]=command[command.index(option)+1]
            profile['no_alm']='--no-alm'in command
            full_profile=not profile['no_alm']and profile.get('--outer')=='45'and profile.get('--pit')=='100'and profile.get('--flip-top')=='16'
            for key in('input_sha256','native_encoded_input_sha256'):
                if key in r:exposures.setdefault(r[key],[]).append(dict(source=str(path.relative_to(ROOT)),slot=r.get('slot',r.get('job')),n=r.get('n'),status=r.get('status'),profile=profile,full_ALM45_pit100_flip16=full_profile))
    allrows=[];alternates={};poses35={};oldposes={}
    for (n,a),(m,b)in zip(gen(p31),gen(p35)):
        assert n==m
        if a==b:continue
        pa,pb35=pose(a),pose(b);i31,i35=info(pa),info(pb35)
        literal31=hashlib.sha256(json.dumps(a,separators=(',',':')).encode()).hexdigest()
        literal35=hashlib.sha256(json.dumps(b,separators=(',',':')).encode()).hexdigest()
        row=dict(n=n,public31=i31,public35=i35,literal31_sha256=literal31,literal35_sha256=literal35,
            exact_native_input_changed=i31['encoded_input_sha256']!=i35['encoded_input_sha256'],
            canonical_side=current[n],dated_reference_side=dated[n],
            canonical_dated_score_headroom=max(0.,(current[n]-dated[n])/math.sqrt(n)),
            public35_side_excess=i35['side']-current[n],public35_vs31_side_gain=i31['side']-i35['side'],
            adopted_and_already_native_finished=n in imported,
            prior_exact_native_input_exposures=exposures.get(i35['encoded_input_sha256'],[]),publisher=publisher[n])
        allrows.append(row)
        if row['exact_native_input_changed']and n not in imported and i35['side']>=current[n]-1e-10:
            alternates[n]=row;poses35[n]=pb35;oldposes[n]=pa
    # Descriptors are computed only for actual alternate sources, not all1000.
    for n,row in alternates.items():
        row['public31'].update(signatures(oldposes[n]));row['public35'].update(signatures(poses35[n]))
    # Current comparison uses the same exact candidate IDs only.
    for n,rows in gen(Path(pointer['raw']['path'])):
        if n in alternates:
            q=pose(rows);alternates[n]['current_geometry']=dict(info(q),**signatures(q))
    finish=json.loads((ROOT/'artifacts/fq-public35-reference-finish-v1/results.json').read_text())
    gains=np.array([float(r['side_gain'])for r in finish if r.get('status')=='certified'])
    report=dict(status='complete',seconds=time.monotonic()-started,baseline=pointer['raw'],
        pointer_changed_during_screen=json.loads(pointer_path.read_text())['raw']['sha256']!=pointer['raw']['sha256'],
        source31=dict(path=str(p31),sha256=sha(p31),version=31),source35=dict(path=str(p35),sha256=sha(p35),version=35),
        literal_changed_cases=len(allrows),encoded_input_changed_cases=sum(r['exact_native_input_changed']for r in allrows),
        already_adopted_excluded=sorted(imported),alternate_count=len(alternates),
        exact_exposure_cases=[n for n,r in alternates.items()if r['prior_exact_native_input_exposures']],
        exposure_sources=exposure_sources,known_exact_exposure_hashes=len(exposures),
        changed_cases=allrows,alternates=[alternates[n]for n in sorted(alternates)],
        observed_18_native_side_gains=dict(minimum=float(gains.min()),median=float(np.median(gains)),maximum=float(gains.max()),
                                           q75=float(np.quantile(gains,.75)),q90=float(np.quantile(gains,.9))),
        scope='Read-only finite source/side/input inventory. Quantized D4 descriptors are not proof of basin differences or exact geometric equivalence. Dated scalar gaps are targets, not attainable-gain claims; no new geometry certificates/optimizer calls.')
    (out/'geometry-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    np.savez_compressed(out/'alternate-public35-poses.npz',**{str(n):q for n,q in poses35.items()})
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    signal.alarm(0)
    print(json.dumps({k:report[k]for k in('status','seconds','literal_changed_cases','encoded_input_changed_cases','alternate_count','exact_exposure_cases','observed_18_native_side_gains')}),flush=True)

if __name__=='__main__':main()
