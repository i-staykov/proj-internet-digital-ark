---
paths:
  - docs/sources.md
  - docs/sources-closed.md
  - docs/approved-sources-list.md
  - docs/hypotheses-pending.md
---

# Touching a register

- `docs/sources.md` is several hundred kilobytes and reading it whole is denied in
  `.claude/settings.json`. Use `grep -n`, or the `register-reader` subagent.
- The entry format, the write-up length rule and what a `Decision:` line may claim are in
  `docs/rules.md`, section Registers. The approval gate itself is enforced by `ark ingest`.
- Every source gets its link and its dating sentence here BEFORE it is ingested.
- Log the negatives too, with the figure and the date, so nobody re-tests a closed family.
- Append; do not rewrite an existing entry's figures. A figure is only meaningful with the
  baseline it was measured against, which is why entries carry dates.
