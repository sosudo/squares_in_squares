# Alternative public layouts as composition donors

The per-puzzle best merge discards many valid arrangements whose subregions and separator profiles may still be useful. This experiment retains whole alternative layouts near the current frontier, rather than retaining only their scalar side lengths or stripping their upright fill.

## Frozen bank

- Baseline: `artifacts/submission-frontier-composition-v1-safe.csv`, SHA-256 `4636cfc395424574a77d81131110eea9444fde0f16e5d48a133e1364d9e95f21`, official score 22.304757959372726.
- Archive: `artifacts/alternative-public-donors/donors.npz`, SHA-256 `543f80c72fc619fa7d6217527e1d6bbf39f404077f2557b92efe41c4da037052`.
- **320 alternative layouts, 211,823 unit squares, 240 puzzle sizes, 21 retained public CSV sources.** 307 layouts have n>324.
- Canonical key/shape/array digest: `8e99e755d180be8416d8162c7200cfec0ab955ae508879179fc8b348bb7a52f2`.
- Every layout passed independent interval non-overlap certification. No new leaderboard score is claimed for this donor bank.

`experiments/alternative_public_donors.py` scanned 31 already downloaded public files, deduplicated to 29 exact CSV byte identities. It inspected 23,501 puzzle groups. It excluded 10,121 geometric/precision duplicates, 9044 grid/trivial layouts, 931 layouts too far from the frontier, 10 known fixture-equivalent poses and one area-bogus source puzzle. The geometry candidate pool was bounded per puzzle before selecting at most two variants per n and applying a source-diversity cap. The local scan and certification took about 120 seconds.

The allowed side gap was 0.15; the actual selected maximum is only 0.0223052. D4 reflections/transposes and translation are used for duplicate detection, with explicit near-precision matching. Retained poses keep every square and its angle, including upright fill and relative wall phase. No arbitrary global rotation, angle snapping or core averaging is applied. Conservative center-only clearance does not resize any unit square.

Full certificates, input hashes, original source URLs/metadata, licenses, per-array hashes, scalar export recipes and the rejected-candidate ledger are in `artifacts/alternative-public-donors/manifest.json`. Attribution and inherited terms are retained under `vendor/notices/alternative-public-donors/`, with the original KMMM and Dariush notices linked there. Where multiple notebooks contained exactly identical CSV bytes, canonical provenance prefers an explicitly versioned dataset; mirror notebooks are not assigned dataset version numbers.

## Lossless portable export

`experiments/alternative_csv_loader.py` restores the frozen bank from a compact descriptor and its exact public CSVs. Decimal strings are converted to correctly rounded binary64 values, then recorded scalar normalization/dilation steps reconstruct the arrays. Every array must match its expected SHA-256 before fresh interval certification.

Descriptor: `artifacts/alternative-public-donors/loader_descriptor.json.zlib` (21,429 bytes compressed), raw descriptor SHA-256 `1dd2a2f52d92d379a4d0ec3bbb0e4eac77ddcf641c181169bb833fe626576a8a`. The local source-backed replay matched all 320 arrays and all interval certificates in 42.93 seconds. Its NPZ SHA-256 is `f4270b00ffdbc8bdacd9e070e4cf1e7910e4ef6f7bd1932c2f8130ce4b03e01b`; array identity is unchanged despite the ZIP entry order differing from the initial bank.

The first private CPU exporter failed closed because two public notebook outputs changed after the frozen download: Malyshev's Neighbour Transfer and mtoshidesu's Ensemble. The exact 19 other CSV sources remained available. The corrected exporter embeds only the 18 original already-certified poses from those two sources, with exact per-array hashes, and fetches the remaining 302 poses from 19 unchanged sources. It does not accept newer CSV bytes or change expected checksums. Original input CSV provenance remains retained for the 18 embedded poses.

Embedded snapshot: `frozen_changed_source_poses.npz`, 88,848 bytes, SHA-256 `27d5de31cb28dc54f5b8c1ec2c5cfdc507563e16ef842fed4601b9224c439163`; source proof is beside it. Complete public CSV caches stay under `/tmp`, outside notebook output attachments.

## Remote readiness

The corrected, unique private CPU exporter **`sos54352/squares-alternative-838d775a1834/1`** completed successfully in 72.11 seconds. Its output is **`alternative_donors.npz`**, actual SHA-256 **`f4270b00ffdbc8bdacd9e070e4cf1e7910e4ef6f7bd1932c2f8130ce4b03e01b`**, exactly matching the local rebuilt archive.

Every downloaded array was independently compared to the pinned local bank; all 320 matched, with 320 interval certificates and zero invalid layouts. The official SDK independently rechecked the exact notebook version, private flag, COMPLETE status and streamed output SHA. Evidence is retained in `artifacts/alternative-public-export-results-v2/completion-proof.json`, `alternative_donors.source_report.json`, and `alternative_export_summary.json`.

`notebook_frontier` received this immutable source and actual hash for the primary agent's broader dual-GPU composition experiment. This CPU export did not run GPU search or make any competition submission. The user's current submission gate is strict: **no submissions unless the validated score is below 22.3**.
