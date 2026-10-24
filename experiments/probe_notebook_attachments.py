import hashlib,json,os,time
from pathlib import Path
started=time.monotonic();root=Path('/kaggle/input');entries=[];matches=[];seen=set();count=0
wanted={'submission.csv','worker0_gadgets.npz','ftmc_candidates.json'}
normal=[str(p)for p in root.rglob('submission.csv')]
for directory,dirs,files in os.walk(root,followlinks=True):
    path=Path(directory)
    try:
        stat=path.stat();identity=(stat.st_dev,stat.st_ino)
    except OSError:
        dirs[:]=[];continue
    if identity in seen:
        dirs[:]=[];continue
    seen.add(identity)
    for name in sorted(dirs+files):
        item=path/name;count+=1
        if len(entries)<150 and len(item.relative_to(root).parts)<=5:
            entries.append({'path':str(item),'is_directory':item.is_dir(),'is_symlink':item.is_symlink(),
                            'resolved_path':str(item.resolve()) if item.is_symlink() else None})
        if name in wanted and item.is_file():
            with item.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            matches.append({'path':str(item),'resolved_path':str(item.resolve()),'bytes':item.stat().st_size,'sha256':digest})
    if count>20000 or time.monotonic()-started>60:
        raise RuntimeError('Bounded input inspection limit exceeded')
report={'requested_kernel_sources':['sos54352/squares-certified-portfolio-source-export/2','sos54352/squares-ftmc-pilot/1'],
        'ordinary_rglob_csv_paths':normal,'followlinks_target_files':matches,'path_entries':entries,
        'known_export_v2_sha256':'97df15c28ee66ab1a414d28218fd4e8b28c2bf6ce8869281db9610f7dac81da9',
        'known_export_v3_sha256':'26b4b55c89b3606385a74645e327c4b9a6b40fda7f62f6bdd969dbff1cb39afb',
        'seconds':time.monotonic()-started,'entries_seen':count}
Path('/kaggle/working/attachment_probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'normal_csv_paths':normal,'target_files':matches,'seconds':report['seconds']}))
