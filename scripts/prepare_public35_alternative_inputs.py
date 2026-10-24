"""Freeze the approved24 changed public35 alternatives; no optimizer/gates."""
from __future__ import annotations
import csv,hashlib,json,math,shutil,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from fq_active_pilot import encode
from fq_variant_campaign import geometry_sha
CASES=(698,752,805,917,797,458,637,588,743,692,372,639,980,593,996,856,982,638,644,858,502,696,697,872)
REPORT_SHA='ce81a024f214ab61d886d0ddc3454be47978b8b5a75733e0999aba2df1e0355e'
POSES_SHA='3a31ca0e83884d4cb465f8c92f89c5d76a49bf17769a62b6c0ab453d3034ece1'
CSV_SHA='b8be571167c0d51693cdce9ac07187098a0d38bceef0d9e25d347d067e4eb6b9'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def prepare(out):
    assert not out.exists();source=ROOT/'artifacts/public-v35';screen=source/'alternate-screen-v3'
    assert sha(screen/'geometry-comparison.json')==REPORT_SHA and sha(screen/'alternate-public35-poses.npz')==POSES_SHA
    assert sha(source/'files/submission.csv')==CSV_SHA
    report=json.loads((screen/'geometry-comparison.json').read_text());rows={r['n']:r for r in report['alternates']}
    assert len(CASES)==24 and len(set(CASES))==24
    pointer_path=ROOT/'artifacts/current-best-portfolio.json';pb=pointer_path.read_bytes();pointer=json.loads(pb)
    assert sha(pointer['raw']['path'])==pointer['raw']['sha256']
    assert sha(pointer['raw']['official_report'])==pointer['raw']['official_report_sha256']
    official=json.loads(Path(pointer['raw']['official_report']).read_text());assert official['valid']and official['sha256']==pointer['raw']['sha256']
    current={r['n']:r for r in official['results']};out.mkdir(parents=True)
    bank={};slots=[];cases={}
    with np.load(screen/'alternate-public35-poses.npz',allow_pickle=False)as z:
        for i,n in enumerate(CASES):
            r=rows[n];q=z[str(n)].copy();assert q.shape==(n,3)and q.dtype==np.dtype('<f8')
            assert geometry_sha(q)==r['public35']['geometry_sha256']and r['exact_native_input_changed']
            assert not r['adopted_and_already_native_finished']
            assert not any(x['full_ALM45_pit100_flip16']for x in r['prior_exact_native_input_exposures'])
            encoded,offset=encode(q,math.isqrt(n),math.isqrt(n));assert offset==[0,0]
            encoded_sha=hashlib.sha256(encoded.encode()).hexdigest();assert encoded_sha==r['public35']['encoded_input_sha256']
            key=f'public35_{n}';bank[key]=q
            slots.append(dict(slot=i,n=n,key=key,role='public35_changed_alternative',geometry_sha256=geometry_sha(q),
                native_encoded_input_sha256=encoded_sha,seed=9710000,source_case=r,
                selection_stratum='closest16'if i<16 else'datedheadroom8_within_observed_q75_cost'))
            cases[str(n)]=dict(n=n,source_key=key,reference_side=current[n]['side'],public_side=r['public35']['side'])
    # Preserve exact literal input rows in source square-id order, including
    # provenance ID fields. Native matrices are conversions of these literals.
    exact={n:{}for n in CASES}
    with(source/'files/submission.csv').open(newline='')as f:
        reader=csv.DictReader(f);fields=reader.fieldnames
        for row in reader:
            n=int(row['n'])
            if n in exact:exact[n][int(row['square_id'])]=row
    with(out/'exact-public35-input-rows.csv').open('w',newline='')as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for n in CASES:
            literal=[exact[n][i]for i in range(n)];q=np.array([[r[k]for k in('x','y','angle')]for r in literal],dtype=np.float64)
            assert np.array_equal(q,bank[f'public35_{n}'])
            assert hashlib.sha256(json.dumps([[r[k]for k in('x','y','angle')]for r in literal],separators=(',',':')).encode()).hexdigest()==rows[n]['literal35_sha256']
            writer.writerows(literal)
    np.savez_compressed(out/'inputs.npz',**bank)
    evidence=out/'source-evidence';evidence.mkdir()
    for name in('download-proof.json','certified-provenance.json'):
        shutil.copyfile(source/name,evidence/name)
    for name in('SOURCE_NOTICES.md','LICENSE-APACHE-2.0.txt','LICENSE-LEVY-SOURCES.txt','portfolio_manifest.json','per_puzzle.csv'):
        shutil.copyfile(source/'files'/name,evidence/name)
    shutil.copyfile(screen/'geometry-comparison.json',evidence/'geometry-comparison.json')
    (out/'canonical-pointer.json').write_bytes(pb);shutil.copyfile(Path(__file__),out/'preparation.py')
    manifest=dict(cases=cases,slots=slots,baseline=pointer['raw'],inputs_sha256=sha(out/'inputs.npz'),
        preparation_source_sha256=sha(__file__),exact_literal_csv_sha256=sha(out/'exact-public35-input-rows.csv'),
        source_csv_sha256=CSV_SHA,source_dataset='kmmmvs/squares-in-squares-best-packings',source_version=35,
        selection_report_sha256=REPORT_SHA,source_pose_archive_sha256=POSES_SHA,
        evidence_sha256={p.relative_to(out).as_posix():sha(p)for p in evidence.iterdir()},
        coordinate_transform='None before native writer; raw source floats preserve source n/square_id identity. Native writer performs its unchanged translation normalization.',
        input_status='Released unit-square poses, not freshly certified here; native outputs require all unchanged full gates.',
        selection_scope='16 closest currently-worse changed sources plus8 high dated-headroom changed sources within observed q75 refinement cost; excludes currentGPU cases and adopted18. Statistical costs/headroom are selection descriptors, not predicted gains.',
        exposure_scope='Exact-input matching in bounded pinned major completed native ledgers, preserving flags. Absence is not an exhaustive historical non-exposure claim.',
        workers=2,cpu_affinity=[0,1],work_seconds=880,whole_seconds=900,native_seconds=60,gate_seconds=8,
        options=['--loosen','1','--outer','45','--pit','100','--flip-top','16'],seed=9710000,
        no_gpu=True,no_optimization=True,no_submission=True,no_canonical_mutation=True)
    save(out/'manifest.json',manifest)
    for p in out.rglob('*'):
        if p.is_file():p.chmod(0o444)
    print(json.dumps(dict(input_manifest_sha256=sha(out/'manifest.json'),inputs_sha256=manifest['inputs_sha256'],cases=list(CASES),baseline=pointer['raw']['sha256'])),flush=True)

if __name__=='__main__':prepare(Path(sys.argv[1]).resolve())
