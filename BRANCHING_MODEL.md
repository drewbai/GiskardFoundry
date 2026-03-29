# GiskardFoundry Branching Model

## Overview

GiskardFoundry uses a two-permanent-branch model. Only `main` and `develop` are long-lived. All feature work is done on short-lived branches that are merged through `develop` → `main` and then deleted.

```
main  ──────────────●──────────────────●──── (tagged releases)
                   ↑                  ↑
develop  ──●───●───●───●───●───●───●──● (integration lane)
             ↑       ↑       ↑
          feature/* feature/* feature/*  (short-lived)
```

---

## Permanent Branches

### `main` — Stable Substrate

- **Purpose:** Production-grade, release-tagged code only.
- **Stability contract:** Every commit on `main` must:
  - Pass all CI tests.
  - Satisfy the `JobInput` / `EvaluationResult` schema contract.
  - Be compatible with the LeadForgeAI adapter/facade boundary.
  - Maintain deterministic substrate guarantees (scoring, filters, risk).
- **Who merges to it:** Only via PR from `develop`, after passing CI.
- **Direct commits:** Forbidden except for critical hotfixes (see hotfix workflow below).
- **Tags:** Every merge to `main` that represents a release is tagged with a semantic version (`v<major>.<minor>.<patch>`).

### `develop` — Integration Lane

- **Purpose:** The single shared integration point for all feature work.
- **Stability contract:** `develop` should be continuously deployable to a staging environment. It must not contain abandoned experiments, personal code, or half-implemented features.
- **Who merges to it:** Any contributor, via PR from a `feature/*` or `fix/*` branch.
- **Rebasing:** Contributors rebase their feature branches onto the tip of `develop` before opening a PR.
- **Direct commits:** Forbidden. All changes come through PRs.

---

## Short-Lived Branch Types

| Prefix | Purpose | Merges into | Lifecycle |
|---|---|---|---|
| `feature/<name>` | New capabilities | `develop` | Delete after PR merge |
| `fix/<name>` | Bug fixes | `develop` | Delete after PR merge |
| `hotfix/<name>` | Critical production fixes | `main` **and** `develop` | Delete after both merges |
| `release/<version>` | Release stabilization (optional) | `main` | Delete after tagging |

### Naming Conventions

- Use lowercase with hyphens: `feature/onenote-sync`, `fix/schema-validation`.
- Keep names short and descriptive of the work, not the person doing it.
- No personal names, dates, or ambiguous labels as branch names.

---

## Schema Contract Alignment

The `main` branch is the source of truth for the following contracts. No breaking changes may land on `main` without a major version bump and a corresponding entry in `CHANGELOG.md`:

- **`JobInput` schema** (`giskardfoundry/core/types/`) — consumed by LeadForgeAI.
- **`EvaluationResult` schema** (`giskardfoundry/core/evaluation/`) — produced by the Giskard evaluation pipeline.
- **Adapter/facade boundary** (`giskardfoundry/facade/`) — the LeadForgeAI integration surface.
- **Scoring and filter determinism** (`giskardfoundry/core/scoring/`, `giskardfoundry/core/filters/`) — outputs must be reproducible given the same input.

Future schema evolution work must be done on a `feature/schema-v<n>` branch and landed on `develop` first. Breaking changes require a deprecation window of at least one release cycle before removal from `main`.

---

## Hotfix Workflow

```
main  ──●──────────────────────────────●── v1.x.y+1
         \                            /
          hotfix/critical-bug ───────●
                                     \
develop  ──●───●──────────────────────●── (back-ported)
```

1. Branch `hotfix/<name>` from the tip of `main`.
2. Fix, test, commit.
3. PR → `main`; merge and tag.
4. PR → `develop`; merge to keep histories in sync.
5. Delete the hotfix branch.

---

## Branch Protection Requirements (GitHub)

| Branch | Required status checks | Require PR review | Restrict push |
|---|---|---|---|
| `main` | All CI, schema tests | ≥ 1 approval | Maintainers only |
| `develop` | All CI | ≥ 1 approval | Contributors |

---

## Keeping `main` Stable and Substrate-Safe

1. **Never force-push `main`.** Tags live on `main` commits; rewriting history invalidates them.
2. **No experimental imports.** External libraries added to `requirements.txt` must be pinned and vetted before landing on `main`.
3. **Schema migrations are coordinated.** Alembic migrations in `migrations/versions/` must be reviewed against the schema contract before merging to `main`.
4. **CI must be green.** The GitHub Actions workflow (`/.github/`) is the gate. Do not merge with failing checks.
5. **Tags are immutable.** `checkpoint-2026-03-27` and all future release tags are never moved or deleted.
