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