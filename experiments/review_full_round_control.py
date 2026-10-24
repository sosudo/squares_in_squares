#!/usr/bin/env python3
"""Read-only rounded-control audit; reuse exact certificates, never optimize."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from extract_broad_active_frontier import orient
from fq_active_pilot import digest,encode,decode
from fq_variant_campaign import geometry_sha
from fq_bottleneck_campaign import contact_geometry


def raw_csv_sha(p):
    rows=[dict(n=str(len(p)),square_id=str(i),x=f'{x:.17g}',y=f'{y:.17g}',angle=f'{a:.17g}')
          for i,(x,y,a)in enumerate(p)]
    return hashlib.sha256(pd.DataFrame(rows).to_csv(index=False).encode()).hexdigest()


def alignment(p,q):
    best=None;gap,dist=contact_geometry(p)
    for trans in(False,True):
        for sx in(-1,1):
            for sy in(-1,1):
                a=orient(q,trans,sx,sy);a[:,:2]+=p[:,:2].mean(0)-a[:,:2].mean(0)
                _,order=linear_sum_assignment(cdist(p[:,:2],a[:,:2],'sqeuclidean'))
                matched=a[order];residual=np.linalg.norm(p[:,:2]-matched[:,:2],axis=1)
                rms=float(np.sqrt(np.mean(residual**2)))
                if best is not None and rms>=best['rms_center_distance']:continue
                delta=(matched[:,2]-p[:,2]+math.pi/4)%(math.pi/2)-math.pi/4
                new_gap,new_dist=contact_geometry(matched)
                changes={str(t):int(np.count_nonzero(np.triu((gap<=t)&(dist<=1.6),1)!=
                    np.triu((new_gap<=t)&(new_dist<=1.6),1)))for t in(1e-6,1e-5,1e-4,.001)}
                best=dict(d4=[trans,sx,sy],rms_center_distance=rms,max_center_distance=float(residual.max()),
                    median_center_distance=float(np.median(residual)),centers_moving_over_01=int(sum(residual>.1)),
                    max_angle_change_degrees=float(np.degrees(abs(delta).max())),angles_changing_over_1_degree=int(sum(abs(delta)>math.pi/180)),
                    changed_near_contact_edges=changes,matching_is_identity=bool(np.array_equal(order,np.arange(len(p)))),
                    matching=order.tolist())
    return best


def review(root):
    manifest=json.loads((root/'manifest.json').read_text());inputs=np.load(root/'inputs.npz')
    assert digest(root/'inputs.npz')==manifest['input_sha256']
    assert digest(manifest['baseline'])==manifest['baseline_sha256']
    rows=[]
    for path in sorted((root/'strict-stages').glob('*.json')):
        record=json.loads(path.read_text());key=record['key'];p=inputs[key];n=len(p)
        assert geometry_sha(p)==record['parent_geometry_sha256']
        stage=Path(record['stage_archive']);assert digest(stage)==record['stage_archive_sha256']
        bank=np.load(stage);assert len(bank.files)==1;q=bank[bank.files[0]]
        certificate=record['certificate']
        assert certificate['valid']and geometry_sha(q)==record['geometry_sha256']
        assert certificate['raw_csv_sha256']==raw_csv_sha(q)
        command=record['command'];inp=Path(command[command.index('--in')+1]);out=Path(command[command.index('--out')+1])
        text,offsets=encode(p,*map(int,key.split('_')[:2]));assert offsets==[0,0]
        assert inp.read_text()==text and digest(inp)==record['input_sha256']and digest(out)==record['output_sha256']
        assert geometry_sha(decode(out,n))==geometry_sha(q)
        trace=json.loads(out.with_suffix('.radius-trace.json').read_text())
        stdout=out.with_suffix('.native-stdout');stderr=out.with_suffix('.native-stderr')
        assert digest(stdout)==trace['stdout_sha256']and digest(stderr)==trace['stderr_sha256']
        native=json.loads(stdout.read_text().strip().splitlines()[-1]);assert native==record['fq']
        radii=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',stderr.read_text())]
        holds=[float(x)for x in re.findall(r'round r [0-9.eE+-]+ hold ([0-9.eE+-]+)',stderr.read_text())]
        k=int(command[command.index('--round-steps')+1]);power=float(command[command.index('--round-p')+1])
        r0=float(command[command.index('--round-r0')+1]);factor=float(command[command.index('--hold-f')+1])
        expected=[r0*(1-j/k)**power for j in range(1,k+1)]
        assert len(radii)==k and radii[-1]==0. and max(abs(a-b)for a,b in zip(radii,expected))<=5.01e-5
        assert trace['valid']and trace['reported_radii']==radii
        native_round=native['round'];assert native_round['r0']==r0
        assert abs(native_round['s_hold']-native_round['s_soft']*factor)<2e-11
        assert len(holds)==k and max(abs(x-native_round['s_hold'])for x in holds)<5.1e-9
        input_side=float(inp.read_text().splitlines()[0].split()[1]);compressed='--round-compress'in command
        if not compressed:assert abs(native_round['s_soft']-input_side)<1e-11
        rows.append(dict(n=n,source_geometry_sha256=geometry_sha(p),output_geometry_sha256=geometry_sha(q),
            exact_input_row_binding=True,exact_native_output_to_certificate_binding=True,
            compressed_initial_rounding=compressed,requested_radius=r0,input_side=input_side,
            rounded_compressed_side=native_round['s_soft'],actual_hold_side=native_round['s_hold'],hold_factor=factor,
            hold_minus_input_side=native_round['s_hold']-input_side,return_radii=radii,exact_zero_return=True,
            zero_radius_pre_rigid_violation=native_round['viol_hard'],certified_side=certificate['independent_raw']['side_upper'],
            deficit_vs_control_input=float(certificate['independent_raw']['side_upper'])-input_side,
            raw_same_label_max_displacement=float(np.linalg.norm(q[:,:2]-p[:,:2],axis=1).max()),
            D4_unlabeled_comparison=alignment(p,q),certificate_sha256=digest(path),stage_archive_sha256=digest(stage)))
    return dict(run=str(root),manifest_sha256=digest(root/'manifest.json'),fresh_full_certificates=0,
        certified_outputs_checked=len(rows),all_hash_and_schedule_checks_passed=True,results=rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();assert not args.out.exists()
    result=review(args.run);result['review_source_sha256']=digest(Path(__file__))
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k!='results'}),flush=True)
