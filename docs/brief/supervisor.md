# For the supervising professor

## The question

Prof. Xiaowei Ding's Internet Digital Ark asks for the hostnames of the web of 1996 to 2013,
1996 to 2001 first, each with item-level evidence for its year. A submission is scored in
equivalent-English (EE): a hostname-year counts as the English share of its top-level domain,
net of what his files already hold. A round ships at 3% EE growth over his files in a window
([the brief](ding/project-brief.md), [the metric](metric-explained.md)).

## The method

The harness is the research. A source is priced against his files before it is hunted; a
measured negative with its reason is a result; the method outranks the source. The pricing
laws are measured facts in [docs/lore/laws.md](../lore/laws.md): a CDX page pays 1,354 EE a
request for 2002 to 2013 and 2.4 for 1996 to 2001; a price against a synced copy of his files
is a ceiling, not a count; a host lane gains nothing past two workers and loses the archive at
four, so throughput is addresses (#585).

## The architecture

Runners collect, the VM thinks, the owner ships. Today and as planned by
[docs/plan.md](../plan.md) and issues #585 to #588:

- Scripted CDX collectors run unattended on a VM; addresses being the bottleneck, scheduled
  runner jobs and free-tier cloud VMs join as runners and upload journals the VM banks.
- A resident agent on the VM reads a yield log, tunes the collectors one lever at a time,
  keeps them alive, merges its own reviewed changes inside rails (`scripts/agents/rails.py`),
  and scouts new sources with fixed, priced lenses.
- A laptop session oversees by pull request; every PR body carries an independent skeptic's
  verdict.
- The owner alone ships rounds.

Guards: a hook gate on every commit (ruff, format, scan, pytest), a leak scan over every
tracked byte (`src/ark/hygiene.py`), a commit identity allowlist, a merge window of :36 to :04
UTC, and token pacing that leaves the owner's share (`scripts/agents/pacer.py`).

## The numbers

As of 2026-11-08; refreshed before presenting. Banked, daily and ceiling figures are the VM
heartbeat's (`scripts/harness/heartbeat.py`); the gates are 3% of his EE in `data/baseline.json`.

- 2002 to 2013: about 3.05M EE banked, about 350k EE a day from one address; gate 9.45M EE.
- 1996 to 2001: about 12.9k EE banked; gate 2.23M EE. The Wayback CDX ceiling for these years
  is about 0.55M EE (#588): 85% of the hosts it returns are in his files. So 1996 to 2001
  needs sources outside Wayback.
- Six non-Wayback sources scouted, each a measured negative under 20 EE
  ([the closed register](../registers/sources-closed.md)).

## The owner's part

Set the research goal and the rules (public repository, rails, the gate), decided every
evidence class, shipped every round.
