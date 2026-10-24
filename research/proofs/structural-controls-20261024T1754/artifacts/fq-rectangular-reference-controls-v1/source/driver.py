"""Four exact certified original-reference controls for rectangular GPU inputs.

Only the finisher's initializer-status description changes. Numerical commands,
rectangle offsets, full gates and durable returned-pose retention stay identical.
"""
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse
import hashlib
import inspect
import json
import multiprocessing as mp
from pathlib import Path
import shutil
import time
import numpy as np
import fq_rectangular_persistent_finish as finish

ROOT=Path(finish.terminal.__file__).resolve().parents[1]
FINISH_SHA='47d391ec9541f70313451c55036702a21c6a8562dc75a75f7ba09d67a50d75b9'
INPUT_SHA='1c2d92e19f8cd35d275122b8ed5746aba03c0ed113d4650a34d19447fbb87751'
FAMILIES=('5_17_7','7_19_13','7_20_14','8_21_13')


def source_function():
    if finish.sha(finish.__file__)!=FINISH_SHA:raise ValueError('reviewed_rectangular_finisher_changed')
    source=inspect.getsource(finish._finish_slot)
    old="input_status='UNVERIFIED exact committed BEST'"
    new="input_status='CERTIFIED immutable original v2 reference control; not a GPU state'"
    if source.count(old)!=1:raise ValueError('unexpected_initializer_status_source')
    generated=source.replace(old,new,1)
    namespace=dict(vars(finish));exec(compile(generated,'<reference-control status-only clone>','exec'),namespace)
    return namespace['_finish_slot'],dict(original_function_sha256=hashlib.sha256(source.encode()).hexdigest(),
                                        generated_function_sha256=hashlib.sha256(generated.encode()).hexdigest(),
                                        replacements=1,change='Initializer status only; all numerical behavior unchanged.')


def prepare(out,inputs):
    out.mkdir(exist_ok=False);(out/'source').mkdir();(out/'inputs').mkdir();(out/'trials').mkdir();(out/'bin').mkdir()
    fn,derivation=source_function();config=json.loads((inputs/'rectangular-input-config.json').read_text())
    proof=json.loads((inputs/'rectangular-input-proof.json').read_text())
    archive=inputs/'rectangular-inputs.npz'
    if finish.sha(archive)!=INPUT_SHA or config['inputs_sha256']!=INPUT_SHA or proof['inputs_sha256']!=INPUT_SHA:
        raise ValueError('frozen_v2_inputs_changed')
    if finish.sha(inputs/'rectangular-input-config.json')!=proof['config_sha256']:raise ValueError('input_config_changed')
    bindings=[]
    def copy(src,dst):
        shutil.copyfile(src,dst);dst.chmod(0o444);bindings.append(dict(original_path=str(src),path=str(dst),sha256=finish.sha(dst)));return dst
    copy(Path(__file__),out/'source/driver.py');copy(Path(finish.__file__),out/'source/finisher.py')
    for name in ('rectangular-inputs.npz','rectangular-input-config.json','rectangular-input-proof.json','prepare-source.py'):
        copy(inputs/name,out/'inputs'/name)
    binary=copy(Path('/tmp/squares-fq-portable-target/release/fq'),out/'bin/fq')
    if finish.sha(binary)!=finish.terminal.BINARY_SHA:raise ValueError('native_binary_changed')
    binary.chmod(0o500)
    cases=[]
    with np.load(archive,allow_pickle=False)as z:
        for index,key in enumerate(FAMILIES):
            family=config['families'][key];seed=next(r for r in family['seeds']if r['key']==family['reference_key'])
            p=z[seed['key']];assert p.shape==(family['n'],3)and finish.terminal.geometry_sha(p)==seed['geometry_sha256']
            cert_path=inputs/seed['certificate']['path'];assert finish.sha(cert_path)==seed['certificate']['sha256']
            certificate=json.loads(cert_path.read_text());assert certificate['valid']
            native_path=inputs/seed['native_input']['path'];encoded,offsets=finish.terminal.fq.encode(p,family['w'],family['h'])
            assert encoded.encode()==native_path.read_bytes()and finish.sha(native_path)==seed['native_input']['sha256']and offsets==seed['native_input']['rect_offsets']
            selected=out/'inputs'/f'{key}.npz';finish.terminal.atomic_npz(selected,{'pose':p});selected.chmod(0o444)
            bindings.append(dict(path=str(selected),sha256=finish.sha(selected)))
            copy(cert_path,out/'inputs'/f'{key}.certificate.json');copy(native_path,out/'inputs'/f'{key}.in')
            cases.append(dict(key=key,n=family['n'],w=family['w'],h=family['h'],d=family['d'],
                              reference_f_lower=family['reference_f_lower'],reference_f_upper=family['reference_f_upper'],
                              source_key=seed['key'],source_geometry_sha256=seed['geometry_sha256'],
                              selected_archive=str(selected),selected_archive_sha256=finish.sha(selected),
                              expected_native_input_sha256=finish.sha(native_path),slot=index))
    helpers=[Path(finish.__file__),Path(finish.terminal.__file__),Path(finish.terminal.fq.__file__),
             ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',ROOT/'experiments/fq_variant_campaign.py',
             ROOT/'scripts/validate_submission.py',ROOT/'scripts/score_official.py',ROOT/'research/official_metric_v17.py']
    manifest=dict(source_sha256=finish.sha(__file__),finisher_sha256=FINISH_SHA,input_archive_sha256=INPUT_SHA,
                  inputs_source=str(inputs),bindings=bindings,helper_hashes={str(p):finish.sha(p)for p in helpers},
                  cases=cases,derivation=derivation,binary_path=str(binary),binary_sha256=finish.terminal.BINARY_SHA,
                  native_source_commit=finish.terminal.fq.SOURCE_COMMIT,options=finish.terminal.OPTIONS,seed=9710000,
                  workers=2,affinity=[2,3],native_seconds=60,certificate_seconds=8,work_seconds=150,whole_seconds=160,
                  provenance='Exact certified v2 seed0 original controls, not GPU states; source attribution/notices inherited from pinned input proof.',
                  no_canonical_mutation=True,no_submission=True)
    finish.terminal.atomic_json(out/'manifest.json',manifest);(out/'manifest.json').chmod(0o444)
    print(json.dumps(dict(prepared=str(out),manifest_sha256=finish.sha(out/'manifest.json'),source_sha256=finish.sha(__file__))))


def trial(payload):
    out,case,binary,deadline=payload;fn,_=source_function()
    if finish.sha(case['selected_archive'])!=case['selected_archive_sha256']:raise ValueError('selected_reference_changed')
    with np.load(case['selected_archive'],allow_pickle=False)as z:p=z['pose'].copy()
    if finish.terminal.geometry_sha(p)!=case['source_geometry_sha256']:raise ValueError('reference_geometry_changed')
    encoded,_=finish.terminal.fq.encode(p,case['w'],case['h'])
    if hashlib.sha256(encoded.encode()).hexdigest()!=case['expected_native_input_sha256']:raise ValueError('native_reference_input_changed')
    slot=dict(slot=case['slot'],kind='original_reference',delta=0.,chain=None,
              design=dict(source_key=case['source_key']),source_geometry_sha256=case['source_geometry_sha256'],
              expected_native_input_sha256=case['expected_native_input_sha256'])
    record,q=fn((out,slot,p,case,binary,deadline))
    if record.get('input_sha256')not in(None,case['expected_native_input_sha256']):raise ValueError('executed_input_differs_from_frozen_reference')
    return record,q


def work(out):
    manifest=json.loads((out/'manifest.json').read_text())
    for row in manifest['bindings']:
        if finish.sha(row['path'])!=row['sha256']:raise ValueError('frozen_control_binding_changed')
    for path,digest in manifest['helper_hashes'].items():
        if finish.sha(path)!=digest:raise ValueError('control_helper_changed')
    source_function();os.sched_setaffinity(0,{2,3})
    started=time.monotonic();deadline=started+150.;results=[];certified={};rectangular={}
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('fork'))as pool:
        futures={pool.submit(trial,(str(out/'trials'),case,manifest['binary_path'],deadline)):case for case in manifest['cases']}
        for future in as_completed(futures):
            case=futures[future]
            try:record,q=future.result()
            except Exception as error:
                record=dict(family_key=case['key'],status='control_error',error_type=type(error).__name__);q=None
            results.append(record)
            if q is not None:
                key=f"{case['key']}__reference_control__{finish.terminal.geometry_sha(q)}";certified[key]=q
                if record.get('usable_rectangular_donor'):rectangular[key]=q
            finish.terminal.atomic_json(out/'results.json',results)
            finish.terminal.atomic_npz(out/'certified.npz',certified);finish.terminal.atomic_npz(out/'rectangular-donors.npz',rectangular)
            print(json.dumps(dict(family=case['key'],status=record['status'],f_upper=record.get('f_upper'),gain=record.get('component_f_gain_lower'))),flush=True)
    summary=dict(seconds=time.monotonic()-started,cases=len(results),certified=len(certified),
                 rectangular_donors=len(rectangular),strict_component_gains=sum(bool(r.get('strict_component_improvement'))for r in results),
                 native_timeouts=sum(r.get('native_status')=='timeout'for r in results),
                 results_sha256=finish.sha(out/'results.json'),certified_sha256=finish.sha(out/'certified.npz'),
                 rectangular_donors_sha256=finish.sha(out/'rectangular-donors.npz'),
                 no_gpu=True,no_full_score_gain_claim=True,no_canonical_mutation=True,no_submission=True)
    finish.terminal.atomic_json(out/'summary.json',summary);print(json.dumps(summary))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--inputs',type=Path,default=ROOT/'artifacts/rectangular-persistent-inputs-v2');args=parser.parse_args()
    if args.prepare:prepare(args.out.resolve(),args.inputs.resolve())
    else:work(args.out.resolve())
