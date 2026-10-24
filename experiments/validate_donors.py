"""Independently interval-check every unit-square pose in a donor archive.

A rectangular donor is checked for non-overlap using the same unit-square
geometry as a full puzzle. This certifies its exported decimal pose, not its
usefulness in a composition or a competition score.
"""
import argparse
import hashlib
import json
from multiprocessing import Pool
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_submission import Square, validate_puzzle


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def check(item):
    key,p=item
    rows=[Square(*(format(float(v),'.17g') for v in row)) for row in p]
    return key,validate_puzzle(len(rows),rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive',type=Path)
    ap.add_argument('--workers',type=int,default=2)
    ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args();started=time.monotonic();digest=sha(args.archive)
    with np.load(args.archive,allow_pickle=False) as z:poses=[(k,z[k]) for k in z.files]
    results={}
    with Pool(args.workers) as pool:
        for key,rec in pool.imap_unordered(check,poses,chunksize=2):
            results[key]=rec
            if len(results)%50==0:print(f'Interval-checked {len(results)}/{len(poses)} donor variants',flush=True)
    if sha(args.archive)!=digest:raise RuntimeError('Donor archive changed during verification')
    invalid={k:v for k,v in results.items() if not v['valid']}
    report={'archive':str(args.archive.resolve()),'sha256':digest,'donors':len(poses),
            'squares':sum(len(p) for _,p in poses),'valid':not invalid,'invalid':invalid,
            'results':results,'elapsed_seconds':time.monotonic()-started,
            'meaning':'All exported unit squares have certified disjoint interiors; no score or separator claim.'}
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['results','invalid']}),flush=True)
    raise SystemExit(bool(invalid))

if __name__=='__main__':main()
