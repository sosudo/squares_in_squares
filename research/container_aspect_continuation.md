# Cold n335 starts under changing rectangular walls

The existing corrected fused solver supports this experiment directly. The
native FQ CLI does not expose a faithful fixed-wall, raw-return path, so no
native optimization campaign was run.

FQ's `--rect-dx` and `--rect-dy` set walls to `(s+dx,s+dy)`, but its normal
quench and polish optimize `s`. Its fixed-side rounded/aspect pre-stages still
end in a free quench/polish and unconditional geometric repair, which can grow
both requested walls. Disabling quench/polish does not disable that repair.
Using those final outputs as though they followed an exact constant-area wall
schedule would misstate the experiment. The existing
`gpu_rect_optimizer.quench(q, boxes[B,2], steps=400, tau=0)` instead takes both
wall dimensions as fixed inputs. Its corrected symmetric ties and
`--fmad=false` can remain unchanged.

Four new cold inputs start from a 19×18 grid with seven explicit holes:
a diagonal, a right-edge segment, an alternating central seam, and a
seven-cell horizontal channel. Each has exactly 335 rigid unit squares.
The initial box is 19.2×18.42204421875, area 18.807². Initial independent
bounded perturbations are at most 0.001 in each center coordinate and 0.15°
in angle. Independent dense pair/wall checks give zero rectangular energy,
minimum pair gap greater than 0.005, and minimum wall gap greater than 0.003.
These are numerical rectangular input controls, not square-packing certificates.

The same arrays placed in the final 18.807 square have 11/11/11/17 actual
crowded near-axis bands under the pinned native detector. The old n335 ribbon
has none. This supplies a concrete occupancy change for the experiment to
resolve, rather than another perturbation of the existing tilted ribbon.

The proposed 33-step schedule decreases width linearly from 19.2 to 18.807 and
sets height to `18.807²/width`. At each transition translate centers by half
the wall-dimension change, preserving centered placement without scaling
centers or unit shapes. Quench at the new fixed rectangle and retain the raw
geometry and actual W/H. Physical energies from different rectangles are not
interchangeable acceptance scores. Only the final equal-wall geometry can
enter the existing independent/raw/default-pandas square admission gates.

The frozen handoff is `artifacts/wall-aspect-cold335-inputs-v1`:
input archive SHA256
`1f47c683a2f70e227162836656ed54e1a1de1f912191e7ceaa41cde8a6831eb2`,
manifest SHA256
`4660d1dfcba4a0c3e60ee1b7cc931b5c776d7ee90f2cd25b32c77bae57084f99`.
It retains all grid IDs, removed cells, RNG seeds, exact arrays, geometry
hashes, source identities and the complete wall schedule. Preparation took
0.34 seconds, with zero optimizer calls, remote jobs or new certificates.
The original helper `rectangular_control` supplies an independent dense
unit-square energy check with separate pair and rectangular-wall terms.

At the continuation agent's request, a second family adds four 20×17 grids
minus five holes. Its starting box is 20.2×17.510061831683167 at the same area;
20 columns and only five vacancies require a different, larger occupancy
change. All four initial rectangular energies are zero, with pair gaps above
0.004 and wall gaps above 0.003. The target-square detector finds
17/17/17/16 crowded bands. This separate 0.40-second construction used no
optimizer. Archive `artifacts/wall-aspect-cold335-20x17-inputs-v1/cold335-inputs.npz`
has SHA256
`628ad1d28fe729763fc8782d49f0f0f9cb84427329a6705a1e3512df2980c014`;
its manifest is
`668d1352ea19703f1e7bdca1e8f9c22b08d8902b6ef594f3164923d02ed48e0f`.
The exact preparation source and full schedule are retained beside it.
