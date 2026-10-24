The dated public per-puzzle table reveals a useful target trajectory:
`n = k² + ceil(4k/5) − 4`, for k17 through31. Its fifteen cases include all
six largest documented gaps:299,335,412,454,498 and803. Their combined gap
against the frozen b9374 portfolio is0.01564433819. These are reported public
side targets, not released coordinates or a construction proved here.
The source version/rendered hash and all fifteen rows are preserved in
`artifacts/public-period5-analysis-v1/report.json`.

The surplus `d=n−k²` rises by four every five side increments. Ordinary
L-frame expansion holds d fixed, so it cannot by itself explain this
trajectory. Nearly constant fractional sides also repeat across changed d:
0.79816558 at k20–21;0.79903359 at k22–24;0.79568537 at k25–26; and
0.79613088 at k27–29. A length-dependent narrow strip or repeating seam is
a better structural hypothesis than fifteen independent constructions.
The count pattern alone does not determine a rational tilt angle or prove
that the same primitive generates every reported record.

The current n299 pose gives a concrete primitive to vary. Its43 tilted
squares have angle24.295189°, satisfying cosθ−sinθ=1/2. In that square basis,
their longitudinal coordinates are integers0..21:21 columns contain a unit
dimer and one terminal column contains a singleton. Each column's transverse
phase may slide while retaining its internal unit-square contact. The
current clearance f=2sinθ=(sqrt7−1)/2 is therefore a useful baseline lock to
explain, rather than a new target already achieved.

A complementary small model can optimize shared upright grid lines, one
longitudinal/transverse phase per dimer, and global or periodic column-angle
patterns. At fixed angles its separating-axis constraints are linear. The
positive control must reproduce the frozen current pose and recover its
side after a controlled dilation; duplicate pieces must fail full SAT.
Every LP residual remains separate from strict independent/official
raw/default-pandas geometry gates. This is distinct from the ongoing native
whole-case vacancy and coherent-bend search.

The initial finite scan completed all87 configurations in20.51seconds on
one CPU. Current/dilated-recovery controls passed; a duplicated square
failed full SAT. Fifty-four distinct outputs passed every full gate, but
none improved17.82287565554912. Global angle offsets on either side of
24.295189° worsened the side; periodic transverse phases returned the old
side. Original source, input hashes and proofs remain under
`artifacts/period5-column-lp-v1/`.

The matched structural ablation then used exactly the same lower-angle
settings in five models:

| Model | Position variables |
| --- | ---: |
| Shared grid lines and rigid dimers |106|
| A: individual upright positions |556|
| B: six selected dimers split |118|
| A+B |568|
| Every square position independent |598|

All five recoverable positive controls and the duplicate-negative control
passed. At−.25°,−.5° and−1°, the five sides agree within approximately3e−8.
Thus these position ties do not explain the plateau within the tested
contact branches. With every position free,36 further treatments preset
±.5°,±1° or±2° on ten uprights beside the seam endpoints/interior junctions;
all worsened the side. The entire61-configuration run completed in32.87seconds
and retained61 fully certified poses, again with zero gain. The scripts and
all imported helpers/metric were hashed and preserved. Root and independent
review both confirmed the matrix, restored split-pair SAT constraints,
distance-safe neighbor radius, wall bounds and full acceptance gates.

These are finite local separating-axis branches and trust regions, not a
global impossibility proof. More unconstrained center or similar angle
samples are not justified by this result. Contact-load/dual diagnostics,
explicit separator-branch changes, or a different occupancy primitive are
the remaining structural questions. The new code is
`experiments/period5_column_ablation.py`; its three tests plus the original
model's three tests pass. Both completed negative experiments and every
certified alternative remain preserved; exact-array deduplication and a
typed17×17+10 handoff are under `artifacts/period5-column-handoff-v1/`.
