# Full-puzzle held-box CPU continuation

The two local controls established that complete-puzzle rounded continuation can
return valid, changed unit-square packings for 147, 299 and 335. The actual-held
control took 18.35 seconds in total. It used initial jitter 0.04 as well as holding
the input box, so it is not an isolated comparison of the hold setting. Its three
outputs remain close to the current side. The earlier compressed n335 output is
0.00627 wider but changes the tilted strip substantially; it remains an explicit
alternative start.

`scripts/build_fq_full_round_cpu_job.py` freezes exactly seven already-certified
inputs: three original current packings, three actual-held outputs, and the
compressed n335 output. It binds their exact binary64 arrays to the existing
official raw/default-pandas and independent interval certificates and raw decimal
CSV hashes. Geometry certification is not repeated for unchanged inputs.

The private offline CPU notebook uses the previously verified native FQ binary
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.
The portable attachment and its source/license manifest are checked by content
hash; the notebook version suffix alone is not treated as a pin. Evan Daniel's
MIT source at commit `659ee62e4a9d39542a1146e8b011cc3ab6407ede` and its notices
remain embedded with the runtime and exact input provenance.

Four workers share a 1200-second search ceiling, with a 1500-second whole-process
supervisor and an explicit 1800-second Kaggle server timeout. Individual complete
trials, including admission, are bounded to 20/45/60 seconds for 147/299/335.
Owned native descendants are stopped at the supervisor deadline. CPU allowance
and remaining concurrency are not exposed by the supported accelerator quota
endpoint; this is one intentionally bounded four-core job, using no GPU.

Case weights are 1:1:2. Per-case visits independently schedule 50% current-best,
25% immutable controlled alternatives and 25% exact original-current starts.
Every starting source cycles through all four settings: radii 0.1/0.15/0.3, with
initial jitters 0.02/0.04/0.08. The selected parent's box is held with `--hold-f 1`
and no `--round-compress`; twelve quadratic radius steps must return exactly to
zero before rigid ALM45/polish100/flip16 and the unchanged full admission gates.
Native reported held side must equal the encoded parent's side.

All exact certified stage outputs are retained before the continuing-search
band is applied. The wider compressed n335 input bypasses the older initial
0.005 cutoff, and initial inputs use exact geometry identities rather than coarse
diversity buckets. All raw native outputs, partial logs and return traces remain
in private notebook outputs. These are alternate search basins, not claims of a
better competition score.

The independent pure scheduler tests cover 128 weighted starts, exact role
fractions, every source/settings combination, immutable arrays, and the actual
adapted loader retaining all seven inputs. The frozen notebook is under 1 MB;
the final source/config review is saved beside its build report before launch.

The remote campaign stopped normally after 1194.554 seconds with four workers:
323 trials, 319 fully certified outputs, and four timeouts at the shared search
deadline. Counts for 147/299/335 were 81/81/161; the four settings received
81/81/81/80 starts. Every original, controlled alternative and incumbent role
reached all four settings. All 323 actual native input hashes reproduce from
their recorded parent geometries. The exact certified side minima are
12.6568542728061082, 17.8228756891781944 and 18.8228756911780941, respectively,
all slightly wider than current RAW. There is no candidate to merge.

Recovery is closed with an explicit native-trace limitation. Two supported
whole-output ZIP requests ended prematurely near 75 MiB; the retry used a
180-second read timeout and failed after 186.77 seconds with
`ChunkedEncodingError`, not a client read timeout. The small private copying job
failed before Python at the parent dataset mount. CRC-checked complete ZIP
members preserve all 319 immutable geometry/certificate pairs and final
termination/exposure records. Their exact binary64 and raw decimal bindings all
pass. All 282 complete native trace sets also pass held-box, radius-zero and
exact native-output decoding checks. The remaining 184 native-return files for
37 certified stages were not downloaded; two failed-trial input files are also
listed separately, although all parent input hashes reproduce exactly.
`artifacts/fq-full-round-cpu-results-v1/bounded_completion_audit.json` records
the precise scope and missing list. No geometry certificates were repeated, and
no more recovery requests are planned for this zero-gain campaign.

Two distinct local pilots are complete and frozen:

- `fq_full_round_aggressive_control.py` ran four terminal trials on one CPU in
  47.405 seconds. Requested radii 0.49/0.4 with 12 quadratic steps first actually
  relax at 0.4117/0.3361, respectively; the initial nominal radius is set but not
  optimized before the loop. All four reached exact zero radius and passed full
  raw/default-pandas/interval gates. The 0.49/jitter0.30 settings widened n335 to
  19.05589 and 19.09196, and n299 to 18.00000. The moderate n299 setting,
  radius0.4/jitter0.15, produced side17.823755583067829, still 0.00087993 worse
  than the incumbent. It is a useful changed starting shape: D4/unlabeled RMS
  0.08180, 31 angle changes above one degree and 894 changed contacts at 1e-5.
  Its exact archive and certificate were handed to the separate ALM work.
- `fq_full_round_linear_control.py` then ran one test on that new n299 shape in
  3.400 seconds. Radius0.49 with 24 linear steps first relaxes at 0.4696 and ends
  at zero, with jitter0.04 and the selected parent's own side17.82375558 held.
  This is not the tighter incumbent box. The fully certified result has side
  17.823755761433566, 1.78e-7 worse than its source, with D4 identity matching,
  RMS0.00818, 23 angle changes above one degree and 22 changed contacts at1e-5.
  It preserves the altered basin but supplies no side reduction.

These pilots do not justify an unchanged extension. All raw native traces and
certified outputs remain in `artifacts/fq-full-round-aggressive-control-v1` and
`artifacts/fq-full-round-linear-control-v1`; the executed source copies and whole
process receipts are adjacent. No competition submission or incumbent update was
made from either pilot.
