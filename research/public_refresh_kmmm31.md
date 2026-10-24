# Public freshness check, 2026-10-24 13:56 UTC

The explicit Ready-version check found KMMM versions 30 and 31 beyond the
previously pinned 29. Version 30, created at 13:31 UTC, announces 60 puzzle
improvements. Version 31, created at 13:55 UTC, says it retains the same packing
CSV and adds a confirmed receipt. Only the latest explicit version 31 CSV was
downloaded; version 30 coordinate identity is the publisher's statement, not a
second download comparison.

Lightning 19, Cdeotte 2, Dariush 11 and Couzo commit
`1c1715399709bc955e9b402947ab8b52bbacdfc3` were unchanged. Exact public metadata
responses, version selections and Git commit responses are retained under
`artifacts/public-freshness/check-20261024T1356/`. Jlevy's repository has a new
HEAD, `2ec489d1eede791bf0686ca1c524278c2bb80253`, directly after the old pin.
The bounded assessment found 269 added files, including 211 rational witnesses.
All 211 are byte-identical to the already retained Couzo catalogue, checked by
both Git blob identity and declared SHA-256. Thus this intake adds no new
coordinates relative to that retained source. Nineteen of the 203 own-count
witnesses at n≤1,000 have tiny nominal header advantages, at most 4.856e-10 in
side and 5.4504e-11 in aggregate score; these are not freshly certified gains.
No witness was downloaded again or recertified. The exact comparison and
identity records are in `artifacts/public-freshness/jlevy-2ec489d1eede/`.

## KMMM 31 result

The 24,627,203-byte CSV has SHA-256
`0dca84e8b18a0de1ec2f3f1bb8c1bd00a529c893a2591138f13231ec9109e799`.
Its public portfolio manifest binds the same bytes and reports 22.307815883682977.
That publisher aggregate was not recomputed here.

All 1,000 supplied cases were compared against the certified final-v2 RAW
portfolio `3855c47798708e4bfb9f053024e6542b0a2a5021824bfd310290e4e7ab1ff9ea`.
The float side filter used a 1e-11 margin and exact coordinate-text hashes.
Only cases 802 and 928 were promising. Neither was already improved in the
hash-bound rigid-search snapshot `gain-0018` inspected before certification.

Both cases passed strict interval side comparison, raw official validation,
ordinary-pandas official validation and an independent interval check of the
pandas copy. The one-worker screen and gates took 20.12 seconds, with exactly two
new evaluations of each kind. No unchanged case was recertified.

| Case | Raw score gain over final-v2 |
| --- | ---: |
| 802 | 0.000000005789556834 |
| 928 | 0.000000090899553662 |
| Total | 0.000000096689110496 |

The exact decimal candidates are
`artifacts/public-kmmm31/certified-screen-v1/winning-candidates.json`, SHA-256
`1e5f35045b931568ffd9f7810d279c2fd2af150aee0c7fdf94e94f5ba6c2600a`.
The full source, baseline, certificate and notice bindings are in
`artifacts/public-kmmm31/completion-proof.json`, SHA-256
`aa97225e704c0c0945df4c5c3336a43d2765999fdc53bf5c3c38e2099736f311`.
This task did not merge the candidates, change the canonical pointer, submit to
the competition or launch remote compute.

## Attribution

The dataset declares **Other (specified in description)**. The full new
`SOURCE_NOTICES.md`, per-puzzle source and contributor tables, external
contributors, public release provenance and exact metadata are retained in
`vendor/notices/kmmm-v31/`.

Both selected cases are expressly identified as `local-candidate-bank`
refinements on inherited witnesses. The release provenance lists them among its
seven local cases and binds the exact CSV. These labels do not establish
exclusive original discovery. The source-specific licenses and inherited
credits remain intact; no blanket relicensing is asserted.
