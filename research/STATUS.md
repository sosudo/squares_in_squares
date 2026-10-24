# Current working status

This competition task is ongoing. The user wants the highest possible rank, ideally first place. Continue optimization after compaction; this checkpoint is not a declaration of completion.

## Latest checkpoint — 2026-10-24 06:29 UTC

- **User steering: no further submission until both validated transport scores are strictly below22.3 (22.2x or better).** Hourly strict improvement and the daily cap still apply. Root stopped PID15213 at06:15:23 UTC, with no pending intent. The persisted authorization policy and controller both enforce this ceiling;31 controller/runner tests passed. Do not restart the runner with an ineligible candidate.
- Latest accepted submission **57584666** is COMPLETE, accepted06:07:08.397 UTC, actual public score **22.3047579593**. It ranked20/505 in the06:14:40 observation. Exact submitted hash4636cfc395424574a77d81131110eea9444fde0f16e5d48a133e1364d9e95f21; private immutable notebook `sos54352/squares-portfolio-4636cfc39542/1`. Two submissions accepted today. Timing alone permits no next submission before07:07:08.397 UTC; the new score threshold is additionally mandatory.
- **Current search baseline:22.304375968681107**, official safe and numeric-roundtrip scores exactly equal,0invalid,21fresh checks+979 hash-identical reuses. `artifacts/submission-public-refresh-v1-safe.csv`, SHA82ad3a551afb934d4b263a9fd1a7dc121f19bd9052c13218c5a39017ed7d0f29. Four KMMM26 improvements and17new Couzo certificates at commit1c1715399709bc955e9b402947ab8b52bbacdfc3. Once-only transport scaling, with all unchanged safe rows proved identical. This candidate is ineligible for submission. It is being exported through a unique private CPU notebook for search.
- The gentle full-target pilot completed with213retained certified new component poses, versus0control. Treatment reached398/464FP64 passes and336official admissions; control0/728passed. This resolves the forced-shrink feasibility bottleneck, but is not yet a complete-puzzle score gain. A released-worker retention bug overwrote one strict component improvement with a worse pose sharing its coarse fingerprint. Before a30-minute combined campaign, immutable snapshots/best-per-fingerprint retention are being added, together with anchor preservation and bounded refill CPU time.
- Refill-gate A/B also finished: relaxing the row-count screen found17refills versus0, but all120FP64finishes failed. General 2D refill consumed269/301worker seconds, so the combined policy must bound its wall-time share to about18% and use each feasible incumbent's measured row deficit.
- A broader dualGPU adaptive composer is in preparation: bins32/three angles on oneT4, bins16/seven angles on the other, using the latest baseline,320alternative public layouts, retained older best poses and the213gentle variants. Actual configured GPU preflights and official full-puzzle validation remain required. All donors must be covered or an explicit extraction cutoff reported.
- Alternative public bank:320layouts/240puzzle sizes/21pinned sources. Two public notebook outputs changed after the snapshot, so18frozen poses will be embedded exactly while302are reconstructed from unchanged sources. The canonical bank hash stays8e99e755d180be8416d8162c7200cfec0ab955ae508879179fc8b348bb7a52f2. A corrected private CPU export is being prepared; do not relax source hash gates.
- Prior composition iteration `sos54352/squares-composition-4636cfc39542/1` still reports RUNNING much longer than its600second supervised worker cap, with no available log. Attached inputs are only34.8MB, so excessive source-output caches are ruled out. Allocation/startup delay versus an execution issue is not yet determined. Do not extend its bound blindly. Notebook_frontier is investigating while preparing the broader run.
- Last observed quota:1.25GPUhours used,28.75remaining of30. Check live quota for current usage. No Paperspace machine exists; free-only authorization remains.
- Latest confirmed push before this checkpoint:d86d3fd. Root is committing the new policy and completed research evidence now. Read live agent messages for newer results.

## User instructions

- Commit and push at useful validated checkpoints. Git branch `work` tracks `origin/main`; use `git push origin HEAD:main` explicitly. Remote is sosudo/squares_in_squares.
- No submissions until both raw and numeric-roundtrip validated scores are strictly below22.3. Then submit at most hourly, only on strict improvement, within ten per UTC day.
- The full available Kaggle GPU quota may be used, but experiments must be intentional and checkpointed. Start with pilots; allocate longer runs based on full-puzzle gains.
- Paperspace/Gradient project squares_in_squares, ID pipamsa5ztw, is FREE instances only. No paid resources or upgrades. No machine exists.

## Submitted baseline

Kaggle submission **57583210** is COMPLETE. Actual public score **22.3048038109**, observed rank **15 / 491 teams**.

- Accepted: 2026-10-24T05:06:59.167 UTC. Next improved submission no earlier than 2026-10-24T06:06:59.167 UTC.
- Private source notebook: sos54352/squares-certified-portfolio-source-export, version2, output submission.csv.
- Local submitted CSV: artifacts/submission-safe.csv.
- SHA256: 97df15c28ee66ab1a414d28218fd4e8b28c2bf6ce8869281db9610f7dac81da9.
- Official local raw and ALL1000 ordinary pandas float64-roundtrip checks both scored22.304803810998131 with zero invalid cases. Kaggle displays a truncated score.
- Reproducible recipe and receipt: portfolios/baseline-57583210/. No credentials are in this recipe.
- Nine submissions remained after this baseline. Check live limits before subsequent submissions.

## Validation and export

Official metric v17 hash:312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733. Rules permit public data/released solutions with their licenses.

Never mutate a certified file during evaluation. Independent and official reports bind exact CSV hashes; official incremental checks reuse only identical decimal-row hashes. Every future candidate must pass raw AND floating-point transport checks.

Important discovery: eight of88 long-precision raw cases overlapped after float64 conversion. scripts/make_transport_safe.py fixes this with deterministic Decimal precision100 centre-only scaling1.00000000001; angles/unit sides stay unchanged. Cost was8.61e-10. Do not revert this precaution.

Kaggle source is limited to1MB. scripts/build_source_export_job.py reconstructs exact rows from hash-pinned public CSVs/certificates plus small embedded patches, then applies the shared transport transform. It is tested locally and remotely. Full literal CSV embedding exceeded the limit and is not used.

Direct local file upload is blocked at www.googleapis.com despite its saved network requirement. Use the fully supported ordinary-CSV notebook-output submission route: CLI competitions submit squares-in-squares -k OWNER/SLUG -v VERSION -f submission.csv. This already worked for the baseline. Pin completed version and verify its remote output hash.

## Search evidence and active work

- Generic Torch pilot: sos54352/squares-search-pilot v1, completed; no gains. Verified private GPU execution/download.
- FTMC pilot: sos54352/squares-ftmc-pilot v1, completed in679s wall /601s worker.96,584 core trials,76 accepted improvement events,154 saved variants,19 directed gadget keys improved. All GPU preflights and official checks passed. Outputs artifacts/ftmc-pilot-results.
- Those historical seed improvements did NOT improve the current full-puzzle frontier. Stronger existing crops dominate them; they need another0.11–0.35 bloat reduction. Do NOT launch the prepared30-minute historical-seed campaign artifacts/ftmc-campaign.
- Composition v1 failed on a CuPy uint64 sentinel comparison. Temporary runtime copies now explicitly type the identical sentinel; original public sources and hashes are retained.
- Composition v2: sos54352/squares-composition-pilot v2, COMPLETE in112s. All corner/seam/adaptive preflights passed. Only micro-gains beyond CPU closure; none of winning chains uses a fresh historical FTMC variant.
- The new GPU composition candidate is certified: `artifacts/submission-gpu-composition-safe.csv`, SHA256 `26b4b55c89b3606385a74645e327c4b9a6b40fda7f62f6bdd969dbff1cb39afb`, official score **22.304803775499245**. Float roundtrip differs by only 3.55e-15 and has zero invalid cases. Both reports cover all 1,000 puzzles, with 14 freshly evaluated and 986 hash-identical certificates reused. It is queued, not yet submitted.
- Private source-export version 3 completed and its downloaded CSV matches that exact hash. Reproducible recipe: `portfolios/candidate-26b4b55c89b3/`.
- The active-frontier A/B pilot targets 17 actual chain bottlenecks. GPU 0 preserves every original separator profile; GPU 1 explores freely from the same active seeds. Both retain certified alternative variants. Budget: 900 seconds per GPU, 120 seconds worker grace, 1,500 seconds overall.
- Active-frontier pilot version 1 failed before GPU preflight because it requested export v2 but Kaggle mounted the latest v3. A CPU-only probe proved that the attachment version suffix does not pin the output. Runtime file hashes remain mandatory. Version 2 removes unused audit attachments and embeds all actual search inputs; it is running with both T4 preflights passed. Preserve failed v1 and corrected v2 artifacts separately.
- Active-frontier v2 completed in 935.9 seconds: 683,941 core trials, 2,474 refill seeds, 39,584 full quenches, zero emitted variants and no failures. The guarded arm received no non-None polished poses, so profile rejection was not the limiting stage. Do not spend more time extending this unchanged configuration blindly.
- Complete-puzzle FTMC v1 completed in 636 seconds: 773,760 core trials, zero refill successes, zero full quenches, zero candidates. Independent exact-initializer controls show that recentering the unchanged tilted core loses 9–20 squares of refill capacity across eight cases, while keeping the original anchor recovers every count. A separate anchor-aware pilot is being prepared.
- The higher-n witness experiment found 200 independently valid donor crops from pinned public n>1000 certificates. Bounded CPU composition found no complete-puzzle gains; broader GPU separator composition is being prepared. Attribution and MIT notices are retained.
- The strict extra-capacity audit completed 200 trials in 285 seconds: 156 completed, 44 timed out, one certified rectangular increase from 544 to 545 squares. It is dominated for direct puzzle 545, but retained for composition. Archive `artifacts/refill-capacity/increased_surplus.npz` has SHA256 `ae8ff1e5b52fff09a56d42e9bddcdb7dcb3933f755e1de583f8a2b6aecd55c7d`. Public FTMC refills truncate to the original target count even when capacity is higher. A separate next pilot captures exploratory overflow cores and attempts N+1/N+2 repair; raw capacity alone is not a valid packing or score gain.
- Private `sos54352/squares-frontier-composition/1` was pushed successfully at approximately 05:49 UTC. It compares baseline control, 200 large plus 202 small higher-n donors, the new 545-square rectangle, and their union. Runtime source hash `42dd67ffcd6277479b34c94fa4a5b70c6c6b055a2dd38c9b1e3fccacf4f5c3b8`; hard wall limit 900 seconds. Keep source-export v3 unchanged while it runs. No FTMC variants were available to add.
- The next mutation experiment will test angle families centered on the actual incumbent geometry. Current active crops often tilt around 17–22 degrees, outside the public solver's preferred 26–45 degree families. This is a hypothesis to test, not an established gain. Do not simply extend old zero-gain runs without examining the search funnel.
- Last observed GPU quota: 0.27h used, 29.73h remaining. Read quota again for exact current use.

## Scheduler

The reviewed submission controller verifies queue/report/output hashes, full raw and numeric-roundtrip coverage, live quota, full history, strict improvement, no pending/ambiguous scoring, and 3,600 seconds since acceptance. It persists intent before submission and reconciles lost acknowledgements by a SHA marker. The queue retains all candidates and chooses the lowest eligible score.

Historical activation (now stopped under the stricter score policy): root enabled `scripts/run_submission_loop.py` at approximately 05:28 UTC with a 12-hour bound, 60-second checks and 600-second subprocess timeout. PID at launch: 15213. Its first actual tick correctly waited until 06:06:59.167 UTC. Read `artifacts/submissions/runner-status.json` and verify the PID before claiming it remains active. No system service is installed; survival across environment shutdown is not guaranteed. The adopted baseline and improved candidate are in `artifacts/submissions/queue.json`.

A brief environment interruption at approximately 05:49 UTC cleared without data or process loss: PID 15213 was explicitly confirmed alive and its tick 22 still respected the cooldown. Notebook-output attachment versions are not pinned by suffix, but the SDK `get_kernel(version_label='v2'/'v3')` was independently verified to return those exact saved versions; the scheduler's versioned output verification remains valid.

## Credentials and Paperspace

Never print credentials, environment dumps, or signed URLs. Kaggle wrapper scripts/kaggle_cli.py reads a runtime binding or protected /tmp/squares-kaggle-auth/token. Paperspace fallback is /tmp/squares-paperspace-auth/token. SSH private key is /workspace/.ssh/paperspace_squares_ed25519; the public key was provided to the user.

Paperspace API domains now respond with Cloudflare Error1010 browser_signature_banned, explicitly nonretryable and requiring site-owner action. This happens before credential authentication. Free availability/private notebook support remain unknown; no resources were created. scripts/paperspace_access.py stops on the denial. Do not spoof a browser or repeat unchanged denied requests. Continue using Kaggle.

## Reproduction references

research/public_frontier.md, additional_sources.md, decimal_transport.md, composition.md and notebook_submission.md describe evidence and exact sources. vendor contains attributed MIT Shubin baseline and Apache Lightning v21 solver plus inherited dataset notices. Artifacts are ignored by Git but retained; submitted reproducible recipes are tracked under portfolios/.
