# Portable gadget composition and transfer

`experiments/compose_gadgets.py` provides an independent CPU conservative staircase composer, cross-size L-frame/subset transfer, and an adapter for the attributed public CUDA composers retained under `vendor/lightning_ftmc`.

The CPU method follows the public multi-gadget fault geometry associated with Chris Deotte and avazaku. A cropped rectangular gadget holds `w*h+d` unit squares inside `(w+f)*(h+f)`. Diagonal concatenation of gadget rectangles adds their surplus counts while the common square's fractional excess is the maximum `f`. Joining two occupied corner tips requires a one-cell horizontal or vertical buffer. If either touching tip is provably empty in the unit corner, a zero-buffer join is allowed. A vectorized minimax DP retains typed states `(width,height,surplus,outgoing_tip)`. Candidate layouts fill the remaining staircase cells with upright unit squares, undergo rounding-only center dilation, and pass the independent interval validator.

This finite conservative family does not establish global optimality. Empty-corner typing can miss joins whose occupied tips are geometrically separable. The public CUDA separator methods broaden the family using clipped polygon support bounds and several diagonal normals. No unit-square side lengths are changed by either search or admission.

## Inputs and commands

The baseline is a complete CSV and is read without mutation. Fresh donor archives are NumPy NPZ files whose arrays are finite `(m,3)` float64 `(x,y,angle)` poses. The FTMC worker's `worker0_gadgets.npz`, with keys such as `w_h_d__fingerprint`, is directly supported. Every donor is cropped as geometry; key names are provenance, not trusted dimensions.

```bash
# Cheap CPU cross-size closure.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/compose_gadgets.py --baseline artifacts/merged-v2.csv --backend closure --closure-seconds 40 --output artifacts/candidates/closure.json

# CPU staircase composition from the public fixtures and the current portfolio.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/compose_gadgets.py --baseline artifacts/merged-closure.csv --gadgets artifacts/compose-example-seeds.npz --backend cpu --baseline-donors 1000 --seconds 45 --rounds 4 --closure-seconds 40 --output artifacts/candidates/composed-full-frontier.json

# On an available CUDA machine after the FTMC worker checkpoints.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/compose_gadgets.py --baseline artifacts/merged-v7.csv --gadgets artifacts/worker0_gadgets.npz --backend gpu --source-dir vendor/lightning_ftmc --method all --seconds 120 --bins 16 --closure-seconds 30 --output artifacts/candidates/composed-worker.json
```

For the GPU path, `--method corner`, `seam`, or `adaptive` selects one implementation; `all` runs each. The time budget bounds crop/extraction work; DP and validation take additional time. The execution caller should enforce any desired overall job limit. CuPy/CUDA, PyTorch, NumPy, pandas, SciPy and mpmath are needed by the public module dependency graph. On a packaged worker, place `compose_gadgets.py` beside `validate_submission.py` and pass the public module directory explicitly.

The GPU adapter uses a temporary work directory and supplies explicit current baseline and fresh donor files. It replaces the public corner/seam modules' legacy input-loading callback and applies the unsigned-sentinel compatibility fix described below in temporary source copies. The original vendored files, CUDA kernels and geometric implementation remain unchanged. Compatibility filenames inside the work directory are not assertions of external source provenance; the adapter's report records actual source paths and SHA-256 values. It collects only improved-puzzle NPZ outputs and recertifies their serialized decimal coordinates. It does not trust the public modules' floating-point feasibility screen as a certificate.

Exported candidates are JSON in the format consumed by `scripts/merge_candidates.py`; raw output never replaces a submission. Independent interval validation and then the official metric remain required for the assembled CSV. The baseline hash, donor hashes, composition recipes, closure operations, estimated gains, rejected candidates and timing are recorded in the companion `.report.json` file.

## Executed experiments

1. CPU closure on `merged-v2.csv` finished in 10.4 seconds and found four certified improvements, total score gain about `0.000206050892658`. The layouts are subsets of n539→494, n640→590, n868→810, and an L-frame of n916→977. Three remained beneficial after adding the later public-record frontier, producing `merged-v6.csv`.
2. The39 public improved FTMC fixture gadgets plus16 small baseline donors produced3,555 typed gadgets but no new complete packing. This is a useful negative control: the fixtures are already part of the public frontier's ancestry.
3. Full frontier extraction within a45second budget produced25,193 typed gadgets. Four DP passes plus closure finished in80.2seconds. Eighteen certified proposals improved the older `merged-closure.csv`; sixteen remained beneficial against `merged-v6.csv`, yielding `merged-v7.csv`.
4. `merged-v7.csv` independent interval score is `22.3048054387900218395`; its SHA-256 is `9c2cb31c689c90e7f1ab25672d77dea02b88ba63582f0b96dc3d2c992b2055e8`. Actual official-metric/submission results are stored separately and should be read before claiming a leaderboard result.

Three meaningful composition tests verify that colliding occupied tips are rejected without a buffer, the DP requires the necessary buffer, and L-frame growth preserves both packing feasibility and the predicted number of squares. GPU execution of this new adapter still needs validation on the actual GPU machine; CPU results do not establish GPU readiness.

## Bounded GPU job packaging

`scripts/build_composition_job.py` prepares a private job without launching it. Kaggle imposes a 1 MB source limit, so use the source-backed portfolio loader rather than embedding the complete CSV:

```bash
python3 scripts/build_composition_job.py --baseline artifacts/merged-v7.csv --source-backed --baseline-report artifacts/merged-v7-official.json --gadgets artifacts/ftmc-pilot-results/artifacts/worker0_gadgets.npz --seconds 120 --wall-seconds 900 --method all --out artifacts/composition-ftmc-job
```

This generated an 811,673-byte script. It contains the fresh gadget checkpoint and attributed source, while the loader reconstructs the baseline from pinned public sources and exact patches and checks its full CSV hash. The loader is independently tested by `build_source_export_job.py`. Network downloads, GPU preflight and search all run within the same supervised child with a 900 second hard timeout. A test actually starts a hung child and verifies termination and an unsuccessful status. No successful result is claimed from a timeout.

The GPU preflight invokes every selected composer on the known five-square diamond, its ten-square L-extension and a buffered twenty-seven-square composition. It requires the expected side lengths and independently interval-validates all three outputs before searching actual data. These are functional GPU checks, not merely device detection. Actual preflight outcomes are written to `composition_preflight.json`; inspect them after the job runs.

The first FTMC pilot supplied 154 certified gadget variants in `artifacts/ftmc-pilot-results/artifacts/worker0_gadgets.npz`, SHA-256 `b7a22cb4fc9c340afdae01d7d8ff7bada63c084031269201074f7c429640dccb`. Conservative CPU composition of those variants and the v7 portfolio produced 27 micro-improvements, total gain about `0.000001628652544`, but a matched control without fresh FTMC variants produced the same gain. Thus the new rectangle improvements have not yet shown a full-portfolio gain under this conservative joining family. The separately certified result is `artifacts/merged-ftmc-cpu.csv`, official score `22.304803810137479`, with zero invalid puzzles. The profile-based GPU joins are an additional experiment, not an already established gain.

The first actual composition GPU job reconstructed the exact v7 CSV and passed all three known-packing checks for the corner composer. It then failed after 31.6 seconds in the seam preflight: modern CuPy inferred a Python `2**64-1` scalar as signed while comparing it to a uint64 array, raising `OverflowError`. No actual portfolio search or full gain was claimed from this failed job. The adapter now copies the public sources to a process-lifetime temporary directory and changes exactly `best!=np.iinfo(np.uint64).max` to `best!=np.uint64(0xffffffffffffffff)` in the seam and adaptive modules. The value is mathematically identical, with an explicit unsigned dtype. Original and runtime source hashes are recorded; original files and all geometry checks remain untouched. A separate rebuilt review bundle is under `artifacts/composition-ftmc-job-v2`. Its GPU retry must pass the same preflight before any search result can be accepted.
