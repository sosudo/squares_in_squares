# Finite sustained-output extractor

The separate private CPU notebook copies selected bytes from
`sos54352/squares-sustained-cold-12case/1` after that exact version is COMPLETE.
It performs no optimization, geometry certification, native execution or GPU
work. The GPU notebook and its files remain unchanged.

`experiments/fq_sustained_output_extract.py` identifies its input by exact
runtime `job_manifest.json` SHA `228ea112d2c30ab20d8d42704e086c6b4be30197e52d94dbb1e636ad3c5bdb45`
and `sustained-config.json` SHA `c7429eb1b2ac4ee4f82972f09df77d497904218a1c622119ab521854b0088330`.
These are derived from frozen parent source
`dc6950e858285433d1975f537431e375bae95584ab314807a3ae08b79baa0451`.
The launcher must independently retain the parent's exact-version/source and
COMPLETE receipt; a matching attachment suffix alone is insufficient.

The whitelist preserves all 164 manifest-listed source, kernel, native binary,
license, notice, input and proof files and verifies every listed hash. It adds
fixed global/per-case configurations, inputs, indices, summaries, status,
events and logs; every file under each case's `preflight/` and `finish/` trees,
including failed controls, immutable certificate snapshots and partial native
outputs; the recovered final state; and only the last completed packet named
by each raw index. Its size and SHA must match that index. Earlier raw packets
are never opened. The zero-energy index is copied, while optional zero-energy
raw snapshots remain in the immutable parent outputs.

Outputs are `extracted/selected-output.zip`, using original relative paths,
and `extracted/inventory.json`. The inventory binds each member's exact size
and SHA, the ZIP SHA, frozen source/manifest/config and extractor worker/builder
hashes, missing optional evidence, terminal-packet counts and all 48 planned
finish-slot statuses. Missing or interrupted slots are reported explicitly.
This is a CPU extraction chain, not a claim of a direct parent download or a
new certificate. Keep both parent and extractor remote/download receipts.

The worker permits at most 500 MiB uncompressed selected data, 512 MiB actual
ZIP bytes, 8 MiB inventory and 20,000 files. ZIP writes are bounded while they
happen; failure/interruption does not publish a complete archive. It rejects
path traversal and symlinks. The private/offline/CPU-only package has a
180-second worker timeout, 235-second alarm within the 240-second whole bound,
300-second server timeout and 768 MiB total-output cap. Root/fullpilot owns
launch after independent review and parent completion.

Preparation validation: five focused tests pass, covering exact path/byte
retention, terminal-only selection, partial finish files, source and packet
tampering, path/symlink rejection, caps and interruption. A local replay of
the actual frozen worker and all 164 actual parent files, with 12 synthetic
terminal byte packets and 48 synthetic partial finish slots, preserved every
selected member exactly. These controls do not execute numerical code.
