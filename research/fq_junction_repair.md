# Full-count reconstruction of the blocked n498 junction

The bounded local reconstruction succeeded in producing valid 498-square
packings from the deliberately overlapping two-donor start, but none beat
the incumbent. Across the repair and compression passes, **33 stages were
strictly certified, producing 32 distinct geometries**. The best side is
`22.851860469001419545761143924175152137507895316019432980820697`,
about 0.02775972 above the current `22.82410074863692`. No portfolio or
competition score changed.

The first pass completed in approximately 56 seconds. It ran all 12 planned
local trials, using 18 or 40 free squares around the actual collision,
0–6% temporary global center expansion, direct pair spreading/rotation,
rigid ALM or 0.6-aspect continuation, and an unrestricted rigid release when
the resulting side was promising. It retained 16 strict stage geometries;
one release timed out. The best release was 22.85186428.

One 40-square local trial moved free squares by up to 1.62 units while
frozen surroundings changed by at most `3.6e-12` after normalization. Its
valid side was 23.47872077 before unrestricted compression. This confirms
that the collision can be repaired by a local rearrangement in the
temporarily expanded container. It does not prove such a rearrangement can
fit the incumbent's tighter side.

The follow-up used at most three certified starting layouts, selected with
a rounded-array sampling heuristic while preserving exact geometry hashes.
It tested global center compression, native square-container shrink hops,
another 40-square local aspect cycle, and critical-tip angle kicks. It
stopped within its 220-second cap after roughly 213 seconds: 17 certified
stages, 16 distinct geometries, and 12 stage timeouts. Its best side improved
only about `3.8e-6` beyond the first pass. All 13 combined timeout records
were checked for saved native outputs; none had an output to recover.

The two actual positive controls first repaired a displaced central square
in a 3×3 grid, once with fixed surrounding squares and once with a complete
soft-to-rigid return. Both passed all full geometry and transport gates in
0.64 seconds. Search, follow-up and finalization together stayed below the
authorized 300-second one-CPU budget. The native executable and every
source/option/input snapshot are pinned; each stage has an inclusive timer,
and timeout handling terminates the owned subprocess group.

All retained results preserve exactly 498 unit squares. There is no
near-best admission band: even very wide valid native repairs remain in
the audit archive. Soft results must demonstrate a monotone aspect trace
ending at exactly zero. Every admitted geometry passes official original,
numeric and ordinary-default-pandas evaluation plus independent original
and default-pandas interval validation. Native final inflation can move
nominally frozen surroundings; measured certified-output motion is reported
instead of claiming every frozen coordinate stayed fixed.

The immutable union is `artifacts/fq-junction-final-v1/`:

- `all-strict-repairs.npz`: 32 exact geometries, SHA256
  `2fe1a6106b647130aecdd8e70819ea5dd715335df80c547f99926bf289a22583`.
- `composition-eligible.npz`: 19 variants fitting a nominal `22×22+14`
  donor with excess below one, SHA256
  `256c8b414f4addff55b08a0d505929fcbf7255d1923feb248222667eded4f5d9`.
- `proofs.json`: complete strict certificates and original run/record
  bindings, SHA256
  `0a9bad7215be51ad9d85439f6e2db21dec6e37d8a5e13803dfe3b7ed974b2062`.

The union reuses certificates only for byte-identical binary64 arrays and
claims zero fresh geometry checks. Deliberately invalid starting arrays
remain separate in `fractional-junction-diagnostic-v1`; they are excluded
from both strict archives. The two original campaigns, commands, stage logs,
all parent relationships, and supervisor receipts remain in
`fq-junction-repair-v1` and `fq-junction-compress-v1`.

This was full-case joint reconstruction, separate from the remote worker's
isolated 5×17 component-corner controls. Its finite negative result concerns
these local neighborhoods, schedules, basins and runtime caps. It does not
establish that the published lower n498 side is unattainable. No remote job
or competition submission was launched by this experiment.
