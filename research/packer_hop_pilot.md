# Native persistent basin-hopping control on n335

The bounded native pilot exercised a genuinely persistent infeasible chain but found **no better valid packing**. Total execution was 134.12 seconds with one CPU, including the full-n335 input/output control and final official raw, ordinary pandas, and independent interval certificates. The native search received 130 seconds and was killed/reaped at 130.10 seconds as intended; the outer 180-second supervisor completed normally.

## Pinned implementation and execution

`experiments/packer_hop_pilot.py` uses Evan Daniel's public MIT `packer`, distinct from `fq`. Source commit: `659ee62e4a9d39542a1146e8b011cc3ab6407ede`; original `main.rs` SHA256 `f17683199f75af1e1489680bfc69ae38991998fe112e723ed648507ff6ff725e`.

An isolated source copy added only observation: per-hop before/proposal/accepted energies, side, move kind, and atomic exact accepted-state snapshots in radians. It changes no random draws, acceptance expression, move, or minimizer. Original vendor source and binaries were untouched. The source, original comparator, telemetry diff, MIT license, compiler commands, logs, and both binaries are frozen in `artifacts/packer-hop-335-v1-source/`:

- Instrumented source SHA256 `3bfa9e5d38449ddd6a6cf2e8d58dc1e8f77c97c2f0f3e8e6770c66c1723f88c1`.
- Observation-only diff SHA256 `2e847221f3ba58c93ccb214278f39ba353fefe57c562f4e01b85b26a45abd72e`.
- Instrumented binary SHA256 `39e7699fc507a67d4acfc75465a476b69a5647058c60bd90832ce6996dc3cf25`.
- Unmodified-source comparator binary SHA256 `937a90cfc82f0adc45dd5d7a905f982839913ac516930b29126346bb09949477`.

Both standalone, standard-library-only builds took 3.29 seconds in total, separately from the search bound. The invocation was:

```
packer_trace hop --in start.in --out best.out --seed 335019
  --iters 1000000000 --temp .3 --amp 1 --maxit 3000
  --descend .0001 --linepen 0
```

These search settings match the verified public starter-kit helper's native defaults; only the seed, instrumentation, bounded process control, and our stronger certificates differ. Source/helper provenance is documented in `research/alex_v19_method_review.md`.

## What actually happened

The 335-square source was the already-certified legalized copy of the then-current reference. Every square was free. A native `relax --maxit 100` control returned all 335 physical unit squares and passed fresh full geometry gates before hopping began.

The search completed 459 proposals and accepted 144, including **55 uphill transitions with nonzero overlap energy**. It retained 147 exact raw snapshots. An independent recomputation over all 55,945 unordered pairs and all four walls agreed with reported accepted energies within `7.46e-20`, confirming genuine uphill infeasible acceptance rather than a logging/stale-energy artifact. The `feasible_best` event carries the pre-squeeze energy and is explicitly excluded from that equality comparison; its raw geometry was independently evaluated and the final feasible output separately certified.

| Mutation | Proposed | Accepted | Uphill accepted |
|---|---:|---:|---:|
| Local shake | 55 | 6 | 3 |
| Random relocation | 58 | 0 | 0 |
| Change one angle | 41 | 33 | 9 |
| Cluster rotation | 54 | 13 | 8 |
| Cluster translation | 52 | 10 | 5 |
| Exchange centers | 55 | 42 | 10 |
| One-sided strip slide | 61 | 18 | 6 |
| Best-of-300 hole relocation | 36 | 7 | 5 |
| Jam-line break / fallback | 47 | 15 | 9 |

An important negative control: **all 47 last-row proposals had zero detected jam lines in their parent state**. They therefore used the native fallback center, not evacuation of a member of a detected crowded row. Accepted mutation IDs alone would have overstated that mechanism's coverage.

The descending target after the initial squeeze was `18.822775656801742`. The terminal accepted raw state was still infeasible. After D4/center assignment alignment it differed from the initial state by RMS center displacement `0.01740`, maximum `0.09788`, and four angle changes exceeding one degree (largest `8.12°`). This is evidence of changed intermediate geometry, not a certified alternative or an unlabeled-topology theorem.

Only the initial feasible packing remained as the best. Its final full certificate gives side `18.822875692446537`, versus canonical n335 side `18.822875655579203`: worse by `3.6867e-8`, consistent with numerical clearance. Its contact and angle arrangement is unchanged. No portfolio merge, score update, remote launch, or submission resulted.

## Retained evidence and interpretation

`artifacts/packer-hop-335-v1/` contains exact inputs and provenance, persistent native stdout/stderr, process receipts, all raw accepted states and energy events, independent energy/jam-line checks, the control certificate, final certificate, and certified output archive. Raw chain states are explicitly **unverified** and must never be treated as valid packing witnesses. A native hop interrupted during a proposal can leave that unfinished proposal unobserved; all reported counts refer to completed events.

This pilot establishes that our implementation tests the persistent-infeasible-state mechanism absent from earlier certified-parent restarts. It does not establish a score benefit. Its narrow target decrement and lack of detected crowded rows limit the conclusion; merely extending the same seed would not be evidence of a different method.

## Calibration for a distinct GPU hop control

Read-only analysis in `experiments/analyze_packer_hop_calibration.py` matched all 147 retained states to the original geometry and each preceding accepted state. Twenty full D4 comparisons, including the largest excursions, all preferred the original orientation. Final report: `artifacts/packer-hop-335-v1-calibration-v2.json`, SHA256 `478da1518b67acc09dab8a32cf6d7deb13347e601816b49659612d87d3d512d9`. The two analysis passes took 10.65 and 9.88 CPU seconds; they did not optimize or repeat certificates.

| Quantity | Median | 90th percentile | Maximum |
|---|---:|---:|---:|
| Accepted proposal physical energy | 4.25e-8 | 5.81e-8 | 1.03e-7 |
| Rejected proposal physical energy | 1.73e-6 | 0.01890 | 0.34284 |
| Accepted uphill energy ratio | 1.086 | 1.523 | 2.195 |
| Accepted uphill additive barrier | 2.55e-9 | 2.11e-8 | 5.62e-8 |
| Rejected energy ratio | 42.48 | 425,094 | 15,963,701 |

Most accepts returned close to their preceding physical configuration: **106/144** had matched center RMS below 0.001 and maximum matched angle change below one degree. All 42 accepted center swaps met that test, with median RMS `1.6e-7`; 28/33 one-angle moves also returned nearby. Larger accepted steps came from cluster translations (8/10 outside that near-return band), shakes (6/6), rotations (7/13), and some strip slides (5/18). The largest immediate RMS step was 0.01729 from a cluster translation; the largest immediate angle change was 6.48 degrees from a strip slide.

Cumulative RMS displacement from the original had median 0.01666 and maximum 0.02491; the largest matched center displacement was 0.1032. The number of squares differing by more than one degree had median two and maximum nine, with maximum angle difference 8.345 degrees. These measurements support localized drift, with no demonstrated large change in occupancy. Contact-threshold differences alone do not establish distinct topological basins, especially for infeasible states.

Native acceptance is a **ratio-temperature** rule:

`P(accept an uphill proposal) = exp(-log(E_proposal / E_current) / T)`.

Thus temperature is dimensionless and a common scalar energy normalization cancels. At an energy ratio of 100, acceptance probability is `2.15e-7` for T=0.3, `0.01` for T=1, and `0.2154` for T=3. The observed cold chain did not cross the large relative barriers that a hotter partition would permit. A concrete 32-chain control is eight chains at T=0.3, twelve at T=1, and twelve at T=3, each group split evenly between native amplitude 1 and 1.5. This is a proposed discriminating experiment, not a forecast of score improvement.

At native amplitude 1, cluster rotation standard deviation is 0.15 radians, cluster translation 0.3 units, strip translation 0.2 units, and shake position standard deviation ranges from 0.05 to 0.35. Amplitude must be translated explicitly if GPU move parameters use different units. Center swaps deserve little budget given their observed physical redundancy.

For fixed GPU targets such as 18.807 and 18.803, acceptance must compare fresh **physical** SAT-plus-wall energies at the same box within each chain, never ALM augmented loss, different multiplier states, or energies at different box sides. The native energy sums each unordered pair's penetration squared and all four wall violations squared. Changing relative wall/pair weights changes the landscape even though multiplying the whole energy by one constant does not. A target-side change requires reevaluating the current geometry before further acceptance decisions.

## Separate deep-box, hotter native comparator

Root authorized one distinct follow-up, using the unchanged binary and exact prior full-n335 control: `--s 18.807 --temp 3 --amp 1.5 --descend 0`, seed 335031. The native box remains 18.807 while infeasible; upstream would squeeze after feasibility before holding its new best. No solver code changed. `experiments/packer_hop_deep_335.py` enforced 110 seconds of native search and a 150-second whole-process bound; actual inclusive completion was 113.36 seconds.

This run completed 1,249 proposals, accepted 1,220 including 408 uphill transitions, and crossed an accepted energy ratio as large as 635.05. It retained 1,221 exact raw states. The initial minimized physical energy was `3.754842460046486e-4`; no later state improved that record. Consequently the native solver produced neither a feasible `best.out` nor a new-record `best.out.inf`. The initial raw state preserves the actual best observed result. Accepted energy had median 0.2228 and maximum 1.5996. Nine predeclared ordinal samples passed the independent dense-energy check. No native final candidate was emitted for a full gate, and no new full certificate or score gain was claimed.

Unlike the cold run, the terminal invalid state had D4-matched RMS center displacement 0.524 and maximum 1.316; 299 centers moved over 0.1 units, 85 angles changed over one degree, and the largest angle change was 33.9 degrees. This demonstrates large geometric exploration, but the chain wandered far above its starting residual. It supports testing a bounded cooling phase while retaining the best observed state separately; it does not establish a valid alternative packing.

Evidence: `artifacts/packer-hop-deep-335-v1/completion-proof.json`, SHA256 `536f1e040cdab7f636b482f65f6f5be3ba715b40590189e624ad78094a8d816c`, binds 1,232 files. Report SHA256 `c53ab1ba67876f5bf40c711621b1ca5f7c60ddd645425417f45a85751957d223`; executed driver SHA256 `a22faf9755323dc9956b7994415e970a178a6884bff2a8bec11bd38659916ca1`. All raw states remain unverified and were not merged or submitted.
