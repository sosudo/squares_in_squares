<div style="padding:26px 30px;background:linear-gradient(135deg,#0f172a,#1e293b,#0f3460);color:#f8fafc;border-radius:14px;border-left:8px solid #38bdf8;box-shadow:0 6px 20px rgba(0,0,0,0.22);">
  <h1 style="margin:0 0 10px 0;font-size:28px;font-weight:800;letter-spacing:-0.4px;color:#ffffff;">
    Squares in Squares: FTMC + Exact Staircase MILP Refill (<code style="color:#38bdf8;">fill_rect</code>) + GPU Seam-Welding (<code style="color:#4ade80;">22.311627</code>)
  </h1>
  <p style="margin:0;font-size:15.5px;line-height:1.6;color:#cbd5e1;">
    <b>Private Technical Briefing:</b> How we jumped from our <code>22.376289</code> ensemble baseline down to <b><code>22.311627</code></b> (<b>–0.06466 LB</b>), why direct full-puzzle perturbations stall on upright zero-modes, and how decoupling the <b>Tilted Core ($T$)</b> from the <b>Upright Staircase Fill ($U$)</b> via exact simplicial reduction + MILP (<code style="color:#38bdf8;">fill_rect</code>) unlocked <b>39 rectangular gadget basin jumps in 7.5 minutes</b> (including non-$45^\circ$ packings breaking below the $1/\sqrt{2} \approx 0.7071$ barrier).
  </p>
</div>


---
## 1. Why Incremental Full-Puzzle Tweaks Stall — And How `FTMC + fill_rect` Jumps Basins

When we audited why local moves on full $N \approx 500\text{--}1000$ packings started saturating around `22.316`, two structural bottlenecks stood out:
1. **Upright Flat Zero-Modes Jam Full-Puzzle Quenching:** In a $K \times K$ puzzle with $n \approx 700$ squares, roughly $500+$ squares are axis-aligned ($0^\circ$) upright blocks. Those upright blocks have over $100$ flat zero-energy sliding modes ("rattlers"). If you apply a large kick or loosen a full puzzle by $2\%$ to jump basins, the upright rows drift slightly out of lattice alignment and jam GPU L-BFGS into a high-bloat local minimum before the tilted core can reorganize.
2. **Two-Ribbon Bottleneck Masking:** In a 2-gadget anti-diagonal packing, the puzzle side length is $L = K + \max(f_1, f_2)$. Even if a radical mutation inside a full puzzle improves Ribbon 1 from $f_1 = 0.92 \to 0.88$, Ribbon 2 is still sitting at $f_2 = 0.92$, so the full puzzle's bounding box $L$ does not shrink at all and the move is rejected!

### The 3-Stage Basin-Jumping Architecture
To jump directly between distinct layout basins without upright jamming or second-ribbon masking, we decouple the problem into three stages:

* **Stage 1 — Free Tilted Monte Carlo (`FTMC`) in Isolated $(w, h, \Delta m)$ Gadget Space:**
  Instead of perturbing all squares in a full puzzle, we isolate a single rectangular gadget $(w, h, \Delta m)$ and **strip away 100% of its upright squares**, keeping only the tilted core $T$ ($\sim 15\text{--}120$ tilted squares). On $T$ alone, we apply four macro-mutations:
  1. **$\Delta m - 1 \to \Delta m$ Core Insertion:** Take the tighter tilted core $T$ from $(w, h, \Delta m - 1)$, open a slot along the band axis $\vec{u} = (w, h)/\|(w, h)\|$, and insert $+1$ new tilted square directly inside the lozenge.
  2. **Boundary-Walk Taper Reshaping:** Walk along the tilted/upright interface, converting $1\text{--}2$ adjacent upright squares into tilted squares (growing a corner bulb) while dropping $1\text{--}3$ tilted squares from the opposite taper tip so an extra staircase row of uprights can fit.
  3. **Rational-Slope Non-$45^\circ$ Re-Angling & Shear:** Rotate and shear the tilted band toward rational slopes $\theta \in \{\arctan(1/2)=26.57^\circ,\, 28.07^\circ,\, \arctan(2/3)=33.69^\circ,\, \arctan(3/4)=36.87^\circ,\, 40^\circ,\, 45^\circ\}$.
* **Stage 2 — Exact Simplicial + MILP Upright Staircase Refill (`fill_rect`):**
  Once the mutated tilted core $T_{\text{new}}$ is placed inside $[0, w + f_{\text{try}}] \times [0, h + f_{\text{try}}]$, we **do not guess upright positions**. Instead, `fill_rect(W, H, T_new)` generates:
  - All 4 wall-anchored integer lattices $\{0.5 + i,\, W - 0.5 - i\} \times \{0.5 + j,\, H - 0.5 - j\}$, **plus**
  - All **staircase upright candidates** pushed flush against the exact polygon edges of every tilted square in $T_{\text{new}}$ (up to 4 steps deep).
  - It then applies **exact simplicial corner-rule graph reduction** (resolving $>90\%$ of upright squares in $<0.5\text{ ms}$) followed by per-component **Maximum Independent Set MILP (`scipy.optimize.milp` / HiGHS)** to pack the exact maximum number of non-overlapping upright squares around $T_{\text{new}}$ in $\sim 20\text{ ms}$!
* **Stage 3 — GPU Loosen-Then-Squeeze + Seam-Welding & Void-Teleportation:**
  Because `fill_rect` hands the L40S GPU a crystal-clean seed $T_{\text{new}} \cup U_{\text{exact}}$ with initial overlap $\le 0.022$, batched CUDA L-BFGS (`lbfgs_rect`) + 6-core Sequential LP (`rect_polish`) rapidly quenches the new basin to strict feasibility ($\text{gap} > 10^{-9}$). Improved gadgets are then welded into full $K \times K$ puzzles via **4D Zero-Buffer DP** and **GPU Seam-to-Void Teleportation** (where any colliding square in the shared seam cell $[w_1, w_1+f] \times [h_2, h_2+f]$ is teleported into the largest exact-clearance pocket `exact_holes` near the lozenge tips).


---
## 2. Score Progression (`22.5919` $\to$ `22.3152`) & Per-Band Gain Breakdown

The chart below shows our progression across every stage of this campaign, along with the per-band score improvements ($\Delta \text{Score} = \sum_{n \in \text{band}} \Delta L(n)/\sqrt{n}$) from our `22.376289` ensemble baseline down to **`22.311627`**.


---
## 3. Complete Before & After Gallery of All 39 `FTMC + fill_rect` Gadget Basin Jumps (7.5-Minute Run)

Below are **all 39 rectangular gadgets** $(w, h, \Delta m)$ where our 7.5-minute run of `gpu_ftmc_rect_basin_jump.py` (`FTMC` Tilted-Core Mutation + `fill_rect` Exact Simplicial/MILP Upright Staircase Refill + GPU L-BFGS + Sequential LP Polish) jumped to a tighter basin, sorted from largest bloat drop ($\Delta f = -0.105950$) to smallest:

* **Non-$45^\circ$ Sub-`0.7071` Breakthroughs:** Look closely at **#7 `(6x20+3): 0.746680 -> 0.697181` ($\Delta f = -0.049499$)** and **#8 `(7x22+4): 0.746680 -> 0.703280` ($\Delta f = -0.043400$)**. A $45^\circ$ tilted square has half-extent $1/\sqrt{2} \approx 0.707107$, which acts as a hard floor for standard $45^\circ$ lozenge crops. By re-angling the tilted band to shallower rational angles ($\sim 26^\circ\text{--}34^\circ$) and refilling the staircase uprights via `fill_rect`, both gadgets broke cleanly **below `0.7071`**!
* **Massive Narrow-Ribbon Jumps:** On narrow $w \in \{3, 4\}$ ribbons (**#1 `(3x14+4)` $-0.1060$**, **#2 `(3x14+5)` $-0.0868$**, **#3 `(3x16+5)` $-0.0850$**, **#4 `(3x15+3)` $-0.0693$**, **#5 `(4x21+3)` $-0.0659$**), inserting a tilted square into the $\Delta m - 1$ core or tapering the lozenge tip allowed `fill_rect` to lock an extra upright staircase column along the wall, collapsing the bounding box bloat by $0.05\text{--}0.10$ units!
* **High-Surplus DP Leverage Jumps:** Look at **#28 `(7x21+15): 0.956821 -> 0.947566` ($\Delta f = -0.009254$)** and **#31 `(5x14+8): 0.904622 -> 0.899231` ($\Delta f = -0.005391$)** — those single gadget jumps immediately cascaded through our 4D Zero-Buffer DP to improve full puzzles `n=503, 702, 813, 871`!

### Part A: Jumps #1 to #13 ($\Delta f$ from `-0.105950` to `-0.037941`)


### Part B: Jumps #14 to #26 ($\Delta f$ from `-0.037676` to `-0.014105`)


### Part C: Jumps #27 to #39 ($\Delta f$ from `-0.013348` to `-0.000874`, Including High-Surplus DP Winners `#28 (7x21+15)` & `#31 (5x14+8)`)


---
## 4. Full-Puzzle Before vs. After Gallery (`22.376` Ensemble vs. `22.315` Champion)

When improved rectangular gadgets are composed across the anti-diagonal fault line via **4D Zero-Buffer DP**, **GPU Seam-Welding + Void-Teleportation**, and **Clean-Compartment Ribbon Grafting**, they transform full $K \times K$ competition puzzles. Below are the top 8 full-puzzle improvements between our `22.376289` ensemble baseline and our current **`22.311627`** bank:


---
## 5. Export `submission.csv` (`22.311627`) & Verify Feasibility
