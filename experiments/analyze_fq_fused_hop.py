"""Read-only event, terminal-energy and throughput audit for the fused pilot."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from fq_torch_hop import acceptance
from packer_hop_physical_energy import physical_energy
from compose_gadgets import legalize


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def group_stats(rows):
    fields=('initial_energy','initial_quenched_energy','best_energy','terminal_energy','terminal_to_best','best_to_initial_quenched')
    result={field+'_median':float(np.median([r[field]for r in rows]))for field in fields}
    return dict(result,chains=len(rows),best_min=min(r['best_energy']for r in rows),
        terminal_to_best_max=max(r['terminal_to_best']for r in rows))


def analyze(folder):
    started=time.monotonic();root=folder/'outputs'
    receipt=json.loads((folder/'download-receipt.json').read_text());assert receipt['status']=='complete'
    for name,row in receipt['files'].items():assert sha(root/name)==row['sha256']
    summary=json.loads((root/'pilot-summary.json').read_text());recovery=summary['recovery']
    design=json.loads((root/'chain-design.json').read_text())
    events=[json.loads(s)for s in(root/'hop-events.jsonl').read_text().splitlines()]
    index=json.loads((root/'raw-index.json').read_text());entries={r['index']:r for r in index['packets']}
    status=json.loads((root/'hop-status.json').read_text())
    with np.load(root/'final-current-best.npz')as z:final={k:z[k]for k in z.files}
    assert sha(root/'final-current-best.npz')==recovery['recovered_final_archive_sha256']
    initial=np.array(events[0]['current_energy']);after_initial=np.array(events[0]['proposal_energy'])
    previous=priorbest=None;phase_counts={};accepted_total=uphill_total=0;best_events={};funnel={};timing=[]
    for i,event in enumerate(events):
        assert event['packet']==entries[i]and event['packet']['status']=='completed'
        e=np.array(event['current_energy']);p=np.array(event['proposal_energy']);n=np.array(event['next_energy'])
        b=np.array(event['best_energy']);temps=np.array(event['temperature']);u=np.array(event['uniform'])
        accepted=np.array(event['accepted'],bool)
        if previous is not None:assert np.allclose(e,previous,rtol=1e-12,atol=1e-16)
        if priorbest is not None:assert np.all(b<=priorbest+1e-16)
        expected,_=acceptance(e,p,temps,u)
        if event['initialization']:expected[:]=True
        if not event['quench_completed']:expected[:]=False
        assert np.array_equal(expected,accepted)and np.allclose(n,np.where(accepted,p,e),rtol=1e-12,atol=1e-16)
        phase='cool'if event['decision_time_monotonic']>=event['search_deadline_monotonic']-60 else'hot'
        factor=.1 if phase=='cool' else 1.
        assert phase==event['temperature_phase']and np.array_equal(temps,np.array(event['base_temperature'])*factor)
        records=event['outer_records'];assert len(records)==1
        r=records[0];assert r['steps_requested']==400 and r['tau']==0 and r['compiler_options']==['--std=c++17','--fmad=false']
        timing.append(r['seconds'])
        if not event['initialization']:
            phase_counts[phase]=phase_counts.get(phase,0)+32;accepted_total+=int(accepted.sum())
            up=np.array(event['accepted_uphill'],bool);assert np.array_equal(up,accepted&(p>e));uphill_total+=int(up.sum())
            for j,row in enumerate(design):
                key=f"T{row['temperature']}/box{row['side']}/{phase}"
                counts=funnel.setdefault(key,dict(proposals=0,accepted=0,uphill=0,best_updates=0))
                counts['proposals']+=1;counts['accepted']+=int(accepted[j]);counts['uphill']+=int(up[j])
                counts['best_updates']+=int(event['best_origin_choice'][j]!=0)
        for j,choice in enumerate(event['best_origin_choice']):
            if choice:best_events[j]=dict(event=i,round=event['round'],elapsed_seconds=event['decision_elapsed_seconds'],
                phase=phase,origin='input'if choice==1 else'quenched',operator=event['moves'][j]['operator'])
        previous=n;priorbest=b
    assert len(events)==recovery['completed']and np.array_equal(final['next_energy'],previous)
    assert np.array_equal(final['best_energy_after'],priorbest)
    chains=[];max_error=0.;repairable=0
    for i,row in enumerate(design):
        q=final['best_after'][i];current=final['current_after'][i];side=final['sides'][i]
        best_e=physical_energy(q,side);current_e=physical_energy(current,side)
        for energy,stored in[(best_e['energy'],final['best_energy_after'][i]),(current_e['energy'],final['next_energy'][i])]:
            error=abs(energy-stored);max_error=max(max_error,error);assert error<1e-12+1e-8*abs(stored)
        repaired=legalize(q);repairable+=int(repaired is not None)
        chains.append(dict(**row,initial_energy=float(initial[i]),initial_quenched_energy=float(after_initial[i]),
            best_energy=best_e['energy'],terminal_energy=current_e['energy'],terminal_to_best=current_e['energy']/best_e['energy'],
            best_to_initial=best_e['energy']/initial[i],best_to_initial_quenched=best_e['energy']/after_initial[i],
            max_pair_overlap=best_e['max_pair_overlap'],max_wall_overlap=best_e['max_wall_overlap'],
            rounding_only_repair_passed=repaired is not None,best_origin=best_events.get(i),geometry_sha256=hashlib.sha256(q.tobytes()).hexdigest()))
    groups={field:{str(value):group_stats([r for r in chains if r[field]==value])
        for value in sorted({r[field]for r in chains},key=str)}for field in('temperature','side','source_key')}
    groups['temperature_and_box']={f'T{t}/box{s}':group_stats([r for r in chains if r['temperature']==t and r['side']==s])
        for t in(.3,1.,3.)for s in(18.807,18.803)}
    quench_seconds=sum(timing);proposals=32*(len(events)-1)
    return dict(source_sha256=receipt['source_sha256'],analyzer_sha256=sha(__file__),
        controls_passed=json.loads((root/'preflight.json').read_text())['passed'],search_parent_epoch_seconds=180.,
        completed_proposals=proposals,complete_proposals_per_second=proposals/180,previous_torch_proposals=1216,
        throughput_ratio=proposals/1216,smoke=json.loads((root/'fused-preflight/smoke/smoke.json').read_text()),
        quench_interface_seconds=quench_seconds,quench_call_median_seconds=float(np.median(timing)),
        quench_call_max_seconds=max(timing),combined_other_epoch_seconds=180-quench_seconds,
        other_time_note='Combined startup,mutation,physical energy,packet publication and control overhead; not separately instrumented.',
        hot_cool_proposals=phase_counts,accepted_proposals=accepted_total,accepted_uphill=uphill_total,
        all_event_ratio_cooling_state_checks_passed=True,all64_final_dense_energy_checks_passed=True,
        max_independent_final_energy_error=max_error,zero_energy_raw_candidates=status['zero_energy_raw_candidates'],
        best_rounding_only_repair_passes=repairable,certified_new_cases=0,chains=chains,groups=groups,
        acceptance_by_temperature_box_phase=funnel,
        raw=dict(completed=recovery['completed'],pending=recovery['pending'],bytes=index['total_bytes'],
            max_packets=index['max_packets'],max_bytes=index['max_bytes'],cap_truncated=False,raw_index_sha256=sha(root/'raw-index.json')),
        final_archive_sha256=sha(root/'final-current-best.npz'),events_sha256=sha(root/'hop-events.jsonl'),
        analysis_seconds=time.monotonic()-started,scope='Physical optimization penalties and raw states; no feasible packing or score gain admission.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
    result=analyze(args.run);(args.run/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in('completed_proposals','quench_interface_seconds','hot_cool_proposals',
        'accepted_proposals','accepted_uphill','max_independent_final_energy_error','best_rounding_only_repair_passes','groups')},indent=2))
