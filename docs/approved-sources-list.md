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
- what dates one item: the 14-digit Internet Archive capture timestamp that prefixes every row. A
- the artifact: the geographic index of the JISC UK Web Domain Dataset, every `.uk` resource the
- potential: 100

Decision: pending

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

Decision: pending

## Found, awaiting triage

### nic_mil_internic_zone_mirror / artifact_listing

- what it is: the Defense Data Network NIC at `nic.mil` mirrored InterNIC's zone-file distribution over
- what dates one item: the zone's own SOA serial in `YYYYMMDDNN` form, `1997041800`, **inside the
- potential: 95

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

- the artifact: `squidGuard`'s robot-compiled blacklist, of which exactly two editions survive, both
- what dates one item: each category file's own compile header, *"compiled in 33:22:40 on 2001.09.09
- potential: 72
- what it is: in-window **domain-based** web content-filter blacklists: the CyberNOT list disclosed in
- what dates one item: the dated release edition, admitted **only as a first-appearance diff across
- potential: 58

Decision: pending

### nominet_whois_port43 / whois_creation

- potential: 72

Decision: pending

### sec_edgar_filings / dated_directory
- measured: 5884 net-new post-split EE, 2026-08-24

- what it is: URLs and e-mail domains printed in SEC 8-K, DEF 14A and 10-KSB filings, 1996-2001
- what dates one item: the filing's own `Date Filed` in `full-index/<year>/QTR<n>/form.idx`
- volume: 222,232 in-window filings (1996 n=22,872 rising to 2001 n=46,480)
- potential: 72
- what makes it worth it: **5,884 net-new equivalent-English, measured 2026-08-24.** Human-typed, so it
  takes the corroboration split. Best-value unbuilt source on the register

Decision: pending

### govinfo_cbd_bulk / typed

- potential: 71

Decision: pending

### ipgod_au_marktext / dated_directory

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
- **THE DECISION IS ONE QUESTION AND IT IS WORTH 19x**: 24 of 25 pages carry
  `<META NAME="Generator" CONTENT="Microsoft Word 97">` and many carry
  `saved from url=(0022)http://internet.e-mail`, so this is a registry report hand-published through
  Word rather than a register regenerating itself. The names originate in MYNIC's database, but a human
  handled the file and three double-dot typos prove it (`imej.com..my`, `mycomplaints..com.my`). If that
  counts as machine-authored it is worth about 10,000 EE; if the Word round-trip makes it human-typed it
  takes the split and is worth about 400
- **also refutes a closure in `sources.md`**: the 2026-08-18 row on dated registration announcements
  concluded that a registry of this era published either dates without names or names without dates, and
  that the CA Domain Registry was the only exception. MYNIC is a second exception, so that row is wrong
  and the lens is reopened

Decision: pending

### repository_ia_capture_census / cdx_timestamp

- what it is: another precomputed Internet Archive capture census deposited as a research replication
- what dates one item: a 14-digit capture timestamp per row, identical semantics to the approved source.
- potential: 70

Decision: pending

### ted_ojs_notices_1996_2001 / link_source

- potential: 70

Decision: pending

### excite_query_logs / dated_directory

- what it is: search-engine and portal **query logs** of the window: Excite 1997, 1999 and 2001 as
- what dates one item: the log line's own server timestamp, machine-written at the moment a user typed
- volume: the 1997 Excite log is 1,025,910 queries for one day and the later logs are the same order,
- potential: 68

Decision: pending

### early_bulk_whois_snapshot / whois_creation

- what it is: a bulk whois or registry snapshot of **vintage 2002 to 2008** rather than 2024, carrying a
- what dates one item: the registry creation date in the row, the same semantics `domain_creation_bulk`
- potential: 65

Decision: pending

### sbir_sttr_award_pi_email_2000_2001 / dated_directory

- potential: 65

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
- what makes it worth it: machine-generated with no prose and no author, so no corroboration split, and
  it reaches **1998 n=2,274 and 1999 n=1,252**, two of our thin years, against only 90 for 2000. The
  weakness is honest and worth stating: it is the register's failing tail, selected for delinquency
  rather than sampled, and it is about 5% of the ~100,000 names `co.za` held in the window

Decision: pending


### discmaster_by_file_size / artifact_listing

- what it is: `discmaster.textfiles.com` queried by **FILE SIZE** rather than by link-artifact filename,
- what dates one item: the media file date corroborated against the disc's own release date. The closed
- potential: 62

Decision: pending

### uk_gazette_addressed_notices_1998_2001 / link_source

- potential: 62

Decision: pending

### courtlistener_caselaw / dated_directory

- potential: 60

Decision: pending

### cybernot_cphack_blacklist / artifact_listing

- what it is: the CyberPatrol **CyberNOT** list as published in the March 2000 cphack proceedings, plus
- what dates one item: the edition or update-file date. Unlike Netcraft, the entry exists because a
- volume: contemporaneous reporting puts a single CyberNOT edition at order 100,000 URLs with several
- potential: 60

Decision: pending

### discmaster_media_index / dated_directory

- what it is: `discmaster.textfiles.com`, a searchable index over the **contents** of archived CD-ROM,
- what dates one item: the file's own filesystem date on the media, which is the `page_directory` shape,
- potential: 60

Decision: pending

### pmc_oa_subset_fulltext_1998_2001 / link_source

- potential: 60

Decision: pending

### caselaw_access_project_opinions / dated_directory

- potential: 58

Decision: pending

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
- what makes it worth it: none of it is hand-typed, so no corroboration split, and the novelty is real
  rather than a re-dating: 8,754 of TWNIC's 9,593 names are absent from the store in every year, because
  `idv.tw` personal sites had nothing for a crawler to find. Weights are low, which is why 12,251 pairs
  buy only 2,856 EE
- **one point a human must rule on**: whether a stated EXPIRY date evidences the registration year. Here
  it does so with no term-length inference, since every date falls inside 2001. The same reasoning kills
  `DN/data/eng.tab`, whose expiry dates are 2002: recovering a 2000 registration from a 2002 expiry minus
  an assumed term would be manufacturing

Decision: pending

### sec_form_adv_part1_2000_2001 / artifact_listing

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
- what makes it worth it: `.mt` at 0.9055 is worth having on weight alone, and `.sa` brings 2,654 wholly
  new names. All four are machine-generated with no prose, so no split

Decision: pending

### can_domain_registry_notices / whois_creation

- potential: 55

Decision: pending

### uspto_trademark_case_files / artifact_listing

- potential: 55

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

### dnsrf_dap_udrp_multiprovider / artifact_listing

- potential: 52

Decision: pending

### isi_us_domain_registry / artifact_listing

- what it is: the ISI RFC 1480 US Domain Registry delegation database, the hand-maintained registry for
- what dates one item: the delegation file's own publication or approval date, the `uucp_map_registry`
- potential: 52

Decision: pending

### reuters_rcv1_newswire / dated_directory

- what it is: Reuters RCV1, 806,791 stories from 1996-08-20 to 1997-08-19, free from NIST under a signed
- what dates one item: the story's own dateline.
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

- what it is: underground release-scene text archives, `defacto2` and its peers: NFO files,
- what dates one item: the release date in the archive's own per-file metadata, repeated inside the NFO.
- volume: order 100,000 dated files with heavy in-window density at roughly one to two hostnames each,
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
- **same 15x split question as `mynic_my_change_report` and it should be ruled the same way**: only 586
  of the 4,071 names were known to the store under any year, so if the split applies almost all of the
  value is refused. Deciding `.my` decides this too

Decision: pending


### usenet_quoted_whois / whois_creation

- what it is: NSI-format and ccTLD-format `whois` output **pasted into message bodies** in
- what dates one item: the registry's own `Record created on DD-Mon-YYYY` line inside the quoted
  block, which dates the domain independently of when the message was posted
- what makes it worth it: **MEASURED 2026-08-24 on the 146 densest archives, 14.4 GB of 383 GB**:
  1,672 in-window blocks (1996 n=834, 1997 n=379, 1998 n=149, 1999 n=107, 2000 n=64, 2001 n=139) giving
  850 distinct pairs, **701 already held and 149 net-new worth 90.41 equivalent-English**. 82% overlap.
  The sample is the dense end, domain and net-abuse groups, so the whole corpus is unlikely to reach
  3,000 EE. Real, cheap, master-eligible, and not a round
- potential: 40

Decision: pending

### uspto_tm_marktext / dated_directory

- potential: 40

Decision: pending

### zenodo_banner_ads / cdx_timestamp
- measured: 432.81 net-new post-split EE, whole file censused, 2026-08-24

- what it is: 22,915 banner images from archived snapshots of URLs in six printed internet directories
  published 1999-2001, `zenodo.org/records/8408539`, CC-BY-4.0, 215 MB
- what dates one item: the 14-digit Wayback capture stamp on each appearance, verified against live CDX
  at 27 of 28 exact matches. Self-dating, so no split
- potential: 38
- what makes it worth it: **432.81 net-new equivalent-English over 934 pairs**, whole file censused not
  sampled. Its `hrefs` field is `link_target` and can only ever be candidate supply

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
- collect it: `uv run python scripts/collect_iedr_register.py`, 38 requests, 1.1 MB
- years: 18,512 pairs at 2001, **812 at 1999**, 17 at 2000. The 1999 pairs come from the `/lists/` tree
  and land in a thin year; the 2000 side is worth 17 pairs because the baseline already used a 2000
  edition of this same artifact
- potential: 96
- what makes it worth it: `.ie` weighs 0.9744, so a pair here is worth 1.54 of a `.com` one, and the
  store holds 18,438 `.ie` at 2000 against 6,598 at 2001, which is exactly the hole this fills. Machine
  generated, so no corroboration split. Corroborating, not the grounds: 889 of 892 names on the April
  2000 edition are already dated 2000 in the store, so the reviewer's own baseline read this same
  artifact the same way

Decision: master
Decided by Ivo, 2026-08-24. The reason is the artifact's own semantics: a cron regenerated the
whole register and stamped the page with the instant it did so, and an IA crawl fixes when that
page existed. The 99.6% agreement with `prior_task` on the 2000 edition corroborates that reading;
it is not the grounds for it.


### educause_edu_whois_activation / whois_creation

- potential: 78

Decision: rejected

### openpgp_keyserver_dumps / link_target

- potential: 20

Decision: rejected

### nlm_medline_affiliation_email_1996_2001 / link_source

- potential: 3

Decision: rejected

### ffiec_call_report_webaddr / artifact_listing

- potential: 2

Decision: rejected
