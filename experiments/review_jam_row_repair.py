"""Read-only exact lineage/radius audit and finite D4 geometry comparisons."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
import json
from pathlib import Path
import re
import time
import numpy as np
from fq_active_pilot import digest,encode,decode
from fq_variant_campaign import atomic_json,geometry_sha
from review_full_round_control import alignment,raw_csv_sha

ROOT=Path(__file__).resolve().parents[1]


def review(root,out):
    started=time.monotonic()
    if out.exists():raise ValueError('Fresh review output required')
    manifest=json.loads((root/'manifest.json').read_text());records=json.loads((root/'results.json').read_text())
    assert digest(manifest['source'])==manifest['source_sha256']
    assert digest(Path(manifest['source']).with_name('report.json'))==manifest['proof_sha256']
    for path,expected in manifest['helpers'].items():assert digest(ROOT/path)==expected
    references={};bindings={}
    path=ROOT/'artifacts/jam-row-evacuation-v1/source335.npz'
    with np.load(path)as z:references['current_44']=z['source335'].copy()
    bindings['current_44']=dict(path=str(path),archive_sha256=digest(path),geometry_sha256=geometry_sha(references['current_44']))
    fixture=ROOT/'artifacts/fq-torch-hop-inputs-v1';config=json.loads((fixture/'pilot-config.json').read_text())
    assert digest(fixture/'pilot-inputs.npz')==config['inputs_sha256']
    with np.load(fixture/'pilot-inputs.npz')as z:
        for key in ('source_43','source_37'):
            p=z[key].copy();assert geometry_sha(p)==config['arrays'][key]['sha256'];references[key]=p
            bindings[key]=dict(path=str(fixture/'pilot-inputs.npz'),archive_sha256=config['inputs_sha256'],
                               config_sha256=digest(fixture/'pilot-config.json'),geometry_sha256=geometry_sha(p))
    inputs=np.load(root/'unverified-inputs.npz');assert digest(root/'unverified-inputs.npz')==manifest['input_sha256']
    details=[]
    for record in records:
        p=inputs[record['raw_source_key']]
        assert geometry_sha(p)==record['parent_geometry_sha256']==manifest['input_geometry_sha256'][record['raw_source_key']]
        stage=Path(record['stage_archive']);assert digest(stage)==record['stage_archive_sha256']
        frozen=json.loads(stage.with_suffix('.json').read_text())
        with np.load(stage)as z:
            assert len(z.files)==1;q=z[z.files[0]].copy()
        assert q.shape==(335,3) and geometry_sha(q)==record['geometry_sha256']==frozen['geometry_sha256']
        assert record['certificate']==frozen['certificate'] and record['certificate']['valid']
        assert record['certificate']['raw_csv_sha256']==raw_csv_sha(q)
        command=record['command'];inp=Path(command[command.index('--in')+1]);dst=Path(command[command.index('--out')+1])
        expected,offsets=encode(p,18,18);assert offsets==[0,0] and inp.read_text()==expected
        assert digest(inp)==record['input_sha256'] and digest(dst)==record['output_sha256']
        assert geometry_sha(decode(dst,335))==geometry_sha(q)
        trace=json.loads(dst.with_suffix('.radius-trace.json').read_text())
        stdout=dst.with_suffix('.native-stdout');stderr=dst.with_suffix('.native-stderr')
        assert digest(stdout)==trace['stdout_sha256'] and digest(stderr)==trace['stderr_sha256']
        native=json.loads(stdout.read_text().strip().splitlines()[-1]);assert native==record['fq']
        radii=[float(x)for x in re.findall(r'round r ([0-9.eE+-]+) hold',stderr.read_text())]
        holds=[float(x)for x in re.findall(r'round r [0-9.eE+-]+ hold ([0-9.eE+-]+)',stderr.read_text())]
        assert trace['valid'] and trace['reported_radii']==radii and record['actual_reported_radii']==radii
        assert len(radii)==12 and radii[-1]==0. and max(abs(a-.49*(1-j/12))for j,a in enumerate(radii,1))<5.01e-5
        initial=float(inp.read_text().splitlines()[0].split()[1]);info=native['round']
        assert abs(info['s_soft']-initial)<1e-10 and abs(info['s_hold']-initial)<1e-10
        assert len(holds)==12 and max(abs(h-initial)for h in holds)<5.1e-9
        angle=q[:,2]%(np.pi/2);degrees=np.degrees(np.minimum(angle,np.pi/2-angle))
        bins=[0.,.01,.1,1.,5.,10.,20.,30.,45.00000001]
        comparisons={}
        for key,ref in references.items():
            comparison=alignment(ref,q);comparison.pop('matching',None);comparisons[key]=comparison
        details.append(dict(source_key=record['raw_source_key'],stage_archive=str(stage),
            stage_archive_sha256=digest(stage),certificate_record_sha256=digest(stage.with_suffix('.json')),
            geometry_sha256=geometry_sha(q),raw_csv_sha256=raw_csv_sha(q),
            terminal_official_side=record['terminal_official_side'],side_gain_vs_current=record['side_gain_vs_current'],
            all_exact_input_output_certificate_bindings=True,actual_initial_side=initial,actual_hold_side=info['s_hold'],
            reported_radii=radii,exact_zero_return=True,unit_count=335,
            angle_histogram_edges_degrees=bins,angle_histogram_counts=np.histogram(degrees,bins=bins)[0].tolist(),
            tilted_over_1degree=int((degrees>1).sum()),max_axis_angle_degrees=float(degrees.max()),
            angle_quantiles_degrees={str(v):float(np.quantile(degrees,v))for v in (0,.5,.9,.95,1)},
            D4_centroid_aligned_unlabeled_comparisons=comparisons))
    result=dict(manifest_sha256=digest(root/'manifest.json'),results_sha256=digest(root/'results.json'),
        supervisor_sha256=digest(root/'supervisor.json'),source_sha256=digest(Path(__file__)),
        comparison_helper_sha256=digest(ROOT/'experiments/review_full_round_control.py'),reference_bindings=bindings,
        details=details,fresh_certificates=0,optimizer_calls=0,seconds=time.monotonic()-started,
        scope='Exact terminal-certificate reuse and geometric diagnostics; threshold contact changes do not establish distinct topology.')
    atomic_json(out,result)
    print(json.dumps({'review_sha256':digest(out),'seconds':result['seconds'],
        'rows':[dict(source=r['source_key'],tilts=r['tilted_over_1degree'],side=r['terminal_official_side'],
                     rms={k:v['rms_center_distance']for k,v in r['D4_centroid_aligned_unlabeled_comparisons'].items()})for r in details]}))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();review(args.root.resolve(),args.out.resolve())
