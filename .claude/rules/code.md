---
paths:
  - src/ark/**
  - scripts/**
  - tests/**
---

# Changing code

- Why the code is shaped the way it is: `docs/lore/documentation.md`. Schema, gate or evidence-class
  changes need an ADR in `docs/lore/ADRs.md` first.
- Look for the existing tool before writing one; `docs/ops/runbook.md` lists what each command prints.
- The gate is CLAUDE.md rule 2.
- Nothing from `private/` is copied into a tracked file, and big data never reaches git. The
  scan that enforces it is `uv run python -m ark.hygiene`.
- Comments are short, human and objective, and match the density of the file they sit in.
- Retiring a module: one line in `docs/lore/retired.md` naming what, why and the commit.
