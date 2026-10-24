"""One bounded GPU diagnostic; no search, native finishing or score admission.

The external notebook supervisor owns the only process group and hard timeout.
Completed control/stage arrays are durable before any subsequent GPU stage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

ARMS = {'A':[('fp64',2000)],'B':[('fp32',1500),('fp64',500)],'C':[('fp64',1500),('fp64',500)]}
ORDERS = ('ABC','BCA','CAB')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    import math
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if hasattr(value,'tolist'):return clean(value.tolist())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def atomic_json(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(clean(value),indent=2,allow_nan=False)+'\n');temporary.replace(path)


class Retention:
    def __init__(self,root):
        self.root=root;self.root.mkdir();self.records=[];self.bytes=0

    def save(self,label,arrays,metadata):
        import numpy as np
        label=re.sub(r'[^A-Za-z0-9_.-]','_',label)
        path=self.root/f'{len(self.records):03d}-{label}.npz';temporary=path.with_suffix('.npz.tmp')
        total=sum(np.asarray(v).nbytes for v in arrays.values())
        if self.bytes+total+65536>512*1024**2:raise ValueError('finite_retention_bound_exceeded')
        with temporary.open('wb') as stream:np.savez(stream,**arrays)
        temporary.replace(path);path.chmod(0o444);self.bytes+=path.stat().st_size
        record=dict(path=str(path),sha256=digest(path),bytes=path.stat().st_size,metadata=metadata,
            arrays={k:dict(shape=list(v.shape),dtype=v.dtype.str,sha256=hashlib.sha256(v.tobytes()).hexdigest()) for k,v in arrays.items()})
        self.records.append(record);atomic_json(self.root.parent/'array-index.json',self.records)
        return record


def load_fixtures(config,base):
    import numpy as np
    path=Path(config['inputs_path']);path=path if path.is_absolute() else base/path
    assert digest(path)==config['inputs_sha256']
    fixtures=[]
    with np.load(path,allow_pickle=False) as archive:
        for row in config['batches']:
            p=archive[row['pose_key']].copy();sides=archive[row['boxes_key']].copy();n=row['n']
            assert p.dtype==sides.dtype==np.dtype('float64') and p.shape==(32,n,3) and sides.shape==(32,)
            assert n in (803,861) and row['epoch'] in ('early','late')
            assert np.isfinite(p).all() and np.isfinite(sides).all() and (sides>0).all()
            assert hashlib.sha256(p.tobytes()).hexdigest()==row['pose_sha256']
            assert hashlib.sha256(sides.tobytes()).hexdigest()==row['boxes_sha256']
            boxes=np.column_stack((sides,sides))
            expanded_sha=hashlib.sha256(boxes.tobytes()).hexdigest()
            p.flags.writeable=False;sides.flags.writeable=False;boxes.flags.writeable=False
            fixtures.append(dict(row,poses=p,boxes=boxes,original_sides=sides,expanded_boxes_sha256=expanded_sha))
    assert len(fixtures)==4 and {(r['n'],r['epoch']) for r in fixtures}=={(803,'early'),(803,'late'),(861,'early'),(861,'late')}
    assert len({r['key'] for r in fixtures})==4
    return fixtures,path


def run(config_path,out,deadline,parent_started):
    import numpy as np
    import cupy as cp
    import torch
    from fq_mixed_precision_adapter import Solver,FP64_SHA,OPTIONS
    from fq_mixed_precision_controls import run as controls,run_fp64,physical_metrics
    out.mkdir(parents=True,exist_ok=False);config=json.loads(config_path.read_text());base=config_path.parent
    assert 0<config['work_seconds']<=240 and deadline-parent_started<=280.001
    assert config['protocol']['arms']=={k:[list(v) for v in values] for k,values in ARMS.items()}
    assert config['protocol']['repeats']==3 and config['protocol']['order']=='ABC/BCA/CAB'
    assert config['protocol']['phase2_fresh_optimizer_state'] and config['protocol']['original_fp64_boxes_in_phase2']
    assert config['compiler_options']==list(OPTIONS) and config['native_finish'] is False and config['search_campaign'] is False
    fixtures,fixture_path=load_fixtures(config,base)
    source_path=Path(config['corrected_fp64_cuda_path']);source_path=source_path if source_path.is_absolute() else base/source_path
    assert digest(source_path)==config['corrected_fp64_cuda_sha256']==FP64_SHA
    source=source_path.read_text();store=Retention(out/'arrays')
    initial_hashes={r['key']:(r['pose_sha256'],r['expanded_boxes_sha256']) for r in fixtures}
    for row in fixtures:store.save('fixture-'+row['key'],dict(poses=row['poses'],expanded_boxes=row['boxes'],original_sides=row['original_sides']),
        dict(source_packet=row['source_packet'],original_sides_sha256=row['boxes_sha256'],expanded_boxes_sha256=row['expanded_boxes_sha256'],verified=False))
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.cuda.set_device(0);cp.cuda.Device(0).use()
    assert torch.cuda.is_available() and 'T4'in torch.cuda.get_device_name(0)
    fp64=Solver(cp,source,'fp64');solvers={'fp64':fp64};fp32_passed=False;fp32_failure=None
    (out/'corrected-fp64.cu').write_text(fp64.source)
    manifest=dict(config_sha256=digest(config_path),inputs_sha256=digest(fixture_path),parent_started_monotonic=parent_started,
        deadline_monotonic=deadline,schedule_deadline_monotonic=min(parent_started+config['work_seconds'],deadline-10),
        fp64_audit=fp64.audit,fp32_audit=None,buffer_inventory={p:s.buffer_inventory() for p,s in solvers.items()},
        runtime_priority=config['runtime_priority'],no_score_claim=True,no_native_finish=True,no_current_or_best_update=True)
    atomic_json(out/'manifest.json',manifest)
    # Force compilation outside all timing measurements.
    for solver in solvers.values():
        solver.module.get_function('eval');solver.module.get_function('lbfgs')
    fp64_passed=run_fp64(cp,torch,fp64,fixtures,store.save);atomic_json(out/'fp64-preflight.json',fp64_passed)
    schedule_deadline=manifest['schedule_deadline_monotonic'];pipeline_records=[];occupancy_records=[];omitted=[]

    def measure(solver,poses,boxes,steps):
        cp.cuda.get_current_stream().synchronize();torch.cuda.synchronize()
        begin_event=cp.cuda.Event();end_event=cp.cuda.Event();start=time.perf_counter();begin_event.record()
        q,native=solver.quench(poses,boxes,steps)
        end_event.record();end_event.synchronize();cp.cuda.get_current_stream().synchronize()
        elapsed=time.perf_counter()-start
        return q,native,dict(wall_seconds_conversion_allocation_launch_sync=elapsed,cuda_event_seconds=float(cp.cuda.get_elapsed_time(begin_event,end_event))/1000,
            precision=solver.precision,steps=steps,memory_pool_used_bytes=int(cp.get_default_memory_pool().used_bytes()),
            memory_pool_total_bytes=int(cp.get_default_memory_pool().total_bytes()),cuda_free_total_bytes=list(cp.cuda.runtime.memGetInfo()))

    def timed_physical(poses,boxes):
        torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();begin=time.perf_counter()
        values=physical_metrics(torch,poses,boxes)
        timing=dict(wall_seconds=time.perf_counter()-begin,
            torch_peak_allocated_bytes=int(torch.cuda.max_memory_allocated()),
            torch_peak_reserved_bytes=int(torch.cuda.max_memory_reserved()))
        return values,timing

    def checkpoint(status):
        atomic_json(out/'benchmark-report.json',dict(status=status,controls_passed=fp32_passed,fp64_controls_passed=True,
            fp32_controls_passed=fp32_passed,fp32_failure=fp32_failure,parent_elapsed_seconds=time.monotonic()-parent_started,
            planned_primary_pipelines=36,completed_primary_pipelines=len(pipeline_records),primary=pipeline_records,occupancy=occupancy_records,
            omitted=omitted,manifest_sha256=digest(out/'manifest.json'),array_index_sha256=digest(out/'array-index.json'),
            retention_bytes=store.bytes,no_score_claim=True,no_native_finish=True,no_search=True))

    # Predeclared occupancy prefix. Every replicated row is labelled explicitly.
    occupancy=config['occupancy'];assert occupancy['enabled'] and occupancy['steps']==2000 and occupancy['batch_sizes']==[32,64,128]
    chosen=next(r for r in fixtures if r['key']==occupancy['fixture_key']);baseline=None;baseline_initial=None
    for B in occupancy['batch_sizes']:
        if time.monotonic()>=schedule_deadline-10:
            omitted.append(dict(kind='occupancy',batch=B,reason='fixed_schedule_deadline'));continue
        copies=B//32;poses=np.tile(chosen['poses'],(copies,1,1));boxes=np.tile(chosen['boxes'],(copies,1));parent_rows=np.tile(np.arange(32),copies)
        copy_ids=np.repeat(np.arange(copies),32);assert all(np.array_equal(poses[k],chosen['poses'][parent_rows[k]]) for k in range(B))
        initial,gradient=fp64.energy(poses,boxes)
        if baseline_initial is None:baseline_initial=(initial.copy(),gradient.copy())
        else:
            assert abs(initial-baseline_initial[0][parent_rows]).max()<1e-9*max(1.,float(abs(initial).max()))
            assert abs(gradient-baseline_initial[1][parent_rows]).max()<1e-8*max(1.,float(abs(gradient).max()))
        q,native,timing=measure(fp64,poses,boxes,2000);host=cp.asnumpy(q);stats=cp.asnumpy(native)
        retained=store.save('occupancy-B'+str(B),dict(input=poses,boxes=boxes,output=host,native=stats,parent_row=parent_rows,copy_index=copy_ids),dict(verified=False,exact_duplicate_inputs=True,fixture=chosen['key']))
        physical,physical_timing=timed_physical(q,boxes)
        if baseline is None:baseline=(host.copy(),physical['energy'].copy())
        differences=dict(coordinate_max=float(abs(host-baseline[0][parent_rows]).max()),physical_energy=(physical['energy']-baseline[1][parent_rows]).tolist(),
            worse_rows=int(np.count_nonzero(physical['energy']>baseline[1][parent_rows]+1e-12+1e-8*abs(baseline[1][parent_rows]))))
        occupancy_records.append(dict(batch=B,fixture=chosen['key'],timing=timing,poses_per_second=B/timing['wall_seconds_conversion_allocation_launch_sync'],
            dense_fp64_physical_evaluation=physical_timing,
            solver_plus_physical_seconds=timing['wall_seconds_conversion_allocation_launch_sync']+physical_timing['wall_seconds'],
            source_duplicate_labels='parent_row+copy_index; no additional geometric diversity',endpoint_differences_vs_B32=differences,
            physical_energy=physical['energy'].tolist(),retained=retained,output_determinism_not_assumed=True));checkpoint('running')

    # FP32 is an independently gated diagnostic arm. Its failure cannot erase
    # already valid FP64 occupancy evidence or enable unreviewed float search.
    if time.monotonic()<schedule_deadline-20:
        try:
            fp32=Solver(cp,source,'fp32');fp32.module.get_function('eval');fp32.module.get_function('lbfgs');fp32.module.get_function('lbfgs_observed')
            (out/'ported-fp32.cu').write_text(fp32.source);(out/'fp32-observational-compiled.cu').write_text(fp32.compiled_source)
            fp32_report=controls(cp,torch,fp64,fp32,fixtures,store.save,fp64_report=fp64_passed)
            atomic_json(out/'fp32-preflight.json',fp32_report);fp32_passed=True;solvers['fp32']=fp32
            manifest['fp32_audit']=fp32.audit;manifest['buffer_inventory']['fp32']=fp32.buffer_inventory()
        except Exception as error:
            fp32_failure=dict(error_type=type(error).__name__,message=str(error),mixed_arm_disabled=True)
            atomic_json(out/'fp32-failure.json',fp32_failure)
    else:
        fp32_failure=dict(reason='fixed_schedule_deadline_before_fp32_controls',mixed_arm_disabled=True)
    atomic_json(out/'manifest.json',manifest);checkpoint('running')
    if not fp32_passed:
        # A failed CUDA call may poison its context. All independent FP64
        # occupancy/control results are already durable host records; perform
        # no further GPU calls after any FP32 failure or budget omission.
        for repeat,order in enumerate(ORDERS):
            for fixture in fixtures:
                for arm in order:
                    omitted.append(dict(kind='primary',repeat=repeat,fixture=fixture['key'],arm=arm,reason='fp32_controls_not_passed_no_further_cuda'))
        assert digest(fixture_path)==config['inputs_sha256']
        checkpoint('fp32_not_passed_fp64_occupancy_preserved')
        return

    # Fixed rotations prevent a chosen arm always benefiting from warm allocation.
    for repeat,order in enumerate(ORDERS):
        for fixture in fixtures:
            for arm in order:
                label=f"r{repeat}-{fixture['key']}-{arm}"
                if arm=='B' and not fp32_passed:
                    omitted.append(dict(kind='primary',repeat=repeat,fixture=fixture['key'],arm=arm,reason='fp32_controls_not_passed'));continue
                if time.monotonic()>=schedule_deadline-10:
                    omitted.append(dict(kind='primary',repeat=repeat,fixture=fixture['key'],arm=arm,reason='fixed_schedule_deadline'));continue
                current=fixture['poses'];original_boxes=fixture['boxes'];phases=[];stage_records=[];wall_begin=time.perf_counter();valid=True
                for phase,(precision,steps) in enumerate(ARMS[arm]):
                    if phase and time.monotonic()>=deadline-5:
                        valid=False;omitted.append(dict(kind='return_phase',label=label,reason='absolute_deadline'));break
                    # A fresh Solver.quench allocates every history/grid/work array.
                    before_host=current if isinstance(current,np.ndarray) else cp.asnumpy(current)
                    represented_before=before_host.astype(np.float64 if precision=='fp64' else np.float32)
                    q,native,timing=measure(solvers[precision],current,original_boxes,steps)
                    host=cp.asnumpy(q);stats=cp.asnumpy(native)
                    timing['endpoint_unchanged_rows_after_dtype_rounding']=int(np.all(host==represented_before,axis=(1,2)).sum())
                    timing['last_iteration_indices']=stats[:,2].tolist()
                    timing['native_residual_is_not_fresh_endpoint_energy']=True
                    timing['maximum_box_rounding_error']=float(abs(original_boxes-original_boxes.astype(np.float32).astype(np.float64)).max()) if precision=='fp32' else 0.
                    metadata=dict(verified=False,repeat=repeat,fixture=fixture['key'],arm=arm,phase=phase,precision=precision,steps=steps,
                        original_sides_vector_sha256=fixture['boxes_sha256'],expanded_original_fp64_boxes_sha256=fixture['expanded_boxes_sha256'],fresh_optimizer_state=True,
                        native_report_may_contain_last_rejected_trial_residual=True)
                    stage_records.append(store.save(label+'-phase'+str(phase),dict(poses=host,native=stats,original_fp64_boxes=original_boxes,
                        represented_explorer_boxes=original_boxes.astype(np.float32) if precision=='fp32' else original_boxes),metadata))
                    phases.append(timing)
                    if not np.isfinite(host).all():valid=False;break
                    current=q
                if valid:
                    assert current.dtype==cp.float64,'completed_endpoint_must_be_FP64'
                    physical,physical_timing=timed_physical(current,original_boxes)
                    energy=physical['energy'].tolist()
                else:energy=None;physical_timing=None
                assert hashlib.sha256(fixture['poses'].tobytes()).hexdigest()==initial_hashes[fixture['key']][0]
                assert hashlib.sha256(original_boxes.tobytes()).hexdigest()==initial_hashes[fixture['key']][1]
                pipeline_records.append(dict(repeat=repeat,fixture=fixture['key'],arm=arm,status='completed' if valid else 'partial_or_nonfinite',
                    phases=phases,compute_wall_sum_excludes_retention_io=sum(p['wall_seconds_conversion_allocation_launch_sync'] for p in phases),
                    cuda_event_seconds_sum=sum(p['cuda_event_seconds'] for p in phases),
                    wall_including_retention_and_physical_evaluation=time.perf_counter()-wall_begin,
                    dense_fp64_physical_evaluation=physical_timing,
                    fp64_physical_energy_on_original_boxes=energy,stages=stage_records,original_fixture_arrays_unchanged=True,
                    precision_return='Original FP64 boxes and fresh unchanged FP64 optimizer; no feasibility or score claim.'))
                checkpoint('running')
    assert digest(fixture_path)==config['inputs_sha256']
    checkpoint('complete' if not omitted else 'deadline_partial')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--deadline',type=float);parser.add_argument('--parent-started',type=float);args=parser.parse_args()
    began=time.monotonic();parent=began if args.parent_started is None else args.parent_started;deadline=parent+280 if args.deadline is None else args.deadline
    try:run(args.config.resolve(),args.out.resolve(),deadline,parent)
    except Exception as error:
        args.out.mkdir(parents=True,exist_ok=True)
        atomic_json(args.out/'failure.json',dict(error_type=type(error).__name__,message=str(error),parent_elapsed_seconds=time.monotonic()-parent,no_score_claim=True))
        raise


if __name__=='__main__':main()
