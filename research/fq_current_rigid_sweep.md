# Finite current-geometry rigid continuation

This follow-up is prepared against RAW `artifacts/merged-fq-broad-final-v2.csv`,
SHA256 `3855c47798708e4bfb9f053024e6542b0a2a5021824bfd310290e4e7ab1ff9ea`,
official RAW score 22.299034777429622. The pointer was read once, its CSV and
official-report hashes were checked, and the pointer stayed unchanged during
preparation. The official metric file and report both match the pinned v17 SHA.

The public factual target table identifies 311 material positive-gap cases.
Recent native lineage separates 223 current poses without a matching recent
rigid input/result, 35 materially changed winner poses, and seven poses with a
previous rigid attempt but no completed native return. Sixteen current poses
match completed rigid results and another 27 match completed rigid inputs; all
43 are excluded. Cases 147, 299 and 335 are excluded by the repeated-family
policy. These are source-eligibility categories within the pinned recent
archives, not claims that older native experiments never tested a case.

The finite 180-source queue contains 138 recent-source eligible cases, all 35
changed winners and all seven no-return attempts. It interleaves two fresh
sources, a changed winner and a no-return attempt, ordered by factual headroom
within each group. The first cases are 496, 541, 638, 861, 629, 915, 979, 752,
994, 372, 594 and 600. Every selected row explicitly marks older legacy history
as uncertain outside the pinned recent archives.

Equivalence requires the same ordered square count, a D4 transform, folded
angle residual at most 2e-12 radians, and one common center scale within 3e-8
of one with center residual at most 5e-10. This conservatively groups tiny
clearance changes; it does not identify arbitrary square permutations or
optimization basins. The comparison checks completed native result geometry
as well as parent geometry, including raw returned states whose earlier gate
timed out. Both recent rigid result archives have no valid-count `.out` files
missing their raw-returned checkpoints.

Frozen inputs are in `artifacts/current-rigid-sweep-inputs-v2/`:

- `freeze.json` SHA256
  `2e1f62eadc327ae79e109b140aa5d9f64b7d13afb79aa96d6875734c0c701d32`.
- `audit.json` SHA256
  `468645433f9ef9fdd5d80b2a22ec3402c31a2571c0d8fe3e442cfec0ca8a42f3`.
- `inputs/current-poses.npz` contains the exact parsed current RAW arrays;
  per-case geometry hashes bind every queue entry.

`artifacts/current-rigid-sweep-queue-review-v1.json` checks the actual frozen
queue is unique, uses the requested RAW, excludes repeated families and every
completed equivalent rigid input/result, and contains the explicit uncertainty
labels. Preparation ran no native optimizer or new geometry certificate.

The authorized run is at most three local CPU workers and 720 seconds whole
time, rigid-only, without LP100 or repeats of unchanged returned geometry.
Native and certificate budgets are separate. Exact parent/input/output/log
bytes and a parsed raw checkpoint must be published before a certificate is
attempted, so a slow gate cannot erase a completed native return. All strict
certified poses are retained, with immutable cumulative-gain snapshots.
Finite queue coverage can end at the deadline and must be reported as partial.

The frozen worker is `experiments/fq_current_rigid_campaign.py`, SHA256
`05c07430d935b6d005ec1d0dde7a383aa32aa6e22745dcfc3dc765f5440d75eb`.
Four mocked fault controls pass in `tests/test_fq_current_rigid_campaign.py`:
the certificate alarm escapes a metric's ordinary `except Exception`, native
bytes survive a gate error, a valid worse pose is retained even after a native
timeout, and malformed output counts never reach certification. The timeout
uses a separate `BaseException` so official metric error handling cannot
swallow it. Unique certified pose/proof files are made read-only.

The authorized run started in exec session 97213, output directory
`artifacts/fq-current-rigid-v1`, log `/tmp/fq-current-rigid-v1.log`. Native trials
have a ten-second timeout; decoding and all full gates have a separate
six-second alarm. Scheduling ends at 706 seconds, with a process-group kill at
717 seconds and a 720-second maximum whole allocation. The source is frozen;
the independent review is `artifacts/fq-current-rigid-independent-review-v1.json`.
The run completed normally in 437.14 seconds (438.15 including supervisor),
with all 180 frozen sources attempted exactly once and no forced kill. All
three worker slots were released. There were 133 native returns and 47 native
timeouts without output. Of the returns, 132 distinct poses passed every full
gate; n969 encountered a gate TypeError, with its exact output, raw array and
decoded array preserved. Its decoded bounding-box side is slightly worse than
the baseline, so it offers no apparent missed score gain.

There are 31 certified improvements, with aggregate per-case score gain
0.00022970116476831576 against the frozen RAW. This is a candidate-set delta;
the root merger independently checks the complete current portfolio and SAFE
transport. Fresh recent-source eligible poses contributed 21 wins and
0.00021196860188605398; changed-winner followups contributed ten wins and
0.000017732562882261826. The seven prior no-return retries produced one valid
return and no gain. The largest case contributions are n808 (0.0000431864),
n504 (0.0000249127), n690 (0.0000193102), n598 (0.0000151447) and n703
(0.0000148851). Summed native process time was 1115.52 seconds; separate
certificate time was 168.14 seconds across the three workers.

Final immutable outputs are under `artifacts/fq-current-rigid-v1/complete/`:

- `candidates.json` SHA256
  `09262fb799c16b722d52413536329bbeef15243f31de0a806da5ae06959b6372`.
- `donors.npz` SHA256
  `f9beeafb51f0f44c87037fe27df35a32ad5c6f5ae08767fc6fd8cc86cc313a9a`.
- `results.json` SHA256
  `2db0a56e75aa7e213daadbd963a1fba6fe01c717d5b1cc64aa315dba3f522e9d`.
- `manifest.json` SHA256
  `fbce3c114ce0f5702531393283a005bb38ae2bb703e0edf99f96a2561976dde7`.

`completion-review.json` independently rechecks every retained archive hash,
per-array geometry hash, square count, full-certificate validity and read-only
pose/proof pair: all 132 match. Worker/helper source hashes stayed unchanged.
Eighty-five lower-ranked recent-source eligible cases remain outside this
finite queue; neither their native behavior nor global optimality is claimed.
