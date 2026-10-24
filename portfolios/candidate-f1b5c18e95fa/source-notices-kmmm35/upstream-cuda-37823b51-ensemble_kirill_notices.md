# Seam LP: CPU / CUDA / MPS + Packing EDA

Frozen primary baseline: Vladislav Lavrentev (lightningv08), Squares in Squares | CUDA Packing Search, version 13, native 361296742.
https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search?scriptVersionId=361296742
CSV SHA256 ce991f2abcfeb3ed0abfe20ea022cea43470f9a916985f623f1cebf2d5dce1cc.
V13 incorporates our V5 witnesses, complementary Janus D4 witnesses, coherent CUDA restarts, bounded graph changes and donor recomposition. Its numerical coordinates are inherited and credited in full. The exact V13 source notices and supporting reports are retained under source_provenance/.

Our increment rebuilds valid separation-axis graphs on the refreshed V13 witnesses and alternates centre compaction with free-angle contact refinement on the strongest new opportunities. A separate ten-puzzle pilot of sampled binary contact switching, inspired by Squarecraft II, produced no material admitted gain; that negative control is retained and is not credited with the result. The portable exploratory implementation offers CPU/CUDA/MPS tensor proposals, with exact CPU geometry, LP and official certification in all modes. CPU implementation and gradients were tested in the prior V5 release; CUDA/MPS remain configured but not hardware-tested. This release's new measured improvement comes from CPU graph and contact LP, not a GPU experiment.

The default run restores pinned inputs and fixed-point new witnesses, then freshly certifies raw decimals and a default pandas float64 round trip. RUN_SEARCH enables optional recomputation on the selected backend. MPS requires a local Mac and is unavailable on Kaggle. Square side lengths stay one; only centres move for numerical clearance. No optimality or algorithm-invention claim is made.

## V13 source credits (including its acknowledgement of our V4 witnesses)

## Sources and limits

* [Kirill Tymchishin — Seam LP V5](https://www.kaggle.com/code/kirilltym/22-3856-cpu-cuda-mps-eda-seam-lp?scriptVersionId=361279753): eight imported numerical improvements, randomized graph reclosure, tangential seam-kick idea and credited CPU refinement helpers.
* [Janus — D4 Seam DP / Dual GPU L-BFGS](https://www.kaggle.com/code/jiwasawa/squares-in-squares-d4-seam-dp-dual-gpu-lbfgs): individually imported witnesses and a contraction-ladder experiment extending this notebook's earlier CUDA optimizer. His original discoverer credits remain applicable.
* [avazaku — Squarecraft II](https://www.kaggle.com/code/avazaku/squarecraft-ii-unjam-the-grid-22-408597-lb): binary contact switching and near-valid alternate axes.
* [Chris Deotte — Multi-Gadget Fault DP](https://www.kaggle.com/code/cdeotte/squares-in-squares-multi-gadget-fault-dp-22-48) and [L-Cut & GPU Squeeze](https://www.kaggle.com/code/cdeotte/squares-in-squares-l-cut-gpu-squeeze-22-41): fault composition and rectangular donor construction.
* [Alex Chilton — Basin Hopping](https://www.kaggle.com/code/alexchilton/fault-line-dp-basin-hopping-lb-22-3945), [Dariush Afshar — Certified Packings](https://www.kaggle.com/datasets/dariushafshar/squares-in-squares-certified-packings/versions/8), Kozykappa, Prvsiyan, SeshuRaju and Malyshev Danil: inherited public portfolio and source lineage, retained in the checked notices.
* [Francisco Couzo and original discoverers](https://github.com/franciscouzo/square-packing), [Evan Daniel](https://github.com/evand/square-packing), [Joshua Levy and contributors](https://github.com/jlevy/squares), Darius Muglich (CC BY 4.0) and the per-witness authors retain their credits and licenses. No inherited mathematical discovery is attributed to this implementation.
* [Official metric v17](https://www.kaggle.com/code/metric/squares-in-squares?scriptVersionId=360167936), unchanged, Apache 2.0. Full notices: `contact_SOURCE_NOTICES.md`, `contact_kirill_notices.md` and prior Layout Atlas records.

Finite restarts, bounded contact choices and conservative composition profiles do not establish an optimum. Default replay is deterministic; additional time-limited search may differ. GPU proposals use float64 here, but floating-point feasibility alone is never a submission certificate.

## Prior portfolio notices

# Seam LP: CPU / CUDA / MPS + Packing EDA

Frozen primary baseline: Vladislav Lavrentev (lightningv08), Squares in Squares | CUDA Packing Search, version 11, native 361263594.
https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search?scriptVersionId=361263594
CSV SHA256 222c09b403701a80c228f22faee1def58a3288c9c5960408ce17fea9a52843be.
V11's new rectangular blocks, cushion joins and occupied-tip profiles are credited to lightningv08 and the mathematical/source authors cited below. The much larger inherited packing quality is distinguished from our incremental seam LP and contact refinement gain. The exact V11 source notices, Layout Atlas README, Dariush Afshar's compilation README and public source map are retained in source_provenance/.

Our increment rebuilds valid separation-axis graphs on the new V11 witnesses, compacts centres with a bounded LP, alternates free-angle contact refinement and tests complete translated-window propagation. The portable exploratory stage implements coherent tangential seam kicks and batched soft SAT pressure with PyTorch. Its cpu/cuda/mps modes share the tensor operations; CPU float64 SAT, LP polishing and the unchanged official metric decide admission in every mode. This hybrid split is explicit. CUDA and MPS are configured but not hardware-tested in this release. CPU was tested locally, including independent finite-difference gradient checks and a real recomputation/official-admission test. No GPU or MPS was used for our local result.

The default run restores pinned inputs and fixed-point new witnesses, then freshly certifies raw decimals and a default pandas float64 round trip. RUN_SEARCH enables optional recomputation on the selected backend. MPS requires a local Mac and is unavailable on Kaggle. Square side lengths stay one; only centres move for numerical clearance. No optimality or algorithm-invention claim is made.

## V11 source credits

## Sources and credits

* [Chris Deotte: Multi-Gadget Fault DP](https://www.kaggle.com/code/cdeotte/squares-in-squares-multi-gadget-fault-dp-22-48) and [L-Cut & GPU Squeeze](https://www.kaggle.com/code/cdeotte/squares-in-squares-l-cut-gpu-squeeze-22-41): composition theorem, rectangular cuts, native corner typing and directed cushion alignment.
* [Dariush Afshar: Exact Validator, Record Merge](https://www.kaggle.com/code/dariushafshar/squares-in-squares-exact-validator-record-merge) and [Certified Packings dataset v8](https://www.kaggle.com/datasets/dariushafshar/squares-in-squares-certified-packings/versions/8): public ribbons, mixed constructions and credited portfolio; compilation CC BY 4.0. Its source README is retained with the inputs.
* [Kirill Tymchishin: Alternating Reclosure](https://www.kaggle.com/code/kirilltym/22-408512-cpu-alternating-reclosure), [avazaku: Squarecraft II](https://www.kaggle.com/code/avazaku/squarecraft-ii-unjam-the-grid-22-408597-lb), [Alex Chilton: Fault-line DP + Basin Hopping](https://www.kaggle.com/code/alexchilton/fault-line-dp-basin-hopping-lb-22-3945): credited public placements and contact-search context.
* [Kozykappa: Subset Transfer](https://www.kaggle.com/code/kozykappa/subset-transfer-contact-refinement-and-compaction), [Prvsiyan: A Square Deal](https://www.kaggle.com/code/prvsiyan/a-square-deal-research-to-verified-packings), [Malyshev Danil: Neighbour Transfer + Squeeze](https://www.kaggle.com/code/malyshevdanil/squares-in-squares-neighbour-transfer-squeeze), [SeshuRaju: Ensemble](https://www.kaggle.com/code/seshurajup/1000-puzzles-ensemble-lb-22-477584): inherited portfolio and search lineage.
* [Francisco Couzo and original discoverers](https://github.com/franciscouzo/square-packing), [Evan Daniel](https://github.com/evand/square-packing), MIT; [Joshua Levy and contributors](https://github.com/jlevy/squares); Darius Muglich's CC BY 4.0 permission and the existing individual witness notices are retained in the Layout Atlas. No inherited mathematical discovery is attributed to this implementation.
* [Official metric v17](https://www.kaggle.com/code/metric/squares-in-squares?scriptVersionId=360167936), unchanged, Apache 2.0. CUDA sources extend the existing implementation of this notebook; the public saved donor bank keeps its previous provenance and notices.

Local certification and the score attached by Kaggle to a submitted version are distinct. Finite search and conservative seam tests do not establish optimality.

## Prior portfolio notices

# Alternating CPU Contact Reclosure

Pinned baseline: avazaku, Squarecraft II | Unjam the Grid, version 2, native 361225541.
https://www.kaggle.com/code/avazaku/squarecraft-ii-unjam-the-grid-22-408597-lb?scriptVersionId=361225541
Baseline CSV SHA256 b44144246654affdee31949aa47e3d52eea95cdad574984bd1bf5c7b03ef8559.
The nine improvements over our previous public version, including n984 and n553, are credited to avazaku. His binary contact-switch experiment informed this follow-up. The new experiment alternates our CPU separation graph LP with free-angle contact refinement, rebuilding the graph after each relaxation. Fixed-angle separation choices are sampled, not solved by a new MILP. Every admitted witness retains exact unit square sizes and is certified using the unchanged official v17 metric. This incremental experiment makes no invention or global-optimality claim.
All new search ran on CPU; no CUDA or MPS was used. The default notebook restores the frozen result, exports readable search source and logs, then evaluates raw CSV decimals and a default pandas float64 round trip. It does not rerun optimization.

## Previous public source notices

# CPU Rectangular Reclosure

Primary baseline: Chris Deotte (cdeotte), Squares in Squares L-Cut GPU Squeeze 22.41, version 1, native version 361208974.
https://www.kaggle.com/code/cdeotte/squares-in-squares-l-cut-gpu-squeeze-22-41?scriptVersionId=361208974
The L-cut layouts, rectangular block construction and GPU search are credited to cdeotte. Most of the final quality is inherited from that portfolio. A complementary public input is Kirill's CPU Separation Graph Reclosure version 8 (native 361188237), with its inherited authors and notices retained below.
https://www.kaggle.com/code/kirilltym/22-472940-cpu-separation-graph-reclosure?scriptVersionId=361188237

This release applies bounded fixed-angle separating-axis linear programs to the new layouts, then free-angle CPU contact refinement and complete translated-window subset propagation at 0/45 degrees. These are incremental experiments with prior algorithmic lineage, not claims to invent packing LPs. cpu_contact_polish.py is adapted from lightningv08 under Apache 2.0; its notice is retained. All new search ran on CPU. No GPU or MPS used. Unit squares retain side length one; clearance is introduced by centre displacement only. The unchanged official metric v17 certifies actual CSV decimals and a default pandas round trip. No global optimality claim is made.
# CPU Separation Graph Reclosure

Frozen baseline: kozykappa, Subset transfer, contact refinement and centre compaction,
version 1, native 361161040.
https://www.kaggle.com/code/kozykappa/subset-transfer-contact-refinement-and-compaction?scriptVersionId=361161040
CSV SHA256: f0478afdf71c02e57c0852c6bdcb510802677ce76bfd6ec1c56375a6e01ec1c5.

The frozen portfolio and complementary fault-line merge are credited to kozykappa
and the inherited authors in the retained notices. This release measures only
its gain over that stronger starting point, rather than the older Kirill V7.
The main experiment selects among currently valid separating axes at contacts
and solves a bounded, fixed-angle LP for all square centres and the box side.
Alternative separation choices permit different row motions. It then applies
CPU free-angle contact refinement and integer-border/subset propagation.
Linear-programming packing and separating-axis constraints have prior lineage;
this is a reproducible incremental experiment, not a claim to invent them.
cpu_contact_polish.py is adapted from lightningv08's Apache-2.0 implementation.
The new cpu_axis_reclosure.py and experiment runners are readable source.
All search used Apple M5 Pro CPU; no CUDA, MPS or GPU was used.
Unit-square sizes never change. Final admission uses the unchanged official v17
metric (Apache 2.0), on both direct decimals and a default pandas float64 round trip.
The standard 0/45-degree transfer pass was also tested before the new LP pass;
its negative result remains in the logs. No global-optimality claim is made.

## Frozen baseline notices

# CPU follow-up to CUDA Packing Search V10

Frozen baseline: lightningv08, CUDA Packing Search V10, native 361128459,
https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search?scriptVersionId=361128459
Baseline CSV SHA256: a0d9c86bd1f42edd9681c31e3f48c21bfee9d2d9a538476cb9f217547398f612.

The strong baseline, mathematical witnesses, tilted-block composition and seam
profiles belong to the credited source authors below. This release adds a CPU
translated-window pass at 0 and 45 degrees and contact refinement of selected
new layouts. It claims only the measured improvement over the frozen baseline.
CPU contact code adapts lightningv08's Apache-2.0 implementation, as credited
in its source header, with configurable trust, regularization and CPU imports.
No CUDA, MPS or GPU was used. Unit-square sizes are never scaled. Translations,
subset selection, centre dilation for safe serialization, border addition and
LP steps modify coordinates. The official v17 metric is unchanged (Apache 2.0).
Previous individual witness attribution and license tables are retained.

## Sources, attribution and limits

* [Kirill Tymchishin — CPU Reclosure + Contact Refinement V6](https://www.kaggle.com/code/kirilltym/22-476936-cpu-window-reclosure-lp-polish), frozen credited baseline, SHA-256 `d9de42e1d16ccee052e93e59825bfa0658dfa67b6564608de19b6f9b3c3a2fd9`.
* [Chris Deotte — Multi-Gadget Fault DP](https://www.kaggle.com/code/cdeotte/squares-in-squares-multi-gadget-fault-dp-22-48), staircase composition, corner crops and the empty-corner seam criterion; this implementation adds CUDA support-profile joins.
* [Alex Chilton — Fault-line DP + Basin Hopping](https://www.kaggle.com/code/alexchilton/fault-line-dp-basin-hopping-lb-22-4776), credited public portfolio, and [his public starter kit](https://www.kaggle.com/datasets/alexchilton/squares-in-squares-starter-kit), large Couzo witness variants.
* [SeshuRaju — 1000 Puzzles Ensemble](https://www.kaggle.com/code/seshurajup/1000-puzzles-ensemble-lb-22-477584), public input comparison. [Malyshev Danil — Neighbour Transfer + Squeeze](https://www.kaggle.com/code/malyshevdanil/squares-in-squares-neighbour-transfer-squeeze), inherited selected witnesses.
* [CUDA Packing Search V9](https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search?scriptVersionId=360983307), independent sliding-row donors and CUDA primitives. [avazaku — Squarecraft](https://www.kaggle.com/code/avazaku/squarecraft-beyond-the-grid-22-7417-lb) supplies the earlier corner/core construction.
* [Francisco Couzo and the original discoverers](https://github.com/franciscouzo/square-packing), MIT; [The Squares Project, Joshua Levy and contributors](https://github.com/jlevy/squares); Darius Muglich's [CC BY 4.0 grant](https://github.com/jlevy/squares/issues/686#issuecomment-6302118274). Existing individual notices, witness provenance and licenses remain in the public Layout Atlas. No inherited mathematical discovery is attributed to the CUDA implementation.
* [Yohei Nakajima — Soft-to-Rigid](https://github.com/yoheinakajima/soft-to-rigid), MIT, inspiration for the separate negative shape-continuation experiment; [Evan Daniel's square-packing search](https://github.com/evand/square-packing), inherited public-search lineage.
* [Organizer per-puzzle leaderboard](https://www.kaggle.com/code/inversion/squares-in-squares-per-puzzle-leaderboard), a delayed diagnostic snapshot; [official metric v17](https://www.kaggle.com/code/metric/squares-in-squares?scriptVersionId=360167936), unchanged, Apache 2.0.

Separating-line profiles are conservative, angle coverage is finite and the donor bank is finite. The method does not establish global optimality. The certified local score is distinguished from the score attached by Kaggle to a submitted saved version.

## Earlier CUDA and mathematical-witness lineage

## Sources, attribution and limits

* [Kirill Tymchishin — CPU Reclosure + Contact Refinement V6](https://www.kaggle.com/code/kirilltym/22-476936-cpu-window-reclosure-lp-polish), frozen credited baseline, SHA-256 `d9de42e1d16ccee052e93e59825bfa0658dfa67b6564608de19b6f9b3c3a2fd9`.
* [Chris Deotte — Multi-Gadget Fault DP](https://www.kaggle.com/code/cdeotte/squares-in-squares-multi-gadget-fault-dp-22-48), staircase composition, corner crops and the empty-corner seam criterion; this implementation adds CUDA support-profile joins.
* [Alex Chilton — Fault-line DP + Basin Hopping](https://www.kaggle.com/code/alexchilton/fault-line-dp-basin-hopping-lb-22-4776), credited public portfolio, and [his public starter kit](https://www.kaggle.com/datasets/alexchilton/squares-in-squares-starter-kit), large Couzo witness variants.
* [SeshuRaju — 1000 Puzzles Ensemble](https://www.kaggle.com/code/seshurajup/1000-puzzles-ensemble-lb-22-477584), public input comparison. [Malyshev Danil — Neighbour Transfer + Squeeze](https://www.kaggle.com/code/malyshevdanil/squares-in-squares-neighbour-transfer-squeeze), inherited selected witnesses.
* [CUDA Packing Search V9](https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search?scriptVersionId=360983307), independent sliding-row donors and CUDA primitives. [avazaku — Squarecraft](https://www.kaggle.com/code/avazaku/squarecraft-beyond-the-grid-22-7417-lb) supplies the earlier corner/core construction.
* [Francisco Couzo and the original discoverers](https://github.com/franciscouzo/square-packing), MIT; [The Squares Project, Joshua Levy and contributors](https://github.com/jlevy/squares); Darius Muglich's [CC BY 4.0 grant](https://github.com/jlevy/squares/issues/686#issuecomment-6302118274). Existing individual notices, witness provenance and licenses remain in the public Layout Atlas. No inherited mathematical discovery is attributed to the CUDA implementation.
* [Yohei Nakajima — Soft-to-Rigid](https://github.com/yoheinakajima/soft-to-rigid), MIT, inspiration for the separate negative shape-continuation experiment; [Evan Daniel's square-packing search](https://github.com/evand/square-packing), inherited public-search lineage.
* [Organizer per-puzzle leaderboard](https://www.kaggle.com/code/inversion/squares-in-squares-per-puzzle-leaderboard), a delayed diagnostic snapshot; [official metric v17](https://www.kaggle.com/code/metric/squares-in-squares?scriptVersionId=360167936), unchanged, Apache 2.0.

Separating-line profiles are conservative, angle coverage is finite and the donor bank is finite. The method does not establish global optimality. The certified local score is distinguished from the score attached by Kaggle to a submitted saved version.