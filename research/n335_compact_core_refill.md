# Compact rotated-core refill screen for n335

The finite construction screen found at most **327 squares at L=18.807**, eight
short of335. It used 51.01 seconds total on one CPU. No complete335-square
candidate, new full certificate, native finish, portfolio change or submission
resulted. All raw partial layouts and finite solver results remain available.

This family was distinct from prior coverage. The earlier FTMC cold-lattice
mutation selected a thin band containing approximately the incumbent tilted
count. The n147 structural work retained a64-square diamond at n147's own box.
Neither was a complete335 construction from a compact dense square/adjacent
rectangle block. The current335 core is a sparse diagonal ribbon.

The target box has area353.703249, giving the weak area upper bound353. Purely
upright squares have exact capacity18×18=324: partition their allowed center
square into18×18 bins of width below one, each of which can contain at most one
upright center. A tilted core must therefore add at least11 net squares after
displacing upright slots. An m×n dense rotated block has bounding dimensions
approximately `m*cos(a)+n*sin(a)` and `m*sin(a)+n*cos(a)` in the positive-angle
range used here. Shape/angle combinations whose bounding box exceeded18.807
were excluded before refill. The actual constructed lattice pitch is1+4e−9,
so adjacent core squares have positive clearance.

The analytic/constructive ranking covered3,619 specifications:

- m×m and m×(m+1), m=3 through14;
- atan(1/2) and45°, each with±0.5° offsets;
- 25 centered offsets from{−.5,−.25,0,.25,.5}², plus four wall/corner anchors
  when the whole core fits;
- four independent wall-anchored upright grids, filtered against the core's
  enclosing rotated rectangle. Their counts are constructive **lower bounds**.

Thirteen overlarge shape/angle combinations were pruned. The best single-grid
construction contained322 squares. Grid ranking favored smaller cores, so the
first pass evaluated40 distinct shape/angle groups. A complementary pass used
the remaining time to cover m≥8 dense blocks at exact45°/atan(1/2), using the
best centered phase in the same finite set.

Strict `fill_rect` used `soft=0`, depth3, margin1e−9 and at most0.12 seconds per
MILP component, with a1.4-second call alarm and an outer process supervisor.
All source upright positions were only candidate hints: each was wall/SAT
filtered against the new core. One actual known five-square diamond control
passed before each pass. The two passes took24.937 and26.069 seconds, with one
CPU affinity enforced. Of61 refill attempts,58 completed and proved the optimum
on their finite candidate graphs; three calls timed out and have no count claim.
The selected complement was truncated by its declared remaining budget, leaving
three additional adjacent-rectangle groups untested.

Selected completed results:

| Dense core | Angle | Tilted count | Strict upright count | Total |
| --- | ---: | ---: | ---: | ---: |
| 8×8 | 45° | 64 | 263 | 327 |
| 8×8 | atan(1/2) | 64 | 259 | 323 |
| 10×10 | atan(1/2) | 100 | 223 | 323 |
| 13×13 | 45° | 169 | 153 | 322 |
| 13×13 | atan(1/2) | 169 | 155 | 324 |
| 14×14 | atan(1/2) | 196 | 120 | 316 |
| 8×9 | atan(1/2) | 72 | 252 | 324 |

The best output is a64-tilt,263-upright327-square **unvalidated partial packing**;
it must not be padded or relabeled as335. The optional near-feasible335 seed
routine requires at least330 strict units before attempting at most five extra
uprights with an explicit0.05 overlap ceiling. No result reached that trigger.
No partial layout was unnecessarily sent through the full official gate.

Evidence is in `artifacts/n335-compact-core-refill-v1` and
`artifacts/n335-compact-core-refill-dense-v1`. Both contain their exact executed
source snapshots, original335 decimal rows, source hashes, ranking, parameters,
raw output archives and supervisor results. The second source adds a bounded
dense-complement selection and exact Decimal comparisons for any future
certificate admission; the first executed source is preserved unchanged.

The negative optimal-capacity results apply only to the58 completed finite
candidate graphs. Ranking the other specifications did not prove an upper
bound. Neither incomplete calls nor other placements, more general compact
shapes, mixed orientations or continuous refill optima are ruled out.
