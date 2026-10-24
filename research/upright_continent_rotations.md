# Whole-upright-continent rotations for n335

Four distinct coherent starts produced four fully certified finals, but none
improved the canonical side. The one-CPU campaign finished in 39.84 seconds
under a 75-second outer bound; each native/validation stage took 9.21–9.57 seconds
within its 15-second inclusive cap. No portfolio changed and no submission ran.

The input is the exact current RAW 335 case from `merged-public-v29.csv`,
SHA256 `a0dad731adc6cacc9c882082aaf9464c7c7fc755ce4eabba6f711b1c31b969bc`,
with official side 18.8228756555792035. The selected ribbon has 44 tilted units.
Its principal-axis normal partitions the 291 near-upright units into 137
upper-left and 154 lower-right units. Classification uses the same 0.018-radian
quarter-turn threshold as the earlier GPU move module.

This starting mechanism was absent from the inspected earlier work:
`full_structural_gpu_moves.py` explicitly preserves every upright unit during
its bend/hinge/column moves. The separate rigid-interface screen concerned
n498/814 donor blocks. Here entire upright continents rotate about their own
centroids, with every selected square center and angle rotated together.
Within-continent pair distances, inverse rotations, and relative angles were
checked numerically; all unselected rows remained byte-identical.

| Start | Selected units | Initial physical energy at canonical side | Certified final side |
| --- | ---: | ---: | ---: |
| Opposite +0.1°/−0.1° |137/154|0.00615811|18.822875735307279|
| Opposite −0.1°/+0.1° |137/154|0.00635459|18.822875720265494|
| Same +0.5°/+0.5°, interior |105/120|0.12071214|18.822875700312215|
| Opposite +0.5°/−0.5°, interior |105/120|0.12976892|18.822875721554689|

Interior trials freeze 66 units whose nearest original wall gap is below 0.05.
All 44 tilted units remain unchanged in every initializer. These starts are
deliberately overlapping; only the internal rigid geometry is preserved.
The unchanged native FQ core then frees all 335 units, using `--loosen 1`,
ALM 45, polish 100 and flip-top 16, without an extra random kick. The established
encoder translates the input and uses its actual bounding span. The exact
portable binary SHA256 is
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.

Each final passed independent interval validation and official raw/ordinary
pandas gates. The best result remains 4.47e-8 wider than the canonical case.
The median imposed continental rotations disappeared: every continent's
terminal median angular difference from its original is below 7e-12 degrees.
A few original boundary-square tilts change by up to 0.463 degrees, and 21–41
labelled near-contact edges differ at a 1e-4 gap threshold. Those local changes
do not establish a new unlabeled topology or a side improvement.

All raw starts, exact selected IDs/pivots/angles, native inputs/outputs/logs,
certificates and four immutable donor poses are retained under
`artifacts/fq-upright-continents-v1`. Script SHA256 is
`2a9e7b82348e31f67141e9df0a3393ab77aa5e274e34ef69afdd46bf59663a1d`;
completion proof SHA256 is
`6655f96c1029c10ebb28f0473f6b321678b19527b5508ed90b1a0f8cc1f3a750`.
The finite negative result does not exclude larger rotations, other partitions,
or constrained continuation that prevents immediate angular relaxation.
