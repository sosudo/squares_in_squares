#!/usr/bin/env python3
"""Package exact, already-certified local donor arrays as a private CPU input."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zlib

import numpy as np


RUNTIME = '''
import base64,hashlib,io,json,zlib
from pathlib import Path
import numpy as np
raw=zlib.decompress(base64.b85decode(PAYLOAD))
assert hashlib.sha256(raw).hexdigest()==MANIFEST['archive_sha256']
with np.load(io.BytesIO(raw),allow_pickle=False)as bank:
    assert sorted(bank.files)==sorted(MANIFEST['arrays'])
    for key in bank.files:
        pose=bank[key];record=MANIFEST['arrays'][key]
        assert list(pose.shape)==record['shape'] and np.isfinite(pose).all()
        assert hashlib.sha256(pose.tobytes()).hexdigest()==record['sha256']
output=Path(MANIFEST['output_file'])
if output.exists():raise RuntimeError('Refuse to overwrite an existing output')
output.write_bytes(raw)
Path('donor_export_manifest.json').write_text(json.dumps(MANIFEST,indent=2)+'\\n')
print(json.dumps({'archive_sha256':MANIFEST['archive_sha256'],'donors':len(MANIFEST['arrays']),
                  'squares':sum(v['shape'][0]for v in MANIFEST['arrays'].values()),
                  'exact_array_hashes_passed':True}),flush=True)
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--slug',required=True)
    p.add_argument('--output-file',default='certified_donors.npz')
    p.add_argument('--provenance',type=Path,nargs='+',required=True)
    p.add_argument('--notices',type=Path,nargs='*',default=[])
    a=p.parse_args()
    if Path(a.output_file).name!=a.output_file or not a.output_file.endswith('.npz'):
        p.error('Output must be an NPZ basename')
    raw=a.archive.read_bytes();sha=lambda data:hashlib.sha256(data).hexdigest()
    arrays={}
    with np.load(a.archive,allow_pickle=False)as bank:
        for key in bank.files:
            pose=bank[key]
            assert pose.ndim==2 and pose.shape[1]==3 and len(pose)>0 and np.isfinite(pose).all()
            arrays[key]={'shape':list(pose.shape),'sha256':sha(pose.tobytes())}
    manifest={'archive_sha256':sha(raw),'archive_bytes':len(raw),'source_archive':str(a.archive),
        'output_file':a.output_file,'source_notebook':a.slug+'/1','arrays':arrays,
        'provenance_files':{str(f):sha(f.read_bytes())for f in a.provenance},
        'source_notices':{str(f):f.read_text()for f in a.notices},
        'certification_note':'Source certificates are hash-bound. This export verifies exact archive and array identity; it does not claim a fresh geometry evaluation.'}
    script='MANIFEST = '+repr(manifest)+'\nPAYLOAD = '+repr(base64.b85encode(zlib.compress(raw,9)).decode())+'\n'+RUNTIME
    compile(script,'export.py','exec')
    if len(script.encode())>=1000000:raise ValueError('Source exceeds the Kaggle1MB limit')
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'export.py').write_text(script)
    metadata={'id':a.slug,'title':a.slug.rsplit('/',1)[-1].replace('-',' ').title(),'code_file':'export.py',
        'language':'python','kernel_type':'script','is_private':True,'enable_gpu':False,'enable_tpu':False,
        'enable_internet':False,'dataset_sources':[],'kernel_sources':[],'competition_sources':[]}
    (a.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (a.out/'donor_export_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with tempfile.TemporaryDirectory()as directory:
        subprocess.run([sys.executable,str((a.out/'export.py').resolve())],cwd=directory,check=True)
        assert (Path(directory)/a.output_file).read_bytes()==raw
    report={'archive_sha256':sha(raw),'script_sha256':sha(script.encode()),'script_bytes':len(script.encode()),
            'donors':len(arrays),'exact_local_replay':True,'launch_performed':False}
    (a.out/'build_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
