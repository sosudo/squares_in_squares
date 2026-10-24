from pathlib import Path
import json,hashlib,shutil,subprocess,os,time
ROOT=Path('/workspace/squares_in_squares');OUT=ROOT/'artifacts/fq-rigid-timeout-trace-n858-v1';OUT.mkdir(exist_ok=False)
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
records=json.loads((ROOT/'artifacts/fq-current-rigid-v1/complete/results.json').read_text());r=next(r for r in records if r['n']==858 and r['job']==13)
assert r['native_status']=='timeout'and r['status']=='no_native_output'
old=r['command'];source_input=Path(old[old.index('--in')+1]);source_parent=source_input.with_suffix('.parent.npz');source_binary=Path(old[0]);binary=OUT/'fq'
shutil.copyfile(source_input,OUT/'native.in');shutil.copyfile(source_parent,OUT/'parent.npz');shutil.copyfile(source_binary,binary);binary.chmod(0o500)
assert digest(OUT/'native.in')==r['input_sha256']and digest(OUT/'parent.npz')==r['parent_archive_sha256']
assert digest(binary)=='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'
command=old.copy();command[0]=str(binary);command[command.index('--in')+1]=str(OUT/'native.in');command[command.index('--out')+1]=str(OUT/'native.out');command.append('--v')
env=os.environ.copy();nontrace={k for k in env if k.startswith('FQ_')and k not in {'FQ_TR','FQ_LPT'}}
assert not nontrace,'Unexpected inherited algorithm settings; no diagnostic run'
env.update(FQ_TR='1',FQ_LPT='1')
manifest={'original_job':13,'n':858,'parent_geometry_sha256':r['parent_geometry_sha256'],'original_record':r,'binary_sha256':digest(binary),'input_sha256':digest(OUT/'native.in'),'parent_archive_sha256':digest(OUT/'parent.npz'),'command':command,'environment_overrides':{'FQ_TR':'1','FQ_LPT':'1'},'added_flag':'--v','native_seconds_cap':26,'workers':1,'no_algorithm_parameter_changes':True,'no_certificate_claim':True,'source_sha256':digest(ROOT/'vendor/fq/src/fq.rs'),'diagnostic_source_sha256':digest(__file__)}
shutil.copyfile(__file__,OUT/'diagnostic.py');(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');start=time.monotonic()
with (OUT/'stdout.log').open('wb')as stdout,(OUT/'stderr.log').open('wb')as stderr:
 try:
  done=subprocess.run(command,stdout=stdout,stderr=stderr,env=env,timeout=26);status='returned';rc=done.returncode
 except subprocess.TimeoutExpired:status='timeout';rc=None
end=time.monotonic();lines=(OUT/'stderr.log').read_text().splitlines();phase=[line for line in lines if line.startswith('outer ')or line.strip().startswith('slp ')or line.startswith('tr ')]
summary={'status':status,'returncode':rc,'seconds':end-start,'output_exists':(OUT/'native.out').exists(),'stdout_bytes':(OUT/'stdout.log').stat().st_size,'stderr_bytes':(OUT/'stderr.log').stat().st_size,'stderr_lines':len(lines),'outer_lines':sum(line.startswith('outer ')for line in lines),'slp_lines':sum(line.strip().startswith('slp ')for line in lines),'tr_lines':sum(line.startswith('tr ')for line in lines),'first_phase_lines':phase[:6],'last_phase_lines':phase[-8:],'files':{p.name:digest(p)for p in OUT.iterdir()if p.is_file()}}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for path in OUT.iterdir():path.chmod(0o500 if path.name=='fq' else 0o444)
print(json.dumps(summary),flush=True)
