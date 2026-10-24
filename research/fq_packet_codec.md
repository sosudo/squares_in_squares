# Standalone packet codec for future jobs

`experiments/fq_packet_codec.py` is a new, unintegrated storage module. No
running job, PacketStore, recovery reader, finisher or other consumer changes.
Use `encode(arrays)` and `decode(raw, expected_sha256=trusted_index_sha)` only
through a future explicitly reviewed adapter. Existing NPZ readers cannot
consume this distinct format directly.

Each packet is independently decodable. Its two ZIP_STORED members are a
canonical versioned JSON manifest and a byte pool. Three-dimensional arrays
use 1,536-byte chunks aligned within each first-axis row; other arrays use
flat chunks. Deduplication uses exact chunk bytes. The manifest records
ordered array names, exact shapes, primitive or structured dtype descriptions,
byte lengths, per-array SHA256, indices, pool ends, payload SHA256 and a
canonical-manifest SHA256. The trusted external packet SHA remains necessary:
internal checks detect corruption, not an attacker rewriting all hashes.

Encoding uses direct C-order bytes, retaining scalar shape, endian order,
structured field offsets/alignment/titles/subarrays and padding bytes. Returned
arrays own independent byte buffers. Object dtypes, dtype metadata and
unsupported schemas are rejected; no pickle/NPY loader is used. Exact NaN
payloads, signed zeros, noncontiguous values and empty arrays are preserved.
Top-level subarray dtype schemas are rejected because NumPy would expand the
declared array shape; nested structured-field subarrays are supported.

Before opening ZipFile, the reader validates the fixed EOCD and exactly two
entries in the 116-byte central directory. Split disks, ZIP64, comments,
compression/encryption, extra or duplicate members and unknown versions are
rejected. Explicit caps cover packet, decoded and payload bytes, manifest
length, dimensions/extents, array count, dtype size/depth/field count, pool
blocks and indices. Shape/byte counts, every block index and tail length,
strictly increasing pool ends and all hashes are verified before success.

Ten tests cover byte fidelity and structured padding, mixed N, valid-ZIP
payload/per-array tampering, external packet identity, malformed shapes,
indices and pool ends, noncanonical/duplicate JSON, truncations, object NPZ,
resource caps and rejection before the central-directory parser. The initial
pre-parser ordering flaw and its small five-entry evidence are preserved in
`artifacts/fq-packet-codec-review-v1`; no large allocation was attempted.

The final benchmark independently loads four original B32 packets from the
early/late 803/861 cold run, including every `metadata_json` byte, and repeats
encoding/decoding three times each. All keys, dtypes, shapes and bytes match;
archives are deterministic. Sizes are 33.18%, 45.14%, 33.10% and 42.95% of plain
NPZ. Median encode times are 9.47–10.76 ms, decode 10.99–13.35 ms, versus plain
serialization 2.47–5.99 ms in this brief measurement. This demonstrates a
storage tradeoff, not a speed or search gain. It excludes disk flush and index
publication, and does not measure sustained B64 production packets.

Before any future integration, inspect the actual completed run's storage
stops, preserve every old consumer, identify format explicitly, bind codec and
packet hashes, and test the new producer/recovery/finisher together. Reserve
worst-case encoded size before an attempted proposal and preserve atomic
pending/completed publication order. A typical measured compression ratio
must never replace a hard byte-cap reservation.
