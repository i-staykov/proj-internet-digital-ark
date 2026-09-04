# His brief, section by section, against what the code does

One row per bullet of the newest numbered section, with the file that satisfies it or the ticket that
does not yet. Re-checked when he ships an update; the verbatim text is in
[ding/project-brief.md](ding/project-brief.md) and is never summarised there.

Sections I to X are satisfied by the rules pages ([rules.md](rules.md), [laws.md](laws.md)) and were
checked when each landed. This page starts at XI because it is the first section that changes what the
code must do rather than what we must report.

## XI. Robust hostname processing and candidate-pool reconciliation (2026-09-04)

| his bullet | ours | where |
|---|---|---|
| hostname-level identity throughout; registrable is secondary metadata | yes. `hostname_year` is a first-class table, `domain_year` keeps the parent, and the export writes both | `src/ark/export.py` |
| **a base hostname and distinct subdomain hostnames may EACH be annual records** | now yes at export, after ADR-008 reverted ADR-007 the same day this landed | ADR-008 |
| the same, one level up: `www.<parent registrable>` | **NOT yet.** The ingest still refuses it outright. His sentence permits it and the evidence rows are already in the store, so this is a backfill and not a re-collection | #101 |
| the same, for DNS-listed hosts | **NOT yet.** Our 2026-09-02 purpose reading (C-55) lets only web-facing lanes write hostname rows, so a zone NS target or a RIPE `nserver:` dates the parent only. XI asks for year-specific evidence and does not restate the web-content condition | #102 |
| annual masters and candidate pools are separate data products | yes | `output/netnew/`, `output/candidates.txt` |
| report annual and active-candidate EE **separately** | **NOT yet.** One figure is reported | #103 |
| normalize, apply the hostname rule, sort before merge | yes: lowercased at ingest, `ORDER BY` on every exported file | `src/ark/export.py` |
| candidate pool: union, dedupe, remove anything already in an annual master | yes | `src/ark/seed_pool.py` |
| malformed values kept in a separately labelled unparsed file | **NOT yet.** Rejects are counted, not emitted. He now ships his own `candidate_pool_unparsed_format.txt`, so the shape is his | #103 |
| resumable per-year queries with templates, checkpoints, retained stamps, failure states | mostly: `just query-queue` and `just cdx-pool` checkpoint and resume, stamps are retained in the journals. No failure-state log | #104 |
| **incomplete queries are scheduled work, not negative evidence** | yes, and it decides the `alt` remainder: 146.2 GB unread is a queue entry, not a closed source | `docs/sources.md` |
| a source-saturation ledger: coverage, overlap, evidence quality, cost, failure reason, decision | close. `docs/sources.md` carries all six for closed families, and the Usenet lane measured overlap at 22.2% and density per GB. Not yet one machine-readable ledger the generator reads | #105 |
| rebuild derived exports after an evidence-rule change | yes, and done for ADR-008: `ark export` regenerates every file from the store | `just rebuild` |
| RDAP: a registration event supports only what it directly names, and no later-year continuity | yes. `whois_creation` writes the creation year only, and no lane propagates a registrable's year to a subdomain | `src/ark/sources.py` |

**The two that are worth money** are the `www.<parent>` backfill and the DNS-listed hosts, both of
which C-55 closed on our reading of his purpose and XI reopens in his own words. Both are measured
before either is proposed, and neither is a re-collection: the evidence rows are in the store.
