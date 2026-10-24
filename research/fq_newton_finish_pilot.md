# Matched Newton finishing on current contact-polish tails

The current n761, n981 and n995 layouts came from runs that reached their
80-step polish limit. n920 stopped after 65 steps without a reported reason.
The pinned solver also offers a Newton finishing path that has not been used
in the checked campaign scripts. It projects a stable load-bearing contact
set, then solves stationarity and checks feasibility and equilibrium. These
internal checks do not replace our independent geometry certificates.

This finite pilot compares LP alone with the same LP plus `--finish` on fresh
current n761, n920, n981 and n995. Both arms use no ALM, loosen 1, 100 polish
steps, no branch flips and `--stag-w 0`. Disabling the rolling side-stagnation
cutoff is shared between arms. The only treatment difference is `--finish`.
Both arms use identical inputs and native seed 9480000+n. This distinguishes
any benefit of Newton finishing from simply allowing more LP iterations.

Before target jobs, both arms must repair a center-dilated n17 control to
within 1e-6 of its certified reference. The finish arm must also emit actual
`FQ_FIN` Gauss-Newton or KKT diagnostics; requesting the option alone does not
establish activation. On targets, activation, internal finish success/failure,
returned coordinates and fully certified side lengths remain separate facts.

The unchanged native binary is
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.
Input RAW is `28feb2d3059e33db0189aa46c2bdb5f1a0f0c0aa35fb0f2003181595491ba6a3`. Every input geometry and encoded
native input is hash-bound in `artifacts/fq-newton-finish-pilot-v1/manifest.json`
(SHA256 `0f990cc2e3249603836123cc02c51e0711ca50cfa79b8cfb0de83f673a15d029`). The new experiment is
adapted from the existing matched SQP harness; previous sources and outcomes
remain unchanged. Native source, MIT license and notice are copied with the
frozen execution evidence.

Two local CPU workers each have a 60-second native cap and a separate
8-second certificate cap. The whole experiment is bounded to 360 seconds,
with a process-group kill at 357 seconds. Native bytes are saved before
certification, and every certified result is retained, including worse ones.
No trace side or merit value counts as a packing. Only full per-case gates
and a later full portfolio validation can establish a score improvement.

The pilot completed with all ten returns fully certified. Newton finishing
activated on the n17 control, but its stable-contact trigger never fired on
any of the four targets. All four LP/finish pairs produced identical certified
side lengths. This therefore gives no evidence of a Newton advantage on
these targets; it is not a test of forcibly invoking Newton on their unstable
contact sets.

The LP-only results improved n761 by 0.0002047514854 in side and n995 by
0.00001832681357. Their combined qualifying score gain is 0.000008003234596.
The n920/n981 changes were below the predeclared 1e-8 side threshold and are
not candidates. The raw summary includes their tiny arithmetic deltas;
`completion-review.json` separates those from the two admitted candidates.
Every certified pose and both arm histories remain retained. This finite
Newton pilot is closed, without a broader repetition.
