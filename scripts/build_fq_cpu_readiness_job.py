#!/usr/bin/env python3
"""Package one exact portable FQ binary, provenance, and CPU readiness controls."""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'));sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
import fq_active_pilot as fq
from compose_gadgets import side

BINARY_SHA='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
SOURCE_COMMIT='659ee62e4a9d39542a1146e8b011cc3ab6407ede'


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,default=Path('/tmp/squares-fq-portable-target/release/fq'))
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--slug',default='sos54352/squares-fq-cpu-ready-10ec7cf773ac')
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Use a fresh CPU readiness output directory')
    binary=args.binary.read_bytes()
    if sha(binary)!=BINARY_SHA:raise ValueError('Expected exact root-authorized portable FQ binary')
    vendor=ROOT/'vendor/fq';manifest=json.loads((vendor/'SOURCE_MANIFEST.json').read_text())
    if manifest['commit']!=SOURCE_COMMIT:raise ValueError('Pinned FQ source commit differs')
    for record in manifest['files']:
        if sha((vendor/record['local_path']).read_bytes())!=record['sha256']:raise ValueError('Pinned native source differs')
    data={'bin/fq':binary}
    for path in sorted(vendor.rglob('*')):
        if path.is_file():data['vendor/fq/'+str(path.relative_to(vendor))]=path.read_bytes()
    source_paths=['experiments/fq_active_pilot.py','experiments/fq_capacity_probe.py',
        'experiments/compose_gadgets.py','experiments/refill_capacity.py','experiments/refill_search.py',
        'scripts/score_official.py','scripts/validate_submission.py','research/official_metric_v17.py']
    for name in source_paths:data[name]=(ROOT/name).read_bytes()
    registry=Path('/tmp/squares-cargo/registry/src/index.crates.io-1949cf8c6b5b557f')
    cache=Path('/tmp/squares-cargo/registry/cache/index.crates.io-1949cf8c6b5b557f')
    toolchain=Path('/tmp/squares-rustup/toolchains/1.99.1-x86_64-unknown-linux-gnu/bin')
    build_environment=dict(os.environ,CARGO_HOME='/tmp/squares-cargo',RUSTUP_HOME='/tmp/squares-rustup',RUSTC=str(toolchain/'rustc'))
    dependency_tree=subprocess.run([str(toolchain/'cargo'),'tree','--manifest-path',str(vendor/'Cargo.toml'),
        '--locked','--offline','--target','x86_64-unknown-linux-gnu','--edges','normal,build',
        '--prefix','none','--format','{p}'],capture_output=True,text=True,check=True,env=build_environment).stdout
    target_packages={tuple(line.split()[:2])for line in dependency_tree.splitlines()}
    data['provenance/x86_64-cargo-tree.txt']=dependency_tree.encode()
    licenses=[]
    non_target=[]
    for package in tomllib.loads((vendor/'Cargo.lock').read_text())['package']:
        if not package.get('source','').startswith('registry'):continue
        label=package['name']+'-'+package['version'];folder=registry/label;crate=cache/(label+'.crate')
        if (package['name'],'v'+package['version'])not in target_packages:
            non_target.append(label);continue
        if not folder.is_dir()or not crate.is_file()or sha(crate.read_bytes())!=package['checksum']:
            raise ValueError('Locked dependency archive is unavailable or changed: '+label)
        meta=tomllib.loads((folder/'Cargo.toml').read_text())['package'];files=[]
        for path in sorted(folder.iterdir()):
            if path.is_file()and any(path.name.lower().startswith(k)for k in ('license','copying','notice','copyright')):
                name='vendor/dependency_licenses/'+label+'/'+path.name;data[name]=path.read_bytes();files.append(name)
        if not files:raise ValueError('Dependency license text missing: '+label)
        licenses.append(dict(name=package['name'],version=package['version'],crate_sha256=package['checksum'],
            declared_license=meta.get('license'),license_files=files))
    preparation=ROOT/'artifacts/fq-cpu-readiness-preparation'
    rust_proof=json.loads((preparation/'rust-license-provenance.json').read_text())
    for name,proof in rust_proof.items():
        value=(preparation/('rust-'+name)).read_bytes()
        if sha(value)!=proof['sha256']:raise ValueError('Rust compiler license changed')
        data['vendor/rust/'+name]=value
    data['vendor/rust/license-provenance.json']=json.dumps(rust_proof,indent=2).encode()
    data['vendor/dependency_licenses/manifest.json']=json.dumps(licenses,indent=2).encode()
    data['provenance/non-target-lock-packages.json']=json.dumps(non_target,indent=2).encode()
    fingerprints=list(args.binary.parent.glob('.fingerprint/packer-*/bin-fq.json'))
    if len(fingerprints)!=1:raise ValueError('Expected one exact portable build fingerprint')
    fingerprint=fingerprints[0].read_bytes();build=json.loads(fingerprint)
    if build['rustflags']!=[]:raise ValueError('Portable binary must not use native-only compiler flags')
    data['provenance/cargo-fingerprint.json']=fingerprint
    data['provenance/rustc-info.json']=(args.binary.parents[1]/'.rustc_info.json').read_bytes()
    version_info=subprocess.run(['readelf','--version-info',str(args.binary)],capture_output=True,text=True,check=True).stdout
    data['provenance/elf-version-requirements.txt']=version_info.encode()
    five=ROOT/'artifacts/fq-preflight/2_2_1-polish-420.in';data['controls/n5.in']=five.read_bytes()
    n65=ROOT/'artifacts/n65-fq-input-v1/reference.npz'
    with np.load(n65,allow_pickle=False)as archive:p=archive['8_8_1']
    encoded,offsets=fq.encode(p,8,8)
    if offsets!=[0,0]or p.shape!=(65,3):raise ValueError('Unexpected n65 control')
    data['controls/n65.in']=encoded.encode()
    controls={'5':dict(source=str(five),source_sha256=sha(five.read_bytes()),maximum_output_side=2.708),
        '65':dict(source=str(n65),source_sha256=sha(n65.read_bytes()),
            geometry_sha256=sha(np.asarray(p,dtype='<f8').tobytes()),maximum_output_side=side(p)+5e-6)}
    for name,value in data.items():
        if name.endswith('.py'):compile(value,name,'exec')
        if b'KGAT_'in value:raise ValueError('Credential-shaped bytes forbidden')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as archive:
        for name,value in data.items():archive.writestr(name,value)
    raw=stream.getvalue();packed=lzma.compress(raw,preset=6)
    runtime=(ROOT/'experiments/fq_cpu_readiness_runtime.py').read_bytes()
    config=dict(kind='cpu_only_fq_readiness',source_repository=manifest['repository'],source_commit=SOURCE_COMMIT,
        binary_sha256=BINARY_SHA,binary_bytes=len(binary),binary_platform='x86_64-unknown-linux-gnu',
        minimum_required_glibc='2.35',required_shared_libraries=['libgcc_s.so.1','libm.so.6','libc.so.6'],
        rustflags=[],worker_wall_seconds=180,server_timeout_seconds=300,controls=controls,
        dependency_license_count=len(licenses),native_search_performed=False,
        payload_bytes=len(raw),payload_sha256=sha(raw),files={name:sha(value)for name,value in data.items()},
        runtime_sha256=sha(runtime),third_party_notices='Exact FQ MIT, locked crate and Rust license texts preserved in package.',
        reproducible_build_command='cargo build --release --locked --manifest-path vendor/fq/Cargo.toml --bin fq',
        parent_binary_provenance='Authorized existing portable build, exact SHA bound; no remote compiler/download dependency.')
    source='CONFIG='+repr(config)+'\nPAYLOAD='+repr(base64.b64encode(packed).decode())+'\n'+runtime.decode()
    compile(source,'readiness.py','exec')
    if len(source.encode())>=1_000_000:raise ValueError('CPU readiness source exceeds Kaggle1MB')
    args.out.mkdir(parents=True)
    metadata=dict(id=args.slug,title=args.slug.split('/')[-1].replace('-',' '),code_file='readiness.py',
        language='python',kernel_type='script',is_private=True,enable_gpu=False,enable_tpu=False,enable_internet=False,
        dataset_sources=[],kernel_sources=[],competition_sources=[])
    report=dict(script_sha256=sha(source.encode()),script_bytes=len(source.encode()),payload_compressed_bytes=len(packed),
        binary_sha256=BINARY_SHA,files=len(data),licenses=len(licenses),server_timeout_seconds=300,launched=False)
    (args.out/'readiness.py').write_text(source)
    for name,value in [('kernel-metadata.json',metadata),('job_manifest.json',config),('build_report.json',report)]:
        (args.out/name).write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
