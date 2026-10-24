# Rigid-square rectangular-wall continuation

This finite pilot starts from cold rectangular grids rather than an incumbent ribbon packing. The enclosing rectangle changes aspect ratio at fixed area while all335 squares keep unit sides and rigid-square geometry. It uses the unchanged corrected fused FP64 kernel: symmetric exact-axis gradients, `--fmad=false`, exact tau0 and explicit independent width/height arguments. There is no Metropolis acceptance, center scaling or unit-shape deformation.

The32 inputs combine two grid families, four vacancy patterns and four independent tiny perturbations:

- 19×18 grid minus7 holes, initially19.2×18.42204421875.
- 20×17 grid minus5 holes, initially20.2×17.510061831683167.

The hole patterns are a diagonal, a right-edge vacancy segment, an alternating central seam and a horizontal channel. Validation's original four starts per family include bounded center/angle perturbations. Each replica adds at most0.0005 per center coordinate and0.05 degrees per angle. All32 prepared starts have exactly zero independently computed rectangular penalty, minimum pair clearance0.00479369 and minimum wall clearance0.00336667. Preparation took0.93 seconds without optimization.

Each family follows its own33-stage path, with width decreasing linearly and height equal to18.807²/width. Every transition translates all centers by half the change in each wall dimension. This keeps the box centers aligned without scaling pair distances or changing angles. Both families reach the exact18.807 square at stage32. Up to16 additional square stages follow. Each stage requests2,000 iterations; the complete49-stage plan is capped by a180-second parent search deadline. The previously tested400-step hop calls all saturated their iteration budget, motivating this deeper repair control.

`artifacts/fq-rect-wall-inputs-v1/rect-inputs.npz` freezes the32 poses,49 actual box arrays and all centering translations, SHA256 `efb5ab7bb1e172187a46150ad875dcb946f64252083780070233be6365806323`. The configuration SHA256 is `b20e89f50bb9fc3e1447139a74f0da2a9b7f43ec94f57e4d5615830657eac136`. Both original grid manifests, exact occupied-cell identities and hole patterns are retained separately in the same input package.

Before search, the notebook must pass the existing full335/tied-axis controls, all32 initial rectangle checks, swapped-width/height controls, final-index pair negatives at both endpoints, a rectangular wall finite difference and a real2,000-step rectangular wall repair for both families. The repaired positive controls receive full geometry certificates; raw rectangular containment diagnostics remain distinct from those certificates.

Every stage first saves its pending input, prior output and actual width/height. Returned poses and fresh independent all-pairs/four-wall energies are then atomically committed. The native optimization loss and its potentially stale line-search residual remain separate diagnostics. Only final equal-wall stages are screened for square admission. A bounded30-second/eight-candidate drain applies unchanged full gates to prospective improvements; all other exact raw stages and pending candidates remain explicitly unverified.

The notebook uses one GPU with300-second worker,480-second whole-job and600-second server bounds. It is a separate experiment; the completed persistent-hop sources and results remain unchanged. No competition submission is part of this pilot.

## Executed result

Private offline notebook `sos54352/squares-rectangular-wall-continuation/1` completed normally. Its remotely verified source SHA256 is `2216a6cd8ccf4834ca504063107dd9446dde29a75620fcf83172278087e4f1b6`. The frozen package is `artifacts/fq-rect-wall-job-v2`: all 72 payload hashes and extracted imports were independently checked; all 65 parent files remained byte-identical. The actual GPU passed the unchanged tied-axis/full-335 controls and the new rectangular containment, wall-gradient and positive-repair controls before search.

All 49 stages and 1,568 stage poses completed in 95.32 seconds of search, within the 180-second cap. The whole worker took 120.82 seconds. Quench calls used 41.01 seconds; independent dense physical diagnostics used 53.54 seconds. The raw index binds 49 complete packets totaling 39,557,169 bytes, with no pending or unindexed packet. The finite plan stopped normally without hitting a byte or time limit.

| Initial grid | First stage with physical energy above 1e-8 | Best final-square physical energy | Maximum folded angle in retained best poses | Reduction from first square stage |
| --- | ---: | ---: | ---: | ---: |
| 19×18 minus 7 | 17 | 0.02173946356 | 0.3214° | 0.180% |
| 20×17 minus 5 | 5 | 0.86795468606 | 0.1873° | 0.110% |

The grids compressed into nearly upright arrangements instead of reorganizing their rows and columns. None of the 32 retained square minima has a square tilted by one degree. None passes the existing rounding-only repair, so there were zero prospective square candidates and zero certified improvements. These physical penalties are diagnostic values, not geometry certificates. The maximum pair penetrations among retained poses were about 0.011 and 0.064 for the two families.

Of the 1,568 native call reports, 752 saturated their 2,000-step request. By stage 37, however, all 32 reports returned iteration index zero, and the remaining square stages made no further progress. That diagnostic does not identify a native stop reason, but the preserved poses and energies show that repeating this unchanged wall path would not address the observed plateau. This pilot is closed without an extension.

Aggregate outputs and exact download receipts are in `artifacts/fq-rect-wall-results-v1`. `analysis.json` checks all downloaded hashes, all stage/index links and every retained square minimum with the independent dense oracle. Raw packets 0, 16, 31, 32 and 48 were downloaded separately to `artifacts/fq-rect-wall-raw-audit-v1` for a second reviewer. The exact final-square best archive SHA256 is `407439bb794f65ffd12724560033c5e22fe26605de1ec44850f3480308d1d92d`; the complete raw index SHA256 is `722a43a239afce4283a0c14ad1b67de27222b46465053f32ea36240d4cbe7577`.

The frozen recovery summary's field `remaining_uncertified` means remaining *unattempted* candidates. The read-only analyzer explicitly reports both unattempted and not-certified counts; both are zero for this run. Failed or timed-out certificates would remain present in the pending archive and failure records. This reporting caveat did not affect the numerical method or admission gates.

The independent terminal/path audit also passed. It recomputed 288 full-335 energies across eight downloaded stage packets and all 32 final-best poses, with maximum energy difference 4.44e-16. Each final-best pose is byte-identical to its recorded stage 32–35 origin, and the origin choices match the 17 square-stage event minima. Selected transitions exactly preserve the prescribed translation and unchanged input angles; adjacent stages 31 through 35 link exactly. The receipt is `artifacts/fq-rect-wall-results-v1/independent-terminal-path-review.json`. This audit performed no optimization or new certification.
