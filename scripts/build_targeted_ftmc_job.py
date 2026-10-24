"""Freeze the bounded six-family dual-T4 continuation; never launch by itself."""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from ftmc_targeted_mutations import extend_row_capacity,extend_reference_capacity,transform_mutations
from ftmc_certified_archive import _fingerprint
from compose_gadgets import extents
from extract_broad_active_frontier import orient,geometry_sha
from build_full_puzzle_ftmc_job import validate_seeds,npz_bytes,METRIC_HASH


def digest(data):return hashlib.sha256(data).hexdigest()


def bloat(p,key):
    w,h,_=map(int,key.split('_'));lo,hi=extents(p)
    return float(max(hi.max(0)-lo.min(0)-[w,h]))


def validation_cache(job):
    if job is None:return {},None
    script=(job/'search.py').read_bytes();tree=ast.parse(script)
    literals={node.targets[0].id:ast.literal_eval(node.value)for node in tree.body
        if isinstance(node,ast.Assign)and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
        and node.targets[0].id in('CONFIG','PAYLOAD')}
    config=literals['CONFIG'];stored=json.loads((job/'seed_validation.json').read_text())
    poses={}
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(literals['PAYLOAD'])))as archive:
        embedded=archive.read('prepared_validation.json')
        if digest(embedded)!=config['embedded_sha256']['prepared_validation.json']or json.loads(embedded)!=stored:
            raise ValueError('Cached validation is not bound to frozen payload')
        for name in('prepared_variants.npz','prepared_bank.npz'):
            data=archive.read(name)
            if digest(data)!=config['embedded_sha256'][name]:raise ValueError('Cached pose archive hash mismatch')
            with np.load(io.BytesIO(data),allow_pickle=False)as z:poses.update({k:z[k]for k in z.files})
    if not stored['valid']or stored['metric_sha256']!=METRIC_HASH:raise ValueError('Invalid seed certificate cache')
    cache={}
    for name,result in stored['results'].items():
        if name not in poses or result['raw_status']!='ok'or result['roundtrip_status']!='ok':
            raise ValueError('Missing/invalid cached exact pose')
        cache[geometry_sha(poses[name])]=result
    return cache,{'job':str(job),'script_sha256':digest(script),
                  'validation_sha256':digest((job/'seed_validation.json').read_bytes()),
                  'exact_pose_certificates':len(cache)}


PROTOCOLS={
    '0':{'arm':'local','anchor_policy':'incumbent','local_angle_fraction':.75,
         'mode_cycle':[0,1,2,3,4,5],'refill_deficit_margin':2,'refill_fraction':.18,
         'full_shrink_depths':[-.004,-.001,0.,.0001,.0005,.001,.002,.004],'n65_mass':.45},
    '1':{'arm':'broad','anchor_policy':'mixed_walls','local_angle_fraction':.25,
         'mode_cycle':[5,4,1,2,5,4,3,0],'refill_deficit_margin':6,'refill_fraction':.25,
         'full_shrink_depths':[-.020,-.006,0.,.0005,.002,.006,.012,.020],'n65_mass':.40}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=ROOT/'artifacts/fq-bottleneck-inputs-v1')
    parser.add_argument('--n65',type=Path,default=ROOT/'artifacts/n65-fq-input-v1')
    parser.add_argument('--override-bank',type=Path,action='append',default=[])
    parser.add_argument('--extra-archive',type=Path,action='append',default=[])
    parser.add_argument('--reuse-job',type=Path)
    parser.add_argument('--baseline',type=Path,default=ROOT/'artifacts/submission-fq-full-basin-v1-safe.csv')
    parser.add_argument('--baseline-report',type=Path,default=ROOT/'artifacts/submission-fq-full-basin-v1-safe-official.json')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=2700)
    parser.add_argument('--replicas',type=int,default=96)
    parser.add_argument('--slug',required=True);parser.add_argument('--title',required=True)
    args=parser.parse_args()
    if args.out.exists()or not 1800<=args.seconds<=2700 or not 16<=args.replicas<=128:
        raise ValueError('Require a new directory and approved bounded search settings')
    baseline_hash=digest(args.baseline.read_bytes());baseline=json.loads(args.baseline_report.read_text())
    if not(baseline['valid']and baseline['sha256']==baseline_hash and baseline['puzzles']==1000
           and baseline['invalid_count']==0 and baseline['metric_sha256']==METRIC_HASH):
        raise ValueError('Current complete official baseline certificate required')
    input_manifest=json.loads((args.inputs/'manifest.json').read_text())
    if (digest((args.inputs/'reference.npz').read_bytes())!=input_manifest['reference_sha256']or
        digest((args.inputs/'donors.npz').read_bytes())!=input_manifest['donors_sha256']):
        raise ValueError('Shared target bank hash mismatch')
    with np.load(args.inputs/'reference.npz',allow_pickle=False)as z:bank={k:z[k]for k in z.files}
    with np.load(args.n65/'reference.npz',allow_pickle=False)as z:
        if z.files!=['8_8_1']:raise ValueError('Unexpected n65 target bank')
        bank['8_8_1']=z['8_8_1']
    original_references={key:p.copy()for key,p in bank.items()}
    variants={};origins={};source_records=[]
    paths=[args.inputs/'reference.npz',args.inputs/'donors.npz',args.n65/'reference.npz',*args.override_bank,*args.extra_archive]
    for path in paths:
        sha=digest(path.read_bytes());source_records.append({'path':str(path),'sha256':sha})
        with np.load(path,allow_pickle=False)as archive:
            for name in archive.files:
                key=name.split('__')[0]
                if key not in bank:continue
                p=np.asarray(archive[name],dtype=float);w,h,d=map(int,key.split('_'))
                if p.shape!=(w*h+d,3)or not np.isfinite(p).all():raise ValueError('Invalid donor geometry')
                origins.setdefault(key+'__'+geometry_sha(p),{'source_archive_sha256':sha,'array_key':name,
                    'transposed':False,'normalization':'unchanged source bytes','geometry_sha256':geometry_sha(p)})
                for trans in(False,True):
                    target=f'{h}_{w}_{d}'if trans else key
                    if target not in bank:continue
                    q=orient(p,trans,1,1)
                    core=int(np.sum(abs((q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018))
                    if not 4<=core<=256:raise ValueError('Unsupported donor core; never silently truncate')
                    f=bloat(q,target)
                    if not 0<f<1:continue
                    identity=target+'__'+geometry_sha(q)
                    variants[identity]=q
                    origins[identity]={'source_archive_sha256':sha,'array_key':name,'transposed':trans,
                        'geometry_sha256':geometry_sha(q),'bloat':f,'tilted_core':core}
                    if f<bloat(bank[target],target):bank[target]=q.copy()
    selected={}
    for key in bank:
        choices={}
        for name,q in variants.items():
            if name.split('__')[0]!=key:continue
            signature=_fingerprint(q)
            if signature not in choices or bloat(q,key)<choices[signature][0]:
                choices[signature]=(bloat(q,key),name,q)
        for _,name,q in sorted(choices.values(),key=lambda row:row[0])[:12]:selected[name]=q
        # Never omit the exact current reference even when its coarse fingerprint aliases.
        selected[key+'__reference']=bank[key]
        selected[key+'__original_active_reference']=original_references[key]
    unique={}
    for name,q in {**selected,**bank}.items():unique.setdefault(geometry_sha(q),(name,q))
    cached,cache_proof=validation_cache(args.reuse_job)
    fresh={name:q for sha,(name,q)in unique.items()if sha not in cached}
    validation=validate_seeds(fresh)
    fresh_count=len(fresh)
    for sha,(name,q)in unique.items():
        if sha in cached:validation['results'][name]=cached[sha]
    validation.update(count=len(unique),freshly_evaluated=fresh_count,
                      exact_pose_certificates_reused=len(unique)-fresh_count,cache_provenance=cache_proof)
    priorities={key:1. for key in bank}
    family_weights={'7_21_15':1.,'8_20_12':.7,'6_22_16':.6,'10_23_14':.8,'9_22_16':.9}
    for key in bank:
        w,h,d=map(int,key.split('_'));priorities[key]=family_weights.get(f'{min(w,h)}_{max(w,h)}_{d}',1.)
    data={};vendor=ROOT/'vendor/lightning_ftmc'
    for path in sorted(vendor.rglob('*')):
        if path.is_file()and'__pycache__'not in path.parts:data[str(path.relative_to(vendor))]=path.read_bytes()
    public=json.loads(data['SOURCE_MANIFEST.json'])
    for name,expected in public['files'].items():
        if digest(data[name])!=expected:raise ValueError('Pinned public source changed: '+name)
    patched,row_audit=extend_row_capacity(data['gpu_upright_rows.py'].decode())
    data['gpu_upright_rows.py']=patched.encode()
    modules=['ftmc_adaptive_angles.py','ftmc_anchor_mutations.py','ftmc_funnel_metrics.py',
        'ftmc_refill_budget.py','ftmc_certified_archive.py','ftmc_exploratory_archive.py',
        'ftmc_gentle_targets.py','ftmc_combined_policy.py','ftmc_combined_export.py',
        'ftmc_targeted_mutations.py','ftmc_targeted_worker.py','ftmc_targeted_preflight.py']
    for name in modules:data[name]=(ROOT/'experiments'/name).read_bytes()
    data['ftmc_refill_budget.py']=extend_reference_capacity(data['ftmc_refill_budget.py'].decode()).encode()
    for name in['LICENSE','NOTICE','SOURCE_MANIFEST.json']:
        data['research/fq_donor_provenance/'+name]=(ROOT/'vendor/fq'/name).read_bytes()
    bank_bytes=npz_bytes(bank)
    data.update({'prepared_bank.npz':bank_bytes,'prepared_bank_device0.npz':bank_bytes,'prepared_bank_device1.npz':bank_bytes,
        'prepared_variants.npz':npz_bytes(selected),'prepared_priorities.json':json.dumps(priorities).encode(),
        'original_target_references.npz':npz_bytes(original_references),
        'prepared_validation.json':json.dumps(validation).encode(),'targeted_protocols.json':json.dumps(PROTOCOLS).encode(),
        'prepared_targeting.json':json.dumps({'families':list(bank),'n65_slope':1.1791211,'n65_cases':17,
            'expected_n65_mass':{'0':.45,'1':.40},'reference_bloats':{k:bloat(p,k)for k,p in bank.items()}}).encode(),
        'prepared_provenance.json':json.dumps({'source_archives':source_records,'selected':{
            k:origins.get(k)or origins.get(k.split('__')[0]+'__'+geometry_sha(q))for k,q in selected.items()},
            'input_manifest_sha256':digest((args.inputs/'manifest.json').read_bytes()),
            'n65_proof':json.loads((args.n65/'input-proof.json').read_text())}).encode()})
    runtime=(ROOT/'experiments/ftmc_combined_runtime.py').read_text()
    old="'ftmc_combined_worker.py'"
    if runtime.count(old)!=1:raise ValueError('Supervisor worker command changed')
    runtime=runtime.replace(old,"'ftmc_targeted_worker.py'")
    marker='    cp.get_default_memory_pool().free_all_blocks()'
    if runtime.count(marker)!=1:raise ValueError('Supervisor preflight insertion point changed')
    extra=("    from ftmc_targeted_preflight import check as targeted_check\n"
           "    targeted=targeted_check(device,json.loads(Path('targeted_protocols.json').read_text())[str(device)])\n"
           "    checks['targeted_256_boundary']=targeted\n"
           "    preflight[str(device)]=checks\n"
           "    atomic_json('preflight.json',preflight)\n"
           "    print(json.dumps({'stage':'targeted_boundary_preflight','device':device,'result':targeted}),flush=True)\n")
    runtime=runtime.replace(marker,extra+marker)
    counts={key:{'squares':len(p),'tilted_core':int(np.sum(abs((p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)>.018)),
                 'bloat':bloat(p,key),'geometry_sha256':geometry_sha(p)}for key,p in bank.items()}
    manifest={'source':public['source'],'source_version':public['version'],
        'source_license':'Apache-2.0 with inherited notices; FQ seed generation MIT Evan Daniel659ee62e4a9d39542a1146e8b011cc3ab6407ede',
        'devices':[0,1],'baseline_sha256':baseline_hash,'baseline_official_score':baseline['score'],
        'baseline_report_sha256':digest(args.baseline_report.read_bytes()),'active_seed_types':len(bank),
        'input_variant_poses':len(selected),'validated_unique_poses':len(unique),'actual_active_families':counts,
        'search_seconds':args.seconds,'grace_seconds':120,'wall_seconds':3300,'server_timeout_seconds':3500,
        'device_configs':{str(i):{'device':i,'replicas':args.replicas,'seed':seed,
            'source_rng_seed':20261024+seed+i*19937,'initial_bank_label':'Latest orientation-fair validated minima',
            'initial_bank_sha256':digest(bank_bytes),'protocol':PROTOCOLS[str(i)]}for i,seed in[(0,517103),(1,617119)]},
        'row_capacity_adaptation':row_audit,'public_original_row_sha256':public['files']['gpu_upright_rows.py'],
        'source_archives':source_records,'input_attachments':[],'slug':args.slug,
        'quota_expectation':{'nominal_device_hours':2*args.seconds/3600,'parent_max_device_hours':2*3300/3600,
                             'server_max_device_hours':2*3500/3600},
        'certificate_policy':'Unchanged strict residual, LP, gap and official raw+pandas gates. Every certified geometry retained immutably; exploratory captures explicitly unvalidated.',
        'runtime_sha256':digest(runtime.encode()),'embedded_sha256':{name:digest(value)for name,value in data.items()}}
    for name,payload in data.items():
        if name.endswith('.py'):compile(payload,name,'exec')
        if b'KGAT_'in payload:raise ValueError('Credential-shaped bytes forbidden in notebook payload')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as archive:
        for name,value in data.items():archive.writestr(name,value)
    script='# Private targeted FTMC continuation. No credentials embedded.\nCONFIG='+repr(manifest)+'\nPAYLOAD='+repr(base64.b64encode(stream.getvalue()).decode())+'\n'+runtime
    if len(script.encode())>=1_000_000:raise ValueError('Notebook source exceeds Kaggle1MB limit')
    compile(script,'search.py','exec');args.out.mkdir(parents=True)
    metadata={'id':args.slug,'title':args.title,'code_file':'search.py','language':'python','kernel_type':'script',
              'is_private':True,'enable_gpu':True,'enable_internet':False,'enable_tpu':False,
              'dataset_sources':[],'kernel_sources':[],'competition_sources':['squares-in-squares'],
              'machine_shape':'NvidiaTeslaT4'}
    for name,value in[('job_manifest.json',manifest),('kernel-metadata.json',metadata),('seed_validation.json',validation)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    (args.out/'search.py').write_text(script)
    print(json.dumps({'out':str(args.out),'source_bytes':len(script.encode()),'script_sha256':digest(script.encode()),
                      'families':counts,'variants':len(selected),'unique_seed_certificates':len(unique),'launched':False},indent=2))


if __name__=='__main__':main()
