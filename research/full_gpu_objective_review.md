# Independent objective and retention review

The frozen v1 remains unchanged. The review found one reproducible gradient
defect at tied SAT axes and several search limitations. None invalidates an
already published packing certificate: v1 independently re-evaluates and
certifies the actual final coordinates.

## Correct the tied-axis angular derivative before v2

The public optimizer computes each pair twice, once from each square. It picks
the first axis with maximum absolute center projection. At equal square angles,
the two directed loops can both select their own duplicated first axis. Each
then attributes the complete angular projection derivative to its own square.
Those two derivatives do not form a consistent derivative of the pair energy.

The source-faithful CPU control uses two unit squares at
`[[2,2,0],[2.9,2.2,0]]`, away from all walls. With tau=0, the native formula's
directional derivative for rotating both angles together is −0.04000000008;
finite differences give −0.02000000004. Relative angles remain fixed along
this direction, so the support-radius cusp does not invalidate the comparison.
Rotating both centers and angles rigidly must preserve pair energy. The same
formula instead gives −0.02000000004, while finite differences give approximately
zero. Tau=0.02 has the same defect. Untied controls agree within 3.5e-11.

An initial canonical-owner correction passed those directional controls, but
root identified a stronger counterexample involving the coupled support-radius
cusp. With displacement (0.9,0.8), the one-sided angle-gradient limits are
approximately (−0.05,−0.03) and (−0.03,−0.05). Canonical-owner selection combined
with the existing zero support subgradient gives (−0.08,0), outside their
Clarke segment by 0.0424264. Coherent-direction agreement alone was therefore
insufficient. The earlier comparator result is retained as an explicitly
incomplete intermediate check; canonical-owner selection is not endorsed.

The corrected recommendation averages gradient contributions uniformly over
all exactly maximal projection axes, while applying the radius derivative
once per directed pair. It gives (−0.04,−0.04), the midpoint of the limiting
gradients in the counterexample. Both coherent and rigid-rotation controls pass
for common angles 0 and 0.31, at tau 0 and 0.02, for displacements (0.9,0.2)
and (0.9,0.8). Exact energy and untied gradients remain unchanged. These are
CPU controls, not CUDA execution claims. V2 still needs the same actual-CUDA
controls and source replacement guards.

At a diagonal corner, the coherent-angle-only direction itself can have a
cusp. A central finite difference there is not a universal subgradient oracle,
especially when floating-point rotation splits an exact four-way tie. The
additional corner checks should use rigid-rotation invariance, row-permutation
equivariance, and the hull of nearby smooth-branch gradients.

Evidence is in `artifacts/full-gpu-objective-review-v1`:

- `tied-axis-gradient-control.json` reproduces the defect and pins the public
  sources and source-faithful control.
- `pair-consistent-fix-control.json` and `pair-consistent-evaluator.py` retain
  the insufficient canonical-owner intermediate control.
- `symmetric-tie-control.json` tests symmetric active-axis weighting and the
  coupled-cusp counterexample that rejects canonical-owner selection.

The original public optimizer SHA256 is
`1e9214275e5ee750ad3b880813d42679f4b22674a5f927af568bce99e5567a7b`;
its base CUDA source file SHA256 is
`93e352b406e100d6ae2a5eb2f8dc4dfa77df3a84da7cd92d6bb0fa990a700eb7`.
No production optimizer file was edited.

## Remaining objective and stopping limitations

All 3N coordinates, including every angle, are optimizer variables. No hidden
angle freeze, clamp, or fixed-core capacity limit was found. However, exactly
upright frame squares frequently have zero first-order angle force under wall
and parallel face-contact terms. The mutation layer intentionally preserves
upright inputs. These facts can keep a frame in the same structure even though
its angles are formally free; a finite interface-frame perturbation would be
a distinct mechanism, not something automatically provided by L-BFGS.

The continuation smooths absolute values, not the maximum over SAT axes. It
therefore retains active-axis nonsmoothness. It also introduces artificial
parallel-contact pressure of roughly tau/2. That pressure can favor expanded
loose-box configurations; the continuation arm's best certified loose poses
were approximately 0.04 wider than the reference. Fixing tie ownership does
not make this exploratory energy an exact physical or smooth objective.

The box is a fixed feasibility target, not an optimized area variable. Once
penetrations disappear, the energy has no pressure to reduce the side further.
Repeating the same exact box after convergence cannot by itself create another
contraction. V1's target depths of 2e-6 to 2e-4 were also much smaller than the
dated 299/335 public side gaps of about 0.020 and 0.028. V2's proposed explicit
depth strata through 0.02 address this limitation, without promising success.

Changing only the upper box walls initially generates translation as well as
compression forces. A smaller requested box or lower penalty energy therefore
does not prove a smaller physical bounding side. Measure actual side and
separate wall versus pair residuals throughout the stages; the proposed v2
coordinate-based priority rules correctly do this.

The native loop stops on max penetration below 2e-11, budget exhaustion, or
failure of all 24 Armijo trials. A failed line search returns the previous
accepted coordinates and energy, but its reported max penetration belongs to
the last rejected trial. V1's fresh exact re-evaluation protects admission.
V2 telemetry should record termination reason, iterations, gradient norm,
line-search failures, and fresh accepted-coordinate energy/residuals. A
positive-overlap pose with zero gradient can also repeat zero-length steps;
it is not a feasible packing. Restarting curvature history and trying a
bounded steepest-descent fallback may help an actual line-search failure,
but should be measured rather than inferred from the iteration budget.

## Retention and throughput assessment

Terminal v1 evidence shows 2,246 certified geometries and no improvement. All
certified search records came from loose stages; complete raw target-stage
feasibility was not retained, so it cannot be reconstructed from these counts.
The exact arm spent 506.23 of 566.33 seconds certifying versus 41.58 in CUDA;
the continuation arm spent 409.68 of 569.04 seconds certifying versus 126.50 in
CUDA. This is a measured host bottleneck, separate from the objective defect.

The v2 design in `artifacts/full-structural-gpu-v2-design-v1/design.md` addresses
the right limitations: save actual shared start bytes and every finite stage
as explicitly unverified, rank candidates from physical legalized coordinates,
defer full certification to a bounded process queue, preserve pending work,
and report actual coverage and per-stage residual populations. Exact final
gates and immutable pose/proof publications remain mandatory. The independently
reviewed scheduler fix addresses the separate source/operator coverage bug.

V2 is not ready for a claim of resolved optimizer behavior until the tied-axis
correction passes live CUDA tests. The recommended additions are the tied-pair
coherent-rotation control, accepted-coordinate stop telemetry, and separate
wall/pair/physical-side metrics. No optimization campaign or remote launch was
performed during this review.
