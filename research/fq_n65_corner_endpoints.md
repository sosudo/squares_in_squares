The finite n65 corner-transition control succeeded, but it produced no side
improvement. The exact Göbel builders for n5, n40 and n65 passed complete
Q(sqrt2) verification and duplicate-square negative controls. All four mapped
sliders have first blocking distance sqrt2/2−1/2; interior slides pass and
beyond-end slides fail. All 47 endpoint/midpoint combinations are feasible,
have changed angle-aware contact edges, and pass independent interval plus
official raw/default-pandas checks after materialization.

The pilot completed 47 rigid-polish and 47 square-shrink trials. It retained
94 unique certified geometries, with no improvement against the immutable
excess0.5355339059402731 reference. The first local-aspect trial then stopped
at the conservative frozen-motion guard: native final repair reported
1.616e−12 against the original1e−12 tolerance. This is an algorithm-neighborhood
guard, separate from the full geometry metric; its tolerance was not relaxed.
The final rigid intermediate was recovered from the preserved native output,
fully certified and stored separately, without claiming the frozen treatment
passed. No continuation search was launched after priority moved to the
larger public-gap families. One CPU was used; the observed search-file
timestamp interval is68.50seconds, not a monotonic runtime certificate.

The original executed source remains at
`artifacts/fq-n65-corner-endpoints-v1/source-at-execution.py`,
SHAeae0a0b8a0edbea3abd3dcf557444af9099e9a235f5f166b720a9bf5eea50b3e.
The diagnosis, exact construction, mapped blockers, individual gates and
retained archives are bound in that directory's `run-diagnosis.json`.

Independent review identified future safeguards that are now implemented:
hard per-phase alarms inside the existing process-group supervisor; immediate
immutable retention before rigid release; explicit intermediate/final records;
coherent final geometry hashes, scores and certificates; and interleaved
method coverage. The minimum tracks every retained certified intermediate.
The original failed run and source were preserved. Three focused exact
collision-interval regressions pass. The revised search code has not been
rerun, so its new local-aspect path is not presented as a successful control.

Public code attribution is Joshua Levy, the squares project
(https://github.com/jlevy/squares), MIT code with its full license copied into
the run; the public research reports are CC BY4.0. Native FQ remains Evan
Daniel's MIT implementation at659ee62e4a9d39542a1146e8b011cc3ab6407ede.
