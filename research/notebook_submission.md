# Submitting an ordinary CSV competition from a private notebook

Verified against Kaggle's live frontend and installed official SDK on 2026-10-24.

## Conclusion

Squares in Squares supports the normal notebook-output submission flow. The
competition does **not** need to be restricted to notebook submissions.

An unauthenticated, read-only POST to
`https://www.kaggle.com/api/i/competitions.CompetitionService/GetCompetition`
with `{"competitionId":166661}` returned `hasScripts:true`. The fields
`onlyAllowKernelSubmissions` and `usesSynchronousReruns` are omitted; the official
frontend defaults both to false. The response also specifies ten submissions
per day and a 20,480 MB submission size limit. That is the output-file limit,
not evidence of the maximum notebook source size.

The official submission dialog disables its Notebook tab only when
`!competition.hasScripts`. It disables File Upload only when
`competition.onlyAllowKernelSubmissions`. Its notebook selector searches the
current user's notebooks with `privacy:"all"`, then selects a saved version
with a run and an output filename. Private notebooks are included.

## Supported public API / CLI

The frontend itself shows this CLI command for its Notebook tab:

```sh
kaggle competitions submit -c squares-in-squares \
  -k OWNER/NOTEBOOK -v SAVED_VERSION_NUMBER \
  -f submission.csv -m 'Validated packing submission'
```

In the official Python client this calls `competition_submit_code()`, then
`CompetitionApiService.CreateCodeSubmission`. Request fields are:

```json
{
  "competitionName": "squares-in-squares",
  "kernelOwner": "OWNER",
  "kernelSlug": "NOTEBOOK",
  "kernelVersion": 1,
  "fileName": "submission.csv",
  "submissionDescription": "Validated packing submission"
}
```

The request's REST route is:

`POST /api/v1/competitions/submissions/submit-notebook/squares-in-squares`

The SDK handles ordinary Kaggle API authentication. This route selects an
existing notebook output; it does not upload a local CSV. Use the actual saved
notebook version number and exact output filename, and retain the notebook as
private. A completed run with the expected, hash-checked output is the prudent
prerequisite. The CLI documentation calls these “code competitions,” but the
live generic submission dialog generates that same CLI command for Notebook
submissions to ordinary competitions.

## Frontend service (reference only)

The normal website uses:

`POST /api/i/competitions.SubmissionService/CreateSubmission`

with:

```json
{
  "competitionId": 166661,
  "description": "Validated packing submission",
  "sandbox": false,
  "kernelSource": {
    "kernelRunId": 123,
    "fileName": "submission.csv",
    "skipOutputFileCheck": false
  }
}
```

The read-only eligibility check is
`POST /api/i/competitions.SubmissionService/CanSubmit`, passing that request in
`{"createRequest": ...}`. It returns `canSubmit`, `notAllowedReasons`, and
submission-limit information. The website creation call also obtains its
normal anti-abuse token. Prefer the supported public API/CLI above rather than
attempting to reproduce browser authentication or bypass anti-abuse checks.

Competition membership/rules acceptance, remaining submission quota, eligible
notebook ownership/access, and a valid output still apply. This research used
only public frontend assets and read-only competition metadata, without reading
credentials or attempting a submission.

## Evidence

- Live official app bundle:
  `https://www.kaggle.com/static/assets/app.js?v=8108a631c84a5d96`
- Live submission-dialog bundle (module 38027):
  `https://www.kaggle.com/static/assets/224.2f1f4535d16bd011.js`
- Public official CLI documentation:
  `https://github.com/Kaggle/kaggle-cli/blob/main/docs/competitions.md#kaggle-competitions-submit`
- Installed official implementation:
  `.venv/lib/python3.12/site-packages/kaggle/api/kaggle_api_extended.py`,
  `competition_submit_code` and `competition_submit_cli`.
- Installed request schema:
  `.venv/lib/python3.12/site-packages/kagglesdk/competitions/types/competition_api_service.py`,
  `ApiCreateCodeSubmissionRequest`.
- Public source responses retained under `/tmp/kaggle-submission-research/`.


## Bounded sessions and recovery (2026-10-24)

Pass an explicit server limit to every private job: `kernels push -p JOB -t SECONDS`. The supported CLI maps this to `ApiSaveKernelRequest.session_timeout_seconds`. Keep the local child/process-group watchdog too. A stale earlier job blocked the two-session GPU limit despite its script-level cap; cancelling that exact job restored productive execution.

When status metadata omits the execution ID, a supported `ApiDownloadKernelOutputRequest` for the exact owner, slug and version, without a file path, can return `/api/v1/kernels/output/download_zip/ID`. The official SDK names this parameter `kernel_session_id` in `ApiDownloadKernelOutputZipRequest`, matching `ApiCancelKernelSessionRequest`. Verify this namespace and exact owner/version binding before cancelling. Notebook IDs and saved-version labels are different identifiers and must never be guessed as session IDs. Cancelling a session preserves its notebook/history. The observed stale session361697299 went fromRUNNING toCANCEL_REQUESTED toCANCEL_ACKNOWLEDGED.

SDK duration serialization has a separate trap: its `to_dict()` uses `timedelta.seconds`, dropping whole days. The108000-second/30-hour GPU allowance appeared as21600seconds. Use the duration’s `.total_seconds()` or the raw official `/api/v1/kernels/quota` response. Reserved session maximums are not consumed quota.
