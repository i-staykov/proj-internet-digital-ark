# Internet Digital Ark

A reproducible pipeline that collects historical **domain names for 1996-2001**, each
record backed by **item-level, per-year evidence**, and ships them as verifiable
additions to a baseline the reviewer supplies. Built for the Internet Digital Ark
research project (Prof. Xiaowei Ding): autonomous, evidence-led discovery of the early
web, scored in **equivalent-English domains**, where each `(domain, year)` record counts
the English page-language share of its right-most TLD (`foo.uk` 0.9813, `foo.de` 0.1324).

## How it runs

```
GitHub Actions fleet (private repo, self-hosted runner on a small VPS)
   researcher waves, twice daily ... propose, screen, price sources; findings as artifacts
   re-opener, daily ................ re-reads closed verdicts when a measurement screen retires
   weekly digest ................... one page of yield, cost and recommendations
VPS (always on)
   two archive collectors under systemd, querying capture indexes at zero token cost
Laptop (episodic, human-supervised)
   `just bank` ..................... drains fleet findings, admits, ingests into the
                                     evidence store, gates, pushes; packaging and reports
```

The store enforces the core rule structurally: **no year without an observation**
(`domain_year.evidence_id` is NOT NULL onto `evidence`), thirteen invariants checked on
every export, and every source class gated behind a human decision before it may date a
year. Negative results are first-class: the register records every family tried, with
the measurement that closed it.

## The repo in one minute

| | |
|---|---|
| [src/ark/](src/ark/) | the pipeline: ingest, evidence store, checks, export |
| [scripts/](scripts/) | by role: `harness/` (research loop), `engines/` (collectors), `pricing/`, `round/`, `sources/<family>/` |
| [docs/sources.md](docs/sources.md) | the register: every source, every rejection, with measurements |
| [docs/documentation.md](docs/documentation.md) | why the pipeline is shaped this way |
| [docs/operations.md](docs/operations.md) | the full runbook: every command and what it should print |
| [docs/ding/](docs/ding/) | the reviewer's own brief, transcribed verbatim |
| [tests/](tests/) | the suite, including drift tests that pin documentation to code |

## Verify it

```bash
uv sync
uv run ruff check . && uv run pytest -q     # the suite
uv run ark check                            # thirteen store invariants (needs the store)
```

The full reproduction recipe, from raw sources to shipped files, is `just reproduce`;
see [docs/operations.md](docs/operations.md).

## Status

Where the round stands is generated into `docs/ROUND.md` by `just state` (not tracked:
it embeds figures that move daily). Orchestration lives in a separate private repo so
this one stays free of secrets and runner exposure; results land here on the `live`
branch and reach `main` as squash-merged snapshots.
