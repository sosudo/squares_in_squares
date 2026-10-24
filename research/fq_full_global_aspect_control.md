# Whole-packing aspect continuation: two bounded controls

Both n335 and n299 controls completed and returned independently certified
unit-square packings. Neither improves the current portfolio. The one-CPU
execution took **14.214 seconds**, under a 90-second outer ceiling; the
telemetry-only native build took another 16.274 seconds separately.

This test differs from the earlier frozen-neighborhood aspect experiments:
every square's position, angle and aspect variable was free. The source uses
`a_i = eps*tanh(b_i)`, with width `exp(a_i/2)` and height `exp(-a_i/2)`,
preserving area one mathematically. The options were `--soft-a0 .6`, sixteen
quadratic return steps, no `--soft-compress`, `--hold-f 1`, an initial
all-square `--kick .04`, and no per-step kick. The selected parent's encoded
box was held throughout continuation. At the final step, eps is exactly zero
and the aspect-variable vector is cleared; `set_soft(0)` precedes ordinary
rigid ALM45/polish100/flip16. There was no frozen-square mask.

The original native JSON field `soft.amax` measures the shape variables before
the fixed-box continuation. With compression disabled they are initially zero,
so this field cannot establish actual deformation. An isolated source copy
adds only read-only logging after each fixed-box relaxation: maximum
`|eps*tanh(b_i)|`, number of deformed units, and aspect-variable count. The
vendor tree and original portable binary remain unchanged. The exact diff,
native source, MIT notices, offline build command and binary hashes are in
`artifacts/fq-full-global-soft-v1-source`.

| Quantity | n335 | n299 |
| --- | ---: | ---: |
| Held search-copy side | 18.822875691188322 | 17.82287568917808 |
| Maximum observed absolute log aspect | 0.02783027 | 0.03555878 |
| Maximum observed aspect ratio | 1.02822115 | 1.03619855 |
| Deformed units at first phase endpoint | 335 | 299 |
| Final rigid side | 18.823112582201865 | 17.82287568941054 |
| Side above true canonical incumbent | 0.0002369266 | 0.00000003386 |
| Inclusive native/output-gate seconds | 3.796 | 8.636 |
| Angles changing more than one degree | 23 | 4 |
| Contact-edge changes at 1e-5 | 339 | 66 |

Deformation observations are the sixteen phase endpoints, not every internal
L-BFGS iterate. The first actual allowed bound is `0.6*(15/16)^2 = 0.52734375`;
the observed deformations use only a small portion of that allowance. Thus
this result does not support increasing the bound alone as a way to force
substantial distortion. Both final traces have zero eps, zero measured
deformation and zero aspect variables. Native support logs and scalar output
independently confirm the held side. All new finals pass official raw and
ordinary pandas checks and both independent interval checks.

The structural comparisons use D4 alignment and a center-assignment matching,
not raw row displacement alone. For n335, changed near-contact edges are
404/339/122 at thresholds 1e-6/1e-5/1e-4 and the maximum angle change is
2.6805 degrees. For n299 the corresponding counts are 67/66/65, with maximum
angle change 4.5269 degrees. These are useful pose diagnostics, not a claim
of a distinct global optimum or a general topological classification.

The two immutable certified outputs are in
`artifacts/fq-full-global-soft-v1/remote-certified/donors.npz`, SHA256
`1ea8043e13179ca736fbdbbcc2b7be20f3d340618a22a03ec83efbcec089b55a`.
Full certificate bindings, native stdout/stderr, exact input files, phase
traces, command options, source hashes and supervisor outcome are preserved
beside the report. The instrumented native binary SHA256 is
`28204076c85925db2709c019fdde40f244ec2dafbc6591737a703544774d0b98`;
the original portable SHA256 remains
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.

The canonical comparison is raw portfolio SHA256
`a5086672035b695a9a67ebd551a1e595161d3a88436d9f27abd41835564cb0f0`.
The slight clearance of the reused certified search copies is explicitly
excluded from improvement claims. No portfolio change, remote launch or
competition submission occurred.
