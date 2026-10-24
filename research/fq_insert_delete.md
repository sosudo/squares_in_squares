The one-CPU N±1 pilot produced two certified increased-surplus motifs and four certified interior-deletion variants in 12 trials over 25.48 seconds. Six insertion repairs converged to excess at least one and were rejected. None of the six accepted new types had a matching entry in the pinned reference banks, so this is not a claim of a new best bound or leaderboard improvement.

| Edit | New type | Squares | Certified excess |
|:---|:---|---:|---:|
| insert | 5_17_8 | 93 | 0.872063605554530 |
| insert | 9_20_13 | 193 | 0.910251941873298 |
| delete | 5_17_6 | 91 | 0.802428750537974 |
| delete | 7_19_12 | 145 | 0.918029559602125 |
| delete | 7_20_13 | 153 | 0.925638684519324 |
| delete | 10_23_13 | 243 | 0.860369396726178 |

Insertions ranked a 0.25 centre grid, box-centre and wall candidates by summed positive SAT penetrations, using upright, common incumbent tilt and 45-degree orientations. One extra square was deliberately placed into the best low-penetration location, then repaired by FQ ALM or soft-square continuation. Deletions removed interior tilted contact junctions before compression. The new adapter permits a larger box than the parent because d±1 is a different type; admission requires interval-certified excess strictly below one.

Every retained pose passed independent interval nonoverlap, interval rectangular bounds, the pinned official raw metric and ordinary pandas numeric roundtripping. The positive control recovered the removed central square of a known certified five-square packing using sampled candidates, without injecting its removed coordinates. A separate timeout control confirmed that the adapter kills its spawned descendant process group.

The frozen archive is `artifacts/fq-insert-delete-v1/donors.npz`, SHA256 `48ec40dc1056ada58e9af62ae91912272e187f3dc899385acaa72df4c0c10315`. `results.json` contains all per-pose certificates, selected insertion sites/deletion junctions and exact commands. Source, input banks and executable are frozen beside `manifest.json`. The source adapter is `experiments/fq_insert_delete.py`; smoke proofs are under `artifacts/fq-insert-delete-smoke-v1/`. Both insertion and deletion subsets are retained separately. The archive was handed to composition and aggressive soft-continuation agents; no competition submission occurred.
