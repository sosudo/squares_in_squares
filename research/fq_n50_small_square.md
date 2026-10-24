# Two bounded n50 basin searches

Neither tested starting arrangement improved the current n50 packing. The true reference side is **7.5714285714351427**, with official case score **0.07076169722627279**, from frozen raw portfolio `ad1daf5d…`. No candidate was merged or submitted.

| Starting arrangement | Trials | Solver campaign time | Strictly valid unique outputs | Best resulting side | Actual n50 score gain |
|---|---:|---:|---:|---:|---:|
| Current n50, 14 tilted squares at 36.8699° | 96 | 141.90 s | 55 / 55 | 7.571428584571444 | 0 |
| Exact n37 packing padded to n50, 15 tilted squares at −45° / ±42.0866° | 128 | 183.39 s | 60 / 60 | 7.598619622441604 | 0 |

Both used the unchanged `experiments/fq_small_square_campaign.py` wrapper on one CPU. Its eight modes include rigid kicks of 0.03/0.12/0.25, aspect continuation at 0.15/0.30, two shrink-hop configurations and rounded continuation at radius 0.20. The original-seed run exercised every mode twelve times; the padded-seed run exercised every mode sixteen times. Each executable call was capped at ten seconds and the supervisor bounded the whole campaign. All admitted soft trials supplied the exact-zero aspect-return trace.

Each starting arrangement first passed independent interval geometry, official raw and ordinary pandas transport checks, followed by a 20-step contact-polish control. The original control completed in 0.16 seconds and only added legalization clearance. The alternative was constructed by the public single-block stitch: a 6×6+1 n37 block plus a complete square frame yields exactly 7×7+1 = 50 squares. Its independently certified initial side was 7.5986196531972405.

The alternative search deliberately used that worse padded pose as its internal reference, allowing it through the campaign's near-reference filter. Its small internal reference improvement was **not** an n50 improvement. Final analysis compared every pose against the separate true n50 reference. No output beat that reference. Independent post-validation checked all 55 and 60 unique saved variants, respectively; none failed geometry or numeric transport.

The equal-excess screen found eleven cases with excess near 4/7: n50,171,198,364,403,444,487,680,733,788,845. Only n50 belongs to the matching k²+1 family. Equal excess alone does not establish that an n50 improvement transfers to all eleven cases. Whole-square buffered-copy templates predict only n50 and n487 near the current bound; the other cases need separate constructions or smaller rectangular components. No projected family benefit is counted as an achieved score gain.

Frozen inputs and evidence:

- `artifacts/n50-fq-input-v1/`: exact original CSV rows, optimizer seed, full certificate, control and family screen.
- `artifacts/fq-n50-small-v1/`: original-seed trials, immutable checkpoints and source/binary/input hashes.
- `artifacts/fq-n50-small-v1-strict/report.json`: independent post-validation; `all-strict.npz` SHA256 `7af154a0bfb816438b037b93cb0e99bda05576eb3da9a6d60f0305d222008ba9`.
- `artifacts/n50-padded37-input-v1/`: exact source/target CSV rows, public construction proof, separate true-target and search-reference sides, and control.
- `artifacts/fq-n50-padded37-v1/`: alternate-seed trials and immutable checkpoints.
- `artifacts/fq-n50-padded37-v1-strict/report.json`: independent post-validation; `all-strict.npz` SHA256 `826a6bc5b48238b1e4a948027610a6fad29a2cea3b7a60306e1ab5f7186cbf72`.

The preparation and independent checking are reproducible through `experiments/fq_small_seed.py`, `experiments/fq_padded_seed.py` and `experiments/certify_small_campaign.py`.
