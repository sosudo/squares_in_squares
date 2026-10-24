from pathlib import Path
import sys,json,hashlib,shutil,subprocess,os,time,csv,signal,math
from decimal import Decimal
import numpy as np
ROOT=Path('/workspace/squares_in_squares');sys.path.insert(0,str(ROOT/'experiments'));sys.path.insert(0,str(ROOT/'scripts'))
from fq_active_pilot import decode,digest
from fq_capacity_probe import full_certificate
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from score_official import OFFICIAL_SHA256
class GateDeadline(BaseException):pass
def alarm(*_):raise GateDeadline()
OUT=ROOT/'artifacts/fq-rigid-timeout-trace-n995-v1';OUT.mkdir(exist_ok=False);started=time.monotonic()
records=json.loads((ROOT/'artifacts/fq-timeout-remainder-v1/complete/results.json').read_text());r=next(r for r in records if r['n']==995);assert r['native_status']=='timeout'and r['status']=='no_native_output'
old=r['command'];source_input=Path(old[old.index('--in')+1]);source_binary=Path(old[0]);binary=OUT/'fq'
for source,target in [(source_input,'native.in'),(source_input.with_suffix('.parent.npz'),'parent.npz'),(source_input.with_suffix('.stderr'),'original-30s.stderr'),(source_input.with_suffix('.stdout'),'original-30s.stdout'),(source_binary,'fq'),(Path(__file__),'diagnostic.py')]:shutil.copyfile(source,OUT/target)
binary.chmod(0o500);assert digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d';assert digest(OUT/'native.in')==r['input_sha256']and digest(OUT/'parent.npz')==r['parent_archive_sha256']
pointer_bytes=(ROOT/'artifacts/current-best-portfolio.json').read_bytes();pointer=json.loads(pointer_bytes);baseline=pointer['raw'];assert digest(baseline['path'])==baseline['sha256']and digest(baseline['official_report'])==baseline['official_report_sha256'];report=json.loads(Path(baseline['official_report']).read_text());assert report['valid']and report['puzzles']==1000 and report['sha256']==baseline['sha256']and report['metric_sha256']==OFFICIAL_SHA256
canonical=next(row['side']for row in report['results']if row['n']==995)
with open(baseline['path'])as stream:values=sorted([(int(row['square_id']),[float(row[k])for k in('x','y','angle')])for row in csv.DictReader(stream)if int(row['n'])==995])
assert geometry_sha(np.array([p for _,p in values],float))==r['parent_geometry_sha256'],'Current995parent changed'
command=old.copy();command[0]=str(binary);command[command.index('--in')+1]=str(OUT/'native.in');command[command.index('--out')+1]=str(OUT/'native.out');assert command.count('--v')==1
native_env=os.environ.copy();assert not {key for key in native_env if key.startswith('FQ_')and key not in {'FQ_TR','FQ_LPT'}};native_env.update(FQ_TR='1',FQ_LPT='1')
manifest={'n':995,'baseline':baseline,'baseline_pointer_sha256':hashlib.sha256(pointer_bytes).hexdigest(),'original_record':r,'original30stderr_sha256':digest(OUT/'original-30s.stderr'),'parent_geometry_sha256':r['parent_geometry_sha256'],'input_sha256':digest(OUT/'native.in'),'parent_archive_sha256':digest(OUT/'parent.npz'),'binary_sha256':digest(binary),'command':command,'environment_overrides':{'FQ_TR':'1','FQ_LPT':'1'},'native_seconds_cap':60,'gate_seconds_cap':8,'maximum_total_seconds':75,'workers':1,'same_parent_seed_numeric_flags':True,'diagnostic_source_sha256':digest(__file__)}
atomic_json(OUT/'manifest.json',manifest);native_start=time.monotonic()
with (OUT/'stdout.log').open('wb')as stdout,(OUT/'stderr.log').open('wb')as stderr:
 try:run=subprocess.run(command,stdout=stdout,stderr=stderr,env=native_env,timeout=60);status='returned';rc=run.returncode
 except subprocess.TimeoutExpired:status='timeout';rc=None
result={'n':995,'native_status':status,'returncode':rc,'native_seconds':time.monotonic()-native_start,'output_exists':(OUT/'native.out').exists(),'valid':False,'canonical_side':canonical,'manifest_sha256':digest(OUT/'manifest.json')};atomic_json(OUT/'native-result.json',result)
if result['output_exists']:
 result['native_output_sha256']=digest(OUT/'native.out');signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,min(8.,max(.1,72-(time.monotonic()-started))))
 try:
  q=decode(OUT/'native.out',995)
  if q is None:result['gate_status']='failed_bounded_clearance'
  else:
   result['geometry_sha256']=geometry_sha(q);atomic_npz(OUT/'decoded.npz',{'pose':q});certificate=full_certificate(q);result['certificate']=certificate;result['valid']=certificate['valid'];result['gate_status']='certified'if certificate['valid']else'failed_full_gates'
   if certificate['valid']:
    side=certificate['independent_raw']['side_upper'];result['side']=side;result['side_gain']=str(Decimal(canonical)-Decimal(side));result['score_gain']=float(Decimal(result['side_gain']))/math.sqrt(995)
    key='31_31_34__traced_rigid_'+geometry_sha(q);atomic_npz(OUT/'certified.npz',{key:q});result['certified_npz_sha256']=digest(OUT/'certified.npz')
    candidates={}
    if Decimal(side)<Decimal(canonical):candidates['995']={'side':side,'squares':[[f'{v:.17g}'for v in row]for row in q],'certificate':certificate,'score_gain':result['score_gain'],'source':'Single completion of traced native timeout with unchanged parent and seed','provenance':{'original_job':r['original_job'],'original_seed':r['original_seed'],'parent_geometry_sha256':r['parent_geometry_sha256'],'native_output_sha256':result['native_output_sha256'],'native_binary_sha256':digest(binary),'trace_manifest_sha256':digest(OUT/'manifest.json'),'geometry_sha256':geometry_sha(q)}}
    atomic_json(OUT/'candidates.json',candidates);result['candidates_sha256']=digest(OUT/'candidates.json')
 except GateDeadline:result['gate_status']='certificate_timeout_saved_return'
 except Exception as error:result['gate_status']='certificate_error_saved_return';result['error_type']=type(error).__name__
 finally:signal.setitimer(signal.ITIMER_REAL,0)
result['seconds']=time.monotonic()-started;result['files']={p.name:digest(p)for p in OUT.iterdir()if p.is_file()};atomic_json(OUT/'result.json',result)
for p in OUT.iterdir():p.chmod(0o500 if p.name=='fq'else 0o444)
print(json.dumps({k:v for k,v in result.items()if k not in('certificate','files')}),flush=True)
