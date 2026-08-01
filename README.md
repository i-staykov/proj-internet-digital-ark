# Internet Digital Ark

A reproducible pipeline that collects historical **domain names for 1996-2001**, each backed by **item-level, per-year evidence** (an archive capture, a dated index, or a WHOIS creation date). It grows a provided ~8.2M-domain baseline and ships its additions as a **separate, verifiable set**; the baseline is never modified.

## Requirements

[`uv`](https://docs.astral.sh/uv/) only. It installs Python 3.12, the dependencies, and their locked versions. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`, then `uv sync`. Every command below runs under `uv run` with nothing else installed; the optional [`just`](https://github.com/casey/just) wraps the same commands.

## Three ways to check this work

Pick by how much you want to spend. **The first two need no downloads and no network**, and the delivery archive's own `README.md` describes the same three from the archive's side.

| Tier | What it proves | Cost | How |
|---|---|---|---|
| **1. Verify the shipped result** | Every shipped pair traces to a recorded observation, and no file has changed | ~10 s | `bash verify.sh` at the archive root; `provenance/trace.py` for any single domain |
| **2. Rebuild from the evidence** | The shipped lists follow from the shipped evidence, byte for byte | ~1 min | `uv run ark rebuild ../provenance` then `ark check` |
| **3. Rebuild from the original sources** | The evidence itself follows from the source data | 50 GB download, then ~20 min | Part 1, then Part 2 below |

**Tier 1** needs nothing from this repository: the archive ships `verify.sh` (checksums, pair counts, and that every pair appears in the evidence manifest) and `provenance/trace.py`, which prints the observations behind any domain-year using only `uv`.

**Tier 2** loads `provenance/` into the store and re-runs the exporter, regenerating all fourteen result files **byte-identically** and re-running the twelve invariants. It needs no source data at all, which is what makes it a one-minute check rather than an afternoon.

**Tier 3** is the full pipeline below, and the only tier that needs the source data. The supplied baseline ships in the archive's `baseline/original/` folder, and the reference this round is scored against in `baseline/merged260730/`, so the ~50 GB of bulk sources are the only thing to fetch. One 47 GB capture index is most of that: **skipping the Arquivo indexes costs 17,696 pairs over 7,001 domains and leaves about 3 GB**, reproducing 98.7% of the result.

**These tier-3 cost figures date from the phase-1 archive and have not been re-measured.**
They are indicative of the shape of the trade, not current. The Arquivo indexes now contribute
zero net-new pairs against merged260730, because a later baseline absorbed them, so skipping
them costs less than the figure above suggests.

Measured, a full run takes about 20 minutes and returns **1,319,272 of the 1,322,365 pairs (99.77%)**, all invariants passing. The gap is two sources with no journal to replay: the legacy `rdap` tranche (3,106 pairs, see the report's limitations) and the superseded `ia_cdx` route (11). Their 840 domains return to the candidate pool rather than being lost. Tier 2 is the byte-for-byte check; tier 3 re-derives what files can re-derive.

`data/raw/checksums.sha256` pins 235 files, every source that can be pinned. Two cannot: the `.fr` file is republished monthly (this used the June 2026 edition) and the Internet Scout feed keeps growing, so a later download need not match. The shipped journals and Parquet export do not move, which is the point of them.

## Reproduce the results

Two jobs, and only the first needs the network:

- **Part 1, get the inputs** (tier 3 only). The bulk source files, about 50 GB, so they are fetched rather than shipped.
- **Part 2, rebuild the result** (tier 3). Deterministic and offline, about 20 minutes measured. Returns 99.77% of the shipped numbers, with the gap accounted for above.

Every step below prints what it did, and the expected output is given so a mismatch is visible immediately rather than three steps later. Every step is re-runnable: work already done is skipped, so an interrupted run is finished by running the same command again. Each run appends to a log in `data/logs/`.

### Part 1: get the inputs

**The baseline** goes in `./legacy-data/`: the six year files, `merge_stats_new0714.csv`, and `deduplicated_urls_2001-2002.txt`. The delivery archive ships these in `baseline/`, so `cp -R ../baseline legacy-data` is enough. Confirm it is the expected one:

```bash
wc -l legacy-data/1996.txt legacy-data/1997.txt legacy-data/1998.txt \
      legacy-data/1999.txt legacy-data/2000.txt legacy-data/2001.txt
# expect 8224963 total
```

**The bulk sources** go in `data/raw/<source>/`, one folder per source. **[docs/sources.md](docs/sources.md) gives the download commands for each**, since the routes differ a lot: several are only available from web-archive captures, and one address still answers HTTP 200 with a stub instead of the file. Sizes:

| Source | Folder | Size | Route |
|---|---|---|---|
| Arquivo.pt CDXJ (IA donation) | `data/raw/arquivo/` | 47 GB | resumable single-connection download, about 8.5 hours |
| UKWA host link graph | `data/raw/ukwa/` | 2.0 GB | only a Wayback capture survives; the original host and the dataset DOI are both dead |
| AFNIC `.fr` open data | `data/raw/afnic/` | 782 MB | `https://opendata.afnic.fr/`, open licence, attribution only |
| IA Early Web CDX | `data/raw/early_web/` | 177 MB | the command below |
| ISC surveys, ODP dumps, Scout Report | `data/raw/{isc_survey,odp,scout}/` | 70 MB | rescued from Wayback or harvested by OAI-PMH, all pinned by hash |
| WebBase host list (seed only, no dates) | `data/raw/webbase/hosts.txt` | 14 MB | Stanford WebBase crawl host list, feeds the candidate pool |

```bash
uvx --from internetarchive ia download early-web_cdx-lang-cdxa \
    --glob='*.cdx.gz' --destdir=data/raw/early_web --no-directories
```

Anything rescued from a host that no longer serves it is pinned by hash, so a re-fetch that returns something different is caught rather than ingested:

```bash
cd data/raw && shasum -a 256 -c checksums.sha256   # expect 235 OK lines
```

The manifest lists paths relative to `data/raw/`, which is why the command runs from there.

**The network journals ship with the delivery** (5.5 MB, from `data/raw/cdx/`, `data/raw/rdap/` and `data/raw/expand/`). They hold the raw responses of every archive, registry and page query made, so Part 2 replays every network stage from bytes on disk and needs no network at all. This also means the result does not drift when a live service changes its answer.

### Part 2: rebuild the result

| # | Command | Expected output |
|---|---|---|
| 1 | `uv sync` | creates `.venv` from `uv.lock`; no version resolution happens |
| 2 | `uv run ark init` | `provenance store ready at data/ark.duckdb`, then `work queue ready at data/queue.sqlite` |
| 3 | `uv run ark ingest-legacy` | `6 files ingested, 0 skipped, 6866913 year rows added, 12220 lines rejected` (about 2 min) |
| 4 | `uv run ark legacy-review` | `see output/legacy_review/dropped_domains.txt (9329 distinct entries)` |
| 5 | `uv run ark audit` | writes `data/reports/normalization_audit.csv`, about 131 MB |
| 6 | `uv run ark ingest early_web data/raw/early_web/*.cdx.gz` | `files_ingested: 224`, `evidence_rows: 2278722` (about 1 min) |
| 7 | `uv run ark ingest isc_survey data/raw/isc_survey/*.gz` | `files_ingested: 5`, `evidence_rows: 1662395` |
| 8 | `uv run ark ingest arquivo_roteiro data/raw/arquivo/Roteiro.cdxj` | `evidence_rows: 3442` |
| 9 | `uv run ark ingest arquivo_ia data/raw/arquivo/IA.cdxj` | `evidence_rows: 28247` |
| 10 | `uv run ark ingest afnic_fr data/raw/afnic/*NomsDeDomaineEnPointFr.csv` | `evidence_rows: 142248` |
| 11 | `uv run ark ingest internet_scout data/raw/scout/scout_oai.xml` | `evidence_rows: 975` |
| 12 | `uv run ark ingest odp data/raw/odp/*.gz` | `files_ingested: 3`, `evidence_rows: 19629` |
| 13 | `uv run ark ingest ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz` | `evidence_rows: 39454` |
| 14 | `uv run ark ingest ukwa_link_target data/raw/ukwa/host-linkage.tsv.gz` | `evidence_rows: 88263`, `enqueued: 5436` (same file, candidate side) |
| 15 | `uv run ark ingest ncsa_whats_new data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv` | `evidence_rows: 4916`, `year_rows: 7` |
| 16 | `uv run ark seed data/raw/webbase/hosts.txt` | `lines: 738625`, `new_candidates: 39` |
| 17 | `uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt` | `lines: 1097867`, `new_candidates: 0` |
| 18 | `uv run ark seed seeds/100hot_hosts.txt` | `lines: 3453`, `new_candidates: 258` |
| 19 | `uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz` | replays every archive query; `files_ingested` equals the number of `cdx_*.jsonl.gz` files present |
| 20 | `uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz` | replays every registry query; `files_ingested` equals the number of `rdap_*.jsonl.gz` files present |
| 21 | the six `ark ingest expansion_*` commands in `just journals` | replays the archived-page fetches; the corroborated half adds `year_rows: 1577` across four rounds, the rest enqueues candidates |
| 21b | `uv run ark ingest usenet_dated data/raw/usenet/usenet_dated*.jsonl.gz` | dated website announcements from Usenet, the largest single source of this round |
| 21c | `uv run ark ingest usenet_candidates data/raw/usenet/usenet_candidates*.jsonl.gz` | the uncorroborated half of the same, which enters the candidate pool rather than an annual file |
| 21d | `uv run ark ingest tucows_dated data/raw/tucows/tucows_dated.jsonl.gz` | software-catalogue release dates with the vendor's home page |
| 21e | `uv run ark ingest tucows_candidates data/raw/tucows/tucows_candidates.jsonl.gz` | and its uncorroborated half |
| 22 | `just seeds`, or the five `ark seed-pool` commands it wraps | rebuilds the auxiliary seed pool: `seeds: 3595769` hostnames and URLs over `domains: 2195955` |
| 23 | `uv run ark export` | one `netnew_<year>` count per year, the per-source table, and `provenance_mb: 241` for the Parquet evidence graph |
| 24 | `uv run ark stats` | the scoreboard, headed by net-new domains and net-new (domain, year) pairs |
| 25 | `uv run ark ingest-lang data/raw/lang/lang_*.jsonl.gz` | replays the English verification: one verdict per (domain, year), from the snapshot URLs the journals name |
| 26 | `uv run ark lang-report` | the two disjoint sets in `output/netnew_english/` and `output/netnew_unverified/`, the per-item `disqualified.csv`, and the section 6.1 language table |
| 27 | `uv run ark check` | twelve `[PASS]` lines then `ALL PASS`; exits non-zero if any invariant fails |

Steps 6 to 15 are independent of each other, so their order does not matter. Steps 19 to 21 must come after them, because a replayed query is evidence about a domain the bulk sources introduced, and step 21's corroboration split is judged against what the store holds by then.

Steps 23 and 24 print the size of the result, which grows every time more evidence is collected, so they are quoted as shapes rather than as fixed numbers. The check that matters is that they agree with each other: the pair total from step 24 equals the line count of the shipped year files, and step 25 fails if it does not.

```bash
wc -l output/netnew/*.txt   # total equals the net-new pair count printed by ark stats
```

For the archive as delivered that total is **1,322,365 pairs over 463,566 domains**, with `output/netnew/evidence_manifest.csv` naming the evidence behind every one of them.

Then, to assemble the archive that was delivered:

```bash
bash scripts/package_delivery.sh   # tar.gz plus its SHA256, and prints the filename, size, format and checksum
```

It refuses to build from a modified working tree, or from an `output/` older than the store, because either one ships code and data that disagree.

**With `just`.** If [`just`](https://github.com/casey/just) is installed, the whole of Part 2 is three commands, and `just --list` shows every recipe:

```bash
just setup       # step 1
just reproduce   # steps 2 to 25: baseline -> sources -> candidates -> journals -> seeds -> deliver
just check       # lint + format-check + tests, then the twelve data invariants
```

Two of those names are deliberate. `just check-data` runs `ark check`, which validates the **data**; `just verify-repo` runs lint, format-check and tests, which validate the **code**. Giving either one the bare name `check` invites running one and believing the other passed, so `just check` runs both.

### Collecting more evidence (this part needs the network)

The two collectors (`ark cdx` against the Internet Archive, `ark rdap` against the registries) write a per-run **journal** and no evidence; a later `ingest` turns journals into evidence. So they never hold the store's single write lock, and a long pass can run for hours alongside everything else. They also hit different services, so both can run at once.

```bash
uv run ark gaps                                      # -> data/raw/cdx/gap_candidates.txt
uv run ark cdx data/raw/cdx/gap_candidates.txt -n 1200 --workers 8 --timeout 70
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz

uv run ark gaps --creation --out data/raw/rdap/creation_candidates.txt
uv run ark rdap data/raw/rdap/creation_candidates.txt -n 2500
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
```

`ark cdx` sends one collapsed query per domain covering all six years, paced by a governor that eases up while the service is healthy and backs off on 429/503/504, honouring `Retry-After`. Concurrency is the throughput lever, because a wildcard CDX query costs about 20 seconds; 8 workers sustained roughly 1,000 answered domains per hour. `scripts/supervise_engines.sh` keeps both fed for an unattended stretch and holds off dispatching against a service that has stopped answering.

A running collector writes `<journal>.jsonl.gz.part` and renames it on exit, so the `ingest` globs never pick up a half-written file (which would record the hash of its first lines and lock the rest of the run out of the ledger). The rename happens on Ctrl-C and on `kill` as well; only `kill -9` leaves a `.part` behind, and renaming it by hand makes it ingestable. Either way, a later run still reads `.part` files when deciding what to skip, so nothing already answered is asked twice.

### Page expansion

The expansion cycle fetches archived pages from the Wayback Machine, extracts the domains they link to, and splits the result by corroboration: a domain some other source already attests becomes dated evidence (its capture year), while a never-before-seen name becomes a candidate. One round:

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

Or `just expand-round seeds/expansion/seeds_round4.txt 5`, which runs the same four steps.

`ark download` requests each seed URL from the Wayback CDX API, fetches up to two original-byte captures per URL, and writes a journal. `split_expansion_journal.py` reads the journal and the store, divides each page's outbound links into corroborated (known to the store from some other source) and uncorroborated (never seen), and writes two journals. The corroborated half is ingested as `expansion_directory` with `dated_directory` evidence; the uncorroborated half as `expansion_links` with `link_target` evidence, which is candidate-only.

The delivered result used four numbered rounds. Round 1 fetched portals and directories as candidate-only links (the `directory` assertion was deliberately withheld until a page was read). Rounds 2 and 4 fetched WWW Virtual Library subject pages, each asserted as a curated catalogue. Round 3 processed 641 VLib captures already on disk from the source survey via `scripts/journal_from_wwwvl.py --write`, then the same two-step ingest; since no download was needed, there is no `seeds_round3.txt`, which is why the shipped seed files are numbered 1, 2, 4. The seed files are in `seeds/expansion/`.

Discovered candidates can then be verified against the archive to close the loop:

```bash
uv run ark cdx data/raw/cdx/discovered_candidates.txt -n 298 --workers 4 --timeout 70 \
    --out data/raw/cdx/cdx_discovered.jsonl.gz
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_discovered.jsonl.gz
```

### Verifying the English-website standard (this part needs the network)

The governing rule for the current round admits a domain to an annual file only when it belongs to an English-language website, or one where English is more than half of the reliably classified body text, judged **at website level from archived page body text** rather than from the domain spelling or its TLD. `ark lang` measures that per (domain, year).

```bash
uv run ark lang-targets                                    # -> data/raw/lang/lang_targets.txt
uv run ark lang data/raw/lang/lang_targets.txt -n 400 \
    --workers 2 --samples 2 --delay 2.0 --min-delay 1.5    # writes a journal, never opens the store
uv run ark ingest-lang data/raw/lang/lang_*.jsonl.gz       # -> the domain_language table
uv run ark lang-report                                     # -> output/netnew_english/ + language_summary.csv
```

Or `bash scripts/supervise_lang.sh 27000 400 2 1.5` to run it in batches for a long stretch, with `bash scripts/watchdog_lang.sh 600 <deadline_epoch>` beside it. The watchdog tests **progress rather than presence**: a batch that hangs on a socket leaves the supervisor alive and the journal frozen, which a process check reports as healthy.

Per pair it asks the CDX index for in-year captures of the domain, fetches up to `--samples` of them as **raw bytes**, decodes with `charset_normalizer` rather than assuming UTF-8, strips markup to body text, and classifies with `py3langid`. Captures under 200 characters or below 0.50 confidence are "not reliably classified" and leave the denominator entirely; the rest are weighted by text length, and a share strictly above 0.50 admits.

**Language is not an evidence type.** Verdicts go to `domain_language`, keyed on the same (domain, year) pair as everything else, because every `evidence_type` answers "did this exist in this year" while a verdict answers "what was this", and a domain can be perfectly evidenced and still inadmissible. Each verdict stores **the exact snapshot URLs it read**, so any one can be refetched and recomputed; that is what separates it from a TLD prior.

#### Two disjoint sets, and the difference between them

`ark lang-report` writes a **partition** of the additions, not a set and a subset of it:

| path | what it holds |
|---|---|
| `output/netnew_english/<year>.txt` and `.csv` | pairs whose archived body text for that year was read and was more than half English |
| `output/netnew_unverified/<year>.txt` and `.csv` | every other addition, with a `status` and a `reason` per row |
| `output/disqualified.csv` | the per-item register: only pairs we judged and rejected |
| `output/language_summary.csv` | the per-year and total mix, for both domain-year records and unique domains |

The two annual sets are disjoint and sum to the total, so a reviewer can add them without double counting. Two integrity checks assert that against the shipped files rather than the README claiming it.

The `status` column carries the distinction that matters most:

- **`disqualified`** means the archive was asked and answered, and the pair failed the standard. Every one carries a `reason` from a closed vocabulary (`no_capture_in_year`, `no_readable_html_capture`, `insufficient_text`, `non_site_text`, `low_confidence`, `other_language`, `mixed_below_threshold`) and appears individually in the register.
- **`unchecked`** means the engine has not reached the pair. **No claim is made about its language, and none about whether the archive holds a capture for it.**

That second point is load-bearing. The capture query filters on `statuscode:200` and `mimetype:text/html`, so an empty result means "nothing matching that filter", not "nothing at all". Before the engine will write `no_capture_in_year` it sends a second, completely unfiltered index probe; if that probe also comes back empty the claim is earned, if it returns rows the reason becomes `no_readable_html_capture`, and if the probe itself fails the pair is left unsettled with no verdict written. A domain is never excluded on the strength of a question that was not asked.

**Rate note.** This sends one CDX query plus up to `--samples` page fetches per pair, so it is several times heavier than `ark cdx`. `--min-delay` is the floor the adaptive governor may not ease below, and for this engine the floor rather than the worker count is what bounds the load on `web.archive.org`. A run at 4 workers with the old 0.05 s floor drew a connection refusal within four minutes. The engine now treats a refused connection as a throttle and stops itself after 25 consecutive failures.

### New sources of this round

```bash
# Usenet: dated website announcements. Split by corroboration before ingest.
uv run python scripts/split_usenet.py data/raw/usenet/*.mbox.zip --tag b1 --write
uv run python scripts/measure_usenet_yield.py data/raw/usenet/*.zip   # yield before committing
bash scripts/ingest_new_usenet.sh auto                                # or let the loop do it

# Tucows: software release dates with the vendor's home page URL
uv run python scripts/split_tucows.py --write

# fold whatever the collectors have finished into the store, every 15 minutes
bash scripts/maintain_phase3.sh 26 900
```

Both sources take the same corroboration split: a domain another source already places in an annual file carries the date as `dated_directory`, and a name appearing only in that source becomes a `link_target` candidate to earn its own evidence. `docs/sources.md` records the reasoning and every source rejected, with the measurement that rejected it.

**Reproducibility.** `uv.lock` pins exact dependency versions and the Public Suffix List is vendored, so canonicalization and the baseline processing are deterministic on any machine. `uv run` is the contract and works with only `uv` installed. CI runs lint, format-check and tests on every push.

## Structure

The repo holds code and docs only; all data stays out of git. `output/` is the generated deliverable: git-ignored and regenerable via `ark export`, shipped in the delivery archive.

```
output/          # git-ignored, regenerable via `ark export`; shipped in the archive
├── netnew/                    # the additions: one file per year (1996..2001)
│   └── evidence_manifest.csv  # every addition traced to its evidence (+ a Wayback link)
├── candidate_unverified.txt   # domains awaiting per-year evidence
├── seeds/
│   ├── download_seeds.txt     # auxiliary seed pool: hostnames and URLs, one per line
│   └── download_seeds.csv     # the same seeds with their domain, year and source
├── provenance/                # the evidence graph as Parquet + LOAD.sql (241 MB)
└── legacy_review/
    └── dropped_domains.txt    # every excluded baseline line, grouped by reason

data/            # git-ignored: DuckDB store, work queue, downloaded sources (raw/),
                 # audit CSVs (reports/), merged master lists (exports/), logs/
legacy-data/     # git-ignored: the provided baseline, dropped in (not in the repo)
src/ark/         # the pipeline package and the `ark` CLI
tests/           # pytest suite (network mocked)
docs/            # SPEC, sources.md (per-source documentation), report
```

`ark export` writes the net-new additions to `output/netnew/`, the candidate list, and the large **merged master lists** (baseline + additions) to `data/exports/`. All of it is git-ignored and regenerable; the delivery archive is assembled from these outputs.
