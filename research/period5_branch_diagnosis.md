The n299 source has421 upright diagonal corner contacts. At each, x and y
are distinct valid separating directions; choosing a single argmax axis
may constrain a later row slide unnecessarily. Duplicate directions from
the two equal-angle squares are deduplicated before counting such choices.
The baseline policy retains the exact original argmax rule.

The finite branch experiment keeps all598 center coordinates independent
and uses the same global tilt offsets0,−.25°,−.5°,−1° and−2° as the matched
position ablation. It compares baseline, vertical-preferred, checkerboard
and16 seeded random choices among tied distinct axes. Two additional
provisional relaxations omit only source contacts with multiple distinct
zero-gap axes: upright diagonal contacts only, or all such corner contacts.
Strictly separated pairs are excluded from the omission set.

After each provisional LP, every one of44,551 square pairs is checked.
Any actually overlapping pair receives a genuine unit-square SAT branch
cut, with at most64 new cuts per round and16 rounds. A lower provisional
side is never a packing gain. Only a complete numerical all-pair/wall
screen, rounding-only legalization, and fresh independent interval plus
official raw/default-pandas gates can retain a pose. Branch choices and
trust regions remain finite and local; failure is not a global impossibility
proof. The LP dual diagnostics distinguish active corner rows from rows
carrying nonzero contact load.

Three focused controls pass: diagonal corners expose two distinct axes,
edge contacts expose one, and an intentionally omitted two-square corner
produces an overlap that is detected and repaired by a new SAT cut. The
real n299 baseline full control runs before search. Source, imported helpers,
the metric, current input and certificates are hashed. Execution is limited
to one CPU, two seconds per LP,590seconds internally and593seconds for the
supervised process group. No GPU or competition submission is involved.

Independent review and the fresh n299 interval/official control passed.
The complete105-configuration experiment then finished in60.35seconds,
retaining100 unique fully certified geometries, with zero gain. Inputs and
executed source hashes stayed unchanged. The original source is preserved
under `artifacts/period5-branch-lp-v1/source/`; its summary binds every output.

In the baseline, all421 corner rows are active, but only14 carry a nonzero
LP dual. Their absolute dual sum is6.6220 of16.5788 over all pair rows.
Those loads alone were misleading as a necessity diagnostic: removing
**every corner row simultaneously** at every matched tilt leaves the side
unchanged, and each relaxed solution already passes all44,551 pair checks.
The real omission cases needed zero repair cuts. The synthetic negative
control did require one and repaired its intentional overlap successfully.
Changing or randomizing the tied choices also produced no gain.

After corner removal, load transfers to an ordinary cage around primitive
column10: core pieces276/277 and upright tips112/127, joined to vertical
upright chains above and below. The three core/cage constraints each carry
0.755928946; the upright chain constraints carry0.688982237. Exact source
IDs, centers, angles and remaining loads are mapped in the run's `analysis.json`.
The earlier upright-angle presets included112/127, but tilted eight other
uprights at the same time; they do not isolate this cage.

The supported conclusion is that the421 diagonal-corner choices are redundant
for the tested local solutions. A necessary next structural change would
involve a remaining non-tied core/chain branch, a different occupancy/cell
primitive, or movement beyond this±.35 trust region. The experiment does not
prove global optimality or rule out those changes. All three period5 runs
and215 source outputs are preserved; exact deduplication retains211 typed
17×17+10 alternatives in `artifacts/period5-column-handoff-v2/` with their
unchanged-array full certificates. No new search followed this finite result.
