"""Private CPU-only portability pilot: two native controls, no packing search."""
import base64
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import zipfile

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[variable]='1'
WORKING=Path(os.environ.get('FQ_CPU_OUTPUT_ROOT','/kaggle/working' if Path('/kaggle/working').is_dir() else str(Path.cwd())))
WORKING.mkdir(parents=True,exist_ok=True)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.incoming')
    temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)


def resource_report():
    evidence=dict(machine=platform.machine(),platform=platform.platform(),libc=platform.libc_ver(),
        python=sys.version,visible_cpus=os.cpu_count(),affinity_cpus=len(os.sched_getaffinity(0)),
        nvidia_device_present=Path('/dev/nvidia0').exists(),configured_threads=1)
    for label,name in [('cpu_max','/sys/fs/cgroup/cpu.max'),('memory_max','/sys/fs/cgroup/memory.max'),
                       ('cpuset','/sys/fs/cgroup/cpuset.cpus.effective')]:
        path=Path(name);evidence[label]=path.read_text().strip() if path.exists() else None
    info=Path('/proc/meminfo')
    if info.exists():evidence['mem_total']=next((s for s in info.read_text().splitlines()if s.startswith('MemTotal:')),None)
    return evidence


def native(command,timeout=30):
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        stdout,stderr=process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
    except BaseException:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.communicate();raise


def worker():
    started=time.monotonic();report=dict(status='started',hardware=resource_report(),controls=[],
        binary_sha256=CONFIG['binary_sha256'],source_commit=CONFIG['source_commit'],
        declared_server_timeout_seconds=CONFIG['server_timeout_seconds'],search_performed=False,
        gpu_requested=False,competition_submission_performed=False)
    atomic_json(WORKING/'readiness_report.json',report)
    try:
        if report['hardware']['machine'] not in ('x86_64','AMD64'):raise ValueError('x86-64 binary requires x86-64 CPU')
        raw=lzma.decompress(base64.b64decode(PAYLOAD),memlimit=128*1024*1024)
        if len(raw)!=CONFIG['payload_bytes'] or hashlib.sha256(raw).hexdigest()!=CONFIG['payload_sha256']:
            raise ValueError('Readiness package hash differs')
        root=WORKING/'fq_package';root.mkdir(exist_ok=False)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if set(archive.namelist())!=set(CONFIG['files']):raise ValueError('Package file inventory differs')
            for entry in archive.infolist():
                destination=root/entry.filename;data=archive.read(entry)
                if not destination.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe package filename')
                if hashlib.sha256(data).hexdigest()!=CONFIG['files'][entry.filename]:raise ValueError('Package file hash differs')
                destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
        binary=root/'bin/fq';binary.chmod(0o500)
        if digest(binary)!=CONFIG['binary_sha256']:raise ValueError('Portable native binary differs')
        # Publish the same verified native bytes as a future private attachment.
        (WORKING/'fq_portable').write_bytes(binary.read_bytes());(WORKING/'fq_portable').chmod(0o500)
        atomic_json(WORKING/'package_manifest.json',CONFIG)
        sys.path[:0]=[str(root/'experiments'),str(root/'scripts')]
        import numpy as np
        import pandas as pd
        import scipy
        import mpmath
        import fq_active_pilot as fq
        from fq_capacity_probe import full_certificate
        report['python_packages']={name:module.__version__ for name,module in
            [('numpy',np),('pandas',pd),('scipy',scipy),('mpmath',mpmath)]}
        output_poses={}
        for n in (5,65):
            inp=root/f'controls/n{n}.in';output=WORKING/f'n{n}-native.out'
            command=[str(binary),'quench','--in',str(inp),'--out',str(output),'--seed',str(950000+n),
                '--no-alm','--loosen','1','--pit','20','--flip-top','0']
            begin=time.monotonic();result=native(command,timeout=30)
            (WORKING/f'n{n}-native.log').write_text(result.stdout+'\n'+result.stderr)
            record=dict(n=n,command=command,input_sha256=digest(inp),native_seconds=time.monotonic()-begin,
                returncode=result.returncode,log_sha256=digest(WORKING/f'n{n}-native.log'))
            if result.returncode or not output.is_file():
                record['status']='native_failed';report['controls'].append(record)
                raise RuntimeError('Native CPU control failed; see its bounded output log')
            record['native_report']=json.loads(result.stdout.strip().splitlines()[-1])
            q=fq.decode(output,n)
            if q is None:raise ValueError('Native control requires more than rounding clearance')
            certificate=full_certificate(q);record['certificate']=certificate
            if not certificate['valid']:raise ValueError('Native output failed full geometry/transport gates')
            length=float(certificate['independent_raw']['side_upper'])
            expected=CONFIG['controls'][str(n)]['maximum_output_side']
            if length>expected:raise ValueError('Native control did not recover the expected packing side')
            record.update(status='passed',certified_side=length,output_sha256=digest(output),
                geometry_sha256=hashlib.sha256(np.asarray(q,dtype='<f8').tobytes()).hexdigest())
            output_poses[str(n)]=q;report['controls'].append(record)
            atomic_json(WORKING/'readiness_report.json',report)
            print(json.dumps(dict(stage='native_and_geometry_control_passed',n=n,native_seconds=record['native_seconds'],side=length)),flush=True)
        bad=output_poses['5'].copy();bad[1]=bad[0]
        negative=full_certificate(bad)
        if negative['valid']:raise ValueError('Overlapping negative geometry control was accepted')
        report['overlap_negative_control']=dict(rejected=True,certificate=negative)
        np.savez_compressed(WORKING/'certified_controls.npz',**output_poses)
        report.update(status='ready',binary_compatible=True,certified_controls_sha256=digest(WORKING/'certified_controls.npz'),
            portable_output_sha256=digest(WORKING/'fq_portable'),seconds=time.monotonic()-started)
        atomic_json(WORKING/'readiness_report.json',report)
        print(json.dumps(dict(stage='private_cpu_fq_ready',hardware=report['hardware'],seconds=report['seconds'])),flush=True)
    except BaseException as error:
        report.update(status='failed',error_type=type(error).__name__,error=str(error)[:500],seconds=time.monotonic()-started)
        atomic_json(WORKING/'readiness_report.json',report);raise


if '--worker' in sys.argv:
    worker()
else:
    begin=time.monotonic();process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],start_new_session=True)
    timed_out=False
    try:code=process.wait(timeout=CONFIG['worker_wall_seconds'])
    except subprocess.TimeoutExpired:
        timed_out=True
        # Native children have their own groups; locate only descendants of
        # this known worker before stopping both the worker and its native FQ.
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():continue
            try:
                parent=int(next(s.split()[1]for s in(path/'status').read_text().splitlines()if s.startswith('PPid:')))
                if parent==process.pid:os.killpg(int(path.name),signal.SIGKILL)
            except (OSError,StopIteration):pass
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        code=process.wait()
    atomic_json(WORKING/'supervisor.json',dict(seconds=time.monotonic()-begin,returncode=code,
        timed_out=timed_out,worker_wall_seconds=CONFIG['worker_wall_seconds'],
        server_timeout_seconds=CONFIG['server_timeout_seconds'],cpu_only=True))
    if code:raise RuntimeError('Bounded CPU readiness pilot failed')
