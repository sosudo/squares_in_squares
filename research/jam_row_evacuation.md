# Why native jam-row detection is inactive on n335

The current layout contains 291 near-axis squares and 44 tilted squares. In
every width-one center band tested by the native detector, the largest row or
column population is 18. The detector requires `floor(side)+1`, which is 19 at
the incumbent side18.822875655579203 and at targets18.807/18.803. It therefore
returns no lines on this source. This is an overfilled-band heuristic, not a
detector of every dense contact row. Reducing the numerical angle tolerance
would not fix this population mismatch.

The source uses `PI2 = FRAC_PI_2`; angles are radians modulo a quarter turn.
The axis filter is `min(a, PI2-a) < .02` (about1.146degrees). For each eligible
center it examines bands centered at that coordinate minus.45, unchanged,
and plus.45, with strict half-width.5. There is no degrees/radians or
quarter-turn convention error in this detector.

Even when a line is found, native kind8 picks only one member, then either
relocates it to the lowest-penalty of300 sampled poses or tilts it in place.
With no line it applies the same operation to its fallback center. Neither
branch evacuates an entire row. The original459-proposal pilot's47 kind8
attempts all had zero detected parent lines; its15 accepted kind8 moves
therefore do not demonstrate row evacuation. See
`artifacts/packer-hop-335-v1/jam-line-check.json` and
`research/packer_hop_pilot.md`.

A fresh read-only pass also checked every one of those47 actual parent
states, verifying each saved parent SHA before reading it. They contained
290 or291 near-axis units, and the largest tested band still contained
exactly18 in every case. This closes the connection between the current
geometry diagnosis and the original operator telemetry. The supplemental
record is `artifacts/jam-row-evacuation-v1/native-parent-audit.json`, SHA256
`c86688b932f9ea113874596909785cbfafd17f8c5d56704d748f2586a3933980`.

## Exact source and controls

The detector comes from Evan Daniel's MIT `packer`, public commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`, original source
`artifacts/packer-hop-335-v1-source/original-main.rs`, SHA256
`f17683199f75af1e1489680bfc69ae38991998fe112e723ed648507ff6ff725e`.
The vendor source is unchanged.

`experiments/analyze_jam_row_evacuation.py` extracts the actual two native
functions into a small Rust comparator. Native and Python results agree for
the current335 at all three box sides, an18-unit control, an overfilled
19-unit control, quarter-turn equivalence, and angles.019/.021radians on
either side of the filter. Source, compiler command, comparator executable,
exact control input, original decimal335 rows and array hashes are retained
under `artifacts/jam-row-evacuation-v1/`.

The current raw portfolio used here is `artifacts/merged-public-v29.csv`,
SHA256 `a0dad731adc6cacc9c882082aaf9464c7c7fc755ce4eabba6f711b1c31b969bc`.
The source report, canonical pointer and exact binary64 conversion are bound
in the audit. Eight native controls and the construction experiment finished
in1.64seconds wall /1.05seconds Python CPU, including native compilation.
No optimizer or remote job was part of that construction run.

## A genuine whole-row construction

The separate raw proposal bank removes all18 members of the densest narrow
horizontal row or vertical column, then constructively reinserts every
member. Every proposal changes exactly those18 rows; the other317 binary64
poses remain byte-identical. There are two constructions, each with both
rotation signs and both row directions:

- An18-unit straight train with every square tilted14degrees. Adjacent
  centers are separated by `sec(theta)*(1+1e-10)` along the train axis.
- A17-unit train tilted22.5degrees, plus the18th unit reinserted outside the
  old strip at the lowest dense-SAT penalty in a fixed32x32x4 pose palette.
  That finite insertion minimizes overlap; it does not promise an empty hole.

For a train of `m` squares, each at angle `theta` to its center axis, its
envelope is

```
width  = (m-1)*(1+1e-10)/cos(theta) + cos(theta) + abs(sin(theta))
height = cos(theta) + abs(sin(theta))
```

The adjacent center projection on each square's rotated major axis is
strictly greater than1. Nonadjacent projections are larger, so the train
itself is nonoverlapping. This is not a rigid cluster rotation: the centers
remain on a straight row/column while every unit rotates and the spacing
changes. The18-unit envelope is18.7326493 by1.2122176; the17-unit envelope is
18.6248382 by1.3065630. Both fit inside18.807, and the train is placed inside
the walls. Existing background units are unchanged and may still protrude
from that tighter diagnostic box.

The four-axis all-pair check includes all55,945 unordered pairs and all
1,340 wall inequalities. It reports physical energy0.982428–1.888966 for
these proposals, versus0.00836726 for the unquenched original at18.807.
The extra energy comes from background interfaces, including the off-strip
insertion. These are deliberately large, high-barrier changes, not valid
packings or evidence of a new achievable side.

All eight full335 arrays are preserved as **UNVERIFIED RAW** in
`artifacts/jam-row-evacuation-v1/raw_states.npz`, SHA256
`13554a44ba81d924b57d83917d7cddc1464d598b16502342bebf8db9b784528c`.
The report pins every selectedID, actual changedID, hole candidate, array
hash, train envelope and physical diagnostic. Independent read-only review
reproduced the dense energies within1e-12 and confirmed all counts and
unchanged rows. No canonical portfolio or active GPU pilot was changed.

## Bounded native repair probe

A separately authorized one-CPU probe uses four source-diverse variants:
row+14degrees, column-14degrees, row-22.5degrees with off-strip insertion,
and column+22.5degrees with off-strip insertion. The unchanged pinned FQ
binary uses requested radius.49, twelve linear return steps, no additional
initial kick, actual parent-box hold, and then rigid ALM45/contact polish100.
The first scheduled relaxed radius is.4491667 and the last is exactly0.
The native trace and reported held side are checked before admission.

The held box is the raw initializer's physical envelope near18.82287566,
not its tighter18.807 diagnostic target. Each trial includes native work
and complete raw/default-pandas/independent validation inside16seconds;
the whole process has an80second cap. Every fully certified terminal pose
is retained even if worse than the incumbent. Exact source and helper hashes,
commands, partial logs, raw outputs and certificates are kept in
`artifacts/fq-jam-row-repair-v1/`. Results are recorded there; no raw span or
optimizer side is interpreted as a feasible packing.

The probe completed in32.58seconds inclusive, with all four terminals fully
certified. Every trace contains twelve actual radius steps, first0.4492
(native rounded display), last0 exactly. The longest inclusive trial took
10.04seconds. None improved the canonical side18.822875655579203.

| Construction | Certified side | Units tilted over1degree | D4-matched RMS vs current | RMS vs43-tilt source | RMS vs37-tilt source |
|---|---:|---:|---:|---:|---:|
| Row+14degrees | 18.822896875764 | 44 | .036691 | .034728 | .467548 |
| Column-14degrees | 18.823755545773 | 45 | .036529 | .034047 | .472644 |
| Row17+hole, -22.5degrees | 18.885618118950 | 48 | .202115 | .201649 | .468582 |
| Column17+hole, +22.5degrees | 18.881135083676 | 49 | .224072 | .229576 | .460903 |

The column-14degree result has25 matched angles changed by more than1degree
versus current, maximum matched angle change10.485degrees and maximum
axis-relative tilt39.483degrees. Its angle histogram over
`[0,.01,.1,1,5,10,20,30,45]`degrees is
`[133,149,8,0,1,0,33,11]`. This is a measured alternative geometry close to
the current and43-tilt sources, not evidence of a distinct topological basin.
The two off-strip insertions induce larger geometric changes but lose
substantially more density after repair. The four finite trials do not
support an unchanged extension.

All four certified terminal arrays, including both outputs outside the
usual near-reference search band, are retained in
`artifacts/fq-jam-row-repair-v1/remote-certified/donors.npz`, SHA256
`99cbc624fbb197ea7b7dd853e140cfa11278e6f38755ad39556d9980e837658f`.
Its provenance SHA256 is
`c8decf2d7e789e84bdf127e8c5a41f4f4ad99b60267c342f8e497ecf89d1db74`.
`experiments/review_jam_row_repair.py` separately checked exact input text,
native outputs, legalized arrays, decimal certificate hashes, complete
radius traces and held-side identity before computing the diagnostics.
That1.83second read-only review reused the four completed certificates;
it performed no optimization or fresh certification. Receipt:
`artifacts/fq-jam-row-repair-v1/lineage-and-geometry-review.json`, SHA256
`59ba2b71d9077105226cfa90b37851bdc3cb5cf8852ce12684c929954871549b`.
