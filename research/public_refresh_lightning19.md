# Lightning Layout Atlas v19 refresh

The actual v19 release contributes ten independently certified case
improvements over raw portfolio `a0dad731…`, for a combined raw score gain of
`0.00000020392094701726649`. The candidates are n546,547,594,595,645,697,751,
797,979 and984. The largest contribution is n979, `1.737137929e-7`.
The predicted merged raw score is22.300815957988586. Full merged transport
certification and the canonical pointer remain root-owned; this investigation
did not merge, submit or change the current portfolio.

## Explicit version and filename matter

The public dataset is
`lightningv08/squares-in-squares-layout-atlas`. Its explicit version19 entry
was Ready at2026-10-24T12:57:40.833Z, with release note “Certified iterative
CUDA recomposition22.307818650783”. The convenience current-version field
still said18. Discovery uses the newest explicit Ready version, not that
stale convenience field.

The version19 `submission.csv` is byte-identical to the pinned version18
file: SHA256 `415710776a1752c4af158827a961d71277bd36aa54b4f0ec41c432fed9f44eb4`.
It contains543 complete case groups /288,417 rows and belongs to an older
22.591925842995 release. All supplied cases were compared; none improved
the incumbent. No geometry certificates were repeated for those unchanged
public bytes. `legacy-csv-equality.json` records the old/new byte equality
and exact versioned download provenance.

The complete version19 inventory has153 files in two pages. Its README's
last section explicitly identifies **`refresh_submission.csv`** as the new
result, and pins SHA256
`51c384deb6230641b521c87b362ec2ea83de2d7f7065f6f880a460d355ce44a9`.
The downloaded bytes match that hash and the release manifest and summary.
This file supplies547 complete case groups /290,670 rows; the other453
incumbent cases have no proposal and remain unchanged. No omitted grid
packing was invented or credited to this source.

Version-pinned downloads used the existing helper:

```bash
.venv/bin/python scripts/fetch_public.py \
  lightningv08/squares-in-squares-layout-atlas \
  --kind dataset --version 19 --filename refresh_submission.csv \
  --output artifacts/public-lightning19/refresh --workers 1
```

`fetch_public.py` names the local CSV after the dataset; the companion
`.source.json` records the actual remote filename, explicit version, URL,
byte count, retrieval time and SHA. Signed redirect URLs are not retained.

## Changed-case validation

`experiments/screen_public_portfolio_update.py` verifies the baseline CSV,
independent report and official report against the atomic current-portfolio
pointer, then preserves all source decimal strings. It checks the supplied
case IDs/counts, uses a conservative floating side screen and requires a
strict separation of exact interval side bounds before selecting a case.
Only the ten selected cases receive fresh independent/raw official checks
and an ordinary default-pandas write/read audit with both independent and
official checks. All forty changed-case evaluations passed; zero cases were
rejected. Unchanged case certificates were not rerun.

The thirteen-second serial run is retained under
`artifacts/public-lightning19/refresh-screen-v1/`. Exact candidate JSON:

```
winning-candidates.json
SHA256 5260b15091b57444d1e44bc98c445e2c9b2752b2155c8ced8d3b5ae995fb22ee
```

`certification-summary.json`, `independent-certificates.json` and
`official-winning-cases.json` bind the unchanged official v17 metric, source
CSV, baseline reports, raw/roundtrip row hashes and exact contribution gains.
The raw candidate audit CSV has SHA256
`5d336b966bffa80f4646e35a3393633c0cf14d5c3d9ab8bc567d261a5a2c8d4b`.
The separately generated ordinary-pandas audit copy has SHA256
`5fc63eebb9dfaabf997ed003d44b3efa59be8cb24aa7aacaa34ea064f865d3a9`.

## Source credit and scope

Exact version19 metadata, README, file inventory, release manifest/summary,
validation record and relevant current/inherited source notices are retained
under `artifacts/public-lightning19/notices/`. The dataset's CC0 declaration
applies to its numerical facts and metadata. It does not relicense linked
third-party notebooks, code, prose or artwork; inherited author and license
notices remain applicable.

The publisher explicitly distinguishes credited public adoption from later
CUDA recomposition. Its first composition stage records nine of our ten
winning cases; its second stage records n547,595,645,697,751 and797. Those
stage records are source lineage, not an attribution of all mathematical
content to the CUDA implementation. The complete `refresh_SOURCE_NOTICES.md`
and `refresh_sungheo_NOTICES.md` retain lightningv08, Chris Deotte, Sung Heo,
Alex Chilton, Malyshev Danil, Evan Daniel, Francisco Couzo, David Ellsworth,
Erich Friedman and the inherited mathematical/software contributors.
Original notice bytes match the publisher's own release-manifest hashes.

The durable attribution subset is also tracked at
`vendor/notices/lightning-v19/`. Its `source-manifest.json` SHA256 is
`38ca05444092b50b50dcfdeba1e565e330f1ba12dc49b1e66b5eb86b6dcc5989`;
the ten-case explicit stage-lineage proof SHA256 is
`995ad5247129db771c0bf0c5b00068c033322f47c9314dad42ca088782a52c8a`.

No older NPZ archive was downloaded merely because its filename contained
“release”. The README and exact manifest resolved the actual new CSV first.
No additional public search, composition, GPU job or submission was run.
