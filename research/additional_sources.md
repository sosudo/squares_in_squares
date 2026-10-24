# Additional public source scan — 2026-10-24 UTC

This scan used only public, unauthenticated Kaggle APIs and public GitHub pages. It did not inspect private notebooks, submit predictions, or contact competitors.

## New retained source

[Dariush Afshar, Squares in Squares: Exact Validator, Record Merge](https://www.kaggle.com/code/dariushafshar/squares-in-squares-exact-validator-record-merge) has no linked leaderboard score in the public notebook catalogue. Its released `submission.csv` nevertheless supplied 29 improvements over `merged-v2.csv`, estimated gain 0.00160448763. A score-sorted scan that stops at linked public scores would miss it.

Its attached [Certified Packings dataset, version 11](https://www.kaggle.com/datasets/dariushafshar/squares-in-squares-certified-packings/versions/11), published 2026-10-24 03:28 UTC, contains a stronger `constructions_v1.csv`. That file supplies 31 improvements over `merged-v2.csv`, estimated gain 0.00160508863, including tiny additional gains over the notebook output. These are whole puzzle layouts; coordinate rows from different layouts are never mixed.

Pinned input files and provenance:

- `artifacts/additional-public/dariushafshar__squares-in-squares-exact-validator-record-merge.csv` and its `.source.json`.
- `artifacts/additional-dataset-v11/packings_v1/dariushafshar__squares-in-squares-certified-packings.csv` and its `.source.json`.
- `artifacts/additional-dataset-v11/constructions_v1/dariushafshar__squares-in-squares-certified-packings.csv` and its `.source.json`.
- Constructions CSV SHA-256: `a542b6a8c97922b0e923d59d96870fa10123fae47c9279a6eec096a7c5971786`.

Dataset metadata identifies the compilation as **CC BY 4.0**. Original source credits and license statements are preserved verbatim under `vendor/notices/dariush-v11/`. Credit belongs to Dariush Afshar and the inherited mathematical discoverers and public notebook authors named there. This project claims its own merge/validation code, not those discoveries.

## Catalogue coverage

The public competition catalogue returned 40 notebooks. Three did not advertise output files. Five notebook references by kmmmvs, cdeotte and lightningv08 were already handled by the main public-frontier investigation. Of the remaining 32, this scan successfully downloaded 25 standard `submission.csv` outputs; seven returned 404 for that filename. The catalogue and successful download hashes are retained in `artifacts/additional-public/kernel_catalogue.json`, `download_scan.json`, and individual `.source.json` files.

All 25 CSVs were screened against `merged-v2.csv`. Only Dariush's file supplied plausible improvements. The Avikdas source has an apparent n=51 gain with side approximately 5.333, below the area lower bound sqrt(51), so that layout cannot be valid and must not be used. The other downloaded sources supplied no improvements beyond the existing merge. Detailed case lists are in `artifacts/additional-public/screening_report.json`.

The failed conventional filenames were inspected through released notebook source where useful. Kyle Luecke's latest notebook publishes a proof/commitment audit rather than packing coordinates. Robina Mirbahar's released notebook is an explanatory write-up. The mpwolke notebook is introductory. The yangkuangou notebooks describe ablation/workbench workflows; no standard public output CSV was available at the checked paths. This is an unavailable-output observation, not a claim about their private work or unpublished results.

## Top team release check

The first 15 teams' public member profiles were checked for published square-packing notebooks. None supplied a relevant public notebook. The top team's leader is `umongsain`; the second team's public members are `angran` and `kaixuanosmas`. Their public dataset lists contain no square-packing coordinates. The linked GitHub profiles `Umong51` and `angranzhang` have no public square-packing repository visible in their current repository lists.

No released coordinates matching the leaderboard leader's 22.2247581510 score were found. No inference about private solutions is made.

A newly published GitHub project, [chaydavs/squares-in-squares](https://github.com/chaydavs/squares-in-squares) at `b8a1c8e41524cac474a3444f2bc943c682d9e2f5`, reports a 22.3499485521 public frontier plus LP sweep. Its notes are useful research context but do not beat the current merged score, and its LP portfolio output is not tracked in the visible repository.

## Public APIs used

- POST `https://www.kaggle.com/api/i/kernels.KernelsService/ListKernels` with `{"kernelFilterCriteria":{"listRequest":{"competitionId":166661,"pageSize":100,"sortBy":"SCORE_ASCENDING"}}}`.
- The same endpoint's public profile filter: listRequest with `userId`, `group:"PROFILE"`, and `pageSize:100`.
- POST `https://www.kaggle.com/api/i/users.ProfileService/GetProfile` with `{"userName":"..."}`.
- GET `https://www.kaggle.com/api/v1/datasets/list?user=...&pageSize=100`.
- GET public notebook source at `https://www.kaggle.com/api/v1/kernels/pull/OWNER/SLUG`.
- GET public outputs at `https://www.kaggle.com/api/v1/kernels/output/download/OWNER/SLUG/submission.csv`.
- GET pinned dataset files at `https://www.kaggle.com/api/v1/datasets/download/OWNER/SLUG/FILE?datasetVersionNumber=11`.

Latest notebook source and latest scored output can differ. Dataset file downloads must pin the version explicitly; unversioned downloads were observed elsewhere in this investigation to return older releases. Signed redirect URLs are not retained in download provenance.

## Certified outcome

The notebook output was retained in immutable `merged-v4.csv` by the main agent. The stronger dataset constructions were then merged into immutable `merged-v5.csv` using `scripts/merge_candidates.py` with the SHA-matched v4 independent report. All 31 replacements passed the independent interval verifier; no candidates were rejected.

The unchanged official v17 metric independently evaluated the 31 changed puzzles and reused the exact unchanged 969 puzzles from the hash-verified v4 official report. Result: **22.304939813270671**, zero invalid puzzles out of 1,000, 500,500 rows. Improvement over v4: **0.00000060075502617**. CSV SHA-256: `c2525393dc70e91f6b1f7957562f8fb9ff022c14afee526b07086d0a57b7da15`.

Reports: `artifacts/merged-v5.validation.json`, `artifacts/merged-v5-official.json`, and `artifacts/merged-v5-official-details.csv`. This is local certification, not a Kaggle submission or ranking claim.
