# The working method

How the project works today. `AGENTS.md` holds the hard rules; each line here holds until a PR that
says why changes it.

- **The research.** The harness is the research: a measured negative with a reason is a result, and
  the METHOD outranks the source. Outside 1996 to 2001 a name is only studied; no `www` or bare
  variant is generated.
- **The annual masters** (spec XIII), `1996.txt`-`2001.txt`, take only exact-host WEBSITE captures
  answering 2xx or 3xx (IA CDX, dated snapshots or web link-graph records, custodians' per-host/year
  web-capture extracts), each `(name, year)` pointing at its dating evidence row, none interpolated.
  Error captures (4xx, 5xx) and other in-window evidence are CANDIDATES, scored alike, needing no
  approval.
- **Held by him** is the exact name in his files (LC_ALL=C comm); both tracks ship net-new against
  it, overlap corroborating a reading, never justifying one. His names short of XIII are his, not
  ours to clean: we add valid names; a flood of them or a large drop in his release is his
  question, not a find.
- **The gate** is `docs/ROUND.md`'s. We may ASK Ding to accept less when the research carries it;
  he decides.
- **Autonomy.** A lead inside the standing bounds (size and terms: ark-fleet `policy.json`
  `standing`; robots and class fixed) gets its `Decision:` line from the loop and proceeds
  unapproved, reviewed with the submission; otherwise it parks `pending`. A material extraction
  change re-opens the line.
- **Price** net-new post-split EE, never gross. A lever under 300 EE per client-hour closes.
- **Registers.** Before ingest a source gets one `docs/registers/sources.md` row with its LINK and
  what dates one item, moved to `docs/registers/sources-closed.md` when closed. Each result, hit or
  miss, replaces its row.
- **Collectors.** Research lanes may use the rest of archive.org, pausing no collector. Send an
  honest User-Agent, honour `Retry-After`, back off on 429, 503 and 504; on throttling retire a
  client, never add one. Collectors run detached to an absolute deadline.
- **Hunting.** A bulk dated HOSTNAME corpus meeting XIII comes first. One lens per leg, never the
  same twice running; two empty hunts change the method, not the effort.
- **Files.** A hard rule lives only in `AGENTS.md`, a method only here, each landing with its code;
  a measured fact only in `docs/lore/laws.md`; code's rationale in its docstring or comment.
  Generated files (`docs/index.md` marks the pages) are never hand-edited. The provenance Parquet
  is the evidence authority, DuckDB its rebuildable index. Local files live only where
  `scripts/agents/brief.py` `LAYOUT` names; the session brief lists anything else, to move or
  delete. `ark check` follows each ingest and precedes each ship.
- **Git.** Push any branch. The owner or an owner-named session merges after review. Once a PR
  merges, its worktree and branch are removed.
- **Writing.** A decision is written as the fact it makes true, never as who made it or when.
  Label an estimate where its number stands; present nothing unmeasured as measured, pad no list
  to a count. No em or en dashes.

| before | read |
|---|---|
| pricing, hunting, quoting a figure | [docs/lore/laws.md](../lore/laws.md) |
| running anything | [docs/ops/runbook.md](runbook.md) |
| proposing a source, briefing an agent | `just find <term>` |
| arguing what Ding accepts | [the brief](../brief/ding/project-brief.md), then `private/personal-context.md` |
