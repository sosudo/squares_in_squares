# Uniform-angle LP screen of n147

The requested fixed-separator construction screen completed in 2.87 seconds
on one CPU. Neither direction of any prescribed nonzero angle offset improved
the current side. This is a finite branch model result, not an impossibility
claim for other pair branches, nonuniform angles, or different occupancies.

The exact input was n147 from `artifacts/merged-public-v29.csv`, archive SHA256
`a0dad731adc6cacc9c882082aaf9464c7c7fc755ce4eabba6f711b1c31b969bc`,
with official side `12.6568542495040365`. It contains 64 squares at the recorded
angle `0.7853981633974483` and 83 at zero. Earlier structural work used n148
deletions and native mutations; it did not solve this all-center n147 LP.

For every one of 10,731 pairs, the code selected the largest absolute center
projection onto an original square-edge normal using 80-digit arithmetic on
the original decimal coordinates. Every chosen branch was separated; the
smallest source gap was `9.98e-13`. The owner square, edge index and projection
sign were then frozen. Each new angle prescription recomputed that owner's
normal and both square supports. All 294 center coordinates were independent,
each with a ±0.5 bound around the translated input center; all 83 outer angles
remained zero. Four wall inequalities per square and one separation inequality
per pair define a linear program minimizing the box side.

The original-center and 1.01-center-dilation controls both recovered
`12.656854249492378` before rounding repair. Both passed the unchanged official
raw/default-pandas and independent raw/roundtrip gates after the standard
rounding-only clearance; their certified side is `12.656854272806177`.

| Core offset | Optimal LP side | Side minus current |
| ---: | ---: | ---: |
| −0.25° | 12.65690809918036 | +0.00005384968 |
| +0.25° | 12.67436150246316 | +0.01750725296 |
| −0.5° | 12.65706965337055 | +0.00021540387 |
| +0.5° | 12.69197712453359 | +0.03512287503 |
| −1° | 12.65771594703488 | +0.00086169753 |
| +1° | 12.72753620674774 | +0.07068195724 |
| −2° | 12.66030235274942 | +0.00344810325 |
| +2° | 12.79998543071641 | +0.14313118121 |
| −4° | 12.67066771102969 | +0.01381346153 |
| +4° | 12.95037495880372 | +0.29352070930 |

All twelve solves were optimal within the LP solver's tolerances. No center
bound was active: the largest coordinate motion across all results was below
0.445. The asymmetric response is specific to the frozen branch choices.
The ten dominated nonzero-angle poses remain explicitly unvalidated raw LP
outputs; their floating SAT residuals are diagnostics, not certificates.
There were no portfolio changes or competition submissions.

Reproduce with:

```sh
.venv/bin/python experiments/n147_uniform_core_lp.py \
  --out artifacts/n147-uniform-core-lp-replay
```

The default input is the current canonical pointer, so exact historical replay
requires a pointer with the above raw/report identities. The executed source
and input rows, selected branches, hashes, raw poses, both control certificates
and supervisor report are frozen in `artifacts/n147-uniform-core-lp-v1`.
Executed source SHA256:
`78d40ac0e72a02347990e1ad9967f841928c3ff1a955cb9e2fad37e41f9ddf46`.
