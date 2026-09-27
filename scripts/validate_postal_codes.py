"""Validate that postal_code columns in tracked CSVs are well-formed 6-digit strings.

Guards against the dtype-inference bug where pd.read_csv without
dtype={"postal_code": str} silently drops a leading zero (e.g. "081001"
becomes "81001"). See CLAUDE.md's "Cache-loading gotcha" section.

Usage: python scripts/validate_postal_codes.py [file ...]
With no args, checks the tracked deliverable
(data/processed/accessibility_by_postal_code.csv) from the working tree.
Pass "-" as the sole arg to instead read CSV content from stdin (e.g. via
`git show :path | validate_postal_codes.py -`, so the pre-commit hook
validates the staged blob rather than the working-tree copy, which may have
diverged from what's actually staged).
Exits non-zero and prints offending rows if any postal_code fails to
match ^\\d{6}$.
"""

import io
import sys
from pathlib import Path

import pandas as pd

DEFAULT_TARGETS = [Path("data/processed/accessibility_by_postal_code.csv")]
POSTAL_CODE_RE = r"^\d{6}$"


def _check_postal_codes(df: pd.DataFrame, label: str) -> list[str]:
    if "postal_code" not in df.columns:
        return []
    bad = df[df["postal_code"].notna() & ~df["postal_code"].str.match(POSTAL_CODE_RE)]
    if bad.empty:
        return []
    sample = bad["postal_code"].head(10).tolist()
    return [f"{label}: {len(bad)} row(s) with malformed postal_code, e.g. {sample}"]


def validate_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    df = pd.read_csv(path, dtype={"postal_code": str})
    return _check_postal_codes(df, str(path))


def validate_stdin() -> list[str]:
    df = pd.read_csv(io.StringIO(sys.stdin.read()), dtype={"postal_code": str})
    return _check_postal_codes(df, "<stdin>")


def main(argv: list[str]) -> int:
    if argv == ["-"]:
        errors = validate_stdin()
    else:
        targets = [Path(p) for p in argv] if argv else DEFAULT_TARGETS
        errors = [msg for path in targets for msg in validate_file(path)]
    if errors:
        print("postal_code validation failed:")
        for msg in errors:
            print(f"  - {msg}")
        print(
            "\nThis usually means a pd.read_csv() call is missing "
            'dtype={"postal_code": str}, letting pandas infer the column as '
            "int64 and drop leading zeros."
        )
        return 1
    print("postal_code validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
