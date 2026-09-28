# Internet Digital Ark

## Rule 0: lean, or it is worthless

**These docs are the source of truth as of today. Never write how things were.** Git is the only
history. Verbosity is the enemy of quality: this is research for people with no time, and a longer
text is worth less. Say it once, as short as it can be said, then stop. **Never grow a file:** the
edit that adds a rule deletes the rule it replaces. No restating, no preamble, no AI slop.

**No posterity.** A decision is written as the fact it makes true, never as who made it or when.

Rebuild 1996 to 2001's domains for Prof. Ding, scored in **equivalent-English (EE)**. **EE and speed are the PROXY; the deliverable is demonstrated research capability**: the harness is that research, a measured negative with a reason is a result, the METHOD outranks the source.

- **Only 1996 to 2001.** Nothing dated outside it is banked or shipped, only studied; no `www` or bare variant is generated.
- **The annual masters** (spec XIII), `1996.txt`-`2001.txt`, take only an exact-host WEBSITE capture answering 2xx or 3xx (IA CDX, a dated snapshot or web link-graph record, a custodian's per-host/year web-capture extract), each `(name, year)` pointing at its dating evidence row, none interpolated. Error captures (4xx, 5xx) and all other evidence are CANDIDATES, scored alike, needing no approval.
- **Held by him** is the exact name in his files (LC_ALL=C comm); both tracks ship net-new against it, overlap corroborating a reading, never justifying one. His names short of XIII are his, not ours to clean: we add valid names, and a flood of them or a large drop in his release is his question, not a find.
- **Nothing ships under the 5% gate** (`docs/ROUND.md`). We may ASK Ding to accept less when the research side carries it; he decides.
- **Autonomy.** A lead inside the standing bounds (size and terms in ark-fleet `policy.json` `standing`, robots and class fixed) gets its `Decision:` line from the loop and proceeds unapproved, reviewed with the submission; outside any bound it parks `pending`. Materially changing a class's extraction re-opens the line. Only the owner approves a new evidence class and packages and sends a round; open asks are `needs-owner` issues.
- **Price** net-new post-split EE, never gross. A lever under 300 EE per client-hour closes.
- **Registers.** Before ingest a source gets one `docs/registers/sources.md` row with its LINK and what dates one item, moved to `docs/registers/sources-closed.md` when closed. Each result, hit or miss, replaces its row.
- **Channel.** At most three archive clients (two laptop, one VPS), all on `web.archive.org/cdx`; no agent queries it. Research lanes may use the rest of archive.org, pausing no collector. Before a host's first request, read its terms and whole robots.txt; send an honest User-Agent, honour `Retry-After`, back off on 429, 503 and 504; on throttling retire a client, never add one.
- **Accounts.** Model work runs only in the harness, legs on the primary token; only an owner-merged PR flips ark-fleet `policy.json` `token`.
- **Git.** Push any branch but `main`, which moves only by PR. The fleet's guard merges an improver PR inside the tunable surface, the owner or a session he names any other after review. Both repos are PUBLIC: no commit, PR, issue or comment names a machine address, IP, login, token value, local path, mail text or personal context. Nothing carries AI attribution, `private/` never ships, big data never reaches git. Work only in your own `git worktree`, never switching or editing a shared clone.
- **Files.** A rule lives only here, a measured fact only in `docs/lore/laws.md`, code's rationale in its docstring. His files are append-only; generated files, as `docs/index.md` marks them, are never hand-edited, frozen `submissions/` never edited. The provenance Parquet is the evidence authority, DuckDB an index rebuilt from it. The hook gate (ruff, format, scan, pytest) passes every commit, ark check every ingest and ship.
- **Hunting.** A bulk dated HOSTNAME corpus meeting XIII comes first. One lens per leg, never the same twice running; two empty hunts change the method, not the effort.
- **No em or en dashes.**

| before | read |
|---|---|
| pricing, hunting, quoting a figure | [docs/lore/laws.md](docs/lore/laws.md) |
| running anything | [docs/ops/runbook.md](docs/ops/runbook.md) |
| proposing a source, briefing an agent | `just find <term>` |
| arguing what Ding accepts | [the brief](docs/brief/ding/project-brief.md), then `private/personal-context.md` |
