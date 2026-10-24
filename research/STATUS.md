# Current working status

This competition task is ongoing. The user wants the highest possible rank, ideally first place. Continue optimization after compaction; this checkpoint is not a declaration of completion.

## Latest checkpoint — 2026-10-24 09:17 UTC

- Competition objective remains active. **No submission until BOTH safe and ordinary pandas-roundtrip scores are strictly below 22.3.** The hourly runner remains stopped. Two submissions today; latest accepted57584666 scored22.3047579593. After crossing the gate require strict improvement, at least3600seconds since last acceptance and the daily limit.
- **Best fully certified SAFE score22.301105561453781; ordinary pandas-roundtrip22.301105561453785**, zero invalid cases. Authoritative atomic pointer: `artifacts/current-best-portfolio.json`. Safe CSV `artifacts/submission-omitted-donor-pair-v1-safe.csv`, SHA63e1b93cda7517e64341d11fa73aadf5c55e5d7d6d4a0f230a5fc3b8a9deef7d. Raw `artifacts/merged-omitted-donor-pair-v1.csv`, SHAb9374e881450748a04a86e39b84c69ba8607ceb1e95a303caeb93f38d9174354. Canonical proof SHA611974f01413d9829e46be02b90a41c9e30a87170e0762ca2f3ec788827f19b9. Latest merge adds n798 with1 fresh/999 exact certificate reuses, preserving all preceding gains. Gap to threshold0.00110556146.
- **Durable exact recipe `portfolios/candidate-63e1b93cda75/` is remotely verified** at09:16:17. Private `sos54352/squares-portfolio-63e1b93cda75-incremental/1` COMPLETE, output SHA matches. Source495603bytes, SHA162b9c9e09545e4653933e2e2eb51e94646b7b4a66c5d928be5a251579966c6d. It patches SAFE row bytes over immutable `squares-portfolio-8cd7c023ab18/1`; applies no further scaling. Keep parent unchanged. The b715 incremental predecessor is also COMPLETE/hash-verified in artifacts.
- Recent gains: five scalar-DP cases improved5cba by0.00005394847; completed7276-donor GPU composition added14 actual admissions and0.00021969475, mostly n748/n993/n992; historical donor recovery added n798 by0.00004854596. The n798 geometry has slightly worse scalar excess yet passes an interface where all64 D4 pairings of the competing lower-excess poses fail. Preserve geometry diversity. See research/composition.md and donor_retention_audit.md.
- Frontier is building a different GPU composition partition: full846 local-soft plus666 bottleneck variants,26 newly polished night minima, original27 omitted geometries, original51 active variants and current whole-case winners. All1512 full-bank arrays were reconstructed through six private CPU parts and remotely byte-verified; all part jobs COMPLETE. A QUEUED-state monitoring bug temporarily admitted four parts concurrently; it is fixed. Kaggle rejected extra pushes at five CPU sessions; no rejected resource launched. CPU consolidation into one attachment precedes the bounded32-bin GPU run (worker1200/server1500). No silent donor truncation.
- Targeted two-T4 FTMC `sos54352/squares-targeted-ftmc-n65-v1/1` is COMPLETE as of09:16:41. Final outputs are being collected by the existing bounded monitor, PID54208/session18161, deadline10:00:40UTC. At2700seconds both arms reported zero accepted strict minima despite246982/595515 core trials and69888/15728 full quenches. Do not extend unchanged. Exact source0aa0b1177774e46d2349520530cfc0757a40b73f2b129c1f504b284d40910e9b; actual256-core/reject257 and194/244-square CUDA controls passed. Per-key wall time is not instrumented:45%/40% n65 sampling is not measured compute share.
- GPU quota is30hours/108000seconds, NOT6hours. Use raw REST or timedelta.total_seconds(); to_dict()/timedelta.seconds drops days. Paid scaling disabled. The earlier stale composition session361728678 was precisely identified, checked with nested SSE and cancelled08:48; the corrected single-attachment composition completed226seconds and produced the14 current gains.
- Four-core private CPU FQ readiness is proven: portable binary SHA10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d; native n5/n65 execution and raw/default-pandas/interval controls passed. Kaggle CPU runtime4cores/30GiB/GLIBC2.39; no NVIDIA. One remote CPU search `sos54352/squares-fq-cpu-complementary-v1/1` is actually RUNNING: four workers on complementary families5x18+11,20x8+12,6x22+16,10x23+14,1140search/1200whole/server1500. Guaranteed25% immutable starts; retain all certified outside-band poses. No gain yet in early logs. Owner full_puzzle_pilot.
- Productive local40-free/.6 rectangle campaign completed588.76seconds/487 trials,175 primary outputs/336 distinct certified outputs,120 immutable starts including73 older basins. Only new component gain9x22+16 by0.00002049031 to f0.936415017681;7x21+15 unchanged. Final341-pose handoff `artifacts/fq-productive-final-handoff-v1/`, referenceSHA9f7667ad3c23f0c5c5a574dd0df1b07a21394201468458dc2e92226e20ca9b7b, donorsSHAaba7b09155a1e97331ff8598f5bcee583fdc66ec2bd2c294e3608f1e784687ac. Both local CPUs released. Matched release control disproved the claim that LP20 alone caused the7x21 plateau; see fq_variant_campaign.md.
- Newly recovered night seed FQ pilot completed205trials/293.16seconds:148 strictly certified geometries,21/26 types improved. Largest component reductions0.03976/0.03971/0.03948, but no full-score gain demonstrated. Exact final handoff `artifacts/fq-night-seeds-v1/final/`, bestSHAc7aa8ca0de7528a774c2113fdc348818ba08a3ef6a368fe5d3b65cf3c03a839b. Final status write originally exited1 from a checkpoint-name collision; all205 records/banks survived, finalizer verified them, naming bug fixed with3 tests. Preserve honest original exit.
- Night finite scalar-DP and direct pair screens total24.49seconds, zero full gains. Direct palette52 oriented new types/208 poses by1391 types/12768 partner options screened433992 type/order/modes and919672 containers;12 scalar-promising jobs all failed exact SAT. Positive controls passed. Exact rectangle-window sweep also retained4 valid scalar-dominated donors and yielded no subsequent full gain. These negative results are documented rather than repeated.
- Next local directions under review: anchor considers full-case structural changes and stronger basin moves (up to2CPU); validation examines materially different multiblock/interface constructions (up to1CPU); exact_candidates reviews frozen frontier GPU payload independently. No heavy work launched before a concrete hypothesis. Local active search workers remain<=5. Root handles canonical proofs, durable exports and checkpoint pushes.
- Public metadata last refreshed08:23:32: maximum Ready versions KMMM28, Cdeotte2, Dariush11, Lightning18 unchanged. Existing large-library CUDA fix widens before multiplication at all4 sites, enforces unsigned32-bit bounds and real IDs35471/60000 controls. Unique immutable notebook slugs plus exact runtime hashes are mandatory; attachment /1 suffix does not pin bytes.
- All182 regression tests passed in12.685seconds at this checkpoint.
- Environment setup remains tested and reusable install/start draft saved; future publication is user-side and current work is unblocked. Paperspace FREE-only API remains explicit nonretryable Cloudflare1010 denial, no spoof/retry/paid resource. Credentials stay protected outside Git. Use `git push origin HEAD:main` at validated checkpoints.

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
