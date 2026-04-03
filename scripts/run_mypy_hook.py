from __future__ import annotations

import sys
from pathlib import Path

from mypy import api as mypy_api


def _run(args: list[str]) -> int:
    stdout, stderr, exit_code = mypy_api.run(args)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    return int(exit_code)


def _statistics_files() -> list[str]:
    return [str(path) for path in sorted(Path("src/statistics").rglob("*.py"))]


def main() -> int:
    # Phase 1: check project, but avoid recursive duplicate discovery for src/statistics.
    code_main = _run([".", "--exclude", r"^src/statistics/", "--follow-imports", "skip"])
    # Phase 2: check statistics files explicitly to avoid mypy's directory-discovery edge case.
    stats_files = _statistics_files()
    code_stats = _run(["--exclude", r"^$", *stats_files]) if stats_files else 0
    return code_main or code_stats


if __name__ == "__main__":
    raise SystemExit(main())
