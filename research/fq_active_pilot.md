# Independent smooth-separator CPU optimizer

Evan Daniel's public MIT-licensed `fq` solver is retained under `vendor/fq` from [evand/square-packing](https://github.com/evand/square-packing/tree/659ee62e4a9d39542a1146e8b011cc3ab6407ede/search/packer), commit659ee62e4a9d39542a1146e8b011cc3ab6407ede. Original Rust source files, Cargo dependency lock, file hashes and license are preserved. The local Cargo manifest selects only the fq executable; no Rust algorithm changes were made.

The solver introduces smooth separating-line variables and uses an augmented Lagrangian, then contact-based sequential linear programming with corner-contact branch search. This supplies a different local optimizer from the current CUDA SAT loss and fixed-angle rectangle LP. Its optional rounded-square continuation is only a search stage; every exported object is checked as actual unit squares.

Build with Rust/Cargo:

```sh
cargo build --release --locked --manifest-path vendor/fq/Cargo.toml --bin fq
```

The cloud workspace lacked Rust, so an official SHA-verified rustup installer provisioned the minimal stable toolchain under `/tmp/squares-rustup` and `/tmp/squares-cargo` without changing shell startup files. Both original-native and portable-vendored release builds succeeded with Rust1.99.1. The pilot used the original-native executable; subsequent trials use the portable vendored build. Binaries and build products are not committed.

`experiments/fq_active_pilot.py` converts radians to fq's degree input, preserving rectangular dimensions as `(s+dx,s+dy)` with one zero offset. Round-only centre dilation supplies2e-9 floating clearance after decoding; unit-square angles and sides are unchanged. Every retained pose then passes the pinned official metric on raw decimal rows and ordinary pandas numeric roundtrip. The five-square diamond and a seven-square rectangular extension passed actual positive controls, shrinking their deliberately expanded inputs back to the expected bloat1/sqrt(2). Evidence is under `artifacts/fq-preflight/`.

The bounded active pilot ran51trials on17current chain component types, using plain contact polish, a small kick, and rounded-square continuation. It retained35officially certified poses, with31strict improving trials across15types. Largest best-per-type bloat reductions included9x21+8:0.0013587072,5x18+11:0.0011235012,20x9+12:0.0008544185,8x21+8:0.0006909874,8x20+7:0.0006740221. These are component gains, not a competition-score improvement.

Frozen outputs: `artifacts/fq-active-v1/donors.npz`, SHA2569b6e1b7ca049ea312522b4c4cda0e881de67a3e162dafacc6634f5227dd45ebc;17-key best bank SHA25667878f469b59b4cfd802fd264d0df2d78de7929af9b548d163149c648044f766. The original incumbent bank has SHA256e183e6bbf16584b836907748b4d08a28af75b648c585e200019b66cadfa88556. Full source/binary bindings, options, exact outputs and individual raw/roundtrip certificates are in manifest.json, results.json and analysis.json. The donor archive is read-only after completion.

The35poses are handed to the broader GPU composer. Separate bounded CPU runs will test full-puzzle polish and refinements from the213gentle alternative poses. No submission is authorized unless the full certified portfolio score is below22.3.
