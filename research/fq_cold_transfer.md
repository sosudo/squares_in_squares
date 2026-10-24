# Independent cold-chain transfer to n803 and n861

The preceding paired n453/n693 experiment produced a certified n693 side gain
of 0.00100257 after adequate native finishing. Its strongest two states came
from base-temperature 0.3 chains, which were persistent in both arms. A matched
native finish of the original n693 reference did not reproduce that gain.
This experiment tests transfer to two new high-gap cases rather than repeating
the already searched case or claiming a benefit from hot-chain resets.
The frozen n803 layout has 71 squares tilted by more than 0.018 radians, with
angles reaching about -38.98 degrees; n861 has 287 such squares and a broader
occupied band near -26.38 degrees.

Original-reference native controls ran first on exact current n803/n861 inputs
from raw portfolio `28feb2d3059e33db0189aa46c2bdb5f1a0f0c0aa35fb0f2003181595491ba6a3`.
Both finished and passed the full gates in an 8.87-second two-CPU run; neither
improved the reference. The original source arrays are therefore retained.
The immutable control input archive is
`artifacts/fq-transfer803861-reference-controls-v2/inputs/restart-inputs.npz`,
SHA256 `79ea2bf403b7f6ca82d6662ffe5bf0128ce5a250be4138efc26061e6649b2e1b`.
An earlier preparation-only attempt failed a stale builder hash check in
0.67 seconds before native work and remains preserved separately.

Each T4 owns one case and 32 independent persistent chains. Sixteen chains use
a fixed square 0.002 smaller than the reference; sixteen use a reduction of
0.008. Each box has eight amplitude-1 and eight amplitude-1.5 chains. All start
at temperature 0.3, followed by temperature 0.03 during the final 150 seconds of
the 600-second search. There are no reset masks, paired arms or repeated
half-batch random streams. The seed namespace is 105833501 plus case number;
mutation streams bind case seed, round and chain, while independent acceptance
draws use a separate domain. This is an exploratory transfer, not a causal
comparison between methods.

The physical move families, full-pose SAT energy, ratio acceptance and corrected
FP64 tau-zero quench remain unchanged. Every quench allows 2,000 iterations and
uses the reviewed symmetric-tie CUDA source with `--fmad=false`. Actual n803 and
n861 numerical, neighbor coverage, last-index, repair and full geometry controls
must pass before search. Every source, accepted/current/best state and completed
packet remains exactly hash-bound. The prior seven-pose packet schema is reused;
its reset-related fields are explicitly inactive. Storage reserves remain
6 GiB and 3,000 packets per case, with 40% reserved for cooling if needed.

Finishing selects up to four states per case: minimum best-state energy plus a
coarse spatial/angle-diverse state in each box. The second state normally must
have energy at most max(4×minimum, minimum+1e-8); otherwise the next-lowest energy
is an explicitly recorded fallback. Diversity uses the minimum distance between
eight D4 occupancy/angle histogram transforms, is unit-row invariant, and is
not a topology proof. A second byte-identical geometry is skipped. All selected
bytes are retained before optimization.

Two CPU workers per case provide up to 60 seconds of native finishing and a
separate 8-second full certificate allowance per state. The exact existing
ALM45/polish100/flip16 numerical flags and terminal gates are unchanged. A
150-second finishing phase fits two waves; actual deadline truncations or
errors must remain explicit. Parent/whole/server limits are 880/900/1,200
seconds, with a 895-second final alarm. Every fully certified pose is retained,
including nonwinners. Only fully certified side improvements can enter the
portfolio; physical penalties alone do not qualify.

The reviewed source was launched privately as
`sos54352/squares-cold-transfer-803-861/1`. Frozen source:
`artifacts/fq-cold-transfer-job-v1/search.py`, SHA256
`34ea1497cf6e24560eff8da939b3288b08029519640ba1eb8907acc1353d1292`,
827,537 bytes and 150 hash-bound payload files. Seven focused CPU tests passed,
including the actual generated search loop through cooling, independent stream
checks and finishing selection/error retention. The isolated import/bootstrap
smoke verified that six replaced historical root fixtures are unused; all 144
remaining numerical/native/license payload files match the prior reviewed job.
Independent receipt SHA256:
`3d8febbcc178d881d7726c9f1c6b7c5ec2159ed14127ce7591cbda402464bf70`.
Remote source, privacy and GPU flags were verified at 15:16:20 UTC.

Before launch, actual service quota was 13,467.363 seconds used out of 108,000,
zero reserved, with paid scaling disabled.

The notebook completed with supervisor exit zero in 675.03 seconds. Both actual
GPU controls passed, in 13.38 and 15.04 seconds. All eight selected native
finishes completed, took 10.15–19.27 seconds each, and passed the full gates.
There was **no certified side or score improvement**. Best returned sides were
28.827586335055624409… for n803, worse by 1.113e-6, and
29.828046794101576400… for n861, worse by 5.362e-8. Every valid geometry is
retained; no extra search or finishing extension was launched.

| Case | Completed proposals | Quench seconds | Median best / initial quench at cut .002 | At cut .008 |
|---|---:|---:|---:|---:|
| 803 | 7,936 | 465.74 | 0.8812 | 0.8662 |
| 861 | 7,616 | 455.59 | 0.9333 | 0.7525 |

Every recorded quench row reached native iteration index 1,999. There were no
observed zero-energy states. The all-event audit verified independent uniform
draws, zero reset masks, exact accepted-state continuity and the decision-time
temperature change. No storage pause or cap occurred.

The requested 600 seconds was the **parent allocation**, including subprocess
startup. Both search children were killed at that hard deadline with one pending
uncommitted proposal each. Their last reported search durations were 595.208
seconds and 596.033 seconds. In the parent epoch, first cooled decisions occurred
at 451.449/451.873 seconds and last completed decisions at 598.335/599.127 seconds.
The spans between observed cooled decisions were 146.887/147.254 seconds;
148.335/149.127 seconds elapsed between the scheduled cooling boundary and last
completed decision. These observations do not establish 600 completed seconds
of child search or a complete 150-second cooling phase. Exact terminal recovery
preserves the last committed state and distinguishes pending work.

Outputs and decision analysis are in `artifacts/fq-cold-transfer-results-v1`.
The predetermined first noninitial and last completed proposal packets are
preserved in `artifacts/fq-cold-transfer-packet-fixtures-v1`: n803 packets 1/248,
n861 packets 1/238. These four exact batches are inputs to a separately
authorized finite performance diagnostic, not an extension of this negative
search result. Previous executed sources remain unchanged.
