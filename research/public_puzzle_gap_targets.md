# Public per-puzzle bounds for structural search

On 2026-10-24 at about 09:25 UTC, the public rendered output of
[inversion's per-puzzle table, version 10](https://www.kaggle.com/code/inversion/squares-in-squares-per-puzzle-leaderboard?scriptVersionId=361620939)
provided 1,000 reported side lengths with team and submission-date attribution.
The notebook session is 361620939, evaluated at 00:02:02.353 UTC that day.
This is a dated public reference, not the latest leaderboard, coordinates, an
optimality proof, or a guarantee that this search can reproduce those bounds.

The private input dataset was not accessed. An unauthenticated read of the
public `kernels.LegacyKernelsService/GetKernelViewModel` endpoint, using the
author, notebook slug and exact session ID, supplied the public rendered-output
URL. Its HTML SHA256 is
`440d8f2a3827851a09325c0f42b96c4b0bdf2d9bfcb467ca59a0d54257ac7c45`.
Temporary output URLs are not stored in Git. The factual decimal rows and
original attribution are retained in [the reference JSON](data/public_puzzle_reference_v10.json).

Against current raw portfolio `b9374e881450748a04a86e39b84c69ba8607ceb1e95a303caeb93f38d9174354`,
311 cases trail the reference by more than 1e-8 score. The sum of positive
differences is 0.1075247867403. Cases already ahead of this snapshot are not
treated as newly discovered records. The comparison verifies every current
side string against its hash-bound official report and uses 80-digit Decimal
arithmetic.

| n | Current side | Reference side | Score gap |
| --- | ---: | ---: | ---: |
| 335 | 18.8228756556 | 18.7949041877 | 0.001528245 |
| 412 | 20.8228756555 | 20.7981655820 | 0.001217378 |
| 454 | 21.8231026571 | 21.7981655820 | 0.001170355 |
| 299 | 17.8228756555 | 17.8027188544 | 0.001165698 |
| 498 | 22.8241007486 | 22.7990335914 | 0.001123286 |
| 803 | 28.8275852224 | 28.7961308788 | 0.001110000 |

Each of these dated gaps exceeds the current 0.00110556 distance to the user's
submission threshold. This prioritizes structural changes around these cases;
it does not supply their missing geometry. Repeated fractional parts across
412/454, 498/544/592, and 747/803/861 suggest shared extendable motifs, a
hypothesis for construction research. In contrast, n65 and n367 match this
snapshot within about 1e-12 score. They remain unsolved search possibilities,
but this table supplies no demonstrated improvement for them. n147 has
0.000479258 of reference headroom and n492 has 0.000244305.

`scripts/compare_public_puzzle_reference.py` parses the rendered table and
compares it with `artifacts/current-best-portfolio.json`. The executed report
is `artifacts/public-freshness/notebooks-20261024T092136Z/hash-bound-public-gap-analysis.json`.

The same freshness check found no newer Ready datasets beyond KMMM28,
Cdeotte2, Dariush11 or Lightning18, and Couzo HEAD remained 1c1715399709.
The public notebook catalogue grew from 40 to 42 entries. Three changed/new
standard CSV outputs were downloaded and screened: Malyshev, Mtoshidesu and
Zkskhurram. None supplied a full-case improvement over the current portfolio;
their exact bytes and provenance remain in the dated artifacts. Kyle's
standard `submission.csv` still returned 404; this says nothing about his
unpublished packings.
