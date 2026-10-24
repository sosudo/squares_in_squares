# Full-target continuation pilot

The completed angle/capacity pilot reached 1,232 finite FP64 full packings, but
none passed the released solver's `3e-5` residual threshold. The best residual
was about 0.000463, and contact LP was never invoked. This follow-up tests whether
the forced full-packing shrink is preventing otherwise useful candidates from
becoming feasible.

The private `sos54352/squares-gentle-ftmc-pilot` bundle uses the same 17 current
active-frontier rectangle seeds on both T4 devices, with incumbent-aware angle
proposals on both arms and no full-puzzle negative controls. Device1 keeps the
public full-packing target rule. Device0 changes exactly the `ff` assignment in
an explicit runtime AST copy of the worker body. Its 16 replicas per refill use
two copies of these shrink depths:

```text
[-0.002, -0.0005, 0, 0.00001, 0.00005, 0.0002, 0.0005, 0.001]
```

Each target is `ff = f0 - depth`, where `f0` is the actual current worker
incumbent. Negative depths allow slightly larger feasible poses; positive
depths request small improvements. No source-coordinate, mutation, LP,
clearance, official raw/roundtrip, strict incumbent-improvement or novel-signature
admission rule changes. Both arms use identical banks and sampling policies with
different random streams. The adapter preserves shared module globals so the
funnel observers remain live; no sampler-cap adapter is installed.

Both workers have 300 nominal seconds, 60 seconds of finishing grace, and a
700-second parent alarm. All admitted certified variants are retained, including
novel poses that do not strictly reduce their rectangle's side, so later
composition can test their separator geometry. The experiment does not claim a
leaderboard gain merely because a relaxed target becomes feasible.

`scripts/build_gentle_ftmc_job.py` prepares a self-contained offline private job
under `artifacts/gentle-ftmc-job`. All 17 seeds passed unchanged official raw and
pandas-roundtrip checks. The initial 293,073-byte script has SHA-256
`9095a1f2fba09349390ad91e0805ace5d2ba938f4fde2c7d9e043804f30220da`.
`experiments/ftmc_gentle_targets.py` contains the target-only adapter;
`experiments/ftmc_gentle_worker.py` composes it with the angle policy and stage
observers. The parent supervisor records per-device funnels in its final
`ftmc_summary.json` and recertifies every saved output. Actual execution results
are recorded separately after completion.

## Completed pilot and retention correction

The private version1 finished in423.33seconds including supervisor output checks. Treatment retained213 certified poses, while control retained0. Treatment passed398/464finite FP64 outputs and made398LP calls and336official admissions; control passed0/728 and made no LP calls. Evidence: `artifacts/gentle-ftmc-results/analysis.json`.

The released worker overwrote a strict4x16+9 improvement under a shared coarse fingerprint with a worse geometry. The recorded improving bloat0.9326650162912387 was lost; the final same-fingerprint pose had0.9340477448559517. The final213-pose archive therefore has no strict incumbent improvement, although its valid alternative geometries can still help composition. The matched local conservative CPU composition against the refreshed82ad portfolio found zero full-puzzle improvements.

`experiments/ftmc_certified_archive.py` now retains exact immutable geometry snapshots and strict bests independently of the sampling fingerprint. Its14regression tests include the actual original raw+pandas certification function, overwrite prevention, mutation isolation, corruption/restart and final incumbent retention. `experiments/ftmc_refill_budget.py` bounds general-refill work using actual elapsed time and the feasible source's measured row deficit. These corrections will be combined with the productive target policy in the next campaign; a prepared bundle is not an executed result.
