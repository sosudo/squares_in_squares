"""Full-count coherent starts; upright coordinates are never stripped/refilled."""
import hashlib
import math
import numpy as np


def geometry_sha(p):
    return hashlib.sha256(np.asarray(p,dtype='<f8').tobytes()).hexdigest()


def coherent_start(source, seed, mode, amplitude):
    rng = np.random.default_rng(seed)
    q = np.asarray(source,dtype=float).copy()
    folded = (q[:,2]+np.pi/4)%(np.pi/2)-np.pi/4
    tilted = np.flatnonzero(abs(folded)>.018)
    upright = np.flatnonzero(abs(folded)<=.018)
    if len(tilted)<4: raise ValueError('Nontrivial tilted strip required')
    centre = q[tilted,:2].mean(0)
    _,_,vt = np.linalg.svd(q[tilted,:2]-centre,full_matrices=False)
    axis = vt[0]
    if axis[0]<0: axis=-axis
    normal = np.array([-axis[1],axis[0]])
    t = (q[tilted,:2]-centre)@axis
    sign = 1 if rng.integers(2) else -1
    details = dict(mode=mode,amplitude=float(amplitude),seed=int(seed),
                   source_geometry_sha256=geometry_sha(source),tilted_count=len(tilted),
                   upright_count=len(upright),full_count=len(q),sign=sign)
    if mode == 'identity':
        selected = np.empty(0,dtype=int)
    elif mode == 'column_slide':
        angle = .25*np.angle(np.mean(np.exp(4j*q[tilted,2])))
        tangent = np.array([math.cos(angle),math.sin(angle)])
        transverse = np.array([-tangent[1],tangent[0]])
        columns = np.rint((q[tilted,:2]-centre)@tangent).astype(int)
        period = int(rng.choice([2,3,4]))
        phase = float(rng.uniform(0,2*np.pi))
        shift = sign*amplitude*np.sin(2*np.pi*columns/period+phase)
        q[tilted,:2] += shift[:,None]*transverse
        selected = tilted
        details.update(column_ids=columns.tolist(),period=period,phase=phase,tangent=tangent.tolist())
    elif mode == 'bend':
        length = float(np.ptp(t)); u=(t-t.min())/length
        frequency = int(rng.choice([1,2]))
        wave = sign*amplitude*np.sin(frequency*np.pi*u)
        angular = np.arctan(sign*amplitude*frequency*np.pi/length*np.cos(frequency*np.pi*u))
        q[tilted,:2] += wave[:,None]*normal; q[tilted,2] += angular
        selected = tilted
        details.update(axis=axis.tolist(),frequency=frequency)
    elif mode == 'hinge':
        quantile = float(rng.choice([.25,.5,.75]))
        cut = float(np.quantile(t,quantile))
        selected = tilted[t>=cut]
        pivot = centre+cut*axis
        angle = sign*amplitude*.6
        c,s = math.cos(angle),math.sin(angle)
        q[selected,:2] = (q[selected,:2]-pivot)@np.array([[c,s],[-s,c]])+pivot
        q[selected,2] += angle
        details.update(pivot=pivot.tolist(),angle_radians=angle,cut_quantile=quantile)
    else:
        raise ValueError(mode)
    assert q.shape == source.shape and np.array_equal(q[upright],source[upright])
    details.update(selected=selected.tolist(),input_geometry_sha256=geometry_sha(q),
                   upright_coordinates_preserved=True,
                   maximum_displacement=float(np.linalg.norm(q[:,:2]-source[:,:2],axis=1).max()))
    return q,details
