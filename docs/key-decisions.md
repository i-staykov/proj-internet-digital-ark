# Key decisions, open and closed

**What this is.** A two-minute review surface for Ivo. The agent appends here as it works, so a
decision can be reversed while it still matters rather than after the round ships.

**How it differs from the other two logs.** `notes.md` is the full dated reasoning and is append-only
history, 4,200 lines of it. `ROUND.md` is the generated current state. **This file is neither: it is
the short list of things a human might want to overrule.** One entry, one screen at most, and a
pointer to the notes entry that carries the working.

**Reading it.** `OPEN` needs you. `CLOSED` was decided by the agent under a standing rule or a
measurement, and is recorded so you can still object. Newest first within each block.

---

## OPEN

### O-5. `ark seed` is slow for a reason I misdiagnosed, and the real fix is a core write path (2026-08-11)

Batching the insert was right and was not the bottleneck: the same seed still held the write lock for
**33 minutes**. The cost is `_CLASSIFY_SQL`, which runs a correlated `EXISTS` per candidate name against
the **53.9M-row** `evidence` table. That never mattered before because nothing else wanted the store; now
the ingest loop and two collectors do, and a 33-minute writer is a 33-minute outage for every reader.

**Not fixed today, deliberately.** It is the write path every seeding route uses, and choosing between a
semi-join, a pre-materialised baseline-domain set and a temp table wants measuring against the real store
rather than guessing. Meanwhile PANDORA seeding is stopped at 7,843 of 29,432 names, which is safe and
resumable, and costs nothing since it is seed-only with an expectation near zero.

---

## CLOSED

### C-10. The two populations go to two machines, and it supersedes C-6 (2026-08-11)

**Ivo's design, and he is right about the part I had corrected.** The VPS works a pool of **pure
bracketed gaps**: a missing year Y where Y-1 and Y+1 are already held. The local engine works the
**candidate pool**, domains held with no year at all, beside the discovery loop that keeps feeding it.

**Why sorting by TLD English share is correct here and wrong for the other pool**, which is the
sharpening my C-5 note missed. A gap query answers 96.0% to 97.5% of the time and that rate is
effectively flat across TLDs, so with the probability factor near 1 and uniform, expected value
collapses to share times the years one query can fill. The candidate pool is the opposite: its hit rate
runs from 36.9% for a name merely mentioned in Usenet text to 90.6% for a link harvested off an
archived page, so there the share must be multiplied by a *measured* rate or `.au` sorts to the top
again. Same formula, and only one of the two populations lets you drop a factor.

**It also maps onto the two outcomes the reviewer asked to keep separate**, which is a good sign:
a gap hit adds a **pair** and never a domain, so the VPS is the completeness baseline; a pool hit makes
a name **net-new**, so the local engine is the discovery half that he asked to be prioritised. The
machine allocation and the reporting split are now the same distinction.

**Two consequences.** Gap targets change slowly, so the VPS needs a refresh rarely rather than
periodically, which was the weakest part of C-5. And **this supersedes C-6**: the local CDX engine goes
back on, but pointed at the discovery pool rather than at a mixed queue, and driven by the loop.

Implemented as `build_query_queue.py --population gap|pool --out PATH`, so the ranking, the era gate
and the measured multipliers are the ones already in use rather than a second implementation.

### C-9. The report leads with the method; the numbers stay at the top as the result (2026-08-11)

Ivo: "the numbers can still go at the top as the 'result', but the focus should be on the method, the
harness, yes." So the five fields open the report, and the body is about how they were found. Two
sources *closed* on measurement become results rather than omissions, which is what SPEC IX asks for
and what a volume framing cannot express.

### C-8. Go back to `.org`, and to previously unavailable sources generally (2026-08-11)

Ivo: "going back to previously unavailable sources is part of the task and what has repeatedly proved
worth it." Correct, and it is already the documented pattern rather than a new idea: feedback section 4
asks for blocked sources to be revisited, and the register's own best example is the Australian Web
Archive, where one endpoint was dead and the other answered normally once someone checked the second
host. **Standing rule from now on: a source closed on *availability* is a source to re-probe, and only
a source closed on *measurement* stays closed.** The two verdict classes are already distinguishable in
`sources.md`, so the screener can say which kind it hit.

### C-7. Ding's research vision logged, and it is background rather than specification (2026-08-11)

His AI4EconFinance / Internet Digital Ark and Digital Archaeology email to Giesecke is now in
`private/personal-context.md` under its own heading, marked FYI. Ivo: "our task specification comes
from elsewhere", meaning `SPEC.md` as amended. Two things in it do bear on method: temporal fidelity
is the point rather than record count, which is why the per-year rule is the deliverable's core
property; and "AI agents that independently discover hypotheses, collect and synthesize evidence"
describes this round's harness, so the harness is on-vision.

### C-6. Local CDX engine stays off (2026-08-11) [SUPERSEDED BY C-10 THE SAME DAY]

Was O-1. Ivo's call: discovery work matters more than another crawl client on this machine. Recorded so
the agent does not quietly reverse it when the queue looks tempting.

### C-5. VPS is the unattended safety baseline, with its queue refreshed periodically (2026-08-11)

Ivo's rule, adopted: the VPS keeps filling in domain-years unattended as steady output, its candidate
pool is refreshed periodically rather than once, and the refresh happens whenever the VPN is up. Added
as a periodic task.

**One correction to the wording, and it matters because the project has already paid for it.** The
instruction was to sort "by the most promising TLDs in terms of EE". Sorting by TLD English share is
what put `.au` first in the whole queue on a 0.9904 share for zero in-window dates, and spent 1,709
queries on a 97.2%-English TLD for five hits. `build_query_queue.py` already sorts by **expected
equivalent-English per query**, which is the share multiplied by a *measured* hit rate, and that is
the ordering the refresh will keep. Same intent, and the multiplier that stops it going wrong.

### C-4. Current state becomes generated, and the handoff retires (2026-08-11)

`phase5-handoff.md` is a hand-written snapshot of current state, which is the one category of memory
that cannot be hand-written: three of its claims were disproved within a day. State moves to a
generated `ROUND.md` with a guard against hand edits, the handoff moves to `legacy/docs/`.
See notes.md, 2026-08-11.

### C-3. Two sources closed on measurement (2026-08-10)

Linux Software Map: 86 net-new pairs, 37.3 EE after the corroboration split, 94.7% already held. Other
defacement mirrors: no sibling survives on archive.org or GitHub. Both are in the rejected register,
so the screener now catches them.

### C-2. `.gov` and `.mil` excluded from RDAP ranking on a fabrication test (2026-08-10)

182 and 2,624 pool names per dated name, against 0.3 for `.com` and `.uk`. Reported as a warning
rather than enforced, since which TLDs to drop is a judgement.

### C-1. VPS deadline extended to 2026-08-31T12:00Z on a freshly rebuilt shard (2026-08-10)

The old shard predated `merged260810` and 28% of the current best-10,000 head was invisible to it.
