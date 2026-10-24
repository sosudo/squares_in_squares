# Complete current-puzzle FTMC pilot

This experiment complements active-chain gadget optimization. Each seed is a
complete current packing, with `w=h=floor(sqrt(n))` and `d=n-w*h`. An improved
fractional side directly improves its original puzzle, without needing a
compatible separator profile or a new multigadget composition. Adding ordinary
L-frames can propagate the same surplus count to larger puzzles.

The first prepared pilot uses the accepted baseline CSV with SHA-256
`97df15c28ee66ab1a414d28218fd4e8b28c2bf6ce8869281db9610f7dac81da9`.
Its 24 target counts are 83, 84, 86, 87, 88, 106, 107, 128, 129, 152, 171, 172,
179, 180, 198, 205, 227, 235, 259, 266, 292, 300, 301 and 302. Their mean full
size is 180.7 squares and their mean tilted-core size is 35 squares.

`experiments/full_puzzle_bank.py` excludes perfect squares, unsupported core
sizes, uniform-angle cores and repeated translated/reflected/transposed copies
of smaller tilted cores. This prevents a short pilot from repeatedly searching
the same exact Göbel motif in successively larger upright frames. The sampler
balances five size intervals and ranks candidates by hypothetical 0.01 side
reduction, its possible L-frame propagation, and a rough size cost. These values
are scheduling estimates, not achieved gains or measured GPU throughput. Small
long-studied records below n=80 are excluded from this exploratory arm.

The private job is prepared with:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/build_full_puzzle_ftmc_job.py
```

`artifacts/full-puzzle-ftmc-job` contains a 246,133-byte script, metadata,
target ranking and seed-validation report. It uses one T4, 64 replicas and 600
seconds of nominal worker search. The supervisor gives a finishing batch 60
seconds of grace and checks it on its normal polling interval; its overall
parent alarm is 960 seconds, followed by child cleanup if necessary. The search
budget is about 0.167 device-hours. Kaggle may attach a second unused T4, and
actual platform quota must be inspected separately. Full-puzzle quenches are
larger than the original narrow-gadget pilot, so throughput must be measured
before extending this arm.

The job is internet-disabled and has no `kernel_sources` or input attachments.
All exact selected search inputs are embedded and hashed. The builder first
checks the complete baseline's official report, retains the original per-puzzle
hashes and report digest, normalizes the selected float poses, and evaluates
each normalized seed with the unchanged official metric both directly and
after a pandas numeric roundtrip. All 24 passed. No external baseline mount is
needed merely to audit source identity. This avoids the unproven private
versioned attachment mechanism that failed in the first active-chain pilot.

All 31 embedded payload hashes and the unchanged public source manifest were
checked locally. Two tests verify that core deduplication recognizes D4,
translation, row order and upright extension, but distinguishes changed tilted
geometry. The frozen supervisor copy receives only a local full-puzzle seed
loader and direct-candidate export branch; public solver and official metric
files are unchanged. Generated script SHA-256:
`848968c2988122d2eef646960d11ef629c39803eaa743d680745b7e6794d99eb`.

Saved worker variants undergo official raw/roundtrip admission and final
revalidation. `full_puzzle_candidates.json` exposes the strongest direct result
for each improved n in the ordinary merge format; all certified variants remain
in the campaign NPZ for broader composition. A full merged CSV must still pass
the ordinary independent, official and transport checks before submission.

At preparation time no GPU run or competition submission had been made by the
packaging agent. Read the job's actual status and outputs before claiming gains.
