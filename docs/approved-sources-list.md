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

### nominet_whois_port43 / whois_creation

- what it is: Nominet's public .uk WHOIS on port 43, one "Relevant dates: Registered on:" line per queried domain.
- where: whois.nic.uk port 43, documented at https://registrars.nominet.uk/uk-namespace/registration-and-domain-management/query-tools/whois/
- what dates one item: the registry's own "Registered on:" date for that one domain, self-dating, no split. Cap the proposal understates: it is the CURRENT registration, not the original, proved 2 of 2 (0345.co.uk, stored as 1997, reads 28-Dec-2022; kestrel-cleaning.co.uk reads 23-May-2025), so every dropped and re-registered .uk name is lost silently. Failure direction is loss, not a fabricated in-window year, so it is safe to bank. Nothing before Aug-1996 (Nominet prints "before Aug-1996"), so 1996 is partial.
- why it may be net-new: 0 of the 60,468 undated .uk names in the pool appear in the 11,362,034-pair merged baseline, and all 202,878 registered .uk names the baseline holds are already dated in the store. Upper bound 60,468 x 15.7% x 0.9813 is roughly 9,300 EE (ESTIMATE, and it assumes a 100% answer rate that 1 of 2 probes already contradicts).
- reachability, checked 2026-08-12: port 43 answered twice at human pace, full record both times, no refusal, no HTTP in the path; the cited docs page fetched 200. The response carries the banner "WHOIS service for .UK will cease on 9th of February 2027", and Nominet's page calls .uk WHOIS end of life and redirects to RDAP, the service that refused this project three times in fourteen queries at 0.5 q/s.
- screener: strongest of the batch, live and measured, but two proposal claims fail. The quoted limits, 5 q/s and 1,000 per rolling 24 hours, are NOT on the page cited, so the 61-day feasibility case rests on an unverified number; and a seeded sample of 20 undated .uk names holds anti-spam munging, typos and junk beside plausible names, so a material share of the 60,468 returns No match and under a daily quota that waste is the whole cost.
- next step: price it, measuring the real rate limit and the answer rate on a plausibility-ranked queue, inside the window that closes February 2027.

Decision: pending

### ucsf_industry_documents / dated_directory

- class note: typed inside a dated artifact, so it takes the corroboration split; the uncorroborated half lands as `link_target`

- what it is: UCSF Industry Documents Library, 28,298,293 litigation-discovery documents and internal industry email with a public Solr metadata endpoint and OCR text on a separate download host.
- where: https://metadata.idl.ucsf.edu/solr/ltdl3/query (OCR text at download.industrydocuments.ucsf.edu)
- what dates one item: each document carries its own documentdate, the date the memo or letter was written, in a human format such as "1995 March 20" or "1999 May 07". A hostname typed in that document evidences that year alone. Typed inside a dated artifact, so it takes the corroboration split, exactly the trade_press shape.
- why it may be net-new: internal corporate correspondence is not prominence-selected, which is the one population a crawl-derived baseline is structurally weak on, and 28.3M documents is the largest corpus in the batch by two orders of magnitude.
- reachability, checked 2026-08-12: 200 twice on the Solr endpoint, 1,262,993 and 1,294,239 bytes of real JSON, no auth. facet.range over documentdate returned an EMPTY facet_counts object, so per-year counts cannot be had that way. A range query 1996-01-01 to 2001-12-31 returned numFound 3,843,392 but its top three hits read "1995 March 20", "1995 April 20", "1999 May 07", so the handler is not filtering on the date (lenient parsing matching year tokens in text) and 3,843,392 is NOT an in-window count. The OCR host was not probed: budget spent on metadata, so the prospector's 200 on gpyh0003.ocr is unverified.
- screener: dating verified as genuinely per item, endpoint open and live, and the largest upside here. Unverified: in-window volume, whether OCR text exists for in-window ids, and hostname density per document. Pricing must re-verify the OCR host first and find a date filter that actually filters.
- next step: price it, on a strict-syntax date query plus a sample of in-window OCR fetches for hostname density.

Decision: pending

### domainsproject_bulk_list / link_target

- class note: an undated bulk list, so it can never date a year; names are dated afterwards by the approved rdap_snapshot route

- what it is: the Domains Project bulk domain list, taken from the free GitHub mirror rather than the vendor host.
- where: https://github.com/tb0hdan/domains (the proposal's raw-data host, https://dataset.domainsproject.org/, returns 401)
- what dates one item: nothing. Undated seed, scores zero until the already-approved rdap_snapshot / whois_creation engine dates a name, so no approval gates collection.
- why it may be net-new: the local engine has 1,357,792 unasked names left, which is 3.2 hours at the measured 118 q/s and not the 11 days claimed, so the pool empties this afternoon and seed volume is the binding constraint.
- reachability, checked 2026-08-12: dataset.domainsproject.org 401 on HEAD; domainsproject.org 200, 36,022 bytes; github.com HTML 502 to curl but the API returns 200 for repos/tb0hdan/domains, BSD-3-Clause, not archived, 1,803,558 KB, pushed 2026-05-03, 1,154 stars.
- screener: the one item that can start unattended tonight, and the free route is real and redistributable. Two caps. Whether the free repo carries 3.235 billion names or a subset is UNVERIFIED, and the landing page's own schema.org data now sells that exact volume from EUR 100 to EUR 1,200, so treat 3.235B as a vendor claim; 1.8 GB implies 35x compression, which is equally consistent with a subset. Second, it is crawl-derived and RDAP can only date a name alive today, so the route reaches only the surviving 1996-2001 population, the same 15% to 17% the .uk figure measures.
- next step: pool only, gated: 5,000 names sampled at random, RDAP'd, reporting any-date rate, in-window rate and mean English weight of the net-new part before any bulk pull.

Decision: pending

### caselaw_access_project_opinions / dated_directory

- class note: typed inside a dated record, so it takes the corroboration split

- what it is: Harvard Caselaw Access Project bulk static files, full text of published US case law, one record per opinion, unauthenticated static files on a non-IA host.
- where: https://static.case.law/
- what dates one item: one opinion is one record with a structured decision date, and a hostname in that opinion evidences that year only, not the dataset publication date. Reporter metadata carries explicit start_year and end_year, so in-window filtering is a metadata operation and not a guess.
- why it may be net-new: hostnames typed by litigants and judges 1996-2001 include small commercial parties that never had a famous crawl footprint, and the repo has never touched this family.
- reachability, checked 2026-08-12: static.case.law/ HTTP/2 200, text/html, last-modified 2024-03-05, Cloudflare, no auth. ReportersMetadata.json returned 206 with real records, id 210, "West's Atlantic Reporter, Second Series", A.2d, start_year 1942, end_year 2010, nested jurisdictions. Data retrieved, not a shell.
- screener: dating sound, retrieval proved, and grep of all 183 tracked files for caselaw|courtlistener|case\.law returned nothing, so genuinely untouched. Split-protected typed evidence, so widening the URL regex is safe and no approval is needed to start on the candidate half. Overlaps courtlistener_caselaw below: price only one of the two first.
- next step: price it, on one in-window reporter, measuring hostnames per opinion and the post-split net-new share.

Decision: pending

### courtlistener_caselaw / dated_directory

- class note: typed inside a dated record, so it takes the corroboration split

- what it is: Free Law Project quarterly bulk CSV export of the whole CourtListener corpus, off any IA host, no key; opinion-clusters carries date_filed, opinions carries the text.
- where: https://storage.courtlistener.com/bulk-data/ (enumerate via the S3 REST listing, ?list-type=2&prefix=bulk-data/opinion)
- what dates one item: date_filed on the opinion cluster, one machine-recorded date per opinion, joined to the text by cluster id, so an opinion filed 2000-06-14 naming foo.com dates foo.com to 2000 with no inference.
- why it may be net-new: same argument as CAP, ACPA and trademark litigation from 1999 plus ordinary commercial disputes naming a party's website. Coverage of the era is published appellate and F.Supp.2d material; unpublished district opinions 1996-2001 are thin, which is knowledge and not measured here.
- reachability, checked 2026-08-12: 200 on both S3 REST listings (application/xml, 62,481 and 25,033 bytes). Real sizes: 72 keys under bulk-data/opinion*, opinions-2026-06-30.csv.bz2 at 54.562 GB, opinion-clusters-2026-06-30.csv.bz2 at 2.457 GB, 36 quarterly generations back to 2022-08, no auth, IsTruncated false.
- screener: dating holds, retrieval proved. The artifact_listing reading the proposal floats is NOT available: the refusal criteria in the udrp_proceedings approval block say a hostname out of prose rather than a structured field means candidate-only or a split-taking spec, so the 5.5x upside quoted from the udrp fork does not transfer and nobody should price this expecting it. 54.562 GB against a population CAP reaches in static per-reporter files.
- next step: price it after CAP, or instead of CAP if CAP's per-reporter slicing proves worse than one quarterly pair.

Decision: pending

### dotgov_real_names / link_target

- class note: an undated list, dated afterwards by the approved rdap_snapshot / whois_creation route

- what it is: CISA's dotgov-data current-full.csv, the authoritative census of every registered .gov domain, 16,483 data rows, 1,406,077 bytes, no date column of any kind.
- where: https://raw.githubusercontent.com/cisagov/dotgov-data/main/current-full.csv (dating route: https://rdap.nic.gov/rdap/)
- what dates one item: not the CSV, which can never date anything. rdap.nic.gov returns registration 1997-10-02T01:29:25Z for loc.gov alongside a separate reregistration 2026-05-19, so this registry preserves the ORIGINAL creation date across a lapse, the property .uk lacks and the failure that makes .au date nothing. Cleanest dating route in the batch. On one reading it needs no new Decision line, because gov resolves to https://rdap.nic.gov/rdap/ in the cached IANA bootstrap and would be swept by the approved rdap_snapshot spec, but that reading is a human's call.
- why it may be net-new: the baseline's 21,271 .gov rows are host-level and collapse to 1,050 distinct registered names, 551 of them in the census, so 15,932 of 16,483 real .gov names are absent from the shipped baseline, slightly more than the 15,816 claimed. Store figures exact: 667 held, 551 dated, all in window.
- reachability, checked 2026-08-12: raw.githubusercontent.com 200, 1,406,077 bytes, text/plain; rdap.nic.gov 200, 6,983 bytes of valid RDAP JSON.
- screener: honest ceiling 15,932 pairs at 0.9825, realistic yield a few hundred to low thousands because the baseline already holds 1,050 in-window .gov names and the in-window .gov namespace was small, so below the 5,000-pair bar. It survives on cost alone: 15,932 queries at 118 q/s is about 2.3 minutes, the cheapest decisive experiment here, and the names are county and city governments rather than famous sites. One correction to the proposed second use as a fabrication filter: 499 registered .gov names in the baseline are absent from the current census and they are real retired federal sites (4woman.gov, 2dol.gov, 21stcentury.gov, 1903to2003.gov), so the filter is one-directional, it can whitelist 16,483 names as real and cannot condemn the rest.
- next step: price it, 2.3 minutes of RDAP, and settle whether the existing rdap_snapshot Decision already covers the gov route.

Decision: pending

### nz_dnc_zone_data / whois_creation

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

- class note: `artifact_listing` is arguable and `dated_directory` is the safe reading, so it is filed under the safe one

- what it is: USPTO trademark full-text XML from the Open Data Portal, the subpopulation being applications filed 1996-2001 whose word mark IS a domain name, each with serial number, mark text and a machine-recorded filing date.
- where: https://api.uspto.gov/api/v1/datasets/products/TRTDXFAP (portal page https://data.uspto.gov/bulkdata/datasets/TRTDXFAP)
- what dates one item: one row is one application with its own filing date, and the domain sits in a STRUCTURED field rather than in prose, so unlike CourtListener it is not pre-capped by the prose criterion and a paid filing has no protocol-placeholder failure mode. Caveat the proposal omits, and it is the generalising lesson of the Netcraft entry: an intent-to-use filing for FOO.COM in 1999 proves the mark was applied for in 1999, not that foo.com resolved in 1999.
- why it may be net-new: dot-com-rush filers were overwhelmingly small businesses buying a name, which is the opposite end of the distribution from the famous hosts a crawl-derived baseline holds first.
- reachability, checked 2026-08-12: 401 Unauthorized, application/json, 26 bytes, {"message":"Unauthorized"}, so the bulk route is key-gated by free self-service registration and not a licence. The annual product page no longer exists: developer.uspto.gov redirected to https://data.uspto.gov/ and served a 20,666-byte JS shell with no title, zero occurrences of bulkdata.uspto.gov and zero of the annual file naming, so no file URL was seen. dig: bulkdata.uspto.gov has NO address while data.uspto.gov, api.uspto.gov and developer.uspto.gov all resolve.
- screener: best shape of the three gated items because the domain is a structured field. Second correction the proposal needs: TRTDXFAP is the DAILY applications product and does not reach 1996-2001; the window lives in the annual backfile whose product page is the one that now redirects, so the in-window file is unconfirmed and no volume figure here is measured.
- next step: access request, free API key, then locate the annual backfile product and measure in-window domain-shaped marks before anything else.

Decision: pending

### uspto_trademark_case_files / artifact_listing

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

- class note: self-dating, and the class is already settled `master` for udrp_proceedings by ADR-002; this is a wider provider set

- what it is: DNS Research Federation's normalised UDRP decisions on DAP.LIVE, claimed as roughly 83,000 cases over 156,000 domains across all four dispute providers, intended as the sanctioned reopen of the NAF, eResolution and CPR gap at docs/sources.md:1721.
- where: https://dap.live, catalogue at https://dnsrf.org/docs/dap-live/inputs/data-feeds/
- what dates one item: one case, one disputed domain in its own field, filing year as the earlier and safer claim. Settled shape, no reviewer time needed on the classification again.
- why it may be net-new: only if it reaches providers the ICANN consolidated table missed, which is now the entire case.
- reachability, checked 2026-08-12: dap.live/ HTTP/2 200, text/html, 23,058 bytes, Vercel, cache HIT; dnsrf.org feeds page 200, 38,739 bytes. Two landing pages and NO data. The catalogue is titled "Feeds List" but renders entries client-side: the fetched content carried navigation and one sentence about filtering, with no UDRP feed named, no export URL, no licence text and no price. Same client-side-app wall that closed adrforum.com at docs/sources.md:1713.
- screener: two proposal claims are void and both are checkable in the repo. The premise that we hold only WIPO's 3,325 in-window cases is false: docs/ROUND.md:113 shows udrp_proceedings ingested at 7,837 pairs and 4,763.1808 EE from ICANN's consolidated multi-provider table, and the reviewed sample at docs/approved-sources-list.md:227 is a NAF record (FA0094335, statefarmdirect.com, 2000), so NAF is partly banked and the 3,000 to 6,000 pair estimate is measured against the wrong baseline. And the class is not pending as claimed: it was decided master artifact_listing in ADR-002 and key-decisions.md C-12. That second error cuts in the proposal's favour and removes the argument it spends most of its case on, but an agent quoting a settled question as open is a reason to distrust its other numbers.
- next step: access request, and only after re-measuring the increment against the banked multi-provider table; a new ingest spec would still need its own Decision line.

Decision: pending

### ripe_db_lastmodified / link_target

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
