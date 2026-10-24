# Complementary private CPU FQ campaign

The first remote search is the private, offline CPU notebook
`sos54352/squares-fq-cpu-complementary-v1/1`. It requests no accelerator and
uses four single-thread workers, matching the four-core quota measured by the
readiness notebook. Search scheduling is bounded at 1,140 seconds, the whole
loader/worker/recovery process at 1,200 seconds, and Kaggle's explicit server
limit at 1,500 seconds. Only one such CPU search was authorized and launched.
Remaining CPU allowance and notebook concurrency are still unknown.

The frozen job is `artifacts/fq-remote-cpu-job-v1`, with a 348,815-byte source
whose SHA-256 is
`d035ab2a5ca23bd5c4eff63f9904c3276670aec7d95d5bcccb5113a55d9f38ed`.
All 105 embedded file hashes and the saved remote source were verified. The
notebook attaches `sos54352/squares-fq-cpu-ready-10ec7cf773ac/1`, but requires
both the exact binary hash and the exact readiness-manifest hash; the attachment
version label is not treated as a content pin. Sources, FQ/Rust/dependency
licenses, and the generated scheduler are preserved in the package.

The four canonical target families and their starting excesses are:

| Family | Frozen orientation-fair excess |
| --- | ---: |
| 5×18+11 | 0.9369086730295173 |
| 6×22+16 | 0.9777836180356161 |
| 8×20+12 | 0.8743104660422176 |
| 10×23+14 | 0.8617520057444494 |

Both orientations start from the same family minimum. Forty-two compact input
variants passed the full official and independent gates. They include the
minima and a deterministic spread of distinct geometric buckets within 0.005
excess. Their source arrays, archive hashes, reflection operations, and complete
certificates are in the input proof. Complete original donor archives remain
at their existing immutable paths. This campaign complements the local
7×21+15 and 9×22+16 search; its seed sequence starts at 12,124,001.

The geometry method is the unchanged productive wrapper: forty free squares,
aspect amplitude 0.6, sixteen exact-return steps, hold factor 1.001, and either
a circular or contact-connected neighborhood. Global release uses the original
ALM45/polish100/flip16 settings. The two stages share twenty seconds; the local
stage gets at most twelve. Exactly every fourth visit to each oriented type
starts from its frozen initial pool, cycled by complete geometry SHA. Improved
outputs cannot replace that pool or alter its ordering.

`experiments/fq_remote_cpu_search.py` installs a stronger stage hook before the
audited scheduler is generated. Each native command has its own process group;
the stage deadline includes certification and retention. The hook requires
the exact zero-aspect trace, unchanged official raw/17-digit-pandas/default-
pandas checks, and independent interval checks. It writes every certified
stage to an immutable array/proof pair before release can start. The original
0.002 quality band determines whether search continues from that pose;
certified wider poses remain in the complete output archive.

The whole-process supervisor pauses and stops only its owned descendants if
needed. Complete immutable stage pairs are authoritative during final recovery;
orphan arrays are ignored and inconsistent complete pairs fail closed. Final
compact outputs are in `campaign/remote-certified/`: `donors.npz`,
`best_bank.npz`, `provenance.json`, and `summary.json`. Raw native outputs and
logs, immutable stage pairs, ordinary campaign checkpoints, and full source
provenance also remain available. Component improvements do not establish a
competition score gain; composition and final complete-CSV validation are
separate.

Before launch, an actual frozen-loader local control ran eight trials across
all eight orientations, four circle and four contact moves. It retained eleven
fully certified stages, including five outside the search band, with zero
orphan pairs. All native input bytes matched their recorded parents; all soft
returns reached exactly zero. It completed in 23.27 seconds on one active CPU.
A second control exercised the actual four-worker executor with one native
task to respect local CPU allocation and exited cleanly in 9.22 seconds.
Neither control established an improvement. Three new retention/deadline
regressions plus two immutable-start regressions passed. Independent review
is frozen in the job's `independent_source_review.json`.

The initial remote log sample confirmed actual execution and sixteen immutable
starts among 79 completed records. It contained 29 search-eligible certified
records, 49 certified wider records, and one bounded stage timeout. No strict
family improvement was observed in that early sample. Final results must be
read from the completed hash-bound output archive.

The authorized launch command was:

```sh
.venv/bin/python scripts/kaggle_cli.py kernels push \
  -p artifacts/fq-remote-cpu-job-v1 -t 1500
```

No credentials are embedded and this code contains no competition submission.
