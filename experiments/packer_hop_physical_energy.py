"""Independent dense float64 physical-energy oracle; no optimization or admission."""
from pathlib import Path
import numpy as np


def read_raw_pose(path,expected_n=None):
    """Read exact native telemetry, whose angles are radians (not native cfg degrees)."""
    lines=Path(path).read_text().splitlines();head=lines[0].split()
    n,side=int(head[0]),float(head[1])
    p=np.asarray([[float(x)for x in row.split()]for row in lines[1:]],dtype=np.float64)
    if p.shape!=(n,3)or not np.isfinite(p).all()or not np.isfinite(side)or side<=0:
        raise ValueError('Invalid raw telemetry count, coordinates or box')
    if expected_n is not None and n!=expected_n:raise ValueError('Unexpected square count')
    return p,side


def physical_energy(p,side):
    """Sum unordered-pair SAT penetration² + all four wall violations².

    Checks every pair, with no neighbor list and no tolerance. Returns numerical
    diagnostics only; a zero value is not an exact geometry certificate.
    """
    p=np.asarray(p,dtype=np.float64)
    if p.ndim!=2 or p.shape[1]!=3 or not np.isfinite(p).all()or not np.isfinite(side)or side<=0:
        raise ValueError('Invalid geometry/box')
    n=len(p);i,j=np.triu_indices(n,1);d=p[j,:2]-p[i,:2]
    axes=np.stack([p[i,2],p[i,2]+np.pi/2,p[j,2],p[j,2]+np.pi/2],axis=1)
    projection=np.abs(d[:,0,None]*np.cos(axes)+d[:,1,None]*np.sin(axes))
    ai=axes-p[i,2,None];aj=axes-p[j,2,None]
    radii=.5*(np.abs(np.cos(ai))+np.abs(np.sin(ai))+np.abs(np.cos(aj))+np.abs(np.sin(aj)))
    penetration=np.maximum(0.,np.min(radii-projection,axis=1))
    half=.5*(np.abs(np.cos(p[:,2]))+np.abs(np.sin(p[:,2])))
    walls=np.maximum(0.,np.stack([half-p[:,0],p[:,0]+half-side,half-p[:,1],p[:,1]+half-side]))
    pair_energy=float(np.sum(penetration**2));wall_energy=float(np.sum(walls**2))
    return dict(energy=pair_energy+wall_energy,pair_energy=pair_energy,wall_energy=wall_energy,
        max_pair_overlap=float(penetration.max(initial=0)),max_wall_overlap=float(walls.max(initial=0)),
        n=n,unordered_pairs=len(i),wall_checks=4*n)
