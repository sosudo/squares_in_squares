# Selective follow-up from winner traces

This was a short read-only audit of the 47 previously missing-output cases after their returned current-source geometries were fully certified. It did not treat every improved case as a reason for longer polishing: the earlier broad LP100 treatment had low measured yield.

The native JSON trace's third column is **merit**, `s + 3*s0*max(violation,0)`, not certified physical side. Verbose stderr separately logs the current side variable before the trial step. Intermediate coordinates are unavailable, so the audit cannot certify intermediate physical side changes. Only the final repaired layouts have full official/raw/pandas/interval proofs.

Three winners reached the hard pit 20 limit with continued side-variable descent: n761, n920 and n997. Their final five logged scale values decreased by approximately 1.14e-5, 1.03e-5 and 9.47e-7; final repair increases were 1.64e-7, 4.69e-7 and 1.55e-8 respectively. These are finite tail proxies, not promised future gains.

Three other winners, n868/n981/n995, stopped at iteration 16 despite recent decreasing scale values. The native default 15-step stagnation check compares against the initial ALM scale, which was still infeasible and smaller than the final scale by 2.10e-4/7.47e-5/5.92e-6. The check therefore stops these runs at 16 even though the later scale is descending. This is a stopping-reference effect, not evidence that any intermediate overlapping state is a valid packing.

The exact six-case tail evidence is frozen at `artifacts/fq-winner-tail-audit-v1/report.json`, SHA256 `40baab5b5401f4c0827f63787105b787be7c74d5a4391f2c8438908c420bf7a6`. The root authorized only these six fresh certified current parents from RAW `add7c0ee1599b97bb229f279dd0ee927c502ad6710940faccd92dca7c7658a53` / SAFE680: `--no-alm --loosen 1 --pit 80 --flip-top 0`, observational trace, two workers, at most 180 seconds, native 40 seconds and a separate 8-second gate. The hypothesis is that starting from a fully valid current pose avoids the misleading initial ALM scale; only actual final full gates can establish gains.

`experiments/fq_selective_polish_campaign.py` reuses the unchanged reviewed worker by explicit process-local configuration. Native solver and metric source files are not edited. A mocked actual fork/initializer test verified flags, time limits and trace environment reach the child; it ran no optimizer. The independent review passed before the root-authorized launch. All returned bytes and certified poses, including worse results, are retained under the separate selective-polish artifact directory. No broad extension is authorized by this note.

## Authorized six-case outcome

The finite test completed all six attempts in 119.12 seconds, supervisor exit zero with no forced kill. Returned n761, n920 and n868 geometries passed every official/raw/ordinary-pandas/interval gate and all three strictly improved, for summed score gain 0.0000129924559716 against frozen add7. This is a per-case sum pending the portfolio owner's full merge and SAFE proof. Cases n997, n981 and n995 reached the forty-second native cutoff without final coordinates; their exact parents, inputs, logs and traces remain preserved, with no infeasibility or convergence claim.

Final immutable candidate JSON: `artifacts/fq-selective-polish-v1/complete/candidates.json`, SHA256 `011f8b798a76017472ff6d7fa7bc77fe35a4c3e4bd92876580ad8efbc1e0ff0a`. The wrapper and imported worker sources remained unchanged. Both workers are free. No additional run or broader extended-polish campaign was started by this lane.

## Completion-only closure of the same experiment

The root authorized one final completion-only call for each unreturned case n997/n981/n995, retaining the exact old 680/add7 parents, encoded inputs, original seeds, no-ALM flags and pit80 limit. Only the native allowance (75 seconds) and concurrency (three instead of two workers) differed. The new source explicitly verifies old input hashes and original job/seed correspondence; it reuses the unchanged reviewed worker. Root coordination reserved the other two CPU slots for a separate n693 completion.

n995 and n981 both reached iteration 80, returned and passed all full gates, adding 0.00000218616587894 score gain against the original frozen baseline. n997 reached trace iteration 77 before its 75-second cutoff but wrote no final coordinates; the positive predicted merit decrease is not an admitted physical gain. The complete run took 76.69 seconds, supervisor exit zero, no forced group kill and no source change. All workers are free. No further extension is authorized for this pilot.

Final completion-only candidates: `artifacts/fq-selective-polish-completion-v1/complete/candidates.json`, SHA256 `7e7bedbcc133fea40f685d9f608468f8adf53872eff1407e1942eae4c6b18acf`. Its `completion-review.json` verifies all three old input/job/seed/flag bindings and both retained geometry/archive/full-certificate pairs. Five of the original six cases now have new certified improvements, with total disjoint gain 0.0000151786218505 pending the portfolio owner's full merge/transport proof. n997 retains its previously certified baseline; no incomplete state is substituted.
