# Internet Digital Ark

## Rule 0: lean, or it is worthless

**These docs are the source of truth as of today. Never write how things were.** Git is the only
history. Verbosity is the enemy of quality: this is research for people with no time, and a longer
text is worth less. Say it once, as short as it can be said, then stop. **Never grow a file:** the
edit that adds a rule deletes the rule it replaces. No restating, no preamble, no AI slop.

**No posterity.** A decision is written as the fact it makes true, never as who made it or when.

---
Rebuild the domains that existed in 1996 to 2001 for Prof. Ding, scored on **equivalent-English (EE)**: each `(domain, year)` counts its TLD's English share. **EE and speed are the PROXY; the deliverable is demonstrated research capability**, and the harness is that research: a measured negative with a reason is a result, and the METHOD outranks the source.

- **Only 1996 to 2001.** Nothing dated outside it is banked or shipped, not even as a candidate; it may be studied. No `www` or bare variant is generated.
- **The annual masters are a WEBSITE-evidence product** (spec XIII). Only an exact-host capture that answered 2xx or 3xx enters `1996.txt`-`2001.txt`: an IA CDX capture, a dated snapshot or web link-graph record, or a custodian's per-host/year web-capture extract. Error captures (4xx, 5xx), DNS, registry, RDAP, WHOIS, mail and Usenet headers and textual mentions are CANDIDATES, scored at the same rate. A candidate needs no approval. Every annual `(name, year)` points at the evidence row that dates it, and nothing is interpolated.
- **Held by him** is the exact name in his files, tested by LC_ALL=C comm. Both tracks ship only valid names, net-new against them. Overlap corroborates a reading, never justifies one; a name of his short of XIII stays his, and a flood of those or a large drop in his release is a question for him, not a find.
- **Nothing ships under the 5% gate.** We may ASK Ding to accept less when the research side carries it; he decides. Where the round stands is in `docs/ROUND.md`.
- **Autonomy.** A lead inside the standing size, terms, robots and class bounds gets its `Decision:` line from the loop and proceeds without approval; its register row and ledger line document it for review with the submission. Outside any bound it parks `pending`. The owner approves a new evidence class, and packages and sends every round; no agent does either. Its size and terms bounds live once in ark-fleet `policy.json` `standing`; robots and class are fixed clauses. A material change to a class's extraction re-opens its `Decision:` line.
- **Asks.** An open ask is an issue labelled `needs-owner`.
- **Price** net-new post-split EE, never gross. A lever under 300 EE per client-hour closes.
- **Registers.** Every source gets one row with a LINK in `docs/registers/sources.md` before ingest, beside the sentence saying what dates one item; a closed row moves to `docs/registers/sources-closed.md`. Every result, hit or miss, replaces its row, so nobody re-tests it.
- **Channel.** Three archive clients at most, all on `web.archive.org/cdx`, two on the laptop and one on the VPS, and no agent queries it. The rest of archive.org is open to a research lane, and no lane pauses a collector. Before the first request to a host, read its terms and whole robots.txt; send an honest User-Agent, honour `Retry-After` and back off on 429, 503 and 504; on throttling, retire a client, never add one.
- **Accounts.** Model work runs only in the harness. Legs run on the primary token; only a PR the owner merges flips ark-fleet `policy.json` `token`.
- **Git.** Any branch but `main` may be pushed; `main` moves only by PR. The fleet's guard merges an improver PR inside the tunable surface; every other PR is merged by the owner or a session the owner names, after review. Treat both repos as PUBLIC: no commit, PR, issue or comment names a machine address, IP, login, token value, local path, mail text or personal context. Nothing carries AI attribution, `private/` never ships, and big data never reaches git.
- **Worktrees.** Several agents share both clones: branch and edit only in your own `git worktree`, and never switch a shared checkout's branch or leave edits in it.
- The hook gate (ruff, format, scan, pytest) on every commit, and ark check after every ingest and before every ship.
- **Files.** A rule lives only here, a measured fact only in `docs/lore/laws.md`. His files stay append-only. Generated files are never hand-edited, the brief in `docs/brief/ding/` and every page `docs/index.md` marks generated among them, and frozen `submissions/` are never edited.
- The provenance Parquet is the evidence authority; DuckDB is an index rebuilt from it.
- **Hunting.** A bulk dated HOSTNAME corpus that meets the XIII standard comes first. One lens per leg, never the same twice running, even when the last one paid; two empty hunts change the method, not the effort.
- **No em or en dashes.**

| before | read |
|---|---|
| pricing, hunting or quoting a figure | [docs/lore/laws.md](docs/lore/laws.md) |
| running anything | [docs/ops/runbook.md](docs/ops/runbook.md) |
| proposing a source or briefing an agent | `just find <term>` over the registers |
| arguing what Ding accepts | [the brief](docs/brief/ding/project-brief.md), then `private/personal-context.md` |
