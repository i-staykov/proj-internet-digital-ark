# Decision log - lightweight ADR

Short notes on why I made certain architectural design choices. Details belong in the report.

## 2026-07-21

- **uv** for Python, deps, environments
  - one tool, and `uv.lock` makes a fresh clone reproduce the exact environment
- **just** as command runner
  - familiar from work, self-documenting shortcuts; raw `uv run` stays the documented fallback
- **CI on GitHub Actions** (lint, format check, tests on every push)
  - familiar from work and cheap insurance that a clean machine still builds
  - unit tests only, network mocked: keeps CI fast and deterministic
- **DuckDB + SQLite**, one per workload
  - DuckDB: system of record + analytics (dedup, yield stats, exports)
  - SQLite (WAL): crawler work-queue, many tiny commits for crash-resume; stdlib, zero extra deps
    - `claim` is a single SQL statement, which is what makes double-claiming impossible without any locking code in future parallelization.
- **Evidence rule enforced by the schema**
  - `domain_year.evidence_id` is NOT NULL, so an unevidenced year assignment is impossible; tested
- **Large data stays out of git**
  - legacy baseline (~1.2 GB) and intermediates are ignored; only net-new output + evidence manifest get committed
- **Baseline never modified, output is disjoint net-new**
  - legacy files load read-only for dedup; our additions ship separately so the group can verify before merging
