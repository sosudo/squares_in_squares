Exact SAFE portfolio 680e332bc6bc

This recipe reconstructs the certified 32,496,900-byte SAFE CSV from immutable private parent `sos54352/squares-portfolio-b84f2ff20f3e-incremental/1` and exact row-byte patches. Both the SAFE and ordinary-pandas-roundtrip official score are 22.298021385704345. All 1,000 cases are valid. Export performs no coordinate reserialization or further clearance scaling.

The 30 selected native cases comprise n858 trace, seven timeout-extension winners, 21 remainder winners, and n995 trace. Selected parent geometry, exact native input/output/logs, raw/decoded/certified archives and certificate bindings are under `native-ancestry/`; full prior source notices and provenance are inherited byte-for-byte. n995 returned in 27.0463 seconds under lighter observed load with a 60-second cap; that observation does not prove that the cap caused its gain.

To reproduce using the exact verified parent CSV, run `export.py` with `INCREMENTAL_PARENT_PATH` set to that parent file and `INCREMENTAL_OUTPUT_ROOT` set to a fresh directory. The runtime rejects parent or patch hash changes. `verify-export.py` records local mount discovery, exact reconstruction and tamper controls. The private CPU/offline notebook attaches the competition from its first launch. Competition submission remains a separate root-controlled action.

Verified remote export: `sos54352/squares-portfolio-680e332bc6bc-incremental/1`, private CPU/offline, COMPLETE at 2026-10-24 14:37 UTC. `submission.csv` SHA256 is `680e332bc6bc5bb7d741505b9460ca18fb410ce11929342e67fb2262b20a2d74`; completion-proof SHA256 is `d427ff816575fea9e303d360e6c74a459b44aa4619c8931dc79bf5dc38c33f72`. All 32,496,900 downloaded bytes match the certified target.
