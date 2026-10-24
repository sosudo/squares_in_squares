"""Bounded full-N CUDA repair; same exact final gates on both continuation arms."""
from __future__ import annotations
import os
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_name]='1'
import argparse
import json
import math
from pathlib import Path
import signal
import time
import numpy as np
from scipy.spatial import cKDTree
from compose_gadgets import normalize,side,legalize
from fq_capacity_probe import full_certificate
from fq_active_pilot import digest
from fq_coherent_clusters import atom_json,atom_npz,Deadline,alarm
from full_structural_gpu_moves import coherent_start,geometry_sha


def dense_oracle(p,box):
    """All-pair CPU SAT oracle, independent of CUDA neighbor hashing."""
    a=p[:,2];extent=.5*(abs(np.cos(a))+abs(np.sin(a)))
    walls=np.maximum(0.,np.array([extent-p[:,0],extent-p[:,1],
                                  p[:,0]+extent-box[0],p[:,1]+extent-box[1]]))
    maximum=float(walls.max())
    i,j=np.triu_indices(len(p),1);delta=p[j,:2]-p[i,:2]
    projection=np.maximum.reduce([abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t))
                                  for t in (a[i],a[i]+np.pi/2,a[j],a[j]+np.pi/2)])
    radius=.5*(1+abs(np.cos(a[i]-a[j]))+abs(np.sin(a[i]-a[j])))+2e-10
    penetration=np.maximum(0.,radius-projection)
    return float(2*np.sum(walls**2)+.5*np.sum(penetration**2)),max(maximum,float(penetration.max()))


def assert_dense_matches(native,p,box):
    energy,residual=dense_oracle(p,box)
    assert abs(native[0]-energy)<1e-8*max(1.,energy)
    assert abs(native[1]-residual)<2e-9


def bounded_certificate(p,seconds=8):
    previous=signal.signal(signal.SIGALRM,alarm)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try:return full_certificate(p)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)


def preflight(cp,gpu,reference,alternatives,device,out):
    result={'device':device,'gradient':gpu.check(),'full_cases':{}}
    control_poses={};control_records={}
    (out/'preflight_entries').mkdir()
    def retain_control(label,pose,certificate,provenance):
        sha=geometry_sha(pose);name=label+'__'+sha;control_poses[name]=pose.copy()
        control_records[name]=dict(geometry_sha256=sha,certificate=certificate,provenance=provenance)
        entry=out/'preflight_entries'/name
        atom_npz(entry.with_suffix('.npz'),{'pose':pose})
        atom_json(entry.with_suffix('.json'),dict(control_records[name],npz_sha256=digest(entry.with_suffix('.npz'))))
        entry.with_suffix('.npz').chmod(0o444);entry.with_suffix('.json').chmod(0o444)
        atom_npz(out/'preflight_packings.npz',control_poses)
        atom_json(out/'preflight_packing_records.json',dict(records=control_records,
            archive_sha256=digest(out/'preflight_packings.npz')))
    for n in (299,335):
        p=reference[n];alt=alternatives[n][0][1]
        q=np.stack((p,alt));boxes=np.array([[side(x)+1e-6]*2 for x in q])
        e,_=gpu.energy(q,boxes,tau=0)
        assert q.shape==(2,n,3) and np.max(e[:,1])<1e-7
        for i in range(2):assert_dense_matches(e[i],q[i],boxes[i])
        preserved,report=gpu.quench(q.copy(),boxes,steps=80,tau=0)
        preserved=cp.asnumpy(preserved);report=cp.asnumpy(report)
        certificates=[]
        for candidate_index,candidate in enumerate(preserved):
            candidate=legalize(candidate,clearance=2e-9)
            assert candidate is not None and len(candidate)==n
            certificate=bounded_certificate(candidate)
            assert certificate['valid'];certificates.append(certificate)
            retain_control(f'n{n}_unchanged_{candidate_index}',candidate,certificate,
                           dict(control='unchanged_full_seed',source_geometry_sha256=geometry_sha(q[candidate_index])))
        bad=p.copy();bad[-1]=bad[0];bad[-1,0]+=.1
        negative,gradient=gpu.energy(bad[None],[[side(p)+.01]*2],tau=0)
        assert negative[0,1]>.8 and np.linalg.norm(gradient[0,-1])>.01
        assert_dense_matches(negative[0],bad,[side(p)+.01]*2)
        assert not bounded_certificate(bad)['valid']
        boundary=p.copy();boundary[-2,:]=[5.9999,6.,0.];boundary[-1,:]=[6.0001,6.,0.]
        boundary_energy,_=gpu.energy(boundary[None],[[side(p)+.01]*2],tau=0)
        assert boundary_energy[0,1]>.99
        assert_dense_matches(boundary_energy[0],boundary,[side(p)+.01]*2)
        # A deliberately overlapping pair inside a mildly expanded full packing.
        positive=p.copy();positive[:,:2]*=1.003;positive=normalize(positive)
        folded=(positive[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
        ids=np.flatnonzero(abs(folded)<1e-5)
        distances,neighbors=cKDTree(positive[ids,:2]).query(positive[ids,:2],k=2)
        i=int(np.argmin(distances[:,1]));j=int(neighbors[i,1]);i,j=int(ids[i]),int(ids[j])
        positive[j,:2]+=.004*(positive[i,:2]-positive[j,:2])
        box=[[side(positive)+.01]*2]
        before,_=gpu.energy(positive[None],box,tau=0)
        assert before[0,1]>1e-5
        repaired=cp.asarray(positive[None]);timings=[]
        for _ in range(4):
            at=time.monotonic();repaired,_=gpu.quench(repaired,box,steps=350,tau=0)
            cp.cuda.get_current_stream().synchronize();timings.append(time.monotonic()-at)
        res,_=gpu.energy(repaired,box,tau=0)
        repaired=cp.asnumpy(repaired)[0]
        assert res[0,1]<1e-7 and len(repaired)==n
        repaired=legalize(repaired,clearance=2e-9)
        assert repaired is not None
        positive_certificate=bounded_certificate(repaired);assert positive_certificate['valid']
        retain_control(f'n{n}_overlap_repair',repaired,positive_certificate,
                       dict(control='expanded_full_pair_overlap',source_geometry_sha256=geometry_sha(p),
                            input_geometry_sha256=geometry_sha(positive),box=box[0]))
        coherent_trials=[]
        for amplitude in (.0001,.00001):
            mild,move=coherent_start(p,27100+n,'bend',amplitude)
            mild_box=[[side(p)+.02]*2];before_mild,_=gpu.energy(mild[None],mild_box,tau=0)
            assert move['maximum_displacement']>amplitude*.5 and move['upright_coordinates_preserved']
            fixed=cp.asarray(mild[None])
            for _ in range(4):fixed,_=gpu.quench(fixed,mild_box,steps=350,tau=0)
            fixed_res,_=gpu.energy(fixed,mild_box,tau=0);fixed=legalize(cp.asnumpy(fixed)[0],clearance=2e-9)
            certificate=bounded_certificate(fixed)if fixed is not None and fixed_res[0,1]<1e-7 else{'valid':False}
            coherent_trials.append(dict(amplitude=amplitude,mutation=move,before=float(before_mild[0,1]),
                                        after=float(fixed_res[0,1]),certificate=certificate))
            if certificate['valid']:
                retain_control(f'n{n}_coherent_repair',fixed,certificate,
                               dict(control='coherent_bend',mutation=move,box=mild_box[0]))
                break
        assert any(r['certificate']['valid']for r in coherent_trials),'Actual coherent full-N repair control failed'
        result['full_cases'][str(n)]=dict(reference_geometry_sha256=geometry_sha(p),
            alternative_geometry_sha256=geometry_sha(alt),all_n_coordinates_preserved=True,
            unchanged_seed_certificates=certificates,last_index=n-1,
            all_pair_cpu_oracle_matches=True,across_hash_cell_boundary_detected=True,
            last_index_negative_penetration=float(negative[0,1]),last_index_gradient_norm=float(np.linalg.norm(gradient[0,-1])),
            deliberate_overlap_before=float(before[0,1]),repair_residual=float(res[0,1]),
            cuda_350step_call_seconds=timings,
            coherent_repair_controls=coherent_trials,
            repair_certificate=positive_certificate)
        atom_json(out/'preflight.json',result)
        print(json.dumps(dict(stage='full_N_preflight',device=device,n=n,passed=True,
                             before=float(before[0,1]),after=float(res[0,1]))),flush=True)
    result['passed']=True
    result['certified_control_packings_sha256']=digest(out/'preflight_packings.npz')
    result['certified_control_records_sha256']=digest(out/'preflight_packing_records.json')
    atom_json(out/'preflight.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',type=int,required=True);args=parser.parse_args()
    import cupy as cp
    import gpu_rect_optimizer as gpu
    config=json.loads(Path('prepared_config.json').read_text())
    cp.cuda.Device(args.device).use();out=Path(f'artifacts/full_structural_device{args.device}');out.mkdir()
    (out/'entries').mkdir()
    reference={};pool={299:[],335:[]}
    with np.load('prepared_references.npz',allow_pickle=False)as z:
        reference={int(k):z[k]for k in z.files}
    with np.load('prepared_variants.npz',allow_pickle=False)as z:
        for name in z.files:pool[len(z[name])].append((name,z[name]))
    for n in pool:pool[n].sort(key=lambda item:(side(item[1]),geometry_sha(item[1])))
    preflight(cp,gpu,reference,pool,args.device,out)
    waiting=time.monotonic()
    while not Path('preflight-approved.json').exists():
        if time.monotonic()-waiting>180:raise TimeoutError('Both-arm CUDA preflight barrier expired')
        time.sleep(1)
    start=time.monotonic();deadline=start+config['search_seconds']
    rng=np.random.default_rng(config['device_seeds'][str(args.device)])
    arm='exact'if args.device==0 else'smooth'
    records=[];poses={};exploratory={};exploratory_records={};seen=set();snapshot=0;batch_index=0
    best={n:float(config['reference_sides'][str(n)])for n in reference}
    stats=dict(batches=0,full_pose_trials=0,exact_feasible=0,full_certificates=0,
               certified=0,strict_gains=0,cuda_seconds=0.,certification_seconds=0.,upright_start_binding_failures=0)

    def checkpoint(status):
        nonlocal snapshot
        snapshot+=1;dest=out/f'snapshot-{snapshot:05d}';dest.mkdir()
        atom_npz(dest/'certified.npz',poses);atom_json(dest/'records.json',records)
        atom_npz(dest/'exploratory.npz',exploratory);atom_json(dest/'exploratory.json',exploratory_records)
        summary=dict(status=status,device=args.device,arm=arm,seconds=time.monotonic()-start,
                     stats=stats,best_sides=best,files={p.name:digest(p)for p in dest.iterdir()})
        atom_json(dest/'summary.json',summary)
        for p in dest.iterdir():p.chmod(0o444)
        atom_json(out/'current.json',dict(snapshot=str(dest),summary_sha256=digest(dest/'summary.json')))
        atom_json(out/'status.json',summary)

    checkpoint('started')

    def retain_stage(q,boxes,metadata,stage,n):
        """Exact re-evaluation and durable publication before another GPU stage."""
        at=time.monotonic();exact,_=gpu.energy(q,boxes,tau=0);host=cp.asnumpy(q)
        stats['cuda_seconds']+=time.monotonic()-at
        eligible=np.flatnonzero(exact[:,1]<1e-7);stats['exact_feasible']+=len(eligible)
        for index in sorted(eligible,key=lambda i:side(host[i])):
            if time.monotonic()>deadline-8:break
            candidate=legalize(host[index],clearance=2e-9)
            if candidate is None:continue
            sha=geometry_sha(candidate)
            if sha in seen:continue
            seen.add(sha);stats['full_certificates']+=1;at=time.monotonic()
            try:certificate=bounded_certificate(candidate)
            except Deadline:certificate={'valid':False,'status':'certificate-timeout'}
            stats['certification_seconds']+=time.monotonic()-at
            if not certificate['valid']:continue
            length=float(certificate['independent_raw']['side_upper']);name=f'{n}__{sha}'
            gain=float(config['reference_sides'][str(n)])-length
            record=dict(name=name,n=n,geometry_sha256=sha,side=length,side_gain=gain,
                        certificate=certificate,mutation=metadata[int(index)],exact_residual=float(exact[index,1]),
                        source_pool_sha256=config['variants_sha256'],arm=arm,stage=stage)
            entry=out/'entries'/name
            atom_npz(entry.with_suffix('.npz'),{'pose':candidate})
            record['entry_npz_sha256']=digest(entry.with_suffix('.npz'))
            atom_json(entry.with_suffix('.json'),record)
            entry.with_suffix('.npz').chmod(0o444);entry.with_suffix('.json').chmod(0o444)
            poses[name]=candidate;records.append(record);stats['certified']+=1
            if length<best[n]-1e-9:best[n]=length;stats['strict_gains']+=1
        for index in np.argsort(exact[:,1])[:2]:
            if exact[index,1]>.003 or len(exploratory)>=128:continue
            sha=geometry_sha(host[index]);name=f'{n}__{sha}'
            if name in exploratory:continue
            exploratory[name]=host[index]
            exploratory_records[name]=dict(validated=False,n=n,geometry_sha256=sha,stage=stage,
                exact_residual=float(exact[index,1]),mutation=metadata[int(index)],target_side=float(boxes[index,0]))
        return exact

    while time.monotonic()<deadline-35:
        n=(299,335)[batch_index%2];B=config['replicas'];inputs=[];metadata=[];targets=[];loose=[]
        for b in range(B):
            # Every fourth start is the unchanged frozen current family source.
            if b%4==0:source_name=f'current_{n}';source=reference[n]
            else:source_name,source=pool[n][(batch_index*B+b)%len(pool[n])]
            mode=('identity','column_slide','bend','hinge')[(b+b//4+batch_index)%4]
            amplitude=(.03,.08,.18,.30)[(b//4+batch_index)%4]
            seed=int(rng.integers(2**31));q,details=coherent_start(source,seed,mode,amplitude)
            details.update(source_name=source_name,batch=batch_index,replica=b,n=n)
            details['source_archive_sha256']=config['references_sha256']if source_name.startswith('current_')else config['variants_sha256']
            inputs.append(q);metadata.append(details)
            source_side=side(source);loose.append([source_side+(.015,.04,.08)[b%3]]*2)
            depth=(.000002,.00001,.00005,.0002)[b%4]
            targets.append([float(config['reference_sides'][str(n)])-depth]*2);details['target_side']=targets[-1][0]
            details['loose_side']=loose[-1][0]
        q=cp.asarray(np.array(inputs),dtype=cp.float64);targets=np.array(targets);loose=np.array(loose)
        stages=[(.02,loose,'loose_soft02'),(.005,loose,'loose_soft005')]if arm=='smooth'else[(0.,loose,'loose_exact0'),(0.,loose,'loose_exact1')]
        stages += [(0.,targets,f'target_exact{i}')for i in range(3)]
        stats['full_pose_trials']+=B;exact=np.zeros((B,2))
        for tau,boxes,label in stages:
            if time.monotonic()>deadline-15:break
            at=time.monotonic();q,_=gpu.quench(q,boxes,steps=400,tau=tau)
            cp.cuda.get_current_stream().synchronize();stats['cuda_seconds']+=time.monotonic()-at
            exact=retain_stage(q,boxes,metadata,label,n)
        stats['batches']+=1
        batch_index+=1;checkpoint('running')
        print(json.dumps(dict(stage='batch',device=args.device,arm=arm,n=n,batch=batch_index,
                             minimum_residual=float(exact[:,1].min()),best=best,**stats)),flush=True)
    checkpoint('complete')
    print(json.dumps(dict(stage='complete',device=args.device,arm=arm,best=best,**stats)),flush=True)


if __name__=='__main__':main()
