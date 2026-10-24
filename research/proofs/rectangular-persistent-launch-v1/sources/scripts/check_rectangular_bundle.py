#!/usr/bin/env python3
"""Replay exact frozen payload/import/input preparation without CUDA or native runs."""
import argparse,ast,base64,hashlib,io,json,lzma,os,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
CODE=r'''
import hashlib,json
from pathlib import Path
import numpy as np
import fq_rectangular_persistent_pilot as driver
import fq_rectangular_persistent_search as searcher
import fq_rectangular_persistent_finish as finish
root=Path.cwd();report={}
for name,module in [('driver',driver),('search',searcher),('finish',finish)]:
 path=Path(module.__file__).resolve();assert path.is_relative_to(root)
 report[name]=dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
protocol=driver.protocol();driver.prepare(root,protocol);finish.check_helper()
checks={}
for key in searcher.FAMILIES:
 folder=root/('family-'+key);config,bank=searcher.load_family(folder);design=searcher.design(config)
 assert len(design)==64 and set(r['source_key']for r in design)==set(config['seed_keys'])
 assert sorted(set(r['delta']for r in design))==[.002,.01,.03,.06]
 for source in config['seed_keys']:
  q=bank[source];assert q.shape==(config['n'],3)and q.dtype==np.float64
  assert searcher.array_sha(q)==config['seed_array_sha256'][source]
  for cut in searcher.CUTS:assert sum(r['source_key']==source and r['delta']==cut for r in design)==4
 for round in(0,1,32):
  signatures=[tuple(searcher.random_stream(design[0]['case_seed'],round,i).random(5))for i in range(64)]
  assert len(set(signatures))==64
 checks[key]=dict(n=config['n'],chains=len(design),seed_hashes=config['seed_array_sha256'],
  family_config_sha256=hashlib.sha256((folder/'family-config.json').read_bytes()).hexdigest(),
  reference_f_lower=config['reference_f_lower'],reference_f_upper=config['reference_f_upper'])
report.update(families=checks,typed_count_design_and_seed_checks=True,exact_prepare_without_cuda=True,actual_cuda_run=False,native_execution=False)
Path('import-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
'''
def main(args):
 source=(args.job/'search.py').read_bytes();values={node.targets[0].id:ast.literal_eval(node.value)for node in ast.parse(source).body[:2]}
 manifest=values['CONFIG'];root=Path(tempfile.mkdtemp(prefix='rectangular-frozen-smoke-',dir='/tmp'))
 with zipfile.ZipFile(io.BytesIO(lzma.decompress(base64.b85decode(values['PAYLOAD']))))as z:
  assert set(z.namelist())==set(manifest['files'])
  for name in z.namelist():
   data=z.read(name);assert sha(data)==manifest['files'][name];path=root/name;assert path.resolve().is_relative_to(root)
   path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 for name,r in manifest['fixture_files'].items():
  src=args.fixture/name;data=src.read_bytes();assert sha(data)==r['sha256']and len(data)==r['bytes']
  dst=root/name;assert not dst.exists();dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
 env=dict(os.environ,PYTHONPATH=os.pathsep.join(str(root/p)for p in('experiments','scripts','public_solver')),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
 result=subprocess.run([str(ROOT/'.venv/bin/python'),'-c',CODE],cwd=root,env=env,text=True,capture_output=True,timeout=45)
 if result.returncode:
  print(result.stdout);print(result.stderr);raise SystemExit(result.returncode)
 report=json.loads((root/'import-smoke.json').read_text());report.update(source_sha256=sha(source),source_bytes=len(source),
  payload_files=len(manifest['files']),fixture_members=len(manifest['fixture_files']),exact_payload_and_fixture_hashes_verified=True,
  isolated_extraction_directory=str(root),check_source_sha256=sha(Path(__file__).read_bytes()))
 (args.job/'local_import_review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(source_sha256=report['source_sha256'],payload_files=report['payload_files'],fixture_members=report['fixture_members'],imported=True,preparation=True,receipt_sha256=sha((args.job/'local_import_review.json').read_bytes()))))
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--job',type=Path,required=True);ap.add_argument('--fixture',type=Path,required=True);main(ap.parse_args())
