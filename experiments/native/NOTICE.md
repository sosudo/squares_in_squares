The native packer is derived from Evan Daniel's MIT-licensed source at
https://github.com/evand/square-packing, commit
`659ee62e4a9d39542a1146e8b011cc3ab6407ede`, original `src/main.rs`.
The complete license is retained in `LICENSE`.

`packer_hop_cooled.rs` is the exact source used for the bounded weighted
hot/cool n335 experiment. Its source SHA256 is
`6c9c02d5af27c9ebeb99d52d1d64e16d0dcae16d26a9702b88b8b700f1c24dc2`.
Modifications add raw-state telemetry, a four-operator weighted proposal draw,
a decision-time cooling schedule, and focused controls. Physical energy,
gradients, neighbor lists and L-BFGS remain unchanged from the public source.
The adjacent provenance JSON records the intermediate telemetry parent and
intentional search changes; the intermediate source and diff remain in the
experiment artifacts.

This standalone source uses only the Rust standard library. To rebuild:

```sh
rustc -O experiments/native/packer_hop_cooled.rs -o /tmp/packer_hop_cooled
rustc --test experiments/native/packer_hop_cooled.rs -o /tmp/packer_hop_cooled_tests
/tmp/packer_hop_cooled_tests
```

A matching source does not guarantee an identical binary across compiler or
build-option changes. The executed binary hash, exact build command and live
controls are recorded in `artifacts/packer-hop-cooled-v1-source/`.
These are search proposals; packing admission still requires the independent
geometry and unchanged official CSV validation gates.
