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

### O-4. Report the harness as the result, or the numbers as the result? (2026-08-11)

Ding's last two emails moved from "as exhaustive as possible" to "not about downloading per se, it is
more about Automated Deep Research and Automated Scientific Discovery". So this round's report can
lead with the method and treat equivalent-English as the evidence it works, or lead with the numbers
as before. **Agent's recommendation: lead with the method**, because two of last night's results were
sources *closed* on measurement, which is worth nothing under a volume framing and is exactly what
SPEC IX section 5 asks for. Needs your call before the weekend submission is written.

### O-3. `.org`: go back to a registry that refused us? (2026-08-11)

308,231 unasked pool names at a 0.7101 share, the best in-window rate measured anywhere at 24.9%, and
a real namespace (pool-to-dated ratio 1.09). But that rate rests on **848 answers** before PIR
returned 403 for 9,253 consecutive requests. You said yes to a probe. Agent will run **150 queries at
well under 1 q/s, stopping on the first refusal**, and will not sweep on a green result without
telling you. Flagging it because it is the one action today that touches a service that has already
said no.

### O-2. Is the 1996-2001 corpus intended for publication? (2026-08-11)

Not a technical decision, but it changes what the harness should optimise for. If the corpus becomes
a paper, the discovery log is a methods contribution and worth writing for that audience. Your own
plan says to ask early and to own a citable component. The agent cannot ask; you can.

### O-1. Local CDX engine stays off. Confirmed, kept here as a visible standing choice (2026-08-11)

Ivo: "I would not restart the CDX engine locally again, as we are now doing other more important
things." Recorded as a rule the agent will not quietly reverse when the queue looks tempting.

---

## CLOSED

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
