"""Fail when the mypy error count grows, and lower the bar when it shrinks.

The backend carried 8535 mypy errors, so both CI and the Makefile ended their
mypy invocation with `|| true`. A check that cannot fail is not a check: nothing
stopped the count climbing, and "fix every error, then make it blocking" was
never going to happen in one sitting.

This enforces the only property that actually matters day to day -- the number
must not increase. When it drops, the baseline is rewritten so the gain cannot
be given back. The endpoint is a baseline of 0, at which point this script and
the baseline file can be deleted in favour of plain `mypy`.

Usage:
    python scripts/mypy_ratchet.py            # check against the baseline
    python scripts/mypy_ratchet.py --update   # accept the current count
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / ".mypy-baseline"
MYPY_ARGS = ["-m", "mypy", "bionodulo", "--ignore-missing-imports"]

# "Found 530 errors in 182 files (checked 1555 source files)"
_FOUND = re.compile(r"^Found (\d+) errors? in \d+ files?", re.MULTILINE)
_SUCCESS = re.compile(r"^Success: no issues found", re.MULTILINE)


def run_mypy() -> tuple[int, str]:
    """Return the current error count and the raw report."""
    result = subprocess.run(
        [sys.executable, *MYPY_ARGS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    if _SUCCESS.search(output):
        return 0, output
    match = _FOUND.search(output)
    if match is None:
        # No count and no success line means mypy itself failed -- a crash, a
        # bad flag, a missing dependency. Reporting that as "0 errors" would
        # silently disable the gate, which is the failure mode this whole
        # script exists to prevent.
        raise SystemExit(
            "mypy produced no parseable summary; treating as failure.\n"
            f"--- mypy output ---\n{output.strip()[-2000:]}"
        )
    return int(match.group(1)), output


def read_baseline() -> int:
    if not BASELINE_PATH.exists():
        raise SystemExit(
            f"No baseline at {BASELINE_PATH.relative_to(REPO_ROOT)}. "
            "Create one with: python scripts/mypy_ratchet.py --update"
        )
    text = BASELINE_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return int(line)
    raise SystemExit(f"{BASELINE_PATH.name} contains no count.")


def write_baseline(count: int) -> None:
    BASELINE_PATH.write_text(
        "# Maximum mypy errors tolerated by scripts/mypy_ratchet.py.\n"
        "# It may only ever go down. Lower it by fixing errors, never by editing\n"
        "# this number upwards to make a red build green.\n"
        f"{count}\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Write the current count as the new baseline (only if it improved).",
    )
    args = parser.parse_args(argv)

    count, _ = run_mypy()

    if args.update:
        if BASELINE_PATH.exists():
            previous = read_baseline()
            if count > previous:
                print(
                    f"Refusing to raise the baseline from {previous} to {count}. "
                    "Fix the new errors instead."
                )
                return 1
        write_baseline(count)
        print(f"Baseline set to {count}.")
        return 0

    baseline = read_baseline()
    if count > baseline:
        print(
            f"mypy errors increased: {count} (baseline {baseline}, "
            f"+{count - baseline}).\n"
            "Fix the new errors, or run scripts/mypy_ratchet.py --update if you "
            "genuinely lowered the count."
        )
        return 1

    if count < baseline:
        write_baseline(count)
        print(
            f"mypy errors dropped from {baseline} to {count}. "
            "Baseline lowered -- commit .mypy-baseline."
        )
        return 0

    print(f"mypy errors steady at {count} (baseline {baseline}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
