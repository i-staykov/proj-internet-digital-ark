# The plan

**The one list of open work, stateless: it says what is open now, never what was done. The PR that
finishes a line deletes it.** Rules live in `AGENTS.md`, measured facts in `docs/lore/laws.md`,
round state in `docs/ROUND.md`, owner decisions in `needs-owner` issues; this page repeats none of
them. Nothing else accumulates: no handoff, audit or progress files.

Aim: round 13 by his priorities, 1996 to 2001 first, 2002 to 2013 along the way. The lane's
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

- Asks: #412 a link graph's target side; #393 the terms sentence for the two candidate-grain
  finds; ark-fleet #215 ClueWeb09 whole; ark-fleet #216 the Internet Archive's private 1996 to
  2013 indexes.
- `data/raw/usenet_header_items` keeps its 21 shards in subfolders the pool fold never globs:
  measured whether they banked, then folded or deleted.

## A. Lean (owns justfile, docs/round, scripts/harness, scripts/agents, hooks, sources-closed.md, intake.py, package_delivery.sh, verify_delivery.sh, extended_export.py, the hostnames ingest)

- #394 the VM timer and no launchd job; #395 the justfile at one comment line per recipe; #396 no
  handoff; #397 no page restates another; #402 the VM's posture in one runbook table.
- #398 the suite keeps only the tests that fail when a shipped thing is wrong.
- #405 a gate crossing packages itself, archive and report in one Drive folder.
- #406 the laptop keeps no copy of the VM's data and intake runs on the VM; #407 the log sink
  deletes after 14 days; #408 a ship reruns nothing whose inputs did not move.

## B. Harness (owns ark-fleet, scripts/pricing, standing_rule, the pricer agent and skills)

- ark-fleet #208 the fleet banks store EE within 100 priced legs or is held; #236 the README opens
  with the architecture diagram; #237 no person named, no dead link, no experiments; #223 a ledger
  line's EE from the program's file alone; #253 an improver proposes a change once.
- #399 the fleet user reads two files of the login's clone; #400 no stray runner token; #401 the
  tick says whether its login is alive.

## D. Collectors and the VM (owns collector deployment, sync)

- Throughput, in this order: #409 a 504 costs the lane one request, never a pause; #391 the
  2,211 suffixes under the cutoff; #392 the worker count that measures best; #411 the VM runs
  the Channel's three clients; #390 the done set is every lane's; #410 one CDX question per pool
  domain never asked.
- #292 End of Term banks; #413 its 2008 and 2012 indexes read whole; #286 dated crawl lists bank
  as 2002 to 2013 evidence.
