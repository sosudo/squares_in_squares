# Insertion branching and exact composition

The expanded insertion pilot produced one certified full-puzzle improvement after exact two-block composition: **n=599**, with side **24.9270519438541920396** and score gain **0.000203786603324** against the frozen KMMM 28 portfolio `a776d6e3…`. No competition submission was made.

The successful search used a changed arrangement of **7×20+14**, produced by reinserting a square into the earlier deleted **7×20+13** pose, alongside the new **16×4+9** pose from bank `006dbc31…`. A subsequent controlled substitution showed that the old 7×20+14 donors achieve the same result. The improvement therefore does **not** demonstrate a benefit from insertion-created boundary diversity. The earlier search restricted eligibility to pairs containing a newly supplied donor, which had omitted the relevant old/new pair. The stronger 16×4+9 pose and broader pair enumeration account for the observed gain.

## Bounded search and validation

`experiments/fq_insertion_campaign.py` performed 64 sequential trials in 201.8 seconds using one CPU worker, within its 560-second budget. Inputs, executable, sources, parent poses, insertion sites, repair options, and each command are preserved. The frozen FQ executable is SHA256 `10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.

Each trial adds exactly one square at a low-penetration location and repairs the arrangement with augmented Lagrangian optimization or soft-square continuation. Successful descendants can become parents. Every admitted pose passes independent interval separation, official metric v17 on decimal strings, ordinary pandas numeric CSV transport, and an interval proof that rectangular excess is below one. The reusable adapter had already passed a removed-square recovery control and a descendant-process timeout control.

The campaign retained **29 valid donor variants** and rejected 35 outputs with excess at least one. It reached **17 types absent from its frozen input banks**, including 5×17+9, 9×21+13 and 8×21+12. These are local bank additions, not claims of published packing records. No existing matching type improved by more than 1e-7.

Final frozen archive:

- `artifacts/fq-insertion-expanded-v1/complete/donors.npz`, SHA256 `051b88caee1f7a075a9f51227db592ba07058ecfd937a2f295faa8f6ed75dcca`.
- `complete/results.json`: all trial commands and certificates.
- `complete/parents.json` and `complete/parent-poses.npz`: exact ancestry and parent arrays.
- `complete/completion-proof.json`: independent recheck of source/input/archive hashes, accepted geometry hashes, count increments, and all certificate statuses.

## Fair comparison and full-puzzle checks

The unchanged `experiments/exact_pair_composition.py` enumerated 768,384 ordered D4 pair/join combinations containing at least one new donor. It screened 1,332,224 square containers, then tested all 2,048 promising pairs exactly. Of these, 192 passed cross-block separation and one distinct full-puzzle improvement survived complete validation. The run finished in 6.5 seconds; its positive control passed. The n=599 candidate passes independent raw and ordinary-pandas interval geometry checks and both official evaluations.

The separately reproducible `experiments/insertion_donor_audit.py` compared all 29 donors with the current primary, final focus, final soft, combined FQ and initial insertion/deletion banks. It found **zero improvements in existing matching types**, **13 variants dominated in same-box count/excess**, and **zero direct improvements across 347 standalone k²+d embeddings**. Same-box count/excess dominance does not establish dominance of boundary compatibility; all valid variants remain available for composition.

Composition evidence is in `artifacts/exact-pair-insertion-expanded-v1/`. Its `candidates.json` is SHA256 `b880b4fc87e726411e219a88257c09661a55a22058681438f5a089a53ec1ca71`. The independent standalone/dominance audit is `artifacts/insertion-standalone-audit-v1/audit.json`. The resulting n=599 candidate was handed to the portfolio owner for a full merged-file transport certificate; this experiment does not claim that full-file step itself.

## Controlled attribution check

`experiments/exact_pair_attribution.py` held the n=599 container, mode-1 join and exact 16×4+9 donor fixed, and independently substituted the best pre-existing 7×20+14 and 20×7+14 donors. Both replacements passed complete independent interval and official raw/default-pandas validation. The transposed 20×7 control reproduced the **identical certified side string**; the other orientation differed only far below binary64 resolution. Mode 1 supplies a full unit spacer, so this comparison does not require a special interlocking boundary profile.

The original attribution to insertion-created boundary compatibility was incorrect and has been corrected. This bounded experiment establishes **no incremental full-puzzle improvement attributable to the new insertion donor geometry**. All valid donor variants remain archived for other compositions. The immutable controlled result is `artifacts/exact-pair-insertion-ablation-v1/report.json`; both original and substitute geometries retain their certificates.
