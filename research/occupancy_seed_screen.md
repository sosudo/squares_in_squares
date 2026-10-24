# Changed-occupancy starts for n335

Prior full-puzzle vacancy coverage was335←336 only, from normalized ancestor SHA256 `f87c5ebd57a12e1e964e884cdea8bde55affc955e10740556c4806f2d058edb6`. Structural deletion IDs259,257,281,270,291,263 each saw rigid delete,±6°/±12° local rotations and coherent strip bends under the recorded sign. Upright-cap IDs256,335,317,119 saw plain deletion and both6° rotations. There were no337–340 multi-deletions in those campaigns or the seven rounded starts.

The uncovered300→335 L-frame was separately certified and tested; see `frame300_to335.md`. It returned close to the incumbent without a gain. The next screen therefore prioritizes genuinely different whole topologies:337 has46 tilted squares,338 has116, and340 has100, versus44 in current335. Their original sides are18.858391767654087,18.886009199752586 and18.926898901280953 respectively.

`occupancy_seed_screen.py` compresses **centres only** toward nominal box18.803, preserving each unit square's size and angle. It ranks squared full-SAT overlap and wall stress, greedily removing two, three or five units to leave exactly335. A matched policy deletes a contiguous boundary-strip group. The two later forced-tilt variants choose the highest-stress tilted unit first, then continue greedy stress deletion. These are explicitly **invalid optimizer inputs**, not geometric certificates or improved submissions. Pair-overlap counts include many small grid overlaps caused by centre compression.

| Parent | Policy | Deleted parent IDs | Remaining tilted count |
| --- | --- | --- | ---: |
| 337 | Stress | 25,236 | 46 |
| 337 | Boundary strip | 15,0 | 46 |
| 338 | Stress | 253,304,320 | 116 |
| 338 | Boundary strip | 271,284,258 | 116 |
| 338 | Forced tilt | 0,253,304 | 115 |
| 340 | Stress | 89,152,154,109,118 | 100 |
| 340 | Boundary strip | 194,195,193,196,192 | 100 |
| 340 | Forced tilt | 209,89,152,154,109 | 99 |

The first six-start screen took1.16seconds; the expanded eight-start screen took1.30seconds. The original executed source is preserved in `artifacts/occupancy-seed-screen-v1/source-at-execution.py`. V2 exact input archive is `artifacts/occupancy-seed-screen-v2/optimizer-seeds.npz`, SHA256 `802009818e63f7ffcd1648a99b4e7b7e421425925de41f6967e003156229c074`. Its full screen/source/parent hashes and actual raw envelopes18.8065–18.8105 are separate from the nominal target. D4-assignment centre RMS distances to the incumbent are .234–.528; different tilt counts also establish structural diversity independently of assignment.

## Bounded native pilot

The four authorized starts are338stress,340stress,338forced-tilt,340forced-tilt. `fq_occupancy_pilot.py` gives each one true-held radius.4 return with initial kick.04, no rounded compression,hold factor1, twelve quadratic return steps and ordinary ALM45/polish100. Each stage has an inclusive25-second cap; the one-worker supervisor ends the entire pilot before130seconds.

The native `read_cfg` directly accepts supplied box side and coordinates, including deliberately infeasible placements. A small explicit writer keeps the raw coordinates unchanged and supplies **exactly18.803** as the initial/held box; it does not silently normalize into the larger raw envelope. Tests verify negative coordinates survive writing and that a held trace at18.8088 is rejected. Only actual fully certified output sides can be candidates. Current score arithmetic requires335 physical side below18.803445346855 for that case alone to cross22.3; an invalid nominal box is never credited.

The pilot is complete in **60.28 seconds total**, one CPU, without an outer kill or source change:

| Start | Final status | Actual certified side | Final tilted count |
| --- | --- | ---: | ---: |
| 338stress | Fully certified | 18.883210517628427 | 115 |
| 340stress | 25-second stage timeout | No output geometry | — |
| 338forced-tilt | Fully certified | 18.878773938772056 | 116 |
| 340forced-tilt | Fully certified | 18.930457706050664 | 104 |

There are **zero canonical335 improvements**. All three successful outputs have twelve monotone radius reports ending at exact zero, native `s_soft=s_hold=18.803`, and fresh independent interval/official raw/default-pandas full certificates. The timed-out340stress treatment reached only nine return steps, last radius.025, with no native output file. Its partial stderr is preserved; it supplies neither a rigid pose nor an infeasibility claim.

All completed output poses and raw native stdout/stderr remain under `artifacts/fq-occupancy-pilot-v1`. `native-traces.json` pins each input/header and stdout/stderr/output file by hash and records incomplete traces honestly. Donor NPZ SHA256 is `9dba9fbae5dff1b28139b90d92e63a562c3cacd1377049267d85d501a7db902f`, manifest `456c8310dbd4a8181c80744f2d90ede7b4b8a3a18c494755156a10189445df6d`, results `3e505523bac49787b0442a46b7922be938b4919aaf4513da6a5e2c5a8f64d8d7`, certificates `1f954d029270d64e129f9ba50c2696c7bc70406101d8be8cb15fa513555824c7`. Both writer/box tests pass. This finite policy stopped after the authorized four starts; no unchanged extension, GPU push or competition submission followed.
