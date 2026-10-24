# Competition goal

Maximize the leaderboard position in Kaggle Squares in Squares, ideally first place, while obeying the competition rules. The user authorizes research, implementation, experiments, and competition submissions. Use public solutions and literature where the rules permit. Do not claim a rank without observing the leaderboard.

Do not put API keys in the repository, scripts, logs, or research notes. Read authentication from the runtime or a protected credential store. The user authorizes using the full available Kaggle GPU quota, but expects intentional experiments. Start with short correctness and throughput pilots, checkpoint results, and allocate longer runs based on evidence. Do not create or resize paid resources. The user created Gradient project squares_in_squares (project ID pipamsa5ztw) and authorizes creating notebooks on FREE machines only, subject to availability. There is no running Paperspace machine. Do not create paid resources or upgrade the account. A protected Paperspace credential is provisioned, but the API currently returns an explicit nonretryable Cloudflare 1010 denial; no resource has been created.

## Checkpoint and submission cadence

The user explicitly requests frequent commits and pushes at validated checkpoints. The latest instruction forbids any further submission until both the exact-decimal and numeric-roundtrip validated scores are strictly below 22.3 (the 22.2x range or better). The hourly runner was stopped. Once this threshold is met, submit at most hourly and only if strictly better than the best already submitted; skip unchanged or worse candidates. Respect the competition limit of ten submissions per day. Every submitted file must pass both exact-decimal and ordinary floating-point transport validation.

## Current plan

1. Verify official rules, scoring version, deadline, and daily submission limits before submitting.
2. Establish a complete validated public baseline with attribution.
3. Merge verified improvements per puzzle, keeping reproducible experiments and score records.
4. Submit promising validated candidates within the competition limits and inspect actual results.
5. Prioritize new constructions and contact optimization where gains remain.

## Access and verification

Kaggle authentication works and the account is already enrolled. Official rules and metric v17 are saved under research/. Ten submissions per day and one final submission are allowed. Public external data and released solutions are permitted, with attribution and applicable licenses. API, website, GitHub and Google Storage access work. The notebook-output download host www.kaggleusercontent.com was additionally saved to the network draft and may still require activation. Public dataset downloads already work through Google Storage.

## Current research state

Read README.md, research/public_frontier.md (when present), and artifacts/ submission/validation reports before restarting work. Never overwrite a candidate while it is being certified. Keep Kaggle submission receipts and actual scores distinct from local estimates. The initial baseline is 22.37200587895322; combining newer public sources and exact certificates has independently certified a lower score near 22.306545. Check the latest official report and submission ledger for the current incumbent.
