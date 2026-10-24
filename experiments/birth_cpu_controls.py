"""One-worker, <=85s mixed-size mathematical and nontrivial birth controls."""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import hashlib
import argparse
import json
import math
from pathlib import Path
import signal
import time
import unittest
import numpy as np
import torch
from birth_continuation import cpu_quench,numpy_oracle
from compose_gadgets import legalize
from fq_capacity_probe import full_certificate,atomic_json,geometry_sha

class Deadline(BaseException):pass
def expired(signum,frame):raise Deadline('85-second control deadline')

def main():
    signal.signal(signal.SIGALRM,expired);signal.alarm(85)
    start=time.monotonic();torch.set_num_threads(1)
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'artifacts/birth-cpu-controls-v2')
    args=parser.parse_args();out=args.out;out.mkdir(exist_ok=False)
    source={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()for p in
        (Path(__file__),root/'experiments/birth_continuation.py',root/'tests/test_birth_continuation.py',
         root/'experiments/fq_capacity_probe.py',root/'research/official_metric_v17.py')}
    suite=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_birth_continuation.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful()
    p=np.array([[.55,.55,0.],[2.17,.55,0.],[.55,2.17,0.],[2.17,2.17,0.],[1.36,1.36,math.pi/4]])
    original=p.copy();stages=[];arrays={'initial':p.copy()}
    for index,size in enumerate((.05,.2,.4,.6,.8,1.)):
        before=numpy_oracle(p,[2.72,2.72],size)
        p,record=cpu_quench(p,[2.72,2.72],size)
        after=numpy_oracle(p,[2.72,2.72],size)
        assert after['unit_sizes'][:-1]==[1.]*4
        stages.append(dict(size=size,before=before,after=after,optimizer=record,
                           geometry_sha256=geometry_sha(p),admissible_stage=size==1.))
        arrays[f'stage_{index}']=p.copy()
    arrays['certified_final']=legalize(p.copy(),clearance=2e-9)
    cert=full_certificate(arrays['certified_final']);assert cert['valid']
    movement=float(np.linalg.norm(p[:4,:2]-original[:4,:2],axis=1).max())
    assert movement>.02
    np.savez_compressed(out/'states.npz',**arrays)
    report=dict(passed=True,seconds=time.monotonic()-start,maximum_seconds=85,workers=1,
                tests_run=result.testsRun,source_sha256=source,stages=stages,
                initial_full_size_energy=numpy_oracle(original,[2.72,2.72],1.)['energy'],
                existing_unit_max_center_movement=movement,full_final_certificate=cert,
                final_geometry_sha256=geometry_sha(arrays['certified_final']),
                states_sha256=hashlib.sha256((out/'states.npz').read_bytes()).hexdigest(),
                scope='Mixed sizes are proposal-only. Only final lambda=1 has full unit-square certificates. '
                'Existing units remain size1 and are required to move. No cross-size energy comparisons or optimizer histories.')
    atomic_json(out/'report.json',report);signal.alarm(0)
    print(json.dumps({k:report[k]for k in ('passed','seconds','tests_run','existing_unit_max_center_movement','initial_full_size_energy')}),flush=True)

if __name__=='__main__':main()
