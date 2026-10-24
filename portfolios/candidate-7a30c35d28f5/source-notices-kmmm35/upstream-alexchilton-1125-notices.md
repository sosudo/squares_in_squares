# Fault-line DP + Basin Hopping

Four steps beyond merging public notebooks:

1. **Couzo's certified register.** Francisco Couzo keeps exact (rational) packings for n = 1 … 10,000 at
   [github.com/franciscouzo/square-packing](https://github.com/franciscouzo/square-packing) (MIT), many of them
   records above n = 324 that no public notebook had. We convert them and keep each one only if the official metric
   certifies it after a float64 round trip.
2. **Search.** Basin hopping with Evan Daniel's Rust engine from
   [github.com/evand/square-packing](https://github.com/evand/square-packing) (`search/packer`, MIT), started from
   our current packings of the puzzles above 324 that are still plain 0°/45° constructions.
3. **Fault-line gadget DP.** Our rebuild of Chris Deotte's composition: crops of the best packings (including the hop
   results) become gadgets along a fault between two shifted lattices, so one local improvement is reused in many n.
4. **Gadget quench.** Squeeze the gadgets themselves with Evan Daniel's smooth solver `fq` (same repository): loosen
   the gadget's box a little, nudge the squares, squeeze it again. A smaller gadget lowers every puzzle that uses it.

Builds on *Thinking Outside the Grid* (the problem, the float64 trap, the 45° family) and
*Certified Merge of Public Packings* (whose output is the starting point here).

## 0. Every known method on one page

The score is the sum over n = 1 … 1000 of L_n/√n − 1, so every puzzle counts, and a gain on a big n is worth as much
as the same relative gain on a small one. These are the methods that move it, roughly in the order they were found.
The column *here* says where this notebook uses each one.

| method | idea in one line | from | here |
|---|---|---|---|
| grid | ⌈√n⌉ × ⌈√n⌉ upright squares; the fallback for every puzzle | — | baseline |
| tilt a square (Göbel 1979) | n = k² + 1: four corner blocks plus squares turned 45° in the middle beat the next grid size | Göbel, Ellsworth's enumerator | starting point |
| record tables | best-known packings for all n ≤ 324 and some larger | Friedman, Ellsworth, Couzo | §1 |
| merge | take the smallest certified box per n from every public notebook | everyone | §3 |
| closures | delete squares from a smaller-box packing of n + k (L_n ≤ L_{n+k}); add an L of squares to n − m | standard | §3 |
| basin hopping | fix the box, minimise overlap with L-BFGS, kick, accept by Metropolis, shrink when overlap-free | Evan Daniel's `packer` | §2 |
| contact LP reclosure | freeze angles, choose a separating axis per touching pair, solve one LP for all centres and the box | Kirill, kozykappa, lightningv08 | inputs |
| fault-line gadget DP | cut good packings into w × h gadgets and chain them along a seam between two shifted lattices | Chris Deotte | §4 |
| gadget quench | squeeze the gadgets the DP uses most, then rerun the DP | this notebook, after Deotte's GPU squeeze | §4b |
| L-cuts | remove a strip from a bigger gadget and re-squeeze it into a smaller key | Chris Deotte (GPU) | not here |

And one trap that silently costs points: the metric reads the CSV as float64 and certifies with interval arithmetic,
so squares that touch *exactly* (any construction with √2 in it) fail. Every packing here is scaled by 1 + 1e-12
about its centre before it is written, which turns contacts into gaps that survive the round trip.

## 1. Couzo's witnesses

Each `.cert` file is an exact packing: the first line is `n side`, then one line per square `x y t` as rationals,
with the rotation stored as `t = tan(θ/2)` so that cos and sin stay rational. Exact packings touch exactly, which the
official metric cannot certify after float64 rounding, so `couzo.py` converts them with 40-digit arithmetic and scales
each packing by 1 + 1e-12 about its centre. Converted file: `couzo.csv` in the starter-kit dataset.

## 2. Basin hopping

`packer hop` keeps the box side fixed and minimises the total overlap (separating-axis penetration, as in the metric)
with L-BFGS. Every step it perturbs a few squares (shift, rotate, swap) and accepts the result by a Metropolis rule.
Whenever the packing becomes overlap-free it **squeezes** the box and sets the next target just below the best side
found, so a run only ever goes down.

Starting points matter: the 0°/45° constructions are rigid and symmetric, and a few minutes of hopping often finds
a slightly tilted, slightly smaller relative. We build the engine here (needs *internet on*) and run a short live
demo; the bigger runs were done offline with the same code (`hop_search.py`), results in `hop.csv`.

## 3. Merge everything

## 4. Fault-line gadget DP

Idea from Chris Deotte's *multi-gadget fault DP* notebook (his markdown describes it; his notebook ships the packings, not the code,
so `fault_dp.py` is our rebuild). Write n = K² + D. Fill the lower-left of a box with upright unit cells on the integer lattice
and the upper-right with the same lattice shifted by f in x and y. The two "continents" meet along a staircase fault running
down the anti-diagonal. Along the fault sit **gadgets**: w × h blocks that hold w·h + dm squares inside (w+f) × (h+f).
Every gadget adds dm squares; the box side is K + f, with f the largest overhang in the chain.

* **Gadgets are crops.** Take any good packing (ours, Couzo's up to n = 3500, the hop results), under each of its 8 symmetries,
  and for every (w, h, dm) keep the w·h + dm squares that stick out least past w × h: that order statistic is f.
* **Seams.** Two gadgets meet corner to corner (only if the tips cannot collide), or with one lattice column or row between them.
* **DP** over (columns used, rows used, surplus, tip type of the last gadget), minimising the largest f.
  A gadget that basin hopping improved in one puzzle is then reused in every band that can hold it.
* Each composition is certified with the official metric after the float64 round trip before it is used.

## 4b. Gadget quench

The DP only rearranges gadgets it already has, so its result is limited by how tight each gadget is.
Here we make the gadgets themselves tighter.

**Quench** is a squeeze. Take a gadget (say 7 × 17 cells holding 130 squares, sticking out by f = 0.90174),
make its box 0-4 % looser, nudge every square a little (about 0.01 in position, a fraction of a degree in angle), then
shrink the box as far as it goes without any overlap. Evan Daniel's `fq` does the shrinking: instead of pushing
overlapping squares apart, it gives every touching pair its own separating line and moves the lines too, which keeps
the problem smooth, so the optimiser does not stall at flat contacts. We repeat this from the best layout so far for
60 seconds per gadget and keep the best.

**Which gadgets.** Not all gadgets move. One built from an exact construction (f = (p + q√2)/r, e.g. Göbel's 8 × 8 + 1
at f = 0.5355) is rigid: every square is locked by contacts and every squeeze returns it unchanged. One found by a
numerical search is usually *almost* rigid: a few squares have a little slack, and a squeeze can win something.
So we target the 78 gadgets that the DP leans on most (ranked offline: lower one gadget's f by 0.005, rerun the DP, sum
the gains over all puzzles) and whose f is not such an exact value. Measured on our best file: 21 of them gave
15 smaller gadgets and +0.0015 over 29 puzzles; most of it came from long thin ones (7 × 16, 7 × 19, 5 × 18, 8 × 23).

Every improved gadget joins the DP's table; every new composition is certified with the official metric before it is used.

## 5. Official score

## 6. What we learned

* **Search rate.** A pilot of 24 construction puzzles × 5 CPU-minutes improved 4 of them, +0.000297 in total:
  about 1.5e-4 score per CPU-hour. Small per run, but there are ~220 such puzzles above n = 324 and nothing else is
  searching them.
* **The grid puzzles are not the target.** 457 puzzles are still the plain grid; for none of them is any smaller box
  known (checked against Couzo's register), and 144 are proven optimal (n = k², k² − 1 … k² − 4). They add the same
  ~7.36 to every team's score.
* **Composition multiplies search.** The fault DP turned hop results on single puzzles (e.g. n = 372, 451) into gadgets
  for larger puzzles: 47 more puzzles improved, +0.0021, from donors we already had. Re-running it on its own output
  gives +0.0002, then +0.0001: it converges in about three passes.
* **Gadgets beat puzzles.** Squeezing 21 gadgets for 60 s each gave +0.0015, about 0.004 score per CPU-hour:
  30-50 times what basin hopping on whole puzzles gives, because each gadget is reused across many puzzles.
* **Rigid gadgets do not move.** The biggest levers (8 × 8 + 1, 12 × 12 + 4, 16 × 16 + 9) are exact constructions;
  a squeeze returns them unchanged. Improving those needs a new construction, not more search.
* **What decides the leaderboard**: syncing new public records quickly (ties go to the earliest submission) and
  search on the non-grid puzzles above 324.

**What did not work** (measured on our files; each is a null, so you can skip it):

| tried | result |
|---|---|
| quench on exact-construction gadgets (8 × 8 + 1, 12 × 12 + 4, 16 × 16 + 9) | 0: they are rigid, every squeeze returns them unchanged |
| "cushion shift": move a gadget with f < F up or right inside its slot so more seams need no buffer | 0 gain at five values of F; chains above n = 324 have room for buffer seams |
| synthetic tilted-block gadgets (a turned a × b block in an upright grid) | 0.14 to 0.29 worse in f than cropped gadgets |
| a local LLM (30B coder) writing gadget constructors, then gadget searches | 0 new gadgets in about 1,600 programs; the plain squeeze loop it was meant to beat found them |

**Public notebooks whose outputs this notebook merges** (their packings are most of the score; thank you):

* [Кирилл Тымчишин (kirilltym)](https://www.kaggle.com/kirilltym): the contact-LP reclosure series (separation-graph, seam LP,
  donor LP, wide LP): fixed-angle LPs over separating axes that move whole rows of squares at once.
* [Vladislav Lavrentev (lightningv08)](https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search):
  CUDA packing search, deletion starts from neighbouring n, and the Apache-2.0 contact-polish code many notebooks build on.
* [Chris Deotte (cdeotte)](https://www.kaggle.com/cdeotte): multi-gadget fault DP, L-cut gadgets and GPU squeezing, and the ensemble.
* [Malyshev Danil (malyshevdanil)](https://www.kaggle.com/malyshevdanil): fresh certified records and neighbour transfer + squeeze.
* [kozykappa](https://www.kaggle.com/code/kozykappa/subset-transfer-contact-refinement-and-compaction): subset transfer, contact refinement and compaction.
* [SeshuRaju (seshurajup)](https://www.kaggle.com/seshurajup), [yuki16](https://www.kaggle.com/yuki16),
  [aqibrazadev](https://www.kaggle.com/aqibrazadev), [dariushafshar](https://www.kaggle.com/dariushafshar): ensembles, merges and validators.

*Credits: Chris Deotte (the fault-line gadget idea, and ranking gadgets by DP leverage), Francisco Couzo (certified register), Evan Daniel and contributors (evand/square-packing, packer and fq engines),
David Ellsworth (records, enumerator), Erich Friedman's survey, and the public notebooks merged in the starting point.
If this helped, an upvote is appreciated.*