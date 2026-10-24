# Bounded finishing for cold full-packing transfer

`experiments/fq_cold_hop_finish.py` provides
`finish_case(root: Path, case_config: dict, deadline: float) -> summary` for
the authorized n803/n861 cold transfer. It imports the exact previously
reviewed aab5ea32 terminal helper; the helper source, native binary, numeric
flags and raw/default-pandas/independent interval gates remain unchanged.
Only process-local native/certificate caps are set to sixty/eight seconds.

Each case has two fixed boxes, reference side minus0.002 and minus0.008,
sixteen chains per box. The first finishing slot takes minimum committed
BEST energy. A second slot selects the largest coarse D4 spatial/angle
histogram distance among states with energy at most
`max(4*minimum_energy, minimum_energy+1e-8)`. Ties use lower energy then chain
ID. If the band contains no alternative, the next-lowest-energy state is an
explicit fallback. Exact geometry-SHA duplicates of the first state are
excluded; if no distinct bytes remain, the second slot is skipped without
reallocation. Different bytes with histogram distance zero remain eligible,
with no positive diversity claim.

The diagnostic uses normalized8×8 spatial cells and eight folded-angle bins,
counts independent of unit row order, and minimum L2 distance over both
eight-image D4 orbits about the fixed box. Diagnostic bin boundaries are
rounded to twelve decimals. Retained coordinates are never rounded by this
diagnostic. Histogram diversity does not prove distinct contact topology or
optimizer basins.

All five recovered final arrays must match the exact last completed packet,
its per-array hashes and design. Every row must belong to the current case,
its common source key and cold arm; fixed box values are bound to the exact
reference-minus-delta calculation. All four selected raw poses are saved
before any native job is submitted, including slots later skipped for time.

Two fork workers run each case's at most four finishes. Full sixty-second
native plus eight-second gate allowances require at most two waves, about
136 seconds plus bounded setup/publication; the caller must allocate this
within its900-second whole supervisor. Every native timeout is also limited
by the absolute caller deadline. Native children stay in the caller's bounded
process group. A failed future produces an explicit finish_error record with
preserved artifact hashes; other fixed slots continue, with no retry or
adaptive budget transfer. Every full-certified result, including worse
scalars, is retained and compared using the worst of the five certified raw
and transport sides.

Frozen source SHA256:
`17f0fdf314fbe652f193e76b4101c1e14e688a0632642bd7b180f695959aafb9`.
The only new local import is the existing `fq_restart_hop_finish` module.
No local optimizer or GPU launch was used to prepare this helper. Anchor owns
the new driver, frontier the immutable packaging, and validation the narrow
independent selection/retention tests and final review.
