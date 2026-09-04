# Runbook: what to run and what each command should print

**The working manual for every command in this repository, with the output each one should
give.** `README.md` is the short front page; this file is the long form. It was named
`operations.md` until 2026-09-02.

## Where it runs

```
GitHub Actions fleet (private repo, self-hosted runner on a small VPS)
   generator, on a schedule ........ proposes hypotheses from the register and the store
   researcher waves, four times daily  screen and price them; findings land as artifacts
   re-opener, daily ................ re-reads closed verdicts when a measurement screen retires
   improver ........................ tunes prompts and model choice from per-run telemetry
   weekly digest ................... one page of yield, cost and recommendations
VPS (always on)
   two archive collectors under systemd, querying capture indexes at zero token cost
Laptop (episodic, human-supervised)
   `just bank` ..................... drains fleet findings, admits, ingests into the
                                     evidence store, gates, pushes; packaging and reports
```

Orchestration lives in that separate private repo so this one stays free of secrets and runner
exposure. Results land here on the `live` branch and reach `main` as merge-commit snapshots, so
`live` keeps its history.

## Three ways to check this work

| Tier | What it proves | Cost | How |
|---|---|---|---|
| **1. Verify the shipped result** | Nothing has changed and every pair traces to a recorded observation | ~10 s | `bash verify.sh` at the delivery archive's root |
| **2. Rebuild from the evidence** | The shipped lists follow from the shipped evidence, byte for byte | ~1 min | `uv run ark rebuild ../provenance` |
| **3. Rebuild from the original sources** | The evidence follows from the source data | a large download, then ~20 min | Parts 1 and 2 below |

Tiers 1 and 2 need no network and no source data. Tier 1 needs nothing from this repository at all.

**Tier-3 cost figures date from the phase-1 archive and have not been re-measured since.** What tier 3
cannot re-derive is measured and larger than it used to be: on 2026-08-18, 2,387,824 assignments of
5,323,465 (44.9%) came from two sources whose inputs cannot ship, one withdrawn by its host and one
under a licence that forbids redistribution. None of them falls inside this round's additions, and
tier 2 reproduces all of them from the provenance export. `docs/delivery_readme.md` has the table.

## Reproduce the results

Every step is re-runnable: work already done is skipped, so an interrupted run finishes by running the
same command again. Each run appends to a log in `data/logs/`.

```bash
just setup       # uv sync
just hooks       # install the pre-commit gate, which refuses a red commit
just reproduce   # all six stages below, offline
just check       # lint + format-check + tests, then the data invariants
```

`just check data` runs the data invariants and `just check code` runs the code checks; the bare
`just check` runs both. They fail differently, which is why neither answers to the bare name.
`lint`, `fmt`, `test` and `scan` are the same dispatcher's other words.

**Eight recipes take a word instead of having one name each**, which is what keeps the set under
forty: `check`, `collect`, `engines`, `expand`, `reproduce`, `schedule`, `ship` and `verify`. Each
prints its own choices when handed a word it does not know, `just collect` with no source lists the
collectors, and `just` alone lists everything with the choices underneath.

### What is on disk, and the copy of it elsewhere

```bash
just verify raw                          # checksum every data entry, regenerate docs/retention.md
just verify trees                        # each extracted release tree against its zip, by CRC
just verify offsite --manifest           # price the off-site payload into data/offsite-manifest.tsv
just verify offsite --upload --yes       # rclone it to gdrive:ark-offsite, one log per entry
just verify offsite --verify             # compare the remote by hash, downloading nothing
```

The payload is the part of [retention.md](retention.md) that nothing else can bring back: our own
journals, the reviewer releases (the zstd trees under `data/archive/` among them), the frozen
`submissions/phase-*`, live inputs with no refetch route, and unpriced corpora other than the two
Usenet ones archive.org serves again. Regenerable entries and anything with a refetch URL stay local
only, and `private/` has no row and cannot appear. The frozen submissions are checksummed into
`submissions/SHA256SUMS`, at the root, so nothing is written inside a phase directory. An entry
`--verify` calls verified is the precondition for deleting its local bytes; the deletion itself is a
separate, human-approved table.

### What is unexhausted, in one command

```bash
just residual                       # all five checks
just residual --check unread --verbose
```

`just residual` answers the reviewer's first priority mechanically: **unprocessed files, globs that
match too little, downloaded bytes with no parser, and derived target lists a newer baseline has
invalidated.** Read-only, no network, no write lock, so it is safe to run at any time and it is the
right thing to run *before* deciding what to collect.

| check | what a finding means |
|---|---|
| `unread` | a documented ingest glob matches a file the ledger has never read. **The cheapest yield in the project**: price it against the live store before ingesting, per [docs/discovery.md](discovery.md) |
| `glob_too_narrow` | the ledger holds a file the documented glob cannot reach. Loses nothing now, but `just reproduce` rebuilds a store without it |
| `unreferenced` | a directory under `data/raw/` that no ingest glob points into at all |
| `usenet` | the corpus against its own `.processed` ledger and the catalogue: unread, size mismatches, partial files |
| `stale_derived` | a target list or queue older than the rows it should carry, so a collector reading it cannot see them. Compared against the mark that actually invalidates each list, **newest pairs** for a gap queue and **newest candidates** for a pool queue, rather than against the baseline release, which changes monthly and once called three stale lists fine |

**It is deliberately not a gate.** It reports and exits 0, because unread material on disk is a fact
about the round rather than a broken invariant, and a check that failed the build for it would be
turned off. It exists because the same diff, run by hand on 2026-08-10, found 496 ISC survey shards
worth 14,956 equivalent-English that had been sitting on disk for five days.

## The discovery harness

The reviewer asks for "automated analysis, association inference, multi-source clue mining, automated
knowledge discovery, automated search engines, and automated DeepResearch engines", and says plainly
that this "is not simply a data-searching or data-downloading effort". The harness is the answer, and
it is built around one admission: **the work splits into what a program can do correctly unattended
and what needs judgement, and pretending otherwise is how autonomy becomes theatre.**

| | command | what it does |
|---|---|---|
| memory | `just state` | regenerates [docs/ROUND.md](ROUND.md), the current state, from the programs that own each figure |
| memory | `just hypo list` | the ledger: what has been proposed, priced, adopted or killed, with status |
| screen | `just screen --dating typed "..."` | kills a proposal that duplicates a closed family, and says whether it was closed on **measurement** or on **availability** |
| re-open | `just reprobe` | re-asks every lead closed because something could not be **reached**. A measurement does not improve by waiting; a dead host might be alive |
| recover | `uv run python scripts/engines/recover_dead_hosts.py` | asks the Wayback Machine for the **data files** of hosts the register wrote off as dead, which is a different question from re-probing the host. Proved twice on 2026-08-16: `nw.com/zone/9701.domains.gz` was recorded unrecoverable and is intact, worth 76,324 pairs; `cybermetrics.wlv.ac.uk` does not resolve and its whole `/database/` tree survives including a 166 MB zip. **It reports and never fetches**, because a file can be available, dated, and 100% already held |
| probe | `just probe probes/x.toml` | turns a URL into a priceable journal from a TOML description, **writing no Python**, so a source can be measured before it earns a collector. Refuses to guess a column, reports what it threw away by reason, and **cannot date a year**: it has no ingest spec ([ADR-004](ADRs.md)). Validated by reproducing a 186-line collector's 8,923 records exactly, from seven lines of TOML |
| price | `just price --items x.jsonl` | measures a dated corpus against the live store: net-new pairs and domains after the corroboration split, mean weight, typo bound, and both a linear and a saturating projection |
| price-hosts | `just price-hosts data/raw/<x>_hostgrain/` | the same question at **hostname grain**, the second unit the reviewer accepted on 2026-09-01: runs the ingest's own funnel over `{url, timestamp}` journals (or `--items x.jsonl`), differences against `hostname_year` and his baseline files on a read-only connection, and prints net-new hostname years and EE per year with the parent pairs beside. `--head N --sample-of M` samples; the projection it prints is an upper bound and says so |
| ship it | `just ship` | banks every class a human has newly moved to `master`, then exports, runs the data invariants, packages, verifies the delivery as a reviewer would, re-checks the totals with **his own calculator**, builds the `.docx`, writes the mail draft and closes the gate issue. **Safe to rehearse before any decision arrives**: `bank_approved.py` reports and skips anything still `pending`, so a dry evening still exercises every later step. `just ship --help` prints the chain and runs none of it |
| approve | `uv run python scripts/harness/request_approval.py <spec> --journal <j>` | writes a request into [docs/approved-sources-list.md](approved-sources-list.md) that a human can decide in two minutes. `ark ingest` **refuses** a master-eligible class until it is decided |
| rank | `just triage-rank` | sorts the triage queue in [docs/approved-sources-list.md](approved-sources-list.md) by the `- potential:` score each entry declares, highest first, so the most promising source is signed off first. `--check` exits 1 if it has drifted. An entry with no score is a hard error, because a source that sorts to the bottom for want of a number is the one nobody looks at |
| `uv run python scripts/engines/build_promotion_journals.py --tag T` | re-file mentions the corroboration split now admits, as dated journals. Dry run by default; `--write` emits, and it never ingests |
| merge | `uv run python scripts/round/merge_against_baseline.py` | **D3**: unions this round's additions into the current baseline, deduplicated on the lowercased line as he does it, and reports per-year overlap, accepted increment and equivalent-English growth in **his own column names** so his audit and ours can be diffed. Ends with the reconciliation checks and exits non-zero if one fails, which includes two that compare a freshly measured baseline against `src/ark/baseline.py` and so catch a round measured against a superseded release |
| brief | `uv run python scripts/round/extract_ding_docs.py --package feedback-phase-N` | transcribes the reviewer's `.docx` into [docs/ding/](ding/) with pandoc, adding only a provenance header carrying the source file's sha256. Run it when a new task package arrives. The body is never retyped: a paraphrase of the brief is the one document here that must not exist |
| loop | `just cycle` | one pass of every mechanical check, rebuilding what it can, **ending by naming what needs judgement**. Add `--until <epoch> --every <secs>` to loop instead of running once |
| schedule | `just schedule install` / `just schedule status` / `just schedule remove` | loads two launchd jobs: `com.ark.bank` runs `scripts/harness/scheduled_bank.sh` at :05 every hour (`just bank`, then the `ship-now` label, see the section below), `com.ark.cycle` runs `scripts/harness/scheduled_cycle.sh` at 01:00, 07:00, 13:00 and 19:00 local, appending `just cycle` and the engine status to `data/logs/scheduled_cycle.log`. **It needs Full Disk Access and says so**: this repository sits under `~/Documents`, which macOS TCC protects, and a launchd agent inherits nothing from the terminal that installed it, so without the grant it exits 126 while `launchctl list` looks perfectly normal, and with launchd's bare PATH it exits 127 the same way, which is why the templates set one. The recipe therefore runs the cycle job once as the probe and reports its exit status rather than trusting the load. **The cycle job reports and never acts**: a job that restarted a collector on its own would eventually restart it with settings that had since been retuned, which is why `extend_engines.sh` performs one handover and exits rather than looping |
| geoindex | `scripts/sources/ukwa/ukwa_geoindex_map.py`, then `scripts/sources/ukwa/ukwa_geoindex_pull.sh`, then `scripts/sources/ukwa/ukwa_geoindex_price.py` | the British Library geoindex, 11.2 GB at `bl.iro.bl.uk`, CC Public Domain, ranged GETs. `map` reads the ZIP64 central directory over HTTP without downloading anything; `pull` streams each member's 1996-2001 rows; `price` measures net-new against the store. **Priced at 77,749.1 equivalent-English on 2026-08-21, admitted at 4,493.0 over 4,591 pairs on 2026-08-24** against a store that had grown into it, C-31. The streamer counts timestamp decreases and cancels its own early abort the moment it sees one, because nine of the twelve members are sharded and aborting early on one of those reads 5% of it while looking normal. Different host from the collectors, so it runs beside them |
| usenet | `bash scripts/sources/usenet/fetch_usenet_hierarchies.sh <epoch>` | downloads the unheld English-facing Usenet hierarchies, largest expected yield first. **Needs no approval**: `usenet_announce / dated_directory` and its siblings are already `master`, so this is collection under an existing decision. Touches `archive.org/download/`, a different service from the `web.archive.org` CDX the collectors meter against, so it runs beside them. Measured worth about 104,000 equivalent-English over roughly 52 GB, C-29, which is an upper bound |
| usenet body URLs | `uv run python scripts/sources/usenet/build_usenet_pool.py <pool dir> <out dir> <workers>`, then `uv run ark ingest-usenet-hostnames <out dir>` | the `usenet_body_url_hostnames` lane, `Decision: master` since 2026-09-04 and worth 119,640 equivalent-English over thirteen pools. Reads every archive in a pool rather than a sample, one `{item, year, text}` shard per worker, and takes hosts ONLY from explicit `http`, `https` and `ftp` URLs after the header block. Six workers keeps a laptop responsive and reads about 45 GB an hour. Price with `just price-hosts --items <out dir> ...`, passing every pool in one command, because summing pools double counts by the saturation share |
| mailing-list body URLs | `uv run python scripts/sources/mail_corpora/build_maillist_pool.py data/raw/maillists data/raw/maillists_items 8`, then `uv run ark ingest-maillist-hostnames data/raw/maillists_items/` | the `maillist_body_url_hostnames` lane, admitted 2026-09-04: the pipermail month files already on disk, read at hostname grain |
| Enron body URLs | `uv run python scripts/sources/mail_corpora/build_enron_pool.py data/raw/enron/enron_mail_20150507.tar.gz data/raw/enron_items`, then `uv run ark ingest-enron-hostnames data/raw/enron_items/` | the `enron_body_url_hostnames` lane, admitted 2026-09-04: the CMU release of the Enron mailbox (443 MB, one request at `Crawl-delay: 10`), streamed without extraction and read at hostname grain; the third member of the body-URL family |
| what a run has added | `just added [--by-source]` | the store query a long collection run wants every half hour: what the lanes have added since `round_since`, priced, through the export's own predicates so a row counted is a row that would ship. Seconds, and read-only, against the 20 minutes `just state` needs. Records are hostname-YEARS, which is the unit he counts |
| hostname lane | `just hostnames <epoch>` | **the standing priority in one command, and leave it running.** Ranks platforms by the hosts we LACK rather than the hosts that exist, starts two sweeps (the maximum) and the fold loop, and needs no hand between starting and reading the figures. Measured 2026-09-04: 22.5M capture rows in three and a half hours, 886,216 net-new shippable records, 552,782 equivalent-English, 48% of the 5% gate. At about 750 times the yield of a gap query an idle hour costs more here than anywhere else, so give it a deadline days out and restart it whenever a session ends |
| hostname lane | **the standing priority in one command** (Ivo, 2026-09-04): ranks platforms by the hosts we LACK rather than the hosts that exist, starts two sweeps (the maximum) and the fold loop, and needs no hand between starting and reading the figures. Measured on 2026-09-04: over 10 million capture rows in 40 minutes, `demon.co.uk` 4,423,683 and `homestead.com` 3,224,657, all under registrables already held |
| gap hostnames | `uv run python scripts/engines/cdx_gap_hostgrain.py`, then `uv run ark ingest-hostnames data/raw/cdx_gap_hostgrain` | the gap engine's own answers one level down, and `maintain.sh` now runs both every pass so it needs no hand. Free: the archive already named the host in a response we had already paid for. Journals written before 2026-09-04 yield NOTHING, because the query asked `fl=timestamp` and kept `{domain, years}`: 2,984,321 answers across 1,163 journals record no host, which is the measured cost of journalling a conclusion instead of a response |
| re-split | `bash scripts/engines/compound_splits.sh <epoch>` | **the largest single lever measured in round 7, and it reads nothing new.** The corroboration split promotes a mention to a dated record only when some other source already places that domain in a year, and that test is re-evaluated every time the split runs, so the same journals are worth more as the store grows. On 2026-08-27 re-splitting the address journals paid 30,645.6 equivalent-English against roughly 700 pairs from the 60 new archives that triggered it, and the bare journals paid 11,447.7 against 128.17 for their 400 new archives: ratios of about 40:1 and 90:1 in favour of re-splitting over reading. Loops the promotion tranche and both corpora to a deadline, and skips a pass rather than queueing when the store's single writer is busy |
| usenet seams | `bash scripts/sources/usenet/work_usenet_addresses.sh <epoch> [batch] [workers] [addresses\|headers]`, `bash scripts/sources/usenet/work_usenet_bare.sh <epoch>` | the three extractors that read what `usenet_announce` does not: `ftp://` and `mailto:` and typed body addresses, the message headers, and the bare `foo.com` written in prose. **All three read `data/raw/usenet`, which was reclaimed once processed and now holds zero archives, so all three had silently become no-ops** over the 16,797 archives that are on disk in `usenet_bulk` and `usenet_new`. Pass a deadline; they batch, stage each batch as symlinks so no bytes move, and bank every eighth batch because the split is O(all journals) while the extraction is O(this batch). Worth 38,639 and 13,955 equivalent-English respectively in round 7 |
| pool queue | `uv run python scripts/engines/build_multisrc_queue.py` | ranks the candidate pool by **how many independent sources name each string**, which is a filter the modelled hit rate cannot express. It exists because the modelled ranking put fabricated names first: on 2026-08-27 a rebuild took the local engine from 1.15-1.66 years per query to 0.014, with 18,184 of the queue's first 20,000 lines `.ca` strings like `afakeaddress.ca`. 86.32% of the pool is named by exactly one source; the multi-source slice is 325,127 names worth 209,036 equivalent-English. **Unmeasured against the gap population and not switched into a running engine**, because a gap target is a name already held and so cannot be fabricated |
| hunt | `Workflow` with `hunt-new-sources` | the standing work of every wake that finds the engines healthy: five independent lenses propose named sources, a sceptic per lens collides each against the closed register and probes whether the data is actually retrievable in 2026, and the survivors are written into the triage queue. **Never stop looking** is a rule in `CLAUDE.md`, not a preference |

**The boundary, stated plainly.** A cycle can notice that a collector died, **that a collector is alive
and finding nothing**, that a journal is sitting unbanked on a remote disk, that a file on disk was never
read, that a target list is older than the rows it should carry, that a hypothesis has been half-priced
for a day, and that the state document is stale. Since
`just probe` it can also **measure** a source that fits one of three described shapes, without anyone
writing code. It cannot invent a hypothesis worth testing, write the collector for a document that needs
refusals of its own, or decide whether a yield justifies one. So it does all of the first and hands over
the second, and the line has moved by exactly one step: **from "cannot try a source" to "cannot promote
one"**, which is the step that was worth moving.

**The one thing the harness may never decide for itself.** A source class may not date a year until a
human has classified it in [docs/approved-sources-list.md](approved-sources-list.md), and `ark ingest` enforces
that before it opens the database. The agent can collect, measure and argue; it cannot promote. The
journal simply waits on disk, so nothing is lost and collection never blocks: candidate-only evidence
passes freely, because a candidate claims nothing. **An unapproved source is not quarantined inside the
store, it was never written to it**, which is stronger than any flag.

**Why this is safe to run unattended**, which is the part that makes it more than a scheduler:
`domain_year.evidence_id` is `NOT NULL` and foreign-keyed, `assign_year` refuses candidate-only
evidence, the corroboration split gates anything a human typed, and seventeen invariants run on every pass.
**An unattended agent physically cannot write an unevidenced year here.** It has latitude about what
to try and none at all about what counts as proof.

### Banking an approval that was merged somewhere else

An approval arrives as a pull request against `live` adding the `Decision:` line, so it can be merged
from a phone. What makes the merge bank something is three machine-readable lines in the request block,
which `request_approval.py` writes and `bank_approved.py` parses:

```
- ingest spec: `some_spec`
- journal: `data/raw/some/some.jsonl.gz`
- refetch: https://host/path (then `uv run ark ingest some_spec data/raw/some/some.jsonl.gz`)
```

The journal is the file the approved figures were measured from. The refetch URL is the way back to
those bytes, needed whenever they were priced on another machine or deleted after their rows landed:
`bank_approved.py --write` downloads it to the journal path, refuses a response that is a page rather
than the artifact, and reports a throttle with its `Retry-After` instead of sleeping through it. A block
that is approved and cannot bank prints under an `APPROVED AND NOT BANKED` banner naming what it lacked;
`--strict` turns that into a non-zero exit for a rehearsal.

The bank's own hygiene is three commands, and the `bank` recipe runs them in this order, with
`bank_approved.py --write` straight after the pull so a merged approval banks on the next bank:

```bash
uv run python scripts/harness/bank_hygiene.py preflight     # first: refuse dirty, fast-forward
uv run python scripts/harness/bank_hygiene.py prune --write # once the run dirs are drained
uv run python scripts/harness/bank_hygiene.py gate --write  # last, off the brief just refreshed
```

`preflight` refuses `main`, refuses uncommitted tracked edits and untracked files under the paths the
recipe stages wholesale (`git add docs/` is how a 1.3 GB copy once reached history), and then pulls
`--ff-only`. It never merges or force-pushes: a diverged clone is reported and reconciled by hand with
`git pull --rebase origin live`. `gate` opens the gate issue once per crossing, latched by both
`data/logs/gate_notified.tsv` and the open-issue query; a brief measured against a superseded release
opens nothing and is reported as stale.

### Banking without a session open, and asking for a package from a phone

`just schedule install` loads two launchd jobs: `com.ark.bank` runs `scripts/harness/scheduled_bank.sh`
at five past every hour, `com.ark.cycle` runs the health check four times a day. The bank wrapper holds a
lock, appends to `data/logs/scheduled_bank.log`, runs `just bank`, and then reads one label: `ship-now` on
any open ark-fleet issue (the gate issue is the natural place) makes it run `just ship all` once, which
banks, regenerates the report, packages, verifies and writes the mail draft, and stops there. Nothing is
sent (C-63). The label is removed before the ship starts, so a failure does not retry every hour, and the
outcome lands as a comment on the issue that carried it. `just schedule status` shows both jobs' last
exit and the last two runs of each log; the exits to know are 126 (no Full Disk Access) and 127 (a tool
missing from the PATH the template sets).

### Screening a source before it costs a request

```bash
just screen --dating typed "1997 conference proceedings with author affiliations"
just screen --list-closed          # the whole closed register, with line numbers
```

Two gates, cheapest first. **Does it collide with a family already closed?** Each closed family
carries the measurement that killed it, and the register is parsed out of
[docs/sources.md](sources.md) and [docs/sources-closed.md](sources-closed.md) at run time rather
than copied, so no count here can drift from it:
`just screen --list-closed` prints the register and its size. A collision prints the verdict, so you argue with the measurement instead of rediscovering
it. **And what dates one item?** `self` needs no corroboration split and must not have its extraction
widened; `typed` takes the split, which is what makes wide extraction safe; `undated` is seed-only.
It **exits 2 if no dating claim is made**, because that answer decides what the source can ever be.

It prices nothing, on purpose: pricing is a sample measured against the live store with a parser per
source, and [docs/discovery.md](discovery.md) is the method. What this removes is the step
before pricing, which is the one that wastes days.

### Part 1: get the inputs (tier 3 only)

**Two baselines, and they are not the same thing.** `legacy-data/` holds the *original* six annual
files supplied with the task, which the normalization audit is computed against. The release additions
are *scored* against is the reviewer's latest merge, and it lives in a `feedback-*/` folder named for
it. Loading a round against a stale release is a silent error that reports already-credited work as
net-new, so the current one is named in `src/ark/baseline.py` and every command follows it.

```bash
wc -l legacy-data/199[6-9].txt legacy-data/200[01].txt   # expect 8224963 total
```

**The bulk sources** go in `data/raw/<source>/`, one folder per source.
**[docs/sources.md](sources.md) has the download command for each**, since the routes differ:
several survive only as web-archive captures, and one address answers HTTP 200 with a stub.

```bash
cd data/raw && shasum -a 256 -c checksums.sha256   # expect 234 OK, plus one known miss
```

The manifest pins 235 files and one of them, `arquivo/IA.cdxj`, was **deliberately deleted** at 47 GB
once its evidence was in the store. So the expected result is 234 OK lines and one missing-file error
for that path. `just reproduce sources` skips it for the same reason and says so.

**The network journals ship with the delivery**, under `journals/`. They hold the raw responses of
every query ever made, so Part 2 replays every network stage offline.

### Part 2: rebuild the result

Six stages, all offline, one recipe. `just reproduce` runs them in order and `just reproduce <stage>`
runs one; the stage bodies are the authoritative list of what gets ingested.

| Stage | Recipe | What it does, and what to look for |
|---|---|---|
| 1 | `just reproduce baseline` | `ark init`, then loads the current release, writes the exclusion droplist, writes the normalization audit. Expect **6 files ingested, 0 skipped**. `6 skipped` means the marker namespace already exists, which is the silent no-op described below |
| 2 | `just reproduce sources` | The bulk ingests: Early Web CDX, ISC surveys, Arquivo, AFNIC, Internet Scout, ODP, the UKWA link graph both ways, NCSA What's New |
| 3 | `just reproduce candidates` | Grows the candidate pool from the year-unlabelled host lists |
| 4 | `just reproduce journals` | Replays every stored network response: CDX, RDAP, page expansion, Usenet and its three re-read seams, UUCP, rtfm, Enron, mailing lists, trade press |
| 5 | `just reproduce seeds` | Rebuilds the auxiliary hostname and URL pool, the granularity the registered-domain unit drops |
| 6 | `just reproduce deliver` | `ark export`, then `ark stats`, then `ark check`. **Export must precede check**, see below |

Stages 2 and 3 are order-independent. Stage 4 must follow them, because a replayed query is evidence
about a domain the bulk sources introduced, and the corroboration split in stage 4 is judged against
what the store holds by then.

```bash
wc -l output/netnew/*.txt   # equals the net-new pair count from `ark stats`
```

**`ark check` must run after `ark export`, not before.** One invariant,
`additions_not_double_counted`, reads the exported annual files and asserts that no domain in them
carries baseline evidence for that year. Run it against a store whose baseline has moved since the
last export and it correctly reports every already-credited pair as a violation.
`just reproduce deliver` has the order right.

### Loading a new reviewer release

He reissues the merged corpus after each round he accepts. Point `src/ark/baseline.py` at it **first**,
then load:

```bash
cp data/ark.duckdb data/ark.duckdb.pre-<release>.bak   # there is no unload command
# edit src/ark/baseline.py: CURRENT_BASELINE_DIR, CURRENT_BASELINE_MARKER,
# CURRENT_ROUND_SINCE, REVIEWER_BASELINE_PAIRS, REVIEWER_BASELINE_EE, ..._BY_YEAR
uv run ark ingest-legacy    # expect: 6 files ingested, 0 skipped
just reproduce deliver      # export, stats, check, in that order
uv run python scripts/round/round_figures.py --verify
```

Two traps, both of which fail quietly:

- **Loading with only `--legacy-dir` is a total no-op.** `--marker-prefix` defaults to the marker in
  `baseline.py`, so the composed marker already exists in the ledger and all six files are skipped
  behind six reassuring "already ingested" lines. Edit the constants first, or pass both flags.
- **`ark stats` prints the release it measured against.** If that is not the newest one he has sent,
  every figure above it is overstated. That check is the whole reason the constant is centralised.

`round_figures.py --verify` re-scores the increment with **his own** `equivalent_english_domains.py`
and refuses the numbers if his total differs from ours or if his validator rejects a record we counted.
Its overlap guard reading zero is also the proof that the new release actually loaded.

### Package the delivery archive

**Use `just ship` rather than packaging by hand.** The packaging stage refuses unless `output/` matches
the store **exactly**, and the store moves every time the ingest loop banks a journal, which is every few
minutes. So a hand-run `ark export` followed by `just ship package` races the loop and refuses, and the
evening a round ships is the wrong time to find that out. Measured on 2026-08-13: export wrote 170,186
pairs and packaging read 170,787 from the store minutes later.

```bash
just ship --help     # the whole chain, printed, nothing run
just ship            # bank the approved, export, gate, package, verify, draft the mail
```

`just ship` ends by writing the mail draft under `private/emails/drafts/`, carrying the figures
`fill_report.py` filled, the cumulative record from [rounds.md](rounds.md) and one line per open row of
[questions.md](questions.md) that is due for a reminder, and it closes the gate issue on a verified
delivery. `just ship draft` prints that mail and writes nothing.

Only the **ingest** loop pauses. Collectors writing journals do not move the store, so they keep running
and their work banks afterwards; journals are ledgered by content hash, so re-offering an ingested one is
skipped in milliseconds. The recipe restarts the loop on exit if it was running when ship began.

```bash
uv run ark export                       # refresh output/ from the store first
uv run python scripts/round/fill_report.py    # substitutes every figure into docs/report.md
just ship package                       # tar.gz plus its SHA256, into submissions/<round>/
just verify delivery                    # run the archive's own checks from outside
```

Packaging refuses to build from a modified working tree, from an `output/` older than the store, from
a `docs/report.md` that disagrees with what `fill_report.py` would emit, or when the baseline release
the figures are measured against is not on disk to ship alongside them. Each of those guards exists
because the failure it catches has happened.

The archive lands in `submissions/<round>/`, defaulting the round to the current git branch. Pass one
explicitly with `just ship package phase-5`. The tarball is git-ignored; the report, the source
documentation, the checksum and `MANIFEST.txt` stay in git, which is enough to say later exactly what
was claimed and to prove a rebuilt archive matches. **Add a row to `submissions/README.md` after each
send.**

## Collecting more evidence (needs the network)

Collectors write journals and never touch the store, so they run for hours alongside everything else.
That one property is why collection can be split across machines, why a parsing bug costs no requests,
and why every network stage replays offline.

### One queue, three populations

Three populations can be queried, and they are worth different things. A **gap target** is a domain that
already holds a year and is missing one it is bracketed by; a hit adds a pair. A **pool target** is a
domain held with no year at all; a hit makes the name net-new. An **edge target** is a domain missing
1996 or 2001 with the adjacent in-window year held. Keeping them in separate lists forced a choice about
which to work, and that choice was once made by hand and made wrong.

All three are scored on the one scale that decides the allocation, **expected net-new equivalent-English
per query**, and merged into a single queue.

**The edge population existed for a month before any queue could express it**, which is why it is worth
naming here rather than only in an ADR. A bracketed gap needs a year held at Y-1 *and* Y+1, so 1996
would need 1995 and 2001 would need 2002: both outside the window. A domain held in 2000 and missing
2001 was therefore not a gap target, and not a pool target either because it already carries a year.
Measured on 2026-08-18: **5,358,097 such slots, 99.8% never asked**, at a measured 94.4% conditional
rate for 2001 and 60.0% for 1996, against a bracketed control of 98.2% on the same method. The best
10,000 rows run at **1.52 expected equivalent-English per query** against 1.249 for the bracketed queue.
The rate is a ceiling and a pilot is what settles it. See ADR-006; nothing points an engine at it yet,
because that allocation is a `key-decisions.md` question.

```bash
just query-queue --dry-run          # what it would return, writes nothing
just query-queue                    # -> queue_shard0.txt, queue_shard1.txt, queue_manifest.tsv.gz

# one population at a time, for one machine
uv run python scripts/engines/build_query_queue.py --population gap  --out data/raw/cdx/queue_gap_vps.txt
uv run python scripts/engines/build_query_queue.py --population pool --out data/raw/cdx/queue_pool_local.txt
uv run python scripts/engines/build_query_queue.py --population edge --out data/raw/cdx/queue_edge.txt
```

A gap target scores `realisation x English share x bracketed years it could fill`; a pool target
scores `P(hit) x English share x years a hit returns`. Both multipliers are measured at build time and
printed with the queue, so a wrong one is visible rather than silent.

**Rebuild after any large ingest.** New evidence creates bracketed gaps as well as filling them, and a
stale queue cannot reach what it does not list. A larger merged baseline grows the gap pool faster
than the crawl closes it, so a queue written before a release lands is structurally blind to it.

### Running the engines

```bash
just engines start $(date -u -v+12d +%s)   # collector and ingest loop, both detached
just engines                                # what both machines are doing
just engines stop                           # without losing the batch in flight
just maintain                                # fold finished collector output in, on a loop
```

`just engines stop` sends TERM to the supervisor, which runs its trap, asks the batch to stop, and lets it
publish what it already has. A stopped batch still writes its journal, so the only thing lost is the
queries it had not made yet. **Never `kill -9` a collector**: that strands the `.part`, and since the
ingest ledger keys on the finished name, the work inside it becomes unreachable.

Stopping the ingest loop leaves whatever the collectors wrote sitting on disk. That is safe, because
journals are ledgered by content hash and re-offering an ingested one is skipped in milliseconds, but
`ark stats` understates the round until the loop runs again.

`just engines` prints the tier mix, which is how a run's health reads at a glance: `host` is the cheap
per-host query answering on its own, `root` is a domain so heavily archived that the archive gave up
and the apex rescued it, `scan` is the wildcard fallback. Drifting toward `root` means a clogged
stretch of queue that will clear; drifting toward failures means the archive is refusing connections,
and the fix is **fewer** workers, not more.

**More workers do not buy more throughput.** The archive limits concurrent connections per IP, and 8
and 12 workers measure the same, 506 against 510 queries an hour. What raises the ceiling is another
address, which is the real argument for a second machine.

**Widening the window without stopping anything.** Every unattended loop takes an absolute epoch and
exits at it, so extending a run means restarting, and restarting kills the batch in flight. Instead:

```bash
bash scripts/engines/extend_engines.sh $(date -u -v+3d +%s)   # hand each engine over as it expires
```

It waits for each of the three loops to reach its own deadline and exit, then starts exactly one
replacement on the new one, re-checking the process table immediately before launching so a second
invocation cannot produce a second collector. It performs one handover per engine and exits; it is not
a watchdog and must not become one, which is why a crashed collector is still a human's problem.

### Growing the pool from the engine's own hits

Page expansion has existed since round 1, but every round of it was fed by a seed list a human chose,
which makes it a source, and sources run out. Feeding it from the engine's own journals closes the loop:

```bash
uv run python scripts/engines/build_expand_seeds.py --recent 40 --domains 600   # hits -> seed pages
uv run ark download data/raw/expand/loop/seeds.txt -n 400 --workers 2 --captures 1 \
    --out data/raw/expand/loop/expand_$(date -u +%Y%m%dT%H%M%SZ).jsonl.gz
uv run ark ingest expansion_links data/raw/expand/loop/expand_*.jsonl.gz --round 6
```

A domain the engine dates was, by construction, live in the window, and the sites its page links to are
overwhelmingly period sites. Extracted names are `link_target`, candidate-only by construction, so this
route can never date a year by itself and needs no approval.

**It is worth running for quality, not quantity.** The pool already holds 2.5M names nobody has queried
against an engine that clears about 600 an hour, so more candidates buy nothing on their own. What this
route buys is *better* candidates: hit rate by where a name came from, over 27,955 answered queries, is
**90.4%** for names harvested from a link graph against 46.0% for the pool as a whole and 38.9% for
Usenet mentions.

**Seed the page, not the site.** The first pilot seeded each domain's home page and returned 0.1 net-new
names per page, because 11 of 27 captured home pages of the period carried no outbound link at all. The
builder therefore spends one CDX query per domain asking which pages the archive holds and seeds the
ones whose path looks like a list of links. That query replaces the two the first version wasted per
domain: IA folds `http://www.x.com/` and `http://x.com/` onto the same key, so seeding both fetched the
same page twice for the same harvest. `--roots-only` reproduces the old behaviour for comparison.

### The registries, retired

`ark rdap` queried the authoritative RDAP server for each TLD and is gone; see
[retired.md](retired.md). It was fast (75 queries a second against 0.83 through the redirector)
and it is closed anyway: the registries' terms forbid the bulk access, and Verisign answers a
quota rather than a rate. The journals it wrote are still ingested, by the `ark ingest
rdap_snapshot` lines in the justfile, and `attested_years` still reads them.

Probe a registry before spending a night on it: 150 queries is enough. Each of the ones tried failed
differently and each failure is recorded in `docs/sources.md`, including one that blocks with 403
rather than throttling and one whose namespace was re-registered in 2002 so its creation dates date
nothing.

**Read the plausibility warning the list builder prints.** It reports, per TLD, how many pool names
there are for every name already holding a year. A real namespace measures about 0.3; `.gov` measures
**182** and `.mil` **2,624**, and their pool names are invented strings and prose words rather than
domains. Because the list is ranked by `P(hit) x English share`, a fabricated namespace with a high
share ranks near the top: `.gov` came fourth by volume at a 0.9825 share. **A high English share times
an invented name is still zero.** The builder warns rather than excluding, since which TLDs to drop is a
judgement; act on it with `--tlds`.

### A second machine

Split the queue into disjoint shares and run one per machine. Assignment is by content hash of the
domain, so the shares are disjoint and jointly complete with no coordination, and because the hash is
independent of the ordering each share is a representative sample of the whole value curve rather
than a contiguous block of it.

**Size each share by how fast its machine is.** Measured, the MacBook sustains 916 queries an hour
against the VPS's 262, and an even split leaves the fast machine grinding its own cheap tail while the
expensive head of the other half goes untouched.

```bash
just query-queue --weights 78,22 --rates 916,262   # shares, measured speeds
bash scripts/engines/make_vps_bundle.sh              # ship share 1 and the repo
bash scripts/engines/vps_bootstrap.sh                # then, on that machine
```

The remote machine needs the repo, `uv`, and its slice. It does **not** need the store: collection
never opens it. Give each machine its own `ARK_PREFIX` so two runs cannot write the same journal name,
and keep the prefix starting `cdx_` so the ingest globs and the resume scan still see it.

**Bringing the remote journals home is the step that gets forgotten**, and a second machine's output
is invisible to every measurement taken on the first. The VPS once ran for a day and a half with 5,793
year-records on its disk and absent from the store, because nothing here ever looked. `just engines`
lists any remote journal missing locally and prints the `rsync` that fetches it, and it now reports
**UNKNOWN** rather than "everything is home" when it could not reach the machine to ask.

### The namespace sweep, which feeds the hostname unit

`matchType=domain` on one parent returns every capture under it, so one request walks
thousands of hosts. `scripts/engines/platform_sweep.sh <deadline> <queue>` walks a queue
of parents through `cdx_suffix_sweep.py`, one at a time, writing raw `{url, timestamp}`
journals to `data/raw/cdx_suffix/`; `ark ingest-hostnames` turns them into hostname
records and `cdx_suffix_convert.py` into the registrable half. It holds the second
archive slot, so the vedge engine stays stopped while it runs; `touch
/tmp/ark-pause-sweeps` idles it between pages.

Three facts decide how it is run, all measured on `co.uk` on 2026-09-02:

- **A page is a count of index blocks and costs about the same at any size**: 200 blocks
  took 11 to 42 s, 10,000 took 110 s. The default is 10,000, which walks `co.uk`
  (3,387,186 blocks) in 339 requests instead of 16,936.
- **The page count is asked up front** (`showNumPages`, without `fl`, which turns the
  count into dashes), so a walk ends where the index ends and writes `suffix_<parent>.done`.
  The state file records the page size; a resume at another size converts its position.
- **A failed page is retried, not skipped.** The August sweep advanced past any non-200
  page, and one archive outage refused thirteen parents on their control probe in three
  minutes. Both are now retried; a parent that still fails lands in
  `data/raw/cdx/platform_retry.txt` for the next walk.

Queues: `platform_queue_*.txt` are parents from `rank_platform_parents.py`,
`suffix_queue_s1/s2.txt` are the English-heavy second-level suffixes (`co.uk`, `com.au`,
`co.nz`, `org.uk`, `gov.uk`, `co.za`, `gc.ca`, the `.us` states) that the bare TLDs, which
answer 403, cannot give. `sweep_chain.sh <pid> <queue>...` runs queues back to back behind
a running sweep so a slot never idles. `just bank` brings finished journals home and skips
any a sweep still holds open.

### The per-source collectors

Each is a collect-then-split pair: the collector writes a journal and touches no database, the split
sorts it into a dated half and a candidate half, and only then does anything reach the store. Yields
and residual headroom for every one are in [docs/sources.md](sources.md).

One recipe, the source as its argument. `just collect` with no source lists them.

```bash
just collect usenet-ingest        # split and ingest whatever has finished downloading
just collect usenet-bare          # bare `foo.com` in the message bodies, no request sent
just collect usenet-addresses     # ftp://, mailto: and typed addresses the parser never read
just collect usenet-whois         # whois records pasted into the bodies
just collect usenet-measure <archives>   # yield against the store, before ingesting
just collect uucp-maps            # a .CA registry dump that travelled over Usenet
just collect rtfm-faqs <tag>      # the Usenet FAQ mirror, dated by revision header
just collect trade-press          # scanned computer magazines, dated by issue
just collect trade-press-reextract
just collect trade-press-american <journal>
just collect attrition            # the defacement mirror index, no request sent
just collect enron                # the FERC corpus, dated per message
just collect maillists            # public pipermail archives, dated per message
just collect tucows               # software release dates plus the vendor's home page
just collect pandora-seed         # the PANDORA title index into the candidate pool
just expand round <seeds> <n>     # archived page expansion, the outbound-link route
just expand loop                  # the closed loop: engine hits become the next seeds
```

Three rules that came out of these, all of them expensive to learn:

- **Before writing a source off, check what the parser actually reads.**
  `comp.mail.maps.mbox.zip` sat marked processed for a day with 1,480,910 registry entries read as
  nothing, because a URL regex cannot see a payload in a record format.
- **Quote the post-split number, never the raw one.** A raw recovered set of 2,440,926 pairs admitted
  107,304. Quoting the former would have overstated the source 24-fold.
- **Re-run a re-extraction after every collection, not once.** A fixed extractor landed while a
  collector was already running with the old pattern in memory, and the second re-read was worth more
  than the collection itself. Pass a fresh `--tag` each time: the ledger keys on content hash and
  refuses a changed file under an ingested name.

### Reporting a round

The reviewer set the format: five fields, where lines 1 and 2 are his merged database **before** our
increment and line 5 is line 4 divided by line 2.

```bash
uv run python scripts/round/round_figures.py            # the five fields, plus per-year and per-source
uv run python scripts/round/round_figures.py --verify   # re-score with HIS calculator; non-zero exit on disagreement
uv run python scripts/engines/cdx_execution_notes.py      # per-collector throughput and failure split
```



`cdx_execution_notes.py` reads the journal directory rather than a list of prefixes, so a collector
started under a name nobody wrote down is still measured. It reports queries, answered, success rate,
in-window hit rate and the failure split per collector.

**Always send with `--verify`.** A record his validator rejects scores zero for him and full weight
for us, which is a live risk every time a source widens its matching. The figures are only correct
once `src/ark/baseline.py` names the release he has actually merged.

**The email and the report are different documents** (Ivo, 2026-08-12). The email is the five fields and
nothing else, short enough to read on a phone; the method goes in an attached report, and he wants that
attachment as `.docx`:

```bash
just ship docx docs/report.md
```

The drafts under `private/` carry a status block at the top and a `## Notes for Ivo` section at the
bottom, holding what is deliberately not being said: what could not be verified, which paragraph is
optional, what he may query. **The converter strips both**, because trimming them by eye is the operation
that eventually sends one. Pass `--keep-markdown` to read exactly what will go out.

`ark stats` also prints **the two outcomes separately**, which he asked for: `discovery` is domains the
baseline holds in no year, scored once per domain for breadth and again over the pairs they carry, and
`completeness` is years filled on domains he already has. The two partition the net-new total exactly,
so they can be quoted side by side without double counting. Reading breadth off the pair count instead
once reported 1,161,961 domains against a true 463,566.

## Structure

The repo holds code and docs only; all data stays out of git. `output/` is generated and regenerable
via `ark export`, and ships in the delivery archive.

```
output/                        git-ignored, regenerable; shipped in the archive
├── netnew/                    the additions: one file per year, plus evidence_manifest.csv
├── candidate_unverified.txt   domains awaiting per-year evidence
├── provenance/                the evidence graph as Parquet + LOAD.sql
├── seeds/                     the auxiliary hostname and URL pool
└── legacy_review/             every excluded baseline line, grouped by reason

data/          git-ignored: DuckDB store, work queue, downloaded sources, audit CSVs, logs
legacy-data/   git-ignored: the original supplied baseline, dropped in
feedback-*/    git-ignored: what the reviewer sent back, including the current merged release
src/ark/       the pipeline package and the `ark` CLI
scripts/       collectors, splitters, supervisors, packaging, measurement
tests/         pytest, network mocked
docs/          the brief and its amendments, sources, discovery method, design notes, decision log
submissions/   one folder per round: the report as sent, its checksum and manifest
```

Two files under `docs/` are **generated, not written**. `docs/ROUND.md` comes from `just state`, and `docs/report.md` comes from
`docs/report.template.md` via `scripts/round/fill_report.py`, which fills every figure from the store and
refuses to write if a placeholder is left unfilled. Editing the generated copy loses the edit at the
next refresh, and packaging refuses outright if the two disagree.
