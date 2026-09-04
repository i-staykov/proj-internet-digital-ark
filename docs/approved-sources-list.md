# Approved sources

**One `Decision:` line per (source, evidence type), and `ark ingest` enforces it** (ADR-003). A
master-eligible class with no `master` line here cannot date a year; the gate exits 2. Vocabulary:
`pending` (nobody has looked), `master` (may date a year), `candidate-only` (collect, never dates a
year), `rejected` (binds, and the request generator refuses to re-open it).

Generate a request with `scripts/harness/request_approval.py <spec> --journal <journal>`: it builds a
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

### ia_cdx_hostnames / cdx_timestamp

- ingest specs: `ark ingest-hostnames` over raw capture journals ({url, timestamp} lines);
  two acquisition methods under the one source row, `ia_cdx_domain_sweep` for the
  `matchType=domain` CDX sweeps and `nypw_timemap_hostgrain` for the NYPW TimeMap parts
  (https://archive.org/download/nypw_timemaps/, CC BY 4.0, the `nypw_timemaps` artifact
  above) re-emitted at hostname grain by `scripts/sources/nypw/nypw_hostgrain.py`
- what dates one item: the row's own 14-digit capture timestamp, quoted in the evidence
  value beside the hostname it dates
- unit: the reviewer accepted hostnames as annual records on 2026-09-01 (his reply,
  verbatim, in private/personal-context.md); registrables stay prioritized, hostnames
  ship as separate per-year files he can merge or discard
- admitted under the standing rule of 2026-08-29 (Ivo): the class (cdx_timestamp on the
  IA CDX API) is master-eligible and approved twice above, the stamp is machine-written
  inside the artifact, the terms are the ones the collectors already honour, and
  `ark check` gates the ingest with two hostname-wall checks

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
  `just reproduce journals`, the reproduction path the shipped archive tells a reviewer to run, and it
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

### early_web_cdx_hostnames / cdx_timestamp

- ingest: `ark ingest-hostnames data/raw/early_web_hostgrain/`, the 224 Early Web CDX parts
  (`data/raw/early_web/*.cdx.gz`, the exact bytes `early_web_cdx` was banked on in July)
  re-emitted as `{url, timestamp}` capture journals by
  `scripts/sources/early_web/early_web_hostgrain.py`, HTTP 200 rows only, as the registrable
  ingest read them; one journal per part so the ledger stays idempotent per part
- source: https://archive.org/details/early-web_cdx-lang-cdxa (224 `*.cdx.gz`, 184,858,264 B;
  `archive.org/robots.txt` read whole, only `/control/` and `/report/` disallowed)
- measured: **631,148.1 net-new EE over 1,163,616 (hostname, year) records, 1996-1999**, re-priced
  2026-09-02 on the live store after the ingest, against both `hostname_year` and the reviewer's own
  `merged260901` files: 1,763,562 rows written, 599,946 of them verbatim in his file for that year
  and so excluded, none dated 2000 or 2001. By year 1996 47,933.4 EE, 1997 38,094.5, 1998 256,111.1,
  1999 289,009.0; by TLD com 424,850.2, uk 49,027.7, org 37,508.9, net 28,872.9, au 14,649.0, edu
  10,378.7, de 9,235.0. Every parent was already held in that year (0 parent registrable-years
  earned). The fleet's snapshot figure (1,163,758 records, 631,215.8 EE) reproduces to 0.01%
- what dates one item: the row's own 14-digit capture timestamp, field 2 of the classic CDX
  line, `uk,co,bucksnet,homepages)/ 19981202041041 http://homepages.bucksnet.co.uk:80/ text/html
  200 ...`, quoted in every evidence value as `cdx capture 19981202041041 homepages.bucksnet.co.uk`
- the disclosure that decides what this is worth: **1,163,612 of the 1,163,616 net-new records are `www.<held registrable>`
  forms** (the four others sit beneath `archive.org` and two `*archive.org` names). The reviewer's
  `merged260901` files hold Early Web's non-`www.` hosts by name (`ei.haygroup.com`,
  `frontpage.helicon.net` sit verbatim in his 1999 file; 1,489,119 non-`www.` multi-label names in
  that file against 385 `www.` ones), so at hostname grain this corpus is IA-derived everywhere
  except the `www.` seam, and his files evidently normalise `www.` away. The figure is real under
  the unit already shipped (the NYPW re-read was 93.6% `www.` forms, disclosed in the report) and
  is worth 0 if his calculator strips `www.`; both readings are quoted in the report and the
  question is put to him with the delivery
- the registrable lane of the same bytes was banked in July (register line 173); the hostname
  unit did not exist until the reviewer accepted it on 2026-09-01, and the fleet's census
  (`early_web_cdx_hostname_grain`, 2026-09-02) is the first reading of the column
- admitted under the standing rule of 2026-08-29 (Ivo): the class is `cdx_timestamp`, master
  for these exact bytes since July; the stamp is the capture timestamp inside the artifact,
  quoted above; the terms are archive.org's public download, robots.txt read whole; `ark check`
  passes after the ingest with both hostname-wall checks

Decision: master

### usfedgov_extract_hostnames / cdx_timestamp

- ingest: `ark ingest-hostnames data/raw/usfedgov_hostgrain/`, a `{url, timestamp}` journal
  with one capture per distinct host (the earliest HTTP 200 capture, else the earliest of any
  status) written by `scripts/sources/usfedgov/usfedgov_hostgrain.py` from the item's merged
  ZipNum index, read whole, no CDX API request
- source: https://archive.org/download/USFEDGOV-EXTRACT-2001/USFEDGOV-EXTRACT-2001.cdx.gz
  (1,364,737,799 B, asserted byte-exact against `archive.org/metadata/USFEDGOV-EXTRACT-2001`;
  collections earlygovweb / webdataservices / web, `access-restricted` unset; `archive.org/robots.txt`
  read whole, only `/control/` and `/report/` disallowed)
- measured: **21,925.9 net-new EE over 22,417 (hostname, 2001) records**, re-priced 2026-09-02 on
  the live store after the ingest, against both `hostname_year` and the reviewer's 2001 file: 33,631
  distinct hosts in the index (48,110,426 rows read whole), 31,218 proper hostnames written, 8,801
  verbatim in his 2001 file and excluded. By TLD gov 21,620.9 EE, edu 79.7, com 76.5, us 63.0, org
  62.5; largest parents `lanl.gov` 10,110 hosts, `nist.gov` 4,126, `nasa.gov` 3,267. The parents
  not yet held at 2001 earn their year from the same rows: 176 registrable-years, 152.5 EE. 3,596 of
  the net-new records are `www.` forms. The fleet's snapshot figure (21,713 hostname EE plus 165
  registrable EE) reproduces within 1%
- what dates one item: the CDX capture timestamp on the row itself, `20011128173757`-form,
  written by the crawler at fetch time, quoted in every evidence value as
  `cdx capture 20011128173757 <hostname>`; the evidence URL is the Wayback replay of that
  capture, as the platform sweep writes it
- the registrable lane was closed twice on saturation (register lines 1065 and 1174, 56.2 and
  100.2 EE); the fleet's census (`usfedgov_extract_hostname_grain`, 2026-09-02) confirms 204
  novel registrables in the whole item and shows the hosts do not saturate. Many novel hosts are
  workstation names beneath big labs (`pn960848.lanl.gov`), captured as embed or link targets;
  they pass the reviewer's validity rule and carry their own capture stamp, and he discards at
  merge what he does not want, which is his stated procedure
- the sibling merged indexes for 1996-2000 (27.8 MB to 1.08 GB, same path pattern, none
  access-restricted) are the same lane and are not part of this admission; 1996 measured a
  ceiling of ~475 EE, 1997-2000 are unmeasured
- admitted under the standing rule of 2026-08-29 (Ivo): the class is `cdx_timestamp`, master
  for IA bulk CDX files since July; the stamp is the capture timestamp inside the artifact,
  quoted above; the terms are archive.org's public download, robots.txt read whole; `ark check`
  passes after the ingest with both hostname-wall checks

Decision: master

### isc_survey_hostnames / artifact_listing

- ingest: `ark ingest-isc-hostnames data/raw/isc_survey/wb_nw_*_*.gz`, the per-TLD host files
  of the Network Wizards / ISC Internet Domain Survey, the exact bytes `isc_survey` was banked on
  in July (584 files on disk, 9607, 9701 and 9707 editions), read one level below the registrable:
  every line is `IP hostname`, the PTR walk's record of a host answering in DNS that month, and
  the registrable ingest kept only the host's parent. `.domains` lists are skipped by name
- source: http://nw.com/zone/9607.hosts/uk.gz and siblings, through the 1996-1997 Wayback
  captures of `nw.com` (`scripts/sources/directories/fetch_nw_host_files.py` lists them from one
  CDX prefix query and fetches each `id_` replay; the fleet reached the same files through
  `archive.org/wayback/available`, e.g.
  `http://web.archive.org/web/19970529075101id_/http://nw.com.:80/zone/9607.hosts/uk.gz`,
  4,105,718 B, byte-identical to `wb_nw_9607_uk.gz` on disk)
- measured: see the re-pricing below, written after the ingest
- what dates one item: the survey's own `YYMM` edition code, `9607` in the artifact's path
  `/zone/9607.hosts/uk.gz` and in every file of the edition, quoted in every evidence value as
  `isc survey 1996-07 host <hostname>`; the reviewer confirmed in writing on 2026-07-24 that a
  dated DNS survey enters the annual files directly on exactly this stamp, and the Wayback capture
  stamp (`19970529075101`) fixes that the file existed then. Same evidence, same class, same
  decision the registrable lane stands on; the hostname unit did not exist until 2026-09-01
- the registrable lane was closed as "complete and fully held" (register line 1144, 14,956.4
  EE banked, 0 parents missing at their year); the fleet's census (`isc_survey_host_files_hostname_grain`,
  2026-09-02) read five 9607 files whole and found 100% of parents held at 1996 and 98.2% of the
  valid hosts absent from both the store and the reviewer's 1996 file: 818,952 EE on the clean
  shapes alone, 2,352,584 EE with the dialup and numbered-label shapes. The disclosure that
  decides what this is worth: a large share of the hosts are per-customer dialup and workstation
  names (`pc50.btbcs.bt.co.uk`, `dynws2.mdx.ac.uk`, 62,374 `x.demon.co.uk` nodenames in one
  file). They are real hosts the walk resolved, pass the reviewer's validity rule and carry the
  edition's stamp, and he discards at merge what he does not want, which is his stated
  procedure; the shape split is quoted in the report so he can do that by eye
- admitted under the standing rule of 2026-08-29 (Ivo): the class is `artifact_listing`, master
  for these exact bytes since July; the stamp is the survey edition code the artifact carries in
  its own path and the reviewer accepted in writing, quoted above; the terms are the Wayback
  public replay of a site the survey published openly, already read for the registrable lane;
  `ark check` passes after the ingest with both hostname-wall checks
- **amended 2026-09-02 (Ivo): at hostname grain this lane is candidate-only.** The reviewer's
  purpose for the unit is retrieving archived pages, and a reverse-DNS walk observes a machine
  answering, not a site (65% of these names are dialup or workstation shapes). The evidence
  class stays master: the same row still dates the parent registrable, and the 18,147,169
  hostname rows it had written were removed by `scripts/round/apply_hostname_purpose_rule.py`.
  Re-admissible by adding the source to `WEB_FACING_HOST_SOURCES` if he rules DNS listings count

Decision: master

### ripe_nserver_hostnames / artifact_listing

- ingest: `ark ingest-ripe-nserver-hostnames data/raw/ripe_funet/ripe.db.gz
  data/raw/ripe_funet_split/ripe.db.domain.gz`, the exact bytes `ripe_dbase_1999` and
  `ripe_dbase_split_2004` were decided on; it records the `*ns:` / `nserver:` HOSTS a `domain:`
  object points at, the attribute both registrable parsers discard. Reverse-zone objects are kept
  here: their nameservers are hosts the registry stated on the same day, and the store's
  reverse-DNS invariant concerns the delegated name, not the server
- source: https://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz (71,919,736 B,
  `Last-Modified: Tue, 03 Aug 1999 21:27:00 GMT`) and
  https://ftp.funet.fi/pub/netinfo/RIPE/dbase/split/ripe.db.domain.gz (5,452,546 B); the host has
  no robots.txt
- measured: **11,780.1 net-new EE over 49,841 hostname records**, re-priced 2026-09-02 on the live
  store after the ingest, against both `hostname_year` and the reviewer's files: the snapshot arm
  40,065 (hostname, 1999) rows written, 1,133 verbatim in his 1999 file and excluded, **38,932
  records, 8,552.5 EE**; the split-edition arm 11,216 rows across 1996-2001, 307 excluded, **10,909
  records, 3,227.6 EE** (1996 48.4, 1997 117.0, 1998 332.3, 1999 156.3, 2000 1,105.6, 2001
  1,468.0). By TLD net 2,647.8 EE, com 2,520.8, de 1,460.2, uk 686.9, it 675.5, ro 433.2, at 366.4,
  fr 315.6. Largest parents `cnr.it` 127 hosts, `pair.com` 114, `uu.net` 64, so no platform. The
  parents not yet held earn their year from the same rows: 1,232 registrable-years, 442.9 EE, which
  is the fleet's registrable-unit figure of ~470 and the L916 closure again. The fleet's hostname
  figure (~11,400 EE) reproduces within 3%
- what dates one item: for the snapshot, the dump's own generation stamp on line 2 of the
  payload, `# 990804 00:07:01`, the same stamp `ripe_dbase_1999` was approved on, quoted in every
  evidence value as `ripe_dbase:19990804 ns <hostname>`, 1999 only (rule 6); for the split
  edition, the object's LATEST `changed:` line, `changed: mx@lucky.net 20010716`, the reading
  `ripe_dbase_split_2004` banked, quoted as `ripe_changed:20010716 nserver <hostname>`: an object
  last changed in year Y is the registry stating its nserver set stood as written in Y. A `*ns:`
  line is the registry's record of which host served that delegation, the same instrument as the
  NS right-hand side in a zone file (`internic_zone_hostnames`). No split: a machine wrote it
- permission: RIPE NCC's reply of 2026-08-26 covers the files as a whole; the promise it binds
  the code to is "publish no personal data", so the readers touch only the nameserver value, the
  object key and the trailing date of `changed:`, and `tests/test_ripe_nserver_hostnames.py`
  fails on a leak exactly as the registrable lanes' tests do
- the registrable lane of the same attribute was closed on yield (register line 916, 70.4 EE) and
  the fleet's reprice reproduces that closure at 254 EE, so the registrable unit stays closed; the
  hostname unit did not exist until 2026-09-01
- admitted under the standing rule of 2026-08-29 (Ivo): the class is `artifact_listing`, decided
  master for these exact bytes on 2026-08-26 and under the standing rule for the split edition;
  the stamps are machine-written inside the artifacts, quoted above; the terms are the written
  RIPE NCC permission; `ark check` passes after the ingest with both hostname-wall checks
- **amended 2026-09-02 (Ivo): at hostname grain this lane is candidate-only.** An `nserver:`
  attribute observes a nameserver, not a site; the class stays master for the parent's year and
  the 51,281 hostname rows were removed by `scripts/round/apply_hostname_purpose_rule.py`

Decision: master



### internic_zone_hostnames / artifact_listing

- ingest: `ark ingest-zone-hostnames` over the six 1997 zone files (`data/raw/internic_zones/{org,edu,gov,mil,root,arpa}.zone.gz`,
  the exact bytes `internic_zone` was decided on); it records the nameserver TARGET of every NS
  record at hostname grain, the column `parse_internic_zone` discards on purpose
- source: https://web.archive.org/web/19970420113748id_/http://nic.mil/oroot.html/org.zone.gz,
  https://web.archive.org/web/19970420112952id_/http://nic.mil/oroot.html/edu.zone.gz,
  https://web.archive.org/web/19970420113002id_/http://nic.mil/oroot.html/gov.zone.gz
- measured: **11,860.7 net-new EE over 19,211 (hostname, 1997) records**, re-priced 2026-09-02 on
  the live store: 21,498 distinct proper hostnames named as NS targets across the six zones,
  663 already in `hostname_year` at 1997, 1,958 already in the reviewer's own `merged260901`
  1997 file, 21,390 (99.5%) with their parent registrable held at 1997. No split: nothing here
  was typed by a person. By TLD: com 7,457 records 4,713.6 EE, net 4,957 / 2,245.5, edu 2,037 /
  1,979.4, org 2,116 / 1,502.6, gov 296 / 290.8, uk 241 / 236.5, ca 269 / 225.0. Largest parent
  `mit.edu` with 24 hosts, so not a platform. The fleet's snapshot figure (19,186 records, 11,862.5
  EE, org+edu+gov only) reproduces within 0.2%
- what dates one item: the zone's own SOA serial on line 2 of the payload, `1997041800` in
  `ORG. IN SOA A.ROOT-SERVERS.NET. hostmaster.INTERNIC.NET. ( 1997041800 ;serial`, quoted in every
  evidence value as `internic org zone serial 1997041800 NS <hostname>`; the IA captures of
  1997-04-20 fix when the file existed. An NS right-hand side is the registry's machine-written
  record that this host served that delegation at that instant
- the registrable lane of the same column was measured and closed on yield on 2026-08-29
  (register line 881: 14,573 domains, 99.28% held at 1997, 63 net-new pairs). That closure was at
  registrable grain and stands; the hostname unit did not exist until the reviewer accepted it on
  2026-09-01. The 85 parents not held at 1997 earn their year from the same rows, as the check
  `nothing_earned_is_left_unassigned` requires, which is those 63 pairs plus baseline drift
- admitted under the standing rule of 2026-08-29 (Ivo): the class is `artifact_listing`, decided
  master for these exact bytes on 2026-08-24; the stamp is the SOA serial inside the artifact,
  quoted above; the terms are the ones read for `internic_zone` (IA replay of a nic.mil capture,
  `archive.org/robots.txt` read whole, only `/control/` and `/report/` disallowed); `ark check`
  passes after the ingest with both hostname-wall checks
- **amended 2026-09-02 (Ivo): at hostname grain this lane is candidate-only.** An NS target
  observes a nameserver, not a site; the class stays master for the parent's year and the
  20,835 hostname rows were removed by `scripts/round/apply_hostname_purpose_rule.py`

Decision: master

### squidguard_2001_hostnames / artifact_listing

- ingest: `ark ingest-blocklist-hostnames data/raw/squidguard/*`, the exact flattened files
  `squidguard_2001_blacklist` was decided on; it keeps the sub-registrable HOST each list line
  names, the column the registrable parser collapses onto its parent (`mail` skipped as before)
- source: http://archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz
  (1,852,659 B, member `samples/dest/blacklists.tar.gz`)
- measured: **1,059.8 net-new EE over 2,093 (hostname, 2001) records**, re-priced 2026-09-02 on the
  live store from the bytes: 4,323 distinct proper hostnames across the `domains`, `urls` and dated
  diff lanes, every parent held at 2001, 432 already in `hostname_year`, 2,175 already in the
  reviewer's own `merged260901` 2001 file. No split: the robot wrote the list. By TLD com 1,123
  records 709.8 EE, net 417 / 188.9, org 57 / 40.5, nu 82 / 22.9. Largest parents `fsn.net` 135,
  `free.fr` 78, `majorhost.com` 51. The fleet's snapshot figure on the `domains` lane alone was
  866.0 EE; the `urls` lane, equally the robot's output, adds the rest. **Banked 2026-09-02: 3,891
  store rows, of which 2,093 ship at 1,059.8 EE**, the rest being hosts the reviewer's file has
- what dates one item: the list's own compile header, `# This list was compiled in 0:00:20 on
  2001.12.18 15:04:29.` from `squidGuardRobot-2.3.4`, or the diff's filename date; quoted in every
  evidence value as `squidguard:<category>/<kind>@20011218 host <hostname>`. The header asserts the
  links `tested successfully`, so the host answered at that instant
- the registrable lane of the same bytes was banked at 10,376.9 EE on 2026-08-26 and the hostname
  grain measured 2026-09-02 (register line 816, fleet `banked_lists_hostname_grain`) is a
  unit-change reopen, not a re-test
- admitted under the standing rule of 2026-08-29 (Ivo): the class is `artifact_listing`, decided
  master for these exact bytes on 2026-08-26; the stamp is the compile header inside the artifact,
  quoted above; the terms are GPL v2, read at approval; `ark check` passes after the ingest with
  both hostname-wall checks

Decision: master

### chastity_list_hostnames / dated_directory

- ingest: `ark ingest-blocklist-hostnames data/raw/chastity/chastity-list_0.5.orig.tar.gz`. It reads
  the TARBALL, not the unpacked tree, because the stamp is the tar member header and extraction
  loses it; every `db/<category>/{domains,urls,*.diff}` member except `mail`
- source: https://archive.debian.org/debian/pool/main/c/chastity-list/chastity-list_0.5.orig.tar.gz
  (720,609 B)
- measured: **2,801.5 net-new EE over 6,520 (hostname, 2001) records**, re-priced 2026-09-02 on the
  live store from the bytes: 10,929 distinct proper hostnames, 10,883 (99.6%) beneath a parent
  that already carries an assigned year, 874 already in `hostname_year`, 4,077 already in the
  reviewer's own 2001 file. By TLD com 2,408 records 1,522.1 EE, net 1,460 / 661.4, fr 1,489 /
  152.0, org 194 / 137.8, uk 64 / 62.8. Largest parents `free.fr` 1,292, `fsn.net` 664,
  `multimania.com` 288, `cjb.net` 227. Union with the squidGuard lane above: **7,653 records,
  3,410.4 EE**, 1,678 hostnames shared between the two lists. **Banked 2026-09-02: 8,225 store rows,
  of which 5,615 ship at 2,381.9 EE**; with the squidGuard lane the family ships **7,708 records,
  3,441.8 EE**, the 55 records above the pre-ingest union being hosts whose parent earned 2001 from
  the same row
- **the corroboration split applies and costs 46 hosts**: the list is hand-kept, so a host counts
  only when its parent registrable already carries an assigned year, the predicate
  `split_chastity.py` states; the 46 beneath a novel parent are counted as parked and not written
- what dates one item: the tar member header tar wrote on every member, `-rw-r----- rkrusty rkrusty
  4729 Dec 14 2001 chastity-list-0.5/db/ads/domains`, read from the tarball at ingest and quoted in
  every evidence value as `chastity-list:20011214 <category>/<kind> host <hostname>`; the same
  argument approved for the registrable lane on 2026-08-31
- admitted under the standing rule of 2026-08-29 (Ivo): the class is `dated_directory`, decided
  master for these exact bytes on 2026-08-31; the stamp is the tar member header inside the
  artifact, quoted above; the terms are GPL v2, verbatim in `COPYING`, read at approval; `ark
  check` passes after the ingest with both hostname-wall checks

Decision: master

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
  reflowed it, and `scripts/sources/usenet/collect_usenet_whois.py` caps the look-back at 40 lines and normalises
  `&nbsp;` and quote prefixes before either pattern runs, because an HTML-escaped second copy of a
  block once bound `openssl.org`'s creation date to `engelschall.com`
- ingest specs: `usenet_whois_dated` and `usenet_whois_candidates`. Journals at
  `data/raw/usenet_whois/usenet_whois_{dated,candidates}.jsonl.gz`, regenerable with `just collect usenet-whois`
- admitted under the standing rule of 2026-08-29 (Ivo)

Decision: master

### nypw_timemaps / cdx_timestamp

- ingest specs: `nypw_timemaps`
- measured: **87,905.0 EE net-new post-split over 197,938 pairs**, over the twenty-seven
  partitions now in the store, read back out of `output/netnew/evidence_manifest.csv` (export of
  2026-09-01 01:22) and priced with `ark.english_share.weight_of` rather than projected. Nothing in
  a TimeMap row was typed by a human, so pre-split equals post-split. Mean weight 0.4441. By
  assigned year: 1997 1, 1998 137, 1999 1,743, 2000 2,629, **2001 193,428**, so 97.7% of the yield
  is a 2001 year, which is the adjacent-year screen paying exactly as the aim-at-2001 law predicts.
  **This supersedes both the 4,084.3 EE over 10,072 pairs first recorded and the 63,969.6 over
  144,118 that replaced it**: each was correct for the partitions ingested at the time and was
  overtaken within the hour. The pre-ingest pricing of the first three parts said 6,424 pairs and
  4,146.8 EE at mean weight 0.6455, so the store took far more pairs at a lower weight: the head the
  pricing counted had been covered in the days between, and what was left is the ccTLD tail.
  **Price and banked figure are not the same number and the banked one is the one to quote**
- **net-new attributed per partition, which is what says where to aim next.** Every one of the
  197,938 pairs matched exactly one ingested partition on its `evidence_url`, with none left
  unattributed, so this is a census and not a sample. By folder, which is the year of FIRST capture:

      folder   partitions   net-new EE   mean per partition
      1997              2        651.3                325.7
      1998             11     23,284.0              2,116.7
      1999              5     19,807.8              3,961.6
      2000              8     44,159.3              5,519.9
      2001              1          2.5                  2.5

  **The payload rises monotonically from 1997 to 2000 and then collapses by three orders of
  magnitude at 2001, and that collapse is structural rather than luck.** A domain in the 2001 folder
  was first captured in 2001, so it has no earlier year to give and its 2001 year is already held by
  an IA-derived baseline by construction. The 2001 years that pay come from 1997 to 2000 folder
  TimeMaps, which carry the later captures of domains first seen earlier. **A reading that takes
  "97.7% of net-new is dated 2001" and concludes "download the 2001 folder" inverts the source**, by
  confusing the year of the CAPTURE with the year of the FOLDER; the collector docstring already had
  this right and was not changed. Within a folder, `rootURLs` outpays `deeplinks` **3.9x per
  partition** (77,912.2 EE over 18 against 9,992.7 over 9), so the queue order that maximises yield
  is 2000 and 1999 `rootURLs` first. The single best partition is
  `2000/rootURLs_part04r` at **18,775.3 EE**, the worst is `2001/deeplinks_part00o` at **2.5 EE**
- what dates one item: field 3 of a TimeMap row is Wayback's own 14-digit capture timestamp, written
  by the crawler at the instant of the capture. One row entire, from `2000/TM_other/TM_x00o2000_10000.txt`
  inside the first tarball:

      https://4free.net/mousepads.shtml net,4free)/mousepads.shtml 20010124104200
      http://www.4free.net:80/mousepads.shtml text/html 200 NT5S4OFZGCGRFF3TKTOCLK7IYFJKQKP6 4009

  `20010124104200` is the stamp and it evidences 2001 for `4free.net` and no other year, which is
  rule 6 satisfied by the row's own shape rather than by an argument about it
- the artifacts, linked so the bytes stay refetchable. All twenty-seven are under
  `https://archive.org/download/nypw_timemaps/`, sizes as logged by the fetcher in
  `data/logs/nypw_pull.log`:

      1999/nypw_timemaps1999_deeplinks_part00o.tar.gz     81,558,295 B
      1999/nypw_timemaps1999_rootURLs_part01r.tar.gz     548,991,394 B
      1999/nypw_timemaps1999_rootURLs_part02r.tar.gz     147,027,083 B
      1999/nypw_timemaps1999_rootURLs_part03r.tar.gz     150,725,864 B
      1999/nypw_timemaps1999_rootURLs_part04r.tar.gz     210,555,238 B
      2000/nypw_timemaps2000_deeplinks_part00o.tar.gz     31,659,131 B
      2000/nypw_timemaps2000_deeplinks_part01o.tar.gz     31,397,597 B
      2000/nypw_timemaps2000_deeplinks_part02o.tar.gz     56,689,031 B
      2000/nypw_timemaps2000_rootURLs_part01r.tar.gz     228,359,937 B
      2000/nypw_timemaps2000_rootURLs_part02r.tar.gz     119,945,969 B
      2000/nypw_timemaps2000_rootURLs_part03r.tar.gz     119,365,472 B
      2000/nypw_timemaps2000_rootURLs_part04r.tar.gz     825,494,346 B
      2000/nypw_timemaps2000_rootURLs_part05r.tar.gz     406,711,686 B
      2001/nypw_timemaps2001_deeplinks_part00o.tar.gz    148,848,304 B
      1997/nypw_timemaps1997_deeplinks_part00o.tar.gz     30,569,952 B
      1997/nypw_timemaps1997_rootURLs_part01r.tar.gz     137,487,874 B
      1998/nypw_timemaps1998_deeplinks_part00o.tar.gz     17,958,107 B
      1998/nypw_timemaps1998_deeplinks_part01o.tar.gz     13,698,867 B
      1998/nypw_timemaps1998_deeplinks_part02o.tar.gz     19,014,371 B
      1998/nypw_timemaps1998_rootURLs_part00r.tar.gz     617,413,931 B
      1998/nypw_timemaps1998_rootURLs_part01r.tar.gz     708,524,984 B
      1998/nypw_timemaps1998_rootURLs_part03r.tar.gz     449,293,008 B
      1998/nypw_timemaps1998_rootURLs_part04r.tar.gz     325,150,887 B
      1998/nypw_timemaps1998_rootURLs_part05r.tar.gz     726,115,622 B
      1998/nypw_timemaps1998_rootURLs_part06r.tar.gz      83,518,037 B
      1998/nypw_timemaps1998_rootURLs_part07r.tar.gz     521,097,923 B
      1998/nypw_timemaps1998_rootURLs_part08r.tar.gz     425,797,234 B

  **Only three of these were recorded when the entry was first written, while eleven were already in
  the store.** The tarballs are deleted after conversion to `.cdx.gz`, so an unrecorded partition is
  an unrefetchable one, which is the exact failure the link rule exists to stop
- terms, read in full before the first request: CC BY 4.0, stated in the item's own
  `nypw_timemaps_readme.txt`, "You are free to share and adapt the material, provided that
  appropriate credit is given". `archive.org/robots.txt` is 238 bytes whole and disallows only
  `/control/` and `/report/`, with no Claude or Anthropic group; the host the download redirect
  lands on, `ia800601.us.archive.org`, serves no robots.txt at all
- **why the sibling above being rejected does not decide this one.** The first-capture index holds
  one row per URL and so can only offer a domain its FIRST year, which an IA-derived baseline holds
  by construction. A TimeMap holds every capture of that URL, so it offers years for domains our
  metered per-domain collector never queried. The 2026-08-24 closure of this item at 14.2 EE tested
  the 1996 folder only, and folder year is the year of FIRST capture: folder Y can add only years
  Y+1..2001, so 1996 is the saturated head and 2001 is held by construction at 108,863 of 108,870
  pairs. The paying folders are 1997 to 2000
- potential: 72

- admitted under the standing rule of 2026-08-29 (Ivo)

Decision: master

Conditions checked one at a time. (1) `cdx_timestamp` is already master-eligible and is the type the
rejected sibling above already carries, so no class is being invented: the row shape is identical and
only the row COUNT per URL differs. (2) The stamp is Wayback's own 14-digit capture timestamp,
machine-written by the crawler, quoted above out of the bytes now on disk rather than from the
published example, which drops the leading queried-URI field and so reads as classic CDX when it is
not. (3) CC BY 4.0 in the item's own readme, `archive.org/robots.txt` 238 B read whole with no
Claude or Anthropic group, and no robots.txt at all on the download host the redirect lands on.
(4) `ark check` after the ingest.

One correction the finding needed and the register should carry, because it is the kind of thing
that silently ingests nothing: a TimeMap row has EIGHT fields, not seven, the first being the URI
that was queried. Written to classic-CDX offsets the collector read 1,503,591 rows and kept zero,
and only an assertion that a part MUST yield in-window rows caught it before the empty file was
renamed and skipped as finished on the next pass. `scripts/sources/nypw/collect_nypw_timemaps.py` now fails the
part rather than writing it.

### urlmerchant_inventory / artifact_listing

- measured 2026-08-31 against the live store, before the ingest, over the 244 listing pages on
  disk at the time of the split (the page collector outlives the session and a later batch takes
  its own `--tag`): 240 pages in window and stamped, 24,000 name slots, **23,875 distinct
  registrable domains**, letter pages effectively disjoint. **3,383 domains corroborated (14.2%)**,
  and the number that makes a 14% held-fraction pay is the second factor: **2,557 of those 3,383
  are held-and-missing-2001, 75.6% of held**. So **net-new post-split 2,557 pairs / 1,591.9 EE**,
  all at 2001, mean weight 0.6225, `com` / `net` / `org`. Gross pre-split is 5,655 EE over 9,153
  pairs on the 95-page probe and scales with the corpus; **do not quote it, it overstates by 9.3x**.
  The 20,492 names seen only here take the split and go to the candidate pool, dating nothing, at a
  measured typo upper bound of 44.8%
- what dates one item: the page's own machine-written generator stamp,
  `<META NAME="UPDATED" CONTENT="Tuesday, Jul 17 2001 1:19:41 AM">`, written by the program that
  printed the table out of URLMerchant's own listings database, with the Wayback capture fixing
  when the archive saw that table. The broker is asserting the name is registered and for sale at
  that instant, and `statistics.html` says they "routinely remove names that have been deleted by
  the registrar and are freely available". **The stamp is read per page and never inferred from the
  capture**: 4 of the 244 pages carry 2002 stamps and are dropped whole, which is also why 7 pages
  served from 2002 captures are harmless. Rule 6 gives 2001 and nothing else; the site's
  "Copyright (c) 1998-2001" implies 1999 and 2000 captures of the same namespace, and those are
  separate artifacts with their own stamps
- the artifact: `http://www.urlmerchant.com/domains/domain_<a-z|0-9>[_<n>].html` replayed as
  `https://web.archive.org/web/20010901000000id_/http://www.urlmerchant.com:80/domains/domain_a.html`,
  ~40 KB and 100 names per page; counts page `http://www.urlmerchant.com/statistics.html` at capture
  `20011231002753`, 18,452 B, stating "Total Domain Names Listed: 156,122". Pages and mementos under
  `data/raw/urlmerchant/`. **Verified as 244 distinct objects, not one interstitial repeated**: 244
  distinct sha256 over 244 files, every one carrying its own `META UPDATED` stamp and its own
  100-name table, which is the content assertion the `id_/` replay trap of 2026-08-19 demands
- terms: the download host is `web.archive.org`, whose `/robots.txt` is 404 (nginx, 146 B);
  `archive.org/robots.txt` was read in full first, 238 B, `Disallow: /control/` and `/report/` only,
  no ClaudeBot group. The origin `urlmerchant.com` serves nothing. Same route as the already-banked
  `namewinner_expiring`, `iedr_register`, `internic_zone` and `cctld_register_listing_capture`
- the NAME is what the split guards, not the date: an owner submitted each name to the broker by
  hand, so the date is a machine's and the name is a person's typing
- ingest specs: `urlmerchant_dated` and `urlmerchant_candidates`. Journals at
  `data/raw/urlmerchant/urlmerchant_{dated,candidates}_b1.jsonl.gz`, regenerable with
  `uv run python scripts/sources/directories/split_urlmerchant.py --tag b1 --write`
- **banked 2026-08-31**: the loader assigned `year_rows: 2557` out of 3,383 evidence rows, which
  is the split's net-new count to the pair, so **1,591.9 EE** is what this ingest added and not an
  estimate. `ark check` all 13 PASS afterwards
- potential: 32
- admitted under the standing rule of 2026-08-29 (Ivo)

Decision: master

Conditions checked one at a time. (1) `artifact_listing` is already master-eligible and is the type
the ISC survey carries on the same argument, so no class is being invented. (2) The stamp is
machine-written and inside the artifact, quoted above and verified in the bytes on disk. (3) The
terms are `web.archive.org`'s and were read before the first request. (4) `ark check` passes after
the ingest.

**Why a 14.2% held-fraction was worth fetching at all**, since the pre-download screen would
normally kill it: the value of a list is `held x P(missing the artifact's year)`, and a broker's
inventory is tail names the store only ever saw once, so the second factor came in at 75.6% against
the population average of 0.611 for `com`. **Screen on the product, not on held alone.** The
for-sale held-fraction band is now measured three times and is narrow: 0.99% (hand-typed hobbyist
inventory), 14.2% (this), 32.0% (domainsww).

### jeb_bush_gubernatorial_email / dated_directory

- measured 2026-08-31 against the live store, before the ingest, and independently reproduced by the
  split to within one pair: 472,949 message-lane rows over **505,927 in-window messages** (1996 26,
  1997 52, 1998 96, 1999 40,390, 2000 187,380, 2001 245,005), 57,934 distinct registrable domains,
  73,546 (domain, year) rows, **distinct-domain held fraction 90.8% (52,625)**. **Net-new post-split
  5,692 pairs / 3,546.1 EE**, by year 1996 10 / 1997 9 / 1998 10 / 1999 216 / 2000 942 / **2001
  4,505**, mean weight 0.6231, `com` 3,978 pairs 2,514.5 EE, `org` 778 / 552.5, `net` 519 / 235.1,
  then `us`, `gov`, `edu`, `uk`, `ca`, `cc`, `au`. The wide-pattern reading gives 3,746.9 EE;
  **quote 3,546.1, not that**, and the 200.8 EE difference is fabrication, not caution, see below.
  Adjacent-year check as CLAUDE.md requires: **4,734 of 5,692 pairs (83.2%) sit on a domain already
  held at Y-1 or Y+1**, 77.1% at Y-1 specifically, so this is not the contaminated held-any-year
  shape. 0.00701 EE per in-window message, against 0.0067 for Enron: **the two mailbox shapes pay
  the same order per message and there is no inbound premium**
- what dates one item: the message block's own unindented `Sent:` line, `Sent:\tMonday, December 4,
  2000 12:38 AM` immediately under `From:\tGloria Rinaman <gloria@rinaman.com>`, written by the
  sending mail client into the export and not typed by a correspondent. Identical basis and identical
  evidence type to the banked `enron_email`. Rule 6: each row carries its own message's year, so a
  domain seen in 1999 and 2001 earns both and a domain seen once earns one
- the artifact: `https://archive.org/download/JebBushEmails/JebBushEmails-Text.7z`, 411,928,998
  bytes, sha256 `821e796f7d9dcd0a5bcb08eaf70760d50f5296481f2175ac4ed45b3301f41f75`, one solid LZMA
  block, 626 files, 3,614,550,412 B uncompressed. Item `JebBushEmails`, publicdate 2015-08-16. Only
  the 154 files named `1999*`, `2000*`, `2001*` matter: they hold 504,439 of the 505,927 in-window
  messages, and the other 472 contribute 1,488 between them
- terms: **the item carries no licence statement**, `licenseurl` and `rights` both absent from its
  metadata, which is on disk at `data/raw/jeb_bush/item_metadata.json`. `archive.org/robots.txt` was
  read in full before the first request, 238 B, `Disallow: /control/` and `/report/` only, no
  ClaudeBot group, and is kept beside it; the two `ia*.us.archive.org` download hosts and the
  `dn760104.eu` redirect target all 404 for robots.txt. The underlying records are Florida public
  records the officeholder released himself in 2015
- the NAME is what the split guards, not the date: a person typed most of these addresses, at a
  measured typo upper bound of 56.1% over 1,500 sampled net-new names, and
  `%20fh@fredomhouse.org` in `2001a_Jan-Jun_GovernF-NRN2.txt#L35425` is a real scoring row. It
  cannot happen in `From:`, which the sending client wrote
- **only the host is stored, never the mailbox.** These are public records naming private citizens,
  the local part is of no use to the score, and the extractor's capture group is the host alone
- ingest specs: `jeb_mail_dated` and `jeb_mail_candidates`. Journals at
  `data/raw/jeb_bush/jeb_mail_{dated,candidates}.jsonl.gz`, regenerable from the artifact with
  `scripts/sources/mail_corpora/parse_jeb_mail.py` then `scripts/sources/mail_corpora/split_jeb_mail.py --write`
- **banked 2026-08-31**: the loader assigned `year_rows: 5692` out of 67,972 evidence rows over
  52,625 domains, which is the split's net-new count to the pair, so **3,546.1 EE** is what this
  ingest added and not an estimate. `ark check` all 13 PASS afterwards
- potential: 71
- admitted under the standing rule of 2026-08-29 (Ivo)

Decision: master

Conditions checked one at a time. (1) `dated_directory` is already master-eligible and
`enron_email` holds it for a released mailbox dated on its own `Sent:` line, so no class is being
invented and no reading is widened. (2) The stamp is machine-written by the sending client and
inside the artifact, quoted above. (4) `ark check` passes after the ingest.

**(3) is the condition worth writing down, because the finding parked on it.** The item has no
licence and no rights field, and the question is whether "the terms permit it" can be satisfied by
an absence. It is satisfied here by the terms that do exist and were read in full first, namely
`archive.org`'s, and the repo has already answered this twice on the same host: `scene_nfo_archives`
was fetched, priced and rejected **on yield alone** with its licence recorded as "none found", and
the banked Usenet family sits on items whose `licenseurl` and `rights` are both null. Absence of a
per-item licence is not a prohibition, which is the distinction the `.nz` and `.uk` port-43 episodes
turn on: there the terms said no, in the registry's own words, and were missed by a reader that
stopped early. **One line reverses this if Ivo reads condition 3 more strictly**, and the ingest is
a re-run of two named scripts.

**The hypothesis behind this source is refuted with the sign reversed, and that is the transferable
result.** The claim was that inbound public mail beats outbound official mail, the correspondents
being "citizens, small businesses, schools and local associations". Measured on the same 505,927
messages, `From:` pays **1,235.4 EE against 1,410.3 EE for `To:`/`Cc:`, 12.4% less**. The mechanism
is that **the public does not own domains**: over 480,657 `From:` occurrences the top twelve
registrable domains are 62.2% of the traffic and nine are consumer ISPs, aol.com alone 25.37%,
while the `To:`/`Cc:` top twelve is 67.8% and institutional (fl.us 17.31%, myflorida.com 13.31%,
senate.gov 5.40%). A citizen mailing the governor contributes a mailbox at AOL, not a host. So the
screen for any mailbox corpus is one grep: **count address occurrences by registrable domain and
read the top-twelve share before pricing anything.**

**A week unbanked cost 264 EE.** The same corpus measured 4,011 EE on 2026-08-24 and 3,746.9 EE
today on the comparable wide basis, 6.6% absorbed by the store's own growth, and no URL was recorded
either time. That is Ivo's link rule of 2026-08-31 paid for in cash.

### nypw_timemaps_nonok / cdx_timestamp

The non-200 lane of the THIRTY-FOUR `nypw_timemaps` partitions already in the store. Since it was
written, `_parse_nypw` has counted every row whose status is not 200 into `stats["non_200"]` and
thrown it away, so **no measurement in this project had ever looked at one**. The lane is
**6,374,276 in-window rows, 12.8% of the corpus**, and reading it costs no archive request: the
`.cdx.gz` files are on disk at `data/raw/nypw_timemaps/`.

- artifact and LINK: item `https://archive.org/details/nypw_timemaps`, the same thirty-four
  partitions already linked one by one in the `nypw_timemaps` entry above and in
  `docs/sources.md`. No new bytes were fetched for this; the flattened `.cdx.gz` are the same
  files `ark ingest nypw_timemaps` read
- **what dates one item: field 3 of the CDX row, the crawler's own 14-digit capture stamp.**
  Verbatim, from `data/raw/nypw_timemaps/nypw_timemaps1998_rootURLs_part06r.cdx.gz`:

      https://hmcfunding.com/ com,hmcfunding)/ 20010309022603 http://www.hmcfunding.com:80/ text/html 302 YSRUTJQPTYE6V4XUYSDKZYOE7SGNOZCU 384

  `20010309022603` is written by IA's crawler, not by a person, and it is inside the artifact.
  The store held `hmcfunding.com` at 1998, 1999 and 2000 and lacked 2001, so this row is the
  adjacent-year screen paying in one line
- **why a 302 dates the year as well as a 200 does, which is the only real question here.** The
  status field records what the crawler received. A three-digit HTTP code means the hostname
  resolved, a TCP connection was accepted and a server returned a status line at the stamped
  instant, and that chain requires the name delegated in its zone. The code describes the
  RESOURCE, not the registration, so a 302 on a host is exactly as much proof of delegation as a
  200 on it. **This is the same evidence class on the same bytes, not a widened reading**: no new
  class is invented and `cdx_timestamp` is unchanged. Checked rather than assumed: every status in
  all 34 partitions is a three-digit code, with no `-` or `0` placeholder rows, so there is no
  no-response row in the corpus that could sneak in. The parser guards for one anyway
- **measured net-new post-split against the LIVE STORE, 2026-09-01, not projected:** 6,374,276
  non-200 rows collapse to 444,308 distinct (registrable domain, year) pairs, of which 431,031 are
  already held and **13,277 are net-new, worth 6,679.7 EE**. Nothing in a CDX row was typed by a
  human, so pre-split equals post-split. By assigned year: 1998 6, 1999 111, 2000 360,
  **2001 12,800**, so 96.4% of the yield is a 2001 year. Top TLDs by pair: `com` 7,757, `de` 896,
  `org` 717, `net` 564, `br` 297. The fleet probe on two 1998 partitions projected 6,540 to 7,276
  and the full corpus came in at 6,680, inside that interval
- **the 2001-threshold law reproducing itself inside a new dimension.** A non-200 row adds nothing
  in a year the store already covers and adds real pairs at 2001, which is why 96.4% of the yield
  sits there. The transferable method is the other half: **to test "we filtered X away", re-parse
  an artifact already ingested rather than querying anything.** Ingesting the 200 lane first makes
  the store the control group, so every pair the relaxed parser finds is attributable to the
  relaxation alone
- terms, read in full before the first request: unchanged from the `nypw_timemaps` entry above,
  CC BY 4.0 stated in the item's own `nypw_timemaps_readme.txt`. `archive.org/robots.txt` is 238
  bytes whole and disallows only `/control/` and `/report/`, with no Claude or Anthropic group.
  This ingest makes no request at all
- ingest specs: `nypw_timemaps_nonok`, over `data/raw/nypw_timemaps/*.cdx.gz`. Ledgered under its
  own `source_name`, so the same files ingest again without disturbing the 200 lane's rows
- **banked 2026-09-01**: the loader assigned `year_rows` totalling **13,277** over the 34 files,
  out of 6,374,276 records and 444,308 evidence rows, so **6,679.7 EE** at mean weight 0.5031 is
  what this ingest added and not an estimate. `ark check` PASSED afterwards. **The pre-ingest
  price and the banked figure agree to the pair here**, which is unusual and only because nothing
  else ingested in the four minutes between them; the `nypw_timemaps` entry above is the standard
  case, where the store moved underneath three successive readings
- **per-partition `year_rows` straight out of the ledger, read before believing anything about a
  partition, as the 2001-folder episode demands.** The folder law reproduces exactly: `2000` 6,962
  over 9 parts, `1999` 3,407 over 6, `1998` 2,292 over 11, `1997` 337 over 3, `1996` 279 over 4,
  and the **2001 folder 0**, alongside 0 for `1996_deeplinks_part00o`. The 24 `rootURLs` parts pay
  13,211 of the 13,277; all ten `deeplinks` parts together pay 66. Biggest single partitions:
  `2000_rootURLs_part00r` 3,500, `1999_rootURLs_part00r` 1,931, `2000_rootURLs_part04r` 1,721
- admitted under the standing rule of 2026-08-29 (Ivo)

Decision: master

Conditions checked one at a time. (1) `cdx_timestamp` is already master-eligible and this is the
same class on the same corpus, so nothing is invented. (2) The stamp is IA's crawler's own 14-digit
timestamp, machine-written, inside the artifact, quoted verbatim above. (3) CC BY 4.0, read in full
when the item was first taken, and this ingest fetches nothing. (4) `ark check` passes after the
ingest.

**The remaining open question, recorded rather than hidden.** A wildcard DNS record above a name
could in principle answer for a name nobody registered, which would make a 302 prove less than
claimed. It does not bite here: no registry wildcard existed in `.com`, `.net` or `.org` inside
1996-2001, and those three carry 68.5% of the net-new pairs. Where it could bite is a ccTLD that
wildcarded its zone, and that risk is identical for the 200 lane already banked, since a wildcard
answering 200 is no better evidence than one answering 302. **If Ivo judges the residual too high,
one line reverses this and the ingest is one `ark ingest` re-run.**

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
  `scripts/pricing/price_items.py --all-tlds` against the live store (merged260827). 18,797 listed items give
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

**Rejected in triage, split out 2026-09-03.** One row each in `sources-closed.md`; the stub keeps the rejection binding for `ark ingest` and the request generator.

### nic_mil_internic_zone_mirror / artifact_listing
Decision: rejected

### fac_sfsac_historic_1998_2001 / artifact_listing
Decision: rejected

### uk_historic_hansard / dated_directory
Decision: rejected

### usac_erate_form471_contact_email_1998_2001 / dated_directory
Decision: rejected

### eric_fulltext_1996_2001 / dated_directory
Decision: rejected

### educause_edu_whois_activation / whois_creation
Decision: rejected

### ucsf_industry_documents / dated_directory
Decision: rejected

### oireachtas_debates_xml / dated_directory
Decision: rejected

### content_filter_blacklists / artifact_listing
Decision: rejected

### nominet_whois_port43 / whois_creation
Decision: rejected

### ipgod_au_marktext / dated_directory
Decision: rejected

### cira_ca_rdap / whois_creation
Decision: rejected

### ted_ojs_notices_1996_2001 / link_source
Decision: rejected

### excite_query_logs / dated_directory
Decision: rejected

### sbir_sttr_award_pi_email_2000_2001 / dated_directory
Decision: rejected

### discmaster_by_file_size / artifact_listing
Decision: rejected

### jpnic_register / artifact_listing
Decision: rejected

### uk_gazette_addressed_notices_1998_2001 / link_source
Decision: rejected

### courtlistener_caselaw / dated_directory
Decision: rejected

### cybernot_cphack_blacklist / artifact_listing
Decision: rejected

### pmc_oa_subset_fulltext_1998_2001 / link_source
Decision: rejected

### caselaw_access_project_opinions / dated_directory
Decision: rejected

### sec_form_adv_part1_2000_2001 / artifact_listing
Decision: rejected

### uspto_trademark_case_files / artifact_listing
Decision: rejected

### dnsrf_dap_udrp_multiprovider / artifact_listing
Decision: rejected

### isi_us_domain_registry / artifact_listing
Decision: rejected

### itu_operational_bulletin_1996_2001 / link_source
Decision: rejected

### nz_dnc_zone_data / whois_creation
Decision: rejected

### scene_nfo_archives / dated_directory
Decision: rejected

### wayback_longitudinal_url_sample / cdx_timestamp
Decision: rejected

### openpgp_keyserver_dumps / link_target
Decision: rejected

### nlm_medline_affiliation_email_1996_2001 / link_source
Decision: rejected

### ffiec_call_report_webaddr / artifact_listing
Decision: rejected

### maillist_body_url_hostnames / link_source

- measured: **589.0482 EE over 1,050 net-new hostname years** against the live store on
  2026-09-04, the whole corpus read rather than sampled: 2,558 month files, 722 MB, 580,212
  messages, 578,705 dated inside 1996-2001, 230,722 carrying a body URL, 13,841 distinct
  host-years, 6,345 candidates, 4,911 already in the store and 374 in his files alone.
  **550.9372 EE past the `www.<a name already held that year>` seam** (76 rows, 38.1110 EE,
  6.5%). By year 1996 8.6 / 1997 9.8 / 1998 52.9 / 1999 108.4 / 2000 197.6 / 2001 211.7; by
  TLD com 170.7, org 133.5, edu 105.9, net 81.1. Beside it **161 parent (registrable, year)
  pairs, 77.0402 EE**, written from the same rows. The fleet's 1,496 EE was priced against the
  2026-09-03 file snapshot, before the Usenet lane put 1,064,563 hostname years into the
  store, and does not survive re-pricing; the `maillists_hostgrain` closure at 186 EE on
  2026-09-03 was a head-of-corpus sample and was wrong in the other direction
- fiction rate, 64 eligible net-new hosts drawn at seed 20260904 and judged by hand against
  the raw message: 2 invented (`a.very.long.host.name.com`, a documentation example;
  `primates.helixode.com`, a typo of helixcode.com by a poster at helixcode.com) and 1 wrong
  year (`TorresQuevedo.hispalinux.es` under `Date: Wed, 01 Jan 1997` on a message filed in the
  2000-July archive, a sender's clock), so **3/64 = 4.7%, Wilson 95% 1.6% to 12.9%**. Net of
  it the lane is about 525 EE of hostnames plus the 77 EE of pairs
- what dates one item: the message's own `Date:` header, written by the sending mail client
  and preserved verbatim by Mailman. Quoted: message 1 of
  `gnome/foundation-announce__2000-October.txt` carries `Date: Thu, 05 Oct 2000 08:13:15
  -0700` and, in its body, `http://foundation.gnome.org for the foundation's charter`, which
  dates `foundation.gnome.org` for 2000. The evidence row is `list message 2000
  gnome/foundation-announce__2000-October.txt#1 foundation.gnome.org`
- the artifact: `https://mail.gnome.org/archives/<list>/<YYYY-Month>.txt.gz`, 1,415 files
  across 89 lists, and `https://mail.python.org/pipermail/<list>/<YYYY-Month>.txt`, 1,143
  files across 43 lists, the two newsgroup-gatewayed lists skipped exactly as the registrable
  lane skips them. On disk since 2026-08-08 in `data/raw/maillists/`, and both hosts still
  serve the files by name (HEAD 200 on 2026-09-04)
- terms: public list archives with no terms page. `mail.gnome.org/robots.txt` is 404;
  `mail.python.org/robots.txt` disallows only `/*/export/` at `crawl-delay: 2`, which the
  2026-08-08 collector honoured. The same terms `maillist_archive / dated_directory` was
  admitted under in phase 4
- class: `link_source`, master-eligible, at the grain Ding accepted on 2026-09-01. The
  identical evidence shape, a host inside a URL a person typed into a dated message body, is
  `Decision: master` for `usenet_body_url_hostnames` since 2026-09-04 (C-68), and the
  registrable lane of this very corpus has been master since phase 4. If C-68 is read as
  binding Usenet alone, this is the entry to downgrade
- ingest spec: `ark ingest-maillist-hostnames data/raw/maillists_items/`, the Usenet item-shard
  ingest with a pipermail item pointer; shards built by
  `scripts/sources/mail_corpora/build_maillist_pool.py`, body URLs only
- potential: 551
- admitted under the standing rule of 2026-08-29 (Ivo)

Decision: master

## Pending requests

### usenet_body_url_hostnames / link_source

- ingest would be: `ark ingest-hostnames` over `{item, year, text}` journals rebuilt from
  `data/raw/usenet_new/` (7,531 mbox zips, 53,539,826,439 B) and `data/raw/usenet_bulk/` (9,266
  mbox zips, 56,026,437,278 B), both already on disk, both banked at registrable grain. The
  extractor takes the host authority of an explicit `http://`, `https://` or `ftp://` URL in the
  post BODY only: a `Path`, `Xref`, `NNTP-Posting-Host`, `Message-ID`, `From` or `Organization`
  host is a news relay or a mailbox and never a host serving web content
- source: https://archive.org/details/usenet-alt and
  https://archive.org/download/usenet-<hierarchy>/<group>.mbox.zip; `archive.org/robots.txt` read
  whole, only `/control/` and `/report/` disallowed
- measured 2026-09-03 and 2026-09-04 on the live store, **thirteen pools read whole and priced
  as one union, no sample and no projection anywhere**: every hierarchy of the catalogue except
  `alt`, fetched overnight with the existing polite fetcher (`uk` 495 archives, `comp` 1,205,
  `rec` 919, `soc` 341, `sci` 237, `misc` 242, `news` 60, `talk` 47, `can` 109, `biz` 95, `aus`
  195) beside `usenet_new` and `usenet_bulk`. **224 GB, 328,201,000 posts, 54,700,642 item lines
  carrying a body URL**, 2,100,957 distinct host-years, 570,272 candidates, 175,368 already in
  the store and 119,517 in his files alone: **274,354 net-new hostname years and 163,985.8408 EE
  gross**. Screens, each measured: the ADR-007 `www.` alias seam takes 57,604 rows and
  36,370.1156 EE (22.2%), leaving **127,615.7252 EE**; and a sampled fiction rate of **6.25%,
  Wilson 95% CI 2.7% to 13.8%**, giving **119,639.7424 EE central, 110,005 to 124,170**. By TLD
  com 56,825.2, edu 28,766.2, uk 18,886.1, net 16,298.0. **Density decides which hierarchy pays**,
  not size: news 2,552 EE per GB gross, comp 1,701, sci 1,413, uk 1,152, the two original pools
  851, soc 418. Cross-hierarchy saturation is 22.2%, so each one still adds four fifths of its
  standalone value
- beside it, needing no hostname decision at all: **83,708 net-new (registrable, year) pairs,
  49,007.3050 EE** across the thirteen pools, BEFORE the corroboration split every typed-name
  class takes. The split is
  known to be brutal on this class (the recorded registrable pass over `usenet_new` measured
  35.8 EE post-split), so treat that as an upper bound and not a second find
- what dates one item: the post's own `Date:` header, the same stamp the banked Usenet body
  classes use, verified against raw bytes with zero wrong-year assignments in 135,695 dated
  posts. **38.02% of them use the Google Groups `YYYY/MM/DD` form**, which
  `email.utils.parsedate_to_datetime` cannot parse, so the four-digit-year regex is deliberate
- **why this is not the pending `usenet_body_pasted_hostnames` request**: that one is hostnames
  inside `dig` answers and config snippets, and it parks because a 60-name sample of its
  survivors was ~13% invented (`mail.bogus.com` beneath a held `bogus.com`). Measured here on
  URL-vouched hosts the same class of error is 6.25%, and the fakes are typos of real hosts
  rather than examples, because a host inside a URL a human typed is a host they visited or
  advertised. The two asks can be answered differently
- the first pass of this measurement was **wrong and is worth reading before trusting the
  second**: the post-boundary regex missed the negative Google Groups ids, so half the posts
  went unrecognised and their headers spilled into the previous body, and the two pools were
  summed rather than unioned. Four verifiers found it; the entry in `sources.md` names the
  defect and the fix. Nothing was ingested from the flawed shards
- condition 1 of the standing rule fails, which is why this is pending rather than banked: no
  master-eligible class covers a human-typed URL's host at hostname grain, and the reviewer's
  2026-09-01 update lists dated Usenet copies among sources unsuitable for further work. The
  corroboration split guards the registrable half and cannot guard this half, so the sampled
  fiction rate above is offered in its place. Conditions 2, 3 and 4 hold: the stamp is
  machine-written and quoted, the terms are archive.org's, and the journals are on disk: the 224
  GB of archives was deleted after pricing because archive.org serves them again by name, and the
  thirteen `data/raw/usenet_*_items` directories hold the `{item, year, text}` shards a yes would
  be ingested from at four workers
- potential: 119640

Decision: master

Approved by Ivo on 2026-09-04. Thirteen pools read whole rather than sampled, the fiction
rate measured on a sample and quoted with its interval, and the same body-only extraction
the banked Usenet classes already use.

### arin_inaddr_ns_hostnames / artifact_listing

- the fleet's probe (2026-09-02, `inaddr_reverse_tree_ns_hostnames_1997_1999`): APNIC's tar of
  its own BIND slave directory holding ARIN's twelve in-addr.arpa /8 zones,
  https://ftp.apnic.net/apnic/arin/arin.zones.tar.gz (405,696 B, directory mtime 1999-02-03,
  `ftp.apnic.net/robots.txt` is a 404), read whole: 194,400 NS records, 8,805 distinct
  nameserver hostnames, all valid, under 5,591 registrables of which 5,412 (96.8%) are held at 1999
- measured by the fleet against the ark-data sync of 2026-09-02 01:09:45, NOT re-priced on the
  live store (the bytes were deleted with the run): **7,232 novel (hostname, 1999) records absent
  from the store and the reviewer's 1999 file, 4,543.3 EE, plus 179 unheld parents at registrable
  grain, 112.2 EE: 4,655.5 EE**. By TLD com 2,008.8, net 914.2, ca 519.5, edu 357.6, us 201.9. The
  names are the operator estate (`ns1.`, `dns.`, `gw.` hosts of every organisation delegated a
  reverse block), only 6.7% verbatim in his 1999 file because a web crawl never fetches a
  nameserver. Re-priced at 1998 on the SOA serial instead: 7,499 novel, 4,679.2 EE, an alternative
  reading and never both. The 1997 InterNIC remainder (`mil`, `root`, `arpa` zones) adds 2.9 EE
  over `zone_ns_glue_hostnames` and is closed
- what dates one item: BIND 8's own transfer comment at the head of each zone member,
  `; from 192.149.252.21   at Thu Jan  7 12:18:51 1999`, written by `named` when the AXFR
  completed (eleven stamps, all 1999-01-07 12:18 to 12:37), with SOA serial `1998111700` in every
  zone and tar member mtimes 1999-02-02: the nameserver named in the zone was delegated-to on that
  day, year 1999, class `artifact_listing`, the class decided master for zone bytes on 2026-08-24
- **condition 3 of the standing rule fails: the terms are not held.** The tarball is ARIN's data on
  APNIC's host and carries no notice of its own; APNIC's bulk-access AUP (register line 904 read it
  as permitting "Internet research and analysis") covers `/apnic/whois/`, not `/apnic/arin/`, and
  two guesses at APNIC's website terms URL were 404. Conditions 1, 2 and 4 would hold: the class is
  master for zone files, the stamp is quoted above, and the ingest is one `{url, timestamp}`-shaped
  journal away from `ark ingest-hostnames`. Register line 904 closed the same file at 99.7 EE on the
  registrable grain and left the terms unread because that figure did not justify it; 4,655 EE
  does. What settles it is one mail to the APNIC helpdesk, or ARIN's own position on
  redistribution of historical in-addr zone data (ARIN publishes the current zones openly). Nothing
  else on that host: the directory has been frozen since 1999, one file
- potential: 4656

Decision: pending

### usenet_body_pasted_hostnames / link_source

- the fleet's probe (2026-09-02, `usenet_pasted_machine_blocks_hostname_grain`): FQDNs inside the
  BODY of archive.org Usenet mbox exports, headers skipped, in `dig` and `nslookup` answers, zone
  and config snippets, signatures and log excerpts, at hostname grain. Artifacts
  https://archive.org/download/usenet-comp/comp.protocols.dns.bind.mbox.zip (67,183,510 B, 103,050
  messages, 45,344 in window) and `comp.dcom.sys.cisco.mbox.zip` (108,989,162 B, 34,231 in window,
  with a 1997-1999 hole in the copy); `archive.org/robots.txt` read whole
- measured by the fleet against the ark-data sync of 2026-09-02 01:09:45, NOT re-priced on the
  live store (zips deleted with the run): bind group, 19,711 (host, year) rows over 7,835 distinct
  registrables, 81.6% of parents held at the post year, 15,165 rows with the parent held AND the
  hostname absent from the store and the reviewer's file, 8,939.0 EE gross; a placeholder-label
  screen (example, domain, foo, acme, bogus and kin) removes 2,844 rows, leaving 12,321 rows and
  7,157.4 EE, and a 60-name sample of the survivors still holds ~13% fictitious config examples
  (`foohost.foobar.com`, `mail.bogus.com`, `ns-2.domainb.net`), so **the quotable figure is ~6,200
  EE for the one group**, of which the machine-answer lane (`dig`/`nslookup` output, 6,744 rows)
  is 2,477.0 EE and the human-pasted lane (config, signatures, logs) 4,651.1 EE. The cisco group
  paid 300.1 EE gross: yield is group-specific by 22x and follows the density of `IN (NS|A|MX)`
  lines. The traceroute lane the hypothesis led with is under 30 EE per group
- what dates one item: the post's own `Date:` header, the stamp the approved Usenet body classes
  use, with the hostname riding the corroboration split on its held parent
- **condition 1 of the standing rule fails: no master-eligible class covers a human-pasted hostname
  at hostname grain.** The banked Usenet body classes (`usenet_address`, `usenet_announce`,
  `usenet_bare`) date REGISTRABLES a human typed, and there the corroboration split is what guards
  against fiction and typos: a name nobody else has dated earns no year. At hostname grain the
  split cannot do that job, because `mail.bogus.com` passes on `bogus.com` being held while
  `mail.bogus.com` never existed, and the fleet measured ~13% such names among the survivors of
  its screen. Reading the split as satisfied by the parent is a new reading Ivo has not made, and
  the reviewer's 2026-09-01 update lists dated Usenet copies among sources unsuitable for further
  work. Condition 4 also fails: no journal exists. The `dig`/`nslookup` lane is machine-written
  output a human pasted, and could be put to him separately at 2,477 EE if he rules the body
  lane out
- potential: 6200

Decision: pending

### dartmouth_nber_arcs_hostnames / cdx_timestamp

- the fleet's probe (2026-09-02, `dartmouth_captures_hostname_grain`): the 282 public per-item
  aggregate ZipNum indexes `DARTMOUTH-NBER-RESEARCH-2017-ARCS-*.cdx.gz` (~105-120 MB each, 30 GB
  together) and their ~105 per-ARC `*.arc.os.cdx.gz` members, read at hostname grain. The
  registrable-grain census (`dartmouth_nber_captures`, `domain-year-captures.txt`) is fully
  banked and has no hostname column: 0 of 277,011 sampled rows begin `www.`, so arm 1 is zero by
  construction
- measured by the fleet, NOT banked: 57 items sampled at one 256 KB Range slice each (15 MB for
  30 GB), 4,809 in-window rows, 467 host-years; at 2001, 120 novel hosts beneath held parents out
  of 235 proper hosts (0.453 per registrable-year), all `.com`; 1998-2000 pooled 40 novel out of
  108 (0.32). Projection from the banked census's 309,721 registrable-years at 2001 and 455,473
  at 1996-2000: ~88,700 EE at 2001, ~92,000 at 1996-2000, labelled a small-sample projection
  from one alphabetic band per item (the aggregates are URL-key sorted). The measured sample
  itself is worth under 100 EE and its bytes were deleted with the run
- what dates one item: field 2 of the CDX row, the archive's own 14-digit capture timestamp,
  `cdx_timestamp`, identical to what dates the banked `dartmouth_nber_captures` rows
- artifact: https://archive.org/details/DARTMOUTH-NBER-RESEARCH-2017-ARCS-20170721000000-00333-00333
  and siblings; the single 25.6 GB `arcs-cdx.tar` and every `.arc.gz` payload return 401, every
  `<item>.cdx.idx` is `private: true`, and the WARC half is 2011-2017 only
- **condition 4 of the standing rule cannot be evaluated: nothing has been ingested.** Conditions
  1 to 3 hold (approved class, machine stamp, archive.org public download with robots.txt read
  whole), but the admission needs a collector on the VPS first: scout ~40 candidate items with one
  per-ARC index each, pull the in-window ARC indexes whole (~2,000 of 26,095, ~2-3 GB), write
  `{url, timestamp}` journals, then `ark ingest-hostnames`. Re-sample two more offsets on items
  00333 and 02693 before committing the collector, to rule out an alphabetic-band artifact. No
  approval issue is filed: the measured figure is under 1,000 EE and the projection needs a
  collector, not a decision
- potential: 88700

Decision: pending



### internic_zone_hostnames_1999 / artifact_listing

- the same census over the two 1999 zones already on disk, `data/raw/internic_zones/edu.zone.19991120.gz`
  (SOA serial `1999112000`) and `gov.zone.19991119.gz` (serial `1999111901`), fetched 2026-08-25 from
  `https://tomocha.net/files/dns/` and ingested at registrable grain as `internic_zone` (179.8 EE)
- measured: 4,678.2 net-new EE over 6,650 (hostname, 1999) records, on the live store 2026-09-02:
  7,252 distinct hostnames, 257 already in `hostname_year` at 1999, 478 in the reviewer's 1999 file,
  7,131 (98.3%) with the parent held at 1999. edu 2,330 / 2,264.1 EE, com 1,460 / 922.9, net 1,814 /
  821.7, gov 315 / 309.5. Largest parent `pair.com` with 21 hosts
- what dates one item: the SOA serial inside each file, `EDU. IN SOA A.ROOT-SERVERS.NET.
  hostmaster.internic.net. ( 1999112000 ;serial`, the same argument as the 1997 lane
- **condition 3 of the standing rule fails, terms.** Two facts, both already in the register and
  neither decided: `tomocha.net/robots.txt` names ClaudeBot `Disallow: /` (lines 51-52 of 61) and
  register line 935 records the refusal as applied to `jpnic_register` but not to these two files,
  "raised for Ivo rather than decided"; and the 1999 `edu` file itself opens with Network Solutions'
  own notice that use of its zone data "is subject to the restrictions described in the access
  Agreement with Network Solutions", which this project does not hold. The 1997 files carry no such
  clause. Nothing is fetched by deciding either way, the bytes are on disk; the code refuses these
  files under the 1997 approval by design (`ingest_zone_hostnames` gates each zone year by name)
- potential: 4678

Decision: pending

### usenet_header_fqdn_hostnames / link_source

- the fleet's probe (2026-09-02, `usenet_header_fqdn_census`): server-written header fields in the
  archive.org Usenet mbox exports, `X-Trace:` trailing customer host, `NNTP-Posting-Host:` and the
  final `Path:` hop, read at hostname grain. Artifacts https://archive.org/download/usenet-demon/
  (58 zips) and https://archive.org/download/usenet-uk/ (495 zips), both already on the VPS under
  `data/raw/usenet_*`
- measured by the fleet, NOT re-priced here: **2,368 EE over 2,413 demon.co.uk customer host-years
  1996-2001** from two demon.* groups (28 MB), 99.1% absent from the CDX demon.co.uk sweep in the
  same year; projection 20,000 to 25,000 EE for demon.* and six figures spool-wide, unmeasured. The
  probe's per-message table was deleted with the run and the bytes are not on this machine, so the
  live-store figure is not available and the fleet's must not be banked as a claim
- second fleet probe, 2026-09-02, over 55.3 MB (`demon.ip.support.pc` and `.newuser`, 72,172
  messages), against the ark-data sync of 2026-09-01: **6,877 EE over 7,186 stable hostname-years**,
  `uk` 6,671.8 of it, of which **2,823 EE is bounded by the three server-written fields** (X-Trace
  2,394.4, Path hop 220.5, NNTP-Posting-Host 208.4) and **4,054 EE more comes from the `Message-ID`
  host**, which Turnpike and Demon's clients stamp from the configured nodename, so it is
  client-written and needs its own class reading before it counts at all. Ephemeral pool shapes
  are 6.9% of the novel rows and were excluded. The seam is 1996-1998 (2,658 / 1,111 / 1,557 `uk`
  hosts), not 2001: the baseline's Demon hostnames are the crawled `www.*` population, the Usenet
  nodenames are a different population under the same registrable. Honest band for demon.* is
  20,000 to 60,000 EE, the uk.* hierarchy unmeasured on top. Also not re-priced on the live store,
  same reason
- what dates one item: the message's own `Date:` header, with the hostname written by the
  injecting server, `X-Trace: mail2news.demon.co.uk 894324354 19133 faqs pcserv.demon.co.uk`
- **conditions 1 and 4 fail.** Condition 1: no master-eligible class covers a server-written
  Usenet header hostname; the banked Usenet classes (`maillist_dated`, `enron_dated`, the whois
  paste) are `link_source` taken WITH the corroboration split, and the fleet's reading that the
  split does not apply because a server wrote the field is a new reading Ivo has not made. Condition
  4: no journal exists, the census is a whole-spool pass on the VPS that has not run, so no ingest
  can be checked. And the reviewer's own 2026-09-01 update lists "dated Usenet archive copies"
  among sources unsuitable for further work (register line 781); the fleet recommends putting the
  hostname-grain figure to Ding before any spool-wide pass, and that is his call, not the loop's.
  The second probe does not move either condition: it widens the ask to two rulings, whether a
  server-written header host is split-free `link_source`, and separately whether a client-written
  `Message-ID` host is evidence at all. Issue 2 on ark-fleet carries the block
- third fleet probe, 2026-09-02 (`usenet_uk_and_edu_header_fqdns`), on a second ISP population:
  `uk.comp.os.win95.mbox.zip` and `uk.comp.misc.mbox.zip` from https://archive.org/download/usenet-uk/
  (27.7 and 28.0 MB, 121,038 messages), headers only, against the ark-data sync of 2026-09-02:
  **3,662 novel stable server-written (hostname, year) pairs, 2,537.3 EE** as a union of the two
  groups (uk 1,265.9, com 583.4, net 394.1; 2001 1,033.8), the second group retaining 73% of the
  first's yield; Message-ID priced separately at 134 and 293 EE and excluded. A tighter pool-shape
  filter would shrink the stable figure 10 to 15%. The `.edu` lane (`comp.sys.sun.wanted`) is
  1,433.2 EE of which only 216.7 is `.edu`, mostly news server names that saturate within tens of
  groups. Honest band for the 495-zip uk.* hierarchy 50,000 to 150,000 EE, a labelled guess. Same
  two conditions still fail; not re-priced on the live store; no new issue, issue 2 stands
- potential: 6877

Decision: pending


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

Emptied on 2026-09-03 by `scripts/round/split_triage.py`: decided blocks moved to Decided above, rejected ones to `sources-closed.md` behind a stub, open hypotheses to `hypotheses-pending.md`. New finds land here as `### key / etype` blocks carrying a `- potential:` line and a pending decision; `just triage-rank` sorts them.

