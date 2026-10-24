# Exact translated-window subset search

The C++ sweep in `experiments/exact_square_window.cpp` finds the largest subset
of fixed source squares contained by an axis-aligned square of a given side.
For each source bounding box `[lo, hi]`, the allowed lower-left window positions
are `[hi_x-L, lo_x] × [hi_y-L, lo_y]`. A sweep of the x endpoints and an inclusive
range-add/max tree over y endpoints finds maximum overlap in O(M log M).
At an equal x, starts are added before querying and ends removed afterward.
This covers every translated window for the supplied binary64 bounding boxes;
it does not search source rotations or rearrangements.

`experiments/exact_square_window.py` uses the complete certified portfolio only
as a target (and optionally a source), tries `incumbent_side - 1e-6`, and binary
searches successful queries. Source square coordinates and indices are retained
without translating the selected subset. The final candidate must pass the
independent interval validator and unchanged official metric on exact `.17g`
text, numeric `.17g` pandas output, and ordinary default pandas output. Candidate
coordinates are exported as the exact certified `.17g` strings.

Four tests cover closed/degenerate boundaries, 180 small random comparisons to
brute force, process cleanup on timeout, and decimal transport. An independent
review confirmed the sweep/event ordering. That review also caught an initial
JSON-float handoff mismatch, which was corrected without rewriting the historical
executed output.

## Completed runs

1. **Portfolio + 320 alternative public poses + 1,243 high-n crops.**
   `artifacts/exact-window-v1` completed all 2,110 sources in 130.60s:
   219,771 threshold queries plus 23 successful binary-search queries. It found
   one certified gain, n807 from the existing n865 geometry, side
   `28.874863077749833`, expected portfolio-score decrease `8.441535816973704e-6`.
   The corrected, recertified handoff is
   `artifacts/exact-window-v1/candidates-transport-verified.json`, SHA256
   `70592ca84bbbc917b4338d25aaeddbafeeca172bd73266bb8b92f223d8b80845`.
   The original running wrapper emitted JSON floats; use the corrected handoff.

2. **175 complete public witnesses, n1057–4979.**
   `experiments/prepare_window_witnesses.py` reconstructed all 487,846 squares
   from pinned Couzo certificates, preserving original square ids and original
   symbolic certificate hashes. Conversion and separately recorded numerical
   clearance took 10.27s. Three tilted-subset conversion controls passed every
   gate; the complete source archive itself was not claimed officially valid.
   Source archive SHA256:
   `79bf0e8cbb3e7013dabb70728f88329e6cb3eb6d26c32b6c03fa098f86ca38d9`.
   Source repository commit:
   `964ee2bdf301d0c8912d956d4010f478dcbbd5ea`.

   The initial band pass (`exact-window-full-v1`) completed 19,600 queries in
   77.70s. The complementary all-counts pass (`exact-window-full-complement-v1`)
   completed 149,975 additional queries in 314.85s. The union is **all 175 sources
   × all 969 non-perfect target counts n2–1000 = 169,575 threshold queries**.
   The other 30 target counts are perfect squares and were skipped by the area
   lower bound. Every query returned fewer than N contained source squares;
   no improving candidate reached the certification stage.

   The target was frozen portfolio SHA256
   `a776d6e323ab20a9498bba64b963ee546ebd931a56440fd80ad24b9fa4508de8`, score
   `22.302218768790183`. The evidence report is
   `artifacts/exact-window-full-coverage.json`, SHA256
   `1537114ea32325f2fd7fccc603eb677cfcee278ca5dff4ae354d73da2ebbf674`.
   The complementary pass saves the exact 857 returned target counts for each
   source. The older coarse wrapper had no per-source coverage file; its 112
   non-perfect counts follow deterministically from the frozen schedule and its
   complete 175-source, 19,600-query receipt.

These negative results rule out the tested fixed-axis subsets at the stated
thresholds for these prepared source geometries. They do not rule out rotated
windows, different sources, continuous rearrangements, or improvements smaller
than the 1e-6 side threshold. After the completed negative pass, compute moved
to localized aspect continuation of complete puzzles rather than repeating
the same window search.
