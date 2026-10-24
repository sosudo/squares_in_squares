"""Two exact current-reference native controls before the803/861 GPU freeze."""
import time
STARTED=time.monotonic()
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
from decimal import Decimal
import argparse,hashlib,inspect,json,multiprocessing as mp,shutil,signal,sys,types
import numpy as np
import fq_restart_hop_finish as finish
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha
from recover_broad_native_returns import current_thresholds
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import build_fq_restart_hop_job as builder
CASES=(803,861)
BINARY=Path('/tmp/squares-fq-portable-target/release/fq')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def copy(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)

def worker(out,n,cpu,deadline):
 os.sched_setaffinity(0,{cpu});config=json.loads((out/'inputs/restart-config.json').read_text());case=dict(config['cases'][str(n)],binary_path=str(BINARY))
 with np.load(out/'inputs/restart-inputs.npz',allow_pickle=False)as z:pose=z[f'reference_{n}'].copy()
 assert geometry_sha(pose)==case['source_geometry_sha256']
 source=(out/'source/adapted-finish-function.py').read_text();finish.NATIVE_SECONDS=60.;finish.CERTIFICATE_SECONDS=8.;namespace=dict(finish.__dict__)
 exec(compile(source,'<original-current-reference-control>','exec'),namespace)
 folder=out/f'case-{n}';folder.mkdir()
 slot=dict(slot=0,arm='original_reference',delta=.002,chain=None,initializer='current_original_reference',delta_role='seed_selector_only; no compression or perturbation')
 record,q=namespace['_finish_slot'](folder,slot,pose,case,BINARY,deadline)
 assert record['command'][record['command'].index('--seed')+1]=='9710000'
 atomic_json(folder/'result.json',record)
 print(json.dumps(dict(n=n,status=record['status'],side=record.get('worst_certified_side'),gain_vs_source=record.get('side_gain'),native_seconds=record.get('native_seconds'),elapsed=time.monotonic()-STARTED)),flush=True)

def run(out):
 os.setsid();cpus=sorted(os.sched_getaffinity(0));assert len(cpus)>=2
 assert sha(Path(finish.__file__))=='aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
 # Final reviewed paired-job builder; the earlier input-preparation snapshot
 # predates its import-closure fix, so bind the actual final build receipt.
 assert sha(Path(builder.__file__))=='42207fe5db2dd6156128f6f917f91e6d607ff9d37767a6a71f7bc010ca829b03'
 assert json.loads((ROOT/'artifacts/fq-restart-hop-job-v1/build_report.json').read_text())['configuration']['builder_sha256']==sha(Path(builder.__file__))
 assert sha(BINARY)==finish.BINARY_SHA
 # Exact existing preparation code, with only its declared case tuple changed.
 namespace=dict(builder.__dict__,CASES=CASES);prepare=types.FunctionType(builder.prepare_inputs.__code__,namespace)
 prepare(ROOT/'artifacts/current-best-portfolio.json',out/'inputs')
 config=json.loads((out/'inputs/restart-config.json').read_text());proof=json.loads((out/'inputs/restart-input-proof.json').read_text())
 baseline=config['baseline'];assert baseline['sha256']=='28feb2d3059e33db0189aa46c2bdb5f1a0f0c0aa35fb0f2003181595491ba6a3'
 for p in [Path(__file__),Path(builder.__file__),Path(finish.__file__),ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_variant_campaign.py',ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py',ROOT/'vendor/fq/LICENSE']:
  copy(p,out/'source'/p.name)
 source=inspect.getsource(finish._finish_slot);before='UNVERIFIED exact committed BEST array';assert source.count(before)==1
 source=source.replace(before,'Source-bound ORIGINAL current reference; native output requires full gates')
 (out/'source/adapted-finish-function.py').write_text(source)
 threshold,pointer=current_thresholds(out/'comparison-initial')
 manifest=dict(cases=CASES,baseline=baseline,input_npz_sha256=proof['inputs_sha256'],input_proof_sha256=sha(out/'inputs/restart-input-proof.json'),
  native_binary_sha256=finish.BINARY_SHA,source_commit=finish.fq.SOURCE_COMMIT,options=finish.OPTIONS,seed=9710000,
  native_seconds_cap=60,certificate_seconds_cap=8,whole_seconds=90,workers=2,original_geometry_only=True,
  preparation_function_unchanged=True,preparation_cases_override=CASES,adapted_finish_metadata_label_only=True,
  source_hashes={str(p.relative_to(out/'source')):sha(p)for p in (out/'source').iterdir()if p.is_file()},
  input_claim='Original/current arrays are exact source-bound float64 with recorded translation only; output validity still requires all full gates.',
  no_gpu=True,no_submission=True,no_canonical_mutation=True)
 atomic_json(out/'manifest.json',manifest);deadline=STARTED+82.;ctx=mp.get_context('fork')
 children=[ctx.Process(target=worker,args=(out,n,cpus[i],deadline))for i,n in enumerate(CASES)]
 for p in children:p.start()
 for p in children:p.join(max(0.,deadline-time.monotonic()))
 if any(p.is_alive()for p in children):raise TimeoutError('Control child exceeded whole deadline')
 assert all(p.exitcode==0 for p in children)
 latest,current=current_thresholds(out/'comparison-final');records=[];donors={};candidates={};handoff={}
 for n in CASES:
  r=json.loads((out/f'case-{n}/result.json').read_text());records.append(r)
  if r['status']=='certified':
   with np.load(r['certified_archive'],allow_pickle=False)as z:q=z['pose'].copy()
   assert geometry_sha(q)==r['geometry_sha256'];donors[str(n)]=q;r['strict_gain_vs_current']=Decimal(r['worst_certified_side'])<latest[n]
   handoff[str(n)]=dict(reference_source_key=f'reference_{n}',original_side=config['cases'][str(n)]['reference_side'],control_side=r['worst_certified_side'],control_geometry_sha256=r['geometry_sha256'],certified_archive=r['certified_archive'],certified_archive_sha256=r['certified_archive_sha256'],strict_gain_vs_current=r['strict_gain_vs_current'],certificate=r['certificate'])
   if r['strict_gain_vs_current']:
    candidates[str(n)]=dict(side=r['worst_certified_side'],squares=[[f'{v:.17g}'for v in row]for row in q],certificate=r['certificate'],source='Matched current original803/861 native completion control',provenance=dict(parent_geometry_sha256=r['selected_geometry_sha256'],geometry_sha256=r['geometry_sha256'],native_output_sha256=r['native_output_sha256'],native_input_sha256=r['input_sha256'],manifest_sha256=sha(out/'manifest.json')))
 atomic_json(out/'results.json',records);atomic_json(out/'candidates.json',candidates);atomic_npz(out/'certified.npz',donors);atomic_json(out/'case-handoff.json',handoff)
 summary=dict(status='complete',seconds=time.monotonic()-STARTED,cases=CASES,certified=len(donors),improved_cases=list(candidates),canonical_raw_sha256=current['raw']['sha256'],
  input_npz_sha256=proof['inputs_sha256'],manifest_sha256=sha(out/'manifest.json'),candidates_sha256=sha(out/'candidates.json'),results_sha256=sha(out/'results.json'),certified_archive_sha256=sha(out/'certified.npz'),case_handoff_sha256=sha(out/'case-handoff.json'),
  no_gpu=True,no_submission=True,no_canonical_mutation=True)
 atomic_json(out/'summary.json',summary)
 for p in out.rglob('*'):
  if p.is_file():p.chmod(0o444)
 print(json.dumps(summary),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
 process=mp.get_context('fork').Process(target=run,args=(args.out.resolve(),));process.start();process.join(max(0.,88.-(time.monotonic()-STARTED)))
 forced=process.is_alive()
 if forced:
  try:os.killpg(process.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  process.join(timeout=max(0.,89.-(time.monotonic()-STARTED)))
 atomic_json(args.out/'supervisor.json',dict(exitcode=process.exitcode,forced_kill=forced,seconds=time.monotonic()-STARTED,maximum_seconds=90,workers=2))
