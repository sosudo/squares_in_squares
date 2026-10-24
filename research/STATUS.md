# Working status

Goal: highest possible rank in Kaggle Squares in Squares. Competition details and authorization are in GOAL.md. Keep working after context compaction; the task is ongoing.

## Confirmed

- Official competition metric v17 pinned SHA256312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733.10submissions/day,1final. Public solutions permitted with licensing/attribution.
- Kaggle account sos54352 authenticated; user entered competition.30GPUhours authorized, roughly0.03h spent on successful infrastructure pilot so far.
- Current latest fully certified candidate merged-v6.csv:22.304824583795792; SHA10f225117b3a237964000c0f8bd5b6659a0a7c1e4eb50c7e06a60d5d1e08b968. Agent preparing v7 with additional composition candidates. All candidate/report versions immutable.
- No competition submission registered yet. Initial local upload stopped at0bytes, next bounded attempt exposed denied destination www.googleapis.com. Domain added to latest network draft but still denied after user approved earlier settings.
- Normal Kaggle notebook-output submissions are verified supported for this CSV competition. scripts/build_export_job.py builds a private CPU notebook which exports exactly certified CSV bytes. Use latest frozen candidate+official report; test export locally; push notebook, waitcomplete, then CLI competitions submit -k sos54352/squares-certified-portfolio -v VERSION -f submission.csv. This is the preferred supported submission route now.
- scripts/kaggle_cli.py loads runtime credential or protected /tmp/squares-kaggle-auth/token. Never print credentials. No secrets embedded in jobs or source.
- sos54352/squares-search-pilot version1 completed; artifacts/gpu-pilot-results contains outputs. Three30s searches, no new gains. Confirms privateGPUexecution and download work.
- sos54352/squares-ftmc-pilot version1 is RUNNING. Bounded600s FTMC worker+180sgrace; uses released Apache2CUDAcode with39public gadgetfixtures. Pull outputs whencomplete, inspect preflight/worker status/candidate variants, and compose winning gadgets into fullpackings. Do not spend longGPUbudget until pilot provides useful throughput/gain evidence.
- Notebook_frontier agent owns CPU/GPU gadget composition adapter and v7. Packing_research agent packagedFTMCpilot. Validation agent implemented officialdelta reuse by exactdecimalrowhash.

## Paperspace

User created Gradient project squares_in_squares, IDpipamsa5ztw. No machine exists. ONLYFREEinstances authorized, no paid resources/upgrades. SSH key exists /workspace/.ssh/paperspace_squares_ed25519 (public supplied to user). APIkey configured in draft; runtimeenv absent but protected fallback/tmp/squares-paperspace-auth/token exists. Never print it.

Paperspace hosts reachable after networkapproval but respondCloudflareError1010 browser_signature_banned, explicitly nonretryable. Tokenvalidity/freeavailability remainunknown; noPaperspaceresourcescreated. scripts/paperspace_access.py stops on this response. Do not evade challenge/spoofbrowser or repeatedlyretryunchangedrequest. Continue Kaggle.

## Sources and artifacts

See research/public_frontier.md and research/additional_sources.md for exactpublicsources/versions/hashes/licenses. vendor holds attributedMITShubinbaseline and ApacheLightningv21solver. artifactsignored byGit but retained. User asked persistentgoal and autonomouswork; don't stop merely after firstsubmission or baseline. Keep receipts, actualscores/rank, computeusage and bestcandidatehash.
