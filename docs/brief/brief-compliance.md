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

## XII. Evidence-first acquisition and reproducible provenance (2026-09-17)

| his bullet | ours | where |
|---|---|---|
| separate, resumable per-year queries with template, stamp, response location and resume state retained | yes for the sweep lanes: journals keep the request and every row's stamp, a parent's position is saved and resumed | `scripts/engines/`, `data/raw/cdx_suffix/` |
| broad enumeration beneath benchmark domains is not a discovery priority | partly: the lanes still sweep held parents for the hostname unit; discovery moved to bulk indexes and registrable lists this round | `docs/round/findings.md` |
| a capped or timed-out query is a work-state, not negative evidence | yes: closures record the measurement under them and a partial read is a queue entry | `docs/registers/sources.md` |
| bulk dataset ledger: institution, title and edition, terms, URL, file identity, record location, year field, acceptance condition, code, per-record verification route | yes for the two bulk CDX collections: approval block, register row, byte size, the stamp field, the converter, the manifest's `evidence_url` | `docs/registers/approved-sources-list.md` |
| no hostname variant inferred from another form | yes, since 2026-09-06 | ADR-008, `src/ark/export.py` |
| undated discoveries are durable assets with evidence level, provenance, verification route and reason | yes: the candidate pool, the ISC collection and the header collection, each with provenance; the evidence level is a lookup on `acquisition_method` | `output/netnew/` |
| source-feedback ledger: coverage, yield, overlap, noise, cost, failures, next decision | close: `audit/source_saturation_ledger.csv` carries it per source; the positive half does not yet reach the generator brief | #105 |

## XIII. Evidence classification and hostname integrity gate (2026-09-17)

| his bullet | ours | where |
|---|---|---|
| annual master takes exact-host website evidence only | yes: `WEB_METHODS` is the allowlist, applied at export and in the figures, tested | `src/ark/evidence_types.py`, `tests/test_export.py` |
| DNS, registry, mail and Usenet headers, mentions are candidate assets with provenance and a route | yes: ISC and the header hosts each ship as a provenance-linked collection and in the candidate claim; registrables re-track to the pool (C-93, C-95) | `src/ark/export.py` |
| gate before merge, score or export: lowercase, syntax and semantic checks, PSL or documented historical TLD | yes: lowercased at ingest, label syntax, IP literals and reverse zones refused, pinned PSL plus a nine-entry historical ccTLD list | `src/ark/canonical.py`, `src/ark/delegation.py` |
| quarantine bare `www.<label>`, unknown terminal TLD, duplicated suffix | partly: unknown suffix and malformed labels are refused; the duplicated-suffix and bare `www.<label>` cases are not named checks | gap |
| machine-readable exclusion ledger with seven columns per validation run | partly: emitted for the header collection's run; `candidates_unparsed.txt` carries a reason per line for the rest | `src/ark/export.py`, gap |
| rebuild from the evidence store, never patch output files | yes: every shipped file is a query over the store; `ark rebuild` reproduces them from `provenance/` | `just rebuild` |
| candidate reconciliation removes names accepted in an annual master | yes, at export, against his six files and ours | `src/ark/export.py` |
| legacy records without an item-level ledger are quarantined | not applicable: every record in the store carries its evidence row; his own files are ingested as `prior_reused` and never re-shipped | `src/ark/stats.py` |
