"""Preserve an actual active chain's separator profiles during gadget search.

This independently implements the clipped-corner support definitions in the
released gpu_adaptive_seams/gpu_seam_profiles code. Smaller BR and larger TL bins
are compatible improvements. It does not replace geometric/official validation.
"""
import math
import numpy as np


def clip_polygon(poly,axis,bound,sign):
    result=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da=sign*(a[axis]-bound);db=sign*(b[axis]-bound)
        if da>=0:result.append(a)
        if (da<0)!=(db<0):result.append(a+(b-a)*(da/(da-db)))
    return result


def clipped_support(p,offset,degrees):
    x,y,angle=p;c=.5*math.cos(angle);s=.5*math.sin(angle)
    poly=[np.array([x+c-s,y+s+c]),np.array([x-c-s,y-s+c]),
          np.array([x-c+s,y-s-c]),np.array([x+c+s,y+s-c])]
    poly=[q-np.asarray(offset)for q in poly]
    for axis,bound,sign in [(0,-2e-8,1),(0,1.00000002,-1),(1,-2e-8,1),(1,1.00000002,-1)]:
        if not poly:break
        poly=clip_polygon(poly,axis,bound,sign)
    normal=np.array([math.cos(math.radians(degrees)),-math.sin(math.radians(degrees))])
    values=[float(q@normal)for q in poly]
    return (min(values),max(values))if values else (2.,-2.)


def profile_bins(p,w,h,incoming,outgoing,bins=16):
    extent=.5*(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))
    br=-2.;tl=2.
    for q,e in zip(p,extent):
        if q[0]+e>w-2e-8 and q[1]-e<1.00000002:
            br=max(br,clipped_support(q,(w,0),outgoing)[1])
        if q[0]-e<1.00000002 and q[1]+e>h-2e-8:
            tl=min(tl,clipped_support(q,(0,h),incoming)[0])
    b=0 if br<-1.5 else max(0,min(bins,math.ceil((br+1)*(bins/2)+2e-6)))
    t=bins if tl>1.5 else max(0,min(bins,math.floor((tl+1)*(bins/2)-2e-6)))
    return int(b),int(t)


def compatible_uses(p,w,h,targets,bins=16):
    key=f'{w}_{h}_{len(p)-w*h}';entry=targets.get(key,{})
    accepted=[]
    for use in entry.get('uses',[]):
        br,tl=profile_bins(p,w,h,use['incoming_degrees'],use['outgoing_degrees'],bins)
        if br<=int(use['br']) and tl>=int(use['tl']):
            accepted.append({'n':use['n'],'stage':use['stage'],'br':br,'tl':tl,
                             'required_br':use['br'],'required_tl':use['tl'],
                             'target_bloat':use['target_bloat'],'partner_bloat':use['partner_bloat']})
    return accepted
