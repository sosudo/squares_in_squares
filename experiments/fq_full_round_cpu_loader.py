"""Private full-case rounded CPU loader:1200s search,1500s whole,1800s server."""
import base64
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile

STARTED=time.monotonic()
for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[variable]='1'
OUT=Path(os.environ.get('FQ_SEARCH_OUTPUT','/kaggle/working'))
OUT.mkdir(parents=True,exist_ok=True)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def owned_descendants(pid):
    mapping={}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:mapping[int(path.name)]=int(next(x.split()[1]for x in(path/'status').read_text().splitlines()if x.startswith('PPid:')))
        except (OSError,StopIteration):pass
    known={pid}
    while True:
        expanded=known|{child for child,parent in mapping.items()if parent in known}
        if expanded==known:return known
        known=expanded


def stop_owned_tree(process):
    # Pause the known worker and descendants before stopping their separately
    # bounded native sessions. Never kill an unrelated process group.
    known={process.pid}
    for _ in range(4):
        for pid in known:
            try:os.kill(pid,signal.SIGSTOP)
            except ProcessLookupError:pass
        expanded=owned_descendants(process.pid)
        if expanded<=known:break
        known|=expanded
    for pid in sorted(known,reverse=True):
        try:os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:pass
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:pass
    return sorted(known)


raw=lzma.decompress(base64.b64decode(PAYLOAD),memlimit=128*1024*1024)
if hashlib.sha256(raw).hexdigest()!=CONFIG['payload_sha256']:raise ValueError('Frozen CPU search package differs')
package=OUT/'full_round_cpu_package';package.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(raw))as archive:
    if len(archive.namelist())!=len(set(archive.namelist()))or set(archive.namelist())!=set(CONFIG['files']):
        raise ValueError('Exact package inventory required')
    for name,expected in CONFIG['files'].items():
        target=package/name;data=archive.read(name)
        if not target.resolve().is_relative_to(package.resolve())or hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError('Invalid package path or bytes')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
input_root=Path(os.environ.get('FQ_SEARCH_INPUT_ROOT','/kaggle/input'))
matches=[]
for path in input_root.rglob('fq_portable'):
    manifest=path.parent/'package_manifest.json'
    if path.is_file()and manifest.is_file()and sha(path)==CONFIG['binary_sha256']and sha(manifest)==CONFIG['ready_manifest_sha256']:
        matches.append(path)
if not matches:raise ValueError('Exact verified private CPU readiness attachment was not mounted')
source=sorted(matches)[0];binary=OUT/'fq_portable';binary.write_bytes(source.read_bytes());binary.chmod(0o500)
(OUT/'binary_attachment_proof.json').write_text(json.dumps(dict(source_path=str(source),binary_sha256=sha(binary),
    readiness_manifest_sha256=sha(source.parent/'package_manifest.json'),readiness_ref=CONFIG['ready_ref']),indent=2)+'\n')
(OUT/'job_manifest.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
workers=int(os.environ.get('FQ_SEARCH_WORKERS','4'));seconds=float(os.environ.get('FQ_SEARCH_SECONDS','1200'))
maximum=int(os.environ.get('FQ_SEARCH_MAX_TRIALS','0'));whole=float(os.environ.get('FQ_SEARCH_TOTAL_SECONDS','1500'))
if not 1<=workers<=4 or not 15<seconds<=1200 or maximum<0 or not seconds+25<=whole<=1500:
    raise ValueError('Requested CPU campaign exceeds frozen bounds')
root=OUT/'campaign';script=package/'experiments/fq_full_round_cpu_search.py'
command=[sys.executable,str(script),'--package',str(package),'--binary',str(binary),'--out',str(root),
    '--seconds',str(seconds),'--workers',str(workers),'--max-trials',str(maximum)]
process=subprocess.Popen(command)
forced=False;killed=[]
try:
    code=process.wait(timeout=max(.01,whole-30-(time.monotonic()-STARTED)))
except subprocess.TimeoutExpired:
    forced=True;killed=stop_owned_tree(process);code=process.returncode
# Complete immutable pairs are authoritative even if the campaign collector
# was interrupted after its scheduling deadline.
remaining=whole-(time.monotonic()-STARTED)-2
collector=None
if root.exists()and remaining>0:
    collector=subprocess.Popen(command+['--collect-only'])
    try:collector.wait(timeout=min(25.,remaining))
    except subprocess.TimeoutExpired:stop_owned_tree(collector)
receipt=dict(returncode=code,hard_deadline_enforced=forced,killed_owned_pids=killed,
    collector_returncode=collector.returncode if collector else None,seconds=time.monotonic()-STARTED,
    configured_whole_seconds=whole,search_seconds=seconds,server_timeout_seconds=1800,workers=workers,
    cpu_only=True,source_package_sha256=CONFIG['payload_sha256'])
(OUT/'supervisor.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(stage='remote_cpu_supervisor_complete',**receipt)),flush=True)
if code and not forced:raise RuntimeError('Remote CPU campaign failed; retained certificates remain available')
if collector is None or collector.returncode:raise RuntimeError('Remote immutable-stage collector did not finish')
