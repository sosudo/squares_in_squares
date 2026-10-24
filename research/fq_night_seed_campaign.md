# FQ treatment of omitted night-seed types

A one-CPU campaign improved **21 of the 26** rectangular types recovered
by the retention audit. It retained **148 distinct strictly certified
geometries** in 205 trials and stopped after 293.16 seconds within the
300-second budget. These are component excess improvements; no competition
score improvement is established until a complete composition passes its
own certificates.

| Type | Historical excess | Final excess | Certified reduction, rounded |
| --- | ---: | ---: | ---: |
| 3×16+5 | 0.8876351572 | 0.8478744553 | 0.0397607019 |
| 4×21+3 | 0.7624839902 | 0.7227739429 | 0.0397100473 |
| 4×12+3 | 0.8210410302 | 0.7815654187 | 0.0394756115 |
| 8×22+4 | 0.7222866026 | 0.6926054593 | 0.0296811432 |
| 11×21+6 | 0.7369067776 | 0.7194589028 | 0.0174478748 |
| 7×22+4 | 0.7032798691 | 0.6877205717 | 0.0155592974 |

The references are orientation-fair minima from all matching historical
poses in the corrected retention inventory, rather than just the 27-pose
handoff. Every seed is transposed into its canonical dimensions when
necessary, retains exactly `w*h+d` squares, and passes full independent and
official validation. Frozen per-type source hashes, historical counts,
interval excess bounds and certificates are in
`artifacts/fq-night-seeds-v1/inputs/reference-proofs.json`.

The native positive control polished the standard five-square diamond
packing and passed all strict gates. The campaign first applied 20 contact
steps to all 26 references, then used small ALM kicks, exact-zero soft aspect
continuation, a larger kick, rounded continuation, and another cycle on
improved parents. Every returned unit-square pose with certified excess
strictly between zero and one was retained even if it did not improve the
current minimum. Soft outputs additionally required a monotone eight-step
aspect trace ending at exactly zero.

There were 148 certified trials, 55 outputs rejected for excess outside
`(0,1)`, and two whole-trial timeouts. In particular, five thin `3×long+4`
families inflated during native repair; their original valid references
remain in the final best bank. No rejected or timed-out result was admitted.
Official v17 checks cover original decimal strings, `%.17g` numeric
transport, and ordinary default pandas read/write; independent interval
checks cover original and ordinary-transport geometry. Rectangular excess
uses the maximum of the independently bounded horizontal and vertical
spans minus their respective integer dimensions.

The final status write collided with the already-created progress
directory at trial 205. All 205 records and both complete banks had been
written successfully beforehand, so the finalizer recovered them by exact
hash without rerunning or inventing any certificate. The original exit
code 1 remains in the final report. Future final checkpoints use a distinct
directory suffix; a regression test exercises the exact same-count
progress/final sequence. Two further tests check rectangular excess and
transpose invariance. All three pass.

The online component gain display used Decimal precision 28. The finalizer
recomputes exact subtraction from the stored outward interval endpoints at
precision 100 and preserves the original evidence. It certifies reuse by
matching every emitted binary64 array hash to its completed certificate;
it reports zero fresh checks rather than claiming revalidation.

Final immutable handoff:

- `artifacts/fq-night-seeds-v1/final/donors.npz`: 148 geometries,
  SHA256 `0b1f1a020efa4d612065a0b2e83f96166a95023cf63ff3f8237f0c7845f216a7`.
- `artifacts/fq-night-seeds-v1/final/best_bank.npz`: all 26 types,
  SHA256 `c7aa8ca0de7528a774c2113fdc348818ba08a3ef6a368fe5d3b65cf3c03a839b`.
- `final/report.json` and `records.json` bind the reference, source,
  binary, original snapshot, supervisor outcome and complete certificates.

The FQ binary remains pinned to SHA256
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`,
built from Evan Daniel's MIT-licensed commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`. Each native trial uses its own
process group and an inclusive timer covering optimization, repair and
certification; the parent supervisor bounds the whole campaign. Inputs,
source snapshots, command options and native logs are retained unchanged.

Early frozen snapshots were handed to the frontier agent. The separate
exact-candidate agent began its authorized composition screen using
snapshot 195, which had 143 geometries; the final bank adds five. No GPU
was launched and no competition submission was made by this campaign.
