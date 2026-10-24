# Local search checkpoint — no remote export

This checkpoint preserves the adopted three-campaign merge exactly. It is not
eligible for submission: current user policy requires SAFE and numeric-roundtrip
score strictly below22.24. This SAFE/roundtrip score is22.29648715325571.
No Kaggle export, queue entry or submission was created.

Provide the exact parent CSV SHA
`f1b5c18e95fa637e93795102f892a160b972ad1fa13789b2e7d737b5b44a1494`,
from the existing committed `../candidate-f1b5c18e95fa` recipe/hash chain or its
already completed output, then run with standard Python only:

```sh
python restore.py --parent /path/to/exact-f1b5.csv --out /tmp/restored-search
```

The helper only copies parent byte ranges and inserts recorded literal bytes.
It checks compressed/raw patch, parent and target lengths/hashes. It performs no
coordinate parsing, rounding, scaling, optimization or geometry certification.
RAW, SAFE and ordinary roundtrip outputs each reconstruct independently against
the same parent, including their original decimal strings and line endings.

| Output | SHA256 |
| --- | --- |
| RAW | `9d18b33ca0efb4c55c0afac2c159f413676d76aae37fb3cbcc6ec93a43975396` |
| SAFE | `c9fca5a1a1fbf55bba5e3ed093cc5412b92845fb01809c3fbc61362bb01d3097` |
| Roundtrip | `fc5c2882e8443fb51d2c9f3f681494d7f5e418032cadbfa1669983fb8be2234e` |

`manifest.json` inventories exact stored evidence and its original paths/hashes.
Some large text evidence uses lossless `.xz`; decompressing restores its original
bytes and SHA. Parent recipe files are hash-referenced, not recursively copied.
New campaign inputs, sources, candidate JSONs, execution/completion/independent
proofs, native artifacts and appropriate MIT sources/notices are retained.
The certified aggregate banks retain all96 sustained GPU/control/native poses,
24 public35 alternative finishes and24 fresh-current native finishes, including
scalar-worse geometries. Individual certificate snapshots are retained too.
Large raw UNVERIFIED archives remain immutable in the exact receipt-bound
local/remote sources; this checkpoint does not claim to embed that full history.

There were26 candidate case winners and23 adopted cases. Cases637/692/917 were
below the merge's approximate-side material screen and were not adopted; their
candidate geometry and certificates remain preserved. Root's unchanged full
RAW/SAFE/ordinary-roundtrip and independent reports are stored as evidence.

`local-proof.json` records exact local replay and wrong-parent refusal.
The independent review is an auxiliary receipt added after the frozen manifest;
this README and local/independent receipts are not part of its payload inventory.
