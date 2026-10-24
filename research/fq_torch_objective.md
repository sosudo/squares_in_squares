# Batched separating-line ALM: local feasibility prototype

The lifted FQ formulation is small enough to be a plausible GPU whole-packing
search path. The minimal Torch transcription matches the native scalar Rust
energy and gradients on actual n147, n299 and n335 packings. This establishes
objective fidelity and manageable state size, not optimization success or
measured GPU speed. No optimizer, GPU notebook or competition submission was
launched by this prototype.

The source is Evan Daniel's MIT-licensed
[square-packing](https://github.com/evand/square-packing), commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`. The original source and notice remain
unchanged at `vendor/fq/src/fq.rs` and `vendor/fq/LICENSE`. The source SHA is
`7045e9feff2d4b433053e4610258ca43d842e599fccf31d8b6b042276c2905c2`.

## Faithful variables, rounded support and objective

`experiments/fq_torch_objective.py` retains every square's `(x,y,theta)`, the
container side `s`, and independent `(phi,d)` variables for each retained pair.
The unit line normal is `(cos(phi),sin(phi))`; `d` is measured from the pair's
center midpoint. Neither the separating angle nor offset is eliminated by
a SAT maximum. No upright square is removed or frozen.

At corner radius `r`, each shape is the Minkowski sum of an inner square with
half-side `0.5-r` and a disk of radius `r`. Thus each inner corner has four
wall inequalities with margin `r`, and each pair has eight corner-to-line
inequalities with margin `r`. This is true corner rounding: `r=0.5` is a unit
disk and exactly `r=0` restores unit squares. There is no aspect deformation
in this prototype.

For every inequality `g<=0`, the PHR term is

`mu/2 * relu(g + lambda/mu)^2 - lambda^2/(2*mu)`.

The objective adds `s` for free-side optimization. Fixed-side mode omits this
term and detaches `s` from the constraints, matching native `fix_s`'s explicitly
zero side gradient. Multiplier updates are `max(0,lambda+mu*g)`.

## Pair-list guarantee

The rounded shape's circumradius is

`R(r) = sqrt(2)*(0.5-r)+r <= sqrt(0.5)` for `0<=r<=0.5`.

Build the pair list at center distance `sqrt(2)+skin`. Any omitted pair starts
farther apart than that cutoff. If each center remains within `skin/2` of
its list-build position, the reverse triangle inequality keeps their current
distance greater than `sqrt(2)`, so their containing disks remain disjoint.
This covers arbitrary angle changes and the entire return from rounded
shapes to `r=0`; no angular displacement term is needed when using this
universal circumradius.

The trial guard must run **before every objective or line-search evaluation**.
Rebuilding only after a long inner solve is insufficient for a continuously
valid list. `guard_pair_list` rejects at `2*dmax >= skin-1e-12`; the current
prototype computes this guard in CPU binary64. A future FP32 device guard
must use an outward error bound or an explicit conservative margin. The
analytic displacement argument is not a substitute for the final interval
geometry certificate.

On a rebuild, retain separators and multipliers by exact `(i,j)` identity,
initialize new lines using FQ's face/center candidates, and give new
multipliers zero values. Do not reuse incompatible L-BFGS history across a
changed variable inventory. This state transport is a future solver concern,
not implemented in the objective prototype.

## Local controls and measurements

`experiments/check_fq_torch_objective.py` extracts the native `Prob::eval`,
`viol_update` and scalar geometry prefix verbatim from the pinned Rust source.
It removes only unrelated module declarations and supplies a stdin/stdout
harness. The optional SIMD sin/cos path is disabled; the oracle uses standard
scalar trigonometry. The derived source and executable hashes are recorded.
No vendored source is edited.

Twenty-four native comparisons cover all three real packing sizes, radii
0/0.08/0.25/0.5, and both free/fixed-side modes, with nonzero multipliers and
perturbed poses and separating lines. Maximum absolute FP64 differences are
`1.82e-13` in energy, `4.27e-14` in the complete gradient and `8.0e-15` in
multiplier updates. Six independent directional finite-difference checks
have maximum error `5.08e-8`.

FP32 errors reach `1.06e-4` in energy and `0.00698` in a gradient component.
Those errors are compatible with exploratory optimization only; these
measurements do not establish stable ALM convergence. At coordinates near
20, FP32 spacing is already roughly 2e-6, far larger than the incumbent
clearances. Native FP64 finishing and unchanged full raw/default-pandas plus
independent geometry gates are essential.

The sparse list with skin0.3 contains:

| Squares | Near pairs | All pairs | Variables per replica | Constraints per replica |
|---:|---:|---:|---:|---:|
| 147 | 481 | 10,731 | 1,404 | 6,200 |
| 299 | 1,030 | 44,551 | 2,958 | 13,024 |
| 335 | 1,163 | 55,945 | 3,332 | 14,664 |

Thirty-six random trials move centers by at most0.149 and independently
rotate every square through arbitrary angles. Every dense all-pair SAT
overlap is present in the sparse list. An explicit omitted-pair control
becomes overlapping after both centers exceed the skin/2 bound and is
rejected by the guard before evaluation. Positive full-packing constraints,
duplicate-square and wall-penetration negatives also pass. Evaluating radius
0, then0.25, then exactly0 reproduces the original constraint bytes.

For a batch of32 n335 replicas, the measured unique saved FP32 autograd
storages total about5.00MB. Twenty L-BFGS history pairs would require another
17.06MB, and a temporary dense center-distance rebuild matrix about14.36MB.
These figures exclude other live tensors, gradients, allocator overhead and
optimizer workspace; they are not a measured GPU peak. They show substantial
memory headroom for a bounded pilot. The current implementation shares one
pair list across a batch; diverse per-replica padded lists/masks are not yet
implemented. A single CPU forward/backward took about28ms for this batch,
which must not be presented as a T4 speed estimate.

## Small next step, conditional on review

A later bounded GPU feasibility pilot should test the objective and gradients
against these native fixtures first, including pair-list expiry and true
zero-radius return. It should measure actual forward/backward time and peak
allocation before choosing a replica count. Any search would need per-replica
state, step acceptance and multipliers; one global Torch L-BFGS line search
over a summed batch would couple otherwise independent packings. A simple
first-order exploratory stage may be easier to batch, but native FP64
finishing still determines whether any full-packing improvement exists.

```bash
OPENBLAS_NUM_THREADS=1 timeout 120 .venv/bin/python experiments/check_fq_torch_objective.py \
  --out artifacts/fq-torch-objective-REPLAY
OPENBLAS_NUM_THREADS=1 timeout 30 .venv/bin/python experiments/check_fq_torch_geometry.py \
  --out artifacts/fq-torch-geometry-controls-REPLAY
```

The first run's report is `artifacts/fq-torch-objective-v1/report.json`, SHA
`94fd131ae308944c3a76b02e652d2d51c98fa26f475b745911895987e5d686cb`.
Supplemental geometry evidence is in `artifacts/fq-torch-geometry-controls-v1`.
The fixtures are the exact three references from the separately reviewed
full-packing GPU v2 bundle; that bundle and its active run were not modified.
