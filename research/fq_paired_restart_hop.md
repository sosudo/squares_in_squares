# Paired persistent chains with bounded hot excursions

The first fused persistent-chain run explored n335 at 120 complete proposals per
second, but the hot chains finished far above their best overlap penalties.
Its base-temperature 0.3 chains kept improving during cooling; native finishes
of four selected states produced no portfolio gain. This experiment transfers
the method to n453 and n693 and tests whether periodically restoring hot chains
to their own retained best state makes their exploration more useful.

The frozen input is the certified `fc931068f0f4…` raw portfolio. The two reference
sides are 21.808663234397324824… and 26.814949271823154329…. Exact original and
translation-only normalized arrays, row text hashes and provenance are retained
in `artifacts/fq-restart-hop-inputs-v1`. Both targets have dated public headroom
and different angle/contact families from the previously tested n335 ribbon.

Each device owns one case and 32 chains, arranged as 16 matched control/treatment
pairs. Each pair uses the same source, fixed box, base temperature, amplitude and
per-round random stream; its acceptance draw comes from an independent paired
stream. The box is either 0.002 or 0.008 smaller than the reference side. Both
arms use the unchanged corrected FP64 unit-square quench, tau zero, 2,000 steps,
and compiler options `--std=c++17 --fmad=false`. Physical Metropolis energy is
recomputed independently from the returned pose, rather than using the weighted
quench loss or possibly stale native residual.

The treatment restores only its base-temperature 1 and 3 chains to their own
best states every 16 completed hops during the first 450 seconds. It performs
one more such reset at the cooling boundary. The final 150 seconds multiply all
temperatures by 0.1 and preserve every chain continuously. Base-temperature 0.3
chains remain persistent throughout both arms. No state moves between arms.
If a quench crosses the boundary, acceptance uses the recorded decision-time
temperature; the boundary reset follows that decision and best-state update.

Every completed packet retains pre-reset current, effective parent, actual
mutated input, previous best, quench output, committed current and new best.
Packet publication precedes state commitment. A 6 GiB/3,000-packet limit per
case reserves 40% for cooling and reports any storage-induced hot-phase pause.
The common search lasts 600 seconds; the worker/whole/server limits are
850/900/1,200 seconds. Terminal recovery reads the final hash-bound packet rather
than rereading all raw storage.

Native finishing selects exactly one lowest-energy best state per arm and box,
four slots per case. Slots are interleaved and paired native seeds are equal.
Each gets at most 12 seconds of native optimization and a separate 8-second
certificate allowance. Complete native decimal output is retained before any
gate. All valid poses are archived, and improvement uses the worst side across
official raw, both pandas transports and independent interval checks. A combined
certified score improvement of at least 0.00001 is the predeclared threshold for
considering an extension. Floating physical penalties alone establish no gain.

The launched source is
`artifacts/fq-restart-hop-job-v2/search.py`, SHA256
`d350aebf10c9bcd07eab3088fd33778cb2e9b55e114eb95bbf0b51a9883f070f`,
995,672 bytes with 150 hash-bound payload files. The isolated import/input smoke,
five protocol tests and six finisher tests passed. The protocol tests execute
the actual generated controller with synthetic CPU physics across both reset
and cooling boundaries. Actual n453/n693 GPU physics, full certificates, copy
isolation, dense physical energy and throughput controls must pass on both
devices before search. Private notebook:
`sos54352/squares-paired-restart-hop-453-693/1`.

The notebook completed with supervisor exit zero in 682.05 seconds. Both actual
size controls passed, in 10.57 and 16.62 seconds. Search children were stopped at
the common 600-second deadline and their last committed packets were recovered;
each also retains one uncommitted pending input. Neither storage limit was
reached, and neither case paused hot search to preserve storage. All recorded
acceptance, paired-uniform, reset and decision-time cooling checks pass.

| Case | Complete proposals | Proposals/s | Hot / cool proposals | Quench seconds |
|---|---:|---:|---:|---:|
| 453 | 12,960 | 21.60 | 9,696 / 3,264 | 513.74 |
| 693 | 9,472 | 15.79 | 7,072 / 2,400 | 474.72 |

The native iteration report reached 1,999 for 12,986/12,992 quench rows at n453
and 9,503/9,504 at n693. Deeper quenching still usually exhausted its iteration
allocation. Physical energy remained positive in every observed state.

The reset policy addressed hot-chain wandering. For base temperature 3, median
terminal energy divided by best energy was 12,307 in the n453 control and 1.53
with resets; the n693 ratios were 17,407 and 1.74. Median best energy relative to
the initial quench was 1.0 for both T3 controls, versus 0.969 and 0.864 with resets.
During n693 cooling, treatment chains recorded 29 best updates versus 3 in the
control. These are penalty improvements, not geometry certificates or proof
that a longer run would find a better packing.

At n693's 0.002 contraction, best physical energy fell from approximately
3.74e-6 to 1.223e-6 in the control and 1.138e-6 with resets. At 0.008 contraction,
the best penalties were 4.318e-5 and 5.289e-5 respectively. The treatment does
not dominate every contraction or chain. Preflight matched input bytes exactly,
but GPU output trajectories were not bitwise identical across paired rows;
this numerical variability is retained in the control report.

All four n453 native finishes passed the full gates but returned sides about
4.16e-8 wider than the frozen reference. All four n693 native finishes timed out
at 12 seconds without producing output. Thus the original run has zero
certified score gain, with n693 finishing unresolved. Root authorized a separate
120-second, two-CPU completion of exactly those four selected inputs with a
40-second native allowance and unchanged 8-second certificate allowance,
options, paired seeds and slot allocation. No new GPU search or reselection is
part of that recovery.

That separate completion finished in 62.47 seconds and all four selected n693
states passed the full gates. Native calls needed 27.63–29.61 seconds, explaining
why every original 12-second finish failed to publish an output. The best was
control / contraction 0.002 / chain 2, with certified side
26.813946701004592194…, a side reduction of 0.00100257081856 and a score reduction
of **0.00003808451614**. Reset / 0.002 / chain 18 reached 26.813949391214426537…;
control / 0.008 / chain 11 reached 26.814333324824699067…; reset / 0.008 / chain 30
reached 26.814948229338201122….

The combined certified gain exceeds the predeclared 0.00001 threshold. Both
strongest states were base-temperature 0.3 chains, which remain persistent in
both arms. Therefore the result supports persistent low-temperature full-pose
search followed by sufficient native finishing; it does **not** establish that
periodic hot-chain resets improve the score. No further GPU run was launched.
Exact completion provenance, selected inputs, native decimal outputs, all four
certified geometries and the strongest-current comparison are retained in
`artifacts/fq-restart-hop-n693-long-finish-v1`.

Aggregate outputs and the all-event analysis are in
`artifacts/fq-restart-hop-results-v1`. Selected reset, boundary, terminal and
pending packets plus the full GPU controls are in
`artifacts/fq-restart-hop-packet-audit-v1`. Exact four-state native input bytes
are in `artifacts/fq-restart-hop-n693-finish-inputs-v1`.

The independent packet audit verified all 32 state transitions in selected
periodic, cooling-boundary and terminal packets, including their predecessors
and next uncommitted inputs. Its 296 predeclared dense all-pair energy checks
matched within 1.33e-15. Receipt:
`artifacts/fq-restart-hop-results-v1/independent-packet-energy-review.json`,
SHA256 `76bbc0a5aa67c09834cf3062f7b1febeea1cf100037df47bf65782e728ae0ecc`.

The older unlaunched `fq-restart-hop-job-v1` remains intact but does not contain
the final hot-only reset policy and must not be used.
