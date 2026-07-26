# Internet Digital Ark

A reproducible pipeline that collects historical **domain names for 1996-2001**, each backed by **item-level, per-year evidence** (an archive capture, a dated index, or a WHOIS creation date). It grows a provided ~8.2M-domain baseline and ships its additions as a **separate, verifiable set**; the baseline is never modified.

## Requirements

[`uv`](https://docs.astral.sh/uv/) only. It installs Python 3.12, the dependencies, and their locked versions. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`, then `uv sync`. Every command below runs under `uv run` with nothing else installed; the optional [`just`](https://github.com/casey/just) wraps the same commands.

## Three ways to check this work

Pick by how much you want to spend. **The first two need no downloads and no network**, and the delivery archive's own `README.md` describes the same three from the archive's side.

| Tier | What it proves | Cost | How |
|---|---|---|---|
| **1. Verify the shipped result** | Every shipped pair traces to a recorded observation, and no file has changed | ~10 s | `bash verify.sh` at the archive root; `provenance/trace.py` for any single domain |
| **2. Rebuild from the evidence** | The shipped lists follow from the shipped evidence, byte for byte | ~1 min | `uv run ark rebuild provenance/` then `ark check` |
| **3. Rebuild from the original sources** | The evidence itself follows from the source data | hours + 51 GB | Part 1, then Part 2 below |

**Tier 1** needs nothing from this repository: the archive ships `verify.sh` (checksums, pair counts, and that every pair appears in the evidence manifest) and `provenance/trace.py`, which prints the observations behind any domain-year using only `uv`.

**Tier 2** loads `provenance/` into a fresh store and re-runs the exporter, regenerating all thirteen result files **byte-identically** and re-running the nine invariants. It needs no source data at all, which is what makes it a one-minute check rather than an afternoon.

**Tier 3** is the full pipeline below, and the only tier that needs the source data: the ~51 GB of bulk sources **and** the supplied baseline in `legacy-data/`, since the annual masters are baseline plus additions and "net-new" is defined against it. One 47 GB capture index is most of the bulk: **skipping it costs exactly 17,696 pairs over 7,001 domains and leaves about 4 GB**, reproducing 98.7% of the result.

## Reproduce the results

Two jobs, and only the first needs the network:

- **Part 1, get the inputs** (tier 3 only). The provided baseline, plus the bulk source files. About 51 GB, so they are fetched rather than shipped.
- **Part 2, rebuild the result** (tier 2). Deterministic and offline, roughly 10 minutes. This reproduces the shipped numbers exactly.

Every step below prints what it did, and the expected output is given so a mismatch is visible immediately rather than three steps later. Every step is re-runnable: work already done is skipped, so an interrupted run is finished by running the same command again. Each run appends to a log in `data/logs/`.

### Part 1: get the inputs

**The baseline** goes in `./legacy-data/`: the six year files, `merge_stats_new0714.csv`, and `deduplicated_urls_2001-2002.txt`. These are the supplied files, not shipped back in the delivery archive; tier 3 needs them because the annual masters are baseline plus additions and "net-new" is defined against the baseline. Confirm it is the expected one:

```bash
wc -l legacy-data/1996.txt legacy-data/1997.txt legacy-data/1998.txt \
      legacy-data/1999.txt legacy-data/2000.txt legacy-data/2001.txt
# expect 8224963 total
```

**The bulk sources** go in `data/raw/<source>/`, one folder per source. Sizes and routes differ a lot, so each source has its own entry in [docs/sources.md](docs/sources.md) giving what it is, where it came from, its licence, and what its dates mean. The two largest dominate the time:

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
| 14b | `uv run ark ingest ncsa_whats_new data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv` | `evidence_rows: 4916`, `year_rows: 7` |
| 15 | `uv run ark seed data/raw/webbase/hosts.txt` | `lines: 738625`, `new_candidates: 39` |
| 16 | `uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt` | `lines: 1097867`, `new_candidates: 0` |
| 17 | `uv run ark seed data/raw/100hot/candidate_hosts.txt` | `lines: 3453`, `new_candidates: 258` |
| 18 | `uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz` | replays every archive query; `files_ingested` equals the number of `cdx_*.jsonl.gz` files present |
| 19 | `uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz` | replays every registry query; `files_ingested` equals the number of `rdap_*.jsonl.gz` files present |
| 20 | the six `ark ingest expansion_*` commands in `just journals` | replays the section VII page fetches; the corroborated half adds `year_rows: 1577` across four rounds, the rest enqueues candidates |
| 21 | `just seeds`, or the five `ark seed-pool` commands it wraps | rebuilds the auxiliary seed pool: `seeds: 3595769` hostnames and URLs over `domains: 2195955` |
| 22 | `uv run ark export` | one `netnew_<year>` count per year, the per-source table, and `provenance_mb: 241` for the Parquet evidence graph |
| 23 | `uv run ark stats` | the scoreboard, headed by net-new domains and net-new (domain, year) pairs |
| 24 | `uv run ark check` | nine `[PASS]` lines then `ALL PASS`; exits non-zero if any invariant fails |

Steps 6 to 14 are independent of each other, so their order does not matter. Steps 18 to 20 must come after them, because a replayed query is evidence about a domain the bulk sources introduced, and step 20's corroboration split is judged against what the store holds by then.

Steps 22 and 23 print the size of the result, which grows every time more evidence is collected, so they are quoted as shapes rather than as fixed numbers. The check that matters is that they agree with each other: the pair total from step 23 equals the line count of the shipped year files, and step 24 fails if it does not.

```bash
wc -l output/netnew/*.txt   # total equals the net-new pair count printed by ark stats
```

For the archive as delivered that total is **1,322,358 pairs over 463,565 domains**, with `output/netnew/evidence_manifest.csv` naming the evidence behind every one of them.

Then, to assemble the archive that was delivered:

```bash
bash scripts/package_delivery.sh   # tar.gz plus its SHA256, and prints the filename, size, format and checksum
```

It refuses to build from a modified working tree, or from an `output/` older than the store, because either one ships code and data that disagree.

**With `just`.** If [`just`](https://github.com/casey/just) is installed, the whole of Part 2 is three commands, and `just --list` shows every recipe:

```bash
just setup       # step 1
just reproduce   # steps 2 to 24: baseline -> sources -> candidates -> journals -> seeds -> deliver
just check       # lint + format-check + tests, then the nine data invariants
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

**The auxiliary seed pool** answers a different question from the annual files. Brief III.8 makes the registered domain the counting unit, so `foo.com`, `www.foo.com` and `shop.foo.com` are one line in `1998.txt`. That is right for counting and wrong for downloading, since a crawler given `foo.com` never reaches pages that only ever existed at `shop.foo.com`. `ark seed-pool` therefore re-reads each source through the same parser as `ark ingest` and keeps the raw value instead of the canonical one, which is why a seed can never disagree with the evidence it came from. The pool holds **3,595,769 distinct hostnames and URLs** across 2,195,955 registered domains, each labelled with the year its source dates it to.
