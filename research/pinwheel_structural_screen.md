# Four-arm cyclic constructions

This experiment tested a macro layout absent from the current monotone-chain
composer: four rectangular blocks rotate around a central upright grid. Their
interfaces form a cycle. The public staircase DP moves monotonically right and
down along a path; its parallel-strip extension is a slicing construction. A
pinwheel therefore supplies a different adjacency graph, even though some
resulting packings might also occur in an unrelated construction family.

The frozen input was the independently reviewed502-pose partner bank at
`artifacts/targeted-partners-v2/partners.npz`, SHA
`e961ca3ac4b18d6e0ee2460cf819fef3da4f718f60c2dde7a32f26392bbb1e2c`.
It contains every417 scalar-minimum canonical family in that retained library,
the mandatory previous winning geometries, and original51 aliases. It is a
finite geometry palette, not all possible rectangular packings. The comparison
portfolio was the current certified5ec SAFE CSV, score22.301061629093095.

## Count and envelope controls

A donor with `m=wh+d` squares inside `(w+f)×(h+f)` can be repeated four times
around a `(w−h)×(w−h)` central grid, after choosing `w≥h`. The ordinary
envelope-disjoint pinwheel has

```
L = w+h+2f
N = 4(wh+d)+(w−h)^2 = (w+h)^2+4d.
```

The second fractional excess cannot be omitted: every side contains a long
dimension from one arm plus a short dimension from its neighbour. The216
eligible congruent layouts gave no headroom, even allowing deletion of squares
to compare with smaller puzzles. The best such case was still0.289866 side
units worse than the incumbent.

Directional extents were then used for two unequal opposite-arm pairs. Let
the top/bottom source have exact bounding dimensions `(a,b)` and count `mA`,
and the right/left source have length/thickness `(c,d)` and count `mB`.
The enclosing side and central hole are

```
L = max(a+d,c+b)
Cx = L−2d,  Cy = L−2b.
```

The complete constructed count includes the central grid and ordinary upright
fill in unused rectangular arm ends:

```
N = 2mA+2mB + floor(Cx)floor(Cy)
    +2 floor(L−d−a)floor(b)
    +2 floor(L−b−c)floor(d).
```

Negative core dimensions are rejected. A deliberately optimistic1e−9
integer-floor tolerance favoured the construction at near-integer boundaries;
it is not a geometry admission tolerance. All1,008,016 ordered orientation
pairs were screened, of which66,814 had feasible counts at most1000. None
improved the current portfolio. The closest normalized score deficit was
0.0095903. No constructive optimization was spent on these rejected families.
This does not rule out four unequal independent arms.

## Four interlocking interfaces

The more aggressive model moves all four envelopes inward. For a source with
actual long/short dimensions `A≥B`, choose outer side `L=A+B−t`, with
`0≤t≤1`. The top block starts at `(0,L−B)`; its clockwise rotations occupy the
other arms. Their adjacent bounding boxes may overlap, so actual square
geometry must separate all four interfaces.

A central `c×c` grid fits in the guaranteed bounding-box hole only when
`L≥2B+c`. The exact count is `N=4m+c²`; its optimistic side lower bound is

```
L_lower = max(A,A+B−1,2B+c,sqrt(N)).
```

The area term is only a necessary condition. It is not an attainable packing
certificate. This screen found152 donor/core choices with optimistic headroom.
For example, four123-square donors suggested n492 with lower bound22.18107
versus incumbent22.70711, before enforcing their interfaces.

`experiments/pinwheel_interlock.py` tested all152 choices at sides strictly
below their incumbent, with four independent reflections per arm. It evaluated
9,728 adjacent pair SAT filters, covering all256 reflection cycles per job.
Zero cycles survived. Even the best failed cycle had a substantial−0.278096
separation gap; this is not a numerical-clearance near miss. The complete
bounded run took2.53seconds on one CPU and emitted no candidates.

The filter is a floating broad-phase/SAT rejection tool, not a certificate.
Had a cycle survived, the implementation would also test every nonadjacent
arm pair and every central-grid pair, then require unchanged full official
raw/default-pandas and independent interval checks before admission. The
upright n9 pinwheel positive control passed all those gates, and a
duplicate-square negative control was rejected. No repair, GPU run, portfolio
change or competition submission occurred.

The current1,000 certified side lengths are also monotone to1e−9; the bound
report is `current-side-monotonicity.json` beside the prototype. Deleting
squares from a construction whose side already loses at its full capacity
therefore cannot rescue it against a smaller current case. This check does not
turn the finite trial-side SAT screen into a continuous impossibility proof.

Reproduce the scalar screens and bounded geometry test in fresh directories:

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python experiments/pinwheel_capacity.py \
  --bank artifacts/targeted-partners-v2/partners.npz \
  --portfolio artifacts/current-best-portfolio.json \
  --out artifacts/pinwheel-capacity-replay-v1
OPENBLAS_NUM_THREADS=1 timeout 300 .venv/bin/python experiments/pinwheel_interlock.py \
  --bank artifacts/targeted-partners-v2/partners.npz \
  --portfolio artifacts/current-best-portfolio.json \
  --out artifacts/pinwheel-interlock-v1 --seconds 290
```

The original evidence remains in `artifacts/pinwheel-screen-v1`; the
reproducible scalar replay is `artifacts/pinwheel-capacity-replay-v1/capacity.json`.
The geometry manifest, exact helper hashes, controls and every failed cycle's
best gap are under `artifacts/pinwheel-interlock-v1`. These negative results
cover the specified finite same-source cyclic model. They do not establish
optimality or rule out mixed-source arms, cuts exposing different interfaces,
or deformed and subsequently repaired layouts.
