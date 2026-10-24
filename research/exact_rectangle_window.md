# Exact translated rectangular-window pilot

The separate `experiments/exact_rectangle_window.{cpp,py}` pilot queried
rectangles `(w+f) × (h+f)` for 21 active canonical donor families, including
the five current FTMC bottlenecks and `9×22+11`. This extends the proven
closed-interval translated-square sweep; it does not repeat that square-only
search. Every selected square retains its exact source coordinates and angle.

The controls in `artifacts/exact-rectangle-controls-v1/controls.json` include
non-square grid/boundary cases, 20 comparisons against an endpoint brute-force
solver, and a six-square layout passing official and independent raw/default
pandas gates. The production run visited all 1,620 prepared source poses,
performed 58,776 threshold queries and 91 binary-refinement queries, and
finished in 71.79 seconds with one worker. Sources include the pinned 175
public full witnesses, 320 public alternative layouts, the named current
reference banks, and 996 cases from the then-current certified portfolio.
No fresh public-source download, GPU job, or competition submission was used.

Four subsets passed all full component official/independent raw/default-pandas
checks, totaling 703 squares. All four are retained in
`artifacts/exact-rectangle-v1/donors.npz`, SHA-256
`bf617cf38dfd0d78ad723c881e22309cbc42f87ea0e3f50e2639cf03857b8462`.
The immutable manifest, report, source square IDs, source array hashes and
gate binding are in that directory.

The initial named reference list omitted stronger existing multiscale layouts.
The subsequent `canonical-reference-audit.json` checks all 7,276 current GPU
input poses in both orientations, matching complete-array square counts to
the target nominal rectangles. All four outputs are scalar-dominated. Three
reproduce existing multiscale layouts under D4, translation and center dilation
`1.000000002`, with maximum coordinate residual below `1.4e-14` and unchanged
square angles. The fourth is a different `20×8+7` arrangement cropped from
full case 915, but its bloat exceeds the retained scalar best by approximately
`0.0009284`. These results establish no new scalar record or portfolio gain.
The geometry comparison is explicitly numerical and does not replace the
stored full validity certificates. All four layouts remain retained because
different arrangements can support different subsequent joins.

A bounded follow-up reused the proven exact two-block composer against the
latest `c766288f...` raw portfolio. Its partners were all 51 original active
layouts and all 28 broad-active variants. Every D4 transform, block order,
public join mode and feasible square container was considered: 120,576
mode-pairs and 183,328 containers screened, with 1,504 scalar-promising jobs.
All 1,504 failed exact cross-block SAT, so no new full construction was emitted.
The buffered positive control passed. This complete finite replay took 1.99
seconds; evidence is in `artifacts/exact-rectangle-pair-replay-v1`.

The scan excludes improvements smaller than its `1e-6` query margin and does
not exhaust new source poses, other donor types, arbitrary polygonal windows,
or multiblock combinations. Negative queries made using looser original
reference boxes also exclude hits in tighter replacement boxes for the same
source, type and requested margin.
