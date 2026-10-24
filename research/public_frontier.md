# Public packing frontier — 2026-10-24

All downloads in this investigation used public, unauthenticated Kaggle endpoints. Coordinates were preserved as their exact original decimal strings. A whole puzzle is the merge unit. No coordinate rows from different layouts are interleaved. Reuse credit identifies the source from which a packing was obtained, not its original discoverer.

## Sources and version caveat

Kaggle's unversioned dataset download endpoint returned an older version even when `datasets/view` listed newer published versions. Pin `datasetVersionNumber`, verify the downloaded hash against any published manifest, and do not infer current output from a notebook title or its latest source version.

| Source | Version | CSV SHA-256 | Reported/locally estimated source score | License |
| --- | --- | --- | --- | --- |
| [Sung Heo / kmmmvs, Best Validated Packings](https://www.kaggle.com/datasets/kmmmvs/squares-in-squares-best-packings/versions/22) | 22 | `aa8d390849d0ff5a8acacc36ad62f232ab76a11acdb8402a79e29167f6d1d920` | 22.36058718713827 | Mixed source-specific terms; original notices retained |
| [Sung Heo / kmmmvs, Best Validated Packings](https://www.kaggle.com/datasets/kmmmvs/squares-in-squares-best-packings/versions/24) | 24 | `79629f489cf84987f55165618f800c6e37c1dbdbd9d0ec8df30be21fee2436dc` | 22.310370759394157 | Mixed source-specific terms; original notices retained |
| [Chris Deotte, FTMC data](https://www.kaggle.com/datasets/cdeotte/squares-in-squares-22-315-data/versions/2) | 2 | `7a9fb4638f6de775d01a8300cbe3616b5c21052fdb5229a0d6bd4c9f67989725` | 22.311618219985608 | Dataset metadata states CC0: Public Domain |

Both KMMM CSV hashes match `portfolio_manifest.json` downloaded from their explicitly pinned versions. Cdeotte's CSV is a permitted partial submission (grid-equivalent puzzles omitted); the score above includes grid fallback for missing puzzles. The independent merger retains the existing complete baseline for missing cases.

KMMM `SOURCE_NOTICES.md`, `LICENSE-APACHE-2.0.txt`, and `LICENSE-LEVY-SOURCES.txt` from version24 are retained unchanged under `vendor/notices/kmmmvs-v24/`. Dataset metadata says the compilation is not blanket relicensed: inherited Apache-2.0, CC BY4.0, MIT, and per-source conditions remain applicable. Original notebook and mathematical witness authors remain credited in those notices. The authors of this repository claim only their merge/validation/experimental implementations.

Original MIT Shubin baseline attribution is in `vendor/SOURCES.md`. Couzo exact certificate attribution is recorded by `experiments/import_records.py` in `artifacts/candidates/records.json` and its summary.

## Reproduce the downloads

From `/workspace/squares_in_squares`:

```bash
python3 scripts/fetch_public.py kmmmvs/squares-in-squares-best-packings --kind dataset --version 22 --output artifacts/public
python3 scripts/fetch_public.py cdeotte/squares-in-squares-22-315-data --kind dataset --version 2 --output artifacts/public
python3 scripts/fetch_public.py kmmmvs/squares-in-squares-best-packings --kind dataset --version 24 --output artifacts/public-v24
```

These use `https://www.kaggle.com/api/v1/datasets/download/OWNER/SLUG/submission.csv?datasetVersionNumber=VERSION`, redirecting to `storage.googleapis.com`. The downloader saves source URL, retrieval time, size, version, and SHA-256 beside each CSV. Signed redirect URLs are not stored.

Public notebook output downloads use `https://www.kaggle.com/api/v1/kernels/output/download/OWNER/SLUG/submission.csv` and redirect to `www.kaggleusercontent.com`; this hostname was initially blocked. Using the publicly documented dataset route made the source datasets available without waiting for that additional domain.

## Reproduce the certified merges

After generating and validating `artifacts/baseline.csv` and exporting the Couzo record candidates:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/merge_candidates.py artifacts/baseline.csv artifacts/merged-records.csv artifacts/candidates/records.json --baseline-report artifacts/baseline-validation.json --workers 2
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/merge_candidates.py artifacts/merged-records.csv artifacts/merged.csv artifacts/public/kmmmvs__squares-in-squares-best-packings.csv artifacts/public/cdeotte__squares-in-squares-22-315-data.csv --baseline-report artifacts/merged-records.validation.json --workers 2
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/merge_candidates.py artifacts/merged.csv artifacts/merged-v2.csv artifacts/public-v24/kmmmvs__squares-in-squares-best-packings.csv --baseline-report artifacts/merged.validation.json --workers 2
```

The merger reuses a baseline certificate only if its SHA-256 matches the input CSV. Every proposed replacement passes the independent interval validator; its certified upper side bound must be below the incumbent's certified lower side bound. Approximate geometry only screens and orders candidates. JSON reports record each source, rejected candidate, exact score interval, input hashes, output hash, and baseline certificate chain.

| Artifact | Independently certified local score | Changes relative to previous row |
| --- | --- | --- |
| `baseline.csv` | 22.37200587895322 | Initial public baseline |
| `merged-records.csv` | 22.350773397223 | 212 exact certificate replacements |
| `merged.csv` | 22.306579055445 | 902 replacements from KMMM22 and Cdeotte2 |
| `merged-v2.csv` | 22.306544901901 | 36 replacements from KMMM24 |

Zero candidate puzzles were rejected in these three merges. These are local validation results; actual Kaggle scores and rankings are tracked separately by the main agent. Three merger tests verify preservation of long decimal strings, rejection of duplicate square IDs, and rejection of an overlapping candidate even when its apparent side is best.

An additional pinned download of `lightningv08/squares-in-squares-layout-atlas` version18 (dataset metadata: CC0) was checked against `merged-v2.csv`. It supplied no improving puzzle. `artifacts/merged-v3.csv` therefore repeats the same coordinates and score; it is not a new improved submission. Its input digest and this negative result are retained in `artifacts/merged-v3.validation.json`. The candidate source and its download provenance are under `artifacts/public-lightning18/`.

## Public method material

[Chris Deotte's FTMC/MILP notebook](https://www.kaggle.com/code/cdeotte/squares-in-squares-ftmc-milp-refill-22-311) describes removing upright staircase fill, mutating isolated tilted cores, then refilling with contact-generated upright candidates, simplicial graph reductions and maximum independent set MILP. L-BFGS and sequential LP polish follow. The notebook distributes before/after gadget data, not its original search engine. `gadgets_39_and_baselines.npz` is downloaded into `artifacts/public/` from dataset version2.

[Vladislav Lavrentev's CUDA Packing Search](https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search) source was read via public `api/v1/kernels/pull/…`. Its source embeds19 files in a literal `SOURCES` dictionary. Those were extracted using Python AST literal parsing, without executing the notebook, into `artifacts/public/lightning_sources/`. They include independent tilted-core/refill, GPU rectangle optimization, row DP, fault composition and campaign modules. Preserve their original source notices and review licensing before redistributing or using substantial code. The latest pulled source need not match the last evaluated public output.


## Targeted freshness check after the second scored submission

At 2026-10-24 06:14 UTC, only the strongest already-used source versions were checked. KMMM advanced from dataset 24 to 26, and Couzo advanced from commit 964ee2bdf301 to 1c1715399709. Cdeotte dataset 2, Dariush dataset 11, Lightning Layout Atlas 18 and Lightning public solver source 21 were unchanged. The Lightning public viewer's current evaluated run is 17 while its public source-pull API serves 21; these version kinds must not be conflated. No broad notebook sweep was performed.

Pinned KMMM 26 CSV: `artifacts/public-v26/kmmmvs__squares-in-squares-best-packings.csv`, SHA256 `cab501fe499261db1c9a5b2d665ca7964e509484442a920376282281444cdd4c`. It exactly matches the separately downloaded version 26 `portfolio_manifest.json`; that source portfolio reports 22.31032126032646. Its notices, Apache 2.0 license and individual Levy-source terms are retained unchanged in `vendor/notices/kmmmvs-v26/`. Float screening found four improving puzzles against the submitted 4636 portfolio: n=338,376,496,802, estimated aggregate gain 0.00002220166. These estimates require certified merge validation.

The new Couzo catalogue is pinned to full commit `1c1715399709bc955e9b402947ab8b52bbacdfc3`. Metadata and per-file download hashes are retained under `artifacts/public-freshness/couzo-1c1715399709/`. Seventeen improved exact certificates were SHA-verified and rendered independently with 100-digit arithmetic, 75-digit coordinates and 1e-40 centre dilation into `artifacts/candidates/records-fresh-1c1715.json`, SHA256 `c361a5d7e9116cae884cc492ecc82f65411f066f4217d738400fa8fee444215a`. The estimated aggregate gain is 0.0003597892 before final transport safety and certification. Original pins, archives and source notices remain preserved.

Neither refresh alone is expected to meet the user's new strict score<22.3 submission threshold; no new submission or runner restart was performed by this research task.

The combined refresh was subsequently certified at **22.304375968681107** on both safe decimal and ordinary pandas numeric-roundtrip CSVs, with zero invalid cases,21 fresh evaluations and979 exact unchanged-certificate reuses. All21 source changes improve after the once-only transport transform. Exact safe CSV SHA256: `82ad3a551afb934d4b263a9fd1a7dc121f19bd9052c13218c5a39017ed7d0f29`. This is a search baseline only: it remains above the user's strict submission ceiling. Full report bindings are in `artifacts/submission-public-refresh-v1-safe.transport-validation.json`.
