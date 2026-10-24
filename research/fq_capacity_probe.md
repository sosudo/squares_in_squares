The fresh-component capacity probe found **no increased-capacity donor**.
It tested 22 canonical rectangle types from the frozen 21-type multiscale bank
and the subsequent broad-active polish bank, including the new 6×22 +16 family.
Transposed entries were grouped and the smallest actual-bloat representative
was retained, with all alternative input geometry hashes preserved.

The immutable inputs were:

- `artifacts/fq-multiscale-v1/snapshot-00061/best_bank.npz`, SHA256
  `9fa57308c8580ab24f0bc178a33119f2fa8a39b3cafdb8bc3f320beb224e6fed`.
- `artifacts/fq-broad-active-polish-v1/improved-types.npz`, SHA256
  `1652171f65d83a63953269734ff3d7885308c4caff23f072e745fb9abd42bf4f`.

For each actual `(w,h,d)`, the available box was `(w+f+s,h+f+s)`, where `f` is
the maximum actual span minus its nominal dimension and `s` was 0, 0.002 or
0.02. Both upright thresholds, 1e-6 and 0.018 radians, were tested. Removed
near-uprights supplied candidate centers only. The existing strict SAT filter,
upright conflict graph and finite maximum independent set solver operated with
zero permitted soft overlap. Any increased-capacity output would also have to
pass the shared official raw/pandas check, default-pandas transport check, and
independent interval checks before export.

All **132 parameter settings were covered**: 128 completed strict finite
searches and four rejected boxes whose bloat would reach or exceed 1. There
were no timeouts and no observed extra squares. Every one of the 22 original
counts was reconstructed at zero slack with the strict 1e-6 threshold. The
0.018 classification sometimes lost several squares, illustrating why snapped
near-uprights cannot be accepted without fresh geometry checks. A complete
source component also passed the full official/independent raw/default-pandas
positive control.

One finite worker ran at a time, with a 1.9-second per-trial process deadline.
The longest finite trial took 0.4964 seconds. An external supervisor covered
input copying, solving, validation and checkpoints with a 240-second ceiling;
the complete experiment exited normally after **19.49 seconds**.

All source modules, input snapshots, structured command tokens and elapsed-time
receipt hashes are retained under `artifacts/fq-capacity-probe-v1/`:

- `manifest.json` pins the sources and exact executed command.
- `report.json` records every setting, candidate count, core size and finite
  solver result. SHA256:
  `2890c11ec2841119fb8c82c64cae631c58bc1a132674c2ace594d51ad0dc243f`.
- `completion-proof.json` binds the manifest, report, supervisor receipt and
  positive-control certificate.
- `near-success-diagnostics.json` records each type's best capacity and all
  settings reaching it. Every type remains one square short of extra capacity.
- `increased_surplus.npz` is intentionally empty; no unvalidated layout was
  promoted.

Four targeted regressions passed, covering transpose identities, threshold
classification, forced finite-worker termination and overlap rejection. Two
independent code reviews found no implementation blocker. The optional
`upright_threshold` argument added to the shared helper preserves its existing
default behavior.

This is a negative finite-search result, not a proof of continuous capacity
optimality. It gives no reason to spend a larger budget repeating the same
fixed cores and candidate construction. Core movement, different layouts or a
new contact-generation method could change the result. No GPU job or
competition submission was launched.
