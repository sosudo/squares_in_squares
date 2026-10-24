<div style="background:#172634;padding:32px;border-radius:16px"><div style="color:#eab765;letter-spacing:4px;font-size:12px">SQUARECRAFT / EXPERIMENT 03</div><h1 style="color:#faf3e3;font-size:36px">Seam Surgery</h1><p style="color:#d9e6ec;font-size:18px">Find the stressed contacts. Unlock a neighbourhood. Certify the result.</p></div>

A CPU search on a frozen public portfolio, with a separate measurement of our own incremental gain. This experiment uses LP shadow prices to focus mixed-integer contact changes near stressed seams. It is a heuristic for selecting a neighbourhood, not a global packing certificate.

**Lower is better.** All 1,000 puzzle contributions are counted, with the competition grid fallback for omitted puzzles. The final exported CSV is evaluated by the unchanged official metric and again after a pandas float64 round trip.

## 1. What changed since Squarecraft II?
The public portfolio progressed from 22.408597 to approximately 22.307847. New tilted-core mutation and exact upright refill methods produce different contact graphs. We inherit those witnesses with explicit credit, then test whether contact selection can improve them further.

In Squarecraft II, binary choices were sampled at ambiguous contacts. Here a preliminary fixed-angle LP supplies constraint shadow prices. We score each candidate pair by its own pressure plus pressure on its endpoints. Half the binary budget goes to the highest scored pairs; the remainder is seeded random coverage. This targets a local contact neighbourhood while retaining exploration. Shadow prices can be unstable at degenerate optima, so no causal or optimality claim is made about this ranking.

## 2. Pinned public baseline and credit
The starting CSV is kmmmvs, **Squares Dashboard Public Batch 20261024, version 11**, native notebook version 361781862. Both version and SHA-256 are pinned. The dashboard copies its public best-validated-packings dataset without running a solver. Its aggregate quality belongs to the credited contributors and original packing authors, not to this notebook.

The published dataset's manifest, contributor table and provenance snapshots are preserved below. Earlier geometry helpers, official metric and inherited licenses are restored separately. The numeric baseline remains pinned even if the public dataset later changes.

## 3. Dual-guided contact surgery
For each nearby pair, non-overlap requires at least one separating local axis. Freezing one axis makes centre compaction a linear program. Its shadow prices measure local objective sensitivity to those frozen constraints.

We distribute these pressures to incident squares and use them to choose a bounded set of binary axis alternatives. The subsequent MILP optimizes all centres and the box side jointly. We test two trust radii and allow a small initial projection deficit on alternative axes in the second pass. Pair-specific big-M constants come from the movement bounds; a radius of $\sqrt2+2\sqrt2t$ covers all pairs that might collide. Every returned candidate is independently repaired and checked before admission.

## 4. Source provenance snapshot
The public dataset can evolve independently of the pinned notebook CSV. These files document the retrieved source snapshot; their hashes are recorded. The public baseline CSV above is always checked against its own frozen hash. No source contribution is presented as our discovery.

## 5. CPU search with stage-by-stage attribution
The baseline is freshly loaded before search. A strictly smaller enclosure is required for admission. Promising MILP candidates receive free-angle sparse LP refinement inherited from the credited CPU implementation. Improvements are transferred by subset selection and integer borders.

Fixed seeds determine sampling. Time-limited solver termination may differ across machines. Solver status, binary counts, LP status and the number of stressed contacts are recorded for every attempt. A failed attempt does not prove that no improvement exists.

## 6. Certify the actual submitted decimal strings
Unchanged puzzle rows retain their original decimal strings. Changed witnesses receive only centre dilation for a numerical safety gap, never square-size scaling. The unchanged official v17 metric evaluates each changed puzzle, with fallback to its original rows if certification fails. We then validate the whole CSV and a default pandas float64 round trip independently.

## 7. Where did the improvement come from?
The score reduction below is incremental over the pinned public portfolio. A zero gain for a stage is a valid negative result. The before/after gallery shows the largest certified improvements; if no new candidate survives, it displays representative inherited witnesses and labels them accordingly.

## Sources, credit and limits
- [kmmmvs, Squares Dashboard Public Batch 20261024 V11](https://www.kaggle.com/code/kmmmvs/squares-dashboard-public-batch-20261024?scriptVersionId=361781862): primary pinned public portfolio, SHA-256 `d62a32592633d8093299516433202e879fe5429ac8bc56b28c309e6368a28c5f`.
- [Squares in Squares Best Validated Packings](https://www.kaggle.com/datasets/kmmmvs/squares-in-squares-best-packings): source aggregation, contributor and provenance records. Its reported contributions describe adoption, not exclusive discovery.
- [Chris Deotte, FTMC & MILP Refill](https://www.kaggle.com/code/cdeotte/squares-in-squares-ftmc-milp-refill-22-311): tilted-core mutation, exact upright refill and new-basin search, incorporated in the public portfolio. This notebook does not reimplement or claim its FTMC discoveries.
- [Alex Chilton, Fault-line DP + Basin Hopping](https://www.kaggle.com/code/alexchilton/fault-line-dp-basin-hopping-lb-22-3079), [Malyshev Danil, Neighbour Transfer + Squeeze](https://www.kaggle.com/code/malyshevdanil/squares-in-squares-neighbour-transfer-squeeze) and the other contributors listed in the retained source tables: inherited portfolio lineage.
- [Our Squarecraft II](https://www.kaggle.com/code/avazaku/squarecraft-ii-unjam-the-grid-22-408597-lb): earlier joint contact-switch experiment.

- [Kirill Tymchishin, CPU Rectangular Reclosure V2](https://www.kaggle.com/code/kirilltym/22-408652-cpu-rectangular-reclosure?scriptVersionId=361218027): primary baseline, SHA-256 pinned; full L-Cut and inherited attribution included.
- [Chris Deotte, L-Cut & GPU Squeeze V1](https://www.kaggle.com/code/cdeotte/squares-in-squares-l-cut-gpu-squeeze-22-41?scriptVersionId=361208974): new rectangular L-cut constructions, inherited through the primary baseline.
- [Kirill Tymchishin, CPU Separation Graph Reclosure V8](https://www.kaggle.com/code/kirilltym/22-472940-cpu-separation-graph-reclosure?scriptVersionId=361188237): pinned public CSV, geometry and CPU refinement helpers, Apache 2.0.
- [lightningv08, CUDA Packing Search](https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search): prior contact refinement implementation; this notebook uses the credited CPU adaptation.
- [kozykappa, Subset transfer, contact refinement and compaction](https://www.kaggle.com/code/kozykappa/subset-transfer-contact-refinement-and-compaction), [Chris Deotte, Multi-Gadget Fault DP](https://www.kaggle.com/code/cdeotte/squares-in-squares-multi-gadget-fault-dp-22-48), and [Alex Chilton](https://www.kaggle.com/code/alexchilton/fault-line-dp-basin-hopping-lb-22-4776): inherited portfolio and construction lineage.
- [Francisco Couzo and original discoverers](https://github.com/franciscouzo/square-packing), [Joshua Levy and The Squares Project contributors](https://github.com/jlevy/squares), David Ellsworth, Erich Friedman and original mathematical packing authors: inherited witnesses and their per-witness notices, preserved in `source_provenance/` and `licenses/`.
- [Official competition metric V17](https://www.kaggle.com/code/metric/squares-in-squares?scriptVersionId=360167936), unchanged, Apache 2.0.

The new experiment uses LP shadow prices and neighbouring contact pressure to select mixed-integer surgery neighbourhoods, followed by inherited refinement and witness transfer. Mixed-integer disjunctive packing optimization and continuous contact optimization are established techniques; no claim is made to invent them or rediscover inherited mathematical packings. `SOURCE_NOTICES.md` preserves the complete inherited credits. The final score is not a proof of global optimality, and search budgets are finite.