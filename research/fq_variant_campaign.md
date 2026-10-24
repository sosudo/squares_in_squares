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
