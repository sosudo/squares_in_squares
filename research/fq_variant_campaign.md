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
