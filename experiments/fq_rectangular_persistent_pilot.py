"""Four bounded complete-rectangle searches; source, control and output gates.

Separate processes own each phase. Numerical quench sources remain unchanged;
accepted proposals use fresh physical W/H energy. No portfolio/submission writes.
"""
from __future__ import annotations
import argparse,hashlib,json,os,signal,subprocess,sys,time
from decimal import Decimal
from pathlib import Path
for name in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import torch
from scipy.spatial import cKDTree
import fq_rectangular_persistent_search as searcher
from fq_coherent_clusters import atom_json,atom_npz
from fq_torch_hop_pilot import digest,json_finite
from full_structural_gpu_ties import check_cuda
from full_structural_gpu_worker import assert_dense_matches,bounded_certificate
from prepare_wall_aspect_inputs import rectangular_control
from compose_gadgets import legalize

QUEUES=(('5_17_7','7_20_14'),('7_19_13','8_21_13'))
SEARCH_SECONDS=3000.
PREFLIGHT_SECONDS=60.
SEARCH_PHASE_SECONDS=3040.
FINISH_SECONDS=290.
RECOVERY_SECONDS=3.
TOTAL_OUTPUT_BYTES=10*1024**3


def read(path):return json.loads(Path(path).read_text())
def tree_bytes(root):
    result=0
    for directory,_,names in os.walk(root):
        for name in names:
            try:result+=(Path(directory)/name).stat().st_size
            except FileNotFoundError:pass
    return result


def protocol():
    p=read('rectangular-protocol.json')
    assert p['families']==list(searcher.FAMILIES)and p['batch_size']==64 and p['cuts']==list(searcher.CUTS)
    assert p['search_seconds']==SEARCH_SECONDS and p['parent_seconds']==7100 and p['server_seconds']==7800
    assert p['phase_seconds']==dict(preflight=60,search=3040,recovery=3,finish=290)
    assert p['whole_seconds']==7200 and p['temperature_by_stream']==[.3,.3,1.,1.]
    assert p['cooling_fraction']==.25 and p['cooled_temperature']==.03 and p['sample_every']==32
    return p


def prepare(root,p):
    source=read(root/'rectangular-input-config.json');proof=read(root/'rectangular-input-proof.json')
    assert digest(root/'rectangular-input-config.json')==p['input_config_sha256']
    assert digest(root/'rectangular-input-proof.json')==p['input_proof_sha256']
    assert digest(root/'rectangular-inputs.npz')==p['input_archive_sha256']==source['inputs_sha256']==proof['inputs_sha256']
    assert proof['config_sha256']==p['input_config_sha256']and proof['all_transformed_gates_passed']
    assert set(source['families'])==set(searcher.FAMILIES)
    control_path=root/p['native_reference_results_path']
    assert digest(control_path)==p['native_reference_results_sha256']
    control_rows=read(control_path);assert len(control_rows)==4
    controls={row['family_key']:row for row in control_rows};assert set(controls)==set(searcher.FAMILIES)
    from fq_restart_hop_finish import BINARY_SHA
    binary=root/'bin/fq';assert digest(binary)==BINARY_SHA;binary.chmod(0o500)
    with np.load(root/'rectangular-inputs.npz',allow_pickle=False)as z:
        for device,queue in enumerate(QUEUES):
            for key in queue:
                family=dict(source['families'][key]);folder=root/('family-'+key);folder.mkdir(exist_ok=False)
                family.update(key=key,device=device,batch_size=64,binary_path=str(binary),seed_keys=[r['key']for r in family['seeds']],
                    source_input_archive_sha256=p['input_archive_sha256'],source_input_config_sha256=p['input_config_sha256'],
                    source_input_proof_sha256=p['input_proof_sha256'],protocol_sha256=digest(root/'rectangular-protocol.json'))
                control=controls[key]
                assert control['status']=='certified'and control['certificate']['valid']and control['rectangular_certificate']['valid']
                assert control['selected_geometry_sha256']==family['seeds'][0]['geometry_sha256']
                family['original_search_reference_f_lower']=family['reference_f_lower']
                family['reference_f_lower']=str(min(Decimal(family['reference_f_lower']),Decimal(control['rectangular_certificate']['f_lower'])))
                family['component_comparison']=dict(policy='Stronger of immutable seed and exact matched native control; search target upper remains original seed upper.',
                    results_path=p['native_reference_results_path'],results_sha256=p['native_reference_results_sha256'],slot=control['slot'],
                    control_f_lower=control['rectangular_certificate']['f_lower'],control_f_upper=control['rectangular_certificate']['f_upper'])
                bank={row['key']:z[row['key']].copy()for row in family['seeds']}
                for row in family['seeds']:
                    assert searcher.array_sha(bank[row['key']])==row['geometry_sha256']
                    assert digest(root/row['certificate']['path'])==row['certificate']['sha256']
                atom_npz(folder/'family-inputs.npz',bank)
                family['inputs_sha256']=digest(folder/'family-inputs.npz')
                family['seed_array_sha256']={k:searcher.array_sha(v)for k,v in bank.items()}
                atom_json(folder/'family-config.json',family);searcher.design(family)
    atom_json(root/'input-preparation.json',dict(passed=True,protocol_sha256=digest(root/'rectangular-protocol.json'),
        input_archive_sha256=p['input_archive_sha256'],family_inputs={key:digest(root/('family-'+key)/'family-inputs.npz')for key in searcher.FAMILIES},
        exact_seed_arrays=16,no_geometry_changes=True))


def _physical_check(p,box):
    tensor=torch.tensor(p[None],dtype=torch.float64,device='cuda:0');bt=torch.tensor(np.asarray(box)[None],dtype=torch.float64,device='cuda:0')
    actual=float(searcher.physical_energy(tensor,bt)['energy'][0]);independent=rectangular_control(p,*box)
    assert abs(actual-independent['energy'])<=1e-10*max(1.,independent['energy'])
    return dict(physical_energy=actual,independent_energy=independent['energy'],absolute_error=abs(actual-independent['energy']))


def preflight(root):
    from fq_rectangular_persistent_finish import rectangular_certificate
    started=time.monotonic();root=Path(root).resolve();config,bank=searcher.load_family(root)
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.cuda.is_available()and'T4'in torch.cuda.get_device_name(0)
    cp,gpu,patch=searcher.fused.configure_gpu();folder=root/'preflight';folder.mkdir(exist_ok=False)
    atom_json(folder/'gradient-patch.json',patch);gradient=check_cuda(gpu);atom_json(folder/'gradient-controls.json',gradient)
    poses={};records={};w,h,n=config['w'],config['h'],config['n']
    def retain(label,p,box):
        p=legalize(p,clearance=2e-9);assert p is not None and len(p)==n
        certificate=bounded_certificate(p,seconds=8);assert certificate['valid']
        # Save every full-certified control before the additional rectangle proof.
        geometry=searcher.array_sha(p);name=label+'__'+geometry;poses[name]=p.copy()
        record=dict(geometry_sha256=geometry,certificate=certificate,box=list(map(float,box)))
        atom_npz(folder/(name+'.npz'),{'pose':p});atom_json(folder/(name+'.json'),record)
        records[name]=record;atom_npz(folder/'certified.npz',poses);atom_json(folder/'certificates.json',records)
        rect=rectangular_certificate(p,w,h);assert rect['valid']
        assert float(rect['transports']['raw']['width_upper'])<=float(box[0])+1e-6
        assert float(rect['transports']['raw']['height_upper'])<=float(box[1])+1e-6
        record['rectangle']=rect;atom_json(folder/(name+'.json'),record);atom_json(folder/'certificates.json',records)
    seeds=[config['seeds'][0],config['seeds'][-1]];q=np.stack([bank[row['key']]for row in seeds])
    boxes=np.array([[w+float(row['f_upper'])+.001,h+float(row['f_upper'])+.001]for row in seeds])
    e,g=gpu.energy(q,boxes,tau=0.)
    for i in range(2):assert_dense_matches(e[i],q[i],boxes[i]);assert e[i,1]<1e-7
    fixed,_=gpu.quench(q.copy(),boxes,steps=80,tau=0.);fixed=cp.asnumpy(fixed)
    for i in range(2):retain('unchanged_'+str(i),fixed[i],boxes[i])
    p=bank[config['seed_keys'][0]];box=np.array([w+float(config['reference_f_upper'])+.01,h+float(config['reference_f_upper'])+.01])
    bad=p.copy();bad[-1]=bad[0];bad[-1,0]+=.1
    negative,grad=gpu.energy(bad[None],box[None],tau=0.);assert negative[0,1]>.8 and np.linalg.norm(grad[0,-1])>.01
    assert_dense_matches(negative[0],bad,box);negative_physical=_physical_check(bad,box)
    assert not bounded_certificate(bad,seconds=8)['valid']
    boundary=p.copy();boundary[-2]=[2.9999,3.,0.];boundary[-1]=[3.0001,3.,0.]
    be,_=gpu.energy(boundary[None],box[None],tau=0.);assert be[0,1]>.99;assert_dense_matches(be[0],boundary,box)
    # A genuinely overlapping existing pair in a slightly relaxed full rectangle.
    positive=p.copy();positive[:,:2]*=1.0002
    folded=(positive[:,2]+np.pi/4)%(np.pi/2)-np.pi/4;ids=np.flatnonzero(abs(folded)<1e-5)
    assert len(ids)>=2
    distances,neighbors=cKDTree(positive[ids,:2]).query(positive[ids,:2],k=2)
    a=int(np.argmin(distances[:,1]));b=int(neighbors[a,1]);i,j=int(ids[a]),int(ids[b])
    positive[j,:2]+=.003*(positive[i,:2]-positive[j,:2]);before,_=gpu.energy(positive[None],box[None],tau=0.)
    assert before[0,1]>1e-5
    repaired=cp.asarray(positive[None])
    for _ in range(4):repaired,_=gpu.quench(repaired,box[None],steps=350,tau=0.)
    residual,_=gpu.energy(repaired,box[None],tau=0.);assert residual[0,1]<1e-7
    retain('actual_full_rectangle_overlap_repair',cp.asnumpy(repaired)[0],box)
    rows=searcher.design(config);actual=np.stack([bank[r['source_key']]for r in rows]);actual_boxes=np.array([[r['width'],r['height']]for r in rows])
    for chain,row in enumerate(rows):
        actual[chain],_=searcher.mutate(actual[chain],np.zeros(n),searcher.random_stream(row['case_seed'],917,chain),.01)
    assert len({searcher.array_sha(pose)for pose in actual})==64
    proposal=torch.tensor(actual,dtype=torch.float64,device='cuda:0');saved=proposal.clone();bt=torch.tensor(actual_boxes,dtype=torch.float64,device='cuda:0')
    returned,report=searcher.quench(proposal,bt);assert torch.equal(proposal,saved)and torch.isfinite(returned).all()
    assert report['steps_requested']==2000 and report['seconds']<=9.5
    checks=[]
    for chain in(0,15,31,32,47,63):
        check=_physical_check(returned[chain].cpu().numpy(),actual_boxes[chain]);check['chain']=chain;checks.append(check)
    # Separate unequal walls are tested by changing only H, including last row.
    walls=p.copy();extent=.5*(abs(np.cos(walls[-1,2]))+abs(np.sin(walls[-1,2])))
    # Put its lower face above H: pair forces vanish, isolating the wall term.
    walls[-1,1]=box[1]+extent+.03;wall_control=_physical_check(walls,box)
    wall_penetration=2*extent+.03
    assert wall_control['physical_energy']>=wall_penetration**2-1e-10
    wall_native,wall_gradient=gpu.energy(walls[None],box[None],tau=0.);assert_dense_matches(wall_native[0],walls,box)
    assert abs(float(wall_gradient[0,-1,1])-4*wall_penetration)<1e-8
    wall_control.update(expected_native_y_gradient=4*wall_penetration,actual_native_y_gradient=float(wall_gradient[0,-1,1]),
        lower_face_above_height=.03,last_unit=n-1)
    result=dict(passed=True,n=n,family=config['key'],seconds=time.monotonic()-started,compiler_options=list(searcher.fused.CUDA_OPTIONS),
        full_unit_count_preserved=True,last_index=n-1,last_unit_overlap_residual=float(negative[0,1]),
        last_unit_gradient_norm=float(np.linalg.norm(grad[0,-1])),negative_physical=negative_physical,
        hash_cell_boundary_residual=float(be[0,1]),independent_rectangle_wall_control=wall_control,
        actual_full_repair_before=float(before[0,1]),actual_full_repair_after=float(residual[0,1]),
        batch_quench=report,independent_batch_inputs=64,physical_energy_checks=checks,proposal_input_unchanged=True,
        certified_archive_sha256=digest(folder/'certified.npz'),certificates_sha256=digest(folder/'certificates.json'))
    atom_json(root/'preflight.json',result)
    print(json.dumps(dict(stage='rectangular_preflight',family=config['key'],passed=True,seconds=result['seconds'])),flush=True)
    return result


def _process_table():
    table={}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            text=path.read_text();tail=text[text.rfind(')')+2:].split()
            table[int(path.parent.name)]=(int(tail[1]),int(tail[19]),tail[0])
        except(OSError,ValueError,IndexError):pass
    return table


def register_descendants(pid,known):
    table=_process_table();roots={p for p,tick in known.items()if p in table and table[p][1]==tick}
    if pid in table:
        if pid not in known:known[pid]=table[pid][1]
        if known[pid]==table[pid][1]:roots.add(pid)
    while True:
        new={child for child,(parent,_,_)in table.items()if parent in roots}-roots
        if not new:break
        roots.update(new)
    for child in roots:known[child]=table[child][1]
    return known


def stop_owned_tree(process,known=None):
    # Registered PID/start-time pairs survive reparenting and cannot hit a later
    # unrelated process which reuses a numeric PID. Freeze before resnapshotting.
    known={}if known is None else dict(known)
    register_descendants(process.pid,known)
    for _ in range(8):
        table=_process_table()
        for pid,tick in known.items():
            if pid in table and table[pid][1]==tick and table[pid][2]!='Z':
                try:os.kill(pid,signal.SIGSTOP)
                except ProcessLookupError:pass
        size=len(known);register_descendants(process.pid,known)
        if len(known)==size:break
    table=_process_table();killed=[]
    for pid,tick in sorted(known.items(),reverse=True):
        if pid in table and table[pid][1]==tick and table[pid][2]!='Z':
            try:os.kill(pid,signal.SIGKILL);killed.append(pid)
            except ProcessLookupError:pass
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:pass
    end=time.monotonic()+2
    while True:
        table=_process_table();alive=[pid for pid,tick in known.items()if pid in table and table[pid][1]==tick and table[pid][2]!='Z']
        if not alive:break
        if time.monotonic()>=end:raise RuntimeError('Owned descendant still alive before output hashing: '+str(alive))
        time.sleep(.01)
    return dict(registered_pid_start_times={str(k):v for k,v in known.items()},killed_pids=killed,all_gone_or_zombie=True)


def run_phase(root,mode,seconds,global_deadline,device):
    started=time.monotonic();deadline=min(started+seconds,global_deadline)
    if deadline-started<seconds-1e-6:return dict(phase=mode,status='skipped_global_deadline',seconds=0.)
    command=[sys.executable,str(Path(__file__).resolve()),'--mode',mode,'--deadline',str(deadline)]
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(device));log=Path(root)/(mode+'.log')
    known={};forced=False;cleanup={}
    with log.open('wb')as out:
        process=subprocess.Popen(command,cwd=root,stdout=out,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        try:
            while process.poll()is None:
                register_descendants(process.pid,known)
                if time.monotonic()>=deadline:forced=True;break
                time.sleep(.1)
        finally:cleanup=stop_owned_tree(process,known)
        code=process.returncode
    return dict(phase=mode,status='complete'if code==0 and not forced else'bounded_partial',returncode=code,
        forced=forced,seconds=time.monotonic()-started,phase_limit_seconds=seconds,cleanup=cleanup,log_sha256=digest(log))


def emit_family_payload(root,config,summary):
    import base64,zlib
    names=['family-config.json','chain-design.json','recovery.json','finish/certified.npz','finish/rectangular-donors.npz',
        'finish/results.json','finish/manifest.json','finish/summary.json']
    files={};total=0
    for name in names:
        path=root/name
        if not path.exists():continue
        data=path.read_bytes();total+=len(data)
        files[name]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),encoding='zlib1-base85',data=base64.b85encode(zlib.compress(data,1)).decode())
    payload=dict(stage='rectangular_family_payload',family=config['key'],protocol_sha256=config['protocol_sha256'],
        input_archive_sha256=config['source_input_archive_sha256'],files=files,
        scope='Exact published transport only. Independently verify geometry/certificates and recompose before any gain claim.')
    text=searcher.compact_json(payload)
    if total<=2*1024**2 and len(text)<=512*1024:
        print(text,flush=True)
        atom_json(root/'live-payload-receipt.json',dict(status='published',encoded_bytes=len(text),uncompressed_bytes=total,
            payload_sha256=hashlib.sha256(text.encode()).hexdigest(),file_hashes={k:v['sha256']for k,v in files.items()}))
    else:
        print(json.dumps(dict(stage='rectangular_payload_omitted_size_cap',family=config['key'],uncompressed_bytes=total,encoded_bytes=len(text))),flush=True)
    print(json.dumps(dict(stage='rectangular_native_complete',family=config['key'],certified=summary['certified'],
        best_f_upper=summary['best_f_upper'],strict_component_improvements=summary['strict_component_improvements'],
        no_full_portfolio_gain_claim=True)),flush=True)


def relay_json_logs(root,offsets,buffers):
    for key in searcher.FAMILIES:
        for phase in('preflight','search','recover','finish'):
            path=root/('family-'+key)/(phase+'.log')
            if not path.exists():continue
            with path.open('rb')as source:
                source.seek(offsets.get(str(path),0));data=source.read(1024*1024);offsets[str(path)]=source.tell()
            data=buffers.get(str(path),b'')+data;lines=data.split(b'\n');buffers[str(path)]=lines.pop()
            for line in lines:
                try:record=json.loads(line)
                except(UnicodeDecodeError,json.JSONDecodeError):continue
                if isinstance(record,dict)and isinstance(record.get('stage'),str):print(line.decode(),flush=True)

def queue(root,device,deadline):
    root=Path(root).resolve();result={}
    for key in QUEUES[device]:
        folder=root/('family-'+key);row={};result[key]=row
        if tree_bytes(root)>=TOTAL_OUTPUT_BYTES:row['status']='global_output_stop';break
        row['preflight']=run_phase(folder,'preflight',PREFLIGHT_SECONDS,deadline,device)
        if row['preflight']['status']!='complete':row['status']='control_failed';atom_json(root/f'queue-{device}.json',result);continue
        row['search']=run_phase(folder,'search',SEARCH_PHASE_SECONDS,deadline,device)
        row['recovery']=run_phase(folder,'recover',RECOVERY_SECONDS,deadline,device)
        if row['recovery']['status']=='complete':
            row['finish']=run_phase(folder,'finish',FINISH_SECONDS,deadline,device)
            summary=folder/'finish/summary.json'
            if row['finish']['status']=='complete':
                if not summary.exists()or read(summary)['status']!='complete':row['finish']['status']='bounded_partial'
                else:row['finish']['summary_sha256']=digest(summary)
        row['status']='complete'if all(r['status']=='complete'for r in row.values())else'bounded_partial'
        atom_json(root/f'queue-{device}.json',result)
        print(json.dumps(dict(stage='rectangular_family_complete',family=key,status=row['status'])),flush=True)
    atom_json(root/f'queue-{device}.json',result);return result


def parent(root,deadline):
    root=Path(root).resolve();p=protocol();prepare(root,p);workers=[];logs=[];registries=[{},{}];offsets={};buffers={}
    for device in(0,1):
        log=(root/f'queue-{device}.log').open('wb');logs.append(log)
        command=[sys.executable,str(Path(__file__).resolve()),'--mode','queue','--device',str(device),'--deadline',str(deadline)]
        workers.append(subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True))
    forced=False
    try:
        while any(worker.poll()is None for worker in workers):
            for i,worker in enumerate(workers):register_descendants(worker.pid,registries[i])
            relay_json_logs(root,offsets,buffers)
            if time.monotonic()>=deadline:forced=True;break
            time.sleep(.5)
    finally:
        cleanup=[stop_owned_tree(worker,registries[i])for i,worker in enumerate(workers)]
        relay_json_logs(root,offsets,buffers)
        for log in logs:log.close()
    summaries={str(d):read(root/f'queue-{d}.json')if(root/f'queue-{d}.json').exists()else{}for d in(0,1)}
    complete=not forced and all(worker.returncode==0 for worker in workers)and sum(len(v)for v in summaries.values())==4
    complete=complete and all(r.get('status')=='complete'for q in summaries.values()for r in q.values())
    result=dict(status='complete'if complete else'bounded_partial',forced=forced,queues=summaries,cleanup=cleanup,
        controls_passed=all(r.get('preflight',{}).get('status')=='complete'for q in summaries.values()for r in q.values())and sum(len(v)for v in summaries.values())==4,
        worker_returncodes=[worker.returncode for worker in workers],output_bytes=tree_bytes(root),
        no_submission=True,no_canonical_mutation=True,sampled_full_transition_history=True)
    atom_json(root/'rectangular-summary.json',result);atom_json(root/'pilot-summary.json',result);print(json.dumps(result),flush=True);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('parent','queue','preflight','search','recover','finish'),default='parent')
    parser.add_argument('--device',type=int,choices=(0,1));parser.add_argument('--deadline',type=float,required=True);args=parser.parse_args();root=Path.cwd()
    if args.mode=='parent':parent(root,args.deadline)
    elif args.mode=='queue':queue(root,args.device,args.deadline)
    elif args.mode=='preflight':preflight(root)
    elif args.mode=='search':searcher.search(root,args.deadline,SEARCH_SECONDS)
    elif args.mode=='recover':searcher.recover(root)
    else:
        from fq_rectangular_persistent_finish import finish_family
        config=read('family-config.json');summary=finish_family(root,config,args.deadline);emit_family_payload(root,config,summary)

if __name__=='__main__':main()
