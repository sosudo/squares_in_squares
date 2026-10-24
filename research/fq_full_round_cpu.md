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
