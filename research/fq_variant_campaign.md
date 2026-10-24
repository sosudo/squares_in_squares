# FQ variant campaign

This local CPU experiment polishes the 213 certified variants from the gentle
FTMC pilot and the 35 variants from the first FQ pilot. Its reference is the
frozen 17-type FQ best bank, not each trial's parent. A donor can improve its
parent and still fail to improve that reference; those cases are not counted
as new type improvements.

Implementation: `experiments/fq_variant_campaign.py`. It calls the unchanged
eight-field `trial(job)` API in `experiments/fq_active_pilot.py`. FQ is the
MIT-licensed source pinned at commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`; the tested portable binary SHA-256 is
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.

## Inputs and scheduling

- Reference: `artifacts/fq-active-v1/best_bank.npz`, SHA-256
  `67878f469b59b4cfd802fd264d0df2d78de7929af9b548d163149c648044f766`.
- Gentle inputs:
  `artifacts/gentle-ftmc-results/artifacts/worker0_gadgets.npz`.
- FQ inputs: `artifacts/fq-active-v1/donors.npz`.
- Priorities: `artifacts/active-frontier/active_priorities.json`.

All inputs are copied into an immutable `inputs` directory before execution;
the manifest hashes those copies and lists every input pose's exact float64
geometry SHA. There are 248 distinct input geometries. The gentle variants
cover four active types: 97 of `5_17_7`, 74 of `19_7_7`, 24 of `7_16_10`, and 18
of `4_16_9`. FQ contributes 35 variants across 15 types.

Inputs are ordered by increasing excess within each type, then interleaved
across types in active-priority order. Every input is submitted to `polish`
before any `kick` task is submitted. Remaining time runs independent seeded
small kicks against the current best bank, cycling through all 17 active
types in priority order. At most two trials are in flight. Each binary call
has a 20-second timeout and shares a monotonic campaign deadline.

The production run has a 590-second wall budget, including three seconds
reserved for final output. NumPy/BLAS thread counts are set to one per worker.
The existing trial API's timeout covers the FQ subprocess; decoding and
official validation follow its completion. Final observed runtime is recorded
in the analysis rather than inferred from the configured limit.

## Validation and output

Every retained new donor passes the unchanged official metric on raw geometry
and ordinary pandas CSV roundtrip data. Full competition composition remains
a separate validation step. New archive keys include the complete geometry
SHA-256, avoiding coarse-fingerprint overwrites. The script verifies that each
returned pose matches its certificate record's SHA and reported excess.

Each checkpoint is a new immutable `snapshot-NNNNN` directory containing
`donors.npz`, `best_bank.npz`, `results.json`, and `analysis.json`. The analysis
hashes the other three files, the frozen reference, and the run manifest.
`current.json` is atomically replaced and names one complete snapshot plus its
analysis hash. Convenience copies are produced at the run root on completion.
`best_bank.npz` starts from the entire frozen reference bank; each entry is
replaced only by a lower-excess officially certified result.

The four-trial smoke in `artifacts/fq-variant-smoke` completed in 2.33 seconds.
All four outputs passed certification, archive hashes and exact geometry hashes
matched, and all 248 inputs were recognized. No changes above `5e-9` relative to
the frozen reference were found or claimed in the smoke.

## Production run

The authorized production run is `artifacts/fq-variant-v1`. Root directed an
early stop after the fixed-scale search plateaued. The stop was requested at
370.22 seconds. All 248 polishes completed, followed by 471 logged kicks:
719 completed trials retained 586 certified exact-SHA donors. Two in-flight
results without logged source provenance are excluded. The last nine logged
trials were recovered after the last checkpoint; their seven certified output
poses were revalidated and matched their original exact geometry hashes.

The final immutable bundle is
`artifacts/fq-variant-v1/final-early-stop-verified`. Its donor archive SHA-256 is
`d5c153631e022ba711e2abe09a0241de54ab1e21b176f9fee6a4ada58268174e`;
its best-bank SHA-256 is
`dfdfe27f04b1b08de942103c3f2e33f4fe5c8e0f46471cf7619cedd475110ad5`.
The root-level `final.json` binds this final analysis. Original checkpoints,
configuration, and inputs remain unchanged; the early-stop record is explicit.

Eight types improved over the frozen FQ reference. The largest gains are
`8_20_7`: 0.001856075519, and `9_19_17`: 0.000296266071. Smaller gains range
from 7.55e-9 to 2.53e-6. These are rectangular component gains, not a scored
full portfolio result. The composition agent received both an early meaningful
snapshot and the final bundle. No Kaggle job or competition submission was
launched by this experiment.

## Follow-up hypothesis

The first fixed-scale kicks produced useful gains rapidly; later repetitions
mostly made much smaller changes. A separate follow-up should compare kick
scales `.003`, `.01`, `.03`, and `.08`, with occasional rounded-square
continuation and both incumbent and diverse donor starts. FQ applies `sigma`
to Gaussian x/y noise and `20*sigma` degrees to angle noise, so these scales
range from 0.06 to 1.6 degrees of angular noise. The current `.008` scale is
0.16 degrees.

Such a follow-up must freeze this run's final bank as its new comparison
reference and record the complete per-trial option list, source pose SHA,
seed, and executable/source hashes. It must retain all exact certified poses
even if an approximate similarity measure is used only for selecting diverse
starts. The v1 experiment was not changed to test this hypothesis.

## Authorized multiscale follow-up

`experiments/fq_multiscale_campaign.py` implements the separate follow-up. It
combines v1's final 17-type bank with the four newer component winners in
`artifacts/fq-additional-active-v1/best-final.npz`, SHA-256
`4a481e75af13d54874e8483c56ff5ab1dbd6d89da6e9c3622aa8644e6752a920`.
The resulting frozen comparison has 21 types. Weighted scheduling gives
`10_23_14` five times the ordinary visit rate and `20_9_12`, `10_23_17`, and
`19_7_13` three times the ordinary rate, based on their measured composition
impact. Every type remains eligible.

Kick scales are `.003`, `.01`, `.03`, and `.08`; one in eight mode slots uses
rounded continuation, alternating corner radius `.15` and `.05`. No repeated
plain-polish phase consumes the new budget. Approximately one in four starts
uses a selected diverse donor within `.005` excess of its type's reference.
The selection buckets round coordinates and angles only to choose starts;
every input and every new exact-SHA certified donor remains stored unchanged.

The executable is copied into the immutable inputs directory and its SHA is
recorded both in the manifest and in every trial record. Per-trial records
also contain the complete option list, seed, exact parent geometry SHA, parent
selection origin, and pinned public source commit. An external supervisor
covers the entire experiment, including copying, official certification,
checkpointing, and worker shutdown. Scheduling ends twelve seconds before the
configured ceiling; if the process group remains alive two seconds before the
ceiling, the supervisor stops the entire group and leaves the last complete
immutable checkpoint available. A `STOP` file requests an orderly early stop.

The authorized bound is fifteen minutes with two CPU workers and twenty
seconds per FQ binary call. The earlier v1 reviewer correctly identified that
its subprocess timeout alone did not enforce a hard whole-campaign deadline;
the separate supervisor addresses that limitation in the new round.

The ten-trial multiscale smoke completed in 8.77 seconds and exercised all four
kick sizes plus rounded radius `.15`; seven results were officially certified.
Archive hashes, exact geometry hashes, option lists, and reference-gain
accounting were independently checked. A deliberately blocked campaign and
its descendant were both stopped at 14.02 seconds under a sixteen-second
supervisor ceiling, verifying the hard process-group deadline path.

The production multiscale run is `artifacts/fq-multiscale-v1`. Its initial
meaningful checkpoints have been handed to composition while the run remains
bounded and unchanged. A compact 21-type best bank from snapshot `00037`
was frozen for immediate composition with SHA-256
`2aa7de3cfa9b3eb0a4e7beac80ec27ef7d4058c5cd0b28d7aa565b2c71099c26`.
By snapshot `00056`, material gains over its frozen reference included
`22_8_14`: .0052588151, `10_23_17`: .0026546681, `8_21_8`: .0021399355,
`19_7_13`: .0007559748, `20_9_12`: .0005287529, and `10_23_14`: .0002612747.
These are component improvements; composition determines their full-score
effect.

## Focused structural follow-up

The full-packing analysis in `research/active_broad_frontier.md` identified
canonical families `5x17+7`, `7x19+13`, and `7x20+14` as high-impact remaining
targets. `experiments/fq_focus_inputs.py` freezes those families in both
orientations, retaining exact broad-frontier reflected/oriented variants and
the available FQ/gentle donor archive. Prepared inputs are in
`artifacts/fq-focus-inputs-v1`: 337 exact donor poses across six orientations.
All eight exact broad-frontier donor variants for those families are retained.

Each orientation's frozen reference is derived from its canonical family's
best known pose. If transposition is needed, the coordinate exchange and angle
reflection are recorded explicitly and the resulting pose is recertified.
All six references pass official raw and pandas checks, and opposite
orientations have equal excess within `1e-12`. This avoids counting an already
known transposed family result as a new gain. The reference archive SHA-256 is
`163bb361caab1e4875038986a53d393206410fb9e4fca5b31a8ed47ac2f204a7`.

`experiments/fq_focus_campaign.py` is a separate configuration of the supervised
multiscale runtime. It gives each `5x17+7` orientation weight three and the
other four orientations weight two. Two of eight mode slots use rounded
continuation; the other slots span the four kick sizes. No plain polishing is
repeated. Its one-worker four-trial smoke completed in 6.44 seconds, exercised
`.01`, `.03`, `.08`, and rounded `.15`, and retained two certified donors.
Production launch is coordinated against the root's total CPU worker cap.

The multiscale production run completed normally in 888.30 seconds: 695 trials,
529 certified exact-SHA donors, and ten improved oriented types. Its final
bundle is `artifacts/fq-multiscale-v1/snapshot-00099`; donor SHA-256
`95d5b73b8a36cea9ea540d5ef0eb9a999d4094b633fa9acb307588bd9fbf4962`,
best-bank SHA-256
`5d8de5063a8c1c1559dc5a73b0f24c7bd6166609a1cabde99fd7d5ee7f38e0f7`.
All returned certified poses, archive hashes, and per-trial option lists were
checked again after completion.

The one-worker focused production run completed normally in 888.25 seconds:
739 trials and 623 certified exact-SHA donors. Its final bundle is
`artifacts/fq-focus-v1/snapshot-00083`; donor SHA-256
`a1d7b556efc1d62f7d6516f26f74d12ad4c87457440437fc456436bbf63beadd`,
best-bank SHA-256
`064b4e76c423c8b5617302b52c06ea8fc46b7f13d245550322406e7e36f8573d`.
Canonical `7x19+13` improved by .000301428965 and `7x20+14` by
.000121065914. Opposite orientations are not additive family gains.
`5x17+7` did not improve materially. Recent improvements justified completing
the original bound after an early-stop check; the slot was then released to
the high-n donor export/certification task, without increasing another run's
worker count.

## Soft-shape continuation

`experiments/fq_soft_campaign.py` is a distinct method using FQ's native
area-preserving aspect variables. Square dimensions temporarily become
`exp(a/2)` by `exp(-a/2)`, where `a = epsilon*tanh(b)`. Compression at nonzero
epsilon can change contact arrangements; eight fixed-box continuation steps
then reduce epsilon to zero before the ordinary rigid finish. Initial
amplitudes are `.03`, `.08`, and `.15`, with one `.08` variant allowing
`hold-f=1.002`. This is separate from both Gaussian-kick runs and rounded-corner
continuation.

Native shrink-hopping was inspected but deferred for rectangular inputs: its
hop clamp uses `[0.5, s-0.5]` on both axes and ignores the rectangular offsets.
The upstream MIT `melt_junction.py` and `contactswitch.py` are diagnostic
analyses of local melt displacement and contact-side/role changes. They support
investigating changed contact topology but are not themselves optimization
implementations. Their source copies are retained with the soft run.

The soft preflight compressed a deliberately loose asymmetric 3x3 grid by
.299999996 and passed official raw and pandas checks. A real `5_17_7` packing
activated log-aspect amplitude `.03`, then returned to a certified rigid pose.
Every retained soft result requires all eight verbose continuation steps,
monotone reported epsilon ending at zero, the expected initial amplitude,
and the unchanged unit-square official certificate. The pinned Rust source
sets exact epsilon zero at `k=K`, clears the aspect-variable vector, and calls
`set_soft(0.0)` again before rigid finishing. The zero-return log SHA is stored
in each record. A trial that lacks this evidence is excluded even if its
geometry alone would certify.

Prepared inputs are in `artifacts/fq-soft-inputs-v1`, containing 1,282 exact
donors and twenty orientation-fair references across ten priority families.
They combine final multiscale winners, the latest stronger focused winners,
the new `6x22+16` family, and preserved original source variants. All twenty
reference poses were recertified; the reference archive SHA-256 is
`69c8f3c7a6a508451aa4840980113159426338e0d925b6828f815537a06aff8a`.

The authorized production is `artifacts/fq-soft-v1`, bounded to 600 seconds
and two CPU workers, with the same whole-process supervisor. Its frozen
source and `rigid-return-proof.json` record the rigid-return evidence and the
actual twenty-orientation scope. The shared runtime's inherited prose mentions
21 types; the manifest and this proof file correctly describe this specialized
run's twenty orientations.

Snapshot `00023` was frozen for simultaneous CPU recipe replay and GPU
composition: compact best-bank SHA-256
`02eeffaa5854957c1ce35b408fda01d7ace9d26cd737e72bae55922447f3bff4`,
45-donor archive SHA-256
`a9858f78bae0fedb120840f947edac1c9c8cca70aa61ac368f6353627d68ab2e`.
No live input changes were applied to those downstream jobs.

If this distinct method plateaus, a separate aggressive pilot could increase
log-aspect limits to `.3` or `.6` (roughly 16% or 35% maximum side extension),
use 12–16 continuation steps with a smoother final schedule, and allow slight
hold-box slack. It must preserve the same explicit zero-return and ordinary
unit-square certification requirements. The current frozen 600-second run is
not modified to test that proposal.

Soft v1 completed normally in 588.13 seconds, with 198 trials and 90 certified
exact-SHA donors. The final immutable bundle is
`artifacts/fq-soft-v1/snapshot-00045`; best-bank SHA-256
`fe5a4f383a374115dd1e2d73f00b57ee5f1135cb92f1832ac5ef947133a7be0a`,
donor SHA-256
`2b52aa18d4ea67a53f4e3deb7e9068f900baa8dc1b509967bb0dfcf3aa786342`.
All archive, exact geometry, and continuation-log hashes were checked after
completion, as were every eight-step zero-return trace and rigid official
certificate. Six canonical families improved: `6x22+16` by .000592397053,
`7x20+14` by .000288419752, `8x20+12` by .000239805269, `8x22+14` by
.000182206892, `10x23+14` by .000147873003, and `9x20+12` by .000094319672.
No opposite-orientation improvements are double-counted in this list.

The final soft bundle was handed to composition, CPU replay, and the combined
GPU-output analyst for future frozen passes. The two workers were released
without automatic reuse. `experiments/fq_soft_aggressive_campaign.py` is a
prepared, unlaunched configuration for the stronger `.3`/`.6` proposal; it uses
the existing traced rigid-return gate and records all altered options.

## Strong-deformation controls and local junction method

Global `.3`/`.6` continuation passed both loose-grid controls but failed all
three real-packing controls: their excess rose toward one as the useful tilted
bands disappeared. The records are retained in
`artifacts/fq-soft-aggressive-preflight`; the corresponding long global run was
not launched.

`experiments/fq_local_soft_campaign.py` makes the strong deformation local. It
selects 24 or 40 nearby squares at an opposite-tilt-band junction, or around a
seeded tilted square when that junction definition is unavailable. FQ freezes
the surrounding already-feasible poses, including their aspect variables,
while the selected neighborhood receives the strong aspect continuation.
After exact zero-aspect return and ordinary rigid certification, every square
is released for a second rigid optimization and certification. Complete freeze
indices, center selection, source SHA, options, intermediate geometry, and both
certificates are recorded.

Each composite attempt shares a twenty-second native-stage scheduling budget;
the local stage is limited to twelve seconds and the rigid release receives the
remaining allowance. Decoding and final official checks can finish slightly
after that per-attempt scheduling deadline. The external 600-second supervisor
still covers all work, certification, collection, and shutdown. Independent
review found no validity or retention blocker. Here, “strict intermediate”
means geometrically certified, including poses whose scalar excess is unchanged
or slightly worse; it does not assert a strict objective improvement.

Real-target controls returned certified `5_17_7` and improved inserted
`5_17_8` by 7.18e-7. The complete four-trial smoke finished in 5.88 seconds:
all four primary results certified, and eight unique certified poses were
retained when local intermediates were included. The final collector runs
inside the supervised process and exports `all-strict/donors.npz` plus full
per-geometry provenance, using full SHA identities and retaining all lineages.

Prepared inputs in `artifacts/fq-local-soft-inputs-v1` contain 1,462 exact donor
poses and 32 orientation-fair references across sixteen families. This includes
the six certified neighboring-count families from
`artifacts/fq-insert-delete-v1/donors.npz`, SHA-256
`48ec40dc1056ada58e9af62ae91912272e187f3dc899385acaa72df4c0c10315`.
All 32 reference poses were recertified. The reference SHA-256 is
`9434e265962a93a1eb3b3e848038a81087d79ef36a6846276be0d4f9b4ef3a86`.
The later 29-pose insertion expansion was kept separate from this frozen run.

The authorized local production run is `artifacts/fq-local-soft-v1`, with two
CPU workers and a 600-second outer ceiling. Its snapshot `00036` provided an
early meaningful handoff: inserted `20_9_13` reached excess .902369770853,
improving its frozen family reference by .007882171020. The compact best-bank
SHA-256 is
`725f20c04864e033ac1de76720af6fa2c1d91f5f4c9c4f351b35900e53916115`;
the 133-pose primary donor archive SHA-256 is
`b413ed611cf314714a9e485d285876c7f3f19f70a984194cf714d240c8203955`.
The winning pose, archive hashes, local zero-return trace, and both rigid
certificates were independently checked before the downstream handoff. Full
portfolio impact remains for composition to determine.

The completed local run finished in 589.46 seconds, with 575 trials and 423
certified primary results. The other outcomes were 151 failures of the
near-best quality band and one timeout. Including every certified local
intermediate retained 846 exact poses and all 846 certificate lineages.
The final primary snapshot is `artifacts/fq-local-soft-v1/snapshot-00085`.
The complete union is `artifacts/fq-local-soft-v1/all-strict/donors.npz`, SHA-256
`c2aeea8fd99ac4c6b5b8c983fb9ac61b0be30672da1560f94ba03ec518033c7e`;
its provenance SHA-256 is
`6fd6f0d80b33017d9f19c3fab8067ef6fd431f9290658095685536ec9da0409a`.
Exact minima were recomputed over the frozen references and all 846 poses.
The resulting `all-strict/best_bank.npz` is identical to the primary best bank,
SHA-256 `9443c4cb997cefd81f4b5f73ec52f2a38a54eaf851865dcfdbdf7c5d9bc4e1d8`.
No certified intermediate contained an omitted better minimum. Archive,
geometry, proof and log hashes, zero-aspect return and recorded official
certificates were verified before handoff to composition. These checks bind
the saved geometries to their existing certificates; they do not claim that
all 846 official evaluations were rerun after completion.

Besides the .007882171020 reduction for `9x20+13`, material family reductions
were .001483748047 for `7x19+12`, .000548901579 for `8x20+12`, and
.000150570026 for `7x20+13`. Opposite orientations count as one family.
These rectangle reductions are not full competition score improvements.

## Five current bottlenecks and contact-connected local regions

The next explicitly bounded campaign targets the families limiting the current
full-puzzle compositions: `7x21+15` (813 and 871), `8x20+12` (807),
`6x22+16` (815), `10x23+14` (924), and `9x22+16` (931).
`experiments/fq_bottleneck_inputs.py` freezes 655 exact donor poses and creates
ten orientation-fair reference poses, all freshly certified through official
raw and ordinary pandas round-trip checks. The input directory is
`artifacts/fq-bottleneck-inputs-v1`; reference SHA-256 is
`d6ec7dc541d2951d3c7a7b237e326ef37ea203f96cac9ef3420039d7a79fa310`,
and donor SHA-256 is
`333c643784bc24275b2b10c9895d2acff458267c0f9b7ef2234b3c3a83b4d888`.
The source manifest and per-pose provenance preserve all original geometry
and source-archive hashes. This immutable bank was also handed to the separate
GPU continuation. The `9x22+16` references have 194 tilted squares; that exceeds
the old 192-row GPU kernel limit, and was explicitly reported for its runtime
preflight. The CPU method preserves all 214 squares without such a filter.

`experiments/fq_bottleneck_campaign.py` alternates the proven circular region
with a contact-connected region. It computes the maximum separating-axis gap
over both squares' axes. Edges have gap at most .035 and center distance at
most 1.6. A seeded opposite-tilt contact starts the region; weighted graph
growth frees 24 or 40 squares. If its connected component is too small, the
nearest remaining squares fill the mask and the fallback count is recorded.
Unlike repeatedly choosing the globally closest opposite-tilt pair, this
visits varied contact junctions. Source coordinates and angles stay unchanged
before the optimizer; all other squares remain frozen during the local stage.
Both policies use the same .3/.6 aspect schedules, exact zero-aspect return,
global rigid release, official gates and full intermediate retention. This is
an interleaved search comparison rather than a causal randomized efficacy
trial: types, evolving incumbents and seeds also differ.

Axis-aligned exact-gap and deterministic connected-mask tests pass under
`unittest`. The eight-trial positive smoke finished in 12.04 seconds, retaining
four certified primary outputs and six unique exact poses, with eight saved
certificate lineages including intermediates.
Both region policies produced certified outputs; four stronger attempts were
rejected by the unchanged near-best gate. The production run
`artifacts/fq-bottleneck-v1` has two CPU workers and a 900-second outer ceiling.
Weights 6 and 5 emphasize the first two families; the other families receive
weight 3 per orientation. These are sampling weights, not predicted score
gains. Its frozen source manifest is
`artifacts/fq-bottleneck-source-v1/manifest.json`, SHA-256
`9b4568bafacbd140abeef4bf6320cc2c4a85b38c6e58054f4723bd18374bbe02`.
The frozen trial source includes the parent's narrow malformed-native-output
handling fix, while preserving the original eight-field API and search flags.

The bottleneck campaign completed normally in 889.92 seconds: 548 trials,
358 certified primary outputs, 189 quality-band rejections and one timeout.
The complete union contains 652 distinct geometries with 716 saved certificate
lineages. The new `experiments/fq_verify_local_bundle.py` audit checks every
input/archive/source/geometry/log hash, the saved official raw and pandas
certificates, exact zero-aspect traces, and coverage of every primary result
and saved intermediate. It does not rerun the official evaluations. Its
real-data smoke passed, and two corruption-rejection unit tests passed.
The completed audit lives in
`artifacts/fq-bottleneck-v1/final-verified/verification.json`.

The largest canonical-family reductions are .003830007550 for `7x21+15` and
.000737512109 for `9x22+16`. `8x20+12` added 3.624091e-6, `10x23+14`
6.292750e-7, and `6x22+16` did not improve. Both orientations independently
reached the same `7x21+15` minimum; this is one family improvement. Its first
material basin transition was saved at 397.53 seconds. No canonical family
gained more than 1e-5 afterward, and the final 187.5-second checkpoint window
added only about 6e-14. The immutable trajectory report is
`artifacts/fq-bottleneck-v1/trajectory-final.json`, SHA-256
`938e75b790c94773857927481a1db748250fd06d300123b754abc465a2be3fe9`.

The final handoff regenerates and freshly certifies both orientations from
each family's exact minimum. It is
`artifacts/fq-bottleneck-final-handoff-v1/reference.npz`, SHA-256
`82aaa6f013bba306a25c3ecdafa8b13a841ea4fa22288d4e2ae9a3dc8696268d`.
The accompanying 666-pose donor union includes the 652 outputs plus preserved
references and new transposes; its SHA-256 is
`826806dab055cf8265477ccc2fbff1589e2a20fd5d1a0f2c35f0696ba438e6eb`.
The source manifest and per-pose provenance remain alongside those files.
All earlier snapshots stay unchanged. Downstream composition independently
reported four full-puzzle gains totaling approximately .000277 from the new
basins; that evidence, rather than a sum of rectangle excess reductions,
motivates further targeted search.

## Prepared larger connected regions

The plateau supports a distinct follow-up in
`experiments/fq_large_region_campaign.py`: 64 or 96 connected free squares,
with the same .3/.6 aspect schedules. Squares within .05 of an original wall
and farther than six units from the selected junction stay frozen. On the
actual new minimum, both requested region sizes are fully connected, with
32–33 distant wall squares explicitly preserved. A deterministic geometry
unit test passes. Global release uses the separately tested full-puzzle flags
`--no-alm --loosen 1 --pit 20 --flip-top 0`; the existing shared twenty-second
native-stage scheduling budget and all intermediate certificates remain.

Fresh inputs in `artifacts/fq-large-region-inputs-v1` contain 275 diverse
exact poses, retaining older starts inside the usual .005 excess band, and
two freshly certified orientations at excess .932818138356037. The reference
SHA-256 is
`a1a6b075541c107d1aeeb2fcddcfaea0e325a8d533508a27d7feccb0c3189792`.
An eight-trial real-data control run must demonstrate certified output and
actual junction motion for the larger masks before the separately authorized
900-second, two-worker production run starts.

Those eight controls completed in 8.78 seconds. Both mask sizes passed at
aspect .3, giving three certified primary outputs and six distinct certified
poses with intermediates. The 64-free control moved nearby squares by .0552
units and 1.244 degrees, with five contact changes; the 96-free control moved
by .0645 units and .203 degrees, with six contact changes. Within 2.5 units
of the selected center, the respective maximum motions were .01964 and
.06451. The first also changed two nearby contact edges. Frozen distant
squares moved only about 3e-8 after clearance legalization. This demonstrates
that the larger neighborhoods can move while returning valid packings; the
controls did not improve the objective.

All four .6 controls failed the existing quality band, so production excludes
that amplitude. The control configuration and actual executed trial dependency
are preserved in `artifacts/fq-large-region-smoke-v1/source-executed`.
The earlier `source/` capture coincided with the parent's parser update;
`source-executed` restores the exact executed trial hash from the prior
immutable snapshot and matches the smoke manifest. Neither artifact was
retroactively overwritten. Motion and junction reports are separately bound
in `motion-control.json` and `junction-motion-control.json`.

The authorized production run is `artifacts/fq-large-region-v1`, with two
workers and a 900-second outer ceiling. It alternates only `.3` continuation
with 64 and 96 free squares, plus the twenty-iteration no-ALM global release.
The source manifest SHA-256 is
`038e4bddcb38a7e1d0c6cab41e6704559cb3a5e565955d685d8d7875c2969918`;
the frozen trial source SHA-256 is
`cc916fe5bc0e58a4cdfdeb6e4f498061522a2ae44cd6443fdffc1f485eb3db33`.
That dependency includes the parent's tested rejection of nonfinite and
non-object native diagnostics; search flags and geometry gates are unchanged.
The 275-pose frozen donor input SHA-256 is
`b1fef663f7feba5c4c817955c4b44b7034aef5829e9c7c6b12c9e810b12c0c72`.
