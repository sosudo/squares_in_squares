<div style="padding:28px;background:#132e42;color:white;border-radius:14px"><p style="color:#80d5c2;letter-spacing:2px">SQUARES IN SQUARES</p><h1 style="color:white">CUDA Packing Search</h1><p style="font-size:19px">Change the core · Refill the grid · Reuse the geometry</p></div>

**Certified score: 22.307818650783. Lower is better.**

The useful unit of search is a reusable rectangular gadget. A new arrangement can improve several puzzle sizes once it is composed with other gadgets. This version combines fresh, credited public witnesses with CUDA support-profile composition, then crops the new compositions and composes again.

Default **Run All** replays a frozen CSV, displays the measured gains and checks all 1,000 score terms on CPU. Optional CUDA search is disabled. All squares keep side one.

## 1. Account for the source of every gain

The score is $\sum_{n=1}^{1000}(L_n/\sqrt{n}-1)$. The official scorer supplies the upright-grid fallback when a puzzle is omitted. A smaller floating bounding box is only a proposal: each accepted replacement passes the official interval geometry checks on raw decimal strings and after ordinary pandas float64 parsing.

The refreshed portfolio retains 60 better witnesses from Sung Heo's public output, which itself preserves its contributors' credits. Malyshev Danil's newer output adds no further wins after that union. Chris Deotte's tilted-core constructions supply the earlier large jump. The two CUDA rows below measure additional certified gain over this refreshed union, not ownership of the input constructions.

Tracing every winning chain shows that none uses the newly mutated nightly worker archive. The additional CUDA gain comes from recomposing retained/public donors, chiefly n=503. The night archive remains available for inspection, but its 59 local gadget improvements are not presented as useful portfolio discoveries.

## 2. Change structure before squeezing

Full-puzzle L-BFGS can spend most of its effort on upright squares that slide inside the same arrangement. Following Chris Deotte's FTMC briefing, strip those squares out and mutate the tilted core: coherent re-angle/shear, insertion, taper deletion, boundary exchange, archive crossover, and rational-slope lattice starts. Refill the upright area, then squeeze the complete gadget.

Bulk row/column refill runs in CUDA. A small number of near-capacity failures reach the finite-candidate conflict graph and bounded HiGHS MILP. FP32 screens many proposals; FP64, gap repair and the unchanged official interval metric guard acceptance. This is not an exact solver for the continuous packing problem.

The saved T4 campaign evaluated more than six million core proposals and accepted 59 gadget improvements. Its final portfolio stayed at its starting union: a local gadget gain is not automatically a global score gain, and the earlier composition stage encountered a CuPy unsigned-sentinel conversion error. The replay below includes the corrected, tested composer and the saved gadget archive.

For a chain of gadgets, $L=K+max_i f_i$. Improving a gadget below the active maximum can leave the score unchanged. Fresh public experiments by Alex Chilton also show that exact-construction gadgets can stay rigid. Spend search on numerical bottlenecks that occur in useful chains, and retain alternative support profiles even when their isolated bounding box is slightly worse.

## 3. Compose, re-crop, compose again

A gadget holds $wh+d$ unit squares in $(w+f)\times(h+f)$. CUDA enumerates all eight symmetries and records occupied-corner support bounds at **30°, 45° and 60°**. Incoming and outgoing separators can differ. The staircase DP keeps footprint, surplus, outgoing normal and support bin, minimizing the largest fractional excess.

Prefix minima prune profiles dominated by another profile with no greater excess, no larger outgoing support and no smaller incoming support. This dominance is exact for the finite conservative profile table. Every reconstructed packing is checked geometrically and certified separately.

The first pass uses 24 support bins. Its newly composed layouts become donors for a second 32-bin pass: a useful compound arrangement can now be cropped into a different gadget. The larger profile table reduces quantization loss, while the new donor set changes the available composition structures. These effects are combined in this experiment and should not be presented as an isolated resolution ablation.

## 4. Look at the accepted arrangements

Both panels use the same scale. Blue squares are tilted; grey squares are nearly upright. Small numerical changes can be invisible, so the measured container side accompanies each drawing.

## 5. Readable implementation and bounded optional search

The archive restores the Python orchestration, CUDA C++ kernels, official metric and original source notices. The frozen default uses CPU only. Enable the optional branch on an NVIDIA GPU with CuPy and PyTorch; it starts from the certified file and uses a 12-minute hard process limit. Search proposals are admitted only after certification. No competition submission is made by the notebook.

## 6. Certify the serialized output

Both checks include submitted witnesses and every omitted puzzle's official grid fallback. Interval overlap or an uncertifiable contact rejects the candidate. GPU floating-point precision is a search tool; this independent final check determines admission.

## Credits

[Chris Deotte](https://www.kaggle.com/code/cdeotte/squares-in-squares-ftmc-milp-refill-22-311): tilted-core/refill architecture, public gadget examples, staircase composition. [Sung Heo](https://www.kaggle.com/code/kmmmvs/squares-dashboard-public-batch-20261024): refreshed portfolio with inherited per-source credits. [Alex Chilton](https://www.kaggle.com/code/alexchilton/fault-line-dp-basin-hopping-lb-22-3079): leverage-ranked gadget experiments and repeated composition. [Malyshev Danil](https://www.kaggle.com/code/malyshevdanil/squares-in-squares-neighbour-transfer-squeeze): neighbour-transfer and propagation experiments.

Avazaku, Kirill Tymchishin, Dariush Afshar, Evan Daniel, Francisco Couzo, Joshua Levy, David Ellsworth, Erich Friedman, prvsiyan, and all contributors listed in the Layout Atlas and the preserved notices retain their mathematical, code and witness credits. Public witnesses are not claimed as new discoveries here. `refresh_SOURCE_NOTICES.md` and `refresh_sungheo_NOTICES.md` preserve source hashes, lineage and licensing context. The solver is heuristic; no global optimality is claimed.