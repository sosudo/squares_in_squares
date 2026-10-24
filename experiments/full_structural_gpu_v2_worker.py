"""Full-N search with exact raw retention and a separate bounded CPU drain."""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import io
import json
from pathlib import Path
import time
import zipfile
import numpy as np
from compose_gadgets import side,legalize
from fq_active_pilot import digest
from fq_coherent_clusters import atom_json,atom_npz,Deadline
from full_structural_gpu_moves import coherent_start,geometry_sha
from full_structural_gpu_schedule import BalancedSeedScheduler
from full_structural_gpu_worker import bounded_certificate


def write_bundle(path,arrays,metadata):
    """One atomic NPZ binds stage bytes and provenance even after interruption."""
    meta=dict(metadata,array_sha256={k:geometry_sha(v)for k,v in arrays.items()})
    payload=dict(arrays,metadata_json=np.frombuffer(json.dumps(meta,allow_nan=False).encode(),dtype=np.uint8))
    temporary=path.with_suffix('.incoming')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1)as archive:
        for name,value in payload.items():
            stream=io.BytesIO();np.save(stream,value,allow_pickle=False);archive.writestr(name+'.npy',stream.getvalue())
    temporary.replace(path)


def read_bundle(path):
    with np.load(path,allow_pickle=False)as archive:
        metadata=json.loads(archive['metadata_json'].tobytes())
        arrays={k:archive[k]for k in archive.files if k!='metadata_json'}
    assert set(arrays)==set(metadata['array_sha256'])
    for name,p in arrays.items():
        assert p.dtype==np.float64 and p.ndim in(2,3)and p.shape[-1]==3
        assert geometry_sha(p)==metadata['array_sha256'][name]
    return arrays,metadata


def finite_values(values):
    return [float(value)if np.isfinite(value)else None for value in values]


def verify_pending_record(record,pose,folder,cache=None,require_packet_hash=True):
    """Bind a saved candidate to its exact raw input/stage, without regeneration."""
    n=int(record['n']);assert pose.dtype==np.float64 and pose.shape==(n,3)and np.isfinite(pose).all()
    assert geometry_sha(pose)==record['geometry_sha256']
    path=Path(record['raw_batch']).resolve();assert path.is_relative_to((Path(folder)/'raw').resolve())
    cache={}if cache is None else cache
    if path not in cache:
        arrays,metadata=read_bundle(path);cache[path]=(digest(path),arrays,metadata)
    packet_sha,arrays,metadata=cache[path]
    if require_packet_hash:assert record['raw_bundle_sha256']==packet_sha
    assert metadata['validated']is False and int(metadata['n'])==n
    i=int(record['replica']);raw=arrays[record['stage']][i];actual_input=arrays['input'][i]
    assert raw.shape==actual_input.shape==(n,3)and np.isfinite(raw).all()
    assert geometry_sha(raw)==record['raw_geometry_sha256']
    assert metadata['rows'][i]==record['row']
    input_sha=geometry_sha(actual_input)
    assert input_sha==record['row']['mutation']['input_geometry_sha256']
    if 'raw_input_geometry_sha256'in record:assert record['raw_input_geometry_sha256']==input_sha
    return dict(raw_bundle_sha256=packet_sha,raw_input_geometry_sha256=input_sha)


def verify_certificate_count(certificate,n):
    if certificate['valid']:
        assert int(certificate['independent_raw']['n'])==n
        assert int(certificate['independent_roundtrip']['n'])==n


def source_inventory(config):
    assert digest(Path('prepared_references.npz'))==config['references_sha256']
    assert digest(Path('prepared_variants.npz'))==config['variants_sha256']
    with np.load('prepared_references.npz',allow_pickle=False)as z:references={int(k):z[k]for k in z.files}
    with np.load('prepared_variants.npz',allow_pickle=False)as z:variants={k:z[k]for k in z.files}
    order={int(n):names for n,names in config['source_order'].items()}
    assert set(order)==set(references)
    flat=[name for names in order.values()for name in names]
    assert len(flat)==len(set(flat))==len(variants)and set(flat)==set(variants)
    for n,names in order.items():
        assert names and all(len(variants[name])==n for name in names)
    return references,variants,order


def prepare_batch(config,references,variants,scheduler,rng,n,batch):
    rows=[];inputs=[];loose=[];targets=[]
    for b in range(config['replicas']):
        choice=scheduler.next(n);name=choice['source_id']
        source=references[n]if choice['is_reference']else variants[name]
        seed=int(rng.integers(2**31));q,mutation=coherent_start(source,seed,choice['mode'],choice['amplitude'])
        rows.append(dict(choice,mutation=mutation,replica=b,batch=batch,
                         source_archive_sha256=config['references_sha256']if choice['is_reference']else config['variants_sha256']))
        inputs.append(q);loose.append([side(source)+choice['loose_slack']]*2)
        targets.append([config['reference_sides'][str(n)]-choice['target_depth']]*2)
    return np.array(inputs),rows,np.array(loose),np.array(targets)


def search(device):
    import cupy as cp
    import gpu_rect_optimizer as gpu
    from full_structural_gpu_ties import patch_cuda,check_cuda
    from full_structural_gpu_v2_preflight import preflight
    config=json.loads(Path('prepared_config.json').read_text());cp.cuda.Device(device).use()
    legalization_source_sha256=digest(Path(legalize.__code__.co_filename))
    folder=Path(f'artifacts/full_structural_v2_device{device}');folder.mkdir();(folder/'raw').mkdir()
    references,variants,order=source_inventory(config)
    patched,audit=patch_cuda(gpu.src);gpu.src=patched
    cuda_options=tuple(config['cuda_options'])
    assert cuda_options==('--std=c++17','--fmad=false')
    gpu.mod=cp.RawModule(code=patched,options=cuda_options,name_expressions=['eval','lbfgs'])
    audit['compiler_options']=list(cuda_options)
    atom_json(folder/'gradient_patch.json',audit)
    atom_json(folder/'gradient_controls.json',dict(check_cuda(gpu),compiler_options=list(cuda_options)))
    pool={n:[(name,variants[name])for name in names]for n,names in order.items()}
    preflight(cp,gpu,references,pool,device,folder)
    waited=time.monotonic()
    while not Path('preflight-approved-v2.json').exists():
        if time.monotonic()-waited>180:raise TimeoutError('Both-device preflight barrier expired')
        time.sleep(.5)
    started=time.monotonic();deadline=started+config['search_seconds'];scheduler=BalancedSeedScheduler(order)
    rng=np.random.default_rng(config['paired_seed']);arm='exact'if device==0 else'smooth'
    stats=dict(planned=0,dispatched=0,first_stage_completed=0,final_stage_completed=0,batches=0,
               cuda_seconds=0.,quench_wall_seconds=0.,fresh_evaluation_transfer_seconds=0.,
               io_seconds=0.,raw_bytes=0,nonfinite_rows=0,nonfinite_metric_rows=0,
               selection_finite_pose_occurrences=0,selection_legalized_occurrences=0,
               selection_legalization_failures=0,selection_prospective_winner_occurrences=0,
               selection_topk_dropped_occurrences=0,selection_prospective_winners_dropped_occurrences=0)
    stage_totals={};pending={};source_visits={};completed_visits={};batch=0;throughput_passed=False

    def status(phase):
        value=dict(phase=phase,arm=arm,device=device,seconds=time.monotonic()-started,stats=stats,
                   stage_totals=stage_totals,dispatched_source_visits=source_visits,
                   first_stage_completed_source_visits=completed_visits,schedule=scheduler.snapshot(),
                   throughput_control_passed=throughput_passed)
        atom_json(folder/'status.json',value);return value

    def preserve_pending():
        # A packet is extended during its batch. Pin its final committed bytes
        # only here, after the final stage write, never at an early stage.
        cache={}
        for item in pending.values():
            if 'raw_bundle_sha256'not in item:
                item.update(verify_pending_record(item,item['pose'],folder,cache,require_packet_hash=False))
        arrays={sha:item['pose']for sha,item in pending.items()}
        records={sha:{k:v for k,v in item.items()if k!='pose'}for sha,item in pending.items()}
        write_bundle(folder/'pending.npz',arrays,dict(validated=False,records=records,
            selection_policy='At most16 prospective winners plus4 angle-diverse representatives per family; all other poses remain raw/unverified.',
            selection_stats={k:v for k,v in stats.items()if k.startswith('selection_')},
            selection_is_bounded=True))

    status('search');preserve_pending()
    while time.monotonic()<deadline-15 and stats['raw_bytes']<config['raw_byte_limit']-16*1024**2:
        n=config['family_cycle'][batch%len(config['family_cycle'])];B=config['replicas']
        inputs,rows,loose,targets=prepare_batch(config,references,variants,scheduler,rng,n,batch)
        path=folder/'raw'/f'batch-{batch:06d}.npz';arrays={'input':inputs}
        meta=dict(validated=False,n=n,batch=batch,arm=arm,rows=rows,stages=[],dispatch_state='planned')
        stats['planned']+=B;at=time.monotonic();write_bundle(path,arrays,meta);stats['io_seconds']+=time.monotonic()-at
        stats['raw_bytes']+=path.stat().st_size
        if time.monotonic()>deadline-12:break
        q=cp.asarray(inputs,dtype=cp.float64)
        stages=[(.02,loose,'loose0'),(.005,loose,'loose1')]if arm=='smooth'else[(0.,loose,'loose0'),(0.,loose,'loose1')]
        stages += [(0.,targets,f'target{i}')for i in range(3)]
        completed=0
        for stage_index,(tau,boxes,label)in enumerate(stages):
            if time.monotonic()>deadline-5:break
            if stage_index==0:
                meta['dispatch_state']='dispatched';stats['dispatched']+=B
                for row in rows:
                    key=f"{n}/{row['source_id']}/{row['mode']}/{row['amplitude']}/{row['target_depth']}/{row['loose_slack']}"
                    source_visits[key]=source_visits.get(key,0)+1
                old_size=path.stat().st_size;at=time.monotonic();write_bundle(path,arrays,meta)
                stats['io_seconds']+=time.monotonic()-at;stats['raw_bytes']+=path.stat().st_size-old_size
                status('search')
            at=time.monotonic();q,native=gpu.quench(q,boxes,steps=400,tau=tau)
            cp.cuda.get_current_stream().synchronize();quench_seconds=time.monotonic()-at
            evaluation_started=time.monotonic()
            exact,gradient=gpu.energy(q,boxes,tau=0);host=cp.asnumpy(q);native=cp.asnumpy(native)
            stats['cuda_seconds']+=time.monotonic()-at;stats['quench_wall_seconds']+=quench_seconds
            stats['fresh_evaluation_transfer_seconds']+=time.monotonic()-evaluation_started
            assert host.shape==(B,n,3)and native.shape==(B,3)and exact.shape==(B,2)
            finite=np.isfinite(host).all(axis=(1,2));metric_finite=np.isfinite(exact).all(1)
            stats['nonfinite_rows']+=int((~finite).sum());stats['nonfinite_metric_rows']+=int((~metric_finite).sum())
            sides=np.array([side(p)if ok else np.nan for p,ok in zip(host,finite)])
            residual_passes=finite&metric_finite&(exact[:,1]<1e-7)
            wall=np.full(B,np.nan)
            for i in np.flatnonzero(finite):
                half=.5*(abs(np.cos(host[i,:,2]))+abs(np.sin(host[i,:,2])))
                wall[i]=max(0.,float(np.max(np.r_[half-host[i,:,0],half-host[i,:,1],
                    host[i,:,0]+half-boxes[i,0],host[i,:,1]+half-boxes[i,1]])))
            gradient_norm=np.linalg.norm(gradient.reshape(B,-1),axis=1)
            metrics=dict(label=label,tau=tau,steps=400,box_sides=boxes[:,0].tolist(),finite_count=int(finite.sum()),
                         finite_metric_count=int(metric_finite.sum()),
                         exact_energy_residual_passes=int(residual_passes.sum()),
                         below_current_float_count=int(np.sum(finite&(sides<config['reference_sides'][str(n)]))),
                         below_box_float_count=int(np.sum(finite&(sides<=boxes[:,0]))),
                         exact_residuals=finite_values(exact[:,1]),exact_energies=finite_values(exact[:,0]),
                         fresh_gradient_norms=finite_values(gradient_norm),fresh_wall_residuals=finite_values(wall),
                         native_reported_energies=finite_values(native[:,0]),native_reported_residuals=finite_values(native[:,1]),
                         native_iterations=finite_values(native[:,2]),native_stop_reason='unknown_public_kernel',
                         native_residual_warning='May refer to a rejected line-search trial; fresh returned-q metrics above are authoritative.',
                         floating_sides=finite_values(sides),
                         stage_box_slacks=finite_values(boxes[:,0]-sides),
                         frozen_reference_slacks=finite_values(config['reference_sides'][str(n)]-sides),
                         quench_wall_seconds=quench_seconds,
                         fresh_evaluation_transfer_seconds=time.monotonic()-evaluation_started)
            arrays[label]=host;meta['stages'].append(metrics);completed+=1
            meta['dispatch_state']='complete'if completed==len(stages)else'partial'
            previous_size=path.stat().st_size;at=time.monotonic();write_bundle(path,arrays,meta)
            stats['io_seconds']+=time.monotonic()-at;stats['raw_bytes']+=path.stat().st_size-previous_size
            if stage_index==0:
                stats['first_stage_completed']+=B
                for row in rows:
                    key=f"{n}/{row['source_id']}/{row['mode']}/{row['amplitude']}/{row['target_depth']}/{row['loose_slack']}"
                    completed_visits[key]=completed_visits.get(key,0)+1
            if completed==len(stages):stats['final_stage_completed']+=B
            key=f'{n}/{label}';totals=stage_totals.setdefault(key,dict(poses=0,finite=0,exact_energy_residual_passes=0,below_current_float=0))
            for field,value in [('poses',B),('finite',finite.sum()),('exact_energy_residual_passes',residual_passes.sum()),
                                ('below_current_float',metrics['below_current_float_count'])]:totals[field]+=int(value)
            # This screening is NOT certification. Every raw finite stage stays
            # in the batch archive even when it is not selected for CPU drain.
            for i in np.flatnonzero(finite):
                stats['selection_finite_pose_occurrences']+=1
                p=legalize(host[i],clearance=2e-9)
                if p is None:
                    stats['selection_legalization_failures']+=1;continue
                stats['selection_legalized_occurrences']+=1
                length=side(p);sha=geometry_sha(p);gain=config['reference_sides'][str(n)]-length
                if gain>1e-9:stats['selection_prospective_winner_occurrences']+=1
                if gain<=1e-9 and length>config['reference_sides'][str(n)]+.1:continue
                record=dict(pose=p,n=n,side=length,gain=gain,geometry_sha256=sha,validated=False,
                            raw_batch=str(path),stage=label,replica=int(i),raw_geometry_sha256=geometry_sha(host[i]),
                            row=rows[i],exact_residual=float(exact[i,1])if np.isfinite(exact[i,1])else None,
                            legalization={'helper':'compose_gadgets.legalize','clearance':2e-9,
                                'helper_file_sha256':legalization_source_sha256})
                pending.setdefault(sha,record)
            # At most16 best prospective winners +4 distinct angle-histogram
            # representatives per family; all other geometry remains in raw.
            selected={}
            for family in order:
                candidates=sorted(((s,r)for s,r in pending.items()if r['n']==family),key=lambda item:(item[1]['side'],item[0]))
                selected.update([(s,r)for s,r in candidates if r['gain']>1e-9][:16])
                signatures=set()
                for sha,r in candidates:
                    folded=(r['pose'][:,2]+np.pi/4)%(np.pi/2)-np.pi/4
                    signature=tuple(np.histogram(folded,bins=np.linspace(-np.pi/4,np.pi/4,9))[0])
                    if signature in signatures:continue
                    signatures.add(signature);selected[sha]=r
                    if len(signatures)>=4:break
            stats['selection_topk_dropped_occurrences']+=len(set(pending)-set(selected))
            stats['selection_prospective_winners_dropped_occurrences']+=sum(
                r['gain']>1e-9 for sha,r in pending.items()if sha not in selected)
            pending=selected
            if not finite.all():break
        at=time.monotonic();preserve_pending();stats['io_seconds']+=time.monotonic()-at
        batch+=1;stats['batches']=batch
        if batch==3:
            duty=stats['cuda_seconds']/max(1e-9,time.monotonic()-started)
            throughput_passed=duty>=.25
            atom_json(folder/'throughput_control.json',dict(passed=throughput_passed,cuda_fraction=duty,stats=stats.copy()))
            if not throughput_passed:status('throughput-control-failed');raise RuntimeError('CUDA duty-cycle control failed')
        status('search')
        if batch%5==0:print(json.dumps(dict(stage='search',device=device,batches=batch,seconds=time.monotonic()-started,stats=stats)),flush=True)
    status('search-complete')


def certify(device):
    config=json.loads(Path('prepared_config.json').read_text());folder=Path(f'artifacts/full_structural_v2_device{device}')
    (folder/'certified_entries').mkdir(exist_ok=False);started=time.monotonic();deadline=started+config['certification_seconds']
    arrays,metadata=read_bundle(folder/'pending.npz');records=[];poses={};cache={}
    pending=sorted(metadata['records'].items(),key=lambda item:(item[1]['gain']<=1e-9,-item[1]['gain'],item[0]))
    for sha,record in pending:
        if time.monotonic()>deadline-9:break
        p=arrays[sha];assert geometry_sha(p)==sha==record['geometry_sha256']
        verify_pending_record(record,p,folder,cache)
        try:certificate=bounded_certificate(p)
        except Deadline:certificate={'valid':False,'status':'timeout'}
        verify_certificate_count(certificate,int(record['n']))
        result=dict(record,certificate=certificate,screening_side=record['side'],screening_gain=record['gain'])
        if certificate['valid']:
            result['side']=float(certificate['independent_raw']['side_upper'])
            result['gain']=config['reference_sides'][str(record['n'])]-result['side']
            result['validated']=True;poses[sha]=p
            atom_npz(folder/'certified_entries'/f'{sha}.npz',{'pose':p})
            result['pose_npz_sha256']=digest(folder/'certified_entries'/f'{sha}.npz')
            atom_json(folder/'certified_entries'/f'{sha}.json',result)
        records.append(result)
    atom_npz(folder/'certified.npz',poses);atom_json(folder/'certificates.json',records)
    atom_json(folder/'certification-summary.json',dict(attempted=len(records),certified=len(poses),
        selected_pending=len(pending),remaining_selected_unverified=len(pending)-len(records),
        selected_drain_complete=len(records)==len(pending),all_raw_candidates_exhausted=False,
        selection_is_bounded=metadata.get('selection_is_bounded',True),selection_stats=metadata.get('selection_stats',{}),
        timed_out=sum(r['certificate'].get('status')=='timeout'for r in records),
        seconds=time.monotonic()-started,archive_sha256=digest(folder/'certified.npz'),
        records_sha256=digest(folder/'certificates.json')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--device',type=int,required=True)
    parser.add_argument('--mode',choices=['search','certify'],default='search');args=parser.parse_args()
    (search if args.mode=='search'else certify)(args.device)
