# Bounded angle and surplus-capacity experiment

The released CUDA upright-refill kernel reports its full row-DP capacity while
returning only the requested number of squares. Ordinary FTMC fixes the gadget's
surplus count. This experiment preserves exploratory tilted cores with capacity
above that count, then separately attempts to turn the extra capacity into
valid packings. A soft-overlap capacity is never treated as a packing proof.

The first private job, `sos54352/squares-overflow-ftmc-pilot`, uses identical
banks and sampling policies on both T4 devices: 17 current active-chain
rectangles plus complete-puzzle controls n87,129,180,300. The controls start with
eight percent of sampling mass. A common, audited runtime AST copy caps their
aggregate probability at ten percent even after visit balancing. The original
public source file remains unchanged.

Device0 uses the incumbent-aware angle library from
`experiments/ftmc_adaptive_angles.py`; device1 retains the original angle
library. Independent RNG seeds distinguish replicas. Both arms preserve the
same mutation mechanics, core positioning, archive rules and official admission
checks. Anchor restoration is a separate experiment and is not mixed into this
comparison.

Each device gets 300 nominal seconds of ordinary FTMC with capacity capture,
then up to 300 seconds repairing its best 16 diverse captured cores. The parent
allows 60 seconds of finishing grace per phase and has a 1,000-second overall
alarm. The nominal search/repair budget is one third of a device-hour total;
actual Kaggle quota accounting is inspected separately. Initial GPU preflights
include an explicit n8→n9 replay: an empty 3×3 core's capacity9 must be observed
despite output truncation at8, reconstructed at9, polished through FP32/FP64 and
contact LP, and accepted by unchanged official raw/roundtrip geometry checks.
That is a functional control, not a new record.

`experiments/ftmc_overflow_capture.py` records the absolute core geometry,
original family and mutation mode, host rectangle, fractional side, requested
and reported counts, row/column families, soft-overlap tolerance and optimizer
residual. Archives are bounded, deduplicated and explicitly marked
`exploratory_unvalidated`. A geometry hash and NPZ digest bind each manifest.
The observer preserves all original return objects and decisions. Independent
tests check family indexing, truncation, archive bounds and this status boundary.

`experiments/ftmc_overflow_repair.py` first rejects targets violating the unit
square area lower bound. It replays N+1/N+2 refill, performs full FP32 quenching,
FP64 finishing and contact LP, checks positive SAT clearance and finally runs
the unchanged official metric on raw and pandas-roundtripped coordinates.
Only accepted variants enter `overflow_repaired_device*.npz`. Useful rectangles
remain available for later composition even if they do not directly improve
their own square-count puzzle. The parent recertifies the combined ordinary
FTMC and repaired geometry, deduplicates it and exports direct improvements
separately as `overflow_full_puzzle_candidates.json`.

`experiments/ftmc_funnel_metrics.py` records numerical pass rates and residual
histograms at core FP32, full FP32, full FP64, contact LP and official admission.
This is intended to distinguish insufficient capacity from unresolved core
collisions or failed final polishing, instead of extending an unproductive arm
without knowing where it fails.

The initial bundle under `artifacts/overflow-ftmc-job` is self-contained,
private and internet-disabled, with no mounted inputs or downloads. All 21 seed
packings passed official raw and numeric-roundtrip checks. Its 35 embedded
payload hashes and all unchanged public source hashes matched. The 320,631-byte
script has SHA-256
`cf5c841b4959a43d5dfae2d6b75d65100ef99d6a72a111303937d4cf2d2bfe2c`.
All 68 tests passed at preparation; a separate executable CPU probe verified
that the sampler runtime copy retains live observer hooks through shared module
globals. The job is built by `scripts/build_overflow_ftmc_job.py`. Actual GPU
outcomes must be read from its completed outputs before claiming improvements.

## Actual first-run result

Private version1 completed in 346.3 seconds. Both T4s passed every preflight,
including the uncapped n8→n9 replay and official raw/roundtrip check. The
incumbent-angle arm produced 496 successful refills from 64,007 core trials
(0.775%); the original-angle arm produced 312 from 77,347 (0.403%). This is
evidence of a better refill rate in this pilot, not yet a leaderboard gain.

Neither arm saved a certified variant. All 1,232 full FP64 outputs were finite,
but none passed the released worker's `3e-5` residual gate. The lowest residuals
were approximately 0.000463 for the adapted arm and 0.000768 for the original.
Consequently contact LP and official admission were never called. The strong
current seeds appear to need a feasible-side continuation or near-feasible LP
repair before the worker's forced side reductions; extending the unchanged
search would not address this observed gate.

The original-angle arm recorded one exploratory overflow core, with reported
capacity three above target, but its core residual exceeded0.01. It was
correctly rejected before repair. The adapted arm recorded none. Both repair
stages therefore had zero eligible inputs and finished immediately, preserving
the remaining planned GPU time. There are no direct candidates or certified
gadget donors to merge from this run. Full output and funnel evidence is under
`artifacts/overflow-ftmc-results`, summarized by `analysis.json`.
