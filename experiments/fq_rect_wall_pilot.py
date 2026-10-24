"""Finite rigid-square rectangular-wall continuation; no Metropolis or scaling."""
from __future__ import annotations
import argparse
from decimal import Decimal,localcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_fused_hop_pilot as fused
from fq_torch_hop_pilot import PacketStore,atom_json,digest,json_finite
from full_structural_gpu_ties import check_cuda
from full_structural_gpu_v2_preflight import preflight as full_preflight
from full_structural_gpu_worker import assert_dense_matches,bounded_certificate
from full_structural_gpu_moves import geometry_sha
from fq_coherent_clusters import atom_npz,Deadline
from prepare_wall_aspect_inputs import rectangular_control
from compose_gadgets import legalize,side


def load_inputs():
    config=json.loads(Path('rect-config.json').read_text())
    assert digest('rect-inputs.npz')==config['inputs_sha256']
    with np.load('rect-inputs.npz',allow_pickle=False)as z:data={k:z[k]for k in z.files}
    assert data['starts'].shape==(32,335,3)and data['boxes'].shape==(49,32,2)
    assert data['centering_deltas'].shape==data['boxes'].shape
    assert config['steps_per_stage']==2000 and config['search_seconds']==180
    assert all(np.isfinite(x).all()for x in data.values())
    assert np.max(abs(data['boxes'].prod(2)-config['area']))<1e-10
    assert np.array_equal(data['boxes'][32:],np.full((17,32,2),config['target_side']))
    assert np.array_equal(data['centering_deltas'][0],np.zeros((32,2)))
    assert np.array_equal(data['centering_deltas'][1:],np.diff(data['boxes'],axis=0)/2)
    for row,p in zip(config['design'],data['starts']):assert geometry_sha(p)==row['geometry_sha256']
    return config,data


def metrics(poses,boxes):
    return[rectangular_control(p,float(w),float(h))for p,(w,h)in zip(poses,boxes)]


def certified_gain(certificate,baseline):
    """Recheck every official/numeric transport side, never just float spans."""
    with localcontext()as context:
        context.prec=70;reference=Decimal(str(baseline));shared=certificate['shared_official_gate']
        sides=[Decimal(str(x))for x in(shared['raw_side'],shared['roundtrip_side'],
            certificate['ordinary_pandas_official_side'],certificate['independent_raw']['side_upper'],
            certificate['independent_roundtrip']['side_upper'])]
        assert all(x.is_finite()for x in sides)and reference.is_finite()
        worst=max(sides);gain=reference-worst
        return dict(actual_improvement=bool(certificate['valid']and gain>Decimal('1e-9')),
            certified_worst_side=str(worst),baseline_side=str(reference),conservative_side_gain=str(gain),
            conservative_score_gain=str(gain/Decimal(335).sqrt()))


def preflight():
    started=time.monotonic();config,data=load_inputs();cp,gpu,audit=fused.configure_gpu()
    device_name=cp.cuda.runtime.getDeviceProperties(0)['name']
    assert'T4'in(device_name.decode()if isinstance(device_name,bytes)else str(device_name))
    folder=Path('rect-preflight');folder.mkdir()
    atom_json(folder/'gradient-patch.json',audit);atom_json(folder/'gradient-controls.json',check_cuda(gpu))
    fixture=json.loads(Path('pilot-config.json').read_text());assert digest('pilot-inputs.npz')==fixture['inputs_sha256']
    with np.load('pilot-inputs.npz',allow_pickle=False)as z:bank={k:z[k]for k in z.files}
    keys=fixture['exploratory_sources']
    for key in keys:assert geometry_sha(bank[key])==fixture['arrays'][key]['sha256']
    previous=full_preflight(cp,gpu,{335:bank[keys[0]]},{335:[(k,bank[k])for k in keys[1:]]},0,folder)
    assert previous['passed']
    starts=data['starts'];boxes=data['boxes'][0];checks=metrics(starts,boxes)
    assert all(r['energy']==0 and r['minimum_wall_gap']>0 and r['minimum_pair_gap']>0 for r in checks)
    native,_=gpu.energy(starts,boxes,tau=0.)
    assert np.max(native[:,1])<1e-8
    for i in range(32):assert_dense_matches(native[i],starts[i],boxes[i])
    controls=[];positive={};positive_proofs={}
    for representative in(0,16):
        p=starts[representative];w,h=boxes[representative]
        swapped,_=gpu.energy(p[None],[[h,w]],tau=0.)
        assert swapped[0,1]>.5;assert_dense_matches(swapped[0],p,[h,w])
        for label,box in[('initial_rectangle',[w,h]),('final_square',[config['target_side']]*2)]:
            bad=p.copy();bad[-1]=bad[0];bad[-1,0]+=.1
            e,g=gpu.energy(bad[None],[box],tau=0.)
            assert e[0,1]>.8 and np.linalg.norm(g[0,-1])>.01;assert_dense_matches(e[0],bad,box)
            controls.append(dict(representative=representative,box=box,endpoint=label,negative_pair_residual=float(e[0,1])))
        wall=p.copy();extent=.5*(abs(np.cos(wall[0,2]))+abs(np.sin(wall[0,2])))
        wall[0,0]=extent-.002;e,g=gpu.energy(wall[None],[[w,h]],tau=0.)
        assert e[0,1]>.001 and abs(g[0,0,0])>.001;assert_dense_matches(e[0],wall,[w,h])
        plus=wall.copy();minus=wall.copy();plus[0,0]+=1e-6;minus[0,0]-=1e-6
        fd=(gpu.energy(plus[None],[[w,h]],tau=0.)[0][0,0]-gpu.energy(minus[None],[[w,h]],tau=0.)[0][0,0])/2e-6
        assert abs(fd-g[0,0,0])<2e-6
        fixed,_=gpu.quench(cp.asarray(wall[None]).copy(),[[w,h]],steps=2000,tau=0.)
        cp.cuda.get_current_stream().synchronize();q=cp.asnumpy(fixed)[0]
        rect=rectangular_control(q,w,h);assert rect['energy']<1e-14 and rect['minimum_wall_gap']>-1e-7
        repaired=legalize(q);assert repaired is not None
        certificate=bounded_certificate(repaired);assert certificate['valid']and certificate['independent_raw']['n']==335
        key=f'family{representative}';positive[key]=repaired
        positive_proofs[key]=dict(certificate=certificate,geometry_sha256=geometry_sha(repaired),
            raw_repaired_geometry_sha256=geometry_sha(q),raw_rectangle_control=rect,actual_box=[w,h],
            physical_wall_finite_difference_error=float(abs(fd-g[0,0,0])))
        atom_npz(folder/(key+'-raw-control.npz'),dict(input=wall,output=q,box=np.array([w,h])))
    atom_npz(folder/'rectangular-certified-controls.npz',positive)
    atom_json(folder/'rectangular-certified-controls.json',dict(records=positive_proofs,archive_sha256=digest(folder/'rectangular-certified-controls.npz')))
    result=dict(passed=True,seconds=time.monotonic()-started,initial_rectangles=checks,full335_controls=True,
        unit_shape='Fixed rigid unit squares',wall_dimensions_independent=True,negative_controls=controls,
        cuda_options=list(fused.CUDA_OPTIONS),input_sha256=config['inputs_sha256'])
    atom_json('preflight.json',result);print(json.dumps(dict(stage='rectangular_preflight',passed=True,seconds=result['seconds'])),flush=True)
    return result


def search(deadline):
    config,data=load_inputs();assert json.loads(Path('preflight.json').read_text())['passed']
    cp,gpu,_=fused.configure_gpu();store=PacketStore('raw-wall',32,335,config['max_packets'],config['max_bytes'])
    current=data['starts'].copy();completed=0;started=time.monotonic();quench_seconds=0.;cpu_seconds=0.
    for stage,boxes in enumerate(data['boxes']):
        if time.monotonic()>=deadline or not store.can_begin():break
        prior=current.copy();actual=prior.copy();actual[:,:,:2]+=data['centering_deltas'][stage,:,None,:]
        assert np.array_equal(actual[:,:,2],prior[:,:,2])
        meta=dict(stage=stage,final_square=stage>=32,boxes=boxes.tolist(),center_deltas=data['centering_deltas'][stage].tolist(),
            design=config['design'],unit_count=335,unit_shapes_unchanged=True,transition='Uniform center translation only',
            input_configuration_sha256=digest('rect-config.json'),verified=False)
        packet=store.begin(dict(prior_output=prior,stage_input=actual,boxes=boxes),meta)
        at=time.monotonic();q,native=gpu.quench(cp.asarray(actual).copy(),boxes,steps=2000,tau=0.)
        cp.cuda.get_current_stream().synchronize();host=cp.asnumpy(q);report=cp.asnumpy(native);elapsed=time.monotonic()-at
        quench_seconds+=elapsed;assert host.shape==(32,335,3)and np.isfinite(host).all()
        at=time.monotonic();physical=metrics(host,boxes);cpu_seconds+=time.monotonic()-at
        native_exact,_=gpu.energy(q,boxes,tau=0.)
        energy=np.array([r['energy']for r in physical])
        event=dict(stage=stage,final_square=stage>=32,steps_requested=2000,tau=0.,
            physical_rectangle_metrics=physical,native_quench_report=report.tolist(),
            fresh_native_metrics=native_exact.tolist(),native_loss_is_not_physical_energy=True,
            native_report_may_describe_rejected_trial=True,quench_seconds=elapsed,
            elapsed_since_child_started=time.monotonic()-started)
        entry=store.complete(packet,dict(prior_output=prior,stage_input=actual,stage_output=host,boxes=boxes,
            physical_energy=energy),dict(meta,event=event))
        with open('wall-events.jsonl','a')as stream:stream.write(json.dumps(dict(event,packet=entry),allow_nan=False)+'\n')
        current=host;completed+=1
        status=dict(completed_stages=completed,final_square_stages=max(0,completed-32),
            last_stage=stage,last_box=boxes.tolist(),minimum_physical_energy=float(energy.min()),
            median_physical_energy=float(np.median(energy)),quench_seconds=quench_seconds,
            independent_metrics_seconds=cpu_seconds,raw_packets=len(store.entries),raw_bytes=store.used,verified=False)
        atom_json('wall-status.json',status)
        print(json.dumps(dict(stage='wall',number=stage,min_energy=float(energy.min()),seconds=time.monotonic()-started)),flush=True)
    atom_json('search-finished.json',dict(stages=completed,complete_path=completed>=33,complete_plan=completed==49,
        seconds=time.monotonic()-started,quench_seconds=quench_seconds,independent_metrics_seconds=cpu_seconds))


def recover_and_certify():
    config,_=load_inputs();index=json.loads(Path('raw-index.json').read_text())if Path('raw-index.json').exists()else{'packets':[]}
    completed=[];best=None;best_energy=np.full(32,np.inf);best_stage=np.full(32,-1);last=None
    candidates={};current_baseline=json.loads(Path('job_manifest.json').read_text())['baseline335']
    baseline=float(current_baseline['side'])
    for entry in index['packets']:
        path=Path(entry['path']);assert digest(path)==entry['sha256']
        if entry['status']!='completed':continue
        with np.load(path,allow_pickle=False)as z:
            metadata=json.loads(z['metadata_json'].tobytes());arrays={k:z[k]for k in z.files if k!='metadata_json'}
        for key,value in arrays.items():assert hashlib.sha256(value.tobytes()).hexdigest()==metadata['array_sha256'][key]
        stage=metadata['stage'];p=arrays['stage_output'];boxes=arrays['boxes'];last=entry;completed.append(stage)
        if metadata['final_square']:
            assert np.array_equal(boxes,np.full((32,2),config['target_side']))
            energy=arrays['physical_energy']
            if best is None:best=p.copy()
            mask=energy<best_energy;best[mask]=p[mask];best_energy[mask]=energy[mask];best_stage[mask]=stage
            for replica,q in enumerate(p):
                fixed=legalize(q)
                if fixed is not None and side(fixed)<baseline-1e-9:
                    identity=geometry_sha(fixed)
                    candidates.setdefault(identity,dict(pose=fixed,side=side(fixed),raw_packet=entry,
                        raw_geometry_sha256=geometry_sha(q),stage=stage,replica=replica,geometry_sha256=identity))
    if best is not None:atom_npz(Path('final-square-best.npz'),dict(poses=best,energy=best_energy,stage=best_stage))
    pending={k:{x:v for x,v in r.items()if x!='pose'}for k,r in candidates.items()}
    atom_npz(Path('pending-square-candidates.npz'),{k:r['pose']for k,r in candidates.items()})
    atom_json('pending-square-candidates.json',dict(verified=False,records=pending))
    began=time.monotonic();certified=[];failures=[];attempted=0;Path('certified').mkdir(exist_ok=True)
    for record in sorted(candidates.values(),key=lambda r:r['side'])[:config['certification_max_candidates']]:
        remaining=config['certification_seconds']-(time.monotonic()-began)
        if remaining<1:break
        attempted+=1
        try:
            certificate=bounded_certificate(record['pose'],seconds=min(8,remaining))
            if certificate['valid']:
                assert certificate['independent_raw']['n']==335
                path=Path('certified')/(record['geometry_sha256']+'.npz');atom_npz(path,dict(pose=record['pose']))
                proof=dict(pending[record['geometry_sha256']],certificate=certificate,archive_sha256=digest(path),verified=True,
                    **certified_gain(certificate,current_baseline['side']))
                atom_json(path.with_suffix('.json'),proof);certified.append(proof)
            else:failures.append(dict(geometry_sha256=record['geometry_sha256'],certificate=certificate))
        except (Deadline,Exception)as error:failures.append(dict(geometry_sha256=record['geometry_sha256'],error_type=type(error).__name__))
    indexed={Path(entry['path'])for entry in index['packets']}
    unindexed=[dict(path=str(path),sha256=digest(path),verified=False)
        for path in sorted(Path('raw-wall').glob('packet-*.npz'))if path not in indexed]
    return dict(completed_stages=completed,pending_packets=sum(r['status']!='completed'for r in index['packets']),
        complete_path=32 in completed,complete_plan=48 in completed,last_completed_packet=last,
        square_best_sha256=digest('final-square-best.npz')if best is not None else None,
        candidate_count=len(candidates),certified_candidates=certified,certification_failures=failures,
        certified_improvements=sum(r['actual_improvement']for r in certified),
        certification_attempts=attempted,remaining_uncertified=len(candidates)-attempted,unindexed_raw_packets=unindexed,
        certification_seconds=time.monotonic()-began,raw_index_sha256=digest('raw-index.json')if Path('raw-index.json').exists()else None)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--search-child',action='store_true')
    parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.search_child:return search(args.deadline)
    started=time.monotonic();controls=preflight();assert controls['seconds']<80
    deadline=time.monotonic()+180
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--search-child','--deadline',str(deadline)])
    forced=False
    try:child.wait(timeout=max(.01,deadline-time.monotonic()))
    except subprocess.TimeoutExpired:forced=True;child.kill();child.wait(timeout=2)
    recovery=recover_and_certify()
    summary=dict(controls_passed=True,seconds=time.monotonic()-started,search_child_returncode=child.returncode,
        hard_search_deadline_enforced=forced,search_limit_seconds=180,recovery=recovery,
        no_mh=True,no_unit_shape_change=True,no_submission=True)
    atom_json('pilot-summary.json',summary);print(json.dumps(summary),flush=True)
    if not forced and child.returncode:raise SystemExit(child.returncode)


if __name__=='__main__':main()
