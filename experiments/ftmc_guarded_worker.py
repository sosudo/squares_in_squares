"""Explicit local adapter: admit only active-chain-compatible FTMC variants.

The vendored solver and its official metric remain unchanged. This wrapper adds
a conservative separator-profile admission condition after rectangular polishing
and before the upstream worker can update its incumbent or archive.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import gpu_ftmc_refill as upstream
from ftmc_profile_guard import compatible_uses


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--device',type=int,default=0)
    ap.add_argument('--seconds',type=float,default=900)
    ap.add_argument('--replicas',type=int,default=128)
    ap.add_argument('--seed',type=int,default=0)
    a=ap.parse_args()
    targets=json.loads(Path('active_targets.json').read_text())
    incumbents=json.loads(Path('campaign_incumbents.json').read_text())
    with np.load('artifacts/night_seed_gadgets.npz')as z:
        for key in z.files:
            w,h,d=map(int,key.split('_'))
            assert len(compatible_uses(z[key],w,h,targets))==len(targets[key]['uses']),('Incompatible active seed',key)
    stats={'polished_candidates':0,'compatible_candidates':0,'incompatible_rejected':0,
           'incompatible_certified_retained':0,'incompatible_official_rejected':0}
    rejected_bank={}
    original_lp=upstream.rect_lp;original_json=upstream.atom_json

    def guarded_lp(p,w,h,rounds=3):
        q=original_lp(p,w,h,rounds)
        if q is None:return None
        stats['polished_candidates']+=1
        key=f'{w}_{h}_{len(q)-w*h}'
        if len(compatible_uses(q,w,h,targets))!=len(targets[key]['uses']):
            stats['incompatible_rejected']+=1
            # Keep valid new topologies for later composition without allowing
            # them to displace this arm's separator-compatible incumbent.
            f=upstream.excess(q,w,h)
            if f<incumbents[key]-2e-7 and upstream.gaps(q)>1e-10:
                name=key+'__'+upstream.fingerprint(q)
                old=rejected_bank.get(name)
                if old is None or f<upstream.excess(old,w,h)-2e-7:
                    if upstream.certify(q):
                        rejected_bank[name]=q.copy()
                        stats['incompatible_certified_retained']=len(rejected_bank)
                    else:stats['incompatible_official_rejected']+=1
            return None
        stats['compatible_candidates']+=1
        return q

    def tracked_json(path,value):
        if str(path).endswith(f'worker{a.device}_status.json'):
            value={**value,'profile_guard':dict(stats)}
            upstream.atom_npz(f'artifacts/worker{a.device}_incompatible_gadgets.npz',rejected_bank)
        original_json(path,value)

    upstream.rect_lp=guarded_lp
    upstream.atom_json=tracked_json
    try:upstream.worker(a.device,a.seconds,a.replicas,a.seed)
    finally:
        upstream.atom_npz(f'artifacts/worker{a.device}_incompatible_gadgets.npz',rejected_bank)
        original_json(f'research/worker{a.device}_profile_guard.json',stats)


if __name__=='__main__':main()
