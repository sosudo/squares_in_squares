"""Local fidelity, derivative and Verlet coverage controls; no search or launch."""
import argparse
import ast
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import time
import zipfile

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import numpy as np
import torch
from fq_torch_objective import (constraints, objective, multiplier_update,
                                initial_lines, near_pairs, guard_pair_list)
from full_structural_gpu_moves import geometry_sha

ROOT = Path(__file__).resolve().parents[1]
NATIVE_SHA = '7045e9feff2d4b433053e4610258ca43d842e599fccf31d8b6b042276c2905c2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_oracle(out):
    source = ROOT / 'vendor/fq/src/fq.rs'
    assert sha(source) == NATIVE_SHA
    prefix = source.read_text().split('// ---------------------------------------------------------------- SLP polish')[0]
    for line in ('mod ldl;\n', 'mod lpipm;\n'):
        assert prefix.count(line) == 1
        prefix = prefix.replace(line, '')
    # Prob::eval/viol_update and every scalar geometry helper remain verbatim.
    # Disable only the upstream optional SIMD sin/cos path for a libm oracle.
    shim = r'''
fn fast_sc() -> bool { false }
fn sincos_batch(a:&[f64],s:&mut[f64],c:&mut[f64]) {
    for i in 0..a.len() { s[i]=a[i].sin();c[i]=a[i].cos(); }
}
fn main() {
    use std::io::Read;
    let mut text=String::new();std::io::stdin().read_to_string(&mut text).unwrap();
    let mut tok=text.split_whitespace();
    let mut next=||tok.next().unwrap().parse::<f64>().unwrap();
    let n=next() as usize;let np=next() as usize;let mu=next();let r=next();
    let dx=next();let dy=next();let fixed=next()!=0.;set_rnd(r);set_rect(dx,dy);
    let v:Vec<f64>=(0..3*n+1+2*np).map(|_|next()).collect();
    let ids:Vec<(usize,usize)>=(0..np).map(|_|(next()as usize,next()as usize)).collect();
    let wlam:Vec<f64>=(0..16*n).map(|_|next()).collect();
    let pairs:Vec<Pair>=ids.into_iter().enumerate().map(|(k,(i,j))|Pair {
        i,j,phi:v[3*n+1+2*k],d:v[3*n+2+2*k],lam:std::array::from_fn(|_|next()),face:99
    }).collect();
    let mut p=Prob{n,pairs,wlam,mu,fix_s:fixed,b:Vec::new()};
    let mut grad=vec![0.;v.len()];let value=p.eval(&v,&mut grad);
    let violation=p.viol_update(&v,true);
    println!("{:.17e} {:.17e}",value,violation);
    for g in grad {print!("{:.17e} ",g);}println!();
    for l in p.wlam {print!("{:.17e} ",l);}
    for pair in p.pairs {for l in pair.lam {print!("{:.17e} ",l);}}println!();
}
'''
    target = out / 'native_prob_oracle.rs'
    target.write_text(prefix + shim)
    binary = out / 'native_prob_oracle'
    rustc = '/tmp/squares-rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/rustc'
    subprocess.run([rustc, '-O', '-Awarnings', str(target), '-o', str(binary)],
                   check=True, capture_output=True, text=True, timeout=45)
    return binary


def call_native(binary, p, s, lines, pairs, wl, pl, mu, radius, fixed):
    n, count = len(p), len(pairs)
    v = np.concatenate((p.ravel(), [s], lines.ravel()))
    data = np.concatenate(([n, count, mu, radius, 0., 0., float(fixed)], v,
                           pairs.ravel(), wl.ravel(), pl.ravel()))
    text = ' '.join(format(float(x), '.17g') for x in data)
    result = subprocess.run([str(binary)], input=text, capture_output=True,
                            text=True, check=True, timeout=10)
    rows = result.stdout.splitlines()
    value, violation = map(float, rows[0].split())
    return value, violation, np.fromstring(rows[1], sep=' '), np.fromstring(rows[2], sep=' ')


def tensors(p, s, lines, pairs, wl, pl, dtype):
    return (torch.tensor(p[None], dtype=dtype, requires_grad=True),
            torch.tensor([s], dtype=dtype, requires_grad=True),
            torch.tensor(lines[None], dtype=dtype, requires_grad=True),
            torch.tensor(pairs, dtype=torch.long),
            torch.tensor(wl[None], dtype=dtype), torch.tensor(pl[None], dtype=dtype))


def torch_eval(args, mu, radius, fixed):
    result = objective(*args, mu, radius=radius, fix_side=fixed)
    gradient = torch.autograd.grad(result.sum(), args[:3])
    walls, pair = constraints(*args[:4], radius=radius, fix_side=fixed)
    updates = multiplier_update(walls, pair, args[4], args[5], mu)
    return (float(result.detach()[0]),
            float(torch.clamp_min(torch.maximum(walls.max(), pair.max()), 0).detach()),
            np.concatenate([v.detach().numpy().ravel() for v in gradient]),
            np.concatenate([v.detach().numpy().ravel() for v in updates]))


def dense_overlaps(p):
    i, j = np.triu_indices(len(p), 1)
    delta = p[j, :2] - p[i, :2]
    angles = np.stack((p[i, 2], p[i, 2] + math.pi/2, p[j, 2], p[j, 2] + math.pi/2), 1)
    projection = np.abs(delta[:, None, 0] * np.cos(angles) + delta[:, None, 1] * np.sin(angles))
    radius = .5 * (np.abs(np.cos(p[i, 2, None] - angles)) + np.abs(np.sin(p[i, 2, None] - angles))
                   + np.abs(np.cos(p[j, 2, None] - angles)) + np.abs(np.sin(p[j, 2, None] - angles)))
    mask = np.max(projection - radius, axis=1) < -1e-10
    return set(zip(i[mask].tolist(), j[mask].tolist()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    started = time.monotonic(); oracle = native_oracle(args.out)
    source = ROOT / 'artifacts/full-structural-gpu-v2-final-job-v1/search.py'
    assert sha(source) == '7779faa0301a20fbd0164a45d8fd4d1bac7d3fc6fa6fec0cfee626c59225b7e9'
    values = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(source.read_bytes()).body
              if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ('CONFIG', 'PAYLOAD')}
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(values['PAYLOAD']))) as archive:
        data = archive.read('prepared_references.npz')
    assert hashlib.sha256(data).hexdigest() == 'ddadbf2e94f9f598018b0e6a484c82fa954e42f8c29c07710574ad5f56562b9e'
    (args.out / 'references.npz').write_bytes(data)
    with np.load(io.BytesIO(data), allow_pickle=False) as bank:
        references = {int(k): bank[k] for k in bank.files}
    rng = np.random.default_rng(149923)
    rows, coverage, memory = [], [], []
    for n, reference in sorted(references.items()):
        pairs = near_pairs(reference)
        skin = .3; covered = set(map(tuple, pairs.tolist()))
        # All angles may change and rounding may return exactly to zero;
        # only center displacement enters the universal circumradius proof.
        overlap_count = 0
        for trial_index in range(12):
            trial = reference.copy()
            direction = rng.normal(size=(n, 2)); direction /= np.linalg.norm(direction, axis=1)[:, None]
            trial[:, :2] += direction * rng.uniform(0, .149, size=(n, 1))
            trial[:, 2] += rng.uniform(-math.pi, math.pi, size=n)
            guard_pair_list(reference, trial, skin)
            overlaps = dense_overlaps(trial); assert overlaps <= covered
            overlap_count += len(overlaps)
        expired = reference.copy(); expired[0, 0] += .151
        try:
            guard_pair_list(reference, expired, skin)
        except ValueError:
            pass
        else:
            raise AssertionError('Expired list was not rejected')
        coverage.append(dict(n=n,source_geometry_sha256=geometry_sha(reference),pairs=len(pairs),
                             dense_pairs=n*(n-1)//2,rotated_trial_count=12,covered_overlaps=overlap_count,
                             expired_trial_rejected=True,skin=skin,maximum_sampled_displacement=.149))
        p = reference.copy(); p[:, :2] += rng.normal(0, .007, (n, 2)); p[:, 2] += rng.normal(0, .02, n)
        sides = np.max(reference[:, :2] + .5*(np.abs(np.cos(reference[:, 2])) + np.abs(np.sin(reference[:, 2])))[:, None]) - .012
        for radius in (0., .08, .25, .5):
            lines = initial_lines(p, pairs, radius); lines += rng.normal(0, .015, lines.shape)
            wl = rng.uniform(0, .5, (n, 4, 4)); pl = rng.uniform(0, .5, (len(pairs), 8)); mu = 71.
            for fixed in (False, True):
                native = call_native(oracle, p, sides, lines, pairs, wl, pl, mu, radius, fixed)
                a64 = tensors(p, sides, lines, pairs, wl, pl, torch.float64)
                actual = torch_eval(a64, mu, radius, fixed)
                errors = [float(np.max(np.abs(np.asarray(x)-np.asarray(y)))) for x,y in zip(native, actual)]
                assert errors[0] < 2e-9 and errors[1] < 1e-11 and errors[2] < 2e-9 and errors[3] < 2e-9, errors
                a32 = tensors(p, sides, lines, pairs, wl, pl, torch.float32)
                approx = torch_eval(a32, mu, radius, fixed)
                fp32_errors = [float(np.max(np.abs(np.asarray(x)-np.asarray(y)))) for x,y in zip(native, approx)]
                row = dict(n=n,radius=radius,fixed_side=fixed,fp64_native_absolute_errors=errors,
                           fp32_native_absolute_errors=fp32_errors,energy=native[0],max_violation=native[1])
                if not fixed and radius in (0., .25):
                    flat = np.concatenate((p.ravel(), [sides], lines.ravel()))
                    direction = rng.normal(size=len(flat)); direction /= np.linalg.norm(direction)
                    step = 2e-6; energies = []
                    for sign in (-1, 1):
                        probe = flat + sign*step*direction
                        probe_args = tensors(probe[:3*n].reshape(n,3), probe[3*n], probe[3*n+1:].reshape(-1,2), pairs, wl, pl, torch.float64)
                        energies.append(float(objective(*probe_args,mu,radius=radius).detach()[0]))
                    finite_difference = (energies[1]-energies[0])/(2*step)
                    derivative = float(actual[2] @ direction)
                    assert abs(finite_difference-derivative) < 2e-7
                    row['directional_gradient_error'] = abs(finite_difference-derivative)
                rows.append(row)
        # Count unique saved autograd storages for a real FP32 batch. CPU
        # timing is diagnostic only; it is not a T4 throughput measurement.
        batch = 32; count = len(pairs); saved = {}
        a = tensors(p, sides, lines, pairs, wl, pl, torch.float32)
        a = tuple(v.repeat((batch,)+(1,)*(v.ndim-1)).detach().requires_grad_(i<3) if i!=3 else v for i,v in enumerate(a))
        def retain(t):
            storage=t.untyped_storage();saved[(str(t.device),storage.data_ptr())]=storage.nbytes();return t
        at=time.monotonic()
        with torch.autograd.graph.saved_tensors_hooks(retain,lambda t:t):
            value=objective(*a,mu,radius=.25);value.sum().backward()
        seconds=time.monotonic()-at
        variables=3*n+1+2*count; constraint_count=16*n+8*count
        memory.append(dict(n=n,batch=batch,pairs=count,variables_per_item=variables,constraints_per_item=constraint_count,
                           fp32_saved_autograd_storage_bytes=sum(saved.values()),one_cpu_forward_backward_seconds=seconds,
                           fp32_lbfgs20_history_bytes=2*20*batch*variables*4,
                           fp32_dense_rebuild_distance_matrix_bytes=batch*n*n*4))
    # Disk-vs-square negative/positive geometry: a diagonal pair overlaps as
    # squares but is separated as true radius-.5 rounded squares (unit disks).
    control=np.array([[1.,1.,0.],[1.8,1.8,0.]])
    pair=np.array([[0,1]]);line=initial_lines(control,pair,.5)
    z=tensors(control,4.,line,pair,np.zeros((2,4,4)),np.zeros((1,8)),torch.float64)
    rigid=constraints(*z[:4],radius=0.)[1];disk=constraints(*z[:4],radius=.5)[1]
    assert rigid.max()>.1 and disk.max()<-.05
    duplicate=control.copy();duplicate[1]=duplicate[0]
    d=tensors(duplicate,4.,initial_lines(duplicate,pair,0.),pair,np.zeros((2,4,4)),np.zeros((1,8)),torch.float64)
    assert constraints(*d[:4],radius=0.)[1].max()>=.5
    report=dict(status='local_objective_controls_passed',seconds=time.monotonic()-started,
                source_commit='659ee62e4a9d39542a1146e8b011cc3ab6407ede',license='MIT; vendor/fq/LICENSE',
                original_native_sha256=NATIVE_SHA,native_oracle_sha256=sha(oracle),
                native_oracle_source_sha256=sha(args.out/'native_prob_oracle.rs'),
                objective_sha256=sha(ROOT/'experiments/fq_torch_objective.py'),control_source_sha256=sha(__file__),
                references_sha256=hashlib.sha256(data).hexdigest(),torch_version=torch.__version__,
                native_comparisons=rows,pair_coverage=coverage,memory_estimates=memory,
                true_rounding_disk_square_control_passed=True,duplicate_negative_passed=True,
                no_search=True,no_gpu=True,no_submission=True,
                limitations=['No optimizer or ALM convergence claim','FP32 is exploration only; native FP64 and complete unchanged gates remain mandatory',
                             'Saved-tensor bytes plus history are not measured GPU peak memory','Shared pair lists only; diverse-batch padding/rebuild state transport is not implemented'])
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],seconds=report['seconds'],cases=len(rows),pair_coverage=coverage,memory_estimates=memory),indent=2))


if __name__=='__main__':
    main()
