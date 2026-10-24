"""One-worker actual coupled-contact MILP controls, no production search."""
from __future__ import annotations
import os
for name in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import hashlib,json,math,signal,time
from pathlib import Path
import numpy as np
from global_contact_milp import geometry,solve
from compose_gadgets import legalize
from fq_capacity_probe import full_certificate
ROOT=Path(__file__).resolve().parents[1]

class ControlDeadline(BaseException):pass
def expired(*_):raise ControlDeadline('90-second control ceiling')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')

def selected_by_witness(g,witness):
    """Control-only known branch obstruction; production uses pressure/random."""
    return [(p['i'],p['j'])for p in g.pairs
        if p['frozen']['axis']@(witness[p['j'],:2]-witness[p['i'],:2])<p['frozen']['radius']-1e-7]

def certify_and_retain(folder,name,q,maximum_side):
    np.savez_compressed(folder/f'{name}-provisional.npz',pose=q)
    repaired=legalize(q.copy(),clearance=2e-9);assert repaired is not None
    cert=full_certificate(repaired);assert cert['valid']
    actual=float(cert['independent_raw']['side_upper']);assert actual<maximum_side
    np.savez_compressed(folder/f'{name}-certified.npz',pose=repaired)
    return dict(certificate=cert,actual_side_upper=actual,
        provisional_sha256=sha(folder/f'{name}-provisional.npz'),certified_sha256=sha(folder/f'{name}-certified.npz'))

def main(out):
    signal.signal(signal.SIGALRM,expired);signal.alarm(90);start=time.monotonic()
    out.mkdir(exist_ok=False);results={}
    # Five current upright units form a five-link x-chain. Two SAT branch
    # switches allow a3x2 arrangement; several existing centers must move.
    p5=np.array([[i+.5,.5+i%2,0.]for i in range(5)])
    witness5=np.array([[.5,.5,0.],[.5,1.5,0.],[1.5,.5,0.],[1.5,1.5,0.],[2.5,.5,0.]])
    # Seventeen units start on6x3 grid minus one. Two vertical vacancy cascades
    # move seven existing units, giving a5x4 envelope at trust2.
    p17=np.array([[i%6+.5,i//6+.5,0.]for i in range(17)]);witness17=p17.copy()
    for i,xy in {5:(4.5,.5),4:(4.5,1.5),10:(4.5,2.5),16:(4.5,3.5),11:(3.5,1.5),9:(3.5,2.5),15:(3.5,3.5)}.items():
        witness17[i,:2]=xy
    np.savez_compressed(out/'exact-fixtures.npz',source5=p5,witness5=witness5,source17=p17,witness17=witness17)
    for n,p,witness,old,new in((5,p5,witness5,5.,3.),(17,p17,witness17,6.,5.)):
        g=geometry(p,trust=2.,side_upper=old+1e-5,clearance=1e-8,side_lower=new)
        selected=selected_by_witness(g,witness);assert len(selected)>=2
        fixed,q0=solve(g,mode='fixed',seconds=5.)
        assert q0 is not None and fixed['provisional_side']>old-1e-6
        relaxed,_=solve(g,selected,mode='relaxed',seconds=5.)
        result,q=solve(g,selected,mode='milp',seconds=20.)
        assert q is not None and result['provisional_side']<new+1e-5,(n,result)
        assert np.array_equal(q[:,2],p[:,2])and len(q)==n
        moved=int((np.max(abs(q[:,:2]-p[:,:2]),axis=1)>1e-4).sum());assert moved>=2
        gate=certify_and_retain(out,f'positive{n}',q,new+2e-5)
        results[str(n)]=dict(fixed=fixed,relaxed=relaxed,milp=result,selected_pairs=selected,
            moved_existing_units=moved,source_side=old,certified=gate,
            selection_scope='Known witness-obstructing branches ONLY for mathematical control; no production pressure claim.')
        write(out/'progress.json',results)
    collision=np.array([[.5,.5,0.],[1.4,.5,0.]])
    negative,q=solve(geometry(collision,0.,2.,clearance=0.),[(0,1)],mode='milp',seconds=2.)
    assert q is None and negative['status']=='pair-domain-impossible'
    identity,q=solve(geometry(witness5,0.,3.,clearance=0.,side_lower=3.),mode='fixed',seconds=2.)
    assert q is not None and np.array_equal(q,witness5)
    results['zero_trust_collision']=negative;results['zero_trust_valid_identity']=identity
    sources={str(p.relative_to(ROOT)):sha(p)for p in(Path(__file__),ROOT/'experiments/global_contact_milp.py',
        ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',ROOT/'research/official_metric_v17.py')}
    report=dict(passed=True,seconds=time.monotonic()-start,workers=1,maximum_seconds=90,
        results=results,source_sha256=sources,fixtures_sha256=sha(out/'exact-fixtures.npz'),
        no_production_cases=True,no_native_solver=True,no_gpu=True,no_submission=True,
        scope='Known5/17-unit branch-switch feasibility controls and negative/identity tests. All MILP positions provisional until full certificates; no global packing or production gain claim.')
    write(out/'report.json',report);signal.alarm(0)
    print(json.dumps(dict(passed=True,seconds=report['seconds'],five_side=results['5']['certified']['actual_side_upper'],
        seventeen_side=results['17']['certified']['actual_side_upper'])),flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    main(p.parse_args().out.resolve())
