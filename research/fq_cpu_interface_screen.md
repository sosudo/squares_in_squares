# Finite interface screen of the second CPU FQ archive

The 960 certified poses from the two-lane CPU follow-up did not justify another
large GPU composition pass. Their corner profiles vary, but the finite screen
below found no newly compatible join with scalar headroom against the current
portfolio. This conclusion concerns whole donors, the stated partner palette,
and the three existing separator angles. It does not cover arbitrary crops,
other separator angles, or other macro layouts.

The exact union is `artifacts/fq-cpu-followup-analysis-v2/donors.npz`, SHA256
`cae35664bfe31c66bd8e3724eea222084809a3ddb6e79d3504f255db91dc89e4`.
The unchanged raw/default-pandas and independent geometry certificates were
audited by `analyze_fq_cpu_followup.py`. No new geometry certificate is claimed
by this screen. The separate minimum-only chain replay improved n807 and n865
by a combined `3.79230726594e-8`; those gains are already in the canonical
SAFE checkpoint `2e6e39f36a7cdf54416fd3241b2daa2d161997f235f93961f945751f0510b958`,
scoring `22.301061591170022`.

## Concrete collision and optimistic capacity

The saved n865 chain joins a 20×8+12 block and an 8×20+12 block with a one-row
buffer. Removing that buffer would produce a 28×28 nominal container with
24 surplus squares, hence n808 at side 28+f. The incumbent n808 side is
28.88371345442487. At the frozen input minimum f=0.8736854096406326, this has
about 0.010028 side headroom, provided the unbuffered interface is valid.

The actual old pair has minimum floating SAT separation gap −0.8717407812.
Thus the scalar headroom alone is insufficient. Among the new poses below
the n808 cost cutoff, even the most favorable support-selected pair has gap
−0.8491110283. This is a direct overlap measurement, not an interval proof.

## Complete finite profile lookup

The broader second pass inspected all 960 source arrays. Of these, 816 fit
their declared 8×20+12 family with f<0.999999, producing 6,528 D4 orientations
and 62 joint corner-bin signatures. Sixty signatures were absent from the
two frozen reference signatures. At 30°, the best outgoing bin changes
29→28; at 45°, 26→25; at 60°, 23→22. Incoming bins also improve. The strongest
support-selected unbuffered self-pair still overlaps, with gap −0.7487267449.

The lookup retains the lowest f for each exact `(w,h,BR[3],TL[3])` signature.
It compares these states to the independently audited 502-pose partner bank,
SHA `e961ca3ac4b18d6e0ee2460cf819fef3da4f718f60c2dde7a32f26392bbb1e2c`.
That bank preserves every prior selected-chain source identity and every
417 canonical-family scalar minimum at its frozen construction time.
The fitting partners yield 1,832 oriented states.

For a new-first join, the filter requires
`new_BR <= partner_TL < min_old_BR`. For a new-second join it requires
`max_old_TL < partner_BR <= new_TL`. The old extrema include all old D4
orientations of the required shape. A qualifying pair must also have
`k >= max(w1+w2,h1+h2)`, `N=k*k+12+partner_surplus <= 1000`, and side
`k+max(f1,f2)+5e-8` strictly below that N's incumbent. All fitting k≤31 and
the 30°/45°/60° separator tests are included.

No pair passed both the newly compatible profile condition and the scalar
headroom condition. Therefore no exact two-block SAT admission or full
construction was attempted. The 62-state reduction intentionally answers
the discrete-profile question; it does not establish equivalence of all
continuous collision geometries sharing one bin signature.

## Reproduction and evidence

```bash
OPENBLAS_NUM_THREADS=1 timeout 90 .venv/bin/python experiments/assess_fq_cpu_interfaces.py \
  --old artifacts/fq-cpu-followup-job-v3/inputs/reference.npz \
  --new artifacts/fq-cpu-followup-analysis-v2/donors.npz \
  --portfolio artifacts/current-best-portfolio.json \
  --max-bloat 0.999999 --out artifacts/fq-cpu-followup-interface-assessment-REPLAY
OPENBLAS_NUM_THREADS=1 timeout 90 .venv/bin/python experiments/screen_fq_cpu_interface_pairs.py \
  --profiles artifacts/fq-cpu-followup-interface-assessment-REPLAY/profile_records.json \
  --out artifacts/fq-cpu-followup-interface-pairs-REPLAY
```

The executed broad assessment is in
`artifacts/fq-cpu-followup-interface-assessment-v2`; the hash-guarded lookup
replay is in `artifacts/fq-cpu-followup-interface-pairs-v3`. They completed
in 5.67 and 2.58 seconds on one CPU. The reports bind the exact source
archives, current SAFE official report, helper source hashes and executed
code. Earlier v1 evidence preserves the narrower n808 cost cutoff and v2
pair evidence preserves the initial lookup implementation. All input poses
remain retained; no GPU allocation or competition submission resulted.
