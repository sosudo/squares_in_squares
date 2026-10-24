# Future packet-format integration map

This is a read-only plan. The completed `dc6950e8…` sustained bundle and all
current readers remain unchanged. Exact source hashes and function locations
are recorded in `artifacts/fq-packet-codec-integration-map-v1/integration-map.json`.
All six runtime writer/recovery/finisher source modules still match that frozen
parent payload. The offline analyzer and CPU extractor have separate pins.

The raw writer is `fq_torch_hop_pilot.PacketStore._publish`. Its seven-pose
budget comes from `fq_restart_hop_pilot.RestartPacketStore`, while sustained
`BoundedPacketStore` adds the protected-output guard and is injected explicitly
into the generated search namespace. The actual sustained recovery is
`fq_restart_hop_pilot.recover_terminal`, called through the driver's three-second
`bounded_recovery`. The older Torch all-history recovery also reads packets but
is not executed by the sustained path.

The finisher's packet read is in frozen `fq_cold_hop_finish.finish_case`.
`fq_sustained_hop_finish._derive` creates its isolated, counted clone. The
unchanged original `fq_restart_hop_finish._finish_slot` handles native input,
outputs and admission gates; it does not need a new packet format. The offline
analyzer reads the terminal packet in `audit_case`, after verifying receipts,
index SHA/size and final-state bindings. Other analyzer `np.load` calls read
inputs, preflight controls, final normalized state and native/certified arrays;
those files can remain ordinary NPZ.

The extractor is a byte copier, not a numerical reader. Its
`terminal_packet` whitelist currently accepts only `packet-NNNN.npz`. A future
extractor needs an explicit `.fqp` branch matched to the entry's format marker
and new parent source/manifest/config pins. It still copies the exact raw bytes
and checks the index SHA/size without decoding. Its builder must bind a new
future parent; the existing 75f5a14f extractor stays reproducible.

Minimal future wrapper:

1. Add an explicit `read_packet(entry, root)` helper. Verify the safe indexed
   path, size and trusted SHA first. An absent legacy marker selects
   `np.load(..., allow_pickle=False)`. The marker
   `packet_format='fq-self-contained-blocks-v1'` selects the exact hash-pinned
   `fq_packet_codec.decode(..., expected_sha256=entry['sha256'])`. Unknown markers
   fail closed. Both branches return the same ordered array mapping, including
   exact `metadata_json`; neither mutates metadata or normalizes coordinates.
2. Add one new packet-store subclass that changes only serialization and entry
   format/codec fields. Use `.fqp` names for new packets. Preserve pending input
   publication, separate completed-file publication, atomic index replacement,
   old-input unlink and state-commit order. Keep actual encoded-byte accounting.
   The internal codec manifest is versioned too; both old and new packets stay
   readable in an explicitly mixed index.
3. Keep a worst-case reservation. For current seven-pose packets it includes
   all seven full arrays, the existing 1 MiB metadata allowance, bounded scalar
   arrays, the codec's 4 MiB manifest limit and ZIP overhead. Reserve coexistence
   of pending and completed files. Typical compression ratios never substitute
   for this bound. The existing hot/cool storage policy and deadlines can stay
   numerically unchanged.
4. In a separate future module, derive narrowly counted recovery and finisher
   clones replacing only the raw packet load with that explicit helper. Continue
   writing the five-field normalized `final-current-best.npz` using ordinary NPZ.
   Preserve exact terminal metadata/design/array hashes and final equality before
   native selection. Inject clones through isolated namespaces or an explicit
   callable; never monkeypatch NumPy globally.
5. Version the offline auditor and extractor wrappers with exact future source
   pins. Change only the terminal packet dispatch, receipt pins and extension
   whitelist. Ordinary NPZ inputs, controls, selected native states, outputs,
   certificates and final-state readers remain unchanged.

Required integration controls before any future launch: legacy and new pending
and completed fixtures; rejection of unknown format/version/codec hash; all
packet fields and metadata bit-exact; interrupted completed-file/index/unlink
publication; terminal recovery and unchanged fixed-slot selection; unchanged
native input bytes; extractor path/size/SHA and receipt ancestry; hard byte-cap
reservation; and actual producer/recovery/finisher/auditor roundtrip. No optimizer
or score improvement is needed to test this storage path.

The completed extraction now provides actual storage evidence: all twelve
cases recorded hot-storage pauses, totaling about 356.8 seconds across both
queues (11.6–43.1 seconds/case). They still ended with `stop_reason='deadline'`,
because the inherited policy pauses at 60% of the raw budget to reserve cooling
space. Final raw bytes were about 649–681 MB/case against 805 MB caps. This
supports considering a future codec adapter, but is not evidence of additional
search gains. No integration or launch follows automatically from this plan.
