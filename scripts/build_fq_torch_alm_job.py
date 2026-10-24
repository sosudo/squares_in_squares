"""Freeze one bounded FP64 ALM prototype; never launch or submit."""
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
from build_full_structural_gpu_job import local_sources

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from full_structural_gpu_moves import geometry_sha


def sha(data):return hashlib.sha256(data).hexdigest()


SUPERVISOR=r'''
import base64,hashlib,io,json,lzma,os,signal,subprocess,sys,time,zipfile
from pathlib import Path
os.chdir('/kaggle/working');root=Path.cwd();started=time.monotonic();worker=None
def stop(signum,frame):
    if worker is not None and worker.poll()is None:
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    raise TimeoutError('Whole prototype deadline')
signal.signal(signal.SIGALRM,stop);signal.alarm(475)
with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(PAYLOAD))))as z:
    assert set(z.namelist())==set(CONFIG['files'])
    for name in z.namelist():
        path=root/name;assert path.resolve().is_relative_to(root)
        data=z.read(name);assert hashlib.sha256(data).hexdigest()==CONFIG['files'][name]
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
Path('job_manifest.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(root/'experiments'),str(root/'scripts')]),
         OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
with open('worker.log','w')as log:
    worker=subprocess.Popen([sys.executable,'-u','experiments/fq_torch_alm_pilot.py'],stdout=log,stderr=subprocess.STDOUT,
                            env=env,start_new_session=True)
    timeout=False
    try:worker.wait(timeout=300)
    except subprocess.TimeoutExpired:
        timeout=True
        try:os.killpg(worker.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        worker.wait(timeout=5)
summary=dict(exitcode=worker.returncode,timed_out=timeout,seconds=time.monotonic()-started)
if Path('pilot-summary.json').exists():summary['pilot']=json.loads(Path('pilot-summary.json').read_text())
Path('supervisor-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
signal.alarm(0)
assert worker.returncode==0 and summary.get('pilot',{}).get('controls_passed')
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists()
    parent=ROOT/'artifacts/fq-torch-benchmark-results-v1/outputs'
    controls_data=(parent/'controls.npz').read_bytes();assert sha(controls_data)=='de4d1c935fb605632a5f4c40e940d4e3dcbbef8391bdda59551d8d54ff17a568'
    with np.load(io.BytesIO(controls_data),allow_pickle=False)as z:
        arrays={f'reference_{n}':z[f'n{n}_r0_reference']for n in(147,299,335)}
        for field in('poses','side','lines','pairs','wall_lambda','pair_lambda','native_value','native_gradient'):
            arrays['native_'+field]=z['n335_r0_'+field]
    source43=ROOT/'artifacts/joint-mis335-full-starts-v1';blob=(source43/'starts.npz').read_bytes()
    assert sha(blob)=='1a3bffda9a6617b3a32a79d6f32e809dd59308e23cbcbfb5d0f214b96995f832'
    key43='18_18_11__joint335_9bd82e9e7fd1d62c036cd8a1720e29ca0fa98d805d5677d3246bd3e46abf75c1'
    with np.load(io.BytesIO(blob),allow_pickle=False)as z:arrays['source_43']=z[key43]
    cert43=json.loads((source43/'certificates.json').read_text());assert cert43[key43]['actual']['valid']
    assert cert43[key43]['actual']['geometry_sha256']==geometry_sha(arrays['source_43'])
    source37=ROOT/'artifacts/n335-buffered-seed-v1';blob=(source37/'retained-seeds.npz').read_bytes()
    assert sha(blob)=='e1e2b2d38986a181b6c7079aa1bee2d242f75ec9da73ec6661cff229ddc9be32'
    key37='18_18_11__initial_2b991001752920f046765b9d90bbc01e1e55353b5b405d5669cad43ed2921b80'
    with np.load(io.BytesIO(blob),allow_pickle=False)as z:arrays['source_37']=z[key37]
    cert37=json.loads((source37/'initial-certificate.json').read_text());assert cert37['valid']
    assert geometry_sha(arrays['source_43'])==key43.split('__joint335_')[1]
    assert geometry_sha(arrays['source_37'])==key37.split('__initial_')[1]
    pointer=ROOT/'artifacts/current-best-portfolio.json';current=json.loads(pointer.read_text());baseline=current['raw']
    report_bytes=Path(baseline['official_report']).read_bytes();assert sha(report_bytes)==baseline['official_report_sha256']
    report=json.loads(report_bytes);assert report['sha256']==baseline['sha256']and report['valid']
    target=float(next(r['side']for r in report['results']if r['n']==335))
    stream=io.BytesIO();np.savez(stream,**arrays);inputs=stream.getvalue()
    config=dict(inputs_sha256=sha(inputs),arrays={k:dict(shape=list(v.shape),dtype=v.dtype.str,sha256=sha(v.tobytes()))for k,v in arrays.items()},
        exploratory_sources=['reference_335','source_43','source_37'],current_335_side=target,
        baseline=baseline,pointer_sha256=sha(pointer.read_bytes()),replicas=32,
        held_box='Each source own side+1e-8;allposecoordinatesfree',radii=[.3,.1,0.],
        compression_depths=[.0002,.001,.01,.02],stages=['held-rounded','held-rounded-return','held-rigid','rigid-compression','rigid-release'],
        optimization_seconds=180,worker_seconds=300,whole_seconds=480,server_timeout_seconds=600,
        all_raw_outer_stages_retained=True,raw_is_unverified=True,maximum_postrun_gate_attempts=4,native_finishing_performed=False,
        source43_attribution='One-tilt removal/filler rearrangement from canonical335;no rounded-source units',
        source37_attribution='Buffered n5+n235 construction;initialside~.00373 worse;no record claim')
    data=local_sources(['experiments/fq_torch_alm_pilot.py','scripts/score_official.py','scripts/validate_submission.py','research/official_metric_v17.py'])
    data['pilot-inputs.npz']=inputs;data['pilot-config.json']=json.dumps(config,indent=2).encode()
    for source,names,label in[(source43,['proof.json','certificates.json','source-mixture.json'],'source43'),
                             (source37,['manifest.json','initial-certificate.json'],'source37')]:
        for name in names:data['provenance/'+label+'/'+name]=(source/name).read_bytes()
    for name in('vendor/fq/LICENSE','vendor/fq/NOTICE','vendor/fq/SOURCE_MANIFEST.json','vendor/lightning_ftmc/SOURCE_MANIFEST.json'):
        data[name]=(ROOT/name).read_bytes()
    data['provenance/objective-review.json']=(ROOT/'artifacts/fq-torch-objective-v1/independent_review.json').read_bytes()
    data['provenance/gpu-objective-proof.json']=(ROOT/'artifacts/fq-torch-benchmark-results-v1/completion-proof.json').read_bytes()
    data['provenance/solver-independent-controls.json']=(ROOT/'artifacts/fq-torch-alm-independent-review-v1/report.json').read_bytes()
    for name,blob in data.items():
        if name.endswith('.py'):compile(blob,name,'exec')
        assert b'KGAT_'not in blob
    manifest=dict(kind='Minimal FP64 batched smooth ALM prototype',worker_seconds=300,whole_seconds=480,server_timeout_seconds=600,
        files={k:sha(v)for k,v in data.items()},builder_sha256=sha(Path(__file__).read_bytes()),
        configuration=config,source_commit='659ee62e4a9d39542a1146e8b011cc3ab6407ede',license='MIT;vendor/fq/LICENSE',
        no_submission=True,devices_used=1)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as z:
        for name,blob in data.items():z.writestr(name,blob)
    source='CONFIG='+repr(manifest)+'\nPAYLOAD='+repr(base64.b85encode(lzma.compress(stream.getvalue(),preset=6)).decode())+'\n'+SUPERVISOR
    compile(source,'search.py','exec');assert len(source.encode())<1_000_000
    args.out.mkdir(parents=True);(args.out/'search.py').write_text(source)
    metadata=dict(id='sos54352/squares-fq-torch-alm-prototype',title='Squares FQ Torch ALM Prototype',code_file='search.py',language='python',
        kernel_type='script',is_private=True,enable_gpu=True,enable_tpu=False,enable_internet=False,
        dataset_sources=[],kernel_sources=[],competition_sources=[],machine_shape='NvidiaTeslaT4')
    report=dict(source_sha256=sha(source.encode()),source_bytes=len(source.encode()),payload_files=len(data),configuration=manifest,launched=False)
    for name,value in [('kernel-metadata.json',metadata),('build_report.json',report)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k!='configuration'},indent=2))


if __name__=='__main__':main()
