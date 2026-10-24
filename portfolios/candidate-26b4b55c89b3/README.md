# Certified GPU composition candidate

This candidate improves 14 puzzles over the first submitted safe portfolio. Its official score is `22.304803775499245`; all 1,000 puzzles remain valid after ordinary pandas numeric CSV roundtrip. The gain over submission 57583210 is approximately `3.54989e-8`.

Private export notebook `sos54352/squares-certified-portfolio-source-export`, version 3, completed successfully. Its downloaded `submission.csv` has SHA-256 `26b4b55c89b3606385a74645e327c4b9a6b40fda7f62f6bdd969dbff1cb39afb`. This directory records a prepared candidate, not a competition submission receipt.

Reconstruct it using the project's Python environment with internet access and mpmath 1.3.0:

```bash
python3 portfolios/candidate-26b4b55c89b3/export.py --destination /tmp/squares-candidate-26b4b55c89b3/submission.csv
```

The exporter downloads pinned public sources, checks each source hash, reconstructs exact decimal rows and applies the reviewed centre-clearance transform. It asserts the final CSV hash. Credentials are unnecessary for reconstruction. The generated script was locally executed and compared byte for byte with the certified candidate before notebook upload.

`recipe.json` records construction and provenance; `export_manifest.json` retains public source references and hashes. Existing source-specific licenses and attribution remain under `vendor/notices/`. `completion-proof.json` records the completed private notebook version and both remote/downloaded output hashes. Independent and official transport validation evidence are included separately. Actual submission scheduling and receipts are managed outside this directory.
