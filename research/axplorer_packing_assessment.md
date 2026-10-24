# Axplorer: public source and a bounded packing adaptation

Read-only assessment, 2026-10-24. No installation, training, optimization, paid
service, external message, or submission was performed.

## What is actually available

[AxiomMath/axplorer](https://github.com/AxiomMath/axplorer/tree/3298b1afcefc04a3404d3d2b24cb3ccd1877c027)
is public Python/PyTorch source under
[Apache-2.0](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/LICENSE).
The checked commit is `3298b1afcefc04a3404d3d2b24cb3ccd1877c027`. It trains a small
decoder from scratch; it needs no paid model API or hosted model account.
The public repository exposes a Python extension interface and CLI, not a
documented hosted packing service. Its release list is empty, and its checked
tree contains no pretrained packing model or packing-coordinate archive.

**Its environment named `square` means graphs without four-cycles, not unit
square packing.** The other shipped environments concern isosceles-free grid
sets and sets without five cospherical points. See the
[explicit environment table](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/README.md#L184-L198).
Axplorer credits Charton, Ellenberg, Wagner and Williamson's
[PatternBoost](https://github.com/zawagner22/transformers_math_experiments): learn
patterns in good local-search outputs, sample new objects, repair/improve them,
and train again. This is a reusable proposal mechanism, not a new geometric
packing solver.

The related public Axolver repository trains mathematical sequence-to-sequence
tasks; its documented tasks likewise do not provide packing witnesses. The
accessible [Packomania catalogue](https://www.packomania.com/) lists circles,
spheres and hyperspheres. It did not expose equal-unit-square coordinates in
the checked catalogue. No such coordinates were imported. Axiom's company
domains and arXiv were blocked by this environment's proxy, so the assessment
does not claim to exhaust an uninspected hosted service or paper.

## Concrete integration contracts

The [new environment tutorial](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/new_envs.ipynb)
and [base interface](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/src/envs/environment.py#L11-L49)
require a `DataPoint` with `calc_score`, `calc_features`, `local_search`, initial
generation, and serializable class parameters; a tokenizer; and an environment
registry entry. For packing, the following distinctions matter:

- Scores below zero mean invalid, and larger valid scores win. Use a positive
  monotone objective such as `1/(1+f)` for a fixed valid surplus rectangle,
  where `f` is its certified excess. A signed improvement over the incumbent
  would wrongly mark valid, slightly worse diversity as invalid.
- The [scoring wrapper](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/src/envs/environment.py#L102-L114)
  evaluates score/features *before* local search and does not automatically
  recompute them afterward. Our projection hook must update both after repair.
- `local_search` can call the existing bounded native FQ solver. Sampled poses
  remain unverified until count, independent geometry, official raw, and
  ordinary-pandas gates pass. All valid outputs stay in our immutable archive,
  even if excluded from the model's training population.
- The stock [sparse tokenizers](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/src/envs/tokenizers.py#L5-L22)
  enumerate an `N**k` occupancy grid. They are not a compact pose-list codec.
  A short fixed-length residual tokenizer is needed; reusing `N` as the number
  of squares would conflate alphabet/grid size with physical object count.
- [Population selection](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/src/datasets.py#L70-L138)
  supports exact feature deduplication, a forced fraction of new examples, and
  a temperature increment when within-batch uniqueness falls below 90%.
  Exact floating-point geometry hashes alone are insufficient evidence of
  distinct contact basins. Keep D4/contact-family splitting separate from
  exact archive identities.

The [training entrypoint](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/train.py#L43-L66)
allows small layer/embedding sizes and an explicit CPU option. Its
[model construction](https://github.com/AxiomMath/axplorer/blob/3298b1afcefc04a3404d3d2b24cb3ccd1877c027/train.py#L95-L114)
creates a local transformer and AdamW optimizer. No paid inference call is
required. Default sample/population sizes should not be used for our expensive
native projection; the existing evaluator can queue generated batches faster
than its CPU projection workers consume them.

## Smallest credible experiment, proposed only

Use one fixed compact gadget family, for example `5_18_11` (101 squares) if its
archive has enough genuinely different contact patterns. Select the family by
an inexpensive archive audit before allocating training. Do not assume the
7,000-plus combined records are independent examples: many differ only by
tiny numerical motion, symmetry, or repeated descent into one basin.

Align each certified pose to a fixed reference using the appropriate D4
symmetry and stable square correspondence. Encode *residual* x, y and angle
bins per square, rather than generating 335 absolute poses from scratch.
The initial candidate bins could be 1/64 unit and one degree, with explicit
overflow rejection; these are parameters to test, not measured optimal
choices. Fixed correspondence requires positional embeddings and exactly
`3*n` output tokens. Preserve native float64 poses as the authoritative source;
the quantized sequences only propose perturbations. Contact fingerprints
provide dataset splits and novelty measurements, never a feasibility shortcut.

A finite decision gate would be:

1. Require at least 128 nontrivial D4/contact groups for training plus a held-out
   group set. With fewer groups, stop rather than train on thousands of nearly
   identical decimal variants.
2. Test 16 held-out quantize/decode/native-projection controls with a short
   fixed native cap. Require at least 12 to return fully valid poses within
   `f_reference+0.002`; otherwise refine or abandon the representation before
   training. This tests representation damage independently of learning.
3. If those pass, propose one small model, two layers/128 channels/four heads,
   capped at ten GPU minutes. Then compare 64 learned proposals with 64
   perturbations sampled from the same empirical residual marginals, using
   identical native/certificate budgets and independent seeds. This isolates
   learned cross-square correlations from the value of simply running FQ.
4. Continue only for a strict certified current-family improvement, or a
   clearly higher yield of competitive new contact geometries with a measured
   downstream composition use. Lower training loss or more distinct hashes
   alone are not success. Otherwise stop after this batch.

The original128-group proposal did not specify a numerical grouping threshold.
The later data audit reports both fine and coarse geometry groups. Using the
coarse count to defer training is a conservative engineering interpretation,
not a precisely predeclared pass/fail test: n65 has177 fine groups but15 coarse
groups. Neither grouping proves distinct optimizer attraction basins. See
`research/axplorer_training_data_audit.md` for the thresholds and imbalance.

No quantized-projection control or training launch has occurred. The hypothesis
is that correlations learned across existing certified geometries produce
better initializers than independent kicks. Native
FQ and the existing admission gates remain the geometric authority. Retain
Apache-2.0, Axiom's PatternBoost attribution and the native MIT notice if any
source is incorporated later.

## Evidence

`artifacts/axplorer-public-research-v1/` contains the public request receipts,
raw README/license, commit/tree responses, inspected code, and public catalogue
page. `provenance.json` binds every downloaded code file to its Git blob at the
pinned commit and records all SHA256 hashes. No old packing source pin changed.
