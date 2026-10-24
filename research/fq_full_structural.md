# Full-puzzle structural search from N+1 constructions

The frozen b937 portfolio scores 22.301105560583192. A public **rendered scalar**
per-puzzle table, version 10/361620939, reports a side of 17.80271885439858 for
299 versus our 17.82287565554912. That empirical gap would be worth approximately
0.001165698 score, enough to cross 22.3. It supplies a target, not coordinates,
an independent certificate, or an attainability guarantee for this search.
Puzzle 335 has an even larger reported score gap of 0.001528245; 412 and 454
also have gaps above 0.00117. The source is recorded in
`artifacts/public-freshness/notebooks-20261024T092136Z/public-gap-analysis.json`.

The previous component hillclimbs had plateaued. This experiment changes the
complete starting topology: take the already certified N+1 construction, delete
one strip or endpoint-adjacent square, then release all N squares. The 300 and
336 constructions have visibly different diagonal strips from 299 and 335.
No single deletion immediately reduces their bounding side. Their source costs
relative to the target are respectively 0.001247733 and 0.002695844 in side.
Thus the dense source needs a genuine rearrangement, not an accounting change.

`experiments/fq_full_structural.py` compares deletion-only ALM release with a
coherent rotation of the 12 squares nearest the vacancy (±6° or ±12°), and a
sinusoidal bend of the tilted strip (position amplitude 0.18, with matching
tangent rotations). The rotations preserve the selected cluster's internal
distances. Deliberately overlapping mutated poses are explicitly optimizer
inputs; they are never exported as valid donors. Distant squares are free during
the full-puzzle release. Native options are `--loosen 1.001 --outer 45 --pit 100
--flip-top 16` with ordinary ALM enabled.

The source safe CSV is default-pandas parsed and normalized, then every selected
N+1 source is freshly certified. Comparisons use the frozen **raw** b937 target
side, never the worse N+1 or mutated parent's side. Each trial records the exact
ancestor, deleted index and square, valid-deletion geometry SHA, actual mutated
input SHA, native text input SHA, options, seed and frozen binary SHA. Every
accepted output passes official raw, 17-digit pandas and ordinary default-pandas
checks, plus independent interval checks on raw/default-pandas coordinates.
All certified outputs are retained with exact SHA and before/after contact
graphs, including valid nonwinners useful as different starting basins.

Four deterministic unittest cases cover exact count/parent bindings, coherent
rotation distances, bounded strip displacement, and actual native timeout.
The real four-trial smoke completed in 14.35 seconds, all four full-certified:

| Target | Mutation | Certified side | Side above current | Changed contact edges |
|---|---|---:|---:|---:|
| 299 | delete endpoint square 298 | 17.82289695758357 | 0.0000213020 | 67 |
| 335 | delete square 281 | 18.825416017357934 | 0.002540362 | 32 |
| 299 | rotate 12 near square 278 by 6° | 17.827194689384342 | 0.004319034 | 113 |
| 335 | bend after deleting square 291 | 18.82541601735795 | 0.002540362 | 24 |

Smoke manifest SHA:
`6d610da62db8fbf90dafede15507d33bdfb024cc7f0f11f6acee2617f50c39d3`.
Executed script SHA:
`173137ef444c07a5a8d1739c75258693aaf030c8977e6f93489cf01ac4a5e382`.

The separately frozen campaign `artifacts/fq-full-structural-v1` has two CPU
workers, a 600-second outer process-group deadline, a 20-second whole-trial
alarm including certification, and a fixed 72-trial plan. Targets 299/335 get
twice the visits of 412/454. Immutable snapshots are published after each
completed trial. The outer process group includes both Python workers and the
native executable, so its hard deadline also bounds worker shutdown and native
work. Per-trial timeout kills the owned native process and observed descendants.
No Kaggle job or submission is launched by this experiment.

The full 72-trial plan completed in **183.09 seconds**, with 72 fully certified
outputs and **zero improvements** over b937. The best sides were:

| Target | Trials / distinct tilted deletions | Best side | Side above current |
|---|---:|---:|---:|
| 299 | 24 / 6 | 17.822878996195904 | 0.000003340647 |
| 335 | 24 / 6 | 18.823131411974725 | 0.000255756396 |
| 412 | 12 / 3 | 20.823096580887405 | 0.000220925350 |
| 454 | 12 / 3 | 21.825024055602764 | 0.001921398487 |

`experiments/analyze_fq_full_structural.py` verifies every recorded native input
against its stored coordinates/encoding and source/deletion hashes, and every
certified geometry against both its per-trial archive and final exact archive.
The audit also compares competitive outputs with the current packing under all
eight square symmetries and a position/angle-weighted assignment. These are
diagnostics, not new geometry certificates. Distinct layouts survive: the best
299 output has **41 tilted squares versus 43** in the current layout, with RMS
assigned center difference 0.0964 and maximum difference 0.5914. Sixty-three
outputs within 0.005 of current side have RMS assigned center difference above
0.05. Their scalar sides approach the same bottleneck, but the geometries are
not merely byte-identical returns to the incumbent.

Final snapshot: `artifacts/fq-full-structural-v1/snapshot-00074`.
Donors SHA: `c51ccfa424b625155f77f5b34522c46cfe9876d10cc2c7275fefe87c0d8bb5d8`.
Manifest SHA: `68b10b86f0a00dbd94b58487c8dd1ef55e26b034c8cb0fa81ce22529825eee8f`.
Audit: `artifacts/fq-full-structural-v1/analysis.json`.

The finite plan did not reach upright end caps: the main targets' six deletion
sites were all tilted squares. A separately authorized **180-second, two-CPU**
control therefore covers all four upright endpoint-neighbor candidates selected
per target, prioritizing actual corner caps, followed by ±6° vacancy rotations
for those eight main-target sites. This is 16 deletion-only trials plus 16
coherent rotations, with no unchanged campaign extension. The separate output
directory is `artifacts/fq-full-structural-caps-v1`; its source is newly frozen.
The future-run source also fixes the harmless timeout-exit `killpg` race and
supports the previously unused `control` mode consistently. All five current
unittest cases pass. Earlier executed source snapshots remain untouched.

The cap control completed all **32 trials in 75.22 seconds**, all fully
certified and again **zero improvements**. Its best 299 side is
17.822876618715814, only 9.631667e-7 above b937; other best sides are
18.82470036183056 (335), 20.823096580887476 (412), and 21.823473465550673 (454).
All 16 selected upright cap/neighbor deletions were exercised. There is no
further unchanged search allocation. Its independent provenance audit also
passes; donor SHA is
`375f9e4bcb0c1a2ebe76244eb9534f058f4fe2595a538036c80efb679dbd4f0e`.
The future source SHA used for this run is
`9795f5972c3ee3c595355def7b1c51ba24652bdbb5870f23973d8cfbe639678c`.

The immutable handoff `artifacts/fq-full-structural-handoff-v1` retains all 104
exact certified full-puzzle alternatives, the best alternative for each case,
and freshly fully certified current reference poses. The alternatives are
potential different starting topologies, not improved submissions.

- `variants.npz`: `b0819e846409cade27dfba7fc958c6a723508ebc67c91e5e2c71acd996522018`
- `best-alternatives.npz`: `74ca59368db2a0158b9acedb9aceb8c3f36b12050b591ee8bb5f2cdf1d149f2a`
- `current-reference.npz`: `30c6c4096ba1c13a1c0bd5375108dc5cb714afce442e390f4c019072ebabc84e`
- `manifest.json`: `72164f059ac21e5ea5d67b44daeac6a3b44bc2d1e9b00f78509106fd68893f30`
- `provenance.json`: `dcf5cdcfb232c695d4e740dd84df3538d444404561a5a2a54aa26af6ab056c66`
