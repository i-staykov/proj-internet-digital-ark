# Phase 5 handoff

**You are joining the Internet Digital Ark on branch `phase-5`.** This document is the complete state
of the project as of 2026-08-10, the round's objective, and the things that will waste your time if you
do not know them. Read it fully before touching anything. It is long because the alternative is you
rediscovering, at cost, what is already measured.

Ivaylo's own summary of the round is in [phase5-plan.md](phase5-plan.md), and it is shorter. This is the
operational version.

---

## 0. Read these, in this order, before doing anything

| # | file | why |
|---|---|---|
| 1 | this file | state, objective, traps |
| 2 | [brief_amendments.md](brief_amendments.md) | what is currently being asked for. The scoring metric, the retired standard, the five priorities, his exact words on intelligent discovery |
| 3 | [sources.md](sources.md) | every source, what dates it, **what remains unexhausted in it**, and roughly fifty families already rejected with the measurement that killed each |
| 4 | [discovery.md](discovery.md) | the acceptance bar for a new source, and the four ways this project has got a projection wrong |
| 5 | [../README.md](../README.md) | what to run and what each command should print |
| 6 | [documentation.md](documentation.md) | why the pipeline is shaped as it is |
| 7 | [SPEC.md](SPEC.md) | the reviewer's original brief. Cited by roman clause number from 21 files. **Never edit or renumber it** |

`notes.md` is the dated decision log, 72 entries. Do not read it front to back; grep it when you want to
know why something is the way it is. **Every figure in it is historical by construction** and was true
against the store of that day.

## 1. What the project is, in one paragraph

Reconstruct the list of domain names that existed 1996-2001, for a reviewer (Prof. Xiaowei Ding) who
merges accepted `(domain, year)` records into six annual `.txt` files. A domain in an annual file is a
**claim about a year**, and every claim must name the observation that supports it: `domain_year.evidence_id`
is `NOT NULL` and foreign-keys a specific row in `evidence`, so there is no code path that writes a year
assignment without one. That is the **evidence wall**, and it is structural rather than a convention.

Scoring is **equivalent-English domains**: each record counts the English page-language share of its
right-most TLD, from a fixed table he supplied. `foo.uk` 0.9813, `foo.com` 0.6321, `foo.net` 0.4530,
`foo.de` 0.1324. A large non-English source is a small source.

## 2. Exact state, 2026-08-10

| | |
|---|---|
| Branch | `phase-5`, based on `main` at `0c929ca` (Phase 4, merged as PR #7) |
| Reviewer baseline | **`merged260810`**: 11,362,034 pairs, 6,226,386.4245 EE, at `feedback-phase-4/merged260810/` |
| Phase-4 outcome | **accepted in full**, 946,266 records, +603,401.7811 EE, +10.730988% |
| Phase-5 increment so far | **46,952 pairs, 19,522.3766 EE, 0.313543%**, mean weight 0.4158. `isc_survey` 42,299 pairs / 14,956.39 EE, `ia_cdx_bulk` 4,653 / 4,565.99 |
| Store | `data/ark.duckdb`, 7.2 GB, 9,736,539 pairs, 53.8M evidence rows, 8.2M domains |
| Candidate pool | 2,634,673 domains held with no year |
| Integrity gate | **nine** invariants, all PASS, no skips |
| Test suite | 285 tests, ~2 s |
| Collectors running | **the VPS only**, `digga@10.1.0.6`, `/projects/proj-internet-digital-ark`, deadline epoch 1787139003 = 2026-08-19T11:30Z. Local machine idle |
| Target | **none set for this round** |

The round window is 2026-08-09T13:51:03Z, when the phase-4 archive was cut, held in
`src/ark/baseline.py` as `CURRENT_ROUND_SINCE`.

**Read the split before planning anything.** `ia_cdx_bulk`'s 4,653 pairs are the two collectors' output
since that cut. `isc_survey`'s 42,299 were **found, not collected**: 496 per-TLD Network Wizards survey
shards had been on disk since 5 August, downloaded and never ingested, and they only entered the store
today because a broken stage in `just sources` was fixed and the stage then ran to completion for the
first time in days. They land in **1996 (+0.7001%) and 1997 (+1.4313%)**, the two years the Internet
Archive cannot supply in bulk.

That is worth internalising rather than just noting: **the largest single gain available this round so
far came from diffing disk against the ingest ledger, not from searching for anything.** See section 4.2
and the 2026-08-10 entry in `notes.md`. Do that diff first.

### The VPS: you cannot reach it on your own, and its clock is running

The second collector runs on `digga@10.1.0.6`, in `/projects/proj-internet-digital-ark`. Three things
about it that you need from the start.

**1. `10.1.0.6` is a private address, so you have to ask Ivaylo to bring the VPN up.** An `ssh` to it
will simply time out otherwise, and that is not a broken machine or a broken key: it is a closed tunnel.
**Ask, rather than debugging your own SSH configuration.** Access has been granted in short windows, so
when you get one, use it immediately and completely: fetch first, ask questions afterwards.

**2. Its journals are invisible to every measurement taken here until you fetch them.** This project once
ran the second machine for a day and a half with 5,793 year-records sitting on its disk, because nothing
here ever looked. `just engines` reports **UNKNOWN** rather than "everything is home" when it could not
reach the machine to ask, which is deliberate and is the fix for exactly that failure. When the link is
up:

```bash
bash scripts/engine_status.sh          # what it is doing, and which journals are not home
rsync -av --ignore-existing \
  'digga@10.1.0.6:/projects/proj-internet-digital-ark/data/raw/cdx/cdx_*.jsonl.gz' data/raw/cdx/
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz
```

Re-offering an ingested journal is skipped in milliseconds, so the glob is safe to run wide. Fetch on
every window you get: a journal left on the remote disk is work that has been paid for and not banked.

**3. It stops collecting at 2026-08-19T11:30Z and will not tell you.** Its supervisor was started with
the deadline epoch `1787139003`, and when that passes the process exits cleanly, leaving no error and no
notice. It runs under `setsid` with its own deadline, so it survives a VPN drop or a laptop shutdown, but
it does not survive its own clock. **Before that date, decide whether to extend it**, and note that
restarting it needs a VPN window plus a fresh queue shard, since a shard written before the
`merged260810` load is blind to what that release added:

```bash
# on this machine, rebuild and re-shard first
just query-queue 78,22
# then, in a VPN window, on the VPS
ARK_TARGETS=data/raw/cdx/queue_shard1.txt ARK_PREFIX=cdx_q1 \
    setsid bash scripts/supervise_cdx_pool.sh <new_deadline_epoch> 300 8 900
```

Do not start a collector here at the same time without asking. The archive rate-limits per IP address,
which is the only reason a second machine helps at all, and two clients from one address is worse than
one.

## 3. The objective

His framing, verbatim, and it is the whole brief for this round:

> This is an intelligent scientific discovery and knowledge discovery problem, not merely an ordinary
> downloading task. Please use a broad range of creative, intelligent methods for continued domain
> discovery. These should include automated analysis, association inference, multi-source clue mining,
> intelligent scientific discovery, automated knowledge discovery, automated search engines, automated
> DeepResearch engines, and other reproducible computational strategies. The objective is to keep
> generating new hypotheses, test them against dated evidence, and continuously expand coverage of
> previously unknown domains.

> The next step is to preserve the same evidentiary rigor while increasing the breadth, automation, and
> creativity of discovery.

The previous four rounds were a human finding a source, measuring it, and writing a collector. **He is
asking for the finding and the measuring to be automated.** The five priorities, in his order:

1. Residual opportunity **inside** every source already used: unprocessed files, failed parses,
   truncated runs, unqueried candidates, missing date partitions, low-recall extraction patterns.
2. Automated discovery beyond the current source set.
3. **Association and graph inference**: organisations, email addresses, hostnames, aliases, redirects,
   neighbouring records, ownership data, archived outbound links.
4. **Track new domains separately from filled years.** Both must stay visible.
5. Keep favouring English-language material.

### What "preserve the same evidentiary rigor" means mechanically

Do not relax any of these to make a harness easier to build. They are why phase 4 was accepted line for
line.

- **Per-item year evidence, no inference.** A capture in 1998 evidences 1998 and nothing else. No
  interpolation across years, no assuming continuity, no dating from a page's "last modified".
- **Master-eligible versus candidate-only.** `prior_reused`, `cdx_timestamp`, `artifact_listing`,
  `link_source`, `dated_directory`, `whois_creation` can assign a year. `link_target` cannot, ever, and
  `assign_year` refuses it.
- **The corroboration split**, which is the wall that makes wide extraction safe. Anything a human
  typed (`dated_directory`: a Usenet post, an OCR'd page, an email) is admitted **only if another source
  already places that domain in an annual file**. The other source proves the name is real; the dated
  artifact supplies only the year. A string appearing nowhere else goes to the candidate pool and claims
  nothing. **An invented name cannot reach an annual file**, by construction rather than by review.
- **Self-dating types take no split**: a registry creation date, a capture timestamp, a dated artifact
  listing. The record is the authority.
- Creation dates evidence **only** the year they fall in (brief III.6).
- **Quote the post-split number, never the raw one.**

## 4. Where the value is, measured

Ranked by equivalent-English per unit of effort, with every figure's status marked. **[M]** measured,
**[G]** guess.

### 4.1 RDAP candidate pool: ~82,700 EE, priced, no new idea needed

**[M]** The pool is 2,634,673 names; about 2.0M sit in an RDAP-served TLD; **~1.54M have never been
asked**, worth roughly **82,700 EE**, about 1.3 points against the new baseline.

**[M]** The route matters enormously. Direct to each TLD's authoritative server, resolved from the IANA
bootstrap file: **75 queries/second, zero refusals** over 391,461 queries. Through the `rdap.org`
redirector: 0.83 q/s and 18.8% refused. Of phase-4's 48,394 net-new RDAP pairs, 48,259 came from the
direct route and 135 from the redirector.

**[M]** It competes with **nothing** the archive engines use, so it is parallel capacity.

**[M] The constraint is yield decay, not exhaustion.** The list is ordered by how many distinct sources
saw a name, so it front-loads the names most likely to be real. `.com` returned 19.2% over its first
100,000 queries, then 11.4%, then 8.4%; `.net` went 20.3% to 4.1% over 114,000. Roughly 359,000 of the
1,345,949-name Verisign list is consumed.

**The open question worth measuring rather than assuming:** where does the RDAP tail's marginal EE per
query fall below the archive queue's head? Both are computable from journals already on disk.

```bash
just rdap-pool com,net        # build, sweep, ingest
```

Per-registry failure modes are all in `sources.md`: PIR blocks with 403 after ~850 queries rather than
throttling, Nominet refuses at 14, `.au` dates nothing because auDA re-registered the namespace in 2002.

### 4.2 Recall over bytes already on disk

**[M] The Usenet download is finished**: 19,231 of 19,233 catalogue groups are in `.processed`. There is
no more corpus to buy. But two re-reads of the same 383 GB returned **62,820.7 EE** (`usenet_address`:
ftp://, mailto:, typed addresses) and **28,460.3 EE** (`usenet_bare`: a plain `foo.com` in prose), both
with **no request sent**, because the original extractor could not see those forms.

The generalisable rule, and it has paid twice: **before writing a source off, check what the parser
actually reads.** `comp.mail.maps.mbox.zip` sat marked processed for a day with 1,480,910 UUCP registry
entries read as nothing, because a URL regex cannot see a payload in a record format.

What is left:

- **[M] Nothing is unread, and an earlier claim of "1,773 archives never opened" was stale.** Audited
  2026-08-10: catalogue 19,233 groups / 411,214,378,850 bytes; on disk 19,231 / 411,023,158,296;
  `.processed` 19,231 and set-identical to disk in both directions; **zero** archives on disk unread,
  **zero** whose size differs from the catalogue's, and no partial file anywhere. The two absent groups
  are `alt.irc` and `alt.music.oasis`, both refused with HTTP 500/502 across two retry runs.
- **[M] What is unmeasured is yield attribution, not ingestion.** The newest whole-corpus yield run
  covered **1,706 archives**, so **17,525 have never been through `measure_usenet_yield.py`**. No
  per-hierarchy or per-group value is known. `legacy/scripts/screen_usenet_archives.py` lists any archive
  with 0.0% in-window coverage. This needs no network and is the prerequisite for choosing where to widen
  an extractor.
- **[M] `alt.*` is fully downloaded, fully processed, and entirely unpriced.** Catalogue 15,288 groups /
  234,057,485,934 bytes, of which 15,286 on disk and all 15,286 processed. **79% of the groups and 57% of
  the bytes.** An earlier "14,910 groups, 229 GB, untested at scale" was the *remainder unprocessed at
  the end of 2026-08-01* and reproduces to the byte from the ingest log; it never described the download
  state. **[G]** many small `alt.*` groups are probably vanity archives announcing nothing, the trap
  `fetch_usenet_groups.py` documented for the `net` token. This is the largest open question about the
  project's largest source.
- **[M] Two seams have precise coverage gaps.** The header pass and the first address pass each covered
  19,083 archives, not 19,231: the 148-archive batch ingested 2026-08-08 as tag `auto084548` landed
  between them, so those 148 were never header-scanned. The bare-host pass enumerated all 19,231 archives
  but **only 9,759 produced a single row**; the sparsity, not the range, is the fact that matters.
- **[M] Four directories hold downloaded bytes nothing reads**, listed in `sources.md` under "Bytes
  already on disk that nothing reads". Best of them: `data/raw/pandora-titles/`, a National Library of
  Australia title index with its schema and crawl documentation beside it, **mentioned in no file in the
  tree**. `.au` weight is 0.9904, the highest in the table.
- **[M] `scripts/diff_usenet_resplit.py` is the safety tool for exactly this work**: it compares a
  staged re-split against journals already ingested and classifies rows NEW / PROMOTED / UNCHANGED, so
  widening a regex over an ingested corpus does not hand DuckDB duplicates. It has no justfile recipe
  and no doc reference, so it looks like dead code. It is not.

**Closed, do not re-propose:** the machine-written header seams. Measured over the whole corpus,
`Message-ID` / `Reply-To` / `Sender` / `NNTP-Posting-Host` gave 1,025,582 pairs, 207,980 corroborated,
**2,869 net-new, 1,038.4 EE**. `Path:` gave 7.1 million parsed hops across only **4,736 distinct
domains** and projects to about **30 EE**, and the Giganews donation carries no `Path:` before 2000 at
all. An older handback contains a 320-archive sample table suggesting ~16,500 EE for these; **that
sample was measured against a store that has since grown and is superseded.**

### 4.3 attrition.org: 3,174 EE, blocked on a licence

**[M]** 6,458 net-new pairs, 3,214 net-new domains, **3,174.08 EE** at mean weight 0.4915. All 33 index
files already downloaded to `data/raw/source_probe_260806/attrition/`. Evidence type would be
`artifact_listing`, self-dating, so no corroboration split. Blocked on **`CC-BY-NC-SA`** and whether
"NonCommercial" permits a paid deliverable. **That is Ivaylo's decision, not yours.** Full detail and
the two smaller caveats are in `sources.md`.

### 4.4 The archive queue: unmeasured against the new baseline, and that is itself the finding

**[M]** Before the `merged260810` load the gap pool held 498,993 domains over 521,618 gap pairs, up from
466,353 the previous week. **Both pools grow faster than the crawl closes them**, because a larger merged
baseline creates new bracketed gaps.

`merged260810` just added 946,266 pairs. **So the gap queue should have grown again, and nobody has
measured by how much.** Do that before ordering any queue: a queue written a day earlier is structurally
blind to what has landed since, and that exact staleness once cost a queue 102,628 targets worth 63,333
EE.

```bash
just query-queue-preview      # writes nothing
just query-queue             # -> queue_shard0.txt, queue_shard1.txt, queue_manifest.tsv.gz
```

**[M]** Hit rates: gap pool 96.0% to 97.5% on consecutive batches; candidate pool 90.6% for a link
harvested off an archived page down to 36.9% for a name merely mentioned in Usenet text. **[M]** 1996
returns an in-year capture only 5.4% of the time and 1997 12.6%, which is why `ark gaps` interleaves
early years rather than working them by volume. **[M]** Throughput is capped by the archive's per-IP
concurrency: 8 and 12 workers both measure ~506 queries/hour. **More workers change the failure mode,
not the rate.**

### 4.5 Priority (c), graph inference: the machinery exists, the loop does not

The reviewer asks for association across organisations, email addresses, hostnames, aliases, redirects,
neighbouring records and archived outbound links. What is already here:

- **`scripts/split_expansion_journal.py`** is the join point: archived outbound links enter through it,
  corroborated links becoming `dated_directory` and never-seen names going to the pool.
- **`output/seeds/`** (305 MB) is the hostname and URL pool before collapse to registered domains, and
  **`legacy-data/deduplicated_urls_2002-2014`** (~1 GB) is out-of-window hostnames that can never carry
  an in-window year. Neither is year evidence; both are **association material**.
- **`data/queue.sqlite`** (352 MB) is one row per fetch task with its HTTP status: the record of which
  questions were asked, which failed, and which were never asked. **It is the instrument for priority
  (a). Do not truncate it.**

**[G]** Nothing has been measured here. Note the structural risk before investing: the failure mode of
association is that it selects for authority. Usenet relay hops, institutional link directories and
award galleries all failed the same way, and the lesson generalises: **a source that selects for
authority cannot be net-new, however large it is.** 7.1 million relay hops were 4,736 domains, and a
CDX-derived baseline already held every one in every year.

### 4.6 Priority (d), which is a small code change and currently missing

`ark stats` computes `netnew_domains` but attaches equivalent-English only to **pairs**. So it cannot
report new domains separately from filled years, which he explicitly asked for. `_equivalent_english`
in `src/ark/stats.py` is where that goes. `round_figures.py` already prints "distinct domains in the
increment", and the one-domain discrepancy between that and `ark stats`'s net-new domains is not a bug:
it is a domain that gained a year while already being in the baseline, which is exactly the distinction
he wants tracked.

## 5. What the round has to produce, and what he actually reads

**None of the discovery work counts until it ships in this shape.** Get familiar with it before you start,
not at the end: two of the packaging guards exist because a round was cut wrong once.

### The deliverable

One `tar.gz` in `submissions/<round>/`, built by `just package` and nothing else. The staged tree is:

| in the archive | what it is |
|---|---|
| `additions/1996.txt` .. `2001.txt` | **the deliverable.** One domain per line, deduplicated within a year, C-locale sorted |
| `candidates.txt` | names held with no year yet. He asked for this to be as large as practicable |
| `masters/` | baseline plus additions merged, ready to use directly |
| `report.md` and `report.docx` | the round report. He asked for Word, so `pandoc` must be installed or packaging warns and ships markdown only |
| `sources.md` | every source: what dates it, how to fetch it, what remains in it |
| `provenance/` | the evidence graph as Parquet plus `LOAD.sql` and `trace.py`, so any single pair can be traced |
| `journals/` | the raw responses of every query ever made, which is what makes the rebuild offline |
| `audit/`, `logs/`, `dropped_domains.txt`, `seeds/` | per-source contribution counts, run logs, excluded baseline lines, the hostname pool |
| `baseline/` | the release the figures are measured against, plus the original, plus a README naming both |
| `source/source.tar.gz`, `COMMIT.txt` | the code as `git archive HEAD`, pinned to a commit |
| `verify.sh`, `SHA256SUMS`, `MANIFEST.txt` | the archive's own checks, needing only coreutils and python3 |

```bash
uv run ark export                       # refresh output/ from the store
uv run python scripts/fill_report.py    # substitute every figure into docs/report.md
just package                            # tar.gz plus SHA256, into submissions/<round>/
just verify-delivery                    # run the archive's own checks from outside
```

Then **add a row to `submissions/README.md`**, and unpack the archive somewhere unrelated to this
repository and follow its own README literally. That clean-room test has found two defects nothing else
did, including a crash on step three of the documented rebuild path.

### The report, and what he cares about

**Generated, never hand-written.** `docs/report.template.md` holds the prose and `[TOKENS]`;
`scripts/fill_report.py` fills every figure from the store and refuses to write if a token is left
unfilled. Packaging exits 1 if `docs/report.md` disagrees with what the filler would emit, so a hand edit
halts the build rather than shipping a stale number.

Its four sections are what he asked for and the order matters: **1.** what this round adds, **2.** where
the additions come from and why each is admissible, **3.** the extra filter on typed addresses,
**4.** how to reproduce.

**Keep it short.** Ivaylo's standing instruction, in his words: the reviewer is already familiar with the
framework and is not interested in technical details, but in **the quality of the newly-ingested
domains**. Focus on where the additions come from, why they are viable, and how they can be reproduced.
Anything else decreases value rather than adding it. Write one subsection per source that is **new or
changed this round** and none for the others; the generated table already carries every source's volume.

Per `SPEC.md` section IX the document must cover the methods used, newly identified methods, yield per
source, limitations, whether further expansion is worthwhile, and the evidentiary standard applied. Note
the last two: **a source you closed on measurement is a reportable result**, and saying so is worth as
much as an addition.

### The five fields he grades on

He set the format himself, and lines 1 and 2 are **his** database before our increment, with line 5 being
line 4 divided by line 2:

```
1. Total number of original domains 1996-2001
2. Equivalent-English total
3. Increment (records)
4. Equivalent-English increment
5. Equivalent-English growth rate  =  4 / 2
```

```bash
uv run python scripts/round_figures.py --verify
```

**Always send with `--verify`.** It re-scores the increment with **his own** `equivalent_english_domains.py`
and refuses the numbers if his total differs from ours or if his validator rejects a record we counted. A
record he rejects scores zero for him and full weight for us, which is a live risk every time an extractor
widens. Its overlap guard reading zero is also the proof the current release is actually loaded.

### Two things that must never be in the archive

Nothing addressed to a person, and no internal planning. `package_delivery.sh` ships
`git archive HEAD`, so **every tracked file reaches him** unless `.gitattributes` marks it
`export-ignore`. That is how one archive shipped an email draft's private "notes for Ivo" section.
`docs/notes.md`, `legacy/`, this handoff and the round plan are all export-ignored; email drafts live in
`private/`, which is git-ignored entirely. If you add a document about how to approach him rather than
about the data, export-ignore it in the same commit.

## 6. Eleven ways this project has fooled itself with a number

Every one of these cost real hours and each is a distinct mechanism. If a figure you produce could be
any of these, say so in the same sentence as the number.

1. **Wrong counting unit.** NYPW estimated at 27,276 net-new domains, measured at **53**: registered
   domains compared against raw hostname lines.
2. **Linear extrapolation over a self-repeating corpus.** A 120-archive pilot projected 1.9M EE against
   a true 62,821. A 0.58% sample proves the shape, never the total. Fit the saturation curve too and
   quote the lower number.
3. **A snapshot that went stale mid-run.** A header projection said ~10,889 EE and delivered 1,038.4,
   because it was measured against an export from three hours earlier and another ingest wrote 102,577
   overlapping pairs in between. **A snapshot is valid only until the next ingest.**
4. **Quoting the pre-split number.** 2,440,926 raw pairs admitted 107,304. The raw figure overstates
   24-fold.
5. **A stale baseline.** `merged260802` sat unread for five days while `ark stats` overstated net-new by
   the 151,949 records already credited. Silent, and it flatters us.
6. **A stale round window.** Fixed today by moving it into `baseline.py` beside the marker, but the
   mechanism stands: `held` counts candidates, candidates are never in the baseline, so only the time
   window separates this round's from last round's.
7. **A stale queue.** New evidence creates bracketed gaps as well as filling them. 102,628 targets worth
   63,333 EE were invisible to a queue two days old.
8. **Ranking by what an answer is worth, ignoring whether there will be one.** 1,709 queries at a TLD
   scoring 97.2% English returned five hits.
9. **Estimating a hit rate over a population that structurally excludes hits.** A domain that hits gets
   a year and leaves the pool, so measuring the pool measures the misses.
10. **A caveat that flatters itself.** A report said "about 1,200 pairs" where the measured figure was
    50,250, understating its own caveat fortyfold.
11. **Counting distinct domains over net-new pairs.** Reported 1,161,961 domains against a true 463,566,
    because a baseline domain gaining a year is a new pair on an old domain.

## 7. Operational traps in this specific repository

### grep here is not grep

In this shell `grep` is a function backed by ripgrep, which **honours `.gitignore`**. That hides
`private/`, `feedback-*/`, `legacy-data/`, `legacy/notes/`, `output/` and `data/` from any recursive
search. An audit of this repo reported a script as unreferenced when a working note cited it twice, and
missed every `lang` reference in the justfile. Use `command grep` with an explicit file list, and note
that zsh does **not** word-split unquoted parameters, so `command grep -n "$t" $FILES` greps one
nonexistent filename and returns zero hits for everything:

```bash
git ls-files > /tmp/files.txt
tr '\n' '\0' < /tmp/files.txt | xargs -0 command grep -n 'pattern'
```

### Two counting traps that return a confident wrong answer

`ls data/raw/usenet/*.mbox.zip | wc -l` returns **0**, not 19,231: 19k arguments overflow the exec limit
and a `2>/dev/null` swallows the error. Use `find data/raw/usenet -maxdepth 1 -name '*.mbox.zip' | wc -l`.

`command grep -c "A|B|C"` is a basic regular expression, so the pipes are **literal** and it returns 0 by
construction. That was used once as evidence a log held no failures. Use `grep -cE`.

Both belong to the same family as the ripgrep trap above: **a search that finds nothing has either proved
something or been pointed at the wrong place, and the two look identical.** Prove the negative by running
the same command against a case you know is positive.

### One live footgun in the Usenet tooling

`scripts/split_usenet_addresses.py` globs `usenet_*.jsonl.gz` inside its own `--in-dir` and writes its
two output journals **back into that same directory**. A second run in `data/raw/usenet_hdr/` would
therefore re-consume its own previous output as input. It has not bitten, because the first run's outputs
are no longer on disk, but it will if the header seam is re-read. Fix it before re-running that seam, not
after.

### DuckDB takes one writer

Many readers **or** one writer. Every read needs a retry loop on "Conflicting lock". `just maintain`
takes the write lock for seconds every 15 minutes, and three scripts open the store with **no** retry
and will crash against it: `split_tucows.py`, `collect_enron.py`, `measure_usenet_yield.py`. Open
read-only when measuring:

```python
duckdb.connect("data/ark.duckdb", read_only=True)
```

### `ark export` before `ark check`, always

`additions_not_double_counted` reads the exported annual files. Run the gate against a store whose
baseline moved since the last export and it reports every already-credited pair as a violation.
`just deliver` has the order right.

### Loading a reviewer release

Edit `src/ark/baseline.py` **first**, then `uv run ark ingest-legacy`. Passing only `--legacy-dir`
composes a marker that already exists and skips all six files behind six "already ingested" lines. Take
a store backup first: there is no unload command.

### Other traps

- **bash parses a `while` body as one compound command**, so editing a running loop script does not
  change the running loop. An RDAP ingest block added to a live `maintain` loop never took effect and
  24,422 creation dates sat unread.
- **`git filter-branch` resets the working tree**, deleting from disk any directory removed from history.
- **Never `kill -9` a collector.** It strands the `.part`, and since the ledger keys on the finished
  name, the work inside becomes unreachable. `just engines-stop` sends TERM and lets the batch publish.
- **Big data must never reach git.** A `git add -A` once swept a 1.3 GB baseline copy into history and
  made the branch unpushable. `.gitignore` now matches `merged*/` by name anywhere in the tree. Check
  `git status` before staging broadly.
- **`data/raw/ukwa/host-linkage.tsv.gz` is exactly 2^31 bytes and fails `gzip -t`.** Already
  investigated: the file is year-sorted 1995 to mid-2004, so the truncation cuts past our window and the
  1996-2001 head is complete. Not a defect. Do not re-investigate.

## 8. House rules, non-negotiable

- **Never `git push`, and never `git commit` unless asked.** Ivaylo commits and pushes. Work on
  `phase-5`.
- **Never add a `Co-Authored-By` trailer or any AI attribution**, anywhere. The project is an audition.
- **No em-dashes and no en-dashes** anywhere: code, comments, docs, prose, commit messages.
- **Log every decision** in `docs/notes.md` as a dated entry in the existing style, ending
  `**Signed off by Ivo: pending.**`. Never edit a figure inside an existing dated entry.
- **Explain and outline before non-trivial file edits**, and wait for the go-ahead. Propose, then act.
- **Comments short, human, objective, future-proof.** Say why, not what.
- **Run the gate before proposing a commit**, and never through a red one:
  `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run ark check`.
- **Update `README.md` in the same sitting** as anything that adds a tool or a command. It is Ivaylo's
  verification checklist.
- **Keep changes atomic.** One logical unit per commit, and flag natural commit points.
- **Never edit** `docs/SPEC.md` (cited by clause number from 21 files), the three frozen files in
  `submissions/phase-4/` (their value is being exactly what was sent, defects included), or
  `docs/report.md` (generated; packaging exits 1 if it disagrees with `fill_report.py`).
- **`legacy/` is read-only.** Not linted, not tested, not shipped. If something there becomes useful,
  move it out and bring it up to standard rather than editing in place.
- **All raw data under `data/raw/` stays.** This round is about what is unexhausted in it.

## 9. If you build a discovery harness

This is the round's ask, so here is the shape that follows from sections 3 to 5. Nothing below is
decided; it is the constraint set.

- **The unit is a hypothesis: a source plus a claim about what dates its individual items.** That is the
  unit section 3 can reject cheaply, and "what dates one item" is the fastest filter available. If you
  cannot answer it in one sentence, the source is seed-only.
- **Pricing is a sample measured against the live store**, reported as net-new pairs, net-new domains and
  the **mean weight of the net-new part**, with projections labelled. Section 6 is the checklist for not
  fooling yourself, and every entry on it is a mistake already made once here.
- **The acceptance bar** is in `discovery.md`: per-item year evidence, roughly 5,000 net-new pairs
  plausibly available, mean weight at or above 0.6 good and below 0.4 needing a volume argument.
- **The rejected register is an input, not an afterthought.** Roughly fifty families are closed with
  proofs, several of which look obvious: DMOZ pre-2002 dumps, IRCache proxy traces, the Internet Traffic
  Archive, shareware CD-ROM ISOs, web rings, the Australian Web Archive. A proposal that duplicates a
  closed lead should die before it costs a request.
- **Count the two outcomes separately** from the start, per priority (d), rather than adding it later.
- **Be a good citizen.** The Internet Archive has refused this project outright three times. Honest
  User-Agent naming the project and a contact address, honour `Retry-After`, back off on 429/503/504,
  modest concurrency. Prefer bulk downloads and non-IA hosts. If the VPS is collecting, do not point a
  third heavy client at `web.archive.org`.
- **Cheapest wins first.** Two of the three largest phase-4 additions came from bytes already on disk and
  sent no requests at all. A harness that only knows how to download will miss the best material in the
  project.
