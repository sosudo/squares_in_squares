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
