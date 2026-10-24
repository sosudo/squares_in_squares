# Complete structural GPU raw-state selection

The private CPU notebook `sos54352/squares-full-raw-selection-1974/1`
completed in 51.64 seconds. It scanned all 1,974 metadata tables from the
immutable `sos54352/squares-full-packing-structural-repair-v2/2` and verified
all 1,974 complete packet hashes. The selection contains 24 **unverified**
raw states, eight distinct initializer source IDs for each of 147, 299, and
335 squares. It performs no optimization or packing certification.

The fixed eligible set consists of contracted target stages with exact
zero smoothing and a box at least 0.001 below the pinned current reference.
There were 113,694 eligible rows. Selection ranks the recorded CUDA loss,
`2 * wall_squared + 0.5 * unordered_pair_squared`, including its existing
2e-10 pair margin. It takes the lowest remaining distinct source ID per
case, excludes the six exact geometries and native encoded inputs already
finished in `full-gpu-v2-native-handoff-v1`, and verifies selected whole
packet, batch, and row hashes before use. Each selected state has an
independent CPU reconstruction of that weighted loss and a separate
unweighted physical SAT-plus-wall energy. This is not a claim of the global
physical-energy minimum across all eligible rows.

The selected physical minima, at the same approximately 0.002 contractions
as the earlier six-state sample, are:

| Case | Selected key | Physical energy | Reduction from earlier sampled minimum |
| --- | --- | ---: | ---: |
| 147 | `n147_00` | 5.84932645e-6 | 11.5% |
| 299 | `n299_01` | 5.59883167e-6 | 16.0% |
| 335 | `n335_00` | 4.88656441e-6 | 22.0% |

The 299 physical minimum differs slightly from the weighted-loss minimum.
Six, six, and seven selected source IDs respectively were absent from the
two previously tested sources for that case. Source identity establishes
provenance diversity; it does not establish different packing topology.
All selected states retain positive overlap and require repair and full
unchanged gates before any portfolio admission.

Reproduction and evidence:

- Selector: `experiments/select_full_structural_gpu_raw.py`, SHA256
  `2d68f5795d547512ffa11398cbc57ca68b0a6023b2ba8c450948f28e42f31fba`.
- Builder: `scripts/build_full_structural_gpu_raw_selection_job.py`.
- Frozen source: `artifacts/full-raw-selection-1974-job-v1/search.py`, SHA256
  `1eedb9f222a0e222af380766fa1cc09ac77f4c573d1a677e97ed76e6bac8d981`.
  The source is 62,698 bytes with 14 exact payloads. It uses a 170-second
  child bound, 175-second parent alarm, and 240-second server cap.
- Independent source review in that job has SHA256
  `0616cffcca883516ce0f29abc8d30f35c8c1079d113450425abfdac5e87d7e54`.
- The existing 20-packet local control completed in 0.828 seconds, selected
  24 states, reproduced all six exclusion encodings, and passed overlap
  positive/touching negative controls. No optimizer or certificate ran.
- Downloaded results and the local exact binding audit are under
  `artifacts/full-raw-selection-1974-results-v1`. Its `completion-proof.json`
  has SHA256 `c2a6745212d2c83a3dd6749c381fa7e7293e996701ed4027bfe9d8404153fe35`.
- `outputs/selection/selected-raw-states.npz` has SHA256
  `2bb30f798af99371e118531c2a2b2707cbb70b4cd8158bc799932f08d540fc4f`.
  It retains the 24 selected states and their 24 original mutation inputs.
- `outputs/selection/selected-rows.json` has SHA256
  `52deea72dd46d00b62f91bacac005891199a2b27822163d7242d4203db26c513`;
  the full selection report has SHA256
  `3eaab551997db82c0b12ce3f351cdb7a390366f0eb0bc3854bdbf77b2cac825d`.
- `comparison-to-six-negatives.json` binds the two already-computed energy
  tables without running additional numerical checks.

The attached source, notices, current reference proof, exclusions, and
full packet index remain pinned in the frozen job. The canonical portfolio
and competition submissions were not changed.
