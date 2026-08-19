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

**One thing this does NOT do, measured rather than assumed.** Approving it would also place 315,085 domains in annual files, which could in principle corroborate Usenet mentions that fail the split today and admit them too. Measured: it would newly corroborate **1,173 pairs over 937 domains**, worth a few hundred equivalent-English. The reason it is so small is itself informative: 2,561,871 mention pairs fail the split because their domain is dated nowhere at all, and a large part of that population is anti-harvester address munging rather than domains. Do not credit this request with a second-order gain it does not have.

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

### dartmouth_nber_captures / cdx_timestamp

- ingest spec: `dartmouth_nber_captures`
- source: archive.org item `DARTMOUTH-NBER-RESEARCH-2017-metadata`, downloaded 2026-08-16. **The item
  stopped serving on 2026-08-17**: `details/` says "Item cannot be found" and `metadata/` returns `{}`.
  It is still in the search index once, at 693,302,553 bytes, so this was a takedown rather than a wrong
  identifier. Do not use it as the verification route; use the per-record Wayback links below, which
  resolve. `sources.md` carries the full account.
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

Decision: master

### domain_creation_bulk / whois_creation

- ingest spec: `domain_creation_bulk`
- source: https://www.kaggle.com/datasets/wotschofsky/171-million-domain-names-whois-dns-dnssec
- journal: `data/raw/domain_creation/domains.csv`
- agent's dating claim: the registry's own creation date for that exact domain, one row per domain, parsed from a port-43 WHOIS answer by the dataset's publisher
- nothing in the closed register resembles this by name.

**Check these before reading anything else.** Seeded-random sample, seed `20260816`, so it is reproducible and was not chosen by the agent:

| record | domain | year claimed | open this |
|---|---|--:|---|
| `registry created 1999-11-27` | `comprehensivecoverage.com` | 1999 | https://lookup.icann.org/en/lookup?q=comprehensivecoverage.com |
| `registry created 2001-11-03` | `kalingasoft.com` | 2001 | https://lookup.icann.org/en/lookup?q=kalingasoft.com |
| `registry created 1998-01-21` | `accentimpression.com` | 1998 | https://lookup.icann.org/en/lookup?q=accentimpression.com |
| `registry created 2001-07-18` | `vqeg.org` | 2001 | https://lookup.icann.org/en/lookup?q=vqeg.org |
| `registry created 1998-10-27` | `heirloomlinens.com` | 1998 | https://lookup.icann.org/en/lookup?q=heirloomlinens.com |
| `registry created 1997-04-08` | `crawhen.com` | 1997 | https://lookup.icann.org/en/lookup?q=crawhen.com |

**Measured against the live store**, by program, not by the agent:

| | |
|---|--:|
| records in the journal | 2,957,620 |
| distinct (domain, year) | 2,957,620 |
| over distinct domains | 2,957,620 |
| already held by the store | 786,403 |
| absent from the store | 73.4% |

**The counterfactual, so the stake is visible before you decide:**

| decision | net-new pairs | equivalent-English |
|---|--:|--:|
| `master` (self-dating, no split) | **2,171,217** | **1,245,366.6** |
| `master` (taking the corroboration split) | 649,475 | 379,868.2 |
| `candidate-only` | 0 | 0.0, and the names still grow the pool |

Mean equivalent-English weight of the net-new part: 0.5736. By year: {1996: 57044, 1997: 112929, 1998: 259459, 1999: 455002, 2000: 682705, 2001: 604078}.

**Reasons a reader should refuse**, listed by the agent against its own request:

- the sample links do not show that domain with that date;
- the year is inferred from something other than the record itself;
- the hostname comes out of prose rather than a structured field, in which case `candidate-only` or a split-taking spec is right, not `master`;
- the closed family named above is the same population under another name.

Decision: master



---

## Pending requests

Priced, measured and waiting on a decision. A class appearing here carries a seeded-random sample with
live links and the counterfactual, is decidable in about two minutes, and gets its own entry under
`## OPEN` in `key-decisions.md`.

None at present.

---

### internic_zone / artifact_listing

- ingest spec: `internic_zone`
- source: https://web.archive.org/web/19970420113748id_/http://nic.mil/oroot.html/org.zone.gz
- journal: `data/raw/internic_zones/org.zone.gz`
- agent's dating claim: a delegation in the 18 April 1997 .org zone is the registry stating the name existed that day, and the SOA serial 1997041800 is inside the file rather than in its name or its capture
- closest closed family, 2 shared terms, `docs/sources.md:1328`: **InterNIC public zone files, via Wayback (2026-08-08)**, closed on measurement.

**Check these before reading anything else.** Seeded-random sample, seed `20260811`, so it is reproducible and was not chosen by the agent:

| record | domain | year claimed | open this |
|---|---|--:|---|
| `internic org zone serial 1997041800` | `ambainc.org` | 1997 |  |
| `internic org zone serial 1997041800` | `cfserve.org` | 1997 |  |
| `internic org zone serial 1997041800` | `meherbaba.org` | 1997 |  |
| `internic org zone serial 1997041800` | `deltadentalnj.org` | 1997 |  |
| `internic org zone serial 1997041800` | `limac.org` | 1997 |  |
| `internic org zone serial 1997041800` | `itug.org` | 1997 |  |

**Measured against the live store**, by program, not by the agent:

| | |
|---|--:|
| records in the journal | 72,972 |
| distinct (domain, year) | 61,252 |
| over distinct domains | 61,252 |
| already held by the store | 49,102 |
| absent from the store | 19.8% |

**The counterfactual, so the stake is visible before you decide:**

| decision | net-new pairs | equivalent-English |
|---|--:|--:|
| `master` (self-dating, no split) | **12,150** | **8,627.7** |
| `master` (taking the corroboration split) | 7,089 | 5,033.9 |
| `candidate-only` | 0 | 0.0, and the names still grow the pool |

Mean equivalent-English weight of the net-new part: 0.7101. By year: {1997: 12150}.

**Reasons a reader should refuse**, listed by the agent against its own request:

- the sample links do not show that domain with that date;
- the year is inferred from something other than the record itself;
- the hostname comes out of prose rather than a structured field, in which case `candidate-only` or a split-taking spec is right, not `master`;
- the closed family named above is the same population under another name.

**Two things the generator could not know, added by hand.**

**The class covers six files and the counterfactual above prices one.** `org.zone.gz` is the
journal that was sampled, so the table understates the stake. Across the whole 1997-04-20 crawl,
measured the same way: **12,400 net-new pairs and 8,871.2 equivalent-English** as a self-dating
class, or 7,326 and 5,264.6 with the split applied anyway. The extra 250 pairs are `.edu` 199,
`.gov` 37, `.mil` 1 and the rest, at higher weights than `.org`. `root.zone.gz` and
`arpa.zone.gz` contribute nothing by construction, the second because the canonicaliser refuses
reverse-DNS zones.

**Why the closed family it collides with is the reason to read it, not to refuse it.** That row
closed on 2026-08-08 having checked archive.org item search, CD-ROM images, four academic FTP
mirrors, DNS-OARC and the ISC survey directories, and concluded no in-window zone file survives.
Every one of those checks was about a *host's* copy. A military NIC mirroring the civilian
registry's distribution was on nobody's list. So this request does not re-propose a rejected
population, it produces the artifact that closure said did not exist, with four independent
integrity checks on it:

    gzip -t          passes on all six
    size             1,317,986 bytes, reproducing the figure recorded before this fetch
    lines            154,141, likewise
    SOA serial       1997041800 on line 2, beside hostmaster.INTERNIC.NET.
    terminator       InterNIC's own `;End of file.`

    97d068586523f8f7ad700ba088f7936d30cf2103e1c36a42e1d02320f1fa8408  arpa.zone.gz
    ce0e56617c00d31dc9ffefb848ac1a6aeec3274e03a2e4338ccedc3df1bcf873  edu.zone.gz
    c6d53fdb2ef331cefe2ee1cec059a43acc3312fb2b25672d9082ca88e733f73c  gov.zone.gz
    ae7faaa46ea9eacc55472d8faa71c8364c914c0b84de2c77b1e2d6a07d39e1c6  mil.zone.gz
    f15c95046eefe6437f84c971979ab5aaf5902b35164527c50e43de31f41f9cc8  org.zone.gz
    91161c22bb76d6e51179c0651f64a8d31c89ad5f64308c33df7f070487ce5912  root.zone.gz

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
| 0 | ukwa_geoindex | 14-digit capture timestamp per row | cdx_timestamp | ~10,000 to 60,000 | ~10,000 to 59,000 | MEASURED sample, ESTIMATE total | pending |
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
| 51 | wikipedia_externallinks | the 14-digit IA capture timestamp embedded in each `web.archive.org/web/<ts>/` citation | cdx_timestamp | unpriced | unpriced | SCREENED, NOT MEASURED: law 1 predicts near-zero | pending |

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

### nic_mil_internic_zone_mirror / artifact_listing
- self-dating, so **no corroboration split**. Found 2026-08-18.
- what it is: the Defense Data Network NIC at `nic.mil` mirrored InterNIC's zone-file distribution over
    HTTP, and the Wayback Machine captured it. `http://nic.mil/oroot.html/org.zone.gz` at capture
    `19970420113748` is a **complete April 1997 InterNIC `.org` zone**.
- what dates one item: the zone's own SOA serial in `YYYYMMDDNN` form, `1997041800`, **inside the
    artifact** on line 2 and corroborated by the capture timestamp. A name in the 18 April 1997 `.org`
    zone evidences 1997 and nothing else.
- verified independently, not taken from the finder: 1,317,986 bytes gzip, `gzip -t` passes,
    9,193,881 bytes and 154,141 lines uncompressed, terminated by InterNIC's own `;End of file.`
    marker. That is the whole battery the corrupt ISC copies fail.
- **measured HERE on 2026-08-18, not inherited, and all six files are now on disk under
    `data/raw/internic_zones/` and sha256-pinned so the figure is reproducible**: 65,261 delegated
    domains, 52,861 already held, **12,400 net-new pairs and 8,871.2 equivalent-English** as the
    self-dating class it is, or 7,326 pairs and 5,264.6 EE if the corroboration split were applied
    anyway. **Both readings clear the ~5,000-pair bar and both mean weights clear the 0.6 line**
    (0.7154 and 0.7186). Every pair lands in **1997**, one of the two years the reviewer's own merge
    audit prices highest for us. By TLD: `.org` 61,252 delegations, `.edu` 3,475, `.gov` 477,
    `.mil` 57; `root` and `arpa` yield zero by construction, the second because the canonicaliser
    now refuses reverse-DNS zones.
- it differs from the 13,324 first reported by 924 pairs, and the direction is the explanation: the
    store has banked more `.org` since, so fewer of the same names are net-new. A figure measured
    against a live store is a figure with a timestamp.
- potential: 95
- **it disproves a closed family**, and the correction is recorded where the claim was made, in the
    two zone-file rows of `sources.md`. `com` and `net` really are absent at this host, so the reopen
    condition is precise: any other mirror of `ftp.internic.net/domain/` whose crawler took a full-size
    `com` or `net` file. A complete `.org` proves such mirrors existed.
- dossier: `docs/archive/source-dossiers.md`, entry of 2026-08-18.

Decision: pending

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

### content_filter_blacklists / artifact_listing
- Found 2026-08-18, and **PRICED the same day**: it is the only lead in three hunt rounds to clear the
    volume bar on a full-population measurement, and the family reduces to one artifact.
- **MEASURED, full population, against the live store: 11,006 net-new (domain, year) pairs, 6,301.0
    equivalent-English, mean weight 0.5725, every pair in 2001.** Reading both editions instead of
    diffing them gives 13,724 pairs. Volume clears the ~5,000 bar by 2.2x; the mean weight is **below**
    the 0.6 good line rather than above it, and above 0.4, so it needs no volume justification.
- the artifact: `squidGuard`'s robot-compiled blacklist, of which exactly two editions survive, both
    2001, from Wayback captures of `ftp.ost.eltele.no/pub/www/proxy/squidGuard/contrib/`.
    `blacklists.20010710.tar.gz` sha256 `cc339bfad82cb3bce296eace1fba7ab68ad9455fa044fd0f9caee02887b226f2`,
    `blacklists.20010911.tar.gz` sha256 `46a817be48e3dc48f8b97f951927295f3d33b86f25949be22e20ad1bc2aa4eb5`,
    both on disk under `data/raw/probes/squidguard/`. The collector is trivial: two files, 2 MB.
- what dates one item: each category file's own compile header, *"compiled in 33:22:40 on 2001.09.09
    09:48:47 ... from 2402 link sources and 463098 links, of which 381583 tested successfully"*. That
    makes it a **crawl log rather than a printed listing**, which is why it is not the Netcraft law-2
    failure. Used as a July-to-September first-appearance diff anyway.
- **law 5 is absent by construction and was verified, not asserted**: a robot wrote the names, so there
    are no author-invented placeholders. 0 of 30 hand-audited. A matched RDAP ladder separates the
    populations: in-window creation dates 11 of 30 for names the store already dates 2001, 7 of 30 for
    the actual yield, **0 of 30** for names with no store attestation, Fisher p=0.0105. All 71 TLDs
    existed on 2001-09-09, and one bare `.co` in 30,916 names.
- **THE OBJECTION THAT MATTERS, and it is why this is not an obvious yes.** The increment is 100%
    year-fill and **zero new domains**: 99.3% of survivors are already dated 2000. And 14 of 14 probed
    accepted names carry a 2001 capture in the Internet Archive's own index, as do 10 of 12 random names
    squidGuard never mentions from the same population, so the pair arrives from the archive whether or
    not this source names the domain. On that reading the source is worth about 9,756 saved CDX
    requests, roughly 14 hours of one engine, rather than 6,301 equivalent-English of new knowledge.
- two smaller deductions if it is folded in: the 442 `mail/domains` names have **no compile header at
    all** and should be dropped, and if the class is approved master-eligible with no split the pipeline
    banks 15,443 pre-split pairs, including 4,437 unattested names that measured 0 of 30 on in-window
    registry creation.
- the family's other members (CyberNOT, SurfWatch, Bess, N2H2, DansGuardian, urlblacklist, MESD) are
    closed for want of two dated editions. The one question that would widen it: whether a 1999 or 2000
    squidGuard blacklist survives on a Linux distribution or university mirror.
- potential: 72
- Self-dating as an edition, but see the first-appearance rule below.
- what it is: in-window **domain-based** web content-filter blacklists: the CyberNOT list disclosed in
    the March 2000 cphack proceedings, SurfWatch, Bess and N2H2 residues, and the earliest squidGuard
    and DansGuardian tarballs of 1999 to 2001.
- what dates one item: the dated release edition, admitted **only as a first-appearance diff across
    consecutive editions**, so the claim is the edition in which a classifier first saw the site. An
    accumulating list otherwise dates a name at or before its edition, which is law 2 exactly.
- why it is not the closed anti-spam row: that was killed because MAPS RBL, ORBS, the DUL and SPEWS are
    **IP-based and contain no domains**. A content filter must list hostnames by construction.
- the population is adult and warez hosts, which is short life plus low traffic and heavily `.com`, the
    profile `discovery.md` says pays. `junkfilter_dated_blocklist`, already queued, is the ad-blocking
    cousin at an estimated 3,000 to 8,000 pairs.
- potential: 58

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

### repository_ia_capture_census / cdx_timestamp
- self-dating, so **no corroboration split**. Found 2026-08-18.
- what it is: another precomputed Internet Archive capture census deposited as a research replication
    package. The precedent is not speculative: `dartmouth_nber_captures` is exactly this shape and is
    worth 227,273 net-new pairs and 142,084.0 equivalent-English.
- where to look: openICPSR, Harvard Dataverse, OSF and Dryad, with DataCite or OpenAIRE as the one API
    that searches all of them, targeting replication packages of 2010-2025 economics, information
    systems and communication papers that were given or bought an IA slice.
- what dates one item: a 14-digit capture timestamp per row, identical semantics to the approved source.
- why it is not already closed: the 2026-08-15 dataset sweep asked those hosts for **domain lists** and
    recorded in its own entry that the query shape was wrong and one should ask for the dating artifact
    instead. That corrected query was never re-run, and ICPSR, OSF and Dryad appear in no tracked file.
- law 1 does not bite: `discovery.md`'s exception is precisely a bulk projection of IA holdings.
- check before pricing: that the deposit is a capture index rather than a bare URL list.
- potential: 70

Decision: pending

### ted_ojs_notices_1996_2001 / link_source
- potential: 70

Decision: pending

### excite_query_logs / dated_directory
- Found 2026-08-18 by the round-four completeness critic, and it is the best-shaped lead in the queue
    because it attacks the one population a crawler-derived baseline cannot contain by construction.
- what it is: search-engine and portal **query logs** of the window: Excite 1997, 1999 and 2001 as
    distributed by Jansen and Spink, Ask Jeeves 2001, the MetaCrawler and Dogpile academic sets. The
    users' side of the engine rather than the crawler's side.
- what dates one item: the log line's own server timestamp, machine-written at the moment a user typed
    the name, so the date attaches to the observation itself and not to a container.
- **why it is not the closed search-engine row**: that row established that no engine ever published a
    dated hostname LIST, which is a fact about crawler output. A query log is the opposite artifact, and
    its population is what people knew from television, packaging and word of mouth. A domain that was
    advertised on a cereal box and never linked to is invisible to every crawl and present here.
- volume: the 1997 Excite log is 1,025,910 queries for one day and the later logs are the same order,
    with the IR literature putting URL-shaped queries at a few percent, so order 10,000 to 100,000 dated
    typed mentions per log. ESTIMATE, not measured.
- **the availability screen is DONE, and it came back the good way.** Probed 2026-08-18:
    `faculty.ist.psu.edu/jjansen/` is HTTP 200 and links to a transaction-log page offering six logs, of
    which **three are in window**: `Excite_1997_small`, `Excite_1997_large`, `Excite_2001`. Access is
    neither a fee nor an agreement, which is what killed the NIST route: *"Please email me if you would
    like access to one or more of the transaction logs"*, after which he *"will place the file(s) on an
    ftp site for you"*. `data.html` is a 404, so the log page is the only route and it is the live one.
- so the remaining blocker is **one email in Ivo's name**, and it sits under `## OPEN` in
    `key-decisions.md` beside the USAC request rather than as a second entry.
- what is still unmeasured, and it is the novelty risk rather than the volume: most of what people type
    is famous, so the pairs may all be held. Measure the split's survival rate on the first log before
    parsing the other two.
- typed by a human, so it takes the corroboration split, which is what makes wide extraction safe.
- potential: 68

Decision: pending

### early_bulk_whois_snapshot / whois_creation
- self-dating, so **no corroboration split**. Found 2026-08-18.
- what it is: a bulk whois or registry snapshot of **vintage 2002 to 2008** rather than 2024, carrying a
    `created_at` field. Hunt it as a file on academictorrents, HuggingFace, Kaggle, GitHub releases,
    university mirrors and the pre-CZDS registrar distributions.
- what dates one item: the registry creation date in the row, the same semantics `domain_creation_bulk`
    already runs on, **so the collector exists and only the file is missing**.
- why it is not the closed zone-file family: those are names without dates. This is a dated snapshot.
- what makes it worth hunting, measured: a 2024 snapshot structurally cannot see a name that died
    before 2024, and on `.se` alone **32,332 of the store's 65,291 in-window domains (49.5%) are absent
    from the 2024 live zone**, against a 2024 file that still paid 649,475 post-split pairs.
- potential: 65

Decision: pending

### sbir_sttr_award_pi_email_2000_2001 / dated_directory
- potential: 65

Decision: pending

### usco_bulk_registrations / typed
- potential: 63

Decision: pending

### discmaster_by_file_size / artifact_listing
- Found 2026-08-18. A different question to the same index, and the reason it is separate matters.
- what it is: `discmaster.textfiles.com` queried by **FILE SIZE** rather than by link-artifact filename,
    hunting the one-file-many-names payload on period media: InterNIC or registrar name dumps, `hosts`
    files, `*.dom` files, ISP customer-domain exports, mail-server relay tables.
- **why it is not the closed `discmaster_media_index` row**: that row priced three populations which are
    all **one name per file** (120,127 `.url` shortcuts, bookmarks and hotlists, 273,212 deduplicated
    `.txt`), so every measurement in it is a density-per-item measurement. Nobody asked the index the
    size question. And the register's zone-file and bulk-snapshot closures are all about **web** routes
    (Wayback, RIPE, DNS-OARC, nic.ddn.mil) rather than about physical media.
- what dates one item: the media file date corroborated against the disc's own release date. The closed
    pass already validated that direction: of 11,811 in-window `ADD_DATE` values, 81.2% equal the media
    year, 18.8% are earlier and **zero are later**.
- **the 0.042-per-item ceiling does not govern this route at all**, which is the point: a single hit of
    this shape carries 100,000+ names. The screen is a handful of JSON queries filtered to size above
    roughly 256 KB with in-window file dates.
- the caveat carried over from the closed row: 77.7% of in-window `.url` files sit inside an installer,
    where the date describes a packaging event and errs in **both** directions. A bulk list on a disc has
    only the disc date, so check for nesting before quoting a year.
- **PROBED 2026-08-18, and the route works.** First payload found was a complete April 1998 `.jp`
    registry listing, 42,701 lines, self-dating from its own header and carrying its own connected flag.
    Priced: 87.5% already held, **3,062 net-new pairs at 185.3 equivalent-English**, rejected on both bar
    conditions. Full verdict in `sources.md`. Two operational facts for the next pass: `dedup=1` kills
    the connection and every other parameter is fine, and `.domains` as a filename yields nothing else
    of size.
- so what remains is the **high-weight** version of the same query, which is where the value would be: a
    `.uk`, `.au` or `.ca` registry listing of the period is worth 16x per name against `.jp` at 0.0605.
- potential: 62

Decision: pending

### uk_gazette_addressed_notices_1998_2001 / link_source
- potential: 62

Decision: pending

### courtlistener_caselaw / dated_directory
- potential: 60

Decision: pending

### cybernot_cphack_blacklist / artifact_listing
- Found 2026-08-18, and it is the named reopen condition on the squidGuard row rather than a new family.
- what it is: the CyberPatrol **CyberNOT** list as published in the March 2000 cphack proceedings, plus
    SurfWatch, X-Stop, Bess and the earliest MESD or urlblacklist editions. Read as dated listings of
    sites **a human rater actually visited**.
- what dates one item: the edition or update-file date. Unlike Netcraft, the entry exists because a
    rater loaded the page, so listing-to-liveness is **one inference shorter** than the step law 2 killed.
    Admitted only as a first-appearance diff across consecutive editions.
- why it is not the closed anti-spam row: that was killed on the **unit** before any fetch, because every
    in-window RBL is IP-based. A content filter's unit is a hostname by construction.
- the population is the one selected for **disapproval** rather than promotion or authority, which is the
    short-life low-traffic shape that made UDRP dockets 87.7% net-new, and it is why squidGuard measured
    20 of 27 sampled names with no current registration at all.
- volume: contemporaneous reporting puts a single CyberNOT edition at order 100,000 URLs with several
    editions a year. ESTIMATE from published accounts, not measured. One edition would be 20x the pair
    bar, and the deciding count is cheap because it is one file per edition rather than 119,000 items.
- potential: 60

Decision: pending

### discmaster_media_index / dated_directory
- Found 2026-08-18. Takes the corroboration split for a link page; a browser history is self-dating.
- what it is: `discmaster.textfiles.com`, a searchable index over the **contents** of archived CD-ROM,
    floppy, hard-disk and FTP-mirror items. Probed live: HTTP 200, 9,889 bytes, reporting 1,870,232,668
    files across 43,452 items and 125.3 TiB.
- what to query for: period link pages, `.url` shortcuts, `bookmark.htm`, `hosts` files, mIRC and WS_FTP
    site lists, and Netscape `history.dat` or IE `index.dat` profiles whose per-visit timestamps are
    machine-written.
- what dates one item: the file's own filesystem date on the media, which is the `page_directory` shape,
    or a per-visit timestamp for a browser history, which is **orthogonal to every crawl**.
- the trap to guard: a re-mastered or zeroed mtime. Corroborate the file date against the disc's own
    release date before quoting either.
- why it is not the closed shareware-disc family: that was closed because archive.org cannot list inside
    an ISO, so density cost a whole ISO download per item and the items carried no date metadata.
    **Discmaster is the missing index**, it is built from user uploads rather than IA crawls so law 1
    does not apply, and no lens has looked at media contents at all.
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

### usenet_quoted_whois / whois_creation
- self-dating, so **no corroboration split**. Found 2026-08-18 by the completeness critic on the
    non-IA hunt, and it is the only one of that hunt's seven leads already carrying a measurement.
- what it is: NSI-format and ccTLD-format `whois` output **pasted into message bodies** in
    `news.admin.net-abuse.*` and `alt.domain-names.*`, and in the Enron and pipermail corpora. The
    411 GB Usenet archive is already on disk, so this costs no requests at all.
- what dates one item: the registry's own `Record created on DD-Mon-YYYY` line inside the quoted
    record, paired with the `Domain Name:` or `(FOO-DOM)` handle in the same block. **The paste date is
    irrelevant to the year claimed**, which is the property that makes deleted names reachable.
- the trap to guard: a paste that has been re-wrapped or truncated so the creation date attaches to the
    neighbouring domain. Require the name and the date inside one block, never across a blank line.
- measured, positive control over the first 300 MB of `news.admin.net-abuse.email.mbox.zip`: 648
    creation-date lines, 283 with a name attached, 32 in-window pairs, 28 already held, **4 net-new**.
- PROJECTION, labelled: 0.0133 net-new pairs per MB gives roughly 5,500 over 411 GB, linear, with no
    saturation fitted. The register's own history says a linear fit over a corpus like this overstates.
- potential: 55

Decision: pending

### uspto_trademark_case_files / artifact_listing
- potential: 55

Decision: pending

### dnsrf_dap_udrp_multiprovider / artifact_listing
- potential: 52

Decision: pending

### isi_us_domain_registry / artifact_listing
- Found 2026-08-18. Self-dating as an edition, with the same first-appearance rule.
- what it is: the ISI RFC 1480 US Domain Registry delegation database, the hand-maintained registry for
    `k12.XX.us`, `lib.XX.us`, `ci.` and `co.` locality names. Recover it by CDXing the **file paths** of
    `isi.edu/in-notes/usdnr/` and `nic.us` rather than their pages, which is the method the Cybermetrics
    row established.
- what dates one item: the delegation file's own publication or approval date, the `uucp_map_registry`
    shape that paid 28,471 pairs.
- the trap to guard: a cumulative registry dates a name at or before the edition, so use a
    first-appearance diff across editions and never a single latest file.
- why it is not already closed: the register's `.us` locality work is all 2002-era **canvasses**
    (COG2002, NCES IMLS, GIAS) rather than the registry itself, and `isi.edu` appears only inside a
    seeds file.
- what makes it worth it: `.us` is the population the store is thinnest on, 18,278 distinct in-window
    against 216,581 `.uk`, at 0.9261 weight.
- probed 2026-08-18: `https://www.isi.edu/in-notes/usdnr/` is HTTP 404 with `https://www.isi.edu/` HTTP
    200 as the positive control, so the artifact must come from an archived path or an FTP mirror.
- potential: 52

Decision: pending

### reuters_rcv1_newswire / dated_directory
- Found 2026-08-18. Typed inside a dated artifact, so it **takes the corroboration split**.
- what it is: Reuters RCV1, 806,791 stories from 1996-08-20 to 1997-08-19, free from NIST under a signed
    agreement, plus its RCV2 and Gigaword siblings. Read as dot-com-era business prose that names a
    company's own website.
- what dates one item: the story's own dateline.
- why it clears the ceiling the scholarly lens established: at 0.042 net-new post-split pairs per item
    the 5,000-pair bar needs 119,062 items, and RCV1 has 806,791. That is roughly **33,900 pairs as a
    PROJECTION** on the family's own measured density, concentrated in 1996 and 1997, which are the two
    years the Internet Archive cannot supply in bulk.
- why it is not the closed trade-press row: that is OCR'd magazines. This is born-digital newswire.
- the trap to guard: the retrofit mechanism measured on 2026-08-18, where 7 of 25 post-split survivors
    were publisher-injected boilerplate. Strip boilerplate before counting.
- the blocker is an **access agreement** rather than engineering, which is the one thing here that
    genuinely needs a human.
- potential: 50

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

### scene_nfo_archives / dated_directory
- Found 2026-08-18. Typed inside a dated artifact, so it **takes the corroboration split**.
- what it is: underground release-scene text archives, `defacto2` and its peers: NFO files,
    `FILE_ID.DIZ`, courier and BBS advertisements, 1996 to 2001, bulk-downloadable from a non-IA host so
    law 1 does not apply.
- what dates one item: the release date in the archive's own per-file metadata, repeated inside the NFO.
- **why no lens has touched it**: the register covers shareware and CD catalogues, defacement mirrors and
    Usenet bodies. This is the one text population of the era that **deliberately avoided being indexed**,
    so the usual rule that a source exists to make a site known points the other way for once.
- volume: order 100,000 dated files with heavy in-window density at roughly one to two hostnames each,
    so 100,000+ mentions before the split. ESTIMATE from the site's own counts.
- **the honest risk, stated by the finder**: the split then removes exactly the hidden names that make
    the population interesting, since a site that avoided being indexed is a site no other source dates.
    Measure the split's survival rate first, because that single number decides the lead.
- potential: 45

Decision: pending
### uspto_tm_marktext / dated_directory
- potential: 40

Decision: pending

### ia_webdataservices_cctld_extraction / cdx_timestamp
- self-dating, so **no corroboration split**. Found 2026-08-18. Two lenses proposed it separately
  (`iawds_pl_cctld_2001` and `pl_2001_extraction_cdx`); they are the same artifact.
- what it is: the Internet Archive's "Web Data Services" national extraction collections. The measured
  one is `Poland_pl-ccTLD_2001-12-31`: 19 items, 204,743,552,253 bytes of ARC payload, each item also
  publishing a cluster CDX index and per-ARC `.arc.os.cdx.gz` derivatives.
- what dates one item: field 2 of every CDX row, a 14-digit capture timestamp. The same field the
  project already trusts for `arquivo_ia` and `early_web_cdx`.
- measured, not projected: all 19 merged indexes downloaded, 1,240,317,860 bytes, 36,117,804 CDX rows
  parsed through this project's own canonicaliser. **69,542 net-new pairs but only 7,441.0
  equivalent-English**, because the population is 100% `.pl` at weight 0.1070.
- **so it is a large source and a small one**, and the honest reading is that it clears the 5,000-pair
  bar and sits far below `discovery.md`'s 0.4 mean-weight line. 97.0% of the net-new lands in 2001,
  the one year the reviewer's own audit says we already win 982,881 to 267, and 1996 and 1997
  contribute one pair each. Low priority on its own terms.
- potential: 34
- **its real value is the register row it falsifies, and that is worth more than the source.**
  `sources.md` closed the Alexa/IA donated-crawl CDX family on 2026-08-15 because "a ranged GET returns
  HTTP 401 ... the restriction covers the index files and not merely the payload WARCs". Here the
  `.cdx.gz` derivatives return **HTTP 200 with no authentication** while the `.arc.gz` payload beside
  them returns 403. The 401 is a per-collection policy, not an archive-wide one, and it does not reach
  `webdataservices`. **The follow-up was chased on 2026-08-18 and the literal question is measured
  dry: no ccTLD extraction of this shape exists for a high-weight namespace.** Enumerated through
  archive.org's own APIs rather than by guessing item names: `collection:webdataservices` returns
  numFound 797 over 783 unique identifiers, and exactly one member matches `/ccTLD/i`, the Polish one.
  `mediatype:collection AND title:(ccTLD)` over all of archive.org returns 1. The
  `*-EXTRACTION-*ARC_arc` naming pattern does not generalise: the scrape API gives 26, being the 19
  Polish items and 7 NHK ones. Ten obvious analogues were probed by identifier and none exists.
  **And the wider version of the question is answered too, negatively.** `webdataservices` does hold
  non-ccTLD extractions of the same shape with equally public CDX, and both were measured and
  rejected the same day: the six-item US federal government extraction covering exactly 1996-2001 is
  worth **56.2 equivalent-English**, and the 659-item Dartmouth/NBER payload family is worth **zero**
  and is the payload of a source already banked. Both rows are in `sources.md`. So the shape is real,
  retrievable and empty for us, which makes this entry's own `.pl` figure the best the family offers.

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

### uk_trade_press_extension / dated_directory
- Screened 2026-08-18 and **deprioritised on the register's own refuted theory**, recorded so nobody
    proposes it a third time.
- the idea: the trade-press OCR route is adopted and works (5,389 pairs, 3,281.0 equivalent-English as
    `artifact_listing`), but it was measured on a hobbyist corpus and an American one. British titles
    (PCW, Internet Magazine, .net, Computer Shopper UK) would carry `.co.uk` at 0.9813 instead of `.com`
    at 0.6321, a 1.55x weight advantage per name on a route already proven.
- **why it is not worth the window.** This is a composition theory, and the register already tested one:
    `collection:computermagazines` being European and hobbyist was read as the cause of its shortfall,
    predicting the American weeklies would beat it several-fold, and they did not. Measured, both:
    hobbyist 0.641 equivalent-English per reachable item, American 0.449. Per-item yield is driven by how
    many URLs a periodical prints, which is low everywhere, not by which country printed it.
- and the corpus is **already partly British and European**: the mined `computermagazines` collection is
    `EnigmaAmiga`, `Elettronica2000`, `Electronique_et_Loisirs`, so the nationality premise is half
    false before any fetch.
- the arithmetic if someone insists: at the measured ~0.5 EE per reachable item, 3,000 in-window British
    items would be roughly 1,500 EE, and the weight advantage might lift it to ~2,300. That is real but
    it is a widening of a working route rather than a source, and it competes against leads with 10x the
    figure. PROJECTION, labelled, on the register's own per-item rate.
- reopen only with evidence that a specific British title prints URLs at several times the measured
    rate, which is a claim about density and not about nationality.
- potential: 22

Decision: pending
### cog2002_gid_school_systems_weburl / link_target
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

### openpgp_keyserver_dumps / link_target
- potential: 20
- **Measured and closed 2026-08-18, so this needs no decision.** The dump hosts were probed for the
    first time (nine dead, NXDOMAIN or 404; `keys.openpgp.org` publishes none by design;
    `pgp.key-server.io/sks-dump/` serves a squatted stub under HTTP 200). The retrievable curated
    substitute prices at **69 net-new pairs and 44.4 equivalent-English**, 70x under the bar, and the
    dating premise was separately disproved: a key creation timestamp dates the keypair, not the
    address, with 47.6% of user IDs bound in a later year and 0% earlier. Full verdict in
    `docs/sources.md`, two rows of 2026-08-18.

Decision: rejected

### nlm_medline_affiliation_email_1996_2001 / link_source
- potential: 3

Decision: rejected

### ffiec_call_report_webaddr / artifact_listing
- potential: 2

Decision: rejected



