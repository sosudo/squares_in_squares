#!/usr/bin/env python3
"""Deterministically add tiny centre clearance to long-decimal packing cases.

Only centres move; angles and unit side lengths are unchanged. This creates a
new candidate which must still pass raw and numeric-roundtrip validation.
The helper is stdlib-only so the same implementation can run on Kaggle.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
from pathlib import Path

DEFAULT_FACTOR = "1.00000000001"
PRECISION = 100
LONG_DECIMAL_LENGTH = 50


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def make_transport_safe(source: Path, target: Path, factor: str = DEFAULT_FACTOR) -> dict:
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve():
        raise ValueError("source and target must differ; preserve the raw candidate")
    source_hash = file_sha256(source)
    with source.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        if fieldnames is None or not {"id", "n", "square_id", "x", "y", "angle"}.issubset(fieldnames):
            raise ValueError("missing submission columns")
        rows = list(reader)
    selected = {int(row["n"]) for row in rows
                if any(len(row[key]) > LONG_DECIMAL_LENGTH for key in ("x", "y", "angle"))}
    changed_rows = 0
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        multiplier = Decimal(factor)
        if not multiplier.is_finite() or multiplier <= 1:
            raise ValueError("factor must be a finite decimal greater than one")
        for row in rows:
            if int(row["n"]) in selected:
                row["x"] = str(Decimal(row["x"]) * multiplier)
                row["y"] = str(Decimal(row["y"]) * multiplier)
                changed_rows += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if file_sha256(source) != source_hash:
        raise RuntimeError("source changed during conversion")
    temporary.replace(target)
    return {"source": str(source), "source_sha256": source_hash,
            "output": str(target), "sha256": file_sha256(target),
            "factor": factor, "decimal_precision": PRECISION,
            "decimal_rounding": "ROUND_HALF_EVEN", "length_threshold": LONG_DECIMAL_LENGTH,
            "selected_cases": sorted(selected), "selected_count": len(selected),
            "changed_rows": changed_rows, "rows": len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--factor", default=DEFAULT_FACTOR)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = make_transport_safe(args.source, args.target, args.factor)
    report = args.report or args.target.with_suffix(".transport-transform.json")
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "selected_cases"}, indent=2))


if __name__ == "__main__":
    main()
