# The plan

**The one list of open work, stateless: it says what is open now, never what was done. The PR that
finishes a line deletes it.** Rules live in `AGENTS.md`, measured facts in `docs/lore/laws.md`,
round state in `docs/ROUND.md`, owner decisions in `needs-owner` issues; this page repeats none of
them. Nothing else accumulates: no handoff, audit or progress files.

Aim: round 13 by his priorities, new year-resolved 1996 to 2001 sources first, 2002 to 2013 along
the way; every PR net negative unless it adds a capability the round needs.

## How the work runs

- One master and up to three peers, each its own Claude session in its own worktree, base `live`.
  Start them with "Run docs/plan.md as master." and "Run workstream X of docs/plan.md as a peer."
- The master assigns lines by `SendMessage` (peers found with `ListAgents`), reviews each PR with
  one skeptic subagent, gives the owner one batch a day, and writes no feature code. A peer
  replies with the PR link, its +/- lines and what is left.
- A peer edits only its workstream's files and its own section here; one theme per PR. A peer whose
  section is empty ends; new work always starts in a fresh session. Every open issue on both repos
  is a line here or waits on one.
- At most three test-running sessions at once; none heavy during the :05 bank or an intake.

## First (master)

1. Issues, the owner's closes: #321, #334 and #331 (each closes on its last comment); #292 and
   #315 take `needs-owner`; ark-fleet #222 closes into #223.

## A. Lean (owns justfile, docs/round, scripts/harness, scripts/agents, hooks, sources-closed.md, intake.py, package_delivery.sh, verify_delivery.sh, extended_export.py, the hostnames ingest)

- `data/raw/usenet_header_items` keeps its 21 shards in subfolders the pool fold never globs:
  measured whether they banked, then folded or deleted. A fresh session.

## B. Harness (owns ark-fleet, scripts/pricing, standing_rule, the pricer agent and skills)

- The 509 October closed leads go, the 106 without a register row after #356.
- Every reader of a price takes the deciding figure: the dealer lands model-written parts on its
  `_landed` path too, prompts and schemas say deciding EE, tests feed two-part prices (ark-fleet
  #223). After ark-fleet #233.

## D. Collectors and the VM (a fresh session once a peer has ended; owns collector deployment, sync)

- #369: the VM's GitHub login, then `just vm install`.
- #292 and #286 are asks under the gate: 73,184 and 229,638 deciding EE against merge261016.
- The VM carries only what runs continuously; spent raw artifacts and old releases go to Google
  Drive by rclone from the laptop (runbook, Backups), the rest stays on the laptop.
- The owner runs the cutover (runbook, The VM), then retires the VPS.
