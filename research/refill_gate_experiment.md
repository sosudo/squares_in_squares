# Bounded general refill after a conservative row screen

The anchor experiment demonstrated a severe full-puzzle refill bottleneck.
Over 99.97% of core quenches passed the source residual gate, yet only one of
734,016 trials produced a full refill. The whole-row routine is restricted to
two wall phases and disjoint complete rows; it cannot generally represent
staircases that occupy adjacent rows in different horizontal regions.

The public worker nevertheless skips its more general 2D refill whenever the
row count is below `N-4`. All eight known feasible full-puzzle seed cores miss
that threshold in the CPU reproduction, despite strict 2D refill reaching N.
This makes the heuristic unsuitable as a near-feasibility screen for these
full-puzzle shapes. It does not invalidate its usefulness on narrow gadgets.

`experiments/ftmc_refill_gate.py` makes an explicit AST copy of the public
worker and changes exactly that rejection condition to false. It preserves:

- At most four general refill attempts per batch.
- A 1.25-second alarm around each attempt and the existing internal solver limit.
- The core maximum-penetration threshold of 0.01 and finite-value checks.
- All quench, contact-LP, geometric and official raw/roundtrip admission checks.

Both proposed comparison arms restore the original core anchor and use the
same eight seed poses, original angle library and uniform priorities. One arm
keeps the original row gate; the other uses the bounded general fallback. They
use distinct RNG seeds and the public device-dependent mode cycle. No overflow
repair stage or gentle-depth modification is mixed into this comparison.

`experiments/ftmc_refill_gate_preflight.py` runs the actual CUDA row routine on
the unchanged seed cores, then independent strict 2D refill. Search proceeds
only if at least one missed general-refill opportunity is demonstrated. The
preflight records all counts, finite-graph optimality, array hashes and timing.
Exact-contact float results remain diagnostic and are not new submissions.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/build_refill_gate_ftmc_job.py
```

The prepared private job is `artifacts/refill-gate-ftmc-job`: 206,705 bytes,
SHA256 `a16eef1e1818b01f7b673c5164be09e321864b69754e20cf94ed75962beb8089`.
It embeds all exact search inputs and uses no network or mounted data. All
public source files remain unchanged. The existing eight raw/roundtrip seed
certificates are reused only through exact frozen payload bindings.

Each T4 has a 300-second nominal search and 60 seconds of worker grace; the
parent alarm is 700 seconds. The normal small shutdown overhead still applies.
Both arms retain all certified variants and optimizer funnel metrics. A new
observer also records general-refill calls, successes, timeouts and elapsed time.

Three tests verify the relaxed gate permits at most four attempts, retains
finite/residual exclusions, leaves disabled mode unchanged, refuses an unknown
public condition, and recognizes the exact condition in the real source.
The packaging agent has not launched this notebook or submitted to Kaggle;
read actual outputs before claiming a GPU result or score gain.

## Executed comparison

Root subsequently launched `sos54352/squares-refill-gate-pilot`, version 1. It
completed in 340.55 seconds. The actual CUDA preflight confirmed all eight
predicted misses, and independent strict 2D refill recovered every required N
with proved finite-graph optimality. The geometry/CUDA preflights passed on
both devices.

| Arm | Core trials | General 2D calls | Refilled packings | Full FP32 quenches | Full FP64 finishes | Certified candidates |
|---|---:|---:|---:|---:|---:|---:|
| Original N-4 gate | 349,056 | 44 | 0 | 0 | 0 | 0 |
| Bounded general fallback | 9,856 | 616 | 17 | 272 | 120 | 0 |

The treatment's general refill calls consumed 269.47 seconds of its 300.75
worker seconds. No calls timed out or raised errors. The relaxed gate opened
the previously blocked stage, but all 120 full FP64 results still exceeded the
3e-5 maximum-penetration gate. The best residual was 0.000970 and the worst
0.02909; none reached contact LP or official admission. No leaderboard gain
was produced.

Outputs are in `artifacts/refill-gate-ftmc-results`. Its `analysis.json` records
both arms and hashes the summary, actual GPU preflight and detailed observers.
This evidence favors improving full-packing repair before allocating a long
full-puzzle run. The source refills in a box up to `f0+.035` but immediately
quenches at least `.002` below f0. Reducing only the final shrink depth removes
little of that `.037` initial contraction; bounded continuation from a repaired
loose packing is a separate hypothesis worth testing if the gentle-depth study
does not resolve the residual barrier.
