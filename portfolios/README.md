# Reproducible submitted portfolios

Each directory retains a small source-backed exporter, its input hashes and notices, validation evidence, and a submission receipt. Full CSVs are generated rather than committed. API keys are never needed to reconstruct these public-source portfolios.

Run an export script from a new empty output directory using the project Python environment. It downloads pinned public datasets/certificates, verifies their hashes, reproduces the chosen coordinates and clearance transform, then asserts the final CSV hash. Internet access and mpmath1.3.0 are required. Source-specific licenses and attribution are retained under vendor/notices and inside export_manifest.json.

A local score is not a Kaggle result. Receipts explicitly distinguish pending/scored status and actual public score/rank. The user requests an hourly submission only when an improved validated candidate exists, within the ten-per-day competition cap.
