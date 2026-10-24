# Axplorer training-data decision: two finite typed-family audits

The public source assessment and proposed native-projected residual model are
in `research/axplorer_packing_assessment.md`. No model was trained. The original
proposal suggested128 "nontrivial D4/contact groups" without specifying a
numerical grouping threshold. We interpreted the coarse geometry count as a
conservative engineering criterion and applied it consistently to both
families. This was not a precisely predeclared128-coarse-group test. In
particular, n65 has177 fine groups, exceeding128, but only15 coarse groups.
The decision to defer training considers this sensitivity and group imbalance;
it does not show that Axplorer cannot help packing or that these groups are
proven optimizer attraction basins.

| Typed family | Unit squares | Exact arrays | Within best excess+0.002 | Residual-token strings | Fine geometry groups | Coarse geometry groups |
|---|---:|---:|---:|---:|---:|---:|
|5×18+11|101|325|186|83|14|3|
|8×8+1|65|5,465|949|453|177|15|

Types were read as `(width,height,surplus)`, preserving `n=width*height+surplus`.
Opposite rectangular orientations were explicitly transposed; unrelated types
with equal n were not pooled. Each pose was aligned by D4 symmetry and exact
Hungarian assignment of unit centers. Both audits passed eight controls made
by reflecting/transposing the reference and randomly permuting its unit rows:
aligned center/angle errors were below1e-12, and the1e-4 contact signature was
unchanged.

Groups use a deterministic greedy representative cover, ordered by excess.
Every comparison repeats symmetry and unit matching. The fine
tolerances used were center RMS0.01 and angle RMS0.5degrees; coarse tolerances were
0.03 and2degrees. Contact fingerprints use all unit pairs and the maximum
separating-axis gap. The5×18+11 subset has37 distinct fingerprints at1e-4;
the8×8+1 subset has949, alongside177 fine and15 coarse geometry groups. Exact
graph counts are sensitive to small geometric changes and do not independently
establish basin diversity. These are measured, tolerance-dependent diagnostics,
not fresh feasibility proofs.

The first audit used the hash-verified combined FTMC archive and first remote
FQ certified archive. It took4.19seconds. For this family, previously successful
rigid-release stages had native medians0.90–0.96seconds,90th percentiles1.05–
1.12seconds, and median whole-stage durations2.37–2.48seconds. These successful
historical stages support a cheap projection control later; they do not
establish repair rates or latency for newly quantized model proposals.

A cheap typed inventory across four certified banks identified8×8+1 as the
clearly richest compact family:5,465 occurrences, versus1,725 across8×20+12,
1,380 across5×17+7,895 across7×19+7 and858 across6×22+16. These inventory counts
deliberately do not deduplicate cross-source or symmetric copies. Only the
richest additional family received the second geometry audit. It completed
all5,465 poses in74.22seconds on one CPU, with no optimizer, native execution,
or new certificate. Its949 near-reference poses form177 fine and15 coarse
groups. The largest coarse group contains572 poses, followed by groups of112,
79,49,44 and36. This imbalance makes a random split of individual records an
unconvincing test of generalization to materially different geometry.

Both families have known construction relevance: the historical active-chain
report uses5×18+11 at n702; the existing n65 amplification helper constructs
k²+1 descendants. Those are reasons to examine the data, not new propagation
or score claims against the latest portfolio. No new chain replay occurred.

The conservative engineering decision is to defer this learned proposal
prototype. The counts are not an impossibility result or a formal failure of
the original underspecified128-group target. A future dataset
should add materially different, competitive contact geometries and split
train/holdout by those groups. The proposed finite quantization/native control
and learned-versus-shuffled residual comparison remain applicable if that
prerequisite is met. The many stored poses remain useful exact archives; they
are simply not thousands of independent learning examples for this purpose.

Evidence and exact executed sources:

- `artifacts/axplorer-family-audit-v1/{summary,records,latencies}.json` and
  `source/audit.py`:5×18+11; source archive SHAs204eaa312767… and651ccf7ada9e….
- `artifacts/axplorer-family-audit-n65-v1/inventory.json`: all four typed source
  inventories, hashes and the numerical thresholds recorded before that
  followup. This does not resolve the original proposal's grouping ambiguity.
- `artifacts/axplorer-family-audit-n65-v1/{summary,records}.json` and
  `source/audit.py`:8×8+1; exact previously certified typed bank
  `b7f96c7c578eb45ef9f3663c4436043b93f464eb0ced888b69df564fd3408e1a`.
- Original retained-array validity and source bindings remain in
  `artifacts/combined-ftmc-results/analysis.json`,
  `artifacts/fq-remote-cpu-analysis-v1/analysis.json`, and
  `artifacts/targeted-ftmc-n65-analysis-v1/typed-bank-handoff.json`.

No source packings, old proofs, canonical portfolio or competition state were
changed by either audit.
