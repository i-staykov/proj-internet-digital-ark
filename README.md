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

## Where the round stands

In `docs/ROUND.md`, written by `just state` from the programs that own each figure. It is generated
and untracked, because the figures move daily and the page names the machine that collects them.
This page states no round figure, so it cannot go stale.

## Where to read next

| | |
|---|---|
| [CLAUDE.md](CLAUDE.md) | the standing rules, and the order to work in |
| [docs/index.md](docs/index.md) | one line per page in `docs/`: what it is and when to read it |
| [docs/runbook.md](docs/runbook.md) | every command, what it prints, and how the machines are arranged |
| [docs/report.md](docs/report.md) | the round as the reviewer receives it (generated) |
