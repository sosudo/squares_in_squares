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
