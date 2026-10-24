The new-surplus two-block composition audit completed with **no valid new
candidate**. It examined every ordered D4 pair containing at least one of the
six newly certified insertion/deletion donor types, paired with the current
primary, final focus, final soft-method and freshly verified combined-top3
banks. Both orientation orders and public join modes 0, 1 and 2 were included.

There were 444 distinct oriented pose/type variants, including 48 from the new
six-type bank. The complete search covered:

- 120,960 ordered pair/mode combinations.
- 243,552 square-container sizes after dimension/surplus screening.
- 352 pair/container combinations that could beat the current certified side
  before geometry checks.

Every one of those 352 promising combinations failed exact cross-block SAT at
the unchanged public stitch offsets. No unchecked full layout was promoted.
The entire one-worker audit finished in 2.03 seconds under an external
300-second process-group ceiling, and all coverage counters mark it complete.
This is a complete negative result for these fixed two-block choices, not a
claim about larger chains, relaxed cores or other geometries.

The suggested 5×17 +8 and 17×5 +8 construction gives n=500 in a 22×22
integer base. Its conservative side estimate is 22.872063636, already above
the incumbent's certified 22.8545909819855184, so the scalar screen correctly
rejects that example before spending time on its join.

The positive control used two classic five-square diamond motifs with a
one-cell buffered join. The unchanged public stitch constructed n=27 in the
minimum 5×5 integer base and n=38 in a 6×6 base. Full independent and official
raw/default-pandas checks passed. Three regressions cover mode dimensions,
container counts and this rotated surplus control. Independent source review
found no enumeration, dimension or acceptance blocker.

The helper is `experiments/exact_pair_composition.py`. Frozen inputs, source
modules, structured command, all coverage counters and hash-bound positive
control/supervisor evidence are retained in
`artifacts/exact-pair-composition-v1/`. At least one new-type block was required
for every pair; original input geometry and source notices remain unchanged.
The comparison baseline was raw SAT portfolio SHA256
`846ecc4acbd2194c5a43e267891aa899b9611f13cc33aba33bba1689da853931`.
No GPU job or competition submission was launched.

A subsequent independent expanded-insertion bank supplied 29 variants, and a
separate run by the validation agent found one successful two-block case:
n=599, using a new 7×20 +14 variant with the verified 16×4 +9 block and join
mode 1. That search used the same unchanged helper; its evidence is retained
in `artifacts/exact-pair-insertion-expanded-v1/`. The original six-type negative
audit remains valid for its frozen inputs.

Controlled substitution subsequently showed that older 7×20 +14 donors
reproduce the identical certified side when paired with the same stronger
4×16 +9 donor. The n=599 gain is therefore attributed to the improved 4×16 +9
geometry and expanded pair search; insertion boundary diversity was not needed.
The ablation is retained in
`artifacts/exact-pair-insertion-ablation-v1/report.json`.

The n=599 candidate was independently admitted into the immutable KMMM 28
portfolio, then fully official/raw and default-pandas transport certified.
`submission-pair-insertion-v1-safe.csv` scores **22.302014983057447**, with the
identical roundtrip score and zero invalid cases. The gain is
0.00020378660332553977; 999 exact official certificates were reused. Its SHA256
is `5e492d45f4a30185724b48fd91898cbe0cb802d2560e8b92eccdbac3480568bd`.
All 89 long-precision safety cases remain unchanged. Canonical bindings are in
`submission-pair-insertion-v1-safe.transport-validation.json`. This is a search
baseline above the user's submission ceiling; it was not submitted.
