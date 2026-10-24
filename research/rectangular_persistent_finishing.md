`experiments/fq_rectangular_persistent_finish.py` owns only the native finishing
and rectangular donor proof for the separate four-family persistent campaign.
The search runtime, device controls, frozen input selection and launch belong to
their respective owners. No GPU or native search was launched while developing
this helper.

Each family supplies 64 committed full-unit states, four cuts and four immutable
source identities. Recovery binds either a sampled terminal packet or the exact
durable head, including every member hash, configuration, chain design and final
archive. The loader requires the selected state members to match byte for byte.
It makes no claim that unsampled transitions can be independently replayed.

Eight finishing slots are fixed before work: minimum BEST physical energy and
one distinct near-best coarse-diverse BEST state for each cut. The diversity
measure uses unit-order-invariant occupancy/angle histograms and the four D2
reflections that preserve the ordered rectangle. It excludes exact duplicate
poses, records zero-distance cases and fallback choices, and makes no topology
claim. Empty or deadline-skipped slots are not reassigned to other cuts.

Two native workers use the pinned `10ec7cf7…` binary and the reviewed `aab5ea32…`
subprocess/parser/full-gate helpers. All slots use seed 9710000 and
`--loosen 1 --outer 45 --pit 100 --flip-top 16`, with at most 60 seconds of native
work and 8 seconds for decoding and certificates. Encoding uses the actual
integer rectangle `(w,h)`, with offsets `(w-min(w,h), h-min(w,h))`. The encoded
physical enclosure and returned native box are recorded explicitly; native
finishing does not promise to preserve the tighter GPU target box.

Every returned decimal native file is retained before decoding. A complete
official raw/17-digit-pandas/default-pandas and independent interval certificate
is saved before the extra rectangular proof. Thus a rectangle-proof timeout,
exception or excess of at least one cannot discard a valid full-unit packing.
`certified.npz` retains all such packings; `rectangular-donors.npz` includes only
those with a successful subunit rectangular excess bound.

The rectangle proof separately encloses width and height using interval
arithmetic on the exact three decimal transports. It computes
`f = max(width-w, height-h)` and takes the worst upper bound across transports.
The existing bounding-square side is insufficient for this purpose. A component
improvement requires this upper bound to be below the immutable reference's
lower bound. It is not a full-portfolio score gain; exact downstream composition
and the usual portfolio gates remain necessary.

Focused unittest controls cover both-axis enclosure, rotated-unit bounds,
translation and D2 symmetry, fixed-cut selection and duplicate exclusion, exact
recovery tampering/path containment, actual rectangular native offsets and
constant seed, and preservation of a fully certified geometry when the extra
rectangle proof times out. Solver calls are mocked in those finishing controls.

The final helper SHA is `47d391ec9541f70313451c55036702a21c6a8562dc75a75f7ba09d67a50d75b9`.
Eight focused tests pass, including a timeout at the first certificate publication
before the rectangle proof begins. Independent review is
`artifacts/rectangular-finisher-independent-review-v1/review.json` (SHA
`1c2f4afd7234e1d644ed57fe4ca4aba6f4a5f1763c2267c919738b88faa32815`).

Four separately authorized exact original-reference controls completed in 3.43
seconds, with all four full-unit and rectangular certificates passing. They used
the frozen v2 seed0 arrays and exact prepared native input text; only the
per-slot initializer-status description changed, explicitly identifying an
original control rather than a GPU state. Numeric options, seed and rectangle
offsets stayed identical. Their separate source is
`experiments/fq_rectangular_reference_controls.py`, with inputs, source snapshots,
native output bytes and all four donor poses in
`artifacts/fq-rectangular-reference-controls-v1/`.

The 5×17+7, 7×19+13 and 7×20+14 controls did not improve their frozen excess
bounds. The 8×21+13 control improved by only 4.63170524e-8, with conservative
`f_upper=0.882903514033625473062062225451076604407611621617628598194867`.
This is not a portfolio gain or evidence of a structural change. Its better
comparison bound must nevertheless be included when judging later search
outputs, even if the exact GPU seed arrays remain unchanged. The control's full
three-transport lower/upper bounds and geometry are in
`trials/slot-03-original_reference.certificate.json` and its adjacent certified
NPZ. The all-four archive SHA is
`5482ea534fb0b51f8ab15c32e5dcab701e39743b382c5403fb80c810f8e5f198`.

Control completion proof `748e36f1c09d4f47591097a43bca14865b4c32ed3bf0f055be1455200e24dfb6`
and independent review
`artifacts/rectangular-reference-independent-review-v1/review.json` (SHA
`93440ff53cd0bf4443695343fa9cfc4f886beedd1042b308b67d1800806cc08c`)
bind all exact inputs, source-only clone difference, commands and returned-pose
certificate links. No further local optimization or GPU launch followed in this
lane.
