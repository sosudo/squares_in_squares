# Four complete rectangular families

This finite campaign searches all unit squares in four ordered rectangular
families: 5×17+7 (92 units), 7×19+13 (146), 7×20+14 (154), and 8×21+13 (181).
It keeps imperfect complete states between proposals. This differs from the
previous tilted-core mutation followed by upright refill and from independent
CPU perturbations of individual valid donors. The method still requires actual
compatible full-puzzle recomposition; a component excess reduction is not a
competition score improvement.

The exact v2 input archive is
`1c2d92e19f8cd35d275122b8ed5746aba03c0ed113d4650a34d19447fbb87751`.
Each family has four certified, assignment-separated geometries, with minimum
reflection/unit-assignment center RMS distances .028/.039/.042/.036. These are
not demonstrated optimizer basins. The lexicographically smallest reflected
corner-profile records number 3/1/1/2 respectively; retaining the full multiset
of all four reflections gives 3/1/1/3. Neither coarse summary proves exact
compatibility. The two seven-wide families do not start with four different
discrete interfaces. Originals, translation-only preparation,
exact certificates, source notices and selected-array hashes are preserved in
the private, byte-verified fixture dataset
`sos54352/squares-rectangle-fixtures-1c2d92e19f8c/1`.

Four exact matched original-reference native controls used seed9710000,
ALM45/pit100/flip16, and the actual rectangular offsets. All four passed the
unchanged full geometry gates and independent two-span gates. Only 8×21+13
improved, by 4.6317e-8 in component excess. Search seeds and target upper bounds
remain unchanged; strict component comparison uses the stronger interval lower
bound of the original and this matched control. Its tiny gain cannot be
attributed to the GPU campaign. These controls are not repeated remotely.

Each family uses B64: four source geometries × four contractions
(.002/.01/.03/.06) × four independent random streams. Contractions use the
same best original source excess across all four starts. At each source/cut,
two streams use T=.3 and two T=1, with matched proposal amplitudes 1 and1.5.
All streams switch to T=.03 for the final quarter of the initialized 3000-second
search epoch. The corrected symmetric-tie FP64 quench remains unchanged at2000
steps and `--fmad=false`. Acceptance and BEST retention instead use a fresh
unordered-pair unit-square SAT energy with separately evaluated width and
height walls. No FP32 search or variable-size units are introduced.

Mandatory actual-device controls precede every family. They cover the original
and wider complete seeds, a genuine overlapping-pair repair, tied axes, cell
boundaries, the actual last unit, the actual B64 batch including chain63, and
an independent CPU rectangular physical-energy oracle. A wall-only fixture
places the last unit wholly above H; its independent numerical derivative
agrees with the analytic native gradient for all four exact source arrays.
The B64 timing must be at most9.5 seconds, and all source arrays must remain
unchanged. A failed family control prevents that family's search.

Two T4 queues each process two families. Each family allocates60 seconds for
controls,3040 for search initialization/search/finalization,3 for recovery and
290 for eight fixed native finishes. The native budget covers four waves of
two workers, each up to60 seconds native and8 seconds certificate processing.
Two waves total6786 seconds. The aligned parent deadline is7100, outer worker
7160, outer alarm7195, whole limit7200 and server limit7800 seconds. Actual
initialized, decision and terminal clocks determine exposure; planned time is
not reported as completed time. Registered PID/start-time descendants include
new sessions and reparented native children. They are killed and observed gone
or zombie before final output hashes are computed; real writer-process tests
exercise both deadline and orphan paths.

All scalar decisions, energy vectors, acceptance draws and RNG identities are
saved. Full transition arrays are sampled every32 rounds, at phase boundaries,
new zero-energy states and termination. An atomic, self-contained latest
current/BEST head is saved every committed round for interruption recovery.
Routine samples may be skipped at1GiB per family without pausing search;
zero-energy snapshots and scalar logs have separate512MiB/256MiB guards. A
10GiB whole-output guard and bounded protected overshoot prevent uncontrolled
storage growth. Scalar history does not independently replay unsaved proposals;
the audit will explicitly report sampled transition coverage. Every certified
pose and every exact selected native initializer is retained.

Native selection is fixed before finishing: for each contraction, lowest BEST
energy and one near-best D2-coarse-diverse BEST state, excluding exact duplicate
geometries. Every full-certified native output survives even if the additional
rectangular span proof fails or its excess is worse. Usable donor admission
requires independent raw,17g-pandas and ordinary-pandas bounds on both
width−w and height−h. Whole-packing overlap, count and official gates remain
unchanged. Component comparisons are conservative interval comparisons.

Each completed family emits a bounded, hash-bound donor/certificate transport
on live stdout as well as retaining all files. This permits early independent
validation and recomposition while the other families continue. Logged validity
alone is never admission evidence. Expansion requires at least two actual
full-case improvements totaling at least.001 against the current certified
portfolio. The notebook neither changes the canonical pointer nor submits;
the user's submission cutoff remains strictly below22.24. There is no automatic
extension of this finite experiment.

Implementation and evidence are in `experiments/fq_rectangular_persistent_*.py`,
`artifacts/rectangular-persistent-protocol-v1`,
`artifacts/rectangular-runtime-local-review-v1`, the independent input/finisher/
reference-control review directories, and the frozen notebook bundle.

The reviewed bundle was launched once as private offline
`sos54352/squares-rectangular-persistent-four/1`. At17:58:03UTC the supported
API reported RUNNING and the exact saved source hash
`fb878006be0daa5bc1c6ce622c3dc58bf39f2b3171d45704f56260368e1df7b9`.
Its830,379-byte source contains155 hash-verified payloads, preserving147 old
parent files. Independent runtime reviewe959be03 and the isolated full-fixture
bootstrap are retained beside the bundle. This launch receipt does not assert
that the mandatory device controls or subsequent search have completed.
