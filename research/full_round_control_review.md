# Independent review of complete-packing rounded continuation

Both completed controls pass the read-only review. All six physical outputs
retain their unit-square counts and match their existing raw/default-pandas
official and independent interval certificates. No certificates or optimizer
runs were repeated during this review.

The first control uses `--round-compress --hold-f 1.001`. Native rehardening
holds 1.001 times the compressed rounded-square side, not the incumbent side.
Its held sides were 12.09044460, 17.64123450, and 18.68782760 for n147, n299,
and n335. Positive overlap remained at radius zero; the subsequent rigid ALM
and polish expanded the box and produced the certified final arrays.

The second control removes compression, uses `--hold-f 1`, and adds an initial
all-square kick of 0.04. Its native `s_soft` and `s_hold` match the encoded input
side within 3.3e-13. Because the initial kick also changes, this comparison does
not isolate the causal effect of the hold-box choice.

For both controls, all 12 logged radii match the pinned quadratic schedule
`r0 * (1-k/12)^2` to their printed precision and end at exactly zero. Native
source explicitly resets radius to zero before the ordinary rigid finish.
Actual holds, logs, native JSON, input text, output text, and certified archives
are connected by exact hashes. Encoding and decoding preserve row order.

| Control | n | Side deficit versus legalized input | Center RMS after D4/unlabeled alignment | Angles changed >1° | Near-contact edges changed, tolerance 1e-5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Compressed box | 147 | 0.170907 | 0.460319 | 67 | 395 |
| Compressed box | 299 | 0.0366744 | 0.157929 | 48 | 785 |
| Compressed box | 335 | 0.00626956 | 0.0773825 | 44 | 273 |
| Incumbent box + initial kick | 147 | 3.27e-13 | 0.0233073 | 2 | 116 |
| Incumbent box + initial kick | 299 | 1.39e-13 | 0.0318328 | 10 | 91 |
| Incumbent box + initial kick | 335 | 2.16e-5 | 0.0265813 | 18 | 228 |

The original compressed n147 maximum same-row displacement of 13.88 is not an
adapter row-order error, but it overstates unlabeled geometric change. After
the best D4 alignment and center assignment, the maximum residual is 1.155.
The packing is still materially different and substantially worse in side.
The center assignment is a comparison of unlabeled outputs, not a reconstructed
trajectory of the optimizer's labeled variables.

Both n335 results are material alternatives. Their best D4 alignment and
center assignment are the identity. For the compressed result, 264–273 contact
edges change across tolerances 1e-6 to 1e-4; for the incumbent-box result, the
range is 214–228. These changes and the substantial angle differences survive
removal of translations, reflections, and relabeling. Near-contact graphs are
numerical diagnostics, not claims about exact touching graphs.

This evidence supports a bounded, distinct multi-start continuation campaign,
especially from the near-reference n335 output. It establishes no score gain.
The compressed n335 seed must be included explicitly if used: its +0.00627
side deficit exceeds the older 0.002/0.005 eligibility filters. Preserve all
certified alternatives, but compare proposed improvements with the actual
portfolio certificate rather than only the slightly dilated control inputs.

Reproducible audit: `experiments/review_full_round_control.py`. Detailed proofs
are in `artifacts/fq-full-round-independent-review-v1/`:

- `compressed-control-complete-review.json`
- `held-control-complete-review.json`

Both records explicitly report zero fresh full certificates and preserve the
chosen D4 transformations and assignments. The original control directories
and all native outputs remain unchanged.
