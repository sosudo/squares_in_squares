# Certified search incumbent 2e6e39f36a7c

Safe and ordinary pandas-roundtrip scores both **22.301061591170022**.
All 1,000 cases pass, with zero invalid cases. This portfolio has not been
submitted because the score remains above the strict 22.3 threshold.

Relative to the 5ec checkpoint, exact-chain replay of the second private CPU
campaign's 8×20+12 minimum improves n807 and n865 by about 3.79e-8 total. Every
other case is preserved. The canonical update passed the independent casewise
nonregression gate. RAW, SAFE and numeric-roundtrip checks each reused only
the 998 exactly unchanged cases and freshly evaluated the two changed cases.
The established long-decimal clearance transform was applied once from RAW.

The 493,592-byte exporter applies exact SAFE row patches to the immutable 8cd7
parent, with no coordinate scaling. Its local frozen-runtime reconstruction
matches the certified CSV byte-for-byte. The completed private CPU export was
also remotely hash-verified; its completion proof is included here. Follow
the two commands in recipe.json to reproduce it without Kaggle credentials;
the parent recipe uses public, hash-pinned inputs.

Inherited attribution and licenses remain in the
[parent notices](../candidate-8cd7c023ab18/source-notices-kmmm28/SOURCE_NOTICES.md),
the parent manifest, and repository vendor notices. The new local optimizer
is Evan Daniel's MIT-licensed
[square-packing](https://github.com/evand/square-packing), pinned to commit
659ee62e4a9d39542a1146e8b011cc3ab6407ede. Exact search, native binary and selected
geometry hashes are recorded in recipe.json. Independent validation and the
complete transport proof are included here.
