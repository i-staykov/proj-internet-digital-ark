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

### ukwa_ds2_year_cdx / cdx_timestamp

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
- **BLOCKED ON ACCESS, NOT ON EVIDENCE, and the zero is proved rather than assumed.** IA captured the
  directory listing and never the files: a prefix query for `ukwa.ds.2/cdx*` returns empty while the
  identical probe for `linkage/host-linkage.tsv.gz` returns its two known captures, so the emptiness
  is the archive's and not the query's. The publisher now answers every path with a 7-line HTML
  `400 Redirect` stub, including `robots.txt`. And no mirror exists: archive.org `advancedsearch.php`
  returns numFound 0 for both `jisc uk web domain dataset` and `ukwa.ds`
- so this is a human request in the shape of `ripe_dbase_1999`, addressed to the UK Web Archive at the
  British Library, and on expected value it should be sent FIRST: RIPE is 90,799 EE of mixed-weight
  European names, this is 13.45 GB of the highest-weight TLD, self-dating and unsplit
- potential: 100. Unpriceable without the file, and scored at the ceiling deliberately: it is the
  highest-weight TLD, self-dating, unsplit, 13.45 GB in window, and its two siblings in the same
  directory both paid. The score says send the request first, not that the yield is proved

Decision: pending, needs Ivo to send an access request

### ripe_dbase_1999 / artifact_listing

- measured: 90799.4 net-new post-split EE over 641,241 (domain, 1999) pairs, measured 2026-08-24
  against the live store. A subagent measured 93,857.7 an hour earlier; the gap is the store growing
  underneath it, not a disagreement
- **BLOCKED ON A LICENCE QUESTION, NOT ON EVIDENCE. Read this before the number.** The file's own
  header, lines 6 to 15, says: `Restricted rights. Except for agreed Internet operational purposes,
  no part of this publication may be reproduced, stored in a retrieval system, or transmitted, in any
  form or by any means, electronic, mechanical, recording, or otherwise, without prior permission of
  the RIPE NCC on behalf of the copyright holders.` Ingesting is arguably "stored in a retrieval
  system" and shipping to the reviewer is arguably "transmitted". Against that: we would ship
  `(domain, 1999)` pairs, not the publication, and bare facts are thin copyright. For it: RIPE NCC is
  Dutch, so the EU sui generis DATABASE right applies to the extraction of a substantial part, and
  641,241 rows is substantial by any reading. **This is your call and it is the reason nothing has
  been ingested.** Your standing rule was "I am paid for this work, so if that makes bulk queries
  illegal, let's not do it", and this is the same shape of question.
  **Checked further 2026-08-24 and it got stronger, not weaker.** The restriction is not one file's
  header: the same paragraph appears verbatim in three sibling files in the same directory,
  `RIGHTS` (2000-02-22), `COPYRIGHT` (2002-02-03, covering 1992 to 2002) and `README` (2000-02-23),
  and the README opens `For all database files in this directory the following copyright notice
  applies`. So it is a directory-wide stated term, restated three times, with **no research
  exception**: the only carve-out is "agreed Internet operational purposes", which this is not.
  **The concrete route, if you want the 90,799 EE, is to ask.** RIPE NCC has a research-access
  process and the text itself says "without prior permission of the RIPE NCC", so permission is
  the named remedy rather than a hypothetical one. That is a letter, not a workaround
- what dates one item: the file's own timestamp on line 2 of its header, `# 990804 00:07:01`, so a
  `domain:` object in it is the registry stating its database contents on 4 August 1999. Evidences
  1999 and no other year, per rule 6
- ingest specs: none written. **No parser exists and none will be written until the licence question
  is answered**, so an approval here cannot be acted on by accident
- the artifact: `http://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz`, 71,919,736 bytes,
  `Last-Modified: Tue, 03 Aug 1999 21:27:00 GMT`
- **why it exists at all, which is the transferable part**: `ftp.ripe.net`'s own `dbase` is closed in
  `sources.md` as GDPR-dummified and `ripe/registries/` as empty since 1998. FUNET mirrored RIPE's
  whole DOCUMENT tree into `/pub/netinfo/`, beside `docs/`, `procedures/` and `minutes/`, then stopped
  updating. The mirror froze holding the pre-GDPR original. This is the "filed next to its documents"
  rule that the zone-file closure produced, working on the first try
- integrity, all three checks pass: `gzip -t` clean, 20,528,780 lines, its own `# 990804 00:07:01` on
  line 2 and its own `# EOF` terminator, so it is not a partial recovery
- measured composition: 1,256,414 `*dn:` lines, 21,047 `.arpa` reverse zones excluded, 429 rejected,
  **1,232,554 distinct registrable names**; 591,313 already dated 1999, 849,540 dated in some year,
  **383,014 the store has never seen**
- **volume beats weight here, which is why it nearly got discarded**: net-new by TLD is `de` 411,128,
  `dk` 73,658, `at` 29,910, `it` 29,685, `nl` 19,753, `cz` 19,314, `no` 15,271, `fr` 12,027, `be`
  9,433, `il` 6,518. Every one is on the near-worthless list, and 1.2M names at 0.1324 still outruns
  any high-weight namespace still available to us
- gross would be 173,359.2 EE. Quoting net-new, as the rule requires
- robots: `ftp.funet.fi/robots.txt` permits `/pub/netinfo/` (it disallows `/ftp/`, `/incoming/`,
  `/pub/mirrors/`, `/.m/`, `/cgi-bin/`) and asks `Crawl-delay: 15`. One request was made
- potential: 99

Decision: pending


### us_domain_delegated / artifact_listing

- measured: 12,775.5 net-new post-split EE over 13,816 pairs, measured 2026-08-25 with the
  project's own `price_items.py` against the live store, over the union of the 1996, 1999, 2000 and
  2001 editions. Mean weight 0.9247. By year 1996 2,284 / 1999 4,185 / 2000 3,823 / 2001 3,524. The
  2001 edition alone is 3,524 pairs and 3,247.3 EE. Gross was 15,270.0 and must not be quoted
- what it is: `us-domain-delegated.txt`, the US Domain Registry's list of delegated `.us` zones, one
  per line with the delegate's contact beside it. Six editions, ~2.5 MB, reached two ways: inside the
  `2015.04.ftp.isc.org.tar` mirror on archive.org at `pub/rfc/`, and at the file's other home
  `www.isi.edu/in-notes/us-domain-delegated.txt`
- what dates one item: the artifact asserts the delegation state of the namespace, and the instant is
  fixed twice. Tar-preserved mtimes 1996-10-09, 1996-11-20 and 1999-03-22 with six rotations whose
  chain is monotone in both date and size (425,505 to 426,388 bytes over Feb-Mar 1999, continuing
  monotone into the captures at 433,937 to 435,847); and `cdx_timestamp` on the 2000-08-15,
  2000-12-06, 2001-04-11 and 2001-06-06 captures. A delegation is the registry serving the name at
  that instant rather than a description of one, which is why killer 2 does not reach it, exactly as
  for `internic_zone`
- the name shapes were checked rather than assumed: the pinned PSL returns None for `K12.AK.US`,
  `AK.US` and `US`, resolves `ANCHORAGE.AK.US`, and collapses `CI.ANCHORAGE.AK.US` to `anchorage.ak.us`
- contamination measured and negligible: every line also carries a contact email, and those survive as
  56 pairs of 13,816. By TLD `us` 13,760, `com` 36, `net` 18, `org` 2
- caveats: the typo upper bound is **17.8%**, structurally rather than reassuringly, since sibling
  locality names are one edit apart by construction (`HAINES`/`HEALY`, `NOME`/`TOK`). And 1997 and
  1998 are unreachable, since no `*.isi.edu` capture predates 2000-08-15 and the ISC tar jumps 1996
  to 1999
- access note: `ftp.isc.org/robots.txt` ends `Disallow: /` under `User-agent: *`, so the live host must
  never be touched. The 2015 mirror inside archive.org is a different host
- potential: 99

Decision: pending

### squidguard_2001_blacklist / artifact_listing

- measured: 10736.2 net-new post-split EE over 18,588 (domain, 2001) pairs, measured 2026-08-25.
  **Reconciled to the decimal with an agent's independent figure** after my first pass read only the 11
  `domains` files and returned 8,118.0; the `urls` files and the 2001-dated diffs are equally the robot's
  own output, and including them gives 44,130 canonical names and 10,736.2 EE
- what dates one item: the list's own header line, `# This list was compiled in 0:00:20 on 2001.12.18
  15:04:29.`, corroborated by the tar member mtime `Dec 18 2001` and by dated diffs running
  `domains.20010814.diff` through `domains.20011218.diff`
- **licence: GNU GPL version 2**, verbatim in `squidguard-1.2.0/COPYING`, and `samples/dest/README` adds
  no data restriction beyond warning that the lists are "entierly products of a dumb robot". So this is
  licence-clear, unlike RIPE and Nominet
- collect it: one request. `https://archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`,
  1,852,659 bytes (`archive.debian.org` serves no robots.txt), then extract
  `squidguard-1.2.0/samples/dest/blacklists.tar.gz`
- ingest specs: none written yet. Format is one host per line with `#` comments, 11 category directories
  each holding `domains`, `urls` and dated diffs
- **no corroboration split**: the list is machine-generated by `squidGuardRobot-2.3.4`, and its header
  asserts liveness rather than mere listing, `compiled from 2402 link sources and 654820 links, of which
  510389 tested successfully`
- measured composition: 44,130 canonical names, **37,437 known to the store (84.8%)** but only **25,542
  already at 2001 (57.9%)**, leaving 18,588 net-new: **11,895 held-missing-2001 worth 6,760.9 EE** plus
  6,693 novel worth 3,975.3. `com` 14,870, `net` 1,618, `de` 1,009, `org` 275
- **why it pays where the 2000 edition paid 18 EE, and it is the interesting part**: this register closed
  squidGuard on the 2000-10-18 edition at 99.47% already held, correctly, because a crawl-fed list finds
  few novel names. **But novelty is not where the value is.** This edition's names are mostly held and
  mostly LACK 2001, so it pays on completeness. **Crawling kills discovery, not completeness.**
- **it satisfies this register's own reopen condition for the class**, which reads "reopen only on an
  in-window edition from a non-Wayback mirror", so the closure is not being contradicted, it is being
  triggered
- typo bound 0.07%, the cleanest blocklist measured on this project
- content is mostly adult, gambling and drugs sites. Worth a human's eye, since the shipped files carry
  domain names only and no categorisation, but it is what it is
- potential: 92

Decision: pending


### ncua_5300_call_report_webaddr / artifact_listing

- measured: 1328.31 net-new post-split EE over 1,998 (domain, year) pairs, measured 2026-08-25 over all
  16 in-window quarters. An agent got 1,289.84 independently; the two agree within 3%
- what dates one item: `CYCLE_DATE` on every `fs220d` row, the quarter the call report covers
- what it is: the web-site and e-mail columns of NCUA's quarterly 5300 Call Report for credit unions,
  `https://ncua.gov/files/publications/data-apps/QCR{YYYY}{MM}.zip`, one zip per quarter. Genuine ERA
  VINTAGE: the 2001Q4 zip's inner files carry a 2002-03-13 mtime
- the columns, verbatim from the `fs220d` header: **`Acct_891`** (web site) and **`Acct_890`** (e-mail),
  neither of which appears in `AcctDesc.txt`. The 1996 zips carry both headers with zero values and the
  1997 zips lack the columns entirely, so coverage is 1998Q1 to 2001Q4
- **human-typed, so the full corroboration split applies**, and the values prove it: `W.W.W.EFEDCU.ORG`,
  `THRU WEB PAGE WWW.BE`, `USE WORLD WIDE WEB ADDRESS`, `JDELLUCA@NOFFCU,ORG`
- measured composition: 150,346 `fs220d` rows, 85,055 non-empty cells, 21,029 candidate pairs, **17,309
  already held (82%)**, 3,720 net-new gross at 2,451.34 EE, **1,502 novel names refused by the split**,
  leaving 1,998 pairs at 1,328.31 EE. `org` 1,066, `com` 773, `net` 118. By year 1998 346, 1999 462,
  2000 474, 2001 716
- **the 82% already-held rate is killer 3 exactly**: a regulated-institution population is what a
  capture-derived store holds first, which is why an era vintage still only reaches the floor
- potential: 88

Decision: pending

### fac_sfsac_historic_1998_2001 / artifact_listing

- **BLOCKED BY ROBOTS, NOT BY EVIDENCE, and it needs one human action.** The bulk files exist and are
  exactly the era vintage wanted: `https://app.fac.gov/dissemination/public-data/census/csv/census-1998.zip`
  through `census-2001.zip`, each with a `.sha1`, linked from the allowed page
  `https://www.fac.gov/data/download/historic/`. But `app.fac.gov/robots.txt` is `User-agent: *` /
  `Disallow: /`, byte-checked, a blanket group binding any automated fetch, so no agent may download it.
  No mirror exists: `archive.org` returns 25 hits and none is the data, `catalog.data.gov` has none, and
  `facdissem.census.gov` and `harvester.census.gov` now redirect to this host
- **A human clicking that link is not a crawler.** If Ivo downloads the four zips by hand into
  `data/raw/fac/`, an agent can price them locally without touching the host
- what dates one item: `AUDITEEDATESIGNED`, "Date of auditee signature", per filing
- the carrying columns are `AUDITEEEMAIL` and `CPAEMAIL`, both typed by a human, so the full split
  applies. **There is no web-address or URL column anywhere in the historic dictionary**, so this pays
  through e-mail domains only
- relationship to `fac_single_audit`, which is measured at 2,406.69 EE: same clearinghouse and same
  window, so these may be one source under two names, but the evidence types differ and neither has been
  measured against the other. Do not close either as a duplicate without that check
- potential: 86

Decision: pending

### gias_england_school_website_domains / link_target

- potential: 82

Decision: pending

### nces_imls_pls_web_addr_1998_2001 / typed

- potential: 82

Decision: pending

### dartmouth_bfs_seed / cdx_timestamp

- measured: 1419.9 net-new post-split EE over 2,460 pairs, measured 2026-08-24 over the COMPLETE level 0,
  three of three files and 13.6 MB, not sampled
- what dates one item: the 14-digit Internet Archive capture timestamp in field 2 of each CDX line, with
  field 5 the HTTP status, so only in-window 200s are read. Self-dating, machine-written, no split
- ingest specs: `dartmouth_bfs_seed`
- collect it: `uv run python scripts/collect_dartmouth_bfs_seed.py`, 3 requests, 13.6 MB
- the artifact: IA ran a breadth-first crawl seeded with URLs pulled from SEC 10-K filings and deposited
  it as `Dartmouth_10KwebURLs_GWB-20180911224740_BFS_4-lvls`, 204 items and 2,064 GB under
  `CorporationWebsitesCollection`. **Only BFS level 0, the seed layer, is worth reading.**
- source: https://archive.org/details/Dartmouth_10KwebURLs_GWB-20180911224740_BFS_4-lvls
- **not the closed ARCS family**: `DARTMOUTH-NBER-RESEARCH-2017-ARCS-*` measured exactly zero net-new
  because every capture in it is of a host on the NBER corporate list whose capture census we had banked.
  This is a different and much larger seed population, from 10-K filings rather than that list
- measured composition: 311,543 rows, 58,035 in-window HTTP 200s, 57,878 distinct pairs, 55,418 already
  held, 2,460 net-new, 104.7 EE per MB. `com` 2,001 of 2,460; **2,377 land in 2001**; 440 of the names
  the store has never seen
- **the rest of the family is not worth downloading and this was measured, not assumed**: levels 2 and 3
  are 92 of the 102 ARC items and three indexes there gave 0.00, 0.00 and 0.59 EE per MB, one level-1
  index gave 1.93, against level 0's 104.7. A rate sampled from the shallow files overstates the family
  about six-fold. The 102 `_warc` items are 2012-2019 with zero in-window rows
- access note: the merged item-level `.cdx.gz` returns HTTP 401 while the per-file `.arc.os.cdx.gz`
  returns 200. The restriction is on the merged object, not the parts, and `access-restricted-item: true`
  predicts neither. `archive.org` downloads are a different service from `web.archive.org` replay, so
  this spends neither archive-client slot
- lineage: `internet_archive`, so it cannot inflate the independent-corroboration count
- potential: 74

Decision: pending


### junkfilter_dated_blocklist / dated_directory

- measured: 2189.4 net-new post-split EE over 3,553 pairs, measured 2026-08-25. Verified two ways: my
  own run over the 13 in-window `jf-domains` editions gave 3,122 pairs and 1,924.1 EE, and the
  difference is exactly the 431 pairs at 1997 that live in the two tarballs I did not open, so the two
  measurements agree to the pair
- what dates one item: three independent machine-written stamps agreeing. The HTTP header on the file
  itself, `last-modified: Tue, 29 May 2001 07:10:09 GMT`; the in-body `$Id: junkfilter,v 2.36
  2001/05/28 20:00:08 gsutter Exp $` and `JFVERSION=20010528` in the same release; and for the 1997
  half a tar member header, `-rw-r--r-- 0 gsutter staff 43879 Dec  6  1997 junkfilter/jf-domains`
- ingest specs: none written yet
- collect it: `https://junkfilter.zer0.org/pkg/` holds 13 ISO-dated in-window release directories,
  `19980508` through `20010529`, plus `/pkg/old/` with two 1997 tarballs. About 900 KB in total
- the artifact: Gregory Sutter's procmail spam filter. `jf-domains` is one `|`-joined line of
  backslash-escaped literal hostnames. **The triage note guessed these were escaped regexps and
  wildcards rather than hostnames, and that is refuted**: 42,005 of 42,034 tokens are domain-shaped,
  99.9%
- **human-typed, so the corroboration split applies and it is already applied above.** A maintainer
  added each spam-origin domain by hand. Gross would be 4,815.8 EE, post-split 2,189.4
- **the reason this lens was worth trying, now measured**: already-held is **50.4% of pairs**, against
  87.5% to 99.8% for every authority-selected corpus closed this week. A blocklist selects for what
  somebody wanted to BLOCK, which is the opposite of the fame bias that killed six lenses. Mean weight
  0.6163, above the 0.4 floor
- reaches the thin years: 431 pairs at 1997 and 727 at 1999
- **killer 2, for a human to rule on**: an entry means the maintainer received mail from or advertising
  that host, which is one inference shorter than a directory listing but is still not a resolution.
  Killer 4 does not apply, since these are 15 separately dated editions rather than a re-released
  current state, and junkfilter began 1997-07-06, inside the window, so no edition carries pre-window
  content
- potential: 74

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

### early_bulk_whois_snapshot / whois_creation

- what it is: a bulk whois or registry snapshot of **vintage 2002 to 2008** rather than 2024, carrying a
- what dates one item: the registry creation date in the row, the same semantics `domain_creation_bulk`
- measured: 2968.49 net-new post-split EE over 4,747 (domain, year) pairs, measured 2026-08-25 across
  three sibling listings. **Corroborated on the largest of the three by an independent per-block parse**:
  8,718 record blocks, 5,239 carrying a creation date, 4,228 in-window pairs, 3,491 net-new, 2,195.92 EE,
  with novelty at 23.9% against the agent's 25.8%. Both the block count and the dated count match exactly
- what dates one item: the record's own `Dates of creation / last modification / expiration:
  27-Feb-2000 / 15-Feb-2002 / 27-Feb-2003`, or on a sibling `Registered on: Sep 29, 2001`, under the
  page's own "All data is as of January-October 2003"
- **licence: NONE FOUND.** No copyright line, no CC mark, no restriction clause on the index or any
  listing page. The only rights-adjacent sentence concerns reader comments. That is the opposite of the
  `ripe_dbase_1999` blocker and of Nominet's terms
- the artifact: Ben Edelman's whois transcriptions, "Last Updated: June 2, 2002", on space at the Berkman
  Center for Internet & Society at Harvard Law School. Three sibling listings, 81 pages, 13,507,154
  bytes, 15,990 entries, 8,787 carrying a creation date:
  `cyber.harvard.edu/archived_content/people/edelman/{invalid-whois/nicgod,renewals/tina,typo-domains/list}-*.html`
- **anachronism test passes**, which is how a frozen artifact is told from a refreshed column: the
  in-window pairs carry exactly `com`, `net` and `org`, no `.biz`, `.info` or `.aero`, and creation years
  run 1996 n=1, 1998 n=4, 1999 n=570, 2000 n=2,592, 2001 n=3,748, 2002 n=1,872 and **nothing after 2002**
- **novelty is the whole reason it pays**: only 49.7% of its domains were in the store at all, and
  **25.8% for the typosquat file**, against 87-99% for every authority-selected corpus. These are junk
  names a capture-derived baseline never held, which is adversarial selection doing the same work it did
  for the junkfilter blocklist
- **the parse trap, and it cost me a 47% overstatement before I caught it**: each `<p>` block names its
  subject in `<b>` and then mentions OTHER domains in the same block, the redirect target and the
  original that was typo'd. Binding a name to any date within reach gave 7,010 pairs and 4,366.68 EE.
  Only the block's subject may take the block's date
- **a human must rule on one thing**: this is a third party's transcription of registrar whois output on
  a uniform template. Read as machine-extracted it takes no split, which is how the figure above is
  computed. Read as human-typed it takes the split and falls sharply
- 230 EE per MiB, so the whole artifact is a 13 MB download
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
- **this row IS a question, and answering it once decides both artifacts.** Both are dated in 2002,
  outside the window, so reaching 2001 needs one inference: a registration had a minimum one-year term,
  so a name expiring or dropping in April or August 2002 was registered no later than the same date in
  2001 and was therefore live during 2001
- why I think the inference holds: `.com`, `.net` and `.org` registrations in that era were sold in
  whole-year increments with a one-year minimum, so a shorter term was not purchasable. And the two
  possible readings of the printed date both land in 2001: if it is the registry expiry, registration
  began at least a year earlier; if it is the deletion date, the name expired some 45 to 75 days before
  that and registration began earlier still. There is no reading on which a name on these lists was
  absent throughout 2001
- what would break it: a printed date that is neither expiry nor deletion but the auction's own
  scheduling date, unrelated to registry state. The April list argues against that, since its per-item
  dates straddle the capture rather than trailing it, which is what a forward schedule of registry
  events looks like
- **the master reading is much larger and I am NOT quoting it as the price**: dropping the
  corroboration split, as `domain_aftermarket_listings_1999_2001` argues it should be dropped for a
  registrar database dump, gives 31,207.7 EE for the April list and 2,456.3 for the LAME page,
  **33,664 EE combined**. But two judgements then compound, the split and the term inference, over a
  population that is 89.9% novel. Decide the inference on the conservative figure first
- a methodological note worth keeping: the conservative figures here use held-at-any-year-and-missing-2001,
  not the adjacent-year measure the headroom rule prescribes. That rule exists because a gap between a
  domain's last held year and the target is evidence of death when you are GUESSING whether data
  exists. Here the artifact is the data and asserts the name was live, so death is not the competing
  explanation. The adjacent figure is quoted alongside as the stricter floor
- potential: 60

Decision: pending

### antispam_media_blocklist / artifact_listing

- measured: 1055.3 net-new post-split EE, measured 2026-08-25, for the two components carrying **no
  licence**. I repriced the larger one from the bytes and got **1,605 pairs and 967.1 EE** against an
  agent's 969.0, agreeing to 0.2%; SQDR adds 88.2
- what dates one item: the file's own timestamp on the preserved media, `2001-04-06`, shown in
  discmaster's listing row for `BlackList.json` and again on its parent `data.mdb`. Per EDITION,
  not per record, so the same shape as `junkfilter_dated_blocklist`
- **a source CLASS nobody had looked at**: consumer anti-spam products shipped their spam-sender
  blocklist as a plain data file, and hundreds of 1996-2001 CD-ROMs preserve those files with per-file
  mtimes on the media. Discmaster's `tsMin`/`tsMax` filter turns the era screen into a query rather
  than a fetch, which is why 24 dated in-window artifacts were found across five products
- the two shippable components, **licence: NONE FOUND in either package**:
  - `BlackList` table of `data.mdb`, "spam filtering services 2.1" (sMaxiimus), Twilight 60, 320,099
    bytes, 10,088 rows, one domain per row in a single `MailServer` column (`{"MailServer":"00154.com"}`),
    8,121 distinct registrable after dropping 9 wildcards and 727 unparseable. **967.1 EE, all at 2001**
  - SQDR `blacklist.upd` x2 from OS/2 Hobbes, 38,739 bytes, 2,322 lines, dated `2001-06-21` and
    `2001-12-28`. **88.2 EE**
- **BLOCKED and deliberately kept separate so it does not hold up the rest**: SpamEater Pro
  `spammers.txt`, 14 editions 1998-05-24 to 1999-09-19 plus a 1997 `SPAMMERS.LST`, 207,777 lines,
  **546.2 EE**, carrying `Copyright (C) 1997-1998 High Mountain Software / All Rights Reserved` and
  `you are specifically prohibited from ... distributing the software and/or documentation with other
  products (commercial or otherwise) without prior written permission`. Two lanes measured it
  independently and agreed to 0.3% (546.2 against 544.4), so the number is sound and the licence is the
  only obstacle
- collect it: targeted requests to `discmaster.textfiles.com`, whose `robots.txt` is `Disallow: /`
  **followed verbatim by** "If you are a researcher, historian or hobbyist, you are free to automate
  requests to the site so long as it's reasonable or somewhat limited or somewhat targeted"
- adversarial selection working as the law predicts: 65.4% of the 2001 blacklist's domains are known to
  the store at all and only 45.6% carry 2001, against 87-99% for authority corpora
- **the honest caveat, and it is the reason to look at a sample before deciding**: the union's typo upper
  bound is 73.7%, the worst on this project. On the component I verified it is milder, 240 of 2,812 novel
  names all-numeric (8.5%), but the union figure of 33.5% means the SpamEater half carries most of it.
  All-numeric `.com` labels have dense one-edit neighbours by construction and cannot be told from junk
  without registry evidence
- lineage: none of these is crawl-derived, so the class is independent of every web archive
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

- measured: 8768.2 EE **is what your one-word ruling is worth**, and that is why this row shows that
  number rather than either raw figure. The artifact measures **9551.2 EE over 11,418 pairs if the
  registry self-dates** and **783.0 EE over 936 pairs if a human typed it**; the 936 are already
  banked, so the incremental prize is 10,482 pairs and 8,768.2 EE. Both raw figures are in this
  file's triage table, measured, row 1
- **THIS IS A RULING WORTH 8,768 EE, NOT A MEASUREMENT.** The two readings differ **12.2x** and the
  difference is one word from Ivo, not any further collection. The question: **is a `Date-Approved:`
  field, printed by the CA Domain Registry in its own approval notice, the registry self-dating, or is it
  prose a human typed?** `docs/discovery.md` records **37,578 `Date-Approved:` fields** in the artifact.
  If the registry self-dates, the class earns 11,418 pairs at 9,551.2 EE; if a human typed it, 936 pairs
  at 783.0. The 936 are the corroborated remainder, so the incremental prize on a self-dating ruling is
  about **10,482 pairs and 8,768 EE for zero further fetching**
- **the same question sits on the UDRP row at 5.5x**, so a ruling here probably settles that too
- what dates one item: `Date-Approved:` on the notice
- **why this is the one namespace where the shape exists at all**: `docs/sources.md` establishes that a
  registry of this era published either dates without names (statistics) or names without dates (a zone
  snapshot), and **the intersection existed in exactly one namespace, the CA Domain Registry, because it
  ran its approval process in public**
- **the honest complication**: `can.domain.mbox.zip` is **no longer on disk** (nothing under `data/`
  matches), so acting on a self-dating ruling needs a re-download from the archive.org `usenethistorical`
  collection before anything can be re-verified. The 936-pair split reading is already banked, since
  `can.domain` was the single largest contributor to the Usenet ingest at 7,137 net-new pairs
- for scale: the store holds 235,237 in-window `.ca` pairs over 96,505 domains, so 11,418 is about 5% on
  top, at `.ca` 0.8365
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
- **same 15x split question as `mynic_my_change_report` and it should be ruled the same way**: only 586
  of the 4,071 names were known to the store under any year, so if the split applies almost all of the
  value is refused. Deciding `.my` decides this too

Decision: pending


### usenet_quoted_whois / whois_creation

- measured: 90.41 net-new EE over 149 pairs, measured 2026-08-24 on the 146 densest archives, 14.4 GB
  of 383 GB. The figure was written into this entry as prose and so never reached the decision sheet,
  which listed the class as unpriced for a day; it is on its own line now. The projection for the whole
  corpus is under 3,000 EE and the sample was the dense end, so treat 90.41 as the measurement and
  3,000 as a ceiling that will not be reached
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

### domain_aftermarket_listings_1999_2001 / artifact_listing

- measured: 11,555.0 net-new EE over 18,951 (domain, 2001) pairs, measured 2026-08-25 against the
  live store, on the master reading. The conservative reading, applying the corroboration split, is
  3,377 pairs and 2,083.9 EE. Both figures independently reproduced; the split figure matches a
  subagent's to the pair
- what it is: `namewinner.com/whole_list.php?del=tab`, Dotster's expiring-domain auction list, Wayback
  capture `20011026120205`. 20,943 distinct registrable domains, 15,660 `.com` / 3,333 `.net` /
  1,950 `.org`. The `?del=none` capture is a strict subset
- what dates one item: the per-item date `25-OCT-01` on every row. Verified in the file itself, which
  carries 20,945 occurrences of that string and no other date of that shape, with the Wayback capture
  fixing the instant at 2001-10-26 12:02 UTC. The operator's own `rule_book.php` calls it "our list of
  soon to be expiring domain names", so the registrar is stating these names are registered now. The
  `coza_deletion_listing` argument, and the standard set in killer 8
- **the one judgement to make**: whether the corroboration split applies. It should not. The split is
  for what a human typed, and this is a dump out of a registrar's expiring-domain database, on which
  being registered is the only way to appear. `iedr_register` (18,826 EE) and `internic_zone`
  (8,813 EE) are the same shape and both dated novel names
- the 25.6% held-fraction is the point rather than a warning: these are speculative 1999-2001 land-rush
  names nobody linked to and no crawler visited, which is the tail law 3 says a trust-selected corpus
  cannot reach. 1,992 are already held at 2001, so the store is thin here, not blind
- **not included in the figure**: the 2002-04-07 sibling, 52,204 domains with zero overlap, worth
  2,543.2 EE post-split but needing the minimum-one-year-term inference to reach 2001. Decide it
  separately rather than beside a stamped in-window date
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

### content_filter_blacklists / artifact_listing

- the artifact: `squidGuard`'s robot-compiled blacklist, of which exactly two editions survive, both
- what dates one item: each category file's own compile header, *"compiled in 33:22:40 on 2001.09.09
- potential: 72
- what it is: in-window **domain-based** web content-filter blacklists: the CyberNOT list disclosed in
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

### repository_ia_capture_census / cdx_timestamp

- what it is: another precomputed Internet Archive capture census deposited as a research replication
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

- what it is: search-engine and portal **query logs** of the window: Excite 1997, 1999 and 2001 as
- what dates one item: the log line's own server timestamp, machine-written at the moment a user typed
- volume: the 1997 Excite log is 1,025,910 queries for one day and the later logs are the same order,
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

- what it is: `discmaster.textfiles.com` queried by **FILE SIZE** rather than by link-artifact filename,
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
- **licence: EXPLICIT PERMISSION, which is why this is worth deciding even at 1,623 EE.** Lines 3 to 10
  carry JPNIC's open-document notice, ending: as long as this copyright notice is included, anyone may
  freely reprint, reproduce and redistribute it. That is the opposite of the RIPE blocker sitting above
  it in this queue
- ingest specs: `jpnic_register`
- collect it: `curl -o data/raw/jpnic_tomocha/domain-list.txt https://tomocha.net/files/dns/domain-list.txt`,
  one request, 6.2 MB. `robots.txt` explicitly `Allow: /files/`
- the artifact: `https://tomocha.net/files/dns/domain-list.txt`, 6,185,475 bytes,
  `Last-Modified: Fri, 30 Apr 1999 04:43:08 GMT`. JPNIC's own register of every registered `.jp` name,
  frozen on a personal DNS document mirror while JPNIC's own tree kept only policy prose
- **completeness proved by the file's own arithmetic, not asserted**: each of 63 sections declares its
  own size and **62 reconcile exactly**; the total lands at 72,770 against a declared 72,769, one over
  in `co.jp`
- measured composition: 72,704 distinct registrable names, 45,877 already dated 1999, 61,074 dated in
  some year, **11,630 the store has never seen**. Second levels: `co.jp` 55,715, `ne.jp`, `gr.jp`,
  `or.jp`, plus 47 geographic sections
- **the trap, worth 4.4x**: 45,662 entries are marked reserved and 923 abolished, and neither was ever
  a registration. The reserved ones are municipal and school names JPNIC held back. Counting them gives
  about 4,394 EE instead of 1,623, and the registry's own header count excludes them, which is how the
  parse is checked
- `.jp` weighs 0.0605, the second-lowest in the model, so 26,827 pairs are worth 1,623 EE. This clears
  the bar on volume alone
- lineage: `registry`, independent of every web crawl
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

- what it is: the CyberPatrol **CyberNOT** list as published in the March 2000 cphack proceedings, plus
- what dates one item: the edition or update-file date. Unlike Netcraft, the entry exists because a
- volume: contemporaneous reporting puts a single CyberNOT edition at order 100,000 URLs with several
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

- what it is: the ISI RFC 1480 US Domain Registry delegation database, the hand-maintained registry for
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

- what it is: underground release-scene text archives, `defacto2` and its peers: NFO files,
- what dates one item: the release date in the archive's own per-file metadata, repeated inside the NFO.
- volume: order 100,000 dated files with heavy in-window density at roughly one to two hostnames each,
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

### openpgp_keyserver_dumps / link_target

- potential: 20

Decision: rejected

### nlm_medline_affiliation_email_1996_2001 / link_source

- potential: 3

Decision: rejected

### ffiec_call_report_webaddr / artifact_listing

- potential: 2

Decision: rejected
