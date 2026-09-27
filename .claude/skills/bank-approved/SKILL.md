---
name: bank-approved
description: Bank the sources a human has newly approved into the store, then export and gate. Use after a Decision line lands, or to rehearse the path before one does.
---

# Bank approved sources

The approval rule is `CLAUDE.md`, Autonomy; the commands are in `docs/ops/runbook.md`. Order:

1. The source has its row in `docs/registers/sources.md` (`CLAUDE.md`, Registers).
2. The class has a `Decision:` line in `docs/registers/approved-sources-list.md`, or the loop writes
   one under `CLAUDE.md`, Autonomy. Otherwise it is `pending`: stop here.
3. `uv run python scripts/harness/bank_approved.py` reports what it would ingest and skips
   anything still `pending`. Read that list before adding `--write`.
4. `uv run python scripts/harness/bank_approved.py --write`, then `uv run ark export` and
   `uv run ark check`, in that order.
5. A five-figure source banks together with its paragraph in `docs/report.template.md`.

`just ship` runs steps 3 and 4 in its first stage, `just bank --force`, so a rehearsal
exercises every later step and banks nothing still pending.

`docs/lore/laws.md`, Pricing: an already-ingested journal shows zero net-new by construction, and a
partition's real yield is the `year_rows` the ingest ledger printed.

Needs the store, so this runs on the main checkout.
