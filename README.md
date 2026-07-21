# Internet Digital Ark Project

A reproducible pipeline for collecting historical **domain names for 1996–2001**, where every domain in a yearly file is backed by **item-level, per-year evidence**. For example, a Wayback/CDX timestamp, a dated snapshot, or a WHOIS creation date. It grows an existing ~8.2M-domain baseline, and its output is a **separate, verifiable set of net-new additions** (the baseline is never modified).

> This is a student trial project.

## Requirements

- **[`uv`](https://docs.astral.sh/uv/)** — manages Python, the virtual environment, dependencies, and the lockfile. Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`. Python itself is installed automatically by `uv` (pinned to 3.12 via `.python-version`).
- **Optional: [`just`](https://github.com/casey/just)** - Makefile for python, command runner for the shortcuts below (`brew install just`). Everything also works with plain `uv run`.

## Setup

```bash
uv sync        # create .venv and install the exact locked dependencies
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

## Verify it works

```bash
uv sync
uv run ark --help   # lists the pipeline commands
just check          # lint + format-check + tests, all green
```

## Data

The `legacy-data/` baseline (~1.2 GB) is expected at `./legacy-data/`. It is **git-ignored** (too large for GitHub) so clone the code, then drop the data folder in place.


## Layout

```
├── pyproject.toml          # project metadata, dependencies, tool config
├── uv.lock                 # exact pinned versions (reproducibility)
├── justfile                # task shortcuts
├── .github/workflows/ci.yml
├── src/ark/                # the package (pipeline modules + CLI)
├── tests/                  # pytest suite (network mocked)
├── legacy-data/            # provided baseline, git-ignored (not in repo)
└── docs/                   # task brief and project notes
```
