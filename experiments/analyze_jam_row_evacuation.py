"""Bounded detector audit and raw whole-row evacuation/reinsertion controls.

The detector is reproduced from Evan Daniel's MIT packer, commit
659ee62e4a9d39542a1146e8b011cc3ab6407ede. Constructed states are UNVERIFIED;
only the inserted train's internal separation is guaranteed analytically.
There is no optimizer, portfolio mutation, remote job, or admission here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import numpy as np

from packer_hop_physical_energy import physical_energy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/packer-hop-335-v1-source/original-main.rs"
SOURCE_SHA = "f17683199f75af1e1489680bfc69ae38991998fe112e723ed648507ff6ff725e"
QUARTER = math.pi / 2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_sha(q):
    return hashlib.sha256(np.asarray(q, dtype="<f8").tobytes(order="C")).hexdigest()


def jam_lines(q, side):
    """Literal native inequalities and offsets; quarter-turn angle convention."""
    angle = q[:, 2] % QUARTER
    ax = np.flatnonzero(np.minimum(angle, QUARTER - angle) < .02)
    need = math.floor(side) + 1
    lines, seen, maxima = [], set(), {}
    for horizontal in (True, False):
        c = 1 if horizontal else 0
        maximum = 0
        for i in ax:
            for off in (-.45, 0., .45):
                members = tuple(int(j) for j in ax[abs(q[ax, c] - (q[i, c] + off)) < .5])
                maximum = max(maximum, len(members))
                identity = (horizontal, members)
                if len(members) >= need and identity not in seen:
                    seen.add(identity)
                    lines.append(identity)
        maxima["row" if horizontal else "column"] = maximum
    return lines, dict(need=need, near_axis=len(ax), tilted=len(q)-len(ax),
                       maximum_band_counts=maxima, line_count=len(lines))


def native_controls(out, q, side):
    source = SOURCE.read_text()
    detector = source[source.index("fn jam_lines("):source.index("/// Move square", source.index("fn jam_lines("))]
    rust = 'use std::io::{self,Read};\nconst PI2:f64=std::f64::consts::FRAC_PI_2;\n' + detector
    rust += '''fn main(){let mut text=String::new();io::stdin().read_to_string(&mut text).unwrap();
for line in text.lines(){let v:Vec<f64>=line.split_whitespace().map(|s|s.parse().unwrap()).collect();
println!("{}",jam_lines(&v[1..],v[0]).len());}}
'''
    rust_path = out / "native-detector-control.rs"
    rust_path.write_text(rust)
    rustc = Path("/tmp/squares-rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/rustc")
    if not rustc.exists():
        raise RuntimeError("Pinned local Rust compiler is missing")
    executable = out / "native-detector-control"
    command = [str(rustc), "--crate-name", "jam_detector_control", "-O", str(rust_path), "-o", str(executable)]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=10)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    cases = [("actual_incumbent", q, side), ("actual_target_18807", q, 18.807),
             ("actual_target_18803", q, 18.803)]
    for name, n, angle in (("eighteen",18,0.),("nineteen",19,0.),
                            ("quarter_turn",19,QUARTER), ("angle_below",19,.019),
                            ("angle_above",19,.021)):
        pose = np.column_stack((np.arange(n)+.5, np.full(n,.5), np.full(n,angle)))
        cases.append((name,pose,18.807))
    native_input = "\n".join(" ".join(format(x,".17g") for x in np.r_[s,p.ravel()]) for _,p,s in cases)+"\n"
    (out / "native-control-input.txt").write_text(native_input)
    native = subprocess.run([str(executable)],input=native_input,capture_output=True,text=True,check=True,timeout=5)
    counts = [int(x) for x in native.stdout.splitlines()]
    expected = [len(jam_lines(p,s)[0]) for _,p,s in cases]
    assert counts == expected
    assert expected[:3] == [0,0,0] and expected[3] == 0
    assert all(expected[i] > 0 for i in (4,5,6)) and expected[7] == 0
    return dict(command=command, source_sha256=sha(rust_path), executable_sha256=sha(executable),
                input_sha256=sha(out/"native-control-input.txt"),
                cases=[dict(name=c[0],native_count=a,python_count=b) for c,a,b in zip(cases,counts,expected)])


def train(m, theta, major, minor_center, side):
    """Same-angle train, straight center axis, sec(theta) nearest spacing.

    Adjacent squares separate on their rotated major axis. Nonadjacent pairs
    have a larger projection. The tiny spacing guard avoids an intended
    exact-contact floating-point ambiguity; it is not a global certificate.
    """
    c, s = abs(math.cos(theta)), abs(math.sin(theta))
    step = (1.+1e-10)/c
    width = (m-1)*step+c+s
    height = c+s
    if width > side or height > side:
        raise ValueError("Constructive train does not fit the chosen box")
    centers = (np.arange(m)-(m-1)/2)*step+side/2
    minor_center = float(np.clip(minor_center,height/2+1e-9,side-height/2-1e-9))
    pose = np.zeros((m,3))
    pose[:,major] = centers
    pose[:,1-major] = minor_center
    pose[:,2] = theta+major*QUARTER
    diagnostic = physical_energy(pose,side)
    assert diagnostic["max_pair_overlap"] < 1e-12 and diagnostic["max_wall_overlap"] < 1e-12
    return pose,dict(count=m,theta=theta,major_axis=major,spacing=step,
                     envelope_width=width,envelope_height=height,minor_center=minor_center,
                     analytical_adjacent_projected_distance=step*c,diagnostic=diagnostic)


def choose_hole(background, side, old_minor, minor_axis):
    """Finite 32x32x4 constructive placement; no optimization/admission.

    Every candidate is wall-contained and outside the original upright strip.
    Minimum dense cross-pair SAT energy is returned even when strictly positive.
    """
    candidates=[]
    for theta in (0.,math.pi/4,math.pi/8,-math.pi/8):
        half=.5*(abs(math.cos(theta))+abs(math.sin(theta)))+1e-9
        xs=np.linspace(half,side-half,32)
        xx,yy=np.meshgrid(xs,xs,indexing="ij")
        p=np.column_stack((xx.ravel(),yy.ravel(),np.full(xx.size,theta)))
        candidates.append(p[abs(p[:,minor_axis]-old_minor)>1.25])
    candidates=np.concatenate(candidates)
    best=None
    for offset in range(0,len(candidates),128):
        p=candidates[offset:offset+128]
        delta=background[None,:,:2]-p[:,None,:2]
        a=p[:,None,2];b=background[None,:,2]
        overlap=np.full((len(p),len(background)),np.inf)
        for phi in (a,a+QUARTER,b,b+QUARTER):
            proj=abs(delta[:,:,0]*np.cos(phi)+delta[:,:,1]*np.sin(phi))
            radii=.5*(abs(np.cos(phi-a))+abs(np.sin(phi-a))+abs(np.cos(phi-b))+abs(np.sin(phi-b)))
            overlap=np.minimum(overlap,radii-proj)
        overlap=np.maximum(overlap,0.)
        energies=(overlap*overlap).sum(1)
        j=int(np.argmin(energies))
        proposal=(float(energies[j]),offset+j,p[j].copy(),float(overlap[j].max()))
        if best is None or proposal[:2]<best[:2]:best=proposal
    return best[2],dict(candidate_count=len(candidates),selected_candidate_index=best[1],
                       cross_pair_energy=best[0],max_pair_overlap=best[3],
                       excluded_old_center_band_halfwidth=1.25,pose=best[2].tolist())


def run(out):
    start=time.monotonic();cpu=time.process_time()
    if out.exists():raise ValueError("Output must be a fresh directory")
    out.mkdir(parents=True)
    if sha(SOURCE)!=SOURCE_SHA:raise ValueError("Native source hash changed")
    pointer_path=ROOT/"artifacts/current-best-portfolio.json"
    pointer=json.loads(pointer_path.read_text());csv_path=Path(pointer["raw"]["path"])
    if sha(csv_path)!=pointer["raw"]["sha256"]:raise ValueError("Current raw hash mismatch")
    rows=[]
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            n=int(row["n"])
            if n==335:rows.append(row)
            elif n>335:break
    rows.sort(key=lambda r:int(r["square_id"]))
    assert [int(r["square_id"]) for r in rows]==list(range(335))
    q=np.asarray([[float(r[k])for k in("x","y","angle")]for r in rows],dtype=np.float64)
    np.savez_compressed(out/"source335.npz",source335=q)
    (out/"source335-decimal-rows.json").write_text(json.dumps(rows,indent=2)+"\n")
    half=.5*(abs(np.cos(q[:,2]))+abs(np.sin(q[:,2])))
    span=float(max(np.max(q[:,0]+half)-np.min(q[:,0]-half),np.max(q[:,1]+half)-np.min(q[:,1]-half)))
    controls=native_controls(out,q,span)
    _,detector=jam_lines(q,span)
    angle=q[:,2]%QUARTER;upright=np.minimum(angle,QUARTER-angle)<.02
    groups=[]
    for minor in(1,0):
        candidates={tuple(np.flatnonzero(upright&(abs(q[:,minor]-center)<.02))) for center in q[upright,minor]}
        ids=min(candidates,key=lambda ids:(-len(ids),float(q[list(ids),minor].mean())))
        ids=np.asarray(sorted(ids,key=lambda i:q[i,1-minor]),dtype=int)
        assert len(ids)==18
        groups.append((minor,ids))
    side=18.807
    records={};bank={}
    for minor,ids in groups:
        major=1-minor;old_minor=float(q[ids,minor].mean())
        for sign in(-1,1):
            for mode,degrees in(("all18",14.),("train17_hole1",22.5)):
                m=18 if mode=="all18" else 17
                inserted,construction=train(m,math.radians(sign*degrees),major,old_minor,side)
                p=q.copy();p[ids[:m]]=inserted;hole=None
                if m<18:
                    keep=np.ones(335,dtype=bool);keep[ids[-1]]=False
                    p[ids[-1]],hole=choose_hole(p[keep],side,old_minor,minor)
                changed=np.flatnonzero(np.any(p!=q,axis=1))
                assert np.array_equal(np.sort(changed),np.sort(ids)) and p.shape==(335,3)
                assert np.array_equal(p[~np.isin(np.arange(335),ids)],q[~np.isin(np.arange(335),ids)])
                key=f"raw335_{'row' if minor==1 else 'column'}_{mode}_{'positive' if sign>0 else 'negative'}"
                bank[key]=p
                angle_delta=abs((p[:,2]-q[:,2]+math.pi/4)%QUARTER-math.pi/4)
                records[key]=dict(status="UNVERIFIED_RAW_NOT_A_PACKING",side=side,count=335,
                    array_sha256=array_sha(p),evacuated_ids=ids.tolist(),changed_ids=changed.tolist(),
                    original_minor_center=old_minor,construction=construction,hole_reinsertion=hole,
                    min_changed_angle_degrees=float(np.degrees(angle_delta[changed]).min()),
                    maximum_center_displacement=float(np.linalg.norm(p[:,:2]-q[:,:2],axis=1).max()),
                    physical=physical_energy(p,side))
    np.savez_compressed(out/"raw_states.npz",**bank)
    proof=dict(schema_version=1,status="FINITE_DETECTOR_AUDIT_AND_UNVERIFIED_CONSTRUCTIONS",
        source=dict(path=str(SOURCE),sha256=SOURCE_SHA,license="MIT",author="Evan Daniel",
                    commit="659ee62e4a9d39542a1146e8b011cc3ab6407ede"),
        input=dict(pointer_path=str(pointer_path),pointer_sha256=sha(pointer_path),raw_csv=str(csv_path),
                   raw_csv_sha256=sha(csv_path),raw_score=pointer["raw"]["score"],
                   decimal_rows_sha256=sha(out/"source335-decimal-rows.json"),
                   source_archive_sha256=sha(out/"source335.npz"),source_array_sha256=array_sha(q)),
        script_sha256=sha(__file__),energy_helper_sha256=sha(ROOT/"experiments/packer_hop_physical_energy.py"),
        source_side=span,detector=detector,native_controls=controls,
        baseline_physical_at_target=physical_energy(q,side),
        raw_archive_sha256=sha(out/"raw_states.npz"),raw_count=len(bank),records=records,
        wall_seconds=time.monotonic()-start,python_cpu_seconds=time.process_time()-cpu,
        limits=dict(whole_process_seconds=55,native_compiler_timeout=10,native_control_timeout=5,
                    optimizer_calls=0,gpu_jobs=0,admissions=0))
    (out/"report.json").write_text(json.dumps(proof,indent=2)+"\n")
    (out/"LICENSE.packer").write_bytes((SOURCE.parent/"LICENSE").read_bytes())
    print(json.dumps({k:proof[k]for k in("detector","raw_count","raw_archive_sha256","wall_seconds","python_cpu_seconds")}))
    print(json.dumps({k:v["physical"]["energy"]for k,v in records.items()}))


if __name__=="__main__":
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError("55-second analysis bound")))
    signal.alarm(55)
    parser=argparse.ArgumentParser();parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args();run(args.out.resolve())
