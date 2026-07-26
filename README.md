# Internet Digital Ark

A reproducible pipeline that collects historical **domain names for 1996-2001**, each backed by **item-level, per-year evidence** (an archive capture, a dated index, or a WHOIS creation date). It grows a provided ~8.2M-domain baseline and ships its additions as a **separate, verifiable set**; the baseline is never modified.

> This is a student trial project. See `docs/notes.md` for more details.

## Requirements

[`uv`](https://docs.astral.sh/uv/) only. It installs Python 3.12, the dependencies, and their locked versions. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`, then `uv sync`. Every command below runs under `uv run` with nothing else installed; the optional [`just`](https://github.com/casey/just) wraps the same commands.

## Reproduce the results

Two separate jobs, and only the first one needs the network:

- **Part 1, get the inputs.** The provided baseline, plus the bulk source files. About 51 GB, so they are fetched rather than shipped.
- **Part 2, rebuild the result.** Deterministic and offline, roughly 10 minutes. This is the part that reproduces the shipped numbers exactly.

Every step below prints what it did, and the expected output is given so a mismatch is visible immediately rather than three steps later. Every step is also re-runnable: work already done is skipped, so an interrupted run is finished by running the same command again. Each run also appends to a log in `data/logs/`.

### Part 1: get the inputs

**The baseline** goes in `./legacy-data/`: the six year files plus `merge_stats_new0714.csv`. Confirm it is the expected one:

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
shasum -a 256 -c data/raw/checksums.sha256
```

**The network journals ship with the delivery** (1.7 MB, in `data/raw/cdx/` and `data/raw/rdap/`). They hold the raw responses of every archive and registry query made, so Part 2 replays both network stages from bytes on disk and needs no network at all. This also means the result does not drift when a live service changes its answer.

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
| 15 | `uv run ark seed data/raw/webbase/hosts.txt` | `lines: 738625`, `new_candidates: 39` |
| 16 | `uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt` | `lines: 1097867`, `new_candidates: 0` |
| 17 | `uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz` | replays every archive query; `files_ingested` equals the number of `cdx_*.jsonl.gz` files present |
| 18 | `uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz` | replays every registry query; `files_ingested` equals the number of `rdap_*.jsonl.gz` files present |
| 18b | the four `ingest expansion_*` commands in `just journals` | replays the section VII page fetches; the curated half adds `year_rows: 1267`, the rest enqueues candidates |
| 19 | `just seeds`, or the five `ark seed-pool` commands it wraps | rebuilds the auxiliary seed pool: `seeds: 3595769` hostnames and URLs over `domains: 2195955` |
| 20 | `uv run ark export` | `source_rows: 14`, one per source that contributed evidence, and one `netnew_<year>` count per year |
| 21 | `uv run ark stats` | the scoreboard, headed by net-new domains and net-new (domain, year) pairs |
| 22 | `uv run ark check` | nine `[PASS]` lines then `ALL PASS`; exits non-zero if any invariant fails |

Steps 6 to 14 are independent of each other, so their order does not matter. Steps 17 and 18 must come after them, because a replayed query is evidence about a domain the bulk sources introduced.

Steps 20 and 21 print the size of the result, which grows every time more evidence is collected, so they are quoted here as shapes rather than as fixed numbers. The check that matters is that they agree with each other: the pair total from step 21 equals the line count of the shipped year files, and step 22 fails if it does not.

```bash
wc -l output/netnew/*.txt   # total equals the net-new pair count printed by ark stats
```

For the archive as delivered that total is **1,308,314 pairs over 463,364 domains**, with `output/netnew/evidence_manifest.csv` naming the evidence behind every one of them.

Then, to assemble the archive that was delivered:

```bash
bash scripts/package_delivery.sh   # tar.gz plus its SHA256; refuses to run on a dirty tree
```

**With `just`.** If [`just`](https://github.com/casey/just) is installed, the whole of Part 2 is five recipes, and `just --list` shows every one:

```bash
just setup       # step 1
just reproduce   # steps 2 to 21: baseline -> sources -> candidates -> journals -> deliver
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

One maintenance script sits outside the pipeline, for stores built before 2026-07-25 only:

```bash
uv run python scripts/restrict_whois_creation_to_creation_year.py rdap          # dry run, reports what it would delete
uv run python scripts/restrict_whois_creation_to_creation_year.py rdap --apply  # delete
```

It prunes WHOIS/RDAP evidence down to the creation year, the one year such a record attests (brief III.6). `ark rdap` has enforced that rule since 2026-07-25, so a store built with the current code needs no migration. See the 2026-07-25 entry in [docs/notes.md](docs/notes.md).

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
└── legacy_review/
    └── dropped_domains.txt    # every excluded baseline line, grouped by reason

data/            # git-ignored: DuckDB store, work queue, downloaded sources (raw/),
                 # audit CSVs (reports/), merged master lists (exports/), logs/
legacy-data/     # git-ignored: the provided baseline, dropped in (not in the repo)
src/ark/         # the pipeline package and the `ark` CLI
tests/           # pytest suite (network mocked)
docs/            # task brief, sources.md (per-source documentation), plan, notes
```

`ark export` writes the net-new additions to `output/netnew/`, the candidate list, and the large **merged master lists** (baseline + additions) to `data/exports/`. All of it is git-ignored and regenerable; the delivery archive is assembled from these outputs.

**The auxiliary seed pool** answers a different question from the annual files. Brief III.8 makes the registered domain the counting unit, so `foo.com`, `www.foo.com` and `shop.foo.com` are one line in `1998.txt`. That is right for counting and wrong for downloading, since a crawler given `foo.com` never reaches pages that only ever existed at `shop.foo.com`. `ark seed-pool` therefore re-reads each source through the same parser as `ark ingest` and keeps the raw value instead of the canonical one, which is why a seed can never disagree with the evidence it came from. The pool holds **3,595,769 distinct hostnames and URLs** across 2,195,955 registered domains, each labelled with the year its source dates it to.
