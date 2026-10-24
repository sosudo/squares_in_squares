# Private Kaggle CPU FQ readiness

The portable native FQ solver ran successfully in the private CPU notebook
`sos54352/squares-fq-cpu-ready-10ec7cf773ac/1`. This was a readiness check, not a
new packing search. No accelerator, Internet access, or competition submission
was requested. The explicit Kaggle server limit was 300 seconds, with a
180-second worker supervisor and a 30-second limit for each native control.

The actual machine had four available CPUs, a cgroup CPU allowance of
`400000 100000` (four cores), 30 GiB of cgroup memory, glibc 2.39, Python 3.13.15,
and no NVIDIA device. The package's single-thread settings were active.
Native n=5 and n=65 controls took 0.0026 and 0.0354 seconds respectively. The
worker took 4.35 seconds and its supervisor 4.68 seconds, excluding Kaggle
startup. Both outputs passed the unchanged official raw, 17-digit pandas,
ordinary pandas, and independent interval gates. An intentionally overlapping
packing failed all the appropriate gates.

This proves one private CPU allocation was accepted. The supported quota API
exposes GPU and TPU usage, but no remaining CPU allowance or CPU concurrency
limit. Those limits remain unknown; this result does not establish unlimited
parallel notebook execution.

## Exact artifacts

The frozen job is `artifacts/fq-cpu-readiness-job-v2`. Its 662,241-byte
`readiness.py` has SHA-256
`a43315643e2e1475212d3cffbdea88e278100493e29dae2a60cb2448c0d48170`.
The saved remote source was independently downloaded through the authenticated
SDK and matched that hash. The runtime source hash is
`9a51c452c8a3da2ffe0ff2a24f8fc99c435ff78a4b3bc89faf36b6d241210d38`.

The portable binary is 1,118,480 bytes and has SHA-256
`10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d`.
It is x86-64 GNU/Linux ELF, uses no native-only Rust target flags, and requires
at most glibc 2.35. Its direct shared libraries are `libgcc_s.so.1`, `libm.so.6`,
and `libc.so.6`. The exact binary is published as the private output
`fq_portable`, so a later CPU notebook can attach this notebook and verify the
binary hash before execution. A version suffix alone is not a content pin.

Downloaded evidence is under `artifacts/fq-cpu-readiness-remote-v1`:

- `verified_readiness.json`: checked resource evidence, source identity, and
  certificate-to-array bindings.
- `download_receipt.json`: exact private version and hashes of all nine
  downloaded output files.
- `readiness_report.json`: native reports, complete positive and negative
  certificates, timings, and hardware observations.
- `package_manifest.json`: every packaged file hash, compiler and source
  provenance, license inventory, and time limits.
- `fq_portable`, `certified_controls.npz`, both native outputs and logs, and
  `supervisor.json`.

The remote output arrays and logs were checked against their report hashes;
they were not redundantly recertified after download. The remote worker ran
the unchanged certified helpers, whose exact bytes are part of the package.

## Rebuilding the readiness package

`scripts/build_fq_cpu_readiness_job.py` packages the existing verified portable
binary, pinned upstream native sources, Python validation helpers, and two
control inputs. It compresses the whole package with XZ; there is no remote
compiler or dependency download. Ninety exact files fit in one notebook, so
split binary exports are unnecessary.

The FQ source is Evan Daniel's MIT-licensed `evand/square-packing`, commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`, as recorded in
`vendor/fq/SOURCE_MANIFEST.json`. All pinned Rust sources and the dependency lock
are unchanged. The package includes the FQ license, licenses for all 35 crates
in the x86-64 build dependency graph, and the Rust compiler's MIT/Apache texts.
Thirteen WASM-only lock entries are documented as outside this target graph.
Cached crate archives are checked against Cargo.lock before their notices
are collected. The original rustc 1.99.1 fingerprint and ELF requirements are
also preserved.

The builder currently uses the verified workspace build under
`/tmp/squares-fq-portable-target`, its registry/toolchain cache, and the exact
Rust license preparation under `artifacts/fq-cpu-readiness-preparation`.
These are explicit local prerequisites. The underlying source rebuild command
is `cargo build --release --locked --manifest-path vendor/fq/Cargo.toml --bin fq`;
byte-identical output also depends on the recorded toolchain and build
environment. A different binary is rejected by this concrete readiness builder.

Use a fresh directory; the builder refuses to replace an existing job:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/build_fq_cpu_readiness_job.py --out artifacts/fq-cpu-readiness-new
FQ_CPU_OUTPUT_ROOT=/tmp/fq-readiness-replay \
  .venv/bin/python artifacts/fq-cpu-readiness-new/readiness.py
.venv/bin/python -m unittest tests.test_fq_cpu_readiness -v
```

The three focused regressions prove archive tampering and member tampering
are rejected before binary execution, and native timeout cleanup reaps the
child process. The complete frozen local replay also passed the actual native
and geometry controls before the remote run. The v1 package and replay remain
preserved; v2 only added the worker-exit timeout race guard. The package's
individual file hashes and controls are unchanged; ZIP timestamps can differ
between builds.

The readiness run used:

```sh
.venv/bin/python scripts/kaggle_cli.py kernels push \
  -p artifacts/fq-cpu-readiness-job-v2 -t 300
```

Credentials are supplied by the existing CLI wrapper and are never packaged.
Any larger search needs its own explicit budget, source and input hashes,
retention policy, and unchanged official admission gates.
