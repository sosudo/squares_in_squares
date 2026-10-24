#!/usr/bin/env python3
"""Independent interval-arithmetic validator for unit-square packing submissions.

The geometry and score follow the public v17 competition metric mirrored at
https://github.com/tiagocabo/kaggle-squares-in-squares/tree/main/metric .
This implementation preserves submitted decimals and does not accept overlaps
within a numerical tolerance. It is stricter than a floating-point smoke test.

Usage: python scripts/validate_submission.py artifacts/baseline.csv --workers 2
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from multiprocessing import Pool
from pathlib import Path
import re
import sys
from typing import Sequence

import mpmath as mp
import numpy as np

DECIMAL = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
REQUIRED = {"id", "n", "square_id", "x", "y", "angle"}
PRECISIONS = (50, 100, 200, 500)


@dataclass(frozen=True)
class Square:
    x: str
    y: str
    angle: str


def decimal(value: str) -> str:
    value = value.strip()
    if len(value) > 1000 or not DECIMAL.fullmatch(value):
        raise ValueError(f"invalid decimal literal {value[:60]!r}")
    if not math.isfinite(float(value)):
        raise ValueError("nonfinite or out-of-range coordinate")
    return value


def read_submission(path: Path, max_n: int = 1000) -> dict[int, list[Square]]:
    """Require the complete row/id structure, preserving exact decimal text."""
    puzzles: dict[int, dict[int, Square]] = {}
    row_ids: set[int] = set()
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError(f"required columns: {sorted(REQUIRED)}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("duplicate column names")
        for line, row in enumerate(reader, 2):
            try:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError("wrong number of fields")
                rid, n, sid = int(row["id"]), int(row["n"]), int(row["square_id"])
                if rid in row_ids:
                    raise ValueError(f"duplicate row id {rid}")
                row_ids.add(rid)
                if not 1 <= n <= max_n:
                    raise ValueError(f"n={n} outside 1..{max_n}")
                if not 0 <= sid < n:
                    raise ValueError(f"square_id={sid} outside 0..{n - 1}")
                group = puzzles.setdefault(n, {})
                if sid in group:
                    raise ValueError(f"duplicate square_id {sid} for n={n}")
                group[sid] = Square(*(decimal(row[k]) for k in ("x", "y", "angle")))
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f"line {line}: {exc}") from exc
    missing = set(range(1, max_n + 1)) - puzzles.keys()
    if missing:
        raise ValueError(f"missing puzzles: {sorted(missing)[:20]}")
    for n, squares in puzzles.items():
        if len(squares) != n:
            raise ValueError(f"n={n}: expected {n} squares, got {len(squares)}")
    return {n: [squares[i] for i in range(n)] for n, squares in sorted(puzzles.items())}


def _iv_min(values):
    return mp.iv.mpf([min(v.a for v in values), min(v.b for v in values)])


def _iv_max(values):
    return mp.iv.mpf([max(v.a for v in values), max(v.b for v in values)])


def _fraction_decimal(value: Fraction, upper: bool, places: int = 60) -> str:
    """Serialize outwards, so JSON round trips cannot narrow a certificate."""
    scale = 10**places
    units = value.numerator * scale // value.denominator
    if upper and Fraction(units, scale) < value:
        units += 1
    sign = "-" if units < 0 else ""
    whole, fraction = divmod(abs(units), scale)
    return f"{sign}{whole}.{fraction:0{places}d}"


def _endpoint_text(value, upper: bool) -> str:
    sign, mantissa, exponent, _ = value._mpi_[0]
    exact = Fraction((-1 if sign else 1) * mantissa) * Fraction(2)**exponent
    return _fraction_decimal(exact, upper)


def _geometry(squares: Sequence[Square], dps: int):
    mp.iv.dps = mp.mp.dps = dps
    angle_cache = {}
    result = []
    half = mp.iv.mpf("0.5")
    for square in squares:
        if square.angle not in angle_cache:
            angle = mp.iv.mpf(square.angle)
            c, s = mp.iv.cos(angle), mp.iv.sin(angle)
            h = half * (abs(c) + abs(s))
            angle_cache[square.angle] = (c, s, h)
        c, s, h = angle_cache[square.angle]
        x, y = mp.iv.mpf(square.x), mp.iv.mpf(square.y)
        result.append((x, y, c, s, h))
    return result


def _candidate_pairs(geometry):
    """Outward-rounded AABBs: excluded pairs are provably separated."""
    bounds = []
    for x, y, c, s, h in geometry:
        values = ((x - h).a, (y - h).a, (x + h).b, (y + h).b)
        bounds.append([
            math.nextafter(float(value), -math.inf if k < 2 else math.inf)
            for k, value in enumerate(values)
        ])
    bounds = np.asarray(bounds)
    order = np.argsort(bounds[:, 0], kind="stable")
    sorted_bounds = bounds[order]
    for pos, (left, bottom, right, top) in enumerate(sorted_bounds):
        end = np.searchsorted(sorted_bounds[:, 0], right, side="right")
        if end <= pos + 1:
            continue
        tail = sorted_bounds[pos + 1:end]
        matching = np.flatnonzero((tail[:, 1] <= top) & (tail[:, 3] >= bottom))
        for offset in matching:
            yield int(order[pos]), int(order[pos + 1 + offset])


def _separated_interval(a, b):
    """True separated, False overlapping, None unresolved at this precision."""
    xa, ya, ca, sa, _ = a
    xb, yb, cb, sb, _ = b
    dx, dy = xb - xa, yb - ya
    # The projection radius sum on any edge normal equals this expression.
    # cos/sin differences use products to avoid reparsing/trig calls per pair.
    cos_delta = ca * cb + sa * sb
    sin_delta = sa * cb - ca * sb
    radius = (1 + abs(cos_delta) + abs(sin_delta)) * mp.iv.mpf("0.5")
    unresolved = False
    for c, s in ((ca, sa), (-sa, ca), (cb, sb), (-sb, cb)):
        gap = abs(dx * c + dy * s) - radius
        if gap.a >= 0:
            return True
        if gap.b >= 0:
            unresolved = True
    return None if unresolved else False


def check_pair(a: Square, b: Square):
    """Certify nonoverlap of two exact decimal-defined unit squares."""
    if Fraction(a.angle) == 0 and Fraction(b.angle) == 0:
        return max(abs(Fraction(a.x) - Fraction(b.x)),
                   abs(Fraction(a.y) - Fraction(b.y))) >= 1
    for dps in PRECISIONS:
        geometry = _geometry([a, b], dps)
        result = _separated_interval(*geometry)
        if result is not None:
            return result
    return None


def validate_puzzle(n: int, squares: Sequence[Square]) -> dict:
    if len(squares) != n:
        raise ValueError(f"n={n}: wrong square count")
    if not squares:
        raise ValueError("empty puzzle")
    # Public API callers receive the same numeric validation as CSV callers.
    for square in squares:
        for value in (square.x, square.y, square.angle):
            decimal(value)
    geometry = _geometry(squares, PRECISIONS[0])
    zero_angles = [Fraction(s.angle) == 0 for s in squares]
    rational_xy = {}
    intervals_checked = exact_checked = 0
    for i, j in _candidate_pairs(geometry):
        if zero_angles[i] and zero_angles[j]:
            for k in (i, j):
                if k not in rational_xy:
                    rational_xy[k] = Fraction(squares[k].x), Fraction(squares[k].y)
            xi, yi = rational_xy[i]
            xj, yj = rational_xy[j]
            result = max(abs(xi - xj), abs(yi - yj)) >= 1
            exact_checked += 1
        else:
            result = _separated_interval(geometry[i], geometry[j])
            intervals_checked += 1
            if result is None:
                result = check_pair(squares[i], squares[j])
                # check_pair escalates global interval precision.
                mp.iv.dps = mp.mp.dps = PRECISIONS[0]
        if result is not True:
            return {"n": n, "valid": False, "pair": [i, j],
                    "reason": "overlap" if result is False else "uncertified contact",
                    "interval_pairs": intervals_checked, "exact_pairs": exact_checked}
    left = _iv_min([x - h for x, y, c, s, h in geometry])
    right = _iv_max([x + h for x, y, c, s, h in geometry])
    bottom = _iv_min([y - h for x, y, c, s, h in geometry])
    top = _iv_max([y + h for x, y, c, s, h in geometry])
    side = _iv_max([right - left, top - bottom])
    score = side / mp.iv.sqrt(n) - 1
    return {"n": n, "valid": True,
            "side_lower": _endpoint_text(side.a, False), "side_upper": _endpoint_text(side.b, True),
            "score_lower": _endpoint_text(score.a, False), "score_upper": _endpoint_text(score.b, True),
            "interval_pairs": intervals_checked, "exact_pairs": exact_checked}


def _worker(item):
    return validate_puzzle(*item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", type=Path)
    parser.add_argument("--max-n", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not 1 <= args.max_n <= 1000 or args.workers < 1:
        parser.error("max-n must be 1..1000 and workers must be positive")
    with args.submission.open("rb") as stream:
        input_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    try:
        puzzles = read_submission(args.submission, args.max_n)
    except ValueError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    results = []
    with Pool(args.workers) as pool:
        for result in pool.imap_unordered(_worker, puzzles.items(), chunksize=4):
            results.append(result)
            if len(results) % 100 == 0:
                print(f"Validated {len(results)}/{args.max_n} puzzles", flush=True)
    results.sort(key=lambda r: r["n"])
    failed = [r for r in results if not r["valid"]]
    report = {"submission": str(args.submission), "sha256": input_sha256, "puzzles": len(results),
              "rows": sum(map(len, puzzles.values())), "invalid": failed,
              "valid": not failed, "results": results}
    if not failed:
        mp.mp.dps = 80
        low = sum(Fraction(r["score_lower"]) for r in results)
        high = sum(Fraction(r["score_upper"]) for r in results)
        report["score_lower"] = _fraction_decimal(low, False)
        report["score_upper"] = _fraction_decimal(high, True)
        midpoint = (mp.mpf(low.numerator) / low.denominator + mp.mpf(high.numerator) / high.denominator) / 2
        print(f"CERTIFIED: {len(results)} puzzles; score {mp.nstr(midpoint, 24)}")
        print(f"Score bounds: [{report['score_lower']}, {report['score_upper']}]")
    else:
        print(f"INVALID: {len(failed)} puzzles: {failed[:10]}")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
