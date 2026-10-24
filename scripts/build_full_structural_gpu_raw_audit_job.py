#!/usr/bin/env python3
"""Freeze a CPU-only metadata audit of one exact completed GPU output version."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();assert not args.out.exists()
    receipt=json.loads((args.results/'download-receipt.json').read_text());assert receipt['status']=='complete'
    assert receipt['private_source_verified'];root=args.results/'outputs'
    for name in('full_structural_v2_raw_index.json','job_manifest.json'):
        assert digest(root/name)==receipt['files'][name]['sha256']
    source=(ROOT/'experiments/analyze_full_structural_gpu_raw.py').read_bytes()
    config=dict(parent_ref=receipt['notebook']+'/'+str(receipt['version']),
        parent_source_sha256=receipt['source_sha256'],index_sha256=digest(root/'full_structural_v2_raw_index.json'),
        parent_manifest_sha256=digest(root/'job_manifest.json'),reader_sha256=hashlib.sha256(source).hexdigest(),
        seconds=120,server_seconds=180,gpu=False,optimization=False)
    runtime='''import base64,hashlib,json,os,runpy,sys\nfrom pathlib import Path\nos.chdir('/kaggle/working');os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'\ndef digest(p):\n with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()\nsource=base64.b64decode(READER);assert hashlib.sha256(source).hexdigest()==CONFIG['reader_sha256'];Path('analysis_reader.py').write_bytes(source)\nindices=[p for p in Path('/kaggle/input').rglob('full_structural_v2_raw_index.json')if digest(p)==CONFIG['index_sha256']];assert len(indices)==1\nroot=indices[0].parent;assert digest(root/'job_manifest.json')==CONFIG['parent_manifest_sha256']\nPath('reader_manifest.json').write_text(json.dumps(CONFIG,indent=2)+'\\n')\nsys.argv=['analysis_reader.py',str(root),'--index-sha256',CONFIG['index_sha256'],'--out','raw_stage_analysis.json']\nrunpy.run_path('analysis_reader.py',run_name='__main__')\n'''
    script='CONFIG='+repr(config)+'\nREADER='+repr(base64.b64encode(source).decode())+'\n'+runtime
    compile(script,'search.py','exec');args.out.mkdir(parents=True)
    metadata=dict(id='sos54352/squares-full-packing-raw-stage-audit',title='Squares Full Packing Raw Stage Audit',
        code_file='search.py',language='python',kernel_type='script',is_private=True,enable_gpu=False,enable_internet=False,
        enable_tpu=False,kernel_sources=[config['parent_ref']],dataset_sources=[],competition_sources=[])
    (args.out/'search.py').write_text(script);(args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (args.out/'manifest.json').write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps(dict(out=str(args.out),source_sha256=hashlib.sha256(script.encode()).hexdigest(),launched=False)))


if __name__=='__main__':main()
