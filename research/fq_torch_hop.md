# Persistent fixed-box GPU hopping

The first bounded pilot completed 38 real batched rounds: 1,216 proposals,
452 accepted transitions, including 163 uphill transitions. It produced no
zero-energy state and no newly certified packing. Its separate per-chain best
archive improved floating overlap penalties for 29 of 32 chains. These are
optimizer diagnostics, not leaderboard improvements or proof of a new basin.

## Frozen method and controls

The new files are `experiments/fq_torch_hop.py` and
`experiments/fq_torch_hop_pilot.py`. The launched frozen source is
`artifacts/fq-torch-hop-job-v2/search.py`, SHA256
`a57ae191b9c61aee32b9a505a963de1bd585dfe815bf103d83e827b067a7e3b1`.
The lifted ALM core remains byte-identical
at SHA256 `c3ce3b8a99f55776bcb4727ad98dd100bad678593746fbdc828436699c03eb83`.
The source fixtures and notices are the exact reviewed payload of the earlier
ALM pilot `477fcf1001bca71020f16c2668951ec279a39c2176f55b7fa989d893e379059e`.

There are 32 independent full-count n335 chains. Each retains its accepted
overlapping unit-square pose at one fixed side, either 18.807 or 18.803.
Temperature strata contain 8 chains at T=.3, 12 at T=1 and 12 at T=3. Every
stratum is evenly split between amplitude 1/1.5 and the two boxes. Three
previously certified starting layouts have 44, 43 and 37 tilted squares.

Each proposal mutates the accepted pose, then runs the unchanged ALM core at
radius exactly zero and fixed side, with at most two outer iterations and
24 L-BFGS iterations per outer iteration. The four moves are local shake,
rigid cluster rotation, rigid cluster translation and an explicit one-sided
strip slide, with weights 2:2:3:3. Move scales adapt Evan Daniel's MIT packer
at commit `659ee62e4a9d39542a1146e8b011cc3ab6407ede`. Actual selected/changed
square IDs and physical displacement are recorded. There is no jam-line
operator or claim of jam-line evacuation.

Acceptance uses a fresh dense physical penalty at the same fixed box:
the sum of squared positive four-wall violations plus the sum of squared
positive minimum four-axis SAT penetrations over every unordered unit pair.
It never uses the multiplier-dependent ALM objective. A downhill proposal is
accepted; otherwise the native dimensionless ratio rule is applied:
`log(Eproposal/Ecurrent) < -T*log(U)`, with explicit finite/zero handling.
Accepted state and lowest observed physical-energy state are retained
separately. The latter may come from an input or quenched proposal, including
a rejected proposal.

The first 120 seconds use the base temperatures. Decisions in the final
60 seconds apply T multiplied by .1, without resetting accepted chains.
Every decision records its monotonic time, the parent search deadline, base
and applied temperatures, phase, uniform draw, log ratio and threshold.

The search runs in an inherited-process-group child bounded at 180 seconds.
The overall worker/parent/server bounds remain 300/475/600 seconds. A pending
packet preserves exact input/current/best before quenching. A separate complete
packet preserves input, quenched, old current, accepted current, old best and
new best before state commitment. Atomic index publication precedes input-file
removal. An interrupted publication therefore leaves either the old pending
input or both complete and pending artifacts. CPU-only recovery uses the last
indexed complete packet; unindexed complete artifacts are explicitly reported.
The 512-packet/1-GiB caps reserve peak pending/output coexistence before a new
proposal begins. Every raw state remains UNVERIFIED.

Seven focused controls cover analytical dense pair/wall/final-index energies,
ratio thresholds and zero handling, actual move masks, finite strata, cooling
boundary, exact packet recovery, pending-only initialization and interruption
during completed-index publication. They passed in .015 seconds, excluding
imports. Independent full335 CPU comparisons agree with a separate dense
physical oracle within 1.74e-18. The unchanged live ALM preflight executes in a
separate directory before search; it includes native/masked objective checks,
Verlet rejection, genuine full147 pair repair, exact zero-radius/count controls
at147/299/335 and a full335 final-index duplicate negative.

Independent source/control reviews are
`artifacts/fq-torch-hop-helper-independent-review.json` and
`artifacts/fq-torch-hop-independent-delta-review.json`.

## Actual finite results

Actual outputs are in `artifacts/fq-torch-hop-results-v1/outputs`. The parent
enforced the 180-second search timeout. CPU recovery found 39 completed packets
(one initialization plus 38 real rounds), 1,248 completed chain quenches, and
one pending packet. Recorded wall time after kill/recovery is 180.407 seconds;
that includes recovery overhead and should not be described as a new search
allocation. All previously published states survived. The raw packet total was
about63.3MB, well below the cap.

Cooling first applied to packet26 at decision elapsed124.10 seconds. Hot and
cooled acceptance counts were:

| Base T | Hot proposals / accepted / uphill | Cooled proposals / accepted / uphill |
|---|---:|---:|
| .3 | 200 / 45 / 15 | 104 / 9 / 1 |
| 1 | 300 / 101 / 48 | 156 / 26 / 4 |
| 3 | 300 / 191 / 73 | 156 / 80 / 22 |

Hot T3 accepted an uphill ratio as large as892.6, demonstrating materially
larger accepted barriers than hot T.3 (maximum1.73). Cooling reduced the T1
median current penalty from .001870 to .000701, and the T3 median from .09931
to .01908. Some T3 chains remained highly overlapped: final maximum current
penalty4.4317. The retained best arrays are essential; the current endpoint
alone is a poor handoff for those chains.

The best observed penalty improved from .00057802 after initialization to
.000435835. There were 67 subsequent per-chain best updates, all from quenched
outputs. By recorded operator: strip slides supplied51 updates from366
proposals, cluster rotations13 from264, shakes2 from245, and cluster
translations1 from341. This is an association within the finite trace,
not an ablation or a claim of persistent topological changes. Every proposed
move changed at least one actual unit, but quenching can undo those changes.

The lowest-penalty best endpoint is chain8, reference335/T1/amplitude1 at
side18.807. A bounded source-diverse endpoint list is:

| Side | Source | Chain | Best floating penalty |
|---|---|---:|---:|
| 18.807 | reference335 | 8 | .000435835 |
| 18.807 | source43 | 1 | .000457325 |
| 18.807 | source37 | 10 | .000661220 |
| 18.803 | reference335 | 13 | .000679204 |
| 18.803 | source43 | 11 | .000642124 |
| 18.803 | source37 | 3 | .000940125 |

Those are unverified optimization inputs. A strict full geometry/decimal and
ordinary pandas transport gate, followed by comparison with the canonical
portfolio, is still required for any score claim. No competition submission
was made by this experiment.

The source-bound trace analysis is
`artifacts/fq-torch-hop-results-v1/operator-temperature-analysis.json`, SHA256
`3901bfd053bffd4c91bccb49a6966721ab8964dee2ffa5b7fba1568a93593975`.

## Bounded native finishing consequence

A separate root-authorized one-worker check finished BEST chains8,11,28 and10
with the pinned native optimizer. All four final outputs passed the full
certificates, but none improved canonical335. The first three returned to
sides about18.82287569–18.82287576; source37 returned to18.82660566908.
This finite consequence supplies no score benefit and does not justify an
unchanged extension. Every valid returned geometry remains retained.

Evidence is `artifacts/fq-torch-hop-native-finish-v1`; its four trials took
25.95 seconds. The exact results SHA256 is
`158b58da51a8bd605001a707d986439e4043878ec3f8b7802b36d5f999096504`.
The independent actual-run audit at
`artifacts/fq-torch-hop-results-v1/independent-actual-run-audit.json` replays
all39 events and verifies representative full335 packet energies, acceptance,
best/current selection, cooling and pending-timeout recovery. Protocol
correctness remains separate from geometric or score success.
