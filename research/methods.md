# Public methods and solver research

Research date: 2026-10-24. Claims about scores below are source reports until
independently validated with the competition metric.

## Public coordinate and code sources

- [Shubin123/unitSquares](https://github.com/Shubin123/unitSquares), MIT licensed,
  bundles `data/kaggle/<n>.bin` (little-endian float64 center x, center y, angle in
  radians) and an index naming source public notebooks. Its exporter combines
  those geometries with explicit constructions for every n=1..1000. README
  reports aggregate score 22.372005. The 475 bundled nontrivial packings are
  mainly from `kirilltym/22-3720-cpu-cuda-mps-eda-band-lp`, with some from
  `malyshevdanil/squares-in-squares-neighbour-transfer-squeeze`.
- [tiagocabo/kaggle-squares-in-squares](https://github.com/tiagocabo/kaggle-squares-in-squares)
  contains a copy of official metric v17, Göbel construction families, extraction
  of public exact rational witnesses, multigadget fault-line dynamic programming,
  monotone deletion/L-extension closure, and PyTorch overlap-penalty optimization.
  Its reported 22.50447 solution predates the stronger merged frontier above.
- [David Ellsworth's table](https://kingbird.myphotos.cc/packing/squares_in_squares.html)
  is the maintained continuation of Erich Friedman's square packing table.
  [Friedman's old page source](https://raw.githubusercontent.com/erich-friedman/erich-friedman.github.io/master/packing/squinsqu/index.html)
  links directly to Ellsworth. SVG figures encode individual unit-square poses.
- [EvanOman/squares-in-squares](https://github.com/EvanOman/squares-in-squares)
  includes `site/data/squares.json`, pre-extracted coordinates for n<=324 and
  attribution to original discoverers. Code is MIT licensed; the actual
  mathematical packings have the separately credited provenance.
- [franciscouzo/square-packing](https://github.com/franciscouzo/square-packing)
  publishes exact rational certificates, including cases beyond n=1000 which can
  serve as crops/donors. Certificate coordinates use x,y,tan(theta/2).
- [jlevy/squares](https://github.com/jlevy/squares) maintains witnesses, current
  upper/lower bounds, methods surveys, provenance and verification grades.
- [BalthasarStrauss/Squares-packing_S-29-_New-Record](https://github.com/BalthasarStrauss/Squares-packing_S-29-_New-Record)
  publishes Schadt's 2025 n=29 packing at 105 decimal places, side approximately
  5.9338857998. The current bundled Kaggle n=29 is already smaller (~5.93383347).

## Methods behind the frontier

1. Start with explicit Göbel 45-degree strip/square constructions and literature
   packings. Close under deletion (a packing of n+1 works for n) and adding an
   L-shaped layer of axis-aligned unit squares.
2. Crop known packings into rectangular gadgets of footprint (w+f,h+f) containing
   w*h+d squares. Chain gadgets on an anti-diagonal staircase through a K by K
   grid. If the corners/joins are compatible, this packs K*K+sum(d) squares in
   side K+max(f). Use a Pareto/DP state for width, height, surplus count and corner
   availability. This is the major structural improvement beyond single gadgets.
3. Optimize angles and positions numerically using squared SAT penetration and
   wall penalties, often with L-BFGS, basin hopping and shrink/restart schedules.
   GPU populations accelerate this, but CPU optimization of a small active
   neighborhood is feasible.
4. Contact LPs compact positions at fixed angles. Sequential LP adds derivatives
   of contacts with respect to angles; band/seam angle choices help avoid poor
   contact cells. Neighbor/subset transfer changes the topology before squeezing.
5. Preserve a per-n best portfolio with attribution. The competition objective is
   separable: each side improvement contributes delta_L/sqrt(n). Validate all
   exported decimal strings with the actual official metric, whose interval
   arithmetic needs genuine separation or exactly supported contact handling.

## Independent experiments in this repository

`experiments/packing_search.py` implements a SciPy/HiGHS sequential linear
program. At each incumbent pair it selects a separating edge, constrains all four
vertices of the other square, and linearizes both centers and angles. Using all
four vertices avoids ambiguous absolute-value derivatives at matching angles.
Bounds limit steps, and every step is rechecked by SAT and legalizing center
expansion before acceptance. No external optimizer implementation is copied.

Initial tests for n=29,37,39,41,54,55,68,69,70,71,84,87,88,102,105,106,107,108,110
found no material improvement. This supports the hypothesis that those public
packings already reached local contact minima; it does not prove optimality.

`experiments/packing_transfer.py` deletes selected squares from n+1 donor
packings, screens possible compression with one LP, then fully compacts promising
deletions. Outputs under `artifacts/candidates/transfer.json` are candidates and
require independent official-metric verification before use. Logs under /tmp
record every screened puzzle. This experiment aims to change the contact topology
rather than repeatedly polish the same incumbent.

`experiments/packing_gpu_search.py` is self-contained for Kaggle/Colab and uses
batched PyTorch SAT/wall penalties, local/band/seam/neighbor-deletion kicks,
Adam quenching, float64 L-BFGS finishing, and independent float64 SAT legalization.
The optional dependency is pinned in `requirements-search.txt`; local smoke tests
used torch 2.14.1+cpu. A three-square autograd finite-difference gradcheck passed.
Bounded CPU CLI runs on n=5 and n=29 completed with positive SAT gaps, retaining
the incumbent when no better candidate was found. GPU execution remains untested
in this CPU-only machine.

## Newer public frontier: isolated tilted-core mutations

The public notebook
[cdeotte/squares-in-squares-ftmc-milp-refill-22-311](https://www.kaggle.com/code/cdeotte/squares-in-squares-ftmc-milp-refill-22-311)
reports 22.311627, improving its 22.376289 ensemble by 0.06466. Its retrieved
source explains two reasons full-puzzle local searches stall: upright grid
rattlers jam the optimizer, and multiple gadgets mask each other's gains because
the full side depends on the maximum gadget bloat.

Its proposed remedy is to optimize each rectangular gadget separately: remove
all upright squares, mutate/insert/delete/re-angle the tilted core, and refill
uprights exactly using four wall-anchored lattices plus contact-generated
staircase positions. A conflict graph of candidate upright squares is reduced
with simplicial-vertex rules, then solved as a maximum independent set by SciPy
MILP per connected component. GPU L-BFGS and sequential LP then quench the clean
refilled seeds; gadget DP propagates improvements to many full puzzles.

This is a stronger next research direction than extending the pure whole-puzzle
SLP experiment. The notebook reports 39 gadget basin changes in 7.5 minutes on
an L40S; those timings and claimed scores have not been reproduced here.

## Bounded pilot and released CUDA implementation

The independent CPU diagnostic `experiments/ftmc_cpu_pilot.py` combines the Torch
rectangle loss with `experiments/refill_search.py`. A 20-second run on published
**before** fixture 0 (3x14+4) reduced bloat from 0.97263674714 to 0.96063615448
with a positive floating-point SAT gap. This is a positive control, **not** an
improvement on the latest public geometry: its published after fixture already
achieves 0.86668669. The saved diagnostic is
`artifacts/candidates/ftmc_pilot.json`; it is not a submission.

The newer public notebook
[lightningv08/squares-in-squares-cuda-packing-search](https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search),
version 21 by Vladislav Lavrentev, releases the full CUDA FTMC/refill implementation.
Its source was parsed from the notebook's literal `SOURCES` data without executing
the notebook. The unchanged source snapshot, Apache 2.0 license, retained upstream
notices and source hashes are in `vendor/lightning_ftmc/`.

`scripts/build_ftmc_job.py` packages that snapshot and all 39 fixture pairs into a
private, internet-disabled Kaggle GPU job. The default job uses one GPU and a
600-second worker budget, plus up to 180 seconds to finish/checkpoint a batch.
It first checks CUDA analytic gradients, square/rectangle agreement, FP32 versus
FP64 evaluation, upright refill and GPU row refill. It starts from the better
published after packings, preserving before packings only as alternative basin
seeds. Each saved candidate is checked with the unchanged official metric on raw
and pandas-roundtripped coordinates; these are rectangular gadgets that still
need composition into complete puzzles before final CSV validation/submission.

The generated job is `artifacts/ftmc-pilot/`. Local Python compilation, complete
embedded-payload SHA256 verification, and the released CPU refill preflight pass.
GPU execution and numerical results are recorded separately by the root agent.

The first GPU pilot subsequently completed on Kaggle: all preflights passed,
96,584 core trials and 15,808 full quenches took 601 seconds of worker time.
It saved 154 officially checked variants across 19 improved gadget keys. For
example, the 3x14+4 gadget improved from the published after bloat 0.8666866917
to 0.8142939801. These are real gadget improvements; their competition-score
effect still depends on composition into full puzzles. Detailed results and
throughput are in `artifacts/ftmc-pilot-results/analysis.json`.

## Prepared resumed dual-T4 campaign

`artifacts/ftmc-campaign/` is prepared but has not been launched by this agent.
It requests devices 0 and 1 for 1,800 seconds each, with 128 replicas and distinct
CLI seeds 42001 and 52009. Both devices receive the same strongest published-plus-
pilot incumbent bank, including transposed improvements, plus 308 resume poses
each and 464 retained alternative poses. Reported strict gains compare against
that stronger starting bank, so resuming an old pilot win is not counted again.

The wrapper `experiments/ftmc_campaign_runtime.py` leaves the public solver code
unchanged. It adds per-device manifests, parallel supervision, an 180-second
worker grace period, a 2,400-second overall parent alarm, deduplicated official
rechecks and per-device throughput reports. Checkpoints survive a timeout. The
builder enforces source size below 1,000,000 bytes; this job is 871,359 bytes.
The nominal search uses 1.0 arithmetic GPU device-hour (30 minutes on each T4);
the hard total bound is 1.333 device-hours. Kaggle's actual quota accounting must
be read from the service rather than inferred from those arithmetic figures.

Rebuild without launching:

```sh
.venv/bin/python scripts/build_ftmc_job.py \
  --seconds 1800 --grace-seconds 180 --wall-seconds 2400 \
  --devices 0,1 --seeds 42001,52009 --replicas 128 \
  --resume artifacts/ftmc-pilot-results/artifacts/worker0_gadgets.npz \
  --slug sos54352/squares-ftmc-campaign --title 'Squares FTMC Campaign' \
  --out artifacts/ftmc-campaign
```

Local validation checks payload hashes, unchanged public source hashes, all
resumed SAT gaps, preservation of strongest transpose-equivalent incumbents,
zero false new wins from imported seeds, and rejection of an oversized source.
See `artifacts/ftmc-campaign/local_validation.json`.
