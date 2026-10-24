# Independent scout: momentum hardening, with a bounded current-case test

The distinct lead is Nakajima-style momentum hardening of every square. The
public MIT implementation is available and its force checks pass, but our four
historical trials did **not** reproduce its published211 merger. This warrants
a small matched current-case test only after review, not an automatic GPU port
or a long production campaign. No current-case test or GPU reservation was made.

The canonical starting point is SAFEc9fca5a1… at22.29648715325571, leaving
0.05648715325571 to the user's strict22.24 cutoff. The proposed method has no
evidence supporting a forecast of that gain.

## What is different

Pinned public `evand/square-packing` commit659ee62e4a9d39542a1146e8b011cc3ab6407ede
contains `search/packer/src/harden.rs`. Its comments and tests explicitly
distinguish it from FQ's quasi-static rounded-shape ALM. The source represents a
rounded square as a core square of half-side h=0.5−r dilated by a radius-r disk.
For disjoint cores it uses their Euclidean distance; for intersecting cores it
uses SAT penetration. Pair loss is max(0,2r−signed_distance)², with wall losses.
Simply changing the radius in the old four-axis unit SAT kernel would not match
this objective at disjoint corner features.

All2N centers and N angles move. Velocities persist, with beta0.85, coordinate
learning rate0.04, translation/angle velocity caps0.03 and decaying noise.
Re-hardening first holds the box while r decreases to zero, then releases the
box under pressure and finally decreases that pressure. The public default
phases are2000 pre-steps,8000 or30000 hold-steps,4000 release and3000 settle.
During the first two phases the side is fixed; during release/settle one extra
box-size degree of freedom moves, with symmetric center translation as it
changes. Unlike the fixed-box cold hop, the path includes every square becoming
rounded, persistent inertia, and a later free-side pressure stage. Unlike closed
single birth, no unit is inserted and the count never changes. Only r=0 outputs
are eligible for unit-square certificates.

There is a box-force normalization caveat, not a silently corrected bug claim:
with symmetric resize δL and center shift δL/2, the wall-energy derivative is
−sum(active wall penetrations), while the code's `gl` is twice that value. It may
be viewed as a half-side force/preconditioner; its box learning rate is0.02.
The faithful controls retained these choices. Any later port should first match
the intended CPU source and report its independent physical oracle separately.
The exact-disk h=0 endpoint in `fresh` also has degenerate edge formulas; our
`reharden r0=.2` controls never exercised it. No fresh-disk or new GPU claim is
made here.

## Published evidence and its limits

The public PACKER ledger reports11/432 historical211 improvements, all at r0.2;
the best side was14.9936458090 from seed14.9979607050. Successful cells included
noise0.004/0.008 with hold30000 and noise0.008 with hold8000. It later rebuilt
the historical176 record after multiple rounds. These are author-reported
mechanism controls, not our reproduced results.

The same public ledger is strongly cautionary:0/18 multi-band records after
three rounds,0 new records on109 public packings up to324, failure at241, and
an110 explorer race leaning slower/worse. Its own recommendation kept harden
optional. Old FQ rounding controls separately failed hundreds of band-merger
attempts, so those do not test the same dynamics; nevertheless a naive claim
that momentum hardening is generally successful is contradicted by the public
negative coverage. No new repository release or protected source was fetched.

## Our historical/sanity result

The exact cached historical input is
`search/exact/batch/inputs/n-211.txt`, declared side14.99796070496771500150.
The exact176 seed at13.808663 was not located and was not replaced by a different
packing. The unchanged Rust source was compiled separately with pinned
Rust1.99.1; the original FQ binary was not overwritten. New hardener binary SHA
is e7775f23b1f3102a1a1b52654d06bcf5509b8eda75672fe77976d68f71d7acf7.

The original hardener test completed20000 pair checks:0/19999 off-smooth
gradient errors above1e−5, worst error2.813e−9; full energy gradient0/90 bad.
Those random checks do not replace future exact-tie and actual-GPU controls.

Four predeclared cells were run unchanged, followed by the public wrapper's
native-only polish (`--loosen 1 --no-alm`, same trial seed) using pinned FQ10ec…:

| Hold / noise / seed | Hardener seconds | Polish seconds | Fully certified final side |
|---|---:|---:|---:|
|8000 /0.008 /1|2.433|3.587|15.00599405163|
|30000 /0.004 /1|6.389|8.912|15.00874332288|
|8000 /0.008 /2|2.479|1.671|15.00000002804|
|30000 /0.004 /2|6.693|7.612|15.01465169074|

All four hardener outputs and all four polished outputs passed unchanged
official raw/default-pandas and independent interval gates on the exact retained
decoded17g unit geometries. Every certified geometry, including worse results,
is retained. Total work was45.63 seconds on one CPU, below180 work/210 whole.
There was no historical improvement and no current-record claim. Four draws
cannot reproduce or statistically falsify the published432-run effort with
11 hits; compiler/hardware trajectories and the sampled seeds also matter.
No extra seeds, parameter changes or follow-up optimizer were launched.

A wrapper defect caused polish stdout to overwrite each preceding hardener's
single-line stdout. Exact inputs, both raw output texts, commands, sources,
binaries and all certificates survive; the missing stdout is explicitly not
reconstructed. The executed driver is frozen separately and `logging-limit.json`
records the gap. The future driver has a logging-only fix with a no-optimizer
regression. Numerical source/options are unchanged, and no trial was rerun.

## Scale and a concrete next test

A read-only2.95-second census pins current RAW9d18b33… and the dated public v10
scalar table. It finds312 material positive dated differences totaling0.1032153.
Among cases above324,200 have multiple tilted bands or multiple folded-angle
families and total conditional difference0.06671859. These are diagnostic
threshold groups, not proven construction families or topology classes. Closing
the new cutoff from this group alone would require about84.7% of that entire
dated difference, which is a demanding conditional scenario, not a forecast.
The narrower multiple-angle-family group totals only0.03539589 and cannot
alone justify the goal. The table supplies no coordinate witnesses or lower
bounds. A small improvement must not be multiplied by200 without measured
case-by-case propagation.

The highest-value small current test is **591 and861**, with unequal bands
132+81 and203+84 and two substantial angle families. Their current dated
normalized differences are approximately0.000999 and0.001088. This deliberately
avoids making identical-piece merger the first test, because the public
identical/multi-band study was negative. Both current geometries have prior
native/cold exposure; the untested factor is faithful momentum hardening.

Proposed finite protocol, **not authorized or launched by this note**:

1. Freeze each exact current pose once and encode it once. The native-only
   control and both hardener cells start from those identical input bytes.
   Retain exact source/case/angle/seed hashes and the original current proof.
2. Run one strong native-only control per case with the established
   ALM45/pit100/flip16/loosen1/seed9710000 flags. Then run two unchanged published
   hardener cells per case: r0.2, seed1, held at the original side, either
   noise0.008/hold8000 or noise0.004/hold30000. Finish every returned r=0 state
   with exactly the same native flags/seed as its control. This future stronger
   finishing treatment is declared separately from the historical no-ALM test.
3. One CPU,300-second worker/330-second whole limit, at most4 hardener runs and
   6 native calls total. Reserve hardener50s, native12s and gate4s per hardener
   slot; controls16s each. Actual211 timing suggests roughly3–5minutes for
   these larger N, but that is an extrapolation; the hard cap and explicit
   deadline-skipped slots define coverage. No GPU port is needed for this test.
4. Preserve all final valid geometries and full decimal/output proofs. Compare
   with both the matched native-only endpoint and latest canonical. Record
   actual tilted count/angle and D4 pose changes without calling threshold
   features a new basin. Do not rank r>0 energy as unit-packing quality.
5. A material positive result should be roughly0.01 side on one case, or at
   least0.0005 total fully certified score improvement across the two, before
   considering a broader method. Small changes justify preservation, not a
   long campaign. Zero material gain closes these finite cells on these inputs.

If that passes, a GPU implementation still needs exact CPU-step/force/rounded
distance controls, preserved velocity/RNG state, conservative neighbor coverage
under both motion and shape change, full count/last-index tests and final r=0
gates. It must not substitute the old unit-SAT or lifted-ALM loss while claiming
the public dynamics. Broad benefit then needs measured gains across new cases
or certified reusable components, not just the conditional0.0667 inventory.

Reproducible evidence: `artifacts/strategy-scout-v1/geometry-census.json` and
`artifacts/nakajima-historical-controls-v1`. Stable scout code is
`experiments/strategy_scout_geometry.py`, `nakajima_historical_controls.py` and
its logging regression. No canonical mutation, export, queue or submission was
performed by the scout; the strict22.24 user policy remains in force.
