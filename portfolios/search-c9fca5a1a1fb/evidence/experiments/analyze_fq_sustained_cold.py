"""Read-only receipt, terminal, native and decimal-certificate audit of one run."""
from __future__ import annotations
import os
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
import argparse
import ast
import base64
from decimal import Decimal
import hashlib
import io
import json
import lzma
import math
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import fq_restart_hop_finish as native
from fq_sustained_hop_finish import select_slots
from recover_broad_native_returns import current_thresholds
from packer_hop_physical_energy import physical_energy

ROOT=Path(__file__).resolve().parents[1]
SOURCE='dc6950e858285433d1975f537431e375bae95584ab314807a3ae08b79baa0451'
EXTRACTOR_SOURCE='75f5a14ff4f1d27e923241f47ff2e9e3369423fc36aab477d63a4b5b94a12e2b'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())


class Downloaded:
    def __init__(self,roots):
        self.paths={};self.receipts=[];self.consumed=set()
        for root in map(Path,roots):
            receipt_path=root/'extraction-receipt.json'
            if receipt_path.exists():
                receipt=read(receipt_path)
                assert receipt['kind']=='verified_private_cpu_extraction_chain' and receipt['status']=='complete'
                assert receipt['parent_source_sha256']==SOURCE and receipt['extractor_source_sha256']==EXTRACTOR_SOURCE
                assert receipt['parent_notebook']=='sos54352/squares-sustained-cold-12case/1'
                for name in ('extractor_download_receipt','parent_source_proof','parent_completion_proof','inventory','bundle'):
                    pointer=receipt[name];path=Path(pointer['path'])
                    assert path.resolve().is_relative_to((ROOT/'artifacts').resolve()) and sha(path)==pointer['sha256']
                parent=read(receipt['parent_source_proof']['path'])
                assert parent['source_sha256']==SOURCE and parent['private'] and parent['gpu']
                completion=read(receipt['parent_completion_proof']['path'])
                assert completion['source_sha256']==SOURCE and completion['status']=='COMPLETE'
                cpu=read(receipt['extractor_download_receipt']['path'])
                assert cpu['source_sha256']==EXTRACTOR_SOURCE and cpu['private_source_verified'] and not cpu['enable_gpu'] and cpu['status']=='complete'
                assert cpu['notebook']=='sos54352/squares-sustained-output-extractor' and cpu['version']==1
                assert cpu['files']['extracted/inventory.json']['sha256']==receipt['inventory']['sha256']
                assert cpu['files']['extracted/selected-output.zip']['sha256']==receipt['bundle']['sha256']
                inventory=read(receipt['inventory']['path'])
                assert inventory['status']=='complete' and inventory['parent_source_sha256']==SOURCE
                assert inventory['files']==receipt['files'] and inventory['zip_sha256']==receipt['bundle']['sha256']
                assert inventory['parent_manifest_sha256']==receipt['files']['job_manifest.json']['sha256']
                assert inventory['parent_config_sha256']==receipt['files']['sustained-config.json']['sha256']
            else:
                receipt_path=root/'download-receipt.json';receipt=read(receipt_path)
                assert receipt['source_sha256']==SOURCE and receipt['private_source_verified'] and receipt['enable_gpu']
                assert receipt['notebook']=='sos54352/squares-sustained-cold-12case' and receipt['version']==1
            for name,row in receipt['files'].items():
                path=root/'outputs'/name
                assert path.resolve().is_relative_to((root/'outputs').resolve()) and sha(path)==row['sha256']
                if name in self.paths:assert sha(self.paths[name])==row['sha256']
                self.paths[name]=path
            self.receipts.append(dict(path=str(receipt_path),sha256=sha(receipt_path),status=receipt['status'],files=len(receipt['files'])))
    def has(self,name):return name in self.paths
    def path(self,name):
        if name not in self.paths:raise ValueError('Consumed output is not receipt-bound: '+name)
        self.consumed.add(name);return self.paths[name]
    def json(self,name):return read(self.path(name))


def certificate_side(pose,certificate):
    """Rebind existing gates to exact emitted decimals; no new geometry gate."""
    n=len(pose);g=certificate['shared_official_gate']
    assert pose.shape==(n,3) and pose.dtype==np.dtype('<f8') and np.isfinite(pose).all()
    assert certificate['valid'] and g['valid'] and g['metric_sha256']==native.fq.OFFICIAL_SHA256
    assert g['raw_reason']==g['roundtrip_reason']==certificate['ordinary_pandas_official_reason']=='ok'
    for field in ('independent_raw','independent_roundtrip'):
        assert certificate[field]['valid'] and certificate[field]['n']==n
    rows=[dict(n=str(n),square_id=str(i),x=f'{x:.17g}',y=f'{y:.17g}',angle=f'{a:.17g}')
        for i,(x,y,a) in enumerate(pose)]
    raw=pd.DataFrame(rows).to_csv(index=False)
    ordinary=pd.read_csv(io.StringIO(raw)).to_csv(index=False)
    assert hashlib.sha256(raw.encode()).hexdigest()==certificate['raw_csv_sha256']
    assert hashlib.sha256(ordinary.encode()).hexdigest()==certificate['ordinary_pandas_csv_sha256']
    return Decimal(native.worst_certificate_side(certificate)[0])


def audit_case(download,config,n,poses,bindings,frozen_bank,frozen_queues):
    prefix=f'case-{n}/';case=config['cases'][str(n)]
    result=dict(n=n,reference_side=case['reference_side'],status='not_started',certified=[])
    actual_case=download.json(prefix+'case-config.json');fixture=download.json(prefix+'pilot-config.json')
    hop=download.json(prefix+'hop-config.json');actual_input=download.path(prefix+'pilot-inputs.npz')
    assert fixture['inputs_sha256']==sha(actual_input)
    key=case['source_key'];assert fixture['exploratory_sources']==[key] and fixture['n']==n
    assert {k:v for k,v in actual_case.items() if k not in ('binary_path','device','batch_size','baseline_sha256')}==case
    assert actual_case['batch_size']==64 and actual_case['baseline_sha256']==config['baseline']['sha256']
    expected_device=next(i for i,queue in enumerate(frozen_queues) if n in queue)
    assert Path(actual_case['binary_path']).name=='fq' and actual_case['device']==expected_device
    assert hop==dict(search_seconds=360.,seed=config['seed']+n,max_packets=2000,max_bytes=config['raw_bytes_per_case'])
    with np.load(actual_input,allow_pickle=False) as z:
        assert z.files==[key] and np.array_equal(z[key],frozen_bank[key])
        assert native.geometry_sha(z[key])==case['source_geometry_sha256']==fixture['arrays'][key]['sha256']
        assert list(z[key].shape)==fixture['arrays'][key]['shape'] and z[key].dtype.str==fixture['arrays'][key]['dtype']
    if not download.has(prefix+'preflight/preflight_packing_records.json'):return result
    control_index=download.json(prefix+'preflight/preflight_packing_records.json')
    path=download.path(prefix+'preflight/preflight_packings.npz');assert sha(path)==control_index['archive_sha256']
    with np.load(path,allow_pickle=False) as bank:
        assert set(bank.files)==set(control_index['records'])
        for name in bank.files:
            pose=bank[name].copy();record=control_index['records'][name]
            assert len(pose)==n and native.geometry_sha(pose)==record['geometry_sha256']
            side=certificate_side(pose,record['certificate']);key=f'preflight_{n}_{name}'
            poses[key]=pose;bindings[key]=dict(n=n,side=str(side),certificate=record['certificate'],
                source_stage='mandatory_gpu_preflight',record=record,archive_sha256=sha(path))
            result['certified'].append(key)
    result['status']='partial_preflight_certificates_verified'
    if not download.has(prefix+'preflight.json'):return result
    control=download.json(prefix+'preflight.json');assert control['passed'] and control['n']==n
    assert control['independent_input_count']==64 and control['proposal_input_unchanged']
    assert {r['chain'] for r in control['physical_energy_checks']}=={0,15,31,32,47,63}
    assert control['quench_report']['steps_requested']==2000 and control['quench_report']['seconds']<=9.5
    full=download.json(prefix+'preflight/preflight.json');entry=full['full_cases'][str(n)]
    assert full['passed'] and entry['all_n_coordinates_preserved'] and entry['last_index']==n-1
    assert entry['all_pair_cpu_oracle_matches'] and entry['across_hash_cell_boundary_detected']
    result['status']='preflight_passed'
    if not download.has(prefix+'recovery.json'):return result
    recovery=download.json(prefix+'recovery.json');result['recovery']=recovery
    if not recovery.get('completed'):return result
    index=download.json(prefix+'raw-index.json');design=download.json(prefix+'chain-design.json')
    assert len(design)==64 and [r['chain'] for r in design]==list(range(64))
    assert all(r['n']==n and r['source_key']==case['source_key'] and r['arm']=='cold' and r['temperature']==.3 for r in design)
    assert all(r['side']==float(case['reference_side'])-r['delta'] and r['delta'] in (.0005,.002) for r in design)
    assert all(sum(r['delta']==cut for r in design)==32 for cut in (.0005,.002))
    complete=[r for r in index['packets'] if r['status']=='completed'];last=complete[-1]
    assert last==recovery['last_completed_packet']
    packet=download.path(prefix+last['path']);assert sha(packet)==last['sha256'] and packet.stat().st_size==last['bytes']
    final=download.path(prefix+'final-current-best.npz');assert sha(final)==recovery['recovered_final_archive_sha256']
    with np.load(packet,allow_pickle=False) as z,np.load(final,allow_pickle=False) as f:
        metadata=json.loads(z['metadata_json'].tobytes());assert metadata['design']==design and metadata['status']=='completed'
        for name in z.files:
            if name!='metadata_json':assert hashlib.sha256(z[name].tobytes()).hexdigest()==metadata['array_sha256'][name]
        arrays={name:f[name].copy() for name in native.STATE_KEYS}
        assert all(np.array_equal(z[name],arrays[name]) for name in native.STATE_KEYS)
    epoch=download.json(prefix+'search-epoch.json');assert epoch['search_seconds']==360 and epoch['finalization_reserve_seconds']==20
    assert abs(epoch['deadline_monotonic']-epoch['started_monotonic']-360)<1e-8
    assert abs(epoch['deadline_monotonic']-epoch['cooling_start_monotonic']-100)<1e-8
    assert epoch['parent_phase_deadline_monotonic']>=epoch['deadline_monotonic']+20
    status=download.json(prefix+'hop-status.json');result.update(status='terminal_verified',terminal_packet_sha256=sha(packet),
        completed_rounds=status['rounds_completed'],completed_chain_quenches=status['completed_chain_quenches'],
        actual_last_committed_search_seconds=status['search_seconds'],planned_search_seconds=360,epoch=epoch,
        raw_bytes=index['total_bytes'],hot_storage_pause_seconds=status.get('hot_storage_pause_seconds'))
    assert index['total_bytes']<=config['raw_bytes_per_case']
    if download.has(prefix+'pilot-summary.json'):
        search=download.json(prefix+'pilot-summary.json')
        result['stop_reason']=search['stop_reason'];result['tail_guard_seconds']=search['tail_guard_seconds']
    if download.has(prefix+'hop-events.jsonl'):
        events=[json.loads(line) for line in download.path(prefix+'hop-events.jsonl').read_text().splitlines()]
        recovered_event=False
        if len(events)+1==len(complete):
            events.append(dict(metadata['event'],packet=last));recovered_event=True
        assert len(events)==len(complete)
        for event,entry in zip(events,complete):
            assert event['packet']==entry
            phase='cool' if event['decision_time_monotonic']>=epoch['deadline_monotonic']-100. else 'hot'
            assert phase==event['temperature_phase']
            elapsed=event['decision_time_monotonic']-epoch['started_monotonic']
            assert abs(elapsed-event['decision_elapsed_seconds'])<1e-8
        result['event_coverage']=dict(committed_packets=len(complete),audited_events=len(events),
            terminal_event_recovered_from_exact_packet=recovered_event,
            scope='Recorded phase/timestamp/index bindings; only terminal raw packet body was downloaded and checked.')
        phases={}
        for phase in ('hot','cool'):
            rows=[r for r in events if r['temperature_phase']==phase]
            phases[phase]=dict(packets=len(rows),mutation_packets=sum(not r['initialization'] for r in rows),
                first_decision_elapsed=min((r['decision_elapsed_seconds'] for r in rows),default=None),
                last_decision_elapsed=max((r['decision_elapsed_seconds'] for r in rows),default=None))
            for row in rows:
                expected=.03 if phase=='cool' else .3
                assert all(t==expected for t in row['temperature'])
                assert row['search_deadline_monotonic']==epoch['deadline_monotonic']
        result['phases']=phases
    expected=select_slots(design,arrays['best_after'],arrays['best_energy_after'],arrays['sides'])
    slots=expected
    if download.has(prefix+'finish/manifest.json'):
        manifest=download.json(prefix+'finish/manifest.json')
        assert manifest['last_completed_packet']['sha256']==sha(packet) and manifest['workers']==2
        assert manifest['native_seconds_cap']==60 and manifest['certificate_seconds_cap']==8
        slots=manifest['fixed_slots'];assert len(slots)==4
        for actual,wanted in zip(slots,expected):
            for key,value in wanted.items():assert actual[key]==value
    summary=download.json(prefix+'finish/summary.json') if download.has(prefix+'finish/summary.json') else None
    records=download.json(prefix+'finish/results.json') if download.has(prefix+'finish/results.json') else []
    if summary:
        assert len(records)==4
        assert sha(download.path(prefix+'finish/manifest.json'))==summary['manifest_sha256']
        assert sha(download.path(prefix+'finish/results.json'))==summary['results_sha256']
    bank={};archive=None
    if download.has(prefix+'finish/certified.npz'):
        archive=download.path(prefix+'finish/certified.npz')
        if summary:assert sha(archive)==summary['certified_archive_sha256']
        with np.load(archive,allow_pickle=False) as z:bank={name:z[name].copy() for name in z.files}
    by_slot={r['slot']:r for r in records};recovered=[]
    evidence_names=sorted(name for name in download.paths if name.startswith(prefix+'finish/'))
    result['native_artifact_inventory']={name:dict(sha256=sha(download.path(name)),bytes=download.path(name).stat().st_size)
        for name in evidence_names}
    # Durable individual certificates are authoritative even if final aggregate
    # publication was interrupted. Preserve failed raw/native files separately.
    for suffix in ('.record.json','.certificate.json'):
        for name in evidence_names:
            if not name.endswith(suffix):continue
            record=download.json(name);i=record['slot'];assert 0<=i<4 and record['n']==n
            if suffix=='.certificate.json':
                assert record['status']=='certified'
                if i in by_slot and by_slot[i].get('status')=='certified':assert by_slot[i]==record
                else:recovered.append(i)
                by_slot[i]=record
            elif i not in by_slot:by_slot[i]=record
            elif by_slot[i].get('status')!='certified':
                by_slot[i]=dict(record,**by_slot[i])
    retained=set();result['native_slots']=[]
    for i,record in sorted(by_slot.items()):
        slot=slots[i];assert record['slot']==i and record['chain']==slot['chain']
        if slot['chain'] is None:continue
        for field in ('kind','delta','arm'):assert record[field]==slot[field]
        chain=slot['chain'];selected=arrays['best_after'][chain]
        assert record['selected_geometry_sha256']==native.geometry_sha(selected)
        energy=physical_energy(selected,float(arrays['sides'][chain]))['energy']
        assert abs(energy-float(arrays['best_energy_after'][chain]))<=1e-11+1e-8*energy
        row=dict(slot=i,chain=chain,kind=record['kind'],delta=record['delta'],status=record.get('status','interrupted_record'),
            physical_energy=energy,native_seconds=record.get('native_seconds'))
        base=f"{prefix}finish/slot-{i:02d}-{record['arm']}-{record['delta']}"
        # with_suffix in the frozen helper removes the trailing decimal cut.
        stem=str(Path(base).with_suffix(''))
        if 'selected_archive_sha256' not in record:
            assert record.get('status')!='certified'
            selected_path=download.path(prefix+f'finish/slot-{i:02d}-selected.npz')
            with np.load(selected_path,allow_pickle=False) as z:assert np.array_equal(z['pose'],selected)
            result['native_slots'].append(row);continue
        selected_path=download.path(stem+'.selected.npz')
        assert sha(selected_path)==record['selected_archive_sha256']
        with np.load(selected_path,allow_pickle=False) as z:assert np.array_equal(z['pose'],selected)
        if 'input_sha256' not in record:
            assert record.get('status')!='certified'
            result['native_slots'].append(row);continue
        encoded,offsets=native.fq.encode(selected,math.isqrt(n),math.isqrt(n));assert offsets==[0,0]
        input_path=download.path(stem+'.in');assert input_path.read_bytes()==encoded.encode()
        assert sha(input_path)==record['input_sha256']
        command=record['command'];assert command[-len(native.OPTIONS):]==native.OPTIONS
        assert command[command.index('--seed')+1]=='9710000'
        assert all(command[command.index(option)+1]=='0' for option in ('--rect-dx','--rect-dy'))
        for suffix in ('stdout','stderr','log'):
            if suffix+'_sha256' in record:assert sha(download.path(stem+'.'+suffix))==record[suffix+'_sha256']
        if 'log_sha256' in record:
            assert download.path(stem+'.log').read_bytes()==download.path(stem+'.stdout').read_bytes()+b'\n'+download.path(stem+'.stderr').read_bytes()
        output=None;decoded_output=None
        if 'native_output_sha256' in record:
            output=download.path(stem+'.out');assert sha(output)==record['native_output_sha256']
        for field,suffix in (('raw_returned','raw'),('decoded_returned','decoded')):
            if field not in record:continue
            info=record[field];path=download.path(stem+'.'+suffix+'.npz');assert sha(path)==info['sha256']
            with np.load(path,allow_pickle=False) as z:q=z['pose'].copy()
            assert native.geometry_sha(q)==info['geometry_sha256']
            expected_pose=native._pose_from_output(output,n) if suffix=='raw' else native.fq.decode(output,n)
            assert expected_pose is not None and np.array_equal(q,expected_pose)
            if suffix=='decoded':decoded_output=expected_pose
        if record.get('status')=='certified':
            path=download.path(stem+'.certified.npz');assert sha(path)==record['certified_archive_sha256']
            assert download.json(stem+'.certificate.json')==record
            with np.load(path,allow_pickle=False) as z:pose=z['pose'].copy()
            name=f"n{n}_{record['kind']}_delta{record['delta']}_chain{chain}"
            if name in bank:assert np.array_equal(bank[name],pose)
            elif summary:raise ValueError('Completed aggregate omitted durable certified geometry')
            if decoded_output is None:decoded_output=native.fq.decode(output,n)
            assert native.geometry_sha(pose)==record['geometry_sha256'] and np.array_equal(decoded_output,pose)
            side=certificate_side(pose,record['certificate']);assert str(side)==record['worst_certified_side']
            key=f'native_{n}_{name}';poses[key]=pose;bindings[key]=dict(n=n,side=str(side),certificate=record['certificate'],
                source_stage='native_finish',record=record,archive_sha256=sha(path),terminal_packet_sha256=sha(packet))
            result['certified'].append(key);retained.add(name);row.update(side=str(side),geometry_sha256=record['geometry_sha256'])
        result['native_slots'].append(row)
    assert set(bank)<=retained
    result['recovered_individual_certificate_slots']=recovered
    result['status']='terminal_and_native_verified' if summary else 'partial_native_durable_outputs_verified'
    return result


def analyze(args):
    args.out.mkdir(parents=True,exist_ok=False)
    assert sha(args.job/'search.py')==SOURCE
    nodes=ast.parse((args.job/'search.py').read_text()).body;manifest=ast.literal_eval(nodes[0].value)
    with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(ast.literal_eval(nodes[1].value))))) as z:
        frozen_input=z.read('sustained-inputs.npz')
        assert hashlib.sha256(frozen_input).hexdigest()==manifest['files']['sustained-inputs.npz']
        driver=z.read('experiments/fq_sustained_cold_pilot.py')
        assert hashlib.sha256(driver).hexdigest()==manifest['files']['experiments/fq_sustained_cold_pilot.py']
        queue_node=next(node for node in ast.parse(driver).body if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='QUEUES' for target in node.targets))
        frozen_queues=ast.literal_eval(queue_node.value)
    with np.load(io.BytesIO(frozen_input),allow_pickle=False) as z:frozen_bank={name:z[name].copy() for name in z.files}
    download=Downloaded(args.download);assert download.json('job_manifest.json')==manifest
    config=download.json('sustained-config.json');assert config==manifest['configuration']
    for name,module in [('experiments/fq_restart_hop_finish.py',native),('experiments/fq_active_pilot.py',native.fq)]:
        assert sha(module.__file__)==manifest['files'][name]
    for name in ('experiments/fq_capacity_probe.py','experiments/compose_gadgets.py','experiments/fq_sustained_hop_finish.py',
                 'experiments/packer_hop_physical_energy.py','research/official_metric_v17.py'):
        assert sha(ROOT/name)==manifest['files'][name]
    supervisor=download.json('supervisor-summary.json');pilot=download.json('pilot-summary.json')
    if 'pilot' in supervisor:assert supervisor['pilot']==pilot
    thresholds,pointer=current_thresholds(args.out/'comparison')
    poses={};bindings={};cases={}
    for n in sorted(map(int,config['cases'])):
        published=pilot['case_summaries'][str(n)];prefix=f'case-{n}/'
        for name,value in published.items():assert download.json(prefix+name)==value
        if 'preflight.json' in published:
            for name in ('preflight/preflight.json','preflight/preflight_packings.npz','preflight/preflight_packing_records.json'):
                download.path(prefix+name)
        if published.get('recovery.json',{}).get('completed'):
            for name in ('raw-index.json','chain-design.json','final-current-best.npz','hop-events.jsonl'):
                download.path(prefix+name)
        if 'finish-summary.json' in published:
            for name in ('finish/summary.json','finish/manifest.json','finish/results.json','finish/certified.npz'):
                download.path(prefix+name)
            assert download.json(prefix+'finish/summary.json')==published['finish-summary.json']
        cases[str(n)]=audit_case(download,config,n,poses,bindings,frozen_bank,frozen_queues)
    candidates={}
    for name,row in bindings.items():
        n=row['n'];side=Decimal(row['side']);row['strict_vs_current']=side<thresholds[n]
        if side<thresholds[n] and (str(n) not in candidates or side<Decimal(candidates[str(n)]['side'])):
            candidates[str(n)]=dict(side=str(side),squares=[[f'{v:.17g}' for v in r] for r in poses[name]],
                certificate=row['certificate'],source='Reviewed twelve-case persistent FP64 campaign',
                provenance=dict(archive_key=name,source_sha256=SOURCE,source_stage=row['source_stage'],
                    geometry_sha256=native.geometry_sha(poses[name]),binding=row))
    native.atomic_npz(args.out/'certified.npz',poses);native.atomic_json(args.out/'bindings.json',bindings)
    native.atomic_json(args.out/'candidates.json',candidates)
    report=dict(status='read_only_audit_complete' if pilot['status']=='complete' else 'partial_execution_available_output_audit',source_sha256=SOURCE,analyzer_sha256=sha(__file__),
        receipts=download.receipts,consumed_files=sorted(download.consumed),supervisor=supervisor,
        remote_pilot_status=pilot['status'],case_results=cases,certified=len(poses),improved_cases=list(candidates),
        canonical_raw_sha256=pointer['raw']['sha256'],certified_sha256=sha(args.out/'certified.npz'),
        bindings_sha256=sha(args.out/'bindings.json'),candidates_sha256=sha(args.out/'candidates.json'),
        no_new_certificates=True,no_optimizer=True,no_canonical_mutation=True,no_submission=True)
    native.atomic_json(args.out/'analysis.json',report)
    print(json.dumps({k:report[k] for k in ('status','certified','improved_cases','canonical_raw_sha256')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--download',type=Path,action='append',required=True);parser.add_argument('--out',type=Path,required=True)
    analyze(parser.parse_args())
