"""Freeze native/CPU fixtures and a bounded private GPU objective benchmark."""
import argparse
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path
import sys
import zipfile
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from fq_torch_objective import initial_lines,near_pairs,guard_pair_list
from check_fq_torch_objective import call_native,tensors,torch_eval


def sha(data):return hashlib.sha256(data).hexdigest()


SUPERVISOR=r'''
import base64,hashlib,io,json,lzma,os,signal,subprocess,sys,time,zipfile
from pathlib import Path
os.chdir('/kaggle/working');root=Path.cwd();started=time.monotonic();child=None
def timed_out(signum,frame):
    if child is not None and child.poll()is None:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    raise TimeoutError('Whole benchmark deadline')
signal.signal(signal.SIGALRM,timed_out);signal.alarm(295)
with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(PAYLOAD))))as archive:
    assert set(archive.namelist())==set(CONFIG['files'])
    for name in archive.namelist():
        path=root/name;assert path.resolve().is_relative_to(root)
        data=archive.read(name);assert hashlib.sha256(data).hexdigest()==CONFIG['files'][name]
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
Path('job_manifest.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
with open('benchmark.log','w')as log:
    child=subprocess.Popen([sys.executable,'-u','benchmark.py'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    timeout=False
    try:child.wait(timeout=120)
    except subprocess.TimeoutExpired:
        timeout=True
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=5)
summary=dict(exitcode=child.returncode,timed_out=timeout,seconds=time.monotonic()-started,no_optimization=True)
if Path('benchmark-report.json').exists():
    report=json.loads(Path('benchmark-report.json').read_text())
    summary.update(phase=report['phase'],settings=len(report['benchmarks']),hardware=report['hardware'],
                   report_sha256=hashlib.sha256(Path('benchmark-report.json').read_bytes()).hexdigest())
Path('supervisor-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
signal.alarm(0)
assert child.returncode==0 and summary.get('phase')=='complete'and summary.get('settings')==36
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();assert not args.out.exists()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    objective=ROOT/'experiments/fq_torch_objective.py'
    assert sha(objective.read_bytes())=='a5d97575daa368b14b71d4f9cf514abe884217240c31c3d485f761f46022ff89'
    original=ROOT/'artifacts/fq-torch-objective-v1'
    proof=json.loads((original/'completion-proof.json').read_text())
    for path,expected in proof['hashes'].items():assert sha((ROOT/path).read_bytes())==expected,path
    with np.load(original/'references.npz',allow_pickle=False)as z:references={int(k):z[k]for k in z.files}
    rng=np.random.default_rng(9127345);arrays={};cases=[]
    oracle=original/'native_prob_oracle'
    for n,reference in sorted(references.items()):
        pairs=near_pairs(reference);p=reference.copy()
        p[:,:2]+=rng.normal(0,.007,(n,2));p[:,2]+=rng.normal(0,.02,n)
        guard_pair_list(reference,p)
        extent=.5*(np.abs(np.cos(reference[:,2]))+np.abs(np.sin(reference[:,2])))
        side=float((reference[:,:2]+extent[:,None]).max()-.012)
        for ri,radius in enumerate((0.,.3)):
            prefix=f'n{n}_r{ri}';lines=initial_lines(p,pairs,radius)+rng.normal(0,.015,(len(pairs),2))
            wl=rng.uniform(0,.5,(n,4,4));pl=rng.uniform(0,.5,(len(pairs),8));mu=71.
            native=call_native(oracle,p,side,lines,pairs,wl,pl,mu,radius,False)
            cpu64=torch_eval(tensors(p,side,lines,pairs,wl,pl,torch.float64),mu,radius,False)
            cpu32=torch_eval(tensors(p,side,lines,pairs,wl,pl,torch.float32),mu,radius,False)
            errors=[float(np.max(np.abs(np.asarray(a)-np.asarray(b))))for a,b in zip(native,cpu64)]
            assert max(errors)<2e-9
            values=dict(reference=reference,poses=p,side=np.array(side),lines=lines,pairs=pairs,
                        wall_lambda=wl,pair_lambda=pl,native_value=np.array(native[0]),native_gradient=native[2],
                        cpu32_value=np.array(cpu32[0]),cpu32_gradient=cpu32[2])
            for name,value in values.items():arrays[prefix+'_'+name]=value
            cases.append(dict(prefix=prefix,n=n,pairs=len(pairs),radius=radius,mu=mu,
                              cpu64_native_errors=errors,
                              cpu32_native_gradient_error=float(np.max(np.abs(cpu32[2]-native[2])))))
    stream=io.BytesIO();np.savez(stream,**arrays);archive=stream.getvalue()
    controls=dict(cases=cases,archive_sha256=sha(archive),
                  arrays={k:dict(shape=list(p.shape),dtype=p.dtype.str,sha256=sha(p.tobytes()))for k,p in arrays.items()},
                  reference_sha256=sha((original/'references.npz').read_bytes()),
                  native_binary_sha256=sha(oracle.read_bytes()),native_source_sha256=proof['native_source_sha256'],
                  original_proof_sha256=sha((original/'completion-proof.json').read_bytes()),
                  relative_absolute_gate_note='F64:1e-10/1e-8;F32 CPU:3e-5/.004grad,.002energy;F32 native:1e-4/.01grad,.003energy. Errors are always reported.')
    data={'fq_torch_objective.py':objective.read_bytes(),'benchmark.py':(ROOT/'experiments/fq_torch_benchmark_runtime.py').read_bytes(),
          'controls.npz':archive,'controls.json':json.dumps(controls,indent=2).encode(),
          'provenance/native_prob_oracle.rs':(original/'native_prob_oracle.rs').read_bytes(),
          'provenance/cpu-native-report.json':(original/'report.json').read_bytes(),
          'provenance/independent-review.json':(original/'independent_review.json').read_bytes(),
          'provenance/completion-proof.json':(original/'completion-proof.json').read_bytes(),
          'vendor/fq/LICENSE':(ROOT/'vendor/fq/LICENSE').read_bytes(),
          'vendor/fq/SOURCE_MANIFEST.json':(ROOT/'vendor/fq/SOURCE_MANIFEST.json').read_bytes()}
    for name,b in data.items():
        if name.endswith('.py'):compile(b,name,'exec')
        assert b'KGAT_'not in b
    config=dict(kind='Native-pinned lifted ALM GPU feasibility benchmark only',
                worker_seconds=120,whole_seconds=300,server_timeout_seconds=420,
                files={k:sha(v)for k,v in data.items()},builder_sha256=sha(Path(__file__).read_bytes()),
                objective_sha256=sha(objective.read_bytes()),controls_sha256=sha(data['controls.json']),
                source_commit=proof['source_commit'],license='MIT;vendor/fq/LICENSE',
                no_optimizer=True,no_submission=True,devices_used=1)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as z:
        for name,b in data.items():z.writestr(name,b)
    source='CONFIG='+repr(config)+'\nPAYLOAD='+repr(base64.b85encode(lzma.compress(stream.getvalue(),preset=6)).decode())+'\n'+SUPERVISOR
    compile(source,'benchmark-job.py','exec');assert len(source.encode())<1_000_000
    args.out.mkdir(parents=True);(args.out/'search.py').write_text(source)
    slug='sos54352/squares-fq-torch-objective-benchmark'
    metadata=dict(id=slug,title='Squares FQ Torch Objective Benchmark',code_file='search.py',language='python',
                  kernel_type='script',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,
                  dataset_sources=[],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
    report=dict(source_sha256=sha(source.encode()),source_bytes=len(source.encode()),payload_files=len(data),
                cases=len(cases),controls=controls,configuration=config,launched=False)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (args.out/'build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    local=args.out/'local-replay';local.mkdir()
    for name,b in data.items():p=local/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    print(json.dumps({k:v for k,v in report.items()if k not in('controls','configuration')},indent=2))


if __name__=='__main__':main()
