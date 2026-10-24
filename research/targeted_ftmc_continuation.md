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
