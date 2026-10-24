# Squares in Squares | Neighbour Transfer + Squeeze

Start from the attached **Fresh Records, Certified** notebook output, then merge the newest public packings puzzle by puzzle and replay this notebook's own certified improvements.

**Version 9 (24 October):** the best attached public output (Sung Heo's dashboard batch, 22.3078473) already contains the best packing of every other public notebook, so merging alone adds nothing.
This version therefore runs a CPU-only contact-LP polish (sequential LP over centres and angles with exact SAT admission) on those packings.
**57 puzzles** shrink, and each one passes the official metric after the float64 round trip.
Result: **22.3078472906 → 22.3078085666** (gain 3.9e-05). The polished coordinates are embedded and replayed below; the merge keeps them only where they are still the smallest certified packing.

Each public packing is admitted only after the same float64 round trip and official certification; border expansion and deletion then run on the merged packings.
Coordinates are round-trip doubles, and centre dilation opens contacts by about `1e-11`. The final CSV is read with pandas' default float64 parser and scored exactly as on Kaggle.
Earlier versions replayed 60 GPU-search gains from 22 October; public packings have since beaten all of them, so their data was replaced by the version 7 improvements.

The default run replays compressed, locally found coordinates. The full search implementation is included below; `RECOMPUTE_SEARCH=True` reruns a bounded search and can take substantially longer.

## Official metric and certification library

Both are embedded verbatim from the certified base. All admission checks use the unchanged competition metric.

## Load the attached base

The parent notebook is the only packing input. Its own credits and source provenance remain applicable.

## Reproducible search code

The extracted CUDA L-BFGS, SAT continuation and contact LP are adapted from lightningv08 (Apache-2.0). Seed selection, checkpointing and the local search schedule are provided here. Floating search candidates still require certification.

## Replay, certify, and write

Every candidate is checked on the exact decimal strings that will be written. The complete 1000-puzzle output is certified again.

## Merge with the newest public packings

Public notebooks move fast. Each attached public output is compared puzzle by puzzle with the packing above.
A smaller public packing replaces ours only if it passes the official metric after the same float64 round trip the scorer uses.
If the best one fails, the next best is tried.

## Score the final float64 file

Default `pd.read_csv` followed by the official `score()` reproduces the leaderboard read path.

## Measured gains and improved packings

## Credits and limitations

* Base packings and exact literature witnesses: [Fresh Records, Certified](https://www.kaggle.com/code/malyshevdanil/squares-in-squares-fresh-records-certified), its attached public notebooks, Francisco Couzo, Evan Daniel, Joshua Levy and all original contributors credited there. Derived data retain those credits.
* CUDA spatial hashing, per-island L-BFGS, conservative SAT continuation, and sparse contact LP: [lightningv08 — CUDA Packing Search](https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search), Apache-2.0. The copied source and its background credit to prvsiyan are retained.
* Related window-closure and contact-polish approach: [kirilltym — CPU Window Closure + Contact Polish](https://www.kaggle.com/code/kirilltym/22-590879-cpu-window-closure-contact-polish). Its executable notebook cells were not run during extraction.
* Public packings merged in version 9: [Sung Heo — Squares Dashboard Public Batch](https://www.kaggle.com/code/kmmmvs/squares-dashboard-public-batch-20261024), [lightningv08 — CUDA Packing Search](https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search), [Chris Deotte — FTMC & MILP Refill](https://www.kaggle.com/code/cdeotte/squares-in-squares-ftmc-milp-refill-22-311), [Dariush Afshar — Exact Validator, Record Merge](https://www.kaggle.com/code/dariushafshar/squares-in-squares-exact-validator-record-merge) and [Aqib Raza — Top LB Blending](https://www.kaggle.com/code/aqibrazadev/squares-in-squares-top-lb-blending-visualization), with every source and credit they list (including alex chilton's Fault-line DP work).
* Official competition metric: Apache-2.0, embedded unchanged.

The optimizer is heuristic. Many starts remain jammed or fail to beat the base; floating geometry alone is never accepted. Small gains should not be interpreted as a proof of optimality. This notebook only writes `submission.csv`; it does not submit anything itself.