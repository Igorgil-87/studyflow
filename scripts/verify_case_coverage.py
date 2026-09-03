#!/usr/bin/env python3
"""Fail-fast precheck for the evaluator-facing case evidence."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from case_mode.evidence import coverage_summary, requirement_matrix


def main() -> int:
    rows = requirement_matrix()
    summary = coverage_summary()
    for row in rows:
        status = "OK" if row["covered"] else "MISSING"
        print(f"[{status:7}] {row['requirement']} — {row['implementation']}")
    print(f"\nCASE COVERAGE: {summary['covered']}/{summary['total']} ({summary['coverage_pct']}%)")
    if not summary["all_covered"]:
        print("CASE COVERAGE PRECHECK FAILED")
        return 1
    print("CASE COVERAGE PRECHECK OK ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
