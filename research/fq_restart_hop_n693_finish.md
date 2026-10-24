# Exact retained n693 states: longer native completion

The paired GPU pilot's four originally selected n693 BEST states had no native
return under12-second finishing caps. This followup reused exactly those
states and native input bytes, with no reselection or new GPU work. Only the
native cap increased to40seconds and the fixed four slots were allocated to
two CPU workers; each certificate cap remained8seconds and the outer process
tree remained bounded by120seconds.

All four completed full independent, official raw and ordinary-pandas gates
in62.47seconds total. The strongest result is control/.002, chain2:

| Original slot | Arm | Compression delta | Chain | Worst certified physical side |
|---:|---|---:|---:|---:|
|0|control|.002|2|26.8139467010045922|
|1|reset|.002|18|26.8139493912144265|
|2|control|.008|11|26.8143333248246991|
|3|reset|.008|30|26.8149482293382011|

The current canonical n693 side was26.8149492718231543. The strongest output
therefore saves about0.00100257082 in side, or0.00003808451614 in competition
score before the parent's exact merge and transport verification. Every valid
geometry, including the three less-improved outcomes, is retained.

This does not establish a reset-policy benefit: the best state came from the
control arm, and the leading paired states both used base temperature0.3.
This four-state recovery alone did not isolate GPU initialization from a longer
native solve of the original reference; the separate matched control below
addresses that comparison. The concrete result is a fully certified
improvement from a previously selected, previously unfinished state.

`experiments/fq_restart_hop_long_finish.py` calls the unchanged frozen
`fq_restart_hop_finish._finish_slot` helper, SHA256
`aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543`.
It preserves native options `--loosen 1 --outer 45 --pit 100 --flip-top 16`, exact
paired seeds9710000/9710001, the same portable binary10ec7cf…, and all eight
numerical-source hashes. The original paired GPU source is
`d350aebf10c9bcd07eab3088fd33778cb2e9b55e114eb95bbf0b51a9883f070f`.

Each selected NPZ was checked byte-for-byte against the original committed
`best_after` row. Regenerated native input text exactly matched its downloaded
original `.in` file before launching. Raw native decimal output and logs were
saved before decoding or certification. Candidate text preserves the same
`.17g` representation used by the existing gates. The current comparison was
rechecked against canonical RAW `add7c0ee1599…` at completion.

Immutable evidence is under `artifacts/fq-restart-hop-n693-long-finish-v1/`:

- `candidates.json` SHA256
  `eb62b7cbafdeb2ad0197645931b8096f1d6420106f41d7bc0f7ffa3f8f6cff3e`.
- `results.json` SHA256
  `f5a6cc84633049bb431bfeea85c5d0493ada9880a897e7c013f2ee05c95090ed`.
- `manifest.json` SHA256
  `e3ae5ce36e604dcb82b60afa27b7993ee16721dbeb82858e60306c5cd8e34ddf`.
- `certified.npz` retains all four valid outputs; SHA256
  `3d070f844f5441da2554f40ce69252fc5a9e5919e0ee6ad41ddb5beb88e7fbc9`.
- `inputs/`, `source/`, original download receipts and
  `finish/slot-00-control-0.*` preserve selected geometry, original/native
  inputs, outputs, logs and the winning full certificate.

No canonical merge or competition submission was performed by this wrapper.

## Matched original-reference completion control

A separate authorized control used the exact pre-GPU `reference_693` from the
frozen paired-job input archive, not a generated BEST state. Its geometry SHA
`0c99323787ff7d1e6602e3576976d0c5692cb03bb213956cfe3079aed1f6809e`
is byte-identical to `original_693` from the fc931 portfolio. Binary, native
flags, seed9710000,40-second native cap and8-second certificate cap match the
winning control/.002 finish. The sole numerical-input difference is the
initializer geometry; the shared finishing function changes only its metadata
label from BEST to ORIGINAL for this control.

The control completed all gates in7.74seconds and returned worst certified
side26.8149486729680261. It improves the old reference by only5.98855e-7, while
the GPU-derived winner is better by0.00100197196343. Allowing the same original
reference and seed a longer finish therefore does not explain the observed
winner in this matched comparison. This supports the changed initializer for
this case; it does not establish general GPU superiority or a reset-policy
benefit. The control is worse than current canonical n693 and generated no
candidate for merge.

Source: `experiments/fq_restart_hop_reference_control.py`. Exact inputs,
command comparison, raw native outputs and all full certificates are under
`artifacts/fq-restart-hop-n693-reference-control-v1/`. Result SHA256:
`58adc28cc6b70cfb066e5e6a912fd79192c4221d7733f0b98056f73ab58cbf5e`.
No portfolio, export or competition state changed during this control.
