# Internet Digital Ark

A reproducible pipeline that collects historical **domain names for 1996-2013**, 1996-2001 first,
each record backed by **item-level, per-year evidence**, and ships them as verifiable additions to a
baseline the reviewer supplies. Built for the Internet Digital Ark research project (Prof. Xiaowei
Ding), it ships two units, registrable domains and the valid hostnames beneath them, scored in
**equivalent-English domains**, where each `(domain, year)` record counts the English page-language
share of its right-most TLD (`foo.uk` 0.9813, `foo.de` 0.1324).

The core rule is structural rather than editorial: **no year without an observation**
(`domain_year.evidence_id` and `hostname_year.evidence_id` are NOT NULL onto `evidence`), checked on
every export.

## Reproduce it

```bash
just setup       # uv sync, once per clone
just reproduce   # every stage, offline, from the raw sources to the shipped files
just check       # lint, format, tests, then the store invariants
```

A delivery archive verifies itself without this repository: `bash verify.sh` inside a fresh
extraction. All three reproduction tiers are in
[docs/round/delivery_readme.md](docs/round/delivery_readme.md), the archive's own README.

## Collect unattended

Collection runs as three walker lanes, one per archive client; the runbook's Collection paragraph
has the command.

```bash
just hold status   # HELD or NOT HELD, one line per name: the job, the flag, each workflow
just hold          # com.ark.sync, pause-platform here and on the VPS, the fleet workflows
```

The hold survives a reboot: only `just hold off [name]` lifts it.

## Take in what the fleet found

```bash
just sync        # hourly under launchd while the laptop is awake, and safe to run by hand
just bank        # what the tick runs when something arrived; --force runs it anyway, never on red
```

`just bank` is the automatic store writer; the runbook's The tick and The bank have each step.

Nothing the fleet downloads bypasses one program:

```bash
uv run python scripts/harness/fetch.py URL --max-bytes 1G --to -   # the only download path
```

## Where the round stands

In `docs/ROUND.md`, written by the bank and `just state` from the claim files. It is generated
and untracked, because the figures move daily and the page names the machine that collects them.

## Where to read next

| | |
|---|---|
| [AGENTS.md](AGENTS.md) | the hard rules |
| [docs/index.md](docs/index.md) | one line per page in `docs/`: what it is and when to read it |
| [docs/ops/runbook.md](docs/ops/runbook.md) | the loop's commands and procedures, in the order a session runs them |
| [docs/report.md](docs/report.md) | the round as the reviewer receives it (generated) |
