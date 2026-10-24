"""Freeze a minimal fused-quench hop delta over two immutable reviewed jobs.

This builder never launches a notebook or submits a competition entry.
"""
import argparse
import ast
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
HOP_SOURCE=ROOT/'artifacts/fq-torch-hop-job-v2/search.py'
HOP_SHA='a57ae191b9c61aee32b9a505a963de1bd585dfe815bf103d83e827b067a7e3b1'
GPU_SOURCE=ROOT/'artifacts/full-structural-gpu-v2-final-job-v2/search.py'
GPU_SHA='e9ccd10c0238ec6666e67ecfe463e9d06230d45ee4ca075a6b48ac046a8737e3'
ADAPTER_SHA='bc105246e9b60e708ed167ab878c1d3aba1236f38af00eb0b0f7a032f9699292'
ORACLE_SHA='9a5fbbe931559f94dbc7f7080629939fa2d9523113b294f37be5ffba2aa09fd5'
TIES_SHA='3c373cb2338eab652d076e1d072cc5f146ab34300fd170a8d1794692aa7ea14a'


def sha(data):return hashlib.sha256(data).hexdigest()


def unpack(path,expected,encoding):
    source=path.read_bytes()
    if sha(source)!=expected:raise ValueError('Frozen source changed: '+str(path))
    values={node.targets[0].id:ast.literal_eval(node.value)for node in ast.parse(source).body
        if isinstance(node,ast.Assign)and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
        and node.targets[0].id in('CONFIG','PAYLOAD')}
    raw=(lzma.decompress(base64.b85decode(values['PAYLOAD']))if encoding=='xz85'
         else base64.b64decode(values['PAYLOAD']))
    expected_files=values['CONFIG'].get('files',values['CONFIG'].get('embedded_sha256'))
    with zipfile.ZipFile(io.BytesIO(raw))as archive:
        if set(archive.namelist())!=set(expected_files):raise ValueError('Frozen file inventory mismatch')
        files={name:archive.read(name)for name in archive.namelist()}
    for name,data in files.items():
        if sha(data)!=expected_files[name]:raise ValueError('Frozen file hash mismatch: '+name)
    return source,values['CONFIG'],files


def add_local_import_closure(files,available):
    """Resolve transitive local imports from immutable payloads, never live cwd.

    Third-party/stdlib imports are outside this map. Directory preference follows
    the worker's explicit import path; same-directory modules take precedence.
    """
    known={**available,**files};paths=[name for name in known if name.endswith('.py')]
    added={};queue=[name for name in files if name.endswith('.py')];visited=set()
    while queue:
        name=queue.pop()
        if name in visited:continue
        visited.add(name)
        for node in ast.walk(ast.parse(known[name])):
            modules=([alias.name for alias in node.names]if isinstance(node,ast.Import)
                     else[node.module]if isinstance(node,ast.ImportFrom)and node.module else[])
            for module in modules:
                relative=module.replace('.','/')+'.py'
                candidates=[str(Path(name).parent/relative),'experiments/'+relative,
                            'scripts/'+relative,'public_solver/'+relative,relative]
                match=next((path for path in candidates if path in known),None)
                if match is None:
                    by_name=[path for path in paths if Path(path).stem==module.split('.')[0]]
                    if len(by_name)==1:match=by_name[0]
                if match is not None and match not in files:
                    files[match]=known[match];added.setdefault(match,[]).append(dict(importer=name,module=module));queue.append(match)
    return added


def build(args):
    if args.out.exists():raise ValueError('Use a fresh bundle directory')
    source,parent,files=unpack(HOP_SOURCE,HOP_SHA,'xz85')
    _,gpu,gpu_files=unpack(GPU_SOURCE,GPU_SHA,'zip64')
    original_hashes={name:sha(data)for name,data in files.items()}
    for name in set(files)&set(gpu_files):
        if files[name]!=gpu_files[name]:raise ValueError('Conflicting immutable helper: '+name)
    supervisor=source.decode().split('\n',2)[2]
    old="'experiments/fq_torch_hop_pilot.py'"
    if supervisor.count(old)!=1:raise ValueError('Ambiguous worker entrypoint')
    supervisor=supervisor.replace(old,"'experiments/fq_fused_hop_pilot.py'",1)
    old_path="[str(root/'experiments'),str(root/'scripts')]"
    if supervisor.count(old_path)!=1:raise ValueError('Ambiguous child import path')
    supervisor=supervisor.replace(old_path,"[str(root/'experiments'),str(root/'scripts'),str(root/'public_solver')]",1)
    for token in('signal.alarm(475)','worker.wait(timeout=300)'):
        if supervisor.count(token)!=1:raise ValueError('Unexpected inherited process bound')
    config_bytes=args.config.read_bytes();config=json.loads(config_bytes)
    if not 0<config['search_seconds']<=180:raise ValueError('Search bound exceeds authorization')
    if config['quench_steps']!=400 or config['cuda_options']!=['--std=c++17','--fmad=false']:
        raise ValueError('Unreviewed fused quench configuration')
    if not(1<=config['max_packets']<=2048 and 1<=config['max_bytes']<=4*1024**3):
        raise ValueError('Raw retention bound exceeds authorization')
    # Preserve the original settings as provenance; this is the one intentional
    # replacement in the32-file parent payload. Inputs/state/helper code stay exact.
    files['provenance/torch-hop-parent-hop-config.json']=files['hop-config.json']
    files['hop-config.json']=config_bytes
    needed=[name for name in gpu_files if name.startswith('public_solver/')]
    needed+=['experiments/full_structural_gpu_ties.py','experiments/full_structural_gpu_v2_preflight.py',
             'experiments/full_structural_gpu_worker.py']
    for name in needed:files[name]=gpu_files[name]
    if sha(files['experiments/full_structural_gpu_ties.py'])!=TIES_SHA:raise ValueError('Tie adapter changed')
    for name,expected in [('experiments/fq_fused_hop_pilot.py',ADAPTER_SHA),
                          ('experiments/packer_hop_physical_energy.py',ORACLE_SHA)]:
        data=(ROOT/name).read_bytes()
        if sha(data)!=expected:raise ValueError('Unreviewed new source: '+name)
        files[name]=data
    dependency_additions=add_local_import_closure(files,gpu_files)
    # A second fixed-point pass must find no missing immutable local modules.
    if add_local_import_closure(dict(files),gpu_files):raise ValueError('Import closure is incomplete')
    needed=sorted(set(needed)|{name for name in dependency_additions if name in gpu_files})
    proof_path=ROOT/'artifacts/fq-torch-hop-results-v1/completion-proof.json'
    proof_bytes=proof_path.read_bytes();proof=json.loads(proof_bytes)
    if proof['source_sha256']!=HOP_SHA or proof['status']!='COMPLETE' or not proof['private']:
        raise ValueError('Completed private parent proof required')
    files['provenance/torch-hop-completion-proof.json']=proof_bytes
    review=ROOT/'artifacts/fq-torch-hop-independent-delta-review.json'
    files['provenance/torch-hop-independent-review.json']=review.read_bytes()
    files['provenance/corrected-gpu-source-review.json']=(ROOT/'artifacts/full-structural-gpu-v2-final-job-v2/independent_retention_review.json').read_bytes()
    pointer_bytes=(ROOT/'artifacts/current-best-portfolio.json').read_bytes();pointer=json.loads(pointer_bytes)
    baseline=pointer['raw'];report_bytes=Path(baseline['official_report']).read_bytes();report=json.loads(report_bytes)
    if sha(report_bytes)!=baseline['official_report_sha256']or not report['valid']or report['sha256']!=baseline['sha256']:
        raise ValueError('Current canonical report changed')
    files['provenance/fused-current-portfolio-pointer.json']=pointer_bytes
    preserved={name:expected for name,expected in original_hashes.items()if name!='hop-config.json'}
    for name,expected in preserved.items():
        if sha(files[name])!=expected:raise ValueError('Parent state/input/helper mutated: '+name)
    for name,data in files.items():
        if name.endswith('.py'):compile(data,name,'exec')
        if b'KGAT_'in data:raise ValueError('Credential-shaped text forbidden')
    manifest=dict(kind='Persistent fixed-box hop with unchanged corrected fused FP64 quench',
        parent_source_sha256=HOP_SHA,solver_parent_source_sha256=GPU_SHA,
        parent_payload_files=original_hashes,exact_preserved_parent_files=preserved,
        intentional_replacement='hop-config.json; exact original retained as provenance/torch-hop-parent-hop-config.json',
        exact_gpu_files={name:sha(gpu_files[name])for name in needed},
        transitive_dependency_additions=dependency_additions,
        files={name:sha(data)for name,data in files.items()},configuration=config,
        builder_sha256=sha(Path(__file__).read_bytes()),baseline=baseline,
        baseline335=next(row for row in report['results']if row['n']==335),baseline_pointer_sha256=sha(pointer_bytes),
        worker_seconds=300,whole_seconds=480,parent_alarm_seconds=475,server_timeout_seconds=600,
        devices_used=1,no_submission=True,licenses=['MIT','Apache-2.0; original notices retained'],
        supervisor_delta='Only entrypoint and added public_solver import path; all process bounds unchanged.')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,data in files.items():archive.writestr(name,data)
    encoded=base64.b85encode(lzma.compress(stream.getvalue(),preset=6)).decode()
    frozen='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(encoded)+'\n'+supervisor
    compile(frozen,'search.py','exec')
    if len(frozen.encode())>=1_000_000:raise ValueError('Kaggle source limit exceeded')
    args.out.mkdir(parents=True);(args.out/'search.py').write_text(frozen)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,
        dataset_sources=[],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
    result=dict(source_sha256=sha(frozen.encode()),source_bytes=len(frozen.encode()),payload_files=len(files),
                configuration=manifest,launched=False)
    for name,value in[('kernel-metadata.json',metadata),('build_report.json',result)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({key:value for key,value in result.items()if key!='configuration'},indent=2));return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--slug',default='sos54352/squares-fused-persistent-hop')
    build(parser.parse_args())


if __name__=='__main__':main()
