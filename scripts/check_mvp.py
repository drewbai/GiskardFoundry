"""Run core MVP quality checks for GiskardFoundry.

Usage:
    python scripts/check_mvp.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_step(command: list[str], description: str, cwd: Path) -> int:
    """Run a single check step and return exit code."""
    print(f"\n==> {description}")
    print("$", " ".join(command))
    result = subprocess.run(command, cwd=cwd, check=False)
    return result.returncode


def main() -> int:
    """Execute lint, manifest validation, and tests in sequence."""
    workspace_root = Path(__file__).resolve().parents[1]

    checks: list[tuple[list[str], str]] = [
        (["python", "-m", "ruff", "check", "."], "Lint with Ruff"),
        (["python", "scripts/validate_manifests.py"], "Validate manifest schema"),
        (["python", "-m", "pytest", "-q"], "Run test suite"),
    ]

    for command, description in checks:
        exit_code = run_step(command, description, cwd=workspace_root)
        if exit_code != 0:
            print(f"\nMVP checks failed at step: {description}")
            return exit_code

    print("\nAll MVP checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
