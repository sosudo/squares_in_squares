# Forced angular randomization with a held rounded return

The four authorized n335 controls completed in **48.07 seconds on one CPU**. All four returned exact unit squares and passed fresh official raw/default-pandas and independent interval checks. None improved the current side **18.822875655579203**.

| Source | Randomized angle mask | Final side | Excess over current |
| --- | --- | ---: | ---: |
| Current, 44 tilted | All 335 | 18.882974076132186 | 0.060098420553 |
| Current, 44 tilted | Core and nearby upright, 83 | 18.885157921335129 | 0.062282265756 |
| Buffered initial, 37 tilted | All 335 | 18.884473613298837 | 0.061597957720 |
| Buffered initial, 37 tilted | Core and nearby upright, 73 | 18.865180796959567 | 0.042305141380 |

This test addressed the possibility that earlier native kicks changed angles too little to leave the original arrangement. Each selected square received a uniform angle offset over one symmetry period, [-pi/4, pi/4]. Both treatments of a source used identical uniform center jitter within ±0.02 per coordinate, and the same underlying angle-offset array. The restricted mask included folded angle >0.018 radians and centers within1.7 of a tilted center. Raw mutated starts were explicitly unvalidated; no normalization, scaling, clamping or geometry repair occurred before native input.

The native input header retained the valid source's original box: 18.822875655579203 for current and 18.826605669096697 for the buffered initial geometry. The mode used `--round-r0 .49 --round-steps 24 --round-p 1 --round-kick 0 --hold-f 1`, without `--round-compress`, followed by the existing ALM45/polish100/flip16 rigid finish. Every actual trace contained24 monotonically decreasing radii, first0.4696 and last exactly0. The native `s_soft` and `s_hold` matched the unchanged header within its printed precision. The rigid finish is allowed to expand the side, explaining valid final boxes larger than the held rounded-stage box.

The comparison always uses the valid current n335 side, including when the source is the worse buffered arrangement. The deliberately invalid starting span cannot count as a gain. Every fully certified result was retained even though all fell outside the ordinary search band. Maximum row-labeled angle changes were34–44 degrees, with449–929 changed row-labeled contact edges. These establish substantial motion, but are not permutation-invariant topology proofs. Four trials do not exclude better outcomes from another schedule; they provide no evidence for extending this unchanged treatment.

Evidence is under `artifacts/fq-forced-angle-control-v1/`:

- `manifest.json`, `inputs.npz`, and `source-bindings.json` bind both parents, the four raw starts, masks, perturbations, native options, frozen dependencies and binary.
- `trials/` retains exact native text, stdout/stderr, output poses and radius checks. Individual trials include certification within their25-second limit; all completed without timeout.
- `strict-stages/` retains each immutable certified pose and proof before aggregation.
- `analysis.json`, `results.json`, `summary.json`, and `supervisor.json` record fair comparisons and the120-second outer bound.
- `remote-certified/donors.npz` has all four poses, SHA256 `457bb71b956e7e0f86448b1e3f3b49ffa0b61f0f235dfaef54f864c9fd575583`; adjacent `provenance.json` SHA256 is `10a76d9dafe1be32127ea2c6f4a23fac460b4678bcc860ccf654a97918f9dbc6`.

Executed wrapper SHA256: `de339342b8694eb2d757910b67b9c63eac11a27ee86cbcc5e500cf2ce290e410`. Binary SHA256: `10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`. The buffered source is the exact initial geometry from `n335-buffered-seed-v1`, not its later rigid result. No GPU work or competition submission was performed.
