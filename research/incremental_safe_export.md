# Exact incremental SAFE-CSV export

The current complete source exporter is 987,338 bytes, close to Kaggle's
1,000,000-byte source limit. `scripts/build_incremental_safe_export_job.py`
provides a concrete fallback using the remotely verified private parent
`sos54352/squares-portfolio-8cd7c023ab18/1`. It leaves all existing full-source
exporters and portable recipes unchanged.

The helper takes already certified **SAFE CSV bytes**. It does not rerun safety
dilation, evaluate geometry, parse coordinate strings into floats, or reserialize
unchanged rows. It embeds only changed raw rows and their integrity checks.
The parent notebook version label is descriptive; the runtime requires the
exact parent SHA256 because Kaggle may attach a newer version despite a suffix.

Prepared bundle:
`artifacts/portfolio-5cba3bdac3cf-incremental-export-job-v2/`

| Item | Value |
|---|---|
| Parent CSV SHA256 | `8cd7c023ab18b5875fcd5084e23415eda3181df1f4e70b5558bfe9eb039b0658` |
| Target CSV SHA256 | `5cba3bdac3cf87483073025bdd3b6c058870518c617383276d8855bc454a5ab0` |
| Frozen notebook source SHA256 | `e9a9fb3c247e1ddf938007d6d85886d90b49413eae9cf1ff66a48db320e8ad05` |
| Source size | 426,252 bytes |
| Exact target size | 35,054,241 bytes |
| Changed rows | 16,526 across 20 puzzles |
| Unchanged rows | 483,974, plus the unchanged header |
| Target official score | 22.30142775062775 |

The builder verifies the parent remote completion receipt, parent/target
official reports and both SAFE/default-pandas transport proofs. The runtime
checks the mounted parent file hash and length; exact CRLF schema; all 500,500
global ids, puzzle counts and square ids; finite decimal-string syntax; patch
compressed and decompressed hashes; strict sorted unique patch ids; changed
parent-row and target-row byte digests; unchanged-byte digest; and the exact
final CSV length and hash. The final file is written atomically. Existing
conflicting output files are rejected. The notebook is private, offline and
CPU-only with a 120-second alarm, and attaches only the unique parent notebook.

The frozen script was executed locally against a simulated attachment mount
containing the correct parent and a wrong-content CSV. It reproduced the target
byte-for-byte, ignored the wrong input, and rejected modified real parent and
patch bytes. The demonstration took 5.83s; proofs are `local_verification.json`
and `local_runtime_proof.json` in the preserved original bundle. Six portable tests also cover long
decimal strings, signed zero, tampered coordinate strings even after rehashing
the patch envelope, malformed ids, and duplicate patches. No geometry checks
were repeated and no notebook or competition submission was launched.

Root review identified a metadata issue before launch: Kaggle may derive the
actual notebook slug from its title. The builder now derives the title directly
from the requested slug, and a seventh test checks their consistency. The v2
bundle changes only metadata; its source, loader and reconstruction manifest
are byte-identical to the tested original. `metadata_correction_proof.json`
binds the corrected metadata to the original exact-byte verification. The
unlaunched original bundle and all its proofs remain intact.

To rebuild this concrete checkpoint into a new output directory:

```bash
.venv/bin/python scripts/build_incremental_safe_export_job.py \
  --out artifacts/portfolio-5cba3bdac3cf-incremental-export-job-v3
```

The default inputs bind the verified 8cd7 parent and current 5cba SAFE target.
The emitted `incremental_loader.py` can reconstruct `submission.csv` when given
the mounted parent or an explicit local parent path. The emitted `export.py`
adds the bounded notebook entry point and a reconstruction proof. An eventual
remote export must still have its output hash checked before another notebook
consumes it. The score remains above the user's competition-submission limit.
