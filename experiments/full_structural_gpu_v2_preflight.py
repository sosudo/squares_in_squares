"""V1 full-size controls generalized to the explicit frozen family inventory.

Only the family loop differs; v1 and upstream sources remain untouched.
"""
from full_structural_gpu_worker import *


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
    for n in sorted(reference):
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
