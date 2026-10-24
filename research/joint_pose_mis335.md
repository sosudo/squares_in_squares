# Joint finite pose selection for n335

This is a distinct source pool from the earlier n299 experiment. It combines exact unit poses from current n335, a true-held rounded n335 basin and a compressed rounded n335 basin at diagonal wall phases 0, .5 and 1; current n336 and n337 each contribute phase .5. Four upright wall grids complete the pool. Before clipping and exact-byte deduplication there are at most `3*3*335 + 336 + 337 + 4*18² = 4984` candidates. Tilt count is unrestricted.

All five exact source arrays were freshly certified by independent interval, official raw-decimal and ordinary-pandas gates. Original source archive/record pins and native options remain in `artifacts/joint-mis335-inputs-v1/source-spec.json`, SHA256 `5ecce48c89338ae765841f5204b8e062c3a00ce4f7fab305c82373a5c3d523fc`. Its source NPZ SHA256 is `770609e58aa6c19f1431fda8dbe912b3fce0303941582f81695b404f3ff039f3`.

| Side reduction | Nodes | Conflict edges | Verified clique-cover upper | Best certified count | MILP reported upper | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 3,937 | 83,639 | 446 | 335 | 335 | Optimal, zero gap |
| .005 | 4,457 | 111,665 | 442 | 325 | 326 | 70-second timeout; optimum not established |
| .020 | 4,451 | 112,099 | 418 | 325 | 325 | Optimal, zero gap |

The .005 MILP's own incumbent was only 223; the independently checked source-seeded greedy witness has 325. Its displayed MILP gap .46188 refers to that weaker solver incumbent. Combining the separate valid greedy witness with the reported upper leaves a cardinality interval [325,326], not a 46% uncertainty about the best known count. The .005 finite optimum remains unknown. Both smaller-box reported bounds are below the required 335, so this finite pose union cannot supply the desired full count under those bounds. This says nothing about continuously translating or rotating the unit squares beyond the sampled phases.

Screening took **10.62 seconds**, with an actual original335 graph-independent witness and full gate control passing. Every graph had **zero unresolved tight edges**. The one-worker solve took **125.08 seconds** and retained six freshly certified actual-count layouts. Input preparation, screening and solving had separately reserved bounds totaling below 300 seconds. No full335 gain, GPU job or competition submission resulted. Evidence is under `artifacts/joint-mis335-screen-v1` and `artifacts/joint-mis335-solve-v1`; solve manifest SHA256 `b89a5d70ec94f2d346f6849d0b8e694cf40748a08bb6c14bdcbd302446b26b98`, donor NPZ `166b222b6a0eb384dafd214a03e88e9e47a5682525a23f7425bd30720338a012`, results `5f7cff0f6c52b72c952003066fdcbd0cb98ff55cec8b3b9c0da640eb5fb925dc`.

## Preserved one-tilt-removal start

The original-box MILP gives a valid n335 layout with **43 tilted squares**, compared with the incumbent's 44, at side **18.822875691224954**. Its side cost versus the current335 source is `3.5645751e-8`, due to bounded numerical clearance. Independent attribution finds exactly **258 current335 squares plus 77 fresh wall-grid uprights**. It removes tilted source square **317** plus 76 other original uprights; all remaining 43 tilted squares are original335 units. No actual held, compressed, n336 or n337 pose was selected in this layout. Thus this is one tilted-square removal with filler rearrangement, not evidence that the rounded basins combined successfully.

The original44-tilt witness and new43-tilt layout are both frozen in `artifacts/joint-mis335-full-starts-v1/starts.npz`, SHA256 `1a3bffda9a6617b3a32a79d6f32e809dd59308e23cbcbfb5d0f214b96995f832`. `proof.json` binds the exact arrays, certificates, solver results and all source graph hashes; `source-mixture.json` maps each row to its exact graph vertex/source square/translation. Attribution evidence SHA256 is `89ef3cf5e1d3cdf06886d148c40f51bdd6264e7b08c4fc2554fc8ea848f91255`. The handoff and explicit attribution caveat were sent to frontier for distinct future smooth-ALM starts.

The reusable graph/solver now accept an explicit frozen source specification, per-source phases and target count inferred from the pinned screen manifest. Legacy299 sources and depth defaults remain unchanged. The complete ten graph/MIS tests pass, including a generic-count phase test and a regression preserving the original299 phase defaults. Independent review found no geometry/count/phase blocker and prompted an additional exact screen-manifest hash check before solving.
