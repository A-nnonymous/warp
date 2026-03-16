from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TARGET_INCLUDE = [
    "runtime/cp/contracts.py",
    "runtime/cp/services/*.py",
    "runtime/cp/stores/*.py",
]
FAIL_UNDER = "90"
TEST_DISCOVER_ARGS = ["-m", "unittest", "discover", "-s", "runtime", "-p", "test_*.py"]


def run(cmd: list[str]) -> None:
    completed = subprocess.run(cmd, cwd=ROOT)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    python = sys.executable
    include_arg = "--include=" + ",".join(TARGET_INCLUDE)
    run([python, "-m", "coverage", "erase"])
    run([python, "-m", "coverage", "run", "--source=runtime/cp", *TEST_DISCOVER_ARGS])
    run([python, "-m", "coverage", "report", include_arg, f"--fail-under={FAIL_UNDER}", "-m"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
