# Contact-LP refinement of twenty newly composed cases

The final union improves the frozen raw portfolio `be22cb064c82…` by **0.0000379026658631** across twenty independently certified cases. Most of the gain comes from three cases:

| n | Score gain |
|---:|---:|
| 812 | 0.00001961116946 |
| 871 | 0.00001044029617 |
| 931 | 0.00000774861474 |

The remaining changes mostly remove tiny export clearances. All retained sides strictly beat the corresponding baseline interval lower bounds and pass independent raw/default-pandas interval checks plus official metric v17 evaluations. No competition submission was made; the portfolio owner received the union for full-file merging and transport certification.

`experiments/fq_full_contact_campaign.py` used one CPU worker and the same frozen FQ executable as the earlier basin pilot. It selected the twenty case IDs from the fine-GPU candidate file but took each geometry from the newer complete raw portfolio, preserving the earlier n702/n813 wins. It tried 20 contact-polish iterations on all twenty cases, 100 iterations in observed-gain order, then 150 iterations on cases with a certified improvement. All phases disabled augmented Lagrangian repair and contact-branch flips. Per-trial wall limits included decoding and certification; immutable early snapshots were published after each completed trial.

The campaign finished in **485.58 seconds**, within its 885-second limit. It attempted 59 trials: 22 certified improvement events, 31 without sufficient side improvement and six timeouts. The 100-step passes added only about 1.69e-8 aggregate score beyond the 20-step results; the 150-step passes added no accepted improvement. These measurements support stopping further repetition of this contact optimum and using a different structural search.

The original n871 20-step optimizer finished, but its complete trial ran out of time during certification. Its output was preserved and separately certified with `experiments/fq_saved_certificate.py` in **1.62 seconds**, without running the optimizer again. That recovered candidate is explicitly distinguished from trials that completed within their original budgets. Other timed-out trials had not completed optimization.

Frozen artifacts:

- `artifacts/fq-full-contact-v1/manifest.json`: exact baseline, source, binary, case selection and phase options.
- `artifacts/fq-full-contact-v1/complete/`: immutable final trial records, candidates and every accepted intermediate donor.
- `artifacts/fq-contact-871-recovery-v1/`: frozen original output, interrupted-trial record and separate full certificate.
- `artifacts/fq-full-contact-union-v1/candidates.json`: twenty best cases, SHA256 `4b0137411fbd443e495250fa19096d33a62f4d11a0dc3123235ed6ab2aac0adb`.
- `artifacts/fq-full-contact-union-v1/donors.npz`: SHA256 `7564db7dc75fdd1ffd6855318416634132a5f2d7951489e78492b31244a55139`.
- `artifacts/fq-full-contact-union-v1/completion-proof.json`: all source/hash/certificate bindings and case-by-case gains.
