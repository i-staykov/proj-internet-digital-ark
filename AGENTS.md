# Internet Digital Ark

Rebuild the domains of 1996 to 2001 for Prof. Ding, scored in equivalent-English (EE). EE is the
proxy; the deliverable is demonstrated research capability.

**Rule 0: lean.** Docs state today's facts, never how things were; git is the only history. Say it
once, as short as it can be said. The edit that adds a rule deletes the one it replaces.

## Hard rules

- **Public.** Write both repos as public. No commit, PR, issue or comment names a machine address,
  login, token value, local path, mail text or personal context, or carries AI attribution.
  `private/` never ships; big data never reaches git.
- **Git.** `main` moves only by PR, merged by the owner or, inside the tunable surface, the fleet's
  guard. Work in your own worktree, never switching or editing a shared clone.
- **The owner decides** a new evidence class and packages and sends every round. Asks are
  `needs-owner` issues.
- **The window.** Nothing dated outside 1996 to 2001 is banked or shipped, and nothing ships under
  the 5% gate.
- **Channel.** At most three clients (two laptop, one VPS) query `web.archive.org/cdx`; no agent
  does. Read a host's terms and whole robots.txt before its first request, and back off when it asks.
- **Accounts.** Model work runs only in the harness, on the primary token unless an owner-merged PR
  changes ark-fleet `policy.json` `token`.
- **Frozen.** His files are append-only; `submissions/` is never edited.
- **Done.** Every commit passes the hook gate (ruff, format, scan, pytest). Only a zero exit marks
  work done.

Everything else is the working method, changed by a PR that says why:
[docs/ops/method.md](docs/ops/method.md).
