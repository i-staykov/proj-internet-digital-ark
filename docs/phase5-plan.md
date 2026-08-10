# Phase 5: the plan, in your terms

Written 2026-08-10, for you rather than for an agent. The agent's version is
[phase5-handoff.md](phase5-handoff.md) and it is long on purpose; this one is meant to be read once and
kept in your head. If the two disagree, this one is the intent and that one is the detail.

---

## 1. Where you stand right now

Phase 4 was **accepted in full**. Not "mostly", not "with corrections": the reviewer merged exactly what
you sent, line for line, and added nothing of his own. That is verified from his files rather than taken
from his email, and it is worth knowing because it means your evidence rules survived contact with
someone checking them.

| | |
|---|---|
| His corpus now | **11,362,034** pairs, **6,226,386.4245** equivalent-English, released as `merged260810` |
| What phase 4 added | 946,266 records, 684,523 domains, 76,538 of them new to all six years |
| Growth he credited | **+10.730988%** |
| Phase 5 so far | **46,952 pairs, 19,522.38 EE, 0.3135%**, and 42,299 of those pairs arrived by accident (see below) |

That splits two ways, and the second half is a story worth knowing.

**4,653 pairs at mean weight 0.9813** are what the two collectors produced after the phase-4 archive was
cut. All `.uk`, the highest-value material in the scoring table. The VPS is still running and has **nine
days** left on its deadline.

**42,299 pairs at mean weight 0.3536 turned up by accident**, and they matter more than their weight
suggests. `just sources` had been aborting at stage 2 on a 47 GB file we deliberately deleted, so that
stage had not run end to end for days. Fixing it made the stage complete, and its glob then swept up
**496 per-TLD Network Wizards survey shards that had been sitting on disk since 5 August, downloaded and
never ingested.** They land almost entirely in **1996 and 1997**, which grew 0.7001% and 1.4313% against
their own baselines, against 0.0042% to 0.1700% for the other four years. Those are the two years the
Internet Archive cannot supply in bulk: only 5.4% of 1996 pairs and 12.6% of 1997 pairs have an in-year
capture at all.

Everything is verified: his own calculator agrees to 0.0000, rejects none of the 46,952, and finds none
already in his merged files. The nine invariants pass.

**The general lesson is the one to carry into the round.** Ding asked us to find "unprocessed files,
failed parses, truncated runs". 496 downloaded files no ingest had ever read is the purest instance of
that, and every measurement taken this round was blind to it, because they all start from the store. So
the first check a discovery harness should run is not a search: it is a **diff of what is on disk against
what the ingest ledger has read.** Free, offline, and it just paid for itself.

## 2. What he actually asked for, and why it is a different kind of round

His words: this is "an intelligent scientific discovery and knowledge discovery problem, not merely an
ordinary downloading task." He wants "automated analysis, association inference, multi-source clue
mining, automated search engines, automated DeepResearch engines", and the objective is to "keep
generating new hypotheses, test them against dated evidence, and continuously expand coverage."

Read plainly, the previous four rounds were you finding a source, measuring it, and writing a collector.
He is asking for the **finding and the measuring to be automated**, with your evidence rules as the
thing that makes an automated proposal safe to act on. That is the round. Everything in
`docs/discovery.md` already exists; what does not exist is anything that runs it on a loop.

He also gave five concrete priorities, and the first one is where the cheap points are:

1. **What remains unexhausted inside sources you already use.** Unprocessed files, failed parses,
   truncated runs, unqueried candidates, missing date partitions, low-recall extraction.
2. Automated discovery of new corpora.
3. **Association and graph inference**: organisations, email addresses, hostnames, aliases, redirects,
   neighbouring records, ownership, archived outbound links.
4. **Track new domains separately from filled years.** He wants both visible.
5. Keep favouring English-language material, per the metric.

**No target was set this round.** He said "perhaps 10%" once, in July, and you returned 10.73%. I have
deliberately removed the code that assumed 10% was still the goal, because after the baseline grew it
would have quietly aimed at a tenth of a bigger number that nobody asked for.

## 3. The three things worth doing first, and why

These are ranked by measured value per hour of your attention, not by how interesting they are.

### First: the RDAP pool, because it is already priced and needs no new idea

**~1.54 million candidate names have never been asked**, worth roughly **82,700 equivalent-English**,
which is about **1.3 points** against the new baseline. The rate improved 90-fold on 8 August when the
queries went straight to the registries instead of through a redirector: 75 queries a second with no
refusals, against 0.83 and 18.8% refused. It competes with nothing the archive engines do, so it is free
capacity.

The honest caveat, and it is the reason this is not simply "run it and collect 1.3 points": the yield
decays down the list, because the list is ordered by how many sources saw a name. `.com` returned 19.2%
over its first 100,000 queries, then 11.4%, then 8.4%. **The decay ends the sweep, not exhaustion.** So
the real question is where the crossover sits between the RDAP tail and the archive queue's head, and
that is a measurement rather than a guess.

### Second: recall over bytes you have already paid for

The Usenet download is **finished**: 19,231 of 19,233 groups are on disk. There is no more corpus to
buy. But two re-reads of the same bytes returned 62,820 and 28,460 equivalent-English respectively, with
no request sent, because the original extractor could not see what was there. The pattern is the whole
lesson of the round: **before writing a source off, check what the parser actually reads.**

What is left on that theme, in order of confidence:

- **The download is finished and nothing is unread.** Audited today: 19,231 of the catalogue's 19,233
  archives are on disk, all 19,231 processed, every one matching its catalogue size to the byte, and the
  two missing groups are unfetchable (HTTP 500 and 502 for `alt.irc` and `alt.music.oasis`). What is
  unmeasured is **yield attribution**: the newest whole-corpus measurement covered 1,706 archives, so
  **17,525 have never been priced.** Close that before deciding where to widen an extractor. No network.
- **`alt.*` is 79% of the groups and 57% of the bytes, fully processed, entirely unpriced.** I told you
  earlier it was 14,910 groups still to work. That was wrong and the audit caught it: those figures were
  the *remainder unprocessed on 1 August*, and they reproduce exactly from the ingest log. Nothing to
  fetch, nothing to crawl, and the largest open question about the corpus.
- **Two seams have small, precise coverage gaps.** The header and first address passes each covered
  19,083 archives rather than 19,231, because a 148-archive batch landed between them. The bare-host pass
  enumerated all 19,231 but **only 9,759 produced a single row**, which matters before extrapolating from
  a sample of it.
- **Four directories hold downloaded bytes that nothing in the tree reads.** The best of them is a
  National Library of Australia title index, with its schema documented beside it, that no file in the
  repository even mentions. `.au` carries the highest English weight of any TLD at 0.9904. The ISC
  survey shards above were a fifth entry on this list until this afternoon, which is the argument for
  taking the rest of it seriously.

Be careful of one trap here, because it has bitten twice: the header seams look like this shape and are
**closed**. Measured over the whole corpus they returned 1,038 EE, and `Path:` about 30, because 7.1
million relay hops are only 4,736 distinct domains and a heavily-crawled baseline already holds all of
them. **A source that selects for authority cannot be net-new, however large it is.**

### Third: attrition.org, which needs a decision from you and not work

A web defacement mirror, 1999-2001, where each row is a date and a hostname, and a defaced host is a
host that was serving that day. **6,458 net-new pairs, 3,174.08 equivalent-English, measured**, and all
33 index files are already on disk. The blocker is that the licence is `CC-BY-NC-SA` and "NonCommercial"
is a real question for paid work. That is your call, or Ding's, and it is worth ten minutes because the
work is already done.

## 4. What I would not do

- **Do not chase more national web archives.** Australia works and is redundant with the Internet
  Archive at zero AWA-only pairs; New Zealand, Canada and Ireland all postdate the window; the UK
  service is offline. All recorded with proofs.
- **Do not scale the mailing lists.** Per message they yield a fifth of what the Enron corpus does, and
  most of the family is unreachable.
- **Do not extend the Usenet header seams.** See above.
- **Do not re-download the 47 GB Arquivo index** unless Ding asks to re-derive that source from scratch.
  Its evidence is in the store; the input file was reclaimed for disk.

Every one of these is in `docs/sources.md` with the measurement that closed it, which is now the first
thing a discovery agent is told to read.

## 5. What I changed today, in one screen

**The baseline moved**, which was the urgent part. Until it did, every `ark stats` run was silently
re-counting the 946,266 records Ding had already credited. One file names the release
(`src/ark/baseline.py`) and nine consumers follow it.

**The English verification standard is gone from the tree.** He retired it in August; it still had
residue in eleven places including the live ingest loop. The engine is in `legacy/src/language.py`. The
integrity gate is nine invariants now instead of twelve, and three checks in the archive's own
`verify.sh` that had been printing SKIP about folders that no longer ship are removed.

**`just reproduce` works again.** It had been aborting at stage 2 on a file that was deliberately
deleted, which is the reviewer-facing reproduction path. Three missing journal replays added, and a
recipe whose `mode` parameter silently ingested the wrong directory fixed.

**The documentation is now a source of truth rather than a log.** Twelve markdown files went in and
what came out is: the brief (untouched), what he changed since it, every source with what remains in it,
how to price a new source, why the code is shaped as it is, the decision log, and these two plans. The
eight past-round session logs and the eight email drafts are gone from your working tree. Nine facts
that existed **only** in those files were promoted into tracked documents first, including his own
framing for this round, which was in none of them.

**14 GB reclaimed**, no raw data touched. There is another 54 GB available in verified byte-identical
Usenet duplicates whenever you want it, but I left it: you said keep the raw data, and the hashing
should be done deliberately rather than in passing.

## 6. The two questions you asked, answered

**The licence.** A licence is the terms a publisher attaches to their material. attrition.org's mirror
repository is published `CC-BY-NC-SA`: attribute the source, do not use it commercially, share
derivatives on the same terms. The "NonCommercial" clause is what gave the earlier session pause, since
this is paid work.

My reading, and it is a reading rather than legal advice: what we take is **facts**, `(hostname, year)`
pairs. We do not redistribute their pages, their prose, or their selection and arrangement. Facts are
not what copyright protects; attribution is given in `sources.md` and in the report; and every row
carries an evidence URL pointing at the specific mirror entry it came from, which is stronger
attribution than the licence asks for. It contributes 5,816 of 11.4M records.

So I ingested it, as you said, and wrote the position into `docs/sources.md` so it is auditable rather
than assumed. What makes that safe is **reversibility**: the rows carry their own `source_id`, so
`attrition_defacement` can be deleted and the export regenerated in minutes if you or Ding ever want it
gone. If you want a second opinion the narrow question to ask is: does extracting factual records from
an NC-licensed compilation count as commercial use of that compilation.

**The empty directories.** Not a broken run, and nothing was lost. They are empty because a batched
script **moved** their contents into `data/raw/usenet/` on the night of 5 August, and a `mv` out of a
directory updates that directory's mtime, so 23:08, 23:20 and 23:42 are removal times rather than
creation times. They match three of the nine "moving N archives" lines in the batch log to the second,
and that log ends "4175 archives in data/raw/usenet, 4175 marked processed".

Four independent checks confirm it, including one the investigation nearly missed: every archive on
disk matches its catalogue size **to the byte**, so nothing was moved and then truncated. The full
account is in `legacy/docs/retired-data.md`. The directories are inert and safe to delete.

**One thing left for you, and it is new:** `alt.*` is 79% of the Usenet groups and 57% of the bytes,
fully downloaded and fully processed, and its yield has never been measured. That is now the largest
open question about the project's biggest source, and it costs a screening pass over local files rather
than a crawl.

## 7. What to do next, concretely

```bash
just check                          # nine data invariants plus the code gate
uv run ark stats                    # confirm it says merged260810
just engines                        # what the VPS is doing, and whether its journals are home
```

Then read [phase5-handoff.md](phase5-handoff.md) if you are pointing an agent at this, or section 3
above if you are doing it yourself. The handoff opens with the same three priorities, in more detail,
plus the eleven ways this project has previously fooled itself with a number.

One last thing worth saying plainly. The reason phase 4 was accepted line for line is the corroboration
split and the evidence wall, not the volume. Whatever the harness ends up doing, **the thing that must
not move is that a domain reaches an annual file only with per-item evidence for that year.** Automating
the search is the ask; automating the standard down is how a round gets rejected.
