# Hypotheses pending

Open triage entries moved out of `approved-sources-list.md` on 2026-09-03 by `scripts/round/split_triage.py`, verbatim and in the order they had. Each is still pending, so `ark ingest` refuses it until a request is raised again. This page moves to the fleet repository; nothing in this repository reads it.

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
  `scripts/pricing/price_items.py --all-tlds` against the live store (merged260827), sampling DISTINCT DOMAINS and
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

### repository_ia_capture_census / cdx_timestamp

- what dates one item: a 14-digit capture timestamp per row, identical semantics to the approved source.
- potential: 70

Decision: pending
**Reopened 2026-09-01 on the unsubmitted parts 01 and 02, and on nothing else.** The rejection below
stands for what it tested and is left verbatim underneath. Three things it recorded are now known to
be wrong or retired, from the reviewer's own accept ledger rather than from a re-fetch:

- It rests on the NOVELTY screen, retired 2026-08-25, and it sampled PAIRS rather than distinct
  domains, which is the exact error CLAUDE.md names. 226,171 rows out of an 80.36 GB corpus.
- Killer 1 was invoked and does not hold for this artifact. Our baseline is homepage-level captures
  and this is the LINK GRAPH, whose column 2 holds targets never themselves captured.
- The reviewer ACCEPTED 4,068,061 records from parts 03-16 of this same deposit, submitted by
  another contributor on 2026-08-14, with 297 already in baseline. That is in
  `merge_audit_umn_drum_0814.json`, which names the submission directory outright:
  `UMN_DRUM_part03-16_..._0814`, baseline `merged260812`.
- The access note is wrong: `conservancy.umn.edu` 403s on `/handle/` behind a WAF JS challenge and
  answers `/server/api/` normally. robots.txt read whole, 3,502 B, no Claude or Anthropic group,
  `/server/api/` not mentioned. That is CLAUDE.md's own "a 403 wall is not always a refusal" trap.

- the untouched slice: `EARLYWEB_1996_2000_part01.tar` (418,764,800 B) and
  `EARLYWEB_1996_2000_part02.tar` (3,305,492,480 B) were never submitted by anybody. 3.72 GB of
  80.36 GB, 4.63% by bytes
- what would date one item: column 3 of a row is the crawl date `YYYYMMDD` written by the extraction
  script, per the deposit's own README.txt: `1 Source URL (only SLD) 2 Target URL 3 Date (YYYYMMDD)
  4 Sum of content length 5 # of links`. Column 1 with column 3 is `link_source` and is
  master-eligible. **Column 2 is `link_target` and never dates a year**, so roughly half of what the
  reviewer accepted from the other contributor is inadmissible here
- projected, not measured: ~103,000 EE gross pro-rata on bytes, halved to **~50,000 EE** for the
  source column alone. Order of magnitude only: part sizes run 138 MB to 9.19 GB, so the parts are
  not uniform and nothing has been fetched. The corpus is collected 1996-01-01 to 2000-12-31 and
  cannot serve 2001, which is where our headroom is

**Parked, not admitted, and the standing rule fails on two of its four conditions.** Condition 2:
nothing has been fetched, so no machine-written stamp has been quoted out of bytes we hold, and
there is no measurement at all, only a projection off another contributor's accepted record count.
Condition 3: the licence is **Attribution-NonCommercial-ShareAlike 3.0 US** and the NC term has
never been read against our use. Fetch part01 first, the cheapest of the sixteen at 418 MB, read
column 1 and column 3 only, and price with `scripts/pricing/price_items.py` sampling DISTINCT DOMAINS.

The rejection this reopens, kept as written:
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
  merged260827 (`scripts/pricing/price_items.py` reads 187 pairs and 117.0 EE; quote the lower). 1,522 distinct
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
  `scripts/pricing/price_items.py --all-tlds` against the live store and reproduced by the harvester to the
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
  `scripts/pricing/price_items.py --all-tlds` against the live store (merged260827), sampling DISTINCT
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
  pairs** from eleven pages (`scripts/pricing/price_items.py` re-read 159.4 EE over 252 pairs at harvest;
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
  priced 2026-08-28 with `scripts/pricing/price_items.py --all-tlds` against merged260827 over 19 dated pages,
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

### whatsnew_register_tree_capture / dated_directory

- measured: **235.0 net-new post-split EE over 399 (domain, 2001) pairs**, priced 2026-09-01 by
  `scripts/pricing/price_items.py --all-tlds` against the live store, sampling DISTINCT DOMAINS. One capture
  of the Nerd World "What's New" tree, `whatsnew.html` plus the 62 category pages `wn<N>.html` it
  links: 3,716 host mentions, 2,059 distinct registrable domains, 1,660 already held at 2001 (80.6%),
  399 held-or-corroborated and MISSING 2001 (19.4%). Mean weight 0.5889, all 399 at 2001, by TLD
  `com` 310, `net` 22, `org` 12, `de` 7, `au` 5, `uk` 4 and a low-weight tail. **Post-split and gross
  coincide at 235.0 here, and the split was applied rather than skipped**: 0 of the 2,059 names were
  new to the candidate pool, so every net-new name was already corroborated and the split cost
  nothing. 63 fetches in about 4 minutes, so 3.73 EE per fetch and roughly 3,300 EE/hour against the
  measured 255 EE/hour querying rate
- **the same tree at a 2000 capture pays ZERO, and this is the fourth reproduction of the
  2001-threshold law.** `20001207050300`, 39 of the 62 pages, 1,919 host mentions, 1,217 distinct
  domains, 1,217 of 1,217 already held AT 2000, net-new 0 pairs, 0.0 EE. Same host, same pages, same
  parser, same hour: 235.0 against 0.0, decided only by which year the capture stamps. squidGuard was
  10,736 EE at 2001 against 18 EE at 2000 on the same reading. Do not spend a request on any 1999 or
  2000 capture of this tree, they are measured at zero
- the artifact: `http://www.nerdworld.com/whatsnew.html` and the 62 `wn<N>.html` it links, fetched as
  `https://web.archive.org/web/20011030063818id_/`, 974,702 B over 62 pages. Also captured in window
  at 19990429, 7 dates in 2000, and 5 dates in 2001: 20010209, 20010413, 20010803, 20011030,
  20011224. The bytes were not kept, so an ingest would refetch from those URLs
- what dates one item: the crawler-stamped Wayback capture timestamp of the category page,
  `20011030063818`, fixing the instant the listing was served. The pages carry no in-body date of any
  kind, and a submission-queue listing is a directory stating what it had accepted when the crawler
  took the page. Same `dated_directory` grounds `page_directory` and `ncsa_whats_new` already run on
- **failed condition 2 of the standing rule of 2026-08-29**: what dates the item is the capture stamp
  rather than a machine-written stamp inside the artifact, the same reason `store_url_listing_pages`
  and `mailman_public_roster` sit in this section. **`coza_deletion_listing` and
  `cctld_register_listing_capture` rest on the identical reading and are `master`, and that is the
  argument FOR parking rather than against it**: both say "the Wayback capture stamp, since these
  editions carry no in-body date", and both carry "approved by Ivo on 2026-08-31" rather than a
  standing-rule line. A human ruled on them one at a time. The capture-stamp reading has therefore
  never once self-admitted, which is exactly what this row would do
- **the arm that PASSES condition 2 is worth nothing, and that is the finding worth keeping.** NU2 /
  What's New Too!, `https://web.archive.org/web/20000622033521id_/http://newtoo.com/`, 11,852 B, is
  the machine-generated submission queue itself and stamps every row from its own database,
  `<dd><i>21 Jun 2000</i>`, inside the artifact. One day page: 25 rows, 18 distinct domains, 18 of 18
  held AND 18 of 18 already carrying 2000, **0.0 EE**; 22 in-window captures at 25 rows each projects
  the whole run at 0 to 20 EE. It collapses to free-host parents (`angelfire.com`, `members.aol.com`,
  `topcities.com`, `profiles.yahoo.com`, `*.baweb.com`) that already carry every year we could date
  them to. **A submission feed dates its rows perfectly and its rows are the wrong population.**
  Closed, not parked
- **the discriminator inside the family is rows per fetch, not evidence quality**, and the method is
  the reusable part: fetch a directory's what's-new TREE at one capture timestamp, not its front page.
  The front page is 5 to 25 rows and is the editorially chosen head; the category pages one level down
  are 40 to 190 rows each and are the submission queue. It costs no CDX at all, since the index page
  enumerates the tree by href
- this reopens nothing that was closed. `docs/sources.md:756` closed award galleries and
  pick-of-the-day archives at 3.5 EE on the current 2001 screen, and its own last line deferred "the
  REGISTER variant rather than the pick variant, a 1999-2001 successor to NCSA What's New listing all
  newly launched sites". That is what was measured here, at 67x the pick variant per capture.
  `ncsa_whats_new` is banked for 1996 only and does not reach 1999-2001
- **Yahoo is measured and closed as not retrievable**: the surviving `www.yahoo.com/new/` index is the
  Daily Picks page, 4 non-Yahoo external domains at 20010504032229 and 22 hosts at 19970110014756. The
  real register exists and IA never crawled it. The 1997 index links `www.yahoo.com/new/970602/`
  annotated "1042" new sites for one day and the 2001 index links
  `dir.yahoo.com/new_additions/20010122/`, and the daily pages have 0 mementos under every form
  probed. Same failure as the dmoz RDF dumps. Dead on probe, 0 mementos: `newtoo.manifest.com`,
  `www.whatsnew.com`, `home.netscape.com/home/whats-new.html`, `www.galaxy.com/info/new.html`,
  `www.stpt.com/whatsnew.html`, `www.linkstar.com`, `www.bizweb.com`, `www.ukdirectory.com/whatsnew.htm`
- ceiling, so nobody scopes this as a project: the honest projection is 5 in-window 2001 captures
  times rotation, **250 to 350 EE for Nerd World**, and a few thousand EE for the whole family. The
  untested part is the other second-tier directories that still had a category-level what's new in
  2001, LookSmart, NBCi and Snap, none of them probed
- ingest specs: not written
- potential: 30. Drivers: the highest EE per fetch this round at 3.73, 13x the querying rate, on a
  method that needs no CDX and no store lock. Held down by the condition-2 failure and by a family
  ceiling of a few thousand EE, not tens of thousands

Decision: pending

**Held under the standing rule of 2026-08-29, on condition 2.** Condition 1 holds: `dated_directory`
is master-eligible and no new class is proposed. Condition 2 fails: the Nerd World category pages
carry no internal date, so the whole 235.0 EE rests on a Wayback capture stamp, which is machine
written but is not inside the artifact. No standing-rule admission rests on it: the one that
looks closest, `nypw_timemaps`, is `cdx_timestamp` on a stamp that is genuinely INSIDE the bytes,
field 3 of a TimeMap row, `20010124104200`, and the Nerd World HTML carries no date of any kind. So
admitting this row would settle the class by the back door, which is what "this moves the gate, it
does not lower it" forbids. Condition 3 was not
established for the origin host and only `web.archive.org` was ever requested. Condition 4 was never
reached: nothing was ingested and the bytes were not kept.

**The cheapest thing Ivo can do here is rule on the capture-stamp class once**, since it now gates
`store_url_listing_pages`, `mailman_public_roster` and this row together. If it is ruled master, this
one follows on the same reading and costs one line and 63 refetches.

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

### whois_server_and_tld_tables / artifact_listing

- measured: **9.7 net-new post-split EE over 22 (domain, 2001) pairs**, priced 2026-09-01 with
  `--all-tlds` against the live store. The whole in-window family was read, not sampled: four
  discmaster filename censuses (`whois.conf`, `whois-servers`, `tld_serv_list`, `whois.txt`) put the
  population at about 20 files and the 14 carrying text were fetched outright. 470 distinct
  registrable domains, 463 held (98.5%), held and missing 2001 24; 880 pairs over 468 domains, 849
  already held. Gross before the split is 31 pairs / 15.6 EE and must not be quoted. Mean weight of
  the net-new 0.4396, TLDs `cf`, `by`, `uz`, `mg`, `af`, `ci` and siblings. Per-year held over the
  470: 1996 310, 1997 370, 1998 409, 1999 439, 2000 455, 2001 439
- the artifact: `https://discmaster.textfiles.com/search?q={whois.conf,whois-servers,tld_serv_list,whois.txt}&qfields=name&mode=deep&tsMin=19960101&tsMax=20011231&limit=1000&dedup=1`,
  then 15 `/view/` fetches at 1.4 s spacing. Largest: `whois-servers.list` 2000-03-09 28,011 B and
  1997-12-01 22,720 B, `whois-servers.gopher-links` 23,858 B and 16,998 B, `whois-servers.dat`
  2001-06-27 18,454 B, `tld_serv_list` 2001-05-04 11,156 B and 2001-01-16 10,924 B, `jwhois.conf`
  2000-08-15 7,118 B, `Whois.conf` 1998-06-11 4,568 B, four `xwhois.servers` 253 to 1,558 B
- what dates one item: the per-file media mtime that discmaster records for the file inside the
  CD-ROM or disk image, as rendered in its listing row. This is the same dating argument as
  `antispam_media_blocklist` and `discmaster_media_index` above
- the typo bound, which the finding raised itself: **23 of 29 sampled net-new names (79.3%) are one
  edit from a name already held**, which is what a hand-copied config tail looks like when
  `whois.nic.cf` sits beside a held `whois.nic.cd`. So 9.7 EE is an upper bound and the true figure
  could be materially lower
- why the family is finished whatever is decided here: **a registry-host table is an INDEX of
  registries and its row count is bounded by the number of TLDs, about 250, forever.** 250 rows x
  0.6 mean weight x the best imaginable missing-year fraction is a few hundred EE at absolute
  maximum. Do not re-census `whois.conf`, `whois-servers`, `tld_serv_list` or `xwhois.servers` on
  discmaster: the in-window population is about 20 files and 14 have now been read in full
- ingest specs: not written
- potential: 3

Decision: pending

**Held under the standing rule of 2026-08-29, on condition 2, which is the one it fails.** The rule
admits a source without asking only when what dates one item is a machine-written stamp INSIDE the
artifact. A media filesystem mtime is not inside the file's bytes; it is metadata on the image,
transcribed by a third-party index. That is a real difference from every stamp the approved lanes
rest on: untroubled's qmail maildir filename epoch written by the receiving MTA, chastity's tar
member header, JPNIC's own `Registered Domains in JP (Apr 30 1999)` line. All three are the
producing machine writing into the object it produced.

**And the register shows this exact argument twice left open by the human gate**, at
`antispam_media_blocklist` (1,055.3 EE, pending) and `discmaster_media_index` (pending). None of the
50 master rows rests on a discmaster media mtime. Admitting a 9.7 EE row on that argument would
settle by the back door a class a 1,055 EE row is still waiting on, which is what "this moves the
gate, it does not lower it" forbids. So the correct move is to park it and let the larger row decide
the class first: if `antispam_media_blocklist` is ever ruled master, this one follows on the same
reading and costs one line.

Condition 1 holds: `artifact_listing` is master-eligible and no new class is proposed. Condition 3 is
marginal rather than clean: discmaster's robots.txt is `User-agent: * / Disallow: /` with a prose
carve-out for researchers making limited, targeted requests, and 19 requests plausibly sits inside
it, but a prose exemption read favourably is not the same as terms that plainly permit. Condition 4
was never reached, and the bytes were not kept, so an ingest would need the refetch above.
