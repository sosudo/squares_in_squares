"""Package an immutable certified CSV as a private CPU Kaggle notebook output.

The normal Kaggle notebook-output submission API can submit the resulting
submission.csv. The embedded lossless payload contains packing data only.
"""
import argparse
import base64
import hashlib
import json
import lzma
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('csv',type=Path)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--slug',default='sos54352/squares-certified-portfolio')
    ap.add_argument('--title',default='Squares Certified Portfolio')
    a=ap.parse_args()
    raw=a.csv.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    report=json.loads(a.report.read_text())
    assert report['valid'] and report['invalid_count']==0 and report['puzzles']==1000
    assert digest==report['sha256']
    assert report['metric_sha256']=='312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'
    manifest={'csv_sha256':digest,'csv_bytes':len(raw),'rows':report['rows'],
              'official_score':report['score'],'metric_version':17,
              'metric_sha256':report['metric_sha256'],
              'source_report_sha256':hashlib.sha256(a.report.read_bytes()).hexdigest(),
              'purpose':'Exact lossless export of independently and officially certified packing data.'}
    payload=base64.b64encode(lzma.compress(raw,preset=6)).decode()
    script=f'''# Private CPU export of certified packing coordinates. No credentials.
import base64, csv, hashlib, io, json, lzma
from pathlib import Path
MANIFEST = {manifest!r}
PAYLOAD = {payload!r}
data = lzma.decompress(base64.b64decode(PAYLOAD))
assert hashlib.sha256(data).hexdigest() == MANIFEST['csv_sha256']
assert len(data) == MANIFEST['csv_bytes']
rows = csv.DictReader(io.StringIO(data.decode()))
counts = {{}}
total = 0
for row in rows:
    n = int(row['n'])
    assert int(row['square_id']) == counts.get(n, 0)
    counts[n] = counts.get(n, 0) + 1
    total += 1
assert total == MANIFEST['rows'] == 500500
assert counts == {{n:n for n in range(1,1001)}}
destination = Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()
out = destination / 'submission.csv'
if out.exists():
    assert hashlib.sha256(out.read_bytes()).hexdigest() == MANIFEST['csv_sha256']
else:
    out.write_bytes(data)
(destination / 'export_manifest.json').write_text(json.dumps(MANIFEST, indent=2))
print(json.dumps(MANIFEST), flush=True)
'''
    metadata={'id':a.slug,'title':a.title,'code_file':'export.py','language':'python',
              'kernel_type':'script','is_private':True,'enable_gpu':False,
              'enable_tpu':False,'enable_internet':False,'dataset_sources':[],
              'kernel_sources':[],'competition_sources':['squares-in-squares']}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'export.py').write_text(script)
    (a.out/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (a.out/'export_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    compile(script,'export.py','exec')
    print(json.dumps({'output':str(a.out),'code_bytes':len(script),**manifest}))


if __name__=='__main__':main()
