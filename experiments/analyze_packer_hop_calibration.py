"""Read-only calibration of a completed native hop trace; no optimization/gates."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse
import json
import math
from pathlib import Path
import time
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from fq_active_pilot import digest
from fq_bottleneck_campaign import contact_geometry
from packer_hop_pilot import raw_pose
from review_full_round_control import alignment


def quantiles(values):
    a=np.asarray(values,dtype=float)
    return {'count':len(a),'quantiles':{}if not len(a)else{str(q):float(np.quantile(a,q))for q in (0,.1,.25,.5,.75,.9,.95,1)}}


def analyze(root):
    started=time.monotonic();events=json.loads((root/'events.json').read_text())
    original,_=raw_pose(root/'raw-chain'/events[0]['raw_file'])
    hops=[r for r in events if r['event']=='hop'];accepted=[r for r in hops if r['accepted']]
    uphill=[r for r in hops if r['proposal_energy']>r['before_energy']]
    accepted_uphill=[r for r in uphill if r['accepted']]
    rejected=[r for r in hops if not r['accepted']]
    samples={}
    for name,rows in [('all',hops),('accepted',accepted),('rejected',rejected),('accepted_uphill',accepted_uphill)]:
        samples[name]=dict(proposal_energy=quantiles([r['proposal_energy']for r in rows]),
            relative_energy=quantiles([r['proposal_energy']/r['before_energy']for r in rows]),
            additive_barrier=quantiles([r['proposal_energy']-r['before_energy']for r in rows]),
            log_ratio=quantiles([math.log(max(r['proposal_energy'],1e-300)/max(r['before_energy'],1e-300))for r in rows]))
    baseline_gap,baseline_distance=contact_geometry(original);upper=np.triu_indices(len(original),1)
    states=[];old=original
    for event in events:
        if event['raw_file']=='-':continue
        q,_=raw_pose(root/'raw-chain'/event['raw_file']);centered=q.copy()
        centered[:,:2]+=original[:,:2].mean(0)-centered[:,:2].mean(0)
        _,order=linear_sum_assignment(cdist(original[:,:2],centered[:,:2],'sqeuclidean'))
        matched=centered[order];d=np.linalg.norm(matched[:,:2]-original[:,:2],axis=1)
        angles=(matched[:,2]-original[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
        increment=q.copy();increment[:,:2]+=old[:,:2].mean(0)-increment[:,:2].mean(0)
        _,previous_order=linear_sum_assignment(cdist(old[:,:2],increment[:,:2],'sqeuclidean'))
        increment=increment[previous_order];step=np.linalg.norm(increment[:,:2]-old[:,:2],axis=1)
        step_angle=(increment[:,2]-old[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
        gap,distance=contact_geometry(matched)
        changes={str(t):int(np.count_nonzero(((baseline_gap<=t)&(baseline_distance<=1.6))[upper]!=
            ((gap<=t)&(distance<=1.6))[upper]))for t in(1e-5,1e-4,.001)}
        states.append(dict(event=event['event'],iteration=event['iteration'],kind=event['kind'],raw_file=event['raw_file'],
            energy=event['accepted_energy'],rms_center_distance=float(np.sqrt(np.mean(d*d))),
            max_center_distance=float(d.max()),centers_over_01=int(sum(d>.1)),
            angles_over_1degree=int(sum(abs(angles)>math.pi/180)),max_angle_degrees=float(np.degrees(abs(angles).max())),
            matched_near_contact_changes=changes,matching_is_identity=bool(np.array_equal(order,np.arange(len(q)))),
            incremental_rms=float(np.sqrt(np.mean(step*step))),incremental_max_center=float(step.max()),
            incremental_max_angle_degrees=float(np.degrees(abs(step_angle).max())),
            incremental_angles_over_1degree=int(sum(abs(step_angle)>math.pi/180))))
        old=q
    # The exhaustive per-state matching fixes the initial orientation. Verify a
    # spread plus the largest excursions using the established full D4 matcher.
    sampled=set(np.linspace(0,len(states)-1,min(17,len(states)),dtype=int).tolist())
    for feature in ('rms_center_distance','max_center_distance','max_angle_degrees','angles_over_1degree'):
        sampled.add(max(range(len(states)),key=lambda i:states[i][feature]))
    d4=[]
    for index in sorted(sampled):
        q,_=raw_pose(root/'raw-chain'/states[index]['raw_file']);r=alignment(original,q);r.pop('matching')
        d4.append(dict(index=index,iteration=states[index]['iteration'],comparison=r))
    operator={}
    for kind in range(9):
        rows=[r for r in hops if r['kind']==kind];acc=[r for r in rows if r['accepted']]
        ss=[r for r in states if r['event']=='hop'and r['kind']==kind]
        operator[str(kind)]=dict(proposed=len(rows),accepted=len(acc),uphill=sum(r['proposal_energy']>r['before_energy']for r in acc),
            proposal_ratio=quantiles([r['proposal_energy']/r['before_energy']for r in rows]),
            accepted_uphill_ratio=quantiles([r['proposal_energy']/r['before_energy']for r in acc if r['proposal_energy']>r['before_energy']]),
            largest_cumulative_rms=max((r['rms_center_distance']for r in ss),default=None),
            incremental_rms=quantiles([r['incremental_rms']for r in ss]),
            incremental_max_angle_degrees=quantiles([r['incremental_max_angle_degrees']for r in ss]),
            near_return_count=sum(r['incremental_rms']<.001 and r['incremental_max_angle_degrees']<1 for r in ss))
    sweep={}
    for temperature in(.3,.6,.8,1.,1.5,3.):
        p=np.array([min(1.,math.exp(-math.log(max(r['proposal_energy'],1e-300)/max(r['before_energy'],1e-300))/temperature))for r in uphill])
        sweep[str(temperature)]=dict(expected_accepted_uphill_over_observed_proposals=float(p.sum()),
            probability_ratio2=2**(-1/temperature),probability_ratio10=10**(-1/temperature),
            probability_ratio100=100**(-1/temperature),interpretation='Static conditional diagnostic; a new chain would generate different proposals.')
    return dict(source_sha256=digest(Path(__file__)),input_event_sha256=digest(root/'events.json'),
        source_manifest_sha256=digest(root/'manifest.json'),physical_energy_definition='Unordered pair penetration squared plus four wall violations squared; unit squares.',
        native_temperature=.3,native_amplitude=1.,acceptance='P(uphill)=exp(-log(Eproposal/Ecurrent)/T)',
        energy_statistics=samples,operator_outcomes=operator,states=states,d4_sample=d4,
        state_summary={feature:quantiles([r[feature]for r in states])for feature in
            ('rms_center_distance','max_center_distance','angles_over_1degree','max_angle_degrees')},
        state_bins={'rms_below_001':sum(r['rms_center_distance']<.001 for r in states),
            'rms_below_01':sum(r['rms_center_distance']<.01 for r in states),
            'rms_over_05':sum(r['rms_center_distance']>.05 for r in states),
            'no_angles_over_1degree':sum(r['angles_over_1degree']==0 for r in states)},
        counterfactual_temperature_sweep=sweep,elapsed_seconds=time.monotonic()-started,
        conclusions_scope='Geometry distances and thresholded contacts, not an unlabeled topology classification or physical feasibility proof.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();assert not args.out.exists()
    result=analyze(args.run);args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k not in ('states','d4_sample')},indent=2))
