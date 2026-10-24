# Higher-n public witnesses as new rectangle donors

The current incumbent for this experiment is `artifacts/submission-gpu-composition-safe.csv`, SHA-256 `26b4b55c89b3606385a74645e327c4b9a6b40fda7f62f6bdd969dbff1cb39afb`, official score 22.304803775499245. Earlier source sweeps used witnesses only through n=1000 and historical FTMC fixtures.

## Sources and reproducible import

The pinned public Couzo catalogue (`franciscouzo/square-packing`, commit `964ee2bdf301d0c8912d956d4010f478dcbbd5ea`) contains 209 finite source witnesses with 1000<n<=5000. This experiment admits the 175 witnesses explicitly attributed to two public MIT source categories: 161 from Mykhailo Polkovskyi/Mishapolk and 14 from Kevin Fang/TheSnakeFang. The actual admitted count range is 1057..4979. Their original MIT notices are retained under `vendor/notices/high-n-donors/`. The source catalogue is not claimed to carry a blanket license.

Every source certificate is SHA-256 checked against the pinned catalogue manifest. The full inherited credit/provenance record is retained. Exact rational x,y,t=tan(angle/2) are converted to binary64 centers and angles, then cropped by removing squares. No unit square is resized.

`experiments/high_n_donors.py` groups neighboring tilted squares and compares their D4-normalized approximate geometry with the current n<=1000 portfolio. It found 103 component fingerprints absent from that finite portfolio and 1243 distinct usable rectangle crops. This is a finite geometric novelty heuristic at 1e-4 precision, not a mathematical record claim.

All crops satisfy nominal w,h<=31, positive surplus<=63 and fractional bloat<1. All 1243 variants are retained in `artifacts/high-n-donors/all_crops.npz`, with source-square IDs, crop windows, credits and hashes in `all_crops.provenance.json`. A diverse 200-pose subset is in `donors.npz`; its observed maximum w+h is 60. Conservative center dilation supplies 2e-9 separation.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/high_n_donors.py --baseline artifacts/submission-gpu-composition-safe.csv --output artifacts/high-n-donors --max-n 5000 --limit 200
```


## Bounded CPU composition and validation

A 60-second extraction budget plus four strict-corner staircase DP rounds and 20 seconds of closure evaluated the 200 new donors plus 48 current-portfolio donors. Extraction completed in 35.6 seconds and retained 37,403 strict-corner gadget types. The complete experiment took 74.0 seconds and produced **zero improving full puzzles**. Reports are `artifacts/high-n-donors/composition_candidates.json` and `.report.json`.

The selection heuristic favored larger surplus. A complementary run therefore tested **all202 crops with nominal w,h<=12**, plus 96 baseline donors. It retained 3366 strict-corner gadget types, completed four DP rounds in 8.6 seconds, and also produced **zero improvements**. Its bank and report are under `artifacts/high-n-small-donors/`.

All 200 selected exported donors (91,526 unit squares) passed independent interval non-overlap validation. The archive hash and every certificate are bound in `artifacts/high-n-donors/donors.validation.json`. The bounded CPU null result does not test the broader GPU separator/profile joins; the full variant archive remains available for that distinct experiment. No leaderboard submission or paid resource was used.

## Portable private-export loader

The selected NPZ exceeds the notebook source-size cap. `experiments/build_high_n_loader_descriptor.py` therefore emits a compact source-backed descriptor. It records 92 needed source certificates at the pinned public commit, certificate SHA-256 values, run-length encoded source-square IDs, exact binary64 angle bits, and normalization/dilation operations. No runtime trigonometric recomputation is needed: correctly rounded Fraction-to-float conversion and separately rounded scalar IEEE754 steps reproduce every original array exactly across NumPy dispatch implementations.

`experiments/load_high_n_donors.py` verifies the descriptor hash, downloads only those 92 public certificates over verified HTTPS, verifies their hashes, reconstructs each crop, requires an exact per-array SHA-256 match, and independently interval-certifies all 200 poses before writing an NPZ. The actual produced NPZ hash is recorded for remote immutable attachment; ZIP metadata/order is not assumed to match another NumPy version.

Descriptor: `artifacts/high-n-donors/loader_descriptor.json.zlib`, 351,614 bytes compressed (about 440KB base85), raw descriptor SHA-256 `9dd889d16a01939744a9bc42f9e0e7b8e24783ee7c319dd406af07a87c8bb7d9`. Canonical key/shape/array hash: `48f522d7f91b84f74998034145b1baa97ee6fa474f384784e5960c2fd96362d1`. Pinned independent validator SHA-256: `a9db77693e2fb093dcfdbbbfbd913f9420ed0a661ae0eeb8076362c0a8cbae4b`.

Local full reconstruction passed all 200 exact array hashes and interval checks in 36.35 seconds. Its resulting NPZ hash is `9c3620f5d702219da1623d947d25406dc5c3528e23e44d5d90c5b04254d20130`; report: `reconstructed_donors.source_report.json`. Two cold HTTPS downloads, one source from each MIT category, also passed their pinned certificate hashes.

The notebook-frontier agent packaged this loader and descriptor into the unique source-only private CPU exporter `sos54352/squares-highn-9dd889d16a01/1`. Its remote run completed successfully in about 49.39 seconds: all 200 canonical array hashes matched and all 91,526 squares passed interval validation. The downloaded NPZ has exactly the local rebuilt archive SHA-256 above. Evidence is retained under `artifacts/high-n-export-results/`, including `completion-proof.json`, `high_n_donors.source_report.json`, and the actual archive. This establishes remote export readiness; broader GPU composition outcomes are tracked separately.


## Small-bank certification for the broader GPU group

At the primary agent's request, the complementary 202-pose bank was independently interval-certified before inclusion in the higher-n GPU donor group. All 20,260 unit squares passed; zero poses failed. Validation took 3.07 seconds. Geometry covers 63 `(w,h,surplus)` types, nominal w,h=4..12, surplus=1..12, 30..156 squares per pose, and 8..127 tilted squares. The crops trace to 64 source counts between n=1057 and 4561.

- Archive: `artifacts/high-n-small-donors/donors.npz`, SHA-256 `b545814c4e6f99b91238b5708c7f2b4809d3810dadf137d57622282746850c54`.
- Validation: `donors.validation.json`, SHA-256 `2fb62fdeac96fc5a3777d58bdba4c13d54a3a9da8107e2b1c660dc2fac9fc688`.
- Complete donor provenance: `manifest.json`, SHA-256 `574cf6c18d93ba34b78289e785aea5d95f0f372ad63068106ff72fb3f8573236`.
- Compact frozen binding record with every per-array SHA: `frozen_record.json`, SHA-256 `6bc97ffa68e6121255b074bb5098ff5fd2e31b789c7de4c01027e79e52f67a1e`.

Those filenames are relative to `artifacts/high-n-small-donors/`. The record also binds the original catalogue commit, source-manifest hash, validator hash, inherited MIT notices and source-square indices through the complete provenance file.
