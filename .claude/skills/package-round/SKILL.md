---
name: package-round
description: Build, verify and freeze a round's delivery archive. Use when a round is ready to send, and never package by hand.
---

# Package a round

`docs/runbook.md` holds the shipping section and what each step should print;
`docs/delivery_readme.md` is the README that ships at the archive root and
`docs/ding/task-package-file-guide.md` is his file guide for what the package must contain.

```
just ship --help              # the whole chain, printed, nothing run
just ship all <round>         # bank, report and .docx, export, gate, package, verify, mail draft
just ship build <round>       # the middle alone: quiesce ingestion, export, gate, package, verify
just verify delivery          # what a reviewer would check: checksums, pair counts, provenance
```

Rules that bite here:

- Never package by hand. `just ship package` refuses a dirty tree or a stale `output/`, correctly,
  and a hand-run `ark export` races the ingest loop.
- Report artifacts are regenerated and committed BEFORE packaging, which `just ship`
  does in that order.
- The round lands in `submissions/<round>/` and is frozen: never edited afterwards, and
  `docs/SPEC.md`, `docs/report.md` and `docs/ROUND.md` are never edited at all.
- `private/` never ships, and the tarball stays out of git.
- The last word on the totals is his own calculator, which `just ship` runs with
  `--verify` (`just ship calculator` runs it alone).

Needs the store and `output/`, so this runs on the main checkout.
