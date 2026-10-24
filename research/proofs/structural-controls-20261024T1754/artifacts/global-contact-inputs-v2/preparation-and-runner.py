"""Finite12-cell whole-center SAT-disjunction pilot; no portfolio mutation."""
from __future__ import annotations
import time
STARTED=time.monotonic()
import os
for name in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse,csv,hashlib,inspect,json,math,multiprocessing as mp,shutil,signal,sys
from concurrent.futures import ProcessPoolExecutor,FIRST_COMPLETED,wait
from decimal import Decimal
from pathlib import Path
import numpy as np
import global_contact_milp as model
import fq_restart_hop_finish as terminal
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from compose_gadgets import normalize,legalize
from recover_broad_native_returns import current_thresholds
ROOT=Path(__file__).resolve().parents[1]
BINARY=Path('/tmp/squares-fq-portable-target/release/fq')
CASES=(588,335,147)
MODEL_SHA='78e06dc2a3584d4f8b978c9cb7db19794eca97e933ec33f5cc52e6e9c19901e5'
TERMINAL_SHA='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rotated(n,p):
    q=p.copy();fold=(q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4;core=np.flatnonzero(abs(fold)>.018)
    if n==147:
        assert len(core)==64
        directions=np.array([[1.,-1.],[1.,1.]])/math.sqrt(2)
        uv=(p[core,:2]-p[core,:2].mean(0))@directions.T
        rc=np.rint(uv+3.5).astype(int);residual=float(abs(uv-(rc-3.5)).max())
        assert residual<1e-6 and len(set(map(tuple,rc)))==64
        signs=1.-2.*((rc[:,0]+rc[:,1])%2);q[core,2]+=math.radians(.5)*signs
        info=dict(kind='Individual diamond-cell checkerboard angles, centers unchanged',degrees=.5,
                  lattice_residual=residual,core_ids=core.tolist(),cell_coordinates=rc.tolist(),signs=signs.tolist())
    else:
        shifts=-np.sign(fold[core])*math.radians(.25);q[core,2]+=shifts
        info=dict(kind='Every >.018rad tilted unit turns .25degree toward its nearest upright; fixed fold tie convention',
                  degrees=.25,core_ids=core.tolist(),angle_shifts=shifts.tolist())
    assert np.array_equal(q[:,:2],p[:,:2]);return q,info

def prepare(out):
    assert not out.exists()and sha(model.__file__)==MODEL_SHA
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pb=pointer_path.read_bytes();pointer=json.loads(pb)
    assert pointer['safe']['sha256']=='c9fca5a1a1fbf55bba5e3ed093cc5412b92845fb01809c3fbc61362bb01d3097'
    assert sha(pointer['raw']['path'])==pointer['raw']['sha256']and sha(pointer['raw']['official_report'])==pointer['raw']['official_report_sha256']
    assert sha(pointer['independent_report']['path'])==pointer['independent_report']['sha256']
    official=json.loads(Path(pointer['raw']['official_report']).read_text());independent=json.loads(Path(pointer['independent_report']['path']).read_text())
    assert official['valid']and independent['valid']and official['sha256']==independent['sha256']==pointer['raw']['sha256']
    bound={r['n']:r for r in independent['results']};off={r['n']:r for r in official['results']};rows={n:[]for n in CASES}
    with Path(pointer['raw']['path']).open(newline='')as f:
        for r in csv.DictReader(f):
            n=int(r['n'])
            if n in rows:
                assert int(r['square_id'])==len(rows[n]);rows[n].append([r[k]for k in('x','y','angle')])
    out.mkdir(parents=True);bank={};cases={};jobs=[]
    for n in CASES:
        original=np.array(rows[n],dtype='<f8');p=normalize(original);q,preset=rotated(n,p)
        bank[f'n{n}_original']=p;bank[f'n{n}_rotated']=q
        cases[str(n)]=dict(n=n,reference_side=off[n]['side'],reference_lower=bound[n]['side_lower'],
            original_official=off[n],original_interval=bound[n],source_literal_rows=rows[n],
            translation_subtracted=(original[:,:2]-p[:,:2])[0].tolist(),rotation=preset)
        for arm in('original','rotated'):
            for trust in(.15,.35):
                jobs.append(dict(slot=len(jobs),n=n,arm=arm,key=f'n{n}_{arm}',trust=trust,
                    binary_pair_budget=64,seed=1170335147+n*37+len(jobs)))
    atomic_npz(out/'inputs.npz',bank);(out/'canonical-pointer.json').write_bytes(pb)
    notices=out/'notices';notices.mkdir()
    for p in(ROOT/'artifacts/public-squarecraft3-method-v1').glob('*'):
        if p.is_file():shutil.copyfile(p,notices/p.name)
    shutil.copyfile(Path(__file__),out/'preparation-and-runner.py')
    manifest=dict(cases=cases,jobs=jobs,baseline=pointer['raw'],safe=pointer['safe'],inputs_sha256=sha(out/'inputs.npz'),
        arrays={k:dict(shape=list(q.shape),dtype=q.dtype.str,geometry_sha256=geometry_sha(q))for k,q in bank.items()},
        model_sha256=MODEL_SHA,runner_sha256=sha(__file__),terminal_sha256=TERMINAL_SHA,
        binary_sha256=terminal.BINARY_SHA,workers=2,cpu_affinity=[0,1],work_seconds=880,whole_seconds=900,
        fixed_lp_seconds=3,relaxed_lp_seconds=3,milp_seconds=45,endpoint_certificate_seconds=8,
        native_seconds=32,native_certificate_seconds=8,maximum_native_slots=6,
        clearance=1e-8,side_upper_pad=5e-7,relaxation_headroom_threshold=1e-6,
        native_promising_rule='Full-certified actual side improves frozen lower by1e-6, OR stays within2e-6 while at least2 frozen SAT branches change. One best actual endpoint per case/angle stratum; max6slots.',
        own_implementation=True,source_scope='Publisher notices describe method; exact public source request404, code unavailable and not executed.',
        no_gpu=True,no_submission=True,no_canonical_mutation=True)
    atomic_json(out/'manifest.json',manifest)
    for p in out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps(dict(manifest_sha256=sha(out/'manifest.json'),inputs_sha256=manifest['inputs_sha256'],jobs=len(jobs),baseline=pointer['raw']['sha256'])),flush=True)

def gate(q,deadline):
    previous=signal.signal(signal.SIGALRM,terminal._alarm);timer=signal.getitimer(signal.ITIMER_REAL)
    signal.setitimer(signal.ITIMER_REAL,max(.001,min(8.,deadline-time.monotonic())))
    try:return full_certificate(q)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        if timer[0]>0:signal.setitimer(signal.ITIMER_REAL,timer[0],timer[1])

def work(payload):
    out,job,p,case,config,deadline=payload;out=Path(out);out.mkdir(exist_ok=False)
    n=job['n'];record=dict(job,status='started',endpoints=[]);atomic_npz(out/'input.npz',{'pose':p})
    assert sha(model.__file__)==MODEL_SHA
    g=model.geometry(p,job['trust'],float(case['original_interval']['side_upper'])+config['side_upper_pad'],clearance=config['clearance'])
    endpoints=[]
    def store(name,info,q):
        atomic_json(out/f'{name}.json',info)
        if q is not None:atomic_npz(out/f'{name}-provisional.npz',{'pose':q})
        record[name]=info;atomic_json(out/'record.json',record)
    fixed,q0=model.solve(g,mode='fixed',seconds=min(config['fixed_lp_seconds'],max(.01,deadline-time.monotonic())))
    store('fixed',fixed,q0)
    selected=model.select_pairs(g,fixed,64,job['seed']);record['selected_pairs']=list(map(list,selected))
    record['selection_ranking']='LP dual plus incident endpoint pressure'if fixed.get('pair_pressure')else'uninformative zero scores: lexicographic first half plus seeded random remaining half'
    relaxed,qr=model.solve(g,selected,mode='relaxed',seconds=min(config['relaxed_lp_seconds'],max(.01,deadline-time.monotonic())))
    store('relaxed_UNVERIFIED',relaxed,qr)
    lower=float(case['reference_lower']);headroom=(relaxed.get('success')and relaxed.get('provisional_side',math.inf)<lower-1e-6)
    record['relaxation_numeric_headroom']=bool(headroom)
    if headroom and deadline-time.monotonic()>.2:
        integer,q=model.solve(g,selected,mode='milp',seconds=min(45.,max(.01,deadline-time.monotonic())))
        store('milp',integer,q)
    else:integer={'status':'skipped_no_numeric_relaxation_headroom'};q=None;store('milp',integer,None)
    for name,info,raw in(('fixed',fixed,q0),('milp',integer,q)):
        if raw is None or deadline-time.monotonic()<.2:continue
        repaired=legalize(raw.copy(),clearance=2e-9)
        if repaired is None:record['endpoints'].append(dict(kind=name,status='failed_bounded_clearance'));continue
        atomic_npz(out/f'{name}-legalized-unverified.npz',{'pose':repaired})
        try:cert=gate(repaired,deadline)
        except terminal.CertificateDeadline:record['endpoints'].append(dict(kind=name,status='certificate_timeout'));continue
        except Exception as error:record['endpoints'].append(dict(kind=name,status='certificate_error',error_type=type(error).__name__));continue
        endpoint=dict(kind=name,certificate=cert,status='full_certified'if cert['valid']else'failed_full_gates')
        if cert['valid']:
            worst,sides=terminal.worst_certificate_side(cert);switches=sum(
                pair['frozen']['axis']@(repaired[pair['j'],:2]-repaired[pair['i'],:2])<pair['frozen']['radius']-1e-7 for pair in g.pairs)
            endpoint.update(actual_worst_side=worst,certified_sides=sides,branch_switches=int(switches),geometry_sha256=geometry_sha(repaired),
                native_promising=bool((Decimal(worst)<Decimal(case['reference_lower'])-Decimal('0.000001'))or
                    (Decimal(worst)<=Decimal(case['reference_lower'])+Decimal('0.000002')and switches>=2)))
            path=out/f'{name}-certified.npz';atomic_npz(path,{'pose':repaired});path.chmod(0o444)
            endpoint.update(archive=str(path),archive_sha256=sha(path));endpoints.append((endpoint,repaired))
        record['endpoints'].append(endpoint);atomic_json(out/f'{name}-certificate.json',endpoint)
    record['status']='complete';atomic_json(out/'record.json',record);return record,endpoints

def native(payload):
    out,slot,p,case,deadline=payload
    assert sha(terminal.__file__)==TERMINAL_SHA and sha(BINARY)==terminal.BINARY_SHA
    namespace=dict(vars(terminal),NATIVE_SECONDS=32.,CERTIFICATE_SECONDS=8.)
    source=inspect.getsource(terminal._finish_slot).replace('UNVERIFIED exact committed BEST array','Fully certified whole-center contact-disjunction endpoint; output still requires all full gates')
    exec(compile(source,'<unchanged32+8 terminal helper>','exec'),namespace)
    return namespace['_finish_slot'](Path(out),dict(slot,arm='jointSAT',delta=.002,chain=slot['slot']),p,case,BINARY,deadline)

def run(args):
    os.setsid();os.sched_setaffinity(0,{0,1});deadline=STARTED+880.
    assert sha(args.inputs/'manifest.json')==args.manifest_sha256
    config=json.loads((args.inputs/'manifest.json').read_text());assert config['model_sha256']==sha(model.__file__)==MODEL_SHA
    assert sha(terminal.__file__)==TERMINAL_SHA and sha(BINARY)==terminal.BINARY_SHA
    assert config['runner_sha256']==sha(__file__)and sha(args.inputs/'inputs.npz')==config['inputs_sha256']
    assert config['workers']==2 and config['work_seconds']==880 and config['whole_seconds']==900
    assert len(config['jobs'])==12 and set(config['cases'])=={'588','335','147'}
    with np.load(args.inputs/'inputs.npz',allow_pickle=False)as z:bank={k:z[k].copy()for k in z.files}
    for k,p in bank.items():assert geometry_sha(p)==config['arrays'][k]['geometry_sha256']
    shutil.copytree(args.inputs,args.out/'inputs');initial,pointer=current_thresholds(args.out/'comparison-initial')
    source=args.out/'source';source.mkdir()
    for p in(Path(__file__),Path(model.__file__),Path(terminal.__file__),ROOT/'experiments/fq_capacity_probe.py',
              ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py'):
        shutil.copyfile(p,source/p.name)
    atomic_json(args.out/'execution-manifest.json',dict(input_manifest_sha256=args.manifest_sha256,configuration=config,
        sources={p.name:sha(p)for p in source.iterdir()},no_gpu=True,no_submission=True,no_canonical_mutation=True))
    jobs=config['jobs'];pending={};records=[];certified={};strata={};cursor=0
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork'))as pool:
        while cursor<len(jobs)or pending:
            while cursor<len(jobs)and len(pending)<2 and time.monotonic()<deadline-165.:
                j=jobs[cursor];cursor+=1
                pending[pool.submit(work,(str(args.out/f"slot-{j['slot']:02d}"),j,bank[j['key']],config['cases'][str(j['n'])],config,deadline-160.))]=j
            if not pending:break
            done,_=wait(pending,timeout=.2,return_when=FIRST_COMPLETED)
            for f in done:
                j=pending.pop(f)
                try:r,endpoints=f.result()
                except Exception as error:r=dict(j,status='error',error_type=type(error).__name__);endpoints=[]
                records.append(r)
                for e,p in endpoints:
                    key=f"n{j['n']}_{j['arm']}_t{j['trust']}_{e['kind']}";certified[key]=p
                    group=(j['n'],j['arm'])
                    if e['native_promising']and(group not in strata or Decimal(e['actual_worst_side'])<Decimal(strata[group][0]['actual_worst_side'])):
                        strata[group]=(dict(e,source_slot=j['slot'],key=key),p)
                atomic_json(args.out/'results.json',records);atomic_npz(args.out/'certified.npz',certified)
                print(json.dumps(dict(slot=j['slot'],n=j['n'],arm=j['arm'],trust=j['trust'],headroom=r.get('relaxation_numeric_headroom'),
                    milp_status=r.get('milp',{}).get('status'),certified_endpoints=len(endpoints),elapsed=time.monotonic()-STARTED)),flush=True)
        native_dir=args.out/'native';native_dir.mkdir();native_records=[];futuremap={}
        assert len(strata)<=6
        for index,((n,arm),(e,p))in enumerate(sorted(strata.items())):
            slot=dict(slot=index,source_endpoint=e,source_case=n,source_arm=arm)
            case=dict(n=n,source_key=e['key'],reference_side=config['cases'][str(n)]['reference_side'])
            futuremap[pool.submit(native,(str(native_dir),slot,p,case,deadline))]=(n,e['key'])
        for f in futuremap:
            n,key=futuremap[f]
            try:r,p=f.result()
            except Exception as error:r=dict(n=n,status='error',error_type=type(error).__name__);p=None
            native_records.append(r)
            if p is not None:certified['native_'+key]=p
            atomic_json(args.out/'native-results.json',native_records);atomic_npz(args.out/'certified.npz',certified)
    final,current=current_thresholds(args.out/'comparison-final');candidates={}
    for r in records:
        for e in r.get('endpoints',[]):
            if e.get('status')!='full_certified':continue
            n=r['n'];key=f"n{n}_{r['arm']}_t{r['trust']}_{e['kind']}"
            if Decimal(e['actual_worst_side'])<final[n]and(str(n)not in candidates or Decimal(e['actual_worst_side'])<Decimal(candidates[str(n)]['side'])):
                candidates[str(n)]=dict(side=e['actual_worst_side'],squares=[[f'{v:.17g}'for v in row]for row in certified[key]],
                    certificate=e['certificate'],source='Independent continuous-center jointSAT branch MILP/pairedLP',provenance=dict(slot=r['slot'],endpoint=e,input_manifest_sha256=args.manifest_sha256))
    for r in native_records:
        if r.get('status')!='certified':continue
        n=r['n'];key='native_'+r['source_key']
        if Decimal(r['worst_certified_side'])<final[n]and(str(n)not in candidates or Decimal(r['worst_certified_side'])<Decimal(candidates[str(n)]['side'])):
            candidates[str(n)]=dict(side=r['worst_certified_side'],squares=[[f'{v:.17g}'for v in row]for row in certified[key]],
                certificate=r['certificate'],source='Native finish of full-certified whole-center jointSAT endpoint',provenance=r)
    atomic_json(args.out/'candidates.json',candidates)
    summary=dict(status='complete'if len(records)==12 else'bounded_partial',jobs=len(records),certified_poses=len(certified),
        native_slots=len(native_records),improved_cases=list(candidates),seconds=time.monotonic()-STARTED,
        canonical_raw_sha256=current['raw']['sha256'],candidates_sha256=sha(args.out/'candidates.json'),
        results_sha256=sha(args.out/'results.json'),certified_sha256=sha(args.out/'certified.npz'),no_submission=True,no_canonical_mutation=True)
    atomic_json(args.out/'summary.json',summary)
    for p in args.out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps(summary),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',type=Path);parser.add_argument('--inputs',type=Path)
    parser.add_argument('--manifest-sha256');parser.add_argument('--out',type=Path);args=parser.parse_args()
    if args.prepare:prepare(args.prepare.resolve());sys.exit(0)
    args.inputs=args.inputs.resolve();args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
    process=mp.get_context('fork').Process(target=run,args=(args,));process.start();process.join(max(0.,890.-(time.monotonic()-STARTED)))
    forced=process.is_alive()
    if forced:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.join(timeout=max(0.,899.-(time.monotonic()-STARTED)))
    atomic_json(args.out/'supervisor.json',dict(returncode=process.exitcode,forced=forced,whole_seconds=900,workers=2,seconds=time.monotonic()-STARTED))
