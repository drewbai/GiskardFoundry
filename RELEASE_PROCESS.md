# GiskardFoundry Release Process

## Overview

Releases follow a `develop → main → tag` workflow. All changes are integrated on `develop` before promotion to the stable `main` branch. Every production release is tagged with a semantic version.

---

## Versioning Rules

GiskardFoundry uses [Semantic Versioning 2.0.0](https://semver.org/): `v<MAJOR>.<MINOR>.<PATCH>`.

| Component | What triggers a bump |
|---|---|
| **MAJOR** | Breaking change to `JobInput`, `EvaluationResult`, or the facade boundary. Requires a deprecation window. |
| **MINOR** | New capability added in a backward-compatible way (new tool, new agent, new evaluation metric). |
| **PATCH** | Backward-compatible bug fix, dependency pin update, doc correction. |

### Pre-release Labels

- `v1.1.0-alpha.1` — functionality is incomplete or under active change.
- `v1.1.0-rc.1` — release candidate on `develop`, awaiting final sign-off.
- Final releases carry no label: `v1.1.0`.

### Current Release Baseline

| Tag | Commit | Notes |
|---|---|---|
| `checkpoint-2026-03-27` | `660fb90` | Pre-release checkpoint; not a versioned release. |

The first formal release tag will be `v1.0.0`, applied to the `main` HEAD once the schema contract and CI baseline are confirmed stable.

---

## Release Workflow

### Standard Release (`develop → main → tag`)

```
Step 1: Ensure develop is green
  git checkout develop
  git pull origin develop
  # Confirm CI passes

Step 2: Create a release branch (optional for larger changes)
  git checkout -b release/v1.1.0

  # Bump version in pyproject.toml
  # Update CHANGELOG.md
  # Run final test pass
  git commit -am "chore: prepare release v1.1.0"

  # PR release/v1.1.0 → main

Step 3: Merge to main
  git checkout main
  git merge --no-ff release/v1.1.0
  git tag -a v1.1.0 -m "Release v1.1.0"
  git push origin main --follow-tags

Step 4: Back-merge to develop
  git checkout develop
  git merge --no-ff main
  git push origin develop

Step 5: Delete the release branch
  git branch -d release/v1.1.0
  git push origin --delete release/v1.1.0
```

### Fast-lane Release (patch from develop directly)

For patch releases where no release branch is needed:

```
git checkout main
git merge --no-ff develop
git tag -a v1.0.1 -m "Release v1.0.1: <one-line summary>"
git push origin main --follow-tags
git checkout develop
git merge --no-ff main
git push origin develop
```

### Hotfix Release

See `BRANCHING_MODEL.md` for the hotfix branch workflow. After merging the hotfix to `main`:

```
git checkout main
git tag -a v1.0.2 -m "Hotfix v1.0.2: <one-line summary>"
git push origin main --follow-tags
```

Then back-merge to `develop` immediately so no divergence accumulates.

---

## Compatibility Contract Updates

When a change touches the schema or facade boundary, the following checklist applies **before merging to `main`**:

### `JobInput` Schema Changes

- [ ] All existing fields remain present (or deprecated, not removed).
- [ ] New required fields have defaults in the `JobInput` model.
- [ ] `giskardfoundry/core/types/` tests cover the new shape.
- [ ] LeadForgeAI adapter (`giskardfoundry/facade/`) handles the new fields.
- [ ] `CHANGELOG.md` documents the change under the correct version heading.
- [ ] MAJOR version bump if any existing field is renamed or removed.

### `EvaluationResult` Schema Changes

- [ ] All downstream consumers of `EvaluationResult` are updated (scoring, risk, reporting).
- [ ] Serialization/deserialization round-trip test passes.
- [ ] MINOR bump for new fields; MAJOR bump for removed or renamed fields.

### Adapter / Facade Boundary (`giskardfoundry/facade/`)

- [ ] `FoundryFacade` interface is unchanged or backward-compatible.
- [ ] `request.py` and `response.py` models are forward-compatible.
- [ ] Integration tests in `tests/facade/` pass.

### Deterministic Substrate (scoring, filters, risk)

- [ ] Same `JobInput` produces identical `EvaluationResult` across runs.
- [ ] No non-deterministic calls (random seeds, time-based logic) introduced without explicit justification.
- [ ] Performance benchmarks have not regressed.

---

## CHANGELOG Convention

`CHANGELOG.md` uses the following format. Each section is added to the top:

```markdown
## v1.1.0 — YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Breaking Changes
- **BREAKING:** Description of breaking change and migration path.
```

All entries are written in imperative mood ("Add X", "Fix Y", "Remove Z").

---

## Release Sign-off Checklist

Before running `git push origin main --follow-tags`:

- [ ] `pyproject.toml` version matches the tag.
- [ ] `CHANGELOG.md` has an entry for the new version.
- [ ] All CI checks pass on the candidate commit.
- [ ] Schema contract checklist completed (if applicable).
- [ ] `develop` has been back-merged from `main` after tagging.
- [ ] No feature branches are left dangling (merged branches deleted).

---

## Environment and Deployment Notes

The release tag is the source of truth for deployment. The Microsoft Agent Framework server is started via:

```
giskardfoundry-server
```

Required environment variables at runtime (set in deployment environment, never committed):

```
FOUNDRY_PROJECT_ENDPOINT=<azure-foundry-endpoint>
FOUNDRY_MODEL_DEPLOYMENT_NAME=<model-deployment-name>
```

These are documented in `.env.example`. The production values live in Azure Key Vault or the deployment environment's secret store — never in source control.
