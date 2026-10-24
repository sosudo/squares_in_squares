# Fractional interface controls and bounded search

The one-CPU prototype completed cleanly in **562.82 seconds**, with zero
certified candidates. It inspected **19,995 continuous phase domains**:
19,509 were rejected by a necessary pairwise translation bound and 486
reached the full MILP, which reported infeasibility. It visited 96 of 203
ranked type jobs, with the last job partial. The legacy counter named
`completed_type_jobs` means visited jobs in this run; it must not be used
to claim all 96 were exhaustive. Raw baseline SHA256 was
`b9374e881450748a04a86e39b84c69ba8607ceb1e95a303caeb93f38d9174354`.

Before this experiment, a 3.51-second scalar screen ruled out a simpler
proposal: deleting one to three colliding interface squares. Across all
1,391 oriented types and every admissible integer container, even its
optimistic bounds gave zero improving cases. Evidence is in
`artifacts/lossy-interface-headroom-v1.json`; no deletion search was run.

Keeping every square gives 79 scalar-promising cases, with an optimistic
aggregate ceiling of 0.06180. This includes impossible-looking classical
cases and is not an achieved or credible forecast. The practical initial
targets were n498 (5×17+7 joined with its transpose, optimistic gain
0.00097114) and n814 (7×21+15 joined with its transpose, 0.00100322).
Both complete finite pose sets failed rigid phase repair.

The new model retains donor angles and counts. Its seven continuous
variables are common fractional side, independent horizontal/vertical
shifts of the upper upright-grid region, and x/y translations of each
rigid donor. The first domain keeps each donor in its nominal expanded
tile; the second permits shifts up to ±0.25 while enforcing every square's
outer-wall constraints. Potential non-overlap is represented by a finite
SAT disjunction over the squares' own edge normals. All possible new
neighbors are included: each center has a proven displacement radius from
its variable-box midpoint, and the broad-phase search uses
`sqrt(2) + 2*max(radius)`. Same rigid-group pairs are invariant. MILP runs
use a single HiGHS thread and a bounded per-solve time.

This extends the existing adaptive separator search, whose blocks stay at
integer staircase anchors. The older cushion variant only adds a prescribed
upward/rightward translation. Neither searches these joint grid and donor
phase variables. Negative results here apply to the finite pinned poses,
bounded translations, fixed angles and numerical model; they do not rule
out deformed interfaces or other topologies.

The positive control forces a nonzero 0.02 donor translation in a known
27-square buffered construction. It finds unequal grid phases and passes
official raw, numeric and ordinary pandas checks plus independent interval
validation. The tight overlapping 18-square zero-buffer control is rejected.
A regression test verifies that a pair initially farther than `sqrt(2)`
is still included when allowed translations can make it collide. Both tests
pass. Frozen controls, source, input arrays, exact metadata, commands,
coverage and supervisor outcome are in `artifacts/fractional-interface-v1/`.

## A concrete shape-repair target

`artifacts/fractional-junction-diagnostic-v1/` freezes the least-overlapping
reflection pair among 256 choices for each targeted type order. Donors use
the favorable upward/rightward slack at a target side 0.0001 below the
current incumbent. All four individual component poses were freshly
certified; the full starts deliberately overlap and are **not packings**.

For n498, only source square 82 in each donor collides. The full-case IDs
are 396 and 488; their centers are near (5.2526,5.5411) and (5.5411,5.2526).
Both are almost upright. Maximum penetration is 0.7129113, and the
radius-2.5 repair neighborhood has 18 squares, six tilted. The donor
transforms are `[false,+1,-1]` and `[true,-1,+1]` of source
`01cbed14c830e3d33c5ba4bad44472a648fcfaacc60763d89ec3ecef7d46abf2`.
The invalid full start meets the intended outer walls.

For n814, one pair also collides, with penetration 0.8836754. Its 18-square
neighborhood has one tilted square. These large overlaps explain why small
rigid translations fail and motivate a separately bounded joint shape and
rearrangement pilot. No such repair success is claimed here.

The certified component archive SHA256 is
`9bc30ed55d7a93cd9db539f00ac3c0ea3650dde66940cb8428aac04810ca2b05`.
The explicitly invalid full-start archive SHA256 is
`faa87cec623f3df88c216b1917df7a9864643ef76418e6a75cec8c7ede42eaf3`.
Its filename and array keys label it uncertified/overlapping. Separate
component proofs, full-case local masks, original donor sources and geometry
hashes accompany both archives. No GPU job or competition submission was
made by this work.
