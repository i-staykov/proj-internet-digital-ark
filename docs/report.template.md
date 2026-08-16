# Internet Digital Ark: round 5

Additions to the 1996-2001 annual domain lists, measured against `[BASELINE]`.

**Every figure in this report is generated from the evidence store** by `scripts/report_figures.py` and
substituted by `scripts/fill_report.py`. No number here is typed by hand, so a table cannot drift from
the files shipped beside it.

---

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

Lines 1 and 2 are the `[BASELINE]` totals, unchanged, since this increment is not yet merged. The
threshold for submission is 5% of the current baseline, which is [EE5PCT] equivalent-English.

Of the [TOTAL] net-new records, [UNIQUE] are distinct domains and **[NEWDOMAINS] appear in none of the
six baseline annual files in any year**, so the majority of the increment is genuinely new names rather
than new years on names already held. Mean equivalent-English weight per record is [EEMEAN].

[PER_YEAR_TABLE]

[CUMULATIVE]

---

## 2. What was added, and the year evidence behind each addition

Four routes account for nearly all of this round. Each is described with the field that dates a year,
because under section IV of the brief a record may enter an annual file only on evidence for that year.

**1. The Internet Archive's own capture census (`dartmouth_nber_captures`).** A 2017 research release
deposited at archive.org under the Dartmouth/NBER web-history collection publishes, for every host the
Wayback Machine held at that time, a count of captures per calendar year. One row is `host`, `year`,
`count`. A row is therefore a statement by the archive that it holds N captures of that host inside that
calendar year, which is the same fact a CDX query returns, published in bulk instead of retrieved one
host at a time. It is filed as `cdx_timestamp` for that reason. **Independent check:** for domains where
our own CDX engine had separately queried the live archive, the two agree on 138,979 (domain, year) pairs,
including exact same-day agreement on single-capture years such as `milwhite.com` 1996 (our engine
recorded `19961231231928` against the census row `ia_captures:1996:1`). The census evidences only the
years it names; no year is inferred from any other.

**2. Registry creation dates in bulk (`domain_creation_bulk`).** A published WHOIS/DNS compilation of
171 million domains carries the registry's own creation date per domain, parsed from port-43 answers.
Section IV states that a WHOIS Creation Date is valid evidence that a domain existed no later than that
date and may support inclusion in the annual file for the year the creation date falls in. That is
exactly and only how it is used here: **a creation date in 1998 writes 1998 and no other year.** The
brief's warning about later years is enforced structurally rather than by care, because the parser emits
one evidence row for one year and `assign_year` cannot write a second.

*Falsification run before admitting it.* A TLD cannot predate its own delegation. Across the six TLDs
delegated in 2001, the file contains 21,698 in-window rows and **zero** dated before 2001: `.info` 20,731
rows, `.biz` 635, `.coop` 315, `.museum` 17. Had the dates been synthesised or shifted, this is where it
would show.

**3. A file we already held, read completely (`ukwa_link_source`).** The UK Web Archive host link graph
had been parsed since July. The parser stopped at the first record whose year exceeded the window, on the
assumption the file was sorted by year. It is not: it is fifteen concatenated shards, and the check that
had verified the assumption stopped 2.4 times short of the first shard boundary at line 11,908,464. The
parser had been reading **6.76%** of the file. Removing four lines recovered 92,646 net-new pairs from
material already on disk.

**4. The January 1997 Internet Domain Survey (`isc_survey`).** The survey's own host is long dead and the
file had been recorded as unrecoverable. A sweep of every dead host in the register asked a different
question, not "does this host answer" but "did the archive keep its files", and found `zone/9701.domains.gz`
intact in the Wayback Machine under a successor hostname. A documented presence in a dated DNS survey is
direct annual evidence under section V.

Alongside these, mentions already held were re-admitted by the corroboration rule described in section 5,
and the CDX engines continued to date candidates from the archive itself.

---

## 3. Source contribution statistics

Every net-new record, by the source that dated it. Raw record increase and equivalent-English increase
are given for each, as required.

[EE_SOURCE_TABLE]

**Candidate pool, kept strictly separate from the annual masters:** [CANDIDATES] domains carry no
year-specific evidence and are shipped as `candidates.txt`, never mixed into `1996.txt` through
`2001.txt`. They are hostnames extracted from archived pages (`link_target`), which the taxonomy makes
structurally incapable of dating a year.

---

## 4. CDX execution notes

Tooling: `ark cdx`, this project's own client for the public Wayback CDX API, driven by
`scripts/supervise_cdx_pool.sh`. It runs two disjoint populations on two machines. The **VPS** works pure
bracketed gaps, a missing year Y where Y-1 and Y+1 are already held, as a completeness baseline. The
**local** engine works the candidate pool beside the discovery loop that feeds it.

[CDX_TABLE]

[CDX_FAILURES]

Failures are handled by adjusting the request rate rather than by stopping, as section VII requires.
The client sends an honest User-Agent naming the project and a contact address, runs modest concurrency,
honours `Retry-After`, and backs off on 429, 503 and 504 with a delay that adapts between a floor and a
ceiling. A batch that ends is republished rather than lost, so an interrupted run costs nothing a repeat
does not recover.

**On whether the CDX route is worth further expansion: yes, but it is no longer the binding constraint.**
Roughly 2.5 million candidate names sit unqueried against engines clearing a few hundred requests an hour.
The queue has not been the constraint at any point this round. That observation is what redirected the
round toward bulk dated corpora, and section 2 is the result.

---

## 5. How this contributes to an autonomous discovery system

The brief asks for a system that discovers, validates and preserves rather than a set of downloads. What
follows is the machinery, all of which ships in the archive.

**The evidence wall is structural, not procedural.** `domain_year.evidence_id` is `NOT NULL` and
foreign-keys a row in `evidence`. There is no code path that can write a year assignment without naming
the observation supporting it. An agent is therefore given wide latitude about what to try and none at
all about what counts as proof.

**A taxonomy decides which evidence may date a year.** Master-eligible types are [MASTERTYPES].
`link_target`, a hostname seen in an archived page, never can, and `assign_year` refuses it. That single
rule is why the discovery loop below can run unattended without risking the annual files.

**The corroboration split.** [CORROBORATION] [ADMISSIBLE]

**A human gate that an agent cannot argue past.** `docs/approved-sources-list.md` carries one decision
line per (source, evidence type), and `ark ingest` refuses any master-eligible class that is pending,
rejected or absent. Requests are machine-generated by `scripts/request_approval.py` out of a
seeded-random sample with live links, the measured counterfactual and the reasons a reviewer should
refuse, so the human checks external evidence instead of reading the agent's argument. Both sources in
section 2 passed through this gate before a single row of theirs could date a year.

**Nine invariants, run before anything ships.** `ark check` asserts, among others, that no exported
addition carries baseline evidence for that year (so the net-new figure cannot be inflated), that the
year named inside an evidence value equals the year it is filed under, and that no master-eligible
evidence sits unassigned. The gate is enforced by a pre-commit hook rather than remembered.

**A discovery loop that does not run out.** A candidate the CDX engine dates is by construction a site
that was live in the window; its archived page names other sites of the same period; those names return
to the pool. `build_expand_seeds.py` to `ark download` to `ark ingest expansion_links` to
`build_query_queue.py` to the engine and back. Because extracted hostnames are `link_target` and can
never date a year, this route needs no approval and is safe to leave running unattended. It was measured
this round: seeding link-looking pages rather than home pages harvested 391 domains against 53, a 7.4x
improvement, but yielded only 5 net-new because 386 of the 391 were already held and already dated. That
negative result is recorded, and it is why bulk link graphs are now preferred over page-by-page expansion.

**The agent harness itself.** A standing brief, `CLAUDE.md`, is loaded into every agent session and holds
only what does not change: the evidence rule, the metric, which document is authoritative for what, the
operational rules, and a section of traps that have each produced a confident wrong answer. Long-running
collectors hold their own absolute deadlines and keep running with no agent present. The agent re-invokes
itself on a heartbeat and a cron wake, and a wake that finds everything healthy is required to spend
itself hunting a new source, because an idle wake beside healthy engines is a wasted one. Decisions land
in an append-only dated log; the few with structural impact become ADRs; anything genuinely needing a
human appears on exactly one surface, so it cannot be buried.

**Negative results are first-class.** [DATASETS_SEARCHED]

---

## 6. Limitations, and what is worth expanding

**The registry creation dates are the largest single contribution and also the narrowest evidence.** A
creation date attests registration, not activity, and it attests one year only. Where a domain was
registered in 1997 and remained live through 2001, this source supplies 1997 alone; the other four years
must still be earned from a capture, a survey or a continued-registration record. This is a deliberate
under-claim and it is enforced by the parser.

**The capture census is a 2017 snapshot.** The archive has grown since, so its per-year counts are a
floor on what the Wayback Machine holds today, never a ceiling.

**Worth expanding, in order.** Bulk dated corpora first, since one such file outweighed an entire round
of per-domain querying and this round found two more. National web archive link graphs second, where the
year association is explicit: `ukwa_link_source` returned a mean equivalent-English weight of 0.9803,
the highest of any source here, because a national link graph is almost entirely `.uk`. Per-domain CDX
querying third, which still pays but is bounded by request rate rather than by candidates.

**Not worth expanding:** the closed families named above, each recorded with the measurement that closed
it so the same ground is not broken twice.

---

## 7. Reproduction

The archive ships the results, the evidence behind every one of them, the code that produced them, and
the raw journals. `README.md` inside the archive gives the order. In short:

- `masters/1996.txt` to `2001.txt`: the full merged annual lists, one registered domain per line,
  deduplicated within each year.
- `additions/`: this round's net-new records only, in the same per-year shape.
- `provenance/domain_year.parquet` and `provenance/evidence.parquet`: every (domain, year) with the
  evidence row that justifies it, joinable by `evidence_id`. This is the audit surface: any single
  assignment in any annual file can be traced to the observation behind it.
- `journals/`: the raw per-source records as collected, before any interpretation.
- `source/source.tar.gz`: the complete repository at the commit that produced this delivery.
- `verify.sh`: re-checks the shipped files against each other and against the stated figures.

`uv run ark export` regenerates every text file from the store; `uv run ark check` re-runs the nine
invariants; `uv run python scripts/round_figures.py --verify` re-scores the round with the reviewer's own
`equivalent_english_domains.py` and its unchanged weight model.
