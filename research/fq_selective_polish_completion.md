# Completion-only retry of three unreturned pit80 jobs

This authorized follow-up repeats only n997, n981 and n995 from the previous
six-case no-ALM experiment. Their original forty-second trials produced no
coordinate output. It keeps the exact frozen680/current RAWadd7 parents,
encoded input SHA256 values, native seeds and `--no-alm --loosen 1 --pit 80
--flip-top 0 --v` options. No iteration limit is extended and no successful
result is repeated.

The original jobs/seeds are n997 job3/9610003, n981 job5/9610005, and n995
job6/9610006. The controller submits these original job numbers to the
unchanged base worker, preserving its derived seed. Frozen inputs are at
`artifacts/fq-selective-polish-completion-inputs-v1/`; `freeze.json` SHA256 is
`7375a303ae9d53b7f8cf8e8ab2ea9e6a5dc7aba10b06bc6e9d2d45cdc53b684e`.
All parent arrays and re-encoded input hashes were checked against the exact
prior archives and native input files.

The new controller `experiments/fq_selective_polish_completion.py` has SHA256
`96dbb8852f4b2e1938bf1d4f1d12e9dd2788abc0a2d34c0b2eb9afab5e4bc008`.
It changes the native wall cap to 75 seconds, retaining the separate
eight-second full gate. Three workers share a 100-second whole limit, with
scheduling deadline 86 seconds and process-group kill at 97 seconds. The
wall-clock cap and concurrency differ from the previous two-worker run;
hardware timing is not treated as a controlled numerical-equivalence claim.

Allocation was coordinated with anchor/full_puzzle_pilot: this run uses CPUs
2,3,4 via taskset, while the other two workers use CPUs0,1. The allowed local
affinity is exactly0–4. The run is exec session81183, outputs
`artifacts/fq-selective-polish-completion-v1`, log
`/tmp/fq-selective-polish-completion-v1.log`. Exact native return bytes precede
certification, and every full-certified pose is retained. Root owns any final
portfolio merge, SAFE transport verification and competition submission.

The run completed normally after 76.69 seconds, with no forced kill and all
three CPU slots released. n995 returned in 64.71 native seconds and n981 in
69.57 seconds, both at exactly eighty SLP iterations with no ALM. Both passed
all full gates. Combined candidate score gain against the frozen RAW is
0.000002186165878942186. n997 still produced no output before the seventy-five
second cap; its last retained trace was iteration77 with positive predicted
decrease. Printed trace values are not coordinate witnesses or admitted gains.
No further retry was run.

Final immutable files under
`artifacts/fq-selective-polish-completion-v1/complete/`:

- `candidates.json` SHA256
  `7e7bedbcc133fea40f685d9f608468f8adf53872eff1407e1942eae4c6b18acf`.
- `donors.npz` SHA256
  `c2b70911dc9c380b6bbcc0a9509629c82e6f34fdef3c6dfcf0732e71392fb429`.
- `results.json` SHA256
  `54b702575ef8eec7ede393bf7f921ff92bea5ea518cc1f6685b00ace3a10705e`.
- `manifest.json` SHA256
  `b50068f59cc1238ce072fcd7d21ef7257db899a207f89d17e6d37fc94cd94b17`.

`completion-review.json` verifies all three original input/job/seed/flag
identities and both retained full-certificate/archive/geometry bindings.
`affinity-proof-final.json` filters the immutable initial process snapshot to
the actual campaign process group, excluding inspection wrappers; all three
workers and the sampled live native child had affinity2,3,4. Earlier diagnostic
snapshot files are preserved but are not the campaign-only affinity proof.
Worker/helper source hashes remained unchanged. Root independently checks the
complete merged portfolio and SAFE transport before claiming a new score.
