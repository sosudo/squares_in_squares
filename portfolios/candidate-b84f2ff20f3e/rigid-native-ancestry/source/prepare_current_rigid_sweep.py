"""Read-only native-exposure audit and finite current-source input freeze.

No native executable, LP, GPU, or geometry-certification call is made here.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
sys.path.insert(0,str(ROOT/'scripts'))
from compose_gadgets import normalize
from fq_variant_campaign import geometry_sha
from score_official import OFFICIAL_SHA256


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equivalent(current,previous):
    """Ordered D4 + tiny uniform center-clearance equivalence, never a basin claim."""
    if current.shape!=previous.shape:return None
    current=normalize(current)
    for swap in(False,True):
        for sx,sy in((1,1),(-1,1),(1,-1),(-1,-1)):
            q=previous.copy()
            if swap:q[:,:2]=q[:,[1,0]];q[:,2]=np.pi/2-q[:,2]
            q[:,0]*=sx;q[:,1]*=sy;q[:,2]*=sx*sy
            angle=float(abs((current[:,2]-q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4).max())
            if angle>2e-12:continue
            a=q[:,:2]-q[:,:2].mean(0);b=current[:,:2]-current[:,:2].mean(0)
            norm=float((a*a).sum());scale=float((a*b).sum()/norm)if norm else 1.
            error=float(abs(b-scale*a).max())
            if abs(scale-1)<=3e-8 and error<=5e-10:
                return dict(d4=[swap,sx,sy],center_scale=scale,center_residual=error,angle_residual=angle)
    return None


def material_difference(current,previous):
    if current.shape!=previous.shape:return None
    a,b=normalize(current),normalize(previous)
    return dict(max_center_change=float(abs(a[:,:2]-b[:,:2]).max()),
        max_angle_change=float(abs((a[:,2]-b[:,2]+np.pi/4)%(np.pi/2)-np.pi/4).max()))


def prepare(args):
    args.out.mkdir(parents=True,exist_ok=False);(args.out/'inputs').mkdir()
    pointer_bytes=args.pointer.read_bytes();pointer=json.loads(pointer_bytes);raw=pointer['raw']
    assert digest(raw['path'])==raw['sha256']and digest(raw['official_report'])==raw['official_report_sha256']
    official=json.loads(Path(raw['official_report']).read_text());assert official['valid']and official['puzzles']==1000 and official['sha256']==raw['sha256']
    assert official['metric_sha256']==OFFICIAL_SHA256 and digest(official['metric'])==OFFICIAL_SHA256
    target_path=ROOT/'artifacts/public-freshness/notebooks-20261024T092136Z/public-per-puzzle-reference.json'
    target={r['n']:r for r in json.loads(target_path.read_text())}
    ranks=sorted([dict(n=r['n'],side=r['side'],target=target[r['n']]['L'],headroom=(float(r['side'])-float(target[r['n']]['L']))/math.sqrt(r['n']))
        for r in official['results']if(float(r['side'])-float(target[r['n']]['L']))/math.sqrt(r['n'])>1e-8],key=lambda r:-r['headroom'])
    selected_n={r['n']for r in ranks};rows={n:[]for n in selected_n}
    with open(raw['path'])as stream:
        for row in csv.DictReader(stream):
            n=int(row['n'])
            if n in rows:rows[n].append((int(row['square_id']),[float(row[k])for k in('x','y','angle')]))
    current={n:np.array([p for _,p in sorted(values)],dtype=np.float64)for n,values in rows.items()}
    assert all(q.shape==(n,3)and np.isfinite(q).all()for n,q in current.items())
    registry={};files={}
    archives=['fq-broad-contact-v1/inputs/current-poses.npz','fq-broad-contact-v1/donors.npz',
        'fq-unvisited-contact-v1/inputs/current-poses.npz','fq-unvisited-contact-v1/donors.npz',
        'fq-broad-contact-recovery-v1/donors.npz','fq-broad-final-native-recovery-v1/donors.npz']
    for relative in archives:
        path=ROOT/'artifacts'/relative
        if not path.exists():continue
        files[str(path)]=digest(path)
        with np.load(path,allow_pickle=False)as archive:
            for key in archive.files:
                q=archive[key]
                if q.ndim==2 and q.shape[1]==3:registry[geometry_sha(q)]=q
    records=[]
    for relative in('fq-broad-contact-v1/results.json','fq-unvisited-contact-v1/results.json'):
        path=ROOT/'artifacts'/relative;files[str(path)]=digest(path)
        for index,row in enumerate(json.loads(path.read_text())):records.append((str(path),index,row))
    exposures={n:[]for n in current};all_rigid_results={n:[]for n in current}
    for path,index,row in records:
        n=row['n'];command=row.get('command',[])
        if n not in current or not command or '--no-alm'in command:continue
        returned=row.get('returncode')==0 and'fq'in row and bool(row.get('raw_returned'))
        source=registry.get(row['parent_geometry_sha256']);input_eq=equivalent(current[n],source)if source is not None else None
        result=registry.get(row.get('geometry_sha256'))
        if returned and result is None:
            saved=row['raw_returned'];raw_path=Path(saved['path']);expected=saved.get('sha256',saved.get('archive_sha256'))
            if expected is not None:assert digest(raw_path)==expected
            with np.load(raw_path,allow_pickle=False)as archive:result=archive['pose']
        result_eq=equivalent(current[n],result)if result is not None and returned else None
        item=dict(record_path=path,record_index=index,mode=row['mode'],parent_geometry_sha256=row['parent_geometry_sha256'],
            status=row['status'],native_returned=returned,certificate_valid=bool(row.get('certificate',{}).get('valid')),
            input_equivalence=input_eq,result_equivalence=result_eq)
        exposures[n].append(item)
        if result is not None and returned:all_rigid_results[n].append((result,item))
    winner_sources={n:[]for n in current}
    for relative in('fq-broad-contact-v1/complete/candidates.json','fq-broad-contact-recovery-v1/candidates.json',
                     'fq-broad-final-native-recovery-v1/candidates.json','fq-unvisited-contact-v1/candidates.json'):
        path=ROOT/'artifacts'/relative;files[str(path)]=digest(path)
        for key,row in json.loads(path.read_text()).items():
            n=int(key)
            if n not in current:continue
            q=np.array(row['squares'],dtype=np.float64)
            if equivalent(current[n],q) is not None:
                parent=row.get('provenance',{}).get('parent_geometry_sha256');source=registry.get(parent)
                winner_sources[n].append(dict(path=str(path),side=row['side'],provenance=row.get('provenance',{}),
                    material_change=material_difference(current[n],source)if source is not None else None))
    output=[]
    for rank in ranks:
        n=rank['n'];case=dict(rank,current_geometry_sha256=geometry_sha(current[n]),exposures=exposures[n],winning_lineage=winner_sources[n])
        exact_result=[r for r in exposures[n]if r['native_returned']and r['result_equivalence']is not None]
        exact_input=[r for r in exposures[n]if r['input_equivalence']is not None]
        completed_input=[r for r in exact_input if r['native_returned']]
        delta=[]
        for result,item in all_rigid_results[n]:
            difference=material_difference(current[n],result)
            if difference is not None:delta.append(difference)
        near_result=min(delta,key=lambda r:r['max_center_change']+r['max_angle_change'])if delta else None
        case['closest_rigid_result_difference']=near_result
        if n in(147,299,335):case['category']='legacy_repeated_policy_exclusion'
        elif exact_result:case['category']='redundant_completed_rigid_result'
        elif completed_input:case['category']='redundant_completed_rigid_current_input'
        elif exact_input:case['category']='attempted_no_native_return'
        elif winner_sources[n]:
            material=(near_result is None or near_result['max_center_change']>1e-5 or near_result['max_angle_change']>1e-6)
            case['category']='changed_winner_rigid_followup'if material else'near_rigid_result_small_change'
        else:case['category']='current_source_rigid_untried'
        output.append(case)
    counts={name:sum(r['category']==name for r in output)for name in sorted({r['category']for r in output})}
    fresh=[r for r in output if r['category']=='current_source_rigid_untried'];changed=[r for r in output if r['category']=='changed_winner_rigid_followup']
    retries=[r for r in output if r['category']=='attempted_no_native_return']
    # Rigid first: finite180-source queue, biased to untouched high-gap sources.
    queue=[];a=fresh.copy();b=changed.copy();c=retries.copy()
    while len(queue)<180 and(a or b or c):
        for group in(a,a,b,c):
            if group and len(queue)<180:
                row=group.pop(0);queue.append(dict(n=row['n'],category=row['category'],headroom=row['headroom'],geometry_sha256=row['current_geometry_sha256'],
                    legacy_history='uncertain_outside_recent_pinned_archives'))
    report=dict(pointer=pointer,used_pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(),pointer_changed_during_audit=args.pointer.read_bytes()!=pointer_bytes,
        target_path=str(target_path),target_sha256=digest(target_path),input_files=files,counts=counts,cases=output,finite_queue=queue,
        queue_scope='Planning only; no optimization.180-source cap,3workers,720swhole; no LP100. Completed rigid results/inputs and legacy repeated3 excluded.',
        equivalence_scope='OrderedD4 and tiny common center scale<=3e-8; center residual<=5e-10, angle residual<=2e-12. No set-permutation or global-basin claim.',
        legacy_scope='Recent two successful broad campaigns and saved recoveries checked; older nonmatching histories are uncertain, not assumed absent.')
    (args.out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    with open(args.out/'inputs/current-poses.npz','wb')as stream:np.savez(stream,**{str(n):p for n,p in current.items()})
    (args.out/'pointer.json').write_bytes(pointer_bytes)
    freeze=dict(files={name:digest(args.out/name)for name in('audit.json','inputs/current-poses.npz','pointer.json')},
        preparer_sha256=digest(__file__),baseline=raw,queue_count=len(queue),no_optimization=True)
    (args.out/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
    for path in args.out.rglob('*'):
        if path.is_file():path.chmod(0o444)
    print(json.dumps(dict(baseline=raw,counts=counts,queue=len(queue),top25=queue[:25],freeze_sha256=digest(args.out/'freeze.json')),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pointer',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    parser.add_argument('--out',type=Path,required=True);prepare(parser.parse_args())
