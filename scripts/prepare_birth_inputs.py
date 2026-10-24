"""Freeze exact497/586 scaffolds and finite32-chain single-square births."""
from __future__ import annotations
import hashlib,json,math,shutil,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from fq_variant_campaign import geometry_sha
SOURCE=ROOT/'artifacts/junction-cavity-inputs-v1'
SOURCE_SHA='b98720068180af1f7d45c963cd5fbf8cfde4803aff21d661af1a05b8f0e24ac5'
SCHEDULES=((.05,.15,.25,.35,.45,.55,.65,.75,.85,.95,1.,1.),
           (.05,.30,.50,.65,.75,.82,.88,.92,.95,.975,.99,1.))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def clearances(p,centers,angle,size,L):
    """All old unit square axes plus both newborn axes and exact box walls."""
    c,s=np.cos(p[:,2]),np.sin(p[:,2]);a,b=math.cos(angle),math.sin(angle)
    C=abs(np.cos(p[:,2]-angle))+abs(np.sin(p[:,2]-angle))
    answer=[]
    for begin in range(0,len(centers),128):
        xy=centers[begin:begin+128];dx=xy[:,0,None]-p[:,0];dy=xy[:,1,None]-p[:,1]
        gap=np.maximum.reduce((abs(dx*c+dy*s)-(.5+.5*size*C),
            abs(-dx*s+dy*c)-(.5+.5*size*C),
            abs(dx*a+dy*b)-(.5*size+.5*C),abs(-dx*b+dy*a)-(.5*size+.5*C)))
        half=.5*size*(abs(a)+abs(b));wall=np.minimum.reduce((xy[:,0]-half,xy[:,1]-half,L-half-xy[:,0],L-half-xy[:,1]))
        answer.extend(np.minimum(gap.min(1),wall))
    return np.array(answer)

def prepare(out):
    assert not out.exists()and sha(SOURCE/'manifest.json')==SOURCE_SHA
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    assert sha(SOURCE/'scaffolds.npz')==manifest['scaffolds_sha256']and sha(SOURCE/'cases.json')==manifest['cases_sha256']
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pb=pointer_path.read_bytes();pointer=json.loads(pb)
    assert sha(pointer['raw']['path'])==pointer['raw']['sha256']and sha(pointer['raw']['official_report'])==pointer['raw']['official_report_sha256']
    official=json.loads(Path(pointer['raw']['official_report']).read_text())
    assert official['valid']and official['sha256']==pointer['raw']['sha256']and official['puzzles']==1000
    sides={r['n']:r['side']for r in official['results']}
    cases=json.loads((SOURCE/'cases.json').read_text());bank={};proof={};design={}
    out.mkdir(parents=True);shutil.copytree(SOURCE/'notices',out/'notices')
    shutil.copyfile(SOURCE/'cases.json',out/'scaffold-cases.json');shutil.copyfile(SOURCE/'manifest.json',out/'scaffold-manifest.json')
    (out/'portfolio-pointer.json').write_bytes(pb)
    with np.load(SOURCE/'scaffolds.npz',allow_pickle=False)as archive:
        for case in sorted(cases,key=lambda r:r['n']):
            n=case['n'];rows=[];bindings=[]
            for variant in case['variants']:
                if not variant['valid']:continue
                key=variant['archive_key'];p=archive[key].copy()
                assert p.shape==(n-1,3)and geometry_sha(p)==variant['geometry_sha256']and variant['full_certificate']['valid']
                bank[key]=p;center=np.array(variant['collision_center']);L=float(variant['side'])+5e-8
                axis=np.arange(-2.25,2.250001,.075);xx,yy=np.meshgrid(axis,axis)
                candidates=center+np.column_stack((xx.ravel(),yy.ravel()))
                for box_index,slack in enumerate((0.,.002)):
                    for angle_index,angle in enumerate((0.,math.pi/8,math.pi/4,-math.pi/8)):
                        values=clearances(p,candidates,angle,.05,L+slack)
                        eligible=np.flatnonzero(values>=(.002 if box_index==0 else .025))
                        assert len(eligible)>0,'No tiny-birth positive source center'
                        order=sorted(eligible,key=lambda i:(float(np.sum((candidates[i]-center)**2)),-float(values[i]),int(i)))
                        chosen=order[0];ghost=[*candidates[chosen],angle]
                        for schedule_index,schedule in enumerate(SCHEDULES):
                            row=dict(chain=len(rows),n=n,source_key=key,variant_index=len(bindings),
                                fixed_side=L+slack,box_slack=slack,angle_index=angle_index,birth_pose=ghost,
                                initial_birth_size=.05,initial_min_clearance=float(values[chosen]),
                                growth_schedule=list(schedule),schedule_index=schedule_index,
                                group=f'{key}-slack{box_index}',source_geometry_sha256=geometry_sha(p))
                            rows.append(row)
                bindings.append(dict(variant,source_key=key))
            assert len(bindings)==2 and len(rows)==32 and sorted(r['chain']for r in rows)==list(range(32))
            design[str(n)]=rows
            proof[str(n)]=dict(n=n,reference_side=str(sides[n]),source_case=case,variants=bindings,
                               all_old_units_side=1.,birth_row=n-1)
    np.savez_compressed(out/'birth-inputs.npz',**bank)
    save(out/'chain-design.json',design)
    config=dict(cases=proof,inputs_sha256=sha(out/'birth-inputs.npz'),design_sha256=sha(out/'chain-design.json'),
        baseline=pointer['raw'],source_manifest_sha256=SOURCE_SHA,chains=32,search_seconds=300,
        maximum_cycles=32,quench_steps_per_growth_stage=1200,
        seed=117498587,growth_schedules=[list(s)for s in SCHEDULES],
        restart_center_jitter=[0.,.015,.04,.08],restart_angle_jitter=[0.,.01,.03,.06],
        no_cross_size_metropolis=True,fresh_optimizer_history_every_growth_stage=True,
        intermediate_states='UNVERIFIED mixed-size proposals; only explicit all-lambda1 arrays may enter native finish',
        finish_slots_per_case=4,finish_workers_per_case=2,finish_native_seconds=60,finish_gate_seconds=8,
        work_seconds=570,whole_seconds=600,server_seconds=720,preflight_seconds=60,
        maximum_full_state_bytes_per_case=512*1024**2,cuda_options=['--std=c++17','--fmad=false'])
    save(out/'birth-config.json',config)
    sources=(Path(__file__),ROOT/'experiments/birth_continuation.py',ROOT/'experiments/birth_cuda.py')
    save(out/'input-proof.json',dict(source_manifest_sha256=SOURCE_SHA,scaffolds_archive_sha256=manifest['scaffolds_sha256'],
        inputs_sha256=config['inputs_sha256'],design_sha256=config['design_sha256'],baseline=pointer['raw'],
        source_hashes={str(p.relative_to(ROOT)):sha(p)for p in sources},
        arrays={k:dict(shape=list(p.shape),dtype=p.dtype.str,geometry_sha256=geometry_sha(p))for k,p in bank.items()},
        notices={p.relative_to(out).as_posix():sha(p)for p in(out/'notices').rglob('*')if p.is_file()},
        source_status='All four N-1 inputs exact-bound to complete existing full certificates; initial tiny candidates screened independently, not fullN packings.',
        no_new_optimization=True,no_submission=True))
    for p in out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps(dict(out=str(out),inputs_sha256=config['inputs_sha256'],design_sha256=config['design_sha256'],
        cases=list(proof),chains_each=32)),flush=True)

if __name__=='__main__':prepare(Path(sys.argv[1]))
