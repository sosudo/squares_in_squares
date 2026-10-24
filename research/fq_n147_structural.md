# Finite n148 deletion and diamond reconstruction for n147

This experiment completed every planned structural trial and found no
portfolio improvement. It retained all325 strictly certified147-square
geometries for possible future composition, including dominated alternatives.
No submission or remote job was launched.

The frozen reference is raw portfolio SHA256
`381ffdc98df53c4ba9838fdc556eeead2f62681e427039e1c25224df873e9f4c`.
Its n147 side is12.656854249504036. The dated public table gives
12.651043553627, a conditional aggregate-score opportunity of approximately
0.000479258. That public value was a target, not an achieved result.

## Structure and finite schedule

The n148 incumbent comprises a centered8×8 lattice of64 squares at45° plus
four21-square upright corner triangles. The n147 incumbent retains the same
64-square diamond, shifts it by(−0.5,−0.5), and uses83 upright squares. Both
currently have the same bounding side. Deleting any square from n148 therefore
creates a feasible147-square topology at no initial side cost.

The pilot first passed a native30-step contact-polish control on the actual
n147 reference. It then tested all148 individual n148 deletions with the same
contact relaxation. No deletion class was skipped by symmetry assumptions.

For the next phase, deleted-square positions were grouped into22 D4 positional
classes:10 diamond classes and12 upright-frame classes. These classes were
only a scheduling heuristic; coordinate similarity was not used as an exact
geometry or certificate identity. One representative per class was chosen
from the completed contact pass. Both signs of four deterministic
reconstructions were then tested:

- Rotate the nearest diamond row by0.06 radians around the vacancy.
- Rotate the complete diamond by0.025 radians about its center.
- Translate the nearest eight diamond squares by0.12 units toward or away
  from the vacancy, creating a controlled dislocation.
- Rotate the nearest two diamond rows by0.06 radians around the vacancy.

These176 exploration starts could overlap. Native augmented-Lagrangian repair
used45 outer iterations and70 contact-polish iterations with no random kick or
flip. Every retained final geometry independently passed the official raw
gate, ordinary default-pandas transport gate, and independent interval checks.
All final squares are unit squares; no soft-aspect deformation was used.

## Result and retained evidence

The complete one-worker run finished in213.484 seconds with exit0, no forced
termination, no timed-out stages, and no invalid final geometries. The325
stages comprise one baseline control,148 deletion trials, and44 trials for
each coherent reconstruction mode.

The best certified side is12.656854272806104, about2.33e-8 above the reference
because of the output clearance margin. The achieved full-score gain is zero.
The finite schedule does not establish global optimality for n147 or rule out
other deletion/reconstruction methods.

All325 exact geometries fit a12×12+3 donor box with excess below1. Their
contact graphs were also compared against their unmutated deletion seeds at
a1e-6 diagnostic threshold. The324 non-control outputs change some measured
contacts, with at most88 changed edges. This supports retaining geometrically
different alternatives, but is neither a strict graph-identity proof nor a
prediction of useful composition gains.

Frozen evidence is in `artifacts/fq-n147-structural-v1`:

- Manifest SHA256:
  `4cea4c82a0bfd6af2e11856c91ca4d9b9f1fe5be665748c2e30e1672a9fda17f`.
- Complete donor archive SHA256:
  `d5567130cba94b0698c9ff0899e94ebb3c1337e09de205f782e2152e3cdc3b8d`.
- `final/composition-eligible.npz` SHA256:
  `8f53d0076dfc98fc02d975a006536e3b6e32a7feea3505d75aea94d4cf18c2d9`.
- `final/proofs.json` SHA256:
  `b427a8565b03ea9ccb35eafcce2ed7e5b7880baffd2d2f30ad92cd245a59c2ea`.

Finalization reused325 already completed certificates only after checking exact
geometry hashes and their record bindings; it ran zero fresh certificates.
All snapshotted source hashes remained unchanged. The native MIT-licensed
FQ binary is pinned by SHA256 and source commit in the manifest. The current
portfolio and all earlier input archives remain unchanged.

## Small material-diversity handoff

`diversity-handoff/donors.npz` contains 12 selected alternatives, SHA256
`9c802152965b352567be7c2570f5862ef67de81758de5e736f0785d75bb60b1a`.
Its full certificate and source bindings are in `diversity-handoff/proofs.json`,
SHA256 `6c498ef7e32217f998f884f9ac342e15a20b349f69a1b81cce158b0fb8ff48ea`.

Each selected pose has one to three squares with angles materially different
from upright or 45°. The largest such angular departure ranges from 0.737° to
8.380° across the 12 poses. Every selected pair must differ by more than
0.0025 radians in its sorted angle spectrum or by more than 0.01 in its center
sets after every D4 alignment and wall normalization. This avoids selecting
variants merely because their floating-point hashes differ.

All 12 near-contact graphs also have different degree histograms at the stated
1e-6 diagnostic tolerance. These are useful distinct starts for future search;
they remain slightly worse than the actual incumbent and establish no score
gain. The original reference and the centered n148 seed are retained in
`inputs/reference.npz`, SHA256
`509597916ab22cc7b984fa6fa4db5a43ea8f9e3bcfc0d84bf5de779c22b83d17`.
