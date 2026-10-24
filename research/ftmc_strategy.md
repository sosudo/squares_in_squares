# FTMC/refill search study

## Verified public sources

- Chris Deotte, https://www.kaggle.com/code/cdeotte/squares-in-squares-ftmc-milp-refill-22-311 , version 2. Source in `artifacts/public/cdeotte__squares-in-squares-ftmc-milp-refill-22-311.notebook.json`. This is an illustrated technical briefing and exports its published dataset; it does not contain the named private solver scripts.
- Published gadget data: https://www.kaggle.com/datasets/cdeotte/squares-in-squares-22-315-data . Public dataset API reports **CC0: Public Domain** and isPrivate=false. Local `artifacts/public/gadgets_39_and_baselines.npz` contains 39 before/after rectangular gadgets and portfolio side-length arrays.
- Vladislav Lavrentev (lightningv08), https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search , current downloaded version 21. Its code cell embeds nineteen readable implementation files in SOURCES, including fused CuPy/CUDA rectangle L-BFGS, FP32 exploration, FP64 finishing, FTMC mutations, refill, novelty archives, fault/seam composition and source notices.

### Notebook code license evidence

The official Kaggle viewer's public-notebook panel states: **“This Notebook has been released under the Apache 2.0 open source license.”** The implementation is visible in the official current frontend bundle https://www.kaggle.com/static/assets/KernelViewer.3f677ea09aac5828.js ; the condition is `!isPrivate`. The public source-pull API reports Lightning isPrivate=false. The metadata endpoint does not repeat a license field because this public-notebook notice is rendered by the viewer. Preserve Apache license text, source author/version, embedded source notices, and modification notices when adapting its implementation.

## Why isolated cores matter

Full-puzzle perturbation wastes most gradients on nearly upright continents and their flat sliding modes. A separate ribbon can also mask another ribbon's improvement because total bloat is the maximum ribbon bloat. Therefore optimize rectangular `(w,h,surplus)` gadgets independently, replacing upright fill after each core mutation, and compose winners afterwards.

The architecture is:
1. Strip near-uprights (folded angle below about 1 degree) from a gadget, retaining the tilted core.
2. Mutate the core by insertion, taper-tip deletion/replacement, coherent rotation/shear, archive crossover, or a fresh rational-slope lattice. Useful angle families include 26.565, 28.072, 33.690, 36.870, 40 and 45 degrees, with both signs.
3. Relax the core in a slightly loosened rectangle. Refill the upright region with wall lattice and exact exclusion-edge candidates. A small soft core overlap (e.g. 0.008) may be used for *exploration seeds only*.
4. Batch GPU quench the full refill, then finish only a few promising replicas in FP64 and with LP contact closure. Certify final decimal output using unchanged official v17.
5. Retain distinct geometric signatures, including some near-best gadgets, rather than only a single smallest-bloat pose. Compose the gadget archive with conservative seam profiles and recertify full portfolio changes.

## Configuration recommendation

Use `experiments/packing_gpu_search.py` as a portable comparator, not the sole long campaign. Its full-puzzle Adam, per-batch CPU neighbor-union construction and global norm clipping are substantially less specialized than the public fused rectangle CUDA L-BFGS. A short full-puzzle run remains useful to establish throughput and improvement rates.

Before consuming a large GPU budget, run a 10–20 minute pilot with 64/128/192 replicas and measure **accepted certified gadget improvements per GPU-hour**, refill success rate, full-quench rate, and composition gains. FP32 should handle most replicas; FP64 should finish only the best few because consumer/cloud GPUs often have weak FP64 throughput. Count GPU-device hours explicitly when multiple devices run concurrently.

A reasonable adaptive campaign starts with roughly half the compute on isolated-core mutations, one quarter on composition/contact closure, and one quarter split between targeted alternative basins and validation/checkpoint recovery. Reallocate based on measured gains; preserve a complete certified portfolio before every long phase.

Good initial gadget targets from the public briefing include `(3,14,+4)`, `(3,14,+5)`, `(3,16,+5)`, `(3,15,+3)`, `(4,21,+3)`, `(6,20,+3)`, `(7,22,+4)`, `(7,21,+15)`, `(5,14,+8)`. The narrow-ribbon and non-45-degree families gave the largest basin jumps. High-surplus gadgets can improve many full puzzles even when their own bloat gain is small.

Full-puzzle candidates highlighted in the public portfolio: n=457,639,701,756,812,930,981,991; higher-surplus gadget refinements also propagated to n=503,702,813,871. Re-rank these against the **current** merged portfolio and the public per-puzzle leaderboard before allocating substantial time, since many inherited gains are already present.

## Independent CPU refill implementation and checks

`experiments/refill_search.py` independently implements analytic sections of the octagonal upright/tilted exclusion region, four wall-anchored integer lattices, finite staircase-contact candidates, safe simplicial-vertex reductions and componentwise HiGHS maximum-independent-set MILPs. `fill_rect(W,H,tilted,incumbents=None,depth=4,time_limit=1.,margin=1e-9,soft=0.)` returns upright poses and explicit solver/repair metadata.

The finite-set optimum is not the continuous global packing optimum. `soft>0` marks the result as requiring repair; it must never be submitted directly. Upright/upright conflict handling remains strict even with soft core overlaps.

Five correctness tests in `tests/test_refill_search.py` pass: finite MIS vs exhaustive enumeration, exclusion intervals vs independent SAT evaluations, the known five-square diamond, empty-rectangle capacity, and explicit labeling/bounds for a soft-overlap seed.

Reconstruction benchmark on all 39 published after-gadgets recovers the original count in **39/39** cases with strict soft=0 and original near-upright centers included as candidates. Every finite graph optimum was proved. Total refill time 2.50 seconds; slowest 0.259 seconds on the current cloud CPU. Results: `artifacts/refill-fixture-benchmark.json`. This verifies reconstruction and throughput; it is not a new leaderboard gain.
