# Matched native SQP pilot

The finite pilot completed in **37.34 seconds on two CPU workers**, with no material improvement. It used the unchanged MIT native FQ binary `10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d` and current RAW `3855c47798708e4bfb9f053024e6542b0a2a5021824bfd310290e4e7ab1ff9ea`.

The treatment added only `--sqp` to `--no-alm --loosen 1 --pit 40 --flip-top 0 --v`. Each pair shared exact native input bytes and seed. The six heterogeneous targets were n418, 453, 641, 693, 742 and 861. A matched n17 control, with center coordinates initially dilated by 1.0005, preceded them. Both control outputs passed the unchanged full gates and recovered the incumbent within 1e-6 side.

The SQP option supplies a diagonally convexified contact Lagrangian Hessian after an accepted step. It is not an unrestricted Newton method or an occupancy-changing intervention. Native trust regions, merit acceptance, geometry encoding/decoding, and all strict final gates stayed unchanged. The broad contact campaign had not used this option.

Native work and certification had separate eight-second limits. Original decimal output bytes, logs and parsed raw coordinates were preserved before decoding or certification. All certified outputs were retained regardless of their side. A 180-second process-group supervisor bounded both workers and all descendants; it was not needed to stop the completed finite matrix.

Activation was observed on all six targets and the positive control. The runner removed inherited `FQ_*` environment variables, explicitly enabled the native IPM, and recorded `FQ_TR`/`FQ_LPT`. A primary non-IPM solver call after an accepted step, without an explicit IPM fallback, identifies a nonempty SQP Hessian under the pinned implementation. This is source-supported inference from the actual solver trace, not directly instrumented Hessian values. The n17 treatment recorded five accepted steps and four such calls. Target counts were 15, 10, 1, 7, 8 and 3 respectively for n418, 453, 641, 693, 742 and 861.

| Case | LP result | SQP result | Material gain |
| ---: | --- | --- | --- |
| 418 | Fully certified | Fully certified | None |
| 453 | Fully certified | Fully certified | None |
| 641 | Fully certified | Fully certified | None |
| 693 | Native eight-second timeout | Native eight-second timeout | Unresolved within cap |
| 742 | Fully certified | Native eight-second timeout | None from completed arm |
| 861 | Fully certified | Fully certified | None |

There were 14 trials including the two controls, 11 fully certified geometries and three native timeouts. No certification timed out. Four completed target pairs showed no SQP improvement over either the LP control or the incumbent. The summary's positive difference of 1.2064e-13 score came from n742 LP and is explicitly excluded from strict gain accounting; `analysis.json` records zero admitted gain. Timeouts do not establish convergence or a negative result for longer native runs.

The complete evidence is `artifacts/fq-sqp-pilot-v2/`: frozen source, seven inputs, binary, original native returns, exact certificates, paired comparisons and supervisor receipt. Executed wrapper SHA256: `98fa1a6178446c52e7ca6e656999eb32d23ea7280796a11b04cfeaaaefa91aa7`. Donor archive SHA256: `2bee6a921103c1de257aa036d485361a7a73b8c51138a933e163b76790a120ef`. The independent source/interface review is `independent_source_review.json`, SHA256 `d29120af76ab141970933d8187ceff582d2df83cb26b7a8b9c6141c6d3578d1f`.

No canonical portfolio or competition submission was changed. This finite pilot is closed without an extension.
