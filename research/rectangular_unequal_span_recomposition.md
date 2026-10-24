# Unequal spans and corner profiles of the four rectangular families

The 16 frozen inputs do not contain a material improvement hidden by the
common-excess representation. Fifteen have horizontal and vertical excesses
within `2.61e-8`. The remaining `8_21_13__seed3` has excesses
`0.8850353341169815` and `0.8852059125746884`; both exceed the best frozen
family excess `0.8829035603506779`. The subsequent original-reference
control improves that family's conservative common excess by another
`4.63e-8`, which strengthens this conclusion. No composition or optimization
was run for this assessment.

| Frozen family | Seed-0 x excess upper | Seed-0 y excess upper | Distinct full reflection multisets / lex-min summaries |
| --- | ---: | ---: | ---: |
| 5×17+7 | 0.8024287265379310 | 0.8024287505378756 | 3 / 3 |
| 7×19+13 | 0.9180306750561245 | 0.9180306990557883 | 1 / 1 |
| 7×20+14 | 0.9253502383857631 | 0.9253502643937171 | 1 / 1 |
| 8×21+13 | 0.8829035342895682 | 0.8829035603506779 | 3 / 2 |

These are interval upper bounds already recorded in input-v2's proof, not
new geometry certificates. The first profile count sorts the complete
multiset of four D2 reflection records, each containing all nine stored
angle-pair profiles. Frontier's earlier diagnostic instead keeps only the
lexicographically smallest reflection, giving the second count. In 8×21,
seeds 2 and 3 share that minimum record but differ in another reflection.
This is a signature-definition difference, with no recomputation or
floating bin-boundary change. Neither summary proves geometric equivalence
or a new compatible join. Continuous support values differ for all four seeds in each
family, but floating-point distinctness alone does not prove that a join's
compatibility changes.

## What the existing construction can exploit

`gpu_fault_composition.stitch` places the donors at integer staircase
anchors, then shifts the upper upright-grid region by the same global
`f` in both coordinates. The square enclosure uses `k+f`, with
`f=max_i(max(fx_i,fy_i))`. Merely replacing this with separate global
`Fx=max_i(fx_i)` and `Fy=max_i(fy_i)` leaves the square bound unchanged:
`max(Fx,Fy)=max_i(max(fx_i,fy_i))`. Transposition does not change that
identity. Using genuinely unequal spans would require a different filler
layout or local phases that avoid the common outer bound, or new donor
geometry; storing two numbers instead of one is insufficient.

Corner geometry remains useful. The existing exact-SAT stitch and pair
composer can admit a different unbuffered join even when the donor's
scalar excess is unchanged or worse. They already support these profiles,
both orders and reflected/oriented poses at their declared integer
offsets. The prepared handoff covers 17 historical chains and a 502-partner
pair bank, but that propagation screen has not yet executed. Its baseline
is current RAW `9d18b33ca0efb4c55c0afac2c159f413676d76aae37fb3cbcc6ec93a43975396`.

## Existing coverage beyond integer offsets

The earlier fractional-interface experiment already allowed independent
horizontal/vertical upper-grid phases and both donors' x/y translations,
with fixed angles and every square retained. In 562.82 seconds it inspected
19,995 bounded phase domains: 19,509 failed a necessary pairwise bound and
486 had infeasible MILP models. It visited 96 of 203 ranked type jobs, with
the last partial. In particular, its complete finite n498/n814 pose sets
failed; their least-overlapping interfaces still had penetrations about
0.713/0.884. This is negative coverage of those frozen poses and translation
domains, not a global impossibility result. Repeating the same phase-only
extension would not be a new method.

## Concrete next step

Use the already prepared exact-SAT replay and pair pass on the new fully
certified GPU/native donors first, retaining scalar-worse geometries. A
reported whole-case gain should be checked by substituting the old donor
into the same newly discovered recipe, so a change in search coverage is
not misattributed to the new geometry. Preserve both span bounds and all
corner profiles in the donor archive even though the current DP uses a
scalar excess.

Only reopen fractional or anisotropic placement when a new exact geometry
changes a previously blocking interface, or when a proposed filler layout
has a demonstrably smaller bound. The current 16 inputs alone do not
justify another such search. No portfolio gain, fresh feasibility check,
or general impossibility is claimed here.

## Evidence

- `artifacts/rectangular-unequal-span-assessment-v1.json`, SHA256
  `76f3b99265735597d409d6a3679e4a5bd94ca1b839b4f9f025e838f8deb982f6`:
  exact span/profile calculations and source/input hashes; 0.0054-second
  read-only calculation.
- `artifacts/rectangular-persistent-recomposition-handoff-v1.json`, SHA256
  `a3925f3f92aa560ce0a8041a0fdec4575270d4acfdde52bb136f3b5f51c7f2bb`:
  unexecuted finite replay/pair scope and current baseline.
- `artifacts/rectangular-reference-independent-review-v1/review.json`,
  SHA256 `93440ff53cd0bf4443695343fa9cfc4f886beedd1042b308b67d1800806cc08c`:
  all four exact native reference controls and both-span certificates.
- `artifacts/rectangular-unequal-span-profile-method-v1.py` and its adjacent
  JSON report: reproducible comparison of the two profile summaries;
  source SHA256 `f139b479039a9c094c8ffafe1982203ab46cbae812463356a0d0a40d76910736`.
- `research/fractional_interface_search.md`: prior bounded phase-search
  scope, controls and negative results.
