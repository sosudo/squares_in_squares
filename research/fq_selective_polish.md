# Six fresh-current contact-polish tails

This finite no-ALM followup starts from the exact current RAW poses for n761,
n920, n997, n868, n981 and n995. The source RAW is
`merged-fq-timeout-all-v1.csv`, SHA256
`add7c0ee1599b97bb229f279dd0ee927c502ad6710940faccd92dca7c7658a53`,
official score 22.298021385039238; SAFE is 680e332bc6bc. The pointer was read
once and all RAW/SAFE/default-pandas CSVs, complete official reports, metric
file and canonical transport proof were hash-verified. No new certificate or
optimizer was run during input preparation.

The new wrapper reuses the unchanged certified worker 05c07430 through an
explicit process-local initializer: `--no-alm --loosen 1 --pit 80 --flip-top 0
--v`, native limit forty seconds, separate certificate limit eight seconds,
and observational FQ_TR/FQ_LPT logging. It uses two workers, a 166-second
scheduling deadline, 177-second process-group kill and 180-second whole limit.
The original native source, metric and completed campaign sources stay intact.

`tests/test_fq_selective_polish_campaign.py` passes an actual fork/initializer
control with a mocked native executable: child flags/caps/environment reach
the live unchanged worker, while the parent module settings remain unchanged.
No optimizer executes in that control. Input freeze SHA256 is
`9bc56d50ad65621ad40f3671b06c9fff1994d39871e2a52231cbea32bb2b0b92`;
wrapper source SHA256 is
`13f94307e32befdc8ced68b4494985b0b71e74604f7a1bebe94e12fb5b449204`.

All six sources were attempted. The run exited normally after 119.12 seconds,
with three full-certified improvements and three forty-second native timeouts
without coordinates. Both worker slots were released. Combined candidate
score gain against the frozen RAW is 0.000012992455971551214. Valid outputs
and exact input/output/log/raw/decoded/certificate ancestry are retained.

Stopping evidence is deliberately finite:

- n761 returned after exactly 80 SLP iterations (iteration limit), 39.13
  native seconds. Final predicted decrease was positive, 5.79e-6.
- n920 returned after 65 iterations, 34.23 seconds; n868 after 30 iterations,
  11.42 seconds. Their stopping reasons are not explicitly reported. No stall
  message appeared and trust radii exceeded the floor, consistent with the
  pinned source's rolling-stagnation guard. Neither is a convergence proof.
- n997, n981 and n995 timed out at forty seconds. Their last trace iterations
  were 57, 65 and 49. Printed trace sides are not coordinate witnesses and are
  excluded from all admitted gains.

Final immutable files under `artifacts/fq-selective-polish-v1/complete/`:

- `candidates.json` SHA256
  `011f8b798a76017472ff6d7fa7bc77fe35a4c3e4bd92876580ad8efbc1e0ff0a`.
- `donors.npz` SHA256
  `583c02f576a2384796152ea0e546f31edfa1f8bb8d593308816749a06a47ef68`.
- `results.json` SHA256
  `8126da637c5bba8b638c015545909df00ba30af7990937a3dbf00307bdf49960`.
- `manifest.json` SHA256
  `9461f1fb7967c7f2cb9c9cb19936d649314c15af1b386565c82723e1246953c8`.

`completion-review.json` binds the stopping logs and three retained geometry,
archive and full-certificate records. Root independently merges and validates
the complete latest portfolio. No automatic continuation was run.
