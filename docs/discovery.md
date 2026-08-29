# Finding and pricing a new source

**How to decide whether something is worth ingesting, before spending a night on it.** This is the
discipline the project has actually paid to learn, written down so it does not have to be relearned.
[sources.md](sources.md) is the register of what has been tried; this is the method.

Read this before proposing a source, and read `sources.md`'s rejected table before proposing one that
sounds obvious. Source families that have been evaluated and rejected are all in the register, each with the
measurement that killed it, and rediscovering one is the single most likely way to waste a session.

---

## 1. What a source has to provide

A domain in an annual file is a **claim about a year**, and every claim names the observation that
supports it. So the only question that matters about a candidate source is: **does each item carry
its own date?**

- **Master-eligible evidence** ties one domain to one specific year. Types are `prior_reused`,
  `cdx_timestamp`, `artifact_listing`, `link_source`, `dated_directory`, `whois_creation`
  (`src/ark/evidence_types.py`).
- **Candidate-only evidence** (`link_target`) shows a domain exists but says nothing about when. It
  never produces an annual row. Candidate pools are valuable, and score nothing until dated.
- **No inference, ever.** A capture in 1998 evidences 1998 and nothing else. Do not interpolate
  across years, do not assume continuity, do not date a domain from a page's "last modified".
- Undated lists are **seed-only**. They still have value, since the CDX and RDAP engines can date
  them, but say so plainly instead of counting them as additions.

Two kinds of master evidence behave differently and the difference decides how much scrutiny a source
needs:

| | example | corroboration |
|---|---|---|
| **self-dating** | a capture timestamp, a registry creation date, a dated artifact listing | none needed: the record is authoritative about the year |
| **typed inside a dated artifact** | a hostname a human wrote in a Usenet post, an OCR'd magazine page | **takes the corroboration split**: the pair is admitted only if another source already places that domain in an annual file |

The corroboration split, not the extraction pattern, is the wall that keeps a bad regex out of the
annual files. That is why widening recall over a human-authored corpus is safe and widening it over a
self-dating one is not.

**The trap inside "what dates one item" is not an absent date, it is a date that dates the wrong thing.**
A source with no date at all is easy to refuse. A source carrying a plausible date next to a hostname is
the one that gets ingested and is wrong, so the question has a sharper form: **a per-entity date is not a
per-field date.** Ask what the date attaches to, and refuse it unless it attaches to the observation being
borrowed. Five instances, each found separately before the pattern was named:

- **the dated-dataset fallacy**: a per-entity current-state row, read as dating an address it merely
  carries today
- **MARC 856**: a catalogue record entered in 1998 may have acquired its URL field in 2005, so the
  record's creation date dates the record and not the link
- **a trademark filed on an intent-to-use basis**: evidences an intention, not a live domain, and only a
  use-in-commerce filing with a dated specimen says the site existed
- **Netcraft**: a name printed on a page captured in 1999, where the capture dates the *page* and the
  inference from listing to liveness is the step that failed, measured
- **an OpenPGP key's creation timestamp**: dates the *keypair*, not the email address bound to it, and
  this is the instance that shows the trap survives a machine-written date. Measured over 4,225 binding
  self-signatures in the Debian keyrings on 2026-08-18: 47.6% of user IDs were bound in a **later** year
  than the key was created, median lag two years, and **0% earlier**. So the reading that looks safest,
  a cryptographically signed timestamp, manufactures claims that a domain existed before its address
  was attached, and only ever in that direction. The correct field is the UID binding signature

A useful test: if the source were re-published tomorrow with today's date, would the item's date change?
If yes, the date belongs to the container and not to the observation.

### Three laws about what a corpus can CONTAIN, which retrievability cannot tell you

Each was established by measurement here, and each closed candidates that were retrievable, correctly
dated and worth building on every other test. **They are the questions to ask before fetching**, since
all three are answerable from a source's description alone.

1. **A corpus derived from Internet Archive crawls cannot be net-new against a baseline that is itself
   IA-derived** (2026-08-18, three candidates). The exception is a bulk *projection* of IA holdings,
   which is what `dartmouth_nber_captures` is and why it paid.
2. **A dated artifact that LISTS names proves the artifact's date, not the names' liveness**
   (2026-08-12 on Netcraft, 2026-08-18 on JANET). A byte-volume or request-count filter does not fix
   this when the field is a period **sum**: any host requested twice carries two error pages and clears
   any threshold set above one.
3. **A corpus assembled by a TRUST decision selects for authorities, not for hosts** (2026-08-18).
   Certificate bundles hold CAs, `Path:` headers hold relays, keyrings hold maintainers, and academic
   papers cite universities. 7.1M Usenet relay hops collapsed to 4,736 domains; 126 in-window
   certificates yielded 17 host tokens, every one a CA's own domain. The tell is that the population
   is *selected* rather than *sampled*, and a selected population is small however large the file is.

### The density ceiling, and the thing it is actually a property of

**A dated prose corpus yields about 0.042 net-new post-split pairs per item.** Measured twice
independently: the closed RFC row at 0.0416 (140 pairs over 3,367 items) and a full census of D-Lib
Magazine at 0.0420 (16 over 381). So clearing the 5,000-pair bar needs roughly **119,000 items**, and
that single number screens a prose lead before any fetch.

**But it is a property of SUBJECT MATTER, not of prose, and that was measured on 2026-08-18.** Both
corpora that established it are prose *about the internet*. Government grant records cleared the item
count decisively, 456,700 dated in-window items across NIH, NSF and CORDIS, 3.8x what the ceiling
demands, and died anyway. Broken out by NSF directorate:

| population | pairs per item |
|---|--:|
| NSF CSE (computing) | 0.0471 |
| NSF BIO | 0.0152 |
| NSF GEO, TIP | 0.0000 |
| NIH, biomedical | **0.0012** |

NIH sits 35x below the ceiling with **164 distinct hostnames in 372,444 abstracts**. And the closing
arithmetic is almost too neat: CSE, the one sub-population that reaches the ceiling, holds about 4,984
in-window items, against the 4,997 of the largest scholarly corpus the ceiling was derived to reject.

**So use the ceiling to screen, and ask what the corpus is ABOUT before trusting it.** A corpus of a
million items about molecular biology names no web sites at all.

A second mechanism closed the same day and is worth keeping beside it. Newswire prose fails for a
different reason: **a wire story names a company's web site only once the company is famous enough to
be in the story.** Measured on 8,010 in-window Reuters, UPI and Newsbytes stories already on disk: 305
pairs, **all 305 already held, zero net-new**, with only 4.79% of stories naming any domain and the
ones they name being `reuters.com`, `microsoft.com`, `aol.com`, `apple.com`, `amazon.com`,
`yahoo.com`. That is promotion-selection, the sibling of law 3's authority-selection.

### The split is not a novelty check, and here is what gets through it, measured

The corroboration split asks only whether a domain is dated in *some* annual file, never whether the
mention was genuine. Hand-auditing 25 post-split survivors across three scholarly corpora on
2026-08-18 found **13 genuine (52%)** and three distinct failure mechanisms, only one of which is what
RFC 2606 was about:

- **author-invented placeholders**, 2 of 25: `bigstate.edu` from an invented URN example, `foo.edu`
  from a `host1`/`host2` pair
- **transcription artefacts**, 3 of 25: `ich.edu` from a line break inside `umich.edu`, and `nctu.edu`
  and `tku.edu` from truncated `.edu.tw` names
- **modern retrofits injected into period-dated records** by the publisher or the server, 7 of 25:
  `creativecommons.org` five times, `arxiv.org` and `description.org`
- **a current-state contact field refreshed under a frozen date**, found 2026-08-18 on NSF award
  records and the fourth mechanism rather than a variant of the third. The award's start date is
  genuinely frozen at award time, but `piEmail` is the principal investigator's address **as of the
  last edit**, so a 1997 award can carry a 2015 mailbox. The tell was `gmail.com` appearing 61 times
  on 1996-2001 awards, and 42 of 58 hand-audited survivors carried a registry creation date **after**
  the year claimed. **Assume any per-entity contact or homepage column is undated until someone
  produces a per-field date for it**

**53.1% of the equivalent-English was junk, and the junk concentrates in the highest-weight TLD**,
`.edu` at 0.9717, so this class biases a reported figure upward every time. Hand-audit the survivors
of any typed corpus before quoting its equivalent-English, and count the three mechanisms separately:
a retrofit is a defect in the *container* and is fixable by stripping boilerplate, while an invented
placeholder is not fixable at all.

## 2. The acceptance bar, which since 2026-08-18 ranks rather than vetoes

**Point 1 is a gate and points 2 and 3 are a sort order.** That is a change, and it is Ivo's, made on
2026-08-18 when the scoring rules arrived: *"take everything we can find which fulfills our evidentiary
standard, while of course still prioritizing higher yield/higher quantity and especially higher speed
sources."* The reasoning is in `CLAUDE.md` under **Method, and when to change it**: the corpus denominator is growing about
82 times faster than we collect, so the cost of refusing a small valid source now exceeds the cost of
building its collector.

1. **Per-item year evidence**, as above. Anything else is seed-only. **This is still a veto**, and no
   deadline touches it.
2. **Net-new `(domain, year)` pairs.** ~5,000 was the old floor and is now the point above which a
   source jumps the queue. A measured 300 is worth having; it is simply worth having later.
3. **A mean equivalent-English weight that pays.** Report the measured mean weight of the **net-new**
   part, not of the source. At or above 0.6 is good, below about 0.4 the volume has to carry it, and
   either way the figure now decides *order* rather than admission.

Add a fourth consideration that the old bar had no reason to name: **time to first pair.** A source
that can be collected this afternoon outranks a larger one that needs a week of parser work, because a
week costs 38.5% of the credit on everything held back. Prefer a bulk download to a crawl, an existing
parser to a new one, and bytes already on disk to either.

**What has not relaxed at all.** A master-eligible class still may not date a year until a human has
written its `Decision:` line, and `ark ingest` still refuses one that has not. Candidate-only evidence
needs no approval and never did, so under the new posture the fast move on most finds is to ingest them
as candidates immediately and raise the master question separately.

Never present an unmeasured source as measured, and never pad a list to reach a count. Ranking three
honest findings beats reporting five with two guesses in them.

## 3. The pattern that has actually worked

Every large win this project has had is the same shape: **a corpus where each item carries its own
date and mentions hostnames.**

| source | the dated artifact | domains added |
|---|---|---|
| `usenet_announce` | a Usenet post's own posting date | 335,504 |
| `early_web_cdx` | Internet Archive capture timestamps | 2,160,814 |
| `isc_survey` | dated DNS survey editions | 1,314,476 |
| `rdap_snapshot` | the registry's own creation date | 48,394 pairs |
| `uucp_map_registry` | a registry dump with publication and approval dates | 28,471 pairs |
| `page_directory` | an archived directory page's capture date | 5,220 |
| `tucows_catalogue` | dated software catalogue pages | 3,464 |

The corollary is the fastest filter available: if you cannot say in one sentence what dates an
individual item, the source is seed-only and the conversation is over.

## 4. Measure before ingesting, and measure against the store

**The standing rule is to measure the yield against the live store before ingesting anything.** It is
not caution for its own sake. Three of five sources assessed in one day were rejected after
measurement contradicted the estimate, two of them by two orders of magnitude, and one of those
measurements avoided a 19.35 GB download in two minutes.

Four ways this project has got a projection wrong, all recorded in the git log because each
cost real hours:

- **Wrong counting unit.** The NYPW index was estimated at 27,276 net-new domains and measured at
  **53**. The estimate compared registered domains against raw hostname lines.
- **Linear extrapolation over a corpus that repeats itself.** A 120-archive pilot projected 1.9M
  equivalent-English against a true 62,821. A sample of 0.58% of a self-repeating corpus proves the
  shape, never the total. Fit the saturation curve as well as the line, and quote the lower one.
- **A snapshot that went stale mid-run.** A header projection said ~10,889 EE and delivered 1,038.4,
  because it was measured against a store export from three hours earlier and another ingest had
  written 102,577 overlapping pairs in between. **A snapshot is valid only until the next ingest.**
  Re-export after any ingest, or open the store read-only and measure against it.
- **Quoting the pre-split number.** A raw recovered set of 2,440,926 pairs admitted 107,304 after the
  corroboration split. Quoting the raw figure would have overstated the source 24-fold. **Always
  quote the post-split number.**

**What actually predicts net-new is how long the domain lived, not how obscure it was.** Three sources
measured on the same store settle it, and they disagree with the obvious story:

| source | what it names | net-new |
|---|---|--:|
| UDRP dispute dockets | a name someone sued over, often a typosquat withdrawn within weeks | **87.7%** |
| a spam archive | a name advertised by email, which leaves no crawlable link | 33% |
| `net-happenings` | a name announced in a promotion feed | **2%** |

The middle row is the informative one. Spam was proposed here on the reasoning that email creates no
crawlable trail, so its domains should escape a capture-derived baseline; two thirds of them did not
escape it. A domain that trades for months gets captured whatever channel advertised it. **The dockets
win because a typosquat is taken down before a crawler arrives**, not because nobody was promoting it.

So the question to ask of a candidate source is **did the domain die before a crawler arrived**, and
both halves matter. A dot-com deadpool names companies that failed, which passes the lifetime half and
fails the other: a funded startup ran a marketing budget for eighteen months and was captured many times
before it folded. A typosquat withdrawn after a complaint was never captured at all. **Short life is
necessary and not sufficient; what pays is short life plus low traffic**, which is why disputes,
seizures and abandoned registrations pay and celebrated failures do not.

**This is an inference from three net-new percentages, not a measurement of lifetime, and the difference
matters.** We cannot measure how long a domain lived: the store knows only what it captured, so "years
held" is a measure of our own coverage and not of the domain's life. An attempt to validate the rule that
way on 2026-08-15 measured the wrong thing and half-refuted itself, since `attrition_defacement` domains
hold **3.04** years against a store mean of 1.74 while being a source that pays. Treat the rule as a
good prior for ranking candidates and never as a criterion that can reject one on its own.

The sharpest form of that rule, and the one to ask first: **a source whose purpose is to make a site
known cannot contain sites nobody knew.** Announcement feeds, directories, award galleries and
promotion lists all exist to publicise, so anything they name was publicised, so a crawler found it, so
the baseline holds it. `comp.internet.net-happenings`, the daily feed of new internet resources, is the
cleanest measurement of this: **182,081 evidence rows over 165,365 domains, 97.8% of them dated** against
roughly 10% for Usenet mentions generally, and only **2,760 net-new pairs worth 1,819.7 equivalent-English**.
The extraction is excellent and the source is real. **The property that makes it clean is what makes it
redundant**, so improving the parser would change nothing.

One structural finding worth carrying into any new lead: **a source that selects for authority cannot
be net-new, however large it is.** Usenet `Path:` relay hops, institutional link directories and
award galleries all failed the same way. 7.1 million accepted relay hops were only 4,736 distinct
domains, and a CDX-derived baseline already holds every one of them in every year. Ask what
population a source selects for before asking how big it is.

Its sibling, and the cheaper of the two to apply: **a corpus derived from the Internet Archive cannot
be net-new against a baseline that is itself Internet-Archive-derived.** Ask what a source's *upstream*
is before pricing it at all. This closes a whole family in one question rather than one measurement
each: the TREC web collections, Stanford WebBase and Early Web CDX are all downstream of the same
1996-1997 crawls the baseline comes from, and the two of them that were actually measured returned
**0.01% and 0.01% net-new**. It also explains why the Australian Web Archive priced at exactly zero
AWA-only pairs: it is Internet Archive data wearing a different interface. The tell is a dataset
described as "built from a crawl donated by the Internet Archive".

**That rule has one exception and it is the most valuable family we know of, so read it before
applying the rule.** Being IA-derived is fatal when the source is a *re-serving* of captures the
baseline already drew on, and is the opposite of fatal when it is a **different projection of IA's
holdings, delivered in bulk**. The distinction is not about provenance, it is about which constraint
binds: our coverage of the Internet Archive is limited by **our own query rate**, not by IA's
holdings. Measured 2026-08-15: **239,631 domains have ever been asked at CDX** against 2.5M sitting in the
pool, and the two engines clear about **713 requests an hour** between them. Those two numbers move, and
the ratio between them is the argument rather than either figure: at any plausible rate the pool is years
of work, so anything that converts a per-domain question into a file download is worth more than its size
suggests.

So a bulk index that names hosts IA holds, without our having to ask about each one, converts our
scarcest resource into a file download. That is exactly why the UK Web Archive host link graph is the
best-performing shape ever measured here at **90.4%**, against 46.0% pool-wide: it **is** Internet
Archive data, and it pays because a link graph surfaces hosts that IA's own CDX rows do not return as
captured sites. Judge such a source on the English share of what it covers and on whether it can
actually be downloaded, never on its upstream.

Where an estimate is unavoidable, **label it in the same sentence as the number**. Most figures in
this project are measurements, which is exactly what makes an unlabelled projection dangerous.

## 4a. Ask the disk and the store before asking the network

**Three times in two days a question that looked like it needed a fetch was answered for free**, so this
is a step rather than an instinct. Before spending a request on a lead, ask whether 411 GB of Usenet, the
rest of `data/raw/`, or the store itself already contains the answer.

- **Anti-spam blocklists**, 1997-2001. Looked like a fetch. Every in-window list is IP-based, so there was
  nothing to extract, and the domain-bearing version of the idea, spam sightings, was already ingested:
  13 `news.admin.net-abuse.*` groups on disk, **173,526 evidence rows over 168,075 domains**.
- **The domain aftermarket.** Queued as needing archived listing pages and Wayback requests we could not
  spare. `alt.domain-names.forsale`, `.registries`, `.wanted` and `.disputes` are on disk and ingested:
  **36,425 rows over about 32,685 domains**. The population was measurable for nothing, and the
  measurement moved the lead from potential 40 to 22.
- **The CA Domain Registry.** Found as a hunt for archived daily registration lists; it is
  `can.domain.mbox.zip`, already held, carrying 37,578 `Date-Approved:` fields.

The general form: **a question about a population is usually cheaper to answer than a question about a
source.** "Do names of this kind earn years?" can be asked of the store in one query; "does this website
still exist?" costs a request and often answers a worse question. The store also answers honestly about
overlap, which is the number that decides everything here and the one a fetch never tells you.

And the corollary that cost the most: `LIMIT 4` is not a census, a heading is not a schema, and a
maximum index is not a count. Ask the whole file.

## 5. Before proposing a source, check it is not already dead

`sources.md` has a rejected register: each entry names the measurement that closed it and, where one
exists, the condition that would reopen it. It includes several leads that look obvious and are not:
DMOZ pre-2002 dumps (archive.org holds exactly one ODP item, from 2015), IRCache and NLANR proxy
traces (domain squatted, FTP dead, zero archive.org items), the Internet Traffic Archive (the ideal
1996 Berkeley dataset has anonymised URLs), shareware CD-ROM catalogues (archive.org cannot list
inside an ISO, so density costs a full ISO download per item, and the items carry no date metadata),
web rings (a prefix query returns zero because the member lists are query strings off the site root),
and the Australian Web Archive (works, and is redundant with the Internet Archive: zero
AWA-only pairs).

An automated discovery agent will walk straight back into all of these unless it reads that register
first. Reading it is the cheapest step in the process.

## 6. Where this is automated

The generating and the pricing run as code, not by hand: `scripts/discover_cycle.py` proposes,
`scripts/screen_hypothesis.py` kills anything colliding with the closed register above, and
`scripts/price_items.py` measures a sample against the live store before a collector is written.
Sections 1 to 5 are the rules those three apply, which is what makes an unattended proposal safe to
act on. A hypothesis is a source plus a claim about what dates its items, because that is the unit
section 1 can reject cheaply.

## The roster law, measured over 37 hypotheses in one night (2026-08-28)

**Any artifact whose unit is "one organisation per row, with a homepage URL" prices at
0.0069 to 0.1097 net-new post-split equivalent-English per listed domain.** That is the
whole seam, not one artifact: seal rosters, trade-association member lists, exhibitor
databases, comparison-engine store registries, newspaper directories, PICS label
registries, marketplace supplier profiles, ad-network publisher rosters, statutory
tourism registers, broadcast and press registers, charity and school registers, and
government entity registers were each priced separately and each landed in that band.

The arithmetic that follows is why the seam is closed rather than merely thin. At a
median of about 0.05 EE per listed domain, **1,000 EE needs roughly 20,000 listed
domains in one artifact and 5% needs fourteen million.** In-window rosters of that size
do not exist: the largest found all night was COMDEX Fall 2001 at 1,550 exhibitor rows.
This is the same wall as the curated-directory floor of 0.013 to 0.024 net-new pairs per
listed domain, reached from the other side and now with a per-domain figure attached.

**So the screen is the UNIT, and it can be applied before a byte is fetched.** Ask what
one row of the artifact IS. One organisation with a URL is dead on arrival. What is not
dead is a row that is a machine's own observation of a name at an instant: a registry
event, a blocklist entry, a crawl fetch, a mail header, a zone delegation. Those are the
shapes that have paid, and every one of this project's five-figure sources has that
shape.

A corollary worth keeping: **a high fill rate does not rescue a bad unit.** Several of
the 37 passed the held-and-missing-2001 screen at 100% and still died, because passing a
fill screen on 41 pairs is still 41 pairs.

## Three measurements from 2026-08-29

**The fetch-endpoint law. A build recipe names the host it FETCHED FROM, and a host that
serves downloads to a whole operating system's user base is the authority head by
construction, so it is already dated in every year we hold.** Measured on 22 dated
checkouts of the FreeBSD, NetBSD and OpenBSD ports trees: 4,044 distinct third-party
domains, 99.16% held in some year, **94.91% already held at 2001**, and on the
adjacent-year screen only 106 of 3,822 names held at 2000 are missing 2001 (2.77%,
against the population's 61.1% in `.com`). 40.8 net-new post-split EE. The volume
premise was right and the population premise was wrong: the arm's own kill threshold of
3,000 hosts was cleared and did not save it. This is the visitor-log result read from the
other end, and it predicts the same failure for **Debian `watch` files, Gentoo ebuild
`SRC_URI`, CPAN and CTAN mirror lists**. The screen to apply is not the host count but the
expected fraction held AT the artifact's own year, and a distribution's fetch endpoint
sits at 95%. Route worth keeping even though the source died: `gh api
"repos/<o>/<r>/commits?until=<date>T23:59:59Z&per_page=1"` gives the SHA, and
`codeload.github.com/<o>/<r>/tar.gz/<sha>` gives the whole tree at that instant in one
request. Neither `codeload` nor `api.github.com` serves a robots.txt, while `github.com`
forbids the archive paths and the projects' own FTP hosts refuse `*.gz` by extension, so
the API route is the only permitted one and also the cheapest.

**The form-endpoint law, measured on 5 hosts. An archived GET-form lookup site leaves
exactly ONE in-window artifact per endpoint, the bare parameterless CGI**, because period
crawlers followed the `FORM ACTION` as an ordinary link but did not fill the form. That
page renders an error or an empty result and carries zero records. The parameter space
gets crawled only from about 2004, and by then the page renders an index stamped outside
1996-2001, so it is wrong twice over, wrong stamp and wrong population. **So for any
archived lookup form, ask WHEN the parameter space was crawled, not whether captures
exist. A POST form is dead on sight.** Screening it costs one request per candidate:
`archive.org/wayback/available` is an exact-match existence oracle that respects query
strings, verified here against a known positive, a known negative and two absent controls,
so a dead CGI's whole parameter space can be swept without touching `web.archive.org/cdx`.
That is the tool to reach for whenever CDX is metered by another collector. Note that
**`arquivo.pt`, the obvious non-IA CDX substitute, is barred**: its 35,470 B robots.txt
opens with a permissive-looking `User-agent: *` at line 15 whose Disallow block sits at
lines 744-753 and covers `/wayback`, `/cdxj`, `/services` and `/datasets`.

**Store headroom by year is U-shaped and 2000 is the trough.** P(store lacks year given
the domain is held), measured against merged260827 with two independent SQL formulations
agreeing to 4 dp, and the EE that buys per already-held name:

    tld  P(miss99) P(miss00) P(miss01)   EE99   EE00   EE01
    com    0.644     0.340     0.639    0.4071 0.2149 0.4039
    net    0.769     0.531     0.765    0.3484 0.2405 0.3465
    org    0.715     0.470     0.691    0.5077 0.3337 0.4907
    uk     0.769     0.454     0.382    0.7546 0.4455 0.3749
    de     0.457     0.259     0.866    0.0605 0.0343 0.1147
    au     0.637     0.399     0.502    0.6309 0.3952 0.4972
    ca     0.630     0.491     0.606    0.5270 0.4107 0.5069

A **1999**-dated artifact prices at or above a 2001-dated one in every TLD except `.de`,
and for `.uk` it is worth **2.01x** (0.7546 against 0.3749). A 2000-dated artifact is worth
about half either. This is the right screen for an artifact that itself attests the domain
was alive at Y, and it is still the WRONG screen for projecting fillable headroom, where
the adjacent-year rule stands unchanged. Consequence: **re-price every parked artifact
dated 1999, `.uk` first.**

