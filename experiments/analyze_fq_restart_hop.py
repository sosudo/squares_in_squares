"""Audit the paired restart pilot's recorded state decisions and final outcomes."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from fq_torch_hop import acceptance
from fq_restart_hop_pilot import acceptance_uniforms


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def energy_summary(rows):
    return dict(chains=len(rows), best_min=min(r['best_energy'] for r in rows),
        best_median=float(np.median([r['best_energy'] for r in rows])),
        terminal_to_best_median=float(np.median([r['terminal_to_best'] for r in rows])),
        best_to_initial_quench_median=float(np.median([r['best_to_initial_quench'] for r in rows])))


def analyze_case(root, n):
    folder=root/f'case-{n}'
    read=lambda name:json.loads((folder/name).read_text())
    config=read('case-config.json'); design=read('chain-design.json')
    index=read('raw-index.json'); recovery=read('recovery.json'); status=read('hop-status.json')
    events=[json.loads(line) for line in (folder/'hop-events.jsonl').read_text().splitlines()]
    completed=[p for p in index['packets'] if p['status']=='completed']
    # A kill between atomic packet publication and event publication can leave
    # one extra committed packet. Its event is recoverable from that exact file.
    added_terminal_event=False
    if len(events)+1==len(completed):
        local=folder/completed[-1]['path']
        assert local.is_file() and sha(local)==completed[-1]['sha256']
        with np.load(local,allow_pickle=False) as archive:
            metadata=json.loads(archive['metadata_json'].tobytes())
        events.append(dict(metadata['event'],packet=completed[-1]));added_terminal_event=True
    assert len(events)==len(completed)
    with np.load(folder/'final-current-best.npz',allow_pickle=False) as archive:
        final={key:archive[key] for key in archive.files}
    assert sha(folder/'final-current-best.npz')==recovery['recovered_final_archive_sha256']
    hot_treatment=np.array([r['arm']=='reset' and r['temperature']>.3 for r in design])
    base=np.array([r['temperature'] for r in design]); previous=priorbest=None
    counts={}; quench_seconds=[]; iterations=[]; reset_events=[]; last_periodic=-1
    boundary_seen=False; last_best={}; phases={}; paired_operator_differences=0
    seed=read('hop-config.json')['seed']
    for event,packet in zip(events,completed):
        assert event['packet']==packet
        before=event['before_reset']; after=event['after_reset']
        bm=np.array(before['mask'],bool); am=np.array(after['mask'],bool)
        assert np.array_equal(bm,hot_treatment & bool(before['periodic'] or before['cooling']))
        assert np.array_equal(am,hot_treatment & bool(after['cooling']))
        assert not after['periodic']
        if before['periodic']:
            assert not boundary_seen and event['round']>0 and event['round']%16==0
            assert event['round']!=last_periodic;last_periodic=event['round']
        if before['cooling'] or after['cooling']:
            assert not boundary_seen and not (before['cooling'] and after['cooling'])
            boundary_seen=True
        e=np.array(event['current_energy']); p=np.array(event['proposal_energy'])
        inp=np.array(event['input_energy']); nxt=np.array(event['next_energy'])
        best=np.array(event['best_energy']); pre=np.array(event['pre_reset_energy'])
        if previous is not None:
            assert np.allclose(pre,previous,rtol=1e-12,atol=1e-16)
            assert np.allclose(e,np.where(bm,priorbest,previous),rtol=1e-12,atol=1e-16)
            choices=np.stack((priorbest,inp,p))
            assert np.array_equal(best,choices.min(0))
            assert np.array_equal(event['best_origin_choice'],choices.argmin(0))
        phase='cool' if event['decision_time_monotonic']>=event['search_deadline_monotonic']-150 else 'hot'
        temps=base*(.1 if phase=='cool' else 1)
        assert phase==event['temperature_phase'] and np.array_equal(temps,event['temperature'])
        u=acceptance_uniforms(seed,event['round']);assert np.array_equal(u,event['uniform'])
        accept,_=acceptance(e,p,temps,u)
        if event['initialization']:accept[:]=True
        if not event['quench_completed']:accept[:]=False
        assert np.array_equal(accept,event['accepted'])
        mh=np.where(accept,p,e)
        assert np.array_equal(mh,event['mh_next_energy'])
        assert np.array_equal(nxt,np.where(am,best,mh))
        uphill=accept&(p>e)&~np.full(32,event['initialization'])
        assert np.array_equal(uphill,event['accepted_uphill'])
        record,=event['outer_records'];assert record['steps_requested']==2000 and record['tau']==0
        assert record['compiler_options']==['--std=c++17','--fmad=false']
        quench_seconds.append(record['seconds']);iterations.extend(np.array(record['native_report'])[:,2].tolist())
        if bm.any() or am.any():
            reset_events.append(dict(packet=packet['index'],round=event['round'],phase=phase,
                decision_elapsed_seconds=event['decision_elapsed_seconds'],before=before,after=after))
        if not event['initialization']:
            phases[phase]=phases.get(phase,0)+32
            paired_operator_differences+=sum(event['moves'][i]['operator']!=event['moves'][i+16]['operator'] for i in range(16))
            for i,row in enumerate(design):
                key=f"{row['arm']}/delta{row['delta']}/T{row['temperature']}/{phase}"
                r=counts.setdefault(key,dict(proposals=0,accepted=0,uphill=0,best_updates=0))
                r['proposals']+=1;r['accepted']+=int(accept[i]);r['uphill']+=int(uphill[i])
                r['best_updates']+=int(event['best_origin_choice'][i]!=0)
        for i,choice in enumerate(event['best_origin_choice']):
            if choice:last_best[i]=dict(packet=packet['index'],round=event['round'],phase=phase,
                elapsed_seconds=event['decision_elapsed_seconds'],origin='input' if choice==1 else 'quenched',
                operator=event['moves'][i]['operator'])
        previous=nxt;priorbest=best
    assert np.array_equal(final['next_energy'],previous) and np.array_equal(final['best_energy_after'],priorbest)
    initial=np.array(events[0]['proposal_energy']); chains=[]
    for i,row in enumerate(design):
        b=float(final['best_energy_after'][i]);t=float(final['next_energy'][i])
        chains.append(dict(row,best_energy=b,terminal_energy=t,
            terminal_to_best=t/max(b,1e-300),initial_quenched_energy=float(initial[i]),
            best_to_initial_quench=b/max(float(initial[i]),1e-300),best_origin=last_best.get(i),
            geometry_sha256=hashlib.sha256(final['best_after'][i].tobytes()).hexdigest()))
    groups={f'{arm}/delta{delta}/T{temp}':energy_summary([r for r in chains
        if r['arm']==arm and r['delta']==delta and r['temperature']==temp])
        for arm in ('control','reset') for delta in (.002,.008) for temp in (.3,1.,3.)}
    paired=[dict(pair=i,control_best=chains[i]['best_energy'],reset_best=chains[i+16]['best_energy'],
        reset_over_control=chains[i+16]['best_energy']/max(chains[i]['best_energy'],1e-300)) for i in range(16)]
    finish=read('finish-summary.json'); winners=[];reference=Decimal(config['reference_side'])
    for r in finish['slots']:
        if r.get('status')=='certified':
            side=Decimal(r['worst_certified_side'])
            if side<reference:winners.append(dict(arm=r['arm'],delta=r['delta'],chain=r['chain'],
                side=str(side),side_gain=str(reference-side),score_gain=str((reference-side)/Decimal(n).sqrt()),
                certified_archive=r['certified_archive'],geometry_sha256=r['geometry_sha256']))
    best_side=min([Decimal(r['side']) for r in winners]+[reference])
    return dict(n=n,controls=read('preflight.json'),all_event_decision_checks_passed=True,
        event_count=len(events),terminal_event_recovered_from_packet=added_terminal_event,
        completed_proposals=32*(len(events)-1),complete_proposals_per_second=32*(len(events)-1)/600,
        phase_proposals=phases,quench_seconds=sum(quench_seconds),quench_median_seconds=float(np.median(quench_seconds)),
        native_iteration_median=float(np.median(iterations)),native_iteration_1999_count=int(np.sum(np.array(iterations)==1999)),
        native_iteration_report_count=len(iterations),reset_events=reset_events,cooling_boundary_seen=boundary_seen,
        paired_operator_differences=paired_operator_differences,acceptance_by_arm_delta_temperature_phase=counts,
        chains=chains,groups=groups,paired_best_comparison=paired,
        zero_energy_raw_candidates=status['zero_energy_raw_candidates'],
        hot_storage_pause_seconds=status.get('hot_storage_pause_seconds'),
        raw=dict(completed=len(completed),pending=len(index['packets'])-len(completed),bytes=index['total_bytes'],
            max_bytes=index['max_bytes'],max_packets=index['max_packets'],index_sha256=sha(folder/'raw-index.json')),
        native_finishing=finish['per_arm'],native_finish_statuses=[r.get('status') for r in finish['slots']],
        strict_certified_winners=winners,score_gain=str((reference-best_side)/Decimal(n).sqrt()),
        baseline_sha256=config['baseline_sha256'],reference_side=str(reference),
        final_archive_sha256=sha(folder/'final-current-best.npz'),events_sha256=sha(folder/'hop-events.jsonl'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args();started=time.monotonic();root=args.run/'outputs'
    receipt=json.loads((args.run/'download-receipt.json').read_text());assert receipt['status']=='complete'
    for name,record in receipt['files'].items():assert sha(root/name)==record['sha256']
    cases={str(n):analyze_case(root,n) for n in (453,693)}
    gain=sum(Decimal(r['score_gain']) for r in cases.values())
    result=dict(source_sha256=receipt['source_sha256'],analyzer_sha256=sha(__file__),cases=cases,
        strict_certified_combined_score_gain=str(gain),extension_gain_threshold='0.00001',
        extension_threshold_met=gain>=Decimal('.00001'),analysis_seconds=time.monotonic()-started,
        scope='Recorded energy decisions audited; geometry admission comes only from retained full certificates. Gains compare the frozen baseline, not a later portfolio.')
    (args.run/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(score_gain=str(gain),cases={n:dict(proposals=r['completed_proposals'],
        phase_proposals=r['phase_proposals'],native_finishing=r['native_finishing'],winners=r['strict_certified_winners'])
        for n,r in cases.items()}),indent=2))


if __name__=='__main__':main()
