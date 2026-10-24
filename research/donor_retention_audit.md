# Historical donor retention audit

The bounded audit found a useful omitted pose: two copies of an older
`8×20+7` geometry improve puzzle 798 by **0.00004854595847** against the
newest certified `c766288f…` portfolio. The candidate passed independent
interval checks and official v17 checks on both original decimal strings
and an ordinary pandas read/write roundtrip. The second emitted case, 993,
ties the newer GPU result and contributes no incremental gain.

The immutable candidate file is
`artifacts/omitted-donor-pairs-v1/candidates.json`, SHA256
`646d92ae77671c0c1a3f3ccbba347783b8eda8191e58932beca79a7402263fe5`.
Portfolio merging and final whole-file transport certification belong to
the frontier agent. This experiment made no submission.

## Inventory and correction

The frozen catalogue covers 2,882 archive paths representing 2,075 distinct
NPZ byte hashes. The inspected GPU descriptor is
`artifacts/composition-consolidated-inputs-v1.json`, SHA256
`cd809698608f4d74c5a7694ac159a0557f08397007b5df664d8583685633ee9f`:
7,276 attached donor arrays plus the 1,000-case `9c8cccde…` baseline.
The restored original 51 active variants were already attached and are
not a new omission from this audit.

The corrected inventory contains 14,692 distinct binary64 arrays including
baseline-only geometries, 8,001 retained exact array hashes, and 943 retained
canonical types. It identifies 6,204 omitted geometry/type combinations,
including **26 rectangular types absent from these pinned inputs**. These
are coverage discoveries, not claims of new mathematical packing records.

The initial inventory included the complete CSV in geometry coverage but
forgot baseline-only type labels and partner entries. That undercounted
retained types as 739 and incorrectly labeled 13 square types as novel.
`inventory-corrected/` fixes this, leaving the original search evidence
unchanged. Two regression tests cover baseline-only type/partner inclusion
and preservation of existing archive provenance. The original bounded
partner sample was not rerun; baseline-only extra partners therefore remain
outside its search coverage.

Identity uses exact little-endian binary64 array hashes and exact hashes
after sorted translated D4 transformations. No scalar-excess equality or
coordinate rounding establishes identity. Floating transformation noise
can conservatively retain aliases. Rounded `1e-6` buckets were used only
to select a manageable diverse sample, never to establish equivalence or
validity.

## Priorities supported by the inventory

| Bank | Omitted geometry/type combinations | Newly covered types | Evidence |
| --- | ---: | ---: | --- |
| `fq-multiscale-v1/snapshot-00099/donors.npz` | 508 | 0 | Contains the certified puzzle-798 winner |
| Initial `night_seed_variants.npz` | 156 | 26 | 12 poses have optimistic two-block opportunities; all 26 selected type representatives pass strict checks |
| Initial `night_seed_gadgets.npz` | 78 | same 26 | Six optimistic two-block opportunities; overlaps the variants' type coverage |
| `fq-local-soft-v1/all-strict/donors.npz` | 820 | 0 | 578 optimistic opportunities; intentionally deferred to another GPU partition |
| `fq-bottleneck-final-handoff-v1/donors.npz` | 646 | 0 | 563 optimistic opportunities; intentionally deferred to another GPU partition |

Rows can overlap geometrically and must not be summed. The two large full
archives are deliberately deferred because the current 7,276-donor bundle
already expands to 66,688 orientations near its uint32 donor-ID limit.
They should be searched in a separate partition, not appended to the
frozen bundle. The 26 night-seed types are separate coverage worth retaining.
For example, `5×14+8` and `4×5+4` have optimistic pair gains around
0.00055246 and 0.00010075 respectively; neither became a certified new
whole-puzzle win in this partial run.

## Strict selection and bounded pair screen

The selector independently certified **153 of 153** selected omitted poses
with raw/default-pandas interval checks and official checks. It searched
120 promising omitted poses against up to three distinct retained
geometries in each of 31 scalar-feasible types: 79 retained partners total.
Every emitted pair contained an exact omitted geometry. The original
39-type metadata is corrected to 26 in `handoff/corrected-checks.json`,
reusing certificates only for byte-identical arrays.

The existing exact-pair implementation was reused unchanged. One worker
stopped at 296.25 seconds within its 300-second supervisor budget. Its
positive control passed. Coverage was 6,405,120 ordered pose/mode pairs
and 14,564,864 container screens, yielding 118,080 promising jobs. It
completed 79,778 cross-block SAT tests and 3,777 whole-layout builds before
the deadline. The result is explicitly **partial**, not an exhaustive
search of all omitted geometry or all retained partners.

Both outputs passed complete independent and official raw/default-pandas
certification. `latest-baseline-comparison.json` binds the comparison to
the newer complete `c766288f…` interval report: 798 remains strictly better,
993 does not. The reused pair script's generic source string mentions
N±1 donors, but this run's actual source is the historical multiscale bank;
its pinned source hashes and per-array records are authoritative.

## Why the puzzle-798 pose matters

The winning array hash is
`0065689b4ce5998d2f3cad14cdbe75018b00df6783ec87869a5c238766d63ae2`.
It comes from multiscale snapshot 99's full donor archive, SHA256
`95d5b73b8a36cea9ea540d5ef0eb9a999d4094b633fa9acb307588bd9fbf4962`.
It is also preserved byte-identically in several later input snapshots.
Two appropriately reflected/transposed copies form an unbuffered mode-0
join inside a 28-base square, with certified side
`28.759627229519353049615660845819850243890105102045005954960849`.

The omitted pose has excess 0.7596271436361022, slightly worse than the
retained minimum 0.7596264938635606. A controlled substitution inspected
all 189 retained matching-type poses. Only two had enough scalar room
to tie the winning side. All 64 role-oriented/reflected pairs of those
two failed cross-block SAT with the successful mode and container held
fixed. Thus scalar-minimum retention loses useful boundary geometry for
this specific template. This does not prove that every other possible
composition requires the omitted pose. The 1.30-second control is frozen
in `n798-attribution/report.json`.

## Handoff and reproduction

`artifacts/donor-retention-audit-v1/handoff/priority-donors.npz` contains
the 26 new type representatives plus the winning older `8×20+7` pose:

```
bf811e07cee3f3cfc0086f4feca82b84531684b514b8ee2fc017e03ca53334d7
```

`priority-donor-proofs.json` binds all 27 arrays to original archives and
their complete strict certificates. `report.json` binds corrected labels,
the original audit/validation hashes, and verbatim retained source notices.
The 26-type-only archive hash is
`d6651d30874cc9501a79e0aadec61f7182685810ef3e109f0cc02cb7b997d700`.

The exact search command, all source snapshots, pinned inputs, positive
control, final coverage, and supervisor result are under
`artifacts/omitted-donor-pairs-v1/`. Reproduction helpers are
`experiments/audit_donor_retention.py`, `prepare_omitted_donors.py`,
`finalize_donor_retention.py`, and `donor_retention_attribution.py`.
All source licenses and notices were preserved unchanged in
`inventory-corrected/source-notices/`.
