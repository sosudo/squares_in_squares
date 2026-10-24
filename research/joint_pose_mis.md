# Joint tilted and upright pose selection for n299

The finite union experiment admits both tilted and upright source poses as exact unit squares. It does not force the incumbent's 43-square tilted core. Sources are the pinned current n299, n300 and n301 layouts, the closest certified 41- and 42-tilt n299 alternatives, wall-phase translations, and new upright wall grids. Identical pose bytes are deduplicated while retaining every origin.

The original-box 299-square witness passed the complete independent interval, official raw-decimal and ordinary-pandas gates. Arbitrary-angle pairs use a safe `sqrt(2)` centre broad phase and all four SAT axes. Tight decisions use the independent exact/interval pair checker; all four frozen graphs have **zero unresolved edges**. Thus no uncertain contact was silently removed in these particular pools.

| Nominal side reduction | Vertices | Conflict edges | Initial verified clique-cover upper bound | Exact finite MIS optimum |
| --- | ---: | ---: | ---: | ---: |
| 0 | 4,072 | 98,659 | 363 | 299 |
| .002 | 4,544 | 127,913 | 403 | 291 |
| .010 | 4,541 | 127,844 | 395 | 291 |
| .020 | 4,541 | 127,994 | 399 | 289 |

Screening took 14.99 seconds. The one-worker solve completed all four cases in 150.85 seconds, with MILP status 0 and zero reported gap in every case. Each source graph, added clique and integral selection is independently checked. The solver stores eight fully certified layouts, including smaller cardinalities with their actual n labels. No n299 side improvement was found. These are finite candidate-pool optima, not impossibility claims about continuously moving squares.

Frozen evidence is under `artifacts/joint-mis-screen-v1` and `artifacts/joint-mis-solve-v1`; solve manifest SHA256 is `40c87b4381e22fc792eaf38b46c7d5f2a65be5536ef7dc2d3d3d1c5a120defa4`, donor archive SHA256 `7967b73117aba0384ce0b9a81daaae54976f318c75528b8a24c84f3dcdd10e0e`. The five graph tests and three solve tests pass. Independent validation review found no blocking issue.

## New 38-tilt start

The original-box optimum produces a mixed-source n299 layout with only **38 tilted squares** at the stated .018-radian classification threshold. Its D4-assignment centre RMS distance from the original is .0842759. The exact selected pose required only the standard centre-clearance repair: the original contact representation was officially undecidable, whereas the exported array passes interval and official raw/default-pandas validation.

The exact handoff is `artifacts/joint-mis-seed38-v1/seed.npz`, key `299`, SHA256 `351a005951818670410f57b20bdf835368006b4f153e6b553a81410d6968bbe8`; little-endian float64 geometry SHA256 is `5aedaabe88331d322640f5b95e7240f93956879d4fb764d400c2701136050094`. Actual side is **17.82287568919487**, versus canonical **17.82287565554912**, a clearance cost of `3.364575107411838e-8`. This is a new certified topology, not a score gain.

`source-mixture.json` maps each exported row back to its exact conflict-graph vertex and all source square IDs/translations. `proof.json` binds the seed, source mixture, source solver result, and both attempted-original and successful-actual certificates. The seed and proof were sent to anchor and full-puzzle pilot for distinct future starts without changing their already frozen campaigns.

The next finite check, `fq_joint_seed_check.py`, starts two native commands from those same exact bytes: rigid ALM45/polish100 and a true held-box corner-radius return from r0=.15 with an initial .04 kick. It explicitly excludes `--round-compress`, uses `--hold-f 1`, verifies all twelve reported return radii ending at exact zero and native `s_soft == s_hold == encoded input side` to 1e-10, then applies unchanged full geometry gates. Its 60-second external limit includes both trials and validation. Every valid output is retained even if scalar-worse; gains are measured against the canonical n299 side, not against the clearance-inflated seed.

That check is now complete under `artifacts/joint-mis-seed38-native-v1`: **7.25 seconds total**, one worker, no timeout. Rigid ALM45/polish100 gives side **17.8228756916757**; the true held-seed-box return gives **17.822875689179966**. Both have 38 tilted squares and pass fresh interval, official raw and ordinary-pandas gates. Neither beats the canonical side. The held trace contains all twelve decreasing radii through exact zero, with native `s_soft = s_hold = 17.822875689195`, equal to the encoded seed side within the recorded tolerance. The native initial rounding radius was .15; with no compression, the first optimized fixed-radius return step is .126, following the pinned `r0*(1-k/12)^2` schedule. This distinction avoids implying an unperformed fixed-r0 minimization.

The exact two-output archive SHA256 is `70c364267208e55dc8a882c6deaa1c86d1bc1cd4bb59b306698723b6daad804d`, manifest `6751f4c71721c16de69dd51a596c48f4edf77f6320f09161752cec818f62124b`, results `abcda50275653d53b06e24be2e214e7159e515b1023d8a7632095c174aaa447d`, and certificates `7f62892b8428e00253c543d6b1ada19b1d8186a5bbf611ea42d35f9f9fe77099`. All three held-path tests pass, including compressed-box and incomplete-return negative controls. No broad continuation followed this negative two-trial result.
