---
name: package-round
description: Build, verify and freeze a round's delivery archive. The owner runs it; no agent packages or sends a round, and nobody packages by hand.
---

# Package a round

`docs/ops/runbook.md` has the owner's ship procedure;
`docs/round/delivery_readme.md` is the README that ships at the archive root.
The package layout is read from his own package, which ships a `Task_Package_File_Guide.txt`.

```
just ship --help              # the whole chain, printed, nothing run
just ship all <round>         # bank, export, gate, report and .docx, package, verify, mail draft
just ship build <round>       # the middle alone: sync lock, full export, gate, package, verify
just verify delivery          # what a reviewer would check: checksums, pair counts, provenance
```

Rules that bite here:

- Never package by hand. `just ship package` refuses a dirty tree or any export but a full one
  matching the store, correctly.
- Report artifacts are regenerated and committed BEFORE packaging, which `just ship`
  does in that order.
- The round lands in `submissions/<round>/`: what is generated and what is frozen is `CLAUDE.md`,
  Files, and what never ships is `CLAUDE.md`, Git. `.gitignore` keeps the tarball in it out of git.
- The last word on the totals is his own calculator, which `just ship` runs with
  `--verify` (`just ship calculator` runs it alone).

Needs the store and `output/`, so this runs on the main checkout.
