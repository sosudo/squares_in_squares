"""Targeted continuation of the certified combined FTMC worker."""
import argparse
import json
from pathlib import Path
import signal
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',type=int,default=0);parser.add_argument('--seconds',type=float,default=2700)
    parser.add_argument('--replicas',type=int,default=96);parser.add_argument('--seed',type=int,default=0)
    args=parser.parse_args()
    import numpy as np
    import gpu_ftmc_refill as upstream
    from ftmc_targeted_mutations import make_mutations,install_policy
    from ftmc_anchor_mutations import install_anchor_mutations
    from ftmc_funnel_metrics import install_metrics
    from ftmc_refill_budget import GeneralRefillBudget
    from ftmc_certified_archive import CertifiedArchive
    from ftmc_exploratory_archive import ExploratoryArchive
    config=json.loads(Path('targeted_protocols.json').read_text())[str(args.device)]
    upstream.cp.cuda.Device(args.device).use()
    original_rows,original_refill=upstream.refill_batch,upstream.refill
    original_json,original_npz=upstream.atom_json,upstream.atom_npz
    upstream.mutations,mutation_audit=make_mutations(upstream,config)
    anchor_audit=install_anchor_mutations(upstream,enabled=True,policy=config['anchor_policy'])
    metrics=install_metrics(upstream,f'research/combined_funnel_device{args.device}.json')
    policy=GeneralRefillBudget(upstream,original_rows,max_fraction=config['refill_fraction'],attempt_seconds=.5,
        startup_credit_seconds=0.,deficit_margin=config['refill_deficit_margin'],
        output_path=f'research/combined_refill_budget_device{args.device}.json')
    upstream.refill=policy.wrap_refill(original_refill)
    keeper=CertifiedArchive(f'artifacts/certified_device{args.device}',certify=upstream.certify,
        fingerprint=upstream.fingerprint,flush_seconds=30)
    exploratory=ExploratoryArchive(upstream,policy,f'artifacts/exploratory_device{args.device}').install()
    state={'bank':None,'wins':None,'path':None,'last_npz':-float('inf'),'last_json':-float('inf'),
           'status_path':None,'status':None}
    def checkpoint(bank,wins,path):
        state.update(bank=bank,wins=wins,path=path);keeper.flush(bank=bank)
        if time.monotonic()-state['last_npz']>=30:
            original_npz(path,wins);state['last_npz']=time.monotonic()
    def checkpoint_json(path,value):
        if str(path).endswith(f'worker{args.device}_status.json'):
            state.update(status_path=path,status=value)
            if time.monotonic()-state['last_json']<15:return
            state['last_json']=time.monotonic();metrics.flush();policy.flush();exploratory.flush()
        return original_json(path,value)
    signal.signal(signal.SIGTERM,lambda signum,frame:(_ for _ in()).throw(SystemExit('Bounded FTMC stopped')))
    upstream.atom_json=checkpoint_json
    worker_audit=install_policy(upstream,keeper,policy,checkpoint,config)
    with np.load(f'artifacts/device{args.device}_initial_bank.npz',allow_pickle=False)as z:
        actual={key:{'count':len(z[key]),'tilted_core':int(np.sum(abs((z[key][:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018))}
                for key in z.files}
    if any(not 4<=record['tilted_core']<=256 for record in actual.values()):raise ValueError('Unsupported actual core')
    Path(f'policy_device{args.device}.json').write_text(json.dumps({'mutations':mutation_audit,
        'anchors':anchor_audit,'worker':worker_audit,'actual_active_families':actual},indent=2)+'\n')
    print(json.dumps({'stage':'targeted_active_families','device':args.device,'families':actual,'protocol':config}),flush=True)
    try:upstream.worker(args.device,args.seconds,args.replicas,args.seed)
    finally:
        keeper.finalflush(bank=state['bank'])
        if state['path']is not None:original_npz(state['path'],state['wins'])
        if state['status_path']is not None:original_json(state['status_path'],state['status'])
        policy.flush();exploratory.restore();metrics.restore()
        upstream.refill=original_refill;upstream.atom_json=original_json


if __name__=='__main__':main()
