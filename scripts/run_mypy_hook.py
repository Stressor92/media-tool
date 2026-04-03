from __future__ import annotations

import sys

from mypy import api as mypy_api


def _run(args: list[str]) -> int:
    stdout, stderr, exit_code = mypy_api.run(args)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    return int(exit_code)


def main() -> int:
    # Phase 1: check project, but avoid recursive duplicate discovery for src/statistics.
    code_main = _run([".", "--exclude", r"^src/statistics/", "--follow-imports", "skip"])
    # Phase 2: check statistics package explicitly under its canonical package name.
    code_stats = _run(["src/statistics/"])
    return code_main or code_stats


if __name__ == "__main__":
    raise SystemExit(main())
