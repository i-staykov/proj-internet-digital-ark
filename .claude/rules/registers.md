---
paths:
  - docs/registers/sources.md
  - docs/registers/sources-closed.md
  - docs/registers/approved-sources-list.md
  - docs/registers/queue.md
---

# Touching a register

- One row per source, negatives included: open (BANKED, SEEDED, ADMITTED, PARKED, FIND, HELD OUT)
  in `sources.md`, closed in `sources-closed.md`. A new measurement replaces the row; git holds
  every earlier one.
- Every source gets an http(s) link in its row BEFORE ingest, beside what dates one item.
- Look a source up with `just find <term>` or the `register-reader` subagent.
- What a `Decision:` line may claim is in `docs/lore/rules.md`, section Registers. The approval
  gate itself is enforced by `ark ingest`.
