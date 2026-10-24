# Conservative hourly submission controller

`./.venv/bin/python scripts/submission_scheduler.py` defaults to a read-only Kaggle **check**. No daemon, timer, or cron job is installed or started. An explicit `check --execute` may create at most one submission; root has not enabled that mode yet.

The baseline was adopted from live Kaggle history: submission **57583210**, accepted **2026-10-24 05:06:59.167 UTC**, completed public score **22.3048038109**, exact validated score **22.30480381099813**. The earliest next accepted submission is **2026-10-24 06:06:59.167 UTC**, and only a new strictly better validated candidate may qualify. The adopted baseline itself can never be resubmitted by this controller.

Local state is `artifacts/submissions/scheduler-state.json`; queue entries are in `artifacts/submissions/queue.json`; accepted receipts are retained under `scheduler-receipts/`. Enqueueing copies all CSVs and reports into read-only, content-addressed `queue-artifacts/` snapshots, so reusing an experiment filename does not change a queued candidate.

Every queue entry binds a completed private notebook reference, immutable version and output filename to the exact local CSV SHA256. Raw official v17 validation, the actual pandas numeric-roundtrip CSV and its official validation, and their transport-summary hashes must agree. Enqueueing verifies the remote completed-version output hash. Execution repeats that read-only check, then refreshes live submission history and quota immediately before requesting scoring through the official notebook-output submission API.

The decision requires a strictly lower validated score, a new CSV hash, no pending scoring or unresolved ambiguous request, at least 3600 seconds since the latest accepted submission, positive live allowance and fewer than ten submissions that UTC day. Unknown displayed-only scores receive a conservative one-display-unit margin. Unexpected Kaggle/local score disagreement blocks further work for review.

Before a submission request, an atomic pending intent records its unique full-SHA marker. A lost response triggers a fresh submission-history read. A matching marker resolves the receipt; absence remains ambiguous and **never causes an automatic retry**. Later checks reconcile history again. An operator must review unresolved ambiguity before clearing or otherwise changing its state.

To enqueue a future completed, validated output:

```bash
.venv/bin/python scripts/submission_scheduler.py enqueue \
  --csv artifacts/improved-safe.csv \
  --raw-report artifacts/improved-safe-official.json \
  --roundtrip-csv artifacts/improved-safe-roundtrip.csv \
  --roundtrip-report artifacts/improved-safe-roundtrip-official.json \
  --transport-report artifacts/improved-safe.transport-validation.json \
  --notebook OWNER/PRIVATE-NOTEBOOK --version SAVED_VERSION --output-file submission.csv
.venv/bin/python scripts/submission_scheduler.py check
```

After root review, an external periodic runner can invoke the same one-shot `check --execute`. It remains the runner's responsibility to stay alive; this implementation makes no claim that a background process will survive a task ending or a machine restart.

Fourteen tests cover immutable binding/snapshot protection, numeric validation linkage, strict score improvement, pending submissions, exact hourly boundaries, live and hard daily limits, dry-run behavior, duplicates, acknowledged submission intent, lost acknowledgments, unresolved ambiguity, and score mismatch. Live read-only integration verified the adopted private notebook's immutable output hash and returned the expected cooldown without submitting anything.
