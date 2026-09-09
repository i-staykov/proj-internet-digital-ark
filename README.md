# Internet Digital Ark

A reproducible pipeline that collects historical **domain names for 1996-2001**, each record backed
by **item-level, per-year evidence**, and ships them as verifiable additions to a baseline the
reviewer supplies. Built for the Internet Digital Ark research project (Prof. Xiaowei Ding), it
ships two units, registrable domains and the valid hostnames beneath them, scored in
**equivalent-English domains**, where each `(domain, year)` record counts the English page-language
share of its right-most TLD (`foo.uk` 0.9813, `foo.de` 0.1324).

The core rule is structural rather than editorial: **no year without an observation**
(`domain_year.evidence_id` and `hostname_year.evidence_id` are NOT NULL onto `evidence`), checked on
every export, and no source class may date a year until a human has written the decision that admits
it. Negative results are first-class: the register keeps every family tried and the measurement that
closed it.

## Reproduce it

```bash
just setup       # uv sync, once per clone
just reproduce   # every stage, offline, from the raw sources to the shipped files
just check       # lint, format, tests, then the store invariants
```

A delivery archive verifies itself without this repository: `bash verify.sh` inside a fresh
extraction. The other two reproduction tiers, and what each command should print, are in the
runbook.

## Collect unattended

The CDX collectors are the laptop's standing lane, held by launchd under `caffeinate -s`, and
three words steer them:

```bash
just collectors status   # running or paused, the current parent, the last journal, the hit rate
just collectors pause    # before travel or a shutdown: the sweeps stop after the page in flight
just collectors resume   # after it: every parent continues from its own state file
```

The pause is a flag file rather than a signal, so it survives sleep and a reboot, and nothing but
`resume` clears it.

## Take in what the fleet found

```bash
just sync        # hourly under launchd while the laptop is awake, and safe to run by hand
```

The fleet measures; the laptop is the only thing that writes the store. One `just sync` drains the
findings, validates each one against the fleet's schema, prices every confirmed FIND again on the
live store so no figure is booked on a copy, writes the register row with both numbers, decides what
Ivo's standing rule already covers and asks him about the rest, ingests, gates, pushes, refreshes the
pricing snapshot the fleet prices against, and writes each lead's fate back into the fleet's queue.

Nothing the fleet downloads bypasses one program:

```bash
uv run python scripts/harness/fetch.py URL --max-bytes 1G --to -   # the only download path
```

It reads the whole robots.txt of the host in the download URL and refuses a group that names us
wherever in the file it sits, and it reads the next host's rules before following a redirect rather
than after. It honours `Retry-After`, counts the bytes twice against the cap, refuses a body shorter
than the length it was promised, writes only into the run's RAM-backed probe directory or the corpus
directory an approved download names, extracts no archive to disk, and prints the sha256 the finding
has to quote. Anything bigger than the cap, or of a type nobody can read in-stream, waits in the
fleet's download backlog for a decision.

## Where the round stands

In `docs/ROUND.md`, written by `just state` from the programs that own each figure. It is generated
and untracked, because the figures move daily and the page names the machine that collects them.
This page states no round figure, so it cannot go stale.

## Where to read next

| | |
|---|---|
| [CLAUDE.md](CLAUDE.md) | the standing rules, and the order to work in |
| [docs/index.md](docs/index.md) | one line per page in `docs/`: what it is and when to read it |
| [docs/ops/runbook.md](docs/ops/runbook.md) | every command, what it prints, and how the machines are arranged |
| [docs/report.md](docs/report.md) | the round as the reviewer receives it (generated) |
