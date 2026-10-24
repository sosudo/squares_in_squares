"""Target FTMC at crops actually used by current full-puzzle chains.

Historical fixtures are not an active search arm here. Matching prior candidates
are retained only when competitive with a current active incumbent.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from ftmc_seed_bank import geometry


def build_frontier_bank(active_path,prior_paths,priorities_path,targets_path,baseline_sha256,min_priority=1e-6):
    priorities=json.loads(Path(priorities_path).read_text())
    targets=json.loads(Path(targets_path).read_text())
    bank={};variants={};provenance={};resume={};rejected={};source_count=0
    active_hash=hashlib.sha256(Path(active_path).read_bytes()).hexdigest()

    def add(p,key,label,origin,allow_new):
        w,h,d=map(int,key.split('_'));p,wh=geometry(p)
        if p.shape!=(w*h+d,3) or not np.isfinite(p).all():raise ValueError(label)
        f=float(max(wh-[w,h]));a=(p[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
        core=int(np.sum(abs(a)>.018))
        if core<4 or core>160:
            rejected[label]={'reason':'unsupported_core_count','core_count':core};return
        if not 0<f<.999999:
            rejected[label]={'reason':'unsupported_bloat','bloat':f};return
        if key not in bank and not allow_new:return
        if key in bank and not allow_new and f>provenance[key]['initial_bloat']+.025:
            rejected[label]={'reason':'obsolete_prior','bloat':f};return
        name=f'{key}__{label}'
        variants[name]=p
        if not allow_new:resume[name]=p
        if key not in bank or f<provenance[key]['initial_bloat']:
            bank[key]=p;provenance[key]={**origin,'initial_bloat':f,'core_count':core,'variant':name,
                                       'campaign_baseline_sha256':baseline_sha256}

    with np.load(active_path)as z:
        for name in z.files:
            key=name.split('__')[0]
            if key not in priorities or float(priorities[key])<min_priority:
                rejected[name]={'reason':'negligible_or_partner_limited_priority','priority':priorities.get(key,0)};continue
            add(z[name],key,'active_'+hashlib.sha256(name.encode()).hexdigest()[:12],
                {'source':'current-frontier active chain crop','active_archive_sha256':active_hash,'source_variant':name},True)
            source_count+=1
    for index,path in enumerate(prior_paths):
        digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with np.load(path)as z:
            for name in z.files:
                key=name.split('__')[0];w,h,d=map(int,key.split('_'))
                for transposed in (False,True):
                    p=z[name].copy();root=key
                    if transposed:p[:,:2]=p[:,[1,0]];p[:,2]=np.pi/2-p[:,2];root=f'{h}_{w}_{d}'
                    if root not in bank:continue
                    add(p,root,f'prior{index}_{hashlib.sha256(name.encode()).hexdigest()[:12]}_t{int(transposed)}',
                        {'source':'competitive previous FTMC variant','resume_sha256':digest,'original_variant':name,'transpose':transposed},False)
    # Normalize only the relative sampling weights, preserving the full original
    # score-impact priorities in the targeting report.
    actual_priorities={key:float(priorities[key])for key in bank}
    peak=max(actual_priorities.values(),default=0)
    scaled={key:value/peak for key,value in actual_priorities.items()}if peak else {}
    if not bank or not scaled:raise ValueError('No supported active frontier targets; stop before GPU search.')
    report={'active_source_poses':source_count,'active_gadgets':len(bank),'retained_variants':len(variants),
            'competitive_resume_variants':len(resume),'rejected':rejected,'original_priorities':actual_priorities,
            'worker_sampling_priorities':scaled,'baseline_sha256':baseline_sha256,'targets':targets,
            'minimum_hypothetical_score_gain':min_priority,
            'incumbents':{key:rec['initial_bloat']for key,rec in provenance.items()}}
    return bank,variants,provenance,resume,scaled,report
