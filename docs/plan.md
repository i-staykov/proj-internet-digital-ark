# The plan

**The one list of open work, stateless: it says what is open now, never what was done. The PR that
finishes a line deletes it.** Rules live in `AGENTS.md`, measured facts in `docs/lore/laws.md`,
round state in `docs/ROUND.md`, owner decisions in `needs-owner` issues; this page repeats none of
them. Nothing else accumulates: no handoff, audit or progress files.

Aim: round 14 by his priorities, 1996 to 2001 first, 2002 to 2013 along the way. The lane's
queue is at its tail (under one row a page), so the round's EE comes from the lane's idle time,
the pool questions, the unpriced suffixes and whole custodian reads; every PR net negative
unless it adds a capability the round needs.

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

## First (master and owner)

- #467 is ruled and built (#469): close it.
- `data/raw/usenet_header_items` keeps its 21 shards in subfolders the pool fold never globs:
  measured whether they banked, then folded or deleted.

## A. Lean (owns justfile, docs/round, scripts/harness, scripts/agents, hooks, sources-closed.md, intake.py, package_delivery.sh, verify_delivery.sh, extended_export.py, the hostnames ingest)

- #397 no page restates another.
- #406 the laptop keeps no copy of the VM's data and intake runs on the VM.

## B. Harness (owns ark-fleet, scripts/pricing, standing_rule, the pricer agent and skills)

- #393 a candidate-grain find is decided on its candidate figure.
- ark-fleet #208: 56 legs banked 0 EE because its candidate figures were hostname grain (244,532
  headline, 42,116 registrable; fixed by #263 and #444); the one measured annual signal is HTTP
  Archive 2010 to 2013 at candidate grain (price legs 114 to 11,510 decided EE a sample);
  defacement-ledgers parks (20 scouts, 0 leads).

## D. Collectors and the VM (owns collector deployment, sync)

- Throughput: #392 the worker count that measures best.
- Readers: `har_year.py` once finished still runs one search and 158 metadata reads an hour; a
  fetch outage strikes a zip with no back-off, so one outage can give up an item; the walker's
  refusal counter climbs on a 200 cut before its first row.
