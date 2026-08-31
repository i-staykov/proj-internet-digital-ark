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
- 2026-08-30, re-priced by the whole-spool census: the 9,050 archives this collector has never
  run over are worth a few hundred EE at most, since the same names already carry the year
  (`docs/discovery.md`, the re-selection law). Not worth the CPU.

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

### usenet_whois_paste / whois_creation

- measured 2026-08-30 against the live store, before the ingest: 769 in-window (domain, creation
  year) pairs read out of the 16,849 on-disk archives, 636 on domains another source already
  attests, **100.0% of those domains held and 92.1% of the pairs held already**, leaving **50
  net-new pairs and 30.4 net-new post-split EE** (`com` 38, `net` 6, `org` 5, `it` 1; by year
  1996 1, 1997 6, 1998 13, 1999 18, 2000 8, 2001 4). The 133 names seen only here take the
  corroboration split and go to the candidate pool as `link_target`, dating nothing
- what dates one item: the registry's own line inside the pasted block, `Record created on
  20-Jul-2000.` from InterNIC, written by the registry and not by the poster, so it fixes the
  registration year whatever year the post carries. Rule 6 applies: it evidences that year alone.
  The ingest puts the stamp first in the evidence value, `record created 2000-03-02 pasted in
  alt.comp.issues.spam <message-id>`, so `ark check`'s year test reads the registry date rather
  than incidental digits in a group name
- the artifact: the Usenet mbox archives already on disk under `data/raw/usenet_{bulk,new,probe,probe5,msft}`,
  16,849 files, read offline at zero network cost. `archive.org/robots.txt` was read in full when
  they were collected: 12 lines, 238 B, `Disallow: /control/` and `/report/` only
- the NAME is what the split guards, not the date: a person chose which record to paste and
  reflowed it, and `scripts/collect_usenet_whois.py` caps the look-back at 40 lines and normalises
  `&nbsp;` and quote prefixes before either pattern runs, because an HTML-escaped second copy of a
  block once bound `openssl.org`'s creation date to `engelschall.com`
- ingest specs: `usenet_whois_dated` and `usenet_whois_candidates`. Journals at
  `data/raw/usenet_whois/usenet_whois_{dated,candidates}.jsonl.gz`, regenerable with `just usenet-whois`
- admitted under the standing rule of 2026-08-29 (Ivo)

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

### wayback_availability_2001 / cdx_timestamp

- measured: 99.52 net-new post-split EE already in hand from 1,798 probe requests, over 415 capture
  pairs on 335 domains sampled as DOMAINS and not as `domain_year` rows; 251 were already held
  because those journals are ingested, 164 were net-new and every one of them was at 2001. No split
  applies: a capture stamp is master evidence. The engine measures at **0.3459 net-new EE per query
  and 1,494 EE/hour**, over a queue of **6,568,275 domains held at 2000 and missing 2001**, of which
  **4,137,392 are com/net/org/uk** (re-measured against the store here; the first pass said 4,256,799)
  and worth about 1.43M EE gross. 240 such domains sampled by hash order at one query pinned to
  `20010701` returned 132 captures, 55.0%, which is 55.0% +/- 6.3% at 95%
- what dates one item: `archived_snapshots.closest.timestamp`, the 14-digit capture stamp the Wayback
  index wrote when its crawler fetched the page, returned inside the JSON body of
  `https://archive.org/wayback/available?url=<domain>&timestamp=YYYYMMDD`. It is the same fact
  `cdx_timestamp` already records, read from a second endpoint of the same archive, so no new
  evidence class is being invented. **A parser must take `archived_snapshots.closest.timestamp` and
  not the last `"timestamp"` in the document, which is the caller's own input echoed back and makes
  every probe report a perfect hit.** Accuracy was graded against cdx ground truth already on disk
  with no new cdx requests: 204 cdx year-pairs over 150 domains, 187 recovered, 91.7% recall and
  94.3% at 2001, and 40 of 40 cdx-negative domains came back empty, so it does not invent years.
  Two defects make every zero a lower bound and never a false year: it returns only status-200
  captures, and it canonicalises `www.` away
- terms: `archive.org/robots.txt` is 238 B and 12 lines, read whole before the first request. One
  `User-agent: *` group disallowing `/control/` and `/report/` only, and no Claude-named group.
  1,798 requests were made, 1,786 completed 200 and 12 returned `429` and were honoured with a wait
- potential: 92. Drivers: the largest live opportunity in the register at 1,494 net-new EE/hour and a
  4.1M-domain queue, retrieved end to end in measurement so no unknowns remain, licence-clear, and
  machine-stamped with a zero-false-positive control. Discounted from higher because it is a
  completeness engine competing with the cdx collectors for the same headroom rather than adding to
  it, and because the whole thing turns on one count that only Ivo can move

Decision: pending

**The standing rule of 2026-08-29 does NOT admit this, and the condition that fails is the fourth:
`ark check` cannot pass after the ingest because there is no ingest.** The 1,798 responses were
measured and discarded, nothing was journalled to `data/raw/`, and producing an artifact to ingest
means standing a **third bulk archive client** against the rule in CLAUDE.md that caps them at two.
That cap is a count, not an evidence standard, so only Ivo can move it. Conditions 1, 2 and 3 all
hold: the class is `cdx_timestamp` and already master-eligible, the stamp is machine-written and
quoted above, and the terms were read in full before the first request.

**The cost of the ruling is measured, so it does not need to be argued.** One availability client
runs at 1.27 q/s with 0.67% of requests throttled, measured in the same minutes both cdx collectors
were running and being throttled 27.3% of the time at 0.308 q/s each, off `cdx_gtail`'s own log at
600 queries per 32.5-minute batch. But rate is the wrong statistic in both directions. In gross
in-window pairs per hour cdx wins, because it returns a whole year set per query: 1.583 pairs per
query against availability's one pinned year, 3,511 per hour against 2,515. Priced in net-new EE the
order reverses. 1,200 `cdx_gtail` queries out of the 10:33 and 11:05 journals, neither ingested at
the time of measurement so this is a genuine pre-ingest snapshot, gave 1,900 in-window pairs of which
1,386 were already held: **514 net-new pairs, 324.90 EE, 0.2707 net-new EE per query, 600 net-new
EE/hour for both cdx collectors combined.** Availability wins per query as well as per second,
because its queue guarantees a hit is net-new while cdx's does not. **So retiring one cdx collector
costs 300 EE/hour and buys 1,494**, and the two honest options are to raise the cap to three or to
make that trade.

If it runs: queue `held at 2000 AND missing 2001 AND tld in (com, net, org, uk)` ranked by English
weight, one query each at `timestamp=20010701`, 2 workers and no delay, `429` honoured with the
returned `Retry-After` or 30 s. Journal `{"domain", "timestamp", "year"}` as `cdx_timestamp`. Six-year
enumeration is the worse shape at 0.208 pairs per query and is not the unit. **Do NOT re-aim it at the
2,410,144 undated pool**: that arm is measured and closed at 114 EE/hour, because 98.4% of the pool is
`usenet_address_mention`, `usenet_mention` and `usenet_bare_mention` extraction and 600 sampled domains
hit 5.17% against 97.5% on interleaved controls.
### ncua_5300_call_report_webaddr / artifact_listing

- measured: 1328.31 net-new post-split EE over 1,998 (domain, year) pairs, measured 2026-08-25 over all
  16 in-window quarters. An agent got 1,289.84 independently; the two agree within 3%
- what dates one item: `CYCLE_DATE` on every `fs220d` row, the quarter the call report covers
- potential: 88

Decision: pending

### bbbonline_reliability_roster / artifact_listing

- measured: **1,470.1 net-new post-split EE over 2,376 (domain, 2001) pairs**, measured 2026-08-27 by
  `scripts/price_items.py --all-tlds` against the live store (merged260827), sampling DISTINCT DOMAINS and
  not `domain_year` rows. An independent duckdb year screen gives 2,375 pairs and 1,469.5 EE, so the two
  readings agree to 0.04%. Under the MASTER reading, with no corroboration split, it is 3,109 pairs and
  1,919.7 EE. 9,019 distinct registrable domains under a weighted TLD, 8,286 held at some year (91.9%),
  5,911 already carrying 2001, **2,375 held-and-missing-2001**, mean weight 0.6187, `com` 2,163 / `net`
  175 / `org` 23, typo upper bound 46.3%, 733 pairs to the candidate pool. Yield 0.163 EE per listed
  domain, 0.193 per row, 0.00044 EE per byte
- the payout is adjacent-year and not death-gap: 2,222 of the 2,375 pairs (93.6%) are on domains the
  store already holds at 2000, which is the figure the headroom law says to quote
- what dates one item: the letter page is generated live from the seal programme's participant database
  and carries no in-body date, so the **Wayback capture timestamp in its own URL** fixes the instant the
  roster was current, and programme participation requires an operating reviewed website, so a row
  asserts liveness rather than merely that a name exists. The `coza_deletion_listing` shape, and the
  standard set in killer 8: the grounds are the artifact asserting a state plus a capture fixing when,
  with the 91.9% overlap cited only as a check afterwards
- the artifact: BBBOnLine's Reliability participant directory, an alphabetically enumerable 36-page
  namespace `http://www.bbbonline.org/search/Relresult.asp?letter=<@,0-9,A-Z>` linked from
  `search/Relbrowse.asp`. **33 letters have a 2001 capture**, 3,574,800 bytes total, 7,605 participant
  rows, 9,184 distinct hostnames. Largest: `A` at `20010711225502` 347,822 B, `C` at `20010424220215`
  327,419 B, `T` at `20010711223827` 255,598 B. `L`, `V` and `6` are EXCLUDED and not counted above,
  because `L` returns nothing from the availability API and `V` and `6` return only 2002-01 captures
- how it was found, since the method is the reusable part: **a provider-run member index links the member
  THROUGH the provider and therefore cannot name the member's own domain, measured at 0.0 EE the same day
  as `free_host_member_indexes`, while a seal or certification roster MUST print the member's own domain,
  because the domain is what is being certified.** So the same "customer showcase" lens dies on hosts and
  pays here, and the pre-download question is whether the listing's subject is the customer's SITE or the
  customer's ACCOUNT. The whole 7,600-row database then comes out in 36 requests and needs no CDX query:
  `archive.org/wayback/available?url=...&timestamp=YYYYMMDD` finds the capture and
  `web.archive.org/web/<ts>id_/` returns the original bytes
- two traps a parser must handle, both paid for here: the availability API returns the CLOSEST capture, so
  a `20011215` target lands in 2002-01 for a third of the letters and would silently import a 2002 roster
  as a 2001 observation. **Target `20010901` and reject any timestamp not starting `2001`.** And this
  template writes `HREF=http://...` UNQUOTED, so a quoted-href regex reports 0 absolute links on a
  347,822-byte page holding 1,013 of them
- ingest specs: not written. No parser is registered until this is decided
- unfetched increments, all cheap, none of them counted in the figure above: the Privacy programme has a
  separate roster at `search/Pribrowse.asp` on a different membership; `L` alone is on the order of 200
  rows and needs a capture found by some route other than a single availability probe; and the SAME
  36-page namespace exists at 1999 and 2000 captures, where the adjacent-year law says price one letter
  page before fetching 36
- potential: 87. Drivers: retrieved and licence-clear, self-dating on the capture, 93.6% of the payout
  adjacent-year, 34 requests for the whole artifact, and a named 2x-to-3x expansion in the Privacy roster
  and the 1999-2000 editions. Held back from the 90s only because the dating is `cdx_timestamp` on a
  live-generated page rather than a per-row date field inside the payload

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

### usco_bulk_registrations / typed

- potential: 63

Decision: pending

### squidguard_contrib_2001_origin / artifact_listing

- measured: **1506.4 net-new post-split EE over 2,553 (domain, 2001) pairs, measured 2026-08-27**
  against the live store, so the banked December edition's 18,000 pairs are already excluded. Before
  the split it is 3,292 pairs and 1,960.0 EE. 74 content files, 75,347 distinct hostnames, 42,321
  registrable domains, of which 39,029 (92.2%) already carry 2001. Typo upper bound 49.1%. TLDs:
  `com` 2,283, `de` 183, `net` 73, `org` 6, `nl` 3, `ch` 2
- what dates one item: each category file's own compile header, `# This list was compiled in 79:50:07
  on 2001.07.03 08:08:29.` and `# This list was compiled in 33:22:40 on 2001.09.09 09:48:47.`, written
  by `squidGuardRobot-2.2.13` and `-2.3.4`, each naming itself and asserting a successful fetch
  (`286445 links, of which 230616 tested successfully`). The same grounds Ivo approved for
  `squidguard_2001_blacklist` on 2026-08-26, so nothing was typed by a person and no split applies.
  Tar member mtimes agree (2001-07-03 to 2001-07-09, 2001-08-10 to 2001-09-09), and the
  `newdomains.YYYYMMDD` and `newurls.YYYYMMDD` members carry the date in the filename too.
  `mail/domains` has no compile header and is skipped, as in the banked edition
- the artifact: the squidGuard project's OWN contrib blacklist, from the host that compiled it.
  `web.archive.org/web/20010710215730id_/http://ftp.ost.eltele.no/pub/www/proxy/squidGuard/contrib/blacklists.tar.gz`,
  403,211 bytes, and the previous edition left on disk as `blacklists.tar.gz~` at capture
  `20010911061641`, 1,576,754 bytes. Staged at `data/raw/squidguard_contrib_2001/`
- **the licence needs the human call and the banked entry does not answer it**: both tarballs hold
  `blacklists/README` and no `COPYING`. GPL v2 covers the squidGuard SOURCE distribution the December
  sample travelled in; these two are the standalone data drop from the project's FTP host and carry
  only the README's "entierly products of a dumb robot" warning
- why it was not found sooner: `content_filter_blacklists` below was rejected in part on an era test
  run against `ftp.teledanmark.no`, a MIRROR whose earliest capture is 2003-12-11. The origin has two
  in-window captures. That entry's own surviving bullet quotes one of these headers verbatim
- content is the same adult, gambling, drugs and warez population Ivo was shown before approving the
  December edition
- ingest specs: not written. The banked `squidguard_2001_blacklist` spec reads this exact layout
- potential: 62

Decision: pending

### discmaster_media_index / dated_directory

- measured: 1,055.3 net-new post-split EE, which is the whole yield of the lens rather than a sample:
  the one artifact it has produced is `antispam_media_blocklist`, and the `.jp` listing beside it was
  rejected at 185.3. sources.md records the index saturated by filename and by size over nine queries
  against 1,718,970,121 indexed files. Its robots.txt is `User-agent: * / Disallow: /` with a note
  exempting researchers making 'somewhat limited or somewhat targeted' requests, so a bulk sweep is
  out on both counts (2026-08-27)
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

### truste_licensee_roster / artifact_listing

- measured: **115.1 net-new post-split EE over 184 (domain, 2001) pairs**, 2026-08-27 against
  merged260827 (`scripts/price_items.py` reads 187 pairs and 117.0 EE; quote the lower). 1,522 distinct
  domains, 99.0% held, 1,323 already carrying 2001
- what dates one item: the same argument as `bbbonline_reliability_roster` above, on which this row
  should be decided: a licensee roster generated from the programme's database, dated by the capture
  timestamp `20010603230742`, and holding a TRUSTe licence requires an operating audited site
- the artifact: `http://www.truste.org/users/users_lookup.html`, one page, 128,247 B
- why it is worth a tenth of BBBOnLine on twice the fetch efficiency: **0.076 EE per listed name against
  BBBOnLine's 0.163, the head-corpus law exactly.** TRUSTe licensed `abc.com`, `about.com` and
  `expedia.com`, which the store already holds at 2001; BBBOnLine listed air-conditioning contractors and
  local ISPs, which it does not
- ingest specs: not written
- potential: 55. Drivers: one request, clean licence, identical dating argument to the entry above, but
  head-selected and so an order of magnitude thinner

Decision: pending

### untroubled_spam_headers / artifact_listing

- measured: **1,288.1 net-new post-split EE over 3,053 (domain, year) pairs**, priced 2026-08-27 by
  `scripts/price_items.py --all-tlds` against the live store and reproduced by the harvester to the
  unit. 20,808 dated items yield 29,356 pairs over **26,112 distinct registrable domains**, of which
  22,031 pairs are already held. 2001 carries 2,794 of the 3,053 pairs (1998 115, 2000 91, 1999 50,
  1997 3); by TLD com 1,353, jp 245, net 194, kr 193, tw 131, de 102; mean weight of net-new 0.4219.
  Gross before the split is 7,325 pairs and 3,470.5 EE and must not be quoted
- adjacent-year check: 1,106.8 EE, **85.9%**, sits on a domain the store already holds at Y-1 or Y+1,
  so the yield is not the contaminated "held any year, missing Y" shape. Only 181.4 EE jumps two years
- what dates one item: **the qmail maildir filename is a unix epoch written by the RECEIVING MTA**,
  for example `2001/12/1008021896.29752_202.txt`, and the last-hop `Received:` line added by that same
  MTA restates it (`Received: (qmail 3581 invoked from network); 8 Dec 2001 00:46:21 -0000`).
  **20,007 of 20,010 filename epochs agree with the archive's own directory year.** The spammer's
  forgeable `Date:` header is ignored entirely. This is the receiving host's own stamp on its own
  artifact, which is why it is `artifact_listing` and not `link_target`
- the artifact: `https://untroubled.org/spam/` `1998.7z` `1999.7z` `2000.7z` `2001.7z`, 9,312,329 bytes,
  plus `1997-1998-headers.tar.bz2` (68,996) and `1997-1998-spam-headers.bz2` (67,270); 9,448,595 bytes
  expanding to 20,010 messages and 401 header dumps, 136 MB. Bruce Guenter's spam trap.
  **Licence on the index page: "Permission is hereby granted to use this archive without restriction."**
  robots.txt is 50 bytes and denies only `/stats/` and `/lists/`
- which population, because it decides what the parser reads: five were cut out of the same messages
  and priced separately. Recipient (To/Cc/Bcc/Delivered-To) 10,313 domains at **91.1% held** and mean
  weight 0.549; sender 15,379 at 82.7%; observed last-hop only 8,999 at 82.6%; asserted
  From/Return-Path/Message-ID 7,486 at 83.3%; **body advertised URLs 4,820 at 77.3%, the worst**. The
  figure above is the union of all five. **Forgery does not predict the held fraction**: observed 82.6%
  against asserted 83.3% is indistinguishable, so the 4.56% remailer figure in the register is a
  property of nym addresses and not a law about forged headers
- spot-check: ten random scoring pairs traced to the byte that dates them, all ten confirmed, for
  example `khuman.com` +2001 from the file above, where the store held it at 2000 only
- this supersedes a closure: `docs/sources.md` closed these exact bytes on 2026-08-15 at 195.5 EE over
  4,793 domains. Nothing was MIME-decoded then, and 2001 spam hides its URLs in base64 and
  quoted-printable HTML. It is the only row in `sources.md` known to understate an artifact 6.6x
- the family is exhausted, recorded so nobody re-fetches: the `untroubled_spam_archive` item on
  archive.org is byte-identical file for file; `spamarchive.org` now serves a Syracuse
  window-replacement business, a proved zero rather than a refusal; Ling-Spam is 481 messages, body-only
- ingest specs: not written. No parser is registered until this is decided. Normalised streams are
  staged per population in `price_items.py` input shape and can be re-priced without a refetch
- potential: 52. Drivers: retrieved, unrestricted licence, self-dating on the receiver's own stamp,
  86% adjacent-year, 92% of the pairs at 2001 where the headroom is. Held back by size: 1,288 EE is a
  quarter of the 5,000 the round wants from one source, and there is no second corpus of this shape

Decision: pending

### reuters_rcv1_newswire / dated_directory

- measured: not fetchable without a human signature, and screened at a few hundred EE either way.
  `trec.nist.gov/data/reuters/reuters.html` distributes it only 'by sending a request to NIST and by
  signing the agreements'. Two independent bounds on what that signature buys: the corpus spans
  1996-08-20 to 1997-08-19, so it can date ONLY 1996 and 1997, where the whole store's adjacent
  headroom is 103,953 pairs against 6.7M at 2000-to-2001; and newswire is formal prose, measured on
  Hansard at 0.00153 URLs per 1,000 words, which puts 806,791 stories of roughly 186M words at a few
  hundred URLs, nearly all head names already held (2026-08-27)
- what it is: Reuters RCV1, 806,791 stories from 1996-08-20 to 1997-08-19, free from NIST under a signed
- what dates one item: the story's own dateline.
- potential: 50

Decision: pending

### cipo_ca_trademark_marktext_1996_2001 / typed

- potential: 49

Decision: pending

### cbd_secretariat_meeting_documents_1996_2001 / link_source

- measured: STILL UNPRICED, and the reason is worth recording because it is not the usual one: the
  host is alive and permits us. `www.cbd.int/robots.txt` serves an 'Under Construction' HTML page
  rather than a robots file, so there are no directives to honour, and `/doc/` and `/decisions/cop/`
  both return real pages. What blocks pricing is enumeration: `/doc/?meeting=COP-04` is a 9,334-byte
  JavaScript shell with no document links in the HTML, so the in-window document list has to come
  from the meetings API before anything can be fetched. Requeued as its own task (2026-08-27)
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

### ffa_link_pages / dated_directory

- measured: **25.2 net-new post-split EE over 41 (domain, 2001) pairs**, measured 2026-08-28 by
  `scripts/price_items.py --all-tlds` against the live store (merged260827), sampling DISTINCT
  DOMAINS. 9 pages, 178,235 B, 522 distinct pairs over 484 domains, 451 already held. Pre-split is
  71 pairs / 43.4 EE and overstates 1.7x, do not quote. Mean weight 0.6146, `com` 37 / `net` 4,
  typo upper bound 40.8%. **All 41 paying names are held at 2000**, so the adjacent-year figure
  equals the raw one and none of the yield is the contaminated "held any year" shape
- **the year is the whole result, and it is the squidGuard split again**: the 2001 captures pay
  25.1997 EE on 347 distinct domains (317 held, 91.35%, 276 already carrying 2001), and the 2000
  captures pay **0.0000** on 175 distinct domains, 175 of 175 held and all 175 already carrying
  2000. A 2000-dated FFA page is worthless
- what dates one item: the Wayback capture instant of a member FFA page, which displays the posted
  link as live text at the instant the capture stamps it. **NOT a per-entry date**: the hypothesis
  said the script appends a timestamp beside each URL and that is refuted, 813 links across the two
  genuine FFA pages carrying 1 date literal between them. And a submitter types their own URL, so
  the corroboration split applies and only ALREADY-HELD names gain a year
- the artifact: `web.archive.org/web/<ts>id_/http://pages.ffanet.com:80/links/<member>.htm`, one page
  per network member, 71,305 B at 20010307072648 (`iwv2000.htm`, 506 links) and 47,810 B at
  20000706234213 (`bds.htm`, 307 links). The roster of 110 member pages is
  `ffanet.com:80/links/list.pl?` at 20010304021731 forms, 14,590 B. Plus `freeforall.net`,
  `linkstoyou.com`, `ffanet.com`, `ffanetwork.com`, `freeffa.com`, `ffapages.com`, `1-2-free.com`
- rate and headroom: **0.0726 EE per listed distinct domain**, against webring's 0.0481 and the
  curated-directory floor of 0.013 to 0.024 pairs per listed domain, and effectively all of it comes
  from ONE 2001 page, so the unit is **~25 EE per 2001-captured member page**. 1,000 EE needs ~40
  such pages and 5,000 EE needs ~200. One `list.pl` capture names 110 members and 17 of 18 sampled
  are archived in window, so the inventory exists; the economics are entirely in discarding the 2000
  captures before replaying anything
- rights: `list.pl` carries "This list is the sole intellectual property of FFA NET", which
  constrains republishing the ROSTER; member pages carry only a normal copyright line. Measurement is
  unaffected either way. `web.archive.org` serves no robots.txt (404, verified)
- ingest specs: not written. No parser is registered until this is decided
- potential: 40 (rate beats the curated floor and the inventory is enumerable, but the unit is one
  request per ~25 EE and only 2001 captures pay)

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

- measured: unretrievable, and now with the reason rather than the symptom. `bulkdata.uspto.gov` no
  longer resolves in DNS; `data.uspto.gov/ui/datasets/products/files/TRCFECO2/<year>/case_file.csv.zip`
  returns the 20,666-byte Angular shell instead of the file for 2011, 2022, 2023 and 2024 alike; and
  `api.uspto.gov/api/v1/datasets/products/...` answers `{"message":"Unauthorized"}` with 401. Reopen
  condition: a human registers for an ODP API key. Nothing else about the class has changed (2026-08-27)
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
| 48 | educause_edu_whois_activation | registry activation date | whois_creation | ~280 | 0 banked, 400 to 1,400 priced | MEASURED | rejected |
| 49 | nlm_medline_affiliation_email_1996_2001 | the citation's PubDate | link_source | 0 post-split | 0.0 | MEASURED | rejected |
| 50 | ffiec_call_report_webaddr | quarter-end date, never published | artifact_listing | 0 | 0.0 | MEASURED | rejected |
| 51 | wikipedia_externallinks | the 14-digit IA capture timestamp embedded in each `web.archive.org/web/<ts>/` citation | cdx_timestamp | unpriced | unpriced | SCREENED, NOT MEASURED: law 1 predicts near-zero | pending |

### ia_webdataservices_cctld_extraction / cdx_timestamp

- measured: **0.0 EE on a complete census of the one in-window year I could finish, and the ccTLD
  arm does not exist.** The family has exactly one ccTLD member, `Poland_pl-ccTLD_2001-12-31`, 19
  items of about 10.8 GB each, `access-restricted-item: true`, and `.pl` weighs 0.107, so it is
  refused and worthless in that order. What the family does hold in window is its `earlygovweb`
  sibling, `USFEDGOV-EXTRACT-1996` through `-2001`, public, with a 0.5 MB `.arc.os.cdx.gz` beside
  every 100 MB ARC, so a year can be priced without touching a payload. 1996, all 99 parts, 647,995
  CDX rows every one stamped 1996: 2,660 distinct hosts collapse to 287 registrable domains and all
  287 are ALREADY HELD at 1996. Zero. 2001, 253 of 5,802 parts, 2,158,981 rows all stamped 2001:
  11,369 hosts, 735 registrable domains, 633 held at 2001, **102 net-new pairs and 100.2 EE**
  self-dating, 76.6 after a split it does not need. The domain space saturates hard, 25 parts giving
  452 domains and 253 giving 735, so the whole 754 GB item is a few hundred EE at the ceiling. This
  is law 1 measured on a corpus that had every reason to
  beat it: a 754 GB extraction of the 2001 federal web, dated by the archive's own capture stamp, at
  0.9825 per pair, and the baseline already holds the names because the baseline came from the same
  archive (2026-08-27)
- what it is: the Internet Archive's "Web Data Services" national extraction collections. The measured
- what dates one item: field 2 of every CDX row, a 14-digit capture timestamp. The same field the
- potential: 34

Decision: pending

### store_url_listing_pages / artifact_listing

- measured 2026-08-30 against the live store: **157.8 net-new post-split EE over 250 (domain, 2001)
  pairs** from eleven pages (`scripts/price_items.py` re-read 159.4 EE over 252 pairs at harvest;
  quote the lower). 1,245 distinct domains sampled AS DOMAINS, 148 already held at 2001, 1,097
  net-new before the split and 688.8 EE, which overstates the source 4.4x and must not be quoted.
  Mean weight 0.6311, `com` 230 / `org` 13 / `net` 7, typo upper bound 46.4%, 847 pairs to the
  candidate pool
- what dates one item: the 14-digit Wayback capture stamp in the page's own URL, `20011023104545`
  over `www.domainsww.com/Domain_Listing.htm`, fixing the instant the listing was served. The
  listing carries no in-body date and whoever kept the page typed the names, so every name takes
  the corroboration split and only the names another source already dates earn 2001
- the artifact: eleven pages, 261,007 B, all fetched as `web.archive.org/web/<ts>id_/`. Largest
  `http://www.domainsww.com/Domain_Listing.htm` @20011023104545 53,245 B,
  `http://promoone.com/Domain_Listing.html` @20011211231904 52,907 B,
  `http://www.registrars.com/static/frontpage/reg_domain_list.shtml` @20010203234600 38,225 B
- **how it was found is the part worth keeping, and it cost no requests**: `data/raw/webbase/webbase-2001.urls.gz`,
  118,142,155 URLs already on disk, matched on the PATH only. The host-inclusive regex is 375x
  noisier (117,912 hits, almost all `www.export.nl` and `gopher.csv.warwick.ac.uk` style host noise)
  against 314 distinct URLs from the path-only domain signature list. 24 were screened through
  `archive.org/wayback/available?timestamp=20010901`, never CDX; 17 had a capture, 15 in 2001, and
  rejecting any stamp not starting `2001` caught 2 that would have imported a 2002 page as a 2001
  observation
- **failed condition 2 of the standing rule of 2026-08-29**: what dates the item is the capture
  stamp rather than a machine-written stamp inside the artifact, the same reason
  `coza_deletion_listing` and `cctld_register_listing_capture` sit in this section
- the held fraction is the ceiling, and it is a pre-download discriminator: **398 of 1,245 names
  (32.0%) are held in any year**, against the 87-99% of an authority corpus, because a for-sale or
  registrar listing prints speculator inventory that never resolved. The 250 that pay are 62.8% of
  the held names, which matches the population `com` 2001 threshold of 0.611, so the pages carry no
  year advantage of their own. Aim the same regex at hosts listing CUSTOMERS rather than INVENTORY
  (`w-link.com/Clients/domain_list.shtml` is the right shape, `promoone.com/Domain_Listing.html`
  the wrong one)
- ingest specs: not written
- potential: 34. Drivers: cheap and licence-clear, and the finder behind it is reusable over four
  more on-disk URL corpora (`early_web`, `ukwa`, `ccgraph`, `cdx_suffix`) at zero request cost, with
  290 of the 314 WebBase candidates still unscreened and worth roughly 1,900 EE at the measured
  rate. Held down by the 32% held fraction, which caps the per-page yield near 14 EE, and by the
  condition-2 failure

Decision: pending

### cordis_fp4_fp5_project_websites / link_target

- potential: 32

Decision: pending

### fdncenter_grantmaker_web_sites / dated_directory

- measured: **202.2 net-new post-split EE over 289 (domain, year) pairs, every one of them at 2001**,
  priced 2026-08-28 with `scripts/price_items.py --all-tlds` against merged260827 over 19 dated pages,
  601,956 B. 1,843 distinct pairs over 1,843 domains, 1,523 already held AT 2001 (82.6%), only 29 names
  never held anywhere (98.43% held). Pre-split 320 pairs and 223.6 EE, which overstates by 1.11x and must
  not be quoted. Mean weight 0.6996, org 257 / com 29 / net 3, typo upper bound 37.8%. **279 of the 289
  gain domains (96.5%) are held at 2000**, so this is adjacent-year headroom and not a death gap
- independently reproduced: a duckdb screen sampling DISTINCT DOMAINS over the three `fdncenter` `_list`
  pages agrees to 0.36%. 1,648 listed distinct, 1,619 held (98.240%), 1,349 already carrying 2001
  (81.857%), held-and-missing-2001 = 268 at 187.43 EE against `price_items`' 269 at 188.1
- what dates one item: the Wayback capture instant of the portal's own roster page. The artifact asserts
  the organisation's web address at the instant the capture stamps, and no page in the family carries a
  usable self-date, so the capture is the only defensible dating and **the corroboration split is taken**
  (it is applied in the 202.2 figure above). A creation date is not claimed and no year outside 2001 is
  evidenced by any of these pages
- the artifact: 7 paying pages, all fetched as `https://web.archive.org/web/<ts>id_/...`.
  `fdncenter.org/funders/grantmaker/gws_pubch/pubch_list.html` at 20011102033013 (109,219 B, 740 domains),
  `gws_priv/priv_list.html` at 20011024182703 (94,984 B, 548), `gws_priv/priv2.html` at 20011004165617
  (110,244 B, 546, a Netscape-4 duplicate of priv_list and the check that priv_list is complete),
  `gws_corp/corp_list.html` at 20010806091046 (60,358 B, 376), `www.interaction.org/members/` at
  20011101195341 (64,657 B, 149), `www.foundations.org/grantmakers.html` at 20011015131123 (13,829 B, 99),
  `www.igc.org/igc/gateway/index.html` at 20011011002103 (19,167 B, 36). priv_list and pubch_list carry
  260 of the 289 pairs
- per-arm attribution, and it is the reason to read the entry rather than the total: the yield spreads
  10.1x inside one directory. priv_list 548 listed / 532 held / 375 carrying 2001 / 157 gain / 109.98 EE
  = **0.2007 EE per listed name**; pubch_list 740 / 728 / 625 / 103 / 72.08 = 0.0974; interaction
  149 / 149 / 134 / 15 / 10.65 = 0.0715; foundations.org 99 / 99 / 94 / 5 / 3.47 = 0.0351; **corp_list
  376 / 373 / 362 / 11 / 7.50 = 0.0199**, because corporate giving programs live at `abbott.com`,
  `aetna.com`, `adobe.com` and 97.05% of the held ones already carry 2001, while private foundations live
  on their own small `.org` domains and only 70.5% do
- why it is small, stated so the reviewer is not surprised by the number: 0.1097 EE per listed domain and
  10.6 EE per page fetched, so 1,000 EE would need 9,116 listed domains in this shape. Only 15.93% of held
  names here lack 2001 (289/1,814) against the `.org` population's 69.15%, a 4.34x head-selection penalty
- there is no expansion, and this is measured rather than assumed: the family is closed at 202.2 EE.
  `gws_comm` was never captured (`comm_list.html`, `comm1.html`, `comm.html` all 404 against a passing
  control), the A-Z letter pages are the same names annotated, and every large 2001 nonprofit portal put
  its records behind a search form (GuideStar ~640,000 orgs and Idealist ~20,000 are one record per
  request; CharityChoice's own meta description claims 7,000 entries and only the FORM is archived).
  `advancedsearch.php` finds no bulk item for the family in window
- licence: Wayback replay of pages whose publishers are defunct. No robots refusal was met on any host
  fetched, and the whole run was done at ~1 q/s
- ingest specs: not written. **Nothing was ingested.** No parser is registered until this is decided
- potential: 32. Drivers: retrieved in full and already in hand at 7 pages, self-dating on the capture,
  96.5% of the payout adjacent-year, and independently reproduced to 0.36% by a second method. Held back
  hard by size, because 202.2 EE is the whole family and there is no next increment to buy with an
  approval, and by the dating being `cdx_timestamp` on a live-generated page rather than a per-row date
  inside the payload

Decision: pending


### bomis_ring_member_lists / dated_directory

- measured: **19.1 net-new post-split EE over 31 (domain, year) pairs, all at 2001**, on a seeded
  20-ring sample of which 16 returned content, priced 2026-08-27 against the live store. 500 host
  strings give 396 distinct registrable domains, **392 held at some year (98.99%)**, 361 already held
  at 2001, **held-and-missing-2001 = 31**, only 4 names never held. Mean weight 0.615, com 28 net 3.
  Rates: **0.0481 EE per listed domain, 0.95 EE per ring attempted, 24.8 domains per ring**
- what dates one item: the Wayback capture timestamp of the ring's own `ring_home.fcgi` page, which
  prints the member's hostname as plain text beside its title, so one archived ring page asserts
  "Bomis listed this host" at the instant the capture stamps it. Human-curated, so it takes the
  corroboration split, and that costs nothing here because held-and-missing-2001 is the whole payable
  set anyway
- the artifact: `http://web.archive.org/web/20010701000000id_/http://www.bomis.com/ring_home.fcgi?ring=<ring>`,
  one page per ring, 6 to 8 KB, all 16 captured between 2001-04 and 2001-07. Ring names come from
  `http://www.bomis.com/tree/<Category>/` at the same pin. In-window archival coverage 16/20 = 80%
- why it is thin, since it reproduces a figure the register already has: only **7.9%** of held names
  lack 2001 here against the population average of 61.1% for `.com`, because a curated ring lists the
  site still worth listing and the store covers those at 2001. 0.0481 EE per name against
  `WinNetMagCD`'s 0.041 and against 0.386 for a random held `.com`
- what would decide it, and it is not measured: volume. At 0.95 EE per ring, 1,000 EE needs ~1,050
  rings and 5,000 EE needs ~5,250. 83 rings sit on the 14 top-level tree pages alone and a BFS of
  `/tree/` had 164 unvisited category pages queued after 4 fetches, so the inventory is plausibly in
  the thousands. Two steps in order: crawl `/tree/` to exhaustion at the 20010701 pin for an exact
  count (~400 pages, cheap, and it decides the whole question), then one `ring_home.fcgi` per ring.
  `www.bomis.com/rings/<r>/` carries the member count as `max=N` in its frame src, so ring SIZE is
  readable one request ahead and the queue can be ranked biggest-first, which matters because the
  yield is concentrated in the few large rings
- what this reopens, since the method is the reusable part: `docs/sources.md` closed webring member
  lists on 2026-08-05 because WebRing routes every member through `go.webring.org`. Bomis routes
  through its own pages too but **prints the bare hostname as text**, so the redirector is irrelevant.
  **A redirector kill is a claim about one hub, not about a shape**
- the siblings are closed and are noted so nobody re-tests them: **RingSurf** dies on retrieval, not on
  shape, with 0 of 16 sampled ring pages archived against a passing control; **LinkExchange** has no
  2001 surface, closest capture 1999-08-30
- ingest specs: not written. Nothing was ingested
- potential: 30. Drivers: self-dating on the capture, permission is not the blocker and IA replay
  throughput is, and the class is master-eligible. Held back by the rate, which is 8x below a random
  held `.com`, and by the fact that the payoff is entirely a bet on a ring count nobody has counted

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

### mailman_public_roster / cdx_timestamp

- measured 2026-08-30 against the live store: **89.4 net-new post-split EE over 179 pairs**, by year
  {2000: 1, 2001: 178}, `com` 70 / `net` 33 / `org` 23 / `de` 11 / `hu` 4 / `fr` 3, mean weight
  0.4996, typo upper bound 67.3%. Re-priced at harvest and identical. Before the split it is 254
  pairs and 128.5 EE, which must not be quoted. 2,358 distinct registrable domains sampled AS
  DOMAINS, **2,283 held (96.8%)**, 2,102 of the held already carrying 2001, so the payout is exactly
  the 181 held-and-missing-2001 names; adjacent-year (held 2000, missing 2001) is 170. The 75
  never-held names take the split and go to the candidate pool, 42 of them new to it
- what dates one item: the Wayback capture timestamp on a Mailman-generated `/mailman/roster/<list>`
  page, `20010717203344` over the 1,430-member `mailman-users` roster. The table itself is written
  by Mailman out of the membership database with nothing typed by a person, but **the page carries
  no internal date stamp of any kind**
- **failed condition 2 of the standing rule of 2026-08-29**: the dating is the capture stamp alone,
  not a machine-written stamp inside the artifact
- the artifact: 5 public in-window rosters, 322,905 B, all `web.archive.org/web/<ts>id_/`:
  `otc.isu.edu:80/mailman/roster/herbal-rx` @20001001121841, `mail.python.org:80/mailman/roster/mailman-announce`
  @20010302182443, `.../xml-sig` @20010430163722, `.../mailman-users` @20010717203344,
  `scipy.net:80/mailman/roster/scipy-user` @20011214121348. `web.archive.org/robots.txt` is a 404,
  so no host rule applies; enumeration used `archive.org/wayback/available`, never `/cdx`
- **a roster is a discovery loss and a year win**, which is the squidGuard 2001-12-18 result again:
  the subscriber population reads 96.8% held, the authority-corpus figure rather than the ~50% of a
  blocklist, and only the 7.7% held-and-missing-2001 slice pays
- unit economics, and they are the reason this is small: **0.0379 EE per listed subscriber domain**,
  17.9 EE per public in-window roster page, at a 1.1% conversion (5 usable of 454 probed roster
  URLs). 5,000 EE needs ~280 more public in-window rosters over ~25,000 candidate roster URLs, and
  saturation is already visible at n=5, since the per-page counts sum to 2,921 against a union of
  2,358, 19.3% duplication, with 3 of the 5 pages on one host
- law 6 does not reach it: Mailman obscures addresses as `user__at__domain.tld` and `user at
  domain.tld`, and both keep the domain intact
- ingest specs: not written
- potential: 22. Drivers: licence-clear, fully retrieved, and the URL generator behind it is free
  (every Mailman footer prints `/mailman/listinfo/<list>`, so 868 MB of on-disk list archives gave
  463 host/list pairs at no network cost). Held down hard by the fixed ~18 EE per page, the 1.1%
  conversion, visible saturation at n=5, and the condition-2 failure

Decision: pending

### state_sos_entity_registers / typed

- potential: 22

Decision: pending

### uk_trade_press_extension / dated_directory

- measured: 191.1 net-new post-split EE over 247 pairs, the whole corpus censused on 2026-08-27
  rather than sampled. All 33 in-window UK issues archive.org holds were read in full: Internet
  Magazine 16, Practical Internet 14, PC Format 2, Personal Computer World 1, by year 1999 10,
  2001 8, 2000 6, 1998 5, 1997 4. 11,639 pairs over 9,541 domains, 8,085 already held, 3,554
  net-new before the split and 247 after, so the raw figure overstates it 14.6x. By TLD `uk` 115,
  `com` 97, `net` 32, `org` 2, `edu` 1. Typo bound 58.3%, which is what OCR of a 1990s magazine
  costs. The `_djvu.txt` of these scans is named 'Internet Magazine 031 [1997-06]_djvu.txt', so the
  probe that assumes `<identifier>_djvu.txt` called 32 of the 33 unreachable (2026-08-27)
- potential: 22

Decision: pending

### cog2002_gid_school_systems_weburl / link_target

- potential: 20

Decision: pending

### udrp_decision_creation_date / whois_creation

- what dates one item: the panel's recitation of the registrar's verification answer inside the
  decision text, for example `The Whois record of the domain MUSICWEB was created on January 10, 1995`
  (WIPO D2000-0001) and `Respondent registered the disputed domain name on July 3, 2001` (NAF 101268).
  The date originates with the registrar, but **the sentence in the artifact was typed by a panellist**,
  which is what stops it here
- measured 2026-08-29 against the live store, census incomplete at 1,125 WIPO and 550 NAF decisions
  fetched: WIPO 284 pairs over 284 domains, 100% attested, 73.6% already held, **46.2 net-new
  post-split EE**; NAF 70 pairs, 75.7% already held, **10.4 EE**. Both arms take the split and lose
  nothing to it, since a disputed name is always already known
- the artifact: `https://www.wipo.int/amc/en/domains/decisions/html/<year>/d<case>.html` and
  `https://www.adrforum.com/domaindecisions/<claim>.htm`. WIPO robots.txt read in full, 134 lines and
  one `User-agent: *` group, which disallows `/amc/en/domains/decisions/word` and permits the `html`
  path used here
- **failed condition 2 of the standing rule of 2026-08-29**: what dates the item is not a
  machine-written stamp inside the artifact but a human recitation of one. **The NAF arm additionally
  fails condition 3**: `adrforum.com/robots.txt` answers with an HTTP redirect body rather than the
  file, so its terms were never actually read
- ingest specs: not written. No parser is registered until this is decided
- potential: 20

Decision: pending

### ripe_db_lastmodified / link_target

- potential: 12

Decision: pending

### ukwa_ds2_year_cdx / cdx_timestamp

- measured: nothing to measure. The artifact cannot be fetched at all, so this row is not a pricing
  question but a waiting one, and the answer below is the reason (2026-08-27)
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

### edelman_cipa_blocked_sites_2001 / artifact_listing

- measured: 134.1 net-new post-split EE, 2026-08-29, over 4,898 distinct domains (99.4% held any
  year, 94.7% already carrying 2001, 228 held-and-missing-2001 all adjacent)
- what dates one item: the vendor classifier's own observation column,
  `Blocked On (dates) (all dates are in 2001)`
- BLOCKED on condition 3 of the standing rule, terms: the host page states "The data contained here
  is not intended for use for other purposes, and it should not be used for other purposes without
  first contacting the author". Not to be ingested unless Edelman answers.
- potential: 6. Drivers: measured small and blocked on terms, so it cannot be worked without a reply

Decision: pending

### osbar_bulletin_html_issues_2000_2001 / link_source

- measured: ceiling about 77 EE for the whole run, 3.2 measured per issue over the 24 monthly issues
  of 2000-2001, and the live host no longer serves any of it: `/publications/bulletin/`,
  `/publications/bulletin/00jun/` and `/publications/bulletin/archives.html` all return the same
  32,677-byte 'Site Error' page, so a full run would be Wayback-only (2026-08-27)
- potential: 6

Decision: pending

### winsite_cica_dated_shareware_index / typed

- potential: 5

Decision: pending

### lawsociety_ie_gazette_issue_pdfs_1997_2001 / link_source

- measured: ceiling about 130 EE, 2.6 measured per issue over roughly 50 in-window issues, and the
  live archive does not serve them: `/gazette/issues/` redirects to `/login`, and the PDF path that
  works for 2026 (`/globalassets/documents/gazette/gazette-pdfs/gazette-2026/july-2026-gazette.pdf`)
  404s for gazette-2001, gazette-1999 and even gazette-2004. Wayback-only (2026-08-27)
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

### ripe_dbase_split_2004 / artifact_listing

- measured: **916.6 net-new EE over 1,514 pairs** against the live store on 2026-08-31, full
  enumeration rather than a sample; **banked 913.84 EE over 1,510 pairs**, the 4-pair gap being the
  store growing between the pricing and the ingest. By year 1998 4 / 1999 253 / **2000 792** /
  **2001 461**, so 800 EE of it is the two years the store is thinnest in. By TLD `gm` 558 pairs,
  `mc` 314, `sm` 248, `bg` 246, `no` 45, `il` 36, `lv` 26. **No corroboration split**, on the identical ruling `ripe_dbase_changed`
  carries: nothing here is typed by a person, the transaction date is written by the database. For
  the record, `price_items.py` applies its split unconditionally and reports 271 pairs / 78.5 EE, and
  that figure is the floor if the ruling of 2026-08-26 is ever reversed
- what dates one item: the object's own `changed:` line, verbatim from the file,
  `changed:      ovema@a.sol.no 19971128` under `domain:      hasselblad.gm`. The date is the
  RIPE database's record of a transaction applied to that object, and you cannot modify an object
  that does not exist. Rule 6 gives that year alone; a second year needs its own `changed:` line
- the artifact: `https://ftp.funet.fi/pub/netinfo/RIPE/dbase/split/ripe.db.domain.gz`, **5,452,546
  bytes**, `Last-Modified: Tue, 09 Nov 2004 23:31:00 GMT`, 2,060,522 lines, 162,408 `domain:`
  objects, 192,835 `changed:` lines. `ftp.funet.fi` has no robots.txt (404, 355 B)
- terms: the directory's own `RIGHTS` notice, reproduced in the file header, is the same RIPE NCC
  "Restricted rights" text as the 1999 file, and RIPE NCC Member Services cleared exactly that notice
  on 2026-08-26. The one condition is request volume against the LIVE database, which a static
  mirrored file does not touch
- ingest spec: `ripe_dbase_split_2004`, reading `domain:` and the trailing date of `changed:` and
  nothing else. Two tests in `tests/test_sources.py` fail on an address leak
- potential: 96
- admitted under the standing rule of 2026-08-29 (Ivo)

Decision: master

**Why a second edition of one database is not a duplicate.** FUNET's whole-database `ripe.db.gz`
froze on 1999-08-03 and the `split/` directory beside it froze on 2004-11-09. A 1999 file cannot
carry a transaction that had not happened yet, so the 16,536 `changed:` lines dated 2000 and the
21,507 dated 2001 exist only in the later edition. That is the whole find.

**It pays hundreds and not thousands because RIPE deleted the forward objects in between.** The 1999
file holds 1.23M forward names; this one holds 6,160, the other 96.2% being `in-addr.arpa` and
`ip6.arpa`, which killer 3 already priced at nothing. `.gm` (Gambia, weight 0.9969) was administered
out of Norway and is the highest-weight population in the file, worth more than `.bg` and `.mc`
together, so a regional registry's forward names need histogramming by TLD rather than assuming
the region.

**Staleness control, because a projection against an export is how a source gets overstated.** Of the
1999 file's names carrying a 1998 `changed:` line, 100.00% are held at 1998, which proves the banked
`ripe_dbase_changed` is fully reflected; of the alive-in-1998 names carrying no 1998 line, 55.88%.
So the residual behind the pricing is real and not an export artefact.

**One correction to `docs/sources.md`**: FUNET's `split/` was recorded there as "15 same-1999-edition
subsets" and it is a 2004-11-09 edition, and the sentence saying the 2000-and-2001 `changed:` route
does not exist was wrong.
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

- approved by Ivo on 2026-08-31, with `sec_edgar_filings` moved to the back of the queue

Decision: master

### granitecanyon_zone_rejects / artifact_listing

- measured: **1,732.9 net-new post-split EE over 3,059 (domain, year) pairs**, measured 2026-08-29 by
  `scripts/price_items.py --all-tlds` against the live store (merged260827). 18,797 listed items give
  17,049 distinct pairs over 16,979 domains, 6,777 already held, mean weight 0.5665, by year
  {1999: 2,001, 2001: 1,058}, by TLD {com 1,613, net 407, org 300, ch 58, de 51, nu 49}, 7,213 pairs
  and 6,828 names to the candidate pool, typo upper bound 57.1% (856 of 1,500). Pre-split is 10,272
  pairs and 5,813.2 EE and **overstates by 3.4x, do not quote it**. An independent duckdb screen
  sampling DISTINCT DOMAINS and not `domain_year` rows agrees to about 1%: stale_30Nov1999 13,199
  distinct domains, 7,969 held-any (60.4%), 5,943 held at 1999, 2,026 held-and-missing-1999 against
  price_items' 2,001; the 2001 ZoneRejects union 4,092 domains, 1,916 held-any (46.8%), 845 held at
  2001, 1,071 held-and-missing-2001 against 1,058. The gap between the two routes is the TLDs with no
  English weight. Split by edition: the 1999 list alone is 1,125.5 EE, the 2001 reject union alone
  607.3 EE
- the population does not collapse on the 2001 threshold, which is the reason to want it: P(lacks 2001
  | held) measured here is com **0.5745**, net 0.6174, org 0.5113 against the store-wide law's 0.611 /
  0.653 / 0.568, so within 6%, and yield per held name at 2001 is 607.3 / 1,916 = **0.317 EE** against
  the 0.386 the law predicts for a held `com`. At 1999 the same names give com 0.2539, net 0.2273, org
  0.2401, so a held name in a 2001 edition is worth 2.3x the same name in a 1999 edition
- held-fraction, the pre-download discriminator: **60.4% and 46.8% held-any**, against 87 to 99% for
  authority corpora, ~50% for blocklists, 98.4 to 99.6% for visitor logs and ~5% for forged-header
  spam corpora. A zone is not a page, so no crawler reaches it through a link, and the artifact is not
  head-selected: it is people who had a domain and no server
- what dates one item: the list stamps its own generation instant in its bytes, `Rejected Zone List:
  7-May-2001 22:11 GMT` on each ZoneRejects edition and status.shtml's "29 November 1999 ... here is
  the list of pruned zones" for the prune file, and the IA capture fixes when the file existed. So one
  row is Granite Canyon's nameserver holding that zone in its BIND configuration at that instant,
  which is a machine's configuration record rather than a description of one. **The zone name was
  typed by the customer into a submission form, so the corroboration split applies and only
  already-held domains earn a year**, and the 1,732.9 above is already post-split. Killer 8 order: the
  grounds are the self-stamp plus the capture, with the 60.4% / 46.8% overlap cited only afterwards as
  a check
- the artifact: seven objects, 1,567,653 B, **all already downloaded and nothing ingested**.
  `https://web.archive.org/web/20010601000000id_/http://soa.granitecanyon.com/stale_30Nov1999.txt`
  (205,787 B, 14,522 zone names) plus six in-window editions of
  `https://web.archive.org/web/{20010223195457,20010508024101,20010611192639,20010626115208,20010901062251,20011204210150}id_/http://soa.granitecanyon.com/ZoneRejects/`
  (193,389 / 212,935 / 215,340 / 222,405 / 245,087 / 272,710 B, 2,948 to 4,097 forward zone names each)
- exhaustion, so nobody re-probes it: six ZoneRejects editions exist in 2001 and no more, fourteen
  probes across 2001-01 to 2002-04 collapsing onto those six timestamps. A seventh edition dated
  26-May-2002 (3,834 names) is **out of window and cannot date a year**. The predecessor
  `zoneRejects.txt` is 9 names at 2000-03-03 and HTTP 403 at every later capture. Cost was 40
  archive.org fetches, no other host touched, zero queries against web.archive.org/cdx
- not a by-construction zero: no `granitecanyon` directory exists under `data/raw`, `docs/sources.md`
  records no ingest of it, and what already dates the held names on a 400-domain sample is
  `prior_task` 196, `usenet_announce` 48, `domain_creation_bulk` 33, `isc_survey` 33, `rdap_snapshot`
  26. Prior art: `docs/sources.md` recorded "Granite Canyon secondary-DNS artifacts 1,881.1 EE
  post-split against a 5,000 bar" on 2026-08-24 and kept no bytes and no URL, so it was not
  reproducible. This request names the artifacts; 1,732.9 is that figure decayed by five days of
  ingest since
- how it was found, since the method is the reusable part: **when a service hides its inventory behind
  a login, look for its ERROR LOG instead.** All four free-DNS operators refused to publish a customer
  list (secondary.com 2001-05-16 behind `/auth/`, zoneedit.com 2001-06-04 behind `login.html`,
  xname.org 2001-10-27 behind a per-zone password, freedns.com an empty Apache index); the one that
  published a nightly list of the zones its BIND could not load gave away 4,369 names it never meant
  to. Reject lists, prune lists, lame-delegation reports and stale-zone reports are machine-generated,
  self-stamped and regenerated on a schedule, so every capture is a fresh dated edition. And the list
  files were enumerated from `status.shtml`, the site's own dated changelog, at four captures spanning
  1999 to 2002, rather than from a CDX prefix query
- density per LISTED name, for the pre-download screen: **0.102 EE combined, 0.148 at 2001, 0.085 at
  1999**, against the curated-directory floor of 0.005 to 0.017. So this class is 6x to 30x denser per
  listed name than a human-curated directory, and the ~83,000-name floor that class demands becomes
  about 7,000 to 12,000 names here
- ingest specs: not written. No parser is registered until this is decided
- unfetched increments, none of them counted above and neither of them this family: registry-scale
  lame-delegation and stale-zone reports, the same artifact shape at 100x the population
  (dailychanges.com's `LAME-DELEGATION.ORG` page paid 1,548 EE on this shape); and
  `news.granitecanyon.com/soa.help`, a support newsgroup whose articles name the poster's own zone,
  dated per article and on this same 46.8%-held population
- potential: 88. Drivers: retrieved in full so no further network is needed, self-dating inside the
  payload rather than on the capture alone, two independent measurement routes agreeing to 1%, and a
  held-fraction and 2001 threshold that both land where the laws want them. Held below the 90s because
  the family is closed at seven objects with no in-family expansion, 65% of the payout is the 1999
  edition at 2.3x lower yield per name, and the split is load-bearing here rather than free

- approved by Ivo on 2026-08-31, with `sec_edgar_filings` moved to the back of the queue

Decision: master

### fac_sfsac_historic_1998_2001 / artifact_listing

- measured: SAME CORPUS as `fac_single_audit`, which was priced at 2,406.69 net-new post-split EE on
  2026-08-24: same filings, same 1998-2001 window, same `AUDITEEDATESIGNED` field. Two class names
  over one artifact, so the word on `fac_single_audit` decides this row too and there is nothing here
  to price separately. Deliberately not written as a `- measured:` figure, because the decision sheet
  sums those and this one would double-count 2,407 EE. The estimate of 6,000-12,000 per YEAR was 15x
  to 30x high (2026-08-27)
- what dates one item: `AUDITEEDATESIGNED`, "Date of auditee signature", per filing
- potential: 86

- **RESOLVED 2026-08-31 as a duplicate, and it must not be counted.** This is the same corpus as
  `fac_single_audit`, which was banked on 2026-08-31 at 1,403.2 net-new post-split EE from bytes Ivo
  downloaded by hand. Same filings, same window, same `AUDITEEDATESIGNED` field. Two class names over
  one artifact, so there is nothing here to admit separately and the 2,407 must not be added to any
  queue total

Decision: rejected

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
**Another entry whose `- measured:` line was lost in the 2026-08-23 compaction; measured for good on
2026-08-29 and now recorded in `docs/sources.md`.** BLOCKED on terms at **0 EE banked**. The banner
PRECEDING every record at `whois.educause.edu:43` prohibits harvesting except as needed to register or
modify a name, so one query was made and no more; `.edu` has no RDAP and the web front end is the same
database behind a Cloudflare challenge. Priced anyway from a third-party name list, touching no term:
of 2,448 live `.edu` names, **51.39% already hold all six in-window years at P(missing) 0.0000**, so a
creation date pays nothing there, and 23,680 of the store's 25,400 `.edu` names are not in the live
register at all. Band is **400 to 1,400 EE** with permission, under the floor and not worth a letter.

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
(2026-08-24, artifact is 2003). **That era test was run on a MIRROR and is superseded**: see
`squidguard_contrib_2001_origin` above, where the origin host `ftp.ost.eltele.no` gives two
in-window editions worth 1,506.4 EE. Reopen condition: a non-Wayback mirror of the decoded cphack blacklist;
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



### mynic_my_change_report / artifact_listing

- measured: **6,883.1 net-new EE over 9,081 pairs, whole tree, measured 2026-08-31** against the live
  store from 34 of the 35 in-window pages (`dec2001-1` has only a 318-byte empty capture). 12,118 rows,
  10,322 `New` and 1,796 `Delete`, years {2000: 3,716, 2001: 8,402}, 11,690 distinct pairs over 11,564
  domains, 2,609 already held, mean weight 0.7579, typo bound 26.6%. Post-split would be 1,180.8 EE
- **the split does NOT apply, settled on a test rather than a judgement**: MYNIC's own monthly
  statistics table gives March 2001 as New 850 / Delete 166, and parsing the two listing halves gives
  **New 850 / Delete 165**, so the listing is a complete enumeration out of the same database and this
  is the registry stating its own register, as TWNIC, IDNIC, RESTENA and SaudiNIC all are. The earlier
  "3091.1 pre-split / 159.9 post-split from 25 pages, whole tree near 10,000 and 400" was 1.45x high on
  the unsplit reading and 3x low on the split one
- what dates one item: the per-day heading above each entry, `2 April 2001`, with `New` or `Delete`
  beside the name, so the registry is stating that this name entered or left the register that day
- ingest specs: not yet written; the parser is measured but no spec is registered until this is decided
- the artifact: MYNIC published a fortnightly `Domain Name Listing` at
  `mynic.net.my/my/stats/<month><year>-{1,2}.htm`. 60 archived pages, of which the `-1` and `-2` halves
  carry names and the bare-month pages are statistics tables only. `.my` weighs 0.7580
- potential: 70

- approved by Ivo on 2026-08-31, after the split test and the truncation screen

Decision: master

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

### coza_deletion_listing / cdx_timestamp

- measured: **3,704.3 net-new EE over 3,826 pairs, wider tree VERIFIED 2026-08-31**. 22 captures return
  HTTP 200 across `co.za`, `posix.co.za` and `www.posix.co.za` against the 11 previously verified, and
  the `posix` half is not duplicate: its earliest editions are 1997-12-21 and 1998-01-17, earlier than
  any `co.za` capture. 12,404 rows, years {1997: 1,656, 1998: 5,551, 1999: 3,074, 2000: 2,123}, 5,439
  distinct pairs over 4,360 domains, 1,613 held, mean weight 0.9682. The agent's 4,462 EE was 1.2x high.
  No split: shell CGI reading the register. Post-split would be 1,211.2 EE
- **640 rows must be dropped and it is a defect in the artifact**: the CGI prints bare labels in fixed
  16-character columns and truncates the name to fit, in the `href` as well as the anchor text, so
  `sahomeimprovement` is served as `sahomeimprovemen`. 303 labels are 15 characters against a spike of
  640 at exactly 16, and admitting them would mint well-formed domains that never existed
- **the years are the caveat**: captures run 1997-12 to 2000-08 with nothing in 2001, and 1,018 of the
  1,251 post-split pairs land at 1998, the thin end of the window
- what dates one item: the Wayback capture stamp on the page, since the listing carries no in-body date
  at all, and a name shortlisted for deletion is one the registry is stating is registered right now
- the artifact: the CO.ZA registry's own `cgi-bin/warn.sh` and `cgi-bin/todel.sh`, 11 in-window
  captures, listing bare labels under a header reading `The following domains are shortlisted for
  deletion. This is either due to lack of payment or lack of paperwork`. `.za` weighs 0.9682
- potential: 62

- approved by Ivo on 2026-08-31, after the split test and the truncation screen

Decision: master

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

- approved by Ivo on 2026-08-31; refetched and repriced from the bytes at 2,450.2 EE

Decision: master

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

### fac_single_audit / dated_directory
- measured: **CLOSED ON ACCESS, not on evidence, 2026-08-31.** The primary source is
  `https://www.fac.gov/data/download/historic/` and the four in-window files are
  `https://app.fac.gov/dissemination/public-data/census/csv/census-{1998,1999,2000,2001}.zip`.
  **`https://app.fac.gov/robots.txt` is exactly `User-agent: *` / `Disallow: /`**, so every data file
  is behind a blanket refusal; only the landing page and dictionary sit on `www.fac.gov`, which permits
  everything. `harvester.census.gov` now 302s to a maintenance page. No open mirror: data.gov's package
  API 404s and archive.org holds only the application's source code
- the claim is structurally correct and the dictionary confirms it: `AUDITEEEMAIL` "Auditee Email
  address, 60 characters max" and `AUDITEEDATESIGNED` "Date of auditee signature, mm/dd/yyyy", across
  every form revision in the window. The dataset also **begins at 1998**, so 1996 and 1997 are
  unreachable through it regardless
- the 2,406.69 EE of 2026-08-24 is not reproducible by us: nothing under `data/raw` or `private/` holds
  the bytes, and the only route to them breaches the `Disallow: /`. One route remains and it is a
  letter to GSA, not a fetch
- one word here decides `fac_sfsac_historic_1998_2001` as well: that entry is the same corpus under a
  second class name, established 2026-08-27

- what it is: e-mail domains on Federal Audit Clearinghouse Single Audit filings, 1998-2001
- what dates one item: that row's own `AUDITEEDATESIGNED` or `CPADATESIGNED`, the date a human wrote
  the address down
- potential: 54
- what makes it worth it: **2,406.69 net-new equivalent-English, measured 2026-08-24.** 18,698 rows were
  dropped for falling outside the window, mostly FY2001 audits signed in 2002: taking the audit year
  instead would have imported all of them silently

- approved by Ivo on 2026-08-31, who downloaded the four ZIPs by hand because app.fac.gov
  refuses all robots; all four SHA1s verified. Banked post-split at 1,403.2 EE

Decision: master

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



