# Current working status

This competition task is ongoing. The user wants the highest possible rank, ideally first place. Continue optimization after compaction; this checkpoint is not a declaration of completion.

## User instructions

- Commit and push at useful validated checkpoints. Git branch `work` tracks `origin/main`; use `git push origin HEAD:main` explicitly. Remote is sosudo/squares_in_squares.
- Check hourly and submit only a strictly improved validated candidate, within Kaggle's ten submissions per UTC day.
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
- A new raw GPU+CPU candidate is being certified by validation agent; score about22.304803774638591 before transport clearance. Keep it separate from submitted files and queue only after both checks.
- notebook_frontier exported51 ACTUAL current-frontier crops and partner thresholds under artifacts/active-frontier. packing_research is redesigning a900s/device dual-T4 pilot from these active families, with explicit priority and no historical scalar-bloat overwrite of compatible active poses. Not launched yet.
- Versioned kernel_sources can mount our completed private baseline export/2 and FTMC pilot/1, keeping new jobs offline and well below1MB. Verify mounted hashes.
- Last observed GPU quota:0.23h used,29.77h remaining. Read quota again for exact current use.

## Scheduler

competition_research is finishing scripts/submission_scheduler.py with conservative tests. Default is check-only. It verifies queue/report/output hashes, live quota, full history, strict improvement, no pending/ambiguous scoring, and3600s since acceptance. It persists intent before submission and reconciles lost acknowledgements by a SHA marker. No daemon or automatic submission has been enabled yet. Local queue/state already adopted57583210. Root should review and enable only after tests and exact queue binding are complete.

## Credentials and Paperspace

Never print credentials, environment dumps, or signed URLs. Kaggle wrapper scripts/kaggle_cli.py reads a runtime binding or protected /tmp/squares-kaggle-auth/token. Paperspace fallback is /tmp/squares-paperspace-auth/token. SSH private key is /workspace/.ssh/paperspace_squares_ed25519; the public key was provided to the user.

Paperspace API domains now respond with Cloudflare Error1010 browser_signature_banned, explicitly nonretryable and requiring site-owner action. This happens before credential authentication. Free availability/private notebook support remain unknown; no resources were created. scripts/paperspace_access.py stops on the denial. Do not spoof a browser or repeat unchanged denied requests. Continue using Kaggle.

## Reproduction references

research/public_frontier.md, additional_sources.md, decimal_transport.md, composition.md and notebook_submission.md describe evidence and exact sources. vendor contains attributed MIT Shubin baseline and Apache Lightning v21 solver plus inherited dataset notices. Artifacts are ignored by Git but retained; submitted reproducible recipes are tracked under portfolios/.
