# Small motifs with repeated full-puzzle gains

The n65 construction is a high-leverage target, not an achieved improvement.
Its 8x8 integer base contains one extra square and has certified side
8.53553390594027. One-copy L-frame expansion matches the current k²+1 sides
for k8..24. Two copies with a unit-buffered public join fit a17x16 integer
rectangle and yield k²+2 cases for k17..31; three copies with buffered join
modes1 then2 fit25x25 and yield k²+3 for k25..31. Together these are39 puzzles.
The ideal derivative of their combined score with respect to the seed's side
is about2.07510608. A0.001 reduction would therefore improve the sum by about
0.002075; this remains conditional on an actual new seed and full certification.

`experiments/amplify_square_family.py` constructs the copies and frames using
the unchanged public stitch function and admits only complete raw/default-pandas
and independent interval certificates. The actual n65/n291/n628 controls passed
in2.10seconds. Their proof is
`artifacts/n65-family-controls-v1/amplification_report.json`, SHA256
`9d40930f0e0388e7d574e5a16897e6fd7f91e364741825572514cbefd73b874d`.
Conservative export clearance costs approximately1.7e-8 to8e-8 in side, so
actual emitted scores, not the ideal derivative, govern the submission gate.

The first bounded CPU search did not improve the n65 seed. After a real native
polish control passed in0.223seconds, `experiments/fq_small_square_campaign.py`
ran104 trials in287.61seconds on one worker:13 repetitions each of three kick
scales(.03/.12/.25), two temporary aspect schedules(.15/.3), two native
shrink-hop schedules, and rounded-shape continuation. Every soft candidate had
to return to exactly zero aspect before the existing rigid metric gates.
Native shrink hopping is allowed only for square containers: its pinned clamp
uses the common side on both axes and must not be applied to rectangle offsets.

Ninety-three trials were certified,11 left the near-best band, and68 unique
certified poses were retained. There were zero strict improvements. The frozen
final snapshot is `artifacts/fq-n65-small-v1/snapshot-00019`; donor archive SHA256
`384970072c7f90eec53e94c361252922c448e31e356b88587d1a3c0f1dbcb828`.
The supervisor exited cleanly within its300-second bound. Inputs, source copies,
options, native logs and exact output hashes remain in the run directories.
This is evidence about these local searches, not a proof of optimality.

A distinct neighbor-seed experiment removed each of the66 squares from the
current n66 packing, producing65-square poses with a different tilted core.
`experiments/fq_deleted_seed_pilot.py` polished all66 deletions, then kicked the
best16 starts. The82 trials completed in19.62seconds, retaining81 certified
alternatives but no current-frontier improvement. Their best side8.6568542648
remained worse than8.53553390594. Archive
`artifacts/fq-n66-delete-to65-v1/donors.npz` has SHA256
`944ef9d7200094740b87717e2f60d4ade5b84bfc829909386eec748047e4a83f`.
These are alternative starting geometries, not score gains.

The targeted GPU continuation has launched with substantial probability to n65 while
also searching the five productive larger rectangle families. A separate n50
pilot investigates another repeated excess, but equal scalar excess alone does
not establish transferable construction or additive score leverage.

The deletion pilot's actual launch was additionally bounded by GNU timeout:
`timeout --signal=TERM --kill-after=5 210 ... --seconds190`. Its internal
seconds argument controls scheduling, while this external process-group limit
covers decoding, validation and shutdown too. A subsequent source-only robustness
fix initializes empty-run output and records exceptional trials; the executed
source snapshot and results remain unchanged. The saved source snapshots cover
primary trial modules, with additional imports available in the repository;
they are not claimed to be a complete standalone dependency bundle.
