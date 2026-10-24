"""Real GPU capacity boundary checks before targeted search workers start."""
import json
from pathlib import Path
import numpy as np


def check(device,config):
    import cupy as cp
    import gpu_ftmc_refill as upstream
    import gpu_rect_explore as fast
    import gpu_rect_optimizer as exact
    from ftmc_targeted_mutations import make_mutations
    cp.cuda.Device(device).use()
    core=np.array([[(i%16)+.5,(i//16)+.5,.02]for i in range(256)],dtype=float)
    packed,counts=upstream.refill_batch(core[None],16,16,.9,258,soft=.008)
    cp.cuda.Stream.null.synchronize();capacity=cp.asnumpy(counts)
    assert packed.shape==(2,258,3)and capacity.shape==(2,)and np.all((capacity>=256)&(capacity<=258))
    rejected=False
    try:upstream.refill_batch(np.resize(core,(1,257,3)),16,16,.9,258,soft=.008)
    except AssertionError:rejected=True
    assert rejected,'257-core input must be rejected before kernel launch'
    boxes=np.array([[16.9,16.9]])
    for label,solver in [('fp32',fast.quench),('fp64',exact.quench)]:
        q,out=solver(core[None],boxes,steps=3)
        assert q.shape==(1,256,3)and np.isfinite(cp.asnumpy(out)).all()
    with np.load(f'prepared_bank_device{device}.npz',allow_pickle=False)as z:
        bank={key:z[key]for key in z.files}
    fn,audit=make_mutations(upstream,config);actual={}
    for key,p in bank.items():
        w,h,d=map(int,key.split('_'));mask=abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018
        mode_counts={}
        for mode in range(6):
            seeds,_,_=fn(p,w,h,d,np.random.default_rng(64000+mode),2,mode,[p])
            assert all(4<=len(q)<=256 for q in seeds)
            if mode==0:assert seeds,'Actual family silently inactive'
            mode_counts[str(mode)]=len(seeds)
        _,count=upstream.refill_batch(p[mask][None],w,h,min(.995,upstream.excess(p,w,h)+.035),len(p),soft=.008)
        cp.cuda.Stream.null.synchronize();assert cp.asnumpy(count).shape==(2,)
        actual[key]={'squares':len(p),'tilted_core':int(mask.sum()),'mutation_rows_by_mode':mode_counts}
    largest=max(bank.values(),key=len);w,h,_=map(int,max(bank,key=lambda key:len(bank[key])).split('_'))
    f=upstream.excess(largest,w,h);box=np.array([[w+f+.001,h+f+.001]])
    for solver in (fast.quench,exact.quench):
        q,out=solver(largest[None],box,steps=3)
        assert q.shape==(1,len(largest),3)and np.isfinite(cp.asnumpy(out)).all()
    original_large=[]
    with np.load('original_target_references.npz',allow_pickle=False)as z:
        for key in z.files:
            p=z[key];mask=abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018
            if mask.sum()<=192:continue
            w,h,_=map(int,key.split('_'));loose=min(.995,upstream.excess(p,w,h)+.035)
            _,counts=upstream.refill_batch(p[mask][None],w,h,loose,len(p),soft=.008)
            cp.cuda.Stream.null.synchronize();assert cp.asnumpy(counts).shape==(2,)
            original_large.append({'key':key,'tilted_core':int(mask.sum())})
    return {'passed':True,'row_capacity':256,'core257_rejected':True,'row256_capacities':capacity.tolist(),
            'optimizer256_fp32_fp64':True,'largest_actual_full_count':len(largest),
            'original_over192_references_checked':original_large,
            'all_actual_families':actual,'mutations_audit':audit,
            'note':'Synthetic boundary poses are memory/shape tests, not geometry certificates or search admissions.'}
