"""Freeze one private rectangular-wall GPU pilot over the exact fused parent.

Packaging and isolated CPU import checks only; never launches a notebook.
"""
from __future__ import annotations
import argparse
import ast
import base64
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from build_fq_fused_hop_job import unpack

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/fq-fused-hop-job-v2/search.py'
PARENT_SHA='e608718a725a16fc241a5ad69f711a0533e9b5cfdb699c983d1765d36a7cf1d7'
INPUTS=ROOT/'artifacts/fq-rect-wall-inputs-v1'
EXPECTED={
    'experiments/fq_rect_wall_pilot.py':'d9ef69674f0a4a912a611bdacb2041a7802f0fb4169af83edefb634af8479535',
    'experiments/prepare_wall_aspect_inputs.py':'0c8fa418453cb8a67c00defe68142f8206ab65c3a5d1068874513f039585cf61',
    'experiments/analyze_jam_row_evacuation.py':'ec67221af2900ac0a8a78c253360b9bb36b8c176a28ff6c30403dec30e60c052',
    'rect-inputs.npz':'efb5ab7bb1e172187a46150ad875dcb946f64252083780070233be6365806323',
    'rect-config.json':'b20e89f50bb9fc3e1447139a74f0da2a9b7f43ec94f57e4d5615830657eac136',
    'source-manifests.json':'8073d723a92fd8579bcb70b99415596348714a4b68f80fc0dd6bc8f164f05ef6',
}


def sha(data):return hashlib.sha256(data).hexdigest()


def add_new_import_closure(files,start):
    """Resolve new local imports recursively; frozen parent helpers always win."""
    queue=list(start);visited=set();edges=[];added={}
    while queue:
        name=queue.pop()
        if name in visited:continue
        visited.add(name)
        for node in ast.walk(ast.parse(files[name])):
            modules=([x.name for x in node.names]if isinstance(node,ast.Import)
                     else[node.module]if isinstance(node,ast.ImportFrom)and node.module else[])
            for module in modules:
                relative=module.replace('.','/')+'.py'
                candidates=[str(Path(name).parent/relative),'experiments/'+relative,
                            'scripts/'+relative,'public_solver/'+relative,relative]
                match=next((p for p in candidates if p in files),None)
                if match is not None:
                    edges.append(dict(importer=name,module=module,path=match,source='frozen_or_already_added'))
                    if match in added:queue.append(match)
                    continue
                match=next((p for p in candidates if (ROOT/p).is_file()),None)
                if match is None:continue
                if match not in EXPECTED:raise ValueError('Unreviewed new transitive local import: '+match)
                data=(ROOT/match).read_bytes()
                if sha(data)!=EXPECTED[match]:raise ValueError('Reviewed local dependency changed: '+match)
                files[match]=data;added[match]=sha(data);queue.append(match)
                edges.append(dict(importer=name,module=module,path=match,source='new_exact_local_dependency'))
    return dict(added=added,edges=edges)


def isolated_import_smoke(out,files,manifest):
    destination=out/'import-smoke';destination.mkdir()
    for name,data in files.items():
        target=destination/name
        if not target.resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe payload path')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        if sha(target.read_bytes())!=manifest['files'][name]:raise ValueError('Extracted payload identity differs')
    (destination/'job_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    smoke="""
import hashlib,json,os,sys,time
from pathlib import Path
started=time.monotonic();root=Path(sys.argv[1]).resolve();os.chdir(root)
sys.path[:0]=[str(root/'experiments'),str(root/'scripts'),str(root/'public_solver')]
manifest=json.loads((root/'job_manifest.json').read_text())
import fq_rect_wall_pilot as pilot
config,data=pilot.load_inputs()
assert data['starts'].shape==(32,335,3)and data['boxes'].shape==(49,32,2)
assert config['steps_per_stage']==2000 and config['search_seconds']==180
modules={}
for name,module in list(sys.modules.items()):
    path=getattr(module,'__file__',None)
    if path is None:continue
    path=Path(path)
    if not path.is_absolute():continue  # Torch exposes synthetic relative __file__ values.
    path=path.resolve()
    if path.is_relative_to(root)and path.suffix=='.py':
        relative=str(path.relative_to(root));digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert manifest['files'].get(relative)==digest
        modules[name]=dict(path=relative,sha256=digest)
required=['fq_rect_wall_pilot','prepare_wall_aspect_inputs','analyze_jam_row_evacuation','fq_fused_hop_pilot']
assert all(name in modules for name in required)
print(json.dumps(dict(passed=True,isolated_python=True,checked_payload_files=len(manifest['files']),
    input_shapes={key:list(value.shape)for key,value in data.items()},imported_local_modules=modules,
    source_inputs_sha256=config['inputs_sha256'],search_seconds=config['search_seconds'],
    cuda_executed=False,optimizer_calls=0,fresh_certificates=0,seconds=time.monotonic()-started)))
"""
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    run=subprocess.run([sys.executable,'-I','-c',smoke,str(destination.resolve())],cwd=destination,
                       env=env,text=True,capture_output=True,timeout=30)
    (out/'import-smoke-stdout.txt').write_text(run.stdout);(out/'import-smoke-stderr.txt').write_text(run.stderr)
    if run.returncode:raise ValueError('Isolated extracted import/load_inputs smoke failed: '+run.stderr[-2000:])
    proof=json.loads(run.stdout.strip().splitlines()[-1]);proof['command_python']=str(Path(sys.executable).resolve())
    (out/'import-smoke.json').write_text(json.dumps(proof,indent=2)+'\n');return proof


def build(args):
    if args.out.exists():raise ValueError('Fresh unlaunched bundle directory required')
    source,parent,files=unpack(PARENT,PARENT_SHA,'xz85')
    if len(files)!=65:raise ValueError('Expected exact65-file reviewed fused parent')
    parent_hashes={name:sha(data)for name,data in files.items()}
    supervisor=source.decode().split('\n',2)[2]
    old="'experiments/fq_fused_hop_pilot.py'";new="'experiments/fq_rect_wall_pilot.py'"
    if supervisor.count(old)!=1:raise ValueError('Ambiguous parent entrypoint')
    changed=supervisor.replace(old,new,1)
    if changed.replace(new,old,1)!=supervisor:raise ValueError('Supervisor changed beyond entrypoint')
    for token in ('signal.alarm(475)','worker.wait(timeout=300)','start_new_session=True'):
        if changed.count(token)!=1:raise ValueError('Inherited supervisor/process bound differs')
    for name in ['rect-inputs.npz','rect-config.json','source-manifests.json','experiments/fq_rect_wall_pilot.py']:
        if name in files:raise ValueError('New root input/driver conflicts with parent payload')
        path=ROOT/name if name.startswith('experiments/')else INPUTS/name
        data=path.read_bytes()
        if sha(data)!=EXPECTED[name]:raise ValueError('Reviewed input/driver identity changed: '+name)
        files[name]=data
    dependencies=add_new_import_closure(files,['experiments/fq_rect_wall_pilot.py'])
    for name,expected in EXPECTED.items():
        if name not in files or sha(files[name])!=expected:raise ValueError('Required exact new closure missing: '+name)
    config=json.loads(files['rect-config.json'])
    if config['inputs_sha256']!=EXPECTED['rect-inputs.npz']or config['source_manifests_sha256']!=EXPECTED['source-manifests.json']:
        raise ValueError('Rectangular input/config source identities disagree')
    if not(0<config['search_seconds']<=180 and config['steps_per_stage']==2000 and config['total_stages']==49
           and config['replicas']==32 and config['unit_count']==335 and config['certification_seconds']<=30
           and config['certification_max_candidates']<=8 and config['max_packets']<=64
           and config['max_bytes']<=128*1024**2 and config['cuda_options']==['--std=c++17','--fmad=false']):
        raise ValueError('Unreviewed rectangular pilot bounds')
    if sha(files['experiments/packer_hop_physical_energy.py'])!=config['physical_oracle_sha256']:
        raise ValueError('Preserved parent physical oracle differs')
    pointer_bytes=(ROOT/'artifacts/current-best-portfolio.json').read_bytes();pointer=json.loads(pointer_bytes)
    baseline=pointer['raw'];report_bytes=Path(baseline['official_report']).read_bytes();report=json.loads(report_bytes)
    if sha(Path(baseline['path']).read_bytes())!=baseline['sha256']or sha(report_bytes)!=baseline['official_report_sha256']:
        raise ValueError('Current canonical RAW/report bytes differ')
    if not report['valid']or report['sha256']!=baseline['sha256']:raise ValueError('Current official baseline binding failed')
    files['provenance/rect-wall-current-portfolio-pointer.json']=pointer_bytes
    for name,expected in parent_hashes.items():
        if sha(files[name])!=expected:raise ValueError('Frozen parent payload mutated: '+name)
    for name,data in files.items():
        if name.endswith('.py'):compile(data,name,'exec')
        if b'KGAT_'in data:raise ValueError('Credential-shaped bytes forbidden')
    manifest=dict(kind='Rigid335 rectangular-wall continuation with corrected fused FP64 quench',
        parent_source_sha256=PARENT_SHA,parent_payload_files=parent_hashes,exact_preserved_parent_files=parent_hashes,
        new_exact_inputs=EXPECTED,transitive_dependency_additions=dependencies,
        files={name:sha(data)for name,data in files.items()},configuration=config,
        builder_sha256=sha(Path(__file__).read_bytes()),builder_helper_sha256=sha((ROOT/'scripts/build_fq_fused_hop_job.py').read_bytes()),
        baseline=baseline,baseline335=next(row for row in report['results']if row['n']==335),
        baseline_pointer_sha256=sha(pointer_bytes),worker_seconds=300,whole_seconds=480,parent_alarm_seconds=475,
        server_timeout_seconds=600,devices_used=1,no_submission=True,
        licenses=['MIT','Apache-2.0; all65parent payloads and original notices retained'],
        supervisor_delta='Exact parent supervisor, only worker entrypoint changed.',
        parent_supervisor_sha256=sha(supervisor.encode()),supervisor_sha256=sha(changed.encode()))
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,data in files.items():archive.writestr(name,data)
    payload=base64.b85encode(lzma.compress(stream.getvalue(),preset=6)).decode()
    frozen='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(payload)+'\n'+changed
    compile(frozen,'search.py','exec')
    if len(frozen.encode())>=1_000_000:raise ValueError('Kaggle source limit exceeded')
    args.out.mkdir(parents=True);(args.out/'search.py').write_text(frozen)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,
        dataset_sources=[],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
    if metadata['title'].replace(' ','-')!=args.slug.split('/')[-1]:raise ValueError('Title/slug mismatch')
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    # Decode the actual frozen source again rather than smoke-testing builder state.
    _,frozen_manifest,frozen_files=unpack(args.out/'search.py',sha(frozen.encode()),'xz85')
    if frozen_manifest!=manifest or frozen_files!=files:raise ValueError('Frozen source roundtrip differs')
    proof=isolated_import_smoke(args.out,frozen_files,frozen_manifest)
    result=dict(source_sha256=sha(frozen.encode()),source_bytes=len(frozen.encode()),payload_files=len(files),
        exact_preserved_parent_files=len(parent_hashes),import_smoke_passed=proof['passed'],configuration=manifest,launched=False)
    (args.out/'build_report.json').write_text(json.dumps(result,indent=2)+'\n')
    receipt=dict(source_sha256=result['source_sha256'],source_bytes=result['source_bytes'],payload_files=len(files),
        parent_source_sha256=PARENT_SHA,parent_payloads_preserved=65,entrypoint_only_supervisor_change=True,
        imported_local_modules=len(proof['imported_local_modules']),
        proofs={name:sha((args.out/name).read_bytes())for name in ('kernel-metadata.json','build_report.json','import-smoke.json')},
        builder_sha256=manifest['builder_sha256'],search_seconds=config['search_seconds'],worker_seconds=300,
        whole_seconds=480,server_timeout_seconds=600,private=True,offline=True,devices_used=1,launched=False)
    (args.out/'freeze_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2));return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-rectangular-wall-continuation')
    build(parser.parse_args())
