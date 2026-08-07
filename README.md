# Internet Digital Ark

A reproducible pipeline collecting historical **domain names for 1996-2001**, each backed by
**item-level, per-year evidence**. It grows a provided baseline and ships its additions as a separate,
verifiable set; the baseline is never modified. From this round, additions are split into
**English-verified** and **non-verified** sets, disjoint.

This file is the operating guide: what to run, and what each command should print. **Why the pipeline
is built this way is [docs/documentation.md](docs/documentation.md)**; the results are
[docs/report_260802.md](docs/report_260802.md); the counting and evidence rules are
[docs/SPEC.md](docs/SPEC.md).

## Requirements

[`uv`](https://docs.astral.sh/uv/) only. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`,
then `uv sync`. Everything below runs under `uv run`. The optional
[`just`](https://github.com/casey/just) wraps the same commands.

## Three ways to check this work

| Tier | What it proves | Cost | How |
|---|---|---|---|
| **1. Verify the shipped result** | Nothing has changed and every pair traces to a recorded observation | ~10 s | `bash verify.sh` at the delivery archive's root |
| **2. Rebuild from the evidence** | The shipped lists follow from the shipped evidence, byte for byte | ~1 min | `uv run ark rebuild ../provenance`, then `ark lang-report` and `ark check` |
| **3. Rebuild from the original sources** | The evidence follows from the source data | ~50 GB download, then ~20 min | Parts 1 and 2 below |

Tiers 1 and 2 need no network and no source data. Tier 1 needs nothing from this repository at all.

**Tier-3 cost figures date from the phase-1 archive and have not been re-measured.** One 47 GB capture
index is most of the download; skipping the Arquivo indexes left about 3 GB and reproduced 98.7% of
that archive. Those indexes now contribute zero net-new pairs against merged260730, so skipping them
costs less than the figure suggests. Measured then, a full run took about 20 minutes and returned
99.77% of the pairs with all invariants passing; the gap is two sources with no journal to replay.

## Reproduce the results

Every step is re-runnable: work already done is skipped, so an interrupted run finishes by running the
same command again. Each run appends to a log in `data/logs/`.

### Part 1: get the inputs (tier 3 only)

**The baseline** goes in `./legacy-data/`: the six year files, `merge_stats_new0714.csv`, and
`deduplicated_urls_2001-2002.txt`. The delivery archive ships these in `baseline/original/`, so
`cp -R ../baseline/original/. legacy-data/` is enough.

```bash
wc -l legacy-data/199[6-9].txt legacy-data/200[01].txt   # expect 8224963 total
```

**The bulk sources** go in `data/raw/<source>/`, one folder per source.
**[docs/sources.md](docs/sources.md) has the download command for each**, since the routes differ:
several survive only as web-archive captures, and one address answers HTTP 200 with a stub.

| Source | Folder | Size |
|---|---|--:|
| Arquivo.pt CDXJ (IA donation) | `data/raw/arquivo/` | 47 GB |
| UKWA host link graph | `data/raw/ukwa/` | 2.0 GB |
| AFNIC `.fr` open data | `data/raw/afnic/` | 782 MB |
| IA Early Web CDX | `data/raw/early_web/` | 177 MB |
| ISC surveys, ODP dumps, Scout Report | `data/raw/{isc_survey,odp,scout}/` | 70 MB |
| WebBase host list (seed only) | `data/raw/webbase/hosts.txt` | 14 MB |

```bash
uvx --from internetarchive ia download early-web_cdx-lang-cdxa \
    --glob='*.cdx.gz' --destdir=data/raw/early_web --no-directories

cd data/raw && shasum -a 256 -c checksums.sha256   # expect 235 OK lines
```

The manifest lists paths relative to `data/raw/`, which is why the check runs from there. Two sources
cannot be pinned: the `.fr` file is republished monthly (this used the June 2026 edition) and the
Internet Scout feed keeps growing.

**The network journals ship with the delivery** (`data/raw/cdx/`, `data/raw/rdap/`, `data/raw/expand/`,
`data/raw/usenet/`, `data/raw/tucows/`, `data/raw/lang/`). They hold the raw responses of every query
made, so Part 2 replays every network stage offline.

### Part 2: rebuild the result

| # | Command | Expected output |
|---|---|---|
| 1 | `uv sync` | creates `.venv` from `uv.lock`; no version resolution |
| 2 | `uv run ark init` | `provenance store ready`, then `work queue ready` |
| 3 | `uv run ark ingest-legacy` | `6 files ingested, 6866913 year rows added, 12220 lines rejected` (~2 min) |
| 4 | `uv run ark legacy-review` | `output/legacy_review/dropped_domains.txt (9329 distinct entries)` |
| 5 | `uv run ark audit` | writes `data/reports/normalization_audit.csv`, ~131 MB |
| 6 | `uv run ark ingest early_web data/raw/early_web/*.cdx.gz` | `files_ingested: 224`, `evidence_rows: 2278722` |
| 7 | `uv run ark ingest isc_survey data/raw/isc_survey/*.gz` | `files_ingested: 5`, `evidence_rows: 1662395` |
| 8 | `uv run ark ingest arquivo_roteiro data/raw/arquivo/Roteiro.cdxj` | `evidence_rows: 3442` |
| 9 | `uv run ark ingest arquivo_ia data/raw/arquivo/IA.cdxj` | `evidence_rows: 28247` |
| 10 | `uv run ark ingest afnic_fr data/raw/afnic/*NomsDeDomaineEnPointFr.csv` | `evidence_rows: 142248` |
| 11 | `uv run ark ingest internet_scout data/raw/scout/scout_oai.xml` | `evidence_rows: 975` |
| 12 | `uv run ark ingest odp data/raw/odp/*.gz` | `files_ingested: 3`, `evidence_rows: 19629` |
| 13 | `uv run ark ingest ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz` | `evidence_rows: 39454` |
| 14 | `uv run ark ingest ukwa_link_target data/raw/ukwa/host-linkage.tsv.gz` | `evidence_rows: 88263`, `enqueued: 5436` |
| 15 | `uv run ark ingest ncsa_whats_new data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv` | `evidence_rows: 4916` |
| 16 | `uv run ark seed data/raw/webbase/hosts.txt` | `lines: 738625`, `new_candidates: 39` |
| 17 | `uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt` | `lines: 1097867`, `new_candidates: 0` |
| 18 | `uv run ark seed seeds/100hot_hosts.txt` | `lines: 3453`, `new_candidates: 258` |
| 19 | `uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz` | replays every archive query |
| 20 | `uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz` | replays every registry query |
| 21 | the six `ark ingest expansion_*` commands in `just journals` | replays the archived-page fetches; `year_rows: 1577` across four rounds |
| 22 | `uv run ark ingest usenet_dated data/raw/usenet/usenet_dated*.jsonl.gz` | dated Usenet announcements, the largest source this round |
| 23 | `uv run ark ingest usenet_candidates data/raw/usenet/usenet_candidates*.jsonl.gz` | its uncorroborated half, to the candidate pool |
| 24 | `uv run ark ingest tucows_dated data/raw/tucows/tucows_dated.jsonl.gz` | software release dates with the vendor's home page |
| 25 | `uv run ark ingest tucows_candidates data/raw/tucows/tucows_candidates.jsonl.gz` | and its uncorroborated half |
| 26 | `just seeds` | `seeds: 3595769` hostnames and URLs over `domains: 2195955` |
| 27 | `uv run ark ingest-lang data/raw/lang/lang_*.jsonl.gz` | replays the English verification, one verdict per pair |
| 28 | `uv run ark export` | one `netnew_<year>` count per year, plus the Parquet evidence graph |
| 29 | `uv run ark lang-report` | the two disjoint sets, `disqualified.csv`, and the language summary |
| 30 | `uv run ark stats` | the scoreboard |
| 31 | `uv run ark check` | twelve `[PASS]` lines then `ALL PASS`; non-zero exit on any failure |

Steps 6 to 15 are order-independent. Steps 19 onward must follow them, because a replayed query is
evidence about a domain the bulk sources introduced, and the corroboration split in steps 22 to 25 is
judged against what the store holds by then.

```bash
wc -l output/netnew/*.txt   # equals the net-new pair count from `ark stats`
```

**With `just`:**

```bash
just setup       # step 1
just reproduce   # steps 2 to 31
just check       # lint + format-check + tests, then the twelve data invariants
```

`just check-data` runs the data invariants and `just verify-repo` runs the code checks; `just check`
runs both.

### Package the delivery archive

```bash
uv run python scripts/fill_report.py    # substitutes every figure into the report and email
bash scripts/package_delivery.sh        # tar.gz plus its SHA256
bash scripts/verify_delivery.sh output/internet-digital-ark-1996-2001
```

Packaging refuses to build from a modified working tree, or from an `output/` older than the store.

## Collecting more evidence (needs the network)

Collectors write journals and never touch the store, so they run for hours alongside everything else.

```bash
uv run ark gaps                                      # -> data/raw/cdx/gap_candidates.txt
uv run ark cdx data/raw/cdx/gap_candidates.txt -n 1200 --workers 8 --timeout 70
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz

uv run ark gaps --creation --out data/raw/rdap/creation_candidates.txt
uv run ark rdap data/raw/rdap/creation_candidates.txt -n 2500
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
```

`scripts/supervise_engines.sh` keeps both fed unattended.

`ark gaps` orders by expected equivalent-English: the English share of the domain's TLD times the
number of bracketed years a capture could fill. `--legacy-year-order` restores the pre-August-2026
order (thinnest gap year first) for reproducing earlier rounds.

The other population is the candidate pool: domains the store holds with no year at all, so a
capture makes a name net-new rather than adding a year to one already shipped.

```bash
uv run python scripts/build_pool_candidates.py   # -> data/raw/cdx/pool_candidates.txt
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_pool_*.jsonl.gz
```

### One queue, not two

Keeping the two populations in two lists forced a choice about which to work, and on 7 August that
choice was being made by hand and made wrong: the MacBook spent a morning on candidate-pool targets
worth 0.476 equivalent-English per query while gap targets worth twice that waited in the other
file. So both are now scored on the one scale that decides the allocation, **expected net-new
equivalent-English per archive query**, and merged into a single queue.

```bash
just query-queue-preview            # what it would return, writes nothing
just query-queue                    # -> queue_shard0.txt, queue_shard1.txt, queue_manifest.tsv.gz
```

A gap target scores `realisation x English share x bracketed years it could fill`; a pool target
scores `P(hit) x English share x years a hit returns`. Both multipliers are measured at build time
and printed with the queue, so a wrong one is visible rather than silent. Rebuild after any large
ingest: new evidence creates bracketed gaps as well as filling them, and a stale queue cannot reach
what it does not list. Ignoring that cost the 5 August lists 102,628 targets worth 63,333
equivalent-English, enough to put the round's ceiling below the goal it was aiming at.

The manifest records the population and predicted score of every target, which is what lets the
next build re-estimate hit rates from a queue that mixes both, and what lets a prediction be checked
against the outcome instead of being taken on trust.

### Collecting from more than one machine

Split the queue into disjoint shares and run one per machine. Assignment is by content hash, so the
shares are disjoint and jointly complete with no coordination, and because the hash is independent
of the ordering each share is a representative sample of the whole value curve rather than a
contiguous block of it.

**Size each share by how fast its machine is.** Equal halves were right while the two collectors ran
at similar speeds; measured on 7 August the MacBook sustains 916 queries an hour against the VPS's
262, and an even split leaves the fast machine grinding its own cheap tail while the expensive head
of the other half goes untouched. `--weights 78,22` costs nothing and saves about 20 hours.

```bash
# on this machine, build both shares (only this one has the store)
just query-queue 78,22

# ship share 1 and the repo to the other machine, then there:
ARK_TARGETS=data/raw/cdx/queue_shard1.txt ARK_PREFIX=cdx_q1 \
    bash scripts/supervise_cdx_pool.sh <deadline_epoch> 300 8 900

# bring its journals back and replay them here
rsync -av vps:~/proj-internet-digital-ark/data/raw/cdx/cdx_q1_*.jsonl.gz data/raw/cdx/
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_q1_*.jsonl.gz
```

The shares are written with every already-answered domain removed, so re-sharding never makes a
machine re-ask a name the other has settled, and the weights can be retuned whenever the measured
speeds change.

The older `just gap-shards` still writes gap-only slices in equal parts, for reproducing rounds
collected that way.

The remote machine needs the repo, `uv`, and its slice. It does **not** need the store: collection
never opens it. Give each machine its own `ARK_PREFIX` so two runs cannot write the same journal
name, and keep the prefix starting `cdx_` so the ingest globs and the resume scan still see it.

The list is ordered best-first: TLDs that existed in 1996-2001, then by the English share of the
TLD from the reviewer's own model, so a run that never finishes the pool has still spent its
requests where the equivalent-English metric pays most. The supervisor takes a deadline epoch and
polls journal growth to catch a batch that has hung while still looking alive.

Check both machines at once, including whether the remote journals have been brought home:

```bash
just engines
```

### Pausing and resuming

```bash
just engines-stop                  # this machine, without losing the batch in flight
just engines-start 1787139003      # deadline epoch, from `date -u -v+12d +%s`
```

`engines-stop` sends TERM to the supervisor, which runs its trap, asks the batch to stop, and lets
it publish what it already has. A stopped batch still writes its journal, so the only thing lost is
the queries it had not made yet: two interruptions on 7 August published 140 and 172 of 300 lines
and nothing had to be re-queried. **Never `kill -9` a collector.** That strands the `.part`, and the
ingest ledger keys on the finished name, so the work inside it becomes unreachable.

Stopping the ingest loop leaves whatever the collectors wrote sitting on disk. That is safe, because
journals are ledgered by content hash and re-offering an ingested one is skipped in milliseconds,
but it does mean `ark stats` understates the round until the loop runs again. To fold everything in
before shutting down for a while:

```bash
for j in data/raw/cdx/cdx_*.jsonl.gz;            do uv run ark ingest cdx_snapshot "$j"; done
for j in data/raw/usenet/usenet_dated_*.jsonl.gz; do uv run ark ingest usenet_dated "$j"; done
```

The remote machine is unaffected by any of this. It runs under `setsid` with its own deadline, so it
keeps collecting through a VPN drop or a laptop shutdown, and its journals wait on its own disk
until the next `rsync`.

That last part is the one worth automating. A second machine's output is invisible to every
measurement taken on the first, and the VPS once ran for a day and a half with 5,793 year-records
sitting on its disk and absent from the store, because nothing here ever looked. `just engines`
lists any remote journal missing locally and prints the `rsync` that fetches it.

It also prints the tier mix, which is how a run's health reads at a glance. `host` is the cheap
per-host query answering on its own, `root` is a domain so heavily archived that the archive gave up
and the apex and www root pages rescued it, `scan` is the wildcard fallback. Drifting toward `root`
means a clogged stretch of queue that will clear; drifting toward failures means the archive is
refusing connections, and the fix is fewer workers, not more.

**More workers do not buy more throughput.** The archive limits concurrent connections per IP, and
8 and 12 workers measure the same, 506 against 510 queries/hour. What raises the ceiling is another
address, which is the real argument for the second machine.

### Page expansion

```bash
uv run ark download seeds/expansion/seeds_round4.txt -n 250 --workers 3 --captures 2 \
    --out data/raw/expand/round5/expand_round5.jsonl.gz
uv run python scripts/split_expansion_journal.py \
    data/raw/expand/round5/expand_round5.jsonl.gz --write
uv run ark ingest expansion_directory \
    data/raw/expand/round5/expand_round5_corroborated.jsonl.gz --round 5
uv run ark ingest expansion_links \
    data/raw/expand/round5/expand_round5_unverified.jsonl.gz --round 5
```

Or `just expand-round seeds/expansion/seeds_round4.txt 5`. The split sends links from domains the
store already attests to dated evidence, and never-before-seen names to the candidate pool.

### English verification

```bash
uv run ark lang-targets                                    # -> data/raw/lang/lang_targets.txt
uv run ark lang data/raw/lang/lang_targets.txt -n 400 \
    --workers 2 --samples 2 --delay 2.0 --min-delay 1.5
uv run ark ingest-lang data/raw/lang/lang_*.jsonl.gz
uv run ark lang-report
```

Unattended, for a long stretch:

```bash
bash scripts/supervise_lang.sh 27000 400 2 1.5           # seconds, batch, workers, min-delay
bash scripts/watchdog_lang.sh 600 <deadline_epoch> 400 2 1.5
```

`--min-delay` is the floor the adaptive governor may not ease below, and for this engine the floor
rather than the worker count is what bounds load on `web.archive.org`. 2 workers and a 1.5 s floor is
the measured setting; more workers is slower.

`ark lang-report` writes a **partition** of the additions:

| path | contents |
|---|---|
| `output/netnew_english/<year>.txt` and `.csv` | pairs whose archived body text for that year was read and was more than half English |
| `output/netnew_unverified/<year>.txt` and `.csv` | every other addition, with a `status` and a `reason` per row |
| `output/disqualified.csv` | the per-item register: pairs judged and rejected |
| `output/language_summary.csv` | the per-year and total mix, for pairs and for unique domains |

The two annual sets are disjoint and sum to the total. Two integrity checks assert that.

### New sources of this round

```bash
uv run python scripts/split_usenet.py data/raw/usenet/*.mbox.zip --tag b1 --write
uv run python scripts/measure_usenet_yield.py data/raw/usenet/*.zip   # yield before committing
bash scripts/ingest_new_usenet.sh auto

uv run python scripts/split_tucows.py --write

bash scripts/maintain_phase3.sh 26 900   # fold finished collector output in, every 15 minutes
```

### Reporting a round

The reviewer set the reporting format on 6 August: five fields, where lines 1 and 2 are his merged
database before our increment and line 5 is line 4 divided by line 2. `round_figures.py` prints them
in his order, so the growth rate cannot drift between rounds by being divided by the wrong total.

```bash
uv run python scripts/round_figures.py            # the five fields, plus per-year and per-source
uv run python scripts/round_figures.py --verify   # re-score with HIS calculator; non-zero exit on any disagreement
```

Always send with `--verify`. It writes the increment out per year, runs his own
`equivalent_english_domains.py` over each file, and refuses the numbers if his total differs from
ours or if his validator rejects a record we counted. A rejected record scores zero for him and full
weight for us, which is a live risk every time a source widens its matching.

## Structure

The repo holds code and docs only; all data stays out of git. `output/` is generated and regenerable
via `ark export`, and ships in the delivery archive.

```
output/                        git-ignored, regenerable; shipped in the archive
├── netnew/                    the additions: one file per year, plus evidence_manifest.csv
├── netnew_english/            the English-verified partition, .txt and .csv
├── netnew_unverified/         the rest, disjoint, with status and reason
├── disqualified.csv           every pair judged and rejected, one row each
├── candidate_unverified.txt   domains awaiting per-year evidence
├── provenance/                the evidence graph as Parquet + LOAD.sql
└── legacy_review/             every excluded baseline line, grouped by reason

data/          git-ignored: DuckDB store, work queue, downloaded sources, audit CSVs, logs
legacy-data/   git-ignored: the provided baseline, dropped in
src/ark/       the pipeline package and the `ark` CLI
tests/         pytest, network mocked
docs/          SPEC, documentation, sources, notes, the round report
```
