"""Copy a source-bound finite partner palette without changing any geometry."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import numpy as np
from compose_gadgets import extents,legalize,read_baseline

ROOT=Path(__file__).resolve().parents[1]

def file_sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def array_sha(p):return hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--maximum',type=int,default=700);args=ap.parse_args()
    if args.out.exists()or not 100<=args.maximum<=750:raise ValueError('Fresh output and bounded palette required')
    report_path=ROOT/'artifacts/diversity-partition-export-job-v1/local-replay/consolidation_report.json'
    report=json.loads(report_path.read_text());archive_path=report_path.parent/'composition_donors.npz'
    if file_sha(archive_path)!=report['archive_sha256']:raise ValueError('Current full source archive changed')
    original_path=ROOT/'artifacts/consolidated-composition-input-results-v1/consolidation_report.json'
    original={r['output_key']:r for r in json.loads(original_path.read_text())['records']}
    small_path=ROOT/'artifacts/high-n-small-donors/manifest.json'
    small=json.loads(small_path.read_text())['donors']
    part_types={};part_proofs={}
    for index in sorted((ROOT/'artifacts/diversity-array-parts-v2').glob('part-*/part_index.json')):
        part_proofs[str(index)]=file_sha(index)
        for rec in json.loads(index.read_text())['arrays']:
            part_types[rec['output_key']]=(tuple(rec['nominal_type']),rec['sha256'])
    sources={};by_key=defaultdict(list);by_count=defaultdict(list)
    with np.load(archive_path,allow_pickle=False)as z:
        for r in report['records']:
            p=np.asarray(z[r['output_key']]);g=array_sha(p)
            if g!=r['array_sha256']:raise ValueError('Retained source array mismatch')
            alias=original[r['source_key']]if r['source_label']=='control_consolidated'else r
            key=alias['source_key'];match=re.match(r'^(\d+)_(\d+)_(\d+)(?:__|$)',key)
            typ=tuple(map(int,match.groups()))if match else None
            if typ is None and key in part_types:
                typ,expected=part_types[key]
                if g!=expected:raise ValueError('Explicit part nominal type has different array bytes')
            if typ is None and alias['source_label']=='higher_n_small':
                m=small[key];typ=(m['nominal_width'],m['nominal_height'],m['surplus'])
            if typ is None and re.search(r'(?:^alt_n|_n|^n)(\d+)(?:_|$)',key):
                n=len(p);k=math.isqrt(n);typ=(k,k,n-k*k)
            if typ is not None and(typ[0]*typ[1]+typ[2]!=len(p)or not(1<=typ[0]<=31 and 1<=typ[1]<=31 and 1<=typ[2]<=63)):
                typ=None
            rec={'array':p.copy(),'nominal_type':typ,'geometry_sha256':g,'full_archive_key':r['output_key'],
                 'source_record':r,'original_source_alias':alias}
            sources[r['output_key']]=rec;by_key[key].append(rec);by_key[r['source_key']].append(rec);by_count[len(p)].append(rec)
    selected_path=ROOT/'artifacts/diversity-partition-export-job-v1/selected-chain-retention-review.json'
    selected=json.loads(selected_path.read_text());retained={};bindings=[];reasons=defaultdict(set)
    def keep(rec,reason,binding=None):
        identity=(rec['nominal_type'],rec['geometry_sha256'])
        if identity not in retained:retained[identity]=rec
        reasons[identity].add(reason)
        if binding is not None:bindings.append({**binding,'identity':identity,
            'source_record':rec['source_record'],'original_source_alias':rec['original_source_alias']})
        return identity
    cached_reports={};legalized_hash={}
    for use in selected['uses']:
        label=use['runtime_source_label'];runtime_hash=use['post_legalization_array_sha256']
        if any(b.get('selected_runtime_source_label')==label and b.get('runtime_geometry_sha256')==runtime_hash for b in bindings):continue
        if use['report']not in cached_reports:cached_reports[use['report']]=json.loads((ROOT/use['report']).read_text())
        rr=cached_reports[use['report']];group=rr['groups'][use['group']]if'groups'in rr else rr
        if ':'in label:
            filename,key=label.split(':',1);allowed={r['sha256']for r in group['gadgets']if Path(r['path']).name==filename}
            candidates=list({r['full_archive_key']:r for r in by_key[key]}.values())
            candidates=[r for r in candidates if r['source_record']['source_archive_sha256']in allowed
                        or r['original_source_alias']['source_archive_sha256']in allowed]
            matched=[]
            for rec in candidates:
                g=rec['geometry_sha256']
                if g not in legalized_hash:
                    q=legalize(rec['array']);legalized_hash[g]=array_sha(q)if q is not None else None
                if legalized_hash[g]==runtime_hash:matched.append(rec)
            if not matched:raise ValueError('Selected source not reproduced exactly: '+label)
            rec=matched[0]
        elif label=='certified baseline n=5':
            baseline_options=[ROOT/name for name in [
                'artifacts/submission-composition-f64-v1-safe.csv',
                'artifacts/submission-public-refresh-v1-safe.csv',
                'artifacts/submission-cpu-bottleneck-v2-safe.csv']]
            matched_paths=[p for p in baseline_options if p.exists()and file_sha(p)==group['baseline_sha256']]
            if not matched_paths:raise ValueError('Selected original baseline changed: '+group['baseline_sha256'])
            baseline_path=matched_paths[0]
            # Baseline-eligible donors bypass read_donors/legalize in the
            # original adapter; its recorded identity is the raw CSV array.
            p=read_baseline(baseline_path)[5]
            if array_sha(p)!=runtime_hash:raise ValueError('Selected baseline n5 mismatch')
            rec={'array':p,'nominal_type':(2,2,1),'geometry_sha256':array_sha(p),'full_archive_key':None,
                 'source_record':{'source_file':str(baseline_path),'source_archive_sha256':file_sha(baseline_path),'n':5},
                 'original_source_alias':{'source_label':'original_baseline','source_key':'5'}}
        else:raise ValueError('Unknown selected source label: '+label)
        keep(rec,'prior_selected_chain',{'selected_runtime_source_label':label,'runtime_geometry_sha256':runtime_hash,
             'source_report':use['report'],'source_report_sha256':selected['reports'][use['report']]})
    original51=[]
    for rec in sources.values():
        if rec['source_record']['source_label']=='control_original_active51':
            original51.append(keep(rec,'original_active51',{'original_active51_key':rec['source_record']['source_key']}))
    if len(original51)!=51:raise ValueError('Original51 source aliases missing')
    minima_path=ROOT/'artifacts/fq-remote-cpu-minima-v1/best_bank.npz'
    minima_proof=ROOT/'artifacts/fq-remote-cpu-minima-v1/selection_proof.json'
    minimum=json.loads(minima_proof.read_text())
    if file_sha(minima_path)!=minimum['selected_bank_sha256']:raise ValueError('New minima bank/proof mismatch')
    with np.load(minima_path,allow_pickle=False)as z:
        for key in z.files:
            p=z[key];typ=tuple(map(int,key.split('_')));g=array_sha(p)
            rec={'array':p.copy(),'nominal_type':typ,'geometry_sha256':g,'full_archive_key':None,
                 'source_record':{'source_file':str(minima_path),'source_archive_sha256':file_sha(minima_path),'source_key':key,
                                  'selection_proof_sha256':file_sha(minima_proof)},
                 'original_source_alias':{'source_label':'verified_remote_cpu_minima','source_key':key}}
            sources['new_minimum:'+key]=rec;keep(rec,'verified_new_minimum')
    mandatory=len(retained);family_best={};untyped=0
    for rec in sources.values():
        typ=rec['nominal_type']
        if typ is None:untyped+=1;continue
        w,h,d=typ;lo,hi=extents(rec['array']);f=float(max(hi.max(0)-lo.min(0)-[w,h]))
        if not 0<f<1:continue
        family=(min(w,h),max(w,h),d)
        if family not in family_best or(f,rec['geometry_sha256'])<(family_best[family][0],family_best[family][1]['geometry_sha256']):
            family_best[family]=(f,rec)
    omitted=[]
    for family,(f,rec)in sorted(family_best.items(),key=lambda item:(-item[0][0]*item[0][1],item[0])):
        identity=(rec['nominal_type'],rec['geometry_sha256'])
        if identity not in retained and len(retained)>=args.maximum:omitted.append(list(family));continue
        keep(rec,'canonical_family_scalar_minimum',{'canonical_family':family,'scalar_bloat':f})
    if len(retained)>args.maximum:raise ValueError('Mandatory sources exceed bounded partner capacity')
    args.out.mkdir();poses={};records={};identity_to_key={}
    for identity,rec in retained.items():
        typ,g=identity;prefix='_'.join(map(str,typ))if typ else'untyped'
        key=prefix+'__source_'+g;poses[key]=rec['array'];identity_to_key[identity]=key
        records[key]={k:v for k,v in rec.items()if k!='array'};records[key]['retention_reasons']=sorted(reasons[identity])
    for b in bindings:
        typ,g=b.pop('identity');b['retained_array_key']=identity_to_key[(tuple(typ)if typ else None,g)]
    np.savez_compressed(args.out/'partners.npz',**poses)
    with np.load(args.out/'partners.npz',allow_pickle=False)as z:
        if z.files!=list(poses):raise ValueError('Serialized row order changed')
        for key in z.files:
            if array_sha(z[key])!=records[key]['geometry_sha256']:raise ValueError('Serialized array changed')
    notices=report_path.parent/'source_notices.json';(args.out/'source_notices.json').write_bytes(notices.read_bytes())
    targeted=ROOT/'artifacts/targeted-ftmc-n65-analysis-v1/typed-bank-handoff.json';hand=json.loads(targeted.read_text())
    bound=8*(hand['poses']+len(poses)+1060)
    if bound*(31*31*63)>2**32:raise ValueError('Combined targeted+partners exceed encoded-ID range')
    manifest={'source_archive':str(archive_path),'source_archive_sha256':report['archive_sha256'],
        'source_report_sha256':file_sha(report_path),'source_selection_sha256':file_sha(selected_path),
        'explicit_part_type_proofs':part_proofs,
        'builder_sha256':file_sha(Path(__file__)),'archive_sha256':file_sha(args.out/'partners.npz'),
        'source_notices_sha256':file_sha(args.out/'source_notices.json'),'poses':len(poses),'mandatory_exact_identities':mandatory,
        'selected_chain_source_identities':87,'original_active51_aliases':51,'canonical_families':len(family_best),
        'optional_families_omitted':omitted,'untyped_source_arrays_not_scalar_ranked':untyped,
        'deduplication':'Only identical declared nominal_type (or explicit null) and exact little-endian float64 row-order bytes; mandatory source aliases retained in bindings.',
        'geometry_changes':False,'fresh_geometry_certification':False,
        'certificate_scope':'Reuses source certificates by exact array identity; selected-chain aliases additionally reproduce their prior post-legalization hashes. All new full compositions still require strict gates.',
        'targeted_handoff_sha256':file_sha(targeted),'targeted_poses':hand['poses'],'combined_conservative_oriented_bound':bound,
        'combined_max_encoded_job':bound*(31*31*63)-1,'records':records,'bindings':bindings}
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for p in args.out.iterdir():p.chmod(0o444)
    print(json.dumps({k:v for k,v in manifest.items()if k not in ['records','bindings']},indent=2))

if __name__=='__main__':main()
