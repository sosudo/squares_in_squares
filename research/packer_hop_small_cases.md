# Small-case persistent native hop pilot

This bounded pilot applies the existing persistent native Metropolis mechanism to two smaller puzzles, changing the case rather than repeating another n335 restart. It uses one CPU,130 seconds per case, and a320-second external supervisor. The telemetry binary is unchanged from the independently checked n335 pilot: SHA256 `39e7699fc507a67d4acfc75465a476b69a5647058c60bd90832ce6996dc3cf25`.

The selection screen compared every available dated public reference for n≤200, excluding65, with the hash-bound current6764 safe portfolio. Only three cases had a score gap above1e-9:

| n | Current safe side | Dated public side | Potential score gap |
| ---: | ---: | ---: | ---: |
| 147 | 12.6568542495040365 | 12.6510435536274192 | 0.0004792581184 |
| 179 | 13.8837954905237819 | 13.8821837703373450 | 0.0001204656227 |
| 182 | 13.9740907131344163 | 13.9727613470647018 | 0.0000985391691 |

The reference is the publicly rendered inversion per-puzzle leaderboard, version10/session361620939, evaluated2026-10-24T00:02:02.353Z. These scalar observations establish documented headroom, not available coordinates or a guarantee of attainment. The complete screen and exact source/report hashes are retained in `artifacts/packer-hop-small-v1/headroom-ranking.json`.

The chosen starts are structurally different: n147 has64 tilted squares at45 degrees, whereas n179 has35 tilted squares with four rounded angle families from41.154 to44.362 degrees. Both come from the verified6764 safe CSV. Inputs undergo translation-only normalization into the physical square box; the encoded count, absolute side, coordinates and degree angles are retained. Native raw telemetry stores exact radians and remains explicitly unverified.

The fixed native options are amplitude1, maxit3000, descend0.0001, linepen0 and a sufficiently large iteration count for an externally stopped130-second chain. Case147 uses temperature0.3; case179 uses temperature1. This is an optimization allocation, **not a causal temperature comparison**, because case and temperature both change. Native uphill acceptance is `P=(E_proposal/E_current)^(-1/T)`, using the fresh physical energy of unit-square overlaps and walls at the same box. Temperature1 was selected after the earlier335 calibration showed that temperature0.3 accepted only small relative barriers.

Each case must pass a real native `relax --maxit100` positive control and full fresh geometry gates before starting the persistent chain. Every accepted raw state is retained by the unchanged native telemetry patch. The case driver records complete proposals, acceptance outcomes, uphill counts and a hash index of the raw states. The final best output passes bounded rounding repair, official raw/default-pandas and independent interval gates. Reported score changes compare with the current **raw** portfolio's official side, never an infeasible chain state or a worse intermediate.

All executed dependencies, native source/telemetry patch, binary and inputs are frozen under `artifacts/packer-hop-small-v1/`. The executed driver SHA256 is `b66c58d0b8fe4bd53fefe3e2ea4541c68867cd608471c9ebaef75f08bfd55008`. No existing335 pilot was changed, and no GPU search or competition submission is part of this run.

## Completed result

The complete run took **263.92 seconds**, with no forced outer termination. Both native positive controls and both final outputs passed full gates. **Strict full-portfolio score gain is zero.** The native best files retained the starting side; bounded rounding clearance produced certified sides12.656854272806108 for147 and13.883795516278512 for179, slightly worse than their incumbents. Both positive-control and final certificates were considered when choosing each case's best result. Exact Decimal differences and the explicit side-gain threshold1e-9 prevent roundoff from counting as a useful win.

| Case / temperature | Completed hops | Accepted | Recorded uphill accepts | Raw snapshots | Accepted uphill ratio median / maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| 147 /0.3 | 2,127 | 998 | 445 | 1,001 | 1.0424 /2.2224 |
| 179 /1.0 | 1,196 | 553 | 199 | 556 | 1.1970 /41.4800 |

The hotter179 chain accepted materially larger relative energy excursions, but neither finite chain found a better valid side. Counts are native telemetry, not independent proof of every recorded energy. After the native worker released the CPU, an independently implemented dense all-pairs oracle checked34 states selected by a predeclared evenly spaced ordinal rule,17 per case, excluding the known pre-squeeze `feasible_best` event. Every sampled energy agreed, with maximum absolute error6.88e-19. This audit took0.28 seconds and did not optimize or admit raw states as feasible packings.

Final evidence: `analysis.json` contains strict gain accounting and acceptance summaries; `sampled-energy-audit.json` binds the sample and independent oracle; per-case `events.json` and `raw-index.json` bind all1,557 raw snapshots. All raw states remain unverified beyond the explicitly sampled numerical energy checks. `independent-protocol-review.json` records validation's read-only source/binary/input/gate review. There is no unchanged extension of this negative pilot.
