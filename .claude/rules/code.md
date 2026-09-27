---
paths:
  - src/ark/**
  - scripts/**
  - tests/**
---

# Changing code

- Why the code has its shape lives in its own docstring or comment: short, human, objective, at the
  density of the file around it. A schema, gate or evidence-class change states its rule in
  `CLAUDE.md` in the same PR.
- Look for the existing tool before writing one; `docs/ops/runbook.md` lists what each command prints.
- The gate is the hook gate in `CLAUDE.md`. Its scan, `uv run python -m ark.hygiene`, catches
  secrets, machine addresses, local paths and dashes, not `private/` text or big data.
- A new acquisition method dates a year only once added to `evidence_types.WEB_METHODS`.
- Run pytest as `uv run pytest -q > "$TMPDIR/pt.log" 2>&1; echo "exit=$?"`, never through a pipe.
- A script that marks work done checks the exit status of the command it wraps.
- An `ark check` invariant is added for a failure it would catch or a property costly to find broken.
- Retiring a module: delete it and its callers, and add one line under `docs/lore/laws.md`, Do not
  rebuild, naming the path and the measured reason.
