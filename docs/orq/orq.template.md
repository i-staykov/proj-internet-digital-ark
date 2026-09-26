# Open Research Questions

These are our answers to the two open research questions of section IV-A of the project brief,
built on [BUILT_AT] from fleet commit `[FLEET_COMMIT]` against his release [RELEASE]. No figure
here was typed: the results on data from before [FIRST_YEAR] are read from the fleet's own lead
files at build time, and every result on assigning years comes from a command in the second
question's table that ran during the build. Each question is answered under the six headings of
section X. The folder `Open Research Questions` holds this text as `Open Research Questions.docx`
with the files it names, and the folder `开放性研究问题` holds the same answers as plain text,
one file per question.

Every test carries one of three labels, computed from its record and never typed:

- **Validated**: the finding records its artifact's `sha256`, its extractor `extract.py`
  compiles, the finding records the command that priced it, and an independent verify leg
  fetched the same bytes, re-ran that command and confirmed the figure.
- **Tested, not independently verified**: the test ran and left its record, but one of those
  is missing, or nothing independent has run it again. `tests.csv` names what is missing.
- **Pending validation**: an approach scouted or proposed and never tested.

This build holds [LABEL_COUNTS].

## Q1. How can historical web data from before 1996 be discovered and acquired at scale?

### Proposed approaches

The evidence rule of section XIII counts a hostname for a year only on web evidence of that
year, and the Internet Archive began crawling in [FIRST_YEAR]. A record from before
[FIRST_YEAR] cannot enter an annual file, so this question is about finding such records and
holding them apart, as an auditable candidate collection. We rank sources by what wrote the
date:

- A web capture from before [FIRST_YEAR] held by another custodian: a national library, a
  university archive, or a mirror that kept its HTTP logs. Only this kind meets the evidence
  rule's own standard, and its coverage is small and institutional. Pending validation: the
  lens scouted a custodian's public index and tested none.
- A machine that named the exact host at a date: HTTP server logs, the host tables of the
  network information centres, dated FTP site lists, news and mail headers. It proves a host
  in service, not a website.
- A date a person wrote beside a host: directories, guides, catalogues and their scans.
  Candidates only.

The fleet's pre-[FIRST_YEAR] lens scouts each lead: it finds a public artifact and records its
address, a sample record and what dates one item. A lead worth pricing goes to a price leg,
which writes an extractor, fetches the artifact and records its `sha256`, extracts each host
with its record's date, and prices the result against a snapshot of his release. Only a
priced find goes on to an independent verify leg.

### Completed related work or tests

The lens scouted [Q1_LENS_LEADS] leads. Left out here, because a test extracted their records,
every year it counted is [FIRST_YEAR] or later, and nothing in the lead names an earlier year:
[Q1_EXCLUDED]. Of the other [Q1_MEMBERS], [Q1_TESTED] reached a price leg and [Q1_PENDING]
were closed at the scout leg, before any extractor ran; `tests.csv` gives each one's reason.
Of the priced, [Q1_VALIDATED] are Validated ([Q1_VALIDATED_LIST]) and [Q1_TESTED_ONLY] are
Tested, not independently verified.

Each figure names the snapshot of his release it was priced against and that snapshot's
manifest, since a snapshot is rebuilt under the same name and one name can carry several
manifests.

[Q1_TESTS_TABLE]

### Preliminary technical-feasibility findings

Bulk records from before [FIRST_YEAR] are public and can be fetched whole, hashed and read by
a short extractor, and a Validated test reproduces: its verify leg fetched the same bytes,
re-ran the pricing command and printed the same figure. A host table dates every record by
its edition's header, and an HTTP log dates every request.

### Preliminary practical-operability findings

The EE column is the figure the price leg printed on the track it names, not a claim. Under
the fleet's own price rule a record dated outside [FIRST_YEAR] to [LAST_YEAR] is an item on
neither track, and the dated column counts the extracted records inside that window: a figure
over none of them counts nowhere. The candidate claim takes registrable names and the ISC
survey's hostnames, so the hostname part of any other candidate figure ships nothing, and a
figure on the annual track enters an annual file only beside a web capture of its year. The register line each test names in
`sources.csv` records what it ships. The fleet has closed the lens, and the tests above are its
whole record.

### Limitations

The date on a record is its edition's or its log's, not a website's. A host table lists
machines, most of which never served a website, and an HTTP log names the clients that
fetched as well as the servers fetched from. Coverage leans to military, academic and
government networks. A figure priced against an older snapshot of his release could move
against the current one.

### Next steps

Each step below is Pending validation.

- Hold a collection from before [FIRST_YEAR] apart from the annual files, with source,
  `sha256`, record location and date for every host, and an overlap report against his files.
- Decide the earlier host table editions in the same mirror as one sweep on the candidate
  track.
- Ask the custodians of the first kind of source what they hold, since only their captures
  meet the evidence rule.
- Admit a new kind of evidence only on his ruling.

## Q2. How can the year in which a website existed be determined more accurately?

### Proposed approaches

- **Direct evidence assigns a year**: web evidence of the exact host in the target year, which
  is an archive-index capture that answered `2xx` or `3xx`, a dated snapshot, a dated web
  link-graph record naming the host, or a custodian's per-host extract. Only this enters an
  annual file.
- **Error captures are candidates.** A `4xx` or `5xx` capture shows that a server answered,
  not that the host served a site: a wildcard virtual host answers `404` for any name.
- **Discovery-only evidence ranks, never assigns**: DNS surveys, registry records and
  server-written headers order the names to check against an archive.
- **No inferred continuity.** A name held in one year is no evidence for the next, and his
  own files show why.
- **Reconciliation at export**: every candidate is diffed against his `candidate_pool.txt`
  and his six annual files, and a name accepted into an annual file leaves the pool.
- **One evidence level per record** (direct, discovery, unresolved), so the reconciliation
  can be checked by machine on his side. Pending validation.
- **Dated bounds from WHOIS, DNS and dated datasets**, used to bound a year rather than assign
  one. Pending validation.

### Completed related work or tests

Every command below ran during this build, with `$HIS` his release [RELEASE], `$NETNEW` our
exported collection, `$CDX` the raw CDX journals and `$AUDIT` the status audit's summary, all
read from files. A row without a command is a proposal nothing has run.

| id | command | register anchor | result |
|:------------------------|:------------------------------------------------------------|:--------------------------------|:----------------------------------------|
| `q2-continuity-1999-2000` | `wc -l < <(LC_ALL=C comm -12 "$HIS/1999.txt" "$HIS/2000.txt"); wc -l < "$HIS/1999.txt"` | `docs/lore/laws.md#Compute headroom from the adjacent year only` | [Q2_CONTINUITY_1999_2000] |
| `q2-continuity-2000-2001` | `wc -l < <(LC_ALL=C comm -12 "$HIS/2000.txt" "$HIS/2001.txt"); wc -l < "$HIS/2000.txt"` | `docs/lore/laws.md#Compute headroom from the adjacent year only` | [Q2_CONTINUITY_2000_2001] |
| `q2-pool-his` | `wc -l < <(LC_ALL=C comm -12 "$HIS/candidate_pool.txt" <(LC_ALL=C sort -m -u "$HIS"/199[6-9].txt "$HIS"/200[01].txt))` | `docs/brief/ding/project-brief.md#candidate_pool.txt should be reconciled` | [Q2_POOL_HIS] |
| `q2-pool-ours` | `wc -l < <(LC_ALL=C comm -12 "$NETNEW/candidate_additions.txt" <(LC_ALL=C sort -m -u "$HIS"/199[6-9].txt "$HIS"/200[01].txt))` | `docs/brief/ding/project-brief.md#candidate_pool.txt should be reconciled` | [Q2_POOL_OURS] |
| `q2-status-share` | `uv run python scripts/round/orq.py --measure q2-status-share --inputs-from-env` | `CLAUDE.md#Error captures (4xx, 5xx)` | [Q2_STATUS_SHARE] |
| `q2-yearfill-kill` | `uv run python scripts/round/orq.py --measure q2-yearfill-kill --inputs-from-env` | `docs/registers/sources-closed.md#CDX exact-host year fill` | [Q2_YEARFILL_KILL] |
| `q2-evidence-level` | none | `docs/brief/ding/project-brief.md#distinguish direct year-specific website evidence` | Pending validation |
| `q2-dated-bounds` | none | `docs/brief/ding/project-brief.md#historical WHOIS, historical DNS, dated datasets` | Pending validation |

Fleet experiments on this question:

[Q2_EXPERIMENTS]

### Preliminary technical-feasibility findings

No check above needs a database: the continuity and pool checks are sorted merges of text
files, the status share reads the audit's summary, and the year-fill check reads the lanes'
journals. Continuity cannot be inferred: of his [CONTINUITY_1999_2000_BASE] names for [CONTINUITY_1999_2000_FROM],
[CONTINUITY_1999_2000_PCT]% are in his file for [CONTINUITY_1999_2000_TO], and of his
[CONTINUITY_2000_2001_BASE] for [CONTINUITY_2000_2001_FROM], [CONTINUITY_2000_2001_PCT]% are in
his file for [CONTINUITY_2000_2001_TO]. A rule that carried a name into the next year would
assign an unsupported year to every name that did not appear there. His `candidate_pool.txt` shares
[POOL_HIS_COUNT] names with the union of his six annual files, and our candidate collection
shares [POOL_OURS_COUNT].

Of [STATUS_SHARE_ROWS] raw CDX rows behind our hostname records, [STATUS_SHARE_FOURXX_PCT]%
answered `4xx` and [STATUS_SHARE_FIVEXX_PCT]% `5xx` (`4xx` by family: [STATUS_SHARE_FAMILIES]).
Of [STATUS_SHARE_SHIPPED] shipped records the audit checked, [STATUS_SHARE_REPOINT] rest on an
error capture and are to be repointed to the earliest `2xx` or `3xx` capture of their host and
year, and [STATUS_SHARE_RETRACT], which have none, are to be retracted.

### Preliminary practical-operability findings

Direct evidence is expensive to find. The year-fill lane asked the archive index one exact host
per query, from [YEARFILL_KILL_LANES] clients, for the hosts of names he holds in
[YEAR_BEFORE_LAST] and not in [LAST_YEAR]. Its [YEARFILL_KILL_NAMES] names had
[YEARFILL_KILL_HOSTS] hosts with a capture in [LAST_YEAR], and his file already held
[YEARFILL_KILL_HELD] of them. The other [YEARFILL_KILL_NOT_HIS] were worth [YEARFILL_KILL_EE] EE,
at most [YEARFILL_KILL_RATE] EE per client-hour, against the floor of [YEARFILL_KILL_FLOOR] below
which a lane is stopped after two hours. The lane was stopped.

### Limitations

An archive index shows only what the archive crawled, so a missing capture does not prove a
site was absent, and every method here errs toward omission. A `2xx` capture can be a parked
or placeholder page. The status audit reads the raw CDX we hold, which is part of the
archive's index, not all of it. The continuity figures describe his files, not the web.

### Next steps

Each step below is Pending validation.

- Add the evidence level to every exported record, and test that his side can check it by
  machine.
- Test dated bounds from WHOIS and DNS against records whose year a capture already shows,
  before using them.
- Run year-assignment experiments in the fleet and land them here, each Validated only when a
  clean re-run prints the same bytes.

## Files in the Open Research Questions folder

- `tests.csv`: one row per test run, with its label, what keeps it from Validated, the fleet
  run it came from, and that run's cost from the fleet ledger in tokens, seconds and seven-day
  points. A run the ledger does not hold says "not recorded". A re-run of this build uses no
  model.
- `sources.csv`: every source behind a test: the artifact's address and `sha256`, the files of
  his release a command read, and the register line each figure rests on.
- `evidence/`: the fleet's own record of each test (scout notes, finding, verify), and the
  inputs a re-run read when they are small.
- `code/`: each test's extractor, as the fleet holds it.
- `logs/`: for a fleet test, the checks behind its label; for a re-run, its command, output
  and seconds.
- `samples/`: each fleet test's sample record as its lead quotes it, and the hosts a re-run
  found.
- `screenshots/`: [SCREENSHOTS].

To build both folders again in our repository, beside a checkout of the fleet:
`uv run python scripts/round/orq.py --preview DIR --fleet FLEET`. It reads the fleet's `leads/`
and `ledger/` and the repository's exported collection, status audit and CDX journals, which the
delivery's `source/` does not carry.
