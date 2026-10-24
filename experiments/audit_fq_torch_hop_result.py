"""Read-only decisions/selected-array audit of the frozen first GPU hop run."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from packer_hop_physical_energy import physical_energy

ROOT=Path(__file__).resolve().parents[1]
SOURCE='a57ae191b9c61aee32b9a505a963de1bd585dfe815bf103d83e827b067a7e3b1'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    started=time.monotonic();summary_root=ROOT/'artifacts/fq-torch-hop-results-v1';raw_root=ROOT/'artifacts/fq-torch-hop-selected-raw-v1'
    for root in (summary_root,raw_root):
        receipt=json.loads((root/'download-receipt.json').read_text())
        assert receipt['source_sha256']==SOURCE and receipt['private_source_verified']and receipt['version']==1
        for name,record in receipt['files'].items():assert sha(root/'outputs'/name)==record['sha256']
    directory=summary_root/'outputs';raw=raw_root/'outputs';index=json.loads((directory/'raw-index.json').read_text())
    events=[json.loads(line)for line in(directory/'hop-events.jsonl').read_text().splitlines()]
    previous=None;previous_best=None;counts=dict(proposals=0,accepted=0,uphill=0);phases=[];max_link_error=0.
    for ordinal,event in enumerate(events):
        entry=index['packets'][ordinal];assert entry['status']=='completed'and event['packet']==entry
        old,proposal,nxt,best=[np.asarray(event[k])for k in('current_energy','proposal_energy','next_energy','best_energy')]
        base,T,U=[np.asarray(event[k])for k in('base_temperature','temperature','uniform')]
        deadline,decision=event['search_deadline_monotonic'],event['decision_time_monotonic']
        cool=decision>=deadline-60;assert event['temperature_phase']==('cool'if cool else'hot')
        np.testing.assert_array_equal(T,base*(.1 if cool else 1.))
        assert abs(event['decision_elapsed_seconds']-(decision-(deadline-180)))<1e-10
        logratio=np.log(np.maximum(proposal,1e-300))-np.log(np.maximum(old,1e-300));threshold=-T*np.log(np.maximum(U,1e-300))
        accept=(proposal<old)|(logratio<threshold)
        if event['initialization']:accept[:]=True
        if not event['quench_completed']:accept[:]=False
        np.testing.assert_array_equal(accept,event['accepted']);np.testing.assert_array_equal(np.where(accept,proposal,old),nxt)
        uphill=accept&(proposal>old)&~np.full(32,event['initialization'])
        np.testing.assert_array_equal(uphill,event['accepted_uphill'])
        np.testing.assert_allclose(logratio,event['log_ratio'],rtol=0,atol=1e-14)
        np.testing.assert_allclose(threshold,event['threshold'],rtol=0,atol=1e-14)
        if previous is not None:
            error=float(abs(old-previous).max());max_link_error=max(max_link_error,error);assert error<1e-12
        before=old if previous_best is None else previous_best
        np.testing.assert_array_equal(np.minimum.reduce([before,np.asarray(event['input_energy']),proposal]),best)
        if not event['initialization']:
            counts['proposals']+=32;counts['accepted']+=int(accept.sum());counts['uphill']+=int(uphill.sum())
        previous=nxt;previous_best=best;phases.append(event['temperature_phase'])
    assert len(events)==39 and len(index['packets'])==40 and index['packets'][-1]['status']=='pending_quench'
    selected=[];loaded={};max_energy_error=0.
    pairs=(('current_before','current_energy'),('proposal_input','input_energy'),('best_before','best_energy_before'),
           ('proposal_quenched','proposal_energy'),('current_after','next_energy'),('best_after','best_energy_after'))
    for entry in index['packets']:
        path=raw/entry['path']
        if not path.exists():continue
        assert sha(path)==entry['sha256'];z=np.load(path,allow_pickle=False);metadata=json.loads(z['metadata_json'].tobytes())
        arrays={key:z[key].copy()for key in z.files if key!='metadata_json'};loaded[entry['index']]=arrays
        for key,value in arrays.items():assert hashlib.sha256(value.tobytes()).hexdigest()==metadata['array_sha256'][key]
        assert arrays['current_before'].shape==(32,335,3)
        if entry['status']=='completed':
            e=dict(events[entry['index']]);e.pop('packet');assert metadata['event']==e
            accept=arrays['accepted'];np.testing.assert_array_equal(arrays['current_after'],np.where(accept[:,None,None],arrays['proposal_quenched'],arrays['current_before']))
            candidates=(arrays['best_before'],arrays['proposal_input'],arrays['proposal_quenched'])
            choice=np.asarray(e['best_origin_choice']);expected=np.stack([candidates[choice[b]][b]for b in range(32)])
            np.testing.assert_array_equal(arrays['best_after'],expected)
        if not metadata['initialization']:
            for b,move in enumerate(metadata['moves']):
                changed=np.flatnonzero(np.any(arrays['proposal_input'][b]!=arrays['current_before'][b],axis=1)).tolist()
                assert changed==move['changed_ids']and len(changed)==move['changed_count']and len(changed)>0
                assert set(changed)<=set(move['selected_ids'])
        checks=[]
        for pose_name,energy_name in pairs:
            if pose_name not in arrays:continue
            assert arrays[pose_name].shape==(32,335,3)
            errors=[]
            for b in range(32):
                measured=physical_energy(arrays[pose_name][b],arrays['sides'][b])['energy']
                error=abs(measured-float(arrays[energy_name][b]));assert error<1e-11
                errors.append(error);max_energy_error=max(max_energy_error,error)
            checks.append(dict(array=pose_name,full335_chains=32,max_absolute_energy_error=max(errors)))
        selected.append(dict(packet=entry['index'],status=entry['status'],sha256=entry['sha256'],checks=checks))
    np.testing.assert_array_equal(loaded[39]['current_before'],loaded[38]['current_after'])
    np.testing.assert_array_equal(loaded[39]['best_before'],loaded[38]['best_after'])
    with np.load(raw/'final-current-best.npz',allow_pickle=False)as z:
        for name in('current_after','best_after','sides','next_energy','best_energy_after'):np.testing.assert_array_equal(z[name],loaded[38][name])
    result=dict(status='PASS; physical search states remain UNVERIFIED',frozen_source_sha256=SOURCE,
        audit_source_sha256=sha(Path(__file__)),summary_receipt_sha256=sha(summary_root/'download-receipt.json'),
        raw_receipt_sha256=sha(raw_root/'download-receipt.json'),completed_events=len(events),pending_packets=1,
        decision_counts=counts,first_cool_packet=phases.index('cool'),max_consecutive_current_energy_error=max_link_error,
        selected_packet_checks=selected,max_dense_physical_energy_error=max_energy_error,
        pending_pose_equals_last_accepted=True,recovered_final_equals_last_complete=True,
        actual_cooling_uses_search_deadline=True,no_full_geometry_certificates_run=True,seconds=time.monotonic()-started)
    out=ROOT/'artifacts/fq-torch-hop-results-v1/independent-actual-run-audit.json'
    assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k!='selected_packet_checks'},indent=2))


if __name__=='__main__':main()
