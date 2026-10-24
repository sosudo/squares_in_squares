"""Complete four frozen n693 GPU-selected starts with longer native caps only."""
import time
STARTED = time.monotonic()
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from pathlib import Path
from decimal import Decimal
import argparse,hashlib,json,math,multiprocessing as mp,shutil,signal
import numpy as np
import fq_restart_hop_finish as finish
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from recover_broad_native_returns import current_thresholds

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA='d350aebf10c9bcd07eab3088fd33778cb2e9b55e114eb95bbf0b51a9883f070f'
HELPER_SHA='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
NATIVE=ROOT/'/tmp/squares-fq-portable-target/release/fq'
AGG=ROOT/'artifacts/fq-restart-hop-results-v1'
INPUTS=ROOT/'artifacts/fq-restart-hop-n693-finish-inputs-v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def copy(p,q):
 q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);q.chmod(0o444)
 return dict(path=str(q),sha256=sha(q))
def bound(receipt,folder,name):
 p=folder/'outputs'/name
 if receipt['files'][name]['sha256']!=sha(p):raise ValueError('Downloaded file hash differs: '+name)
 return p

def worker(out,slots,case,binary,deadline,cpu):
 os.sched_setaffinity(0,{cpu});finish.NATIVE_SECONDS=40.;finish.CERTIFICATE_SECONDS=8.
 for slot in slots:
  i=slot['slot'];base=out/'inputs'/f'slot-{i:02d}'
  with np.load(base.with_suffix('.npz'),allow_pickle=False)as z:pose=z['pose'].copy()
  record,q=finish._finish_slot(out/'finish',slot,pose,case,binary,deadline)
  native_input=Path(record['command'][record['command'].index('--in')+1])
  if native_input.read_bytes()!=base.with_suffix('.in').read_bytes():raise ValueError('Regenerated native input differs')
  record['original_input_exact']=True
  atomic_json(out/'finish'/f'slot-{i:02d}-result.json',record)
  print(json.dumps(dict(stage='slot_finished',slot=i,arm=slot['arm'],delta=slot['delta'],status=record['status'],
   worst_side=record.get('worst_certified_side'),gain_vs_frozen=record.get('side_gain'),elapsed=time.monotonic()-STARTED)),flush=True)

def run(out):
 os.setsid();cpus=sorted(os.sched_getaffinity(0))
 if len(cpus)<2:raise ValueError('Two allocated CPU cores required')
 receipt=json.loads((INPUTS/'download-receipt.json').read_text());aggregate=json.loads((AGG/'download-receipt.json').read_text())
 for r in (receipt,aggregate):
  if r['status']!='complete'or r['source_sha256']!=SOURCE_SHA or not r['private_source_verified']:raise ValueError('Exact completed private source receipt required')
 prefix='case-693/';manifest_path=bound(aggregate,AGG,prefix+'finish/manifest.json');records_path=bound(aggregate,AGG,prefix+'finish/results.json')
 manifest=json.loads(manifest_path.read_text());old=json.loads(records_path.read_text());case=manifest['case_config'];assert case['n']==693
 if sha(Path(finish.__file__))!=HELPER_SHA or sha(NATIVE)!=finish.BINARY_SHA:raise ValueError('Frozen helper/binary changed')
 numerical={}
 for remote,digest in manifest['helper_hashes'].items():
  rel=Path(remote).relative_to('/kaggle/working');local=ROOT/rel
  if sha(local)!=digest:raise ValueError('Frozen numerical source changed')
  numerical[str(rel)]=copy(local,out/'source'/rel)
 final_path=bound(aggregate,AGG,prefix+'final-current-best.npz');assert sha(final_path)==manifest['final_archive_sha256']
 index_path=bound(aggregate,AGG,prefix+'raw-index.json');assert sha(index_path)==manifest['index_sha256']
 design_path=bound(aggregate,AGG,prefix+'chain-design.json');assert sha(design_path)==manifest['design_sha256']
 slots=manifest['fixed_slots'];assert [(s['slot'],s['arm'],s['delta'],s['chain'])for s in slots]==[(0,'control',.002,2),(1,'reset',.002,18),(2,'control',.008,11),(3,'reset',.008,30)]
 selected=[];out.joinpath('inputs').mkdir();out.joinpath('finish').mkdir();bindings=[]
 with np.load(final_path,allow_pickle=False)as z:
  for slot in slots:
   record=next(r for r in old if r['slot']==slot['slot']);name=Path(record['selected_archive']).name
   selected_path=bound(receipt,INPUTS,prefix+'finish/'+name)
   assert sha(selected_path)==record['selected_archive_sha256']
   input_name=Path(record['command'][record['command'].index('--in')+1]).name
   input_path=bound(receipt,INPUTS,prefix+'finish/'+input_name);assert sha(input_path)==record['input_sha256']
   with np.load(selected_path,allow_pickle=False)as original:pose=original['pose'].copy()
   assert geometry_sha(pose)==record['selected_geometry_sha256']and np.array_equal(pose,z['best_after'][slot['chain']])
   encoded,offset=finish.fq.encode(pose,math.isqrt(693),math.isqrt(693));assert offset==[0,0]and encoded.encode()==input_path.read_bytes()
   base=out/'inputs'/f"slot-{slot['slot']:02d}";a=copy(selected_path,base.with_suffix('.npz'));b=copy(input_path,base.with_suffix('.in'))
   c=copy(bound(receipt,INPUTS,prefix+'finish/'+Path(record['selected_archive']).name.replace('.selected.npz','.record.json')),base.with_suffix('.original-record.json'))
   slot=dict(slot,committed_best_energy=record['committed_best_energy'],current_energy_not_selected=record['current_energy_not_selected'],fixed_box=record['fixed_box'],last_completed_packet_sha256=record['last_completed_packet_sha256'])
   assert slot['last_completed_packet_sha256']==manifest['last_completed_packet']['sha256']
   selected.append(slot);bindings.append(dict(slot=slot,selected=a,input=b,original_record=c,original_geometry_sha256=record['selected_geometry_sha256'],original_input_exact=True))
 for p,name in [(manifest_path,'original-finish-manifest.json'),(records_path,'original-finish-results.json'),(INPUTS/'download-receipt.json','selected-download-receipt.json'),(AGG/'download-receipt.json','aggregate-download-receipt.json')]:copy(p,out/name)
 threshold,pointer=current_thresholds(out/'comparison-initial')
 case=dict(case,binary_path=str(NATIVE));copy(Path(__file__),out/'source/recovery-wrapper.py')
 proof=dict(frozen_case=case,exact_original_slots=bindings,source_sha256=SOURCE_SHA,helper_sha256=HELPER_SHA,binary_sha256=finish.BINARY_SHA,
  options=finish.OPTIONS,numerical_sources=numerical,changes_only=dict(native_seconds=40,certificate_seconds=8,workers=2,whole_seconds=120),
  allocation=[[0,1],[2,3]],canonical_raw_sha256=pointer['raw']['sha256'],no_reselection=True,no_gpu=True,no_submission=True,
  final_archive_sha256=sha(final_path),last_completed_packet=manifest['last_completed_packet'],wrapper_sha256=sha(Path(__file__)))
 atomic_json(out/'manifest.json',proof);print(json.dumps(dict(stage='exact_inputs_verified',slots=[s['chain']for s in selected],seconds=time.monotonic()-STARTED)),flush=True)
 deadline=STARTED+114.;ctx=mp.get_context('fork')
 children=[ctx.Process(target=worker,args=(out,selected[i*2:i*2+2],case,NATIVE,deadline,cpus[i]))for i in range(2)]
 for p in children:p.start()
 for p in children:p.join(max(0.,deadline-time.monotonic()))
 if any(p.is_alive()for p in children):raise TimeoutError('Fixed allocation exceeded controller deadline')
 if any(p.exitcode!=0 for p in children):raise RuntimeError('Finish child failed')
 records=[json.loads((out/'finish'/f'slot-{i:02d}-result.json').read_text())for i in range(4)]
 latest,current=current_thresholds(out/'comparison-final');donors={};candidates={}
 for r in records:
  if r['status']!='certified':continue
  with np.load(r['certified_archive'],allow_pickle=False)as z:q=z['pose'].copy()
  assert geometry_sha(q)==r['geometry_sha256'];key=f"693__slot{r['slot']}_{r['geometry_sha256']}";donors[key]=q
  r['strict_gain_vs_current']=Decimal(r['worst_certified_side'])<latest[693]
  if r['strict_gain_vs_current']and('693'not in candidates or Decimal(r['worst_certified_side'])<Decimal(candidates['693']['side'])):
   candidates['693']=dict(side=r['worst_certified_side'],squares=[[f'{v:.17g}'for v in row]for row in q],certificate=r['certificate'],
    source='Exact retained GPU BEST state; longer rigid finish of original selected slot',provenance=dict(slot=r['slot'],arm=r['arm'],delta=r['delta'],chain=r['chain'],selected_geometry_sha256=r['selected_geometry_sha256'],geometry_sha256=r['geometry_sha256'],native_output_sha256=r['native_output_sha256'],original_input_sha256=r['input_sha256'],remote_source_sha256=SOURCE_SHA,manifest_sha256=sha(out/'manifest.json')))
 atomic_json(out/'results.json',records);atomic_json(out/'candidates.json',candidates);atomic_npz(out/'certified.npz',donors)
 summary=dict(status='complete',seconds=time.monotonic()-STARTED,n=693,slots=4,certified=len(donors),improved_cases=list(candidates),
  canonical_raw_sha256=current['raw']['sha256'],canonical_side_lower=str(latest[693]),candidates_sha256=sha(out/'candidates.json'),
  results_sha256=sha(out/'results.json'),certified_archive_sha256=sha(out/'certified.npz'),manifest_sha256=sha(out/'manifest.json'),
  no_reselection=True,no_gpu=True,no_submission=True,no_canonical_mutation=True)
 atomic_json(out/'summary.json',summary)
 for p in out.rglob('*'):
  if p.is_file():p.chmod(0o444)
 print(json.dumps(summary),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
 process=mp.get_context('fork').Process(target=run,args=(args.out.resolve(),));process.start();process.join(max(0.,118.-(time.monotonic()-STARTED)))
 forced=process.is_alive()
 if forced:
  try:os.killpg(process.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  process.join(timeout=max(0.,119.-(time.monotonic()-STARTED)))
 atomic_json(args.out/'supervisor.json',dict(exitcode=process.exitcode,forced_kill=forced,seconds=time.monotonic()-STARTED,maximum_seconds=120,workers=2))
