# Lossless search-packet storage probe

The running twelve-case campaign keeps its frozen ZIP_STORED format. This
separate CPU-only probe measures a future storage option; no search state,
numerical method, running source or acceptance rule was changed.

The earlier ZIPlevel1 probe saved only11–12% and cost0.26–0.39seconds per
concatenated B64-shaped packet. Repeated current/best arrays and accepted
rows are often exact duplicates too far apart for that compressor's window.
Self-contained1536-byte block deduplication retains those bytes once and
stores indices. It requires no previous packet to reconstruct any array.

On the same first/last real B32 packet concatenations, n803 reduced from
8,644,406 to3,313,215bytes and n861 from9,268,022 to3,366,599bytes. Three
repeats gave median encoding times0.0075/0.0073seconds; decoding about0.006s.
All numerical-array dtype, shape and byte hashes matched exactly. These
concatenations are serialization fixtures, not actual B64 search histories.

An independent test then used all four original individual B32 packets,
including `metadata_json`. Three repeats per packet preserved every array's
dtype, shape, byteorder and bytes. Encoded size was33.2–45.2% of plain NPZ;
median encoding3.94–5.04ms and decoding3.61–4.42ms. Exact source/fixture pins
and measurements are in `artifacts/fq-packet-dedup-independent-review-v1`.

The experiment is deliberately not a production codec. Review exposed a
zero-dimensional literal shape conversion, unchecked changed payload bytes
in an otherwise valid ZIP, and acceptance of object arrays by the encoder.
A separate codec with explicit schema, bounds, object rejection and per-array
hashes is being developed for future use. It must pass adversarial tests and
independent review before integration. Production speed and actual additional
search coverage are not yet measured.

A free P100 comparison was also considered. Kaggle CLI2.2.5 explicitly maps
the retired `NvidiaTeslaP100` label to default `NvidiaTeslaT4`, so no P100 job
was launched. The generated SDK's older string documentation is not evidence
that genuine P100 hardware remains available. Read-only source hashes are in
`artifacts/p100-availability-audit-v1/read-only-proof.json`.
