#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reconcile two CSV extracts row by row on a key, with exact decimal math.

Compares an oracle extract (--left) against a candidate extract (--right) at
the same grain. Reports control totals, rows missing on either side, duplicate
or null keys, per-column value breaks, and any differences a --tol let through
(a one-signed pile of those is a logic bug, not rounding). Numbers are compared as Decimal, never
float, so 0.1 + 0.2 style noise cannot hide or invent a break.

Writes <out>/summary.md and <out>/breaks.csv (one row per break).
Exit codes: 0 = every row and value matches, 1 = breaks found,
2 = bad arguments or unreadable input.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import NoReturn

BREAK_FIELDS = ["break_type", "column", "left_value", "right_value", "diff_right_minus_left"]


def die(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(value.strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


# ponytail: in-memory hash join, fine to a few million rows; beyond that reconcile
# in SQL inside the database (references/reconciliation.md).
def load(
    path: Path, keys: list[str], rename: dict[str, str], nulls: set[str]
) -> tuple[
    list[str], dict[tuple[str, ...], dict[str, str | None]], list[tuple[tuple[str, ...], str]]
]:
    """Return (columns, rows by key, bad keys as (key, kind)). Later duplicates are dropped."""
    try:
        fh = path.open(newline="", encoding="utf-8-sig")
    except OSError as exc:
        die(f"cannot read {path}: {exc}")
    with fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            die(f"{path} is empty; an extract needs a header row")
        columns = [rename.get(c.strip(), c.strip()) for c in reader.fieldnames]
        missing = [k for k in keys if k not in columns]
        if missing:
            die(f"{path} has no key column(s) {missing}; columns are {columns}")
        rows: dict[tuple[str, ...], dict[str, str | None]] = {}
        bad: list[tuple[tuple[str, ...], str]] = []
        for raw in reader:
            row = {
                rename.get(k.strip(), k.strip()): (
                    None if v is None or v.strip() in nulls else v.strip()
                )
                for k, v in raw.items()
                if k is not None
            }
            key = tuple(row.get(k) or "" for k in keys)
            if any(row.get(k) is None for k in keys):
                bad.append((key, "null_key"))
            elif key in rows:
                bad.append((key, "duplicate_key"))
            else:
                rows[key] = row
    return columns, rows, bad


def parse_tolerances(specs: list[str]) -> dict[str, Decimal]:
    tolerances: dict[str, Decimal] = {}
    for spec in specs:
        column, sep, value = spec.partition("=")
        tolerance = to_decimal(value) if sep else None
        if not column or tolerance is None or tolerance < 0:
            die(f"--tol expects COLUMN=NONNEGATIVE_NUMBER, got {spec!r}")
        tolerances[column] = tolerance
    return tolerances


def parse_renames(specs: list[str]) -> dict[str, str]:
    renames: dict[str, str] = {}
    for spec in specs:
        right, sep, left = spec.partition("=")
        if not sep or not right or not left:
            die(f"--rename expects RIGHT_COLUMN=LEFT_COLUMN, got {spec!r}")
        renames[right] = left
    return renames


def compare_values(
    left: str | None, right: str | None, tolerance: Decimal, as_text: bool
) -> tuple[bool, Decimal | None]:
    """Return (matches, right - left). Numbers compare by value; other text exactly."""
    if left is None or right is None:
        return left is None and right is None, None
    if as_text:
        return left == right, None
    left_num, right_num = to_decimal(left), to_decimal(right)
    if left_num is not None and right_num is not None:
        diff = right_num - left_num
        return abs(diff) <= tolerance, diff
    return left == right, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--left", type=Path, required=True, help="oracle extract (CSV with header)")
    parser.add_argument(
        "--right", type=Path, required=True, help="candidate extract (CSV with header)"
    )
    parser.add_argument(
        "--key", required=True, help="comma-separated key columns that define the grain"
    )
    parser.add_argument(
        "--compare",
        help="comma-separated columns to compare (default: every shared non-key column)",
    )
    parser.add_argument(
        "--ignore",
        default="",
        help="comma-separated columns to skip (run timestamps, surrogate ids)",
    )
    parser.add_argument(
        "--tol",
        action="append",
        default=[],
        metavar="COLUMN=ABS",
        help="absolute tolerance for one numeric column; repeatable. Default is exact.",
    )
    parser.add_argument(
        "--text",
        default="",
        help="comma-separated numeric-looking columns to compare as exact text (ids with leading zeros)",
    )
    parser.add_argument(
        "--rename",
        action="append",
        default=[],
        metavar="RIGHT=LEFT",
        help="map a candidate column name onto the oracle's name; repeatable",
    )
    parser.add_argument(
        "--null",
        action="append",
        default=[""],
        metavar="TOKEN",
        help="cell text that means NULL, repeatable (empty cells always do), e.g. --null NULL",
    )
    parser.add_argument("--left-name", default="oracle", help="label for --left in the report")
    parser.add_argument("--right-name", default="candidate", help="label for --right in the report")
    parser.add_argument(
        "--out", type=Path, required=True, help="directory for summary.md and breaks.csv"
    )
    args = parser.parse_args()

    keys = [k.strip() for k in args.key.split(",") if k.strip()]
    ignore = {c.strip() for c in args.ignore.split(",") if c.strip()}
    text_cols = {c.strip() for c in args.text.split(",") if c.strip()}
    tolerances = parse_tolerances(args.tol)
    nulls = set(args.null)
    left_cols, left_rows, left_bad = load(args.left, keys, {}, nulls)
    right_cols, right_rows, right_bad = load(args.right, keys, parse_renames(args.rename), nulls)

    if args.compare:
        compare = [c.strip() for c in args.compare.split(",") if c.strip()]
        absent = [c for c in compare if c not in left_cols or c not in right_cols]
        if absent:
            die(f"--compare column(s) {absent} missing from one side")
    else:
        compare = [c for c in left_cols if c in right_cols and c not in keys and c not in ignore]
    if not compare:
        die("no columns to compare; check --compare, --ignore, and --rename")
    unknown_tol = sorted(set(tolerances) - set(compare))
    if unknown_tol:
        die(f"--tol names column(s) not being compared: {unknown_tol}")
    unmatched_cols = sorted((set(left_cols) ^ set(right_cols)) - ignore)

    args.out.mkdir(parents=True, exist_ok=True)
    breaks_path = args.out / "breaks.csv"
    break_counts: Counter[str] = Counter()
    column_breaks: Counter[str] = Counter()
    tolerated: dict[str, list[Decimal]] = {c: [] for c in tolerances}
    rows_with_value_breaks = 0
    matched = 0

    with breaks_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([*keys, *BREAK_FIELDS])

        def emit(
            key: tuple[str, ...],
            kind: str,
            column: str = "",
            left: str | None = None,
            right: str | None = None,
            diff: Decimal | None = None,
        ) -> None:
            break_counts[kind] += 1
            writer.writerow(
                [*key, kind, column, left or "", right or "", "" if diff is None else diff]
            )

        for key, kind in left_bad:
            emit(key, f"{kind}_in_{args.left_name}")
        for key, kind in right_bad:
            emit(key, f"{kind}_in_{args.right_name}")
        for key in sorted(left_rows.keys() - right_rows.keys()):
            emit(key, f"missing_in_{args.right_name}")
        for key in sorted(right_rows.keys() - left_rows.keys()):
            emit(key, f"missing_in_{args.left_name}")
        for key in sorted(left_rows.keys() & right_rows.keys()):
            left_row, right_row = left_rows[key], right_rows[key]
            row_ok = True
            for column in compare:
                ok, diff = compare_values(
                    left_row.get(column),
                    right_row.get(column),
                    tolerances.get(column, Decimal(0)),
                    column in text_cols,
                )
                if ok and diff and column in tolerated:
                    tolerated[column].append(diff)
                if not ok:
                    row_ok = False
                    column_breaks[column] += 1
                    emit(key, "value", column, left_row.get(column), right_row.get(column), diff)
            if row_ok:
                matched += 1
            else:
                rows_with_value_breaks += 1

    # Control totals: every compared column whose non-null cells are all numeric on both sides.
    totals: list[tuple[str, Decimal, Decimal]] = []
    for column in (c for c in compare if c not in text_cols):
        sums: list[Decimal] = []
        for rows in (left_rows, right_rows):
            cells = [v for r in rows.values() if (v := r.get(column)) is not None]
            numbers = [n for c in cells if (n := to_decimal(c)) is not None]
            if not cells or len(numbers) != len(cells):
                break
            sums.append(sum(numbers, Decimal(0)))
        if len(sums) == 2:
            totals.append((column, sums[0], sums[1]))

    total_breaks = sum(break_counts.values())
    verdict = "MATCH" if total_breaks == 0 else "BREAKS"
    lines = [
        f"# Reconciliation: {verdict}",
        "",
        (
            f"- {args.left_name}: `{args.left}` sha256 `{sha256(args.left)}`, "
            f"{len(left_rows) + len(left_bad)} rows"
        ),
        (
            f"- {args.right_name}: `{args.right}` sha256 `{sha256(args.right)}`, "
            f"{len(right_rows) + len(right_bad)} rows"
        ),
        f"- Key: {', '.join(keys)}",
        f"- Compared: {', '.join(compare)}",
        "- Tolerance: "
        + (
            ", ".join(f"{c} ±{t}" for c, t in tolerances.items()) + "; others exact"
            if tolerances
            else "exact on every column"
        ),
        f"- Ignored: {', '.join(sorted(ignore)) or 'none'}",
        f"- Columns on one side only (not compared): {', '.join(unmatched_cols) or 'none'}",
        "",
        "| Check | Count |",
        "|---|---|",
        f"| Keys on both sides, all values match | {matched} |",
        f"| Keys on both sides, value breaks | {rows_with_value_breaks} |",
        *(
            f"| {kind} | {count} |"
            for kind, count in sorted(break_counts.items())
            if kind != "value"
        ),
        "",
    ]
    if column_breaks:
        lines += ["| Column | Value breaks |", "|---|---|"]
        lines += [f"| {c} | {n} |" for c, n in column_breaks.most_common()]
        lines.append("")
    if tolerances:
        lines += [
            "| Tolerated column | Nonzero diffs within tolerance | Net diff | Same sign |",
            "|---|---|---|---|",
        ]
        for column, diffs in tolerated.items():
            one_sign = len(diffs) > 1 and (all(d > 0 for d in diffs) or all(d < 0 for d in diffs))
            lines.append(
                f"| {column} | {len(diffs)} | {sum(diffs, Decimal(0))} | {'YES, investigate' if one_sign else 'no'} |"
            )
        lines.append("")
    if totals:
        lines += [
            f"| Control total | {args.left_name} | {args.right_name} | Diff |",
            "|---|---|---|---|",
        ]
        lines += [f"| {c} | {a} | {b} | {b - a} |" for c, a, b in totals]
        lines.append("")
    lines.append(f"Breaks: {total_breaks} rows in `{breaks_path.name}`.")
    summary = "\n".join(lines) + "\n"
    (args.out / "summary.md").write_text(summary, encoding="utf-8")
    print(summary, end="")
    return 0 if total_breaks == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
