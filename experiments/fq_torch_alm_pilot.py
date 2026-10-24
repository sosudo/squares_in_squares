"""Bounded GPU feasibility pilot; raw stages are never implicit admissions."""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time
import zipfile
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import torch
from scipy.spatial import cKDTree
from fq_torch_alm import LiftedBatch,independent_lbfgs
from fq_torch_objective import objective
from full_structural_gpu_moves import coherent_start,geometry_sha
from compose_gadgets import side,normalize,legalize
from fq_capacity_probe import full_certificate


def atom_json(path,value):
    path=Path(path);tmp=path.with_suffix('.incoming');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def signed_pair_gap(p):
    pairs=cKDTree(p[:,:2]).query_pairs(1.5,output_type='ndarray')
    if not len(pairs):return float('inf')
    i,j=pairs.T;delta=p[j,:2]-p[i,:2];a,b=p[i,2],p[j,2]
    projection=np.maximum.reduce([abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t))for t in(a,a+math.pi/2,b,b+math.pi/2)])
    return float(np.min(projection-.5*(1+abs(np.cos(a-b))+abs(np.sin(a-b)))))


def main():
    started=time.monotonic();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.cuda.is_available();device=torch.device('cuda:0');assert'T4'in torch.cuda.get_device_name(device)
    config=json.loads(Path('pilot-config.json').read_text());data=Path('pilot-inputs.npz').read_bytes()
    assert hashlib.sha256(data).hexdigest()==config['inputs_sha256']
    with np.load('pilot-inputs.npz',allow_pickle=False)as z:bank={k:z[k]for k in z.files}
    for key,p in bank.items():
        expected=config['arrays'][key];assert list(p.shape)==expected['shape']and p.dtype.str==expected['dtype']
        assert hashlib.sha256(p.tobytes()).hexdigest()==expected['sha256']
    Path('raw').mkdir();raw=[];gates={};candidates={};potential=[];counter=0;labels=[]
    def retain(state,record,phase):
        nonlocal counter
        arrays=dict(poses=state.poses.detach().cpu().numpy(),sides=state.sides.detach().cpu().numpy(),
                    pairs=state.pair_ids.detach().cpu().numpy(),mask=state.mask.detach().cpu().numpy(),
                    lines=state.lines.detach().cpu().numpy(),wall_lambda=state.wall_lambda.detach().cpu().numpy(),
                    pair_lambda=state.pair_lambda.detach().cpu().numpy(),mu=state.mu.detach().cpu().numpy(),
                    list_reference=state.reference.detach().cpu().numpy())
        metadata=dict(phase=phase,index=counter,record=record,verified=False,
                      array_sha256={k:hashlib.sha256(v.tobytes()).hexdigest()for k,v in arrays.items()})
        arrays['metadata_json']=np.frombuffer(json.dumps(metadata).encode(),dtype=np.uint8)
        path=Path('raw')/f'stage-{counter:04d}.npz';counter+=1;tmp=path.with_suffix('.incoming')
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1)as z:
            for key,p in arrays.items():
                buffer=io.BytesIO();np.save(buffer,p,allow_pickle=False);z.writestr(key+'.npy',buffer.getvalue())
        tmp.replace(path);entry=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                   phase=phase,replicas=len(state.poses),n=state.N,record=record,verified=False)
        raw.append(entry);atom_json('raw-index.json',dict(stages=raw,verified=False))
        if phase.startswith('explore')and record.get('radius')==0.:
            for b,p in enumerate(arrays['poses']):
                if np.isfinite(p).all():potential.append(dict(path=str(path),replica=b,physical_side=side(p),
                    residual=record['violation'][b],geometry_sha256=geometry_sha(p),source=labels[b]))
        print(json.dumps(dict(stage=phase,outer=record.get('iteration'),radius=record.get('radius'),
                             seconds=time.monotonic()-started,replicas=len(state.poses),n=state.N)),flush=True)
    def state_of(p,s):
        return LiftedBatch(torch.tensor(p,dtype=torch.float64,device=device),torch.tensor(s,dtype=torch.float64,device=device))
    def save_certified(name,pose,certificate,source):
        assert certificate['valid'];folder=Path('certified');folder.mkdir(exist_ok=True)
        path=folder/(name+'.npz');temporary=path.with_suffix('.incoming')
        with temporary.open('wb')as stream:np.savez_compressed(stream,pose=pose)
        temporary.replace(path)
        record=dict(path=str(path),archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    geometry_sha256=geometry_sha(pose),count=len(pose),certificate=certificate,source=source,verified=True)
        atom_json(path.with_suffix('.json'),record);return record
    # A heterogeneous native-pinned pair objective test executes on the GPU.
    n=335;prefix='native';poses=bank[prefix+'_poses'];pairs=bank[prefix+'_pairs'];P=len(pairs)
    test=state_of(np.stack([poses,poses]),[float(bank[prefix+'_side'])]*2)
    test.pair_ids=torch.tensor(np.stack([pairs,pairs]),device=device);test.mask=torch.ones((2,P),dtype=torch.bool,device=device);test.mask[1,-7:]=False
    test.lines=torch.tensor(np.stack([bank[prefix+'_lines']]*2),dtype=torch.float64,device=device)
    test.wall_lambda=torch.tensor(np.stack([bank[prefix+'_wall_lambda'],2*bank[prefix+'_wall_lambda']]),dtype=torch.float64,device=device)
    test.pair_lambda=torch.tensor(np.stack([bank[prefix+'_pair_lambda'],2*bank[prefix+'_pair_lambda']]),dtype=torch.float64,device=device)*test.mask[...,None]
    test.mu=torch.tensor([71.,113.],dtype=torch.float64,device=device)
    value,gradient=test.value_grad(test.pack(),0.,False)
    assert abs(float(value[0])-float(bank[prefix+'_native_value']))<1e-8
    assert np.allclose(gradient[0].cpu().numpy(),bank[prefix+'_native_gradient'],rtol=1e-10,atol=1e-8)
    for b,count in((0,P),(1,P-7)):
        p=test.poses[b:b+1].clone().requires_grad_();s=test.sides[b:b+1].clone().requires_grad_();l=test.lines[b:b+1,:count].clone().requires_grad_()
        result=objective(p,s,l,test.pair_ids[b,:count],test.wall_lambda[b:b+1],test.pair_lambda[b:b+1,:count],float(test.mu[b]))
        grad=torch.cat([x.flatten()for x in torch.autograd.grad(result.sum(),(p,s,l))])
        assert torch.allclose(result[0],value[b],rtol=1e-10,atol=1e-8)
        assert torch.allclose(grad,gradient[b,:3*n+1+2*count],rtol=1e-10,atol=1e-8)
        assert float(gradient[b,3*n+1+2*count:].abs().sum())==0.
    gates['native_and_heterogeneous_masked_objective']=True
    invalid=test.pack();invalid[0,0]+=.151;assert not bool(test.valid(invalid)[0]);gates['trial_verlet_rejection']=True
    del test
    # Actual full-N pair repair and zero-radius return, with final full gates.
    control_started=time.monotonic()
    for n in(147,299,335):
        original=bank[f'reference_{n}'];p=original.copy();p[:,:2]*=1.003;p=normalize(p);box=side(p)+.01
        if n==147:
            folded=(p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4;upright=np.flatnonzero(abs(folded)<1e-5)
            distances,neighbors=cKDTree(p[upright,:2]).query(p[upright,:2],k=2)
            a=int(np.argmin(distances[:,1]));b=int(neighbors[a,1]);i,j=int(upright[a]),int(upright[b])
            p[j,:2]+=.006*(p[i,:2]-p[j,:2])
        state=state_of(p[None],[box]);wall,pair=state.constraints(state.pack(),0.,True)
        initial=dict(pair_violation=float(pair.max()),wall_violation=float(wall.max()),signed_pair_gap=signed_pair_gap(p))
        if n==147:assert initial['pair_violation']>1e-4 and initial['signed_pair_gap']< -1e-4
        retain(state,dict(radius=0.,initial=True),f'control{n}-input')
        executed_radii=[]
        for radius in(.3,.1,0.):
            control_rows=state.stage(radius,True,outer=6,inner=40,tolerance=1e-9,
                callback=lambda q,r,state=state,n=n:retain(state,r,f'control{n}'),deadline=lambda:time.monotonic()-started>80)
            assert control_rows and control_rows[-1]['radius']==radius
            executed_radii.extend(r['radius']for r in control_rows)
        q=state.poses[0].cpu().numpy();assert q.shape==(n,3)and float(state.sides[0])==box
        wall,pair=state.constraints(state.pack(),0.,True);final=float(torch.maximum(wall.max(),pair.max()))
        assert final<1e-7
        corrected=legalize(q,clearance=2e-9);assert corrected is not None
        certificate=full_certificate(corrected);assert certificate['valid']
        certified=save_certified(f'control{n}',corrected,certificate,
            dict(raw_stage=raw[-1]['path'],raw_archive_sha256=raw[-1]['sha256'],raw_geometry_sha256=geometry_sha(q)))
        gates[str(n)]=dict(initial=initial,final_violation=final,held_side_bit_equal=True,
                          returned_radius=executed_radii[-1],executed_radii=executed_radii,count=n,certified_pose=certified)
        atom_json('preflight.json',dict(passed=False,gates=gates))
    # Duplicate involving the final square must be detected at full N.
    bad=bank['reference_335'].copy();bad[-1]=bad[0]
    state=state_of(bad[None],[side(bad)+.1]);wall,pair=state.constraints(state.pack(),0.,True)
    _,gradient=state.value_grad(state.pack(),0.,True)
    assert float(pair.max())>.4 and float(torch.linalg.vector_norm(gradient[0,3*334:3*334+2]))>1e-3
    assert not full_certificate(bad)['valid'];gates['full_last_index_duplicate_rejected']=True
    atom_json('preflight.json',dict(passed=True,seconds=time.monotonic()-control_started,gates=gates))
    print(json.dumps(dict(stage='all_controls_passed',seconds=time.monotonic()-started)),flush=True)
    # No optimization stage below is reachable before the live controls pass.
    sources=config['exploratory_sources'];starts=[];sides=[]
    for b in range(32):
        key=sources[b%len(sources)];p=bank[key]
        mode='identity'if b<3 else('column_slide','bend','hinge')[(b//len(sources))%3]
        amplitude=(.03,.08,.15)[(b//9)%3];q,mutation=coherent_start(p,440000+b,mode,amplitude)
        starts.append(q);sides.append(side(p)+1e-8);labels.append(dict(source_key=key,mutation=mutation))
    atom_json('start-provenance.json',labels);state=state_of(np.asarray(starts),sides)
    retain(state,dict(radius=.3,initial=True), 'explore-input')
    exploration_started=time.monotonic();deadline=min(started+240,exploration_started+180)
    completed=[];last_radius=None
    for label,radius,fixed in [('held-rounded',.3,True),('held-rounded-return',.1,True),('held-rigid',0.,True),
                               ('rigid-compression',0.,True),('rigid-release',0.,False)]:
        if time.monotonic()>=deadline:break
        if label=='rigid-compression':
            state.sides[:]=torch.tensor([config['current_335_side']-config['compression_depths'][b%4]for b in range(32)],dtype=torch.float64,device=device)
        records=state.stage(radius,fixed,outer=7,inner=35,tolerance=1e-8,
            callback=lambda q,r,label=label:retain(state,r,'explore-'+label),deadline=lambda:time.monotonic()>=deadline)
        if records:last_radius=records[-1]['radius']
        completed.append(dict(label=label,outer_completed=len(records),requested_outer_limit=7,
                              final_violation=records[-1]['violation']if records else None))
    optimization_seconds=time.monotonic()-exploration_started
    atom_json('search-summary.json',dict(seconds=optimization_seconds,completed=completed,raw_stages=len(raw),
        potential_rigid_records=len(potential),native_finishing_performed=False,final_radius=last_radius,
        full_stage_plan_executed=len(completed)==5 and all(r['outer_completed']>0 for r in completed)))
    # Tiny separate gate drain; all other actual raw stages remain available.
    ordered=sorted(potential,key=lambda r:(r['physical_side'],r['residual']))
    selected=[];seen=set()
    for row in ordered:
        if row['geometry_sha256']in seen:continue
        seen.add(row['geometry_sha256']);selected.append(row)
        if len(selected)==4:break
    drain_started=time.monotonic();admissions=[]
    for row in selected:
        if time.monotonic()-started>280:break
        with np.load(row['path'],allow_pickle=False)as z:p=z['poses'][row['replica']]
        assert geometry_sha(p)==row['geometry_sha256'];q=legalize(p,clearance=2e-9)
        certificate=full_certificate(q)if q is not None else{'valid':False,'reason':'residual_exceeds_clearance_repair'}
        admission=dict(row,certificate=certificate);admissions.append(admission)
        if certificate['valid']:
            admission['certified_pose']=save_certified(f'candidate-{len(admissions):02d}',q,certificate,row)
            length=float(certificate['independent_raw']['side_upper'])
            if length<config['current_335_side']-1e-8:
                old=candidates.get('335')
                if old is None or length<old['side']:candidates['335']=dict(side=length,squares=[[f'{v:.17g}'for v in r]for r in q],certificate=certificate,provenance=row)
        atom_json('candidate-gates.json',admissions);atom_json('candidates.json',candidates)
    atom_json('candidate-gates.json',admissions);atom_json('candidates.json',candidates)
    atom_json('pilot-summary.json',dict(controls_passed=True,seconds=time.monotonic()-started,
        optimization_seconds=optimization_seconds,gate_drain_seconds=time.monotonic()-drain_started,
        completed=completed,raw_stages=len(raw),raw_replica_poses=sum(r['replicas']for r in raw),
        rigid_records=len(potential),gate_attempts=len(admissions),improved_cases=len(candidates),
        native_finishing_performed=False,peak_memory_bytes=torch.cuda.max_memory_allocated(device)))
    print(json.dumps(dict(stage='complete',seconds=time.monotonic()-started,improved_cases=len(candidates))),flush=True)


if __name__=='__main__':main()
