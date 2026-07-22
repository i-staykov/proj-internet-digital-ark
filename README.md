# Internet Digital Ark Project

A reproducible pipeline for collecting historical **domain names for 1996–2001**, where every domain in a yearly file is backed by **item-level, per-year evidence**. For example, a Wayback/CDX timestamp, a dated snapshot, or a WHOIS creation date. It grows an existing ~8.2M-domain baseline, and its output is a **separate, verifiable set of net-new additions** (the baseline is never modified).

> This is a student trial project. See `docs/notes.md` for further documentation.

## Requirements

- **[`uv`](https://docs.astral.sh/uv/)** — manages Python, the virtual environment, dependencies, and the lockfile. Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`. Python itself is installed automatically by `uv` (pinned to 3.12 via `.python-version`).
- **Optional: [`just`](https://github.com/casey/just)** - Makefile for python, command runner for the shortcuts below (`brew install just`). Everything also works with plain `uv run`.

## Setup

```bash
uv sync            # create .venv and install the exact locked dependencies
uv run ark init    # create the local databases (data/ark.duckdb + data/queue.sqlite)
```

## Commands

| Task | With `just` | Raw (only `uv` needed) |
|---|---|---|
| Run the CLI | `just run …` | `uv run ark …` |
| Tests | `just test` | `uv run pytest` |
| Lint | `just lint` | `uv run ruff check .` |
| Format | `just fmt` | `uv run ruff format .` |
| Full check | `just check` | `uv run ruff check . && uv run ruff format --check . && uv run pytest` |

The raw `uv run` commands are the **reproducibility contract** (they work with only `uv` installed); `just` is convenience. CI runs the same `check` sequence on every push and PR.

The pipeline runs as ordered stages: `ark seed` → `ark verify` → `ark download` → `ark export`. Run `ark --help` for the full list.

`uv run ark stats` prints the scoreboard at any time: how many domains and (domain, year) pairs have been added on top of the provided baseline, per year, plus the size of the unverified candidate pool.

### Collecting

```bash
uv run ark seed <file> [--limit N]   # canonicalize a seed file, register candidates,
                                     # queue domains the store has never seen
uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt --limit 5000
```

Seeding is idempotent: re-running the same file adds nothing twice, and lines already known (baseline or earlier runs) are skipped. The per-file result is logged as a funnel: `lines / invalid / already_known / new_candidates / enqueued`. Queued domains wait in the crash-safe work queue for `ark verify`.

Every command documents itself: `uv run ark --help` lists all commands, `uv run ark seed --help` shows the arguments of one. Add `-v` before a command (`uv run ark -v seed ...`) for debug logging.

## Verify it works

```bash
uv sync
uv run ark --help   # lists the pipeline commands
just check          # lint + format-check + tests, all green
```

## Data

The `legacy-data/` baseline (~1.2 GB) is expected at `./legacy-data/`. It is **git-ignored** (too large for GitHub) so clone the code, then drop the data folder in place.

Our own results in `output/` **are** committed: they are small and they are the project's work product. Intermediate artifacts (the DuckDB database, downloaded pages) live in the git-ignored `data/`.

# Baseline ingest and review

With `legacy-data/` in place (the `.txt` files and the one `.csv`), load the provided baseline and audit it:

```bash
uv run ark init             # create the local databases
uv run ark ingest-legacy    # canonicalize + load the six year files (~2 min)
uv run ark legacy-review    # write output/legacy_review/dropped_domains.txt (~2 min)
```

Every line passes through one canonicalizer (`src/ark/canonical.py`) that reduces hosts to registered domains using the vendored PSL snapshot plus a documented list of retired ccTLDs (`.yu`, `.an`, ...). Lines that cannot be a registered domain are dropped; `dropped_domains.txt` lists every one of them, grouped by reason, and rerunning the commands above reproduces the file exactly on any machine.


## Layout

```
├── pyproject.toml          # project metadata, dependencies, tool config
├── uv.lock                 # exact pinned versions (reproducibility)
├── justfile                # task shortcuts
├── .github/workflows/ci.yml
├── src/ark/                # the package (pipeline modules + CLI)
├── tests/                  # pytest suite (network mocked)
├── legacy-data/            # provided baseline, git-ignored (not in repo)
├── data/                   # local DuckDB + intermediate artifacts, git-ignored
└── docs/                   # task brief and project notes
```
