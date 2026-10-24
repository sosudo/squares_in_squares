# Working status

Goal: highest possible rank in Kaggle Squares in Squares. Competition details and authorization are in GOAL.md. Keep working after context compaction; the task is ongoing.

## Confirmed

- Official competition metric v17 pinned SHA256312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733.10submissions/day,1final. Public solutions permitted with licensing/attribution.
- Kaggle account sos54352 authenticated; user entered competition.30GPUhours authorized, roughly0.03h spent on successful infrastructure pilot so far.
- Latest fully certified candidate: artifacts/merged-v7.csv, official score 22.304805438790023, SHA256 9c2cb31c689c90e7f1ab25672d77dea02b88ba63582f0b96dc3d2c992b2055e8. Its lossless private CPU export job is artifacts/certified-export. Local export test passed. All candidate/report versions immutable.
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

## Latest checkpoint (2026-10-24 05:03 UTC)

- Initial raw CPU export succeeded remotely as sos54352/squares-certified-portfolio-source-export version1. Actual URL differs from early intended slug because title determined the slug. Its remote export_manifest matches immutable v7 exactly. No competition submission yet.
- Important transport finding:8of88highprecisioncases fail after pandasfloat64roundtrip. Validation agent created scripts/make_transport_safe.py, scales only centres by1.00000000001 usingDecimal100, angles/unit sides unchanged. Current best safe artifact submission-safe.csv derives from merged-ftmc-cpu.csv; safe SHA97df15c28ee66ab1a414d28218fd4e8b28c2bf6ce8869281db9610f7dac81da9. Official rawscore22.304803810998131,0invalid. FullALL1000floatroundtripcheck running. Wait for that report beforefirstsubmit.
- competition_research agent adapting scripts/build_source_export_job.py to reconstruct raw source portfolio then apply exact shared clearancetransform; artifacts/source-export-safe will fit<1MB and use existingactualrefabove forversion2. FullCSVliteral source was9.4MB and Kaggle rejects source>=1MB. Source-backed reconstruction is tested and works remotely.
- FTMCpilot version1 completed:601sworker,96,584coretrials,76acceptedimprovementevents,154savedvariants,19directedgadgetkeys improved. Outputs artifacts/ftmc-pilot-results. Allpreflight andofficialchecks pass. CPUcomposition found no gain fromthese newgadgets underconservativecornerjoins; needGPUseparatorprofilecomposition.
- sos54352/squares-composition-pilot version1 ERROR after31.6s. Cornerpreflight passed; seam/adaptivepreflight hitsCuPy PythonUINT64_MAXscalaroverflow. notebook_frontier agent prepares explicituint64compatibilitypatch, original/newhashrecord, then rootshouldpushcorrectedversion afterlocaltests. Do not assume numericalkernels validated.
- Prepared but NOTLAUNCHED dualT4campaign artifacts/ftmc-campaign.1800sperdevice,128replicas,distinctseeds,resumepilotbestvariants,hard40mincap; code871KB. Wait forfullpuzzlecompositionbenefitbeforelaunch, peruserquotaintentionality.
- Quota lastread:0.23hused,29.77hremaining.
