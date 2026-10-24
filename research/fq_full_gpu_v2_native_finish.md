# Six retained GPU-v2 poses with matched native controls

This was new native finishing of six exact full-structural-GPU-v2 raw states,
not recovery of interrupted native solves. The frozen selection contains two
states each for n147, n299 and n335, with three exact current-original controls.
The overlapping raw states had physical spans about 0.00172–0.00191 below the
current boxes; those spans were never treated as valid packing sides.

Inputs are `artifacts/full-gpu-v2-native-handoff-v1/inputs.npz`, SHA256
`f80768ea1989b0fb3226a6e52dfe58e38aacca4c9bed826abd41f6de72c9c6c5`.
The authoritative manifest SHA256 is
`3dc40a39040c6bb7e27306778ed00ba0cbc15c6d8b196460c962bafb1fc9abae`;
it binds all nine geometry identities, exact native input texts, baseline and
packet/source provenance. History checks found no prior native trial on these
six exact GPU-derived inputs.

The runner reused the frozen `aab5ea32` native finisher; its only copied-function
change clarifies the initializer metadata label. Options were unchanged rigid
ALM45/polish100/flip16/loosen1, seed 9710000 for every slot, with 60 seconds native
and a separate 8-second full-certificate limit. Two CPU workers had a 345-second
work deadline and a 360-second whole-process-tree limit. All three originals
had to pass full gates before any GPU-derived input could run. No GPU was used.

All nine outputs passed the full raw/default-pandas/independent interval gates
in 23.67 seconds overall. Actual native calls lasted 0.47–9.34 seconds; none hit
a cap. The six new finished poses did not improve the stronger current portfolio.

| n | Original control side | Best GPU-derived finished side |
|---|---:|---:|
| 147 | 12.656854272806276 | 12.656854272806199 |
| 299 | 17.822875700849145 | 17.822915792684231 |
| 335 | 18.822875739464317 | 18.822875713511638 |

The tiny differences between a GPU-derived result and its control are not gains
against the canonical packing. Candidate admission compared each worst certified
side with the latest canonical independent lower bound (RAW `52c9d3e6…`), and
`candidates.json` is empty. All nine valid geometries, including worse outcomes,
remain in `artifacts/fq-full-gpu-v2-native-finish-v1`, with original decimal native
outputs, logs, exact inputs and certificates retained before aggregation.

Results SHA256: `1967f751836a95dc3c270ee5db3630a5a27c7eb27136d52b217417c6f3fdd4a3`.
Certified nine-pose archive SHA256:
`ff3905974c5a57e534670473a23cadcb567e729a12205cb4b5254db77e0120ac`.
The source review is `runner-source-review.json` in the immutable input handoff,
SHA256 `6af8c88b238c5e474e80970e2413dc471c97ceea344ce0600e6b93604675dc2e`.

This finite test is complete and negative. It changed no canonical pointer or
competition submission. The six exact inputs are excluded from subsequent raw
archive screening. The original public GPU source and FQ MIT source provenance
remain bound in the handoff and copied execution sources.
