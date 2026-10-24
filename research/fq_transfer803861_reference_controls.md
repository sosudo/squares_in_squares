# Matched original-reference controls for n803 and n861

Before the distinct cold GPU transfer pilot, both exact current references were
completed with the existing portable FQ binary and unchanged rigid options:
`--loosen 1 --outer 45 --pit 100 --flip-top 16`, seed `9710000`.
Each solve had a 60-second limit and a separate 8-second full-certificate limit;
the two-worker supervisor allowed 90 seconds total. No GPU was used.

The frozen input is the canonical RAW `28feb2d3059e33db0189aa46c2bdb5f1a0f0c0aa35fb0f2003181595491ba6a3`.
Input preparation preserves the original coordinate strings and their exact
float64 arrays, with only a recorded translation for the native reference.
The `delta=.002` field selects the matched seed; it does not compress or perturb
these controls. Both slots are explicitly labeled `original_reference`.

| n | Canonical side | Worst certified control side | Native seconds |
|---|---:|---:|---:|
| 803 | 28.8275852224118928 | 28.82758633505586031 | 5.8305 |
| 861 | 29.8280467404800652 | 29.82804679410396280 | 6.1842 |

Both completed well within their limits and passed the unchanged official raw,
ordinary-pandas and independent interval gates. Neither improves the canonical
packing. The next GPU input should therefore retain the stronger original
reference arrays. This is a matched completion control, not evidence of global
optimality or of how different native seeds would perform.

Evidence is frozen in `artifacts/fq-transfer803861-reference-controls-v2`.
`inputs/restart-inputs.npz` has SHA256
`79ea2bf403b7f6ca82d6662ffe5bf0128ce5a250be4138efc26061e6649b2e1b`;
`restart-input-proof.json` binds the baseline, source decimal strings, original
and translated arrays, official and interval reports. Complete native inputs,
outputs, logs, certificates and both certified geometries remain under the two
case directories. `candidates.json` is empty. Total measured runtime was 8.87
seconds; no canonical portfolio was changed.

The initial `v1` attempt stopped at its builder hash assertion after 0.67
seconds, before input preparation or native work. It expected an older
preparation snapshot. The corrected wrapper binds the actual final reviewed
builder `42207fe5db2dd6156128f6f917f91e6d607ff9d37767a6a71f7bc010ca829b03`
to its original build receipt, reuses its preparation function with only the
case tuple changed, and preserves the failed attempt. The numerical finisher
remains the frozen `aab5ea32` source; its cloned function changes only the
initializer metadata label. The reused preparation configuration includes old
GPU defaults, which are not the new cold pilot's schedule or authorization.

Portable FQ is Evan Daniel's MIT-licensed `evand/square-packing`, commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`. The exact binary SHA256 is
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`;
the source and license are retained with the control evidence.
