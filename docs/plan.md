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

1. Issues, the owner's closes: #321, #334 and #331 (each closes on its last comment); #292 takes
   `needs-owner`; ark-fleet #222 closes into #223.

## A. Lean (owns justfile, docs/round, scripts/harness, scripts/agents, hooks, sources-closed.md, intake.py, package_delivery.sh, verify_delivery.sh, extended_export.py, the hostnames ingest)

- The claim export skips a bank whose evidence ids, domain rows and baseline are unchanged, and
  the ISC reduction is cached per release: 314.5 s per no-op bank, 90 s per bank.
- The snapshot manifest rehashes only entries whose size, mtime_ns or inode moved, and a price
  verifies the stage once: 54.8 s of CPU per exporting bank, 9.76 GB of reads per leg.
- The bank folds only globs whose fingerprint moved, and the hostnames ingest skips an unchanged
  journal by size and mtime_ns before its sha256: 18.3 s and 28 s per bank.
- The ark log file takes INFO, not DEBUG (7.75 MB per bank, 2.4 GB on disk), and `just ship all`
  uploads retention after the mail draft (8,540 s off its path); #315 closes with this line.

## B. Harness (owns ark-fleet, scripts/pricing, standing_rule, the pricer agent and skills)

- The 509 October closed leads go, the 106 without a register row after #356.
- Every reader of a price takes the deciding figure: the dealer lands model-written parts on its
  `_landed` path too, prompts and schemas say deciding EE, tests feed two-part prices (ark-fleet
  #223). After ark-fleet #233.

- The fleet runs on the VM: the runners are user services there, every workflow reads the snapshot
  and journals from the VM's own `data/`, `sync_fleet.sh` and `ARK_VPS` go, the VPS retires after
  the cutover. ark-fleet is rebuilt around that, as simple as it can be on HPI hardware, with one
  short README stating the architecture (what runs where, what moves by PR, how a leg, a read and
  the bank meet) and nothing else restated; ark-fleet #232 closes with that fact. A fresh session.

## D. Collectors and the VM (a fresh session once a peer has ended; owns collector deployment, sync)

- #369: the VM's GitHub login, then `just vm install`.
- #292 and #286 are asks under the gate: 73,184 and 229,638 deciding EE against merge261016.
- The VM carries only what runs continuously; spent raw artifacts and old releases go to Google
  Drive by rclone from the laptop (runbook, Backups), the rest stays on the laptop.
- The owner runs the cutover (runbook, The VM); after ark-fleet #232, retire the VPS and drop
  `ARK_VPS` from `sync_fleet.sh` and the fleet_findings reprice.
