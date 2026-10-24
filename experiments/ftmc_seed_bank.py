"""Build reproducible FTMC incumbents and diverse resume archives, without CUDA."""
from pathlib import Path
import hashlib
import numpy as np


def geometry(p):
    q=np.array(p,dtype=float,copy=True)
    extent=.5*(np.abs(np.cos(q[:,2]))+np.abs(np.sin(q[:,2])))
    q[:,:2]-=(q[:,:2]-extent[:,None]).min(0)
    dimensions=(q[:,:2]+extent[:,None]).max(0)-(q[:,:2]-extent[:,None]).min(0)
    return q,dimensions


def build_seed_bank(examples,resume_paths,ids):
    bank={};variants={};provenance={};resume={}
    def add(p,w,h,d,label,origin,is_resume):
        if p.shape!=(w*h+d,3) or not np.isfinite(p).all():raise ValueError(label)
        for transpose in (False,True):
            q=np.array(p,copy=True);ww,hh=w,h
            if transpose:q[:,:2]=q[:,[1,0]];q[:,2]=np.pi/2-q[:,2];ww,hh=h,w
            q,dims=geometry(q);key=f'{ww}_{hh}_{d}';name=f'{key}__{label}_t{int(transpose)}'
            variants[name]=q
            if is_resume:resume[name]=q
            f=float(max(dims-[ww,hh]))
            if key not in bank or f<provenance[key]['initial_bloat']:
                bank[key]=q
                provenance[key]={**origin,'variant':name,'transpose':transpose,'initial_bloat':f}
    with np.load(examples) as z:
        for idx in ids:
            w,h,d=map(int,z['meta_39'][idx,:3])
            for stage in ('before','after'):
                add(z[f'{stage}_{idx}'],w,h,d,f'{stage}{idx}',
                    {'dataset':'cdeotte/squares-in-squares-22-315-data','fixture':f'{stage}_{idx}'},False)
    for index,path in enumerate(resume_paths):
        digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with np.load(path) as z:
            for name in z.files:
                key=name.split('__')[0];w,h,d=map(int,key.split('_'))
                label=f'resume{index}_{hashlib.sha256(name.encode()).hexdigest()[:12]}'
                add(z[name],w,h,d,label,{'resume_file':str(path),'resume_sha256':digest,'original_variant':name},True)
    return bank,variants,provenance,resume
