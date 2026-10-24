# One finite full-pose n65 cold-chain pilot

The planning scope is in `research/n65_persistent_cold_assessment.md`. This
experiment searches for a new n65 construction; the current Göbel construction
is already as good as the checked public scalar reference. No optimality claim
follows from that observation or from the prior negative core/refill searches.

The private offline notebook is `sos54352/squares-n65-persistent-cold/1`.
Frozen source SHA256 is
`4e6059d6d26650e7688e6b429e987f20b42585e8db36bb25af2ea37d928fc073`
(870,560 bytes, 174 payload files). The supported T4 shape allocates two GPUs;
this pilot uses device zero and accounts for both allocated devices. Search is
300 seconds, with a 570-second worker limit, 595-second parent alarm, 600-second
whole-job budget and 720-second server fail-safe. It does not displace the
already-launched n803/n861 experiment.

The 32 independent full-65 chains start from 15 exact coarse geometric-cover
representatives plus one 23-tilt n66-deletion pose. Each source starts once at
each fixed side, current canonical n65 side minus 0.0005 and minus 0.002. The
deletion pose starts wider (about 8.65685426); it supplies a distinct occupancy
attempt, not a competitive initial packing. All centers and angles remain free.
The source cover groups are not proven attraction basins.

Each proposal uses the unchanged corrected symmetric-tie FP64 rigid-unit
quench, requesting 2,000 steps. Physical energy is independently recomputed for
Metropolis acceptance; the native quench report is never used as its substitute.
Independent streams are derived per chain and round, with a separate acceptance
domain. Temperature is 0.3 for the first 200 seconds and 0.03 for the final 100
seconds, at decision time. There are no resets. Current, best, proposals and
pending/completed packet states remain distinct and hash-bound. Actual N=65,
tied-axis, final-unit, overlap-negative and recovery controls must pass before
search starts.

At most eight committed BEST states receive native finishing. Four fixed source
group bins (0–3, 4–7, 8–11, 12–15) supply one minimum-energy state at each target
box; the second box excludes groups already selected for the first. Thus the
eight selected states have different source groups when all groups have finite
states. Energy is never ranked across boxes, and distinct source groups do not
prove distinct final basins. Four CPU workers each use the existing rigid FQ
options, 60 seconds native plus a separate 8-second full-certificate limit.
Every valid result is retained, including worse outcomes. Only unchanged raw,
ordinary-pandas and independent interval gates establish admissible geometry.

All 17 exact input arrays (16 search starts and a separate current reference)
passed fresh full gates in 5.15 seconds. Archive SHA256 is
`3341352955bf5029ec18949153334ba5ae4567befff30fc51bb4a953212bcac0`;
input proof SHA256 is
`09ab33e3c1a31727475448d62dc898218b6d2fa4e7ab5118fdf672f292f29e74`.
Evidence is in `artifacts/fq-n65-cold-inputs-v1`. Source bytes are unchanged,
except a recorded translation of the separate current-reference control.
Historical FTMC certificate IDs hash full NPY files while the audit hashes raw
float arrays; the source handoff explicitly reconciles those different digest
definitions. All 15 original certificates bind their exact source arrays.

The remote package retains all selected lineage, certificates and notices. The
complete 5,465-array audit ledger remains immutable locally: its 1.24MB compressed
size alone exceeds the notebook source budget. Only that redundant full ledger
is omitted from transport, with its full hash/path/size recorded. All 15 selected
ledger records occur verbatim in the transported lineage, and every other
source-evidence file is transported unchanged.

A matched original-reference native control used the same rigid options and
seed 9710000. It finished in 0.99 seconds (0.168 seconds native), passing full
gates at side 8.535533921003891 versus canonical 8.535533905940273: no gain.
Complete logs, exact inputs/output and certificates are in
`artifacts/fq-n65-cold-reference-control-v1`.

Independent review `artifacts/fq-n65-cold-job-v1/independent_delta_review.json`
has SHA256 `383a41ad93a3fb6ed99dff1b4a7873cf762411ae5d3544c9876d9631c90fb842`.
It verifies all 174 payload hashes, 144 unchanged parent files, source/finish
adapters, existing 17 certificates, selected ledger rows, source notices and
bounds. Isolated import and parent-bootstrap controls passed; the three pure
policy tests and full 328-test repository suite passed. These local controls do
not replace the mandatory actual GPU preflight.

The remote source/private/offline identity was verified after the launch ACK at
15:20 UTC. Completion and physical results are pending. No canonical portfolio
or competition submission has been changed by this pilot. If all finishes return
to the Göbel construction, this finite pilot closes; no unchanged extension is
authorized by this note. A genuine gain would first go to the root agent for
exact seventeen-case L-frame propagation and full gates.

The original public solver, corrected GPU source, portable FQ source commit and
all dependency licenses remain inside the frozen package. FQ is Evan Daniel's
MIT-licensed `evand/square-packing`, commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`, binary
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.
