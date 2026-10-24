# Sources and changes

The frozen starting submission is Vladislav Lavrentev (lightningv08),
Squares in Squares | CUDA Packing Search, version 6 / native version 360946057:
https://www.kaggle.com/code/lightningv08/squares-in-squares-cuda-packing-search?scriptVersionId=360946057
Baseline CSV SHA-256: 2ab6ab746b5ab0fdf14f8f9eb86da3ce052b651803d65009cbef2d12530c7aac
Baseline official v17 score: 22.595460848551.

The new contribution is a CPU experiment applying exhaustive translated-window
queries to the latest portfolio, followed by contact refinement with changed
regularization/trust settings and propagation across puzzle sizes. Segment-tree
window sweeps, cross-size transfer and contact polishing already occur in the
credited source lineage; these primitives are not claimed as new inventions.
cpu_contact_polish.py is adapted from lightningv08's Apache-2.0 contact_polish.py.
Changes remove CUDA imports, expose trust/regularization parameters, and use the
local CPU geometry/repair implementation. The other experiment modules are
written for this experiment. No new world-record or global-optimality claim.

The baseline inherits numerical layouts from avazaku's Squarecraft, prvsiyan's
A Square Deal, alexchilton's Thinking Outside the Grid and Certified Merge,
David Ellsworth's catalogue and Erich Friedman's collection, Joshua Levy and
contributors' Squares Project, Francisco Couzo and individually credited
contributors, and Darius Muglich. Original discoverers, construction and solver
authors retain credit, including de Winter, Fang, Daniel, Göbel, Cantrell,
Bidwell, Hajba and Schadt. The frozen attribution files are retained under
source_provenance/. Mathematical coordinates are modified by subset selection,
rotations, contact refinement, centre dilation and integer border addition.

Primary snapshots and grants:
https://github.com/jlevy/squares/tree/970e89de8c253133500797b414d2dd31f9e17258
https://github.com/franciscouzo/square-packing/tree/7b6c87e129cf80b5ff9847b90b47fd30b4563c54/certificates/best
https://github.com/jlevy/squares/issues/686#issuecomment-6302118274
https://creativecommons.org/licenses/by/4.0/
https://kingbird.myphotos.cc/packing/squares_in_squares.html
https://www.kaggle.com/datasets/lightningv08/squares-in-squares-layout-atlas

The official metric is an unchanged Apache-2.0 copy of Kaggle Competition
Metrics, version 17 / native version 360167936:
https://www.kaggle.com/code/metric/squares-in-squares?scriptVersionId=360167936
Metric SHA-256: 312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733

Inherited source licenses and original authorship are preserved. This notebook
does not redistribute source research prose, SVG artwork, or third-party images.
