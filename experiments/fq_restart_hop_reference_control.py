"""One matched original-reference n693 finish; no GPU state or reselection."""
import time
STARTED=time.monotonic()
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
from decimal import Decimal
import argparse,hashlib,inspect,json,multiprocessing as mp,shutil,signal
import numpy as np
import fq_restart_hop_finish as finish
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from recover_broad_native_returns import current_thresholds
ROOT=Path(__file__).resolve().parents[1]
INPUTS=ROOT/'artifacts/fq-restart-hop-inputs-v1'
WINNER=ROOT/'artifacts/fq-restart-hop-n693-long-finish-v1'
BINARY=Path('/tmp/squares-fq-portable-target/release/fq')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def copy(p,q):
 q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);return dict(path=str(q),sha256=sha(q))
def signature(command):
 command=command.copy()
 for flag in ('--in','--out'):command[command.index(flag)+1]='PATH'
 command[0]='EXACT_BOUND_BINARY';return command

def run(out):
 os.setsid();os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
 assert sha(Path(finish.__file__))=='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
 assert sha(BINARY)==finish.BINARY_SHA
 config=json.loads((INPUTS/'restart-config.json').read_text());proof=json.loads((INPUTS/'restart-input-proof.json').read_text());case=config['cases']['693']
 assert config['baseline']['sha256']=='fc931068f0f4accb37c8ed8b33ea59607e4690440d7c3f98b4b79fbb8c34cffc'
 assert sha(INPUTS/'restart-inputs.npz')==config['inputs_sha256']==proof['inputs_sha256']=='f49522bd1337e243745fe04ae98ebb67eb8659cfc38537318040fdeae020607b'
 with np.load(INPUTS/'restart-inputs.npz',allow_pickle=False)as z:
  pose=z['reference_693'].copy();assert np.array_equal(pose,z['original_693'])
 assert geometry_sha(pose)==case['source_geometry_sha256']==proof['cases']['693']['reference_geometry_sha256']=='0c99323787ff7d1e6602e3576976d0c5692cb03bb213956cfe3079aed1f6809e'
 original=json.loads((WINNER/'results.json').read_text())[0];assert original['slot']==0 and original['chain']==2
 inherited=json.loads((WINNER/'original-finish-manifest.json').read_text())
 for remote,digest in inherited['helper_hashes'].items():
  rel=Path(remote).relative_to('/kaggle/working');assert sha(ROOT/rel)==digest;copy(ROOT/rel,out/'source'/rel)
 threshold,pointer=current_thresholds(out/'comparison-initial')
 for p,name in [(INPUTS/'restart-config.json','original-job-config.json'),(INPUTS/'restart-input-proof.json','original-input-proof.json'),(WINNER/'results.json','gpu-finish-results.json'),(WINNER/'manifest.json','gpu-finish-manifest.json')]:copy(p,out/name)
 atomic_npz(out/'original-reference.npz',{'pose':pose});copy(Path(__file__),out/'source/reference-control-wrapper.py')
 finish.NATIVE_SECONDS=40.;finish.CERTIFICATE_SECONDS=8.
 # Only correct the shared helper's BEST-state label for this ORIGINAL control.
 source=inspect.getsource(finish._finish_slot);old='UNVERIFIED exact committed BEST array';new='Source-bound ORIGINAL pre-GPU reference; native output requires full gates'
 assert source.count(old)==1;source=source.replace(old,new);namespace=dict(finish.__dict__);exec(compile(source,'<original-reference-finish-label>','exec'),namespace)
 (out/'source/adapted-finish-function.py').write_text(source)
 slot=dict(slot=0,arm='control',delta=.002,chain=None,initializer='original_reference_693',paired_gpu_winner_chain=2)
 case=dict(case,binary_path=str(BINARY));(out/'finish').mkdir()
 manifest=dict(case=case,input_geometry_sha256=geometry_sha(pose),input_archive_sha256=sha(INPUTS/'restart-inputs.npz'),
  input_key='reference_693',original_equals_reference=True,comparison_gpu_selected_geometry_sha256=original['selected_geometry_sha256'],
  same_binary_sha256=finish.BINARY_SHA,same_options=finish.OPTIONS,same_seed=9710000,native_seconds=40,certificate_seconds=8,
  whole_seconds=55,workers=1,helper_sha256=sha(Path(finish.__file__)),wrapper_sha256=sha(Path(__file__)),
  adapted_metadata_label_only=True,adapted_function_sha256=hashlib.sha256(source.encode()).hexdigest(),
  initial_canonical_raw_sha256=pointer['raw']['sha256'],initial_canonical_side_lower=str(threshold[693]),
  gpu_winner_worst_side=original['worst_certified_side'],no_gpu_state_initializer=True,no_submission=True,no_canonical_mutation=True)
 atomic_json(out/'manifest.json',manifest)
 record,q=namespace['_finish_slot'](out/'finish',slot,pose,case,BINARY,STARTED+51.)
 assert signature(record['command'])==signature(original['command'])
 assert record['input_sha256']!=original['input_sha256']
 record['matched_command_except_geometry_paths']=True;record['gpu_winner_worst_side']=original['worst_certified_side']
 latest,current=current_thresholds(out/'comparison-final');candidates={}
 if q is not None:
  record['strict_gain_vs_current']=Decimal(record['worst_certified_side'])<latest[693]
  record['better_than_gpu_winner']=Decimal(record['worst_certified_side'])<Decimal(original['worst_certified_side'])
  if record['strict_gain_vs_current']:
   candidates['693']=dict(side=record['worst_certified_side'],squares=[[f'{v:.17g}'for v in row]for row in q],certificate=record['certificate'],source='Matched original pre-GPU reference native completion',provenance=dict(geometry_sha256=record['geometry_sha256'],original_reference_sha256=geometry_sha(pose),native_output_sha256=record['native_output_sha256'],manifest_sha256=sha(out/'manifest.json')))
 atomic_json(out/'result.json',record);atomic_json(out/'candidates.json',candidates)
 summary=dict(status=record['status'],seconds=time.monotonic()-STARTED,old_baseline_side=case['reference_side'],
  current_canonical_raw_sha256=current['raw']['sha256'],current_693_side_lower=str(latest[693]),
  gpu_winner_worst_side=original['worst_certified_side'],control_worst_side=record.get('worst_certified_side'),
  strict_gain_vs_current=record.get('strict_gain_vs_current',False),better_than_gpu_winner=record.get('better_than_gpu_winner',False),
  result_sha256=sha(out/'result.json'),manifest_sha256=sha(out/'manifest.json'),candidates_sha256=sha(out/'candidates.json'),
  no_gpu=True,no_canonical_mutation=True,no_submission=True)
 atomic_json(out/'summary.json',summary)
 for p in out.rglob('*'):
  if p.is_file():p.chmod(0o444)
 print(json.dumps(summary),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
 process=mp.get_context('fork').Process(target=run,args=(args.out.resolve(),));process.start();process.join(max(0.,53.-(time.monotonic()-STARTED)))
 forced=process.is_alive()
 if forced:
  try:os.killpg(process.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  process.join(timeout=max(0.,54.-(time.monotonic()-STARTED)))
 atomic_json(args.out/'supervisor.json',dict(exitcode=process.exitcode,forced_kill=forced,seconds=time.monotonic()-STARTED,maximum_seconds=55,workers=1))
