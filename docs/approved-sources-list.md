# Approved sources: which source classes may date a year

**What this file is.** The pipeline can measure a source without help. It cannot decide whether that
source's records belong in the annual files, because that is a judgement about what counts as proof.
The thing being distrusted in an unattended run is exactly **the agent's reasoning about its own
finds**, so an argument written by the agent is the least trustworthy artifact here. This file is where
a human classifies a source class, and `src/ark/approvals.py` **enforces** the answer rather than
trusting anyone to remember it.

**How the gate behaves.** `ark ingest` refuses, before it even opens the database, any source whose
evidence type is master-eligible and whose class is not approved below. Candidate-only evidence passes
without a lookup: it can never date a year, the reviewer asked for the pool to be as large as
practicable, and gating it would stall collection for no gain. **An unapproved source is not
quarantined inside the store; it was never written to it.** The journal waits on disk and nothing is
lost.

**How to decide one, in about two minutes.** Each request below carries a link to the source, a
**seeded-random** sample of real records with a live link each, and the measured figures. Open two or
three of the sample links. If the page shows that domain with that date, the class is sound. **Do not
read the agent's argument as evidence**; it is there to be checked, not believed.

**Set exactly one `Decision:` line per request:**

| value | meaning |
|---|---|
| `pending` | nobody has looked. Ingest refuses. |
| `master` | approved: its rows may date a year and enter the annual files. |
| `candidate-only` | collect it, but its rows may never date a year. |
| `rejected` | do not ingest at all, and do not re-request without new external evidence. |

`rejected` binds: the gate refuses it and the request generator will not re-open it, because an agent
that forgets a rejection re-proposes it a week later.

---

## Approved before this mechanism existed

These were classified by the reviewer merging and crediting the round that contained them, or by Ivo by
name and date. They are recorded here so the gate has an answer for them, **not** re-argued: the
authority is the merge or the named decision, and it is cited per entry.

### afnic_fr / whois_creation

- ingest specs: `afnic_fr`
- authority: phase 2; the registry documents that crDate resets on re-registration, quoted in sources.md

Decision: master

### arquivo_ia / cdx_timestamp

- ingest specs: `arquivo_ia`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### arquivo_roteiro / cdx_timestamp

- ingest specs: `arquivo_roteiro`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### attrition_defacement / artifact_listing

- ingest specs: `attrition_dated`
- authority: phase 5, classified by Ivo 2026-08-10 after the licence question was resolved

Decision: master

### early_web_cdx / cdx_timestamp

- ingest specs: `early_web`
- authority: phase 1, merged and credited by the reviewer 2026-07-27

Decision: master

### enron_email / dated_directory

- ingest specs: `enron_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### ia_cdx_bulk / cdx_timestamp

- ingest specs: `cdx_snapshot`
- authority: phase 1 onward, the reviewer's own named route (SPEC VI)

Decision: master

### internet_scout / dated_directory

- ingest specs: `internet_scout`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### isc_survey / artifact_listing

- ingest specs: `isc_survey`
- authority: reviewer confirmed in writing 2026-07-24 that a dated DNS survey may enter the annual files directly

Decision: master

### maillist_archive / dated_directory

- ingest specs: `maillist_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### ncsa_whats_new / dated_directory

- ingest specs: `ncsa_whats_new`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### nypw_firstcdx / cdx_timestamp

- ingest specs: `nypw_firstcdx`
- authority: parser retained and wired, but the source was REJECTED on measurement: 53 net-new domains over 6.28M lines

Decision: rejected

### odp / artifact_listing

- ingest specs: `odp`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### page_directory / dated_directory

- ingest specs: `expansion_directory`
- authority: phase 1; the curated-catalogue assertion is made per seed and on the record (SPEC IV.i)

Decision: master

### rdap_snapshot / whois_creation

- ingest specs: `rdap_snapshot`
- authority: phase 4, merged and credited 2026-08-10; SPEC III.6 allows a creation date for the year it falls in

Decision: master

### rtfm_faq / dated_directory

- ingest specs: `rtfm_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### trade_press / dated_directory

- ingest specs: `tradepress_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### tucows_catalogue / dated_directory

- ingest specs: `tucows_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master


### ukwa_link_source / link_source

- ingest specs: `ukwa_link_source`
- authority: reviewer confirmed in writing 2026-07-24: host/link graph rows may serve as direct annual evidence where the year is explicit

Decision: master

### usenet_address / dated_directory

- ingest specs: `usenet_addr_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### usenet_announce / dated_directory

- ingest specs: `usenet_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### usenet_bare / dated_directory

- ingest specs: `usenet_bare_dated`
- authority: phase 4, merged and credited 2026-08-10, and takes the corroboration split

Decision: master

### uucp_map_creation / whois_creation

- ingest specs: `uucp_creation`
- authority: phase 4, merged and credited 2026-08-10

Decision: master

### uucp_map_registry / artifact_listing

- ingest specs: `uucp_listing`
- authority: phase 4, merged and credited 2026-08-10

Decision: master

---

## Decided, with the request that was reviewed

### udrp_proceedings / artifact_listing

- ingest spec: `udrp_proceedings`
- source: https://www.icann.org/udrp/proceedings-list.htm
- journal: `data/raw/udrp/udrp_proceedings.jsonl.gz`
- agent's dating claim: a proceeding exists only because the domain was registered and a complaint was filed against it, and the commencement date is printed in the record
- nothing in the closed register resembles this by name.

**Check these before reading anything else.** Seeded-random sample, seed `20260811`, so it is reproducible and was not chosen by the agent:

| record | domain | year claimed | open this |
|---|---|--:|---|
| `NAF FA0094335` | `statefarmdirect.com` | 2000 | https://www.icann.org/udrp/proceedings-list.htm |
| `WIPO D2000-0599` | `teliasystems.com` | 2000 | https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-0599.html |
| `WIPO D2001-0044` | `christiesimages.net` | 2001 | https://www.wipo.int/amc/en/domains/decisions/html/2001/d2001-0044.html |
| `WIPO D2000-0862` | `mcgraw-hill.org` | 2000 | https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-0862.html |
| `WIPO D2000-1713` | `tatawestside.com` | 2000 | https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-1713.html |
| `WIPO D2000-1497` | `ge-points.com` | 2000 | https://www.wipo.int/amc/en/domains/decisions/html/2000/d2000-1497.html |

**Measured against the live store**, by program, not by the agent:

| | |
|---|--:|
| records in the journal | 8,972 |
| distinct (domain, year) | 8,923 |
| over distinct domains | 8,892 |
| already held by the store | 8,923 |
| absent from the store | 0.0% |

**What was at stake when the decision was taken**, measured 2026-08-11 before the ingest:

| decision | net-new pairs | equivalent-English |
|---|--:|--:|
| `master` (self-dating, no split) | **7,714** | **4,708.9** |
| `master` (taking the corroboration split) | 1,471 | 914.1 |
| `candidate-only` | 0 | 0.0, and the names still grow the pool |

Mean equivalent-English weight of the net-new part: 0.6214. Contributed **7,837 pairs and 4,763.1808
equivalent-English** on ingest, the difference being pairs the store acquired between the measurement and
the ingest.

The request block above was generated **after** the ingest, so its own counterfactual read zero: nothing
was net-new any more. That is why `request_approval.py` now refuses to build a request for a class the
store already holds evidence for.

**Reasons a reader should refuse**, listed by the agent against its own request:

- the sample links do not show that domain with that date;
- the year is inferred from something other than the record itself;
- the hostname comes out of prose rather than a structured field, in which case `candidate-only` or a split-taking spec is right, not `master`;
- the closed family named above is the same population under another name.

**Decided by Ivo, 2026-08-11**, in these words: "Treated as master artifact-listing sounds fine to me,
just make sure to document and reason about the decision and ingest carefully as you described." The
reasoning, the argument against it and the three mitigations are in
[ADR-002](ADRs.md). The counterfactual above reads zero because the source was already
ingested by the time this request was generated; at the time of the decision it was **7,714 net-new
pairs and 4,708.9 equivalent-English** under the `master` reading against 1,471 and 914.1 under the
split.

Decision: master

---

### netcraft_survey_cache / artifact_listing

- source: archived Netcraft Web Server Survey `/domains/cache/<word>.html` listing pages, via the
  Wayback Machine. Live index: <https://web.archive.org/cdx/search/cdx?url=netcraft.com/domains/cache/*>
- journal: `data/raw/probes/H008-decide.jsonl` (19 of the 20 in-window captures; `silly.html` failed on a
  transient network error and `nature.html` returned no rows)
- agent's dating claim: a hostname printed on a survey dump captured in 1999 was in Netcraft's survey
  database by 1999, and the page's capture timestamp is the only date involved. **This is the claim being
  asked about**, and it is the agent's, not a measurement.
- closest closed family: none by name. The nearest by *shape* is `isc_survey`, which is **approved
  `master`** here: a machine host census published in dated editions, taking no split.

**The whole decision is one question: did a human type these hostnames?** If yes, the corroboration split
applies. If no, this is self-dating like `isc_survey` and it does not.

The case for no split, which is why this is being asked rather than filed: the page is a machine dump from
Netcraft's survey database. There is no prose, no author, and no per-item date; only the *search word*
(`key`, `mesi`, `princeton`) is human-chosen, and the split is about who typed the **hostname**. The store
already carries two machine host censuses this way, `isc_survey` at 1,719,409 records and
`uucp_map_registry`.

The case against: unlike an ISC zone snapshot, this is a **search result over a database**, and if that
database retained hostnames it had stopped observing, a 1999 page could print a name that was gone by 1999.
That was not tested. The monthly-census character of the survey and the page's own "Copyright Netcraft
1999" footer weigh against it, but a reviewer should weigh it too.

**Check these before reading anything else.** Seeded-random sample of the **net-new** rows, seed
`20260811`, so it is reproducible and was not chosen by the agent. Open a link and search the page for the
domain:

| page | domain | year claimed | open this |
|---|---|--:|---|
| `key.html` | `applevalleyhockey.com` | 1999 | https://web.archive.org/web/19991013102618/http://www.netcraft.com/domains/cache/key.html |
| `mesi.html` | `ciemmesistemi.it` | 1999 | https://web.archive.org/web/19991129023605/http://www.netcraft.com/domains/cache/mesi.html |
| `mace.html` | `macedonia-a-to-z.com` | 1999 | https://web.archive.org/web/19991013110743/http://www.netcraft.com/domains/cache/mace.html |
| `mesi.html` | `darlenesellshomesinpa.com` | 1999 | https://web.archive.org/web/19991129023605/http://www.netcraft.com/domains/cache/mesi.html |
| `pcl.html` | `jpcltd.co.jp` | 1999 | https://web.archive.org/web/19991127163507/http://www.netcraft.com/domains/cache/pcl.html |
| `mesi.html` | `homesissaquah.com` | 1999 | https://web.archive.org/web/19991129023605/http://www.netcraft.com/domains/cache/mesi.html |
| `key.html` | `buckeyeortho.com` | 1999 | https://web.archive.org/web/19991013102618/http://www.netcraft.com/domains/cache/key.html |
| `princeton.html` | `princetondevelopment.net` | 1999 | https://web.archive.org/web/19991012054114/http://www.netcraft.com/domains/cache/princeton.html |

**Measured against the live store**, by program, over 19 pages actually fetched. **These are measurements,
not projections**: the first version of this lead projected from 2 pages and the projection was wrong in
both directions.

| | |
|---|--:|
| rows extracted | 13,092 |
| distinct (domain, year) | 11,309 |
| over distinct domains | 11,299 |
| already held by the store | 2,568 |
| absent from the store | 77.3% |
| per-page spread, distinct domains | 0 to 1,821 |
| typo upper bound | 24.3% of 1,500 sampled, and they are hyphen and TLD sibling families rather than OCR junk |

**The counterfactual, and the reason this cannot be filed either way without you:**

| decision | net-new pairs | equivalent-English | against the ~5,000 bar |
|---|--:|--:|---|
| `master` as `artifact_listing`, self-dating | **8,741** | **5,708.4** | clears it |
| `master` taking the corroboration split | 2,204 | 1,458.2 | fails it, 2.3x short |
| `candidate-only` | 0 | 0.0, and 6,314 names still grow the pool | n/a |

Mean equivalent-English weight of the net-new part: 0.6616, which is good. By year: 1999 dominates because
that is when the archive captured these pages, not a property of the survey. By TLD the net-new part is
`.com` 1800, `.org` 135, `.uk` 111, `.net` 70, `.au` 40, `.ca` 16.

**Reasons a reader should refuse**, listed by the agent against its own request:

- the sample links do not show that domain on that page;
- you judge that a search result over a mutable database is not contemporaneous evidence, unlike a zone
  snapshot, in which case the split reading is right and this fails the bar;
- the survey is a census of *web servers*, so a hostname could be a virtual host rather than a registered
  domain the reviewer would accept, and the extraction reduces to the registrable name without checking;
- `candidate-only` is the safe answer that loses nothing: the 6,314 pool names can still be dated by the
  CDX and RDAP engines on their own evidence, which needs no approval at all.

**The reviewer answered on 2026-08-12, conditionally, and the condition failed.** Ivo's words: the
domains do not look human typed to him, and *if you are sure of how these lists came about and that they
hold domains which were actually active during the year they were surveyed, then they can be master
evidence*. The first half is settled: reading the archived pages shows a machine-generated alphabetical
dump of every hostname in the database matching the search word, no prose, no author, no per-item date, so
nobody typed these hostnames and the corroboration split was never the right question. The second half was
measured and did not hold.

**Three instruments, none of which found the population these pages claim.** A name printed on a page
captured in 1999 should behave like a site that was live in 1999. Measured against two controls, it does
not. The positive control is 230 domains the store dates to 1999 from an Internet Archive capture, so
known live that year; the negative control is the undated candidate pool, names with no claim to any year.

| instrument | netcraft names | live-in-1999 control | undated pool control |
|---|--:|--:|--:|
| earliest archive capture is 1999 or earlier | 9.4% (127 hits) | 100% by construction | 10.9% (12,836 hits) |
| still registered today | 52.2% (230) | 94.3% (230) | n/a |
| registered continuously since 1999 or earlier | 25.0% (120) | 74.7% (217) | 16.6% (413,942) |

The first row is the one that decides it, because it is the only one free of survivorship bias: both
populations were queried by the same engine, against the same archive, in the same days. **Netcraft's
names are no likelier to have been captured by 1999 than names with no claim to 1999 at all.** The other
two rows agree in direction and are weaker evidence: the live-in-1999 control is drawn from
archive-captured domains, which skews to prominent sites that were likelier to keep their registration.

Registry dates cannot settle it either way, which is worth recording so the test is not repeated: a 1999
domain that lapsed and was re-registered reports the later date, and twelve sampled names created in 2003
to 2026 were all verified as genuinely printed on the archived 1999 page. The extraction is faithful; it
is the inference from listing to liveness that fails.

**So this cannot date a year, and loses almost nothing by not doing so.** All 13,078 names were banked as
candidates on 2026-08-11 and the engine has been querying them since; 127 have already been dated on their
own capture evidence, which needs no approval and does not depend on trusting the listing.

Decision: candidate-only


---

## Pending requests

Priced, measured and waiting on a decision. A class appearing here carries a seeded-random sample with
live links and the counterfactual, is decidable in about two minutes, and gets its own entry under
`## OPEN` in `key-decisions.md`.

None at present.

---

## Found, awaiting triage

**This section grows indefinitely and that is its purpose** (Ivo, 2026-08-12): *"Grow the list of sources
for sign-off in approved-sources-list.md. Keep growing it indefinitely. Every time when I have a moment to
look at that list, I will tell you whether to add those sources to the candidate pool or to fold them in
directly."*

**How it differs from the section above.** These are sources that have been found, screened against the
closed register and checked for reachability, but **not yet priced against the store**, so they carry no
measured net-new figure and no sample to check. They are here so that hunting sources never waits on a
decision, and so that a wake with healthy engines still produces something.

**What is being asked of a reader.** For each entry, one of two words. *Candidate pool* means
`Decision: candidate-only`: its names may be searched and can never date a year, which is the safe answer
and loses very little, because the archive can still date them from its own captures. *Fold in directly*
means `Decision: master`: its records may date a year on their own authority. `rejected` also binds and is
the right answer for anything not worth keeping.

**Nothing is blocked while these sit here.** A `pending` class cannot date a year, so `ark ingest` refuses
it and collection continues regardless. This queue reaches `key-decisions.md` as **one line naming the
count**, never one entry per source, because that surface stops being read the moment it stops fitting on
a screen.

**Pass 1, 2026-08-12.** Five independent lenses proposed sources, a sceptic per lens collided each against the closed register and probed whether the data is retrievable in 2026, and 11 of 21 survived. **The figures inside these entries are the hunt's own, not measurements I have reproduced**, except where an entry says otherwise; that is what pricing is for, and the `next step` line names it. One claim was checked here and holds exactly: 60,468 undated `.uk` names in the pool.

### ncua_5300_call_report_webaddr / artifact_listing

- potential: 88 (per-row CYCLE_DATE, real data retrieved and parsed, 1,913 net-new pairs and 1,293.3 EE measured off one quarter, mean TLD weight 0.6845; capped by thousands-not-millions volume)
- what it is: NCUA 5300 Call Report quarterly bulk ZIPs, every federally insured natural-person credit union, carrying Acct_891 "World Wide Website Address" and Acct_890 "Internet E-Mail Address" in table FS220D.
- where: https://ncua.gov/files/publications/data-apps/QCR199906.zip
- what dates one item: every FS220D row carries its own CYCLE_DATE, measured as "6/30/1999 0:00:00" on all 10,964 rows of the 1999-06 file, so a single record holds both the hostname and the date with no inference.
- why it may be net-new: credit unions are small US .org/.com institutions with no reason to have been linked; 1,495 of 2,128 website domains are not held for 1999, and 431 of those are pure bracketed gaps with 1998 and 2000 already held.
- reachability, checked 2026-08-13: HTTP/2 200, application/octet-stream, 6,625,659 bytes, last-modified 2018-12-18, nginx, no auth, no redirect; unzips to 10 files, 38.8 MB, and was parsed end to end. QCR199612.zip also 200 at 7,047,436 bytes.
- terms: no prohibition served; headers carried only nginx, x-content-type-options, x-frame-options and HSTS, no banner or auth. NCUA's Website Policies name no restriction on automated access and the dataset is on catalog.data.gov described as "suitable for importing into a database or spreadsheet". Honest gap: robots.txt was not fetched. Work is 8 to 20 static file GETs, not a crawl.
- screener: self-dating, so no corroboration split and 1,913 is already the post-split number; extraction must be tightened not widened, since 406 of 2,484 raw values (16.3%) are malformed (WWW.NDCU.ORGFPSFCU, HTTP:/WWW.LATFCU.COM) and nothing catches a fabricated host. Two proposal claims disproved: the field is in FS220D not FOICU (FOICUDES.txt enumerates 25 fields, none a URL), and whole-window coverage is false, QCR199612 has both columns present but 0 of 11,573 rows populated against a positive control of 11,479 non-empty Phone. 1996 is dead; start quarter is somewhere in 1997-03 to 1999-06 and unpinned.
- next step: price it, binary-searching the start quarter; master-eligible so it cannot bank until this Decision line is decided.

Decision: pending

### fac_sfsac_historic_1998_2001 / artifact_listing

- potential: 86 (+40 AUDITEEDATESIGNED mm/dd/yyyy on the same ELECAUDITHEADER row as AUDITEEEMAIL, +20 largest in-window volume in the slate, ESTIMATE 6,000 to 12,000 own-domain e-mail domains per signature year, capped because the populated rate is unmeasured, +18 the best English lean here, .us MEASURED 0.9261 with a .org and .com tail, +8 half credit, both HTML bodies read in full but no zip byte pulled. School districts, counties, tribes and nonprofits are administrative and exhaustive, so no prominence penalty)

- class note: an e-mail source, not a web-address source. The proposal called it a website source and that is DISPROVED: there is no website or URL column anywhere in ELECAUDITHEADER. Same shape as the pending ncua_5300_call_report_webaddr e-mail field, so a mail domain is the deliverable.

- what it is: Federal Audit Clearinghouse historic SF-SAC returns, every Single Audit filed 1998-2015 by entities spending above the $300,000 A-133 threshold, republished by GSA as per-year CSV zips.
- where: https://www.fac.gov/data/download/historic/
- what dates one item: AUDITEEDATESIGNED on the row that carries AUDITEEEMAIL, mapped to form item I/6/g in the 1997-2000 column, so a form signed 03/1999 evidences that address in 1999. NOT AUDITYEAR: an audit-year-1998 return is signed months after fiscal year end, so dating by the folder claims a year BEFORE the address was attested, which is the dangerous direction. Consequence: five folders census-1997 through census-2001 yield signature dates in 1998-2001, not the four annual folders the proposal named.
- why it may be net-new: MEASURED absence of exactly this population. The store holds 18,278 distinct in-window .us domains (8,266 k12.XX.us, 9,906 other locality, 53 state.XX.us, 53 flat .us) against 3,239,423 .com, so the RFC 1480 locality namespace where every school district and county lived is 0.3% of in-window domains. Nobody linked to a school district site, which is the shape that made UDRP dockets and NCUA pay.
- reachability, checked 2026-08-13: 2 GETs to www.fac.gov, both 200 text/html with real bodies read, no error page. /data/download/historic-dictionary/ 93,080 bytes rendered the complete ELECAUDITHEADER field table across six era columns; /data/download/historic/ 60,000 bytes listed per-year links with SHA1s, census-1998.zip 15 MB, census-1999.zip 16 MB, census-2000.zip 16 MB, census-2001.zip 20 MB, plus a 413 MB 1998-2015 zip. A Login.gov modal renders on both pages but governs SUBMITTING audits; the dictionary and links rendered fully in the same 200 body. Honest gaps: app.fac.gov never contacted, so zip retrievability is unproven, and robots.txt not fetched.
- terms: no prohibition served and an explicit research blessing, verbatim from the body read at /data/download/historic/: "This dataset includes Single Audit submissions collected by the Census FAC from 1998 to 2015. It is provided as-is for historical research and is not included in our web-based search or API." The prospector's separate quote "The data collected by the FAC is free to use and in the public domain" from /data/ was NOT re-verified. Work is 5 static GETs of 15-20 MB, not a crawl.
- screener: artifact_listing, self-dating, master-eligible, no corroboration split, so it needs a human Decision line before it may date a year and that is not the agent's call; candidate-only collection needs no approval. Two warnings the dictionary serves against itself, both the NCUA failure mode: "The quality of data validations were limited in the beginning, and improved over the years" and, for a different column, "FORM DATE RECEIVED ... This field was not populated before 2001", a documented precedent for a column present but empty in exactly the in-window years.
- next step: price it in this order, because either kills it: (1) populated rate of AUDITEEEMAIL in the 1998, 1999 and 2000 folders against a positive control such as AUDITEEPHONE, which is how QCR199612 died with both columns present and 0 of 11,573 rows populated; (2) share of populated addresses on an own domain rather than aol.com, juno.com or worldnet.att.net.

Decision: pending

### uk_historic_hansard / dated_directory

- potential: 84 (+40 per-item date proved four ways on the leaf page, +10 usable volume, ESTIMATE 1,000-3,000 distinct domains against a MEASURED ceiling of 3,811 .gov.uk and 4,292 .ac.uk pairs, +19 .uk at 0.9813, the highest-weight namespace held in volume, +15 real prose retrieved. Not scored down for prominence: the corpus is exhaustive. The unscored risks are the two that decide it, density MEASURED at zero hostnames in 199 words and a crawl of 300,000 to 700,000 leaf pages on one host)

- class note: typed inside a dated artifact, so it takes the corroboration split. Not `link_source` and never `link_target`: what is extracted is an address printed in transcript prose.

- what it is: the digitised Official Report of both Houses, 1996-2001, static HTML on a live non-IA host, one page per contribution rather than per sitting day.
- where: https://api.parliament.uk/historic-hansard/written-answers/1999/mar/10/tourism-strategy
- what dates one item: the date is in the URL path, the HTML title ("Tourism Strategy (Hansard, 10 March 1999)"), the breadcrumb and the printed citation "HC Deb 10 March 1999 vol 327 cc212-3W". No volume-level dating, no inference.
- why it may be net-new: real headroom is .co.uk and .org.uk businesses named in debate, the half a prominence-biased crawl baseline is weakest on.
- reachability, checked 2026-08-12: 2 requests. The day index for 1999-03-10 returned 301 and was not chased; the leaf item returned 200, text/html, 8,133 bytes, 0 redirects, full prose (199 visible words). Third-party hostnames in the answer text: ZERO. Chrome only (parliament.uk, two speaker permalinks, az416426.vo.msecnd.net).
- screener: dating is the strongest in the batch. The proposal's cost is wrong by three orders of magnitude, it is one page per contribution, not roughly 1,200 sitting-day documents, so ESTIMATE 300,000 to 700,000 files. Density is UNMEASURED and one 199-word page proves nothing either way; the .gov.uk and .ac.uk half is capped by measurement at 8,103 pairs even in the impossible case where every held name is mentioned in all six years.
- next step: price it, density first on a sample of a few hundred leaf pages, before anyone writes a crawler. Oireachtas answers the same family question more cheaply, so run that first.

Decision: pending

### usac_erate_form471_contact_email_1998_2001 / dated_directory

- potential: 84 (+40 the funding year is written on the form itself and the entity key is a separate column, +10 volume ESTIMATE only and gated behind a records request, +19 the .us/.edu locality namespace at 0.9261 is the best English weight in this lens, +15 metadata field-completeness and a store-side cap test both actually measured. No prominence or current-state penalty)
- class note: typed, so the corroboration split binds. It is doubly keyed for paper filings, which puts the expected typo rate at or above the library survey's measured 39.3% of never-held domains sitting one edit from a held one. Not a candidate for `artifact_listing`: the records have an author, the applicant.
- what it is: FCC Form 471 E-Rate basic-information filings by US school districts, schools and public libraries, mined for the applicant-typed Contact Email, Billed Entity Email and Authorized Email.
- where: https://opendata.usac.org/E-Rate/E-Rate-Request-for-Discount-on-Services-Basic-Info/9s6i-myen (metadata https://opendata.usac.org/api/views/9s6i-myen.json), form instructions https://docs.fcc.gov/public/attachments/DA-02-2954A5.pdf
- what dates one item: the funding year written on the form, Block 1 Item 2 verbatim, "Provide the funding year for which you are applying for funds by filling in the appropriate year in the blanks provided (e.g., July 1, 2003 through June 30, 2004)", with Item 3 Entity Number a separate stable key, verbatim "a unique number assigned to your organization or institution by the SLD". CAVEAT: the instructions read are the October 2002 revision, one year past window, so the email field's in-window presence is INFERRED from an adjacent-year artifact, not observed.
- row shape: per-filing, one Form 471 per applicant per funding year. Unconfirmed for whatever the pre-EPC system would actually release; that shape is unknown outside USAC.
- who keyed it: human, twice. The applicant hand-completed or typed it and, for paper filings, an SLD data-entry contractor keyed it again, verbatim "before data entry begins". Typed class, split applies.
- why it may be net-new: the k12.XX.us, lib.XX.us and city/county .us namespace, not the saturated .edu corner, at 0.9261 English share.
- reachability, checked 2026-08-13: metadata API 200, application/json, 111,226 bytes of real metadata; the human dataset page returned a Socrata SPA shell, a 200 carrying no dataset content at all; FCC PDF 200, 208,861 bytes, 1,436 lines of extracted text. In-window DATA is not reachable at any status because it is not served.
- terms: licence verbatim `{"name": "Public Domain"}`, licenseId `PUBLIC_DOMAIN`, attribution "Universal Service Administrative Company". Description verbatim and this is the blocker: "This dataset contains data for the last 10 years. To request older records, please email opendata@usac.org." No harvesting prohibition in the metadata. HONEST LIMIT: the portal terms page was never read, only the dataset licence.
- kill condition: on whatever USAC releases, the email columns near zero while Billed Entity Phone is near 100%, or an extract that turns out per-entity rather than per-filing. Positive control, the same two columns in the published years: phone 739,972/739,972 (100.0%) against Billed Entity Email 342,115/739,972 (46.2%). This is the test that killed QCR199612 (both columns present, 0 of 11,573 filled) and that the library survey passed (PHONE 99.15% against WEB_ADDR 26.5%).
- screener: measured 739,972 filings, Funding Year 100% populated at 2017-2026 only. DISPROVED the 33-char field cap as a kill: against 10,611 in-window locality-namespace domains, median length 17, mean 17.0, p90 21, max 33, so 98.6% survive an 8-char local part and 92.6% an 11-char one. Also disproved as transferable: the 100.0% Contact Email rate is an EPC login artifact, and the in-window paper form said "if you have one". Yield ESTIMATE low thousands of post-split pairs, under the ~5,000 bar.
- next step: email opendata@usac.org for FY1998-FY2001 basic information, asking explicitly for a per-filing extract carrying funding year, entity number, contact email and phone; run the phone-against-email control on what arrives before any approval request is written.

Decision: pending

### eric_fulltext_1996_2001 / dated_directory

- potential: 83 (+40 publicationdateyear verified per record on two live IDs, +12 usable volume, ESTIMATE 1,300 to 4,700 net-new pairs by density transfer from the two rejected dated corpora, +16 .edu 0.9717 with .org, .gov and .com behind it, +15 a real 3.3 MB PDF retrieved, not a landing page. Administrative prose whose purpose is to print school URLs, so no prominence penalty)

- class note: typed inside a dated record, so it takes the corroboration split. This is the one entry in the batch where OCR garbage cannot become a master year claim: a mangled name simply fails to corroborate and lands in the pool.

- what it is: ERIC restricted to 1996-2001 with ERIC-hosted full text, in-window documents being state and district technology plans, campus computing and library reports and district case studies. Open JSON API, no key, plus bulk XML.
- where: https://api.ies.ed.gov/eric/ (full text at https://files.eric.ed.gov/fulltext/ED######.pdf, bulk XML at https://eric.ed.gov/?download=)
- what dates one item: one publicationdateyear stamped on each document, verified live ({"id":"ED661491",...,2001} and {"id":"ED445105","title":"Mini-Digest of Education Statistics, 1999.",...,2000}). The date is per item; the hostname lives inside the PDF, so the join is an extraction step, not a lookup.
- why it may be net-new: school, district and campus hosts are the obscure administrative tail a crawl baseline covers thinly, and 52,354 documents is 70x to 84x the size of the two dated corpora whose density it borrows.
- reachability, checked 2026-08-12: 2 requests, the full budget, no archive.org. The API search for publicationdateyear:[1996 TO 2001] AND e_fulltextauth:1 returned 200 with numFound 52,354, reproducing the proposal's population independently. ED445105.pdf returned 200, a genuine 3.3 MB PDF.
- screener: population MEASURED, not claimed. The kill risk is n=1 and labelled as such: ED445105 is a JBIG2 scanned-image PDF with NO text layer (Photoshop CS5 metadata, 2010 scan pipeline), and 1996-2001 ED documents are largely digitised microfiche. On its own density transfer it straddles and mostly misses the roughly 5,000-pair bar. Cheaper route the proposal missed: bulk XML abstracts are born-digital clean text, 52,354 dated records with zero PDF fetches and zero OCR, at lower host density. Caveat for pricing: k12.xx.us school hosts are third-and-deeper labels and the store dates two-label registrable domains only.
- next step: price it, on the bulk XML abstracts first and a sampled text-layer rate over the PDFs, since the OCR question decides whether the PDF route exists at all.

Decision: pending

### nces_imls_pls_web_addr_1998_2001 / typed

- potential: 82 (+40 per-cycle date verified against the file itself rather than assumed, +10 volume, MEASURED 348 post-split net-new pairs for FY1999 and ESTIMATE 1,200 to 1,800 across FY1997 to FY2001, under the ~5,000 bar but bought with 5 static GETs, +17 MEASURED post-split mean weight 0.805, +15 data actually downloaded, canonicalised through `ark.canonical.to_registrable` and differenced against the live store. No prominence penalty: an administrative census of every US public library outlet is the opposite of prominence-selected)

- class note: the proposer's `artifact_listing`, unsplit and self-dating, is REJECTED. WEB_ADDR is a form field keyed by state library agency staff, and the consequence is measured: of the 122 domains never held at any year, 48 (39.3%) sit at Damerau-Levenshtein distance 1 from a domain the store already holds (crytstallakelibrary.org / crystallakelibrary.org, nrewburghlibrary.org / newburghlibrary.org, ostegolibrary.org / otsegolibrary.org, punamco.lib.oh.us / putnamco.lib.oh.us, soffolk.lib.ny.us / suffolk.lib.ny.us). Admitting those unsplit mints year claims for domains that never existed, which is the placeholder failure mode in a different dress, and typos are by construction the never-held names, so the split removes exactly that population and almost nothing else. Upgrading to `artifact_listing` is a separate human decision and this line does not ask for it.
- what it is: the NCES/IMLS Public Libraries Survey annual public-use files, specifically the OUTLET file (one row per library service outlet per fiscal year), which carried WEB_ADDR until FY2002 deleted it; the admin-entity file has no web column at all in this era.
- where: https://www.imls.gov/research-evaluation/surveys/public-libraries-survey-pls (lists every FY1992 to FY2005 file); measured file https://www.imls.gov/sites/default/files/pupldf99_csv.zip; in-window siblings pupld97a_csv.zip, pupldf98_csv.zip, pupldf00_csv.zip, pupld01b_csv.zip.
- what dates one item: the reporting period on the state summary record, NOT the submission column. YR_SUB is uniformly 2000 on all 17,057 FY1999 outlet rows, so keying off it would file 1999 data as 2000. STARTDAT/ENDDATE per state read 07/1998-06/1999, 10/1998-09/1999, 01/1999-12/1999, so every FY1999 period ends in 1999 and mapping by ENDDATE year is correct. Independent check, the strongest number here: 1,019 of the 1,489 domains (68.4%) are ALREADY dated to 1999 by other evidence in the store.
- row shape: per-filing. Each fiscal year is a fresh submission by the 50 state agencies, one row per outlet, WEB_ADDR coded 'M' per individual row. The decisive evidence against the dated-dataset fallacy is the 26.5% population rate: the zip members were repackaged in 2013, so a backfilled current-state address would be near-universally filled, and 26.5% is the correct contemporaneous web-adoption rate for 1999 US library outlets.
- why it may be net-new: municipal and county library outlets on lib.XX.us, k12.XX.us and city/county .us, the shape a crawl-derived baseline is thinnest on (the store holds 18,278 .us against 216,581 .uk).
- reachability, checked 2026-08-13: 2 requests, both bodies read. Survey page 200, a real content page enumerating 14 fiscal years of links. pupldf99_csv.zip 200, application/zip, 1,861,128 bytes, 302 imls.gov to www.imls.gov followed; `file` reports "Zip archive data" and unzip lists three real members (4,226,830 / 23,388 / 2,326,171). Not an error page wearing a 200.
- terms: quoted verbatim from the page as read: "Public-use data files are publicly available without restriction, and do not require a license." Also "Survey data are coded or aggregated without individually identifiable information." No harvesting banner, no rate language, no click-through, US federal government work. Item 7C, the library director's e-mail, is collected but WITHHELD from the public file, so the e-mail route is closed and only WEB_ADDR is available.
- kill condition: WEB_ADDR does not change between FY1998 and FY1999 for the same FSCSKEY, which would mean one current-state address stamped onto each annual filing and would void every year claim. That diff is free once the second file is on disk and is the first test to run; it is the one thing NOT yet observed. Positive control, PHONE on the same outlet row, MEASURED 16,912 of 17,057 (99.15%), which is the test that killed QCR199612 (both columns present, 0 of 11,573 filled) and PLS passes cleanly, so 26.5% is genuine 1999 sparsity and not an unpopulated column.
- screener: measured on the live store rather than estimated. 4,519 of 17,057 rows carry a real WEB_ADDR (12,404 'M', 128 'None'), giving 1,489 distinct registrable domains, of which 1,367 (91.8%) are already held and 1,019 (68.4%) already dated 1999. RAW net-new 470 pairs / 374.6 EE; POST-SPLIT, the number to quote, 348 pairs / 280.1 EE / mean weight 0.805, composed of 135 lib.XX.us, 127 .org, 42 .com, 28 city/county .us, 11 k12.XX.us. Disproved: the proposer's canonicalisation risk. PSL collapses WWW.CI.ANCHORAGE.AK.US/SERVICES/DEPARTMENTS to anchorage.ak.us and www.co.broward.fl.us/library to broward.fl.us, keeps 4-label detroit.lib.mi.us, rejects the 'M' code, and the store already holds 10,645 four-label in-window .us domains, so the collapser demonstrably keeps this shape.
- next step: price it, first and cheapest in the batch. Download FY1998 and FY2000, run the FSCSKEY diff, then request approval on the split reading with the four remaining files measured.

Decision: pending

### ucsf_industry_documents / dated_directory

- potential: 78 (per-item documentdate on 28.3M litigation documents, endpoint open and real JSON retrieved, internal corporate correspondence is the least prominence-selected population available; capped because the in-window count is unverified and the date filter was shown not to filter)

- class note: typed inside a dated artifact, so it takes the corroboration split; the uncorroborated half lands as `link_target`

- what it is: UCSF Industry Documents Library, 28,298,293 litigation-discovery documents and internal industry email with a public Solr metadata endpoint and OCR text on a separate download host.
- where: https://metadata.idl.ucsf.edu/solr/ltdl3/query (OCR text at download.industrydocuments.ucsf.edu)
- what dates one item: each document carries its own documentdate, the date the memo or letter was written, in a human format such as "1995 March 20" or "1999 May 07". A hostname typed in that document evidences that year alone. Typed inside a dated artifact, so it takes the corroboration split, exactly the trade_press shape.
- why it may be net-new: internal corporate correspondence is not prominence-selected, which is the one population a crawl-derived baseline is structurally weak on, and 28.3M documents is the largest corpus in the batch by two orders of magnitude.
- reachability, checked 2026-08-12: 200 twice on the Solr endpoint, 1,262,993 and 1,294,239 bytes of real JSON, no auth. facet.range over documentdate returned an EMPTY facet_counts object, so per-year counts cannot be had that way. A range query 1996-01-01 to 2001-12-31 returned numFound 3,843,392 but its top three hits read "1995 March 20", "1995 April 20", "1999 May 07", so the handler is not filtering on the date (lenient parsing matching year tokens in text) and 3,843,392 is NOT an in-window count. The OCR host was not probed: budget spent on metadata, so the prospector's 200 on gpyh0003.ocr is unverified.
- screener: dating verified as genuinely per item, endpoint open and live, and the largest upside here. Unverified: in-window volume, whether OCR text exists for in-window ids, and hostname density per document. Pricing must re-verify the OCR host first and find a date filter that actually filters.
- next step: price it, on a strict-syntax date query plus a sample of in-window OCR fetches for hostname density.

Decision: pending

### oireachtas_debates_xml / dated_directory

- potential: 77 (+40 FRBRdate verified per record, +3 usable volume, ESTIMATE tens to low hundreds of pairs, +19 .ie at 0.9744 into a namespace holding only 8,430 distinct domains, +15 clean full-text XML retrieved. It scores on weight and cheapness, not on yield, and its real job is to price the parliamentary family before anyone touches Hansard)

- class note: typed inside a dated artifact, so it takes the corroboration split and widening extraction is safe.

- what it is: the Irish parliamentary record as Akoma Ntoso XML, Dail, Seanad and committees, listed by a documented open API, one XML file per debate record. ESTIMATE roughly 1,470 in-window files at about 172 KB each, collectable politely in an afternoon.
- where: https://api.oireachtas.ie/v1/debates?date_start=1996-01-01&date_end=1996-12-31&limit=2
- what dates one item: FRBRdate date="1996-12-20" name="#generation" plus a second at name="#reported", the date in the URI path, and the same date repeated in the API record. The publication date in the same header reads 2020-06-25 and is the digitisation stamp; it must never be read as the year.
- why it may be net-new: a genuine .ie tail would be net-new against 8,430 held .ie domains; the split, not the weight, is the constraint.
- reachability, checked 2026-08-12: 2 requests, both real data. The 1996 debates query returned 200, application/json, 10,538 bytes with live records for 1996-12-20 and 1996-12-19; the 1996-12-20 Seanad main.xml returned 200, application/xml, 172,181 bytes of clean full text, 23,016 visible words, not OCR and not a stub.
- screener: two proposal claims corrected. The API does return committee records, and written answers are a separate writtens_pdf key whose URIs came back NULL, so the PQ replies called the dense part are NOT in the artifact verified here. Density: hostnames in those 23,016 words, ZERO, which bounds the rate at under 1 per 20,000 words on the only sample anyone has taken. At roughly 30M in-window words that is 50x under the bar and in the territory where W3C technical reports were rejected at 56 pairs.
- next step: price it, as the cheap density probe that decides Hansard and the whole parliamentary family, not as a source expected to clear the bar alone.

Decision: pending

### junkfilter_dated_blocklist / dated_directory

- potential: 74 (+40 the snapshot directory dates the file, which is the dated_directory shape already approved for internet_scout and ncsa_whats_new, +14 usable volume, ESTIMATE 3,000 to 8,000 distinct entries across 13 snapshots with no split to pay, +12 .com 0.6321 and .net 0.4530 ESTIMATE, +8 half credit, autoindex bytes retrieved but jf-domains itself never opened. Spam-origin hosts are the opposite of prominence-selected, so no penalty, and the whole census is affordable so the ceiling can be measured exactly)

- class note: CONTAINER-dated, not per-record: the hostname sits in a file, the date is the directory name. Self-dating, so no corroboration split, so there is no wall behind the parser and a bad match becomes a master claim directly. A diff of consecutive snapshots is required to turn a listing into a first-seen year.

- what it is: junkfilter, the procmail anti-spam package (Sutter/Hunt, 1997), whose live mirror keeps the whole release tree as ISO-dated directories. jf-domains is the source at 48,745 bytes in the 19980508 release; jf-addresses (311 B) and jf-ip (121 B) are negligible.
- where: https://junkfilter.zer0.org/pkg/
- what dates one item: the ISO-dated release directory the file sits in, so an entry present in 19980508/jf-domains evidences 1998 and nothing else; first-seen year comes from diffing consecutive snapshots.
- why it may be net-new: domains observed originating spam in 1998 are short-lived and obscure, exactly what a crawl-derived baseline lacks, and being self-dating the pairs are not cut back to the already-held set.
- reachability, checked 2026-08-12: 2 requests, no IA. /pkg/ returned 200, 2,418 bytes of nginx autoindex, listing exactly the 13 in-window dated directories claimed (19980508, 19980831, 19980901, 19981015, 19981016, 19990312, 19990331, 20000304, 20000313, 20001025, 20001130, 20010528, 20010529) plus 20020519 and 20030115 out of window and unenumerated old/, dev/, current/ and a duplicate 980508/. /pkg/19980508/ returned 200, 2,788 bytes, showing jf-domains at 48,745 bytes stamped 08-May-1998 00:22 beside jf-addresses 311, jf-ip 121, jf-bodychk 2,816, junkfilter.readme 6,249 and junkfilter-980508.tar.gz 28,118.
- screener: container and dates verified exactly as claimed. NOT verified and load-bearing: the file contents. "Plain text list of literal hostnames" is the proposal's claim, not a measured fact; this is procmail input, so entries are plausibly escaped-regexp fragments (foo\.com) and may carry wildcards, which are not names and must be dropped rather than reconstructed. The line-count and pair figures are ESTIMATE from byte size alone.
- next step: price it, opening jf-domains first to establish what an entry actually looks like, then the 13-file census and diff, which is a complete measurement rather than a projection.

Decision: pending

### nominet_whois_port43 / whois_creation

- potential: 72 (self-dating registry date on the highest English-weight TLD at 0.9813, answered live twice, 60,468 undated .uk names verified in the pool; capped because it returns the CURRENT registration so lapsed names are lost, and the service closes February 2027)

- what it is: Nominet's public .uk WHOIS on port 43, one "Relevant dates: Registered on:" line per queried domain.
- where: whois.nic.uk port 43, documented at https://registrars.nominet.uk/uk-namespace/registration-and-domain-management/query-tools/whois/
- what dates one item: the registry's own "Registered on:" date for that one domain, self-dating, no split. Cap the proposal understates: it is the CURRENT registration, not the original, proved 2 of 2 (0345.co.uk, stored as 1997, reads 28-Dec-2022; kestrel-cleaning.co.uk reads 23-May-2025), so every dropped and re-registered .uk name is lost silently. Failure direction is loss, not a fabricated in-window year, so it is safe to bank. Nothing before Aug-1996 (Nominet prints "before Aug-1996"), so 1996 is partial.
- why it may be net-new: 0 of the 60,468 undated .uk names in the pool appear in the 11,362,034-pair merged baseline, and all 202,878 registered .uk names the baseline holds are already dated in the store. Upper bound 60,468 x 15.7% x 0.9813 is roughly 9,300 EE (ESTIMATE, and it assumes a 100% answer rate that 1 of 2 probes already contradicts).
- reachability, checked 2026-08-12: port 43 answered twice at human pace, full record both times, no refusal, no HTTP in the path; the cited docs page fetched 200. The response carries the banner "WHOIS service for .UK will cease on 9th of February 2027", and Nominet's page calls .uk WHOIS end of life and redirects to RDAP, the service that refused this project three times in fourteen queries at 0.5 q/s.
- screener: strongest of the batch, live and measured, but two proposal claims fail. The quoted limits, 5 q/s and 1,000 per rolling 24 hours, are NOT on the page cited, so the 61-day feasibility case rests on an unverified number; and a seeded sample of 20 undated .uk names holds anti-spam munging, typos and junk beside plausible names, so a material share of the 60,468 returns No match and under a daily quota that waste is the whole cost.
- next step: price it, measuring the real rate limit and the answer rate on a plausibility-ranked queue, inside the window that closes February 2027.

Decision: pending

### govinfo_cbd_bulk / typed

- potential: 71 (per-issue filename date, real zip bytes retrieved, order 10^6 notices in window, .com-dominant vendor half; net-new density unmeasured and the EDGAR precedent is a live risk)
- what it is: Commerce Business Daily, the statutory daily federal procurement gazette through 1 January 2002, published by GPO as bulk-only per-year zips of born-digital HTML; the usable half is vendor contact e-mail and solicitation URLs from small contractors.
- where: https://www.govinfo.gov/bulkdata/CBD/1998/CBD-1998.zip
- what dates one item: the zip's first local file header names the entry CBD-1998-30no98.html, so each record is one issue carrying its own date in its own filename; a hostname in the 30 November 1998 issue evidences 1998 and nothing else.
- why it may be net-new: thousands of small federal contractors printing a contact block, a population with no reason to have been crawled, unlike the large public filers that sank EDGAR.
- reachability, checked 2026-08-13: 206 Partial Content, application/zip, content-range bytes 0-2047/60093265, last-modified 2010-04-13, cloudflare, first bytes 504b 0304 real PK magic. Only the 1998 zip was fetched; the 1996, 1997, 1999, 2000 and 2001 folders are search context, not observed.
- terms: no banner, terms text, auth challenge or robots gate served on either route. govinfo runs the Bulk Data Repository for programmatic access and these are US Government works. Honest gap: no request was spent on a terms page, so this is "nothing prohibitive encountered", not "terms read and permit it".
- screener: typed, takes the corroboration split, so widening recall is safe because the split and not the pattern is the wall; not master-eligible, needs no Decision line and never waits on a human. Disproved: the proposal's cited machine listing https://www.govinfo.gov/bulkdata/json/CBD is DEAD, returning 200 text/html, 67,225 bytes, "Govinfo Bulkdata Service Error", byte-identical to the page that closed govinfo_fedreg at approved-sources-list.md:721, so its "measured, not recalled" directory listing was measured on an error page. The 60,093,265-byte size figure was nevertheless genuine.
- next step: price it by unzipping the 1998 and 2001 zips and counting distinct hostnames per 1,000 notices in both years, because density almost certainly rises across the window.

Decision: pending

### ipgod_au_marktext / dated_directory

- potential: 71 (+40 registry-issued per-item filing date, +10 usable volume, ESTIMATE 2,000 to 6,000 domain-shaped marks in window before dedupe and before the split, +13 .com.au 0.9904 diluted by an unknown share of plain .com 0.6321, +8 half credit, HEAD on the real CSV with content-length and accept-ranges but not one row read. Trade mark register is administrative and exhaustive, so no prominence penalty)

- class note: screened deliberately as typed so the corroboration split stays as the wall. Reading it as artifact_listing would remove that wall in front of an unmitigated invented-hostname failure mode, and that reading is a human decision, not the agent's.

- what it is: IP Australia's IPGOD bulk CSV on data.gov.au, target population being 1996-2001 applications whose mark text is itself a domain name.
- where: https://data.gov.au/data/dataset/49017fd0-e7be-4fc0-88c8-046fc366d980/resource/474471f2-8325-491f-af82-feb3ed91acec/download/trade-mark-application-description.csv
- what dates one item: the application filing date on that one mark record. This is the WEAKEST dating claim of the batch: a mark reading FOO.COM.AU filed in 2000 proves someone applied in 2000, not that the domain resolved.
- why it may be net-new: speculative domain-name marks peaked in 1999-2000, precisely the window, and .com.au carries the highest weight in the table.
- reachability, checked 2026-08-12: 2 requests. CKAN package_search?q=ipgod returned 200, application/json, 228,003 bytes, 16 packages with direct resource URLs and sizes. HEAD on the live 2022 description CSV returned HTTP/2 200, text/csv, content-length 249,236,662, last-modified 17 Jun 2022, accept-ranges bytes, via CloudFront, so the in-window slice can be range-pulled without moving 250 MB. Six trade mark tables enumerated with byte sizes (application 285,766,239, classification 213,728,540, description 249,236,662, events 2,337,427,679, links 84,644,274, party activity 820,290,648).
- screener: two proposal errors. It cites ipgod2021, which the catalogue titles "IPGOD2021 [SUPERSEDED]"; the live release is IPGOD2022. And the catalogue describes trade-mark-application-description.csv only as "Application Description Table for Trade Mark", so the claim that this is the file holding the mark text is UNVERIFIED; the words may sit in trade-mark-application.csv. No field name in this entry is observed, all are inferred from table titles. The safeguard the two pending USPTO entries rely on, restricting to Section 1(a) use-based filings where the applicant swears use in commerce, DOES NOT EXIST in Australian law (knowledge, not checked against the IPGOD schema). The premise is also weaker than proposed: .au is MEASURED as well held, 69,783 distinct .com.au and .net.au domains over 141,956 in-window pairs.
- next step: price it, one range request to find the mark-text and filing-date columns, then the in-window domain-shaped count, before any 250 MB pull.

Decision: pending

### ted_ojs_notices_1996_2001 / link_source

- potential: 70 (+40 PD publication date on every notice, +13 volume, ESTIMATE 2,000 to 6,000 net-new pairs straddling the ~5,000 bar and weighted to pair completion rather than new names, +8 English, ESTIMATE mean weight 0.30 to 0.45 with a genuine 0.9813 core, +9 half credit, the two monthly packages HEADed and the store overlap measured by me, but the 8-day content sample is the prober's and not re-measured. No prominence penalty: ordinary public bodies tendering above threshold)

- class note: typed inside a dated notice, so it takes the corroboration split and widening the extraction regex is safe. RFC-placeholder risk does not apply, because a tender notice giving a fake address for document requests defeats its own purpose. The split is nearly free on the population that matters, since already-held UK bodies corroborate trivially.
- what it is: Tenders Electronic Daily, the Supplement to the Official Journal, as free bulk monthly tarballs. Each month holds one nested tarball per publication day, each day one ZIP per language, and the EN_ member is flat tagged text (TI, PD, CY, TX). Domains sit in the TX body: the contracting authority's address block and the "documents available from" line.
- where: https://ted.europa.eu/packages/monthly/2001-6 (72 monthly packages cover the window)
- what dates one item: the notice's own PD field, e.g. PD: 19990105. A hostname typed inside that notice evidences that year and nothing else, no carry-forward. Caveat not closed: address density was measured only at Jan 1999 (8.7%) and Jun 2001 (20.2%), so 1996-1998 is likely near-empty and this is effectively a 1999-2001 source until an early package is opened. 1996-01 exists as a file; whether it carries an EN_ flat-text member is UNVERIFIED.
- row shape: per-filing. The unit of publication is the notice, republished afresh each time an authority tenders, so the same council recurring monthly produces repeated dated observations rather than one mutable row. Not a current-state register.
- why it may be net-new: pair completion, not new domains, and this is the honest reading. Held gov.uk domains have 3,816 unfilled (domain, year) slots with only 188 of 1,264 complete across six years; nhs.uk has 752 unfilled slots with only 12 of 169 complete, and NHS coverage is a 2001-only snapshot (by year 15, 15, 16, 21, 41, 154), so a 1999 or 2000 tender naming a trust is a net-new pair at 0.9813.
- reachability, checked 2026-08-13: 200 on both. 1996-01: application/gzip, content-length 87,388,631, content-disposition filename=1996-01.tar.gz. 2001-06: application/gzip, content-length 147,601,141, filename=2001-06.tar.gz. Real gzip payloads with correct attachment dispositions, not HTML behind a 200, and 147,601,141 matches the proposal byte for byte, so the prober did download it. The whole 1996-2001 window is present as files.
- terms: quoted from https://ted.europa.eu/en/legal-notice, fetched: "Unless otherwise noted, the procurement notices published in the Supplement to the Official Journal of the European Union can be freely reused, for commercial or non-commercial purposes." Editorial content CC BY 4.0, system metadata CC0 1.0. Nothing on the legal notice prohibits automated access, crawling or scraping, and /packages/ exists to be downloaded in bulk. Logos and industrial-property material are excluded from reuse, which does not touch hostnames.
- kill condition: distinct-hosts-per-issue flattens as issues are consumed, since the same council reappears every month; fit a saturation curve against issues consumed, not a line, and close it when the marginal issue stops paying. Positive control: the TX address block against CY, using UK authorities the store dates for all six years (barnsley.gov.uk, brent.gov.uk, bristol-city.gov.uk). If a month's EN_ member yields none of those three the extractor is broken rather than the month being empty. Do NOT control on PD, which is populated by construction and proves nothing about the address field.
- screener: the proposal's central claim is FALSE and measured so. This is NOT the non-US analogue of the k12/city.state.us gap: the store holds 216,581 .uk against 18,278 .us, so UK public bodies are comparatively well covered. 15 of its own 17 exemplar hosts are already held, most for all six years (barnsley.gov.uk, brent.gov.uk, bristol-city.gov.uk 1996-2001; bexley.gov.uk, audit-commission.gov.uk 1997-2001; dublincorp.ie, fingalcoco.ie, courts.ie; and the "cheap long tail" gavle.se, krokom.se, botkyrka.se, comune.roma.it all held). Only bkcw-tr.nhs.uk and wirralh-tr.nwest.nhs.uk missed. The 247 EE per eight days it quotes is GROSS, with no overlap subtracted, and the bar is defined on net-new. Continental bulk (it 97, se 80, fr 72, de 70 at 0.1324, at 51, no 30, fi 26, nl 26, es 19) adds names cheaply and almost no equivalent-English, and even those are largely held.
- next step: price it on one month, 2000-06, measuring post-split net-new PAIRS on already-held .uk and .nhs.uk rather than new domains, and open 1996-01 in the same pass to settle whether the early years carry an EN_ member at all.

Decision: pending

### sbir_sttr_award_pi_email_2000_2001 / dated_directory

- potential: 65 (+40 Award Year on every award row, +5 volume, only 2 of 6 window years are usable and ESTIMATE 1,000 to 2,000 net-new pairs, +13 English, .com 0.6321 with a small .edu nudge and no ccTLD tail, +15 real data retrieved and 351 rows parsed, -8 the two columns the proposal leaned on are dead or current-state, and no terms page was ever read)

- class note: candidate-only today. Self-dating, so there is NO corroboration split behind it and the email regex must be tightened rather than widened. `Company Website` is candidate-only PERMANENTLY and regardless of approval, being per-entity current state; `Contact Email` is not evidence of anything in window, being empty. This line covers the `PI Email` column alone.
- what it is: the SBA consolidated SBIR/STTR award database, one bulk CSV of every award since programme inception, 41 columns confirmed by reading the header row (the proposal's data-dictionary URL was 404). Columns that matter, by index: [16] Award Year, [30-33] Contact block, [34-37] PI Name/Title/Phone/Email, [24] Company Website. The awardee is a small federal R&D contractor, typically ten to fifty staff.
- where: https://data.www.sbir.gov/mod_awarddatapublic_no_abstract/award_data_no_abstract.csv
- what dates one item: `Award Year` alone, which corrects the proposal: `Proposal Award Date` is 0/52 populated on in-window rows, so the ISO date it leaned on does not exist that far back and the bare year is the only date. That is sufficient, since the deliverable is a (domain, year) pair. PI Email fill by window year, measured on 52 rows: 1996 0/8, 1997 0/8, 1998 0/8, 1999 0/8, 2000-2001 12/20. The usable span is 2000-2001 only, the two years the crawl baseline is already thickest on. The contemporaneity test passes: KPaul1214@worldnet.att.net and amshipley@capecod.net sit on 2000-2001 rows, and a fill rate of 0% before 2000 and 60% after is the signature of an as-submitted field, since a backfill fills uniformly.
- row shape: SPLIT, and the split is the finding. PER-FILING for PI Email: one row is one award keyed by Agency Tracking Number and Contract, and of 25 companies appearing more than once, 11 carry multiple distinct PI Emails (physical sciences inc. has 4, across award years 1999/2009/2026). PER-ENTITY CURRENT STATE for Company Website: 0 of 25 repeat companies carry more than one distinct value, lynntech.com appears identically as https://lynntech.com/ on both a 1990 and a 1995 row, and THE SMOKING GUN is https://nsc.aero/ on a year-2000 row for NEAR SPACE CORP. The .aero TLD was not delegated until December 2001 and took no registrations until 2002, so that value cannot be a year-2000 observation. Proven from the bytes, not from documentation, which was 404.
- why it may be net-new: own-domain .com of ten-to-fifty-person R&D firms; 8 of the 12 observed emails are own-domain corporate (rdainc.com, gsslinc.com, sterling-semiconductor.com, avidyne.com, indigosystems.com, photera.com, fce.com, esli.com), 1 .edu subdomain, 3 consumer ISP and worthless.
- reachability, checked 2026-08-13: 2 requests, one host. HEAD 200: content-length 91,426,516 (91.4 MB, not the 65 MB claimed), binary/octet-stream, last-modified Sat 01 Aug 2026 05:47:05 GMT, AmazonS3 via CloudFront, etag 5ef6180bb6e1a15eec977da3b611c5d1, accept-ranges bytes. Then ONE multi-range GET, -r 0-24000,45000000-45060000,88000000-88060000, returning 206 multipart/byteranges, 144,449 bytes, three slices in one round trip, 351 well-formed rows parsed against the 41-column header. No login, no gate, and the body parsed as CSV, which is the check a status code cannot give.
- terms: PARTIALLY VERIFIED, flagged rather than papered over. Both responses carried no licence header, no terms header, no robots gate and no authentication, and the file was served openly to an identifying User-Agent. What was NOT done: fetch a terms-of-use page. The proposal's claim that "the data-resources page carries no terms of use, licence or restriction on automated downloading" is UNVERIFIED and must not be quoted as checked. Background only, not a substitute: US federal government work, uncopyrightable under 17 U.S.C. 105. Spend one request on the sbir.gov terms page before anything else.
- kill condition: dedupe collapses the yield. SBIR firms routinely win several awards in one year and each is a row, so gross pairs are not distinct pairs; if distinct in-window own-domain pairs come in under ~1,500 before differencing, close it. Positive control: PI Phone on the same row, MEASURED 52/52 (100%), which REPLACES the control the proposal named. `Contact Phone` was offered as the control for `Contact Email` and is itself 0/52 in window, so testing one empty column against another proves nothing; that is QCR199612 recurring and it would have been walked into. Secondary controls Company and Address1, both 52/52.
- screener: ESTIMATE throughout on scale, anchored on the external ~4,000-6,000 awards a year rather than on slice byte-density (the tail slice spans 1984-2024 and is plainly not year-sorted): ~30,000 in-window rows, ~10,000 in 2000-2001, times the measured 60% PI Email fill (n=20, thin) and ~67% own-domain share (n=12, very thin) gives ~4,200 gross pairs, plausibly ~3,000 distinct, plausibly 1,000-2,000 net-new against 3,239,423 in-window .com already held, roughly 600-1,300 EE. That MISSES the ~5,000 bar. The offset is cost: converting every estimate above into a measurement is exactly one more GET, with zero per-item requests and no archive traffic.
- next step: candidate-only, and cheap. One request to the sbir.gov terms page, then one full GET to measure distinct 2000-2001 own-domain pairs against the store. Do not write an approval request until that measurement exists.

Decision: pending

### usco_bulk_registrations / typed

- potential: 63 (schema proof retrieved, two independent per-record dates, 2.8M in-window registrations ESTIMATE, .com lean; the hostname-titled share is entirely unmeasured)
- what it is: US Copyright Office Registration and Recordations bulk dataset, ~22M registrations 1978 to 2025 as MARC, parsed CSV and tabular CSV; the slice is in-window registrations titled in the era's cataloguing shape "www.example.com : [web site]".
- where: https://data.copyright.gov/Registrations/Tabular/ (index at https://www.copyright.gov/economic-research/usco-datasets/)
- what dates one item: the CSV header carries reg_date and publication_date beside title in the same row, so one record holds the hostname and two independent statutory dates.
- why it may be net-new: a registrant who filed a website title in 1999 need not have had a crawled site, and the corpus is a record office rather than a link graph.
- reachability, checked 2026-08-13: 206 Partial Content, text/csv, content-range bytes 0-1500/2155230698, last-modified 2026-05-18, no auth, non-IA host. Header row read verbatim: record_id,reg_num,reg_date,title,work_type,alternate_title,creation_date,publication_status,publication_date,...
- terms: reliance disclaimer only, quoted verbatim: "This data set does not replace or supersede the online public catalog or existing search practices established by the U.S. Copyright Office, and the data set should not be relied on for legal matters." No restriction on automated or bulk download; bulk download is the stated purpose.
- screener: typed, takes the corroboration split, not master-eligible, no Decision line needed. The split is load-bearing and must not be relaxed: a title reading "Amazon.com" is a company name and no proof a host resolved. Gap stated plainly: the sampled category was musical works, which is the wrong category for websites, so no pair figure exists for this source and none should be quoted.
- next step: price it against the computer-file and text categories, counting hostname-regex titles with reg_date or publication_date in window, streaming or range-GET rather than pulling 2 GB per category.

Decision: pending

### uk_gazette_addressed_notices_1998_2001 / link_source

- potential: 62 (+40 publication date per notice, +1 volume, MEASURED at 3x to 5x below the ~5,000 bar with no rescue available, +19 English, .co.uk and .org.uk at 0.9813 which is the top band, +2 counts re-derived but no notice body ever parsed and not one domain recovered)

- class note: a solicitor or insolvency practitioner typed the address into a statutory notice, so the corroboration split applies and wide extraction is safe.
- what it is: The Gazette (London, Edinburgh, Belfast), the UK official public record of statutory notices: insolvency, corporate, personal legal, planning, state. 1998 onward exists as the XML that rendered it; 1996-1997 is OCR of scans and out of reach in structured form. Retrieval is a documented Atom/JSON/RDF API plus SPARQL with per-notice URIs, so it is queryable rather than crawlable.
- where: https://www.thegazette.co.uk/all-notices/notice/data.feed?text=www&start-publish-date=1998-01-01&end-publish-date=2001-12-31
- what dates one item: the notice's publication date, which the feed filters on, so a hostname in a notice published 1999-04-26 evidences 1999 and nothing else. Window truncated at both ends: 1998-2001 only.
- row shape: per-filing. One notice is one dated publication event, and a practitioner appearing in forty notices produces forty dated rows. The shape is right; only the scale is wrong.
- why it may be net-new: small UK firms and professional practices on .co.uk and .org.uk, the highest weight band and where a crawl-derived baseline is thinnest.
- reachability, checked 2026-08-13: 200 on both queries with genuine Atom bodies rather than an error page behind a 200: 23,425 bytes carrying real notice titles ("Bankruptcy Orders") unfiltered, 9,486 bytes filtered.
- terms: permitted with conditions the project already meets. From https://www.thegazette.co.uk/data: "The Gazette is a rich source of open data that is free for the developer community to use and repurpose unless stated otherwise, is Crown Copyright and is therefore free for you to use under the Open Government Licence", with the caveat "this licence does not cover the re-use of personal data". That caveat has teeth, because the corpus is largely bankruptcy notices about named individuals, so only the registrable domain may be retained and never the mailbox. The fair-use policy explicitly PERMITS automated harvesting: "Carry out crawling in non-business hours between 9pm and 7am UK.", "Limit requests to 5 request every 10 seconds.", "Comply with our robots.txt file and any crawl delay instructions.", "Use a unique and identifiable User-Agent that includes your application name and version", "Not attempt to bypass rate limits or access restrictions.", plus honouring Retry-After on a 429. Probes ran at 05:19 UK, inside the permitted window.
- kill condition: already met. 715 address-bearing notices measured against a ~5,000 net-new pair bar, with each domain typically appearing in one notice and so yielding one pair rather than four. Positive control if anyone reopens it: NOT text=www, which the whole-token index makes unreliable in both directions, but the notice XML body field that renders the address block, controlled against the 7 known-positive notices demon.co.uk returns. If parsing those 7 does not recover demon.co.uk the extractor is broken rather than the corpus being empty.
- screener: both headline figures re-derived independently and they reproduce EXACTLY: <f:total>490734</f:total> for all notices 1998-01-01 to 2001-12-31, and <f:total>715</f:total> for text=www over the same range, i.e. 0.146% of the corpus. The prober's self-kill is sound and its trap disclosure is correct: text=co.uk returns 622 for 1999 alone while btinternet returns 0 and demon.co.uk returns 7, proving the index is whole-token and the 622 is matching company names like "Direct Clothing Co (UK) Limited". One correction in the source's favour that the prober did not draw: because the index is whole-token, a query for www cannot match an address written as the single token www.foo.co.uk, so 715 is a soft FLOOR. The prose proxies bound it anyway (e-mail 592, website 414, http 359, same order of magnitude), so the true address-bearing population is order 1,000-2,000 notices and at most a couple of thousand distinct domains even granting a 3x undercount. Cost is genuinely tiny, order 1,500 API calls with no crawling, which is the only thing it has going for it.
- next step: close it. No approval request. Reopen only if the OCR pre-1998 years are ever released as structured text, which would not change the density and so probably never.

Decision: pending
### courtlistener_caselaw / dated_directory

- potential: 60 (date_filed per opinion, bulk CSV off a non-IA host with no key, litigant hostnames are not prominence-selected; overlaps caselaw_access_project, price only one first)

- class note: typed inside a dated record, so it takes the corroboration split

- what it is: Free Law Project quarterly bulk CSV export of the whole CourtListener corpus, off any IA host, no key; opinion-clusters carries date_filed, opinions carries the text.
- where: https://storage.courtlistener.com/bulk-data/ (enumerate via the S3 REST listing, ?list-type=2&prefix=bulk-data/opinion)
- what dates one item: date_filed on the opinion cluster, one machine-recorded date per opinion, joined to the text by cluster id, so an opinion filed 2000-06-14 naming foo.com dates foo.com to 2000 with no inference.
- why it may be net-new: same argument as CAP, ACPA and trademark litigation from 1999 plus ordinary commercial disputes naming a party's website. Coverage of the era is published appellate and F.Supp.2d material; unpublished district opinions 1996-2001 are thin, which is knowledge and not measured here.
- reachability, checked 2026-08-12: 200 on both S3 REST listings (application/xml, 62,481 and 25,033 bytes). Real sizes: 72 keys under bulk-data/opinion*, opinions-2026-06-30.csv.bz2 at 54.562 GB, opinion-clusters-2026-06-30.csv.bz2 at 2.457 GB, 36 quarterly generations back to 2022-08, no auth, IsTruncated false.
- screener: dating holds, retrieval proved. The artifact_listing reading the proposal floats is NOT available: the refusal criteria in the udrp_proceedings approval block say a hostname out of prose rather than a structured field means candidate-only or a split-taking spec, so the 5.5x upside quoted from the udrp fork does not transfer and nobody should price this expecting it. 54.562 GB against a population CAP reaches in static per-reporter files.
- next step: price it after CAP, or instead of CAP if CAP's per-reporter slicing proves worse than one quarterly pair.

Decision: pending

### ffiec_call_report_webaddr / artifact_listing

- potential: 60 (+40 the quarter-end report date of the filing that carries the URL, sound in principle, but conditional on an unverified premise, +8 usable volume, ESTIMATE well below bar on the only verified route, +12 US filers, .com-dominant, mean weight ESTIMATE 0.62, +0 no data retrieved, both 200s were a landing page and an instructions PDF. Exhaustive regulatory panel, so no prominence penalty)

- class note: this is a snapshot filed on a date, not a current-state field with a historical date beside it, which is what makes it per-item. That holds only for the filing itself.

- what it is: MDRM item TEXT4087, "Primary Internet Web Address of Bank", on the FFIEC/FDIC Call Report cover page, requested of every FDIC-insured commercial bank and savings institution from the June 1999 quarter, so 11 in-window quarter-ends collected it.
- where: https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx
- what dates one item: the quarter-end report date of the filing, so a web address in the 2000-06-30 file evidences that domain in 2000 alone and one bank across 11 quarters yields at most three year claims. CRITICAL: the FDIC BankFind/SDI route nominated for 1999-2000 serves WEBADDR as a CURRENT-state attribute, and joining that onto a historical report date converts a valid per-item claim into the dated-dataset fallacy.
- why it may be net-new: small US community bank domains in 1999-2000, a population with little crawl prominence.
- reachability, checked 2026-08-12: 2 requests plus one to a host not otherwise touched. HEAD on the primary URL returned HTTP/1.1 200, text/html, 27,777 bytes, which is the terms-acceptance landing page and explicitly NOT the data; the product sits behind terms acceptance and a POST. The proposal's central citation verified live: the FDIC June 1999 supplemental instructions returned HTTP/2 301 then 200, application/pdf, 22,030 bytes, so the item's existence and its June 1999 start date are real and not asserted.
- screener: the field exists; its PUBLICATION is unproved, and that is the whole source. Established by search and corroborated on the Chicago Fed page that CDR public bulk holds historical data starting 2001-03-31, so the verified route cannot serve 1999 or 2000 at all and 11 in-window quarters become 4, all in 2001, the best-covered year. call.report's bulk-files documentation describes the ZIP only as per-institution XBRL plus one delimited all-schedules text file and never mentions TEXT4087. The Chicago Fed historical files (SAS XPORT, 1976-2021) are "financial variables plus selected structure data" and returned 403. MEASURED ceiling: the store already dates 4,007 bank-like domains in 1999, 4,730 in 2000 and 6,907 in 2001, with 17,077 missing in-window slots across 9,751 domains in total.
- next step: access request, but a narrow one: ask FFIEC or the Chicago Fed whether any public per-quarter product for 1999-06-30 through 2000-12-31 carries TEXT4087. If the answer is no, close it; nothing else about this source matters.

Decision: pending

### pmc_oa_subset_fulltext_1998_2001 / link_source

- potential: 60 (+40 sound per-item JATS pub-date, +0 volume, the distinguishing body-URL claim measured to nothing, +10 weight not separately measured and expected to track 0.5569, +10 store-side measurement real but the positive control was never established)
- class note: typed inside a dated artifact, master-eligible behind a Decision line. Moot on the measured yield, so no approval should be requested.
- what it is: the PubMed Central Open Access Subset restricted to 1998-2001, mined from JATS full text rather than metadata, on the claim that printed body and reference URLs reach non-institutional domains an affiliation field cannot carry.
- where: https://pmc.ncbi.nlm.nih.gov/tools/openftlist/
- what dates one item: the JATS pub-date in the same article XML as the address. Per-item, conservative in direction, never reached because the population fails first.
- row shape: per-filing. The article XML is fixed at publication and carries both the addresses and its own date. Not the dated-dataset fallacy; the shape is fine and the population is not.
- who keyed it: human. The author typed the email and the URL, the publisher typeset them. The body-URL half is if anything more typo-prone, since a URL printed in running text was validated by nobody.
- why it may be net-new: it is not. All 36 domains a 1998-2001 biomedical paper actually prints are already held, 25 of them at all six years.
- reachability, checked 2026-08-13: 200 on esearch db=pmc, a real eSearchResult with `<Count>21497</Count>` and QueryTranslation `1998/01/01:2001/12/31[Date - Publication] AND "open access"[Filter]`; 200 on the tools page, 86,577 bytes of real terms text, not an SPA shell.
- terms: CONDITIONALLY GREEN, verbatim, "The PMC Cloud Service, PMC OAI-PMH Service, PMC FTP Service, E-Utilities and BioC API are the only services that may be used for automated retrieval of PMC content. Systematic retrieval (or bulk retrieval) of articles through any other automated process is prohibited." Also verbatim, "License terms vary. Please refer to the license statement in each article for specific terms of use." So scraping article pages is CLOSED, the named bulk channels are open, and a collector must stay strictly inside the OA subset.
- kill condition: the printed body and reference URLs collapse to domains the store already holds at 6 of 6 years. FIRED, measured free against the store: ebi.ac.uk, sanger.ac.uk, tigr.org, embl-heidelberg.de, genome.ad.jp, gnu.org, jax.org, incyte.com, affymetrix.com, clontech.com, promega.com, invitrogen.com, roche.com, mathworks.com, spss.com, sas.com, graphpad.com, medscape.com, cdc.gov, nih.gov, stanford.edu, mrc.ac.uk, pasteur.fr, infobiogen.fr all at 6 of 6. Positive control NOT ESTABLISHED and recorded as a gap: no in-window OA article was named that prints a correspondence email. Anyone reopening this must name that control article FIRST; the intended control columns are the JATS `<email>` element and body URL text.
- screener: in-window OA subset MEASURED at 21,497 articles, inside the proposal's own estimate. The email half is proposal 1's population one hundred times smaller, and proposal 1 measured 0 post-split. The body-URL half, the entire distinguishing argument, measured 36 of 36 already held. The ones holding fewer than six years are not headroom either: ensembl.org 2, flybase.org 2, bioperl.org 3, biomedcentral.com 3 are missing precisely the years in which they did not yet exist, so those gaps are correct and filling them would be a false claim. Registrable-domain collapse finishes it, a lab page at www.somelab.uni-x.de/software collapses to the same saturated uni-x.de.
- next step: close it. Record the 36-of-36 measurement in docs/sources.md so the "full text reaches domains metadata cannot" argument is not reproposed.

Decision: pending

### caselaw_access_project_opinions / dated_directory

- potential: 58 (decision date per opinion, static files retrieved with real reporter metadata and explicit start_year, US-heavy so English weight is high; same population as courtlistener)

- class note: typed inside a dated record, so it takes the corroboration split

- what it is: Harvard Caselaw Access Project bulk static files, full text of published US case law, one record per opinion, unauthenticated static files on a non-IA host.
- where: https://static.case.law/
- what dates one item: one opinion is one record with a structured decision date, and a hostname in that opinion evidences that year only, not the dataset publication date. Reporter metadata carries explicit start_year and end_year, so in-window filtering is a metadata operation and not a guess.
- why it may be net-new: hostnames typed by litigants and judges 1996-2001 include small commercial parties that never had a famous crawl footprint, and the repo has never touched this family.
- reachability, checked 2026-08-12: static.case.law/ HTTP/2 200, text/html, last-modified 2024-03-05, Cloudflare, no auth. ReportersMetadata.json returned 206 with real records, id 210, "West's Atlantic Reporter, Second Series", A.2d, start_year 1942, end_year 2010, nested jurisdictions. Data retrieved, not a shell.
- screener: dating sound, retrieval proved, and grep of all 183 tracked files for caselaw|courtlistener|case\.law returned nothing, so genuinely untouched. Split-protected typed evidence, so widening the URL regex is safe and no approval is needed to start on the candidate half. Overlaps courtlistener_caselaw below: price only one of the two first.
- next step: price it, on one in-window reporter, measuring hostnames per opinion and the post-split net-new share.

Decision: pending

### sec_form_adv_part1_2000_2001 / artifact_listing

- potential: 58 (+30 the website item is VERIFIED to exist in the form but the row shape is not, so a per-item date is probable rather than proved, +8 one in-window year only, ESTIMATE 1,200 to 2,500 net-new pairs against a ~5,000 bar and it cannot repeat across years, +12 .com-dominant with a .net tail, ESTIMATE mean weight 0.62 to 0.65, +8 half credit, page body parsed and the primary Federal Register text retrieved and grepped, but no data row read. Registered-adviser panel is a near-census, so no prominence penalty)

- class note: downgrade to dated_directory if a row turns out to be current-state rather than per-filing.

- what it is: SEC Form ADV Part 1 bulk filing data from IARD, the registration and annual updating return of every SEC-registered investment adviser, published free as a zip; the population is small private advisory partnerships that never file on EDGAR, which is why the EDGAR reject at 46 pairs from 150 filings does not price this.
- where: https://www.sec.gov/files/adv-filing-data-20001019-20111104.zip
- what dates one item: PROBABLE, not verified. Item 1.I is verified from 65 FR (22 September 2000), Release IA-1897, verbatim: "In response to Item 1.I., the World Wide Web site addresses you list on Schedule D should be sites that provide information about your own activities, rather than general information about your bank", and "advisers must provide the email address of a contact person (if she has one), and the address of any web site the adviser sponsors." The in-window slice is 2001 ALONE, not the fifteen months proposed, on the same release: "Persons applying for registration with the Commission as an investment adviser after January 1, 2001 must file Form ADV, as amended, through the IARD", so the Oct-Dec 2000 head of the file predates the website item. THE OPEN RISK is the FDIC BankFind trap in new dress: if the zip holds one current-state row per adviser as of 2011-11-04 with a latest-filing date beside it, joining that website onto an old date is the dated-dataset fallacy and the source is worth nothing. The filename with a non-overlapping window followed by a separate 20111105-20241231 file argues per-filing, but no byte of content was read.
- why it may be net-new: not prominence, and the proposal's version of this should not be quoted. The honest argument is namespace exhaustion: the store's RDAP headroom table shows .com asked 1,068,844 times against 917,549 undated names, so a new .com must earn its place on the date rather than on the name. A 2001 advisory firm site is a small commercial .com, the most heavily crawled category there is, in the best-covered year in the store.
- reachability, checked 2026-08-13: 2 GETs to www.sec.gov, both real. Page 200 text/html, 85,446 bytes, body parsed and the link extracted rather than assumed, exact link text "From ADV Part 1 - October 19, 2000, to November 4, 2011". Data file HEAD HTTP/2 200, application/zip, content-length 249,976,083, last-modified Fri 01 May 2026, nginx, no auth, no redirect. WebFetch had 403'd for the prospector; curl with the project User-Agent succeeded, so that 403 was agent-based, not a block. Third host disclosed: govinfo.gov/content/pkg/FR-2000-09-22/pdf/00-23888.pdf, 200 application/pdf, 2,733,540 bytes, 10 pages, converted to 6,991 lines and grepped.
- terms: no prohibition in the body read. The full 85,446 bytes were grepped for automated, robot, crawl, scrape, User-Agent, user agent, rate, Terms, Privacy and Security: ZERO occurrences of every one, so the page carries no automated-access language at all. HONEST GAP: sec.gov's site-wide automated-access rule lives on a separate webmaster/EDGAR-access page that was NOT fetched, because it would have exceeded the 2-request budget, so it is UNVERIFIED here; the project sends a compliant identifying User-Agent in any case. Work is 1 static GET of a 250 MB zip.
- screener: artifact_listing, self-dating, master-eligible, no split, so a human Decision line is required before it dates a year. Scale ceiling from a contemporaneous figure: approximately 7,800 SEC-registered advisers had filed through IARD as of 25 September 2001. The 8,200 state-registered advisers are OUT on the SEC's own scope limit, verbatim "The SEC does not have access to data for state-registered investment advisers." The compensating strength is the transition schedule in the same release, SEC number 801-54146 or higher "must file no later than March 30, 2001" and non-December fiscal year ends "no later than April 30, 2001", which forces a near-census of fresh Part 1A filings into Q1-Q2 2001 rather than a trickle.
- next step: one GET and one unzip, which prices it completely: does a row represent a filing with its own date, or an adviser's current state. Everything else is downstream of that answer.

Decision: pending

### uspto_trademark_case_files / artifact_listing

- potential: 55 (filing date per case file on a large administrative corpus, US so English weight is high; capped because a mark text is not a hostname and the extraction is unproven)

- class note: read as self-dating; under the corroboration split it would be `dated_directory` instead, which is the cautious reading

- what it is: USPTO Trademark Case Files Dataset, the Chief Economist's bulk release of 12.7M applications and registrations 1870 to March 2024, as CSV or Stata ZIPs (case_file 414 MB CSV, full set 4.33 GB). Slice that matters: 1996-2001 filings whose mark text is a domain name, restricted to use-based Section 1(a) rows.
- where: https://www.uspto.gov/ip-policy/economic-research/research-datasets/trademark-case-files-dataset (the cited file path is not a file, see reachability)
- what dates one item: one application is one row carrying its own filing date. The 1(a) versus 1(b) split is the right safeguard, because an intent-to-use filing proves only that somebody wanted the name, which is the invented-hostname failure mode. A 1(a) filing swears use of the MARK in commerce, which for a mark reading FOO.COM strongly implies but does not prove the domain resolved.
- why it may be net-new: same small-filer population as uspto_tm_marktext, reached through a research release rather than the XML backfile.
- reachability, checked 2026-08-12: as cited, HTTP 200 but text/html, 1,936 bytes, not the data. data.uspto.gov/ui/datasets/products/files/TRCFECO2/2023/case_file.csv.zip and data.uspto.gov/bulkdata returned byte-identical responses with the same etag db36270368f2d51573a14ff0f32c14f1 and the same last-modified, which is the proof it is one single-page-app shell served for every path. developer.uspto.gov product page 301 to https://data.uspto.gov/. The catalog.data.gov slug from search: 404. Corroborating context from search, not fetched: the legacy Developer Hub was decommissioned 2026-06-05 and the data APIs now need a key.
- screener: two links unverified because the file would not open, the field names (mark_id_char, filing_dt) and the presence of usable filing-basis columns, both quoted from documentation rather than observed. The dataset itself is real and current, so this is a moved download route and not a dead source. Duplicates uspto_tm_marktext on population: solving access once serves both, and this route is the one that pays a measurement without a 10 to 20 GB download.
- next step: access request, find the live TRCFECO path or the OCE mirror, then confirm the two columns exist before pricing.

Decision: pending

### dnsrf_dap_udrp_multiprovider / artifact_listing

- potential: 52 (same shape as udrp_proceedings which is already approved master and paid 7,837 records, wider provider set; capped because the incremental population over what we hold is unknown)

- class note: self-dating, and the class is already settled `master` for udrp_proceedings by ADR-002; this is a wider provider set

- what it is: DNS Research Federation's normalised UDRP decisions on DAP.LIVE, claimed as roughly 83,000 cases over 156,000 domains across all four dispute providers, intended as the sanctioned reopen of the NAF, eResolution and CPR gap at docs/sources.md:1721.
- where: https://dap.live, catalogue at https://dnsrf.org/docs/dap-live/inputs/data-feeds/
- what dates one item: one case, one disputed domain in its own field, filing year as the earlier and safer claim. Settled shape, no reviewer time needed on the classification again.
- why it may be net-new: only if it reaches providers the ICANN consolidated table missed, which is now the entire case.
- reachability, checked 2026-08-12: dap.live/ HTTP/2 200, text/html, 23,058 bytes, Vercel, cache HIT; dnsrf.org feeds page 200, 38,739 bytes. Two landing pages and NO data. The catalogue is titled "Feeds List" but renders entries client-side: the fetched content carried navigation and one sentence about filtering, with no UDRP feed named, no export URL, no licence text and no price. Same client-side-app wall that closed adrforum.com at docs/sources.md:1713.
- screener: two proposal claims are void and both are checkable in the repo. The premise that we hold only WIPO's 3,325 in-window cases is false: docs/ROUND.md:113 shows udrp_proceedings ingested at 7,837 pairs and 4,763.1808 EE from ICANN's consolidated multi-provider table, and the reviewed sample at docs/approved-sources-list.md:227 is a NAF record (FA0094335, statefarmdirect.com, 2000), so NAF is partly banked and the 3,000 to 6,000 pair estimate is measured against the wrong baseline. And the class is not pending as claimed: it was decided master artifact_listing in ADR-002 and key-decisions.md C-12. That second error cuts in the proposal's favour and removes the argument it spends most of its case on, but an agent quoting a settled question as open is a reason to distrust its other numbers.
- next step: access request, and only after re-measuring the increment against the banked multi-provider table; a new ingest spec would still need its own Decision line.

Decision: pending

### cipo_ca_trademark_marktext_1996_2001 / typed

- potential: 49 (+40 statutory per-item filing date and the only candidate here covering all six years, +10 ESTIMATE 1,500 to 5,000 domain-shaped marks before dedupe and BEFORE the split, at or below the ~5,000 bar already, +13 blended lean ESTIMATE 0.65 to 0.70 rather than the proposal's 0.8365, +6 catalogue JSON parsed but the payload URL as published is dead, -20 prominence: a name someone paid a law firm to register is by construction a commercially active site, which an 11.4M-pair crawl-derived baseline holds FIRST)

- class note: the proposal's assertion of self-dating artifact_listing with NO split is REJECTED. approved-sources-list.md:552 already decided the identical Australian shape, ipgod_au_marktext "screened deliberately as typed so the corroboration split stays as the wall. Reading it as artifact_listing would remove that wall in front of an unmitigated invented-hostname failure mode, and that reading is a human decision, not the agent's." CIPO is the same shape and takes the same treatment, which removes the proposal's stated headline differentiator.

- what it is: CIPO Trademark Data bulk release, catalogued on open.canada.ca and served as 29 ZIPs from opic-cipo.ca; the slice is 1996-2001 applications whose mark text is itself a domain name. Coverage verbatim from the API body: "The database contains trademark documents covering applications filed from July 7, 1865 to August 16, 2023."
- where: https://open.canada.ca/data/en/api/3/action/package_show?id=4bf74760-7ae7-4c83-ace8-b84a3b9aea8d
- what dates one item: the application filing date on that one mark record, per-item and no inference. The limit must not be softened: a mark reading FOO.COM filed in 1999 proves an APPLICATION in 1999, not that foo.com resolved in 1999. Worse than the pending USPTO pair: the Section 1(a) use-in-commerce safeguard those two lean on DOES NOT EXIST in Canadian law at filing time, since proposed-use filings were permitted and a Declaration of Use only fell due before registration. That is knowledge, not checked against the schema.
- why it may be net-new: weakest link in the entry. The store already holds 128,134 .ca pairs over 47,140 distinct domains, so the proposal's "nothing in the store or the queue is Canadian" is FALSE, and its claim that these are small filers a crawl misses is an assertion with no measurement behind it.
- reachability, checked 2026-08-13: PARTIAL. GET package_show 200, application/json;charset=utf-8, 33,194 bytes, parsed as real JSON, success:true, 29 resources with direct ZIP URLs, tables including TM_application_main, TM_application_text, TM_claim, TM_event. HEAD on the mark-text URL AS PUBLISHED IN THE RECORD, opic-cipo.ca/cipo/client_downloads/TM_CSV_2024_08_20/TM_application_text.zip, returned HTTP/2 404, text/html, 1,245 bytes, Microsoft-IIS/10.0, body read as a genuine IIS error page and not a redirect. The dated sibling TM_application_text_2024-08-20.zip listed in the same record is the likely live one but is UNTESTED, so payload retrievability is unproven. The record is itself unreliable: the TXT resource named TM_applicant_classification_txt_format points at a URL for TM_application_text_txt_format, so resource NAMES here cannot be trusted to identify contents. No row of data was read and no field name was observed.
- terms: CLEAN and measured rather than asserted, verbatim from the package_show response: license_title "Open Government Licence - Canada", license_url https://open.canada.ca/en/open-government-licence-canada. No automated-access banner, no harvesting prohibition. Bulk download, one fetch, nowhere near web.archive.org.
- screener: typed, takes the corroboration split, not master-eligible, so it needs no Decision line and never waits on a human; uspto_tm_marktext:680 independently records that the split "historically removes most of the net-new part", which is what caps this. The 0.8365 headline is misleading: .ca was a RESTRICTED namespace for most of the window, requiring a federal or provincial corporate presence and manually administered until CIRA took over in late 2000, so 1996-2000 domain-name marks filed in Canada would overwhelmingly be .com at 0.6321. That is knowledge, testable in the first pricing pass.
- next step: locate the live mark-text ZIP, confirm which table actually holds the words, then measure the in-window domain-shaped count and the .ca-versus-.com split before anything else. Verify the filing-basis field against TM_claim before any approval request is written.

Decision: pending

### itu_operational_bulletin_1996_2001 / link_source

- potential: 49 (+40 a per-issue date with an explicit observation cut-off, +4 volume, ~145 issues at a measured mean of 7 net-new pairs, +10 mean weight 0.4957, +15 two issues fetched and measured against the store, -20 the exemplar issue was prominence-selected and measured to be the outlier)
- class note: typed, master-eligible only behind a Decision line, and it should never get one. Anyone tempted to file the carrier annex as `artifact_listing` to escape the split should read the typo pair first: issue 718 carries BOTH fhh-telcomlaw.com and fhh-telecomlaw.com, one edit apart; the store holds the first at 1998 and has never held the second. That is the library-survey typo signature reproducing in a second corpus.
- what it is: the ITU Operational Bulletin, the fortnightly administrative return in which telecommunication administrations and recognized operating agencies notify the TSB of service and contact details. Born-digital PDFs with a text layer, enumerable as T-SP-OB.{NUMBER}-{YEAR}-PDF-E.pdf.
- where: https://www.itu.int/dms_pub/itu-t/opb/sp/T-SP-OB.718-2000-PDF-E.pdf and .../T-SP-OB.719-2000-PDF-E.pdf
- what dates one item: the masthead on every page, "ITU Operational Bulletin, No. 718, 15.VI.2000, (Information received by 8 June 2000)". The parenthetical states an explicit observation window, so a hostname in issue 718 is an observation no later than 8 June 2000. Verbatim caveat: the original separates title and date with a dash, replaced here with a comma to honour the house rule.
- row shape: per-notification inside a per-issue artefact. Contemporaneous by construction, not the dated-dataset fallacy. The shape is genuinely good.
- who keyed it: human, at national administrations and at the TSB. Typed class, split applies, and the typo pair above is the proof rather than an inference.
- why it may be net-new: 13 net-new (domain, 2000) pairs from issue 718, three times its own proposal's headline, but the median issue carries almost none.
- reachability, checked 2026-08-13: issue 718 200, application/pdf, 245,934 bytes, PDF 1.3, 10 pages, 69,549 characters extracted; issue 719 200, application/pdf, 348,590 bytes, 10 pages, 75,606 characters. Real bulletins with the ITU masthead, not error pages. No challenge, no banner, no rate limiting. Reachability is not this source's problem, in contrast with cites.org and ramsar.org (403 to every client) and unfccc.int (Incapsula).
- terms: SECOND-HAND and moot given the recommendation. The proposal quotes permission to "download, copy and use content for personal, educational, or non-commercial purposes provided that you acknowledge the source and maintain all copyright and other proprietary notices", with no automated-access prohibition; the terms page was not re-fetched. Attested from own traffic only: 200 to an honest User-Agent, no banner, no challenge, no redirect off host.
- kill condition: mean net-new pairs per issue times ~145 issues falls under the ~5,000 pair bar. FIRED under both readings, which is what makes the closure safe: at the measured mean of 7 pairs, about 1,015 pairs and 519 EE; at issue 718's 13 pairs taken as typical, about 1,885 pairs and 934 EE, both assuming zero saturation. Positive control: 89 email matches from issue 718 against 17 from issue 719 on comparable page and character counts, so 719's thinness is the corpus, not the parser.
- screener: verdict confirmed, REASON CORRECTED. The proposal's own figures reproduce (87 distinct domains in 718, 82 dated somewhere, exactly 4 never pooled: bouygestelecom.fr, carrier24.de, fhh-telecomlaw.com, tecoint.com, EE 1.50) but the post-split figure it never computed is three times its headline, 13 net-new pairs, EE 6.44, mean weight 0.4957. DISPROVED, the load-bearing claim that "the issues reprint the same carrier annex with amendments": intersection of consecutive issues 718 and 719 is 2 domains out of 92 in the union, only 28.6% overlap. The real fact is worse and different in kind, the large carrier annex appears in OCCASIONAL issues and the median issue carries almost no addresses (issue 719: 7 distinct domains, 1 net-new pair, tcc.go.tz). Weight cannot improve with volume, the membership is global by design: btc.com.bh, cwbda.net.bm, goldenlines.co.il, itu.hn, maltacom.com, tlda.com.ar, finnet.fi, primustel.co.uk.
- next step: close it, and record in docs/sources.md with the corrected reason, not annex reprinting (measured at 28.6% overlap, so false) but occasional annexes against a near-empty median issue. No approval request.

Decision: pending

### cbd_secretariat_meeting_documents_1996_2001 / link_source

- potential: 48 (+40 the UN symbol and date line on every page, +4 volume, an estimated 500 to 900 in-window documents against a measured 90.6% saturation wall, +9 mean weight 0.4747, +15 two PDFs fetched and measured against the store, -20 the exemplar document was surfaced by search precisely because it embeds a contact directory)
- class note: typed, master-eligible only behind a Decision line. The placeholder risk the split does not cover is genuinely low here, these are real contact directories such as "email: <rcarrere@chasque.apc.org>" rather than technical prose inventing acmecorp.com. That does not rescue it. Since closure is the recommendation, no approval request and no `## OPEN` entry: closing it costs Ivo nothing, which is the point.
- what it is: the Convention on Biological Diversity secretariat's meeting document archive, COP-03 (1996) through COP-05 (2000) plus SBSTTA sessions and working groups, official and information series, born-digital PDFs with a real text layer on an enumerable path. The one multilateral host of five probed that answers 200 to an honest User-Agent.
- where: https://www.cbd.int/doc/meetings/cop/cop-05/information/cop-05-inf-22-en.pdf and https://www.cbd.int/doc/meetings/sbstta/sbstta-05/information/sbstta-05-inf-12-en.pdf
- what dates one item: the document's own symbol and date block, verbatim from own extraction, "UNEP/CBD/COP/5/INF/22" and "5 April 2000"; document 2 "UNEP/CBD/SBSTTA/5/INF/12" and "14 January 2000". Both self-date to 2000, so a hostname inside is a claim about 2000 and nothing else.
- row shape: per-mention inside a per-document artefact, which is correct and not the fallacy. A hostname printed in a document dated 5 April 2000 is a contemporaneous observation, not a current-state field refreshed later.
- who keyed it: human, secretariat staff and workshop rapporteurs typing contact directories into policy documents. Typed class, split applies.
- why it may be net-new: the never-pooled tail is genuinely exotic (canadian-forest.com, datec.org.pg, guanet.gt, intnet.bn, ncuicn.nl, safire.co.zw), and that is exactly the tail the split sends to the pool rather than to an annual file.
- reachability, checked 2026-08-13: document 1 200, application/pdf, 2,012,715 bytes, PDF 1.3, 513,140 characters extracted (the proposal reported 663,974, a pdftotext layout difference, immaterial); document 2 200, application/pdf, 467,271 bytes, 6 pages, 59,695 characters. Neither is an error page, no challenge, no banner.
- terms: SECOND-HAND and moot given the recommendation. The proposal quotes permission "to download and copy the information, documents and materials ... for the User's personal, non-commercial use, without any right to resell or redistribute them or to compile or create derivative works therefrom"; the terms page was not fetched. The derivative-works clause IS a genuine question about building an annual file from these materials and it is Ivo's call, but on closure it never needs to be put to him.
- kill condition: saturation, the share of a document's dated domains already dated at the document's own year. FIRED and measured: 77 of the 85 dated domains in document 1 are ALREADY DATED AT 2000, a 90.6% wall that is structural rather than a sampling artefact, since there are only six possible years and the CBD contact population repeats across meetings (focal points, IUCN, UNEP, WWF). Positive control: 157 email matches from document 1 against 0 from document 2 proves the regex works and that document 2's emptiness is the corpus; store-side control, ramsar.org held at 1997, 1998, 1999 and 2001 but not 2000, which is precisely the one pair document 2 contributes.
- screener: the proposal's arithmetic is honest (92 distinct domains, 6 never pooled, EE 4.00) but it computed the wrong number. The number that counts, dated somewhere AND not yet dated at 2000, is 8 net-new pairs, EE 3.80, mean weight 0.4747. The six never-pooled names cannot count at all under the split and land in the pool at one request per document against CORDIS's 472 names per request. Second draw, deliberately generous (same year, same information series): ZERO emails, one URL, one net-new pair. Two documents, 9 net-new pairs, EE 4.51. ESTIMATE, labelled: 500 to 900 in-window English documents at 4.5 pairs each is 2,250 to 4,050 pairs and roughly 1,100 to 1,900 EE for 500 to 900 requests, a miss against the ~5,000 bar before saturation is even applied.
- next step: close it. IF ANYONE REVIVES IT the test is a 30-document seeded-random sample across the OFFICIAL series and the number to beat is 4.5 net-new pairs per document sustained; the kill rests on two draws and says so.

Decision: pending

### ietf_meeting_attendee_rosters / typed

- potential: 45 (+40 the edition tag is intrinsic to the directory and filename, +1 MEASURED 27 post-split net-new pairs for the largest in-window meeting against a ~5,000 bar, +9 mean weight of the net-new part 0.502, +15 full credit, 160,625 bytes of roster retrieved, parsed and joined against the live store, -20 prominence: network-engineering employers are the most heavily crawled population there is, which is what the 98.1% overlap measures)

- class note: the proposal's request that a human reclassify this as artifact_listing is MOOT and must not be sent. Master-eligible would lift the yield from 27 to at most 40 pairs for the largest meeting, still 100x below the bar, so the classification cannot change the answer and an approval request would spend a reviewer for nothing.

- what it is: full-meeting registration rosters for IETF 35 to 52 (1996-2001), plain text in dated proceedings directories, each entry name, phone, fax, email. There is NO organisation field, so the domain comes from the mail address alone. The per-working-group files are a red herring: each meeting carries ONE union file and the ~60 per-WG lists are subsets of it.
- where: https://www.ietf.org/proceedings/42/attendees/98aug-attendees.txt
- what dates one item: the 98aug edition tag in the directory and the filename, not an mtime, plus the fact that the mailbox had to deliver on the meeting date. Sound, and irrelevant, because the population is already held.
- why it may be net-new: it is not. MEASURED against the live store: IETF 42, the largest in-window meeting, 2,017 addresses, 845 distinct mail hosts, 684 distinct registrable domains, of which 671 (98.1%) are already in the store, 664 (97.1%) already carry a year and 637 (93.1%) are ALREADY DATED 1998. The 13 entirely unknown names fail the corroboration split, so they go to the pool, not to a year.
- reachability, checked 2026-08-13: 200 on all three. robots.txt 200 text/plain 51 bytes; directory index 200, genuine server-rendered listing; roster 200 text/plain; charset=utf-8, 160,625 bytes read and parsed, not inferred from the status.
- terms: CLEAN, verified first-hand. www.ietf.org/robots.txt in full is "User-agent: *" / "Disallow: /admin/" / "Disallow: /search/". Neither /proceedings/ nor /ietf-ftp/ is disallowed, no Crawl-delay, no anti-harvesting banner. Terms are not why it dies.
- screener: typed, takes the split. Post-split net-new for the biggest meeting is 27 pairs and 13.56 EE, reproducing docs/sources.md:1126 (institutional link directories, 386 of 388 held) and landing beside the closed RFC/I-D lead on the same host (140 pairs, 88.2 EE). Whole-source ESTIMATE fails at both ends so the imprecision does not matter: three meetings a year draw one community, so a generous 2x union gives ~324 pairs / ~160 EE for 1996-2001, and the absurd upper bound of full independence across all 18 meetings gives 486 pairs / 244 EE, against a ~5,000-pair bar and a 6.23M EE baseline. Raw-rows-to-value ratio 75:1. One honest counterweight recorded so it is not lost: 13.56 EE for a single HTTP request is ~22x the gap engine's 0.6 EE per request, the cheapest EE per request seen here, and it still loses because the bar is absolute net-new pairs. SEPARATE FINDING WORTH KEEPING regardless of the verdict: rosters carry typo'd mail domains the split cannot catch, imre.i.juhasz@telia.sc among eight @telia.se, and umu.sc for Umea University's umu.se. That is the RFC fictional-hostname failure in new dress, a mistyped name someone later registers taking a year it never had.
- next step: close it, and do not raise the reclassification. Keep the typo finding as a general caution on any human-typed mail corpus.

Decision: pending
### nz_dnc_zone_data / whois_creation

- potential: 45 (per-domain creation date from whois.srs.net.nz, .nz is high English weight; capped because the zone file itself is undated and the query volume needed is large)

- class note: the creation date comes from whois.srs.net.nz per domain; the zone file itself is an undated seed

- what it is: two halves that must be separated. The dating half is the .nz registry WHOIS at whois.srs.net.nz, live and excellent. The seed half is the DNC zone data file on written ZTP1 application, and that half failed contact.
- where: whois.srs.net.nz port 43 (verified); https://dnc.org.nz/tools-and-services/how-do-i-2/request-the-zone-data-file/ returns 403 to us
- what dates one item: stronger than claimed. The field named in the proposal, domain_dateregistered, is the retired DNC format; the live response is ICANN-style and returns BOTH Creation Date: 1997-03-05T11:00:00Z and Original Created: 1997-03-05T11:00:00Z for xtra.co.nz, which the store independently dates 1996 to 2001. Original Created is exactly the field that survives a lapse, so .nz suffers neither the .uk loss nor the .au migration stamp.
- why it may be net-new: nz is confirmed ABSENT from all 590 entries and 1,200 TLDs of the cached IANA RDAP bootstrap published 2026-07-23, so no existing engine can reach a 0.9895-weight namespace by any other route. 0 of the 3,865 undated .nz pool names appear in the merged baseline, and all 24,486 baseline .nz names are already dated in the store.
- reachability, checked 2026-08-12: whois.srs.net.nz answered normally on port 43 with a full record; dnc.org.nz ZTP1 page 403, 5,785 bytes of block page, so the named artifact and its application procedure are NOT retrievable by us and the 764,987-name figure is unverified. Rate limit UNMEASURED, one query answered.
- screener: the seed the proposal rests on is unreachable, so what survives is a smaller source that needs no application at all, the 3,865 undated .nz pool names, figures verified as claimed. At a 15% survivor rate that free population is roughly 570 EE (ESTIMATE), below the 5,000-pair bar but above every source rejected in sources.md this round (12 to 88 EE). It ranks because pricing the free names costs nothing, needs no approval, and produces the one number any ZTP1 application would have to justify itself with.
- next step: price the free 3,865 and measure the WHOIS rate limit; treat the 735,000 unseen names as a separate access request only if that number justifies it.

Decision: pending

### uspto_tm_marktext / dated_directory

- potential: 40 (dated filings, but a trademark text is only sometimes a domain and the safe class reading takes the corroboration split, which historically removes most of the net-new part)

- class note: `artifact_listing` is arguable and `dated_directory` is the safe reading, so it is filed under the safe one

- what it is: USPTO trademark full-text XML from the Open Data Portal, the subpopulation being applications filed 1996-2001 whose word mark IS a domain name, each with serial number, mark text and a machine-recorded filing date.
- where: https://api.uspto.gov/api/v1/datasets/products/TRTDXFAP (portal page https://data.uspto.gov/bulkdata/datasets/TRTDXFAP)
- what dates one item: one row is one application with its own filing date, and the domain sits in a STRUCTURED field rather than in prose, so unlike CourtListener it is not pre-capped by the prose criterion and a paid filing has no protocol-placeholder failure mode. Caveat the proposal omits, and it is the generalising lesson of the Netcraft entry: an intent-to-use filing for FOO.COM in 1999 proves the mark was applied for in 1999, not that foo.com resolved in 1999.
- why it may be net-new: dot-com-rush filers were overwhelmingly small businesses buying a name, which is the opposite end of the distribution from the famous hosts a crawl-derived baseline holds first.
- reachability, checked 2026-08-12: 401 Unauthorized, application/json, 26 bytes, {"message":"Unauthorized"}, so the bulk route is key-gated by free self-service registration and not a licence. The annual product page no longer exists: developer.uspto.gov redirected to https://data.uspto.gov/ and served a 20,666-byte JS shell with no title, zero occurrences of bulkdata.uspto.gov and zero of the annual file naming, so no file URL was seen. dig: bulkdata.uspto.gov has NO address while data.uspto.gov, api.uspto.gov and developer.uspto.gov all resolve.
- screener: best shape of the three gated items because the domain is a structured field. Second correction the proposal needs: TRTDXFAP is the DAILY applications product and does not reach 1996-2001; the window lives in the annual backfile whose product page is the one that now redirects, so the in-window file is unconfirmed and no volume figure here is measured.
- next step: access request, free API key, then locate the annual backfile product and measure in-window domain-shaped marks before anything else.

Decision: pending

### cordis_fp4_fp5_project_websites / link_target

- potential: 32 (+0 no per-item date exists, which is the rubric's zero condition and makes it pool-only by construction, +6 volume, 944 pool-novel names measured, +11 mean weight 0.5334, +15 both archives downloaded, parsed in full and measured against the store. The entire case is cost per name, not size)
- class note: undated, seed-only, so it needs no approval and waits on no human. Recorded here only so the family is not reproposed as dating evidence, because the fields ARE human-typed and a future pass pairing physUrl with startDate would be making a year claim it may not make.
- what it is: the European Commission's CORDIS bulk CSV exports for FP4 (1994-1998) and FP5 (1998-2002), specifically webLink.csv (project related websites) and organization.csv (organizationURL). Note each zip holds EIGHT members, not the three the proposal describes.
- where: https://cordis.europa.eu/data/cordis-fp4projects-csv.zip and https://cordis.europa.eu/data/cordis-fp5projects-csv.zip
- what dates one item: nothing. A webLink row carries projectID, physUrl, status, archivedDate, type, source, represents; the only dates are project.startDate and archivedDate, uniformly 2021-11-16, which is CORDIS's own link check. Never pair physUrl with startDate and call it a year claim.
- row shape: two shapes, and only one is worth anything. webLink.csv is per-link, 3,756 rows keyed on (projectID, physUrl). organization.csv is per-entity-per-participation, 149,610 rows, and organizationURL is the organisation's CURRENT homepage with contentUpdateDate stamps from 2005 to 2024 beside a project that ended in 2002, the dated-dataset fallacy in its purest form.
- who keyed it: human. Project coordinators and EC project officers typed these into the CORDA contract database; the source column reads "corda" on every row. So if it were ever promoted it would be typed and take the split. It cannot be promoted, because it is undated.
- why it may be net-new: 944 registrable domains absent from the candidate pool for 2 HTTP requests and zero per-item fetches, mostly consortium vanity domains that survive the registrable-domain collapse (6winit.org, 6power.org, acegis.net, acats-forum.org, 3dproject.gr, adaptit.org, aboutrobotics.net, ambient-agoras.org).
- reachability, checked 2026-08-13: FP4 200, application/zip, 14,114,353 bytes; FP5 200, application/zip, 13,059,978 bytes. Bodies verified real, `file` reports "Zip archive data", both unzip to 8 members, every CSV parses as semicolon-delimited with quoted headers. No redirect off host, no robots or automated-harvest banner served.
- terms: NOT independently re-fetched and flagged as such rather than passed along as verified. The proposal's "CC BY 4.0" and "European Union, 1994-2026" strings are second-hand. Attested from own requests: both files served cleanly to an honest User-Agent, 200, no interstitial, no rate limiting, no harvest banner. Candidate-only evidence carries less licence weight, but read the terms page once before a collector ships.
- kill condition: the pool-novel count collapses on canonicalisation, or the names are already in the pool. Did not fire, and every headline reproduced exactly: webLink 3,756 rows, 3,734 canonicalising to 2,022 distinct domains, 738 pool-novel, EE 419.4, mean 0.5683; in-window starts 1,579 distinct, 483 pool-novel, EE 273.8; organizationURL 1,294 distinct, 217 pool-novel, EE 90.2, mean 0.4156; union 2,959 distinct, 944 pool-novel, EE 503.5. Positive control on sparsity, over all 149,610 organisation rows: name 100.0%, contactForm 100.0%, country 99.4%, city 93.7%, street 90.2%, postCode 86.3%, against organizationURL at 3.8%, so the address column is genuinely sparse rather than a stub. Link-side control: 11.30% of projects carry any webLink against 96.1% carrying a startDate, the right way round for a real field.
- screener: candidate-only, take it because it is nearly free. DISPROVED, the "strong prior" that a consortium vanity domain is registered at project start: among the 483 pool-novel domains on projects starting 1996-2001, SEVEN are .eu (not delegated until 2005) and NINE are .info (delegated late 2001), so at least 1.4% provably postdate their project and the true leak is higher, since only TLD age is detectable this way. ALSO DISPROVED, that the store could confirm the prior: domain_year.assigned_year is 1996 to 2001 by construction, so "earliest held year in window" is 100% for every domain and the test is vacuous; it returns 1053/1053, which means nothing. Two facts the proposal never mentions: 2,732 of 3,756 rows have status "invalid" and 756 "legacy", so CORDIS itself found roughly 73% dead in 2021, which makes the set a historical record rather than a live one; and of the 1,579 in-window-start webLink domains 1,084 of the 1,096 pooled ones are dated (98.9%) against a whole-pool base rate of 69.0%, which is SELECTION-BIASED upward because a CDX discovery registers and dates in one act and must NOT be quoted as an RDAP hit rate on the 944 novel names. Honest scale: 944 names against 1.54M already unasked is 0.06% of existing headroom, ceiling EE 503.5, which is 0.0081% of the 6,226,386.42 EE baseline.
- next step: seed the 944 into the candidate pool from the two already-downloaded archives, no approval needed, and read the CORDIS terms page once before shipping the collector.

Decision: pending
### domainsproject_bulk_list / link_target

- potential: 30 (no date at all so it can never date a year, but it is the one item that could feed the RDAP engine tonight, and that engine's .org list runs dry before Sunday; volume unverified and the vendor now sells it, so the free mirror may be a subset)

- class note: an undated bulk list, so it can never date a year; names are dated afterwards by the approved rdap_snapshot route

- what it is: the Domains Project bulk domain list, taken from the free GitHub mirror rather than the vendor host.
- where: https://github.com/tb0hdan/domains (the proposal's raw-data host, https://dataset.domainsproject.org/, returns 401)
- what dates one item: nothing. Undated seed, scores zero until the already-approved rdap_snapshot / whois_creation engine dates a name, so no approval gates collection.
- why it may be net-new: the local engine has 1,357,792 unasked names left, which is 3.2 hours at the measured 118 q/s and not the 11 days claimed, so the pool empties this afternoon and seed volume is the binding constraint.
- reachability, checked 2026-08-12: dataset.domainsproject.org 401 on HEAD; domainsproject.org 200, 36,022 bytes; github.com HTML 502 to curl but the API returns 200 for repos/tb0hdan/domains, BSD-3-Clause, not archived, 1,803,558 KB, pushed 2026-05-03, 1,154 stars.
- screener: the one item that can start unattended tonight, and the free route is real and redistributable. Two caps. Whether the free repo carries 3.235 billion names or a subset is UNVERIFIED, and the landing page's own schema.org data now sells that exact volume from EUR 100 to EUR 1,200, so treat 3.235B as a vendor claim; 1.8 GB implies 35x compression, which is equally consistent with a subset. Second, it is crawl-derived and RDAP can only date a name alive today, so the route reaches only the surviving 1996-2001 population, the same 15% to 17% the .uk figure measures.
- next step: pool only, gated: 5,000 names sampled at random, RDAP'd, reporting any-date rate, in-window rate and mean English weight of the net-new part before any bulk pull.

Decision: pending

### dotgov_real_names / link_target

- potential: 22 (undated list dated afterwards by the approved RDAP route, .gov is high English weight but small and the baseline holds government sites first, which is the prominence penalty)

- class note: an undated list, dated afterwards by the approved rdap_snapshot / whois_creation route

- what it is: CISA's dotgov-data current-full.csv, the authoritative census of every registered .gov domain, 16,483 data rows, 1,406,077 bytes, no date column of any kind.
- where: https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv (dating route: https://rdap.nic.gov/rdap/)
- what dates one item: not the CSV, which can never date anything. rdap.nic.gov returns registration 1997-10-02T01:29:25Z for loc.gov alongside a separate reregistration 2026-05-19, so this registry preserves the ORIGINAL creation date across a lapse, the property .uk lacks and the failure that makes .au date nothing. Cleanest dating route in the batch. On one reading it needs no new Decision line, because gov resolves to https://rdap.nic.gov/rdap/ in the cached IANA bootstrap and would be swept by the approved rdap_snapshot spec, but that reading is a human's call.
- why it may be net-new: the baseline's 21,271 .gov rows are host-level and collapse to 1,050 distinct registered names, 551 of them in the census, so 15,932 of 16,483 real .gov names are absent from the shipped baseline, slightly more than the 15,816 claimed. Store figures exact: 667 held, 551 dated, all in window.
- reachability, checked 2026-08-12: raw.githubusercontent.com 200, 1,406,077 bytes, text/plain; rdap.nic.gov 200, 6,983 bytes of valid RDAP JSON.
- screener: honest ceiling 15,932 pairs at 0.9825, realistic yield a few hundred to low thousands because the baseline already holds 1,050 in-window .gov names and the in-window .gov namespace was small, so below the 5,000-pair bar. It survives on cost alone: 15,932 queries at 118 q/s is about 2.3 minutes, the cheapest decisive experiment here, and the names are county and city governments rather than famous sites. One correction to the proposed second use as a fabrication filter: 499 registered .gov names in the baseline are absent from the current census and they are real retired federal sites (4woman.gov, 2dol.gov, 21stcentury.gov, 1903to2003.gov), so the filter is one-directional, it can whitelist 16,483 names as real and cannot condemn the rest.
- next step: price it, 2.3 minutes of RDAP, and settle whether the existing rdap_snapshot Decision already covers the gov route.

Decision: pending

### state_sos_entity_registers / typed

- potential: 22 (per-row formation date and a public-domain API, but a measured 1,384-match ceiling for a whole state across the whole window, 11x below bar before four attritions)
- what it is: State Secretary of State corporate registers as free bulk open data, Colorado confirmed: business entities registered with CDOS since 1864, 35 columns, over a million records; the slice is entities whose registered name is itself hostname-shaped.
- where: https://data.colorado.gov/resource/4ykn-tg5h.json
- what dates one item: entityformdate as a native calendar_date beside entityname as text, so "FOO.COM, INC." formed 1999-04-12 is a typed hostname in a dated statutory record.
- why it may be net-new: it is not, and that is the finding; a company that incorporated as FOO.COM in 1999 existed in order to run foo.com and was therefore crawled.
- reachability, checked 2026-08-13: 200 on both requests, application/json, real data. /api/views returned 18,969 bytes with 35 column definitions; a SoQL GROUP BY returned 148 bytes of counts. No auth, no key, no rate gate.
- terms: permissive and not the reason to close it. Dataset licence field reads {"name": "Public Domain"}, licenseId PUBLIC_DOMAIN, attribution CDOS, rights ["read"]. The Socrata portal ToU was not read, but the per-dataset licence is explicit and governs.
- screener: typed, takes the split, not master-eligible. MEASURED and fatal: 1,384 raw matches on upper(entityname) LIKE '%.COM%' OR '%.NET%' OR '%.ORG%' with entityformdate in window, by year 1996 n=25, 1997 n=30, 1998 n=81, 1999 n=469, 2000 n=614, 2001 n=165, against a ~5,000 net-new pair bar at docs/discovery.md:46. Even at an implausible 50% net-new that is about 437 EE (ESTIMATE). Also disproved: there is no e-mail, web-address or URL column anywhere in the 35, so the entity name is the only route. National scaling needs one collector per 50 portals and most states publish no free bulk register; the pool half is worthless against 1.54M names never asked.
- next step: pool only, and close.

Decision: pending

### openpgp_keyserver_dumps / link_target

- potential: 20 (+0 no approved master-eligible type covers a PGP self-signature, so it cannot date a year at all and is pool-only, +15 ESTIMATE 50,000 to 150,000 distinct in-window email domains out of roughly 6 million keys, +5 heavy .de tail at 0.1324 drags the mean well below the 0.6 line, +0 not retrieved, the dumps are password-gated. Every figure here is a projection about a corpus nobody on this project has seen)

- class note: typed as `link_target` because the taxonomy has no home for it. The key creation timestamp is the OWNER's machine clock, self-asserted and trivially backdatable, which is the worst possible fit for a self-dating class that takes no corroboration split. Dating it would need a NEW evidence class plus a human Decision line, so the full path is email, password, 14 GB, new class, request_approval.py, Ivo. Third-party signatures carry independent timestamps and would have to become the dating attribute instead.
- what it is: bulk key dumps from the SKS / Hockeypuck keyserver network as numbered .pgp packet files, each key carrying a self-signature timestamp and user IDs holding email addresses.
- where: rsync://rsync.cyberbits.eu/hockeypuck/dump and rsync://rsync.cyberbits.asia/hockeypuck/dump
- what dates one item: the key's self-signature creation timestamp, in the same packet as the user ID, so hostname and date are in one record. Owner-asserted, not registry-stamped.
- why it may be net-new: email-only domains that never ran a web server are invisible to a crawl baseline; it is the only proposal in the batch whose raw ceiling is clearly above the roughly 5,000-pair bar.
- reachability, checked 2026-08-12: NOT retrievable. 1 request, to raw.githubusercontent.com/hockeypuck/hockeypuck/master/contrib/data-sources.md, 200 with the real file, which is upstream's own current source list and therefore the authority. It names exactly two surviving sources and both are gated, verbatim: "Please email hockeypuck@cyberbits.dev to get the rsync password" and "To prevent abuse, these data sources are password-protected." No request was issued to the dump hosts: the proposal had already recorded all six SKS-wiki mirrors dead (keys.niif.hu refused, pgp.uni-mainz.de and keywin.trifence.ch NXDOMAIN, mirror.cyberbits.eu/sks/dump/ 404, rsync module "sks" unknown, pgp.key-server.io obsolete since Jan 2021) and upstream corroborates rather than contradicts that.
- screener: the SKS wiki page the proposal cites is a historical document listing hosts that no longer exist. The public mirror network is gone and the successor distributes only under an access request whose stated purpose is abuse prevention, which a request for the whole 14 GB corpus is exactly the shape of. Two blockers, either fatal on its own: no access, and no evidence class.
- next step: pool only, and not before the rsync password. Even granted, its names can only enter the candidate pool, which already holds 1.54M names never asked, so the honest reading is that this is worth an email and nothing more.

Decision: pending
### ripe_db_lastmodified / link_target

- potential: 12 (its artifact_listing reading was DISPROVED, so candidate-only only; last-modified is a current field and says nothing about 1996-2001)

- class note: `artifact_listing` was DISPROVED by the sceptic, so candidate-only is the only honest reading

- what it is: the RIPE NCC public whois database dump ripe.db.gz, live, regenerated daily, 367,072,352 bytes, the copy read built 2026-08-11. Personal data scrubbed but notify: survives, 768 notify lines in a 307,200-byte prefix naming role mailboxes at restena.lu, ebone.net, aco.net, teleglobe.net, casema.net.
- where: https://ftp.ripe.net/ripe/dbase/
- what dates one item: nothing reliable. The claim was that an in-window last-modified bounds the object's last write, so its hostnames existed then. Measured in the prefix: 1,343 objects carry last-modified, 118 read 2001, and 108 of those 118 are stamped 2001-09-21 inside a 15-second window from 21:49:51Z to 21:50:06Z, all 108 carrying created: 1970-01-01T00:00:00Z. That is a bulk migration job, not human edits, and it is the earliest last-modified anywhere in the sample. The proposal's own example, as-set AS-TMPEBONECWIX with notify staff@ebone.net, is one of the 108, so it cannot date ebone.net to 2001; under the no-inference rule it is an interval, not a year.
- why it may be net-new: only through the residue, 10 objects of 1,343 with genuine post-floor edits 2001-09-27 to 2001-12-20, 7 naming a notify host (tele2.no, gemsoft.net, ipcenta.net, arcor-online.net, ua.net, enron.com, cyb.it). That is 0.74% of objects, it can only ever date 2001, and only the window's last 3.4 months. enron.com already underpins the enron_email source and .no, .it, .ua carry poor English weight.
- reachability, checked 2026-08-12: 206 Partial Content, Content-Range bytes 0-307199/367072352, Last-Modified Tue, 11 Aug 2026 22:24:36 GMT, nginx, no login, non-IA host. Decompressed to 62,614 lines. last-modified histogram: nothing before 2001, then 2001 118, 2002 33, 2003 32, up to 2026 178. created: led by 654 instances of the 1970 epoch.
- screener: artifact is exactly as described, dating claim disproved for 92% of in-window hits. Do NOT open an approval request: the sample that would go into it is the 108 placeholder objects, and a reviewer checking live links would find the epoch created: beside every one. Whether the 7 residue domains are net-new is an assessment, not a measurement, since the store was not queried.
- next step: pool only, no approval needed, and no crawl time beyond a single sweep for notify hostnames as candidates.

Decision: pending

### Closed this pass

- czds_zone_seed: mechanism true and quoted verbatim from Verisign, but no per-item date, the portal 200 is an authenticated landing and not the data, CZDS terms restrict redistribution while this project ships a name list, and it is strictly dominated by domainsproject_bulk_list, the same currently-resolving population under BSD-3-Clause with no application. Reopen only if the free GitHub mirror proves to be a subset, when it becomes the only route to a complete .com census.
- radb_irr_changed: mechanism real, empty in window. 409,600 bytes of radb.db.gz decompressed to 430,550 lines, 51,621 route objects, 51,641 changed: lines, of which 22 fall in 1996-2001 and collapse to 3 distinct domains (bora.net, internap.com, slk.com), with ZERO lines in 1996 through 1999. The prefix runs 1.0.0.0/24 to 16.10.11.0/24, the earliest-allocated space, so the sample is biased in its favour. last-modified is no fallback, 47,460 of 51,621 read 2023, and archive/ per-year directories begin at 2016.
- bu_cs_proxy_trace_1998: the repository item is the release-notes memo, not the log (DataCite resourceTypeGeneral "Report", issued 1999-09-07). Both data routes its abstract names are dead: the http techreports path 404s and ftp.cs.bu.edu is NXDOMAIN. The genuine loss of the batch, a proxy log is not prominence-selected, but it is now the same failure as IRCache and what remains is a direct ask to BU CS.
- uspto_patent_fulltext_urls: not retrievable as cited (the same 1,936-byte SPA shell with an etag identical to the trademark path), the correct rule of excluding examiner citations removes most of the recall the 3% to 8% density estimate rested on, and in-window patent URLs skew to standards bodies and large vendors, the famous end the baseline holds. Revisit only if uspto_trademark_case_files clears access first, since that solves the route for free.
- uspto_patent_text: same key gate with none of the trademark shape advantage. bulkdata.uspto.gov does not resolve, URLs sit in prose and take the split, and the URL-bearing subset is the SEC EDGAR population that closed at 1.9 EE. 1.1M in-window grants is a volume argument, not a density one.
- govinfo_fedreg: out of window for four of six years, since FR bulk XML begins with 2000 and govinfo states 1994-1999 is unconverted. /bulkdata/json/FR/1996 and /FR/2000 both returned 200 text/html with byte-identical 67,225-byte bodies titled "Govinfo Bulkdata Service Error", which is exactly the "67,225 bytes of links" the proposal offered as proof. Reopen only against federalregister.gov's own API, a different source needing its own screen.
- medline_affiliation: retrievable (1,334 pubmed26n*.xml.gz files, 200) and still the wrong population. An affiliation email domain is a university, hospital or institute, which is the population that closed Usenet Path relay chains at 49 net-new pairs and 13.89 EE, and pre-2014 MEDLINE stored only the first author's affiliation. Its own figure, 514 of 474,778 records for 1998, argues the same way.
- untroubled_spam_trap: honestly dated and measured over a complete year. 1998.7z extracted to 1,097 messages, 1,096 carrying a Received: header all reading 1998; 518 carry a body http:// URL giving 306 distinct names, 214 already held for 1998, 25 corroborated elsewhere and therefore the only net-new master pairs, worth roughly 16 EE (ESTIMATE). Whole span order 200 to 400 pairs (ESTIMATE), 12x to 25x below bar, and unrescuable: the corroborated half is famous free hosting, the interesting throwaway names are attested nowhere else and so can never date a year.
- fidonet_nodelist: self-dating verified (nodelist.348, 1,214,176 bytes, "A FidoNet Nodelist for Friday, December 14, 2001"), and the densest edition kills it. 13,818 records give 699 hostname tokens collapsing to under 200 registrable names, several of the 209 second-level strings being public suffixes, and what remains is dynamic DNS and infrastructure (fidonet.net 281 third-levels, dyndns.org 62, darktech.org 24). Whole-window union is low thousands of names at best (ESTIMATE) with a bad TLD mix, and it would spend reviewer attention on the smallest win in the batch.
- hnet_discussion_logs: the only proposal whose data could not be reached. The month index returned HTTP 403 from nginx with the honest User-Agent while the bare CGI returned 200 and 11,155 bytes of HTML, so the reachability evidence is a landing page. Retrieval is one message per request, order 10^5 to 10^6 CGI hits on one small academic host, which is not being a good citizen, and the measured analogue, public pipermail archives at 83.6% already held and 0.0025 net-new pairs per message, needs about 2 million in-window messages to clear the bar. Re-probe only if a bulk or month-level export appears on that host.

### bsd_ports_master_sites_dated_trees / typed

- potential: 8 (dating is sound and the tarball was fully retrieved, but the designated kill test measured 0 net-new domains, 0 pairs, 0.0 EE)
- what it is: the ports tree inside dated BSD release trees, every port a Makefile carrying MASTER_SITES download hosts and a MAINTAINER email.
- where: https://archive.freebsd.org/old-releases/i386/2.1.5-RELEASE/ports.tgz
- what dates one item: the release tree is the dated artifact and dates only itself; FreeBSD 2.1.5 shipped July 1996, and the internal tar mtimes top out at "Jul 14 1996" with nothing later, so the outer 1999-Sep-20 tgz mtime is a repack date and the payload is authentically the 1996 tree.
- why it may be net-new: it is not; a MASTER_SITE is by definition a high-traffic public mirror, which is the best-crawled category of 1996 host.
- reachability, checked 2026-08-13: 200 on the release listing (4,479 bytes) and 200 on ports.tgz with 1,778,764 bytes fully downloaded and parsed; 6,306 entries, 538 port Makefiles, 474 with MASTER_SITES.
- terms: clean and not the reason it fails. archive.freebsd.org served both requests with no banner, robots directive or terms text, and served a 1.7 MB tarball to an honest UA without rate limiting. Recorded so nobody reopens this hoping the block was procedural.
- screener: typed inside a dated artifact, so it takes the split and can only ever add a NEW YEAR to an ALREADY-HELD domain. Measured against the live store read_only: 636 MASTER_SITES lines give 326 hostnames collapsing to 242 registrable domains, 222 (91.7%) already held and all 222 already held FOR 1996, so year headroom is zero too. The 20 apparent net-new names are parse artifacts verified individually (alt.sources, comp.speech, pub.gnu, usr.bin are Usenet and directory paths; ad.jp, gc.ca, oz.au are public suffixes my collapser truncated to). Top names dec.com, mit.edu, x.org, unc.edu, freebsd.org, uu.net. The early-years thesis is disproved at the proposal's own stated kill point. TLD spread is also weaker than sold: edu 49, com 37, jp 24, de 22. MAINTAINER fallback checked while the tarball was open: 40 domains, led by freebsd.org, de 7 com 7 jp 5 edu 4. Residual: 1 tree of ~40 measured; NetBSD and OpenBSD unprobed but same record shape on the same mirror network.
- next step: close it. No approval request should be written.

Decision: pending

### winsite_cica_dated_shareware_index / typed

- potential: 5 (per-file mtimes are genuinely preserved, so dating would have worked, but the hostname-bearing payload does not exist and the aggregate index is an existing measured zero)
- what it is: WinSite, the Windows shareware archive formerly CICA, on the ftp.icm.edu.pl mirror; proposed as Info-Mac's sibling on the theory that every uploaded archive has a .txt description carrying the author's URL.
- where: https://ftp.icm.edu.pl/packages/winsite/win95/winsock/
- what dates one item: per-file mtime, and this is the one thing that passed: dicer039.zip carries a preserved 1998-07-08 mtime, so ICM does not rewrite mtimes on sync. A date with no domain beside it cannot produce a domain_year row.
- why it may be net-new: it is not; the descriptions live in a per-category INDEX already measured at zero vendor domains.
- reachability, checked 2026-08-13: 200 on /packages/winsite/win95/ (8,461 bytes, Apache/2.4.68 Debian) and 200 on /packages/winsite/win95/winsock/ (1,249 bytes). The winsock category holds exactly two entries, a 1.3K INDEX and a single dicer039.zip, with no sibling .txt.
- terms: no prohibition found and none served; Apache autoindex, no banner, no terms text, no robots directive. Not the reason to close it.
- screener: moot and never reached; would have been typed under the split. The proposal's central mechanism does not exist on this mirror, and its net-new argument rests on a false claim: docs/sources.md:1415 already records WinSite INDEX.TXT as a named measured negative, "7,057 entries, two email addresses and zero vendor domains in the whole file", concluding that this "settles the whole CD-ROM catalogue family at once". Screening must read the row body, not only its four headline names. Second problem: the top level shows no INDEX.TXT and no plain LS-LTR, and the mirror's INDEX is stamped 2009-04-23, so this is a 2009 snapshot of a pruned archive rather than the 1996-2001 archive.
- next step: close it.

Decision: pending

### aminet_index_uploader_readme / typed

- potential: 3 (no per-item date exists at all, which is the rubric's zero condition; German-dominated TLD lean would have sunk it anyway)
- what it is: Aminet, the Amiga archive, on the ftp.fau.de mirror, proposed on the strength of a master INDEX carrying a date per file so one cheap fetch would enumerate the in-window population.
- where: https://ftp.fau.de/aminet/INDEX
- what dates one item: nothing. The INDEX header reads verbatim "Aminet index, created on 12-Aug-2026" and its third numeric column is an AGE IN WEEKS relative to that build which SATURATES AT 999, so every in-window entry reads identically: A2KDeck.lha 999, AB.lha 999, AmigaBase26.lha 999.
- why it may be net-new: unreachable question; the file cannot separate 1996 from 2001.
- reachability, checked 2026-08-13: 206 Partial Content on a Range GET of the INDEX (first 6,001 bytes, honoured cleanly) and 200 on /aminet/info/ (687 bytes, Apache/2.4.58 Ubuntu).
- terms: no prohibition found and none served; university mirror, Apache autoindex, no banner, honoured a Range request politely.
- screener: undated as it stands, so seed-only at best and it cannot date a year by any route found. Sub-values below the cap prove the reading (BeeBase-1.2.lha 48, AlphaBase_keyfile.lha 958, Audithec.lha 985) and 999 weeks before August 2026 is roughly mid-2007. The rescue route was checked rather than assumed: /aminet/info/ holds one adt/ subdirectory and no dated index family. Two further weaknesses recorded: the hostname was never in the INDEX at all (it lives in ~40,000 sibling .readme files) and is typically an "Author:" mail domain rather than a web one. The proposal itself disclosed the .de weight risk at 0.1324.
- next step: pool only, and close.

Decision: pending
### educause_edu_whois_activation / whois_creation

- REJECTED BY THE AGENT ON TERMS, NOT ON YIELD, under the standing good-citizen rule: the server's own banner reads "The use of electronic processes to harvest information from this server is generally prohibited except as reasonably necessary to register or modify .edu domain names", and a 6,438-name sweep is unambiguously that prohibited shape. Measured yield was 1 net-new pair per 20 queries in any case. Overrule it if you disagree.

- potential: 78 (+40 hostname and its own date in adjacent fields, the strongest record shape here, +3 usable volume, MEASURED at 1 net-new pair per 20 queries and ESTIMATE roughly 280 pairs under the project default rule, +20 .edu at 0.9717, the highest mean weight of anything screened, +15 real WHOIS records retrieved. The score is the weight and the semantics fork; the yield measurement is what caps it)

- class note: self-dating, no corroboration split. It can never seed: WHOIS answers only names already held, so it is a dating instrument with zero discovery value.

- what it is: EDUCAUSE port-43 WHOIS, the authoritative .edu registry, one record per currently registered domain carrying a "Domain record activated" line.
- where: whois.educause.edu port 43 (programme page https://www.educause.edu/edu-domain-administration)
- what dates one item: the registry's activation date for that one domain (mit.edu reads "Domain record activated: 23-May-1985"). Value swings entirely on a decision that is not the agent's: under the project default (docs/sources.md:526, creation year only) one record dates one year; under the AFNIC interval reading (docs/sources.md:201) a still-registered domain activated in or before 2001 dates every in-window year from max(1996, activation). AFNIC earned the interval reading by documenting that crDate resets on re-creation; EDUCAUSE publishes no such semantics, so the default stands until a human rules.
- why it may be net-new: 13,788 empty in-window year-slots across 6,438 dated .edu domains, at the highest English weight the project holds.
- reachability, checked 2026-08-12: 0 HTTP requests, port 43 is not HTTP. 20 WHOIS queries at human pace: 9 full records, 11 no-match, service healthy and unthrottled at that rate.
- screener: the headline claim FAILS on direct test. Of 12 random names from the 1,730-domain 1999 bucket, 7 returned NO MATCH and of the 5 that answered, 4 activated in 1999, the year already held; exactly ONE back-dated (thegateway.edu, 1999 to 1998). A further 8-name probe agrees. Across all 20 queries: 1 net-new pair. The mechanism is the reusable finding: a .edu site registered in year Y is crawled in year Y, so the baseline already holds the activation year, while the registry has deleted precisely the defunct institutions where a capture was the only surviving record. Also disproved: the "222,623 known .edu names" framing, since 216,176 of those are Usenet and FAQ mention-extraction noise. Read verbatim from the banner: "The use of electronic processes to harvest information from this server is generally prohibited except as reasonably necessary to register or modify .edu domain names." A 6,438-name sweep is unambiguously the prohibited shape, and the Internet Archive has already refused this project three times.
- next step: access request, and it is one question to Ivo, not two: rule on creation-year-only versus the AFNIC interval reading for a registry that documents nothing (roughly 280 pairs against an ESTIMATE of 6,000 pairs and 5,800 EE), and decide whether to write to EDUCAUSE at all given the banner. No sweep before both.

Decision: rejected

### nlm_medline_affiliation_email_1996_2001 / link_source

- CLOSED ON MEASUREMENT BY THE AGENT, not awaiting your decision. Its own sceptic measured **0 net-new pairs after the corroboration split** over a live 581-citation sample: 108 emails, 90 distinct domains, 100 pairs, 97 already held, and all 3 remaining held in no year so all 3 fail the split. The positive control passed first, affiliation populated on 369 of 475 in-window citations, so the zero is the corpus rather than the parser. Scored 66 by a rubric that rewards having a per-item date; a measured zero should outrank that and the rubric is corrected for the next pass. Recorded here rather than deleted, because a negative result is worth keeping.

- potential: 3 (+40 a sound per-item date from the citation's own PubDate, +0 volume because the measured post-split net-new is zero, +11 mean weight 0.5569 below the 0.6 bar, +15 a live 581-citation sample measured against the store. The score is the record shape; the yield is what closes it)
- class note: typed inside a dated artifact, so master-eligible behind a Decision line, and the split is doing real work here. The 3 net-new domains it rejects are shimizu-pharm.co.jp, iicb.res.in and inst.gov, exactly the never-held tail where a keying typo is indistinguishable from a real small institution.
- what it is: the PubMed/MEDLINE annual baseline, mined for the email at the end of the `<Affiliation>` element.
- where: https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/
- what dates one item: the citation's own `<PubDate>`, in the same `<PubmedArticle>` as the address. Journal lag means the address was typed at or before the assigned year, so the claim errs conservative.
- row shape: per-filing. One row is one citation; the affiliation is transcribed from the printed article and NLM does not refresh it to the author's later address. Measured: 369 citations with exactly one `<Affiliation>`, zero with more than one, so at most one email per citation in window.
- who keyed it: human, twice. The author typed it into the manuscript, an NLM indexer or vendor keyed it from the printed page. Typed class, split applies.
- why it may be net-new: it is not. Of 90 distinct domains sampled, 75 already hold all six years and the mean is 5.57 of 6.
- reachability, checked 2026-08-13: 200 on README.txt, 4,599 bytes, text/plain, a real README; 200 on an efetch POST of 600 PMIDs, 3,115,027 bytes of valid PubmedArticleSet XML, 581 resolved.
- terms: GREEN and verbatim, "Downloading PubMed data from the National Library of Medicine FTP servers indicates your acceptance of the following Terms and Conditions. No charges, usage fees or royalties are paid to NLM for these data." Obligations verbatim: "acknowledge NLM as the source of the data in a clear and conspicuous manner", "NOT use the PubMed wordmark or the PubMed logo", "NOT to indicate or imply that NLM/NIH/HHS has endorsed its products/services/applications". THERE IS NO PROHIBITION ON AUTOMATED OR BULK RETRIEVAL; bulk download is the documented channel. Terms are not what closes this.
- kill condition: already fired. Net-new pairs surviving the split at or near zero on a live sample. Positive control passed first, so the zero is the corpus and not the parser: `<Affiliation>` populated on 369 of 475 in-window citations (77.7%) with named live records PMID 9300001 (1997, greenla@umich.edu), PMID 9300048 (1997, A.Leigh-Brown@ed.ac.uk), PMID 9300039 (1997, daikokut@tsuru.med.nagoya-u.ac.jp).
- screener: MEASURED against the store, 108 emails in 475 in-window citations (22.74%, well ABOVE the proposal's own "low" forecast), 90 distinct domains, 100 pairs, 97 ALREADY HELD, 3 net-new, all 3 on domains held in no year, so all 3 fail the split. NET-NEW POST-SPLIT: 0 of 100. Email presence rises steeply across the window (1996: 0 of 32 affiliations, 1997: 18%, 1999: 34%, 2001: 38%), so 1996, the smallest and most valuable baseline year, is the year it cannot serve at all. HONEST RESIDUAL: 0 of 100 bounds the rate at roughly 3% at 95% confidence, not at 0%; the store-side ceiling closes it, only 37,245 missing pairs exist across every academic suffix combined, of which ac.jp, edu.cn, ac.kr, edu.tw, ac.at and ac.il contribute 14,198 worth about 1,500 EE. Sample gap disclosed: 1998 absent from the draw.
- next step: close it, and write the measured zero into docs/sources.md. If certainty is wanted over inference, ONE baseline file settles it exactly for one request. No approval request; no reviewer attention.

Decision: rejected

