# Same-parent native timeout comparison

This finite follow-up extends native runtime from ten to thirty seconds on
sixteen exact unchanged parents whose previous rigid trial timed out without
an output file. It does not repeat successful rigid results. Case 858 is
explicitly excluded. Cases 802 and 928 are excluded because their current
coordinate arrays changed in the intervening public refresh.

The frozen baseline is RAW `merged-fq-rigid180-kmmm31-v1.csv`, SHA256
`fc931068f0f4accb37c8ed8b33ea59607e4690440d7c3f98b4b79fbb8c34cffc`,
official score 22.298804979575742. The pointer was read once and checked against
the exact CSV, official report and pinned v17 metric. All selected arrays are
byte-equal to their previous `.parent.npz` poses, with matching geometry hashes
and matching re-encoded native input SHA256 values. Original seeds and numeric
flags remain fixed. Only the timeout and observational `--v`, `FQ_TR=1`,
`FQ_LPT=1` logging change.

The highest-headroom sixteen eligible cases are 745, 696, 996, 799, 911, 905,
966, 980, 919, 860, 920, 914, 977, 968, 973 and 865. There were 44 unchanged
eligible sources after the three explicit/changed-parent exclusions. The dated
public target table ranks scalar headroom; it does not establish an attainable
native solution. No other timeout sources are part of this run.

Inputs are immutable under `artifacts/fq-timeout-extension-inputs-v1/`;
`freeze.json` SHA256 is
`bd7695b1de6bfd3e687b80ca2ef772d3e048cc4a9c1da3421b30feda81f1ad10`.
The separate worker `experiments/fq_timeout_extension_campaign.py` has SHA256
`d442e136a93f8cdafe6ce451a03c1b09870c14be48b58b4ce432a9f580f8bb78`.
The completed 180-case worker and its outputs remain unchanged.

Four adapted mocked fault controls pass: exact original seed/input identity,
observational environment and thirty-second cap; unswallowable separate gate
deadline; output/log/raw preservation before a gate error; valid worse-pose
retention; and malformed count rejection. These controls execute no optimizer.

The authorized run uses three workers and at most 240 seconds whole time:
native timeout thirty seconds, separate gate alarm six seconds, scheduling
deadline 226 seconds and process-group kill at 237 seconds. Exact native
output, logs, parent and parsed raw arrays are published before gates. Outputs
are under `artifacts/fq-timeout-extension-v1`, with exec session 38987 and log
`/tmp/fq-timeout-extension-v1.log`. All valid geometries are retained, and gains
are published as immutable cumulative snapshots. Canonical merges and any
submission remain root's separate validated actions.

The run completed normally: all sixteen native trials returned and all sixteen
poses passed the full gates, with seven improvements. Candidate score gain is
0.00016308517066165504 against the frozen RAW. The largest contributions are
n920 (0.0000595975), n919 (0.0000519804), n696 (0.0000210066) and n996
(0.0000148749). Total run time was 78.85 seconds, with no forced kill and all
three CPU workers released.

Native times ranged from 5.13 to 22.07 seconds, median 11.54 seconds; ten of
sixteen exceeded the previous ten-second cap. Six finished within ten seconds
under this run's load despite timing out previously. Thus input/seed/numeric
settings are exactly matched, while wall-clock timing is not a controlled
hardware-load experiment. Summed native time was 191.81 seconds; separate gate
time was 23.30 seconds. The unchanged worker/helper source hashes all matched.

Final immutable outputs under `artifacts/fq-timeout-extension-v1/complete/`:

- `candidates.json` SHA256
  `e44e0a4a7a3b5acbde6dbc18eb1e1f2de88dbfbfc3fae56be0f11da0053cd33c`.
- `donors.npz` SHA256
  `7c74767603add6d16aeade20de929e5d439239bed12dcdd544ed99189f0269d8`.
- `results.json` SHA256
  `6da3b7e53dcddc09113ef90f767ab1448fb4f943d81cb64efec3a58d1185c34e`.
- `manifest.json` SHA256
  `af2bf8f26811e71a640842abd3f67765516f024c44d363517ca5e309b68f70db`.

`completion-review.json` verifies every original input/seed and every retained
archive/geometry/full-certificate binding. Twenty-eight unchanged eligible
timeout parents remain outside this finite queue; no further trial was run.
