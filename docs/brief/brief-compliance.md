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
| the same, one level up: `www.<parent registrable>` | yes. Backfilled as its own record, 6,915,924 rows, each holding a capture of that exact host; he credited the round that shipped them | ADR-009 |
| the same, for DNS-listed hosts | no, and he settled it himself. A DNS survey observation admits the host to the CANDIDATE pool only, because it does not establish that the host served web content; an annual record needs exact-host evidence for that year | `src/ark/hostnames.py` |
| annual masters and candidate pools are separate data products | yes | `output/netnew/`, `output/candidates.txt` |
| report annual and active-candidate EE **separately** | yes. Candidate EE prints under its own heading | `scripts/round/round_figures.py` |
| normalize, apply the hostname rule, sort before merge | yes: lowercased at ingest, `ORDER BY` on every exported file | `src/ark/export.py` |
| candidate pool: union, dedupe, remove anything already in an annual master | yes | `src/ark/seed_pool.py` |
| malformed values kept in a separately labelled unparsed file | yes. `candidates_unparsed.txt` ships with a reason per line, in the shape he uses | `scripts/round/unparsed_pool.py` |
| resumable per-year queries with templates, checkpoints, retained stamps, failure states | mostly. `query_health.py` writes a durable failure ledger inside `just cycle`, but its rows carry no time, so "unretried for a day" cannot be asked | #104 |
| **incomplete queries are scheduled work, not negative evidence** | yes, and it decides the `alt` remainder: 146.2 GB unread is a queue entry, not a closed source | `docs/registers/sources.md` |
| a source-saturation ledger: coverage, overlap, evidence quality, cost, failure reason, decision | close. The ledger exists as a CSV and `yield_priors.py` ranks what paid, but the generator brief is still handed only the closed list, so the positive half never reaches it | #105 |
| rebuild derived exports after an evidence-rule change | yes, and done for ADR-008: `ark export` regenerates every file from the store | `just rebuild` |
| RDAP: a registration event supports only what it directly names, and no later-year continuity | yes. `whois_creation` writes the creation year only, and no lane propagates a registrable's year to a subdomain | `src/ark/sources.py` |

**The two that were worth money** were the `www.<parent>` backfill and the DNS-listed hosts. He
settled both himself: the backfill is banked and credited, and the DNS hosts are a candidate asset,
not annual records. What is left on this page is reporting plumbing, not evidence.
