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

1. Intake of merge261016: C's first line, then `just intake` on his 1016 archive, then the
   release literals in `docs/report.template.md:10` and `docs/round/delivery_readme.md:15,60` by
   hand. Until then no round 13 figure is quoted: `ROUND.md` measures against merge261008-3.
2. Issues. Close #329 (done by #332), #321, #334, #331, then #320; #304 (shipped platform
   host-years stay) and #305; fold #287 into #286, close #285 and #303; label #216 backlog.
   ark-fleet: close #214 into #208, close #217; #222 and #223 wait on #221, #215 on #286.

## A. Lean, public (owns justfile, docs/round, scripts/harness, scripts/agents, hooks, sources-closed.md)


## B. Harness (owns ark-fleet, scripts/pricing, standing_rule, the pricer agent and skills)

- On the owner's word: the 1,518 `legacy` rows of ark-fleet `ledger/2026-09.jsonl` go; one
  supervised read.yaml run, then Leg at pace_days 7 (or every lens at weight 0); then the 509
  October closed leads go, the 106 without a register row after #356.

## C. Throughput and packaging (owns intake.py, package_delivery.sh, verify_delivery.sh, extended_export.py, the hostnames ingest, delivery_readme.md)

- The bank folds each source's new journals in one transaction, since a fold costs 4 to 6 s per
  journal whatever its length (hostnames.py:644).
- The extended export reads only new and grown inputs, since a full run rereads all 18,714 when
  one is new.

## D. Collectors and the VM (a fresh session once a peer has ended; owns collector deployment, sync)

- Collection and banking run with the laptop off: the VM, reached over the VPN, runs the walker
  lanes, the hourly bank and store, export and packaging as user services; the fleet stays on
  GitHub Actions, since the VM's terms bar AI agents allocating compute.
- One host list in `local.env` replaces the VPS-specific install and sync; holds work remotely.
- #292 End of Term; #286 re-priced against merge261016 for the owner's ruling.
- Cutover: copy the store, run both for one bank, switch, retire the VPS; AGENTS.md names three
  CDX clients without placing them.
