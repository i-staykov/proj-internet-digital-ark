# Approved sources

**One `Decision:` line per (source, evidence type), and `ark ingest` enforces it** (ADR-003). A
master-eligible class with no `master` line here cannot date a year; the gate exits 2. Vocabulary:
`pending` (nobody has looked), `master` (may date a year), `candidate-only` (collect, never dates a
year), `rejected` (binds, and the request generator refuses to re-open it).

Generate a request with `scripts/request_approval.py <spec> --journal <journal>`: it builds a
seeded-random sample with live links and the measured figures, so a reviewer checks external evidence
rather than an agent's argument.


## Approved before this mechanism existed


### afnic_fr / whois_creation

- ingest specs: `afnic_fr`
- authority: phase 2; the registry documents that crDate resets on re-registration, quoted in sources.md

Decision: master

### arquivo_ia / cdx_timestamp

- ingest specs: `arquivo_ia`
- authority: phase 1, merged and credited 2026-07-27

Decision: master

### ukwa_geoindex / cdx_timestamp
- measured: 4509.1 net-new post-split EE over 4,595 pairs, re-counted 2026-08-24 against the live
  store; 4,559 of them `.uk` and 4,565 of them 2001

- ingest specs: `ukwa_geoindex`
- what dates one item: the 14-digit Internet Archive capture timestamp that prefixes every row, so a capture in 1999 evidences 1999 and nothing else. Nothing in the file was typed by a human, so no corroboration split
- the artifact: the geographic index of the JISC UK Web Domain Dataset, 11,217,295,098 bytes under CC Public Domain Mark 1.0 at `https://bl.iro.bl.uk/downloads/090bbffa-d82c-4641-ba72-0089e8ef885f`, one row per capture as `<14-digit timestamp>/<url><TAB><postcode>`, every `.uk` resource the
- potential: 100

Decision: master
Decided by Ivo, 2026-08-24. The grounds are the row itself: a 14-digit IA capture timestamp is a
record of the capture, so it dates that year and no other, and nothing in the file was typed. The
bulk-projection exception to killer 1 applies, as it did for `dartmouth_nber_captures`.

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
- **the evidential question was settled in phase 4 and the TERMS question was never asked, and on
  2026-08-27 it was.** All four registries this class has queried publish a terms notice inside the
  RDAP response itself, so it has been on disk the whole time. Read from our own journals and, for
  Verisign, from the page its notice links to:
  - **Verisign (`.com`, `.net`)**, `verisign.com/legal-center/rdap-terms/`: you will not use the data
    to "(2) enable high volume, automated, electronic processes that send queries or data to the
    systems of Verisign or an ICANN-accredited registrar, except as reasonably necessary to register
    domain names or modify existing registrations"
  - **PIR (`.org`)**: the same clause with the same registration-only carve-out, plus "Abuse of the
    RDAP system through data mining is mitigated by detecting and limiting bulk query access"
  - **Nominet (`.uk`)**: the same clause **with no carve-out at all**, and a second one that goes
    further than any of the others: "You are explicitly prohibited from extracting, copying and/or
    using or re-using in any form and by any means (electronically or not) all or part (quantitatively
    or qualitatively) of the contents of the RDAP database without prior and explicit permission from
    the Registry Operator"
  - **CIRA (`.ca`)**: rejected on the same clause this morning, before any of this was checked
- **so the rule this project already had, applied consistently, closes the class**: trap 8 in
  `CLAUDE.md` says to read past the record because the terms follow the data, names `.nz` as having
  cost 7,586 EE that way, and says in as many words that **`.uk` says the same thing**. The engine was
  pointed at Nominet on 2026-08-24 with the commit message "needing no approval", which was true of
  the evidence class and false of the terms
- **both engines were stopped on 2026-08-27 at 07:47 and 07:51** and no RDAP query has been sent since
- exposure, measured against `merged260827`: the class holds **748,099 pairs and 459,792.0 EE**
  (Verisign 711,894 / 433,749.9, PIR 20,917 / 14,853.2, CIRA 7,092 / 5,932.5, Nominet 4,714 / 4,625.8,
  other registries 3,482 / 630.6). **All but 1,615 pairs and 851.0 EE of it is already submitted and
  merged into his baseline**, so the withdrawable part is 851.0 EE: Verisign 600.9, PIR 131.4,
  Nominet 118.7. The cost of stopping is the route's future, not a restatement of the past
- the `.ca` pairs are the sharpest part of it. The `cira_ca_rdap` entry below says "one query was spent
  on evaluation", and that is wrong: **7,092 `.ca` pairs were already banked** through the
  `rdap.org` redirector, which 302s to the authoritative server, so a per-TLD decision was never
  reached because the sweep never asked per TLD
- **the decision stays `master`, and that is deliberate rather than convenient.** What Verisign and PIR
  prohibit is *sending* the queries, and every pair already in the store came from a response already
  received: replaying a stored journal sends nothing. Setting the class to `pending` would also break
  `just journals`, which is the reproduction path the shipped archive tells a reviewer to run, and it
  would withdraw 458,941 EE the reviewer has already merged on a reading the terms do not support
- **what is closed is COLLECTION, and it is closed in code rather than in a note.** `ark rdap` now
  refuses every registry whose terms have been read and prohibit it, and needs
  `ARK_RDAP_TERMS_OVERRIDE=1` plus a named authority to send a single query. A comment in a docstring
  is what allowed the Nominet engine to start three days after `CLAUDE.md` recorded that `.uk` says
  the same thing
- **Nominet is the one slice where USE is prohibited too**, by the extraction clause, and that is Ivo's
  call rather than mine: 4,714 pairs and 4,625.8 EE in total, of which 121 pairs and 118.7 EE are
  net-new and unshipped. The rest is already in his baseline
- **what needs Ivo's ruling.** (1) Whether to send a permission letter of the RIPE kind to Verisign,
  PIR or Nominet, which is the only thing that reopens the route. (2) Whether the 118.7 EE of unshipped
  Nominet pairs are withdrawn from this round. The other 732.3 EE of unshipped RDAP pairs are not in
  question

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

## Decided, with the request that was reviewed


### udrp_proceedings / artifact_listing

- ingest spec: `udrp_proceedings`
- source: https://www.icann.org/udrp/proceedings-list.htm
- journal: `data/raw/udrp/udrp_proceedings.jsonl.gz`

Decision: master

### netcraft_survey_cache / artifact_listing

- source: archived Netcraft Web Server Survey `/domains/cache/<word>.html` listing pages, via the
- journal: `data/raw/probes/H008-decide.jsonl` (19 of the 20 in-window captures; `silly.html` failed on a

Decision: candidate-only

### dartmouth_nber_captures / cdx_timestamp

- ingest spec: `dartmouth_nber_captures`
- source: archive.org item `DARTMOUTH-NBER-RESEARCH-2017-metadata`, downloaded 2026-08-16. **The item
- journal: `data/raw/dartmouth_nber/domain-year-captures.txt`

Decision: master

### domain_creation_bulk / whois_creation

- ingest spec: `domain_creation_bulk`
- source: https://www.kaggle.com/datasets/wotschofsky/171-million-domain-names-whois-dns-dnssec
- journal: `data/raw/domain_creation/domains.csv`

Decision: master

## Pending requests


### internic_zone / artifact_listing
- measured: 8814.04 net-new post-split EE over 12,322 pairs, re-counted 2026-08-24 against the live store, `.arpa` excluded because the export drops it
- what dates one item: the zone's own SOA serial inside the artifact, `1997041800`, and an NS delegation is the registry stating the name existed that day

- ingest spec: `internic_zone`
- source: https://web.archive.org/web/19970420113748id_/http://nic.mil/oroot.html/org.zone.gz
- journal: `data/raw/internic_zones/org.zone.gz`

Decision: master
Decided by Ivo, 2026-08-24. The grounds are the artifact alone: the SOA serial `1997041800` sits on
line 2 inside the payload, and an IA crawl two days later fixes when the file existed. An NS record
in a zone is the delegation itself rather than a description of one, which is why killer 2 does not
reach it: the registry was serving that name at that instant.

## Found, awaiting triage

### chastity_list_blacklist / dated_directory

- measured: **14,229.0 net-new post-split EE over 24,927 (domain, year) pairs at 2001**, measured
  2026-08-27 against `merged260827`. 136,743 list lines across 13 categories yield 97,937 distinct
  registrable domains, of which **92,059 are already held, 94.0%**, and 24,927 are held with no 2001
  record. **The split costs nothing here by construction**: the corroboration test is "another source
  already places this domain in `domain_year`", which is exactly what "held" means, so every one of the
  24,927 pairs sits on a corroborated domain. `.com` carries it at 20,149 pairs and 12,736.2 EE
- what dates one item: **the tar member header written by tar, `Dec 14 2001`, on every file in the
  archive**, plus per-date diff filenames inside the window that agree with it, for example
  `db/ads/domains.20011124.diff` and `db/ads/urls.20011103.diff`. This is the same argument already
  approved for the 1997 half of `junkfilter_dated_blocklist`, where a tar member header dated the
  edition. A blocklist entry is a claim that the site is live and serving now
- the artifact: `chastity-list_0.5.orig.tar.gz`, 720,609 bytes, from
  `https://archive.debian.org/debian/pool/main/c/chastity-list/`. The chastity project's ACL files for
  squidGuard, by Roy-Magne Mo. **Licence GNU GPL v2, verbatim in `COPYING`**, and the README carries
  "Roy-Magne Mo, rmo@sunnmore.net, 2001". Staged at `data/raw/chastity/`
- how it was found, since the method is the reusable part: `archive.debian.org` has no robots.txt, and
  ONE request per release for `dists/<rel>/main/binary-i386/Packages.gz` indexes every package and
  description in that release. Grepping the potato and woody indexes for blocklist-shaped descriptions
  gave 41 and 81 candidates, and the largest in woody was this one at 701,038 bytes, described as
  "blacklists for SquidGuard". **This is the `ls-lR` trick applied to a package archive.**
- the sibling is out of window and is noted so nobody fetches it twice:
  `chastity-list_0.5.20020928.orig.tar.gz` is stamped `Sep 28 2002`
- ingest specs: not written. No parser is registered until this is decided
- potential: 90

Decision: pending

### ncua_5300_call_report_webaddr / artifact_listing

- measured: 1328.31 net-new post-split EE over 1,998 (domain, year) pairs, measured 2026-08-25 over all
  16 in-window quarters. An agent got 1,289.84 independently; the two agree within 3%
- what dates one item: `CYCLE_DATE` on every `fs220d` row, the quarter the call report covers
- potential: 88

Decision: pending

### fac_sfsac_historic_1998_2001 / artifact_listing

- what dates one item: `AUDITEEDATESIGNED`, "Date of auditee signature", per filing
- potential: 86

Decision: pending

### gias_england_school_website_domains / link_target

- potential: 82

Decision: pending

### nces_imls_pls_web_addr_1998_2001 / typed

- potential: 82

Decision: pending

### sec_edgar_filings / dated_directory

- measured: 5884 net-new post-split EE, 2026-08-24. **RE-MEASURED 2026-08-26 by sampling, and the
  figure is right in order of magnitude but wrong in shape: the yield is almost entirely in 2000-2001
  and is zero in 1999.** Two strata, both against the live store: **1999 QTR1, n=389 filings, 496
  mentions, 81 distinct pairs, 0 net-new, 0.0000 EE per filing**; **2001 QTR4, n=248, 350 mentions, 94
  distinct pairs, 13 net-new, 8.0 EE, 0.0324 EE per filing**
- what dates one item: the filing's own `Date Filed` in `full-index/<year>/QTR<n>/form.idx`
- potential: 72

Decision: pending

### govinfo_cbd_bulk / typed

- potential: 71

Decision: pending

### mynic_my_change_report / artifact_listing

- measured: 3091.1 net-new post-split EE pre-split over 4,078 pairs from 25 of 60 pages, or **159.9 EE
  over 211 pairs if the corroboration split applies**; whole-tree figures land near 10,000 and 400
- what dates one item: the per-day heading above each entry, `2 April 2001`, with `New` or `Delete`
  beside the name, so the registry is stating that this name entered or left the register that day
- ingest specs: not yet written; the parser is measured but no spec is registered until this is decided
- the artifact: MYNIC published a fortnightly `Domain Name Listing` at
  `mynic.net.my/my/stats/<month><year>-{1,2}.htm`. 60 archived pages, of which the `-1` and `-2` halves
  carry names and the bare-month pages are statistics tables only. `.my` weighs 0.7580
- potential: 70

Decision: pending

### usco_bulk_registrations / typed

- potential: 63

Decision: pending

### coza_deletion_listing / cdx_timestamp

- measured: 2720.6 net-new post-split EE over 2,810 pairs, counted 2026-08-24 over 10 of the 11 archived
  captures on `co.za`; an agent measured a wider tree including `posix.co.za` at 4,462 EE and I have not
  verified that half
- what dates one item: the Wayback capture stamp on the page, since the listing carries no in-body date
  at all, and a name shortlisted for deletion is one the registry is stating is registered right now
- the artifact: the CO.ZA registry's own `cgi-bin/warn.sh` and `cgi-bin/todel.sh`, 11 in-window
  captures, listing bare labels under a header reading `The following domains are shortlisted for
  deletion. This is either due to lack of payment or lack of paperwork`. `.za` weighs 0.9682
- potential: 62

Decision: pending

### discmaster_media_index / dated_directory

- what it is: `discmaster.textfiles.com`, a searchable index over the **contents** of archived CD-ROM,
- what dates one item: the file's own filesystem date on the media, which is the `page_directory` shape,
- potential: 60

Decision: pending

### expiring_list_2002_term_inference / artifact_listing

- measured: 3,619.5 net-new post-split EE on the conservative reading, over 5,941 pairs, measured
  2026-08-25 against the live store. Two artifacts, priced separately and reproduced independently of
  the subagent that found them: `namewinner.com/whole_list.php?del=none` capture `20020407171418`,
  52,204 distinct domains, 2,543.2 EE; and `dailychanges.com detail/?ns=LAME-DELEGATION.ORG&date=2002-08-01`,
  4,511 domains, 1,565.3 EE (1,076.3 on the stricter adjacent-year measure)
- potential: 60

Decision: pending

### antispam_media_blocklist / artifact_listing

- measured: 1055.3 net-new post-split EE, measured 2026-08-25, for the two components carrying **no
  licence**. I repriced the larger one from the bytes and got **1,605 pairs and 967.1 EE** against an
  agent's 969.0, agreeing to 0.2%; SQDR adds 88.2
- what dates one item: the file's own timestamp on the preserved media, `2001-04-06`, shown in
  discmaster's listing row for `BlackList.json` and again on its parent `data.mdb`. Per EDITION,
  not per record, so the same shape as `junkfilter_dated_blocklist`
- potential: 58

Decision: pending

### cctld_register_listing_capture / cdx_timestamp

- measured: 3496.0 net-new post-split EE over 6,996 pairs across four registries, same provenance and
  same caveat as the entry above
- what dates one item: the Wayback capture stamp, since these editions carry no in-body date, and a
  register listing is the registry stating what stood in it when the crawler took the page
- the artifacts, one line each. **NIC Malta `.mt` register**, 1,624 pairs, **1,470.5 EE** at 0.9055, the
  highest weight in this batch. **SaudiNIC `AllSA`**, 2,944 pairs, **1,506.4 EE** at 0.5117, of which
  2,654 names are absent from the store in every year. **ISOC-IL `.il` 1998 register**, 1,915 pairs,
  **375.0 EE** at 0.1958, and only 641 of its 7,315 names are new, so `.il` 1998 is already well covered.
  **`.nu` `notrenewed.cfm`**, 517 pairs, **144.1 EE** at 0.2787
- potential: 56

Decision: pending

### fac_single_audit / dated_directory
- measured: 2406.69 net-new post-split EE, 2026-08-24

- what it is: e-mail domains on Federal Audit Clearinghouse Single Audit filings, 1998-2001
- what dates one item: that row's own `AUDITEEDATESIGNED` or `CPADATESIGNED`, the date a human wrote
  the address down
- potential: 54
- what makes it worth it: **2,406.69 net-new equivalent-English, measured 2026-08-24.** 18,698 rows were
  dropped for falling outside the window, mostly FY2001 audits signed in 2002: taking the audit year
  instead would have imported all of them silently

Decision: pending

### reuters_rcv1_newswire / dated_directory

- what it is: Reuters RCV1, 806,791 stories from 1996-08-20 to 1997-08-19, free from NIST under a signed
- what dates one item: the story's own dateline.
- potential: 50

Decision: pending

### cipo_ca_trademark_marktext_1996_2001 / typed

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

### nic_ve_cartelera / artifact_listing

- measured: 1131.3 net-new post-split EE over 3,885 pairs, **or 75.7 EE over 260 pairs if the
  corroboration split applies**; measured twice and the sceptic reproduced every figure to the unit
- what dates one item: the notice's own publication date on NIC Venezuela's `cartelera`, the registry's
  public notice board of names entering the register
- the artifact: 4,071 distinct `.ve` names, 4,281 pairs, 2000 n=1,746 and 2001 n=2,535. `.ve` weighs
  0.2912 and the store holds 5,733 in-window `.ve` pairs, verified
- potential: 44

Decision: pending

### usenet_quoted_whois / whois_creation

- measured: 90.41 net-new EE over 149 pairs, measured 2026-08-24 on the 146 densest archives, 14.4 GB
  of 383 GB. The figure was written into this entry as prose and so never reached the decision sheet,
  which listed the class as unpriced for a day; it is on its own line now. The projection for the whole
  corpus is under 3,000 EE and the sample was the dense end, so treat 90.41 as the measurement and
  3,000 as a ceiling that will not be reached
- what dates one item: the registry's own `Record created on DD-Mon-YYYY` line inside the quoted
  block, which dates the domain independently of when the message was posted
- potential: 40

Decision: pending

### uspto_tm_marktext / dated_directory

- potential: 40

Decision: pending

### zenodo_banner_ads / cdx_timestamp

- measured: 432.81 net-new post-split EE, whole file censused, 2026-08-24
- what dates one item: the 14-digit Wayback capture stamp on each appearance, verified against live CDX
  at 27 of 28 exact matches. Self-dating, so no split
- potential: 38

Decision: pending

**Grows without bound by design** (Ivo, 2026-08-12). One of two words per row: *candidate pool*
(`candidate-only`) or *fold in directly* (`master`). Nothing is blocked while an entry sits here,
since a pending class cannot date a year. Reaches `key-decisions.md` as a count, never one line each.

| # | Source | What dates an item | Type | Net-new pairs | EE | Evidence | Decision |
|--:|---|---|---|---|---|---|---|
| 0 | ukwa_geoindex | 14-digit capture timestamp per row | cdx_timestamp | **79,253 MEASURED** | **77,749.1 MEASURED** | MEASURED, whole file extracted 2026-08-20 | pending |
| 1 | can_domain_registry_notices | `Date-Approved:` on the notice | whois_creation | 11,418 self-dating / 936 split | 9,551.2 / 783.0 | MEASURED | pending |
| 2 | nominet_whois_port43 | registry `Registered on:` per name | whois_creation | ~9,500 ceiling | ~9,300 ceiling | ESTIMATE | pending |
| 3 | gias_england_school_website_domains | nothing in the file, Nominet per name | link_target | ~5,568 sch.uk | ~5,463 | MIXED | pending |
| 4 | ccew_charity_register_contact_domains | nothing in the file, CDX per name | link_target | ~5,200 | ~4,557 | MIXED | pending |
| 5 | ncua_5300_call_report_webaddr | CYCLE_DATE on every FS220D row | artifact_listing | 1,998 whole corpus | 1,328.3 whole corpus | MEASURED | pending |
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
| 26 | namewinner_expiring (formerly domain_aftermarket_listings_1999_2001) | the listing page's capture date | artifact_listing | unpriced | unpriced | none | pending |
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

### ia_webdataservices_cctld_extraction / cdx_timestamp

- what it is: the Internet Archive's "Web Data Services" national extraction collections. The measured
- what dates one item: field 2 of every CDX row, a 14-digit capture timestamp. The same field the
- potential: 34

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

- potential: 22

Decision: pending

### cog2002_gid_school_systems_weburl / link_target

- potential: 20

Decision: pending

### ripe_db_lastmodified / link_target

- potential: 12

Decision: pending

### ukwa_ds2_year_cdx / cdx_timestamp

- **ASKED AND ANSWERED: NO, AND NOT BEFORE AUTUMN 2026. Do not write to them again.** Ivo enquired
  through `openaccess@bl.uk` on 2026-07-22, citing the dataset record at
  `bl.iro.bl.uk/concern/datasets/3c39a755-5e3d-405b-9944-b13e76a87ad8` and the dead download location.
  Nora Ramsey, Assistant Web Archivist, replied for the UK Web Archive Team: "it is not currently
  possible to access dataset hosted on our servers. The UK Web Archive website remains offline
  following a cyber-attack on the British Library in October 2023 ... Our target for restoring access
  to digital collections is Autumn 2026. The first stage of restoration will include a URL lookup
  service", with full-text search and other features "reintroduced gradually thereafter"
- **so this is out of reach for this project, on two counts.** Autumn 2026 is later than the submission
  needs, and the first restored service is a per-URL lookup rather than a bulk download, which is not
  what a 13.45 GB CDX pull is. The data is preserved and the Library says so; it simply cannot be served
- the potential below is deliberately LOW and encodes obtainability, not value. On value this would
  still outrank everything else on the page. Nothing here is a reason to stop wanting it, and if the
  restoration lands early and includes bulk access it should be re-opened at once
- what it is: one CDX file per year, 1996 to 2013, in `webarchive.org.uk/datasets/ukwa.ds.2/cdx/`,
  the same JISC UK Web Domain Dataset directory that already gave us `geo/` (`ukwa_geoindex`, banked
  4,493 EE) and `linkage/` (`host-linkage.tsv.gz`, 116,467 pairs from its first 10.26%). The `cdx/`
  sibling had never been looked at. In-window sizes, compressed, read off the archived listing:
  1996 52,619,201; 1997 509,195,112; 1998 364,720,850; 1999 1,428,820,719; 2000 4,580,260,146;
  2001 6,515,380,682. **13.45 GB in window**, and 2001 is the largest in-window year
- what dates one item: field 2 of every CDX row, a 14-digit capture timestamp. Self-dating,
  machine-written, so no corroboration split, and the same field `dartmouth_bfs_seed` is admitted on
- why it would outrank everything else on this page: the population is the `.uk` crawl and `.uk`
  scores 0.9813, the highest weight in the model. Law 1 does not dismiss it, and the two siblings in
  the same dataset are the proof: both are equally IA-derived and both paid, because Ding's baseline
  is a merged sample rather than the whole `.uk` crawl, and our CDX engine can only ask about names
  it already holds. A full `.uk` CDX dump is discovery as well as dating
- the retrieval zero is proved rather than assumed, and it is now explained by the outage above. IA captured the
  directory listing and never the files: a prefix query for `ukwa.ds.2/cdx*` returns empty while the
  identical probe for `linkage/host-linkage.tsv.gz` returns its two known captures, so the emptiness
  is the archive's and not the query's. The publisher now answers every path with a 7-line HTML
  `400 Redirect` stub, including `robots.txt`. And no mirror exists: archive.org `advancedsearch.php`
  returns numFound 0 for both `jisc uk web domain dataset` and `ukwa.ds`
- **superseded.** This entry previously said the request should be sent FIRST, ahead of
  `ripe_dbase_1999`. That was written without checking whether we had already asked, and we had.
  `ripe_dbase_1999` is now unambiguously the top access request, because permission there is a decision
  someone can still take, whereas here there is no server to serve the file
- potential: 12. Scored on obtainability before submission, not on value: the British Library has
  already said no until Autumn 2026 and the first restored service is a URL lookup rather than bulk
  access. It sat at 100 for one evening on the assumption that nobody had asked yet

Decision: pending, but externally blocked. Nothing for Ivo to do here.

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

### ripe_dbase_changed / artifact_listing

- measured: 58,398.0 net-new post-split EE over **399,401 pairs**, measured 2026-08-26 against the
  live store. By year **1996 18,944 / 1997 67,515 / 1998 312,942**, and 1999 contributes ZERO because
  the snapshot's own date already banked that year. Top TLDs `de` 220,606, `dk` 51,034, `nl` 27,662,
  `it` 24,449, `no` 18,045, `at` 15,369
- what dates one item: the date on the `changed:` line itself. You cannot modify a registry object that
  does not exist, so `19980315` is the registry's own dated record that this registration existed then.
  Not an inference from a listing but an explicit transaction record inside the object, which is why
  killer 2 does not reach it
- potential: 100

Decision: master

Approved by Ivo 2026-08-26, on the condition that it is fully documented and that the reviewer can
inspect and discard it. Both are met: the grounds are stated in the round report's source table so
Prof. Ding sees WHY it was admitted and not only what it yielded, every pair carries its own evidence
row naming the `changed:` date it came from, and the shipped provenance parquet joins each pair to
that row. So the class can be removed by the reviewer without touching anything else.

The ruling: a dated `changed:` transaction on a registry object evidences that the registration
existed on that date. This satisfies rule 6 literally rather than by analogy, since rule 6 asks for
"its own record" for continued registration and a `changed:` line is exactly that. It extends the
existing snapshot decision rather than opening a new one, because it rests on the same premise, that
a RIPE `domain:` object is a real registration.

Checked before approval rather than asserted: the top eight changer addresses are all ccTLD registry
role accounts with DENIC alone at 49.4%, and the 1998 concentration is 643,788 lines over 368 distinct
day values rather than one bulk re-stamp.

### ripe_dbase_1999 / artifact_listing

- measured: 90799.4 net-new post-split EE over 641,241 (domain, 1999) pairs, measured 2026-08-24
  against the live store. A subagent measured 93,857.7 an hour earlier; the gap is the store growing
  underneath it, not a disagreement
- what dates one item: the file's own timestamp on line 2 of its header, `# 990804 00:07:01`, so a
  `domain:` object in it is the registry stating its database contents on 4 August 1999. Evidences
  1999 and no other year, per rule 6
- ingest spec: `ripe_dbase_1999`, reading `*dn:` and nothing else
- the artifact: `http://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz`, 71,919,736 bytes,
  `Last-Modified: Tue, 03 Aug 1999 21:27:00 GMT`
- potential: 99

Decision: master

Approved by Ivo 2026-08-26, after RIPE NCC granted the request. The licence question that blocked
this for two days is answered: Member Services replied that research use of publicly available data
is fine, and the only condition attached is request volume against the LIVE database, which cannot
bind a static file already on disk. The full exchange is recorded verbatim in `sources.md`, including
the honest limit that it is a support-desk reply which does not quote the 1999 notice back.

**The permission constrains the code, so the constraint is in the code.** Ivo's request promised to
read the domain objects and publish no personal data. `parse_ripe_dbase_1999` matches `*dn:` and
nothing else, four tests in `tests/test_sources.py` enforce it, and one of them fails on a leak of a
postal address, a phone number or an e-mail. That matters more than it looks: the file has no
`person:` objects, which invites the conclusion that there is nothing to protect, and the conclusion
is wrong. Contact details are inline in the domain objects under `*de`, `*ac`, `*tc` and `*ch`, and
three of those five codes are not obviously personal from their names.

Measured on the real file at ingest: 20,528,780 lines, 19,272,364 attributes discarded, 1,235,440
domain objects, 20,974 reverse zones skipped, header year read as 1999 rather than assumed, and
**zero values emitted that were not bare hostnames**. 1,232,554 distinct registrable names, 68.9%
already held at some year, **641,038 net-new pairs at 1999 worth 90,770.3 equivalent-English**. That
is 29 EE below the figure measured on 2026-08-24, the difference being the store growing underneath
it, not a disagreement.

### us_domain_delegated / artifact_listing

- measured: 12,775.5 net-new post-split EE over 13,816 pairs, measured 2026-08-25 with the
  project's own `price_items.py` against the live store, over the union of the 1996, 1999, 2000 and
  2001 editions. Mean weight 0.9247. By year 1996 2,284 / 1999 4,185 / 2000 3,823 / 2001 3,524. The
  2001 edition alone is 3,524 pairs and 3,247.3 EE. Gross was 15,270.0 and must not be quoted
- what dates one item: the artifact asserts the delegation state of the namespace, and the instant is
  fixed twice. Tar-preserved mtimes 1996-10-09, 1996-11-20 and 1999-03-22 with six rotations whose
  chain is monotone in both date and size (425,505 to 426,388 bytes over Feb-Mar 1999, continuing
  monotone into the captures at 433,937 to 435,847); and `cdx_timestamp` on the 2000-08-15,
  2000-12-06, 2001-04-11 and 2001-06-06 captures. A delegation is the registry serving the name at
  that instant rather than a description of one, which is why killer 2 does not reach it, exactly as
  for `internic_zone`
- potential: 99

Decision: master

Approved by Ivo 2026-08-26 after reviewing the artifact and its receipts. The grounds are the
delegation argument, not overlap: a delegated-zone list is the registry serving those names at the
instant the edition is stamped, the same instrument as a DNS zone file, which is why killer 2 does
not reach it. Machine-generated, so no corroboration split. Evidences the edition's own year and no
other, per rule 6. Column 2 only, so contact mail domains are never read as delegations.

### iedr_register / artifact_listing

- measured: 18845.9 net-new post-split EE over 19,341 pairs, one measurement over both trees on
  2026-08-24; the 2001 tree alone was counted three times independently and agreed to within 0.3%
- what dates one item: the page's own machine-written line, `updated automatically at 14:51 GMT on
  Friday, 21 December 2001`, and a register regeneration is the registry stating what was registered
  at that instant
- ingest specs: `iedr_register`
- the artifact: the IE Domain Registry, run by University College Dublin Computing Services, published
  the whole `.ie` register as static A-Z pages. Two trees: `/statistics/` gives 26 in-window pages and
  24,805 names at December 2001, and the earlier `/lists/` gives 8 pages at November 1999 and March 2000.
  `l-doms.html` resolves to a March 2002 edition and the parser drops it whole. `stalled.html` is PENDING
  APPLICATIONS and is excluded by filename, because reading it would invent registrations
- potential: 96

Decision: master
Decided by Ivo, 2026-08-24. The reason is the artifact's own semantics: a cron regenerated the
whole register and stamped the page with the instant it did so, and an IA crawl fixes when that
page existed. The 99.6% agreement with `prior_task` on the 2000 edition corroborates that reading;
it is not the grounds for it.

### nic_mil_internic_zone_mirror / artifact_listing

- what it is: the Defense Data Network NIC at `nic.mil` mirrored InterNIC's zone-file distribution over
- what dates one item: the zone's own SOA serial in `YYYYMMDDNN` form, `1997041800`, **inside the
- potential: 95

Decision: rejected
Superseded, not refused on merit. This is the same artifact as `internic_zone`, which Ivo approved
master on 2026-08-24 and which is banked at 12,320 net-new 1997 pairs and 8,813.3 EE. All six zones
from this mirror are in the ingest ledger: `arpa`, `edu`, `gov`, `mil`, `org`, `root`. Rejected so the
request generator stops reopening a duplicate of a decided source; the evidence stands under the other
name. Closed by the agent rather than by Ivo because admitting nothing new is not an approval.

### squidguard_2001_blacklist / artifact_listing

- measured: 10736.2 net-new post-split EE over 18,588 (domain, 2001) pairs, measured 2026-08-25.
  **Reconciled to the decimal with an agent's independent figure** after my first pass read only the 11
  `domains` files and returned 8,118.0; the `urls` files and the 2001-dated diffs are equally the robot's
  own output, and including them gives 44,130 canonical names and 10,736.2 EE
- what dates one item: the list's own header line, `# This list was compiled in 0:00:20 on 2001.12.18
  15:04:29.`, corroborated by the tar member mtime `Dec 18 2001` and by dated diffs running
  `domains.20010814.diff` through `domains.20011218.diff`
- ingest spec: `squidguard_2001_blacklist`. Format is one host per line with `#` comments, 11
  category directories each holding `domains`, `urls` and dated diffs
- potential: 92

Decision: master

Approved by Ivo 2026-08-26 after the artifact was re-verified live. The grounds are the header's
assertion of a successful fetch, `compiled from 2402 link sources and 654820 links, of which 510389
tested successfully`, plus the robot naming itself, so nothing here was typed by a person and no
corroboration split applies. Dated by the list's own stamp (all between 2001.12.15 and 2001.12.18)
or by the diff filename. GPL v2, so licence-clear. Content is mostly adult, gambling, drugs and
warez domains, which Ivo was shown before approving.

**Banked at 10,376.9 EE over 18,000 pairs, NOT the 10,736.2 measured earlier**, and the gap is
deliberate: a diff's `-` lines are removals, which evidence a host ceasing to answer rather than
being live, so 35,230 of them are dropped. The earlier figure counted them. Also skipped:
`squidguard-mail-domains`, the one file in the archive with no compile header, which is a
hand-kept list of free-webmail providers rather than robot output.

### uk_historic_hansard / dated_directory

- potential: 84

Decision: rejected
Measured 2026-08-25 at **0.00 net-new post-split EE**, and it is the most instructive negative of the
batch because it passes the item screen 9.7x over and still pays nothing. 1,002 sitting days enumerated
exactly from all 72 month indexes, ~235,270 section pages at a measured 234.8 per day. Sampled **1,795
section pages and 3,260,082 words**, and they contain **exactly 5 URLs**: `dti.gov.uk`, `fco.gov.uk`,
`homeoffice.gov.uk`, `edwarddavey.co.uk`, `ecb.int`. **All 5 pairs already held.** Density is 0.0028
gross pairs per item, **15x below the 0.042 prose ceiling**. Reweighted to the true section mix
(written answers are 77.9% of pages, sampled 1 in 7) the whole corpus carries ~479 URL mentions, so even
if every one were a distinct never-held `.uk` name the ceiling is 470 EE, under the floor. Dated by
`HC Deb 21 February 1996 vol 272 cc137-8W` printed on the page; human-typed, a Minister speaking. No
bulk exists and mySociety's parlparse is `Disallow: /pwdata`.

### usac_erate_form471_contact_email_1998_2001 / dated_directory

- potential: 84

Decision: rejected
Measured 2026-08-25: **there is no in-window data published, so there is nothing to price.** The
`opendata.usac.org` dataset `9s6i-myen` has exactly the right columns (`funding_year`, `cnct_email`,
`org_email`, `aut_email`) and a `$group=funding_year` count returns **2017-2026 only**; `avi8-svp9`
returns 2016-2026. The portal's own description on `gifc-3grz` settles it: "provides users with the
ability to search, view, and download FCC Form 471 data for **Funding Year 2016+**. To request older
records, please email opendata@usac.org." The legacy host `data.usac.org` publishes no robots.txt and
403s on `/publicreports/`. Everything on the portal is EPC current state in any case, so killer 4 would
apply even if the years were there. Reopen only if someone makes that e-mail request and receives files.

### eric_fulltext_1996_2001 / dated_directory

- potential: 83

Decision: rejected
Measured 2026-08-25 at **12.98 net-new post-split EE over 296 documents**, and rejected on COST rather
than on the band. **The ERIC API is up again**, so this can be re-classified from UNRETRIEVABLE, and the
reachable population is **52,354** documents with ERIC full text (`e_fulltextauth:1`), not the 77,079 a
pool ratio first suggested. Dated per document and cleanly: `publicationdateyear` is a separate field
from `e_yearadded`, so the publication year is not borrowed from the accession year.
**It passes the density screen and fails the authority screen, which is the finding.** Raw URL density
is **0.339 per 1,000 words over 5,003,152 words, 221x Hansard's 0.00153**, so grey literature really does
print URLs. But **93.0% of its pairs are already held**, above the abandon line, and 38 of 57 net-new
pairs die to the split as OCR damage (120 of 1,174 host observations rejected outright, the killed bucket
holding `oracle` and `grainger` as TLDs and `educatiorialliance.org`).
**`.edu` is where the apparent high weight evaporates**: the union holds **184 `.edu` pairs and exactly
one survives** (`educause.edu` 1997), so the survivors' mean weight is 0.6833 and they are 15 `.org`
against 1 `.edu`.
**Two honest limits on the band.** Sampling was NOT uniform: the API sorts `ED` documents ahead of `EJ`
ones, so both samples come from two accession blocks per year (offsets 0 and 4000) covering roughly the
first 4,200 of ~8,700. Between those blocks yield differs **5.5x** (0.0707 against 0.0129 EE per item) at
similar raw density, the difference being entirely split survival, so both samples are biased upward by
the rich block. And with 19 survivors, Poisson alone is +/-40%. Whole-corpus band therefore **~700 to
2,900 EE**, straddling the floor.
**Cost is what settles it**: 52,354 PDF fetches and ~36 GB at the observed 690 KB mean is **0.044 EE per
request**, about 125 hours at the measured 7 PDFs/min, against querying's ~3,000 EE/hour. Record the lens
finding, do not collect the corpus.

### educause_edu_whois_activation / whois_creation

- potential: 78

Decision: rejected

### ucsf_industry_documents / dated_directory

- potential: 78

Decision: rejected
**Fifth entry today whose `- measured:` line was lost in the 2026-08-23 compaction; the measurement has
existed since 2026-08-24.** `docs/sources.md` records it in full: the solr index gives 3,826,999
in-window documents, dated per document (`'documentdate' = '1996 January 24'`), non-IA and properly
enriched rather than sampled blind, 0.76% of documents containing `www` and **6,000 of those fetched end
to end**. 5,462 pairs, 3,522 already held, **1,940 net-new gross for 1,284.4 EE and 216 pairs for 146.6
EE after the split**, because 89% of the net-new names are dated nowhere else. Whole-population
projection about **730 EE post-split**, under the floor. The TLD census names the other half of the
problem: `cam` appears 34 times, which is `com` misread, so the net-new half and the OCR-damaged half are
the same population.

### oireachtas_debates_xml / dated_directory

- potential: 77

Decision: rejected
Measured 2026-08-25 at **0.00 net-new post-split EE**, and decidable on arithmetic before any download:
**1,527 debate records** in window (1996: 247 through 2001: 299) against the ~24,438 items that `.ie` at
0.9744 needs for a 1,000 EE bar, so the corpus is **16x too small**. Measured anyway on 119 records
(7.8%, random across all six years, 68.2 MB): 19 distinct pairs, **18 already held (94.7%)**, and the
mentions are `irlgov.ie`, `doh.ie`, `entemp.ie`, `welfare.ie`, the authority core. Dated by
`<FRBRdate date="1999-02-03" name="#generation"/>`; human-typed, a TD speaking. Note the store's `.ie`
position changed under this source's feet: after the IEDR register was banked it holds 55,432 in-window
`.ie` pairs over 27,067 domains, so saturation is far higher than a week ago.

### dartmouth_bfs_seed / cdx_timestamp

- measured: 1419.9 net-new post-split EE over 2,460 pairs, measured 2026-08-24 over the COMPLETE level 0,
  three of three files and 13.6 MB, not sampled
- what dates one item: the 14-digit Internet Archive capture timestamp in field 2 of each CDX line, with
  field 5 the HTTP status, so only in-window 200s are read. Self-dating, machine-written, no split
- ingest specs: `dartmouth_bfs_seed`
- the artifact: IA ran a breadth-first crawl seeded with URLs pulled from SEC 10-K filings and deposited
  it as `Dartmouth_10KwebURLs_GWB-20180911224740_BFS_4-lvls`, 204 items and 2,064 GB under
  `CorporationWebsitesCollection`. **Only BFS level 0, the seed layer, is worth reading.**
- source: https://archive.org/details/Dartmouth_10KwebURLs_GWB-20180911224740_BFS_4-lvls
- potential: 74

Decision: master

Approved by Ivo 2026-08-26. `cdx_timestamp`: field 2 of every CDX row is a 14-digit capture stamp, so
each row is self-dating and takes no corroboration split, and field 5 is the HTTP status so only
in-window 200s are read. Same evidence field the CDX engines are admitted on.

Level 0 only, and that is the whole source rather than a sample of it: levels 2 and 3 measured 0.00,
0.00 and 0.59 EE per MB against level 0's 104.7, and the 102 `_warc` items hold 2012-2019 with zero
in-window rows. Lineage is `internet_archive`, since this is IA's own crawl indexed by IA, which
costs a corroboration statistic and is the correct trade.

### junkfilter_dated_blocklist / dated_directory

- measured: 2189.4 net-new post-split EE over 3,553 pairs, measured 2026-08-25. Verified two ways: my
  own run over the 13 in-window `jf-domains` editions gave 3,122 pairs and 1,924.1 EE, and the
  difference is exactly the 431 pairs at 1997 that live in the two tarballs I did not open, so the two
  measurements agree to the pair
- what dates one item: three independent machine-written stamps agreeing. The HTTP header on the file
  itself, `last-modified: Tue, 29 May 2001 07:10:09 GMT`; the in-body `$Id: junkfilter,v 2.36
  2001/05/28 20:00:08 gsutter Exp $` and `JFVERSION=20010528` in the same release; and for the 1997
  half a tar member header, `-rw-r--r-- 0 gsutter staff 43879 Dec  6  1997 junkfilter/jf-domains`
- the artifact: Gregory Sutter's procmail spam filter. `jf-domains` is one `|`-joined line of
  backslash-escaped literal hostnames. **The triage note guessed these were escaped regexps and
  wildcards rather than hostnames, and that is refuted**: 42,005 of 42,034 tokens are domain-shaped,
  99.9%
- potential: 74

- **approved by Ivo, 2026-08-27**: "junkfilter_dated_blocklist and early_bulk_whois_snapshot
  can be ingested."

Decision: master

### content_filter_blacklists / artifact_listing

- the artifact: `squidGuard`'s robot-compiled blacklist, of which exactly two editions survive, both
- what dates one item: each category file's own compile header, *"compiled in 33:22:40 on 2001.09.09
- potential: 72
- what dates one item: the dated release edition, admitted **only as a first-appearance diff across
- potential: 58

Decision: rejected
Measured 2026-08-25 at **32.2 EE**, and closed on a ceiling rather than on the measurement. **The
artifact that mattered is gone from the live web**: the 16 March 2000 decoded CyberNOT list, 40,715
hostnames, had one publication route at `cphack.robinlionheart.com`, which is **NXDOMAIN on both the
system resolver and 8.8.8.8**; the apex resolves only to a ZoneEdit forwarder returning HTTP 400. The
two surviving cphack mirrors, `cyberpetrol.978.org` and `linas.org/banned/cp4break/`, carry the paper
and no `blacklist/` path. What does survive is the COPA Commission's mirror of peacefire at
`govinfo.library.unt.edu`, whose one real name list is `SurfWatch/first-1000-com.txt`, 1,000 names,
dated in body `8/2/2000` and "as of June 14, 2000". Measured: 497 already held, **51 pairs post-split,
32.2 EE**, all `.com`. **The whole surviving artifact ceilings at 1,000 x 0.6321 = 632.1 EE, below the
floor before anything is measured.** The squidGuard half of this entry was already closed on era
(2026-08-24, artifact is 2003). Reopen condition: a non-Wayback mirror of the decoded cphack blacklist;
four searches found none.

### nominet_whois_port43 / whois_creation

- potential: 72

Decision: rejected
**Rejected on Ivo's own standing decision, not on the measurement, and the measurement is the reason to
record it carefully.** The port-43 door is genuinely open where RDAP was shut: 432 queries at 0.5 q/s
with **zero refusals**, against this register's "3 refusals in the first fourteen queries" for Nominet
RDAP. Two random-sampled pools over the 560,548 addressable `.uk` domains project **~81,419 EE**
(measured 32.38 EE over 300 queries; Wilson 95% band 55,946 to 115,872), at 0.1636 EE per query, **1.8x
Verisign's measured 0.091**. Dated by `Relevant dates: / Registered on: 14-Oct-1997`.
**But Ivo already stopped a Nominet bulk engine for legality on 2026-08-24**, answering O5: "I am paid
for this work, so if that makes bulk queries illegal, let's not do it." The port-43 footer states the
terms verbatim and they name exactly what we would do: "You may not access the .uk WHOIS or use any data
from it except as permitted by the terms of use... which includes restrictions on: (A) use of the data
for advertising, or its repackaging, recompilation, redistribution or reuse... and (C) exceeding query
rate or volume limits." A 481,543-query sweep and a shipped master file are repackaging and volume.
**Two traps recorded because they would silently fabricate yield.** `*.ac.uk` and `*.gov.uk`
third-levels return the PARENT record (`newoldlabour.gov.uk` gives `Domain name: gov.uk`); re-querying
all 128 dated hits found 10 such mismatches and every one returned `before Aug-1996`, so scoring that
string as 1996 would have invented ~12% of the yield. And `before Aug-1996` carries no year at all.
Positive control: `bbc.co.uk` answered in the same minutes as the 100 no-match responses. Also noted
in-band: "WHOIS service for .UK will cease on 9th of February 2027".

### ipgod_au_marktext / dated_directory

- potential: 71

Decision: rejected
**Blocked by robots at the only distribution host, and rejected on the screen rather than parked.**
IPGOD is published only on `data.gov.au`, whose host-root `robots.txt` is, in full after the comments,
`User-agent: * / Disallow: /` (HTTP 200, 552 bytes). That is the `app.fac.gov` condition, so nothing was
fetched. The sub-path `data.gov.au/data/robots.txt` is permissive, but the standard is host-scoped and
the root file governs; that conflict is a human call. `researchdata.edu.au/ipgod2022/3792412` is metadata
whose two download links point back into `data.gov.au`, and `www.ipaustralia.gov.au` serves no bulk file.
Rejected because the screen answers it without the exemption: mark text is applicant-typed so it takes
the corroboration split, which cost MYNIC 19x and junkfilter 2.2x, and this register already closed the
USPTO version on authority selection plus the intent-to-use dating defect. Both objections apply
unchanged to AU marks.

### cira_ca_rdap / whois_creation

- potential: 70
- measured: **~25,377 EE ceiling, not a measured yield.** The store holds 103,541 distinct `.ca`
  domains in window with 376,315 empty year slots between them. At the 29.3% in-window rate measured
  on Nominet `.uk`, that is about 30,337 pairs at `.ca`'s 0.8365, so ~25,377 EE. A pilot would
  replace the estimate, and no pilot has been run because of the licence question below
- what dates one item: the registry's own `registration` event, the same `whois_creation` semantics
  already approved for `rdap_snapshot`. Verified live on one name: `rita.ca` returns
  `('registration', '2001-02-01T17:11:06Z')`, in window
- the artifact: `https://rdap.ca.fury.ca/rdap/domain/<name>`, reached through the IANA bootstrap at
  `https://data.iana.org/rdap/dns.json`, so `ark rdap` already knows how to get there
- **THE TERMS WERE READ ON 2026-08-27 AND THEY FORBID IT, ON FOUR SEPARATE GROUNDS.** The page answers
  HTTP 403 behind a Cloudflare challenge to an honest User-Agent, so Ivo fetched it from a browser and
  left the text at `private/cira.c-terms-of-use`. The record's Legal Notice binds use of the service to
  it, and it says:
  - s.10(c): "use any robot, spider, site search/retrieval application, or other device to retrieve or
    index any portion of the Website to collect information about other users **or domain names**". That
    clause names our exact purpose
  - s.11: WHOIS may be used "solely" to query availability, identify a holder, or contact a holder.
    Building an annual domain census is none of the three, and "you may not use the WHOIS information
    for any other purpose"
  - s.11, prohibited uses: "unauthorised aggregation or collection of information from the WHOIS
    database". A bulk creation-date harvest is aggregation by definition
  - s.11: "You may not use automated processes that send multiple queries ... except as reasonably
    necessary to register domain names or modify existing registrations"
  - s.4 grants a content licence for "non-commercial purposes" only, and this work is paid
- so this is the `.nz` shape and it ends the same way. `.nz` cost 7,586 EE by reading past the record
  to the terms; `.ca` costs the ~25,377 EE ceiling for the same reason, and the cost is the correct
  price of the rule. `robots.txt` was never the obstacle: it is 8 lines, names no agent and disallows
  only `/wp-admin/`, `/?s=`, `/page/*/?s=` and `/search/`
- **it can only be reopened by CIRA's written permission**, of the kind RIPE gave, asking to derive
  `(domain, year)` pairs only and publish no registrant data. Nothing else changes the reading
- one query was spent on evaluation and nothing further will be sent

- **rejected on the Terms of Use read 2026-08-27**, not on evidence. Reopen only on written
  CIRA permission of the RIPE kind

Decision: rejected



### repository_ia_capture_census / cdx_timestamp

- what dates one item: a 14-digit capture timestamp per row, identical semantics to the approved source.
- potential: 70

Decision: rejected
**Not unpriced, mis-filed: the fourth entry today whose `- measured:` line was lost in the 2026-08-23
compaction.** Measured 2026-08-18 and recorded in `docs/sources.md`: UMN DRUM `10.13020/D62684`, "Link
Lists for Websites Tracking the Development of the Early Web from 1996 to 2000", 74.83 GB in 16 tar
parts, and **45,130 of 45,130 sampled pairs already held, 1 net-new pair worth 0.63 EE over 226,171 real
rows**, with 97,904 of 97,905 source-side pairs already dated that exact year. Payload presence is
established by that read, which is the test the payload-less UKWA CDX sibling failed. Licence is
Attribution-NonCommercial-ShareAlike 3.0 US. Killer 1 in its documented-exception form, and **the
exception did not fire**: this census is a projection of the same index our baseline was built from.
Access note for anyone returning: `conservancy.umn.edu` 403s an honest User-Agent behind Azure WAF, and
`api.datacite.org` answers the DOI in full.

### ted_ojs_notices_1996_2001 / link_source

- potential: 70

Decision: rejected
Not measured, because **the bulk download is robots-disallowed at the only host that has it**. The
in-window packages do exist: `ted.europa.eu/en/simap/xml-bulk-download/-/xml-files/monthly/1998` lists
12 monthly files and the year selector runs to 1993, but every endpoint sits under
`ted.europa.eu/packages/...` and TED's robots.txt carries `Disallow: /packages/*` for `User-agent: *`.
Not fetched. The structured alternative `ted-csv` on `data.europa.eu` has 48 distributions spanning
**2006-2024 only**, entirely outside the window, and EUR-Lex returns 202 with zero bytes for robots.txt
so it is off limits too. Rejected rather than parked on the screen: OJ S notices are pan-European
contracting authorities, so the histogram would be dominated by `fr` 0.1021, `de` 0.1324 and `it`
0.1421, needing roughly 6,700 pairs rather than 1,019, on top of killer 5 for address-block URLs a
human typed and killer 3 for ministries and municipalities.

### excite_query_logs / dated_directory

- what dates one item: the log line's own server timestamp, machine-written at the moment a user typed
- potential: 68

Decision: rejected
Not measured, because **no bytes are obtainable**. Four in-window logs are listed at
`faculty.ist.psu.edu/jjansen/academic/transaction_logs.html` (Excite 1997 small and large, 1999, 2001)
and none has a download link; the access instruction is verbatim "Please email me, Jim Jansen
(jjansen@acm.org), if you would like access to one or more of the transaction logs." Cross-checked
against Jeff Huang's aggregator of public query logs, whose **earliest entry is AOL 2006** and which
lists no Excite log. Rejected rather than parked because two structural problems would need answering
even if the file arrived: **killer 5 in its purest form**, since a query string is a human keystroke so
every novel name takes the split and earns no year; and killer 3 from the demand side, since search
volume concentrates on popular sites, which is the population the store is already saturated on.
**Reopen cheaply if Ivo wants to spend one e-mail**: ask for `Excite_1997_large` and `Excite_2001` only,
and price before requesting the rest.

### early_bulk_whois_snapshot / whois_creation

- what dates one item: the registry creation date in the row, the same semantics `domain_creation_bulk`
- measured: 2968.49 net-new post-split EE over 4,747 (domain, year) pairs, measured 2026-08-25 across
  three sibling listings. **Corroborated on the largest of the three by an independent per-block parse**:
  8,718 record blocks, 5,239 carrying a creation date, 4,228 in-window pairs, 3,491 net-new, 2,195.92 EE,
  with novelty at 23.9% against the agent's 25.8%. Both the block count and the dated count match exactly
- what dates one item: the record's own `Dates of creation / last modification / expiration:
  27-Feb-2000 / 15-Feb-2002 / 27-Feb-2003`, or on a sibling `Registered on: Sep 29, 2001`, under the
  page's own "All data is as of January-October 2003"
- the artifact: Ben Edelman's whois transcriptions, "Last Updated: June 2, 2002", on space at the Berkman
  Center for Internet & Society at Harvard Law School. Three sibling listings, 81 pages, 13,507,154
  bytes, 15,990 entries, 8,787 carrying a creation date:
  `cyber.harvard.edu/archived_content/people/edelman/{invalid-whois/nicgod,renewals/tina,typo-domains/list}-*.html`
- potential: 65

- **approved by Ivo, 2026-08-27**: "junkfilter_dated_blocklist and early_bulk_whois_snapshot
  can be ingested."

Decision: master

### sbir_sttr_award_pi_email_2000_2001 / dated_directory

- potential: 65

Decision: rejected
Measured 2026-08-25 and closed under Ivo's 1,000 EE floor. 502.05 EE over the whole 1996-2001 window,
169.14 EE at the 2000-2001 scope this entry actually asks for. **Killer 4, proven rather than argued**:
of 10,189 in-window rows whose `Company Website` canonicalises, **89 carry a TLD that did not exist in
2001** (`.space` 37, `.biz` 19, `.aero` 17, `.ai` 11, `.tech` 5). A 1998 award row cannot have carried a
`.space` domain, so the column is current state refreshed later under an old `Award Year`. Both address
columns are self-reported, so the split applies on top. 219,503 rows in
`data.www.sbir.gov/mod_awarddatapublic_no_abstract/award_data_no_abstract.csv`, 29,922 in window, and
3,502 of 5,017 candidate pairs already held.

### discmaster_by_file_size / artifact_listing

- what dates one item: the media file date corroborated against the disc's own release date. The closed
- potential: 62

Decision: rejected
**Not an open question, a bookkeeping gap.** `docs/sources.md` closed this on 2026-08-18 with full
working under "Discmaster by file size, and the April 1998 `.jp` registry listing it found":
`email.domains`, 2,085,500 bytes, 42,701 lines, self-dating from its own header "Registered Domains in
JP (Apr 30 1998): 42143", priced at 36,187 pairs, **31,686 already held (87.5%), 3,062 net-new
post-split, 185.3 EE** at mean weight 0.0605, rejected on both bar conditions. The `- measured:` line
was lost in the 2026-08-23 compaction, which is why it reappeared as unpriced. **The recorded reopen
condition remains untested rather than refuted**: the search endpoint's `file=` parameter is silently
ignored, returning 25 unrelated rows, and the `q=` with `qfields=file` route timed out at 120s on three
consecutive queries.

### jpnic_register / artifact_listing

- measured: 1623.0 net-new post-split EE over 26,827 (domain, 1999) pairs, measured 2026-08-24 against
  the live store. An agent reported the same figure; I reparsed and repriced from the bytes and it
  agrees to the decimal
- what dates one item: the file's own header line, `Registered Domains in JP (Apr 30 1999): 72769`, so
  the registry is stating its register's contents on 30 April 1999. Machine-generated, no split.
  Evidences 1999 and no other year, per rule 6
- ingest specs: `jpnic_register`
- the artifact: `https://tomocha.net/files/dns/domain-list.txt`, 6,185,475 bytes,
  `Last-Modified: Fri, 30 Apr 1999 04:43:08 GMT`. JPNIC's own register of every registered `.jp` name,
  frozen on a personal DNS document mirror while JPNIC's own tree kept only policy prose
- potential: 62

Decision: rejected
**Withdrawn on citizenship, not on evidence. The measurement stands at 1,623 EE and must not be used.**
`tomocha.net/robots.txt` carries, at lines 51-52 of a 61-line file, `User-agent: ClaudeBot` /
`Disallow: /`. **That is a by-name refusal covering the whole host.** When this source was proposed on
2026-08-25 the agent read only the first ten lines of that file, saw `Allow: /files/` under
`User-agent: *`, and proceeded; the refusal is 41 lines further down. So the 6,185,475-byte fetch of
`domain-list.txt` was taken from a host that refuses us, and this class cannot be admitted however good
the artifact is.
**The rule this cost 1,623 EE to learn: read the WHOLE robots.txt, not its head.** A by-name group can
sit anywhere in the file, and a permissive `User-agent: *` block at the top does not override it. The
project's off-limits list now carries `tomocha.net` beside `cryptome.org`, `tbtf.com`,
`www.openpgp.net` and `ftp.nluug.nl`.
**If the artifact is ever wanted, it needs a different route**: JPNIC's own tree holds policy prose only,
so someone would have to find another mirror of the 1999-04-30 register, or ask JPNIC. Its licence is
genuinely permissive (JPNIC's open-document notice grants free redistribution), which makes the loss
here entirely self-inflicted.

### uk_gazette_addressed_notices_1998_2001 / link_source

- potential: 62

Decision: rejected
Measured 2026-08-25 at **0.98 EE over 1 pair**, projecting ~50 EE and ceilinged at ~500. Passes the item
screen 20x over (**490,740 notices**, from the Atom feed's own `rel="last"`) and still fails, which is
the same lesson as Hansard. **The URL-bearing population is tiny and was measured rather than assumed**:
`text=www` returns 720 notices and `text=http` 360, while `text=co.uk` (3,080) and `text=.com` (910) are
**tokenisation artefacts proved as such** (43 `co.uk` hits yielded 2 notices carrying a domain, 8 `.com`
hits yielded 0, against 14 of 14 precision on the `www` stratum). Sample of 69 notices across three
strata: 13 distinct pairs, **12 already held (92.3%)**. Killer 3 visible in the sample, `wales.gov.uk`
alone being 3 of 18 hits. Dated `Publication date: 29 June 1998`; human-typed, the advertiser drafts the
notice.

### courtlistener_caselaw / dated_directory

- potential: 60

Decision: rejected
Closed 2026-08-25 on access AND on content, so no exemption would help. **Access**: `static.case.law` is
`User-agent: * / Disallow: /`, `case.law` disallows `/caselaw/`, and `www.courtlistener.com`
blanket-403s us at CloudFront ("Request blocked"), all treated as refusals and not evaded. **Content, via
the one permitted route**: a complete 25,676-opinion shard on the Hugging Face CAP mirror, **432,051,278
characters and roughly 69 million words, contains ZERO occurrences of `http://`, `https://` or `www.`**,
against same-shard controls returning 23,548 rows for `Circuit` and 62 for `.com`. Judicial opinions do
not print URLs, which is the density screen failing about as hard as it can. **And the mirrors carry no
decision-date field at all**: `created` is the 2024 ingest timestamp on every row, so a `dated_directory`
reading would have to parse the date out of the opinion text. The measured shard is 1972-77 so it does
not price the window directly, but the format facts are corpus-wide.
Same population as `caselaw_access_project_opinions` from a second publisher, closed together and for the
same reasons; treat them as one artifact in future.

### cybernot_cphack_blacklist / artifact_listing

- what dates one item: the edition or update-file date. Unlike Netcraft, the entry exists because a
- potential: 60

Decision: rejected
Measured 2026-08-25 as the CyberNOT half of `content_filter_blacklists`, which was rejected in the same
pass, so this is one artifact under two entries. **The 40,715-hostname decoded list is gone from the
live web**: its one publication route, `cphack.robinlionheart.com`, is NXDOMAIN on both the system
resolver and 8.8.8.8, and the apex resolves only to a ZoneEdit forwarder returning HTTP 400. The two
surviving cphack mirrors, `cyberpetrol.978.org` and `linas.org/banned/cp4break/`, carry the paper and no
`blacklist/` path; four searches found no other copy outside Wayback. The largest surviving related
artifact, peacefire's `SurfWatch/first-1000-com.txt`, is 1,000 names measured at **32.2 EE** and
**ceilings at 632.1 EE even at 100% novelty**, below the floor before anything is measured. Reopen
condition: a non-Wayback mirror of the decoded blacklist.

### pmc_oa_subset_fulltext_1998_2001 / link_source

- potential: 60

Decision: rejected
Measured and recorded at **0 net-new EE**; the table row already reads `0 / 0.0 / MEASURED` and only this
entry's `- measured:` line was lost. 299 articles, 5.89 MB, **5 net-new pairs and every one of them
`creativecommons.org`**, dated 1996 to 2000 from a `<license>` element **added to the XML decades after
publication**. That is killer 4 in a form worth remembering: a modern element inside an old document
carries the old document's date unless the parser knows better.

### caselaw_access_project_opinions / dated_directory

- potential: 58

Decision: rejected
Closed 2026-08-25 on access AND on content, so no exemption would help. **Access**: `static.case.law` is
`User-agent: * / Disallow: /`, `case.law` disallows `/caselaw/`, and `www.courtlistener.com`
blanket-403s us at CloudFront ("Request blocked"), all treated as refusals and not evaded. **Content, via
the one permitted route**: a complete 25,676-opinion shard on the Hugging Face CAP mirror, **432,051,278
characters and roughly 69 million words, contains ZERO occurrences of `http://`, `https://` or `www.`**,
against same-shard controls returning 23,548 rows for `Circuit` and 62 for `.com`. Judicial opinions do
not print URLs, which is the density screen failing about as hard as it can. **And the mirrors carry no
decision-date field at all**: `created` is the 2024 ingest timestamp on every row, so a `dated_directory`
reading would have to parse the date out of the opinion text. The measured shard is 1972-77 so it does
not price the window directly, but the format facts are corpus-wide.

### cctld_register_listing_inbody / artifact_listing

- measured: 2855.6 net-new post-split EE over 12,251 pairs across three registries, each measured twice
  by independent agents against the live store; **I verified the store side of every figure myself and it
  reproduces exactly** (`.tw` 43,981 in-window names and 1,283 `idv.tw`, `.lu` 1999 holdings), but I have
  not re-parsed the artifacts
- what dates one item: the page's own machine-written timestamp, `更新時間: 2001/8/27 20:0:31` on TWNIC's
  frozen-domain list and a cron line on RESTENA's, so the registry is stating the register's contents at
  that instant
- the artifacts, one line each. **TWNIC `.tw` frozen-domain list** `twnic.net.tw/DN/fz1.shtml`, 9,529
  net-new pairs, **1,275.0 EE** at 0.1338: names whose registration expired between 2001-05-29 and
  2001-08-26, so every one was in the register during 2001 and the artifact implies nothing about another
  year. **IDNIC `.id` unpaid list** `idnic.net.id/Info/RekapBelumBayar.html`, 2,162 pairs, **872.6 EE** at
  0.4036. **RESTENA `.lu` register**, 1,865 pairs, **708.5 EE** at 0.3799
- potential: 58

Decision: master

Approved by Ivo 2026-08-26. `artifact_listing`: a registry that wrote its register to a static page
carrying its own machine-written timestamp is stating the register's contents at that instant, which
is the zone-file argument. Nothing is typed by a person, so no corroboration split.

**Banked at 1,609.6 EE over 10,177 pairs, below the recorded 2,855.6, and two reasons are worth
separating.** Only two of the three artifacts were retrievable in time: TWNIC 9,318 names and IDNIC
1,671, with RESTENA `.lu` (708.5 EE) still to fetch. And IDNIC is dated conservatively, from its own
`Jatuh Tempo` due-date column only, rather than also from the capture stamp; the recorded 2,162 pairs
for 1,671 names implies the earlier measurement counted both routes. One route per artifact is the
cleaner claim and it is what shipped.

### sec_form_adv_part1_2000_2001 / artifact_listing

- potential: 58

Decision: rejected
Measured 2026-08-25 at **674.42 net-new post-split EE** over 1,076 pairs, under the floor. The only
genuinely open one of its batch, and an era vintage does exist: `www.sec.gov/files/adv-filing-data-20001019-20111104.zip`,
249,976,083 bytes, read by HTTP range over the ZIP central directory so ~52 MB moved rather than 250.
**Licence: none found**, and US federal work so 17 USC 105 applies by default. Dated per filing by its own
`DateSubmitted`, verbatim `"07/17/2001 12:56:08 PM"` on FilingID 16215 with `FormVersion "02/2001"`,
joining to a Schedule D 1.I `Website` of `"WWW.CONSECOSECURITIES.COM"`. **Anachronism test passed**: 1
`.biz` domain among 4,052 in-window, 0.02%, against the 89-of-10,189 that condemned SBIR. Selection is
not what kills it either, at 82.5% already-held on domains and 56.7% on pairs, both under the abandon
line. **It dies on item count**: IARD went live on **2000-10-19**, so the era-vintage window is 14.5
months of 72 and everything before was paper that was never digitised. Density is fine, 0.075 post-split
pairs per filing, which beats the 0.042 prose ceiling. The monthly IAPD compilation series that covers
more advisers starts at **June 2006** and is a current-state snapshot, so killer 4 closes the reopen
route. The free-text `Schedule_D_Miscellaneous` adds **0.63 EE** over 72,468 rows.

### can_domain_registry_notices / whois_creation

- measured: 8768.2 EE **is what your one-word ruling is worth**, and that is why this row shows that
  number rather than either raw figure. The artifact measures **9551.2 EE over 11,418 pairs if the
  registry self-dates** and **783.0 EE over 936 pairs if a human typed it**; the 936 are already
  banked, so the incremental prize is 10,482 pairs and 8,768.2 EE. Both raw figures are in this
  file's triage table, measured, row 1
- what dates one item: `Date-Approved:` on the notice
- potential: 55

Decision: master

Approved by Ivo 2026-08-26. The ruling: a `Date-Approved:` field printed by the registry inside its
own approval notice IS the registry stating its database, not prose a human typed. Grounds: the
fields are machine-formatted with aligned columns and ISO-style dates, the approval is the registry's
own act rather than a description of somebody else's, and this is the registry publishing its own
process in public. So it is `whois_creation`, and rule 6 gives that year and no other.

Re-measured at approval against the live store: **9,485 net-new pairs, 7,934.2 EE**, below the 8,768
on record because the store grew underneath it. Approvals fall 1996 7,766 / 1997 9,520 / 1998 15,133
/ 1999 4,473 / 2000 0 / 2001 0, so 36,133 in-window pairs collapse to 9,485 under rule 6.

`Date-Modified:` was checked as a possible second route and is worth nothing: nine in-window records
in the whole archive, 0.0 EE.

**The archive is not the one a search finds first.** `usenet-can.domain` and a `FULL-USENET-BACKUP`
item are 208 KB and 124 KB, hold ZERO `Date-Approved:` fields and date 2003-2009. The real archive is
`archive.org/download/usenet-can/can.domain.mbox.zip`, 14,326,153 bytes, 37,578 approval fields.

### uspto_trademark_case_files / artifact_listing

- potential: 55

Decision: rejected
**Already closed in `docs/sources.md` on 2026-08-15**, on two independent grounds, and this entry is a
duplicate of that verdict: authority selection, since a corpus of registered trademarks holds the brands
a capture-derived store already has, plus the **intent-to-use dating defect**, since a US mark can be
filed for a name before it is used, so the filing date evidences an intention rather than a live site.
Both objections were re-confirmed this weekend when the same reasoning closed the Australian equivalent
`ipgod_au_marktext`, whose mark text is applicant-typed and therefore takes the corroboration split as
well. Nothing new to measure.

### dnsrf_dap_udrp_multiprovider / artifact_listing

- potential: 52

Decision: rejected
**Already answered: 90.10 EE, and the family is explicitly closed.** `docs/sources.md` records the
multiprovider bulk artifact measured, Zenodo 16954717 under MIT,
`full-udrp-parsed-proceedings.jsonl.gz`, 90,153 proceedings across all five providers, 6,766 in-window
pairs and **158 net-new at 90.10 EE**; the ICANN plain-text exports gave 8,662 in-window pairs and 90
net-new. The store already holds all five providers as `udrp_proceedings` (WIPO 5,963, NAF 2,575, DeC
210, eResolution 133, CPR 42, 8,923 evidence rows). The register's own wording: do not reopen this family
on availability, the ceiling for everything remaining in it is about 90 EE. **And the Zenodo `submitted`
date is the corrupted field this project has already been caught by**: trusting it inflates 158 to 769 by
inventing 518 fabricated 1999 pairs.

### isi_us_domain_registry / artifact_listing

- what dates one item: the delegation file's own publication or approval date, the `uucp_map_registry`
- potential: 52

Decision: rejected
**Already answered on 2026-08-18 at 0.9 EE, and it is this register's cleanest instance of killer 2.**
Four dated in-window editions were recovered from a non-ISI route, so the artifact is not unreachable,
but the registry **added four names between August 2000 and November 2001**, giving **1 net-new pair and
0.9 EE**. The illegitimate reading, taking each edition's date as dating every name in it, would have
claimed **13,014 EE, a ratio of 13,014 to 1**. Separately confirmed: the "ISI contact column at 97.7%
already held" recorded elsewhere is a DIFFERENT artifact from this delegation register, so the two should
not be conflated.

### itu_operational_bulletin_1996_2001 / link_source

- potential: 49

Decision: rejected
Measured 2026-08-25 with a ceiling of **~300 EE**, below this entry's own ~519-934 estimate. Dated in
body, verbatim `No. 739 - 1.V.2001` with `(Information received by 24 April 2001)`. Licence: none found;
robots permits `/dms_pub/itu-t/opb/sp/`. **Retrievable for 1999-2001 only**: issues 690, 715, 731, 739
and 745 return 200 while 665/1998, 640/1997 and 615/1996 all 404 at the same derived path, controls
passing both ways in the same minutes. At 24 issues a year the in-window population is ~144 items, **826x
short of the 119,000-item prose screen**. **Density is wildly stratified and one issue alone would have
misled**: a plain issue carries 3-6 domains, but the annexed *List of ITU Carrier Codes* in OB 739 carries
**244 in 144,646 characters**. Pricing that richest item gives 93.0% domain-known and **37 pairs at 12.27
EE post-split** (54 pairs / 20.37 EE pre-split, do not quote), on a TLD mix that is mostly worthless
(`it` 37, `kz` 8, `mx` 8) at ~0.33 EE per pair.

### nz_dnc_zone_data / whois_creation

- potential: 45

Decision: rejected
**Measured at 7,586 EE and rejected on the registry's own terms, which an agent reported as "none
found".** The measurement is sound and its arithmetic was verified against the store: 200 domains drawn at
random from all 47,914 held `.nz` names, 123 dated, **122 in-window and 1 out (2023)**, a 99.2% in-window
rate that is the opposite of a refresh signature; 32 net-new pairs at 0.1600 per held domain;
0.1600 x 47,914 x 0.9895 = **7,586 EE**, CI 5,177 to 9,995. No corroboration split, since a creation date
is the registry's own machine record. The route is **port 43 at `whois.irs.net.nz`**, not the
`dnc.org.nz` zone file this entry was named for, which Cloudflare-403s.
**But the terms of use ARE in the response, about 1,100 bytes in, after the record and after the
`>>> Last update of WHOIS database <<<` line, which is why they were missed.** Verbatim: `By submitting a
WHOIS query you are entering into an agreement with Domain Name Commission Ltd on the following terms and
conditions... It is prohibited to: - Send high volume WHOIS queries with the effect of downloading part of
or all of the .nz Register or collecting register data or records; - Access the .nz Register in bulk
through the WHOIS service (ie. where a user is able to access WHOIS data other than by sending individual
queries to the database);`
**A 47,914-query sweep is precisely the prohibited act, in the registry's own words.** Same shape as
`nominet_whois_port43`, which Ivo rejected on 2026-08-24 answering O5: "I am paid for this work, so if
that makes bulk queries illegal, let's not do it." Rejected on the same ground.
**The transferable lesson: on a port-43 source, read PAST the record.** The terms follow the data, so a
reader that stops at the last field or the first blank line reports "no licence" on a source that carries
an explicit prohibition.

### scene_nfo_archives / dated_directory

- what dates one item: the release date in the archive's own per-file metadata, repeated inside the NFO.
- potential: 45

Decision: rejected
Measured 2026-08-25 at **34.61 net-new post-split EE**, the novelty-is-a-cost rule paid in cash.
`defacto2.net` Cloudflare-403s, but the artifact is reachable as
`archive.org/download/Defacto2_NFO_PACK-1.7z/Defacto2_NFO_PACK-1.7z`, 6,324,360 bytes, **licence: none
found** (`licenseurl` and `rights` both absent from the item metadata). 7,014 files with preserved mtimes
of which **5,381 are in window** (1996:338 rising to 2000:2107), and genuine pre-1996 files exist, which
is the evidence that mtimes were not stamped at pack time. 1,431 pairs over 1,074 domains after filtering
to pre-2002 TLDs, 84.6% already-held. Net-new 221 pairs and 115.16 EE pre-split (do not quote), **58
pairs and 34.61 EE post-split, because 73.8% of the net-new pairs sit on domains not in the store at
all** and therefore earn no year. Ceiling at the claimed 19x volume ~643 EE. **One trap recorded**: the
first pass showed `.zip` as the top TLD at 1,741 pairs, the filename-as-hostname error, removed by a TLD
whitelist.

### wayback_longitudinal_url_sample / cdx_timestamp

- potential: 28

Decision: rejected
**Unmeasurable by construction: the data was never published.** This entry's own row records "first
capture time, data unpublished" with evidence "none". It is also structurally dead by law 1, since an
IA-derived sample cannot be net-new against a baseline that is itself IA-derived. Marked refused rather
than left pending so the request generator stops re-queueing a source that does not exist.

### namewinner_expiring / artifact_listing

- measured: 11,555.0 net-new EE over 18,951 (domain, 2001) pairs, measured 2026-08-25 against the
  live store, on the master reading. The conservative reading, applying the corroboration split, is
  3,377 pairs and 2,083.9 EE. Both figures independently reproduced; the split figure matches a
  subagent's to the pair
- what dates one item: the per-item date `25-OCT-01` on every row. Verified in the file itself, which
  carries 20,945 occurrences of that string and no other date of that shape, with the Wayback capture
  fixing the instant at 2001-10-26 12:02 UTC. The operator's own `rule_book.php` calls it "our list of
  soon to be expiring domain names", so the registrar is stating these names are registered now. The
  `coza_deletion_listing` argument, and the standard set in killer 8
- potential: 22

Decision: master

Approved by Ivo 2026-08-26, on the master reading: the corroboration split does NOT apply. The
ruling is that a dump out of a registrar's expiring-domain database is not something a human typed,
and being registered is the only way onto it, so it dates the names on it including novel ones,
exactly as `iedr_register` and `internic_zone` do. Ingested as `namewinner_expiring`.

Scope of the ruling: the 2001-10-26 capture only. It needs no inference, because the artifact's own
per-item date `25-OCT-01` is inside the window. The 2002-04 capture of the same page is a separate
row and is NOT covered by this, and the parser refuses it automatically by reading each row's own
date rather than the file's.

### openpgp_keyserver_dumps / link_target

- potential: 20

Decision: rejected

### nlm_medline_affiliation_email_1996_2001 / link_source

- potential: 3

Decision: rejected

### ffiec_call_report_webaddr / artifact_listing

- potential: 2

Decision: rejected
