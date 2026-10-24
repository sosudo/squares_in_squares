# Current working status

This competition task is ongoing. The user wants the highest possible rank, ideally first place. Continue optimization after compaction; this checkpoint is not a declaration of completion.

## Latest checkpoint — 2026-10-24 08:00 UTC

- Submission gate remains strict: BOTH official safe and ordinary pandas-roundtrip scores must be below 22.3. The controller is stopped; only two competition submissions have been made. Latest accepted 57584666 scored 22.3047579593. No new submission has been authorized above the threshold.
- **Best fully certified score 22.301832917346843**, identical after pandas roundtrip, zero invalid cases. Safe `artifacts/submission-composition-fine-v1-safe.csv`, SHA bcdec008d7f128c44bf31b51013449b39df988158cac52869c47dda9d0a2bb19. Raw `artifacts/merged-composition-fine-v1.csv`, SHA dcef215e7561ef72ee959782b2f03736b858307113776bbbfe3293002bf70128. Canonical summary `artifacts/submission-composition-fine-v1-safe.transport-validation.json`, SHA 214943b05f718316d5a63d86c03d967f126a2a1e8f0b1fa5090944d7249f8de4: 10 fresh checks and 990 exact certificate reuses. All earlier CPU, public, and n599 gains are preserved.
- Pending full-basin merge contains n702 and n813, with combined certified candidate gain 0.0000902639778009 against the fine portfolio. Frozen candidates `artifacts/fq-full-basin-union-v1/candidates.json`. Notebook_frontier owns the merge and complete transport validation; do not report the expected aggregate as certified until that finishes.
- Fine GPU composition `sos54352/squares-composition-fine-9c8cccde95fe/1` completed all 61,600 orientations on both T4s in 273.88 seconds. The 64-bin arm gave no material benefit over 32 bins. Both actual-sized geometry controls and real-CUDA high-index controls passed. Critical runtime fix widens donor-index multiplication BEFORE multiplication in four copied CUDA sites; vendor sources remain unchanged. The previous larger bundle with the overflow bug was never launched. Tests cover the actual compiled expression and old signed-int32 failure boundary.
- Public-data freshness checks previously missed Ready versions 27/28 because `currentVersionNumber` incorrectly said 26. The corrected helper selects the highest explicitly Ready version and refuses an unchanged claim when history is incomplete. Explicit KMMM v28 added three small improvements (n338,376,928), with exact source SHA and source-specific notices preserved. Earlier negative evidence is retained with a correction. Latest public refresh was approximately 07:39 UTC.
- Combined FTMC completed 1,840.25 seconds: 69 strict minima retained, 4,596 certified variants. Three types improved the newest CPU references: 4x16+9, 21x7+15, 5x18+11. Aggregate SHA 204eaa312767cdaf957e708bc8476f4fa5c7eba869e5994cdafd781b4a67d45f. Root's later FQ polish improved 4x16+9 to f=0.9270518650565833 and 5x18+11 to f=0.9369086730295173; frozen bank `artifacts/fq-combined-top3-v1/final-verified/best_bank.npz`, SHA 006dbc3100df8231c328a1da6d441bfea55e771ed9cba5964ca3e155deb01deb. One invalid optimizer JSON was rejected; all nine trial outcomes are recorded.
- Exact-pair composition improved n599 to side 24.927051943854192, gaining 0.000203786603324 over the v28 ancestor. Controlled substitution proved the old 7x20+14 donor gives the SAME certified side: the win depends on the improved 4x16+9 donor and expanded pair eligibility, not insertion-created boundary diversity. Attribution corrected in research/fq_insertion_campaign.md and frozen ablation report. Expanded insertion/deletion retained 29 valid donors across 17 types; no claim of new mathematical records.
- Local strong-aspect continuation completed 575 trials in 589.46 seconds, retaining 846 certified final/intermediate poses. Frozen best bank `artifacts/fq-local-soft-v1/all-strict/best_bank.npz`, SHA 9443c4cb997cefd81f4b5f73ec52f2a38a54eaf851865dcfdbdf7c5d9bc4e1d8. Main gains: 20x9+13 by 0.007882171, 7x19+12 by 0.001483748, and 20x8+12 by 0.000548902. These component improvements require composition before counting as full-score gains. Anchor now owns a new targeted two-CPU, 900-second continuation.
- Exact translated-square-window sweep tested 219,794 queries across 2,110 sources in 130.60 seconds. Its n807 gain was narrowly dominated by fine GPU composition. A distinct scan of 175 complete public witnesses (n1057..4979) completed 19,600 coarse queries in 77.70 seconds without improvement; remaining untested counts are being scanned under the same 600-second total allocation. Every emitted subset must pass independent interval, official raw, and ordinary-pandas checks.
- All 1,243 higher-n donor crops are independently interval-certified and remotely reconstructed under exact hashes. Private source `sos54352/squares-all-highn-9e136197ddaf/1`; bank SHA c602beaf773cd463535a7519b90d14acea687267a5e1a199f32aa16479c51ed4. No new higher-n donor appeared in selected fine winning recipes; this is not a controlled ablation.
- Active ownership: notebook_frontier merges latest fullcases then prepares one refreshed composition notebook; competition_research prepares a distinct targeted FTMC notebook; anchor has two CPU workers; validation has one for targeted fullcase contact polish; full_puzzle_pilot has one window worker. Local total must remain at most five workers. New GPU pushes require server `-t` and local hard bounds. GPU quota is 30 hours, not six: use timedelta.total_seconds(), never the SDK's day-dropping `.to_dict()` representation. Last durable portable export is candidate-9c8cccde95fe; root is preparing a newer one.
- All 138 tests passed in 5.132 seconds at this checkpoint. Git push uses `git push origin HEAD:main`. Preserve frozen inputs and immutable private notebook slugs; attachment version suffixes do not pin output bytes.
- Environment install/start draft is saved and tested, with Python 3.12, pinned CPU stack, Rust 1.99.1 and portable FQ controls. Publication remains user-side. Paperspace FREE-only access remains blocked by explicit nonretryable Cloudflare 1010; do not repeat or spoof. Credentials stay protected and untracked.

### Subsequent verified checkpoint — 08:05 UTC

The n702/n813 merge is complete: **22.301742653369043**, identical safe and pandas-roundtrip score, zero invalid cases, two fresh official checks and 998 exact reuses. Safe SHA 8cd7c023ab18b5875fcd5084e23415eda3181df1f4e70b5558bfe9eb039b0658; raw SHA be22cb064c823a843d44b6734d78b5101cad7d7c3d27d97168845454e124e721. Canonical summary `artifacts/submission-fq-full-basin-v1-safe.transport-validation.json`, SHA 1072cfe3877df76345369bf2e0f2c3533870df7c15fe2186b7748f2d73de1a74. Unique private CPU source `sos54352/squares-portfolio-8cd7c023ab18/1` is COMPLETE and remotely hash-verified. Portable recipe and all v28 source notices are tracked in `portfolios/candidate-8cd7c023ab18/`. No competition submission.

Native FQ malformed reports/coordinates now produce rejected trial records; an unexpected worker exception no longer loses other completed certified results. Three integration tests include a real subprocess campaign with one failed worker and one independently certified surviving pose. Existing trial API and search parameters are unchanged.

Full-witness translated-window search is complete: 169,575 threshold queries across 175 public complete poses, all non-perfect target counts n=2..1000 covered, no feasible improvements. Search time 392.55 seconds plus 10.27 seconds preparation. This rules out only fixed axis-oriented windows; it does not establish a global packing bound. A distinct complete-puzzle localized soft-shape control is being prepared before further allocation.

## User instructions

- Commit and push at useful validated checkpoints. Git branch `work` tracks `origin/main`; use `git push origin HEAD:main` explicitly. Remote is sosudo/squares_in_squares.
- No submissions until both safe and numeric-roundtrip validated scores are strictly below22.3. Then submit at most hourly, only on strict improvement, within ten per UTC day.
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
