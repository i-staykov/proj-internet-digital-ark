# The measured laws of source pricing

**What kills a source before it is downloaded, and what a surviving source is worth.** Every
figure here was measured on this project's own store. A date beside a figure is its measurement
date; a figure without one was current when this page was cut from `CLAUDE.md` on 2026-09-02.
Read this before pricing or proposing a source. [discovery.md](discovery.md) has the long form,
[traps.md](traps.md) the mistakes already paid for, [rules.md](rules.md) the evidence standard.

## The eight laws

1. IA-derived cannot be net-new: the baseline is IA-derived too.
2. Listing a name proves the artifact's date, not that the name was live.
3. A trust-selected corpus holds authorities, not hosts.
4. A current-state snapshot cannot evidence a past year.
5. Human-typed novel names take the split and earn no year.
6. Anonymised or hashed hostnames are worth nothing: ask for the sanitisation paragraph first.
7. Dating and URL-bearing anticorrelate: a record naming a site is one somebody has since edited.
8. Overlap with the baseline corroborates a reading; it never justifies one (Ivo, 2026-08-24).
   The grounds must be what dates the item: the artifact asserting a state at an instant it
   stamps itself, and a capture fixing when it existed. Agreement with `prior_task` is a check
   on that argument, and cited only after it.

## Prose density, and the second screen behind it

Prose density ceiling: ~0.042 net-new pairs per item, so ~119,000 items to clear the bar. Ask
what the corpus is *about* before trusting even that.

**Density and authority are two INDEPENDENT screens and a corpus must pass both.** Formal prose
fails the first: Hansard is 3.26M words per 5 URLs, 0.00153 URLs per 1,000 words. Grey
literature passes it emphatically at **221x that rate** (ERIC, 0.339 per 1,000 words) and then
fails the second at 93.0% already held, because program reports print the URLs of institutions
we already have. Measure BOTH on a sample before pricing any prose corpus, and expect `.edu` and
`.gov` to die to the split: ERIC held 184 `.edu` pairs and exactly one survived.

## Under the split, novelty is a cost

**A list's EE is (domains held AND missing that year) x nothing else.** A novel name earns no
year. But high already-held is only half the test: an IRR dump at 97.6% held paid **4.44 EE**
because 95.2% were held **in that very year**. The screen is *held AND missing this year*.
junkfilter paid 2,189 EE spanning 13 editions 1997-2001; a two-year list over the same
population paid 120. Ask which YEARS an artifact can add to names we already have.

## Compute headroom from the adjacent year only

A gap between a domain's LAST held year and the target is evidence of death, not of missing
data: of 9,680 `.us` names missing 2001, **6,948 were last seen in July 1997**, and only 37.65%
of the names an ISC 1997 walk attests have any 2001 record at all (`.com` from the same file:
40.31%). So "held ANY year, missing Y" is contaminated and "held Y-1, missing Y" is not. Quote
the adjacent figure.

## Aim at 2001, not 1996

Measured headroom: **6,708,320 domains held at 2000 and missing 2001**, worth ~2.92M EE gross
in the top eight TLDs, against **103,953** for the 1996-to-1997 gap. A 64x difference. Thin in
absolute pairs is not the same as fillable. So aim the frozen-mirror rule at media and mirrors
that stopped in **2001-2003**, not the 1990s.

## The 2001 threshold, and it is the screen to use

P(store lacks 2001 | domain held) is `com` 0.611, `net` 0.653, `org` 0.568, `uk` 0.309, `de`
0.841. So one ALREADY-HELD name in a 2001-dated artifact is worth 0.386 EE in `com`, and
**1,000 EE needs only ~2,600 held `com` names** (2,477 `org`, 2,484 `au`, 3,298 `uk`). That is
32x below the 83,000 the curated-directory floor demands, because that floor was measured on
artifacts dated in years already well covered. **A few thousand held names dated 2001 is a
find; the same list dated 1999 is not.**

**That is a population average and does NOT transfer to head-selected corpora.** A 2001
magazine article archive measured **0.041 EE per name**, nine times worse, because a magazine
cites the head of the distribution and we already cover the head at 2001. Head-type artifacts
need ~24,000 names. **The pre-download discriminator is the expected held-fraction**: blocklists
~50%, authority corpora 87-99%, forged-header spam corpora **~5%** (a remailer log was 23,102
names and 4.56% held, since spam sender hostnames are invented). When sampling to check, sample
DISTINCT DOMAINS, not `domain_year` rows: per-row gives P=0.492 against the true per-domain
0.611.

## Crawling kills discovery, not completeness, and the two laws interact

A crawl-fed adversary finds few novel names (only 15% of a squidGuard list is unknown to us), so
it loses on discovery. But if its held names LACK the year it is dated, it wins anyway: the
**2001-12-18** squidGuard blacklist is 84.8% known and only 57.9% held at 2001, so it pays
**10,736 EE**, while the 2000-10-18 edition paid 18 because its names already carried 2000.
**So ask which YEAR the artifact can add before dismissing it for crawling.** Non-crawl channels
still win on discovery: junkfilter 50.4% held, SpamEater 59.1%, a typosquat listing 25.8%.
Visitor logs lose on both, at 98.4% and 99.6%, because the hostname is reverse DNS and the long
tail resolves to its ISP.

## The curated-directory floor

Measured over four artifacts: 0.013 to 0.024 net-new post-split pairs per LISTED domain, at
0.39 to 0.70 EE per pair. So 1,000 EE needs 83,000+ listed domains in one artifact. For a
human-curated list, novelty and datability are mutually exclusive: what we lack takes the split,
what survives the split we already hold. Ask whether the lister held the database, not how long
the list is.

## The hostname unit pays where a human typed the host, not where a crawler visited it

Measured 2026-09-03 over the whole E9.5 batch. A hostname is net-new only if neither the store
nor his files hold it in that year, and **the commonest way to satisfy that and mean nothing is
`www.<a name already held that year>`**: the ingest refuses `www.<parent registrable>` as the
parent's own site under the name every crawler tries first, and nothing refuses the same alias
one level down, where the bare name is a hostname or a registrable we or he already date.

The share of net-new hostname EE that is this alias, by artifact type: a bulk CDX index re-read
at hostname grain is **essentially nothing else** (`nypw_firstcdx` 100.0% of 7,074.09 EE, leaving
2.84; `ukwa` geoindex 99.5% of 20,916.90 EE, leaving 107.94), while a corpus of URLs people typed
keeps most of its figure (`usenet_new` 33.8%, `usenet_bulk` 27.3%, `rtfm` FAQs 32.8%). **So the
pre-pricing question for any hostname-grain reopen is whether a human or a crawler produced the
host**, and `just price-hosts` prints the share for exactly this reason. The round's own figures
print it too: on 2026-09-03 it was 61.0% of the shipped hostname half, 201,767.94 of 330,577.84 EE.

## Breadth pays and depth does not: 22.2% saturation across hierarchies, 90.5% inside one

Measured on 2026-09-04 over 272 GB of Usenet, which is the largest single corpus this project has
read, and the two numbers point in opposite directions.

**Across hierarchies, saturation is mild.** Thirteen pools summed standalone give 158,841 EE
eligible; unioned they give 127,616. So a hierarchy nobody has read still adds about four fifths
of its own value, which is what justified reading eleven of them rather than sampling one.

**Inside a hierarchy that is already read, saturation is near total.** 133 more `alt.*` archives,
48 GB and 29.8M posts on top of the 9,266 `alt.*` archives already priced: 48,635 candidates, of
which **44,028 were already in the store, 90.5%**. Net-new was **3,278 hostname years and
1,929.1974 EE, about 40 EE per GB** against `news` at 2,552 gross and `soc` at 418. The remaining
101 GB of non-`alt.sex` archives is therefore worth order 4,000 EE, and **the download was
cancelled on that number** rather than on a guess.

**The reason is what makes it transferable.** The hosts people typed at each other are the same
few thousand free-hosting, portal and university hosts wherever they typed them, so depth inside
one community re-finds them and breadth into another community finds a different set. The
operational rule: **when a corpus divides into communities, read one archive from every community
before a second archive from any of them.** The `usenet_probe` report of 2026-08-27 recommended
closing the entire Usenet hostname lane on one `comp` group, which was wrong by two orders of
magnitude for exactly this reason, and the same error in the opposite direction would have spent
a day fetching `alt`.

## Why only a bulk corpus closes the gap

Querying is measured at **255 EE/hour** (400 pairs/hour over a 16.9-hour window, 2026-08-31, at
0.638 EE/pair). The older ~3,000 EE/hour figure was the RDAP era and is dead with it. Ding
confirmed 5% is a hard trigger, and on 2026-08-31 the gap was **530,535 EE**, which is 87 days
of pure querying. The whole priced approval queue that day was 27,386 EE, or 5.2% of the gap.
Spend the hours on bulk dated corpora accordingly; the current gap is in `ROUND.md`.
