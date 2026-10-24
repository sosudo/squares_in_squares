"""Exact private CPU package, two dedicated two-worker lanes, hard supervisor."""
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
if hashlib.sha256(raw).hexdigest()!=CONFIG['payload_sha256']:raise ValueError('Frozen payload changed')
package=OUT/'cpu_followup_package';package.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(raw))as archive:
    if len(archive.namelist())!=len(set(archive.namelist()))or set(archive.namelist())!=set(CONFIG['files']):
        raise ValueError('Exact payload inventory required')
    for name,expected in CONFIG['files'].items():
        path=package/name;data=archive.read(name)
        if not path.resolve().is_relative_to(package.resolve())or hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError('Unsafe payload path or changed bytes')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
input_root=Path(os.environ.get('FQ_SEARCH_INPUT_ROOT','/kaggle/input'))
matches=[]
for path in input_root.rglob('fq_portable'):
    proof=path.parent/'package_manifest.json'
    if path.is_file()and proof.is_file()and sha(path)==CONFIG['binary_sha256']and sha(proof)==CONFIG['ready_manifest_sha256']:
        matches.append(path)
if not matches:raise ValueError('Exact private readiness binary and manifest not mounted')
source=sorted(matches)[0];binary=OUT/'fq_portable';binary.write_bytes(source.read_bytes());binary.chmod(0o500)
(OUT/'binary_attachment_proof.json').write_text(json.dumps(dict(source_path=str(source),binary_sha256=sha(binary),
    readiness_manifest_sha256=sha(source.parent/'package_manifest.json'),readiness_ref=CONFIG['ready_ref']),indent=2)+'\n')
(OUT/'job_manifest.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
lanes=os.environ.get('FQ_SEARCH_LANES','productive,large').split(',')
workers=int(os.environ.get('FQ_SEARCH_WORKERS_PER_LANE','2'))
seconds=float(os.environ.get('FQ_SEARCH_SECONDS','1200'))
maximum=int(os.environ.get('FQ_SEARCH_MAX_TRIALS','0'))
whole=float(os.environ.get('FQ_SEARCH_TOTAL_SECONDS','1260'))
if (not lanes or len(set(lanes))!=len(lanes)or not set(lanes)<={'productive','large'}
        or not 1<=workers<=2 or not 15<seconds<=1200 or maximum<0 or not seconds+30<=whole<=1260):
    raise ValueError('Requested CPU work exceeds the frozen authorization')
processes={};commands={};receipts={};logs={}
deadline=STARTED+whole-30
if any((OUT/('campaign_'+lane)).exists()for lane in lanes):
    raise ValueError('All campaign outputs must be fresh before any lane starts')
for lane in lanes:
    root=OUT/('campaign_'+lane)
    if root.exists():raise ValueError('Campaign output must be fresh')
    command=[sys.executable,str(package/'experiments/fq_cpu_followup_search.py'),'--package',str(package),
        '--binary',str(binary),'--out',str(root),'--lane',lane,'--seconds',str(seconds),'--workers',str(workers),
        '--max-trials',str(maximum)]
    commands[lane]=command;logs[lane]=open(OUT/(lane+'.log'),'w')
    try:
        processes[lane]=subprocess.Popen(command,stdout=logs[lane],stderr=subprocess.STDOUT)
    except BaseException:
        for process in processes.values():stop_owned_tree(process)
        for log in logs.values():log.close()
        raise
    print(json.dumps(dict(stage='cpu_lane_started',lane=lane,pid=processes[lane].pid,workers=workers,search_seconds=seconds)),flush=True)
for lane,process in processes.items():
    forced=False;killed=[]
    try:process.wait(timeout=max(.01,deadline-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True;killed=stop_owned_tree(process)
    receipts[lane]=dict(returncode=process.returncode,hard_deadline_enforced=forced,killed_owned_pids=killed,
        workers=workers,search_seconds=seconds)
    logs[lane].close()
# Recover both lanes concurrently, with a single shared whole-run deadline.
collectors={}
for lane in lanes:
    root=OUT/('campaign_'+lane)
    if root.exists()and time.monotonic()<STARTED+whole-7:
        collectors[lane]=subprocess.Popen(commands[lane]+['--collect-only'],stdout=subprocess.DEVNULL)
for lane,process in collectors.items():
    try:process.wait(timeout=max(.01,STARTED+whole-7-time.monotonic()))
    except subprocess.TimeoutExpired:stop_owned_tree(process)
    receipts[lane]['collector_returncode']=process.returncode
receipt=dict(lanes=receipts,seconds=time.monotonic()-STARTED,configured_whole_seconds=whole,
    workers_total=workers*len(lanes),server_timeout_seconds=1500,cpu_only=True,payload_sha256=CONFIG['payload_sha256'])
(OUT/'supervisor.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(stage='dual_cpu_supervisor_complete',**receipt)),flush=True)
if any(row['returncode']and not row['hard_deadline_enforced']for row in receipts.values()):
    raise RuntimeError('A CPU lane failed; immutable stages remain available')
if any(receipts[lane].get('collector_returncode')!=0 for lane in lanes):
    raise RuntimeError('An immutable-stage collector did not finish')
