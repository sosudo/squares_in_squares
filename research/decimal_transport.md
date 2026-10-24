# Decimal transport audit

Audited immutable `artifacts/merged-v7.csv` before the first submission.

The published official metric v17 accepts plain decimal coordinates with
arbitrary precision, then measures sides from decimal strings. However, its
entry point receives a pandas DataFrame and serializes it with `to_csv()` before
parsing those strings. The backend's preceding DataFrame loader is outside the
published notebook. Consequently, the metric's support for long decimals alone
does not prove that the upload transport preserves them.

Francisco Couzo's public `KAGGLE.md` documents 100-digit arithmetic, 75-digit
exported coordinates and angles, and centre dilation by `1 + 1e-40`. It reports
local metric validation and explicitly distinguishes that from Kaggle's eventual
uploaded-file score. It does not document a successful backend string-preserving
roundtrip. Other public sources (kmmmvs and lightningv08 notices) explicitly
validate both original decimals and ordinary pandas float64 CSV read/write.

Competition metadata exposes `evaluationAlgorithm.passCompleteSubmission:true`,
but no loader dtype declaration was present in the public GetCompetition
response. Backend dtype preservation remains unconfirmed.

## Measured risk

`scripts/check_decimal_transport.py` preserves the original artifact and uses
its SHA-matched official report as the raw baseline. It selects all 88 cases
containing coordinate fields longer than 50 characters, loads the complete CSV
with default pandas type inference, serializes the selected numeric rows, then
runs the unchanged SHA-pinned official v17 evaluator on those actual strings.

Eight cases fail certified overlap checks after the numeric roundtrip:

`444, 487, 733, 734, 737, 788, 789, 845`.

Their total score penalty is `0.127869469619130`. If these were the only cases
affected by backend conversion, v7's score would increase from
`22.304805438790023` to approximately `22.43267490840915`.

Full evidence is saved in `artifacts/merged-v7-transport.json`, including input
hash, pandas version, selected cases, numeric dtypes, and all per-case reasons.
This is a concrete conditional transport failure, not proof of Kaggle's loader
behavior. The other 912 cases were outside this targeted audit.

## Supported geometric remedy

Scale **centres only** by a tiny factor, such as `1.00000000001`, using high
precision, preserving the angles and unit square side lengths. This creates a
small positive geometric clearance that survives float64 transport. Retain the
original v7 file, write a separate safety candidate, and certify both the raw
CSV and its default pandas roundtrip before submitting that candidate.

A proof check on failing case n=444 used Decimal precision 100 and that factor:
both the new raw decimal rows and their default pandas read/write passed the
unchanged official metric. Both produced score `0.023734695428782704`.
The expected total cost of applying this factor to 88 cases is below `1e-8`,
far below the observed conditional overlap penalty. A full repaired-candidate
validation is still required; this one-case check does not certify all cases.

No prefix strings, precision-check bypass, or changes to the official metric
are needed. Quoting numeric CSV fields alone does not prevent pandas numeric
inference.

## Completed fix and full validation

The latest immutable source, `artifacts/merged-ftmc-cpu.csv`, was transformed
with `scripts/make_transport_safe.py` into `artifacts/submission-safe.csv`.
The stdlib-only helper uses Decimal precision 100, explicit ROUND_HALF_EVEN,
factor `1.00000000001`, and preserves the original CSV field order and all
angle strings. It selects a whole puzzle if any x/y/angle field exceeds 50
characters. This moved 55,545 centres across 88 puzzles. All other rows, IDs,
and angles were checked unchanged. A repeat conversion and the independently
reconstructed Kaggle source exporter both reproduced the exact safe CSV hash.

- Original score: `22.30480381013748`.
- Raw safe score: `22.304803810998131`, zero invalid puzzles (88 checked anew,
  912 unchanged cases reused through source and per-puzzle hashes).
- Score cost: approximately `8.60652e-10`.
- Full default pandas float64 roundtrip: **all 1,000 puzzles evaluated anew,
  zero invalid puzzles**, score `22.304803810998131` — the identical returned
  binary64 score.
- Safe submission SHA256:
  `97df15c28ee66ab1a414d28218fd4e8b28c2bf6ce8869281db9610f7dac81da9`.

Full reports:
`artifacts/submission-safe-official.json`,
`artifacts/submission-safe-roundtrip-official.json`, and
`artifacts/submission-safe.transport-validation.json`.

The successful numeric-roundtrip check removes the practical dependence on
unconfirmed backend decimal-string preservation for this candidate.
