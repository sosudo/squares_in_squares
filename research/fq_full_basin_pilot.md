# Aggressive refinement of newly composed complete puzzles

The bounded one-CPU pilot retained two complete-puzzle improvements against the latest fine-GPU poses:

| n | Method | Certified side | Score gain |
|---:|---|---:|---:|
| 702 | New-seed control, 20 contact-polish iterations | 26.937382228301886659 | 0.00007940442112 |
| 813 | Augmented Lagrangian repair after a 0.03 kick | 28.936338591652053 | 0.00001085955668 |

Total gain against the selected seeds is **0.0000902639778009**. These are full-case, independent interval and official raw/default-pandas certified improvements. The portfolio owner must still merge them and certify the complete file. No submission was made.

`experiments/fq_full_basin_pilot.py` selected the best available pose for n599/702/807/813/815/871/924/931 from the pinned KMMM 28 portfolio, fine-GPU candidates, the exact-pair n599 result and the verified exact-window result. The n807 GPU candidate won its comparison; n599 used the pair result. Native FQ input uses `w=h=floor(side)` and `d=n-w*w`, retaining the exact square count and treating the bounding side as the solver's container parameter.

The run took **283.24 seconds**, including its positive control, on one worker. Each complete trial had an inclusive cap of 18 seconds, shortened by the remaining global deadline on the final trial. It attempted eight 0.03-kick repairs, eight rounded-continuation repairs at radius 0.15, and one 0.08-kick repair. One aggressive trial improved n813, three converged without improving the incumbent, and 13 reached the time limit. All eight rounded trials timed out; this run does not establish whether longer rounded repairs would improve those cases. The solver process group is killed when a complete trial times out.

The n702 positive control also improved the incumbent materially. Its exact output was recovered separately, its binary64 geometry hash checked against the recorded full certificate, and it was retained alongside the n813 search result. The successful control is not counted as an aggressive-basin success.

Frozen evidence:

- `artifacts/fq-full-basin-v1/`: selected input arrays, candidate-source hashes, executable and source snapshots, commands, positive control, 17 trial records and supervisor receipt.
- `artifacts/fq-full-basin-control-v1/`: immutable extracted n702 candidate and matching geometry/certificate proof.
- `artifacts/fq-full-basin-union-v1/candidates.json`: both retained cases, SHA256 `d6261fbd69eed384f40cb6f2e185e7ba713486faa8fb2bbfd1bfb9d3a16fc24d`.
- `artifacts/fq-full-basin-union-v1/donors.npz`: both complete poses, SHA256 `c606ade62025414b0e8212b6229e6327381cd730af6d983598fe3f1c42bed2ba`.
- `artifacts/fq-full-basin-union-v1/completion-proof.json`: verified source/input/report bindings and all full-case certificate checks.
