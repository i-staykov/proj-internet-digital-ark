# Handoff, for Ivo

Written 2026-08-18, when the project was paused and prepared for GitHub Copilot.

---

## 1. The number you asked for: 41.0640%

Your cumulative score, reconstructed from Ding's emails as the sum of each accepted round's **net-new
record** percentage against the baseline it was scored against:

| round | accepted records | baseline records | record % |
|---|--:|--:|--:|
| 1 | 1,429,524 | 8,224,963 | 17.3803% |
| 3 | 151,949 | 10,263,632 | 1.4805% |
| 4 | 946,266 | 10,415,768 | 9.0849% |
| 5 | 2,608,322 | 19,883,096 | 13.1183% |
| | | | **41.0640%** |

**The method checks out on round 1**: Ding stated 17.38% himself and this reproduces 17.3803%. One
baseline is derived rather than quoted, `merged260730`, which is 9,654,487 plus the 609,145 records of an
external contributor's round, so that single row carries a little uncertainty and the other three do not.

Reported separately, as you asked: cumulative accepted **equivalent-English is 3,018,005.5168** over
5,136,061 records, which is 24.9895% of the corpus as it now stands. **That percentage is not additive**
and should not be summed with the table above.

## 2. The honest assessment, now that 5% gates every submission

You were right to correct me, and it makes the position worse rather than tighter. I had been arguing for
submitting early and often; with a hard 5% gate that is simply not available.

- the threshold is about **603,855 EE** and we hold **14,359**;
- it **recedes by roughly 54,101 EE a day**, because other contributors are growing the corpus at
  1,082,013 EE a day, measured across three intervals of Ding's own published release totals;
- the engines add about **13,200 EE a day**.

**So the gap widens by roughly 40,901 EE a day and never closes by querying.** This is arithmetic from his
figures, not pessimism about the code. Phase 5 hit 195,779 EE a day, but by landing two bulk dated
corpora, not by running collectors.

**The conclusion is uncomfortable and I want to state it plainly: reaching another submission requires
finding a single bulk source worth roughly 600,000 equivalent-English, and I did not find one.** I
screened seven families on the last day and every one was already closed on a sound measurement. The
register now holds 112 closed families. That is not a claim the space is empty; it is a claim that the
cheap parts of it are.

The one lead I think could plausibly clear the bar is the one that needs your permission: **writing
researchers and archives to ask whether an unpublished early-web crawl or link graph can be shared.**
Published bulk data has been worked hard; unpublished bulk data has not been asked for.

## 3. What is waiting on you

All in `docs/key-decisions.md`, which is the only surface anything asks you from:

1. **`internic_zone`**: one word, `master`, `candidate-only` or `rejected`. Worth 12,150 pairs and
   8,627.7 EE. Nowhere near the gate on its own, but it is banked work sitting behind a decision.
2. **60 found sources**: one word each, candidate pool or fold in directly.
3. **Two permission asks**: bulk Nominet queries, and the outreach above.

## 4. What round 6 is, and why it was not sent

Packaged, verified, and deliberately unsent because 0.118894% is far below the gate.

- **17,733 records / 14,358.9235 EE**, overlap with his baseline **zero**
- **all nine delivery checks pass** inside a fresh extraction, including the five enforcing D1 to D4
- **D3 reconciles 22 of 22**; his own calculator reproduces our figure to the digit
- archive `submissions/phase-6/`, 1.9 GB, sha256 in `MANIFEST.txt`, git-ignored and regenerable

## 5. What I changed in the repository today

**The rules now live in one place.** `.github/copilot-instructions.md` is the standing brief, 120 lines,
and Copilot reads that path automatically. `CLAUDE.md` is now a 16-line pointer at it rather than a second
copy, because two copies of an evidence rule drift and that is the last rule that should.

**Documentation shrank from about 19,000 lines in `docs/` to 7,106.** The 11,941-line decision log,
the source dossiers and a stale phase-5 plan moved to `docs/archive/`, which is there to be grepped and
never read whole.

**One thing I did not do, and you should know it.** I archived the decision log rather than curating it.
Curating 11,941 lines honestly would have meant reading all of it, which is exactly the token cost you
asked me to avoid. Its durable content, the traps that each produced a confident wrong answer, is
distilled into the brief and into `handoff-copilot.md`. Everything else is still there, and git history
holds it regardless.

**Nothing was deleted as dead**, because nothing was: every document is cross-referenced and there are no
orphaned scripts. The bulk was verbosity, not rot.

## 6. Three corrections I owe you from today

I want these on the record because two of them nearly went outward.

1. **"Submit early and often" was wrong**, void as soon as you told me 5% gates every submission.
2. **I claimed bare second-level `.uk` names could not have existed** and put a line on your surface
   telling you to report 13,991 of them in Ding's baseline as impossible. `bl.uk` is the British Library.
   `jet.uk`, `nic.uk` and `nls.uk` are equally real. I withdrew the line entirely rather than soften it.
   Two further filter rules over-caught the same way, one of them flagging `x.com`, so I abandoned the
   idea instead of trying a fourth.
3. **I reported an edge-population advantage of "6x to 8.5x"** which is a hit-rate ratio, not a value
   ratio. The measurement that would settle it returns zero by construction against an already-banked
   journal, so the value ratio is still unknown.

The delivery figures in section 4 are program-generated and cross-checked against Ding's own calculator,
and none of them depend on the three items above.

## 7. Starting Copilot

Point it at the repository and it will pick up `.github/copilot-instructions.md` on its own. If it seems
not to, tell it in the first message: *"Read .github/copilot-instructions.md and handoff-copilot.md before
doing anything."* There is no background machinery to recreate: the collectors are plain shell supervisors
holding their own deadlines, and the agent's loop is just `just cycle`, act on what it flags, then hunt.
