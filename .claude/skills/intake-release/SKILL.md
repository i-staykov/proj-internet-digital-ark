---
name: intake-release
description: Take one reviewer release into the repository: verify its sha256, extract it, recount the year files and point the baseline at the new marker. Use when a new merged corpus arrives.
---

# Take a reviewer release

`docs/releases.md` is the record and says what each column means; `docs/runbook.md` has the
surrounding steps. One command does the work:

```
just intake <his.zip> --dry-run     # says what it would do, writes nothing
just intake <his.zip>
```

With `--mail <file> --round <label> --received '<YYYY-MM-DD HH:MM>'` it also writes the round's
row in `docs/rounds.md`.

What matters while running it:

- Every figure comes from the extracted files, never from his mail. The recount uses his own
  calculator.
- A marker already recorded under a different sha256 stops the run. Do not force it: ask which
  zip is the artifact of record.
- A second run on the same zip changes nothing, so a doubtful run is safe to repeat.
- It does NOT load the release into the store. That stays the separate deliberate
  `uv run ark ingest-legacy` step, which the runbook covers.
- The new baseline moves the denominator, so any EE figure quoted from before the intake is
  stale. Re-run `just brief` before quoting one.

Needs `feedback/` and the store, so it runs on the main checkout, never in a worktree.
