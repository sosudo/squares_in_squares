# Saved broad-contact output recovery

Three completed native `contact20` outputs had returned successfully but exceeded the original eight-second inclusive trial budget before certification completed: job 12/n638, job 26/n979, and job 69/n807. This recovery froze the original inputs, outputs, logs, returned arrays, parent poses, original records, and source manifests before any further work. It did not rerun the native optimizer or alter the campaign.

The bounded recovery verified every original byte/geometry hash, parsed each native output against its saved raw array, and used the existing count/finite decoder plus rounding-clearance repair (`2e-9`). The actual repaired geometry then passed the pinned official metric on raw and ordinary-pandas CSV, plus independent interval checks on both representations. All three valid poses were retained. Sequential recovery took 5.44 seconds on one CPU.

| Case | Actual certified side upper bound | Score gain versus frozen 41b46 RAW |
|---|---:|---:|
| 638 | 25.776817768270808328155477185559 | 0.00000670036778565 |
| 979 | 31.784270058546410308984752463955 | 0.00000020364256970 |
| 807 | 28.873684869861180759231321691637 | 0.00000000274172727 |

The gain sum is 0.00000690675208262 against RAW `c57e2d8cd0d1859accf7ba9efdaffa0b059d74083367e3b24d16b767f5015437`. A fresh captured comparison against immutable broad snapshot `gain-0104` found no better same-case candidate, and the captured live results contained no later completed certificate for these cases. The campaign can continue independently; the final merge must still choose the best exact case geometry.

The separate immutable handoff is `artifacts/fq-broad-contact-recovery-v1/`:

- `candidates.json`: SHA256 `fb9ee6d6219945190f8d75eb5c57248455c26d255697e25312f34e2a248fbc16`.
- `donors.npz`: SHA256 `f708efbcbfddc9a8492306d07ac62ee606a85bf4bad0af64082c3dd1234337ea`.
- `results.json`: SHA256 `5f16897f2d5c75ec692025e6f50d4eb2548a28bd01d3614772af438238e22c34`.
- `freeze.json`, `inputs/`, `source/`, and `comparison/` preserve exact ancestry and executed certification source bytes.

No canonical portfolio, remote resource, submission, or submission policy was changed. Native source remains Evan Daniel's MIT-licensed commit `659ee62e4a9d39542a1146e8b011cc3ab6407ede`; the native executable was not invoked by recovery. The official metric pin remains `312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733`.
