# Findings, round 9

Three results from this round that we think transfer to anyone doing this work. The figures are
measured against the store, not projected, and each says what it was measured on. The round's
totals are in `report.md`; failures, yields and next steps are in `experience-summary.md`.

## 1. A server writing its own name is one evidence class, not one source, and it crosses protocols

Last round admitted the `Received: ... by <host>` clause of a dated mailing-list message: the
receiving mail server names itself, about itself, in a transaction it completed. The finding this
round is that the clause is not the point. The **authorship** is. A news server writes `Path:`,
`X-Trace:` and `NNTP-Posting-Host:` about a transaction it completed in exactly the same sense, so
the same reading admits Usenet server headers with no new rule and no new approval class.

That lane paid **350,946 equivalent-English on 736,440 records**, entirely from spool already on
disk. The same clause at two mailing-list archives paid a further 18,999 on 34,134.

**Three exclusions come with it, each costing yield.** The `from` HELO name is chosen by the
sender. The parenthesised reverse-DNS is written by the receiver but was outside the approval. A
`Message-ID` host is stamped by the sending client. None of the three is read.

**Two parsing traps, because both banked fiction before they were caught.** A news server appends
its own verdict to a `Path` element. `.POSTED` marks the injecting site, and left in place it banks
`news2-win.server.<parent>.posted` as a host in its own right: 2,006 rows in a 35 MB test.
`.MISMATCH` is the server stating that the reverse-DNS did **not** match, so those elements are
dropped rather than cleaned. A further filter removes dial-up lease names, which name a session and
not a machine: an address embedded in the label, a pool word beside a digit, a bare numeric or long
hex first label. It drops 6.5% of candidate hosts against 6.9% expected.

**The side effect worth noting.** 21.9% of this round's hostname records are a `www.` form, against
95.0% last round. Mail relays and news servers are not named `www`, so an evidence class written by
servers reaches names that a crawl of the public web cannot.

## 2. A closure is a measurement about our search, not a fact about the artifact

The Usenet header class had been closed in our own register on 2026-09-08 as "224 GB, on neither
machine any more". Re-measured from the archive's own metadata, the two collections it was priced
on are **15.3 GB**, and 104.8 GB of the same corpus was already on the laptop. The class needed no
fetch at all and became the second-largest lane of the round. The rejection was not wrong about the
policy; it was wrong about a number nobody had re-run.

Two further families closed at 0.0000 were re-probed for the same reason and were also wrong. One
because the inventory page was one link deeper than the sweep had looked. One because an FTP index
was assumed already held, and 31.5% to 64.3% of its hosts were missing at their own year.

So a verdict resting on "we looked and found nothing" is now re-run against the artifact's own
structure rather than against the path we guessed, and every closure records the measurement under
it so that the measurement can be repeated.

## 3. Rank a query queue on what is missing, and plan with the sustained rate

A domain-wide capture query is worth what the years we hold its parent in are worth, not what its
host count is: a capture under a parent we do not hold for that year cannot become a record.
Ranking parents on hosts-we-lack times years-we-hold, minus host-years already held, took the
accepted share of one night's sweep from **4.9% to 21%**.

The rate that ranking produces is not a property of the source. The same query, code and two
clients paid about **193,000 equivalent-English per client-hour** on a fresh ranked head and **210
per hour** two nights later, once that head had been walked. Measured over ten hours from a
re-rank, two clients wrote 1,067 MB of journal for 247,042 equivalent-English: **231 per MB, where
the head alone reads 565.** Plan an hour with the sustained figure.

**The caution that goes with it.** Correlating a parent's rank against what it actually banked
gives Spearman **+0.746** over 198 parents, which reads as an exactly inverted ranker and is not:
the head of any ranking is swept first, so re-measuring it measures sweep history. Over the 54
parents swept fresh from a new ranking, the same correlation is **-0.655**. Price a ranker only on
parents it has never been used on.
