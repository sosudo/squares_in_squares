# Local aspect continuation on complete puzzles

`experiments/fq_full_local_campaign.py` applies strong local aspect continuation
to complete n813, n871, n931, n807, n815 and n924 poses. It preserves the real
composition join and freezes distant squares during the temporary deformation.
The first mask uses the previously tested opposite-tilt join; later masks sample
unlike-angle pairs within 0.035 of SAT contact. Neighborhoods contain 20, 40 or
64 free squares. Aspect amplitudes are 0.3 or 0.6 and return to exactly zero in
12 or 16 native steps. The source is Evan Daniel's pinned MIT-licensed FQ commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`.

The actual n813 control took 26.35s including complete independent and official
numeric transport checks. Its local native stage took 1.13s; ordinary global
ALM consumed the remaining budget and timed out. Production therefore used an
unrestricted contact-LP release with `--no-alm --pit 20 --flip-top 0`. Each local
stage, including certification, has a 12s ceiling; the combined local/release
attempt and its bookkeeping share a 28s alarm. An outer process supervisor
caps the complete run at 590s. Every fully certified local intermediate is
saved immutably before release. The unchanged complete certificate includes
official raw/17g-pandas/default-pandas and independent raw/default-pandas checks.
Only the original unit-square geometry is admitted.

The run is `artifacts/fq-full-local-v1`, with executed wrapper SHA256
`37d2c3fa9beb3d59aab6f0f964eb62c72e307bf45da949e1691a6edf9084c467`,
binary SHA256
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`,
and complete source portfolio SHA256
`be22cb064c823a843d44b6734d78b5101cad7d7c3d27d97168845454e124e721`.
Three tests cover the mask partition, translation-invariant pose/contact
diagnostics, and rejection of a missing zero-aspect return before decoding or
certifying output.

The run was deliberately stopped after **340.89s**, once all six puzzles had
20/40-neighborhood coverage and the three priority puzzles also had 64-square
controls. The largest controls frequently left the near-best band or timed
out. The frozen wrapper had no STOP hook: an explicit stop script paused its
Python worker while its exact frozen native FQ child was live, verified that
boundary, then terminated only those owned processes. No certificate evaluation
was interrupted. `intentional-stop.json` records the exact stage and the
supervisor's exit -9 is intentional, not an unexplained failure. After that run,
the repository wrapper gained a cooperative `STOP` file checked before each
trial and after the certified local intermediate is safely retained. The frozen
executed source and its original hash above remain unchanged.

The retained archive contains **28 independently and officially certified full
poses** (15 local intermediates and 13 released poses), SHA256
`002686b29631ab7a0533ed88c50b3b192bd863afd3153b601598ae4aed990ff0`.
The exact aggregate matches all immutable NPZ/JSON certificate pairs. Twenty-two
variants changed the diagnostic contact graph; maximum local displacement was
0.2741 and maximum angle change was 14.62 degrees. These are real changed
geometries, although they produced little additional objective improvement.

The initial apparent score gains mostly overlapped the concurrent full-contact
LP campaign. Against its newer portfolio SHA256
`ad1daf5dafb4ef95b77d3143cb49512ab64d6b8d27fd3e7d3dc5731626868e99`,
score `22.301704749832588`, the remaining gains are:

| n | Certified side | Additional side decrease | Additional score decrease |
|---|---:|---:|---:|
| 931 | 30.9369160669764402 | 0.0000206888979 | 0.0000006780512 |
| 871 | 29.9363388995594475 | 0.0000012128899 | 0.0000000410972 |
| 924 | 30.8617532309448593 | 0.0000000882406 | 0.0000000029029 |

The combined extra score decrease is **7.2205135e-7**; full portfolio merging and
validation remain the parent's separate step. The immutable final handoff is
`artifacts/fq-full-local-v1/handoff-final/candidates.json`, SHA256
`30c784857c12408e69789c2c4100d5ef87cddb40462406a3578a5b1f82db428a`.
`experiments/analyze_fq_full_local.py` verifies exact geometry/text/archive/
certificate bindings and local-to-release ancestry without rerunning identical
certifications. Coverage and conservative comparisons are saved alongside it.

This method can cross real local contact arrangements but is a poor use of
further full-n CPU time at the observed yield. The remaining allocation moved to
small repeatable families and a distinct scalar staircase-composition search.
