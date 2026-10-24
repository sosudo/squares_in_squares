The bounded fq full-puzzle pilot improved eight complete packings and reduced the certified safe portfolio score from 22.304375968681107 to 22.304272228261368. The official score is identical after ordinary pandas numeric read/write, with zero invalid cases across all 1,000 puzzles. This remains above the user's 22.3 submission threshold and is a search baseline only.

The search ran 283.96 seconds with two CPU workers: 24 selected cases spanning n103–995, all eight requested seeds, a polish-only pass followed by a small-kick pass. Forty-eight trials yielded 43 officially valid outputs and five 30-second timeouts. Eight best complete-puzzle improvements were independently interval-certified; worse candidates were excluded from the merge. The finite pilot is not an optimality claim.

| n | Retained mode | Side reduction | Score improvement |
|---:|:---|---:|---:|
| 539 | polish | 7.06655083924e-05 | 3.04377892157e-06 |
| 599 | kick | 0.000627778456082 | 2.56503323393e-05 |
| 646 | kick | 1.89264307338e-05 | 7.44650457518e-07 |
| 650 | polish | 0.000334070291977 | 1.31033149056e-05 |
| 799 | kick | 0.000850012303935 | 3.00712736332e-05 |
| 813 | kick | 0.000190740910682 | 6.68957579841e-06 |
| 925 | polish | 0.000478929122618 | 1.57470925497e-05 |
| 991 | kick | 0.000273575152772 | 8.6904011336e-06 |

The source is Evan Daniel's MIT-licensed fq at commit 659ee62e4a9d39542a1146e8b011cc3ab6407ede. The portable executable hash is `10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`. The unchanged shared adapter records exact CLI parameters, output geometry hashes, and per-trial certificates in `artifacts/fq-full-pilot-v1/manifest.json` and `results.json`. Full containers use w=h=floor(sqrt(n)) and d=n-w*h, preserving every input count.

The frozen candidate JSON is `artifacts/fq-full-pilot-v1/full_candidates.json` (SHA256 `90275ae727d22dea991afd0685b7ea0a72fd19345c9e072d19c49771a449f51c`). The donor archive retains 13 independently certified complete-pose variants that improve the original baseline; `replaced-baseline.npz` preserves the eight replaced incumbent poses. All original CSVs are unchanged.

The raw merge starts from `merged-public-refresh-v1.csv`, never from its already-scaled safe form. The standard Decimal transport transform runs exactly once. All 992 unchanged safe puzzles retain their previous exact row hashes, including the 91 remaining long-precision cases. Raw, safe and ordinary-roundtrip official evaluations each cover all 1,000 cases: eight fresh and 992 exact-hash reuses. `artifacts/submission-fq-full-v1-safe.transport-validation.json` binds every input, output, report, and cached baseline hash.

The gains are concentrated in cases with diverse angle families. Regular single-angle cases mostly reproduced the incumbent plus clearance. Polish timed out for n813, 910, 991 and 995; the kick pass recovered improvements at n813 and n991. A later pilot can prioritize mixed-angle cases and lighter polish settings for the unresolved larger cases.

The executed script is frozen as `artifacts/fq-full-pilot-v1/source_fq_full_pilot.py`, matching its original manifest hash. After this completed run, the reusable script's deadline exception was hardened to escape metric-style Exception handlers; `tests/test_fq_full_deadline.py` verifies that behavior. No search or geometry parameters changed.
