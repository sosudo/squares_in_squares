#!/usr/bin/env python3
"""Freeze the four-family rectangular campaign; never upload or launch it."""
from __future__ import annotations
import argparse,ast,base64,hashlib,io,json,lzma
from pathlib import Path
import zipfile
import numpy as np
from build_fq_fused_hop_job import unpack,add_local_import_closure
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/fq-cold-transfer-job-v1/search.py'
PARENT_SHA='34ea1497cf6e24560eff8da939b3288b08029519640ba1eb8907acc1353d1292'
BINARY_SHA='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
BASELINE_SHA='9d18b33ca0efb4c55c0afac2c159f413676d76aae37fb3cbcc6ec93a43975396'
FAMILIES={'5_17_7':92,'7_19_13':146,'7_20_14':154,'8_21_13':181}
REMOVED_DATA=('cold-config.json','cold-inputs.npz','cold-input-proof.json')
NEW_SOURCES=('experiments/fq_rectangular_persistent_pilot.py','experiments/fq_rectangular_persistent_search.py','experiments/fq_rectangular_persistent_finish.py')
AUXILIARY_SOURCES={'experiments/prepare_wall_aspect_inputs.py':'0c8fa418453cb8a67c00defe68142f8206ab65c3a5d1068874513f039585cf61','experiments/analyze_jam_row_evacuation.py':'ec67221af2900ac0a8a78c253360b9bb36b8c176a28ff6c30403dec30e60c052'}

def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def safe_name(name):
 p=Path(name)
 return bool(name and not p.is_absolute() and '..'not in p.parts and str(p)==name)


TREE_STOPPER=r'''
def stop_owned_tree(process):
    # Suspend the owned root before finding descendants, including new sessions.
    owned={process.pid}
    try:os.kill(process.pid,signal.SIGSTOP)
    except ProcessLookupError:pass
    for attempt in range(8):
        parents={}
        for stat in Path('/proc').glob('[0-9]*/stat'):
            try:
                tail=stat.read_text();tail=tail[tail.rfind(')')+2:].split()
                parents[int(stat.parent.name)]=int(tail[1])
            except (OSError,ValueError,IndexError):pass
        found=set(owned)
        while True:
            new={pid for pid,parent in parents.items()if parent in found}-found
            if not new:break
            found.update(new)
        new=found-owned
        for pid in new:
            try:os.kill(pid,signal.SIGSTOP)
            except ProcessLookupError:pass
        owned=found
        if not new:break
    for pid in sorted(owned-{process.pid},reverse=True):
        try:os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:pass
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    if process.poll()is None:process.kill()
    process.wait(timeout=3)
    wait_deadline=time.monotonic()+3.
    while True:
        active=[]
        for pid in owned-{process.pid}:
            try:
                stat=(Path('/proc')/str(pid)/'stat').read_text()
                if stat[stat.rfind(')')+2:].split()[0]not in('Z','X'):active.append(pid)
            except (OSError,ValueError,IndexError):pass
        if not active:break
        if time.monotonic()>=wait_deadline:raise RuntimeError('Owned descendants remain live after kill')
        time.sleep(.01)
'''


STREAM_WORKER=r'''
import threading
with open('worker.log','w')as log:
    worker=subprocess.Popen([sys.executable,'-u','experiments/fq_rectangular_persistent_pilot.py',
        '--mode','parent','--deadline',str(started+7100.)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,bufsize=1,env=env,start_new_session=True)
    stream_errors=[]
    def relay_worker():
        try:
            for line in worker.stdout:
                log.write(line);log.flush();print(line,end='',flush=True)
        except Exception as error:stream_errors.append(type(error).__name__)
    relay=threading.Thread(target=relay_worker,daemon=True);relay.start();timeout=False
    try:worker.wait(timeout=max(.01,started+7160.-time.monotonic()))
    except subprocess.TimeoutExpired:
        timeout=True;stop_owned_tree(worker)
    relay.join(timeout=5.)
    if relay.is_alive()or stream_errors:raise RuntimeError('Child log relay did not finish cleanly')
'''

FIXTURE_LOADER=r'''
fixture_found=None
for candidate in sorted(Path('/kaggle/input').rglob('rectangular-inputs.npz')):
    if hashlib.sha256(candidate.read_bytes()).hexdigest()!=CONFIG['inputs_sha256']:continue
    base=candidate.parent
    if all((base/name).is_file() and (base/name).stat().st_size==record['bytes']
           and hashlib.sha256((base/name).read_bytes()).hexdigest()==record['sha256']
           for name,record in CONFIG['fixture_files'].items()):
        fixture_found=base;break
if fixture_found is None:raise ValueError('Exact private rectangular fixture not found')
for name,record in CONFIG['fixture_files'].items():
    src=(fixture_found/name).resolve();dst=(root/name).resolve()
    assert src.is_relative_to(fixture_found.resolve()) and dst.is_relative_to(root)
    assert not dst.exists(), 'Fixture may not overwrite numerical source or inherited payload'
    data=src.read_bytes()
    assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
    dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
Path('fixture-verification.json').write_text(json.dumps(dict(ref=CONFIG['fixture_transport']['ref'],
    inputs_sha256=CONFIG['inputs_sha256'],verified_files=len(CONFIG['fixture_files']),
    every_file_exact=True),indent=2)+'\n')
'''

def validate_fixture(folder):
 config_bytes=(folder/'rectangular-input-config.json').read_bytes();config=json.loads(config_bytes)
 proof_bytes=(folder/'rectangular-input-proof.json').read_bytes();proof=json.loads(proof_bytes)
 inputs=(folder/'rectangular-inputs.npz').read_bytes()
 if not (sha(inputs)==config['inputs_sha256']==proof['inputs_sha256'] and sha(config_bytes)==proof['config_sha256']
         and config['baseline']['raw']['sha256']==proof['baseline']['raw']['sha256']==BASELINE_SHA
         and set(config['families'])==set(FAMILIES) and proof['all_transformed_gates_passed']):
  raise ValueError('Exact rectangular input/portfolio bindings required')
 with np.load(io.BytesIO(inputs),allow_pickle=False)as z:
  if set(z.files)!=set(proof['array_hashes'])or len(z.files)!=32:raise ValueError('All16 original and16 canonical poses required')
  for key in z.files:
   q=z[key]
   if q.dtype.str!='<f8'or not np.isfinite(q).all()or sha(q.tobytes())!=proof['array_hashes'][key]:raise ValueError('Input array changed: '+key)
  for family,n in FAMILIES.items():
   f=config['families'][family];w,h,d=map(int,family.split('_'))
   if (f['w'],f['h'],f['d'],f['n'])!=(w,h,d,n)or len(f['seeds'])!=4:raise ValueError('Typed family/count differs')
   if f['reference_key']not in{r['key']for r in f['seeds']}:raise ValueError('Reference not in seed inventory')
   for row in f['seeds']:
    key=row['key'];certificate=folder/row['certificate']['path']
    if not (z[key].shape==z[row['original_key']].shape==(n,3)
            and sha(z[key].tobytes())==row['geometry_sha256']==row['certificate']['geometry_sha256']
            and sha(certificate.read_bytes())==row['certificate']['sha256']
            and json.loads(certificate.read_bytes())['valid']):raise ValueError('Seed certificate/count/bytes differs')
    native=folder/row['native_input']['path']
    if sha(native.read_bytes())!=row['native_input']['sha256']:raise ValueError('Exact native reference input changed')
 for row in proof['evidence']:
  path=folder/row['path']
  if not safe_name(row['path'])or sha(path.read_bytes())!=row['sha256']or path.stat().st_size!=row['bytes']:raise ValueError('Input notice/evidence changed')
 if sha((folder/'prepare-source.py').read_bytes())!=proof['prepare_source_sha256']:raise ValueError('Executed preparer changed')
 return config,proof


def build(args):
 if args.out.exists():raise ValueError('Fresh output directory required')
 source,parent,files=unpack(PARENT,PARENT_SHA,'xz85');original={k:sha(v)for k,v in files.items()}
 removed={name:dict(sha256=sha(files[name]),bytes=len(files[name]))for name in REMOVED_DATA}
 for name in REMOVED_DATA:del files[name]
 if sha(files['bin/fq'])!=BINARY_SHA:raise ValueError('Pinned native binary changed')
 config,proof=validate_fixture(args.inputs)
 fixture_manifest=json.loads(args.fixture_manifest.read_bytes());receipt=json.loads(args.dataset_proof.read_bytes())
 fixture_files=fixture_manifest['files']
 if not(all(safe_name(k)for k in fixture_files)and not set(files)&set(fixture_files)):raise ValueError('Unsafe fixture destination')
 for name,r in fixture_files.items():
  data=(args.inputs/name).read_bytes()
  if sha(data)!=r['sha256']or len(data)!=r['bytes']:raise ValueError('Frozen fixture member differs')
 mandatory={'rectangular-inputs.npz','rectangular-input-config.json','rectangular-input-proof.json','prepare-source.py'}
 mandatory.update(row['path']for row in proof['evidence'])
 mandatory.update(row['certificate']['path']for f in config['families'].values()for row in f['seeds'])
 mandatory.update(row['native_input']['path']for f in config['families'].values()for row in f['seeds'])
 if not mandatory<=set(fixture_files):raise ValueError('Incomplete immutable fixture')
 if not(receipt['status']=='complete'and receipt['is_private']and receipt['version']==1
        and args.dataset_ref==receipt['ref']+'/1'and receipt['inputs_sha256']==config['inputs_sha256']
        and receipt['input_proof_sha256']==sha((args.inputs/'rectangular-input-proof.json').read_bytes())
        and receipt['fixture_manifest_sha256']==sha(args.fixture_manifest.read_bytes())
        and receipt['downloaded_files']=={k:r['sha256']for k,r in fixture_files.items()}):
  raise ValueError('Exact private version1 remote fixture verification required')
 protocol_bytes=args.protocol.read_bytes();protocol=json.loads(protocol_bytes)
 if protocol.get('whole_seconds')!=7200 or protocol.get('server_seconds')!=7800:raise ValueError('Approved whole/server bounds required')
 if not(0<protocol.get('search_seconds',0)<=3000 and protocol.get('batch_size')==64
        and protocol.get('cuts')==[.002,.01,.03,.06] and protocol.get('quench_steps')==2000):raise ValueError('Approved finite rectangular search required')
 if not(protocol['families']==list(FAMILIES) and protocol['parent_seconds']==7100 and protocol['outer_worker_seconds']==7160 and protocol['outer_alarm_seconds']==7195
        and protocol['phase_seconds']==dict(preflight=60,search=3040,recovery=3,finish=290)
        and protocol['input_archive_sha256']==config['inputs_sha256']
        and protocol['input_config_sha256']==proof['config_sha256']
        and protocol['input_proof_sha256']==sha((args.inputs/'rectangular-input-proof.json').read_bytes())):
  raise ValueError('Protocol and fixture/deadline pins differ')
 control_name=protocol['native_reference_results_path']
 if control_name not in fixture_files or fixture_files[control_name]['sha256']!=protocol['native_reference_results_sha256']:
  raise ValueError('Exact matched native control comparison not staged')
 files['rectangular-protocol.json']=protocol_bytes
 source_hashes=json.loads(args.source_manifest.read_bytes())
 if not set(NEW_SOURCES)<=set(source_hashes)<=set(NEW_SOURCES)|set(AUXILIARY_SOURCES):raise ValueError('Exact three new reviewed sources and declared oracle closure required')
 for name,expected in AUXILIARY_SOURCES.items():
  if name in source_hashes and source_hashes[name]!=expected:raise ValueError('Independent oracle source changed')
 for name,expected in source_hashes.items():
  data=(ROOT/name).read_bytes()
  if sha(data)!=expected:raise ValueError('Unfrozen new source: '+name)
  files[name]=data
 files['provenance/rectangular-private-fixture-proof.json']=args.dataset_proof.read_bytes()
 files['provenance/rectangular-fixture-manifest.json']=args.fixture_manifest.read_bytes()
 dependency_additions=add_local_import_closure(files,{})
 if add_local_import_closure(dict(files),{}):raise ValueError('Import closure incomplete')
 for name,data in files.items():
  if name.endswith('.py'):
   compile(data,name,'exec')
   if name.startswith('provenance/'):continue
   for node in ast.walk(ast.parse(data)):
    modules=([x.name for x in node.names]if isinstance(node,ast.Import)else[node.module]if isinstance(node,ast.ImportFrom)and node.module else[])
    for mod in modules:
     rel=mod.replace('.','/')+'.py';candidates=[str(Path(name).parent/rel),'experiments/'+rel,'scripts/'+rel,'public_solver/'+rel,rel]
     if not any(k in files for k in candidates)and any((ROOT/k).is_file()for k in candidates):raise ValueError('Unfrozen local import: '+name+' -> '+mod)
  if b'KGAT_'in data:raise ValueError('Credential-shaped bytes forbidden')
 for name,h in original.items():
  if name not in REMOVED_DATA and sha(files[name])!=h:raise ValueError('Inherited source/native/license changed: '+name)
 supervisor=source.decode().split('\n',2)[2]
 replacements={"'experiments/fq_cold_transfer_pilot.py'":"'experiments/fq_rectangular_persistent_pilot.py'",'worker.wait(timeout=880)':'worker.wait(timeout=7160)','signal.alarm(895)':'signal.alarm(7195)'}
 for old,new in replacements.items():
  if supervisor.count(old)!=1:raise ValueError('Ambiguous counted supervisor delta')
  supervisor=supervisor.replace(old,new,1)
 launch="[sys.executable,'-u','experiments/fq_rectangular_persistent_pilot.py']"
 if supervisor.count(launch)!=1:raise ValueError('Ambiguous parent deadline arguments')
 supervisor=supervisor.replace(launch,"[sys.executable,'-u','experiments/fq_rectangular_persistent_pilot.py','--mode','parent','--deadline',str(started+7100.)]",1)
 marker='def stop(signum,frame):'
 if supervisor.count(marker)!=1:raise ValueError('Ambiguous outer tree cleanup insertion')
 supervisor=supervisor.replace(marker,TREE_STOPPER+'\n'+marker,1)
 for indentation in ('        ','        '):
  old=indentation+'try:os.killpg(worker.pid,signal.SIGKILL)\n'+indentation+'except ProcessLookupError:pass'
  if old not in supervisor:raise ValueError('Ambiguous inherited kill path')
  supervisor=supervisor.replace(old,indentation+'stop_owned_tree(worker)',1)
 insertion="Path('job_manifest.json').write_text"
 if supervisor.count(insertion)!=1:raise ValueError('Ambiguous fixture insertion')
 supervisor=supervisor.replace(insertion,FIXTURE_LOADER+'\n'+insertion,1)
 stream_start=supervisor.index("with open('worker.log','w')as log:")
 stream_end=supervisor.index('summary=dict(exitcode=',stream_start)
 replaced_stream=supervisor[stream_start:stream_end]
 if replaced_stream.count('subprocess.Popen')!=1 or replaced_stream.count('worker.wait(timeout=7160)')!=1:raise ValueError('Ambiguous inherited worker block')
 supervisor=supervisor[:stream_start]+STREAM_WORKER+'\n'+supervisor[stream_end:]
 manifest=dict(kind='Four-family all-unit rectangular persistent discovery',parent_source_sha256=PARENT_SHA,native_binary_sha256=BINARY_SHA,
  original_file_count=len(original),preserved_original_file_count=len(original)-len(removed),replaced_inactive_root_data=removed,
  files={k:sha(v)for k,v in files.items()},fixture_files=fixture_files,
  fixture_transport=dict(kind='private_dataset',ref=args.dataset_ref,verification_sha256=sha(args.dataset_proof.read_bytes())),
  inputs_sha256=config['inputs_sha256'],input_proof_sha256=sha((args.inputs/'rectangular-input-proof.json').read_bytes()),
  input_config_sha256=sha((args.inputs/'rectangular-input-config.json').read_bytes()),configuration=protocol,baseline_raw_sha256=BASELINE_SHA,
  source_manifest=source_hashes,builder_sha256=sha(Path(__file__).read_bytes()),transitive_dependency_additions=dependency_additions,
  supervisor_delta=replacements,fixture_loader_sha256=sha(FIXTURE_LOADER.encode()),tree_stopper_sha256=sha(TREE_STOPPER.encode()),stream_worker_sha256=sha(STREAM_WORKER.encode()),replaced_worker_block_sha256=sha(replaced_stream.encode()),parent_deadline_seconds=7100,worker_seconds=7160,parent_alarm_seconds=7195,
  whole_seconds=7200,server_timeout_seconds=7800,devices_used=2,native_dependency_license_count=parent['native_dependency_license_count'],no_submission=True)
 stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
  for name,data in files.items():archive.writestr(name,data)
 packed=base64.b85encode(lzma.compress(stream.getvalue(),preset=9)).decode()
 frozen='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(packed)+'\n'+supervisor;compile(frozen,'search.py','exec')
 if len(frozen.encode())>=1_000_000:raise ValueError('Exact source exceeds1MB: '+str(len(frozen.encode())))
 args.out.mkdir(parents=True);(args.out/'search.py').write_text(frozen)
 metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',kernel_type='script',is_private=True,
  enable_gpu=True,enable_tpu=False,enable_internet=False,dataset_sources=[args.dataset_ref],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
 report=dict(source_sha256=sha(frozen.encode()),source_bytes=len(frozen.encode()),payload_files=len(files),configuration=manifest,launched=False)
 save(args.out/'kernel-metadata.json',metadata);save(args.out/'build_report.json',report)
 print(json.dumps({k:v for k,v in report.items()if k!='configuration'},indent=2));return report

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 for name in('inputs','protocol','source-manifest','fixture-manifest','dataset-proof','out'):ap.add_argument('--'+name,type=Path,required=True)
 ap.add_argument('--dataset-ref',required=True);ap.add_argument('--slug',default='sos54352/squares-rectangular-persistent-four')
 build(ap.parse_args())
