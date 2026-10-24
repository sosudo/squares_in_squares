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
zero reserved, with paid scaling disabled. No result is yet claimed, and
previous executed experiments remain unchanged.
