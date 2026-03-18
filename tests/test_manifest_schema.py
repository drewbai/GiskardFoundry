"""Tests for validating agent manifests against the shared schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_all_agent_manifests_match_schema() -> None:
    """Every agent manifest should validate against the shared schema."""
    workspace_root = Path(__file__).resolve().parents[1]
    schema_path = workspace_root / "config" / "agent_manifest_schema.json"
    manifests = sorted((workspace_root / "agents").glob("*/manifest.json"))

    assert schema_path.exists(), "Manifest schema file is missing."
    assert manifests, "No agent manifests found to validate."

    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema)

    errors_by_file: dict[str, list[str]] = {}
    for manifest_path in manifests:
        manifest = _load_json(manifest_path)
        errors = sorted(validator.iter_errors(manifest), key=lambda error: error.path)
        if errors:
            relative_path = str(manifest_path.relative_to(workspace_root)).replace("\\", "/")
            errors_by_file[relative_path] = [
                f"{'.'.join(str(p) for p in error.path) or '<root>'}: {error.message}"
                for error in errors
            ]

    assert not errors_by_file, f"Manifest schema validation errors: {errors_by_file}"
