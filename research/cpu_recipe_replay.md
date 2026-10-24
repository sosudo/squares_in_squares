Direct CPU replay found **17 certified complete-puzzle improvements** without a
GPU dynamic-programming run. It reduced the fully certified safe portfolio
from 22.303038673749423 to **22.302494429786211**, a gain of
0.0005442439632119545. Ordinary pandas numeric roundtrip has the identical
binary64 score and zero invalid cases. This remains above the user's strict
22.3 submission ceiling; no submission was made.

The frozen replay used the original 35 accepted broad-composition recipes,
the final multiscale best bank at snapshot 00099, and the broad-active component
polish bank. It kept all chain dimensions, join modes and separator angles.
For every chain the unchanged public CPU `stitch` function reproduced the
original recorded side within 1e-9. Its first whole-puzzle reconstruction also
passed a full official and independent raw/default-pandas positive control.
The implementation extracts only unchanged CPU function definitions from the
attributed public modules; it never imports CuPy or initializes a GPU.

New component candidates retain the original crop's left/bottom wall phase.
The first frozen experiment considered all D4 orientations with matching
dimensions and surplus, computed both separator profiles, and used a small
CPU minimax chain dynamic program to select compatible replacements. Unit
square sizes and angles were not rescaled. Complete reconstructed layouts
received a rounding-only center-clearance repair, then passed official raw and
ordinary pandas checks and independent interval validation on both forms.

All 17 complete-puzzle candidates were independently admitted into the raw
portfolio; none was rejected. The principal gains were n=927 (0.000172722),
n=989 (0.000167221), n=930 (0.000058761), and n=701,755,811 (approximately
0.000026–0.000029 each). The full replay completed in 32.84 seconds with one
worker under an external 300-second process-group ceiling.

Immutable evidence is retained in `artifacts/cpu-recipe-replay-v1/`:

- Candidate JSON SHA256:
  `f1e3ff0f17c8db9d71f92f4160a636a2272313e32ba69f0711d95119d7ce4198`.
- Per-case report SHA256:
  `a88bd728c698e200f4cdb5ecf1ef696904aa43065aa9bb31b753556b44f6b6a1`.
- Frozen source modules, exact input banks, structured command, source hashes,
  full geometry certificates and completion receipt remain beside those files.

Final portfolio evidence:

| Artifact | SHA256 |
| --- | --- |
| `merged-cpu-replay-v1.csv` | `4885ef2f2932bb665f8cad4a42cb5c0233224208970796ca93fbe20d1b95ff3f` |
| `submission-cpu-replay-v1-safe.csv` | `b2a93f03252b15181b3bcb10e00143f44e4996c721d6aabb90f9d6362eb9dce1` |
| `submission-cpu-replay-v1-safe-roundtrip.csv` | `1bab20d5c9655c6a04f1325d3026927ae0a47f2ef069798faf3bc4a26a15d32b` |

The canonical `submission-cpu-replay-v1-safe.transport-validation.json` binds
the official reports, raw independent certificate, exact shared transport
transform and pilot provenance. Every official report covers all 1,000 cases;
17 changed cases were evaluated and 983 exact matches reused. All 89
long-precision safety-scaled cases are byte-equivalent at the official puzzle
hash level to the preceding certified safe portfolio.

The next implementation version adds explicitly frozen `--join-check`
settings: `bins` preserves the first experiment, `continuous` removes profile
quantization false negatives, and `sat` checks exact cross-block unit-square
separation at the unchanged stitch-relative offsets. The latter can admit
valid pairs without a separating line at one of the saved normals. Its 1e-12
floating contact allowance is for proposals only; full official and interval
certificates decide acceptance. These modes do not change the completed v1
snapshot. Six regressions cover greedy/minimax differences, buffered joins,
public count preservation, continuous quantization gaps, and separated,
touching and overlapping SAT pairs.

The frozen SAT pass completed all 35 chains in 25.78 seconds using final focus
snapshot 00083, final multiscale snapshot 00099, soft-method snapshot 00023 and
their full donor archives. It found **11 additional certified improvements**
against the subsequent GPU-composition portfolio, for a gain of
0.00009830109279019987. The raw merge scores 22.302227280115410; its safe version
scores **22.302227280985999**. The winning selected joins also satisfy the older
bin rule, so this experiment attributes its gains to the fresh/diverse donor
geometries. It does not demonstrate an additional gain from nonseparable SAT
joins.

SAT experiment evidence lives in `artifacts/cpu-recipe-replay-sat-v1/`.
Its frozen candidates have SHA256
`809b67f80aa630639f231156b512568feb0ba1b883347454d59fa903b004c3d6`.
The compact `whole_puzzle_donors.npz` contains all 11 exact successful layouts,
SHA256 `596c40dc888748867dd42b82ece8a1ab512087903bae4ea760aa2c080348ba63`.
`winning_rectangles.npz` contains 17 actual winning replacement blocks,
SHA256 `eef5cf78cc5203ac49c139bd4312bbdbc6eb1e0c438a53918f7dd736622e894e`.
These blocks are unchanged row subsets of the successful certified complete
layouts; removing other squares preserves their geometric validity. Original
global coordinates and exact full-puzzle row IDs are retained in
`donor_export_manifest.json`. No new standalone official score is claimed for
the subsets, and all future compositions still require full certification.
