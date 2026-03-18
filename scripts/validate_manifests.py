"""Validate all agent manifests against the shared JSON schema.

Usage:
    python scripts/validate_manifests.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file into a dictionary."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> int:
    """Validate every agent manifest and return process exit code."""
    workspace_root = Path(__file__).resolve().parents[1]
    schema_path = workspace_root / "config" / "agent_manifest_schema.json"
    manifests = sorted((workspace_root / "agents").glob("*/manifest.json"))

    if not schema_path.exists():
        print(f"Schema not found: {schema_path}")
        return 1

    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)

    if not manifests:
        print("No agent manifests found.")
        return 1

    has_errors = False
    for manifest_path in manifests:
        manifest = load_json(manifest_path)
        errors = sorted(validator.iter_errors(manifest), key=lambda error: error.path)
        if errors:
            has_errors = True
            print(f"\nFAILED: {manifest_path.relative_to(workspace_root)}")
            for error in errors:
                location = ".".join(str(part) for part in error.path) or "<root>"
                print(f"  - {location}: {error.message}")
        else:
            print(f"OK: {manifest_path.relative_to(workspace_root)}")

    if has_errors:
        print("\nManifest validation failed.")
        return 1

    print("\nAll manifests are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
