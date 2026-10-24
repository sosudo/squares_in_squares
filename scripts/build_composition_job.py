#!/usr/bin/env python3
"""Prepare, but do not launch, a private bounded CUDA gadget-composition job.

The bundle includes immutable input hashes and original public source notices.
Its GPU preflight constructs known5,10,27-square packings with every selected
composer and independently interval-validates them before searching the actual
incumbent. A parent process enforces an overall subprocess timeout.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]

DRIVER = r'''
import argparse,csv,hashlib,importlib.util,json,math,sys,tempfile,time
from pathlib import Path
import numpy as np
import cupy as cp
from compose_gadgets import legalize,gpu_compose
from validate_submission import Square,validate_puzzle
import compose_gadgets

parser=argparse.ArgumentParser()
parser.add_argument('--config',type=Path,required=True)
parser.add_argument('--root',type=Path,required=True)
args=parser.parse_args()
root=args.root.resolve();config=json.loads(args.config.read_text());started=time.monotonic()
if config.get('source_backed'):
    spec=importlib.util.spec_from_file_location('portfolio_loader',root/'pipeline/portfolio_loader.py')
    loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
    (root/'inputs').mkdir(exist_ok=True)
    loader.reconstruct_portfolio(root/'inputs/baseline.csv',cache_dir=root/'portfolio_cache')
    assert hashlib.sha256((root/'inputs/baseline.csv').read_bytes()).hexdigest()==config['baseline_sha256']
    print(json.dumps({'stage':'baseline reconstructed','sha256':config['baseline_sha256']}),flush=True)
assert cp.cuda.runtime.getDeviceCount()>0,'CUDA unavailable'
cp.cuda.Device(0).use()
name=cp.cuda.runtime.getDeviceProperties(0)['name']
if isinstance(name,bytes):name=name.decode()
L=2+math.sqrt(.5)
five=legalize(np.array([[.5,.5,0],[L-.5,.5,0],[.5,L-.5,0],[L-.5,L-.5,0],[L/2,L/2,math.pi/4]]))
base={n:np.array([(i%math.ceil(math.sqrt(n))+.5,i//math.ceil(math.sqrt(n))+.5,0.)for i in range(n)])for n in range(1,1001)}
checks={}
with tempfile.TemporaryDirectory(prefix='preflight-',dir=root)as directory:
    directory=Path(directory);csv_path=directory/'known_grids.csv'
    with csv_path.open('w',newline='')as stream:
        writer=csv.writer(stream);writer.writerow(['id','n','square_id','x','y','angle']);rid=0
        for n in [5,10,27]:
            for i,row in enumerate(base[n]):writer.writerow([rid,n,i,*row]);rid+=1
    methods=['corner','seam','adaptive']if config['method']=='all'else[config['method']]
    for method in methods:
        bank,report=gpu_compose(base,csv_path,[(five,'known five-square diamond')],
                               root/'sources',directory,method,5.,4)
        checks[method]={'source_compatibility':report.get('_source_compatibility',[])}
        for n,expected in [(5,2+math.sqrt(.5)),(10,3+math.sqrt(.5)),(27,5+math.sqrt(.5))]:
            assert n in bank,(method,n,'known composition missing')
            p=legalize(bank[n]);assert p is not None
            squares=[Square(*(format(float(v),'.17g')for v in row))for row in p]
            certificate=validate_puzzle(n,squares)
            assert certificate['valid'],(method,n,certificate)
            actual=float(certificate['side_upper'])
            assert abs(actual-expected)<1e-5,(method,n,actual,expected)
            checks[method][str(n)]=certificate
        (root/'composition_preflight.json').write_text(json.dumps(
            {'gpu':name,'cupy_version':cp.__version__,'checks':checks,'passed':False,
             'completed_methods':list(checks),'note':'Full preflight not complete until every selected method passes'},indent=2))
        print(json.dumps({'stage':'GPU composition preflight','method':method,'puzzles':[5,10,27],'passed':True}),flush=True)
preflight={'gpu':name,'cupy_version':cp.__version__,'seconds':time.monotonic()-started,'checks':checks,'passed':True}
(root/'composition_preflight.json').write_text(json.dumps(preflight,indent=2))
cp.get_default_memory_pool().free_all_blocks()
argv=['compose_gadgets.py','--baseline',str(root/'inputs/baseline.csv'),
      '--backend','gpu','--source-dir',str(root/'sources'),'--method',config['method'],
      '--seconds',str(config['seconds']),'--bins',str(config['bins']),
      '--baseline-donors',str(config['baseline_donors']),
      '--closure-seconds',str(config['closure_seconds']),
      '--output',str(root/'composition_candidates.json')]
if config['gadget_paths']:argv+=['--gadgets',*config['gadget_paths']]
sys.argv=argv
compose_gadgets.main()
'''

RUNTIME = r'''
import base64,hashlib,io,json,os,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
working=Path('/kaggle/working')if Path('/kaggle/working').is_dir()else Path.cwd()
root=Path(tempfile.mkdtemp(prefix='composition-run-',dir=working))
config=CONFIG
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD)))as archive:
    for entry in archive.infolist():
        target=root/entry.filename
        assert target.resolve().is_relative_to(root.resolve()),entry.filename
        data=archive.read(entry)
        assert hashlib.sha256(data).hexdigest()==config['embedded_sha256'][entry.filename]
        target.parent.mkdir(exist_ok=True,parents=True);target.write_bytes(data)
config['gadget_paths']=[str(root/name)for name in config['embedded_gadgets']]
for name in config['runtime_gadgets']:
    path=Path(name)
    if not path.is_absolute():path=working/path
    assert path.is_file(),f'Required runtime gadget archive missing: {name}'
    config['gadget_paths'].append(str(path.resolve()))
config['runtime_gadget_sha256']={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in config['gadget_paths']}
(root/'composition_config.json').write_text(json.dumps(config,indent=2))
started=time.monotonic();status={'root':str(root),'configuration':config}
command=[sys.executable,'-u',str(root/'pipeline/driver.py'),'--config',str(root/'composition_config.json'),'--root',str(root)]
with (root/'composition.log').open('w')as log:
    try:
        completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=config['wall_seconds'],cwd=root)
        status.update(returncode=completed.returncode,timed_out=False)
    except subprocess.TimeoutExpired:
        status.update(returncode=None,timed_out=True)
status['wall_seconds']=time.monotonic()-started
status['success']=not status['timed_out'] and status['returncode']==0 and(root/'composition_candidates.json').is_file()
(root/'composition_job_summary.json').write_text(json.dumps(status,indent=2))
for name in ['composition_candidates.json','composition_candidates.report.json','composition_preflight.json',
             'composition_job_summary.json','composition.log']:
    source=root/name
    if source.exists():
        destination=working/name
        if destination.exists():raise RuntimeError(f'Refuse to overwrite previous job output: {destination}')
        shutil.copy2(source,destination)
print(json.dumps({k:v for k,v in status.items()if k!='configuration'}),flush=True)
if not status['success']:
    print((root/'composition.log').read_text(errors='replace')[-6000:],flush=True)
    raise RuntimeError('Bounded composition job did not complete successfully; inspect saved log')
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--source-backed', action='store_true',
                        help='Reconstruct baseline from pinned public sources and exact embedded patches')
    parser.add_argument('--baseline-report', type=Path,
                        help='Official metric report; default adjacent STEM-official.json')
    parser.add_argument('--gadgets', nargs='*', type=Path, default=[])
    parser.add_argument('--runtime-gadgets', nargs='*', default=[])
    parser.add_argument('--source-dir', type=Path, default=ROOT/'vendor/lightning_ftmc')
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/composition-job')
    parser.add_argument('--method', choices=['corner','seam','adaptive','all'], default='all')
    parser.add_argument('--seconds', type=float, default=120.)
    parser.add_argument('--wall-seconds', type=float, default=900.)
    parser.add_argument('--closure-seconds', type=float, default=30.)
    parser.add_argument('--bins', type=int, default=16)
    parser.add_argument('--baseline-donors', type=int, default=64)
    parser.add_argument('--slug', default='sos54352/squares-composition-pilot')
    parser.add_argument('--title', help='Default derives from the slug so Kaggle preserves the requested URL')
    parser.add_argument('--max-script-bytes', type=int, default=1000000,
                        help='Kaggle API source size limit; larger local-only bundles need explicit override')
    args = parser.parse_args()
    if args.seconds <= 0 or args.wall_seconds <= 0 or args.closure_seconds < 0:
        parser.error('Invalid wall/extraction budget')
    payload = {}
    for path in sorted(args.source_dir.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            payload['sources/'+str(path.relative_to(args.source_dir))] = path.read_bytes()
    for required in ['gpu_fault_composition.py','gpu_seam_profiles.py','gpu_adaptive_seams.py','LICENSE','NOTICE']:
        if 'sources/'+required not in payload:
            raise ValueError(f'Missing attributed public source: {required}')
    payload['pipeline/compose_gadgets.py'] = (ROOT/'experiments/compose_gadgets.py').read_bytes()
    payload['pipeline/validate_submission.py'] = (ROOT/'scripts/validate_submission.py').read_bytes()
    payload['pipeline/driver.py'] = DRIVER.encode()
    baseline_bytes = args.baseline.read_bytes()
    portfolio_manifest = None
    if args.source_backed:
        from build_source_export_job import make_loader
        report = args.baseline_report or args.baseline.with_name(args.baseline.stem+'-official.json')
        loader, portfolio_manifest, _ = make_loader(args.baseline, report)
        payload['pipeline/portfolio_loader.py'] = loader.encode()
    else:
        payload['inputs/baseline.csv'] = baseline_bytes
    embedded_gadgets = []
    for index, path in enumerate(args.gadgets):
        name = f'inputs/gadgets-{index}.npz'
        payload[name] = path.read_bytes()
        embedded_gadgets.append(name)
    for name, data in payload.items():
        if b'KGAT_' in data:
            raise ValueError(f'Credential-shaped content in payload: {name}')
        if name.endswith('.py'):
            compile(data, name, 'exec')
    manifest = {'source': 'lightningv08 public CUDA Packing Search v21',
                'source_license': 'Apache-2.0 with retained inherited notices',
                'baseline_input': str(args.baseline),
                'baseline_sha256': hashlib.sha256(baseline_bytes).hexdigest(),
                'source_backed': args.source_backed, 'portfolio_sources': portfolio_manifest,
                'method': args.method, 'seconds': args.seconds,
                'wall_seconds': args.wall_seconds, 'closure_seconds': args.closure_seconds,
                'bins': args.bins, 'baseline_donors': args.baseline_donors,
                'embedded_gadgets': embedded_gadgets, 'runtime_gadgets': args.runtime_gadgets,
                'embedded_sha256': {name: hashlib.sha256(data).hexdigest() for name,data in payload.items()}}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as stream:
        for name, data in payload.items():
            stream.writestr(name, data)
    source = 'CONFIG = '+repr(manifest)+'\nPAYLOAD = '+repr(base64.b64encode(archive.getvalue()).decode())+'\n'+RUNTIME
    compile(source, 'search.py', 'exec')
    if len(source.encode()) >= args.max_script_bytes:
        raise ValueError(f'Generated source is {len(source.encode())} bytes, exceeding '
                         f'{args.max_script_bytes}; use --source-backed for Kaggle jobs')
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'search.py').write_text(source)
    (args.out/'job_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    title = args.title or args.slug.rsplit('/', 1)[-1].replace('-', ' ').title()
    metadata = {'id': args.slug, 'title': title,
                'code_file': 'search.py', 'language': 'python', 'kernel_type': 'script',
                'is_private': True, 'enable_gpu': True, 'enable_internet': args.source_backed,
                'dataset_sources': [], 'competition_sources': [], 'kernel_sources': []}
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps({'output': str(args.out), 'script_bytes': len(source.encode()),
                      'baseline_sha256': manifest['baseline_sha256'], 'files': len(payload),
                      'wall_seconds': args.wall_seconds, 'launch_performed': False}))


if __name__ == '__main__':
    main()
