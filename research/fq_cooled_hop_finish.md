# Native finish of the weighted cooled-hop best

One rigid native finish of the retained best n335 state completed normally in
10.003 seconds. The output passes the unchanged official raw/default-pandas
and independent raw/roundtrip gates, but its side `18.8229053267614937` is
`0.0000296711823` wider than canonical RAW `18.8228756555792035`. No portfolio
change, submission, or broad follow-up sweep was performed.

The input is the exact radians array from
`artifacts/packer-hop-cooled-335-v1/best-infeasible-exact-radians.npz`, key `pose`,
archive SHA256
`58af99513d847949e8f9d65d5732b036078989dd6a47a867e94a40a850cc165d`,
geometry SHA256
`cef0adb5ddcc0f9296b31908aa2c87fa7ba3faae43f06160c2fff76e85d431d7`.
The loader exact-compares it with the iteration-70 raw radians text and binds
the input handoff and native search source manifests. It does not use the
lower-precision degree-format `best.out.inf` as its geometry source.

This state came from the T1→0.1 cooled run, but its best event occurred at
16.513 seconds during the warm T1 phase, after a 40-square cluster translation.
At the fixed 18.807 box, independent energy was `0.00030155242167129024`;
maximum pair and wall overlaps were about 0.0018664 and 0.0014811. It remained
explicitly infeasible. Neither this energy nor its coordinate span was treated
as a feasible score, and the initializer was not legalized or rescaled.

`experiments/fq_cooled_hop_finish_control.py` uses the pinned portable FQ binary
and ordinary rigid `--loosen 1 --outer 45 --pit 100 --flip-top 16 --v`, with one
CPU, a 25-second inclusive trial limit and 45-second outer supervisor. Encoding
only translates centers and converts radians to native degrees. Terminal
rounding repair and all full gates are unchanged. The valid result is retained
before the search-band filter despite being wider than the invalid initializer.

All inputs, source/proof bindings, native logs, certificates and the retained
pose are in `artifacts/fq-cooled-hop-native-finish-v1`. Donor archive SHA256:
`f004636b6085482b9dce9afa17248eade901b94ab51a516cc5bd1e6a751f05f1`.
Provenance SHA256:
`67c83b5061c0d66d770ee94e7013f1630f8dedde4289b7900949a18548788c1b`.
Executed source SHA256:
`bf8efe26b63ca4a7e1862e0d80a1120bb96ddebbaa073de5e5ad1009e64e3a3c`.
