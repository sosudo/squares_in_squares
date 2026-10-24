# Squares in Squares competition research

Researched 2026-10-24. No Kaggle credentials were used.

## Verification status

Kaggle network access was enabled during this task. Official pages were retrieved using unauthenticated public frontend APIs and saved as `official_*.md` in this directory. The official metric v17 was pulled directly and confirmed byte-for-byte identical to the original mirror. Rules, scoring, schema, timeline, and leaderboard have now been verified from official sources.

## Objective and format

For every n=1..1000, pack n non-overlapping unit squares with arbitrary rotation into the smallest axis-aligned bounding square. Bounding length is translation-invariant: `L=max(max_x-min_x,max_y-min_y)` over all square corners. Minimize `sum_n (L_n/sqrt(n)-1)`; lower is better. Grid upper bound is `ceil(sqrt(n))`, area lower bound is `sqrt(n)`.

CSV header: `id,n,square_id,x,y,angle`. Full submission has 500500 rows. `square_id` must be exactly 0..n-1 for each n, with exactly n rows. x,y are centers and angle is radians. Coordinates and angles are plain decimal/scientific literals, not symbolic expressions. id is a unique row integer and is removed by the scoring entry point.

The mirrored v17 metric uses interval arithmetic at increasing precision 50,100,200,500 digits to certify non-overlap; undecidable contacts are rejected. Touching is mathematically allowed but decimal approximations should have verified positive gaps. Invalid or absent puzzles receive their trivial-grid penalty rather than making the score zero. Side length itself is measured with 60-digit mpmath precision; per-puzzle output has 50 decimal places.

## Public reusable solutions

1. https://github.com/Shubin123/unitSquares
   - Locally cloned at `/tmp/squares-research/shubin`.
   - Inspected commit `fe423cb11a483504f327ddc8eb251569ead7420d`.
   - MIT licensed, copyright 2026 Shubin123. Preserve the license when copying substantial code.
   - Bundles 475 improved-case packings in `data/kaggle/{n}.bin` (triples of f64 x,y,angle), plus exact construction code for the rest.
   - `node tools/make-submission.mjs [output.csv]` builds and checks a complete CSV offline.
   - README claims merged score 22.372005; not independently validated here.
   - Bundled sources: kirilltym Band LP (370 cases), malyshevdanil Neighbour Transfer + Squeeze (92), alexchilton Fault-line DP + Basin Hopping (13).
   - Geometry, strict f64 SAT check, positive-gap finalization, and CPU/GPU local optimizers are in `src/`.
2. https://github.com/tiagocabo/kaggle-squares-in-squares
   - Locally cloned at `/tmp/squares-research/tiagocabo`.
   - Inspected commit `9f4236dd436cb534aaf65ebd46ee072839976140`.
   - No LICENSE file observed; inspect licensing before redistributing its code.
   - Includes `metric/metric.py`, claimed official v17, SHA256 `312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733`.
   - Contains grid/Goebel strip baseline, record SVG/certificate parsers, L-extension/drop-a-square closure, fault-line gadget DP, L-BFGS compaction and basin-hopping.
   - Claimed public scores: v1 24.02152; v2 22.64887; v3 22.50447.

Public notebook links cited by Shubin123:
- https://www.kaggle.com/code/kirilltym/22-3720-cpu-cuda-mps-eda-band-lp
- https://www.kaggle.com/code/malyshevdanil/squares-in-squares-neighbour-transfer-squeeze
- https://www.kaggle.com/code/alexchilton/fault-line-dp-basin-hopping-lb-22-3747
- https://www.kaggle.com/code/cdeotte/squares-in-squares-multi-gadget-fault-dp-22-48
- https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search
- https://www.kaggle.com/code/kozykappa/subset-transfer-contact-refinement-and-compaction
- https://www.kaggle.com/code/avazaku/squarecraft-ii-unjam-the-grid-22-408597-lb

README documents public output downloads at `https://www.kaggle.com/api/v1/kernels/output/download/<user>/<slug>/submission.csv`, reportedly without login. Not yet tested successfully due network block.

## Literature / constructions

- David Ellsworth records and SVGs: https://kingbird.myphotos.cc/packing/squares_in_squares.html
- https://github.com/franciscouzo/square-packing : rational certificates (x,y,tan(theta/2)) reportedly through n=10000.
- https://github.com/jlevy/squares : witness/frontier packings.
- https://github.com/evand/square-packing : additional reference implementation.

Promising workflow: merge the public frontier; validate with official interval metric; apply monotone subset transfer and L-frame extensions; compact with contact LP/SLP or SAT penalty; target high-waste cases and extrapolate improved motifs. Public frontier is around 22.372 per the latest cited repository, materially stronger than rebuilding a grid baseline.


## Official verification (2026-10-24)

Source APIs (public, read-only):
- POST `https://www.kaggle.com/api/i/competitions.CompetitionService/GetCompetition` with `{"competitionName":"squares-in-squares"}`.
- POST `https://www.kaggle.com/api/i/competitions.PageService/ListPages` with `{"competitionId":166661}`.
- POST `https://www.kaggle.com/api/i/competitions.LeaderboardService/GetLeaderboard` with `{"competitionId":166661}`.
- GET `https://www.kaggle.com/api/v1/kernels/pull/metric/squares-in-squares`.

Key rules: B6 allows equally accessible public external data at no cost, and tools/LLMs meeting the reasonableness and licensing requirements. C5/C6 forbid private competition-code/data sharing outside a team. One unique Kaggle account; maximum five team members; ten submissions per day; one selected final submission. Winners must provide reproducible source and grant CC BY4.0 or Apache2.0 licensing. No restriction on automated optimization or AI assistance identified in the published rules.

Deadlines: start 2026-10-21; milestones 2027-01-17 and2027-04-18; entry/team-merger 2027-07-11; final 2027-07-18. Each deadline 23:59UTC.

At retrieval, 483 teams; leader 22.2247581510, second 22.2337487110, third 22.2504461270. The current public notebook frontier is newer than the GitHub bundle: kmmmvs/squares-dashboard-public-batch-20261024 reports 22.3103707593, cdeotte/squares-in-squares-ftmc-milp-refill-22-311 reports 22.3116182199. Public outputs redirect to www.kaggleusercontent.com.

Current Couzo catalogue produces 212 improved candidates relative to the initial 22.372005 baseline, estimated gain 0.02123248173. Importer: `experiments/import_records.py`; candidate data:`artifacts/candidates/records.json`; 75-digit decimal strings, exact source/certificate provenance. Official interval validation is required before merging.
