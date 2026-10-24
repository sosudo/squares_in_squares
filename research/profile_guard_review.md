# Independent review of the active-frontier A/B pilot

Reviewed source artifact:
`artifacts/active-frontier-job/search.py`, SHA256
`7148885af12c52bb29513c5dd063a6992210925cc951509d2915c325544026bc`.

The final pilot has no remaining launch blocker identified by this review.
No launch or submission was performed by the reviewer.

- Square corner ordering, clipping bounds, `(cos(theta), -sin(theta))`
  separator normal, BR ceiling/TL floor, and 16-bin quantization agree with the
  vendored CUDA definitions in `gpu_adaptive_seams.py`/`gpu_seam_profiles.py`.
- A separate half-plane boundary-intersection reference verified the clipping
  implementation over 300 deterministic random cases and 45 edge-contact/sign
  cases. Tests are in `tests/test_profile_guard_review.py`.
- All 17 selected seeds satisfy all recorded active profiles. An initial
  “any compatible use” policy could have lost another useful profile when the
  scalar incumbent changed. The final GPU0 wrapper requires **all** recorded
  profiles before promotion. Geometrically certified incompatible candidates
  are retained separately for later recomposition, never promoted in that arm.
- GPU1 is explicitly the unrestricted active-seed control. Export distinguishes
  guarded/control provenance and compatible/incompatible candidate archives.
- The 31 embedded payload entries match their manifest SHA256 hashes. Current
  adapters and runtime match the built script. Required notebook inputs are
  versioned, selected by exact content hash, and restricted to the task workspace.
  Historical examples/checkpoints are attached for audit but excluded from the
  active bank and worker resume path.
- Metadata specifies a private offline dual-T4 script. Seeds differ across
  devices. Hardware and analytic-gradient/geometry preflights remain required
  on the actual GPUs.
- Budget semantics were clarified: 900 seconds is the nominal upstream search
  limit, with 120 seconds of parent grace and a 1,500-second overall alarm.
  Batch completion, polling and process termination can add small shutdown
  overhead. The parent explicitly accepted these bounds; the pilot should not
  be described as a strict 900-second end-to-end run.

Every output still requires full-puzzle recomposition and official raw plus
numeric-roundtrip validation. Passing the support guard alone establishes
separator compatibility, not a leaderboard improvement.

Current full-puzzle CPU refinement priorities are saved separately in
`research/cpu_refinement_priorities.json`, with the baseline hash and explicitly
hypothetical gains. Leading actionable cases are n=646, 650, 813, 925, 799, 599.
