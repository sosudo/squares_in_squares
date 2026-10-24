# Broader whole-packing native continuation

The finite broad campaign produced 53 fully certified improved cases, with
summed per-case score gain **0.0013701727596243** against frozen RAW
`artifacts/merged-fq-broad-lightning19-v1.csv` (22.30061363233568).
This is a per-case result. Whole-portfolio SAFE/ordinary-roundtrip proofs and
competition submissions belong to the portfolio owner.

The preceding one-worker diagnostic selected all18 newly imported public29
cases plus12 high-gap cases outside the earlier full-packing campaign lists.
It finished41 trials in157.08 seconds, retained37 certified outputs, and
improved11 cases by0.0002023256529056. Its final candidates are immutable at
`artifacts/fq-unvisited-contact-v1/candidates.json`, SHA256
`90b0a764ba8c2cfed751c1a7e7aaf642b474510dc36bdbdfeba6c5e7bd2c0175`.

## Frozen coverage and method

`experiments/fq_broad_contact_campaign.py` is separate from the completed
diagnostic. Inputs were frozen after the authoritative41b46 portfolio was
published. The factual per-puzzle target table had311 material positive score
gaps. The broad first pass selected265 cases after excluding the recent30,
the repeatedly tested147/299/335, and13 archived geometries equivalent to
current ordered normalized poses within documented precision-clearance
tolerances. Uncertain histories remained eligible. The target table supplies
reported scalar headroom, not a proof of available coordinates or attainability.

The exposure audit and exact parsed source arrays are frozen under
`artifacts/fq-broad-contact-inputs-v1`. Freeze SHA256:
`ad9129f4b79d2e58897c38c8e35e9e761af535ff846736264e4df63dde71707c`.
The audit records source CSV/report hashes, public target hash, every selected
case, and all historical matching archives. It does not claim exhaustive
historical or D4/set-matching coverage.

Three workers reused the same pinned native FQ binary, source commit,
encode/decode adapter and full certifier as the successful diagnostic. First
pass flags were `--no-alm --loosen 1 --pit 20 --flip-top 0`, with an inclusive
eight-second trial cap. The native header and all returned coordinates remain
preserved even when later clearance or certification times out. Every fully
certified output is retained, including scalar-worse variants.

After completing all265 first-pass cases, refinement interleaved:

- rigid ALM continuation on observed winners, capped at10 seconds;
- 20 high-gap rigid checks without an LP gain, capped at10 seconds;
- LP100 continuation on winners, capped at12 seconds.

At most one trial per case ran concurrently. Every stage used its exact
submitted parent geometry and compared certified side against the frozen
canonical RAW side. A candidate required more than1e-8 side improvement and
the shared official raw gate, ordinary default-pandas official gate, and
independent raw/ordinary-roundtrip interval gates. Native starts had no random
kick or rounded/aspect deformation in this experiment.

The full process group had a720-second ceiling. It exited normally after
708.73 seconds, with all three workers released and no source changes.
The remaining refinement queue stopped at the authorized scheduling deadline.
There was no canonical mutation or submission by this experiment.

## Results and measured allocation

There were370 attempted trials:265 LP20,42 LP100,43 rigid-winner trials and
20 rigid probes without an LP gain. Outcomes were248 certified outputs,
121 whole-stage timeouts and one interval-gate error at its eight-second cap.
All248 certified outputs have distinct exact geometry hashes. There are265
preserved native decimal outputs, including17 outputs that did not finish
their gates.

Summed incremental gain by the actual sequence of accepted per-case bests:

| Stage | Incremental score gain |
|---|---:|
| LP20 coverage | .0009539018415 |
| Rigid continuation on winners | .0002931858503 |
| High-gap rigid checks without LP gain | .0001168516751 |
| LP100 continuation | .0000062333927 |

A final candidate's last mode is not an attribution of all its gain. For
example, a small final LP100 update can carry a much larger earlier rigid
improvement. These observed increments support broad short contact coverage
and rigid continuation; they do not prove the best allocation for every case.

The no-LP rigid queue had a recorded scheduling overlap:411/498/544 were
already recent rigid outputs from the preceding diagnostic. The frozen run
was preserved. This redundant finite exposure is distinguished from the
other high-gap probes; no exact-current novelty is claimed for those three.

The first immutable below-threshold prediction occurred at gain-0028:
28 certified cases and0.0006886159417649 summed gain. This predicted a RAW
score near22.2999250164, but required the separate full SAFE and ordinary
roundtrip gate before any competition submission. The final immutable result
is `artifacts/fq-broad-contact-v1/complete/candidates.json`, SHA256
`022332cdb4a340908959e547e4e473cb09df7bb2c3f86521d440df8844bc5a86`.
Final donor archive, trial records, manifest, exposure audit and summary are
stored read-only in the same `complete/` directory. Early gain snapshots
remain immutable under `snapshots/`.

## Saved-output recovery is separate

No timed-out optimization was rerun. A raw-span shortlist at
`artifacts/fq-broad-contact-v1/saved-output-recovery-shortlist.json` identifies
native outputs worth fresh gating, without an admission claim. Parent-owned
recovery already certified638/979/807 separately. Additional unverified
outputs550/551/456/505 have the largest raw-span potential; their actual
increment depends on strict gating and comparison with the latest portfolio.
These recoveries are not included in the campaign's reported53 cases or
0.0013701727596243 gain unless explicitly merged by the portfolio owner.
