# Bounded mixed-precision and occupancy diagnostic

This is one diagnostic, not a search or native-finishing campaign. Its four
immutable B32 inputs are the first completed noninitial and final completed
proposal batches from n803/n861. Original proposal/side-vector bytes and
source packet/event/index/design bindings are preserved in private fixture
version1; the archive SHA256 is
`989ce13bcd70b43791b941a7c7a53483f6e38b72b215881126e09eaa6fc99a27`.
Side-vector hashes are checked before explicit width/height duplication; the
expanded array receives a separate hash. Fixture arrays stay read-only.

The fixed precision arms are A:2000 FP64 steps; B:1500 FP32 plus a fresh500
FP64 steps; C:1500 FP64 plus a fresh500 FP64 steps. Each of the four fixtures
receives three repeats, with orders ABC/BCA/CAB. The FP64 return always uses
the original exact FP64 boxes and new history/grid/work buffers. A versus C
separates a history restart from a precision change. All outputs remain
UNVERIFIED; ranking uses fresh dense FP64 physical energy, never stale native
residuals, and makes no feasible-side or score claim.

Corrected FP64 CUDA text is unchanged, SHA2568ccc1e355158401881545c054c53cc0e6ed1036aaec24856ca2d37b179247601.
The explicit FP32 timed port changes floating types/literals/math overloads;
stop and curvature thresholds retain their original magnitudes. Cell indexing
and radial screening alone promote the exact float-rounded coordinates to
double, preserving broad-phase coverage of physical unit-square overlaps.
The2e-10 pair margin can round away in FP32, which is used only for exploration.
Both compile with `--fmad=false`, without fast math. A separate untimed
observational FP32 kernel records accepted steps, accepted exact no-ops and
stopping information; it does not rewrite the timed optimizer body.

Runtime priority is independent FP64 controls, then FP64 B32/B64/B128 occupancy
on exact duplicated n803-early inputs, then FP32 controls and precision arms.
Input duplicates carry parent-row/copy labels; they are not extra diversity.
Initial energy/gradient row equivalence is checked, while endpoint coordinate
and energy differences are measured without assuming deterministic linked-list
summation. Any FP32 failure preserves the already durable FP64 evidence and
causes host-only partial reporting with no further CUDA calls.

Mandatory live gates cover rounded-input oracles, tied/corner/untied/wall
gradients, full counts, isolated last-index cross-cell collisions, conservative
dense coverage, nonfinite rejection and unchanged zero-step updates. Precision
control tolerances are explicitly separate from optimizer thresholds. These
actual CUDA gates have not been claimed passed by local source preparation.

Compute timing includes conversion, allocation, launch and synchronization.
CUDA-event timing is separate. Intermediate arrays are published before the
next phase; retention IO is excluded from summed compute time and included in
reported whole-pipeline wall time. The already required dense FP64 physical
evaluation has its own wall time and Torch peak allocated/reserved memory.

One GPU runs the finite schedule. A parent-epoch scheduling deadline limits
new launches; the notebook supervisor owns the only process group, a280-second
child deadline and295-second alarm within300 whole seconds/server480. Partial
coverage and omitted jobs are explicit. No timing result is a matched-wall
search comparison or evidence of convergence.

Final implementation hashes:

- `fq_mixed_precision_adapter.py`:482ee62e16fba2d4dbffbd6b26d7664f4c2f576079dfc838c1b056231692a68b.
- `fq_mixed_precision_controls.py`:fb00f522c0a8c62c1fbf767fa67ef616b197c40c0d3d549ee73bbad4556bf454.
- `fq_mixed_precision_diagnostic.py`:479f900b0288098d586893b037bec3262a49a117d236ef08d4696c5d42d62056.

Four local tests pass: exact source/threshold/screening guards, generated C++
syntax, actual frozen side-vector admission/expansion, and a mocked poisoned
FP32 context proving durable FP64 occupancy plus zero subsequent GPU calls.
No local optimizer or GPU execution was used for those tests. Frontier owns
immutable packaging; validation owns the independent final numerical review.

## Actual T4 result, 2026-10-24

The single launched notebook was
`sos54352/squares-mixed-precision-diagnostic/1`, source
`f7bfd48c5dfcb1dd16933c16d56e8fcd04fcec5864e6e61bc0582039cab2768c`.
The superseded v1 package was never launched. The actual FP64 and FP32 controls
passed, all 36 planned precision pipelines completed, and the supervisor ended
normally in 120.50 seconds. No work was omitted. All 98 retained NPZ files
(47,621,852 bytes), including controls and every intermediate, were downloaded
and checked against both archive and individual-array hashes. Reproduce the
summary with `experiments/analyze_fq_mixed_precision.py`; its bound report is
`artifacts/fq-mixed-precision-results-v1/analysis.json`.

The unchanged FP64 occupancy measurements used exact duplicated n803-early
proposals, with 2000 steps and conversion/allocation/synchronization included:

| Batch | Quench seconds | Poses/second | Dense physical seconds | Combined poses/second | Torch peak GiB |
|---|---:|---:|---:|---:|---:|
|32|2.2227|14.40|0.0884|13.85|0.850|
|64|3.4235|18.69|0.1725|17.80|1.704|
|128|6.3411|20.19|0.3468|19.14|3.387|

These are one measurement per batch size on one fixed fixture, not a repeated
throughput study across cases. The apparent quench gains are 1.30× and1.40×;
against the median of the three later B32 repeats on this fixture, B128 is
about 1.34× faster. Initial objective/gradient row-equivalence controls passed.
Optimizer endpoints were not bitwise equivalent: B64/B128 maximum coordinate
differences from the first B32 were 0.220/0.394. Their median physical-energy
ratios were 1.00246/1.00340 and 90th-percentile ratios 1.0360/1.0515. The three
unchanged B32 repeats also differed, with 90th-percentile ratios 1.0351–1.0459.
Thus the observed endpoint variation is comparable to existing optimizer
nondeterminism; it is explicitly measured, not described as exact equivalence.
Larger independent FP64 batches are the promising throughput change, subject
to actual-size memory/retention controls in any subsequent campaign.

Mixed precision did not justify production use. Across all 12 paired pipelines,
A consumed 23.384 compute seconds, B 24.759 seconds, and C 23.860 seconds. B had
higher final physical energy on 379 of 384 matched rows, median ratio 1.19266
and 90th-percentile ratio 1.97241 relative to A. C was also generally worse:
330 of 384 rows, median ratio 1.02913. All A rows used the full 2000-step budget;
most FP32 stages stopped before their 1500-step cap. This diagnostic does not
establish the cause of those early stops. The uninterrupted FP64 optimizer
remains the supported choice; neither FP32 nor splitting its history is a
demonstrated improvement. There was no native finishing, feasible-side
admission, score gain, or competition submission in this diagnostic.

Independent terminal review checked exact duplicate fixtures/row labels/counts
and nine CPU all-pair physical-energy samples, agreeing within 4.17e-17. Against
the per-row median of four B32 outputs, B64/B128 median energy ratios were
0.9986/0.9990, with no observed systematic median loss. The receipt is
`artifacts/fq-mixed-precision-review-v1/independent-occupancy-analysis.json`
(SHA256 `81a09aef42e7ac1ea0c3887a6800f01d3151653680b4d6a2267b7ffb7b30706c`).
B128 improved combined solver-plus-physical throughput by 7.54% over B64 while
using about twice the dense-evaluation memory. The final recommendation is
B128 FP64 with campaign-specific size/memory/retention controls; this remains
a throughput choice, not a demonstrated search-score improvement.

The root agent selected B64 for the subsequent twelve-case campaign. That
setting captured about 28.5% combined throughput improvement on this fixture;
the extra 7.54% from B128 was judged insufficient to justify twice the dense
memory and fewer sequential history updates per chain at fixed wall time.
This production allocation keeps the unchanged FP64 optimizer and does not
reopen the rejected FP32 treatment.
