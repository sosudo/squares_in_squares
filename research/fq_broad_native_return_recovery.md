# Final saved-output recovery from broad contact search

The completed broad campaign had266 saved native outputs.248 already had
successful full certificates; jobs12/26/69 were already recovered separately.
This pass screened all15 remaining returns, without running a native executable
or any optimizer. Four decoded outputs were dominated by the stronger available
comparison. All11 side-promising returns passed fresh full certification in a
total12.63 seconds on one CPU, within the180-second outer limit.

The comparison used the minimum physical-side bound from current canonical RAW,
the **final** broad candidate set, and the three earlier recoveries. Canonical
files were hash-checked and snapshotted again after certification. The recovered
gain beyond that stronger combined comparison is **0.00020177539491064025**.
This is an incremental candidate-set gain; the root's whole-portfolio merge,
SAFE transform and full validation remain the authority for submission score.

| Case | Original job | Incremental score gain |
| ---: | ---: | ---: |
| 550 | 195 | 0.00006175119 |
| 551 | 121 | 0.00005682312 |
| 456 | 67 | 0.00004058318 |
| 505 | 114 | 0.00003889524 |
| 555 | 277 | 0.00000201661 |
| 532 | 120 | 0.00000087828 |
| 645 | 323 | 0.00000047503 |
| 502 | 344 | 0.00000024843 |
| 594 | 313 | 0.00000009814 |
| 988 | 179 | 0.00000000370 |
| 798 | 102 | 0.00000000247 |

Cases632/868/911/912 were dominated after the existing bounded-clearance decode
and were not recertified. Job179/n988 had a complete native `.out` but no
`raw-returned` NPZ, so inspecting only the NPZ directory would have missed it.
Every saved NPZ was accounted for. For the other selected returns, parsing the
native degree output and converting to radians matched the saved array exactly.
All11 prospective outputs also have exact parent-geometry and native input-text
bindings. The original campaign and its source files were never modified.

The implementation reuses `fq_active_pilot.decode` (count/finite checks and
rounding-only clearance2e−9) and `fq_capacity_probe.full_certificate` (official
raw/default-pandas plus independent raw/roundtrip). Both independent side upper
bounds must improve the stronger comparison. Every fully certified output is
retained even if a later comparison were to dominate it. Candidate coordinates
use the same `.17g` decimal representation as their certificates.

Immutable evidence is in `artifacts/fq-broad-final-native-recovery-v1`:

- `candidates.json` SHA256
  `be2b434f394ac0f67c9c2068c5d62e4e8cd12bb70e65b57bb1c667963552ac4d`;
- `donors.npz` SHA256
  `bfb527f383edd52b203a2d4e990d0f0ceaecc5fe515af49f0eadf3168de4315c`;
- `results.json` SHA256
  `f2950816e31da76053730e2047bf32710f079f9e618656055bc5660555e7e0de`.

The directory also preserves final campaign files, all native-return inventories,
the original source/input/output lineage, each completed certificate and the
outer-supervisor result. Executed `experiments/recover_broad_native_returns.py`
SHA256 is `b9f66ac28b2970f729fdb2be2206c2ffc0cca664bb9389b61dd1b5628adfe816`.
No merge or competition submission was performed by this recovery worker.
