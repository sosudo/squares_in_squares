"""Build a private, self-contained Kaggle search job without embedding secrets.

Embed only the chosen seed puzzles (and their n+1 donors). Search configuration
and seed hashes are retained with results. Generated files live in artifacts/.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--ns',required=True)
    ap.add_argument('--slug',required=True,help='account/notebook-slug')
    ap.add_argument('--title',required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--seconds',type=int,default=60)
    ap.add_argument('--replicas',type=int,default=128)
    ap.add_argument('--steps',type=int,default=1000)
    ap.add_argument('--seed',type=int,default=20261024)
    args=ap.parse_args()
    ns=[int(n) for n in args.ns.split(',')]
    keep=set(ns)|{n+1 for n in ns if n<1000}
    buf=io.StringIO()
    with args.base.open(newline='') as f:
        reader=csv.DictReader(f)
        writer=csv.DictWriter(buf,fieldnames=reader.fieldnames)
        writer.writeheader()
        counts={}
        for row in reader:
            n=int(row['n'])
            if n in keep:
                writer.writerow(row);counts[n]=counts.get(n,0)+1
    for n in ns:
        if counts.get(n)!=n:raise ValueError(f'missing or incomplete seed n={n}')
    seed_csv=buf.getvalue().encode()
    encoded=base64.b64encode(zlib.compress(seed_csv,9)).decode()
    worker=(ROOT/'experiments/packing_gpu_search.py').read_text()
    manifest={'base_sha256':hashlib.sha256(args.base.read_bytes()).hexdigest(),
              'seed_sha256':hashlib.sha256(seed_csv).hexdigest(),
              'worker_sha256':hashlib.sha256(worker.encode()).hexdigest(),
              'ns':ns,'seconds_per_puzzle':args.seconds,'replicas':args.replicas,
              'steps':args.steps,'seed':args.seed,'slug':args.slug,
              'validation':'Search candidates require independent and official validation before submission.'}
    argv=['packing_gpu_search.py','--base','seed.csv','--out','candidates.json',
          '--ns',args.ns,'--seconds',str(args.seconds),'--replicas',str(args.replicas),
          '--steps',str(args.steps),'--device','cuda','--seed',str(args.seed)]
    script=f'''# Private competition search; no credentials embedded.
import base64, hashlib, json, os, runpy, sys, zlib
from pathlib import Path
import torch
os.chdir('/kaggle/working')
assert torch.cuda.is_available(), 'GPU unavailable: stop without running CPU search'
manifest = {manifest!r}
manifest['torch_version'] = torch.__version__
manifest['gpu'] = torch.cuda.get_device_name(0)
manifest['gpu_count'] = torch.cuda.device_count()
Path('job_manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest), flush=True)
seed = zlib.decompress(base64.b64decode({encoded!r}))
assert hashlib.sha256(seed).hexdigest() == manifest['seed_sha256']
Path('seed.csv').write_bytes(seed)
Path('packing_gpu_search.py').write_text({worker!r})
sys.argv = {argv!r}
runpy.run_path('packing_gpu_search.py', run_name='__main__')
'''
    metadata={'id':args.slug,'title':args.title,'code_file':'search.py',
              'language':'python','kernel_type':'script','is_private':True,
              'enable_gpu':True,'enable_internet':False,'enable_tpu':False,
              'dataset_sources':[],'kernel_sources':[],
              'competition_sources':['squares-in-squares'],
              'machine_shape':'NvidiaTeslaT4'}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'search.py').write_text(script)
    (args.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (args.out/'job_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Built {args.out}: {len(ns)} puzzles, {len(script)} code bytes; nominal search budget {len(ns)*args.seconds}s plus startup/polish.')


if __name__=='__main__':main()
