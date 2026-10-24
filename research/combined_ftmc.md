# Productive combined FTMC campaign

The gentle-target pilot produced 213 certified rectangle variants, while its
original-target control produced none. The released retention map also lost an
actual strict improvement when a worse geometry reused its coarse fingerprint.
The next campaign combines the productive search settings and fixes retention;
it does not spend another GPU arm repeating the failed target policy.

The prepared private job is `sos54352/squares-combined-ftmc-campaign`. Both T4s
search the same 17 active rectangle types for 1,800 seconds each, with 120
seconds of finishing grace and a 2,400-second parent alarm. Device0 starts from
the independently certified FQ contact minima; device1 starts from the original
active crops. Both retain FQ, original and selected gentle alternatives in their
sampling archives. The FQ and original initial NPZ hashes are respectively
`67878f469b59b4cfd802fd264d0df2d78de7929af9b548d163149c648044f766`
and `e183e6bbf16584b836907748b4d08a28af75b648c585e200019b66cadfa88556`.

Both devices use incumbent-aware angle proposals, rigid incumbent anchor
restoration, and the successful near-incumbent full-target schedule. General
2-D refill compares each core's row count with its own source pose's measured
row deficit, allowing a margin of two squares. It gets at most one attempt per
batch, a 0.5-second external alarm, a 0.15-second MILP time limit and an 18%
cumulative worker wall-time allowance. Actual elapsed refill time is charged,
including timeouts. A native solver that returns after its alarm can overshoot;
the recorded debt blocks further calls until the allowance catches up.

Current target side lengths are recomputed against the 82ad baseline with score
22.304375968681107. Sampling assigns 75% of its initial mass to hypothetical
score opportunity and 25% to the four families that generated certified gentle
variants. A hypothetical .01 bloat reduction is only a ranking estimate. The
recorded old chain partners do not prove new poses will compose successfully.

The worker body changes in one audited AST pass, preserving live module globals.
The original finite, penetration, LP, clearance, strict-or-novel and official
raw/pandas admission gates stay unchanged. Every exact post-gate pose is written
immediately as an immutable NPY snapshot and certificate record. Separate tables
retain best per fingerprint, best per rectangle and live incumbents. Search
archives hold at most 12 fingerprints per key and replace stale same-fingerprint
poses on improvement. The complete immutable output archive is not limited to
those 12 sampling entries. Exploratory near-capacity cores and near-feasible full
poses are bounded separately and explicitly marked unvalidated.

The parent verifies byte-identical certificate, snapshot, aggregate and pinned
metric bindings instead of repeating every worker metric call. If interruption
occurs between aggregate and index writes, complete immutable pairs reconstruct
the aggregate. Corrupt complete pairs fail closed; orphan NPY files are not
treated as certified. Final composed CSVs still require independent complete
raw and numeric-roundtrip official evaluation. FQ-seeded gains and newly found
gains are reported separately against each device's actual initial bank.

`scripts/build_combined_ftmc_job.py` creates a self-contained offline bundle with
no remote input mounts. The initial review bundle has 43 verified payloads,
83 selected archive poses and 85 distinct exact poses passing official raw and
pandas checks. Source size is 701,333 bytes, SHA-256
`01a5a171091f3f2c6871dd054024cc8b9e26ca445af4f85e1f03cece56cd7183`.
Four independent regressions cover the exact AST changes, live observers and
per-device incumbents in an executed mock-CUDA worker, and actual official
certification with interrupted checkpoint recovery. Stale worker output paths
are refused before CUDA initialization, preventing unintended legacy resume.
The exporter also detects complete immutable records newer than an otherwise
consistent aggregate, covering interruption immediately after record publication.
These are preparation results; execution and resulting full-puzzle gains must
be recorded after the reviewed job runs. No competition submission is part of
this builder or campaign.
