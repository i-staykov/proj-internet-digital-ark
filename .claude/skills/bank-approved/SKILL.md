---
name: bank-approved
description: Bank the sources a human has newly approved into the store, then export and gate. Use after a Decision line lands, or to rehearse the path before one does.
---

# Bank approved sources

The evidence bar and the standing approval rule are in `docs/rules.md`; the command table is in
`docs/runbook.md`. Order:

1. The source has a link and its dating sentence in `docs/sources.md`. No link, no ingest.
2. The class has a `Decision:` line in `docs/approved-sources-list.md`. The loop may write that
   line itself only when all four conditions of the standing approval rule hold, and cites the
   rule in the line. Failing any one, park the source as `pending` and stop here.
3. `uv run python scripts/harness/bank_approved.py` reports what it would ingest and skips
   anything still `pending`. Read that list before adding `--write`.
4. `uv run python scripts/harness/bank_approved.py --write`, then `uv run ark export` and
   `uv run ark check`, in that order.
5. A five-figure source banks together with its paragraph in `docs/report.template.md`.

`just ship-approved` runs step 3 to 4 as the first stage of shipping, so a rehearsal before any
decision arrives exercises every later step and changes nothing.

Traps worth re-reading in `docs/traps.md`: an already-ingested journal shows zero net-new by
construction, and a partition's real yield is the `year_rows` the ingest ledger printed, not an
argument about the partition.

Needs the store, so this runs on the main checkout.
