# Current working status

This competition task is ongoing. The user wants the highest possible rank, ideally first place. Continue optimization after compaction; this checkpoint is not a declaration of completion.

## Latest checkpoint — 2026-10-24 07:25 UTC

- No competition submission until BOTH official safe and ordinary numeric-roundtrip scores are strictly below22.3. Controller remains stopped; only two submissions today. Latest accepted57584666 scored22.3047579593.
- **Best fully certified score22.302325582078790**, identical roundtrip,0invalid/1000. Safe `artifacts/submission-composition-f64-v1-safe.csv`, SHA9c8cccde95fe1c6008737247c0f50c8c117037ae5b37e39fcf456b0dd09a6ed4. Raw `artifacts/merged-composition-f64-v1.csv`, SHA994c032b4b7c24b6ff8f4e19ff0a7a6921ecbec437da2a3bc9549b85393ee9f8. Canonical transport summary alongside it;10 fresh+990 exact reuses. Portable869KB source locally reconstructs exact bytes; privateCPU exporter `sos54352/squares-portfolio-9c8cccde95fe/1` is COMPLETE and remotely SHA-verified. Recipe `portfolios/candidate-9c8cccde95fe/`.
- CPU replay v1 certified17 complete-puzzle wins, gain0.000544244, safe22.302494429786211. GPU composition f64v1 then completed all15312 orientations in149.13seconds and added10 strict wins beyond that newer ancestor. Full-puzzle FQ gains remain preserved.
- Exact-SAT CPU replay now tests actual adjacent-block collision geometry instead of separator bins. It completed25.78seconds,11 certified candidate cases, estimated additional gain0.0000983011. None of the selected winning joins was excluded by old bins: these gains demonstrate fresh/different donors, not a proven benefit from broader join compatibility. Full merge/transport checks are underway under competition_research; upcoming raw `merged-cpu-replay-sat-v1.csv`. Future GPU results must merge into the newest certified raw ancestor.
- The stale GPU job was safely cancelled: exact private owner/version download redirect exposed session361697299, official SDK explicitly establishes the session-ID namespace, supported cancellation returned no error and terminal CANCEL_ACKNOWLEDGED. Notebook/history retained. New f64job launched successfully with server timeout1200s. Use `-t` on future pushes in addition to local watchdogs. GPU allowance remains30hours; SDK `.to_dict()` drops days from timedeltas, so use `.total_seconds()`/raw REST. Details in research/notebook_submission.md and artifacts/stale-composition-cancellation/.
- Combined two-T4 FTMC campaign finished successfully in1840.25seconds:26 strict events on FQ-start,43 original-start,4596 certified variants. General-refill budget shares6.27%/5.71% remained below18%. Aggregate SHA204eaa312767cdaf957e708bc8476f4fa5c7eba869e5994cdafd781b4a67d45f. Full_puzzle_pilot owns final aggregate download/analysis against both initial and newest CPU reference banks. Preserve all certified and exploratory geometry regardless of scalar ranking; per-pose snapshots remain remote. No complete-puzzle gain is claimed yet.
- Final multiscale FQ:888.30seconds,695trials,529 certified donors,10 improved types. Snapshot `artifacts/fq-multiscale-v1/snapshot-00099`, bestSHA5d8de5063a8c1c1559dc5a73b0f24c7bd6166609a1cabde99fd7d5ee7f38e0f7. Final focus FQ:888.25seconds,739trials,623 donors; two canonical families gained0.000301429 and0.000121066. Snapshot `artifacts/fq-focus-v1/snapshot-00083`, bestSHA064b4e76c423c8b5617302b52c06ea8fc46b7f13d245550322406e7e36f8573d.
- Soft-square continuation is a distinct active2CPU/600second method: temporary area-preserving aspect changes return exactly to rigid squares before certification. Positive controls and complete8-step epsilon-to-zero traces passed. Frozen downstream snapshot `artifacts/fq-soft-v1/snapshot-00023`, bestSHA02eeffaa5854957c1ce35b408fda01d7ace9d26cd737e72bae55922447f3bff4. Current snapshot may be newer; never change a running job’s frozen input.
- Coherent cluster/band moves completed36trials in39.3seconds,29 certified donors, zero gains above1e-5. Donor bank `artifacts/fq-coherent-v1/donors.npz`, SHA3ac366321c97e1ad6d66eef6d0bf51645a96db5dde0b9ac8d1faddc60d0b679e. Validation now owns a separate N+1 insertion/N-1 interior-deletion repair pilot,1CPU/300seconds, matching new surplus types and requiring f<1 plus all geometry/transport gates.
- The larger high-n bank expands200 selected windows to all1243 retained crops (473930squares). Child exact_candidates completed local reconstruction and interval checks; privateCPU source exporter/proof preparation ongoing. Full official submission checks remain a separate gate. Notebook_frontier owns next GPU bundle: original bins32/angles30,45,60 and finer bins64/angles30,45; include latest frozen banks, all1243 high-n inputs and all4596 combined variants if conservative uint32 identifier bounds pass, exact hash checks and actual-sized preflight. No next GPU launch until root review.
- Full_puzzle_pilot will prepare exact translated-square-window subset search (sweep-line/range-add maximum overlap) to broaden the existing9-centre heuristic. No production allocation yet. Total local active search workers must remain<=5.
- Environment install/start draft is saved and tested (Python3.12, pinned CPU stack, Rust1.99.1, portablefq,11geometry checks and actual5-square optimizer control); future environment publication remains user-side. Paperspace FREE-only access remains blocked by nonretryable Cloudflare1010; do not repeat or spoof. Credentials stay in protected/tmp files and are never committed.
- Last confirmed Git push39e880e; root is committing this checkpoint and stable search sources. Current user goal remains active; no submission or scheduler restart.

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
