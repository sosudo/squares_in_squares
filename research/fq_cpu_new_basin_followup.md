# Private CPU continuation of the new 8×20+12 minimum

This follow-up uses the exact certified excess `0.8736854096406326` found by
the first complementary CPU campaign. Its geometry SHA256 is
`1cb865a90232308f6becb125dd4687fb3ab37f7b35e7d7ca93a387435b41a0f9`.
The previous discovery was an incumbent continuation, not an immutable-pool
restart. Its direct full-puzzle recipe replay improved n807 and n865; component
excess gains alone are never treated as competition-score gains.

Two independent processes each reserve two CPU workers:

| Lane | Local treatment | Rigid release | Seed namespace |
| --- | --- | --- | --- |
| productive | 40 free squares, circle/contact, aspect .6 over 16 steps | Original ALM45, polish100, flip16 | 14124001 onward |
| large | 64 connected free squares, distant walls fixed, aspect .3 over 12 steps | Same original release | 15124001 onward |

Both start from the exact new minimum in both orientations. Eight distinct
certified inputs per orientation include older basins from the first CPU run
and the original donor archive. Every fourth visit to a type cycles through
the immutable initial pool by full geometry hash. Other visits use that lane's
incumbent. Every strict local intermediate and rigid result is saved before
another stage can run, including results outside the continuing-search band.

The isolated 5×17+7 corner alternative was screened out: its useful-size
outputs changed no contact edges and worsened the confirmed n498 junction.
A topology-changing output was too large. A separate full n498 joint-repair
experiment owns that interface. The chosen 64-square alternative had useful
near-reference outputs with 8–11 changed edges; it is a distinct controlled
perturbation, not a claim of an already improved minimum.

Each composite native trial shares 20 seconds; its local stage receives at
most 12 seconds. The frozen job permits 1,200 seconds of search per lane,
1,260 seconds total, and a 1,500-second explicit Kaggle server timeout. Native
groups and their owned worker descendants are stopped at the outer bound.
Complete immutable stage pairs remain authoritative after interruption.
This is one private offline CPU notebook with no GPU allocation or credentials.
Kaggle's supported accelerator-quota API does not expose remaining CPU
allowance or CPU concurrency; the prior readiness run measured four CPU cores.

The portable binary and readiness manifest are checked by exact hashes at
runtime; a notebook-version suffix is not considered a content pin. All
original source and dependency-license provenance from readiness is included.

The frozen source is `artifacts/fq-cpu-followup-job-v3/search.py`, SHA256
`82c9b8c8eb880c72a949bca9719b4e9fa5b61e7bd2b63f055b06afc9562302fa`,
246,633 bytes, with 117 checked payload files. The partial v2 packaging attempt
stopped because a credential-prefix scanner matched its own source literal;
no notebook was launched. Its 16 completed input certificates were reused
only under exact input-proof and file hashes in v3.

Actual executions of the frozen loader, sequentially at one local CPU, checked
eight trials per lane, including two immutable starts each. All 16 actual
native inputs matched their recorded parent geometries. The productive lane
retained 13 certified stages and the large lane retained 12; seven were outside
the search band and still retained. Full raw/default-pandas/interval certificate
bindings, exact-zero aspect traces, actual free counts, and release flags were
verified without repeating geometry validation. Evidence is in
`artifacts/fq-cpu-followup-job-v3/local_control_review.json`.

## Completed run and exact-chain replay

Private notebook `sos54352/squares-fq-cpu-new-basin-v2/1` completed normally in
1,199.31 seconds. Both two-worker lanes and their final collectors returned
zero; neither needed forced termination. The saved source and all 23 downloaded
aggregate/checkpoint files were verified. Evidence is under
`artifacts/fq-cpu-followup-results-v2`.

| Lane | Trials | Immutable starts | Strict retained stages | Near-reference poses |
| --- | ---: | ---: | ---: | ---: |
| productive40/.6 | 330 | 82 | 435 | 228 |
| connected64/.3 | 311 | 77 | 525 | 449 |

The productive lane recorded six whole-stage timeouts; the larger-region lane
recorded none. All 960 exact retained geometries passed the offline binding
audit, including 308 stages outside the continuing-search band. No geometry
recertification was repeated during that audit. The 677 near-reference poses
have 601 rounded diagnostic buckets, 596 absent from the initial bank; these
counts describe diversity only and do not claim distinct mathematical basins.

The best new rectangle came from the 64-square lane's rigid release, seed
15124302. Its excess is `0.8736848611346204`, an improvement of
`5.48506012165717e-7`; exact geometry SHA256 is
`a11cd7b3e9da9f5ad75a7ba1534572e9cd94f714e291c97e12116fe1ca2a9631`.
The compact selection is
`artifacts/fq-cpu-followup-analysis-v2/best_bank.npz`, SHA256
`9a6b2497369015a588438b3f6c13df3294aa9e4d16b59c9766064445aa6fc348`.
Its adjacent proof retains the complete original strict-stage certificate.
The complete union and near-reference archives remain available separately.

The reviewed offline analyzer, its serialization helper, the independent
review and every output are bound in `analysis_provenance.json`. Both real
local fixtures and ten independently constructed tamper cases passed the
review's accept/reject expectations. No running source was modified.

A subsequent one-CPU exact-chain replay took 7.67 seconds against the current
RAW `381ffdc98df53c4ba9838fdc556eeead2f62681e427039e1c25224df873e9f4c`
and its SAFE5ec ancestor. It produced fully gated improvements at n807 and
n865, with total normalized score gain `3.7923072659403104e-8`; n702 was
unchanged. Merge-ready `.17g` candidates are in
`artifacts/fq-cpu-followup-replay-v2/candidates.json`, SHA256
`fc551af27a88f703498412ad9ffbbebd0469eeefce8d0a75340851b265fab653`.
The canonical merge completed in 35.24 seconds and passed the casewise
nonregression gate. RAW, SAFE and ordinary-roundtrip checks each freshly
evaluated the two changed cases and reused 998 exactly unchanged cases.
The established safety factor was applied once from RAW to the same 89
long-decimal cases. SAFE and ordinary-roundtrip scores both equal
`22.301061591170022`, with zero invalid cases. The updated SAFE SHA256 is
`2e6e39f36a7cdf54416fd3241b2daa2d161997f235f93961f945751f0510b958`.

The durable recipe is `portfolios/candidate-2e6e39f36a7c/`. Its 493,592-byte
incremental exporter reconstructed the certified CSV exactly in 1.75 seconds
locally. Private CPU notebook
`sos54352/squares-portfolio-2e6e39f36a7c-incremental/1` then completed and its
remote CSV was hash-verified. It applies exact SAFE row patches over the
unchanged, reproducible 8cd7 parent and never reapplies safety scaling. No
competition submission was made.

The scalar improvement has plateaued. A further same-family continuation is
not justified by these results; any next use should test a measured interface
benefit from the retained geometry variants or a distinct search mechanism.
