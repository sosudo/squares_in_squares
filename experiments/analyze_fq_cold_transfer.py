"""Read-only cold-chain decision audit and full-certificate candidate handoff."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from fq_torch_hop import acceptance
from fq_cold_transfer_pilot import acceptance_uniforms,design


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze_case(folder):
    read=lambda name:json.loads((folder/name).read_text())
    config=read('case-config.json');n=config['n'];rows=read('chain-design.json')
    assert rows==design(n,config['reference_side'],config['source_key'])
    hop=read('hop-config.json');events=[json.loads(line)for line in(folder/'hop-events.jsonl').read_text().splitlines()]
    index=read('raw-index.json');completed=[r for r in index['packets']if r['status']=='completed']
    recovery=read('recovery.json');status=read('hop-status.json')
    if len(events)+1==len(completed):
        entry=completed[-1];path=folder/entry['path'];assert sha(path)==entry['sha256']
        with np.load(path,allow_pickle=False)as archive:meta=json.loads(archive['metadata_json'].tobytes())
        events.append(dict(meta['event'],packet=entry))
    assert len(events)==len(completed)
    previous=priorbest=None;counts={};times=[];iterations=[];last_best={}
    for event,entry in zip(events,completed):
        assert event['packet']==entry
        for key in('before_reset','after_reset'):
            assert not any(event[key]['mask'])and not event[key]['periodic']and not event[key]['cooling']
        current=np.array(event['current_energy']);proposal=np.array(event['proposal_energy']);inp=np.array(event['input_energy'])
        nxt=np.array(event['next_energy']);best=np.array(event['best_energy']);uniform=np.array(event['uniform'])
        assert np.array_equal(current,event['pre_reset_energy'])
        if previous is not None:
            assert np.allclose(current,previous,rtol=1e-12,atol=1e-16)
            choices=np.stack((priorbest,inp,proposal))
            assert np.array_equal(best,choices.min(0))and np.array_equal(event['best_origin_choice'],choices.argmin(0))
        assert np.array_equal(uniform,acceptance_uniforms(hop['seed'],event['round']))
        phase='cool'if event['decision_time_monotonic']>=event['search_deadline_monotonic']-150 else'hot'
        temperatures=np.full(32,.3)*(.1 if phase=='cool' else 1.)
        assert phase==event['temperature_phase']and np.array_equal(temperatures,event['temperature'])
        accepted,_=acceptance(current,proposal,temperatures,uniform)
        if event['initialization']:accepted[:]=True
        if not event['quench_completed']:accepted[:]=False
        assert np.array_equal(accepted,event['accepted'])
        assert np.array_equal(nxt,np.where(accepted,proposal,current))and np.array_equal(nxt,event['mh_next_energy'])
        uphill=accepted&(proposal>current)&~np.full(32,event['initialization'])
        assert np.array_equal(uphill,event['accepted_uphill'])
        report,=event['outer_records'];assert report['steps_requested']==2000 and report['tau']==0
        assert report['compiler_options']==['--std=c++17','--fmad=false']
        times.append(report['seconds']);iterations.extend(np.array(report['native_report'])[:,2].tolist())
        if not event['initialization']:
            for i,row in enumerate(rows):
                key=f"delta{row['delta']}/amplitude{row['amplitude']}/{phase}"
                r=counts.setdefault(key,dict(proposals=0,accepted=0,uphill=0,best_updates=0))
                r['proposals']+=1;r['accepted']+=int(accepted[i]);r['uphill']+=int(uphill[i]);r['best_updates']+=int(event['best_origin_choice'][i]!=0)
        for i,choice in enumerate(event['best_origin_choice']):
            if choice:last_best[i]=dict(packet=entry['index'],round=event['round'],phase=phase,
                elapsed_seconds=event['decision_elapsed_seconds'],origin='input'if choice==1 else'quenched',operator=event['moves'][i]['operator'])
        previous=nxt;priorbest=best
    assert sha(folder/'final-current-best.npz')==recovery['recovered_final_archive_sha256']
    with np.load(folder/'final-current-best.npz',allow_pickle=False)as archive:final={k:archive[k]for k in archive.files}
    assert np.array_equal(final['next_energy'],previous)and np.array_equal(final['best_energy_after'],priorbest)
    chains=[]
    for i,row in enumerate(rows):
        best=float(priorbest[i]);initial=float(events[0]['proposal_energy'][i])
        chains.append(dict(row,best_energy=best,current_energy=float(previous[i]),
            best_to_initial_quench=best/max(initial,1e-300),current_to_best=float(previous[i])/max(best,1e-300),
            best_origin=last_best.get(i),geometry_sha256=hashlib.sha256(final['best_after'][i].tobytes()).hexdigest()))
    finish=read('finish-summary.json');candidates={};reference=Decimal(config['reference_side'])
    assert sha(folder/'finish/results.json')==finish['results_sha256']
    assert sha(folder/'finish/certified.npz')==finish['certified_archive_sha256']
    with np.load(folder/'finish/certified.npz',allow_pickle=False)as bank:
        for record in finish['slots']:
            if record.get('status')!='certified':continue
            side=Decimal(record['worst_certified_side'])
            if side>=reference:continue
            key=f"n{n}_{record['kind']}_delta{record['delta']}_chain{record['chain']}";q=bank[key]
            assert q.shape==(n,3)and hashlib.sha256(q.tobytes()).hexdigest()==record['geometry_sha256']
            assert record['certificate']['valid']
            candidate=dict(side=str(side),squares=[[f'{v:.17g}'for v in row]for row in q],certificate=record['certificate'],
                source='Independent persistent cold full-pose GPU transfer with fixed native finish',
                provenance=dict(geometry_sha256=record['geometry_sha256'],native_output_sha256=record['native_output_sha256'],
                    finish_manifest_sha256=finish['manifest_sha256'],selected_chain=record['chain'],selection_kind=record['kind']))
            if str(n)not in candidates or side<Decimal(candidates[str(n)]['side']):candidates[str(n)]=candidate
    bestside=Decimal(candidates[str(n)]['side'])if str(n)in candidates else reference
    returned_sides=[Decimal(r['worst_certified_side'])for r in finish['slots']if r.get('status')=='certified']
    cooled=[event for event in events if event['temperature_phase']=='cool']
    timing=dict(requested_parent_search_seconds=600,reported_child_seconds=status['seconds'],
        reported_child_search_seconds=status['search_seconds'],
        first_committed_decision_parent_elapsed=events[0]['decision_elapsed_seconds'],
        last_committed_decision_parent_elapsed=events[-1]['decision_elapsed_seconds'],
        first_cooled_decision_parent_elapsed=cooled[0]['decision_elapsed_seconds']if cooled else None,
        last_cooled_decision_parent_elapsed=cooled[-1]['decision_elapsed_seconds']if cooled else None,
        observed_cooled_decision_span=cooled[-1]['decision_time_monotonic']-cooled[0]['decision_time_monotonic'] if cooled else 0,
        cooling_boundary_to_last_completed_decision=cooled[-1]['decision_elapsed_seconds']-450 if cooled else 0,
        note='Parent allocation includes child startup. Deadline kills retained pending work; observed commits do not imply600s of child search or all150s cooling.')
    result=dict(n=n,all_recorded_decisions_checked=True,controls=read('preflight.json'),timing=timing,
        completed_proposals=32*(len(events)-1),complete_proposals_per_second=32*(len(events)-1)/600,
        throughput_denominator='Requested600s parent epoch, including child startup and interrupted final work.',
        quench_seconds=sum(times),quench_median_seconds=float(np.median(times)),
        native_iteration_1999_count=int(np.sum(np.array(iterations)==1999)),native_report_count=len(iterations),
        funnel=counts,chains=chains,hot_storage_pause_seconds=status['hot_storage_pause_seconds'],
        zero_energy_raw_candidates=status['zero_energy_raw_candidates'],raw=dict(completed=len(completed),
            pending=len(index['packets'])-len(completed),bytes=index['total_bytes'],index_sha256=sha(folder/'raw-index.json')),
        finish_statuses=[r.get('status')for r in finish['slots']],certified=finish['certified'],
        score_gain=str((reference-bestside)/Decimal(n).sqrt()),reference_side=str(reference),best_retained_side=str(bestside),
        best_new_certified_side=str(min(returned_sides))if returned_sides else None,
        final_archive_sha256=sha(folder/'final-current-best.npz'),events_sha256=sha(folder/'hop-events.jsonl'))
    return result,candidates


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);args=parser.parse_args()
    started=time.monotonic();root=args.run/'outputs';receipt=json.loads((args.run/'download-receipt.json').read_text())
    assert receipt['status']=='complete'
    for name,record in receipt['files'].items():assert sha(root/name)==record['sha256']
    cases={};candidates={}
    for n in(803,861):cases[str(n)],new=analyze_case(root/f'case-{n}');candidates.update(new)
    (args.run/'candidates.json').write_text(json.dumps(candidates,indent=2)+'\n')
    result=dict(source_sha256=receipt['source_sha256'],analyzer_sha256=sha(__file__),cases=cases,
        combined_score_gain=str(sum(Decimal(r['score_gain'])for r in cases.values())),
        candidate_cases=list(candidates),candidates_sha256=sha(args.run/'candidates.json'),seconds=time.monotonic()-started,
        scope='Independent exploratory chains, not causal arm comparison; only full-certificate sides form candidates, against frozen baseline.')
    (args.run/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(score_gain=result['combined_score_gain'],candidate_cases=list(candidates),
        cases={n:{k:r[k]for k in('completed_proposals','quench_seconds','certified','finish_statuses','best_new_certified_side','score_gain')}for n,r in cases.items()}),indent=2))


if __name__=='__main__':main()
