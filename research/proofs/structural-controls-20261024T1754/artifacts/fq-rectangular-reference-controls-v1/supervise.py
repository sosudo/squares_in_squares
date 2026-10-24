import hashlib,json,os,signal,subprocess,time
from pathlib import Path
root=Path('/workspace/squares_in_squares');out=root/'artifacts/fq-rectangular-reference-controls-v1'
assert hashlib.sha256((out/'source/driver.py').read_bytes()).hexdigest()=='f15bcbc3f3fbc5abd9e305d32527ba2fe46446a7a4113529a7280a3e252b0d85'
env=os.environ.copy();env['PYTHONPATH']=str(root/'experiments')+os.pathsep+str(root/'scripts')
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):env[name]='1'
start=time.monotonic();timedout=False
with (out/'campaign.log').open('wb')as log:
 p=subprocess.Popen([str(root/'.venv/bin/python'),str(out/'source/driver.py'),'--out',str(out)],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
 try:code=p.wait(timeout=160)
 except subprocess.TimeoutExpired:
  timedout=True
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  code=p.wait()
report=dict(returncode=code,timeout=timedout,whole_seconds=time.monotonic()-start,whole_cap_seconds=160)
(out/'supervisor-result.json').write_text(json.dumps(report)+'\n');print(json.dumps(report))
