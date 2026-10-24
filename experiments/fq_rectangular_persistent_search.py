"""Complete-unit rectangular hopping policy and sampled, atomic state retention.

The corrected public FP64 quench is imported unchanged. The physical oracle
extends our existing unit-only all-pair formula to separate W/H walls.
Unverified search states are never packing certificates.
"""
from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import torch
from fq_torch_hop import acceptance,mutate
from fq_torch_hop_pilot import atom_json,json_finite,digest
from fq_coherent_clusters import atom_npz
import fq_fused_hop_pilot as fused

FAMILIES=('5_17_7','7_19_13','7_20_14','8_21_13')
CUTS=(.002,.01,.03,.06)
BATCH=64
SEED=217240001
STATE_KEYS=('current_after','best_after','boxes','next_energy','best_energy_after')
RAW_LIMIT=1024**3
PROTECTED_LIMIT=512*1024**2
SCALAR_LIMIT=256*1024**2
SAMPLE_EVERY=32


def array_sha(p):return hashlib.sha256(np.ascontiguousarray(p).tobytes()).hexdigest()

def compact_json(value):return json.dumps(json_finite(value),sort_keys=True,separators=(',',':'),allow_nan=False)


@torch.no_grad()
def physical_energy(poses,boxes):
    if poses.dtype!=torch.float64 or poses.ndim!=3 or poses.shape[-1]!=3:
        raise ValueError('FP64 B,N,3 unit poses required')
    B,N,_=poses.shape
    if boxes.shape!=(B,2)or boxes.dtype!=torch.float64 or not bool(torch.isfinite(poses).all()and torch.isfinite(boxes).all()and(boxes>0).all()):
        raise ValueError('Finite positive independent W/H boxes required')
    x,y,a=poses.unbind(-1);extent=.5*(a.cos().abs()+a.sin().abs())
    wall=torch.stack((extent-x,x+extent-boxes[:,0,None],extent-y,y+extent-boxes[:,1,None]),-1).clamp_min(0.)
    per=wall.square().sum(-1);wall_energy=per.sum(1)
    i,j=torch.triu_indices(N,N,1,device=poses.device)
    dx=x[:,j]-x[:,i];dy=y[:,j]-y[:,i];ai=a[:,i];aj=a[:,j]
    penetration=torch.full_like(dx,torch.inf)
    for owner,other in((ai,aj),(aj,ai)):
        for offset in(0.,np.pi/2):
            phi=owner+offset;relative=phi-other
            radius=.5+.5*(relative.cos().abs()+relative.sin().abs())
            penetration=torch.minimum(penetration,radius-(dx*phi.cos()+dy*phi.sin()).abs())
    penetration=penetration.clamp_min(0.);pair=penetration.square()
    per.scatter_add_(1,i[None].expand(B,-1),.5*pair)
    per.scatter_add_(1,j[None].expand(B,-1),.5*pair)
    return dict(energy=wall_energy+pair.sum(1),per_square=per,wall_energy=wall_energy,pair_energy=pair.sum(1),
        max_wall=wall.amax((1,2)),max_pair=penetration.amax(1))


def host_metrics(poses,boxes):
    return{k:v.detach().cpu().numpy()for k,v in physical_energy(poses,boxes).items()}


def design(config):
    key=config['key'];w,h,d=map(int,key.split('_'))
    if key not in FAMILIES or(w,h,d,config['n'])!=(config['w'],config['h'],config['d'],w*h+d):
        raise ValueError('Exact supported typed family required')
    keys=config['seed_keys']
    if len(keys)!=4 or len(set(keys))!=4:raise ValueError('Four explicitly identified immutable seed entries required')
    f=float(config['reference_f_upper']);rows=[]
    for group,source in enumerate(keys):
        for cut in CUTS:
            target=f-cut
            if(w+target)*(h+target)<w*h+d:raise ValueError('Area-impossible target')
            for stream in range(4):
                rows.append(dict(chain=len(rows),arm='rectangular',family=key,n=w*h+d,source_key=source,seed_group=group,
                    delta=cut,target_f=target,width=w+target,height=h+target,temperature=(.3,.3,1.,1.)[stream],
                    amplitude=(1.,1.5,1.,1.5)[stream],stream=stream,
                    case_seed=SEED+FAMILIES.index(key),seed_recipe='SeedSequence([familyseed,round,chain,41]); acceptance domain2718'))
    assert len(rows)==BATCH
    return rows


def random_stream(seed,round_number,chain):
    return np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),int(chain),41]))


def uniforms(seed,round_number):
    return np.random.default_rng(np.random.SeedSequence([int(seed),int(round_number),2718])).random(BATCH)


def temperatures(base,started,deadline,decision):
    boundary=started+.75*(deadline-started);phase='cool'if decision>=boundary else'initial'
    return np.full(BATCH,.03)if phase=='cool'else np.asarray(base,dtype=float),phase


def quench(proposal,boxes,steps=2000):
    cp,gpu,audit=fused.configure_gpu()
    if proposal.dtype!=torch.float64 or boxes.dtype!=torch.float64 or proposal.shape[0]!=BATCH or boxes.shape!=(BATCH,2):
        raise ValueError('Actual B64 FP64 rectangle interface required')
    if proposal.shape[1]not in(92,146,154,181)or not proposal.is_cuda:raise ValueError('Unexpected complete-unit count')
    at=time.monotonic();torch.cuda.synchronize();q=cp.from_dlpack(proposal.detach()).copy()
    output,report=gpu.quench(q,boxes.detach().cpu().numpy(),steps=int(steps),tau=0.)
    cp.cuda.get_current_stream().synchronize();result=torch.utils.dlpack.from_dlpack(output).clone()
    report=cp.asnumpy(report)
    if result.shape!=proposal.shape or report.shape!=(BATCH,3):raise ValueError('Quench shape changed')
    return result,dict(steps_requested=int(steps),seconds=time.monotonic()-at,compiler_options=list(fused.CUDA_OPTIONS),
        native_report=report.tolist(),native_report_is_not_acceptance_energy=True,quench_completion='Returned batch; no convergence claim')


def _atomic_npz(path,arrays,metadata):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    values={k:np.asarray(v)for k,v in arrays.items()}
    metadata=dict(metadata,array_sha256={k:array_sha(v)for k,v in values.items()})
    values['metadata_json']=np.frombuffer(compact_json(metadata).encode(),dtype=np.uint8)
    temporary=path.with_suffix(path.suffix+'.incoming')
    with temporary.open('wb')as out:np.savez(out,**values)
    temporary.replace(path)
    return dict(path=str(path),sha256=digest(path),bytes=path.stat().st_size,round=metadata['round'],array_sha256=metadata['array_sha256'])


class SampledStore:
    """All scalar decisions, sampled full transitions, and one atomic latest head.

    The mutable head is exploratory state, not an immutable certificate archive.
    It contains exact current/BEST arrays and its own self-contained metadata;
    interruption never requires combining two separately published head files.
    """
    def __init__(self,root,config_sha,design_sha,raw_limit=RAW_LIMIT):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.config_sha=config_sha;self.design_sha=design_sha;self.raw_limit=int(raw_limit)
        self.entries=[];self.used=0;self.last_phase=None;self.previous_event_sha=None;self.skipped=0;self.last=None
        self.zero={};self.zero_bytes=0
        if any((self.root/name).exists()for name in('state-head.npz','scalar-events.jsonl','sampled-index.json')):
            raise ValueError('Refuse existing search state')

    def commit(self,arrays,event,force=False):
        event=dict(event);round_number=int(event['round']);phase=event['temperature_phase']
        event['previous_event_sha256']=self.previous_event_sha
        scalar_text=compact_json(event);event_sha=hashlib.sha256(scalar_text.encode()).hexdigest()
        meta=dict(round=round_number,event=event,event_sha256=event_sha,design_sha256=self.design_sha,
            family_config_sha256=self.config_sha,verified=False,
            audit_scope='Full transition arrays are sampled; scalar history does not independently replay unsaved proposals.')
        reasons=[]
        if round_number%SAMPLE_EVERY==0:reasons.append('periodic32')
        if phase!=self.last_phase:reasons.append('phase_boundary')
        if force:reasons.append('terminal')
        zeros=np.flatnonzero(np.asarray(arrays['best_energy_after'])==0.)
        new_zero=[]
        for chain in zeros:
            pose=arrays['best_after'][chain];identity=array_sha(pose)
            if identity in self.zero:continue
            entry=_atomic_npz(self.root/'zero-energy'/f'{identity}.npz',{'pose':pose,'box':arrays['boxes'][chain]},dict(meta,chain=int(chain)))
            entry['path']=str(Path(entry['path']).relative_to(self.root));entry['chain']=int(chain);entry['verified']=False
            self.zero[identity]=entry;self.zero_bytes+=entry['bytes'];new_zero.append(identity)
        if new_zero:reasons.append('new_zero_energy')
        if self.zero:atom_json(self.root/'zero-energy-index.json',self.zero)
        entry=None
        estimate=sum(np.asarray(v).nbytes for v in arrays.values())+512*1024
        essential=force or'phase_boundary'in reasons or bool(new_zero)
        if reasons and(self.used+estimate<=self.raw_limit or essential):
            name=f'raw-samples/round-{round_number:07d}-{len(self.entries):05d}.npz'
            entry=_atomic_npz(self.root/name,arrays,dict(meta,sampling_reasons=reasons))
            entry['path']=name;entry['sampling_reasons']=reasons;self.entries.append(entry);self.used+=entry['bytes']
        elif reasons:self.skipped+=1
        # Atomic head is published before the append-only scalar record and
        # before caller commits memory. Its embedded last event closes one-line lag.
        head=_atomic_npz(self.root/'state-head.npz',{k:arrays[k]for k in STATE_KEYS},dict(meta,kind='durable_head'))
        with(self.root/'scalar-events.jsonl').open('a')as out:
            out.write(compact_json(dict(event,event_sha256=event_sha,sampled_packet=entry))+'\n');out.flush()
        self.previous_event_sha=event_sha;self.last_phase=phase
        self.last=dict(head=head,sampled_packet=entry,event_sha256=event_sha,round=round_number,event=event)
        atom_json(self.root/'sampled-index.json',dict(packets=self.entries,total_bytes=self.used,routine_samples_skipped=self.skipped,
            last_head=head,scalar_event_sha256=event_sha,all_scalar_decisions_retained=True,
            full_transition_scope='periodic32/phase/zero/terminal plus explicit storage skips; not full history'))
        return self.last

    def can_continue(self):
        scalar=self.root/'scalar-events.jsonl'
        return self.zero_bytes<PROTECTED_LIMIT and(not scalar.exists()or scalar.stat().st_size<SCALAR_LIMIT)and self.used<self.raw_limit+PROTECTED_LIMIT//2


def recover(root):
    root=Path(root);head=root/'state-head.npz';index=json.loads((root/'sampled-index.json').read_text())if(root/'sampled-index.json').exists()else{}
    # A complete terminal sample is preferred; otherwise the atomic head remains
    # authoritative even when its separate index publication was interrupted.
    packets=index.get('packets',[]);terminal=[p for p in packets if'terminal'in p.get('sampling_reasons',[])]
    origin=(root/terminal[-1]['path'])if terminal else head
    if terminal:assert digest(origin)==terminal[-1]['sha256'] and origin.stat().st_size==terminal[-1]['bytes']
    with np.load(origin,allow_pickle=False)as z:
        meta=json.loads(z['metadata_json'].tobytes());members={k:z[k].copy()for k in z.files if k!='metadata_json'}
    assert set(members)==set(meta['array_sha256'])
    assert all(array_sha(value)==meta['array_sha256'][key]for key,value in members.items())
    assert digest(root/'family-config.json')==meta['family_config_sha256'] and digest(root/'chain-design.json')==meta['design_sha256']
    selected={k:members[k]for k in STATE_KEYS};atom_npz(root/'final-current-best.npz',selected)
    result=dict(completed=True,status='complete'if terminal else'recovered_head',state_origin=dict(
        kind='sampled_terminal_packet'if terminal else'durable_head',path=str(origin.relative_to(root)),sha256=digest(origin),round=meta['round'],array_sha256=meta['array_sha256']),
        final_archive='final-current-best.npz',final_archive_sha256=digest(root/'final-current-best.npz'),
        design_sha256=meta['design_sha256'],family_config_sha256=meta['family_config_sha256'])
    atom_json(root/'recovery.json',result);return result


def load_family(root):
    root=Path(root);config=json.loads((root/'family-config.json').read_text())
    if digest(root/'family-inputs.npz')!=config['inputs_sha256']:raise ValueError('Family inputs changed')
    with np.load(root/'family-inputs.npz',allow_pickle=False)as z:
        if set(z.files)!=set(config['seed_keys']):raise ValueError('Unexpected seed inventory')
        bank={name:z[name].copy()for name in z.files}
    for name,p in bank.items():
        if p.shape!=(config['n'],3)or p.dtype!=np.dtype('<f8')or not np.isfinite(p).all()or array_sha(p)!=config['seed_array_sha256'][name]:
            raise ValueError('Exact seed geometry/count changed')
        p.setflags(write=False)
    return config,bank


def search(root,parent_deadline,search_seconds=3000.):
    root=Path(root).resolve();config,bank=load_family(root)
    if float(search_seconds)!=3000.:raise ValueError('Frozen 3000-second search policy required')
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    if not torch.cuda.is_available()or'T4'not in torch.cuda.get_device_name(0):raise ValueError('Free T4 device required')
    fused.configure_gpu();rows=design(config);atom_json(root/'chain-design.json',rows)
    before_source={name:array_sha(p)for name,p in bank.items()}
    current=torch.tensor(np.stack([bank[r['source_key']]for r in rows]),dtype=torch.float64,device='cuda:0')
    boxes=torch.tensor([[r['width'],r['height']]for r in rows],dtype=torch.float64,device='cuda:0')
    base=np.array([r['temperature']for r in rows]);seed=rows[0]['case_seed']
    metrics=host_metrics(current,boxes);best=current.clone();best_energy=metrics['energy'].copy()
    preflight=json.loads((root/'preflight.json').read_text());assert preflight['passed'] and preflight['n']==config['n']
    tail_guard=max(2.,2.*float(preflight['batch_quench']['seconds'])+1.)
    if tail_guard>20.:raise ValueError('Measured quench exceeds finalization reserve')
    started=time.monotonic();deadline=started+search_seconds
    if deadline+20.>parent_deadline:raise TimeoutError('Search initialization exceeded20-second allowance')
    epoch=dict(started_monotonic=started,deadline_monotonic=deadline,cooling_start_monotonic=started+.75*search_seconds,
        parent_phase_deadline_monotonic=parent_deadline,search_seconds=search_seconds,finalization_reserve_seconds=20.,tail_guard_seconds=tail_guard)
    atom_json(root/'search-epoch.json',epoch)
    store=SampledStore(root,digest(root/'family-config.json'),digest(root/'chain-design.json'))
    round_number=0;mutations=0;quenches=0;last_arrays=None;last_event=None;counters={};last_notice=0.;stop='deadline_tail_guard'
    while time.monotonic()<deadline-tail_guard and store.can_continue():
        initial=round_number==0;old=current.clone();old_best=best.clone();old_np=old.cpu().numpy()
        old_metrics=host_metrics(old,boxes)
        assert np.allclose(old_metrics['energy'],metrics['energy'],rtol=1e-12,atol=1e-16)
        details=[];proposals=[]
        for chain,row in enumerate(rows):
            if initial:q=old_np[chain].copy();detail=dict(operator='initial_quench',selected_count=0,changed_count=0)
            else:
                rng=random_stream(seed,round_number,chain)
                for attempt in range(4):
                    q,detail=mutate(old_np[chain],old_metrics['per_square'][chain],rng,row['amplitude'])
                    if detail['changed_count']>0:break
                else:raise ValueError('Repeated zero-change move')
                detail['zero_change_resamples']=attempt
            # Keep exact draws reproducible without copying every selected-ID list
            # into the scalar log. Full sampled packets retain the proposal array.
            detail=dict(detail)
            for field in('selected_ids','changed_ids'):
                if field in detail:
                    values=np.asarray(detail.pop(field),dtype='<i8');detail[field+'_sha256']=array_sha(values)
            detail['rng_identity']=[seed,round_number,chain,41]
            proposals.append(q);details.append(detail)
        proposal=torch.tensor(np.stack(proposals),dtype=torch.float64,device='cuda:0')
        saved_proposal=proposal.clone();input_metrics=host_metrics(proposal,boxes)
        returned,quench_report=quench(proposal,boxes)
        assert torch.equal(proposal,saved_proposal)
        finite=torch.isfinite(returned).all((1,2));safe=torch.where(finite[:,None,None],returned,old)
        output_metrics=host_metrics(safe,boxes);output_metrics['energy'][~finite.cpu().numpy()]=np.inf
        decision=time.monotonic();temperature,phase=temperatures(base,started,deadline,decision)
        draws=uniforms(seed,round_number);accepted,rule=acceptance(old_metrics['energy'],output_metrics['energy'],temperature,draws)
        if initial:accepted=np.isfinite(output_metrics['energy'])
        next_current=torch.where(torch.tensor(accepted,device='cuda:0')[:,None,None],safe,old)
        next_energy=np.where(accepted,output_metrics['energy'],old_metrics['energy'])
        choices=np.stack((best_energy,input_metrics['energy'],output_metrics['energy']));choice=choices.argmin(0)
        next_best=old_best.clone()
        for kind,values in((1,proposal),(2,safe)):
            mask=torch.tensor(choice==kind,device='cuda:0');next_best[mask]=values[mask]
        next_best_energy=choices.min(0)
        event=dict(round=round_number,initialization=initial,decision_time_monotonic=decision,
            decision_elapsed_seconds=decision-started,search_deadline_monotonic=deadline,
            temperature_phase=phase,temperature=temperature,base_temperature=base,moves=details,
            acceptance_rng_identity=[seed,round_number,2718],uniform=draws,accepted=accepted,
            current_energy=old_metrics['energy'],input_energy=input_metrics['energy'],proposal_energy=output_metrics['energy'],
            next_energy=next_energy,best_energy=next_best_energy,best_origin_choice=choice,
            quench=quench_report,finite_returned=finite.cpu().numpy(),physical_unit_sizes=True,**rule)
        arrays=dict(current_before=old_np,best_before=old_best.cpu().numpy(),proposal_input=saved_proposal.cpu().numpy(),
            proposal_quenched=returned.cpu().numpy(),current_after=next_current.cpu().numpy(),best_after=next_best.cpu().numpy(),
            boxes=boxes.cpu().numpy(),current_energy=old_metrics['energy'],input_energy=input_metrics['energy'],
            proposal_energy=output_metrics['energy'],next_energy=next_energy,best_energy_before=best_energy,
            best_energy_after=next_best_energy,uniform=draws,accepted=accepted,temperature=temperature)
        store.commit(arrays,event);last_arrays=arrays;last_event=store.last['event']
        current=next_current;best=next_best;best_energy=next_best_energy;metrics=host_metrics(current,boxes)
        assert np.allclose(metrics['energy'],next_energy,rtol=1e-12,atol=1e-16)
        quenches+=BATCH;mutations+=int(not initial)
        for chain,row in enumerate(rows):
            label=f"cut{row['delta']}/T{row['temperature']}/{phase}/{details[chain]['operator']}"
            counter=counters.setdefault(label,dict(proposals=0,accepted=0,uphill=0))
            counter['proposals']+=1;counter['accepted']+=int(accepted[chain]);counter['uphill']+=int(accepted[chain]and rule['uphill'][chain])
        round_number+=1
        status=dict(rounds_completed=mutations,chain_quenches=quenches,actual_elapsed_seconds=time.monotonic()-started,
            best_energy=best_energy,current_energy=metrics['energy'],sampled_packets=len(store.entries),raw_sample_bytes=store.used,
            skipped_routine_samples=store.skipped,zero_energy_states=len(store.zero),counters=counters,verified=False)
        atom_json(root/'search-status.json',json_finite(status))
        if time.monotonic()-last_notice>=60.:
            print(compact_json(dict(stage='rectangular_search',family=config['key'],rounds=mutations,
                elapsed_seconds=status['actual_elapsed_seconds'],minimum_best_energy=float(best_energy.min()),sampled_packets=len(store.entries))),flush=True)
            last_notice=time.monotonic()
    if not store.can_continue():stop='bounded_output_limit'
    if last_arrays is None:raise RuntimeError('No complete quench to retain')
    # Final publication repeats the exact last transition, never advances state.
    # Do not append another scalar event with a duplicate round.
    final=_atomic_npz(root/'terminal-state.npz',last_arrays,dict(round=last_event['round'],event=last_event,event_sha256=store.previous_event_sha,
        design_sha256=digest(root/'chain-design.json'),family_config_sha256=digest(root/'family-config.json'),sampling_reasons=['terminal'],verified=False))
    final['path']='terminal-state.npz';final['sampling_reasons']=['terminal'];store.entries.append(final);store.used+=final['bytes']
    atom_json(root/'sampled-index.json',dict(packets=store.entries,total_bytes=store.used,routine_samples_skipped=store.skipped,
        all_scalar_decisions_retained=True,full_transition_scope='Sampled arrays, exact final transition and latest atomic head; not full history'))
    assert before_source=={name:array_sha(p)for name,p in bank.items()}
    recovery=recover(root)
    summary=dict(status='complete',stop_reason=stop,search_epoch=epoch,actual_elapsed_seconds=time.monotonic()-started,
        completed_mutation_rounds=mutations,completed_chain_quenches=quenches,sampled_packets=len(store.entries),raw_sample_bytes=store.used,
        skipped_routine_samples=store.skipped,zero_energy_states=len(store.zero),scalar_history_sha256=digest(root/'scalar-events.jsonl'),
        recovery=recovery,source_seeds_unchanged=True,no_certified_gain_claim=True,no_canonical_mutation=True)
    atom_json(root/'search-summary.json',summary);return summary
