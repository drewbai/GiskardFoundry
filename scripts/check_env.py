"""Validate required environment variables for MAF/Foundry runtime.

Usage:
    python scripts/check_env.py
"""

from __future__ import annotations

import os
import sys

REQUIRED_ENV_VARS = (
    "FOUNDRY_PROJECT_ENDPOINT",
    "FOUNDRY_MODEL_DEPLOYMENT_NAME",
)


def validate_env_vars(required_env_vars: tuple[str, ...] = REQUIRED_ENV_VARS) -> list[str]:
    """Return missing required environment variable names."""
    missing: list[str] = []
    for name in required_env_vars:
        value = os.getenv(name)
        if value is None or not value.strip():
            missing.append(name)
    return missing


def main() -> int:
    """CLI entrypoint for env validation."""
    missing = validate_env_vars()
    if missing:
        print("Missing required environment variables:")
        for name in missing:
            print(f"- {name}")
        print("\nCopy .env.example to .env and set the missing values.")
        return 1

    print("Environment check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
