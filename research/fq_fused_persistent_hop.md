# Persistent chains with the corrected fused FP64 quench

This experiment keeps the reviewed physical moves, fixed-box Metropolis acceptance, persistent current/best states, decision-time cooling and atomic raw packet retention from the Torch hop pilot. Its one algorithmic change is the local repair engine: the unchanged corrected rectangular CuPy FP64 L-BFGS kernel replaces the two-outer-step Torch ALM repair. The kernel runs400 iterations at exact unit-square tau0, with the existing symmetric exact-axis gradient rule and `--fmad=false`. No CUDA source, tolerance or tie-control change is introduced.

The native quench loss has different wall/pair weights from the physical acceptance energy. It is never substituted into the acceptance rule. The unchanged dense Torch FP64 helper freshly computes the sum of all unordered-pair SAT penetration squares and four wall penetration squares on the returned coordinates. The quench's native residual can describe a rejected line-search trial and remains diagnostic only. The repair input is copied from a DLPack view before the in-place kernel; synchronization and a returned Torch clone preserve the exact saved proposal.

The32-chain design and three335 input sources are unchanged from the preceding hop pilot. Fixed sides are18.807 and18.803; base temperatures0.3,1 and3 have8,12 and12 chains, split across amplitudes1 and1.5. The parent epoch allocates120 seconds hot and60 seconds at0.1 times the base temperature. The absolute search bound includes child startup. Each proposal's actual decision time determines its recorded and applied temperature.

The preflight first runs the existing corrected-kernel directional/tie controls and full335 unchanged-seed, last-index, spatial-hash-boundary and positive-repair controls with their full geometry certificates. An additional three-batch smoke tests96 actual400-step repairs, untouched proposal bytes, nine independently calculated physical energies, scalar ratio decisions and pending/completed packet hashes. The smoke requires at least20 repaired poses/second before the search can run. This is an interface throughput gate, not a convergence or feasibility assertion.

All stages remain raw and unverified until full admission gates. The raw capacity is2,048 packets/4GiB, raised to avoid truncating cooling when the faster kernel produces more proposals. Search is bounded at180 seconds, worker300 seconds, outer alarm475 seconds and server600 seconds. One device is used in the private offline T4 session. No native finishing or competition submission occurs inside this notebook.

The first frozen source, `b572cad7919681dc77341c6d7b9eebf516cb4db6c17b03f2b7ebcfdf70830b65`, failed after15.15 seconds at an omitted transitive import, `fq_coherent_clusters`, before any CUDA control or search. That source and its traceback remain under `artifacts/fq-fused-hop-job-v1/` and `artifacts/fq-fused-hop-failure-v1/`. The corrected version adds only that exact helper from the frozen corrected-v2 payload; all existing payload files and numerical controls are identical. Recursive dependency closure and isolated extracted-payload imports were checked before relaunch.

The corrected private notebook is `sos54352/squares-fused-persistent-hop/2`. Frozen source SHA256 is `e608718a725a16fc241a5ad69f711a0533e9b5cfdb699c983d1765d36a7cf1d7`, with65 hash-bound payload files. `artifacts/fq-fused-hop-job-v2/` records the remote exact-source/private/GPU check, independent adapter review, structural delta proof and extracted import smoke. The generated search function changes exactly one quench block and one preflight identity check; the parent process/recovery supervisor is unchanged. Its source SHA256 is `eca57325e71b9b7699b7f8d9b90060db8b7de3cb1e1038a9ff1513e409acff0e`.

## Actual result

All actual-device controls passed. Preflight took8.87 seconds; the96-pose interface smoke measured125.53 poses/second. The full notebook worker completed in221.66 seconds. The parent enforced the180-second search boundary, then spent3.93 seconds recovering committed CPU packets; this recovery time is included in the reported183.93-second search-supervisor interval and does not represent additional GPU search.

The pilot completed **21,600 proposals**, plus32 initialization quenches, in the180-second parent epoch: **120 proposals/second**, or17.76 times the preceding Torch pilot's1,216 proposals. Of these,17,164 were accepted and5,630 were uphill. The hot phase completed14,272 proposals and the cool phase7,328. The quench interface accounted for112.01 seconds; the remaining67.99 seconds combines startup, mutation, physical-energy evaluation, packet writing and other control overhead, which were not independently timed. Every native report reached iteration index399; no explicit native stop-reason field exists.

Storage did not truncate cooling:676 completed packets and one pending packet retain1,083,607,029 bytes, below both2,048 packets and4GiB. Exact current/best states were recovered from the final committed packet. The pending proposal remained separate and unaccepted.

| Base T | Best penalty median | Terminal penalty median | Terminal / best median | Best updates during cooling |
| ---: | ---: | ---: | ---: | ---: |
| 0.3 | 0.00049553 | 0.00051386 | 1.053 | 34 |
| 1 | 0.00055710 | 0.03243183 | 52.70 | 0 |
| 3 | 0.00062450 | 0.04614312 | 79.19 | 0 |

Every T3 chain recorded its final best by9.22 seconds; every T1 chain did so by56.61 seconds. The colder chains continued improving late: the best18.807 penalty decreased from0.00029145 at120 seconds to0.00026546 at179 seconds, while the best18.803 penalty decreased from0.00049963 to0.00049286. Hotter chains accepted many moves but lost good current states and did not return to them during cooling. This supports testing same-box exchange or explicit best-derived restarts, and comparing deeper local repair, rather than merely extending identical hot wandering. No such follow-up is implemented in this run.

The minimum penalties were0.0002654600854 at18.807 and0.0004928605651 at18.803. By source, minima were0.00026546 for source43,0.00029486 for the current44 source, and0.00058545 for buffered37. These are optimization diagnostics only: there were zero floating zero-energy states, and **all32 best poses failed rounding-only repair**. Their maximum pair overlaps were at least0.00150.

The full event audit replayed acceptance decisions, decision-time temperatures, current-state continuity and best monotonicity. Independently recomputed energies of all64 terminal current/best poses agreed within9.72e-17. Validation separately checked the last completed→pending→recovered byte links and288 energies across all nine terminal pose arrays, maximum error8.88e-16. Numerical energy agreement does not certify those overlapping states.

Four selected best states were handed to the standard native finish: global best18.807(chain1), best18.803(chain7), best buffered37(chain15), and a distinct hot reference pose(chain28). The final archive and origin packet/member hashes are bound in `artifacts/fq-fused-hop-finish-handoff-v1/manifest.json`. The four-pose state archive SHA256 is `49a1c3dccb73e359c5f341693083e08ce2147137f190c015c1c560dd7b4a876a`.

All four native finishes passed full geometry gates but **none improved the portfolio**. Sides were18.822879218438158,18.823755594840202,18.827682089231154 and18.822875694582324, respectively, versus current RAW18.8228756555792035. Their fully certified geometries remain in `artifacts/fq-fused-hop-native-finish-v1/`; donor archive SHA256 `66d48dc28bb7471cc10c957deac2a113fa8278fbf3da57d792841c0b3845d416`.

Terminal evidence is in `artifacts/fq-fused-hop-results-v1/analysis.json`, `progression.json`, `independent-terminal-state-review.json`, and the exact downloaded outputs. The retained raw packet index also binds the remote raw states that were not downloaded. No residual reduction was promoted to a feasible gain, and no submission was made.
