# Scalar staircase DP with exact finite-palette joins

The bounded pilot completed in **20.76 seconds with one CPU worker**, using the validated `5cba…` portfolio (score 22.30142775062775). It retained 1,315 rectangle types and 8,704 finite pose options from current whole cases, combined FTMC, full higher-n, latest soft, insertion, alternative and original active banks. Native C++ keeps a six-trace minimax beam without a separating-line restriction; Python realizes its proposed chains using actual adjacent-block SAT. A directed type edge is excluded only after every retained pose pair for that edge fails. This is a finite heuristic, not exhaustive geometric composition.

Five cases passed unchanged official raw and ordinary-pandas evaluation plus independent interval validation. Their final candidate interval-side gains against that frozen baseline are:

| n | Score gain |
|---:|---:|
| 807 | 0.00001931733991 |
| 865 | 0.00001863058484 |
| 921 | 0.00001597424185 |
| 982 | 0.00000001177526 |
| 986 | 0.00000001452628 |

Total: **0.00005394846814**. These figures precede the separate whole-portfolio merge and transport certification. Candidates use the exact `.17g` strings checked by the gates. The candidate file is `artifacts/scalar-sat-staircase-v1/candidates.json`, SHA-256 `6f475d09b9cef1fd6d443b8f90d2a86277185bf070679ca517f7bb7d41866c88`; `report.json` contains every full-case certificate and source recipe.

All five successful chains use a one-cell horizontal or vertical buffer. Thus this run demonstrates newer-seed propagation and retained-source coverage, rather than an improvement caused by removing separator profiles. The five DP rounds attempted 593 distinct chains and 13,640 actual pose-pair SAT checks. They rejected 559 unrealizable scalar chains and learned **238 unique** incompatible finite type edges. The raw counter `finite_type_edges_forbidden=558` counts repeated observations; the explicit `blocked_edges` set is authoritative for unique edges. One chain had pairwise-compatible options that could not be made globally consistent along the path. Coverage is limited to whole-donor nominal rectangles, eight pose options per type, and the finite beam; no general absence-of-improvement claim follows.

Mandatory controls reproduced a valid 27-square construction from two five-square diamond motifs with a unit buffer, and rejected the corresponding overlapping zero-buffer proposal for n=18. Final acceptance always follows full-layout construction and the unchanged geometry/transport gates. Public vendor files remain unchanged. Executed Python/C++ source snapshots are preserved under `artifacts/scalar-sat-staircase-v1/executed-source/`.

Four successful chains explicitly use `artifacts/active-frontier/active_seed_variants.npz`, whose 51 original crop poses were not explicitly retained in the then-current GPU input descriptor. In particular, n=921 combines its old 9×22+11 crop (bloat 0.830770954) with a combined 8×20+10 variant. The 51-pose archive is now being included explicitly to avoid losing those geometries when full-case incumbents change. This is not a causal ablation of equivalent crops available elsewhere.

The original archive SHA-256 is `5075a4454e2bd5eaef2ab5e6e0a7192c3bc71d02fe606830d2c7cccdf704cf13`. All 51 arrays are byte-identical to their corresponding primary arrays in the already interval-validated original bank. Per-array hashes, equality checks and inherited provenance are bound by `old-active-donor-binding.json`, SHA-256 `c9d7c7e8d426b857b527f7bb8be96afd2e68babf4cf40fa204533831869ff0b6`. No new official-certification claim is made for that entire bank.

The related `experiments/amplify_square_family.py` is stable for the intended surplus-one n65/n50 use. Its n65, n291 and n628 buffered-copy/L-frame controls all passed full raw/default-pandas official and independent gates in 2.10 seconds; their frozen proof is `artifacts/n65-family-controls-v1/amplification_report.json`, SHA-256 `9d40930f0e0388e7d574e5a16897e6fd7f91e364741825572514cbefd73b874d`. The 39-case n65 amplification remains conditional on finding a better source seed; no n65 improvement was achieved by this work.
