# Internet Digital Ark

A reproducible pipeline collecting historical **domain names for 1996-2001**, each backed by
**item-level, per-year evidence**. It grows a baseline the reviewer supplies and ships its additions
as a separate, verifiable set; the baseline is never modified.

Additions are scored on **equivalent-English domains**: each `(domain, year)` record counts not 1 but
the English page-language share of its right-most TLD, so `foo.uk` is worth 0.9813 of a record and
`foo.de` 0.1324. The current release being measured against, and its totals, live in one place:
[`src/ark/baseline.py`](src/ark/baseline.py).

**This file is the operating guide: what to run, and what each command should print.**

| Document | |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | the reviewer's original brief, verbatim and never edited. Cited by clause number from the code |
| [docs/brief_amendments.md](docs/brief_amendments.md) | what he has changed since: the metric, the retired standard, the current priorities |
| [docs/sources.md](docs/sources.md) | every source: what it is, what dates it, how to fetch it, **what remains unexhausted in it**, and every family rejected with the measurement that killed it |
| [docs/discovery.md](docs/discovery.md) | how to price a candidate source before building a collector |
| [docs/documentation.md](docs/documentation.md) | why the pipeline is shaped the way it is |
| [docs/delivery_readme.md](docs/delivery_readme.md) | the README that ships at the root of the delivery archive |
| [docs/report.md](docs/report.md) | the round report. **Generated** from `docs/report.template.md`; edit the template, never the output |
| [docs/notes.md](docs/notes.md) | the dated decision log |
| [docs/phase5-plan.md](docs/phase5-plan.md) | this round's plan, in plain terms |
| [CLAUDE.md](CLAUDE.md) | the standing brief an agent is loaded with: the evidence rules, the house rules, the traps. **Only what never changes** |
| [docs/ROUND.md](docs/ROUND.md) | **generated**: where the round stands right now. `just state` writes it, `just state --check` says whether it is stale |
| [docs/key-decisions.md](docs/key-decisions.md) | the short list of open and closed decisions, for review at a glance |
| [docs/ADRs.md](docs/ADRs.md) | architecture decision records: the few structural decisions, with what was measured and what was rejected |
| [submissions/](submissions/) | what was sent, round by round |
| [legacy/](legacy/) | retired engines and spent probes, kept for their negative results |

## Requirements

[`uv`](https://docs.astral.sh/uv/) only. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`,
then `uv sync`. Everything below runs under `uv run`. The optional
[`just`](https://github.com/casey/just) wraps the same commands, and `just --list` is the index.

## Three ways to check this work

| Tier | What it proves | Cost | How |
|---|---|---|---|
| **1. Verify the shipped result** | Nothing has changed and every pair traces to a recorded observation | ~10 s | `bash verify.sh` at the delivery archive's root |
| **2. Rebuild from the evidence** | The shipped lists follow from the shipped evidence, byte for byte | ~1 min | `uv run ark rebuild ../provenance` |
| **3. Rebuild from the original sources** | The evidence follows from the source data | a large download, then ~20 min | Parts 1 and 2 below |

Tiers 1 and 2 need no network and no source data. Tier 1 needs nothing from this repository at all.

**Tier-3 cost figures date from the phase-1 archive and have not been re-measured since.** Measured
then, a full run took about 20 minutes and returned 99.77% of the pairs with all invariants passing;
the gap was two sources with no journal to replay.

## Reproduce the results

Every step is re-runnable: work already done is skipped, so an interrupted run finishes by running the
same command again. Each run appends to a log in `data/logs/`.

```bash
just setup       # uv sync
just reproduce   # all six stages below, offline
just check       # lint + format-check + tests, then the nine data invariants
```

`just check-data` runs the data invariants and `just verify-repo` runs the code checks; `just check`
runs both. They fail differently, which is why neither gets the bare name.

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
| `unread` | a documented ingest glob matches a file the ledger has never read. **The cheapest yield in the project**: price it against the live store before ingesting, per [docs/discovery.md](docs/discovery.md) |
| `glob_too_narrow` | the ledger holds a file the documented glob cannot reach. Loses nothing now, but `just reproduce` rebuilds a store without it |
| `unreferenced` | a directory under `data/raw/` that no ingest glob points into at all |
| `usenet` | the corpus against its own `.processed` ledger and the catalogue: unread, size mismatches, partial files |
| `stale_derived` | a target list or queue built before the current baseline landed, so it is blind to what that release added |

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
| memory | `just state` | regenerates [docs/ROUND.md](docs/ROUND.md), the current state, from the programs that own each figure |
| memory | `just hypo list` | the ledger: what has been proposed, priced, adopted or killed, with status |
| screen | `just screen --dating typed "..."` | kills a proposal that duplicates one of ~60 closed families, and says whether it was closed on **measurement** or on **availability** |
| re-open | `just reprobe` | re-asks every lead closed because something could not be **reached**. A measurement does not improve by waiting; a dead host might be alive |
| price | `just price --items x.jsonl` | measures a dated corpus against the live store: net-new pairs and domains after the corroboration split, mean weight, typo bound, and both a linear and a saturating projection |
| loop | `uv run python scripts/discover_cycle.py --until <epoch>` | runs the mechanical checks on a schedule and **ends each cycle by naming what needs judgement** |

**The boundary, stated plainly.** A cycle can notice that a collector died, that a journal is sitting
unbanked on a remote disk, that a file on disk was never read, that a target list predates the current
baseline, that a hypothesis has been half-priced for a day, and that the state document is stale. It
cannot invent a hypothesis worth testing, write the fetcher that turns a source into dated items, or
decide whether a yield justifies a collector. So it does all of the first and hands over the second.

**Why this is safe to run unattended**, which is the part that makes it more than a scheduler:
`domain_year.evidence_id` is `NOT NULL` and foreign-keyed, `assign_year` refuses candidate-only
evidence, the corroboration split gates anything a human typed, and nine invariants run on every pass.
**An unattended agent physically cannot write an unevidenced year here.** It has latitude about what
to try and none at all about what counts as proof.

### Screening a source before it costs a request

```bash
just screen --dating typed "1997 conference proceedings with author affiliations"
just screen --list-closed          # the whole closed register, with line numbers
```

Two gates, cheapest first. **Does it collide with a family already closed?** Roughly fifty are, each
with the measurement that killed it, and the register is parsed out of
[docs/sources.md](docs/sources.md) at run time rather than copied, so it cannot drift from the
verdicts. A collision prints the verdict, so you argue with the measurement instead of rediscovering
it. **And what dates one item?** `self` needs no corroboration split and must not have its extraction
widened; `typed` takes the split, which is what makes wide extraction safe; `undated` is seed-only.
It **exits 2 if no dating claim is made**, because that answer decides what the source can ever be.

It prices nothing, on purpose: pricing is a sample measured against the live store with a parser per
source, and [docs/discovery.md](docs/discovery.md) is the method. What this removes is the step
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
**[docs/sources.md](docs/sources.md) has the download command for each**, since the routes differ:
several survive only as web-archive captures, and one address answers HTTP 200 with a stub.

```bash
cd data/raw && shasum -a 256 -c checksums.sha256   # expect 234 OK, plus one known miss
```

The manifest pins 235 files and one of them, `arquivo/IA.cdxj`, was **deliberately deleted** at 47 GB
once its evidence was in the store. So the expected result is 234 OK lines and one missing-file error
for that path. `just sources` skips it for the same reason and says so.

**The network journals ship with the delivery**, under `journals/`. They hold the raw responses of
every query ever made, so Part 2 replays every network stage offline.

### Part 2: rebuild the result

Six stages, all offline. `just reproduce` runs them in order; the recipes are the authoritative list
of what gets ingested, and `just --list` names them.

| Stage | Recipe | What it does, and what to look for |
|---|---|---|
| 1 | `just baseline` | `ark init`, then loads the current release, writes the exclusion droplist, writes the normalization audit. Expect **6 files ingested, 0 skipped**. `6 skipped` means the marker namespace already exists, which is the silent no-op described below |
| 2 | `just sources` | The bulk ingests: Early Web CDX, ISC surveys, Arquivo, AFNIC, Internet Scout, ODP, the UKWA link graph both ways, NCSA What's New |
| 3 | `just candidates` | Grows the candidate pool from the year-unlabelled host lists |
| 4 | `just journals` | Replays every stored network response: CDX, RDAP, page expansion, Usenet and its three re-read seams, UUCP, rtfm, Enron, mailing lists, trade press |
| 5 | `just seeds` | Rebuilds the auxiliary hostname and URL pool, the granularity the registered-domain unit drops |
| 6 | `just deliver` | `ark export`, then `ark stats`, then `ark check`. **Export must precede check**, see below |

Stages 2 and 3 are order-independent. Stage 4 must follow them, because a replayed query is evidence
about a domain the bulk sources introduced, and the corroboration split in stage 4 is judged against
what the store holds by then.

```bash
wc -l output/netnew/*.txt   # equals the net-new pair count from `ark stats`
```

**`ark check` must run after `ark export`, not before.** One invariant,
`additions_not_double_counted`, reads the exported annual files and asserts that no domain in them
carries baseline evidence for that year. Run it against a store whose baseline has moved since the
last export and it correctly reports every already-credited pair as a violation. `just deliver` has
the order right.

### Loading a new reviewer release

He reissues the merged corpus after each round he accepts. Point `src/ark/baseline.py` at it **first**,
then load:

```bash
cp data/ark.duckdb data/ark.duckdb.pre-<release>.bak   # there is no unload command
# edit src/ark/baseline.py: CURRENT_BASELINE_DIR, CURRENT_BASELINE_MARKER,
# CURRENT_ROUND_SINCE, REVIEWER_BASELINE_PAIRS, REVIEWER_BASELINE_EE, ..._BY_YEAR
uv run ark ingest-legacy    # expect: 6 files ingested, 0 skipped
just deliver                # export, stats, check, in that order
uv run python scripts/round_figures.py --verify
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

```bash
uv run ark export                       # refresh output/ from the store first
uv run python scripts/fill_report.py    # substitutes every figure into docs/report.md
just package                            # tar.gz plus its SHA256, into submissions/<round>/
just verify-delivery                    # run the archive's own checks from outside
```

Packaging refuses to build from a modified working tree, from an `output/` older than the store, from
a `docs/report.md` that disagrees with what `fill_report.py` would emit, or when the baseline release
the figures are measured against is not on disk to ship alongside them. Each of those guards exists
because the failure it catches has happened.

The archive lands in `submissions/<round>/`, defaulting the round to the current git branch. Pass one
explicitly with `just package phase-5`. The tarball is git-ignored; the report, the source
documentation, the checksum and `MANIFEST.txt` stay in git, which is enough to say later exactly what
was claimed and to prove a rebuilt archive matches. **Add a row to `submissions/README.md` after each
send.**

## Collecting more evidence (needs the network)

Collectors write journals and never touch the store, so they run for hours alongside everything else.
That one property is why collection can be split across machines, why a parsing bug costs no requests,
and why every network stage replays offline.

### One queue, both populations

Two populations can be queried, and they are worth different things. A **gap target** is a domain that
already holds a year and is missing one it is bracketed by; a hit adds a pair. A **pool target** is a
domain held with no year at all; a hit makes the name net-new. Keeping them in two lists forced a
choice about which to work, and that choice was once made by hand and made wrong.

Both are now scored on the one scale that decides the allocation, **expected net-new
equivalent-English per query**, and merged into a single queue.

```bash
just query-queue-preview            # what it would return, writes nothing
just query-queue                    # -> queue_shard0.txt, queue_shard1.txt, queue_manifest.tsv.gz
```

A gap target scores `realisation x English share x bracketed years it could fill`; a pool target
scores `P(hit) x English share x years a hit returns`. Both multipliers are measured at build time and
printed with the queue, so a wrong one is visible rather than silent.

**Rebuild after any large ingest.** New evidence creates bracketed gaps as well as filling them, and a
stale queue cannot reach what it does not list. A larger merged baseline grows the gap pool faster
than the crawl closes it, so a queue written before a release lands is structurally blind to it.

### Running the engines

```bash
just engines-start $(date -u -v+12d +%s)   # collector and ingest loop, both detached
just engines                                # what both machines are doing
just engines-stop                           # without losing the batch in flight
just maintain                                # fold finished collector output in, on a loop
```

`engines-stop` sends TERM to the supervisor, which runs its trap, asks the batch to stop, and lets it
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

### The registries, which compete with nothing

`ark rdap` goes straight to the authoritative RDAP server for each TLD, resolved from the IANA
bootstrap file, with `rdap.org` kept only as a fallback. Measured: **75 queries a second with no
refusals**, against 0.83 q/s and 18.8% refused through the redirector. It talks to registries rather
than to `web.archive.org`, so it is free capacity while the CDX engines are saturated.

```bash
just rdap-pool com,net          # build the list, sweep it, ingest the journals
just rdap-batch                 # or: creation years for domains adjacent to a held year
```

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
just query-queue 78,22                       # weights, measured speeds
bash scripts/make_vps_bundle.sh              # ship share 1 and the repo
bash scripts/vps_bootstrap.sh                # then, on that machine
```

The remote machine needs the repo, `uv`, and its slice. It does **not** need the store: collection
never opens it. Give each machine its own `ARK_PREFIX` so two runs cannot write the same journal name,
and keep the prefix starting `cdx_` so the ingest globs and the resume scan still see it.

**Bringing the remote journals home is the step that gets forgotten**, and a second machine's output
is invisible to every measurement taken on the first. The VPS once ran for a day and a half with 5,793
year-records on its disk and absent from the store, because nothing here ever looked. `just engines`
lists any remote journal missing locally and prints the `rsync` that fetches it, and it now reports
**UNKNOWN** rather than "everything is home" when it could not reach the machine to ask.

### The per-source collectors

Each is a collect-then-split pair: the collector writes a journal and touches no database, the split
sorts it into a dated half and a candidate half, and only then does anything reach the store. Yields
and residual headroom for every one are in [docs/sources.md](docs/sources.md).

```bash
just usenet-ingest        # split and ingest whatever has finished downloading
just usenet-bare          # bare `foo.com` in the message bodies, no request sent
just usenet-addresses     # ftp://, mailto: and typed addresses the parser never read
just uucp-maps            # a .CA registry dump that travelled over Usenet
just rtfm-faqs <tag>      # the Usenet FAQ mirror, dated by revision header
just trade-press          # scanned computer magazines, dated by issue
just trade-press-reextract
just attrition            # the defacement mirror index, no request sent
just enron                # the FERC corpus, dated per message
just maillists            # public pipermail archives, dated per message
just tucows               # software release dates plus the vendor's home page
just expand-round <seeds> <n>   # archived page expansion, the outbound-link route
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
uv run python scripts/round_figures.py            # the five fields, plus per-year and per-source
uv run python scripts/round_figures.py --verify   # re-score with HIS calculator; non-zero exit on disagreement
```

**Always send with `--verify`.** A record his validator rejects scores zero for him and full weight
for us, which is a live risk every time a source widens its matching. The figures are only correct
once `src/ark/baseline.py` names the release he has actually merged.

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
legacy/        retired engines and spent probes, kept for their negative results; not linted, not shipped
```

Two files under `docs/` are **generated, not written**: `docs/report.md` comes from
`docs/report.template.md` via `scripts/fill_report.py`, which fills every figure from the store and
refuses to write if a placeholder is left unfilled. Editing the generated copy loses the edit at the
next refresh, and packaging refuses outright if the two disagree.
