# Public discovery: KMMM29 and AlexChilton19

The bounded broad pass queried the public competition notebook listing with `DATE_CREATED`, page size100, returning42 notebooks, plus public dataset searches for `squares in squares` sorted by updated and published, each returning20 rows. A notebook `DATE_UPDATED` query was unsupported and is not counted as successful coverage. The previous comparison catalogue was the09:21 snapshot; the requested discovery horizon was06:14UTC. Discovery paused when genuinely new useful releases appeared. Cdeotte2,Dariush11,Lightning18 and CouzoHEAD were not redownloaded.

KMMM's dataset listing exposed **Ready version29**, created2026-10-24T11:32:46.983Z, after the11:20–25 targeted check. The ordinary view still reports top-level version28: the explicit versions list is authoritative. Its exact release note is **“Certified public/local 1125: 34 puzzle improvements; preserve notices”**. All file requests therefore pin `datasetVersionNumber=29`.

The new public AlexChilton fault-line notebook is **version19 / scriptVersionId361756451**, dated09:53:13.637UTC, with listed public score22.3078562103. Its exact named output was fetched through the official SDK with version19 after verifying the notebook is public. The current source notebook is pinned separately; no claim is made that a current source blob automatically proves the provenance of every historical output.

| Public source | Exact CSV SHA256 |
| --- | --- |
| KMMM29 submission.csv | `d62a32592633d8093299516433202e879fe5429ac8bc56b28c309e6368a28c5f` |
| AlexChilton19 submission.csv | `417bb0b665107d5d33b320ea5637ac46933fb2ab4ff17bf4f49ef39a68274982` |

KMMM's manifest matches its CSV hash and reports local score22.30784729064431. Its mixed source-specific license remains “Other”; SOURCE_NOTICES.md and contributor/per-case files are retained. The absent source_manifest.json was recorded as unavailable, not fabricated. The public Alex notebook source SHA256 is `96b087bfec41a506a3a8ec316b43ba5bc7523591a3362452e532cfea1d380c0a`; notebook-wrapper licensing was not established by the pull metadata.

The attached **public** `alexchilton/squares-in-squares-starter-kit` is Ready version7. Its description states: “Licence: our code (metric.py excepted, which is Kaggle's) is CC0. The record packings in records.json are David Ellsworth's and are not relicensed here; see his page for terms.” Exact named public v7 helpers fault_dp.py,quench_gadgets.py and hop_search.py were downloaded and hash-pinned for the separate read-only method review. SOURCE_NOTICES.md was absent. No unknown or private input was accessed.

## Certified case improvements

Against frozen latest raw portfolio `a5086672035b695a9a67ebd551a1e595161d3a88436d9f27abd41835564cb0f0`, KMMM29 supplies **18 strict whole-case improvements**, with no rejected candidates:

338,376,415,497,501,543,590,597,640,698,744,746,752,800,802,861,917,928.

Alex19 has13 common promising cases but adds no winner over the KMMM29 union. KMMM's own per_puzzle.csv credits Alex's exact output hash for those13 inherited cases. The five other winners are338,376,802,917,928. Thus the latest uploader is not credited as discoverer of all18. `winning-source-lineage.json` preserves every original per-case source and hash.

All18 exact decimal candidates pass fresh independent interval checks, pinned official v17 raw-decimal checks, ordinary default-pandas serialization plus official checks, and fresh independent roundtrip checks. Official incremental gain is **0.0002454283899011589**. The largest contributions are n415(.0001183931),n501(.0000393624),n698(.0000332682),n752(.0000298821). Full merge, safe-transport transform and canonical pointer remain root-owned; no competition submission occurred. Expected safe score after the normal merge is about22.30081616278, still above the user's strict22.3 submission threshold.

The handoff is `artifacts/public-v29/winning-candidates.json`, SHA256 `9ecab2750dd49159d3a27190f694924853f965ad43a5e1ce9e1f341753fb4323`. Its independent certificates SHA256 is `744d8d518a7f1854afb0a2b0b9c5328818d21c81e8a67d06d6e1d1559a7046ab`; official per-case report SHA256 is `1eab2e9662ad9995461d89db1ad344a0e2e06f854afe2aab894d6a554af4f069`. `winning-cases-certification.json` binds raw and numeric CSV hashes, source scripts, metric and exact baseline. These are18-case certificates, not a fabricated fresh1000-case report. Screening/independent checks took15.43seconds and official/roundtrip checks17.22seconds on one CPU.

Public metadata, filtered discovery receipts and the precise query coverage remain under `artifacts/public-freshness/discovery-20261024T1140`; sources and download receipts are under `artifacts/public-v29` and `artifacts/public-alex-v19`. Signed redirect URLs are not printed in the new receipts or provenance; only stable public request URLs and redirect hosts are retained.
