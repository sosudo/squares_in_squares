The private targeted continuation is running at
`sos54352/squares-targeted-ftmc-n65-v1/1`. It uses two T4 devices with no dataset
or notebook attachments and no internet dependency. The frozen local bundle is
`artifacts/targeted-ftmc-n65-job-v2/`; its 949,841-byte source SHA256 is
`0aa0b1177774e46d2349520530cfc0757a40b73f2b129c1f504b284d40910e9b`.
The official API confirmed privacy, GPU selection, version 1 and exact equality
of remote/local source bytes. Local build revision 2 is distinct from Kaggle
notebook version 1. The earlier local build was preserved and never launched.

The six targeted families are 8×8 +1 (n=65), 7×21 +15, 8×20 +12, 6×22 +16,
10×23 +14 and 9×22 +16. Both orientations of each rectangle start from the
latest snapshot-00038 canonical minimum, with explicit, freshly certified
transposes. In particular, both 7×21 orientations start at excess
0.9328181383562715 and both 9×22 orientations at 0.9364374896484584. The n=65
reference starts at excess 0.5355339059402731 with 25 tilted squares. It receives
45% and 40% fixed sampling mass in the two arms because its L-frame family
affects 17 cases; hypothetical amplification is not an achieved score gain.

The starting bank and representative archive contain 120 distinct geometries:
24 freshly evaluated and 96 exact certificate reuses. Reuse checks the prior
frozen payload, matching validation bytes and every pose's binary64 array hash.
Source archives, prior references and n66→65 deletion topologies remain
separately bound in `prepared_provenance.json`. The cloud archive embeds 136
named poses; the complete original archives remain preserved locally.

| Setting | T4 arm 0 | T4 arm 1 |
| --- | --- | --- |
| Wall initialization | Incumbent fractional clearance | Incumbent plus mixed walls |
| Local-angle sampling | 75% | 25% |
| Mutation cycle | 0,1,2,3,4,5 | 5,4,1,2,5,4,3,0 |
| Birth/drop proposal | Existing +1 / drop1–3 | Add1–3 / drop2–6 |
| Extra broad moves | Existing distributions | Larger rotation, shear and position perturbations |
| Refill eligibility | Source-relative deficit +2 | Source-relative deficit +6 |
| Measured general-refill cap | 18% wall time | 25% wall time |
| Full-side shrink depths | −.004 through .004 | −.020 through .020 |
| n65 sampling mass | 45% | 40% |

Both arms retain the existing one-attempt-per-batch, 0.5-second refill alarm,
0.15-second finite MILP setting, FP32 exploration, FP64 refinement, rectangle LP,
strict gap checks and unchanged official raw/pandas admission. Every admitted
geometry is saved with its exact immutable certificate. Near-feasible captures
remain explicitly unvalidated; complete-puzzle recomposition still needs fresh
independent and official raw/default-pandas certification.

The old public mutation guard at 160 cores would have silently excluded
10×23 +14. Original 9×22 +16 references have 194 cores, above the existing
192-core row limit. An explicitly counted embedded adaptation extends only the
four coordinate/trig row arrays and matching checked guards to 256, using
1,024 additional shared-memory bytes. The other row/DP dimensions remain
bounded by w,h≤31. The original public vendor files remain unchanged; modified
embedded code carries a modification notice and distinct hashes.

Real GPU preflight passed on both devices before workers started: 256-core row
and FP32/FP64 optimizer paths, rejection of 257 before kernel launch, both
original 194-core references, all actual 171-core paths, and the largest
244-square full layout. All 11 actual target orientations produced mode-0
mutations; legitimate empty cold starts are recorded separately. Four local
regressions and independent frozen-payload review passed. Evidence is in
`targeted-ftmc-n65-v2-independent-review.json` and the bundle's
`actual-startup-proof.json`.

The search budget is 2,700 seconds per arm, followed by 120 seconds worker
grace. A parent alarm caps execution at 3,300 seconds; the official CLI launch
requested a 3,500-second server timeout. The immediate launch quota check used
`timedelta.total_seconds()`: 7,982.98 of 108,000 GPU seconds used, zero reserved,
and paid scaling disabled. Conservative arithmetic bounds are 1.5 nominal
device-hours and 1.944 maximum server device-hours; actual service accounting
is recorded separately. There is no reserved local search worker.

The startup stream proves active search, not merely RUNNING metadata. At the
captured 380-second heartbeat, arm 0 had 329 batches, 30,059 core trials and
8,624 full quenches; arm 1 had 882 batches, 76,984 core trials and 2,064 full
quenches. Both processes were healthy and no strict minimum improvement had
yet been reported. The stream is nested SSE: parse each outer `data:` JSON,
then parse the lines inside its `data` string. The initial outer-only parser
observation is retained, explicitly superseded by the decoded startup proof.

Source attribution remains the public Lightning v21 Apache-2.0 snapshot and
Evan Daniel's MIT FQ implementation at commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`, with inherited notices retained in
the payload. This is a search notebook, not a competition submission. The
user's strict submission threshold below 22.3 remains in force.

The bounded read-only monitor now runs as local PID 54208 (exec session 18161).
Its first two real polls verified the exact source and both active workers.
State is in `artifacts/targeted-ftmc-n65-monitor-v1/latest.json`; its original
70-minute deadline remains 2026-10-24 10:00:40.748376 UTC after a clean local
monitor replacement. It polls every 150 seconds, with independent request
timeouts and an exclusive lock. On completion it requests only 27 fixed named
aggregate/summary/certificate outputs, records their hashes and treats missing
outputs as incomplete. Eight monitor regressions passed. This is an owned
process in the current environment, with no survival guarantee after shutdown;
the remote notebook was never stopped or changed.

At the 2,100-second job heartbeat, arm 0 had 193,703 core trials and 55,168 full
quenches; arm 1 had 465,039 and 12,160 respectively, with no strict minimum
improvements yet. Frozen instrumentation has no per-key stage counts or wall
times. Its `families` counter means mutation modes, while the per-key `visits`
dictionary is never persisted. Funnel timings are global and the refill
per-key fields describe reference capacities rather than effort. Therefore
the actual n65 core/full-quench effort and wall share cannot be quantified from
this run; the 40–45% setting is sampling mass only. The live exact named funnel
file request returned HTTP 404 while the notebook was running. The frozen
source hashes, aggregate snapshot and unavailable-field evidence are preserved
in `artifacts/targeted-ftmc-n65-counter-inspection-v1/inspection.json`.

The run subsequently completed normally: 2,740.25 seconds total notebook
runtime and 2,725.12 seconds for parallel worker search plus final export,
with no timeout or worker failures. Both 2,700-second arms accepted zero
strict minima improvements. Their 849,624 core trials led to 85,968 full
FP32 quenches and 8,000 FP64 rows; all eleven final per-key minima equal
the frozen starts. The monitor collected all 27 named outputs and exited
successfully at 09:17:02 UTC.

There are nevertheless 7,033 retained, exact certificate-bound geometries:
4,595 from arm 0 and 2,449 from arm 1, sharing only the eleven initial
incumbents. The union has no exact typed-array or cross-type-array duplicates.
It retains 5,465 n65 poses and 1,568 poses across the other ten oriented types.
All arrays, records, aggregate hashes and the remote immutable-snapshot
verification receipts were checked locally without rerunning unchanged
geometry certificates. Individual immutable snapshots were not downloaded;
the proof explicitly distinguishes that from the remote runtime's check.
Archive SHA256 is
`b7f96c7c578eb45ef9f3663c4436043b93f464eb0ced888b69df564fd3408e1a`.

The original-phase 32-bin separator pairs show actual interface diversity:
for example 10×23 +14 has 5, 7 and 8 different pairs at 30°, 45° and 60°;
n65 has one, three and one. These describe possible join choices, not score
gains. All poses remain available for a separate composition partition in
`artifacts/targeted-ftmc-n65-analysis-v1/typed-bank-handoff.json`. Eight D4
transforms produce 56,264 sources before additional inputs, whose largest
packed job ID is 3,406,391,351. This exceeds signed int32 but fits the format's
unsigned32 field; every added source must be included in the bound.

The global funnel also reveals expensive repeated certification: raw/pandas
checks used 1,610.29 seconds (59.6% of arm 0) and 671.95 seconds (24.9% of
arm 1), while general refill used 142.01 seconds (5.3%) and 635.50 seconds
(23.5%). These timings are not assigned to n65. Per-key retained certificate
counts are selection-biased and cannot recover missing core/full effort or
wall shares. The exact final audit is reproducible with
`scripts/analyze_targeted_ftmc.py`; three tamper/admission regressions pass.
No further FTMC extension or GPU notebook was launched.

The later separate composition partition retained all7,033 poses with502
provenance-bound partners, covering65,168 orientations. Its finite32-bin
30°/45°/60° search completed in169.43seconds with all real CUDA controls
passing and zero proposals. Thus this archive has now been tested for
interface/crop propagation as well as scalar minima. This remains a finite
profile search, not an exhaustive impossibility claim; every variant is
preserved. Completion proof is under
`artifacts/composition-targeted-results-v1/completion-proof.json`.
