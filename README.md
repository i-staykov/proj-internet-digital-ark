# Internet Digital Ark

A reproducible pipeline that collects historical **domain names for 1996–2001**, each backed by **item-level, per-year evidence** (an archive capture, a dated index, or a WHOIS creation date). It grows a provided ~8.2M-domain baseline and ships its additions as a **separate, verifiable set**; the baseline is never modified.

> This is a student trial project. See `docs/notes.md` for more details.

## Requirements

[`uv`](https://docs.astral.sh/uv/) only. It installs Python 3.12, the dependencies, and their locked versions. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`, then `uv sync`. Every command below runs under `uv run` with nothing else installed; the optional [`just`](https://github.com/casey/just) wraps the same commands.

## Reproduce the processing

Place the provided baseline in `./legacy-data/` (the six year `.txt` files and the one `.csv`), then run the stages in order:

```bash
uv run ark init            # create the local databases
uv run ark ingest-legacy   # load the baseline read-only (~2 min)
uv run ark legacy-review   # write output/legacy_review/dropped_domains.txt
uv run ark audit           # write the normalization/salvage audit CSV

uv run ark ingest <source> <files...>   # bulk sources that carry a date in the file
uv run ark seed <file> [--limit N]      # year-unlabelled sources -> candidate pool
uv run ark verify [--batch-size N]      # prove candidates year-by-year via the IA CDX API
uv run ark rdap <candidates> [-n N]     # query RDAP -> a per-run journal file (collection only)
uv run ark ingest rdap_snapshot <journal>   # journal -> creation-year evidence, hashed into the ledger

uv run ark gaps                         # list held domains whose missing year is bracketed
uv run ark cdx <domains> [-n N] [--workers N]   # ask IA CDX which years hold a capture -> journal
uv run ark ingest cdx_snapshot <journal>    # journal -> per-year capture evidence

uv run ark export          # write the deliverable (see Structure)
uv run ark stats           # scoreboard: additions on top of the baseline
uv run ark check           # integrity gate: fails (non-zero) if any invariant is violated

bash scripts/package_delivery.sh   # assemble the delivery archive (tar.gz + SHA256)
```

Every stage is re-runnable and resumable: re-running skips work already done, so an interrupted run is finished by running it again. Each run appends to a log in `data/logs/`. Run `uv run ark --help` for all commands and their arguments.

**Or with `just`.** If [`just`](https://github.com/casey/just) is installed, every command above has a named recipe, so the order is harder to get wrong. `just --list` shows them all. The whole result rebuilds from an empty store with no network access:

```bash
just setup       # uv sync
just reproduce   # baseline -> sources -> candidates -> journals -> deliver
just check       # lint + format-check + tests, then the nine data invariants
```

`just reproduce` chains the five stages (`baseline`, `sources`, `candidates`, `journals`, `deliver`), each runnable on its own. Two names deserve their spelling: `just check-data` runs `ark check`, which validates the **data**, and `just verify-repo` runs lint, format-check and tests, which validate the **code**. Calling either one plain `check` invites running one and believing the other passed, so `just check` runs both.

The two network stages (`ark rdap`, `ark cdx`) write a per-run **journal** and no evidence, then an `ingest` step turns journals into evidence. They therefore never hold the store's single write lock, so a long `ark cdx` pass runs for hours alongside other work. `ark cdx` sends one collapsed query per domain covering all six years, paced by a governor that eases up while the service is healthy and backs off on 429/503/504 honouring `Retry-After`; concurrency is the throughput lever because a wildcard CDX query costs about 20 seconds. A practical long run looks like:

```bash
uv run ark gaps                                              # -> data/raw/cdx/gap_candidates.txt
for i in $(seq 1 12); do
  uv run ark cdx data/raw/cdx/gap_candidates.txt -n 5000 --workers 24
done
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz
```

One maintenance script sits outside the pipeline, for stores built before 2026-07-25 only:

```bash
uv run python scripts/restrict_whois_creation_to_creation_year.py rdap          # dry run, reports what it would delete
uv run python scripts/restrict_whois_creation_to_creation_year.py rdap --apply  # delete
```

It prunes WHOIS/RDAP evidence down to the creation year, the one year such a record attests (brief III.6). `ark rdap` has enforced that rule since 2026-07-25, so a store built with the current code needs no migration. See the 2026-07-25 entry in [docs/notes.md](docs/notes.md).

External bulk sources are downloaded into `data/raw/` first. For example, the Internet Archive Early Web CDX dataset (the first `ingest` source, `early_web`):

```bash
uvx --from internetarchive ia download early-web_cdx-lang-cdxa \
    --glob='*.cdx.gz' --destdir=data/raw/early_web --no-directories
uv run ark ingest early_web data/raw/early_web/*.cdx.gz
```

**Reproducibility.** `uv.lock` pins exact dependency versions and the Public Suffix List is vendored in the repo, so canonicalization and the baseline processing are deterministic on any machine; only the live-archive queries depend on network state. `uv run` is the contract (works with only `uv` installed); CI runs lint, format-check, and tests on every push.

## Structure

The repo holds code and docs only; all data stays out of git. `output/` is the generated deliverable — git-ignored and regenerable via `ark export`, shipped in the delivery archive.

```
output/          # git-ignored, regenerable via `ark export`; shipped in the archive
├── netnew/                    # the additions: one file per year (1996..2001)
│   └── evidence_manifest.csv  # every addition traced to its evidence (+ a Wayback link)
├── candidate_unverified.txt   # domains awaiting per-year evidence
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
