# Squares in Squares: certified packings for n = 1..1000

Validated unit-square packings for the Kaggle competition *Squares in Squares*, one per puzzle
n = 1..1000, plus the certified best-known index they come from.

## Files

* `index_packings_dilated.csv` - for every count whose best-known side beats the grid (543 of the 1000),
  the exact rational certificate from Francisco Couzo's repository converted to decimal coordinates
  (34 significant digits) with a centre dilation of (1 + 2e-8). The dilation turns every exact contact
  into a gap of at least 2e-8, which the official metric's float64 stage accepts outright; it costs
  about 2e-8 * L on each side. Columns: `n, square_id, x, y, angle` (radians).
* `index_per_n.csv` - the index line for each n: `rounded_up` (the certified side, rounded up to 12
  decimals), `credit` (who found the arrangement, as recorded in the repository), `source`, `status`.
* `certificates/nN.cert` (from version 2 on) - the raw rational witnesses, unchanged: `n S` then one `x y t`
  line per square, `t = tan(theta/2)`. Format and exact verifier by Evan Daniel.
* `packings_v1.csv` - a complete submission (`id, n, square_id, x, y, angle`): per n, the best of the
  certificate, the grid, and the public Kaggle packings listed below (version 2 of this dataset: the merge of
  2026-10-22 03:45 UTC, metric score 22.578267), after passing a line-by-line mirror
  of the official metric both on the strings as written and after a float64 round trip.
* `per_n_v1.csv` - per n: measured side `L` (50 decimals), `score`, winning `source`, index bound,
  tightest float64 gap and the number of pairs that needed interval arithmetic.

## How it was built

Notebook: https://www.kaggle.com/code/dariushafshar/squares-in-squares-exact-validator-record-merge
(the validator, the merge and the per-band tables are all there). Scores are the competition metric,
sum over n of L/sqrt(n) - 1, lower is better.

## Sources and credits

* Francisco Couzo, franciscouzo/square-packing (MIT), the certificates and the per-n credit lines.
  The MIT notice of that repository (Copyright (c) 2026 Evan Daniel for the verifier; the repository
  licence file) applies to the certificate files redistributed here.
* Evan Daniel, evand/square-packing (MIT): certificate format and exact checker.
* David Ellsworth, Squares in Squares catalogue (https://kingbird.myphotos.cc/packing/squares_in_squares.html),
  continuing Erich Friedman's survey; and the discoverers named in each credit line (Frits Göbel,
  Erich Friedman, David Ellsworth, Thomas Schadt, David W. Cantrell, Károly Hajba, Joost de Winter,
  Evan Daniel, Darius Muglich, PingYou Ltd, Mykhailo Polkovskyi, M.Z. Arslanov, S.A. Mustafin and
  Z.K. Shangitbayev, and others).
* Joshua Levy and contributors, The Squares Project (https://github.com/jlevy/squares), the open register
  most of the recent records went through.
* Public Kaggle packings in `packings_v1.csv` (rows marked by `source` in `per_n_v1.csv`): alex chilton,
  *Certified Merge of Public Packings*; Кирилл Тымчишин, *CPU Window Closure + Contact Polish*;
  Vladislav Lavrentev, *CUDA Packing Search*; and the earlier work they build on by avazaku and prvsiyan.

Everything here is an upper bound. No record claim is made for any n.

Licence of this compilation: CC BY 4.0. Certificate files keep their MIT licence.

