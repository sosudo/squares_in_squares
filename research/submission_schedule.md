# Conservative hourly submission controller

`./.venv/bin/python scripts/submission_scheduler.py` defaults to a read-only Kaggle **check**. No system timer or cron job is installed. An explicit `check --execute` may create at most one submission; root enabled periodic execution in this environment on 2026-10-24 at 05:28 UTC.

The baseline was adopted from live Kaggle history: submission **57583210**, accepted **2026-10-24 05:06:59.167 UTC**, completed public score **22.3048038109**, exact validated score **22.30480381099813**. The earliest next accepted submission is **2026-10-24 06:06:59.167 UTC**, and only a new strictly better validated candidate may qualify. The adopted baseline itself can never be resubmitted by this controller.

Local state is `artifacts/submissions/scheduler-state.json`; queue entries are in `artifacts/submissions/queue.json`; accepted receipts are retained under `scheduler-receipts/`. Enqueueing copies all CSVs and reports into read-only, content-addressed `queue-artifacts/` snapshots, so reusing an experiment filename does not change a queued candidate.

Every queue entry binds a completed private notebook reference, immutable version and output filename to the exact local CSV SHA256. Raw official v17 validation, the actual pandas numeric-roundtrip CSV and its official validation, and their transport-summary hashes must agree. Enqueueing verifies the remote completed-version output hash. Execution repeats that read-only check, then refreshes live submission history and quota immediately before requesting scoring through the official notebook-output submission API.

The decision requires a strictly lower validated score, a new CSV hash, no pending scoring or unresolved ambiguous request, at least 3600 seconds since the latest accepted submission, positive live allowance and fewer than ten submissions that UTC day. All completed public scores remain in the strict improvement bound, including tracked references; a one-display-unit margin avoids spending quota on displayed ties. Unexpected Kaggle/local score disagreement blocks further work for review.

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

Seventeen tests cover immutable binding/snapshot protection, numeric validation linkage, strict score improvement, pending submissions, exact hourly boundaries, live and hard daily limits, dry-run behavior, duplicates, acknowledged submission intent, lost acknowledgments, unresolved ambiguity, score mismatch, and adoption guards that cannot erase an unresolved intent. Live read-only integration verified the adopted private notebook's immutable output hash and returned the expected cooldown without submitting anything.

## Bounded periodic runner

`run_submission_loop.py` is disabled by default. Root can explicitly enable a 12-hour run:

```bash
.venv/bin/python scripts/run_submission_loop.py --enable-submissions --hours 12 --cadence 60 --timeout 600
```

The runner holds an exclusive lock, checks once per minute, and gives each controller invocation at most 600 seconds. The controller still enforces a full hour between accepted submissions, strictly better validated/public scores, no duplicates and the live daily allowance. SIGTERM or Ctrl-C stops the runner and its owned controller process group cleanly. It does not install a system service.

At startup and after a controller timeout, the runner invokes `check --reconcile-only`. That mode only reads Kaggle history and persists verified reconciliation/receipts; it cannot create a submission. Timeouts never delete an unresolved intent. If the total runtime expires before reconciliation can finish, the saved intent remains available for the next explicit run.

Terse scalar outcomes are saved in `artifacts/submissions/runner-status.json` and appended to `runner-events.jsonl`. Subprocess stderr, arbitrary error text, credentials and signed URLs are excluded. The runner's continued operation depends on the cloud machine and process remaining alive; task completion, restart or disconnection may require an explicit restart.

There are now 25 targeted controller/runner tests. The added tests cover duplicate-runner exclusion, correct execution/reconciliation flags, real subprocess timeout cleanup, persisted intent after timeout, disabled default behavior and filtering of sensitive subprocess output. Transport summaries can truthfully report complete cached coverage, such as 986 reused plus 14 freshly evaluated cases, with exact report hashes and score agreement within 1e-10; bit-identical floating-point totals are not required.


Current-instance activation: root started runner PID 15213 at approximately 2026-10-24 05:28 UTC with the 12-hour bound, 60-second cadence and 600-second timeout. Startup reconciliation succeeded; the first tick observed no pending intent and waited until the baseline cooldown ends at 06:06:59.167 UTC. This records the observed current process, not a guarantee of survival after a task or machine restart.
