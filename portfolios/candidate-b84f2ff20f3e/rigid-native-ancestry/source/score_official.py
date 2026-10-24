#!/usr/bin/env python3
"""Run the pinned, unmodified official Kaggle v17 metric on submitted strings.

Source downloaded from the public metric/squares-in-squares Kaggle notebook,
currentVersionNumber=17. This wrapper checks its exact SHA256, calls score(),
and captures its per-puzzle outcomes without changing geometry or scoring.

Usage: python scripts/score_official.py artifacts/merged.csv --workers 2
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

import mpmath
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SHA256 = "312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_metric(path: Path):
    actual = digest(path)
    if actual != OFFICIAL_SHA256:
        raise ValueError(f"official metric hash mismatch: {actual}")
    spec = importlib.util.spec_from_file_location("squares_official_metric_v17", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load metric: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def puzzle_hashes(puzzles: dict) -> dict[int, str]:
    """Hash exact decimal row dictionaries; cosmetic changes only lose reuse."""
    return {n: hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            for n, rows in puzzles.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", type=Path)
    parser.add_argument("--metric", type=Path, default=ROOT / "research/official_metric_v17.py")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-n", type=int, default=1000,
                        help="score n=1..N; default is the full competition")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--baseline-report", type=Path,
                        help="reuse exact unchanged puzzles from a hash-verified official report")
    args = parser.parse_args()
    if args.workers < 1 or not 1 <= args.max_n <= 1000:
        parser.error("workers must be positive; max-n must be 1..1000")
    submission_path = args.submission.resolve()
    metric_path = args.metric.resolve()
    report_path = (args.report or submission_path.with_name(submission_path.stem + "-official.json")).resolve()
    details_path = report_path.with_name(report_path.stem + "-details.csv")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    source_hash = digest(submission_path)
    metric = load_metric(metric_path)
    metric.KAGGLE_CORES = args.workers
    # Reading every field as text is essential: float parsing would discard
    # decimal precision before the official interval verifier sees it.
    submission = pd.read_csv(submission_path, dtype=str, keep_default_na=False)
    solution = pd.DataFrame({"id": range(args.max_n), "n": range(1, args.max_n + 1)})
    captured = []
    evaluate_original = metric._evaluate_puzzles_parallel
    cached_results = {}
    cached_hashes = {}
    baseline_provenance = None
    if args.baseline_report:
        baseline_report = args.baseline_report.resolve()
        old_report = json.loads(baseline_report.read_text())
        baseline_csv = Path(old_report["submission"])
        if (old_report.get("metric_sha256") != OFFICIAL_SHA256
                or old_report.get("max_n") != args.max_n
                or not old_report.get("valid")
                or old_report.get("mpmath_version") != mpmath.__version__
                or digest(baseline_csv) != old_report.get("sha256")):
            raise ValueError("baseline report/source/hash/version does not permit reuse")
        old_submission = pd.read_csv(baseline_csv, dtype=str, keep_default_na=False)
        old_puzzles = metric._parse_submission_csv(old_submission.drop(columns=["id"]).to_csv(index=False))
        cached_hashes = puzzle_hashes(old_puzzles)
        cached_results = {r["n"]: (r["n"], r["score"], r["side"], r["reason"])
                          for r in old_report["results"]}
        if set(cached_results) != set(range(1, args.max_n + 1)):
            raise ValueError("baseline report does not cover every target puzzle")
        if digest(baseline_csv) != old_report["sha256"]:
            raise ValueError("baseline source changed while loading")
        baseline_provenance = {"report": str(baseline_report), "report_sha256": digest(baseline_report),
                               "submission": str(baseline_csv), "sha256": old_report["sha256"]}
    reuse_summary = {"reused": 0, "evaluated": 0}
    current_hashes = {}

    def evaluate_and_capture(puzzles, puzzle_ns):
        current_hashes.update(puzzle_hashes(puzzles))
        reused = {n for n in puzzle_ns if n in cached_results
                  and n in current_hashes and current_hashes[n] == cached_hashes.get(n)}
        changed = puzzle_ns - reused
        _, fresh = evaluate_original({n: rows for n, rows in puzzles.items() if n in changed}, changed)
        outcomes = sorted(fresh + [cached_results[n] for n in reused], key=lambda r: r[0])
        # This is the exact same sorted binary64 summation order as official v17.
        total = sum(r[1] for r in outcomes)
        reuse_summary.update(reused=len(reused), evaluated=len(changed))
        captured.extend(outcomes)
        return total, outcomes

    metric._evaluate_puzzles_parallel = evaluate_and_capture
    started = time.monotonic()
    print(f"Scoring {len(submission)} rows for n=1..{args.max_n} with official v17 ({args.workers} workers)", flush=True)
    previous_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="official-metric-", dir=report_path.parent) as temp:
        try:
            os.chdir(temp)
            score = metric.score(solution, submission, "id")
            details_source = Path("/kaggle/working/submission_details.csv")
            if not details_source.parent.is_dir():
                details_source = Path(temp) / "submission_details.csv"
            if not details_source.is_file():
                raise RuntimeError("official metric did not write submission_details.csv")
            shutil.copy2(details_source, details_path)
        finally:
            os.chdir(previous_cwd)
    if digest(submission_path) != source_hash:
        raise RuntimeError("input file changed while scoring; refuse to certify its hash")
    results = [{"n": n, "score": value, "side": side, "reason": reason}
               for n, value, side, reason in captured]
    invalid = [r for r in results if r["side"] is None]
    report = {
        "submission": str(submission_path), "sha256": source_hash,
        "metric": str(metric_path), "metric_version": 17,
        "metric_sha256": OFFICIAL_SHA256, "mpmath_version": mpmath.__version__,
        "pandas_version": pd.__version__, "max_n": args.max_n,
        "rows": len(submission), "puzzles": len(results), "score": score,
        "valid": not invalid, "invalid_count": len(invalid), "invalid": invalid,
        "details": str(details_path), "elapsed_seconds": time.monotonic() - started,
        "results": results, "puzzle_hashes": current_hashes,
        "reuse": reuse_summary, "baseline_provenance": baseline_provenance,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Official v17 score: {score:.15f}; invalid puzzles: {len(invalid)}/{len(results)}", flush=True)
    print(f"Officially evaluated: {reuse_summary['evaluated']}; exact unchanged reuse: {reuse_summary['reused']}")
    if invalid:
        print(json.dumps(invalid[:10], indent=2))
    print(f"Report: {report_path}")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
