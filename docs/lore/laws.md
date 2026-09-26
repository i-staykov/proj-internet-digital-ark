# Laws

Measured facts, one per line, each with its figure and its pointer. He and his mean the reviewer.
The rules these facts support live in CLAUDE.md; `just find <term>` opens a register row.

## Evidence

- XIII passes 9.3% of round 10's net-new registrables (32,228 of 346,389, 30,343 by CDX) and 75.2% of hostnames (2,674,952 of 3,554,784, 2,509,555 by sweep); `src/ark/evidence_types.py` `WEB_METHODS`.
- A Wayback capture of a zone file dates the delegation, not a site: 255,211 of round 10's registrable failures are DK Hostmaster's; `tests/test_xiii_web_evidence.py`.
- Only `MASTER_TYPES` (six types) may back a year, and `link_target` never does (`src/ark/evidence_types.py`).
- The claim takes only `WEB_METHODS`, an allowlist where an unknown method fails closed into candidates (`src/ark/evidence_types.py`).
- A capture whose evidence reads status 4xx or 5xx stays a candidate whatever its method; `nypw_timemap_non_200` is the one method admitted by status, its 3xx rows only, since a wildcard vhost answers 404 for any name (`REDIRECT_METHOD`, `ERROR_STATUS`).
- Of 1,800 ISC hostname-years he audited, 48 (2.67%) had an exact-host CDX record anywhere in 1996 to 2013, against 22.1% for one Apache list-month's `by` hosts and 84.2% for his own `www.` names; `just find isc_survey_hostnames`.
- By that 2.67%, at most about 483,000 of our 18,087,127 ISC hosts could ever carry web evidence, and promotion still needs the target year; `just find isc_survey_hostnames`.
- ISC hosts ship in `<year>-ISC.txt` and `candidate_additions.txt` (`src/ark/export.py` `export_isc_provenance`).
- Export fails unless each ISC host has an `isc_survey_provenance.csv` row naming edition, file, URL, location, method and a target year matching the edition (`export_isc_provenance`).
- 1.419% of the ISC survey's 13,347,250 hosts are in his files; `just find isc_survey_hostnames`.
- Hosts with only non-web evidence ship in `server_header_hostnames/` with provenance and exclusion ledger: 39,812 names, 30,384 EE (`src/ark/export.py` `export_header_candidates`).
- A registrable with no web-method year and no baseline row enters the candidate claim; 189,251 `.dk` zone list names ship there (`src/ark/export.py` `candidate_pool`).
- A self-dating record (capture stamp, registry creation date, dated listing) takes no corroboration split: `just price --no-split`.
- Only a name recovered from free text takes the corroboration split, counting once another source dates that domain; on a delimited field it costs 1.3x to 5.5x, 255,254 to 56,707 DK zone list pairs (`scripts/pricing/price_items.py`, `src/ark/sources.py`).
- The split, not the regex, is the wall on a human-typed corpus; a self-dating corpus takes no split, so its regex is its only screen (`scripts/harness/screen_hypothesis.py` `DATING`).
- The split tests dating, never genuineness: 13 of 25 hand-audited post-split survivors from three scholarly corpora were genuine (52%); `just find pmc_oa_subset_fulltext_1998_2001`.
- Of those 25: 2 invented placeholders (`foo.edu`), 3 transcription artefacts (`ich.edu` from `umich.edu`), 7 modern retrofits (`creativecommons.org` five times); `just find pmc_oa_subset_fulltext_1998_2001`.
- 53.1% of audited survivors' EE was junk, most in `.edu` (weight 0.9717), so junk inflates figures; `just find pmc_oa_subset_fulltext_1998_2001`.
- Stripping boilerplate removes a modern retrofit; nothing removes an invented placeholder; `just find pmc_oa_subset_fulltext_1998_2001`.
- A per-entity date does not date its fields: NSF `piEmail` is the last-edit address, `gmail.com` is on 61 awards of 1996 to 2001, and 42 of 58 audited survivors were registered later; `just find piEmail`.
- MARC 856: a record entered in 1998 may have gained its URL field in 2005, so the record date does not date the link; `just find 856`.
- An intent-to-use trademark filing evidences an intention; only a use-in-commerce filing with a dated specimen shows a live site; `just find trademark`.
- OpenPGP key creation dates the keypair, not the UID: of 4,225 Debian binding signatures, 47.6% bound the UID later, median two years, 0% earlier; `just find OpenPGP`.
- A date dates the container, not the item, when republishing the source tomorrow would change it (`src/ark/sources.py` `_ZONE_SERIAL`).
- Surviving fake hosts are typos of real ones (`mmembers.aol.com`, `home.mci20000.com`): no word list catches them, only a hand-judged sample rates them; `just find mmembers`.
- Any name-shape filter over-catches: `bl.uk` is the British Library and `x.com` is real, so `src/ark/hostnames.py` `_VALID_HOST` tests structure only.
- Munged addresses extract as hosts (`nospam.bigfoot.com`, `bigfoot.com.invalid`), more in his `prior_task` than ours; `just find nospam`.
- A munged host found by two extractors is one artifact twice, not corroboration; `just find nospam`.
- A dotted-token regex prices the transport: rtfm priced 20,049.42 EE by token and 3,719.91 EE by http, https and ftp URLs, an 81.45% error; `just find rtfm`.
- Usenet body URLs are candidates, a textual mention: explicit http, https and ftp body URLs dated by the post's `Date:`, fiction 6.25%, Wilson 2.7% to 13.8% (`src/ark/hostnames.py`).
- A mail `Received: ... by <host>` clause dates that host as a candidate; the `from` HELO, reverse-DNS and `Message-ID` hosts are not read (`src/ark/hostnames.py` `APACHE_METHOD`).
- A UKWA link-graph target is annual only when it is its own registrable (`ukwa_link_target_bare`); `www.` targets (77%) and deeper ones stay candidate `link_target` (`src/ark/sources.py`).
- `afnic_fr` is the one span source: AFNIC's guide v3.0 defines `crDate` as the last creation date, so `[crDate, deletion or now]` is continuous (`src/ark/checks.py` `_SPAN_SOURCES`).
- The `www.` alias share of hostname EE: bulk CDX indexes run 99.5% to 100% `www.<held name>` (`ukwa` geoindex, `nypw_firstcdx`), typed-URL corpora 27.3% to 33.8% (`just price-hosts`).
- `www.<registrable>` is its own hostname record where evidence names that exact host (`a_www_record_has_its_own_evidence`); 1,221,065 of his names carry both forms in one year.
- His merge kept all 1,313,547 `www.` names of one round, 1,106,188 beside the bare name in the same year, and credited it 7.562846%, so the alias ships (`src/ark/export.py` `NOT_WWW_ALIAS`).
- Neither `www.` nor the bare name evidences the other: a bare record resting only on `www.` evidence is refused, 47,004 domain-years (`a_bare_record_is_not_inferred_from_www`).
- A 3xx filter adds 2.4% more CDX rows; dropping the status filter adds another 3.3%, all 4xx and 5xx: the server answered, the host served nothing (`scripts/engines/cdx_suffix_sweep.py`).
- A replay status is not the page: a 200 can be a period IIS 404, and a 301 an acquisition redirect onto a live 404 (FTP Search); `just find ftp_index_server_inventories`.

## Scoring

- Both tracks score S = 10 x (p / t) on the same annual EE denominator, so a candidate point costs an annual point: 1,702,122.4578 / 27,740,079.6441 = 6.135968% (`scripts/round/round_figures.py`).
- A candidate is a name with no web-evidence year; malformed but recoverable strings go to normalization review (`scripts/round/unparsed_pool.py`).
- The candidate claim is our pool minus his `candidate_pool.txt` and annual files: 2,279,755 registrables left 29,327, 78x fewer (`src/ark/export.py`).
- Export diffs every shipped list against his six annual files as released, since an ingested copy lags: 303 held names in one 2001 file (`src/ark/export.py` `load_his_annual_files`).
- His releases purge: merged260922 dropped 22,666,119 names from `candidate_pool.txt`, so a pure diff re-offered 12,870,758 he had just removed (98.2%) and our claim jumped from 261,977 to 13,104,122 (`src/ark/export.py`).
- A screen left off one query ships what it refuses: 251,178 rows in `masters/2001.txt` (`src/ark/evidence_types.py`).
- Export, stats and contribution share one web-evidence screen, `web_evidence_sql` (`src/ark/evidence_types.py`).
- What ships is counted with `ark.delegation.shipping_filter`: a store count without it read 17,638 pairs against 16,772 shipped (866 pairs, 479.4256 EE) (`src/ark/stats.py`).
- t counts whole days from the task assignment and never resets, so a week's delay costs 7/(t+7) of the score: round 8 scores 10 x 18.769714 / 33 = 5.687792 (`src/ark/figures.py` `t_days_assignment`).
- The benchmark clock, release stamp to receipt rounded up to whole days, reproduces rounds 6 and 7 at 6.884530 and 6.302372; from midnight it misses (`src/ark/figures.py` `t_days`, `docs/registers/rounds.md`).
- A (name, year) scores its TLD's English share, e.g. .uk 0.9813, .edu 0.9717, .com 0.6321, .net 0.4530, .de 0.1324; a TLD absent from the table scores 0 (`src/ark/english_share.py`).
- Hostnames are annual records at full TLD weight, shipped in `NNNN_hostnames.txt`: the 180 suffix journals priced 0 at registrable grain and 338,865 net-new hostname records, 301,650 EE, at hostname grain (`src/ark/export.py`).
- Round figures sum both units, registrables and hostnames at full weight; `ee_netnew` alone is the registrable half (`scripts/round/build_round_state.py`, `scripts/round/fill_report.py`).
- `www.<parent>` records are accepted at hostname grain: round 8, its hostname half 95.0% that alias, is credited 18.769714% (`data/baseline.json`).
- A round records his accepted figures, never what was sent (`data/baseline.json`, read by `ark.baseline` `SUBMITTED_ROUNDS`).

## Pricing

- Several unverified numbers, a subagent's among them, were fabricated or out by 1000x.
- A verifier re-running the same code reproduced to the digit a Usenet figure whose `^From` boundary missed 50.019% of posts (`scripts/sources/usenet/build_usenet_pool.py` `BOUNDARY`).
- A worse reimplementation of an existing tool overstated a source 20x (`scripts/engines/build_promotion_journals.py`).
- Net-new post-split EE and gross differ by more than 10x (`scripts/pricing/price_items.py` prints both).
- Filing floor, net-new post-split EE: 5,000 for a new master-eligible class or a candidate-only lead, 1,000 for an approved class at a new grain whose items date the host; nothing below is filed (`sync_approvals.py` `DEFAULT_FLOOR`, ark-fleet `prompts/scout.md`).
- `price_items.py` prints the net-new part's mean weight, calling 0.6 good and under 0.4 the floor, below which only volume carries a source.
- If one sentence cannot say what dates one item, the source is seed-only: `just screen` exits 2 without `--dating self|typed|undated`.
- An already ingested journal prices at 0 net-new by construction, since net-new is pairs minus held pairs (`scripts/pricing/price_items.py`).
- The yield check measures a rate over the newest 3 journals against the collector's own history, never a lifetime or across a backfill, and calls a fall below 0.25 of it a collapse (`src/ark/yield_check.py` `RECENT_FILES`, `COLLAPSE_FRACTION`).
- A closed verdict holds only for its artifact, partition and grain: `nypw_timemaps` paid 14.2 EE on 1996, 87,905 EE on 1999 and 2000, 6 rows on 2001 (`ark ingest` year_rows per file).
- A corroboration partner cut after our own collector ran validates nothing: one Usenet parse priced 22,838 EE on a baseline cut after that collector, 252 on merged260810 (91x); `just find usenet_body_url_hostnames`.
- Two corpora of one class priced apart and added double counted 12,387 shared keys that their union counts once; `just find usenet_body_url_hostnames`.
- The jeb_bush_anchored union priced 5,999.2714 EE over 8,000 host-years; its url_body lane alone, the one that may ship, 322.4322 EE over 479 (18.6x), 94.6% mailboxes; `just find jeb_bush`.
- One mail corpus was 55.1% held at hostname grain and 94.6% at registrable grain; `just find maillist_body_url_hostnames`.
- Grain decides yield: thirteen Usenet pools read whole paid 35.8 EE at registrable grain and 119,640 EE at hostname grain, net of the 6.25% fiction rate; `just find usenet_body_url_hostnames`.
- A projection counting registrables against raw hostname lines put the NYPW index at 27,276 net-new domains; it measured 53; `just find NYPW`.
- The IOS Counter's `r.9904.*.txt` look like aggregate tables for 25 lines and carry 16 hostnames from line 27; `just find OCLC`.
- A target set recomputed live scored 24.2% where a fixed snapshot of the same 200 answers scored 59.7% (`src/ark/price_snapshot.py`).
- `ark price-snapshot` exits 2 when its snapshot disagrees with its manifest (`src/ark/price_snapshot.py`).
- A conditional rate taken off 725 journals, a proxy population, overstated the edge-year pilot 1.6x (`just price` prices a sample of the real items).
- A share-first ranking spent 1,709 CDX queries on .edu, 97.2% English, for 5 hits (`scripts/engines/build_expand_seeds.py`).
- `scripts/engines/build_expand_seeds.py` scores a seed by TLD weight x years held, capped at 3.
- Sweep order confounds rank against yield: on the platform-parent ranking, 198 swept parents gave rho +0.746 and 54 fresh ones rho -0.655; `just find ia_cdx_hostnames`.
- A re-ranked queue's dense head is about 20 parents: 8 to 17 MB of compressed rows at the head, 0.2 to 2 MB by rank 50; two clients walk it in an hour; `just find ia_cdx_hostnames`.
- EE per byte from a best-first head overstates the rest: 565 then 53 EE/MB (10.7x) on the domain-wide sweep, 722 then 134 EE/GB (5.4x) on Usenet alt; `just find usenet_alt`.
- A head-of-corpus projection is a lower bound: mailing lists closed at 186 EE on 7.63% of files, then paid 589.0482 EE read whole; `just find maillist_body_url_hostnames`.
- A 0.58% sample of a self-repeating corpus projected 1.9M EE against a true 62,821: a sample proves the shape, never the total (`scripts/pricing/price_items.py`).
- A held-set export goes stale at the next ingest: a header projection of 10,889 EE delivered 1,038.4 after another ingest wrote 102,577 overlapping pairs (`scripts/pricing/price_items.py`).
- Every six- and seven-figure EE in the registers is a whole-corpus read; per-shape medians run 2.1 to 590.3 EE with 43x to 800,396x spreads, so shape sets no floor (`docs/registers/sources.md`).
- `probes/udrp_selftest.toml` reproduces the 186-line UDRP collector's 8,923 records exactly, so a probe's yield holds before any collector exists (`scripts/pricing/probe_source.py`).
- Dated prose yields about 0.042 net-new post-split pairs per item (RFC 0.0416, 140 over 3,367; D-Lib 0.0420, 16 over 381): about 238,000 items per 10,000 pairs; `just find D-Lib`.
- Density follows subject: grant records held 456,700 dated in-window items (NIH, NSF, CORDIS), 1.9x the 238,000 items the ceiling needs, and still died; `just find CORDIS`.
- Pairs per item: NSF CSE 0.0471, NSF BIO 0.0152, NSF GEO and TIP 0.0000, NIH 0.0012 (164 distinct hostnames in 372,444 abstracts, 35x below the ceiling); `just find NSF`.
- The held-and-missing screen: an artifact pays only for the years it adds, so an IRR dump 97.6% held paid 4.44 EE because 95.2% were held in that very year (`price_items.py`; `just find long-running-series`).
- Headroom is held Y-1, missing Y: a later gap is death, and 6,948 of 9,680 `.us` names missing 2001 were last seen July 1997; `just find locality`.
- Headroom sits at 2001: 6,708,320 domains held at 2000 lack 2001, against 103,953 held at 1996 lacking 1997, a 64x gap; `just find threshold`.
- P(store lacks 2001 | held), per distinct domain: `com` 0.611, `net` 0.653, `org` 0.568, `uk` 0.309, `de` 0.841; `just find threshold`.
- Counted per `domain_year` row instead of per distinct domain, that `com` figure reads 0.492; `just find threshold`.
- A held name in a 2001-dated artifact is worth 0.386 EE in `com`, so 1,000 EE needs about 2,600 held `com` names (2,477 `org`, 2,484 `au`, 3,298 `uk`); `just find threshold`.
- A head-selected corpus pays about a ninth of that: a 2001 magazine archive paid 0.041 EE per name, about 24,000 names per 1,000 EE, since it cites names already held; `just find threshold`.
- P(lacks 1999, 2000, 2001 | held), against merged260827: com 0.644 0.340 0.639; net 0.769 0.531 0.765; org 0.715 0.470 0.691; uk 0.769 0.454 0.382; de 0.457 0.259 0.866; au 0.637 0.399 0.502; ca 0.630 0.491 0.606 (`src/ark/english_share.py` weighs each).
- A 1999-dated artifact is worth at least a 2001 one per held name in every TLD but `.de` (`.uk` 2.01x, 0.7546 against 0.3749 EE); headroom still uses the adjacent year (`src/ark/english_share.py`).
- Public direct `.uk` registration opened in 2014, so a queued direct `.uk` name has no 2001 capture: 150 asks returned 0 hits; `just find Nominet`.
- An ingested corpus whose names show P(store lacks Y given attested) under about 0.05, against `com` at 0.611, pays for no new extraction signature (`scripts/sources/usenet/`).
- Usenet spool census (456.82 GB, 178,700,605 messages): P(store lacks Y given named) is 0.0051 to 0.0151 in each window year; 682 of 45,147 at 2001 (`scripts/sources/usenet/`).
- 65,101 host-dense recurring Usenet posting families, priced as a union: 2,207 net-new post-split pairs, 780.1 EE at mean weight 0.3535; 62.7% one edit from a held name (`scripts/sources/usenet/`).
- No extraction over that spool can beat 780 EE: none of its 65,101 families reaches 10,000 distinct in-window domains (`scripts/sources/usenet/`).
- The typo bound in `price_items.py` counts a name one edit from a held one as junk, which on a typosquat source is the signal: UDRP dockets, 5,306 proceedings, 8,800 pairs, 87.7% net-new (`scripts/pricing/price_items.py`).
- 12.8% of qualifying Usenet rows were the same post, by `Message-ID`, in a second group's archive (`scripts/sources/usenet/build_usenet_pool.py`).

## Sources

- An IA re-serving corpus adds years and hosts but no registrables against the IA-derived baseline: 14 of 652,853, 0.002%; `just find WebBase`.
- Whether a corpus re-serves IA data shows in its description before any fetch; `just find WebBase`.
- A bulk IA holdings projection (`dartmouth_nber_captures`) is the exception that adds registrables; `just find dartmouth_nber_captures`.
- TREC web, Stanford WebBase and Early Web CDX descend from the baseline's 1996 to 1997 crawls; the two measured gave 0.01% net-new each; `just find trec`.
- The public IA bulk indexes we know are read (Dartmouth ARCS, the node CDX, UKWA); the 2,223 in-window Alexa and Inktomi deposits' CDX files are `private=true` and answer 401; `just find archiveorg_in_window_web_items_alexa_inktomi`.
- Our IA coverage is bound by our query rate, not IA's holdings: 239,631 domains ever asked at CDX against 2.5M in the pool, at about 713 requests an hour (`src/ark/cdx.py`).
- The UK Web Archive host link graph is IA data and ran 90.4% net-new against 46.0% pool-wide: a link graph names hosts CDX does not return as captures; `just find ukwa`.
- Listing a name proves the artifact's date, not liveness (Netcraft, JANET); `just find Netcraft`.
- A request-count filter fails on a period sum: a host asked twice clears it; `just find Netcraft`.
- A trust-selected corpus holds authorities: 7.1M Usenet `Path:` hops were 4,736 domains; 126 in-window certificates held 17 hosts, all CA domains; `just find X.509`.
- Held share decides before download: blocklists about 50%, authority corpora 87% to 99%, visitor logs 98.4% to 99.6%, remailer logs 4.56% of 23,102; `just find remailer`.
- A fetch endpoint list sits at 95% held at the artifact's own year, and Debian `watch`, Gentoo `SRC_URI`, CPAN and CTAN mirror lists share that shape; `just find ports-tree`.
- A build recipe names its fetch host, an authority head: 22 dated BSD ports checkouts named 4,044 third-party domains, 94.91% held at 2001, for 40.8 net-new post-split EE; `just find ports-tree`.
- Newswire names a site once its company is famous: 8,010 in-window Reuters, UPI and Newsbytes stories gave 305 pairs, all held; 4.79% named any domain; `just find Reuters`.
- Prose faces two independent screens: Hansard has 0.00153 URLs per 1,000 words, ERIC 0.339 (221x) yet 93.0% held, 1 of 184 `.edu` pairs surviving; `just find ERIC`.
- Anonymised traces are worth 0: UC Berkeley Home IP 1996 hashes 9,244,728 request URLs, SNAP graphs number nodes, and each sanitisation note says so; `just find lbl.gov`.
- Dating and URL-bearing anticorrelate: LC books date 28.25% of records and hold 67 hosts in 72,588; LC serials hold 3,492 and date 0.34%; `just find 856`.
- Net-new share follows how briefly and quietly a name lived: UDRP dockets 87.7%, a spam archive 33%, `net-happenings` 2%; `just find udrp_wipo`.
- A name that traded for months was captured whatever advertised it: two thirds of spam-advertised domains were held; a typosquat died before a crawler came; `just find spam`.
- Short life plus low traffic pays: disputes, seizures and abandoned registrations do; a dot-com deadpool does not, its startups captured many times before folding; `just find deadpool`.
- Lifetime is a ranking prior, never a rejection: `attrition_defacement` domains hold 3.04 years against a store mean of 1.74 and still pay; `just find attrition_defacement`.
- A source made to publicise holds nothing unknown: `net-happenings` gave 182,081 rows over 165,365 domains, 97.8% dated, and 2,760 net-new pairs worth 1,819.7 EE (`scripts/pricing/price_items.py`).
- A roster, one organisation per row with a homepage URL, prices at 0.0069 to 0.1097 net-new post-split EE per listed domain, over 37 artifacts of twelve kinds; `just find roster`.
- At a median 0.05 EE per listed domain, 1,000 EE needs about 20,000 listed domains in one artifact; the largest in-window roster found, COMDEX Fall 2001, has 1,550 rows; `just find COMDEX`.
- Every five-figure source is a machine's dated observation of a name (registry event, crawl fetch), never one organisation per row; `just find roster`.
- A high fill rate does not rescue a bad unit: rosters passing the held-and-missing-2001 screen at 100% still died on 41 pairs; `just find roster`.
- An archived GET lookup form leaves one in-window capture per endpoint, the bare CGI with no records (5 hosts); its parameters were crawled from about 2004. POST is dead; `just find new_net_thirdlevel_hosts_2001`.
- A census keyed on an IP address emits no names however large or well dated: the IOS Counter's 1,465,124 hosts and RIPE's 4,965,839 `.de` hosts gave 0; 54 artifacts, 2.1 EE; `just find OCLC`.
- Breadth pays and depth does not: 13 Usenet hierarchies read once union to 127,616 of 158,841 EE, while more `alt.*` was 90.5% held at 40 EE per GB; `just find usenet_alt`.
- 42.1% of `alt.*` messages fall in 1996 to 2001, and the share ignores size: 0.0% to 85.2% at 70 to 155 MB; `just find usenet_alt`.
- Ordering a Usenet fetch by in-window share about doubles EE per GB; `scripts/sources/usenet/fetch_usenet_hierarchies.sh` orders largest first within a hierarchy instead.
- Mail-archive cost is `crawl-delay`, not bandwidth: `mail.gnome.org` read 1,415 files in 562 s, `mail.python.org` at `crawl-delay: 2` 1,207 in 2,400 s; `just find crawl-delay`.
- Dartmouth ARCS per-item CDX, 25 in-window items: 20.6 EE per MB gzip, 1,363 to 29,078 EE an item, 60% to 98% `www.` of a held parent; `just find dartmouth_arcs_cdx_hostnames`.
- The one public node CDX, `host_cdx_ia600702` (57.6 GB gzip), read whole: 931,864 host-years, 88% held, 104,347 records, 50,722 EE, 0.9 EE per MB; `just find host_cdx_ia600702`.
- Ingesting `host_cdx_ia600702` needs a 28 GB DuckDB memory limit, `ARK_DB_MEMORY_LIMIT` in `local.env` (`src/ark/db.py`).
- Arquivo.pt `IA.cdxj` (50,930,113,941 bytes) is a hostname-grain custodian extract, fetched in parallel ranges in about 25 minutes (`scripts/sources/arquivo/fetch_ia_cdxj.sh`).
- Arquivo.pt's robots.txt disallows `/wayback`, `/cdxj`, `/services` and `/datasets` for `User-agent: *`, so `IA.cdxj` is no CDX substitute; `just find IA.cdxj`.
- Nominet's RDAP terms forbid extracting or re-using any part of the database, so `.uk` RDAP journals sit in `rdap_hold_uk`, where no ingest reaches (`scripts/harness/audit_residual.py`).
- lists.apache.org honours only `d=YYYY-MM`: a ten-day 2001 range answers 200 with 15,001 newest-month messages, `d=1999` a 13-message stub, and the echoed `searchParams` repeat the range it ignored (`scripts/sources/mail_corpora/collect_apache_lists.py`).
- lists.apache.org `stats.lua list=*` caps silently at 15,001 messages a month from 2000-07 and drops quiet lists, a largest value that repeats; per-list `active_months` is exact (`collect_apache_lists.py --expand`).
- archive.org `services/search/v1/scrape` lies under load: 6 items for five collections, total=28330 for five queries, six false zeros in one batch (`scripts/harness/dataset_discovery.py` asks `advancedsearch.php`).
- archive.org `services/search/v1/scrape` rejects `count<100` (`scripts/harness/dataset_discovery.py`).
- One request clears an FTP host: its `ls-lR.gz` or `locatedb.gz` grepped offline, where `ftp.gwdg.de`'s 926 MB locatedb indexes an 8.8 GB tree; `just find locatedb`.
- A size floor passes a wrong artifact: a replay URL missing the slash in `id_/` served seven objects as one 154,263-byte interstitial, and a floor at half the expected bytes passed all seven (`scripts/harness/fetch.py` prints each object's bytes and sha256).

## Channel

- A running collector is not a working one: a queue led by 2,675 `.mil` names ran 1,200 queries for zero in-window captures while every mechanical check was clean, so `just cycle` checks yield (`src/ark/yield_check.py`).
- Hit rate, not query rate, tells queues apart: one returned nothing on 1,114 of 1,200 queries while another in the same hour gave 1,647 years per 1,200, 45x apart (`src/ark/yield_check.py`).
- Journal bytes, rows and peaks are not rates: a journal is a file and only a distinct net-new (host, year) is a record, and a stopwatch on journals per minute parked `columbia.edu` at 885,968 capture rows (`src/ark/yield_check.py`).
- An archive client is its open journal, not its process: a `uv run` wrapper plus its python child doubles a process count (`scripts/harness/collectors.sh` `local_clients()`).
- More CDX workers never raised throughput: 4 lost the archive, a bigger server was no faster, 3 ran slower than 2 (`src/ark/cdx.py`).
- CDX seconds per query (1,179 journals): by_host 2.78 to 4.93, scan 3.65 to 7.58, by_root 11.84 to 46.00, 32.9% of seconds for 15.3% of years (`src/ark/cdx.py`).
- A CDX page costs about the same at any size (200 blocks 11 to 42 s, 10,000 blocks 110 s), so sweeps page at 10,000 and ask `showNumPages` first (`scripts/engines/cdx_suffix_sweep.py`).
- `matchType=domain` on a public suffix returns its names in disjoint pages (`co.uk` is 3,387,186 blocks, 339 requests); a bare TLD answers 403, so `.com` cannot be walked (`scripts/engines/cdx_suffix_sweep.py`).
- Page 0 of a CDX namespace is about twice as dense as the whole, so a page 0 projection is an upper bound (`scripts/engines/cdx_suffix_sweep.py`).
- A page-number walk that skips a failed page still ends `.done`: five of 31 platform walks stopped short, so the walker asks `showResumeKey` until the index twice says no more (`scripts/engines/cdx_platform_walk.py`).
- `collapse=timestamp:4` on a domain walk folds a host into its SURT neighbour in the same year, at least 56.7% of `cjb.net` host-years, so the walker keeps one row per (host, year) itself (`cdx_platform_walk.py`).
- One `matchType=domain` answer names thousands of hosts: 14,256,371 capture rows in 75 minutes gave 774,767 net-new records, 482,567.9442 EE; `just find ia_cdx_hostnames`.
- Distinct hosts per capture row, not TLD weight, set a sweep page's worth: `co.uk`, first at weight 0.9813, paid 16.0 EE per 1,000 rows at 61.5 rows a host against 657.2 at 1.5 (42x); one index page measures it, and above about 20 most requests re-read named hosts; `just find ia_cdx_hostnames`.
- The domain-wide sweep's rate decays: 193,000 EE per client-hour on its dense head, 210 an hour for two clients once walked; `just find ia_cdx_hostnames`.
- The CDX API takes the regex filter `statuscode:[23][0-9][0-9]`; a multi-clause negated filter returns HTTP 400 (`scripts/engines/cdx_suffix_sweep.py`).
- `archive.org/wayback/available` can answer 429, `x-rl: 0`, no `Retry-After`, with none of our clients running while CDX answers normally; the block is per service and per IP (8 of 8 answered from the VPS while the laptop sat at 429); `just find availability`.
- A throttle recorded as "no capture" spends a queue entry and learns nothing: the availability queue build recorded 429s that way; `just find availability`.
- TimeMaps (`/web/timemap/link/<url>`) answer through the availability block and list every memento with its datetime; `just find ftp_index_server_inventories`.
- A Wayback `id_` replay URL can answer 200 with no redirect and serve a 2020 capture: its `Memento-Datetime` dates it, not the requested stamp (`scripts/harness/fetch.py` fetches `id_` replays).
- A rate limit can be a quota: Verisign RDAP served 64,568 queries at 65 q/s for 17 minutes, then about 1 q/s through three restarts, and three queue orderings compared inside that clamp all read catastrophic; only rest clears it; `just find RDAP`.
- A 403 wall can be a throttle: .info RDAP 403'd from record 199 on above ~3 q/s (awselb/2.0, 118 bytes, no Retry-After) and answered after ~12 idle minutes; `just find RDAP`.
- A park file nothing re-reads is a queue leak: `cdx_platform_walk.py` parks a platform as too heavy after `MAX_FAILED_RUNS` (3) runs of 5xx, in the same `.refused` file as a 403, and its `todo` never asks a `.refused` seed again.
- Robots is read on the host in the download URL: www.fac.gov permits all while its data files sit on app.fac.gov, Disallow: / (`scripts/harness/fetch.py`).
- A by-name robots group can sit anywhere in the file: tomocha.net names ClaudeBot at line 51 of 61 under a permissive *, and a ten-line read cost 1,623 EE (`scripts/harness/fetch.py`; `just find tomocha.net`).
- `ftp.acc.umu.se` names Claude-User, Claude-Code, Claude-SearchBot, Claude-Web and ClaudeBot at lines 115 to 119 of a 6,238 B robots.txt whose first group is a permissive `User-agent: *` (`scripts/harness/fetch.py` `OUR_ROBOT_NAMES`).
- Refusing us by name: cryptome.org, tbtf.com, www.openpgp.net, ftp.nluug.nl, tomocha.net, mirror.aarnet.edu.au, ftp.aarnet.edu.au, www.potaroo.net, ftp.sunet.se, ftp.surfnet.nl, www.math.upenn.edu, ftp.cc.uoc.gr, ftp.acc.umu.se, www.floodgap.com, gopher.floodgap.com, leb.net, app.fac.gov (`scripts/harness/fetch.py` `OUR_ROBOT_NAMES`).
- Surviving old mirrors are the ones refusing us: five of seven live large mirrors in one sweep refused, and the two that allowed held only current distro trees; `just find ClaudeBot`.
- `codeload.github.com` and `api.github.com` serve no robots.txt and `github.com` forbids archive paths, so an API commit SHA plus a codeload tarball fetches a repository; `just find codeload`.

## Store

- DuckDB admits one process per file: a read-only handle blocks the writer, and the lock error names the holder's PID and suggests read-only mode, the wrong fix (`scripts/harness/sync_lock.sh`).
- `prior_task` is a source, `prior_reused` the evidence type: `'prior_task'` as a filter matches nothing and counts all 43.7M baseline rows as ours (`src/ark/stats.py` `BASELINE_TYPE`).
- A lane counts once the bank reads it, converters too: 67 RDAP journals (~12,000 EE) and 5,793 CDX year-records sat unread (`just bank` step c, `bank_trigger.py` `FOLD`).
- `just residual` (`scripts/harness/audit_residual.py`) finds unread journals only for families with an ingest glob; a new lane has none and stays invisible to it.
- An ingest that opens no file prints zeros, `files_seen` 0, and exits 0: a gz-only glob missed every IETF `.jsonl` shard (`src/ark/hostnames.py` `ingest_usenet_item_dir`).
- A name key freezes a growing file: the IETF collector appends to one shard per list, so the ingest keys name plus sha256 and re-reads a changed digest (`src/ark/hostnames.py`).
- A collector's output name carries a run id, never a resetting counter: a restarted sweep overwrote six `batch1_shard_*` files (`scripts/sources/usenet/sweep_alt_hierarchy.sh` `RUN_ID`).
- The ingest ledger keys (source_name, file_name) with sha256, so a recycled name fails with `ledgered with different content (sha256 mismatch)` (`src/ark/bulk.py`).
- `data/raw` has 129,101,381,838 bytes unledgered, of which journal-shaped `*.jsonl.gz` is 599,459,118, 215x less: raw containers are never ledgered (`just residual`).
- An unledgered journal is usually a superseded intermediate: banked `usenet_addr` and `usenet_bare` `*_candidates_cmp*` files hold the older per-run journals' pairs (`just residual`).
- A journal of answers without the response cannot be re-read: 1,163 gap journals hold 2,984,321 answers with no host, unreadable at hostname grain (`scripts/engines/cdx_gap_hostgrain.py`).
- 7,578,321 domain-years rest on CDX evidence with a timestamp and no host, so no host can be named; every CDX query asks `fl=timestamp,original` (`src/ark/cdx.py`).
- A cleanup downstream of the writer does not hold: bare years inferred from `www.` captures, cleaned to zero, came back as 22,920 from the fold overnight (`src/ark/hostnames.py`).
- XIII filters the claim, never the store: `export.py` screens six year files, six hostname files and both manifests; `domain_year` and `hostname_year` keep every row (`src/ark/export.py`).
- `domain_language` and its migration stay in `src/ark/db.py`: shipped provenance exports hold its rows and `ark rebuild` loads them (`src/ark/provenance.py` `OPTIONAL_TABLES`).
- `private/` has no retention row, so `offsite.py` never copies it off-site and no reproduction reads it (`scripts/round/offsite.py`, `docs/registers/retention.md`).

## Harness

- A fleet price on a synced held-set is a ceiling: 1,180,003.5 EE re-priced on the store to about 4,850 (132 of 258,631 pairs missing) (`src/ark/price_snapshot.py`, `ark price-snapshot`).
- A fleet leg downloads only through `scripts/harness/fetch.py`: whole robots.txt on every hop, 1 GB cap by header and stream, no extraction, two write roots.
- `standing_rule.py` parks a lead unless its `standing` block shows the fleet admitted it on all five clauses (size, terms, robots, class, window), and itself tests only the class: one with no master source in the register parks (`CLAUSES`).
- The store re-price decides a FIND until the fleet program's figure has agreed with it within 1% on the last ten booked finds; then the program's figure decides (`scripts/harness/standing_rule.py`).
- ark-fleet CI refuses a workflow that does not default to `CLAUDE_CODE_OAUTH_TOKEN_PRIMARY` (ark-fleet `.github/workflows/ci.yaml`).
- Fable costs about 22x sonnet against the five-hour window: 18.7 points per million tokens against 0.85; ark-fleet `scripts/fixtures/telemetry-20260908.jsonl`.
- VPS corpus bytes go only to `$ARK_PROBE_DIR`, a RAM tmpfs private to one run, since `/tmp` sits on the root disk agentless scanning images (ark-fleet `.github/workflows/leg.yaml`).
- A sweep of the guessed globs `/tmp/ark_probe*` and `/tmp/ark_run_*` missed `/tmp/arkrun` (ark-fleet `.github/workflows/leg.yaml`).
- Killed legs left 2.4 GiB of a 3.9 GiB tmpfs (ark-fleet `vps/cleanup.sh`).

## Do not rebuild

- RDAP client (`src/ark/rdap.py`, `ark rdap`): the terms in every RDAP response forbid bulk querying at all four registries.
- `parse_rdap_snapshot`, `attested_years` and `RDAP_REDIRECTOR` stay in `src/ark/sources.py`: they replay the RDAP journals already on disk.
- Sibling RDAP queue ranker (`rank_sibling_queue.py`): no RDAP queue is left, and the candidate-pool headroom it fed measured 0.107 points, not 1.47.
- Page-level English verification engine: EE is the TLD-weighted share in `docs/brief/ding/project-brief.md` section III, not a per-site verdict.
- Local admitter (`scripts/harness/admit_prompt.txt`, the `claude -p` leg of `just bank`): a local `claude -p` bills the laptop's own Claude login at API rates, and `standing_rule.py` makes the admit decision with no tokens.
- Laptop agent fan-out and overnight hunt (`agent_fanout.sh`, `agent_watchdog.sh`, `just hunt-overnight`, `just agent-loop`): the fleet runs sessions on a schedule with per-run telemetry.
- Decision sheet (`scripts/harness/decision_sheet.py`, `decisions-open.md`): a third copy of the pending queue, beside the `Decision: pending` blocks and the `needs-owner` issues.
- VPS sweep scripts (restart_sweeps, make_vps_bundle, vps_bootstrap, pull_vps_journals, vps_start_edge, cdx_suffix_run, pull_suffix_loop): the one VPS client runs `cdx_platform_walk.py`.
- Output-unit pack (`scripts/output_unit_pack/`): it copied `canonical.py`, the public suffix list and the English-share table, and copies drift.
- One-shot migrations (admit_www_of_parent, apply_hostname_purpose_rule, assign_unassigned_evidence, convert_register): ingest and `ark check` enforce their rules.
- One-shot collectors (`collect_yahoo_directory.py`, `collect_dartmouth_bfs_seed.py`, `collect_namewinner_2001.py`): the Yahoo tree closed at 7.73 EE, and the other two ran once, their bytes in `data/raw/` with refetch URLs in the register; `just find Yahoo`.
- Pending-hypotheses backlog: of 50 entries ranked by subjective 0 to 100 potential, 3 measured at or above 5,000 EE, all answered elsewhere; `docs/registers/queue.md` ranks by measured EE.
- `maintain.sh` fold loop: `just bank` step c folds journals when `bank_trigger.py check` sees the `FOLD` globs move, a move alone waiting until the last bank is `ARK_BANK_JOURNAL_HOURS` (3) old.
- `added_since.py`: its queries never applied the spec XIII screen, so readers quote `docs/ROUND.md` field 5.
- Fleet leg CDX seat (`scripts/harness/cdx_slot.sh`): no fleet leg queries CDX, and a seat for one reopens the channel the three collectors meter.
- Availability endpoint (`wayback_availability.py`, `availability_home.sh`, `availability_vps_loop.sh`): it names no exact host (`{}` for yahoo.com from both IPs) and closed at 11.0976 EE; re-aimed at `ark cdx`, its queue paid 125 EE/hour; `just find availability`.
- CDX year fill (`cdx_yearfill.py`), one 2001 question per name held at 2000: he held 74 of the 118 hosts with a 2001 capture and the rest paid at most 7.08 EE per client-hour, as his release is archive-derived; `just find cdx_yearfill`.
- Parent shards: enumerating subdomains of parents he holds earns 96 EE per client-hour, and the brief calls that expansion duplicative (`project-brief.md`, CDX paragraph).
- Platform-parent sweep (`rank_platform_parents.py`, `build_rows_per_host.py`, `platform_sweep_loop.sh`, `platform_sweep.sh`): a clean exit before the first page left no state file, no `.done` and no park entry, so 96 parents sat unasked, yahoo.com and aol.com among them; `cdx_platform_walk.py` walks platforms now.
- Per-parent `matchType=domain` (`cdx_thin_sweep.py`): 10,029,609 zero-hostname registrables at about 0.55 EE a parent, 642 EE per client-hour (563 when held 5 or 6 years); 74 thin parents gave 0.21 each, 61 an hour.
- Per-domain gap query (`src/ark/gaps.py`): 255 EE/hour, 400 pairs an hour at 0.638 EE over 16.9 hours, one pair per answer.
- Per-domain query queues (`build_query_queue.py`, `build_pool_candidates.py`, `supervise_cdx_pool.sh`): one question per domain paid 1.249 EE per query on bracketed gaps, 0.2645 on edge years and about 0.18 on the candidate pool.
- Dead-host file finder (`recover_dead_hosts.py`): it asked `web.archive.org/cdx` from outside the three metered collectors.
- An mbox-head era pre-filter, never built: the first 200 KB does not date an archive, which runs in donation batches (first `Date:` 2013 at 0% in window, 2008 at 85%) (`scripts/sources/usenet/fetch_usenet_hierarchies.sh`).
- `_CLASSIFY_SQL` in `src/ark/seed.py`: correlated EXISTS runs 0.33 s per 3,000 names, a hand-written semi-join 1.30 s; DuckDB already plans a hash semi-join.
