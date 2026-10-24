"""Freeze one private offline two-T4 birth pilot; this builder never launches."""
from __future__ import annotations
import argparse,ast,base64,hashlib,io,json,lzma
from pathlib import Path
import zipfile
import numpy as np
from build_fq_restart_hop_job import native_payload
from build_fq_fused_hop_job import add_local_import_closure

ROOT=Path(__file__).resolve().parents[1]
ENTRYPOINT='experiments/birth_gpu_pilot.py'
SOURCES=('experiments/birth_continuation.py','experiments/birth_cuda.py',
         'experiments/birth_gpu_preflight.py',ENTRYPOINT,'experiments/birth_finish.py',
         'experiments/fq_restart_hop_finish.py','experiments/fq_capacity_probe.py',
         'research/official_metric_v17.py',
         'vendor/lightning_ftmc/gpu_topology.py','vendor/lightning_ftmc/LICENSE','vendor/lightning_ftmc/NOTICE')
RUNTIME=r'''
import base64,hashlib,io,json,lzma,os,signal,subprocess,sys,zipfile
from pathlib import Path
def stop(signum,frame):raise SystemExit('bounded birth supervisor stopped')
signal.signal(signal.SIGALRM,stop);signal.alarm(595)
root=Path('/kaggle/working/birth-run');root.mkdir(parents=True,exist_ok=False)
raw=lzma.decompress(base64.b85decode(PAYLOAD));archive=zipfile.ZipFile(io.BytesIO(raw))
assert set(archive.namelist())==set(CONFIG['files'])
for name,expected in CONFIG['files'].items():
    path=root/name
    assert path.resolve().is_relative_to(root.resolve())
    data=archive.read(name);assert hashlib.sha256(data).hexdigest()==expected
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
(root/'bin/fq').chmod(0o755)
env=dict(os.environ)
env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    PYTHONPATH=os.pathsep.join([str(root/'experiments'),str(root/'scripts')]))
worker=None
try:
    worker=subprocess.Popen([sys.executable,str(root/'experiments/birth_gpu_pilot.py')],cwd=root,env=env,start_new_session=True)
    worker.wait(timeout=575)
finally:
    if worker is not None:
        registry=root/'arm-groups.json'
        if registry.exists():
            groups=json.loads(registry.read_text())
            assert groups['parent_pid']==worker.pid and len(groups['groups'])<=2
            for pid in groups['groups']:
                assert isinstance(pid,int)and pid>1 and pid!=os.getpgrp()
                try:os.killpg(pid,signal.SIGKILL)
                except ProcessLookupError:pass
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        worker.wait(timeout=3)
    for name in ('birth-results.zip','completion.json','output-manifest.json'):
        source=root/name
        if source.exists():
            import shutil
            shutil.copyfile(source,Path('/kaggle/working')/name)
    receipt=dict(returncode=worker.returncode if worker else None,no_submission=True,whole_seconds=600)
    Path('/kaggle/working/supervisor.json').write_text(json.dumps(receipt,indent=2)+'\n')
signal.alarm(0)
'''

def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,x):path.write_text(json.dumps(x,indent=2)+'\n')

def build(args):
    assert not args.out.exists();config=json.loads((args.inputs/'birth-config.json').read_text())
    proof=json.loads((args.inputs/'input-proof.json').read_text());design=json.loads((args.inputs/'chain-design.json').read_text())
    assert set(config['cases'])==set(design)=={'498','587'}and config['search_seconds']==300 and config['chains']==32
    assert config['maximum_cycles']==32 and config['quench_steps_per_growth_stage']==1200
    assert config['work_seconds']==570 and config['whole_seconds']==600 and config['server_seconds']==720
    assert sha((args.inputs/'birth-inputs.npz').read_bytes())==config['inputs_sha256']==proof['inputs_sha256']
    assert sha((args.inputs/'chain-design.json').read_bytes())==config['design_sha256']==proof['design_sha256']
    with np.load(args.inputs/'birth-inputs.npz',allow_pickle=False)as z:
        assert set(z.files)==set(proof['arrays'])
        for k in z.files:
            p=z[k];r=proof['arrays'][k]
            assert list(p.shape)==r['shape']and p.dtype.str==r['dtype']and sha(p.tobytes())==r['geometry_sha256']
    native,files=native_payload();original={name:sha(data)for name,data in files.items()}
    for name in SOURCES:files[name]=(ROOT/name).read_bytes()
    # Available local modules are only pulled when an executed import requires
    # them; keep transitive import bytes explicit and compile every payload.
    available={p.relative_to(ROOT).as_posix():p.read_bytes()for folder in('experiments','scripts')for p in(ROOT/folder).glob('*.py')}
    dependencies=add_local_import_closure(files,available)
    for p in args.inputs.rglob('*'):
        if not p.is_file():continue
        name=p.relative_to(args.inputs).as_posix();files[name]=p.read_bytes()
    for name in ('birth-targets-public35-confirmation.json','birth-driver-controls-v1.json'):
        files['provenance/'+name]=(ROOT/'artifacts'/name).read_bytes()
    for folder in ('artifacts/birth-original-controls-v1','artifacts/birth-cpu-controls-v2','artifacts/birth-cuda-cpu-controls-v2','artifacts/birth-objective-review-v1'):
        directory=ROOT/folder
        # Exact reports and selected source/input/output ancestry are retained;
        # host shared library is an executable control artifact, not a runtime
        # dependency, and remains locally pinned rather than shipped.
        for p in directory.rglob('*'):
            if p.is_file()and p.suffix!='.so':files['provenance/'+Path(folder).name+'/'+p.relative_to(directory).as_posix()]=p.read_bytes()
    for name,expected in original.items():assert sha(files[name])==expected,'Native/dependency bytes changed'
    for name,data in files.items():
        assert not Path(name).is_absolute()and '..'not in Path(name).parts
        if name.endswith('.py'):compile(data,name,'exec')
        assert b'KGAT_'not in data
    manifest=dict(kind='Exact497/586 scaffold single-square birth continuation; proposal-only mixed sizes',
        files={name:sha(data)for name,data in files.items()},configuration=config,
        source_hashes={name:sha(files[name])for name in SOURCES},builder_sha256=sha(Path(__file__).read_bytes()),
        dependencies=dependencies,native_binary_sha256=sha(files['bin/fq']),
        original_native_file_inventory=original,native_dependency_license_count=native['dependency_license_count'],
        machine_shape='NvidiaTeslaT4',devices_allocated=2,devices_used=2,
        whole_seconds=600,server_seconds=720,maximum_allocated_gpu_seconds=1200,server_fail_safe_gpu_seconds=1440,
        no_submission=True,no_canonical_mutation=True,actual_gpu_controls_required=True,
        original_all_unit_kernel_and_metric_modified=False,
        objective_controls=dict(cpu_report_sha256=sha((ROOT/'artifacts/birth-cpu-controls-v2/report.json').read_bytes()),
            exact_cuda_host_report_sha256=sha((ROOT/'artifacts/birth-cuda-cpu-controls-v2/report.json').read_bytes()),
            corrected_parallel_unequal_tie='Select exact active depths by one-sided birth-angle depth derivative, then average the two limiting gradients; the invalid independent amin/abs gradient is retained only as failed evidence.',
            lambda1_identity='Exact all-unit forward energy and symmetric exact-axis tie gradient against the dense physical SAT reference. This is a new proposal objective, not the weighted/clearance quench loss; original kernel and metric files are untouched.',
            mixed_state_admission='No mixed-size state is a unit packing or eligible for native finish; only explicitly recorded stage11 with all birth sizes1 enters fullN pool.',
            fresh_history='A new L-BFGS work/history allocation and fresh physical evaluation for each growth stage; no cross-size Metropolis rule.'))
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as z:
        for name,data in sorted(files.items()):z.writestr(zipfile.ZipInfo(name,(1980,1,1,0,0,0)),data)
    payload=base64.b85encode(lzma.compress(stream.getvalue(),preset=9)).decode()
    source='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(payload)+'\n'+RUNTIME
    compile(source,'search.py','exec');data=source.encode();assert len(data)<1_000_000,len(data)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,
        dataset_sources=[],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
    args.out.mkdir(parents=True);(args.out/'search.py').write_bytes(data)
    save(args.out/'kernel-metadata.json',metadata);save(args.out/'manifest.json',manifest)
    report=dict(source_sha256=sha(data),source_bytes=len(data),files=len(files),input_sha256=config['inputs_sha256'],
        no_launch=True,actual_gpu_controls_required=True,whole_seconds=600,server_seconds=720)
    save(args.out/'build-report.json',report);print(json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--slug',default='sos54352/squares-junction-single-birth-v1');build(p.parse_args())
