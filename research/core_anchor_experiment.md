# Tilted-core wall position

The first complete-puzzle FTMC pilot generated 773,760 tilted-core trials but
zero refill successes. The public mutation initializer removes upright fillers,
normalizes the remaining core and centers its bounding box in the full square.
For these inputs, that rigid translation destroys a useful wall/corner position.
The core-only optimizer has no upright-fill objective that would restore it.

An independent CPU control isolated the translation. Eight unchanged, certified
cores were refilled either at their original position or centered exactly in
the original `f0` box, matching the public initializer. Both variants used the
same original upright candidate centres and the same exploration box
`min(.995, f0+.035)`. The control ran with both strict `soft=0` and the public
exploration allowance `soft=.008`.

| n | Tilted squares | Strict original capacity | Strict centered capacity |
|---|---:|---:|---:|
| 83 | 28 | 83 | 74 |
| 86 | 21 | 86 | 77 |
| 106 | 22 | 106 | 96 |
| 129 | 29 | 129 | 120 |
| 171 | 32 | 171 | 157 |
| 205 | 34 | 205 | 192 |
| 259 | 49 | 259 | 243 |
| 302 | 49 | 302 | 282 |

All 32 finite candidate graphs were solved optimally in 23.1 seconds total.
The soft controls showed the same severe deficit; n83 gave 73 instead of 74.
Candidate sets change with the soft allowance, so their finite optima need not
be monotone. These numbers are not global packing capacity bounds or score
improvements. No GPU quench occurred in this control. Exact-contact floating
outputs still require official validation before export.

Evidence and reproduction:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python experiments/core_anchor_control.py
```

`artifacts/core-anchor-control.json` binds the tested seed archive and records
each result, elapsed time and the exact centering translation.

## Optional initializer adapter

`experiments/ftmc_anchor_mutations.py` calls the unchanged public mutation
function, then translates each returned core. Its default treatment preserves
the incumbent core's fractional wall clearance on each axis. A separate
`mixed_walls` policy can explore four corner anchors, but it is **not used** in
the initial A/B experiment. The adapter changes no angles, relative square
positions, shrink targets, geometry admission checks or random draws. Disabled
mode returns the original function directly.

Three tests cover exact restoration of a centered unchanged core, preservation
of rigid geometry at all wall anchors, and isolation of RNG state and input
objects. A further local check compared 384 actual public mutations across all
six modes and the eight real seeds. Angles, relative coordinates, shrink
targets, original recipe fields and RNG state were unchanged; only rigid
translations differed.

## Prepared GPU comparison

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/build_anchor_ftmc_job.py
```

The builder freezes an independent copy of the already certified complete-puzzle
job. It selects the eight controlled seeds with uniform priorities. GPU0 uses
the original initializer; GPU1 restores the original wall anchor. Both use the
original angle library, 64 replicas and distinct random seeds. Funnel metrics
run in both arms. The original source also offsets its mutation-mode cycle by
device, so this is a practical search comparison, not an exactly paired
statistical trial.

The self-contained private job is `artifacts/anchor-ftmc-job`, with no network
or mounted input requirements. All public-source hashes are unchanged, and
the eight exact seed poses retain their raw/roundtrip official certificates.
The source is 195,697 bytes with SHA256
`69d19f2917ec735cbde503d3742931f638cffdca97135264e902c85fe2f03159`.

Each T4 has a 300-second nominal search, a 60-second worker grace period and a
700-second overall parent alarm. Shutdown can add small cleanup overhead.
Arithmetic nominal usage is 0.167 device-hours; actual Kaggle quota accounting
is separate. All admitted variants remain available, including geometrically
distinct near-best configurations. Full-puzzle candidates still require merged
CSV certification and numeric transport validation before any submission.

This file records preparation and CPU evidence. Read the actual remote status
and results before claiming GPU success or a leaderboard gain. The packaging
agent did not launch the notebook or submit to the competition.
