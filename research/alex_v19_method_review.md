# Public Alex v19 method review

This is a read-only review. No notebook, search, download of attached inputs, or new optimizer was run. The public notebook does perform search and composition, but its visible fault-line DP and gadget quench largely duplicate methods already exercised in this repository. The most distinct mechanism worth considering is **persistent basin hopping through infeasible local minima**, combined with row-breaking and relocation moves in Evan Daniel's separate `packer` executable.

## Exact evidence and limits

- Public notebook: `alexchilton/fault-line-dp-basin-hopping-lb-22-3747`, version 19, script version 361756451. Source `artifacts/public-alex-v19/source.ipynb`, SHA256 `96b087bfec41a506a3a8ec316b43ba5bc7523591a3362452e532cfea1d380c0a`; public/version proof is `source-code-provenance.json` beside it, response SHA256 `74c5262cd7fb33fbf22604ca89ca19f2af03acb487153c908e534fbd42dc7d16`.
- The notebook imports attached `hop_search.py`, `fault_dp.py`, `quench_gadgets.py`, `ensemble.py`, and `closure.py`. During this review, the competition-research agent verified its sole dataset attachment as public `alexchilton/squares-in-squares-starter-kit` v7 and downloaded the first three named helpers. Its description licenses the author's code CC0, excluding Kaggle's metric and independently licensed record packings. Exact metadata is `artifacts/public-alex-v19/starter-kit-metadata.json`, SHA256 `1498c926ab486f1cfd35760a9306f68a25cc8549c7553c59a44013dbcbae6abd`. No helper implementation was copied or executed here. No earlier helper version was compared, so this is not a v19-only algorithm-change claim.
- Exact v7 helper pins under `artifacts/public-alex-v19/starter-v7/`: `hop_search.py` SHA256 `9a42b0201e6974da7bfedd9dd4ada8ed214808e4213560a229a5744b6af57bc1`; `fault_dp.py` `828b6d99837acd8f008836d5abdeb6c7d4084c684acad16e5dcb6b749bdd3c68`; `quench_gadgets.py` `095ea6c09f1e9d1dda64536cc17684df826b62259448e058e4efb75c8f9277df`.
- The notebook builds an unpinned current GitHub checkout at runtime. To inspect its described native mechanism, this review instead used the already-local MIT checkout `/tmp/squares-research/evand`, commit `659ee62e4a9d39542a1146e8b011cc3ab6407ede`. Its `search/packer/src/main.rs` SHA256 is `f17683199f75af1e1489680bfc69ae38991998fe112e723ed648507ff6ff725e`. This is a pinned mechanism reference, **not proof of the exact binary used in notebook v19**.

## What the visible notebook does

1. Merge a public certified baseline, converted Couzo records, offline hopping results, and other attached public outputs. A live demonstration runs cases 494, 845, and 903 for three seconds each.
2. Run three rounds of cropped-gadget fault-line DP, merge, and closure. Compositions from one round become donors for the next. The described DP state tracks used width, height, surplus, and the last tip type; corner joins and complete unit row/column buffers connect gadgets between two shifted upright lattices.
3. Quench 78 preselected gadget types for 60 seconds each, then compose and close again. Selection uses the counterfactual portfolio benefit of reducing each gadget's overhang by 0.005. The described search loosens by 0–4%, nudges centers/angles, and restarts from its best layout.
4. Evaluate the final CSV after an ordinary float64 read.

We already have public-record merges, repeated composition with diverse crops, buffer/corner joins, counterfactual donor priorities, FQ gadget campaigns, closure, and stronger raw/default-pandas certification. The notebook explicitly says L-cuts/strip removal are **not** implemented there. Its negative controls for rigid constructions, cushion translations, and tilted-block gadgets are finite results on its own inputs, not impossibility proofs.

## Concrete difference: persistent infeasible-state search

The inspected `packer hop` command is a different search loop from our FQ restart campaigns:

- Keep the box fixed and locally minimize a squared SAT-penetration/wall objective using L-BFGS.
- Perturb the **current locally minimized state**, minimize again, and retain some uphill states using a Metropolis rule. With optional jam-line penalty included in objective `F`, uphill acceptance is `log(F_new/F_current) < -temperature*log(U)`. Thus a failed quench can become the parent of a later attempt; it need not be discarded in favor of the best certified packing.
- Once feasible, squeeze, save a smaller box, and target a side just below the best. Default target decrement is `1e-4`; default temperature is `0.3`. The verified helper supplies only input, seed, iteration count, output, and `--quiet`, confirming that it relies on those native defaults (subject to its unpinned runtime native revision).

The native move mix includes moves that can change strip occupancy without changing total count:

- **Row break:** find heuristic jam lines containing at least `floor(side)+1` near-upright centers in a width-one band; relocate a member to a sampled low-penalty hole or rotate it by about 15–45 degrees. This near-upright heuristic is not an exact geometric infeasibility certificate.
- **Best-hole relocation:** evaluate 300 random center/angle proposals for one square, choosing the least wall-plus-pair penetration penalty. Angles are upright or borrowed from an existing free square. This deliberately changes which region a square occupies.
- **One-sided strip slide:** translate only one side of a cut through a selected horizontal/vertical band. Its random band has half-width 0.5–1 and the displacement scale is `0.2*amplitude`.
- Other moves include coherent cluster rotation/translation, local shaking, changing one angle, and exchanging two centers while leaving their angles in place.

The optional `--linepen` biases acceptance away from jammed rows but defaults to zero; the verified helper does not enable it. Even with zero line penalty, row-breaking remains one of the nine native mutation choices.

The repository search found no prior `packer hop`, `--linepen`, or Metropolis campaign under `experiments/`, `scripts/`, or `research/`. Existing `fq_small_square_campaign.py` and `fq_junction_followup.py` use FQ's separate bounded shrink/hop facility; this is not evidence of a persistent `packer` Metropolis chain. `fq_multiscale_campaign.py` chooses certified best/diverse source parents, and `full_structural_gpu_v2_worker.prepare_batch` restarts batches from fixed reference/variant sources. Some constituent perturbations already exist here; the **state-retention policy plus deliberate row evacuation** is the useful difference.

## Priority assessment

A future bounded control should distinguish persistent-chain retention from the same moves restarted from the incumbent, and record actual row-break/relocation events and accepted uphill transitions. Count, final rigid geometry, and the full raw/default-pandas gates remain necessary. Do not infer any promised score gain from this review.

The notebook reports only 4 improvements from 24 full-puzzle runs of five CPU-minutes each, total score gain 0.000297 on its own older inputs. That is a reason for a small discriminating control, not a long campaign justified by its title or aggregate score. Its claim of greater gadget-quench leverage also concerns a weaker starting portfolio and does not establish remaining headroom against our current incumbent.
