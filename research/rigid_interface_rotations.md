# Rigid donor rotations at the 498 and 814 interfaces

The bounded screen rejected this construction family before any optimization
trials. It found no new packing and changed no portfolio files.

The reference is the frozen raw portfolio
`artifacts/merged-fq-remote-replay-v1.csv`, SHA256
`381ffdc98df53c4ba9838fdc556eeead2f62681e427039e1c25224df873e9f4c`.
Its official aggregate score is 22.301061628222506; the ordinary-CSV-safe
portfolio score is 22.301061629093095. Neither satisfies the user's submission
threshold of 22.3.

## Construction and scope

The experiment considers the 5×17+7 / 17×5+7 pair for n498 and the
7×21+15 / 21×7+15 pair for n814. Each pair uses the existing integer
staircase anchors, with two independent translations in [−0.25,0.25]².
Each donor independently rotates rigidly about its center mean by an angle in
[−0.1,0.1] radians. All center distances and relative square angles within a
donor are preserved mathematically; the experiment introduces no shape repair.

The frozen option archive is
`artifacts/fractional-interface-v1/input-options.npz`, SHA256
`dd41c60a29ee46db15e10ecb280b55270e62c0d6d830c2387855c1b762688909`.
It supplies 16 finite geometry options for each oriented type. Both pair orders
are covered, giving 512 source pairs for each n. This does not exhaust other
donor geometries, larger translations, larger rotations, or different anchors.

## Angular exclusion bound

Each angle range is partitioned into 100 cells of width 0.002 radians. For a
cell midpoint, exact rotated square centers and square angles are computed.
If R bounds every donor vertex's distance from the fixed rotation center,
then every vertex moves by at most R times the cell's angular half-width.
Relaxing every outer wall by that amount yields a translation box containing
all feasible translations throughout that angle cell.

For each source pair, up to six obstructing cross-donor square pairs are chosen
at zero rotation. For each such pair and angle-cell pair, the maximum signed
projection along each SAT axis is bounded over the relaxed translation box.
The bound also includes both centers' possible rotational movement, the SAT
axis's possible rotation, and the change in the unit-square support radius.
If all four unsigned SAT-axis bounds are negative, those two squares overlap
throughout that entire angle-cell pair. This is a necessary geometric
exclusion, not a claim that a surviving cell would be feasible. Floating-point
calculations include 1e-10 slack; the observed exclusions are orders of
magnitude larger. This is not a formal arbitrary-precision interval proof.

Only donor/donor collisions are needed for the final rejection, so allowing
the upright filler squares to translate, rotate, or otherwise rearrange cannot
repair these particular excluded donor placements.

## Results and controls

The frozen run is `artifacts/rigid-interface-rotations-v1`:

| Quantity | n498 | n814 |
| --- | ---: | ---: |
| Source pairs, both orders | 512 | 512 |
| Angle-cell pairs considered | 5,120,000 | 5,120,000 |
| Cells remaining after necessary outer-wall bounds | 524,800 | 320,512 |
| Cells remaining after necessary cross-donor SAT bounds | 0 | 0 |
| Largest witness upper bound among wall-possible cells | −0.2993371978 | −0.1958447438 |

The complete screen took 11.429 seconds; the run finished normally in 11.453
seconds. No midpoint MILP search was justified or run. The empty candidate
file and complete source, input, and reference hashes are retained.

Two tests pass. The actual positive control rotates two five-square motifs in
opposite directions, composes them with a unit buffer, and passes independent
interval and official raw/default-pandas validation. The corresponding tight
zero-buffer construction is rejected. Additional controls verify rigid
distance preservation and check the conservative angular bound against
endpoint and randomized intermediate angles.

The frozen manifest SHA256 is
`8265ecf238134da0cfaa500f3292f20ac26669d22934720512c92ea8a502103f`;
the detailed screen SHA256 is
`56e1bfb4abdc82d211e074db68cda09542a77810c37803f145bb450e368e42ed`.
Every source hash remained unchanged through completion.

The separate independent review of the tied-branch LP engine passed all three
of its real-LP tests and a fresh full n299 baseline certificate. Its reviewed
source SHA256 is
`7e0a4df2a670aa291fb017581d9287bde274aa9eb6f2cc113186ea4629dec9b7`,
and the certificate is retained in
`artifacts/period5-branch-independent-review-v1/report.json`.
