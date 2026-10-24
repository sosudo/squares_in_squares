"""Small geometry/endpoint controls complementing the native gradient oracle."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import torch
from fq_torch_objective import constraints, initial_lines, near_pairs, guard_pair_list
from check_fq_torch_objective import dense_overlaps


def evaluate(p, side, radius):
    pairs=near_pairs(p)
    return constraints(torch.tensor(p[None],dtype=torch.float64),
                       torch.tensor([side],dtype=torch.float64),
                       torch.tensor(initial_lines(p,pairs,radius)[None],dtype=torch.float64),
                       torch.tensor(pairs,dtype=torch.long),radius=radius)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1)
    source=Path('artifacts/fq-torch-objective-v1/references.npz')
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    assert sha(source)=='ddadbf2e94f9f598018b0e6a484c82fa954e42f8c29c07710574ad5f56562b9e'
    controls=[]
    with np.load(source,allow_pickle=False)as bank:
        for name in bank.files:
            p=bank[name].copy()
            extent=.5*(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))
            p[:,:2]-=(p[:,:2]-extent[:,None]).min(0)
            side=float((p[:,:2]+extent[:,None]).max()+1e-10)
            wall,pair=evaluate(p,side,0.)
            assert float(wall.max())<2e-12 and float(pair.max())<2e-12
            assert not dense_overlaps(p)
            original=[v.numpy().tobytes()for v in(wall,pair)]
            evaluate(p,side,.25)
            returned=evaluate(p,side,0.)
            assert original==[v.numpy().tobytes()for v in returned]
            bad=p.copy();bad[0,0]-=side
            negative_wall=evaluate(bad,side,0.)[0]
            assert float(negative_wall.max())>.1
            controls.append(dict(n=int(name),positive_max_wall=float(wall.max()),
                                 positive_max_pair=float(pair.max()),dense_no_overlap=True,
                                 exactly_zero_radius_return_byte_equal=True,wall_negative_detected=True))
    # Demonstrate the reason a list guard must precede every trial. Both
    # centers cross skin/2 and a previously omitted pair then truly overlaps.
    p=np.array([[2.,2.,math.pi/4],[2.+math.sqrt(2)+.302,2.,math.pi/4]])
    assert len(near_pairs(p,.3))==0
    safe=p.copy();safe[0,0]+=.149;safe[1,0]-=.149
    guard_pair_list(p,safe,.3);assert not dense_overlaps(safe)
    bad=p.copy();bad[0,0]+=.16;bad[1,0]-=.16
    assert dense_overlaps(bad)=={(0,1)}
    try:guard_pair_list(p,bad,.3)
    except ValueError:pass
    else:raise AssertionError('New omitted collision escaped the trial guard')
    report=dict(status='geometry_controls_passed',cases=controls,
                adversarial_new_omitted_pair_collision_rejected_before_evaluation=True,
                hashes={str(p):sha(p)for p in(source,Path(__file__),Path('experiments/fq_torch_objective.py'),
                                           Path('experiments/check_fq_torch_objective.py'))},
                no_search=True,no_gpu=True,no_fresh_official_certificate=True)
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
