# The working behind the open decisions

**What this is.** Moved out of `docs/key-decisions.md` on 2026-08-20, on Ivo's instruction: that file
had grown to a 280-line essay and the four questions it actually asked were invisible inside it. It is
now a numbered list, and this file holds the measurements the list is standing on.

**Nothing here asks anyone for anything.** Everything that does is in `key-decisions.md`.

---

### The only question that matters now: where do 590,000 equivalent-English come from?

**5% gates every submission** (Ivo, 2026-08-18): we may not send anything below it. That closes the
cadence question I had open here, and it makes the arithmetic brutal rather than merely tight.

- threshold today: **603,854.78 EE**; we hold **14,358.92**.
- the threshold **recedes by about 54,101 EE a day** as other contributors grow the corpus, measured at
  1,082,013 EE/day over the newest interval between his releases.
- our own collection adds about **13,200 EE a day**.
- so the gap **widens by roughly 40,901 EE a day and never closes by querying.** `scripts/submission_cadence.py`.

**Therefore only a bulk dated corpus can produce a submittable round**, something in the order of 600,000
EE at once, which is what phase 5 did at 195,779 EE/day by landing `domain_creation_bulk` and the
Dartmouth capture census. Per-domain archive querying is arithmetically incapable of it. Seven source
families were screened on 2026-08-18 and every one was already closed on a sound measurement, so **there
is no known candidate of that size on the list today.** That is the honest state, and it is the problem
to hand over.

### The one sized lead found on 2026-08-19: the registry route is roughly 40% worked, not finished

`domain_creation_bulk` is the largest source this project holds, 2,165,523 in-window pairs from a
published compilation of 171 million domains. **It was assumed to be spent. Measured, it is not.**

Counted over the 25.9 GB file itself: **84,279,284 `.com` rows, of which 2,100,199 carry a creation date
inside 1996-2001.** The current `.com` zone is roughly 157 million names, so the compilation holds about
**half the namespace**.

**The tempting inference is that a complete compilation holds twice as many in-window creations, and it
had to be tested rather than believed.** The test: draw 2,999 `.com` domains this project already dates
inside the window **on evidence that is not `whois_creation`**, so the sample cannot have come from this
file, and ask how many the file holds.

| | |
|---|--:|
| sampled, dated in window on non-WHOIS evidence | 2,999 |
| present in the compilation at all | **1,187 (39.6%)** |
| of those, carrying an in-window creation date | 656 (55.3% of the 1,187) |

Two things fall out. **The compilation covers the in-window population worse than it covers the
namespace**, 39.6% against about 54%, and **44.7% of the in-window names it does hold now carry a later
creation date**, which is a domain that dropped and was re-registered, and is the mechanism that makes
WHOIS lossy about 1998 in the first place.

**What that is worth, stated as an estimate and not a measurement.** If the uncovered part of the current
`.com` zone carries in-window creations at anything like the density of the covered part, a complete
current compilation is worth a further **1.8 to 3.1 million `.com` year-pairs, or roughly 1.1 to 2.0
million equivalent-English at weight 0.6321**. That is two to three times the 603,855 EE gate. The range
is wide because it turns on how much of the 39.6% shortfall is names that no longer exist anywhere, which
no current compilation can recover, against names simply absent from this publisher's crawl.

**THAT ESTIMATE WAS TESTED THE NEXT HOUR AND IS ROUGHLY HALVED. Read the correction, not the paragraph
above.** The paragraph names its own weak point, that the shortfall might be dead domains, and then
prices the lead without settling it. It is left standing rather than edited so the correction is legible.

**The test.** The compilation is of domains that exist **now**. A 1998 domain that dropped and was never
re-registered is absent from it and would be absent from **any** current compilation, a complete zone
file included. So the missing 1,813 names were asked of Verisign's RDAP service, which is the registry's
own answer, against a control of 100 names known to be in the compilation.

| | decided | registered today |
|---|--:|--:|
| **control**, names known to be in the compilation | 100 | **98.0%** |
| **test**, names missing from it | 200 | **52.5%** |

The control is what makes this a measurement: at 98% it shows the probe works, so 52.5% is a fact about
the names rather than about the method.

**So 47.5% of the shortfall is dead and unrecoverable by anyone, and 52.5% is real headroom.** Redone on
the measured figures: a complete current compilation would hold 71.3% of the in-window `.com` population
rather than 39.6%, and dating them at the same 55.3% rate would take the share it can date from **21.9%
to about 39.4%, a multiplier of 1.80x** rather than the 2 to 3x assumed. That is **roughly 1.7 million
further in-window `.com` pairs, about 1.06 million equivalent-English gross**.

**Two things about that number that must travel with it.**

**It is gross, not net-new, and this sample cannot measure net-new by construction.** Every domain in it
was drawn from names we already date, so a more complete compilation would corroborate them rather than
add them. What the sample measures is *coverage*. How much of the 1.06 million is new to the store is
unmeasured, and quoting the gross figure as an increment would be the error this project has made before.

**The remaining bias runs against us and its direction is known.** The sample is domains dated on
non-WHOIS evidence, meaning something archived or mentioned them, so they are more prominent than the
average 1998 domain and therefore **more likely to have survived to today**. The true survival rate of
the shortfall is below 52.5%, so 1.80x is an upper bound on the multiplier.

**One genuinely new number falls out, and it bounds all `.com` work rather than just this source.** If
the compilation dates 21.9% of the in-window `.com` population and holds 2,100,199 such rows, that
population is on the order of **9.6 million `.com` domains**, against **6,104,712 `.com` domains the
store already dates**. So `.com` discovery has perhaps 3.5 million domains of headroom in total, about
2.2 million equivalent-English, from every source combined and not from this one. That is the ceiling the
5% gate has to be found inside, and it is the first time this project has had an estimate of it.

**So the ask is concrete rather than a research direction, and it is the first thing found in this round
that could clear 5% on its own.** Three routes, in ascending cost:

1. **A larger published compilation.** The one we hold is a Kaggle deposit and there is no Kaggle account
   on this machine. Others may exist. This costs an account and an afternoon.
2. **ICANN CZDS.** Free zone-file access to `.com`, `.net` and `.org` gives the complete current name
   list, though not creation dates. It needs an account, a stated purpose and registry approval. It would
   settle the estimate above exactly, by telling us how many names the compilation is missing.
3. **Creation dates for the missing names.** This is the part that does not scale: port-43 and RDAP run
   at thousands a day here, and tens of millions of lookups is not a plan. So route 3 only becomes real
   if route 1 finds a compilation that already did the work.

### Route 1 has an answer, and it is a class of source this register has never once considered

**Searched for a larger compilation and found one, commercial.** `whoisxmlapi.com` publishes a WHOIS
Database Download whose own product page states **374 million active domains tracked**, **7,596 TLDs and
ccTLDs**, and lists **creation date** among the per-domain fields. Read off their page on 2026-08-20,
not inferred.

Against the 171 million of the compilation we hold, and a current `.com` zone of roughly 157 million,
that is the "compilation that already did the work" route 1 was defined to look for. On the measured
ceiling above it would be worth up to the full **1.80x multiplier, about 1.7 million further in-window
`.com` pairs and 1.06 million equivalent-English gross**, with net-new unmeasured and certainly lower.

**The reason this is worth writing down even before it is priced is that the whole class is missing from
the register.** `docs/sources.md` holds 112 closed families. A grep for `domaintools`, `whoisxmlapi` and
`securitytrails` across `sources.md` and `approved-sources-list.md` returns **zero**, against a control
grep for `netcraft` in the same two files which returns 2 and 18. So the search works and the absence is
real: **commercial WHOIS data vendors have never been evaluated here at all.** Every registry route this
project has taken has been to a registry or to a free deposit.

**What is NOT established, and was checked rather than assumed.** DomainTools advertises a WHOIS History
product and it is widely said to reach the late 1990s. **Three of their live pages were read and none
states a start year**, so the depth claim is unverified and is not being relied on. It matters because a
*historical* WHOIS archive is categorically better than any current one: it could hold the **47.5% of
in-window names that are dead today**, which the measurement above shows no current compilation can ever
reach. If that product really does reach 1996-1998, it is the most valuable source this project has ever
identified. That is a question for them, not for us.

**The catch is that both are commercial**, so this is a purchase or a research-access grant rather than a
download, and either needs a named person. It is prepared below.

### The compilation is dark over two high-weight namespaces, and that is a smaller separate lead

Counted over the same file: several namespaces are held in bulk with **zero** in-window creation dates,
because their registries do not publish one. Filtered to weight >= 0.5 and 100,000+ rows, the ones that
also plausibly existed in the window are:

| namespace | rows in the file | in-window dates | weight |
|---|--:|--:|--:|
| `com.au` + `au` | 2,166,910 | **0** | 0.9904 |
| `co.za` | 903,228 | **0** | 0.9682 |

Everything else on that list is disqualified by delegation date rather than by policy: `.us` was
locality-only until its 2002 relaunch, bare `.uk` did not open until 2014, and `.io`, `.store`, `.dev`,
`.ai`, `.bond` and the rest are modern gTLDs that could not have existed in the window. **That
disqualification is a registry fact, not a name-shape rule.**

So the honest residue is `.au` and `.co.za`, both at near-1.0 weight. Neither registry publishes bulk
creation dates and `data.gov.au` has nothing (1,466 results for "domain", every one geological or
planning). Worth a probe when the large routes are exhausted; **not worth a night**, since the whole `.au`
namespace was on the order of 200,000 names by 2001 and the store already dates 90,669 of them.

**Nothing here has been fetched and nothing needs deciding tonight.** What is needed is a yes to opening
a Kaggle account and applying to CZDS, both of which are ordinary and neither of which touches the
evidence rules: a registry creation date is already an approved master class under `whois_creation`.

**ANSWERED YES BY IVO, 2026-08-19, on both routes.** Both are now the agent's to execute, with one
boundary that neither the answer nor the mandate moves: **an account and an application are things done
in a person's name.** Where a route needs an identity, a signature or a stated purpose attributed to a
human, the agent prepares it and stops. What was blocked was permission and permission is granted; what
remains blocked on Ivo is only the parts that are literally his to sign. Those are collected under
`## WAITING ON IVO, PREPARED AND READY` below, so a single sitting clears them.

