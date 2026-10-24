# Native finishes of compressed GPU states

The four explicitly overlapping n335 states from the private Torch ALM pilot
were finished with the pinned native FQ solver. The raw state archive is
`artifacts/fq-torch-alm-native-handoff-v1/raw_states.npz`, SHA256
`158997c79816cb1c3b4e47d58d42d818d0de66ae64dd1eef7910eea731512314`.
Each selected array is bound to the stage0039 packet and source notebook
`sos54352/squares-fq-torch-alm-prototype/1`. The initial optimized boxes and
coordinate spans are unverified starting measurements, not feasible packings.

`experiments/fq_torch_raw_finish_control.py` ran four ordinary rigid
ALM45/polish100/flip16 finishes with one CPU, an inclusive 18-second limit per
trial and a 90-second outer supervisor. It completed normally in 30.076 seconds.
All four outputs passed official raw, ordinary pandas and independent interval
gates; all native traces and outputs are retained.

| Stage0039 replica | Requested compression | Native terminal side | Inclusive seconds |
| --- | ---: | ---: | ---: |
| 00 | 0.0002 | 18.8228757373411 | 10.92 |
| 01 | 0.001 | 18.8228756911782 | 5.05 |
| 10 | 0.01 | 18.8228827542172 | 10.10 |
| 03 | 0.02 | 18.8228783979249 | 2.28 |

All are wider than current RAW side18.8228756555792035. The two deeper repairs
are outside the continuing-search band relative to their invalid compressed
spans; their certified outputs were still retained. Native repair removed the
overlaps and returned near the existing minima, avoiding the larger inflation
observed in the GPU free-release stage. This supplies no feasible compression
gain and does not establish a global lower bound.

Evidence is in `artifacts/fq-torch-raw-native-finish-v1`. The complete four-pose
archive has SHA256
`58974bf8e064c529ae267ea04cb7ef34d26d9a5c3de987fbf2583f299cd116e0`;
its provenance index is
`8f84c02189a55e72ec1f7d78687b3102995e65ff2cfc421067755f174a419119`.
The executed source is
`97c8ab442e65756368124d5dd03dae8cf4aed56348236ce3c6a4ab2c0c6ddd3b`.
No portfolio update or competition submission was made.

## Retained best states from persistent hopping

A separate four-trial control used exact `best_after` arrays from the completed
private persistent-hop notebook, never its current-chain arrays. The frozen
archive `artifacts/fq-torch-hop-selected-raw-v1/outputs/final-current-best.npz`
has SHA256
`7c72b4fc73cdd159676e911ef3af7081d0438275b31fe8b5d8dd3c615c0ff228`.
Its authenticated download receipt and `selected-state-bindings.json` bind the
source notebook SHA `a57ae191b9c61aee32b9a505a963de1bd585dfe815bf103d83e827b067a7e3b1`.
The loader also exact-compares all retained best arrays to the last completed
packet, checks selected geometry hashes and energy/box metadata, and binds the
current `6764…` SAFE and `a0dad…` RAW portfolio bytes.

Chains 8 and 11 were the lowest-energy best states in the respective 18.807 and
18.803 boxes. Chain 28 had the second-lowest 18.807 best energy even though its
final current energy was much worse. Chain 10 was the lowest-energy best from
the distinct `source_37` input. Every selected best array differed from its
chain's current array, and every input was explicitly unverified/overlapping.

`experiments/fq_torch_hop_finish_control.py` used the same rigid ALM45/polish100/
flip16 protocol, one CPU, inclusive 18-second trials and 90-second outer limit.
The entire run completed normally in 26.759 seconds.

| Best chain | Source | Native terminal side | Inclusive seconds |
| ---: | --- | ---: | ---: |
| 8 | reference_335 | 18.82287575516411 | 9.029 |
| 11 | source_43 | 18.82287569117876 | 5.698 |
| 28 | reference_335 | 18.82287572466114 | 8.832 |
| 10 | source_37 | 18.82660566908183 | 1.511 |

All four passed the complete official raw/default-pandas and independent
raw/roundtrip gates. All were outside the search band relative to their invalid
initializer spans; every certified output was retained before that filter.
None improves RAW side `18.8228756555792035`. Three return to essentially the
existing minimum, while the source_37 result is wider by 0.0037300. Low raw
energy and compressed input spans therefore supplied no feasible gain in this
bounded finishing test; no unchanged extension or portfolio update was made.

Complete evidence and native logs are in
`artifacts/fq-torch-hop-native-finish-v1`. The four-pose archive
`remote-certified/donors.npz` has SHA256
`cdfc5553e5229f503ae87d14fff91262db9a3ebd97e0f8132eed4678e0f2b1a7`;
its provenance index has SHA256
`1e55737bde6e0af1b6975737a5dc71e70e30834278d8cd6bd6f65bc9fea1af15`.
Executed source SHA256:
`25a2b771b684c0099f52f968c42d51289e730eef1e3a8a57f379d49c6a3aced1`.
