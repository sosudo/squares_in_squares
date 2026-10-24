"""Freeze two failed scalar joins and strictly certified one-defect scaffolds."""
from pathlib import Path
import csv,hashlib,json,math,shutil,sys
import numpy as np
from scipy.spatial import cKDTree
from compose_gadgets import extents,legalize
from cpu_recipe_replay import public_functions
from extract_broad_active_frontier import orient,geometry_sha
from fq_capacity_probe import full_certificate
from fq_active_pilot import digest
from fq_variant_campaign import atomic_json,atomic_npz
ROOT=Path(__file__).resolve().parents[1]


def gaps(p,pairs):
    a,b=p[pairs[:,0]],p[pairs[:,1]];delta=b[:,:2]-a[:,:2]
    proj=np.maximum.reduce([abs(delta[:,0]*np.cos(t)+delta[:,1]*np.sin(t))for t in(a[:,2],a[:,2]+np.pi/2,b[:,2],b[:,2]+np.pi/2)])
    return proj-.5*(1+abs(np.cos(a[:,2]-b[:,2]))+abs(np.sin(a[:,2]-b[:,2])))


def overlaps(p):
    pairs=cKDTree(p[:,:2]).query_pairs(1.5,output_type='ndarray');values=gaps(p,pairs);bad=pairs[values < -1e-8]
    return bad,float(np.maximum(-values,0).max(initial=0)),float((np.maximum(-values,0)**2).sum())


def descriptor(p,w,h,d,f=None):
    if f is None:
        _,hi=extents(p);f=math.ceil((float(max(hi.max(0)-[w,h]))+3e-8)*1e9)*1e-9
    return {'pose':p,'w':w,'h':h,'dm':d,'f':float(f)}


def build(a,b,k,stitch):
    gs=[{**{key:r[key]for key in('w','h','dm','f')},'donor':i}for i,r in enumerate((a,b))]
    p,_=stitch([(0,3),(1,0)],gs,[(a['pose'],'a'),(b['pose'],'b')],box=(k,k));return p


def prepare(out):
    out.mkdir(parents=True,exist_ok=False)
    for d in ('inputs','source','scaffolds','notices'):(out/d).mkdir()
    pb=(ROOT/'artifacts/current-best-portfolio.json').read_bytes();pointer=json.loads(pb);base=pointer['raw']
    assert digest(base['path'])==base['sha256']and digest(base['official_report'])==base['official_report_sha256']
    official=json.loads(Path(base['official_report']).read_text());assert official['valid']and official['puzzles']==1000 and official['sha256']==base['sha256']
    before={r['n']:r['side']for r in official['results']};(out/'inputs/pointer.json').write_bytes(pb)
    vendor=ROOT/'vendor/lightning_ftmc';stitch,_=public_functions(vendor);recipes=[];source_paths=[]
    # Whole494 plus the classic diamond: exact previous minimum-collision join.
    prior=ROOT/'artifacts/broad-delta-four-joins-v1';row=next(r for r in json.loads((ROOT/'artifacts/next-avenue-public-check-v1/four-join-soft-screen.json').read_text())['best']if r['target_n']==587)
    with np.load(prior/'inputs/new-whole-donors.npz',allow_pickle=False)as z:p=orient(z['494'],*row['new_transform'])
    with np.load(prior/'inputs/classic-partners.npz',allow_pickle=False)as z:q=orient(z[row['partner']],*row['partner_transform'])
    a,b=descriptor(p,22,22,10),descriptor(q,2,2,1)
    if row['reverse']:a,b=b,a
    recipes.append((587,build(a,b,24,stitch),{'prior_join':row,'blocks':[{key:g[key]for key in('w','h','dm','f')}for g in(a,b)]}))
    source_paths.extend([prior/'inputs/new-whole-donors.npz',prior/'inputs/classic-partners.npz',prior/'manifest.json'])
    # New public crop + private17x5+7. Keep original crop wall phase unchanged.
    cropdir=ROOT/'artifacts/public-v29/localized-crops-v1';jobs=[r for r in json.loads((cropdir/'scalar-pair-jobs.json').read_text())if r['n']==498]
    provenance={r['key']:r for r in json.loads((cropdir/'provenance.json').read_text())};partners=ROOT/'artifacts/targeted-partners-v2/partners.npz';options=[]
    with np.load(cropdir/'crops.npz',allow_pickle=False)as crops,np.load(partners,allow_pickle=False)as old:
        for job in jobs:
            cr=provenance[job['minimum_cost_crop']];p=crops[cr['key']].copy();a=descriptor(p,cr['w'],cr['h'],cr['d'],cr['f'])
            for sx,sy in((1,1),(-1,1),(1,-1),(-1,-1)):
                pr=job['partner'];q=orient(old[pr['key']],pr['transpose'],sx,sy);b=descriptor(q,pr['w'],pr['h'],pr['d'],pr['f'])
                for reverse in(False,True):
                    x,y=(b,a)if reverse else(a,b);raw=build(x,y,22,stitch);bad,maximum,energy=overlaps(raw)
                    common=set(bad[0])if len(bad)else set()
                    for pair in bad[1:]:common.intersection_update(map(int,pair))
                    options.append((0 if common else 1,len(bad),energy,raw,{'job':job,'crop_provenance':cr,'partner_transform':[pr['transpose'],sx,sy],'reverse':reverse,'bad_pairs':bad.tolist(),'maximum_penetration':maximum,'energy':energy,'one_vertex_cover':sorted(map(int,common)),'blocks':[{key:g[key]for key in('w','h','dm','f')}for g in(x,y)]}))
    options.sort(key=lambda x:x[:3]);best=options[0];recipes.append((498,best[3],best[4]));atomic_json(out/'inputs/n498-geometry-prefilter.json',[r[4]for r in options])
    source_paths.extend([cropdir/'crops.npz',cropdir/'provenance.json',cropdir/'scalar-pair-jobs.json',partners,ROOT/'artifacts/public-v29/notices/SOURCE_NOTICES.md'])
    cases=[];donors={}
    for n,raw,recipe in recipes:
        bad,maximum,energy=overlaps(raw);common=set(bad[0])if len(bad)else set()
        for pair in bad[1:]:common.intersection_update(map(int,pair))
        atomic_npz(out/'scaffolds'/f'n{n}-raw-invalid.npz',{'pose':raw})
        record={'n':n,'canonical_side':before[n],'recipe':recipe,'raw_geometry_sha256':geometry_sha(raw),'collision_pairs':bad.tolist(),'maximum_penetration':maximum,'physical_overlap_energy':energy,'single_vertex_covers':sorted(map(int,common)),'variants':[]}
        if not common:record['status']='not_a_one_defect_scaffold';cases.append(record);continue
        for deleted in sorted(common):
            q=legalize(np.delete(raw,deleted,axis=0));assert q is not None;c=full_certificate(q)
            v={'deleted_original_row':int(deleted),'full_certificate':c,'valid':c['valid']}
            if c['valid']:
                key=f'n{n}_drop{deleted}';donors[key]=q;v.update(archive_key=key,geometry_sha256=geometry_sha(q),actual_n=len(q),side=c['independent_raw']['side_upper'],source_row_ids=[i for i in range(n)if i!=deleted],collision_center=raw[bad.flatten(),:2].mean(0).tolist())
            record['variants'].append(v)
        record['status']='certified_one_defect'if any(v['valid']for v in record['variants'])else'failed_scaffold_gates';cases.append(record)
    atomic_npz(out/'scaffolds.npz',donors);atomic_json(out/'cases.json',cases)
    # Existing source/code notices remain byte-identical. Missing optional source
    # paths are listed explicitly rather than inventing attribution text.
    copy_sources=[Path(__file__),ROOT/'experiments/cpu_recipe_replay.py',ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/fq_capacity_probe.py',ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py',vendor/'solver.py',vendor/'gpu_fault_composition.py',vendor/'packing_pipeline.py']
    for p in copy_sources:shutil.copyfile(p,out/'source'/p.name)
    notices=[vendor/'LICENSE',vendor/'NOTICE',ROOT/'vendor/fq/LICENSE',ROOT/'vendor/fq/NOTICE']
    for folder in(ROOT/'artifacts/public-v29/notices',ROOT/'vendor/notices/kmmm-v31'):
        if folder.exists():notices.extend(p for p in folder.iterdir()if p.is_file()and p.suffix in('.md','.txt'))
    notice_records=[]
    for i,p in enumerate(notices):
        dst=out/'notices'/f'{i:02d}-{p.name}';shutil.copyfile(p,dst);notice_records.append({'source':str(p),'sha256':digest(dst),'retained':str(dst)})
    manifest={'baseline':base,'safe':pointer['safe'],'pointer_sha256':__import__('hashlib').sha256(pb).hexdigest(),'cases_sha256':digest(out/'cases.json'),'scaffolds_sha256':digest(out/'scaffolds.npz'),'sources':{str(p):digest(p)for p in source_paths+copy_sources if p.exists()},'missing_optional_source_paths':[str(p)for p in source_paths if not p.exists()],'notices':notice_records,'no_optimizer_or_native_calls':True,'scope':'Exact source arrays/offsets, overlapping fullN witnesses and all certifiedN-1variants retained. Source raw invalids are not packings.'}
    atomic_json(out/'manifest.json',manifest)
    for p in out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps({'cases':[(r['n'],r['status'],len(r['collision_pairs']),len(r['variants']))for r in cases],'manifest_sha256':digest(out/'manifest.json')}),flush=True)


if __name__=='__main__':prepare(Path(sys.argv[1]))
