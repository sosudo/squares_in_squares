#!/usr/bin/env python3
"""Freeze 15 exact coarse representatives, one topology, and current n65.

Fresh small-input certificates are computed once. No optimization or launch.
"""
from __future__ import annotations
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,csv,hashlib,io,json,sys,time,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from fq_capacity_probe import full_certificate
from fq_variant_campaign import geometry_sha,atomic_json,atomic_npz
from fq_restart_hop_finish import worst_certificate_side

PLANNING_SHA='66fdf3139843ce05b1cc6ad1b9d55a5aea8249be570fe26b18e55b577b9bd0f3'
TOPOLOGY_SHA='6681f277fc179d9b14fb92c36309cafa08f92977cc794b9ec69bb59c9602b938'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(args):
    started=time.monotonic();args.out.mkdir(parents=True,exist_ok=False)
    source_data=args.source_manifest.read_bytes();source_manifest=json.loads(source_data)
    assert sha(args.seed_bank)==source_manifest['seeds_sha256']
    assert sha(args.source_manifest.parent/'lineage.json')==source_manifest['lineage_sha256']
    evidence=args.out/'source-evidence';shutil.copytree(args.source_manifest.parent,evidence)
    for record in source_manifest['notices']+source_manifest['proofs']:
        assert sha(record.get('retained',record.get('path')))==record['sha256']
    planning_path=ROOT/'artifacts/n65-persistent-cold-planning-v1/report.json'
    assert sha(planning_path)==PLANNING_SHA
    planning=json.loads(planning_path.read_text())
    assert len(planning['proposed_group_representatives'])==15
    with np.load(args.seed_bank,allow_pickle=False) as z:
        source_bank={key:z[key].copy() for key in z.files}
    lookup={geometry_sha(p):(key,p) for key,p in source_bank.items()}
    selected={};bindings={};certificates={};source_keys=[]
    for index,row in enumerate(planning['proposed_group_representatives']):
        source_key,p=lookup[row['geometry_sha256']]
        key=f'group_{index:02d}';selected[key]=p;source_keys.append(key)
        bindings[key]=dict(source_archive=str(args.seed_bank),source_archive_sha256=sha(args.seed_bank),
            source_key=source_key,source_geometry_sha256=geometry_sha(p),group_index=index,
            original_ftmc_key=row['key'],planning_representative=row,
            semantics='Exact geometric-cover representative; not a proven optimizer basin.')
    key='group_15';source_key,p=lookup[TOPOLOGY_SHA];selected[key]=p;source_keys.append(key)
    bindings[key]=dict(source_archive=str(args.seed_bank),source_archive_sha256=sha(args.seed_bank),
        source_key=source_key,source_geometry_sha256=geometry_sha(p),group_index=15,
        semantics='Distinct23-tilt n66-deletion source; fresh full gates required here.')
    pointer_bytes=args.pointer.read_bytes();pointer=json.loads(pointer_bytes)
    raw=Path(pointer['raw']['path']);official_path=Path(pointer['raw']['official_report']);interval_path=Path(pointer['independent_report']['path'])
    assert sha(raw)==pointer['raw']['sha256'] and sha(official_path)==pointer['raw']['official_report_sha256']
    assert sha(interval_path)==pointer['independent_report']['sha256']
    official=json.loads(official_path.read_text());interval=json.loads(interval_path.read_text())
    assert official['valid'] and interval['valid'] and official['sha256']==interval['sha256']==sha(raw)
    rows=[r for r in csv.DictReader(io.StringIO(raw.read_text())) if int(r['n'])==65]
    assert len(rows)==65 and [int(r['square_id']) for r in rows]==list(range(65))
    text=[[r[k] for k in ('x','y','angle')] for r in rows];original=np.asarray(text,dtype='<f8')
    extent=.5*(np.abs(np.cos(original[:,2]))+np.abs(np.sin(original[:,2])))
    shift=np.min(original[:,:2]-extent[:,None],axis=0);reference=original.copy();reference[:,:2]-=shift
    selected['current_reference']=reference
    current_side=str(next(r for r in official['results'] if r['n']==65)['side'])
    bindings['current_reference']=dict(source_raw_sha256=sha(raw),
        original_geometry_sha256=geometry_sha(original),source_geometry_sha256=geometry_sha(reference),
        original_decimal_text_sha256=hashlib.sha256(json.dumps(text,separators=(',',':')).encode()).hexdigest(),
        translation_subtracted=shift.tolist(),scaling_applied=False,
        official=next(r for r in official['results'] if r['n']==65),
        interval=next(r for r in interval['results'] if r['n']==65))
    atomic_npz(args.out/'source-inputs.npz',selected)
    for key,p in selected.items():
        assert p.shape==(65,3) and p.dtype==np.dtype('<f8') and np.isfinite(p).all()
        at=time.monotonic();certificate=full_certificate(p)
        certificates[key]=dict(geometry_sha256=geometry_sha(p),certificate=certificate,seconds=time.monotonic()-at)
        atomic_json(args.out/'input-certificates.json',certificates)
        if not certificate['valid']:
            raise ValueError('Exact input failed full gates; no automatic rescaling: '+key)
        certificates[key]['worst_certified_side']=worst_certificate_side(certificate)[0]
    atomic_json(args.out/'input-certificates.json',certificates)
    atomic_npz(args.out/'n65-cold-inputs.npz',selected)
    reference_sha=geometry_sha(reference)
    case=dict(n=65,device=0,source_key='current_reference',source_geometry_sha256=reference_sha,
        reference_side=current_side,source_keys=source_keys)
    config=dict(cases={'65':case},inputs_sha256=sha(args.out/'n65-cold-inputs.npz'),baseline=pointer['raw'],
        seed=116506501,search_seconds=300,cooling_seconds=100,quench_steps=2000,chains=32,
        temperature=.3,cuts=[.0005,.002],amplitudes=[1.],max_packets=2000,max_bytes=2*1024**3,
        finish_native_seconds=60,finish_certificate_seconds=8,finish_workers_per_case=4,finish_slots_per_case=8,
        cuda_options=['--std=c++17','--fmad=false'])
    proof=dict(baseline=pointer['raw'],inputs_sha256=config['inputs_sha256'],
        pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(),planning_sha256=PLANNING_SHA,
        cases={'65':dict(reference_key='current_reference',reference_geometry_sha256=reference_sha,
            reference_side=current_side,source_keys=source_keys)},
        arrays={key:dict(shape=list(p.shape),dtype=p.dtype.str,sha256=geometry_sha(p)) for key,p in selected.items()},
        bindings=bindings,input_certificates=certificates,
        source_manifest=source_manifest,source_manifest_sha256=hashlib.sha256(source_data).hexdigest(),
        retained_source_evidence={str(p.relative_to(evidence)):sha(p) for p in evidence.rglob('*') if p.is_file()},
        source_bank_sha256=sha(args.seed_bank),preparation_source_sha256=sha(__file__),
        scope='Exact source geometries; source-unit identities unchanged; current reference translated only. All17 exact inputs freshly full-certified. No optimization.',
        source_differences='15 cover-group representatives plus separately certified23-tilt deletion topology; groups are not proven attraction basins.',
        seconds=time.monotonic()-started)
    atomic_json(args.out/'n65-cold-config.json',config);atomic_json(args.out/'n65-cold-input-proof.json',proof)
    (args.out/'portfolio-pointer.json').write_bytes(pointer_bytes)
    (args.out/'prepare-n65-cold-inputs.py').write_bytes(Path(__file__).read_bytes())
    (args.out/'source-manifest.json').write_bytes(source_data)
    atomic_json(args.out/'completion.json',dict(inputs_sha256=proof['inputs_sha256'],
        proof_sha256=sha(args.out/'n65-cold-input-proof.json'),config_sha256=sha(args.out/'n65-cold-config.json'),
        certified_inputs=17,seconds=time.monotonic()-started))
    for p in args.out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps(json.loads((args.out/'completion.json').read_text())),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('seed-bank','source-manifest','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--pointer',type=Path,default=ROOT/'artifacts/current-best-portfolio.json')
    prepare(parser.parse_args())
