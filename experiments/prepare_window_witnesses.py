"""Prepare complete pinned public witnesses, retaining original square indices.

Binary64 conversion and a separately recorded rounding-clearance dilation are
not full-bank certification. Every selected window still needs the strict gates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from build_high_n_loader_descriptor import load_raw, record_legalize, bits, vector_bits, array_sha
from exact_square_window import certify, metric_module, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection',type=Path,default=Path('artifacts/high-n-donors/manifest.json'))
    parser.add_argument('--catalogue',type=Path,default=Path('/tmp/squares-research/couzo'))
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args();started = time.monotonic()
    if args.out.exists():raise ValueError('Use a fresh immutable witness preparation directory')
    selection = json.loads(args.selection.read_text())
    public_path = args.catalogue/'certificates/best/manifest.json'
    if sha(public_path)!=selection['manifest_sha256']:raise ValueError('Pinned public witness manifest changed')
    witnesses = json.loads(public_path.read_text())['witnesses']
    poses,records,controls = {},{},{}
    metric = metric_module()
    for row in selection['inventory']:
        n = int(row['n'])
        if not 1000<n<=5000:continue
        public = witnesses[str(n)]
        if public['certificate']!=row['certificate'] or public['certificate_sha256']!=row['certificate_sha256']:
            raise ValueError('Selection disagrees with pinned witness manifest')
        path = args.catalogue/row['certificate']
        if sha(path)!=row['certificate_sha256']:raise ValueError('Source certificate changed')
        raw = load_raw(path)
        prepared,offset,factor,final = record_legalize(raw)
        key = f'full_n{n}'
        poses[key] = prepared
        records[key] = {'n':n,'certificate':row['certificate'],'certificate_sha256':row['certificate_sha256'],
            'source_repository':row['source_repository'],'credit':row['credit'],'manifest_record':public,
            'square_ids_preserved':'row index0..n-1','raw_array_sha256':array_sha(raw),
            'prepared_array_sha256':array_sha(prepared),'legalize_offset_bits':vector_bits(offset),
            'dilation_factor_bits':bits(factor),'dilation_factor':factor,'final_offset_bits':vector_bits(final),
            'full_prepared_pose_official_certification_performed':False}
        if len(controls)<3:
            angle = abs((prepared[:,2]+np.pi/4)%(np.pi/2)-np.pi/4)
            tilted = np.flatnonzero(angle>.018)
            if len(tilted)>=16:
                ids = tilted[:32]
                certificate = certify(prepared[ids],metric)
                if certificate is None:raise ValueError('Converted tilted witness positive control failed')
                controls[key] = {'indices':ids.tolist(),'certificate':certificate}
    if not poses:raise ValueError('No complete higher-n witnesses available')
    args.out.mkdir(parents=True)
    with (args.out/'donors.npz').open('wb') as stream:np.savez_compressed(stream,**poses)
    manifest = {'source_commit':selection['catalogue_commit'],'source_manifest_sha256':selection['manifest_sha256'],
        'selection_sha256':sha(args.selection),'archive_sha256':sha(args.out/'donors.npz'),
        'sources':len(poses),'squares':sum(len(q) for q in poses.values()),
        'source_n_min':min(map(len,poses.values())),'source_n_max':max(map(len,poses.values())),
        'licenses':{p.name:p.read_text() for p in Path('vendor/notices/high-n-donors').glob('LICENSE-*.txt')},
        'records':records,'positive_controls':controls,'elapsed_seconds':time.monotonic()-started,
        'note':'Complete sources retain original index order. Raw symbolic certificate/provenance is pinned; binary64 rounding dilation is separately recorded. Full-source exports are exploratory until a selected subset passes interval and official raw/default-pandas gates.'}
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({key:value for key,value in manifest.items() if key not in ['records','licenses','positive_controls']}))


if __name__=='__main__':main()
