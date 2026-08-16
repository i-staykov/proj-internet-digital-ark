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

### dartmouth_nber_captures / cdx_timestamp

- ingest spec: `dartmouth_nber_captures`
- source: https://archive.org/details/DARTMOUTH-NBER-RESEARCH-2017-metadata
- journal: `data/raw/dartmouth_nber/domain-year-captures.txt`
- agent's dating claim: the Internet Archive's own count of the captures it holds for that host in that calendar year, one row per (host, year)
- nothing in the closed register resembles this by name.

**Check these before reading anything else.** Seeded-random sample, seed `20260816`, so it is reproducible and was not chosen by the agent:

| record | domain | year claimed | open this |
|---|---|--:|---|
| `ia_captures:2000:124` | `safaripress.com` | 2000 | https://web.archive.org/web/2000*/http://safaripress.com/ |
| `ia_captures:2001:5` | `ewen-parker.com` | 2001 | https://web.archive.org/web/2001*/http://ewen-parker.com/ |
| `ia_captures:2000:500` | `media100.com` | 2000 | https://web.archive.org/web/2000*/http://media100.com/ |
| `ia_captures:2001:10` | `tuckerind.com` | 2001 | https://web.archive.org/web/2001*/http://tuckerind.com/ |
| `ia_captures:2000:5` | `honoursgolf.com` | 2000 | https://web.archive.org/web/2000*/http://honoursgolf.com/ |
| `ia_captures:2001:186` | `mcdermott.com` | 2001 | https://web.archive.org/web/2001*/http://mcdermott.com/ |

**Measured against the live store**, by program, not by the agent:

| | |
|---|--:|
| records in the journal | 765,188 |
| distinct (domain, year) | 764,982 |
| over distinct domains | 315,085 |
| already held by the store | 537,709 |
| absent from the store | 29.7% |

**The counterfactual, so the stake is visible before you decide:**

| decision | net-new pairs | equivalent-English |
|---|--:|--:|
| `master` (self-dating, no split) | **227,273** | **142,084.0** |
| `master` (taking the corroboration split) | 130,966 | 82,161.2 |
| `candidate-only` | 0 | 0.0, and the names still grow the pool |

Mean equivalent-English weight of the net-new part: 0.6252. By year: {1996: 33, 1997: 107, 1998: 4177, 1999: 14315, 2000: 21621, 2001: 187020}.

**Reasons a reader should refuse**, listed by the agent against its own request:

- the sample links do not show that domain with that date;
- the year is inferred from something other than the record itself;
- the hostname comes out of prose rather than a structured field, in which case `candidate-only` or a split-taking spec is right, not `master`;
- the closed family named above is the same population under another name.

Decision: pending

## Found, awaiting triage

**This section grows indefinitely and that is its purpose** (Ivo, 2026-08-12): *"Grow the list of sources
for sign-off in approved-sources-list.md. Keep growing it indefinitely. Every time when I have a moment to
look at that list, I will tell you whether to add those sources to the candidate pool or to fold them in
directly."*

**What is being asked of you.** One of two words per row. *Candidate pool* means `Decision: candidate-only`:
its names may be searched and can never date a year, which is the safe answer and loses very little, because
the archive can still date them from its own captures. *Fold in directly* means `Decision: master`: its
records may date a year on their own authority. `rejected` also binds and is the right answer for anything
not worth keeping. **Nothing is blocked while a row sits here**: a `pending` class cannot date a year, so
`ark ingest` refuses it and collection carries on regardless. This queue reaches `key-decisions.md` as **one
line naming the count**, never one entry per source, because that surface stops being read the moment it
stops fitting on a screen.

**How these differ from the priced requests above.** None of them carries a seeded-random sample with live
links, so none is checkable in two minutes the way a request block is. Many have since been priced against
the store and say so in the `Evidence` column; the rest are screened and reachable and not yet measured.

**The table is ranked by expected net-new equivalent-English**: on the EE figure where an entry gives one,
on its net-new pairs where it does not, and on the size of the corpus where it is unpriced. A lead whose own
kill condition has already fired sits below live leads carrying the same figure, because that figure is a
ceiling it has been measured not to reach. `~` marks an estimate, and `unpriced` means the entry has no
figure of that kind rather than a small one.

| # | Source | What dates an item | Type | Net-new pairs | EE | Evidence | Decision |
|--:|---|---|---|---|---|---|---|
| 1 | can_domain_registry_notices | `Date-Approved:` on the notice | whois_creation | 11,418 self-dating / 936 split | 9,551.2 / 783.0 | MEASURED | pending |
| 2 | nominet_whois_port43 | registry `Registered on:` per name | whois_creation | ~9,500 ceiling | ~9,300 ceiling | ESTIMATE | pending |
| 3 | gias_england_school_website_domains | nothing in the file, Nominet per name | link_target | ~5,568 sch.uk | ~5,463 | MIXED | pending |
| 4 | ccew_charity_register_contact_domains | nothing in the file, CDX per name | link_target | ~5,200 | ~4,557 | MIXED | pending |
| 5 | ncua_5300_call_report_webaddr | CYCLE_DATE on every FS220D row | artifact_listing | 1,913 per quarter | 1,293.3 per quarter | MEASURED | pending |
| 6 | fac_sfsac_historic_1998_2001 | AUDITEEDATESIGNED on the e-mail row | artifact_listing | ~6,000-12,000 per year | unpriced | ESTIMATE | pending |
| 7 | junkfilter_dated_blocklist | the ISO-dated release directory | dated_directory | ~3,000-8,000 | unpriced | ESTIMATE | pending |
| 8 | ipgod_au_marktext | the mark's own filing date | dated_directory | ~2,000-6,000 pre-split | unpriced | ESTIMATE | pending |
| 9 | ted_ojs_notices_1996_2001 | the notice's own PD field | link_source | ~2,000-6,000 | unpriced | ESTIMATE | pending |
| 10 | cipo_ca_trademark_marktext_1996_2001 | the mark's own filing date | typed | ~1,500-5,000 pre-split | unpriced | ESTIMATE | pending |
| 11 | eric_fulltext_1996_2001 | publicationdateyear per document | dated_directory | ~1,300-4,700 | unpriced | ESTIMATE | pending |
| 12 | uk_historic_hansard | the sitting date, printed four ways | dated_directory | ~1,000-3,000 | unpriced | ESTIMATE | pending |
| 13 | sec_form_adv_part1_2000_2001 | the filing's own date, probable | artifact_listing | ~1,200-2,500 | unpriced | ESTIMATE | pending |
| 14 | usac_erate_form471_contact_email_1998_2001 | funding year written on the form | dated_directory | ~low thousands | unpriced | ESTIMATE | pending |
| 15 | sbir_sttr_award_pi_email_2000_2001 | Award Year on the award row | dated_directory | ~1,000-2,000 | ~600-1,300 | ESTIMATE | pending |
| 16 | nces_imls_pls_web_addr_1998_2001 | ENDDATE of the reporting period | typed | 348 FY1999, ~1,200-1,800 all | 280.1 FY1999 | MIXED | pending |
| 17 | ucsf_industry_documents | documentdate on each document | dated_directory | unpriced | unpriced | none | pending |
| 18 | usco_bulk_registrations | reg_date beside the title | typed | unpriced | unpriced | none | pending |
| 19 | govinfo_cbd_bulk | the issue date in each filename | typed | unpriced | unpriced | none | pending |
| 20 | courtlistener_caselaw | date_filed on the opinion cluster | dated_directory | unpriced | unpriced | none | pending |
| 21 | caselaw_access_project_opinions | the opinion's decision date | dated_directory | unpriced | unpriced | none | pending |
| 22 | uspto_trademark_case_files | the application's filing date | artifact_listing | unpriced | unpriced | none | pending |
| 23 | uspto_tm_marktext | the application's filing date | dated_directory | unpriced | unpriced | none | pending |
| 24 | dnsrf_dap_udrp_multiprovider | the case filing year | artifact_listing | unpriced | unpriced | none | pending |
| 25 | domainsproject_bulk_list | nothing, RDAP dates it after | link_target | unpriced | unpriced | none | pending |
| 26 | domain_aftermarket_listings_1999_2001 | the listing page's capture date | artifact_listing | unpriced | unpriced | none | pending |
| 27 | openpgp_keyserver_dumps | key self-signature, owner-asserted | link_target | ~50,000-150,000 names, gated | unpriced | ESTIMATE | pending |
| 28 | wayback_longitudinal_url_sample | first capture time, data unpublished | cdx_timestamp | unpriced | unpriced | none | pending |
| 29 | dotgov_real_names | nothing, RDAP dates it after | link_target | ~few hundred to low thousands | unpriced | ESTIMATE | pending |
| 30 | govuk_domain_name_register_council_seeds | nothing, CDX pool engine only | link_target | 4,864 names | ~4,773 ceiling | MIXED | pending |
| 31 | cog2002_gid_localgov_weburl | nothing, a 2002 canvass | link_target | 1,365 names | ~500, ceiling 954 | MIXED | pending |
| 32 | cordis_fp4_fp5_project_websites | nothing, no per-item date exists | link_target | 944 names | 503.5 ceiling | MEASURED | pending |
| 33 | nz_dnc_zone_data | registry Original Created per name | whois_creation | ~580 | ~570 | ESTIMATE | pending |
| 34 | cog2002_gid_school_systems_weburl | nothing, a 2002 canvass | link_target | 553 names | ~200, ceiling 444 | MIXED | pending |
| 35 | state_sos_entity_registers | entityformdate beside entityname | typed | 1,384 raw, Colorado only | ~437 | MIXED | pending |
| 36 | cbd_secretariat_meeting_documents_1996_2001 | the document's symbol and date | link_source | ~2,250-4,050 pre-saturation | ~1,100-1,900 | MIXED | pending |
| 37 | itu_operational_bulletin_1996_2001 | the issue masthead and cut-off | link_source | ~1,015-1,885 | ~519-934 | MIXED | pending |
| 38 | uk_gazette_addressed_notices_1998_2001 | the notice's publication date | link_source | ~1,000-2,000 ceiling | unpriced | MIXED | pending |
| 39 | ietf_meeting_attendee_rosters | the meeting edition tag | typed | 27 measured, ~324 all | 13.56 measured, ~160 all | MIXED | pending |
| 40 | oireachtas_debates_xml | FRBRdate on the debate record | dated_directory | ~tens to low hundreds | unpriced | ESTIMATE | pending |
| 41 | ripe_db_lastmodified | last-modified, disproved | link_target | 7 names | unpriced | MEASURED | pending |
| 42 | osbar_bulletin_html_issues_2000_2001 | the issue, internally dated | link_source | 5 per issue, 8-95 all | 3.2 per issue, ~60 all | MIXED | pending |
| 43 | lawsociety_ie_gazette_issue_pdfs_1997_2001 | the issue printed in the PDF | link_source | 3 per issue, ~10-150 all | 2.6 per issue | MIXED | pending |
| 44 | bsd_ports_master_sites_dated_trees | the dated release tree | typed | 0 | 0.0 | MEASURED | pending |
| 45 | winsite_cica_dated_shareware_index | per-file mtime | typed | 0 | 0.0 | MEASURED | pending |
| 46 | pmc_oa_subset_fulltext_1998_2001 | the JATS pub-date | link_source | 0 | 0.0 | MEASURED | pending |
| 47 | aminet_index_uploader_readme | nothing, age in weeks saturates | typed | cannot date a year | unpriced | none | pending |
| 48 | educause_edu_whois_activation | registry activation date | whois_creation | ~280 | unpriced | MEASURED | rejected |
| 49 | nlm_medline_affiliation_email_1996_2001 | the citation's PubDate | link_source | 0 post-split | 0.0 | MEASURED | rejected |
| 50 | ffiec_call_report_webaddr | quarter-end date, never published | artifact_listing | 0 | 0.0 | MEASURED | rejected |

**The top eight, in two lines each.**

1. **can_domain_registry_notices**, the CA registry's own per-registration notices, already on disk in the
   Usenet corpus and needing no download: 11,418 net-new pairs and 9,551.2 EE read as a registry record,
   936 and 783.0 if it takes the corroboration split, so one classification is worth 12.2x.
   *Kills it:* 25.0% of 1,500 sampled net-new names sit one edit from a name already held, and a self-dating
   class has no split behind it to catch a typo.
2. **nominet_whois_port43**, the .uk registry WHOIS on port 43, one `Registered on:` line per queried name
   against 60,468 undated .uk names already in the pool, at the highest English weight there is, 0.9813.
   *Kills it:* it returns the CURRENT registration, so every dropped and re-registered name is lost
   silently, the answer rate is unmeasured, and the service closes on 9 February 2027.
3. **gias_england_school_website_domains**, the DfE bulk extract of every school in England, 20,905 net-new
   registrable domains measured from one request, whose sch.uk slice alone prices at ~5,463 EE on a measured
   87.7% registry answer rate.
   *Kills it:* the file itself can never date a year, so the whole figure depends on row 2 going your way,
   or on the CDX pool engine reaching the names instead.
4. **ccew_charity_register_contact_domains**, the Charity Commission daily full register, 103,509 net-new
   registrable domains measured, the largest volume in the queue, pricing to ~4,557 EE.
   *Kills it:* only 5.0% of a 40-name sample were in window, so it spends 103,509 queries to get there,
   17.5x worse per hit than row 3, and no row in the file can ever date a year itself.
5. **ncua_5300_call_report_webaddr**, credit union quarterly call reports carrying a website field beside a
   per-row CYCLE_DATE: 1,913 net-new pairs and 1,293.3 EE measured off a single 1999 quarter, with 8 to 20
   in-window quarters available.
   *Kills it:* 6.7% of raw values are malformed by a hard 25-character truncation in the source, and being
   self-dating there is no corroboration split behind the extractor.
6. **fac_sfsac_historic_1998_2001**, Federal Audit Clearinghouse returns dated by the signature on the row
   that carries the e-mail address, an estimated 6,000 to 12,000 own-domain addresses per signature year in
   the .us locality namespace the store is thinnest in.
   *Kills it:* the populated rate of AUDITEEEMAIL in 1998 to 2000 is unmeasured, and the dataset's own
   dictionary documents a sibling column that is present but empty in exactly those years.
7. **junkfilter_dated_blocklist**, the procmail anti-spam release tree kept as 13 ISO-dated snapshots in
   window, an estimated 3,000 to 8,000 spam-origin hostnames, self-dating so no split is paid.
   *Kills it:* the file was never opened. Procmail input is plausibly escaped regexps and wildcards rather
   than hostnames, and a self-dating class turns a bad match straight into a year claim.
8. **ipgod_au_marktext**, IP Australia's bulk trade mark register, an estimated 2,000 to 6,000 domain-shaped
   marks filed in window at the highest-weight TLD in the table, .com.au 0.9904.
   *Kills it:* a mark reading FOO.COM.AU filed in 2000 proves an application, not that the domain resolved,
   and the table holding the mark text is still unverified.

**The full working behind any row**, what it is, what was reached, what was measured, what would kill it and
what the next step is, is in [source-dossiers.md](source-dossiers.md) under the same
`### source / evidence_type` heading. **Set the decision on the `Decision:` line below**, not in the table:
that line is what `ark ingest` reads. Rows 1, 26 and 28 have no `Decision:` line at all, having been
recorded before they were priced; the gate refuses them exactly as it refuses `pending`, and adding a line
is what turns one into an answer.

### ncua_5300_call_report_webaddr / artifact_listing
- potential: 88

Decision: pending

### fac_sfsac_historic_1998_2001 / artifact_listing
- potential: 86

Decision: pending

### uk_historic_hansard / dated_directory
- potential: 84

Decision: pending

### usac_erate_form471_contact_email_1998_2001 / dated_directory
- potential: 84

Decision: pending

### eric_fulltext_1996_2001 / dated_directory
- potential: 83

Decision: pending

### gias_england_school_website_domains / link_target
- potential: 82

Decision: pending

### nces_imls_pls_web_addr_1998_2001 / typed
- potential: 82

Decision: pending

### ucsf_industry_documents / dated_directory
- potential: 78

Decision: pending

### oireachtas_debates_xml / dated_directory
- potential: 77

Decision: pending

### junkfilter_dated_blocklist / dated_directory
- potential: 74

Decision: pending

### nominet_whois_port43 / whois_creation
- potential: 72

Decision: pending

### govinfo_cbd_bulk / typed
- potential: 71

Decision: pending

### ipgod_au_marktext / dated_directory
- potential: 71

Decision: pending

### ted_ojs_notices_1996_2001 / link_source
- potential: 70

Decision: pending

### sbir_sttr_award_pi_email_2000_2001 / dated_directory
- potential: 65

Decision: pending

### usco_bulk_registrations / typed
- potential: 63

Decision: pending

### uk_gazette_addressed_notices_1998_2001 / link_source
- potential: 62

Decision: pending

### courtlistener_caselaw / dated_directory
- potential: 60

Decision: pending

### pmc_oa_subset_fulltext_1998_2001 / link_source
- potential: 60

Decision: pending

### caselaw_access_project_opinions / dated_directory
- potential: 58

Decision: pending

### sec_form_adv_part1_2000_2001 / artifact_listing
- potential: 58

Decision: pending

### can_domain_registry_notices / whois_creation
- potential: 55

Decision: pending

### uspto_trademark_case_files / artifact_listing
- potential: 55

Decision: pending

### dnsrf_dap_udrp_multiprovider / artifact_listing
- potential: 52

Decision: pending

### cipo_ca_trademark_marktext_1996_2001 / typed
- potential: 49

Decision: pending

### itu_operational_bulletin_1996_2001 / link_source
- potential: 49

Decision: pending

### cbd_secretariat_meeting_documents_1996_2001 / link_source
- potential: 48

Decision: pending

### ccew_charity_register_contact_domains / link_target
- potential: 45

Decision: pending

### ietf_meeting_attendee_rosters / typed
- potential: 45

Decision: pending

### nz_dnc_zone_data / whois_creation
- potential: 45

Decision: pending

### uspto_tm_marktext / dated_directory
- potential: 40

Decision: pending

### cordis_fp4_fp5_project_websites / link_target
- potential: 32

Decision: pending

### cog2002_gid_localgov_weburl / link_target
- potential: 30

Decision: pending

### domainsproject_bulk_list / link_target
- potential: 30

Decision: pending

### wayback_longitudinal_url_sample / cdx_timestamp
- potential: 28

Decision: pending

### domain_aftermarket_listings_1999_2001 / artifact_listing
- potential: 22

Decision: pending

### dotgov_real_names / link_target
- potential: 22

Decision: pending

### govuk_domain_name_register_council_seeds / link_target
- potential: 22

Decision: pending

### state_sos_entity_registers / typed
- potential: 22

Decision: pending

### cog2002_gid_school_systems_weburl / link_target
- potential: 20

Decision: pending

### openpgp_keyserver_dumps / link_target
- potential: 20

Decision: pending

### ripe_db_lastmodified / link_target
- potential: 12

Decision: pending

### bsd_ports_master_sites_dated_trees / typed
- potential: 8

Decision: pending

### osbar_bulletin_html_issues_2000_2001 / link_source
- potential: 6

Decision: pending

### winsite_cica_dated_shareware_index / typed
- potential: 5

Decision: pending

### lawsociety_ie_gazette_issue_pdfs_1997_2001 / link_source
- potential: 4

Decision: pending

### aminet_index_uploader_readme / typed
- potential: 3

Decision: pending

### educause_edu_whois_activation / whois_creation
- potential: 78

Decision: rejected

### nlm_medline_affiliation_email_1996_2001 / link_source
- potential: 3

Decision: rejected

### ffiec_call_report_webaddr / artifact_listing
- potential: 2

Decision: rejected
