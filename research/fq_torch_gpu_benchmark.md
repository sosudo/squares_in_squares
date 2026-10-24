# Measured T4 objective benchmark

The private benchmark `sos54352/squares-fq-torch-objective-benchmark/1`
completed in17.29seconds. All12 native fidelity gates and all36 requested
settings passed. The actual hardware was a Tesla T4 with Torch2.11.0+cu128.
No optimizer, search or submission ran.

The frozen source SHA is
`ac46cbf0902e520322fa622779b668e6d5a80c01703ac13ff8e8544f17b9af75`
(956,625bytes). Its ten payload files and66 fixture arrays are hash-bound.
All downloaded fixture bytes match the locally reviewed source. Each setting
uses actual n147/299/335 poses, radius0 or0.3, FP64 orFP32, and batch1/8/32.
Native gradient controls and device movement-bound rejection precede timing.

Each measurement warms up three times, synchronizes before and after seven
forward/backward evaluations, and resets the device peak-memory counters.
The n335 medians below aggregate the two radius-specific medians:

| Batch | FP64 T4 | FP32 T4 | FP64 local one CPU | FP32 local one CPU |
|---:|---:|---:|---:|---:|
| 1 | 3.476ms | 3.577ms | 3.103ms | 1.667ms |
| 8 | 3.761ms | 3.577ms | 12.571ms | 9.454ms |
| 32 | 3.515ms | 3.658ms | 51.466ms | 29.120ms |

The entire36-setting T4 median range is approximately3.46–4.11ms. FP64 had
no material penalty at these sizes. Batching amortizes the per-call cost;
kernel-launch overhead is a plausible explanation for the flat latency,
but this experiment does not isolate the cause. Local CPU and T4 measurements
use different machines and Torch builds; both passed the same native controls.

Peak allocated device memory was26,021,376bytes; peak reserved memory was
48,234,496bytes. The maximum FP64 native differences were2.14e-13 in energy
and2.65e-14 in any gradient entry. FP32 differences reached8.02e-5 in energy
and0.003962 in a gradient entry. FP64 is therefore the more defensible initial
precision for a small batched ALM pilot, with unchanged final geometry gates.

These are repeated shared-list objective evaluations. The timing excludes
dynamic pair-list rebuilds, pair-state transport, per-replica line searches,
optimizer history, native finishing and complete certification. It does not
demonstrate ALM convergence or a better packing. A diverse source union can
have many more pair indices than these fixtures; the next solver should use
per-replica padded lists or homogeneous cohorts and report actual counts.

The worker was limited to120seconds, its supervisor to295seconds and the
official server session to420seconds. Source, privacy, GPU configuration and
completion were independently read from the official SDK. The GPU session
is complete and no longer occupies a slot.

Reproduction builders are `scripts/build_fq_torch_benchmark_job.py` and
`experiments/fq_torch_benchmark_runtime.py`. Exact outputs are under
`artifacts/fq-torch-benchmark-results-v1/outputs`. The complete proof SHA is
`7c77b717c82df32116c3f9f5cff8680a978309b0ffbc0d951c4f0e3c5d905e87`.
The report SHA is
`3926f8e32b2278601e74b1ca0deb5ae7340659123b1dae50794c32b918f0d233`.
The separate minimal CPU/native objective derivation and MIT attribution
remain in `research/fq_torch_objective.md`.
