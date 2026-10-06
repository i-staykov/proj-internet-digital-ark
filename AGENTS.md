# Internet Digital Ark

## Rule 0: lean, or it is worthless

**These docs are the source of truth as of today. Never write how things were.** Git is the only
history. Verbosity is the enemy of quality: this is research for people with no time, and a longer
text is worth less. Say it once, as short as it can be said, then stop. **Never grow a file:** the
edit that adds a rule deletes the rule it replaces. No restating, no preamble, no AI slop.

**No posterity.** A decision is written as the fact it makes true, never as who made it or when.

Rebuild 1996 to 2015's hostnames for Prof. Ding, scored in **equivalent-English (EE)**. **EE and speed are the PROXY; the deliverable is demonstrated research capability**: the harness is that research, a measured negative with a reason is a result, the METHOD outranks the source.

## Hard rules

- **Public.** This repo is public; ark-fleet is private. No commit, PR, issue or comment here names
  a machine address, login, token value, local path, mail text or personal context. Nothing carries
  AI attribution, `private/` never ships, big data never reaches git.
- **Git.** `main` moves only by PR, merged by the owner or, inside the tunable surface, the fleet's
  guard. Work in your own worktree, never switching or editing a shared clone.
- **The owner decides** a new evidence class and packages and sends every round. Asks are
  `needs-owner` issues.
- **The window.** A host-year ships only by its own evidence, as an addition to his file for that
  year, 1996 to 2015: 2002 on in `extended_years/YYYY.txt`. All of it counts toward the gate, 5% of
  his 1996 to 2015 EE; nothing ships under it, and the goal is to reach it fast.
- **Channel.** At most three clients (two laptop, one VPS) query `web.archive.org/cdx`, agents only
  under an owner's contract. Read a host's terms and whole robots.txt first; back off when it asks.
- **Accounts.** Model work runs only in the harness, on the primary token unless an owner-merged PR
  changes ark-fleet `policy.json` `token`.
- **Frozen.** His files are append-only; `submissions/` and generated pages (`docs/index.md` marks
  them) are never hand-edited.
- **Files.** A rule lives only here, a measured fact only in `docs/lore/laws.md`, code's rationale
  in its docstring or comment.
- **Done.** Every commit passes the hook gate (ruff, format, scan, pytest). Only a zero exit marks
  work done. No em or en dashes.

| before | read |
|---|---|
| pricing, hunting, quoting a figure | [docs/lore/laws.md](docs/lore/laws.md) |
| running anything | [docs/ops/runbook.md](docs/ops/runbook.md) |
| proposing a source, briefing an agent | `just find <term>` |
| arguing what Ding accepts | [the brief](docs/brief/ding/project-brief.md), then `private/personal-context.md` |
