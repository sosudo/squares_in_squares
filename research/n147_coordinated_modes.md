# Coordinated nonuniform deformation of the n147 diamond

This finite structural lane found **no certified improvement**. It completed
76 prescribed pattern/shear LP trials and six deterministic native finishes.
The exact current side remained **12.656854249504036**. The dated public value
12.651043553627 was only a target; no corresponding coordinates were accessed.

## Family and mathematical rationale

The source contains 64 unit squares on an 8×8 diamond lattice at 45 degrees,
plus 83 upright squares. Its lattice directions are
`u=(1,-1)/sqrt(2)` and `v=(1,1)/sqrt(2)`. Parallel core rows have tangential
phase freedoms: translating alternating rows by ±0.3 along their tangent
leaves the core-only minimum SAT gap positive, about `9.98e-13`, while it can
change contacts with the upright frame. A duplicated-square negative control
is correctly detected. No initial full-layout validity is claimed for these
structured warm states.

The tested families were opposite rotations of two 4×8 half-cores along each
lattice direction, four checkerboard 4×4 quadrants, and alternating whole rows
or columns. Each group is rotated rigidly about its own centroid and receives
a coordinated tangential translation; internal group distances are checked to
1e-12. The main arm also counter-rotates the 20 immediate upright/core interface
neighbors by 15% of their nearest core group's angle. This changes the frame
angles that the preceding uniform-angle LP kept fixed. It does not use random
independent square kicks, deletion or uniform whole-core rotation.

The finite matrix has 60 coupled trials: five families, core offsets
±0.5/±1.5/±4 degrees and tangential shear 0 or 0.3. Twelve half-core/quadrant
controls omit the frame-angle coupling. Four zero-angle row/column phase
trials test changed registrations independently of prescribed rotation.

All 294 center coordinates are LP variables within ±0.7 of each structured
warm position. Angles are prescribed exactly per trial; square supports are
recomputed at those angles, rather than linearizing a rotation. Each LP has
all four walls and unit-square separating-axis constraints. The 188 source
multi-axis corner contacts are provisionally omitted; every actually violated
pair gets its true SAT disjunct restored from the coherent warm registration.
Every result receives a fresh full 10,731-pair numerical screen. Six cut rounds
are allowed. This is a finite local branch/trust model, not a global packing
optimality proof.

## Control diagnosis retained

The first invocation stopped in 4.14 seconds before any exploration because
its reproduction assertion failed. Geometry validation itself passed: greedy
corner-cut choices from an arbitrary provisional overlapping LP placement led
to a valid but wider side **12.937184358135386**. The replay trace and exact
source/raw/repaired arrays and certificate are preserved under
`artifacts/n147-coordinated-control-diagnosis-v1`.

The corrected matched positive control uses all source branches and recovers
the reference within numerical clearance. Exploratory restored cuts use the
disjunct selected from the structured warm start, avoiding arbitrary extreme
provisional placements choosing the corner registration. No metric, strict
geometry gate or improvement criterion was relaxed. Both executed source
versions and the original stopped-run evidence remain preserved.

## Completed result

The corrected run completed in **21.85 seconds total**, with one worker and
no outer kill. Including the earlier stop and short diagnostic replay remains
well below the authorized 90-second CPU bound. All 76 prescriptions ran;
74 raw LP states were retained, 62 passed the full numerical SAT/wall screen,
and all six selected native ALM45/polish100 finishes passed fresh official
raw/default-pandas and independent interval gates. No random native kick was
used. Best raw LP side was **12.656854272139418**, still above the reference.

| Nonzero-angle family | Best numerically feasible LP side |
| --- | ---: |
| Opposed row half-cores | 12.677617845601965 |
| Opposed column half-cores | 12.671933952799968 |
| Checkerboard quadrants | 12.669113861749096 |
| Alternating rows | 12.697166369046473 |
| Alternating columns | 12.697166369046482 |

The native results are not all numerical returns to the same coordinates:
five have seven squares departing from 0/45 degrees by more than 0.001 radians;
maximum departures range from 0.50 to 3.42 degrees. Their D4-assignment center
RMS distance from the source ranges from 0.0347 to 0.0687. These valid changed
starts remain slightly wider because of the numerical clearance/bottleneck.
They are retained without a score claim or unchanged continuation.

Evidence is under `artifacts/n147-coordinated-modes-v2`: `raw/`,
`raw-lp-states.npz`, `lp-results.json`, `certified-native.npz`,
`native-certificates.json`, `structural-diagnostics.json`, source snapshots
and the supervisor receipt. Manifest SHA256 is
`ef49bd288c9add5418db5a0642c729606be68940ac69eda4670b1f2807bfb06e`;
LP results SHA256 is
`e0abe1227d1f9bc0ba6d23bb3aa3bf3523a846f042baeacad4606f2b11e57aed`.
The raw portfolio input is pinned by its official report and CSV hash in the
manifest. Native FQ is the existing MIT-licensed Evan Daniel source commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`, binary SHA256
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.

Source scope was local, already available material: the previous uniform-core
LP and n148-deletion study, plus Evan Daniel's `analysis/contactswitch.py` and
`analysis/melt_junction.py` diagnostics about changed contacts and junctions.
Those diagnostic scripts were read, not executed or presented as a released
n147 solution. No GPU job, canonical mutation or submission occurred.
