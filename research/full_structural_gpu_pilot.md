# Full-packing GPU repair from certified structural alternatives

The CPU structural/cap controls produced 104 fully certified alternatives for
299/335/412/454 with no portfolio gain. The closest 299 starts contain 41 or 42
tilted squares versus the incumbent's 43, while remaining within 3.34e-6 side
of the incumbent. This pilot uses those complete geometries to test a different
repair mechanism. It keeps all upright filler squares and never calls FTMC
refill or applies its finite row-capacity gate.

The frozen first GPU pool contains 65 competitive n299/n335 alternatives plus
the two current reference poses, bound to
`artifacts/fq-full-structural-handoff-v1`. Every source has exact geometry hashes
and official raw/17-digit/default-pandas plus independent raw/default-pandas
interval certificates. Comparisons remain against the raw b937 per-case sides;
whole-portfolio validation remains required for any later submission.

The solver is the pinned public Lightning v21 `gpu_rect_optimizer` FP64 batched
L-BFGS, with Apache-2.0 attribution retained. Its full-N buffers are dynamically
sized; the 256-thread reduction is not a 256-square capacity limit. Spatial
neighbors refresh on every objective evaluation. The two arms use identical
source, mutation seed, loose box and target schedules:

- Exact arm: two 400-step exact-SAT loose repairs.
- Smooth arm: 400 steps at tau=0.02, then 400 at tau=0.005.
- Both: three 400-step exact tau=0 target repairs.

This smooths **absolute-value terms**, not the maximum over separating axes.
Exploratory smoothed energy is never a validity certificate. All stages are
re-evaluated with exact tau=0 before admission. The mutation copies the complete
packing and changes only explicitly tilted indices: coherent column-phase
slides, sinusoidal strip bends, or hinged strip rotations, with amplitudes
0.03/0.08/0.18/0.30. Upright rows are asserted bitwise unchanged before repair;
the subsequent full-N optimizer may move all squares. Loose box offsets are
0.015/0.04/0.08. Final contractions from the frozen current side are only
2e-6/1e-5/5e-5/2e-4. One quarter of starts use the immutable current reference,
and each operator is applied to those starts across the batch schedule.

Both GPUs must pass the live control barrier before either begins search:

1. Public finite-difference gradient/endpoint checks.
2. Actual N=299 and N=335 zero-move repairs and exact full certification.
3. Dense all-pair CPU versus GPU energy/max-penetration comparisons on those
   sizes, a last-index overlapping square, and a pair across a hash-cell edge.
4. An overlap negative must fail the full official/interval gates.
5. A mild overlap inside an expanded full packing must repair and certify.
6. An actual coherent bend of a frozen reference must repair and certify; the
   attempted amplitudes and any failed attempt remain recorded.

The CPU energy oracle matches native weighting: twice squared wall penalties
plus half the sum of squared undirected-pair penetrations, with the native
2e-10 radius margin. Local controls confirm that the coherent preflight starts
move about 1e-4 or 1e-5 and have real nonzero penetration, while preserving every
upright input row. Eight local unittest cases pass; CUDA behavior is tested only
by the mandatory live phase, not claimed from CPU tests.

Every new candidate that passes the small-clearance repair (maximum dilation
factor 1.000001) and all exact geometry gates is published as an immutable
pose/proof pair **before another optimizer stage**, including wider valid
intermediates. No top-four-only final selection is used. Near-feasible complete
poses are separately bounded and explicitly unvalidated. The supervisor
recovers completed per-pose publications even when the worker's aggregate
checkpoint was interrupted. Exact SHA keys preserve geometric diversity.

The private offline notebook uses two T4 workers, batch 32, no more than 400
steps per CUDA call, at most 600 seconds of search per worker, 900 seconds whole
notebook and a 1200-second platform timeout. The parent kills owned worker
process groups at the search deadline; Python alarms are not relied upon to
interrupt an active CUDA kernel. Per-call CUDA timings are recorded in live
preflight. There is no paid compute or automatic continuation.

Implementation: `experiments/full_structural_gpu_moves.py`,
`full_structural_gpu_worker.py`, `full_structural_gpu_runtime.py`, and
`scripts/build_full_structural_gpu_job.py`. The independent source/control
assessment is `artifacts/full-structural-gpu-review-v1/method-spec.md`.

The independent review caught a preflight retention gap before launch: control
repairs had certificates but their coordinates were not saved. The final
candidate fixes that by publishing every certified control as an immutable
pose/proof pair, plus an aggregate preflight bank with exact hash bindings.
The parent also refuses a stale prior preflight approval. Earlier unlaunched
candidate bundles remain intact.

Candidate frozen bundle: `artifacts/full-structural-gpu-job-v4/search.py`,
498,499 bytes, SHA256
`b79e6d174215379ad8033e8ae2d4b986bcca34f5355bdcc1564c82f6118683bf`.
Independent final source review passed, recorded in
`artifacts/full-structural-gpu-job-v4/independent_source_review.json`
(SHA `e3ea3c19b7eba31fee2ea5fae31e7dd70424b3a8bacfb985bda04cb81f2254ba`).
The authorized private notebook launched as
`sos54352/squares-full-packing-structural-repair-pilot/1`: Kaggle canonicalized
the title to this slug, different from the requested metadata slug. The actual
private remote source was retrieved and matched the reviewed SHA exactly;
`remote-source-proof.json` records that binding. No duplicate launch occurred.

Both devices passed every mandatory live CUDA control, and the common barrier
enabled search at 22.64 seconds. The frozen run completed its worker/collector
phase in **594.86 seconds**, without worker failure or deadline enforcement.
It retained **2,246 certified exact geometries and found zero improvements**.
Final aggregate SHA:
`ccaa71bb7f53bd55a3187eeae97885e2b6d49f462629e472f0be89d6ee40b453`.

Live timing exposed a major resource bottleneck: at about 60 seconds the exact
arm had spent 54.2 seconds certifying and 4.15 seconds in CUDA; the continuation
arm had spent 41.7 seconds certifying and 12.6 seconds in CUDA. They used paired
input schedules but reached different prefix lengths within the wall budget.
The run was kept unchanged. A separate follow-up design will save finite stages
as explicitly unverified and certify strict candidates plus a bounded diverse
subset, allowing more actual GPU search without changing final admission.
No follow-up has been launched. Terminal stage/timing and immutable archive
audits remain pending output collection at this point in the note.
