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
