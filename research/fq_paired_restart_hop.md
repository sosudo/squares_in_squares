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

Results are pending. The older unlaunched `fq-restart-hop-job-v1` is retained but
does not contain the final hot-only reset policy and must not be used.
