The next seed bank follows the 35 broad-composition constructions that actually
entered the latest certified portfolio. It contains **25 oriented rectangle
types and 28 geometry variants**, grouped into 16 useful transpose families.
The reference is `merged-broad-composition-v1.csv`, SHA256
`d12aabf77738101d90ceecb002314e02a5fe9d75f53df345317b9069a5aceb4d`.
Its final transport-safe portfolio scores **22.303055580908733**, with ordinary
pandas roundtrip 22.303055580908730 and no invalid puzzles; the safe CSV hash is
`f64b8e59f3a4f19c8839b772115b3bcf63fd212c9986cb9b6161822561fb1abc`.

Use `artifacts/active-broad-frontier-v1/active_seed_gadgets.npz` with
`active_priorities.json` for a type-based CPU FQ campaign. The NPZ SHA256 is
`13a55c6987b0f12595426252536ea83d68467640e918759dd0f4668dc7333241`.
`active_seed_variants.npz` retains all 28 variants, including alternative wall
phases and reflections of the same type. Its SHA256 is
`6c658b4b4ca5f3ece89c5d2e071022f08457f213c546251bfbc3185ca3968f74`.
All variants pass the pinned official metric and the independent interval
validator, both on their exported 17-digit coordinates and after ordinary
pandas numeric parsing/serialization. Exact geometry and certificate bindings
are in `active_seed_validation.json`.

The immutable recipe sources are the two completed broad profiles
`bins32_angles3` and `bins16_angles7`, the original 82ad source portfolio and
the pinned donor archives. The extractor verifies the source archive hashes,
composer input array hashes, exact D4 transforms, stable crop order statistics
and fixed-point bloat. It reproduced the incoming TL and outgoing BR profile
bins for every one of the 54 selected recipe occurrences.

`raw_phase_variants.npz` preserves the exact selected source poses before any
normalization or rounding repair. SHA256:
`887d52334a2260fbd2d1d35dcf06bd7ff7e3ab51fa43ffe7f9dd99de26da58bc`.
The manifest records original wall margins, crop square IDs, the conservative
profile square superset, incoming/outgoing normals, both exact support values
and quantized bins, source notices, and the affine center transform to each
certified optimization seed. Seed normalization changes phase; an optimized
seed must have its profiles recomputed and be recomposed into the whole puzzle.

The largest conditional opportunities for a **0.01 reduction of bloat in every
relevant occurrence of a family** are:

| Rectangle family | Conditional full-score gain | Tilted squares in primary seed |
| --- | ---: | ---: |
| 5×17 +7 | 0.001890318 | 78 |
| 7×19 +13 | 0.000834027 | 128 |
| 7×20 +14 | 0.000823607 | 136 |
| 8×21 +13 | 0.000646763 | 153 |
| 8×22 +14 | 0.000646425 | 164 |
| 9×21 +8 | 0.000621858 | 158 |
| 9×20 +12 | 0.000463600 | 150 |
| 8×20 +12 | 0.000340010 | 144 |
| 10×22 +14 | 0.000174328 | 180 |
| 8×20 +10 | 0.000103619 | 146 |

These are search priorities, not achieved gains. Transposed occurrences can be
tied for the maximum bloat; improving only one leaves the full puzzle score
unchanged. Family estimates overlap and must not be added. Holding both
separator profiles fixed, simultaneous reductions give the following
non-double-counted estimates on the current 35 chains:

| Families improved | Bloat reduction 0.001 | Reduction 0.005 | Reduction 0.01 |
| --- | ---: | ---: | ---: |
| Highest 1 | 0.000205081 | 0.001025403 | 0.001890318 |
| Highest 3 | 0.000451475 | 0.002090577 | 0.003669003 |
| Highest 5 | 0.000580793 | 0.002737171 | 0.004962191 |
| All 16 | 0.001148630 | 0.004727100 | 0.008419021 |

The top-three 0.01 scenario would reach approximately 22.29938658, provided
those improvements preserve compatible profiles and survive full-puzzle
recomposition and certification. This is a hypothesis to test, not an
authorization to submit the current above-threshold portfolio.

Five concrete orientations were absent from the previous active bank:
`17_5_7`, `7_19_13`, `22_10_14`, `18_5_11`, and `22_6_16`. The 6×22 +16 family is
new to that bank; the other four complement existing transpose families.
CPU FQ can also pursue the useful types exceeding the GPU worker's 160-tilted
square cap: 8×22 +14, 10×22 +14, 8×21 +14 and 10×23 +17. The last has 218 tilted
squares. A smaller bloat alone is insufficient if it damages either separator.

The reproducible helper is `experiments/extract_broad_active_frontier.py`.
Four regressions check tied bottlenecks, partner limits, wall-phase sensitivity
and D4 transpose identities. Run with:

```sh
.venv/bin/python -m unittest discover -s tests -p test_extract_broad_active_frontier.py -v
```

No GPU work or competition submission was launched for this extraction. Original
public pins and licenses remain unchanged.
