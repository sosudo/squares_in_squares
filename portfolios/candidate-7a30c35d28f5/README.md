# Certified public KMMM35 updates

Exact SAFE row-byte export over immutable
`sos54352/squares-portfolio-3c4cfc19361e-incremental/1`.
Target SHA256: `7a30c35d28f5df9f5cde6de6f831f1d4a76cd8cfbb87cc747bed395d84599e72`.
Validated SAFE score: **22.297895630470705**; ordinary pandas roundtrip:
**22.29789563047071**. Eighteen cases replace 13,493 rows; all other 486,007 rows
remain byte-identical to the parent.

The improvements are copied from the publicly released
[kmmmvs/squares-in-squares-best-packings version35](https://www.kaggle.com/datasets/kmmmvs/squares-in-squares-best-packings/versions/35).
All original authors retain credit. No new search method or discovery is claimed.
The exact archive SHA256 is
`55d9284e8d1f75dbe694bd8437ea202acc4f7e738f3b42b85567c082c69103c3`.
All 2,250 archive members and extracted files were hash-verified. The original
47.6MB archive remains at `artifacts/public-v35/dataset-v35.zip`; this recipe
contains the exact selected decimal rows, all official/pandas/interval
certificates, original archive/download/member proofs and 45 complete notice
files. The coordinate tokens agree from original CSV through subset and
candidate JSON; adopted RAW coordinates agree as Decimal values.

The exporter preserves the reviewed runtime and codec. It performs no search,
new geometry evaluation, coordinate reserialization or extra safety scaling.
For local reconstruction, run `export.py` with `INCREMENTAL_PARENT_PATH`
pointing to the exact 3c4 SAFE CSV and `INCREMENTAL_OUTPUT_ROOT` pointing to a
fresh directory. Notebook metadata is private, CPU-only and offline, with the
competition attached at its initial version. Competition submission remains a
separate root-controlled action.

Private export version1 completed and was remotely byte-verified at 2026-10-24T16:46:46.285039+00:00. Runtime: 3.54 seconds. Completion proof SHA256: `9dd78ee3c0f3637ecca435050a419a89ee1fb4364b2fce2c54421d84f69a4db7`. No competition submission was performed.
