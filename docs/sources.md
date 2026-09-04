# Sources

One entry per source: what it is, where to obtain it, and **what fixes one item to one year**. That
last clause is the whole of the evidence argument, so it is stated per source rather than in a
preamble, and a source with no per-item date is not admitted whatever else it offers.

Paths are relative to the repository root. Every ingest command assumes the file has been placed at
the path shown.

Sources evaluated and closed have their own page, [sources-closed.md](sources-closed.md), each with
the single measurement that closed it, so the same ground is not broken twice. Grep both before
proposing a lens. [discovery.md](discovery.md) is the method used to price one before
building a collector.

**Where a figure appears below it is the measurement a source was admitted or rejected on, at the
date given, not a current count.** A source re-measured later against a larger store reads lower, so
the two are different quantities and both are kept. The authoritative current counts are in
`audit/source_contribution.csv`, which `ark export` rewrites from the store on every run and whose
`netnew_pairs` column sums to the report's headline increment. A hand-copied snapshot once lived here
claiming to be generated, and by the time anyone checked it had omitted the round's largest
contributor entirely.

---

## `prior_task`: the supplied baseline

The six annual files supplied with the task, 8,224,963 hostname lines. In the delivery archive at
`baseline/original/`; the baseline additions are scored against sits at `baseline/<release>/`, named
by `CURRENT_BASELINE_MARKER` in `src/ark/baseline.py`.

```bash
cp -R <archive>/baseline/original legacy-data
uv run ark ingest-legacy --legacy-dir legacy-data --marker-prefix original
```

Both flags are required, or the six files are skipped as already ingested.

**Dating: the file a line appears in is its year. No inference.**

`prior_reused`. Excluded from the scored metric, being baseline rather than addition.

---

## `isc_survey`: Internet Domain Survey host lists

The Network Wizards / ISC twice-yearly DNS walk: five intact `.domains` lists for 1996-1997 plus 583
per-TLD host files. ISC's own copies fail their gzip integrity check, so these come from a 1996
Wayback crawl of `nw.com` and the survey author's live site.

```bash
mkdir -p data/raw/isc_survey && cd data/raw/isc_survey
curl -O http://web.archive.org/web/19961112163532id_/http://nw.com:80/zone/9507.domains.gz
curl -O http://web.archive.org/web/19961112163635id_/http://nw.com:80/zone/9601.domains.gz
curl -O http://web.archive.org/web/19961112163826id_/http://nw.com:80/zone/9607.domains.gz
curl -O http://3waylabs.com/zone/9707.domains.gz
cd - && uv run ark ingest isc_survey data/raw/isc_survey/*.gz
```

```bash
uv run python scripts/sources/directories/fetch_nw_host_files.py   # resumable, three connections, ~2h for 116 MB
uv run ark ingest isc_survey data/raw/isc_survey/*.gz
```

**Dating: the survey date is the `YYMM` code in the filename (`9607` = July 1996), and every host in
that file was observed in DNS on that date, so the file's provenance fixes the year for all of its
lines.**

`artifact_listing`. 42,299 net-new pairs, **14,956.3877 equivalent-English**, in the two years the
Internet Archive cannot supply in bulk: **the best 1996-1997 source in the project.** Hard caps: no
`com.gz` and no `edu.gz` in any edition, and the `.domains` lists stop at 9707.

---

## `afnic_fr`: `.fr` registry open data

The monthly `.fr` open-data file, one row per domain. Open licence, attribution only.

```bash
mkdir -p data/raw/afnic && cd data/raw/afnic
# from https://opendata.afnic.fr/ download the current "A" file (Noms de domaine en .fr)
unzip '*_OPENDATA_A.zip'
cd - && uv run ark ingest afnic_fr data/raw/afnic/*NomsDeDomaineEnPointFr.csv
```

**Dating: the row's registry-written creation date and permanent-deletion date (blank while
registered). AFNIC's Technical Integration Guide v3.0 (27 February 2015) states `<domain:crDate>` is
"the last creation date of the domain name" or the date of the last transmission, and both events
fall after any prior deletion, so `[crDate, deletion-or-now]` contains no deletion event: it is
continuous by construction.**
<https://www.afnic.fr/medias/documents/technique/integration-guide-en-2015-02-27.pdf>

`whois_creation`, master for every in-window year the interval covers; each row stores its interval
verbatim (`registered 16-03-1999..active`).

`crDate` can only be later than the true first registration, so the tranche undercounts and cannot
overcount. Omits names deleted before 28 January 2014. Republished monthly, so unpinnable; this
delivery used the June 2026 edition.

---

## `ukwa_link_source` and `ukwa_link_target`: UK Web Archive host link graph

The JISC UK Web Domain Dataset host link graph 1996-2010, rows of
`year|source_host|target_host<TAB>count`. Wayback only: the original address answers HTTP 200 with a
159-byte stub and the DOI is dead. The archived stream drops partway, giving 2 GiB of the advertised
20.9 GB.

**The file is not year-sorted.** The year column decreases 14 times, so it is 15 concatenated shards
each sorted internally, with **2,468,674** in-window rows spread across all of them; a parser must
not stop at the first post-2001 row.

```bash
mkdir -p data/raw/ukwa && cd data/raw/ukwa
curl -L -o host-linkage.tsv.gz \
  "https://web.archive.org/web/2019id_/https://www.webarchive.org.uk/datasets/ukwa.ds.2/linkage/host-linkage.tsv.gz"
cd -
uv run ark ingest ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz
uv run ark ingest ukwa_link_target data/raw/ukwa/host-linkage.tsv.gz
```

**Dating: the year column of each row, the crawl year that observed the link.**

The source host was crawled successfully that year to produce the row, so `link_source` is
master-eligible; the target was merely linked to, so `link_target` is candidate-only. One file,
ingested twice. `.uk`-weighted.

---

## `arquivo_ia` and `arquivo_roteiro`: Arquivo.pt capture indexes

Two CDXJ indexes from the Portuguese web archive: `IA.cdxj`, 47 GB donated by the Internet Archive,
covering 1996-2007, and the smaller early-Portuguese-web `Roteiro.cdxj`.

```bash
mkdir -p data/raw/arquivo && cd data/raw/arquivo
curl -C - -O https://arquivo.pt/datasets/cdxj/IA.cdxj
curl -C - -O https://arquivo.pt/datasets/cdxj/Roteiro.cdxj
cd -
uv run ark ingest arquivo_ia data/raw/arquivo/IA.cdxj
uv run ark ingest arquivo_roteiro data/raw/arquivo/Roteiro.cdxj
```

**Dating: the 14-digit crawler-written capture timestamp on each line.**

`cdx_timestamp`, a capture with an in-year timestamp and HTTP 200. Portuguese-web weighted; skipping
both costs 17,696 pairs over 7,001 domains.

---

## `odp`: Open Directory Project (DMOZ) RDF content dumps

Three surviving dumps: a truncated prefix of the August 2000 full dump and two complete 2001
Kids-and-Teens dumps. The live URLs serve a stub, so these come from Wayback.

```bash
curl -s "https://web.archive.org/cdx/search/cdx?url=dmoz.org/rdf/*&from=2000&to=2001&filter=statuscode:200&fl=timestamp,original"
mkdir -p data/raw/odp
# then, for each capture of interest:
curl -o data/raw/odp/c2000.gz "https://web.archive.org/web/<timestamp>id_/http://dmoz.org/rdf/content.rdf.u8.gz"
uv run ark ingest odp data/raw/odp/*.gz
```

**Dating: the dump's own generation stamp, corroborated by the Wayback capture timestamp and the
filename (`c2000` = 2000, `kt200106` = June 2001).**

`artifact_listing`: a dated data file, not an undated directory page, so every catalogued external
URL inside it is a line in that file and the file's date fixes the year.

The August 2000 full dump is unrecoverable, Wayback holding only that year's `structure.rdf`, which
carries no external links. The 2001 full content dumps are not retrievable.

---

## `early_web_cdx`: Internet Archive Early Web CDX dataset

A published CDX dataset of early-web captures, 224 gzipped index files.

```bash
uvx --from internetarchive ia download early-web_cdx-lang-cdxa \
    --glob='*.cdx.gz' --destdir=data/raw/early_web --no-directories
uv run ark ingest early_web data/raw/early_web/*.cdx.gz
```

Item: <https://archive.org/details/early-web_cdx-lang-cdxa>

**Dating: the 14-digit capture timestamp on each line.**

`cdx_timestamp`. It overlaps the supplied baseline almost completely, itself derived from the same
archive, so its 2.28M evidence rows serve as corroboration.

---


## The hostname purpose rule, 2026-09-02

The reviewer's acceptance of hostnames (2026-09-01) says why he wants them: "our downstream objective
is to retrieve historical webpages as completely as possible", a domain-wide CDX query "can expose
many subdomain websites", and his three examples are sites. A first build counted every valid
hostname with a dated observation and 67% of its EE was names that pass that letter and serve the
purpose nothing. Two conditions were added, enforced at ingest and by the invariants
`hostname_observed_serving_web` and `hostname_is_not_the_parent_www`:

- **the observation must show the host serving web content**: a capture of a URL on it or a URL
  listing naming it. Lanes: `ia_cdx_hostnames`, `early_web_cdx_hostnames`,
  `usfedgov_extract_hostnames`, `squidguard_2001_hostnames`, `chastity_list_hostnames`. A DNS listing
  (ISC reverse walk, RIPE `nserver:`, InterNIC NS target) dates the parent and writes no hostname row;
- **`www.<parent>` is not a record**: it is the registrable's own site and its capture dates the
  registrable, which the ingest already did.

`scripts/round/apply_hostname_purpose_rule.py` applied both to the store as first built: 28,069,111
hostname rows, 23,381,935 removed (18,219,285 DNS-listed across the three lanes, 5,162,650
`www.<parent>` across five), 4,687,176 kept, evidence untouched. The corresponding shipped figures
before the rule were 25,598,889 hostname records and 13,340,945.6 EE against `merged260901`; after
it, and against `merged260902`, the round ships 1,917,606 hostname records and 1,129,415.6336 EE
(IA domain sweeps 956,099; NYPW 70,937; Early Web 65,026; USFEDGOV 34,726; the two URL blocklists
2,628), beside 623,823 registrables and 328,847.5752 EE.

The reviewer's 0902 brief, received the same day, says that a domain-wide query may return the base
hostname and every qualifying subdomain and that overlap is removed downstream. The `www.<parent>`
hold-out is therefore narrower than his text, disclosed as such in the report, and the rows are
recoverable from the kept evidence with one filter.

## `ia_cdx_hostnames`: hostname records from Wayback CDX domain sweeps

The second output unit, accepted by the reviewer on 2026-09-01 (his reply, verbatim, in
`private/personal-context.md`): hostnames are annual records beside registrables, which
stay prioritized. Same endpoint as `ia_cdx_bulk`, <https://web.archive.org/cdx/search/cdx>,
queried with `matchType=domain` per platform parent by `scripts/engines/cdx_suffix_sweep.py`;
what dates one item is the row's own 14-digit capture timestamp (`cdx_timestamp`), quoted in
the evidence value beside the hostname. `ark ingest-hostnames` fills `hostname_year`; the
registrable half of the same journal enters via `cdx_suffix_convert.py` as before. The 180
raw suffix journals of 2026-08-21..24 (`data/raw/cdx_suffix/`, 46.8M capture rows), recorded
then as "worth exactly 0" under the registrable unit, are the first corpus in: the unit
change repriced bytes already on disk. Exports: `output/netnew/NNNN_hostnames.txt` per year
plus `hostnames_evidence_manifest.csv`. Admitted under the standing rule of 2026-08-29;
Decision block in `docs/approved-sources-list.md`.

### The same journals at hostname grain

Any corpus of raw capture rows this project already holds re-prices under the hostname
unit, because the registrable ingest collapsed the host and the hostname ingest keeps it.
Measured 2026-09-01, all against the merged260901 baseline files and scored with the
reviewer's own calculator (zero invalid records): the 180 suffix-sweep journals of
August wrote 384,700 hostname rows; the NYPW TimeMap parts at hostname grain
(`scripts/sources/nypw/nypw_hostgrain.py`, same artifact and link as the registrable
NYPW entries below) wrote **4,223,217 rows, the largest single reprice this project has
made**; the first night of platform sweeps (cjb.net 882k capture rows, demon.co.uk 56.6 MB,
freeserve.co.uk and onward per `data/raw/cdx/platform_queue_{a,b}.txt`) wrote 725,337.
Shipped together: **4,872,448 net-new hostname records, 2,749,488.7901 EE**, 93.6% of them
`www.` forms of held registrables, disclosed as such. The two lanes sit under the one
`ia_cdx_hostnames` source row and are told apart by `acquisition_method`, which the shipped
manifest carries: `nypw_timemap_hostgrain` 4,039,562 records, 2,097,954.68 EE;
`ia_cdx_domain_sweep` (August suffix sweeps plus the platform night) 832,886 records,
651,534.11 EE. The report's top-sources table is generated from that column. privatedances.co.uk read 0
captures in a first probe and 158,734 rows in the queued sweep an hour later, so a single
probe never closes a parent; cjb.net stopped on HTTP 400 after 20 pages (882,229 rows,
next page 45 in its state file) and is not marked done, so a later pass re-verifies whether
the namespace is exhausted. Queues c and d (ranks 61-250 of `rank_platform_parents.py
--top 250`, 190 parents) were chained behind a and b on 2026-09-02.

### The suffix namespaces reopened at hostname grain (2026-09-02)

C-39 to C-41 closed the public-suffix sweep on 2026-08-21 at registrable grain, and the
2026-08-24 line below prices its raw journals at "worth exactly 0". Both were right for
their unit and both were measured on 1.2% of the index: `co.uk` is 3,387,186 index blocks,
16,936 pages at the 200-block size the August sweep used, and 208 were walked (`ac.uk`
120 of 1,386). At hostname grain those 208 pages hold 59,418 hostname rows, about 286 a
page, so the whole namespace projects to millions of hostname rows, and `com.au` (20,491
pages), `co.nz` (4,462), `org.uk`, `gov.uk`, `co.za`, `gc.ca` and the `.us` states are
queued behind it (`data/raw/cdx/suffix_queue_s1.txt`, `s2.txt`). What made it affordable
is a page-size law measured on `co.uk` the same night: one page costs about the same at
any block count (200 blocks 11 to 42 s, 1,000 blocks 77 s, 3,000 blocks 70 s, 10,000
blocks 110 s), and the smaller pages were verified as exact subsets of the 10,000-block
page, so `cdx_suffix_sweep.py` now defaults to 10,000 and walks `co.uk` in 339 requests.
`showNumPages` answers with dashes when `fl` is in the query, which is why the August
walks never knew where the index ended. The platform queues stay ahead of the suffixes
because they pay more per client-hour (`listbot.com` 1,415,340 capture rows in two pages,
`homepage.com` 67,871 rows in 752 s, against ~286 hostname rows per 200-block `co.uk`
page). Two accounting notes for the ledger: thirteen parents were refused on their control
probe during an archive outage on 2026-09-01 (HTTP 503 and 504 between 19:42 and 22:01
UTC) and are requeued as `platform_queue_r1.txt` and `r2.txt`; and the old sweep advanced
past any non-200 page, so `cjb.net` (24 of 26 pages) and `yourmd.com` (ended on 21
transport errors) are re-walked in queues c and d, where the ingest dedups whatever the
first pass already wrote. Screen it teaches: **a closure at one unit says nothing about
another, and a closure on 1% of an index says nothing about the index.** Bare TLDs still
answer 403, so `.com` remains unreachable this way (C-39 stands).

## `ia_cdx_bulk`: Wayback CDX verification engine

A query engine, not a file: one collapsed CDX query per domain covering all six years, run against domains missing a year they are bracketed by. Endpoint <https://web.archive.org/cdx/search/cdx>; the response journals ship under `journals/`, so ingest replays offline.

```bash
uv run ark gaps                                             # choose targets
uv run ark cdx data/raw/cdx/gap_candidates.txt --workers 8  # query, writes a journal
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz  # journal -> evidence
```

**Dating: the 14-digit capture timestamps the archive returns for that domain, written by the crawler at capture time, collapsed to distinct years client-side.**

Evidence type: `cdx_timestamp`.

## `dartmouth_nber_captures`: the archive's own capture census

A 2017 research release publishing, for every host the Wayback Machine then held, captures per calendar year; 228 MB of `host<TAB>year<TAB>count`. From archive.org item `DARTMOUTH-NBER-RESEARCH-2017-metadata`, which no longer serves. The input does not ship:

```bash
uv run ark ingest dartmouth_nber_captures data/raw/dartmouth_nber/domain-year-captures.txt
```

**Dating: a row states the archive holds N captures of that host inside that calendar year, the same machine-counted fact a CDX query returns, so it dates that year and no other.**

**Evidence type: `cdx_timestamp`.** Self-dating, no corroboration split. Agrees with our own CDX querying on **138,760 (domain, year) pairs**. Yield **227,273 net-new pairs, 142,084.0 equivalent-English**. Approved `master` by Ivo 2026-08-17.

## `domain_creation_bulk`: published registry creation dates in bulk

A published WHOIS/DNS compilation of 171 million domains, each carrying the registry's own creation date parsed from a port-43 answer. 25.9 GB semicolon-separated CSV, fetched with the Kaggle CLI: `kaggle datasets download -d wotschofsky/171-million-domain-names-whois-dns-dnssec`.

```bash
uv run ark ingest domain_creation_bulk data/raw/domain_creation/domains.csv
```

**Dating: the registry-written Creation Date field in the record. A creation date in 1998 writes 1998 and no other year, because the parser emits one evidence row for one year.** Falsification: of 21,698 in-window rows in the six TLDs delegated in 2001, **zero** predate 2001.

**Evidence type: `whois_creation`.** Filed under the `registry` lineage, so it cannot corroborate our own `rdap` sweeps. Yield **2,165,523 net-new pairs, 1,241,812.0 equivalent-English**. Approved `master` by Ivo 2026-08-17.


## `rdap` and `rdap_snapshot`: registry creation dates

Registry RDAP lookups, direct to the authoritative registry resolved per TLD from the IANA bootstrap,
`rdap.org` fallback only. `rdap_snapshot` is the journalled path, `rdap` an earlier tranche.

```bash
uv run ark gaps --creation --out data/raw/rdap/creation_candidates.txt
uv run ark rdap data/raw/rdap/creation_candidates.txt
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
```

```bash
uv run python scripts/build_rdap_pool_list.py --tlds com,net --limit 1400000 \
    --out data/raw/rdap/pool_targets_verisign.txt
bash scripts/rdap_pool_sweep.sh 6 100000 32
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_pool_*.jsonl.gz
```

Bootstrap <https://data.iana.org/rdap/dns.json>, fallback <https://rdap.org/>

**Dating: the `registration` event date, a registry-written timestamp in the response. RDAP gives the
current state plus that one historical timestamp, no registration history.**

`whois_creation`, creation year only: it does not establish registration in a later year. Dated
outside 1996-2001, the name stays a candidate.

| closed here | what closed it | reopen |
| --- | --- | --- |
| PIR `.org` | 403 for 9,253 consecutive requests after ~850 answers | slow probe, stop on first refusal |
| Nominet `.uk` | three refusals in the first fourteen queries at 0.5 q/s | |
| auDA `.au` | namespace re-registered 2002, dates stamped with the migration | |
| `.gov` pool | pool-to-dated ratio 182.0 against `.com` 0.3, names invented | |

---

## `page_directory` and `page_expansion`: archived curated directory pages

Wayback captures of curated catalogue pages, read for the sites they list. Seeds under
`seeds/expansion/`; primary catalogue the WWW Virtual Library, <http://vlib.org/>

```bash
uv run ark download seeds/expansion/seeds_round2.txt --out data/raw/expand/round2/expand_round2.jsonl.gz
uv run python scripts/engines/split_expansion_journal.py data/raw/expand/round2/expand_round2.jsonl.gz --write
uv run ark ingest expansion_directory data/raw/expand/round2/*_corroborated.jsonl.gz --round 2
uv run ark ingest expansion_links     data/raw/expand/round2/*_unverified.jsonl.gz --round 2
```

**Dating: the crawler-stamped Wayback capture timestamp of the page. A listing dated 1998 evidences
its entries for 1998 only.**

`dated_directory` for a page recorded as a curated catalogue. Every other name, and any name no other
source attests, carries `link_target` under `page_expansion` and is candidate-only, a listing being a
claim by the linking page.

Rejected: the 1996-1997 Yahoo tree under `www.yahoo.com/<Category>/`, 11 pairs and 7.7295 EE from 55
archive requests.

---

## `internet_scout`: Internet Scout Report archive

Weekly curated review of scholarly, government and educational sites, harvested by OAI-PMH from
<https://archives.internetscout.org/OAI>.

```bash
mkdir -p data/raw/scout
curl -A "Mozilla/5.0" \
  "https://archives.internetscout.org/OAI?verb=ListRecords&metadataPrefix=oai_dc" \
  >> data/raw/scout/scout_oai.xml
# then repeat with &resumptionToken=<token from the previous page> until none is returned
uv run ark ingest internet_scout data/raw/scout/scout_oai.xml
```

**Dating: `dc:date` on each record gives the issue year and `dc:identifier` the reviewed URL, archive
metadata fields, not prose.**

`dated_directory`. Scholarly and US-weighted; the live feed cannot be hash-pinned.

---

## `ncsa_whats_new`: NCSA "What's New" announcement pages

Dated issues of the era's list of newly launched sites, from Wayback captures of the NCSA Mosaic site.
The only surviving 1996 editorial directory artifact here.

```bash
curl -s "https://web.archive.org/cdx/search/cdx?url=ncsa.uiuc.edu/SDG/Software/Mosaic/Docs/whats-new*&from=1996&to=1996&filter=statuscode:200&fl=timestamp,original"
# fetch each monthly issue with the id_ modifier, then extract the announced entries
uv run ark ingest ncsa_whats_new data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv
```

**Dating: the issue date carried by the page holding the entry. Every row is 1996.**

`dated_directory`. Navigation and masthead links are excluded. One of the 4,916 names is attested by
no other source.

---

## `ia_cdx`: per-year CDX verification (superseded)

Kept only so its 11 rows stay attributable. Superseded by the collapsed six-year query in
`ia_cdx_bulk`.

---

## NYPW first-capture index: rejected

IA's "Not Your Parents' Web" first-capture index (`https://archive.org/details/nypw_urls_CDXfirstentry`)
yields **60 net-new pairs over 53 net-new domains** from 2,413,003 in-window pairs, 99.998% overlap
with the same IA CDX the baseline drains. The 19.35 GB `nypw_timemaps` sibling samples that URL
universe too, and it is a separate source with a separate verdict: see below.

## `nypw_timemaps`: NYPW TimeMaps, master

Item: `https://archive.org/details/nypw_timemaps`. The THIRTY-FOUR parts ingested on 2026-09-01,
each linked so the bytes can be pulled again. The entry first listed only three of these while
eleven were already in the store, and the tarballs are deleted once converted to `.cdx.gz`, so the
missing links were the difference between a refetchable partition and a lost one:

- `https://archive.org/download/nypw_timemaps/1999/nypw_timemaps1999_deeplinks_part00o.tar.gz`, 81,558,295 B
- `https://archive.org/download/nypw_timemaps/1999/nypw_timemaps1999_rootURLs_part01r.tar.gz`, 548,991,394 B
- `https://archive.org/download/nypw_timemaps/1999/nypw_timemaps1999_rootURLs_part02r.tar.gz`, 147,027,083 B
- `https://archive.org/download/nypw_timemaps/1999/nypw_timemaps1999_rootURLs_part03r.tar.gz`, 150,725,864 B
- `https://archive.org/download/nypw_timemaps/1999/nypw_timemaps1999_rootURLs_part04r.tar.gz`, 210,555,238 B
- `https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_deeplinks_part00o.tar.gz`, 31,659,131 B
- `https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_deeplinks_part01o.tar.gz`, 31,397,597 B
- `https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_deeplinks_part02o.tar.gz`, 56,689,031 B
- `https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_rootURLs_part01r.tar.gz`, 228,359,937 B
- `https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_rootURLs_part02r.tar.gz`, 119,945,969 B
- `https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_rootURLs_part03r.tar.gz`, 119,365,472 B
- `https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_rootURLs_part04r.tar.gz`, 825,494,346 B
- `https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_rootURLs_part05r.tar.gz`, 406,711,686 B
- `https://archive.org/download/nypw_timemaps/2001/nypw_timemaps2001_deeplinks_part00o.tar.gz`, 148,848,304 B
- `https://archive.org/download/nypw_timemaps/1997/nypw_timemaps1997_deeplinks_part00o.tar.gz`, 30,569,952 B
- `https://archive.org/download/nypw_timemaps/1997/nypw_timemaps1997_rootURLs_part01r.tar.gz`, 137,487,874 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_deeplinks_part00o.tar.gz`, 17,958,107 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_deeplinks_part01o.tar.gz`, 13,698,867 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_deeplinks_part02o.tar.gz`, 19,014,371 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_rootURLs_part00r.tar.gz`, 617,413,931 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_rootURLs_part01r.tar.gz`, 708,524,984 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_rootURLs_part03r.tar.gz`, 449,293,008 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_rootURLs_part04r.tar.gz`, 325,150,887 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_rootURLs_part05r.tar.gz`, 726,115,622 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_rootURLs_part06r.tar.gz`, 83,518,037 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_rootURLs_part07r.tar.gz`, 521,097,923 B
- `https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_rootURLs_part08r.tar.gz`, 425,797,234 B

Banked, read out of the 2026-09-01 01:22 export rather than projected: **87,905.0 EE net-new
post-split over 197,938 pairs**, mean weight 0.4441, of which 193,428 pairs carry a 2001 year.

**Seven further parts were pulled and ingested by the operator after that reading, taking the
item to THIRTY-FOUR parts and closing every in-window folder.** They are, with their year rows
straight out of `ark ingest`, which is the cheapest honest per-partition figure this project has:

- `.../1999/nypw_timemaps1999_rootURLs_part00r.tar.gz`, 1,434,653,466 B, **47,229 year rows**
- `.../1997/nypw_timemaps1997_rootURLs_part00r.tar.gz`, 3,477,105 records, **5,222 year rows**
- `.../2000/nypw_timemaps2000_rootURLs_part00r.tar.gz`, 3,945,494 records, **94,695 year rows**
- `.../1996/nypw_timemaps1996_deeplinks_part00o.tar.gz` + `rootURLs_part00r` + `part01r`,
  9,897,209 lines together, **4,512 year rows between all three**
- `.../1996/nypw_timemaps1996_rootURLs_part02r.tar.gz`, 291,061,385 B, **761 year rows**

**The per-folder verdict, now that every in-window folder has been measured rather than argued
about.** Year rows per million records: 2000 about 24,000, 1999 about 10,000, 1997 about 1,500,
1996 about 640, 2001 **4**. So the payload is 1999 and 2000, 1997 is thin but real, 1996 is the
saturated head exactly as the original 2026-08-24 closure found, and the 2001 folder is dead
because a domain first captured in 2001 carries only a 2001 pair and the IA-derived baseline holds
that by construction. The whole round moved from 1.2567% to **2.3318%** on this item.

**The out-of-window folders are closed too, measured rather than assumed.** The item runs to
2021 and only 1996-2001 was ever pulled, on the reasoning that a URL first captured in 2002
cannot carry an in-window capture. That reasoning is now checked: `2002_deeplinks_part02o`,
4,036,843 rows, contains **one** row stamped 1996-2001. So folder year really is absolute first
capture, and the roughly 60 GB of 2002-2021 folders is dead. One 112 MB download settled it.

**Do not re-price this item by argument.** One run on 2026-09-01 reasoned from a plausible
mechanism that the 2001 folder was the real seam and recommended redirecting the download queue
there; the ledger says that partition wrote six year rows. See the correction on that row in the
evaluated table below.

**Which folder to pull next, measured as a census over all 197,938 pairs rather than sampled.**
Attributing each pair to the partition whose row supplied its `evidence_url` leaves nothing
unattributed and gives, per folder: 1997 651.3 EE over 2 parts, 1998 23,284.0 over 11, 1999
19,807.8 over 5, 2000 44,159.3 over 8, and **2001 just 2.5 EE over 1**. The yield rises from 1997
to 2000 and collapses at 2001, because folder year is the year of FIRST capture: a 2001-folder
domain has no earlier year to offer and its 2001 year is held by an IA-derived baseline by
construction. **So "97.7% of the net-new is dated 2001" is not a reason to pull the 2001 folder,
and reading it that way inverts the source.** `rootURLs` parts outpay `deeplinks` 3.9x per part
(77,912.2 EE over 18 against 9,992.7 over 9), so the remaining 1999 and 2000 `rootURLs` parts are
the queue. The 1997 and 1998 folders had been projected at "under 100 EE combined" and in fact
paid **23,935.4 EE**, the projection having been made on the same folder-versus-capture confusion.

**What dates one item:** field 3 of a TimeMap row is Wayback's own 14-digit capture timestamp,
written by the crawler at the moment of the capture, so the row evidences that year and no other.
A row entire, from `2000/TM_other/TM_x00o2000_10000.txt` inside the first tarball:

    https://4free.net/mousepads.shtml net,4free)/mousepads.shtml 20010124104200
    http://www.4free.net:80/mousepads.shtml text/html 200 NT5S4OFZGCGRFF3TKTOCLK7IYFJKQKP6 4009

Class `cdx_timestamp`, already master-eligible, and nothing in the row was typed by a human, so
pre-split equals post-split. Terms: CC BY 4.0, stated in the item's own `nypw_timemaps_readme.txt`.

**Why the sibling's rejection does not carry over, and why the 2026-08-24 closure of this item was
wrong.** The first-capture index gives one row per URL, so it can only ever offer a domain its
FIRST year, which the IA-derived baseline holds by construction. A TimeMap gives every capture of
that URL. The folder year is the year of first capture, not of the content, so folder Y can only
add years Y+1..2001: the 1996 folder the old test used is the saturated head, and the 2001 folder
is held by construction at 108,863 of 108,870 pairs. The paying folders are 1997 to 2000.

**Banked, net-new post-split, read back out of the store after the ingest:** 10,072 pairs and
**4,084.3 EE**, mean weight 0.4055, TLDs `com` 4,818, `de` 1,001, `org` 641, `net` 377, `co.jp` 320,
`it` 284. **10,070 of the 10,072 land at 2001.** Per part, `year_rows`: 2000 deeplinks part00o 3,566,
2000 rootURLs part02r 6,500, 2001 deeplinks part00o 6.

The pre-ingest pricing said 6,424 pairs at 4,146.8 EE and mean weight 0.6455, so the store took 57%
more pairs for 1.5% less EE. The head the pricing counted got covered in the days between and what
was left is the ccTLD tail. Worth carrying forward for any source priced more than a day before it
is banked: the pair count and the EE move in opposite directions, so a price that still looks right
in EE can be right for the wrong reason.

**What is left.** In-window folders are 19,350,762,163 B across 47 tarballs and the rootURLs lane is
about 90% of the bytes and was never opened before. At the measured 21 to 51 EE per MB the rest of
the 2000 folder alone projects five figures before saturation, which has to be re-measured as
banking proceeds. Take 1999 next: it has holes at both 2000 and 2001. Skip 1996 and 2001, both
measured dead.

## `nypw_timemaps_nonok`: the non-200 lane of the same partitions, master

**Same bytes, same LINKS, no new request.** Item `https://archive.org/details/nypw_timemaps`; the
thirty-four partition URLs are listed one by one in the `nypw_timemaps` section above and are the
only download links this source needs, because it reads the `.cdx.gz` already at
`data/raw/nypw_timemaps/`. Terms unchanged: CC BY 4.0 from the item's own
`nypw_timemaps_readme.txt`; `archive.org/robots.txt` is 238 bytes and disallows only `/control/`
and `/report/`.

**What dates one item:** field 3 of the CDX row, the crawler's own 14-digit capture stamp, exactly
as for the 200 lane. A row entire, from
`data/raw/nypw_timemaps/nypw_timemaps1998_rootURLs_part06r.cdx.gz`:

    https://hmcfunding.com/ com,hmcfunding)/ 20010309022603 http://www.hmcfunding.com:80/
    text/html 302 YSRUTJQPTYE6V4XUYSDKZYOE7SGNOZCU 384

The store held `hmcfunding.com` at 1998, 1999 and 2000 and lacked 2001. A 302 means the hostname
resolved, a server accepted the connection and answered at `20010309022603`, which requires the
name delegated at that instant. **The status describes the resource, not the registration**, so
this is `cdx_timestamp` unchanged rather than a new class.

**Measured net-new post-split against the live store on 2026-09-01: 6,679.7 EE over 13,277 pairs**,
out of 6,374,276 non-200 in-window rows that collapse to 444,308 distinct pairs, 97.0% of which
were already held. By year: 1998 6, 1999 111, 2000 360, **2001 12,800**. Approval entry and the
banked `year_rows` are in `docs/approved-sources-list.md`.

**The method is worth more than the source.** `_parse_nypw` had discarded every non-200 row since
it was written, counting them into `stats["non_200"]` and moving on, so the size of the lane was
recoverable from past ingest journals with no fetch at all. **To test "we filtered X away",
re-parse an artifact already ingested rather than querying anything**: ingesting the 200 lane first
turns the store into the control group, and every pair the relaxed parser finds that the store
lacks is attributable to the relaxation alone. Cost: no requests, one parser.

**`parse_arquivo_cdxj` (`src/ark/sources.py`) throws non-200 rows away the same way and is the
obvious next application, but it cannot be refetched**: `arquivo.pt/robots.txt`, 35,470 B read
whole, carries `Disallow: /wayback`, `Disallow: /cdxj` AND `Disallow: /datasets` in its
`User-agent: *` group, roughly 720 lines of `Allow:` exceptions in. That closes both the CDX API
and the CDXJ bulk files, and it also means the `curl` of
`https://arquivo.pt/datasets/cdxj/IA.cdxj` recorded earlier in this file would be disallowed today.
Only bytes still on a collector machine can be re-parsed.

**Every substitute pywb/CDX archive was checked and is closed**, so the live-query version of this
idea is dead and the bulk re-parse is the only route: `web.archive.org.au/robots.txt` is 26 B of
`User-agent: *` / `Disallow: /`; `webarchive.nationalarchives.gov.uk` is `Disallow: /` for `*` and
`Allow: /` for Oncrawl only; `www.webarchive.org.uk` serves an identical 159 B "400 Redirect" stub
to `/robots.txt` and to every `/wayback/archive/cdx?...` path, which is the identical-bytes-across-
different-objects signature of a failed fetch, and separately its TLS chain omits the DigiCert
Global G2 intermediate, which appending that intermediate from `cacerts.digicert.com` to the CA
bundle fixes for any future `.uk` work; `web.archive.bibalex.org` connect-times-out at 20 s;
`webarchive.loc.gov` 403s behind a Cloudflare JS challenge; `wayback.vefsafn.is` has a certificate
name mismatch. Also empty:
`archive.org/advancedsearch.php?q=format:(CDX) AND year:[1996 TO 2001]` returns 66,670 items that
are all scanned books on a loose token match, and Zenodo's "Webarchive CDX summary" is a 366 KB
conference PDF rather than data.

## Australian Web Archive: rejected, endpoint correction kept

`https://webarchive.nla.gov.au/awa/cdx` returns an Anubis challenge, but
**`https://web.archive.org.au/awa/cdx` answers normally**, a pywb server supporting `url`,
`matchType=domain`, `from`/`to`, `limit`, `collapse`, `output=json`. It is a lookup API, not a bulk
dump. Paired with the PANDORA titles list
(`https://github.com/GLAM-Workbench/trove-web-archives-titles`, CC0) it gives 35,391 registered
domains, 29,595 in no annual file, but a random 60-domain sample returned **60 answers, 0 transport
failures and 0 with any in-window capture**.

## Source names that are not separate sources

`cdx_snapshot` writes under `ia_cdx_bulk`, `rdap_snapshot` under `rdap_snapshot`, `early_web` under
`early_web_cdx`, `expansion_directory` and `expansion_links` under `page_directory` and
`page_expansion`. `deduplicated_urls_2001-2002` and `mid_slice` are candidate-only names with zero
evidence rows, retained so earlier seeding runs stay attributable.

---


## `trade_press` and `trade_press_mention`: scanned computer magazines

archive.org's scanned, OCR'd computer press, via `archive.org/advancedsearch.php` then
`archive.org/download/<id>/<id>_djvu.txt`. Hobbyist corpus `collection:computermagazines OR
collection:byte-magazine OR boardwatch`, 4,030 in-window items; American `collection:computerworld
OR collection:pub_computerworld OR collection:applemagazines OR (identifier:bub_gb* AND
(title:infoworld OR title:"network world" OR title:computerworld OR title:"pc mag"))`, 1,288.

**Dating: the item's `year` metadata field, the publication date of the issue. No inference.**

`dated_directory` after the corroboration split, because OCR fabricates hostnames: names seen only
here go to the candidate pool. Lineage `trade_press`. Yield 1,590 pairs, 1,004.33
equivalent-English.

```bash
uv run python scripts/sources/trade_press/collect_trade_press.py --discover     # collection sizes, run this first
uv run python scripts/sources/trade_press/collect_trade_press.py --limit 5000 --query "$HOBBYIST"   # first corpus
uv run python scripts/sources/trade_press/split_trade_press.py --write
uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated.jsonl.gz
uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates.jsonl.gz

uv run python scripts/sources/trade_press/collect_trade_press.py --limit 1400   # second corpus, now the default
uv run python scripts/sources/trade_press/split_trade_press.py \
    --journal data/raw/tradepress/tradepress_20260808T172417Z.jsonl.gz --tag american --write
uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american.jsonl.gz
uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american.jsonl.gz
```

The extractor also reads bare `foo.com`, `http://foo.com/` and `bob@foo.com`; re-reading cached OCR
under it sends no request:

```bash
uv run python scripts/sources/trade_press/reextract_trade_press.py --write
uv run python scripts/sources/trade_press/split_trade_press.py \
    --journal data/raw/tradepress/tradepress_reextract_<stamp>.jsonl.gz --tag reextract --write
uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_reextract.jsonl.gz
uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_reextract.jsonl.gz
```

| closed | the fact that closed it |
| --- | --- |
| widening the query | `--discover` finds no `pub_infoworld`, `pub_network-world`, `pub_pc-week`, `pub_internet-world`, `pub_cio`, `pub_web-techniques`, `drdobbs`, `linuxjournal`, `maccompendium`, `boardwatch`, `pcmag`, `wired-magazine` or `internet-magazines` collection, and no `sim_*` microfilm run of a computing title except Computerworld |
| `magazine_rack` | 34,288 items, 0.4 net-new pairs each |
| `folkscanomy_computer` | 519 items, 36 of 40 unreachable |
| `sim_microfilm` at large | 57,245 in-window items, but a 1,500-item sample is journals, gazettes and "Table of Contents" stubs |

---

## `usenet_address` and `usenet_address_mention`: the addresses the extractor never read

The 19,083 already-ingested Usenet archives at `data/raw/usenet/*.mbox.zip`, re-read for `ftp://`
hosts, `mailto:` links and typed body addresses. **Dating: the posting date of the message carrying
the address, from the message header, identical to `usenet_announce`.** `dated_directory` after the
corroboration split, `link_target` otherwise. Lineage `usenet`: a post and an address inside it are
one observation. Yield 102,577 pairs, 62,820.7 equivalent-English.

```bash
uv run python scripts/sources/usenet/collect_usenet_addresses.py --workers 10
uv run python scripts/sources/usenet/split_usenet_addresses.py --write
uv run ark ingest usenet_addr_dated      data/raw/usenet_addr/usenet_addr_dated.jsonl.gz
uv run ark ingest usenet_addr_candidates data/raw/usenet_addr/usenet_addr_candidates.jsonl.gz
```

Closed: a generic dot-rule token scan of the same text gave 354 net-new tokens worth at most 193
equivalent-English, contaminated (`ads.my`, `lol.ie`). Closed: mining `.edu` from the pool, since
these extractors supply 213,703 of its 216,185 `.edu` names and they are anti-harvester munged
addresses, CDX hit rate 0.003 over 1,709 answers.

---

## `usenet_bare` and `usenet_bare_mention`: the bare `foo.com` in the message bodies

The same 19,231 archives read a third time for a plain `foo.com` in prose, no scheme, no `www.`, no
`@`. No network. **Dating: the posting date of the message, identical to `usenet_announce`.**
`dated_directory` after the corroboration split, `link_target` otherwise; 36.3% of rows were
uncorroborated and went to the pool, so a company or file name asserts nothing. Lineage `usenet`.
Guards in `ark.usenet` are unit-pinned: TLD allowlist, lookbehind, lookahead, all-digits rule, and
body text only, never `Path:`, `Xref:` or `Newsgroups:`. Yield 42,139 pairs, 28,460.3
equivalent-English.

```bash
uv run python scripts/sources/usenet/collect_usenet_bare.py --sample 400 --workers 8    # project first
uv run python scripts/sources/usenet/project_usenet_bare.py --journal data/raw/usenet_bare/<file> --archives 400
just collect usenet-bare                                                # or the whole corpus
```

Limitation: 1,200 of the 42,139 pairs come from `comp.mail.maps` or `can.uucp.maps`, which
`ark.uucp` already parses under the `registry` lineage, so one posting can be read twice; every
evidence row names its group.

Coverage gap, measured 2026-08-30 by matching every `group` field in the journals against the
archives on disk: **9,050 of the 16,846 archives, 29.96 GB, are named in no `usenet_bare` journal at
all**, the largest being `alt.sex.erotica` 1.53 GB, `free.ucp` 674 MB, `us.politics` 646 MB and
`linux.kernel` 449 MB. That is unread bytes in an existing pipeline, not a new source, and it is the
cheapest unclaimed work in the register: no request, no terms, no new evidence class.

---


## `uucp_map_registry`, `uucp_map_creation`, `uucp_map_mention`: the UUCP maps

UUCP maps posted to `comp.mail.maps`, the `.CA` portion machine-generated from the Canadian domain
registry. On disk at `data/raw/usenet/comp.mail.maps.mbox.zip` (205,143,394 bytes), identical to
`https://archive.org/download/usenet-comp/comp.mail.maps.mbox.zip`.

```bash
uv run python scripts/sources/usenet/split_uucp_maps.py --write
uv run ark ingest uucp_listing  data/raw/uucp/uucp_listing.jsonl.gz
uv run ark ingest uucp_creation data/raw/uucp/uucp_creation.jsonl.gz
uv run ark ingest uucp_mentions data/raw/uucp/uucp_mentions.jsonl.gz
```

**Dating.** A registry-generated file declares its own provenance (`#R Automatically generated from a
.CA domain registration form`) and is regenerated from the live registration database at posting time,
so it takes the posting date: all 8,309 in-window registry postings carry an internal generation stamp
in the same year as their `Date:` header.

`artifact_listing` (posting date), `whois_creation` (registrar's `approved:`/`received:` date), lineage
`registry`. Hand-maintained maps are `link_target`, candidate-only.

---

## `rtfm_faq` and `rtfm_faq_mention`: the Usenet FAQ mirror

The `rtfm.mit.edu` FTP mirror, 19,478 FAQ documents under `pub/usenet-by-group`, at
`https://archive.org/download/ftp_rtfm.mit.edu_2014.07/2014.07.rtfm.mit.edu.tar` (1,691,248,640
bytes); the live host refuses connections.

```bash
tar -xf 2014.07.rtfm.mit.edu.tar -C data/raw/rtfm rtfm.mit.edu/pub/usenet-by-group
uv run python scripts/sources/usenet/split_rtfm_faqs.py --write
uv run ark ingest rtfm_dated      data/raw/rtfm/rtfm_dated.jsonl.gz
uv run ark ingest rtfm_candidates data/raw/rtfm/rtfm_candidates.jsonl.gz
```

**Dating.** The document's own `Last-modified:` / `X-Last-Updated:` / `Version:` revision header, not
`Date:`, which is the auto-reposter's stamp on the single copy rtfm keeps: of 12,318 documents carrying
both, 6,610 disagree, 3,296 with the repost later against 4 earlier.

`dated_directory`, after the corroboration split, because these URLs are prose typed by a human.
Lineage `usenet`.

---

## `ukwa_geoindex`: the UKWA Geoindex, found served after being closed as unreachable

Geographic index of the JISC UK Web Domain Dataset: every `.uk` resource the Internet Archive held for
1996-2013, each row a 14-digit timestamp, the URL, a tab, a postcode. 11,217,295,098 bytes over 12
members, CC Public Domain Mark 1.0:

```bash
curl -L -r 0-0 https://bl.iro.bl.uk/downloads/090bbffa-d82c-4641-ba72-0089e8ef885f
```

Extracted whole by `scripts/sources/ukwa/ukwa_geoindex_pull.sh`.

**Dating.** The row's own 14-digit IA capture timestamp prefix, a machine record of the capture, so it
dates that year and no other, and nothing in the file was typed by a human.

`cdx_timestamp`, master-eligible, no corroboration split. **Admitted master 2026-08-24** at 4,591
net-new pairs, 4,493.0 EE. `bl.iro.bl.uk` robots names ClaudeBot `Disallow: /`; `/downloads/` is allowed.

| closed | closing fact |
|---|---|
| rest of `bl.iro.bl.uk` | all 20,871 file_sets enumerated, the geoindex is the only web dataset; `woa1.zip` at 16.7 GB is 583 War Office photographs |
| DOI `10.5259/ukwa.ds.2/cdx/1` | the record has no file attached, one of 389 works in a 2021-10-20 bulk metadata import; cheaply re-testable |

## `iedr_register`: the archived IE Domain Registry register listing

The IE Domain Registry regenerated the whole `.ie` register as static pages at
`/statistics/<letter>-doms.html`, one per initial letter, captured by Wayback; 26 in-window pages hold
24,805 distinct `.ie` names.

```bash
uv run python scripts/sources/registries/collect_iedr_register.py
uv run ark ingest iedr_register data/raw/iedr/*-doms.html
```

**Dating.** Each page's own machine-written line, `updated automatically at 14:51 GMT on Friday, 21
December 2001`, stamped by the cron that rebuilt the register. A page whose own line falls outside the
window is dropped whole: `l-doms.html` resolves to a 28 March 2002 edition, and taking the capture
stamp instead would have imported 931 names into 2001.

`artifact_listing`, lineage `registry`: the registry stating which names were registered at a stated
instant, the same instrument as an InterNIC zone file. Nobody typed the list, so no corroboration
split, and it says nothing about any other year. **Admitted master by Ivo, 2026-08-24**, at 19,263
net-new pairs worth 18,769.9 EE. **829 of those come from the earlier `/lists/` tree, 812 at 1999 and
17 at 2000, and they carry a different footer**: a plain `Last updated 27 Nov 1999` rather than the
`updated automatically at 14:51 GMT on Friday, 21 December 2001` cron stamp the 2001 editions carry.
They rest on the page being a generated register listing, not on the word "automatically", which is a
weaker ground and is stated so it can be discarded separately.

`stalled.html` is excluded by filename before its date is read: it lists pending applications, names
nobody had registered.

---


## Closed by the reviewer himself, 0901 update

Ding's update of 2026-09-01 (Update_Log, 11:31:59 UTC+8) publishes his own negative
results: families "recorded as high-overlap, low-yield, noisy, incomplete, or otherwise
unsuitable for further work in their current form". They are register-closures of the
strongest kind, since the reviewer cannot be scooped by himself. Do not re-propose any of
them; where we hold our own verdict on the same family, both are cited.

| His closure | Our own verdict, where one exists |
|---|---|
| Internet Archive early-web language annotations | never tried here; CLOSED on his word |
| New Riders WWW Yellow Pages CD-ROM | never tried here; the curated-directory floor (0.013-0.024 pairs/listed domain) predicted this class dead, and his reading agrees |
| LAW / WebGraph WebBase-2001 | CLOSED here twice: novelty screen 2026-08-08, re-tested on the current screen 2026-09-01 at exactly 0 EE (all 603,245 registrable domains held AT 2001; SPEC names WebBase as an original-project source) |
| Dated Usenet archive copies | our Usenet channel is banked and its seams measured to saturation (bare-hostname arm projects 514-1,007 EE over all remaining archives); his "high-overlap" reading matches |
| Sampled scanned magazines | `trade_press` banked small here; prose-density ceiling 0.042 pairs/item documented 2026-08-2x |
| Specific raw ISC archive copies | `isc_survey` banked and closed for good here 2026-08-1x |

## Evaluated and rejected

One row per source evaluated. Families their own verdict word closes are in
[sources-closed.md](sources-closed.md), in that file's five columns. `n/a` means the
entry does not say, never that the answer is nothing. The link column carries the source
URL; where an entry names several, the first is here and all of them are in its `## `ukwa_geoindex_hostnames`: BANKED 2026-09-04 at 20,916.9 EE, held out for one day and 99.5% a crawler's own alias

`https://data.webarchive.org.uk/opendata/ukwa.ds.2/geoindex/`, the twelve
`geoindex_postcode-*_inwindow.tsv.gz` members already on disk as `data/raw/ukwa/` and banked at
registrable grain (CC Public Domain Mark 1.0, `sources.md` line 771). **What dates one item is the
row's own 14-digit IA capture timestamp, the first field of every line, immediately before the URL
it captured**: `19981202095846/http://www.dci.clrc.ac.uk:80/Person/N.B.M.Calton` dates
`www.dci.clrc.ac.uk` to 1998, class `cdx_timestamp`, master-eligible and already approved for this
source. `scripts/sources/ukwa/ukwa_hostgrain.py` re-emits each member as a `{url, timestamp}`
journal, one per member, and the journals are in `data/raw/ukwa_hostgrain/`. Priced over all
17,912,511 in-window rows with no sample: 429,415 distinct host-years, 122,501 candidates after the
funnel, 87,259 already in the store, 13,910 in his files alone, **21,332 net-new hostname years and
20,916.8958 EE**, 80.5% of it at 2001, `uk` 20,892.9 of the EE. **The finding stands and the decision reversed: 21,222 of those
21,332 records, 20,808.9528 of the 20,916.8958 EE (99.5%), are `www.<a name already held in that
same year>`**, the crawler-default alias of a name we or he already date. ADR-007 held the corpus
out for that reason on 2026-09-03; ADR-008 ships it on 2026-09-04, because his merges keep all
1,313,547 `www.` forms we sent and his section XI says a base hostname and a distinct subdomain
hostname may each be annual records. **Ingested 2026-09-04, 32,156 hostname years.** Eligible on
the old reading was 107.9430 EE, which is what the reversal was worth here. **The transferable point: a bulk CDX index re-read at hostname
grain yields almost nothing but the alias, and the share must be measured before the figure is
quoted.** `just price-hosts` prints it.

## `usenet_new_hostgrain`: FIND at 22,702.6 EE eligible, the whole 53.5 GB pool measured, awaiting a class decision

`https://archive.org/download/usenet-<hierarchy>/<group>.mbox.zip`, on disk as
`data/raw/usenet_new/`, 7,531 `*.mbox.zip` Google Groups exports of the bit, linux, microsoft, gov,
us and lucky hierarchies, 53,539,826,439 B, worth 35.8 EE at registrable grain (`sources.md` line
1032). **What dates one item is each post's own machine-written `Date:` header inside the mbox**,
one item per post; the hosts are the authorities of explicit `http://`, `https://` and `ftp://`
URLs in the post BODY only, because a `Path`, `Xref`, `NNTP-Posting-Host`, `Message-ID` or `From`
host is a news relay or a mailbox and not a host serving web content. Read whole, no projection:
46,962,780 posts, 12,844,569 dated inside 1996-2001, 5,228,888 of them carrying a body URL,
456,378 distinct host-years, 129,277 candidates, 43,562 already in the store and 29,926 in his
files alone, **55,789 net-new hostname years and 32,107.4096 EE, of which 29.3% is the `www.`
alias seam, leaving 22,702.6354 EE eligible**, plus **1,120 net-new parent registrable-years worth
611.3989 EE** that need no hostname decision at all. Spread 1996 2,371.1 EE to 2000 8,306.7 EE, so
it is not a one-year artifact; `com` 10,376.6, `edu` 6,276.2, `net` 3,101.2, `mil` 1,587.0.
A fiction screen over the eligible rows (RFC 2606 reserved names, the idiomatic fakes
`foo`, `acme`, `bogus`, `yourdomain` and kin, and digit-mask shapes) removes **517 rows and
324.8664 EE, 1.43%**, leaving **22,377.7690 EE**; a `home.ml.org` or `home.pages.de` label is NOT
fiction, both were real free-hosting services, and the screen was tightened until it stopped
catching them. **Nothing is ingested**: at hostname grain a human-typed URL is not a class we
hold, so this is the new `usenet_body_url_hostnames / link_source` request and it waits on that
word. **The transferable point: the hostname unit pays where a human typed the host**, and the two
Usenet pools are the only corpora in the 26-corpus retention audit that kept their figure through
the alias screen.

## `usenet_bulk_hostgrain`: FIND at 42,462.6 EE eligible, the whole 56.0 GB alt.* pool measured

`https://archive.org/details/usenet-alt`, on disk as `data/raw/usenet_bulk/`, 9,266 `*.mbox.zip`
Google Groups exports of the `alt.*` hierarchy, 56,026,437,278 B, projected at roughly 33,000 EE
at registrable grain on a 2-60 MB stratum sample and never read whole (`sources-closed.md`, the
`data-raw-usenet-bulk-a-second` row). **What dates one item is each post's own machine-written
`Date:` header inside the mbox**, one item per post, and the hosts are the authorities of explicit
`http://`, `https://` and `ftp://` URLs in the post BODY only. Read whole this time, no stratum and
no projection: 39,928,768 posts, 22,759,309 dated inside 1996-2001, 12,380,662 carrying a body URL,
794,929 distinct host-years, 212,593 candidates, 73,465 already in the store and 44,694 in his
files alone, **94,434 net-new hostname years and 56,012.4049 EE**. Two screens then apply, both
measured: the `www.<a name already held that year>` alias seam is **20,741 rows and 13,431.6477 EE
(24.0%)**, and the fiction screen removes a further **196 rows and 118.1302 EE (0.28% of what is
left)**, so the defensible figure is **42,462.6270 EE over 73,497 hostname records**, plus **1,575
net-new parent registrable-years worth 883.8281 EE** that need no hostname decision at all. Spread
1996 4,613.7 EE to 2000 15,305.2 EE; `com` 22,065.3, `edu` 7,359.7, `net` 7,338.1, `uk` 6,631.6.
**The 0.28% fiction rate is the whole argument for this lane**: the sibling request
`usenet_body_pasted_hostnames` parks because `dig` and config-snippet hostnames were ~13%
invented, and a host inside a URL a human typed is not. Waiting on the same word as
`usenet_new_hostgrain`; nothing is ingested. **Two pools together: 64,840.4 EE eligible over
113,864 hostname records, measured over 110 GB with no projection.**

## `usenet_body_url_hostnames`: FIND at 65,280 EE, and the two entries above it were wrong

**This supersedes `usenet_new_hostgrain` and `usenet_bulk_hostgrain`, written earlier the same
day.** Those entries stand as the record of what was measured then; four independent verifiers
attacked the figure and three of them landed, so the numbers here are the ones to quote.

**What was wrong, and it was the method rather than the arithmetic.** The extractor's post
boundary was `^From (\d+|\S+@\S+)`, and Google Groups exports separate posts with
`From <signed 64-bit id>` where about half the ids are negative. So **50.019% of posts were
never recognised**, and every unrecognised post's header block was appended to the previous
post's body: 14.02% of extracted host mentions came from a header line, `Organization:` alone
12.65%, which is the news-provider class the entry promised to exclude. `ftp://` was claimed
and never implemented. The two pools were also priced separately and **added**, double counting
12,387 shared (host, year) keys. And the pricer counted only the subdomain rows, discarding the
registrable-year pairs the same captures assert.

**The corrected measurement**, both pools read whole with `-?\d+` and priced as one union
(`just price-hosts --items <pool> <pool>`): 173,738,432 posts, **71,209,294 dated inside
1996-2001**, 24,308,602 carrying a body URL, 1,111,076 distinct host-years, 316,847 candidates,
99,318 already in the store and 65,032 in his files alone. **151,977 net-new hostname years and
88,564.4995 EE gross.** Then three screens, each measured: the ADR-007 `www.` alias seam is
29,884 rows and 18,932.8616 EE (21.4%), leaving **69,631.6379 EE**; the `.arpa` and
TLD-delegation rules the hostname export had never applied take 510 rows; and fiction, which is
the one screen that cannot be mechanical, because the surviving fakes are **typos of real
hosts** (`mmembers.aol.com`, `www3.per.sypatico.ca`, `home.mci20000.com`) rather than
`foo.com`. Hand-judged over 80 random eligible rows across two seeds: 5 implausible, so
**6.25%, Wilson 95% CI 2.7% to 13.8%**, giving **65,279.6605 EE central, 60,022 to 67,752**.
A word list finds only 949 of them, which is why the rate is sampled and quoted with an interval.

**The registrable half is separate and needs no hostname decision: 42,625 net-new (registrable,
year) pairs, 24,172.0540 EE**, from the 775,507 pairs the same rows assert. That figure is
BEFORE the corroboration split every typed-name class takes, and the split is known to be
brutal here: the recorded registrable pass over `usenet_new` measured 35.8 EE post-split. So it
is an upper bound on that half, not a second find.

**What dates one item** is unchanged and survived its own verifier intact: each post's own
machine-written `Date:` header, zero wrong-year assignments in 135,695 dated posts. One warning
for anyone who tries to harden it: **38.02% of the dated posts use the Google Groups
`YYYY/MM/DD` form, which `email.utils.parsedate_to_datetime` cannot parse**, so the
four-digit-year regex is deliberate and a strict RFC 822 parse would silently discard 51,584 of
135,695 sampled posts.

Nothing is ingested. The request is `usenet_body_url_hostnames / link_source` in
`approved-sources-list.md`; **the transferable point is that a one-character regex defect
survived a skeptic that reproduced every figure to the digit, because it re-ran the same code:
a verifier has to read the extractor against the raw bytes, not re-price the same output.**

## `usenet_uk_hostgrain`: FIND at 9,644 EE, the whole uk hierarchy read in one evening

`https://archive.org/download/usenet-uk/<group>.mbox.zip`, 495 archives, 14,478,540,197 B,
fetched 2026-09-03 23:23 with the existing polite fetcher into `data/raw/usenet_uk/` (honest
User-Agent, one client, largest first, two passes). **The catalogue on disk said this pool
existed and nobody had opened it**: `data/raw/usenet_catalog.json` lists 9,918 archives and
328.5 GB never downloaded, of which this is the highest-weight block, because `.uk` scores
0.9813 against `.com` 0.6321.

**What dates one item is each post's own machine-written `Date:` header**, one item per post,
and the hosts are the authorities of explicit `http://`, `https://` and `ftp://` URLs in the
post BODY only, so a `Path`, `Xref`, `NNTP-Posting-Host`, `Message-ID`, `From` or
`Organization` host never enters. Read whole, no sample and no projection: 25,943,465 posts,
**9,295,674 dated inside 1996-2001**, 2,848,005 carrying a body URL, 203,622 distinct
host-years, 61,112 candidates, 27,444 already in the store and 11,645 in his files alone.
**21,968 net-new hostname years and 15,552.5896 EE gross.** The ADR-007 alias seam takes
7,218 rows and 5,265.2005 EE (33.9%), leaving **10,287.3891 EE**, and the pools' sampled
fiction rate of 6.25% takes it to **9,644.4273 EE central** (a mechanical word-list screen
finds only 38 rows and 28.0860 EE here, 0.27%, which is why the sampled rate is the one to
quote). Beside it, **6,066 net-new registrable-years worth 4,169.0703 EE** before the
corroboration split.

**`uk` is the top TLD of its own pool at 7,335.2 EE**, then `com` 3,657.3, `net` 1,408.4,
`edu` 1,214.6. Spread 1996 1,055.2 EE to 2000 4,065.6 EE, so it is not a one-year artifact.

**The transferable number: 1,152 EE per GB gross, against 851 for the two big pools**, which
is the `.uk` weight showing up exactly where the weight table says it should. Nothing is
ingested: this is the same `usenet_body_url_hostnames / link_source` class as the two pools
and it waits on the same word.

## `usenet_comp_hostgrain` and the four-pool union: 93,590 EE, and the overlap between hierarchies is only 16%

Fetched and read whole overnight on 2026-09-04, same lane and same extractor as the other
pools: `https://archive.org/download/usenet-comp/<group>.mbox.zip`, **1,205 archives,
33,056,417,861 B**, into `data/raw/usenet_comp/`. 52,630,472 posts, **26,191,307 dated
inside 1996-2001**, 8,446,768 carrying a body URL. Standalone: 87,073 net-new hostname
years and **52,397.0489 EE gross**, alias seam 25.9%, **38,808.0098 EE eligible**, plus
12,602 net-new registrable-years worth 7,258.9375 EE. `com` 14,892.9 EE then **`edu`
13,950.7**, which is what the technical hierarchy looks like.

**Density, which is the number that decides what to fetch next: comp is 1,701 EE per GB
gross, uk 1,152, and the two original pools 851.** Bigger is not better; denser is, and
density tracks how much people typed URLs at each other.

**The union of all four pools, priced in one run, is the figure to quote**: 35,603,375
item lines, 1,577,656 distinct host-years, 446,081 candidates, 138,342 already in the
store and 92,158 in his files alone, **214,706 net-new hostname years and 127,336.8919 EE
gross**. The ADR-007 alias seam takes 43,781 rows and 27,507.2807 EE (21.6%), leaving
**99,829.6112 EE**, and the sampled 6.25% fiction rate gives **93,590.2605 EE central**.
Beside it, **57,227 net-new registrable-years worth 33,172.8989 EE** before the
corroboration split.

**Saturation between hierarchies is 15.9%, not the wall it was assumed to be.** Priced
separately the four give 118,727.04 EE eligible; unioned they give 99,829.61, so a new
hierarchy still adds about four fifths of its standalone value. That is what makes the
remaining 262 GB of the catalogue worth reading rather than projecting.

Nothing is ingested. All four pools are the same `usenet_body_url_hostnames / link_source`
class and wait on the same word.

## `usenet_body_url_hostnames`: BANKED 2026-09-04, 119,640 EE over every non-alt hierarchy, 224 GB read whole in one night

**The whole catalogue except `alt`, read rather than projected.** `data/raw/usenet_catalog.json`
listed 9,918 archives and 328.5 GB nobody had downloaded; overnight on 2026-09-04 eleven
hierarchies came down with the existing polite fetcher and were read with the body-URL
extractor: `uk` 495 archives, `comp` 1,205, `rec` 919, `soc` 341, `sci` 237, `misc` 242,
`news` 60, `talk` 47, `can` 109, `biz` 95, `aus` 195, beside the `usenet_new` and
`usenet_bulk` pools priced the day before. **13 pools, 224 GB, 328,201,000 posts.**

**What dates one item** is unchanged and verified against raw bytes: each post's own
machine-written `Date:` header, with hosts taken only from explicit `http://`, `https://`
and `ftp://` URLs in the post BODY, so a `Path`, `Xref`, `NNTP-Posting-Host`,
`Message-ID`, `From` or `Organization` host never enters.

**Priced as ONE union, because summing pools double counts**: 54,700,642 item lines,
2,100,957 distinct host-years, 570,272 candidates, 175,368 already in the store and
119,517 in his files alone. **274,354 net-new hostname years and 163,985.8408 EE gross.**
The ADR-007 alias seam takes 57,604 rows and 36,370.1156 EE (22.2%), leaving
**127,615.7252 EE**, and the sampled 6.25% fiction rate gives **119,639.7424 EE central,
110,005 to 124,170** on its Wilson interval. A mechanical word-list screen finds only
1,081 rows and 668.41 EE (0.52%), which is why the rate is sampled and quoted with an
interval rather than word-listed. Beside it, **83,708 net-new registrable-years worth
49,007.3050 EE** before the corroboration split.

Spread 1996 15,207 EE to 2000 30,432 EE of eligible; `com` 56,825.2 gross, `edu`
28,766.2, `uk` 18,886.1, `net` 16,298.0.

**The law this establishes, and it is the useful part. Density, not size, decides which
hierarchy to read**, and density is how much people typed URLs at each other:

| pool | GB | EE per GB gross |
|---|---|---|
| `news` | 5.5 | 2,552 |
| `comp` | 30.8 | 1,701 |
| `sci` | 10.8 | 1,413 |
| `biz` | 1.1 | 1,435 |
| `uk` | 13.5 | 1,152 |
| `aus` | 5.0 | 1,213 |
| `usenet_new` + `usenet_bulk` | 102 | 851 |
| `rec` | 51.6 | 717 |
| `can` | 2.0 | 771 |
| `misc` | 9.1 | 1,033 |
| `soc` | 30.1 | 418 |

**And cross-hierarchy saturation is mild: 22.2% between the thirteen.** Summed
standalone they give 158,841 EE eligible; unioned they give 127,616, so a new hierarchy
still adds about four fifths of its own value. That is what justified reading eleven of
them instead of sampling one.

**Ingested 2026-09-04** under `Decision: master` (Ivo), by `ark ingest-usenet-hostnames`
over the thirteen `data/raw/usenet_*_items` directories: **394,904 hostname years and
77,029 (registrable, year) pairs** into the store, of which 76,208 registrable pairs reach
the shipped files at 44,574.5944 EE. Class `link_source`, one evidence row per
(host, year) quoting the dating year and the exact post: `usenet post 1997
uk.comp.sys.mbox.zip#12 www.demon.co.uk`, with `evidence_url` the archive.org download the
post came from. **All 24 derived identifiers were probed against `archive.org/metadata`
before the ingest**, one request each, so no evidence row points at an item that does not
exist: the identifier follows the group's first label rather than the pool directory,
because `usenet_new` and `usenet_bulk` hold twelve hierarchies between them.

**The archives are gone and the journals stay**: 224 GB of `.mbox.zip` was deleted after
pricing because archive.org serves them again by name from the catalogue, and the shards
are a few hundred MB in total.

## Detail`
section, which holds the entry as it was written.

| source | version or date | coverage period | retrieval method | what dates one item | baseline overlap | net-new EE (date) | quality issues | effort | verdict | link |
|---|---|---|---|---|---|---|---|---|---|---|
| early_web_nonok_hostgrain | 2026-09-04, fleet night-hunt-20260903 | n/a | a converter beside early_web_hostgrain.py keeping every status but 200 | field 2 of the classic CDX row, IA's own 14-digit capture timestamp | n/a | 3,988.7876 EE (2026-09-04) | 100.0% of it is www.<a name already held that year>, which ADR-007 refused for one day and ADR-008 ships; ingested 2026-09-04, 53,934 hostname years | n/a | BANKED | <https://archive.org/details/early-web_cdx-lang-cdxa> |
| arquivo_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts over the converted Arquivo CDX journals | each CDXJ line's own 14-digit capture stamp, field 2, beside the original URL | n/a | 540.9323 EE (2026-09-03) | Measured 540.9323 EE over the whole converted index, 9x under the bar. | n/a | CLOSED | <https://arquivo.pt/datasets/cdxj/Roteiro.cdxj> |
| attrition_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the attrition defacement records | the defacement date stamped inside the mirror path for that item | n/a | 922.6577 EE (2026-09-03) | Measured 922.6577 EE: one host per dated item, and most already held in that very year. | n/a | CLOSED | <https://raw.githubusercontent.com/attrition-org/web-hack-mirror/main/mirror/> |
| can_domain_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the can_domain listing | the message's own Date header inside the mbox, one per item, machine-written by the posting host: the CDNnet registrar notices carry the | n/a | 37.7522 EE (2026-09-03) | Lane B, and measured, not reasoned. | n/a | CLOSED | <https://archive.org/download/usenet-can/can.domain.mbox.zip> |
| dartmouth_bfs_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts over the converted Dartmouth BFS capture journals | field 2 of every classic CDX row, its own 14-digit IA capture timestamp | n/a | 60.0495 EE (2026-09-03) | Measured 60.0495 EE: the BFS crawl's hosts are already held at the capture year. | n/a | CLOSED | <https://archive.org/details/Dartmouth_10KwebURLs_GWB-20180911224740_BFS_4-lvls> |
| freebsd_ports_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the FreeBSD ports tree snapshots | The port's own machine-written RCS stamp inside its Makefile, e.g. | n/a | 1323.6735 EE (2026-09-03) | Lane B, because no row in this corpus carries its own capture timestamp next to a URL. | n/a | CLOSED | n/a |
| jeb_bush_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over all 472,949 anchored lines, then over the URL-vouched subset alone | Each item is one message block, dated by its own unindented `Sent:` line, written by the sending mail client into the released export | n/a | 7126.8923 EE (2026-09-03) | Lane B, and it does not pay. | n/a | CLOSED | <https://archive.org/download/JebBushEmails/JebBushEmails-Text.7z> |
| maillists_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the mailing-list archives, body URLs only | The message's own `Date:` header inside the archive file, a machine-written stamp emitted by the sending mail client and preserved | n/a | 186.1089 EE (2026-09-03) | Lane B, and it does not pay. | n/a | CLOSED | <https://mail.python.org/pipermail/> |
| ncsa-whats-new_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the NCSA What's New editions | Each issue file carries its own edition date in a publisher-written H2 header: data/raw/ncsa-whats-new/issues-1996/0196-01.html holds | n/a | 225.8968 EE (2026-09-03) | Lane B, measured, and far under the bar. | n/a | CLOSED | <https://web.archive.org/cdx/search/cdx?url=ncsa.uiuc.edu/SDG/Software/Mosaic/Docs/whats-new*&from=1996&to=1996> |
| nypw_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | converter to {url, timestamp} journals, then price-hosts over the whole 6,281,937-row first-capture index | field 3 of each row, Wayback's own 14-digit capture timestamp | n/a | 7,074.0871 EE (2026-09-04) | 100.0% alias, so 2.8404 EE on the ADR-007 reading and its gross under ADR-008. Ingested, 94,099 hostname years | n/a | BANKED | <https://archive.org/details/nypw_urls_CDXfirstentry> |
| odp_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the ODP dump | The dump's own machine-written generation stamp in the first 200 bytes, matched by the ingest's regex "Generated at | n/a | 639.7007 EE (2026-09-03) | Lane B, not A: the RDF dumps carry no per-row capture timestamp. | n/a | CLOSED | <https://web.archive.org/cdx/search/cdx?url=dmoz.org/rdf/*&from=2000&to=2001> |
| probes_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | inventory first, then price-hosts --items over the parts that are corpora rather than prober output | For an RFC or an Internet Draft, the month-and-year printed in the document's own header block beside the Request for Comments or draft | n/a | 387.1391 EE (2026-09-03) | Lane B, and it does not pay. | n/a | CLOSED | n/a |
| rtfm_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | items rebuilt body-only, then price-hosts over all 16,604 dated FAQs | the FAQ's own revision header, Last-modified or X-Last-Updated, written by its tooling | n/a | 3719.9091 EE (2026-09-03) | 20,049.4200 EE became 3,719.9091 EE once only hosts inside explicit URLs in the body counted: an 81.45% extraction error. | n/a | CLOSED | <https://archive.org/download/ftp_rtfm.mit.edu_2014.07/2014.07.rtfm.mit.edu.tar> |
| scout_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the Scout Report editions | The record's own Dublin Core publication year inside the oai_dc metadata block. | n/a | 307.196 EE (2026-09-03) | Lane B, and it does not pay. | n/a | CLOSED | <https://archives.internetscout.org/OAI?verb=ListRecords&metadataPrefix=oai_dc> |
| source_probe_260806_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the 2026-08-06 source probe journals | A machine-written stamp inside each item, one per component. | n/a | 3133.9122 EE (2026-09-03) | Lane B, not A: nothing in the corpus is CDX-shaped. | n/a | CLOSED | <https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz> |
| squidguard_contrib_2001_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the 2001 squidGuard editions | Each list file's own machine-written compile header, e.g. | n/a | 81.8016 EE (2026-09-03) | Lane B. | n/a | CLOSED | <https://web.archive.org/web/20010710215730id_/http://ftp.ost.eltele.no/pub/www/proxy/squidGuard/contrib/blacklists.tar.gz> |
| texts_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over 1,703 of 1,911 OCR caches, edition year per item | the item's printed publication year from the archive.org metadata, an edition date and not a stamp inside the artifact | n/a | 7341.8948 EE (2026-09-03) | Measured 7,341.8948 EE, and no class can carry an edition date. | n/a | CLOSED | <https://archive.org/download/IDENTIFIER/IDENTIFIER_djvu.txt> |
| tucows_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the Tucows mirror listings | The item's own structured `date` field in the archive.org catalogue scrape. | n/a | 232.4641 EE (2026-09-03) | Lane B, not A: no row carries a capture timestamp. | n/a | CLOSED | <https://archive.org/advancedsearch.php?q=collection:tucows+AND+year:[1996+TO+2001]> |
| usenet_msft_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | digest comparison against the already-processed copy, no sample | Each Usenet post's own `Date:` header, written by the posting agent inside the artifact and preserved in the mbox export. | n/a | 341.0836 EE (2026-09-03) | Lane B, and it does not pay. | n/a | CLOSED | <https://archive.org/details/usenet-alt> |
| usenet_probe5_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts against the live store | each post's own machine-written Date header inside the mbox | n/a | 2419.3872 EE (2026-09-03) | Measured 2,419.3872 EE over the 48 mboxes; the paying Usenet lane is the two big pools, priced whole. | n/a | CLOSED | <https://archive.org/download/usenet-<hierarchy>/<group>.mbox.zip> |
| usenet_probe_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the whole 142 MB mbox, body URLs only | each post's own machine-written Date header inside the mbox | n/a | 480.8799 EE (2026-09-03) | Measured 480.8799 EE over the whole mbox of the one group whose subject IS the web: 69.4% of the surviving hosts are already held in the post's year. | n/a | CLOSED | <https://archive.org/download/usenet-comp/comp.infosystems.www.misc.mbox.zip> |
| wwwvl_hostgrain | 2026-09-03, fleet e95-hostname-grain | n/a | price-hosts --items over the WWW Virtual Library editions | One item is one archived directory page, and it is dated by the 14-digit Wayback capture stamp that prefixes its filename, the same stamp | n/a | 3136.7893 EE (2026-09-03) | Lane B, and measured negative. | n/a | CLOSED | <http://vlib.org/> |
| inaddr_reverse_tree_ns_hostnames_1997_1999 | 2026-09-02 fleet 20260902T0232Z | 1997-1999 | ftp listing | ARIN arm: BIND 8's transfer comment at the head of each zone member, `;. | n/a | 4655.5 EE (2026-09-02) | FIND at 4655.5 EE, against the ark-data sync. Artifact:. both arms read whole, no sampling. | n/a | FIND | <https://ftp.apnic.net/apnic/arin/arin.zones.tar.gz> [detail](#inaddr-reverse-tree-ns-hostnames-1997-1999) |
| isc_survey_host_files_hostname_grain | 2026-09-02 fleet 20260902T0232Z | 1996 | wayback replay | the survey `YYMM` in the artifact path (`9607.hosts/` = July 1996 PTR walk), class `artifact_listing`, already master for `isc_survey`;. | n/a | 818952 EE (2026-09-02) | FIND at 818952 EE, against the ark-data sync. Artifact:. `9607.hosts/uk.gz` | n/a | FIND | <http://web.archive.org/web/19970529075101id_/http://nw.com.:80/zone/9607.hosts/uk.gz> [detail](#isc-survey-host-files-hostname-grain) |
| usenet_pasted_machine_blocks_hostname_grain | 2026-09-02 fleet 20260902T0232Z | 1999 | http download | the post's own `Date:` header (`Date: 1999/12/30` in the old Google form, RFC 822 in the rest), the same stamp the approved Usenet body | n/a | 6200 EE (2026-09-02) | FIND at 6200 EE, against the ark-data sync. Artifact:. two whole groups from | n/a | FIND | <https://archive.org/download/usenet-comp/comp.protocols.dns.bind.mbox.zip> [detail](#usenet-pasted-machine-blocks-hostname-grain) |
| usenet_uk_and_edu_header_fqdns | 2026-09-02 fleet 20260902T0232Z | 1996-2001 | http download | the message's own `Date:` header (fallback: the X-Trace epoch the injecting server wrote), and the hostname is written by the NNTP server | n/a | 2537 EE (2026-09-02) | FIND at 2537 EE, against the ark-data sync. Artifact:. `uk.comp.os.win95.mbox.zip` (27,709,004 B | 60,588 messages | FIND | <https://archive.org/download/usenet-uk/uk.comp.os.win95.mbox.zip> [detail](#usenet-uk-and-edu-header-fqdns) |
| usfedgov_extract_1996_2000_hostname_grain | 2026-09-02 fleet 20260902T0232Z | 1996-2000 | cdx query | the 14-digit CDX capture timestamp on the row itself (`20000508164730`-form), written by the crawler at fetch time;. | n/a | 18702.8 EE (2026-09-02) | FIND at 18702.8 EE, against the ark-data sync. Artifact: < <year>/USFEDGOV-EXTRACT-<year>.cdx.gz>. no probe needed after | n/a | FIND | <https://archive.org/download/USFEDGOV-EXTRACT-> [detail](#usfedgov-extract-1996-2000-hostname-grain) |
| dartmouth_captures_hostname_grain | 2026-09-02 fleet 20260902T0034Z | n/a | cdx query | field 2 of the CDX row, the 14-digit capture timestamp written by the archive (`cdx_timestamp`), identical to what dates the banked | n/a | 0 EE (2026-09-02) | FIND at 0 EE, against the ark-data sync. Artifact:. ARM 1 | n/a | FIND | <https://archive.org/download/DARTMOUTH-NBER-RESEARCH-2017-metadata/domain-year-captures.txt> [detail](#dartmouth-captures-hostname-grain) |
| early_web_cdx_hostname_grain | 2026-09-02 fleet 20260902T0034Z | 1996-1999 | cdx query | the row's own 14-digit capture timestamp, field 2 of the classic CDX line, class `cdx_timestamp`, quoted beside the hostname exactly as the | n/a | 631215.8 EE (2026-09-02) | FIND at 631215.8 EE, against the ark-data sync. Artifact:. no probe needed, the whole artifact is | 177 MB, 224 files | FIND | <https://archive.org/details/early-web_cdx-lang-cdxa> [detail](#early-web-cdx-hostname-grain) |
| ripe1999_nserver_hostnames | 2026-09-02 fleet 20260902T0034Z | 1999 | ftp listing | the dump's own machine-written cut stamp on line 2 of the payload, `# 990804 00:07:01`, the same stamp `ripe_dbase_1999` was approved on.. | n/a | 11400 EE (2026-09-02) | FIND at 11400 EE, against the ark-data sync. Artifact:. no probe needed: the artifact is one 71,919,736 B file | n/a | FIND | <https://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz,> [detail](#ripe1999-nserver-hostnames) |
| usfedgov_extract_hostname_grain | 2026-09-02 fleet 20260902T0034Z | 2001 | cdx query | the CDX capture timestamp on the row itself, `20011128173757`-form, written by the crawler at fetch time;. | n/a | 21713 EE (2026-09-02) | FIND at 21713 EE, against the ark-data sync. Artifact:. whole 2001 merged ZipNum index read, not a sample: 48,110,425 | n/a | FIND | <https://archive.org/download/USFEDGOV-EXTRACT-2001/USFEDGOV-EXTRACT-2001.cdx.gz,> [detail](#usfedgov-extract-hostname-grain) |
| banked_lists_hostname_grain | 2026-09-02 fleet 20260901T2358Z | n/a | n/a | unchanged from the banked registrable ingests: squidGuard's machine-written compile stamp `# This list was compiled in .... | n/a | 2967.5 EE (2026-09-02) | FIND at 2967.5 EE, against the ark-data sync. Artifact:. The whole population, not a sample, because both artifacts are | 2 MB | FIND | <http://archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz> [detail](#banked-lists-hostname-grain) |
| usenet_header_fqdn_census | 2026-09-02 fleet 20260901T2358Z | n/a | http download | the message's own `Date:` header (and for X-Trace rows the injecting server's own epoch stamp, e.g.. | n/a | 6877 EE (2026-09-02) | FIND at 6877 EE, against the ark-data sync. Artifact:. `demon.ip.support.pc.mbox.zip` (15,308,303 B, 17,469 messages) then | 17,469 messages | FIND | <https://archive.org/download/usenet-demon/demon.ip.support.pc.mbox.zip> [detail](#usenet-header-fqdn-census) |
| hostname_benchmark_headroom | 2026-09-02 fleet 20260901T2246Z | n/a | n/a | nothing, this is a coverage measurement over held files. | n/a | 0 EE (2026-09-02) | FIND at 0 EE, against the ark-data sync. not a source. | n/a | FIND, not a source | n/a [detail](#hostname-benchmark-headroom) |
| usenet_header_fqdn_census | 2026-09-02 fleet 20260901T2246Z | n/a | http download | the message's own `Date:` header fixes the year;. | n/a | 2368 EE (2026-09-02) | FIND at 2368 EE, against the ark-data sync. Artifact: < <group>.mbox.zip>. four archive.org `usenet-` mbox zips, 44.4 MB compressed, 76,889 messages, parsed in-stream, nothing extracted. | 44.4 MB, 76,889 messages | FIND | <https://archive.org/download/usenet-demon/> [detail](#usenet-header-fqdn-census-2) |
| zone_ns_glue_hostnames | 2026-09-02 fleet 20260901T2246Z | 1997 | wayback replay | the zone's own SOA serial `1997041800` on line 2 of the payload (all three zones), fixed in time by IA captures 19970420113748 (org) | n/a | 11862.5 EE (2026-09-02) | FIND at 11862.5 EE, against the ark-data sync. Artifact:. the whole 1997 lane, not a sample: org+edu+gov zones | n/a | FIND | <https://web.archive.org/web/19970420113748id_/http://nic.mil/oroot.html/org.zone.gz> [detail](#zone-ns-glue-hostnames) |
| cdx_nonzero_status_rows | 2026-09-01 fleet 20260901T1557Z | 1998 | cdx query | the CDX capture timestamp of a non-200 response.. | n/a | 33.35 EE (2026-09-01) | FIND at 33.35 EE, against the ark-data sync. Artifact:. TWO already-ingested `nypw_timemaps` parts, chosen so that every HTTP-200 row is guaranteed already banked and any net-new | n/a | FIND | <https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_deeplinks_part01o.tar.gz> [detail](#cdx-nonzero-status-rows) |
| gap_queue_high_weight_tld_tail | 2026-09-01 fleet 20260901T1400Z | n/a | none, screened | nothing.. | n/a | 0 EE (2026-09-01) | FIND at 0 EE, against the ark-data sync. no probe and no fetch, because the whole hypothesis is one query over the store, which | n/a | FIND | n/a [detail](#gap-queue-high-weight-tld-tail) |
| parked_approval_queue_reprice | 2026-09-01 fleet 20260901T1400Z | n/a | n/a | nothing new is dated here.. | n/a | 12024 EE (2026-09-01) | FIND at 12024 EE, against the ark-data sync. the kill screen was five parked sources. | n/a | FIND | n/a [detail](#parked-approval-queue-reprice) |
| Law 1 conditional test: is IA-derived net-new only on domains we've never queried? | 2026-09-01 | 1999-2001 | cdx query | is the TimeMap's `cdx_timestamp`. | n/a | 0 EE (2026-09-01) | FIND, 0 EE net-new banked, redirects an existing collector. Measured against `data/raw/cdx/.jsonl.gz` (1,137 journals) and NYPW's 1,306,611 pairs: Law 1 splits into discovery (holds absolutely: 14 of | 1,137 journals | FIND | n/a [detail](#law-1-conditional-test-is-ia-derived-net-new-only-on-domains-we-ve-nev) |
| Nerd World "What's New" register tree | 2026-09-01 | n/a | wayback replay | the Wayback capture stamp on each category page (`dated_directory`), machine-written but not printed inside the artifact itself; 399 of | n/a | 235.0 EE (2026-09-01) | FIND, 235.0 EE, parked pending (fails standing-rule condition 2). | n/a | FIND | <https://web.archive.org/web/20011030063818id_/http://www.nerdworld.com/whatsnew.html> [detail](#nerd-world-what-s-new-register-tree-https-web-archive-org-web-20011030) |
| URLMerchant's for-sale inventory, continued past its first 244 pages | 2026-08-31 | 1999-2000 | n/a | is unchanged, the page's own `<META NAME="UPDATED">` generator stamp. | 13.6% held | 606.3 EE (2026-08-31) | FIND, in progress: 606.3 EE measured over 974 net-new post-split pairs from 95 pages fetched at 2001 captures, projecting to 9,254 EE across the full ~1,562-page namespace; still | 95 pages | FIND | n/a [detail](#urlmerchant-s-for-sale-inventory-continued-past-its-first-244-pages) |
| The RDAP 404 verdict as a LIVENESS PRIOR on the CDX gap queue: does a name that is unregistered today answer a 2001 | 2026-08-31 | 2000-2001 | none, screened | n/a | n/a | 900 EE (2026-08-31) | FIND, and the mechanism is confirmed at z = 53.6 while the economics miss the hypothesis' own 900 EE/hour floor by 6x to 9x. Measured +0.0805 EE per `.com` | 6.5 GB, 1,112 files | FIND, not a source | n/a [detail](#the-rdap-404-verdict-as-a-liveness-prior-on-the-cdx-gap-queue-does-a-n) |
| A pre-1999 RIPE database split, an edition of `ripe.db` dated 1996, 1997 or 1998 | 2026-08-31 | 1996-2001 | archive.org search api | is the object's own `changed:` transaction line, `changed: ovema@a.sol.no 19971128` under `domain: hasselblad.gm`, the database's record of | n/a | 502 EE (2026-08-31) | The hypothesis' | n/a | worth | <https://ftp.funet.fi/pub/netinfo/RIPE/dbase/split/ripe.db.domain.gz> [detail](#a-pre-1999-ripe-database-split-an-edition-of-ripe-db-dated-1996-1997-o) |
| The on-disk URL corpus as an artifact FINDER: which PATHS we already hold promise a machine dump | 2026-08-30 | 2001 | none, screened | is the Wayback capture stamp on the page and nothing inside it, and the names are human-typed, so they take the | 32.0% held | 157.8 EE (2026-08-30) | n/a | n/a | FIND | <https://web.archive.org/web/20011023104545id_/http://www.domainsww.com/Domain_Listing.htm> [detail](#the-on-disk-url-corpus-as-an-artifact-finder-which-paths-we-already-ho) |
| Public Mailman subscriber rosters, the membership table rather than the messages | 2026-08-30 | 2001 | cdx query | n/a | 96.8% held | 89.4 EE (2026-08-30) | FIND, 89.4 net-new post-split EE over 179 pairs, 178 of them at 2001, parked on condition 2 of the standing rule. Five in-window rosters | 868 MB | FIND | <https://web.archive.org/web/20010717203344id_/http://mail.python.org:80/mailman/roster/mailman-users> [detail](#public-mailman-subscriber-rosters-the-membership-table-rather-than-the) |
| Registry whois records transcribed into artifacts that stamp themselves: pasted whois blocks in the on-disk Usenet | 2026-08-30 | 1998-2000 | robots refusal | n/a | 92.1% already held | 30.4 EE (2026-08-30) | FIND, BANKED at 30.4 EE on the Usenet arm (see `usenet_whois_paste` below), the UDRP arm PARKED. The Usenet arm reads the registry's own `Record created on 20-Jul-2000.` line out | n/a | FIND | n/a [detail](#registry-whois-records-transcribed-into-artifacts-that-stamp-themselve) |
| Free-DNS hosted-zone inventories, the nameserver's own list of the zones it was configured to serve (Granite Canyon | 2026-08-29 | 1999-2001 | cdx query | the list stamps its own generation instant (`Rejected Zone List: 7-May-2001 22:11 GMT`; status.shtml's "29 November 1999 ... | 99.3% held | 1,732.9 EE (2026-08-29) | FIND at 1,732.9 net-new post-split EE over 3,059 pairs from | 18,797 items | FIND | n/a [detail](#free-dns-hosted-zone-inventories-the-nameserver-s-own-list-of-the-zone) |
| Free-for-all (FFA) link pages, ffanet.com and the networks around it, where the self-dating premise is REFUTED and the | 2026-08-28 | 1997-2001 | robots refusal | the Wayback capture instant of a member FFA page, which displays the posted link as live text at that instant. | 91.35% held | 25.2 EE (2026-08-28) | FIND at 25.2 net-new post-split EE over | 9 pages | FIND | <http://pages.ffanet.com:80/links/> [detail](#free-for-all-ffa-link-pages-ffanet-com-and-the-networks-around-it-wher) |
| 2001 nonprofit portals, a FIND that closes its own family, and the head-selection law operating INSIDE one directory | 2026-08-28 | 2000-2001 | wayback replay | n/a | 98.43% held | 202.2 EE (2026-08-28) | FIND at 202.2 net-new post-split EE over 289 pairs, all at 2001, mean weight 0.6996 (org 257 / com 29 / net 3), from 19 dated pages and 601,956 B; and the family is CLOSED at that | 1KB | FIND | n/a [detail](#2001-nonprofit-portals-a-find-that-closes-its-own-family-and-the-head-) |
| Seal and certification rosters, the one shape of "customer showcase" that pays | 2026-08-27 | 1999-2001 | cdx query | n/a | 93.6%) are adjacent held | 1,581.7 EE (2026-08-27) | FIND, 1,581.7 net-new post-split EE over 2,554 pairs, and a discriminator that splits the family in two. BBBOnLine's Reliability participant | 3,574,800 bytes, 36 requests | FIND | <http://www.bbbonline.org/search/Relresult.asp?letter=> [detail](#seal-and-certification-rosters-the-one-shape-of-customer-showcase-that) |
| Bruce Guenter's spam archive re-priced: the advertised URL is refuted and the RECIPIENT header is the find | 2026-08-27 | 1997-1998 | robots refusal | n/a | 91.1% held | 1,288.1 EE (2026-08-27) | 1,288.1 net-new post-split EE over 3,053 pairs, 6.6x the 2026-08-15 reading of the same bytes, and the hypothesis that produced it is refuted with the sign | 78,753,891 bytes, 20,010 messages | n/a | n/a [detail](#bruce-guenter-s-spam-archive-re-priced-the-advertised-url-is-refuted-a) |
| Free-hosting and ISP member indexes, re-tested at 2001 on the right screen | 2026-08-27 | 2000-2001 | robots refusal | n/a | 97.4% already held | 0.0 EE (2026-08-27) | Still 0.0 EE, and now for the right reason, plus a mechanism that generalises. The 2026-08-08 closure used the RETIRED novelty screen ("617 domains at 97.4% already held"), written 17 days before the | 17,627 bytes, 17 days | n/a | n/a [detail](#free-hosting-and-isp-member-indexes-re-tested-at-2001-on-the-right-scr) |
| Site Meter and the counter-service lens, re-proposed and closed without a fetch | 2026-08-27 | 1998-2001 | http download | n/a | n/a | 0 EE (2026-08-27) | 0 EE, duplicate lens. The hypothesis named theCounter, NedStat, eXTReMe Tracking and Site Meter; the counter-directory row above sizes the first three by name in the same sweep (`nedstat.com` 3,392 in-window captures | 483 captures | n/a | n/a [detail](#site-meter-and-the-counter-service-lens-re-proposed-and-closed-without) |
| The "Wayback refused this IP" hour, measured: it was not us, not a block, and not that hour | 2026-08-27 | n/a | cdx query | n/a | n/a | n/a | The refusal is real but it is REPLAY ONLY, and the concurrency hypothesis is refuted three ways. The flag said `web.archive.org` refused this IP at the TCP layer through most of the 15:00 UTC hour while `ark cdx` ran two | 26.9 minutes, 233 queries | n/a | n/a [detail](#the-wayback-refused-this-ip-hour-measured-it-was-not-us-not-a-block-an) |
| The Debian package archive as a blocklist seam, and the one find in it | 2026-08-27 | 1998-2001 | robots refusal | n/a | 94.0% held | 14,229.0 EE (2026-08-27) | 14,229.0 EE found, and the method is the reusable part: ONE request per release indexes every package in it. `archive.debian.org` has no robots.txt, and `dists/<rel>/main/binary-i386/Packages.gz` carries every package | 104 KB | n/a | n/a [detail](#the-debian-package-archive-as-a-blocklist-seam-and-the-one-find-in-it) |
| The `tomocha.net` refusal, applied to one file and not the other | 2026-08-27 | 1999 | robots refusal | n/a | n/a | 1,623 EE (2026-08-27) | An inconsistency in this register, found by the same consistency check that caught the RDAP terms, and it currently costs nothing. `tomocha.net/robots.txt` carries `User-agent: ClaudeBot` / `Disallow: /` at lines 51-52, and on 2026-08-25 | n/a | n/a | n/a [detail](#the-tomocha-net-refusal-applied-to-one-file-and-not-the-other) |
| The expansion corpus's unpromoted half | 2026-08-27 | n/a | n/a | n/a | n/a | 3 EE (2026-08-27) | A real gap in the promotion tool worth about 3 EE. `build_promotion_journals.py` covers eight mention sources and `page_expansion` is not one of them, so its candidate half had never been re-promoted. By the re-split law that should pay; it | n/a | worth | n/a [detail](#the-expansion-corpus-s-unpromoted-half) |
| Ranking the candidate pool by corroboration instead of by a modelled hit rate | 2026-08-27 | n/a | n/a | n/a | n/a | 209,036 EE (2026-08-27) | Built, measured, and deliberately NOT switched into a running engine. The modelled ranking's failure mode is fabricated names, so the fix is a filter the model cannot express: how many INDEPENDENT sources name the string at all. Over the | n/a | n/a | n/a [detail](#ranking-the-candidate-pool-by-corroboration-instead-of-by-a-modelled-h) |
| Re-splitting a mention corpus against a grown store, measured twice | 2026-08-27 | n/a | n/a | n/a | n/a | 30,645.6 EE (2026-08-27) | The largest lever found in this round, and it reads nothing new. The corroboration split promotes a mention to a dated record only when some OTHER source already places that domain in a year, and that test is re-evaluated on every split | 08 journals | n/a | n/a [detail](#re-splitting-a-mention-corpus-against-a-grown-store-measured-twice) |
| FUNET's frozen `netinfo` mirror, swept by its own index | 2026-08-27 | 1996-2001 | robots refusal | n/a | n/a | 66,701.7 EE (2026-08-27) | The one-request `ls-lR` trick worked and the prize it named is gone, but the lead it leaves is worth finishing. FUNET is the host that supplied `ripe_dbase_1999` and has NO robots.txt at all, so nothing there forbids us. | 351,368 bytes, 563 files | worth | n/a [detail](#funet-s-frozen-netinfo-mirror-swept-by-its-own-index) |
| The bare-hostname Usenet seam, priced over the pools still on disk | 2026-08-27 | n/a | bytes already on disk | n/a | n/a | 128.17 EE (2026-08-27) | 128.17 EE over 400 archives, projecting to 514-1,007 EE over all 16,797, so worth free CPU and nothing more. `collect_usenet_bare.py` reads the plain `foo.com` in running prose that no other extractor sees, and it had the same | 3,922,752 messages | worth | n/a [detail](#the-bare-hostname-usenet-seam-priced-over-the-pools-still-on-disk) |
| The rebuilt candidate-pool CDX queue, an 80x collapse and a measured revert | 2026-08-27 | n/a | cdx query | n/a | n/a | n/a | Recorded as a measurement, deliberately NOT as a law about ranking, because that mistake has already been made once here. Rebuilding `queue_pool_local.txt` against the new baseline took the local engine from 1.15-1.66 years per query, over | 342 requests | n/a | n/a [detail](#the-rebuilt-candidate-pool-cdx-queue-an-80x-collapse-and-a-measured-re) |
| The whole RDAP query route, closed on the registries' own terms | 2026-08-27 | n/a | rdap query | n/a | n/a | 459,792.0 EE (2026-08-27) | The terms were inside every response the entire time, in the `notices` block, so this cost nothing to find and three days of engine time not to. Read out of our own journals for Verisign, PIR and Nominet, and from the page Verisign's notice | n/a | find | n/a [detail](#the-whole-rdap-query-route-closed-on-the-registries-own-terms) |
| The VPS RDAP journals nobody had banked, priced at zero | 2026-08-27 | n/a | rdap query | n/a | n/a | 0.00 EE (2026-08-27) | A collector alive for 45 hours writing nothing, and 85 MB of journal that paid 0.00 EE. The VPS sibling sweep showed `up 2-16:29` in the process table while its newest journal had last been written at 2026-08-25 08:51:28 UTC. Six `.part` | 85 MB, 45 hours | n/a | n/a [detail](#the-vps-rdap-journals-nobody-had-banked-priced-at-zero) |
| The residual audit's `unread` flag, priced | 2026-08-27 | 2000-2001 | cdx query | n/a | n/a | 22.2 EE (2026-08-27) | Worth 22.2 EE, not the "cheapest yield in the project" the audit calls it, because it counts FILES and not value. Four files matched a documented ingest glob and no ingest had read them. Three are `us_domain_delegated` captures at | 435,847 bytes, 20010606 editions | Worth | n/a [detail](#the-residual-audit-s-unread-flag-priced) |
| Every RDAP-served TLD ranked by headroom, the family closed on measurement | 2026-08-27 | n/a | robots refusal | n/a | n/a | 25,377 EE (2026-08-27) | Systematic rather than guessed, and `.ca` is the only one worth a conversation. The IANA bootstrap was joined against our own holdings and each TLD priced at held-domains x weight x the 29.3% | n/a | worth | <https://rdap.ca.fury.ca/rdap/domain/rita.ca> [detail](#every-rdap-served-tld-ranked-by-headroom-the-family-closed-on-measurem) |
| The VPS journal backlog, and why the cycle undercounted it | 2026-08-27 | n/a | cdx query | n/a | n/a | 40,893.6 EE (2026-08-27) | 125 journals had never come home and they were worth 40,893.6 EE, which is more than everything else this night produced combined. `just cycle` reported "rsync 2 VPS journals home"; the real diff between the two machines was 125 files and | 416 MB, 125 journals | worth | n/a [detail](#the-vps-journal-backlog-and-why-the-cycle-undercounted-it) |
| Scholarly-index sweep for deposited early-web data | 2026-08-24 | n/a | n/a | n/a | n/a | n/a | Failed positive control: OpenAlex `early web` returns 314 works and not one is the UMN DRUM dataset already ingested here. `type:dataset` 1996-2005 with web/URL/domain returns 3,363 works and no URL corpus; `domain` in scholarly search | n/a | n/a | n/a [detail](#scholarly-index-sweep-for-deposited-early-web-data) |
| The pre-Nominet and Nominet `.uk` register | 2026-08-24 | n/a | port 43 whois | n/a | n/a | 1.96 EE (2026-08-24) | The file never existed. 12,491 captures over 2,710 URLs of `nic.uk`, `nominet.org.uk`, `nominet.net`; largest object ever served is a 94,785-byte membership list, worth 2 net-new pairs, 1.96 EE. Register exposed only per-name | 12,491 captures | worth | n/a [detail](#the-pre-nominet-and-nominet-uk-register) |
| `.us` locality registers, Granite Canyon, and a 20,000 EE wildcard | 2026-08-24 | n/a | n/a | n/a | n/a | 39.6 EE (2026-08-24) | `.us` locality registers 39.6 EE, 0 novel names on all four states tested. Granite Canyon secondary-DNS artifacts 1,881.1 EE post-split against a 5,000 bar. Best wildcard candidate, Nominet's member list, 507.96 EE. | n/a | n/a | n/a |
| `ark gaps` queue ranking | 2026-08-24 | n/a | n/a | n/a | n/a | 264,814 EE (2026-08-24) | Not a source: the bracketed-gap queue, 451,490 domains at a 264,814 EE ceiling, ranks by weight and returns 31 years from 600 queries (5.2%) against 673 years from 600 on the `.com`-heavy file it replaced. Reordered to put | 600 queries | not a source | n/a [detail](#ark-gaps-queue-ranking) |
| Not Your Parents' Web TimeMaps, deferral converted to REJECT | 2026-08-24 | 1996-2001 | wayback timemap | n/a | n/a | 14.2 EE (2026-08-24) | Tested at `1996/..._deeplinks_part00o.tar.gz`, 5,641,617 bytes: 17,035 in-window pairs, 17,006 already held, 29 net-new, 14.2 EE. Folder year is year of first archive, not of content, so the 1996 folder's net-new pairs land in 1998, 1999 | 5,641,617 bytes | n/a | n/a [detail](#not-your-parents-web-timemaps-deferral-converted-to-reject) |
| Wayback `__wb/sparkline` endpoint | 2026-08-24 | n/a | cdx query | n/a | n/a | n/a | Right shape, same rate limiter. Head to head over 80 gap-queue domains: sparkline 8 of 80 at 1.93 q/s, CDX 7 of 80 at 0.93 q/s. Twice as fast per attempt and no less refused. | n/a | n/a | n/a |
| The re-registration rule, re-measured | 2026-08-24 | n/a | rdap query | n/a | n/a | n/a | Of 370 answering RDAP records over 472 seeded-random capture-dated domains, 59.7% still carry an in-window creation date. Transfer, bankruptcy and change of owner never reset it (EFF 1990-10-10, Pets 1994-11-21, Napster 1999-02-20). | n/a | n/a | n/a |
| Arquivo.pt live CDX as a dating engine | 2026-08-24 | n/a | cdx query | n/a | n/a | n/a | Answers 17.3 q/s, 250 of 250 HTTP 200, and holds nothing needed: 0 in-window 200s over 250 candidate-pool names and 0 over 157 domains our store already dates in window. | n/a | n/a | n/a |
| RDAP over the candidate pool | 2026-08-24 | n/a | rdap query | n/a | n/a | 1,658,653 EE (2026-08-24) | The 2,395,205 undated names would be worth 1,658,653 EE, and two pilots of 3,000 returned 0 in-window creation dates (336 answers, 234 of them 404; 266 answers, 195 of them 404). | n/a | worth | n/a |
| Registry change reports across five regions | 2026-08-24 | n/a | n/a | n/a | n/a | 7,500 EE (2026-08-24) | Paid about 7,500 EE over eight small artifacts (TWNIC 1,275.0, SaudiNIC 1,506.4, NIC Malta 1,470.5, NIC Venezuela 1,131.3, IDNIC 872.6, RESTENA 708.5, ISOC-IL 375.0, `.nu` 144.1). gTLD side empty: the only in-window listing is | n/a | n/a | n/a [detail](#registry-change-reports-across-five-regions) |
| National register listings, the `.ie` shape across nine namespaces | 2026-08-24 | n/a | n/a | n/a | n/a | n/a | Two paid (`.my` MYNIC, `co.za`), six empty on measurement: `.nz` whole Domainz site is 170 URLs yielding 5 and 1 names, `.au` largest AUNIC page yields 10 names all worked examples, `.ca` counts only, `.sg` and `.hk` no listing, `.ph` a | n/a | n/a | n/a [detail](#national-register-listings-the-ie-shape-across-nine-namespaces) |
| Pricing on parser `raw` rather than canonical form | 2026-08-24 | n/a | n/a | n/a | n/a | 4,509.1 EE (2026-08-24) | `ukwa_geoindex` priced at 4,509.1 EE over 4,595 pairs, admitted at 4,493.0 over 4,591. Joining `BulkRecord.raw` URLs against `domain_year` finds zero held and returns top TLDs `htm` 2,106,483 and `html` 2,055,761. After canonicalisation | n/a | priced | n/a [detail](#pricing-on-parser-raw-rather-than-canonical-form) |
| DataCite sweep for deposited early-web datasets | 2026-08-24 | n/a | http api | n/a | n/a | n/a | Eight query shapes against `api.datacite.org/dois` surface nothing not already held: link list/graph plus web gives 21 hits, the only in-window one the UKWA host link graph; `early web` gives 19 hits whose only deposits are UMN DRUM and the | n/a | n/a | n/a [detail](#datacite-sweep-for-deposited-early-web-datasets) |
| Nominet RDAP over held `.uk`, banked | 2026-08-24 | n/a | rdap query | n/a | n/a | 118.8 EE (2026-08-24) | Banked, no approval needed. `rdap.nominet.uk` publishes a machine-written `registration` event with a full timestamp, verified `demon.co.uk 1996-05-05T21:08:48Z`, reached through the IANA bootstrap by `ark rdap`. Evidence type | 1,000 queries | Banked | n/a [detail](#nominet-rdap-over-held-uk-banked) |
| UCSF Industry Documents Library | 2026-08-24 | n/a | n/a | n/a | n/a | 146.6 EE (2026-08-24) | 3,826,999 in-window documents with per-document `documentdate`, and 6,000 fetched give 216 pairs for 146.6 EE after the corroboration split, because 89% of the net-new names are dated nowhere else. Whole-population projection about 730 EE | n/a | n/a | n/a [detail](#ucsf-industry-documents-library) |
| Organisational mail releases beyond Enron | 2026-08-24 | n/a | n/a | n/a | n/a | 4,011 EE (2026-08-24) | One real member, 67x short: `jeb_bush_gubernatorial_email`, 411,928,998 bytes, 626 born-digital files, 519,581 in-window `Sent:`/`Date:` headers, 4,011 EE over 6,412 net-new post-split pairs of which only 1,607.7 EE comes from a `To:`/`Cc:` | 411,928,998 bytes | n/a | n/a [detail](#organisational-mail-releases-beyond-enron) |
| Generated RDAP target populations, and what ORDER to query them in | 2026-08-24 extended 2026-08-27 | n/a | rdap query | n/a | 92.4% already held | 13.5 EE (2026-08-24) | Four populations of 1,500 to 3,000 names queried direct to Verisign: English dictionary words 13.5 EE per 1,000 queries (28.00% in-window) but finite at ~235,000 words and 92.4% already held, sibling TLDs of held names | 1,000 queries | n/a | n/a [detail](#generated-rdap-target-populations-and-what-order-to-query-them-in) |
| Internet Archive bulk CDX / ZipNum index | 2026-08-16 | 1999 | cdx query | n/a | n/a | n/a | Not public. `archive.org/metadata/wayback-cdx-index` returns `{}` and `cdx/search/cdx?url=.com&from=1999&to=1999` returns HTTP 403. The 403 is policy, not an outage: do not re-probe. | n/a | n/a | n/a |
| UKWA ds.1 classification list | 2026-08-16 | 2001 | wayback replay | n/a | n/a | n/a | Recovered from Wayback at `opendata/ukwa.ds.1/classification/classification.tsv`, 3,011,797 bytes over 26,910 rows, and deliberately not ingested: columns are category, title and URL with no date field of any kind, so it is candidate-pool | 3,011,797 bytes | n/a | n/a [detail](#ukwa-ds-1-classification-list) |
| Library catalogue records with a MARC 856 URL, measured | 2026-08-16 | n/a | n/a | n/a | n/a | n/a | 47 qualifying records in 48.2 MB of Scriblio give 13 domains, 12 already held, one net-new and that one a public-suffix subdomain. Dating and URL-bearing are anticorrelated: LC books carry an in-window MARC 005 on 28.25% of records and hold | 48.2 MB | n/a | n/a [detail](#library-catalogue-records-with-a-marc-856-url-measured) |
| Search engine indexes 1996-2001, the whole family | 2026-08-16 | 1996-2001 | n/a | n/a | n/a | n/a | Not one machine-readable dated hostname list survives. AltaVista's May 1999 crawl of 203M URLs was never published and Yahoo Webscope no longer resolves; six archive.org sweeps over Lycos, Excite, HotBot/Inktomi, Infoseek, Northern Light | n/a | n/a | n/a [detail](#search-engine-indexes-1996-2001-the-whole-family) |
| IPEDS institutional characteristics | 2026-08-16 | 1999 | n/a | n/a | n/a | 100.8 EE (2026-08-16) | Of 3,251 domains in `IC99_HD`, 2,946 are already dated 1999, the exact year the file attests, leaving 147 post-split pairs and 100.8 EE. The web-address column exists for one in-window year only. `.edu` is 95.5% saturated at the year an | n/a | n/a | n/a [detail](#ipeds-institutional-characteristics) |
| Unheld Usenet hierarchies, IA `usenethistorical` | 2026-08-16 | n/a | n/a | n/a | n/a | n/a | Deferred. Of the unheld remainder only about 40 GB is English-facing (`microsoft` 26.6 GB) and about 135 GB is national hierarchies an English-weighted metric discounts to near nothing. | 40 GB | Deferred | n/a |
| Not Your Parents' Web TimeMaps, IA `nypw_timemaps` | 2026-08-16 | n/a | cdx query | n/a | n/a | n/a | Deferred on cost: in-window folders total 19,350,762,163 bytes, field 3 of a TimeMap line is a 14-digit capture timestamp so the year is per-record, but the methodology paper (arXiv:2507.14752) documents downsampling and the sibling | 19,350,762,163 bytes | Deferred | n/a [detail](#not-your-parents-web-timemaps-ia-nypw-timemaps) |
| Parallel Language Records of the Early Web | 2026-08-16 | 2000 | n/a | n/a | n/a | n/a | No date of any kind in a record: README plus shard 00 (42,290 lines) confirm SURT pattern then `<lang> <url>`, the only date being collection-level "captured before year 2000". Its 1,164,183 records also select for multilingual mirrors, top | n/a | n/a | n/a [detail](#parallel-language-records-of-the-early-web) |
| Netcraft Web Server Survey `/domains/cache/` listings | 2026-08-12 | n/a | n/a | n/a | n/a | n/a | Candidate-only: 0 pairs as master, 13,078 names stay in the pool. The pages are machine-generated alphabetical dumps with no per-item date, so they died on contemporaneity rather than on the corroboration split. | n/a | n/a | n/a |
| INET conference proceedings 1996 to 2001 | 2026-08-11 | 1996-2001 | wayback replay | n/a | n/a | 12.7 EE (2026-08-11) | 460 in-window pairs, 416 already held, 19 net-new after the split worth 12.7 EE over 223 pages; whole-corpus estimate 116 EE. `isoc.org` 301-redirects every proceedings path to web.archive.org, so the source is IA-only. | 223 pages | worth | n/a |
| Debian package changelogs and upstream homepage fields | 2026-08-11 | n/a | n/a | n/a | n/a | 14.4 EE (2026-08-11) | 803 in-window pairs, 762 already held, 21 net-new after the split worth 14.4 EE. The named mechanism does not exist in window: grep for `Homepage:` returns 0 across all 36 in-window index files, because it entered Debian policy around 2007. | n/a | worth | n/a |
| W3C technical reports index | 2026-08-11 | n/a | n/a | n/a | n/a | 36.1 EE (2026-08-11) | Census, not sample: 626 in-window reports yield 1,225 pairs, 1,078 already held, 56 net-new after the split worth 36.1 EE, 87x below the bar. Trap: W3C retrofits post-window status banners into archived recommendations. | n/a | worth | n/a |
| RFC and Internet-Draft documents | 2026-08-11 | n/a | n/a | n/a | n/a | 88.2 EE (2026-08-11) | Complete RFC population plus a 12.2% draft sample: 3,605 in-window pairs, 3,151 already held, 140 net-new after the split worth 88.2 EE. The split does not protect against fictional hostnames, and this corpus is full of them | n/a | worth | n/a [detail](#rfc-and-internet-draft-documents) |
| Microsoft Bookshelf Internet Directory, 1996 CD-ROM | 2026-08-11 | 1996 | n/a | n/a | n/a | 4.7 EE (2026-08-11) | 7 net-new pairs and 4.7 EE after the split. The 99 MB ISO yields 2,020 distinct (domain, 1996) pairs of which 1,863, or 92.2%, are already held. | 99 MB | n/a | n/a |
| Linux Software Map, ibiblio LSM snapshots | 2026-08-10 | n/a | n/a | n/a | n/a | 37.3 EE (2026-08-10) | 86 net-new pairs and 37.3 EE after the split. Each `Begin3 .. End` block carries its own `Entered-date` beside `Primary-site`, so the dating is ideal and the population is wrong: 3,743 of 3,951 in-window pairs, 94.7%, are already held. | n/a | n/a | n/a |
| SEC EDGAR filings 1996-2001 | 2026-08-08 | 1996-2001 | n/a | n/a | n/a | 1.9 EE (2026-08-08) | 150 filings stratified across six years, 150 of 150 reachable, 61.1 MB, 46 pairs in total, 4 net-new and 1.9 EE, or 0.01 EE per filing. Filers that print URLs are the large public companies the baseline holds first. | 61.1 MB | n/a | n/a |
| InterNIC public zone files via Wayback | 2026-08-08 | n/a | wayback replay | n/a | n/a | n/a | Absent: `internic.net` under `matchType=domain` holds 8,001 captures of which 16 resemble data and those are single-domain whois lookups; `ftp.internic.net/domain` captures are 435-byte stubs. Trap: `url=host/path/` with `matchType=prefix` | 8,001 captures | n/a | n/a [detail](#internic-public-zone-files-via-wayback) |
| Usenet `Path:` relay chains | 2026-08-08 | n/a | n/a | n/a | 99.32% of sampled pairs are already held | 13.89 EE (2026-08-08) | 7.1M accepted hops over a 400-archive sample collapse to 4,736 domains and 7,201 pairs, of which 49 are net-new after the split: 13.89 EE. A relay is a large ISP or university, so 99.32% of sampled pairs are already held or uncorroborated. | n/a | n/a | n/a |
| Other national web archives, non-Nordic | 2026-08-08 | n/a | cdx query | n/a | n/a | n/a | Australia's AWA is the only open in-window index and it is IA data: 13 of 13 cross-checked domains return identical year sets from AWA and the IA CDX, 0 AWA-only pairs, every in-window row from `NLA-EXTRACTION-1996-2004-ARCS-PART-`. Japan | n/a | n/a | n/a [detail](#other-national-web-archives-non-nordic) |
| Nordic and Baltic national web archives | 2026-08-08 | n/a | cdx query | n/a | n/a | n/a | Seven of eight have no public in-window index. Iceland's `vefsafn.is` pywb CDX serves in-window captures but cannot be enumerated, capping the addressable set at 2,540 known `.is` names: 66 lookups, 0 unknown domains, 867 projected EE. | n/a | n/a | n/a [detail](#nordic-and-baltic-national-web-archives) |
| Shareware and CD-ROM catalogues beyond Tucows | 2026-08-08 | n/a | n/a | n/a | n/a | 134.15 EE (2026-08-08) | Info-Mac worked to exhaustion: 2,604 domains, 2,477 already held, 234 pairs, 134.15 EE. garbo.uwasa.fi's master index contains one domain, its own. Trap: an archive.org software scrape reports 682 net-new domains and all are spurious | n/a | n/a | n/a [detail](#shareware-and-cd-rom-catalogues-beyond-tucows) |
| Free-hosting member indexes: GeoCities, Tripod, Angelfire, Xoom, FortuneCity, Homestead | 2026-08-08 | n/a | n/a | n/a | 97.4% already held | n/a | Collapses architecturally: every member URL is a path or subdomain under the provider's own domain and all ten provider domains are held. 0 member-owned registered domains from 4 index pages; the member-links fallback gives 617 domains at | n/a | n/a | n/a |
| Award galleries and cool-site lists | 2026-08-08 | 1996 | n/a | n/a | n/a | 3.16 EE (2026-08-08) | 206 domains across 7 dated award pages: 2 net-new domains (0.97%), 5 net-new pairs, 3.16 EE. `point.lycos.com` gives 1 outbound domain in a 90 KB, 484-href 1996 listing page. | 90 KB | n/a | n/a |
| Institutional link directories: university, library, government, museum | 2026-08-08 | n/a | n/a | n/a | n/a | 1.96 EE (2026-08-08) | 386 of 388 domains across 11 archived BUBL LINK pages are already held: 2 net-new domains, 5 pairs, 1.96 EE. The best-case page, a worldwide museums directory with 192 external links, gave 0. | n/a | n/a | n/a |
| Research crawl datasets, remaining angles | 2026-08-08 | n/a | n/a | n/a | n/a | 374 EE (2026-08-08) | academictorrents 2,851 items with 0 in-window web crawls, `collection:webarchivedatasets` exactly 8 items, LAW/UNIMI 2 in-window graphs (`cnr-2000` is 325,557 URLs to one domain), CAIDA no hostname inventory, RIPE Hostcount aggregates only. | 2,851 items | n/a | n/a [detail](#research-crawl-datasets-remaining-angles) |
| Non-English regional portals | 2026-08-08 | 2001 | n/a | n/a | n/a | 445 EE (2026-08-08) | Deferred: 10 archived catalogue pages give 445 EE measured after the split, about 27 EE per request, but 97.4% comes from one Indian portal (Khoj), Seznam's 1,723 domains gave 0, the Brazilian pages gave 0, and everything lands in 2001. | n/a | Deferred | n/a |
| Stanford WebBase 2001 (via LAW) | n/a | 2001 | n/a | n/a | 99.99% already held | n/a | 118M URLs to 603,245 registered domains, 99.99% already held. Retired as a growth source. | n/a | n/a | n/a |
| `deduplicated_urls_` (supplied seeds) | n/a | n/a | n/a | n/a | n/a | n/a | Exhausted: 200k lines probed yielded 3 domains not in the baseline. | n/a | n/a | n/a |
| Common Crawl | n/a | n/a | n/a | n/a | n/a | n/a | Earliest collection is 2008-05; capture timestamps fail the in-window evidence bar. | n/a | n/a | n/a |
| Arquivo.pt bulk `AWP` collections | n/a | n/a | cdx query | n/a | n/a | n/a | 214 files, sampled slices all 2008, out of window (`Roteiro` and `IA.cdxj` are the in-window exceptions). | 214 files | n/a | n/a |
| UKWA per-year bulk CDX | n/a | 1999 | cdx query | n/a | n/a | n/a | Not publicly retrievable in 2026: dead host, soft-404 successor, 404 DOI, never Wayback-captured. Probe the data paths, not the repository front page:, with `linkage/host-linkage.tsv.gz` as the positive control, a file we hold 2 GiB of that | n/a | n/a | <https://www.webarchive.org.uk/datasets/ukwa.ds.2/cdx/1999.cdx.gz> [detail](#ukwa-per-year-bulk-cdx) |
| ODP full Aug-2000 content dump | n/a | n/a | n/a | n/a | n/a | n/a | Unrecoverable; only `structure.rdf` was archived, which has no external links. | n/a | n/a | n/a |
| Public 1996-2001 zone files | n/a | 1996-2001 | n/a | n/a | n/a | n/a | Some do survive: an intact April 1997 InterNIC `.org` zone was found at `nic.mil` on 2026-08-18. | n/a | n/a | n/a |
| Other ccTLD registry open data | n/a | 1996-2001 | port 43 whois | n/a | n/a | n/a | Nothing free reaches 1996-2001. CENTR aggregates only, OpenINTEL starts 2015, commercial WHOIS is paid. Re-checked for a per-domain file carrying both a creation and a withdrawal date: Nominet, auDA, InternetNZ, CIRA, SGNIC, IEDR, SWITCH | n/a | n/a | n/a [detail](#other-cctld-registry-open-data) |
| SNAP web graphs | n/a | n/a | n/a | n/a | n/a | n/a | Nodes are anonymised integers with no URL mapping. | n/a | n/a | n/a |
| Yahoo! Webscope AltaVista graph | n/a | n/a | n/a | n/a | n/a | n/a | Permanent: `webscope.sandbox.yahoo.com` has no DNS record. Does not want re-probing. | n/a | n/a | n/a |
| Yahoo! Directory | n/a | n/a | n/a | n/a | n/a | n/a | No machine-readable dump was ever published. Not a re-probe candidate: the artefact never existed. | n/a | n/a | n/a |
| GeoCities derivatives, DNS Census | n/a | n/a | n/a | n/a | n/a | n/a | 2009 and 2013 respectively, out of window. | n/a | n/a | n/a |
| Post-July-1997 ISC `.domains` lists | n/a | n/a | n/a | n/a | n/a | n/a | Do not exist; later editions publish aggregate counts only. Confirmed from two independent live directory listings, so an absence rather than an outage. | n/a | n/a | n/a |
| ISC January 1997 file | n/a | 1997 | n/a | n/a | n/a | n/a | Corrupt in every known copy. Permanent gap. | n/a | n/a | n/a |
| Internet Archive Alexa crawls (`alexacrawls`, `webwidecrawl`) | n/a | 1996 | cdx query | n/a | n/a | n/a | 226,901 items from 1996 with per-item CDX, but every payload returns HTTP 401; only `_meta.xml` is public. | 226,901 items | n/a | n/a |
| UKWA per-year bulk CDX (2026 recheck) | n/a | n/a | cdx query | n/a | n/a | n/a | Docs survive at `ukwa.github.io/opendata/ukwa.ds.2/cdx/`; the download host serves the same 159-byte stub and the DOI 403s behind Cloudflare. Wayback captured the directory listing but never the `.gz` files. In-window size would have been | 13.4 GB | n/a | n/a [detail](#ukwa-per-year-bulk-cdx-2026-recheck) |
| New Zealand (National Library) | n/a | n/a | cdx query | n/a | n/a | n/a | `webarchive.natlib.govt.nz` and `natlib.govt.nz` return an Imperva bot interstitial; NLNZ's archive.org CDX items are 2025-2026 crawls. Keep in rotation: harvesting began in window, `.nz` weighs 0.9895, and a bot interstitial can change. | n/a | n/a | n/a |
| Ireland (National Library) | n/a | n/a | n/a | n/a | n/a | n/a | Archives via Archive-It, 138 collections, earliest captures 2011. | n/a | n/a | n/a |
| `early-web_parallel-language-urls` | n/a | n/a | n/a | n/a | n/a | n/a | 1,164,183 pre-2000 multilingual URL patterns with no timestamps, so no per-year evidence. Seed-only at best. | n/a | n/a | n/a |
| OCLC Web Characterization Project | n/a | n/a | n/a | n/a | n/a | n/a | Only aggregate statistics were published; the host is gone. | n/a | n/a | n/a |
| Mailing-list archives | 2026-08-01 | 1997 | n/a | n/a | n/a | n/a | Population is wrong. archive.org's in-window holdings are hobbyist digests (`sf-lovers`, `GLOWBUGS`); the W3C public lists are small and technical, `www-announce` running for 3 archive periods, `www-talk` 121, `www-html` 246. A 1997 | 53 messages | n/a | n/a [detail](#mailing-list-archives) |
| archive.org books, three collections | 2026-08-05 | n/a | http download | n/a | n/a | n/a | `subject:(internet)`: 57 of 60 sampled in-window items publish no downloadable `_djvu.txt`, 2 net-new pairs. `collection:folkscanomy_computer`: 36 of 40 unreachable, 2 net-new pairs from 40 items. In-window book scans largely carry no OCR | 40 items | n/a | n/a [detail](#archive-org-books-three-collections) |
| archive.org `magazine_rack` at large | 2026-08-05 | n/a | n/a | n/a | n/a | n/a | 34,279 in-window items at 0.4 net-new pairs per reachable item, against 10.5 for the computing trade press measured the same way. In-window holdings are user-group zines and lab newsletters. | n/a | n/a | n/a |
| Boardwatch ISP Directory volumes | 2026-08-05 | n/a | n/a | n/a | n/a | n/a | The monthly issues carry `_djvu.txt`; the directory volumes do not. `boardwatch-directory-of-internet-service-providers-july-august-1997_djvu.txt` returns a 146-byte stub. | n/a | n/a | n/a |
| Internet Traffic Archive web traces | 2026-08-06 | 1996 | n/a | n/a | n/a | n/a | `ita.ee.lbl.gov` is alive and the ideal dataset is unusable: UC Berkeley Home IP 1996, 9,244,728 requests, has anonymised URLs, its own format example being `GET 9168504434183313441..gif`. `BU-Web-Client` has clear URLs and runs 1994-1995 | 9,244,728 requests | n/a | n/a [detail](#internet-traffic-archive-web-traces) |
| Shareware CD-ROM catalogues on archive.org | 2026-08-06 | n/a | http download | n/a | n/a | n/a | archive.org cannot list inside an ISO: `/download/<item>/<file>.ISO/` ends "failed to obtain file list", so measuring density costs a full ISO download per item, 127 MB to 1,300 MB. The 3,578 `cdbbsarchive` items also carry no `date` or | 127 MB | n/a | n/a [detail](#shareware-cd-rom-catalogues-on-archive-org) |
| DMOZ / ODP pre-2002 dumps on archive.org | 2026-08-06 | n/a | n/a | n/a | n/a | n/a | archive.org holds exactly one ODP RDF item, `dmoz-rdf-20150327`, 29.8 GB, 2015. No pre-2002 dump exists there. | 29.8 GB | n/a | n/a |
| InterNIC / NSI zone or WHOIS snapshots on archive.org | 2026-08-06 | n/a | port 43 whois | n/a | n/a | n/a | 8 hits for `internic AND (zone OR whois OR domain)` and none is data: two Tucows programs, an RFC, two videos, two GitHub mirrors. | n/a | n/a | n/a |
| Other released email corpora | 2026-08-06 | n/a | n/a | n/a | n/a | n/a | Enron is the only released corpus in window. | n/a | n/a | n/a |
| Bibliotheca Alexandrina IA mirror | 2026-08-05 | n/a | wayback replay | n/a | n/a | n/a | `web.archive.bibalex.org` and `web.archive.org.bibalex.org` both fail to resolve; only the institutional landing page answers. | n/a | n/a | n/a |
| URLs cited in US patents, 1996-2001 | 2026-08-15 | 1996-2001 | n/a | n/a | n/a | n/a | A projection, not a measurement: a cited reference is the definition of an authority-selected population, and even at 3% of the roughly 1.0M US patents granted 1996-2001 citing a URL the distinct-domain count is order 10^4. | n/a | n/a | n/a |
| NTP Survey 1999, Nelson Minar / MIT Media Lab | 2026-08-15 | 1999 | n/a | n/a | n/a | n/a | Live index, dead payloads. `alumni.media.mit.edu/~nelson/research/ntp-survey99/data/` is 4,337 bytes of period HTML listing `ntp-survey-1999.tar.bz2` and siblings; the census of 175,527 NTP hosts is orthogonal to a capture-derived baseline | 4,337 bytes | n/a | n/a [detail](#ntp-survey-1999-nelson-minar-mit-media-lab) |
| Dot-com deadpool and failure lists, 2000-2001 | 2026-08-15 | 2000-2001 | n/a | n/a | n/a | n/a | Short life is necessary and not sufficient: a funded dot-com ran a marketing budget and was captured repeatedly before it folded. The population is celebrated failures, which is authority selection, and the store holds every one. What pays | n/a | n/a | n/a [detail](#dot-com-deadpool-and-failure-lists-2000-2001) |
| Bruce Guenter's spam archive, `untroubled.org/spam/` | 2026-08-15 | 1998-2001 | n/a | n/a | n/a | 195.5 EE (2026-08-15) | 312 net-new pairs and 195.5 EE after the split, 16x below the bar. `1998.7z` through `2001.7z` total 9.3 MB and expand to 20,010 messages each carrying its own `Date` header, but 19,992 in-window messages name only 5,342 pairs over 4,793 | 9.3 MB, 20,010 messages | n/a | n/a [detail](#bruce-guenter-s-spam-archive-untroubled-org-spam) |
| Anti-spam blocklists and blackhole lists, 1997-2001 | 2026-08-15 | 1997-2001 | n/a | n/a | n/a | n/a | Every in-window blocklist is IP-based, not domain-based: MAPS RBL, ORBS, the Dial-Up List and SPEWS all publish addresses and netblocks, and the output unit is the registered domain. The domain-bearing variant, spam sightings in | n/a | n/a | n/a [detail](#anti-spam-blocklists-and-blackhole-lists-1997-2001) |
| `data.webarchive.org.uk` | 2026-08-05 | n/a | cdx query | n/a | n/a | n/a | Does not resolve. A third distinct host tried for the UKWA bulk CDX. | n/a | n/a | n/a |
| The whole `webarchive.org.uk/datasets/` tree | 2026-08-15 | n/a | n/a | n/a | n/a | n/a | The stub is the tree, not the file: `/datasets/ukwa.ds.2/geo/` returns the same 159-byte "400 Redirect" body under HTTP 200 as `linkage/host-linkage.tsv.gz`, a file we hold. The Geoindex behind it is 700,641,549 lines covering 1996-2010 | 8 GB | n/a | n/a [detail](#the-whole-webarchive-org-uk-datasets-tree) |
| Alexa / IA donated crawl items on archive.org, their CDX indexes | 2026-08-15 | 1999 | cdx query | n/a | n/a | n/a | The bulk index exists and is access-controlled: in-window items carry per-item CDX (`FS-587676-c.cdx.gz` at 104 MB, a 1999 item at 631 MB) and a ranged GET returns HTTP 401 with a 172-byte body, so the restriction covers the index and not | 104 MB | n/a | n/a [detail](#alexa-ia-donated-crawl-items-on-archive-org-their-cdx-indexes) |
| National-library historical web extractions on archive.org: INA `.fr`, FCCN `.pt`, NLI `.ie` | 2026-08-18 | n/a | http api | n/a | n/a | n/a | Enumerated by scraping all 34,841 identifiers containing `HISTORICAL`: `INA-HISTORICAL-` 49 items, `FCCN-PT-HISTORICAL-` and `PT-HISTORICAL-` 31, `NLI-IE-` 46. Ireland is the only high-weight one and its earliest item date is 2002. The | 49 items | n/a | n/a [detail](#national-library-historical-web-extractions-on-archive-org-ina-fr-fccn) |
| UKWA Geoindex, E17 postcode slice, figshare 825956 | 2026-08-15 | n/a | cdx query | n/a | n/a | 120.7 EE (2026-08-15) | Reachable and too small: 1,886,146 bytes, 12,081 rows of `postcode,year,subdomain,waybackurl`, the 14-digit timestamp inside each wayback URL being self-dating `cdx_timestamp`. 296 net-new pairs raw, 123 pairs and 120.7 EE after the split. | 1,886,146 bytes | n/a | n/a |
| Other JISC UK Web Domain Dataset derived files | 2026-08-15 | n/a | n/a | n/a | n/a | n/a | Hostless by construction: `fmts-cleaned.tsv` is MIME-type counts, `link-summary-.tsv` is suffix-to-suffix counts, `ds.1/classification.tsv` is URL plus category with no year. | n/a | n/a | n/a |
| Archives Unleashed derived datasets | 2026-08-15 | n/a | n/a | n/a | n/a | n/a | Structurally out of window: derivatives are built from Archive-It collections, which begin in 2005. | n/a | n/a | n/a |
| DMOZ / ODP copies on Zenodo | 2026-08-05 | n/a | n/a | n/a | n/a | n/a | 12 hits, all 2018-2020 research derivatives of late DMOZ dumps. | n/a | n/a | n/a |
| `biz.` Usenet hierarchy | 2026-08-05 | n/a | n/a | n/a | n/a | n/a | Exhausted: no unprocessed `.mbox.zip` archives remain in the 19,233-group catalogue. | n/a | n/a | n/a |
| OpenPGP keyserver bulk dumps, SKS and Hockeypuck | 2026-08-18 | n/a | n/a | n/a | n/a | n/a | Nine dump hosts are dead, NXDOMAIN or 404; `pgp.key-server.io/sks-dump/` serves a squatted 1,095-byte redirect stub under HTTP 200; `keys.openpgp.org` publishes no dump by design; archive.org and Zenodo hold none against a working positive | n/a | n/a | n/a [detail](#openpgp-keyserver-bulk-dumps-sks-and-hockeypuck) |
| Curated distribution keyrings: Debian removed-keys and emeritus, GNU, Apache KEYS | 2026-08-18 | n/a | n/a | n/a | n/a | 44.4 EE (2026-08-18) | Retrievable, correctly dated and 70x too small. Priced on the UID binding signature over 4,096 items: 1,418 pairs, 1,273 already held (89.8%), 69 net-new pairs, 44.4 EE. `debian.org` alone is 1,033 of the in-window user IDs, and a current | 4,096 items | Priced | n/a [detail](#curated-distribution-keyrings-debian-removed-keys-and-emeritus-gnu-apa) |
| X.509 certificate corpora with `notBefore` in 1996-2001 | 2026-08-18 | 1996-2001 | n/a | n/a | n/a | 0.6 EE (2026-08-18) | `notBefore` is CA-written into a signed structure and genuinely self-dating; the population fails. The only retrievable in-window corpus is `hg.mozilla.org`'s 139 revisions of `certdata.txt`, and a census of its 126 in-window certs gives 1 | n/a | n/a | n/a [detail](#x-509-certificate-corpora-with-notbefore-in-1996-2001) |
| Machine-written mail headers in bulk mailing-list archives | 2026-08-18 | n/a | n/a | n/a | n/a | 107.3 EE (2026-08-18) | `pipermail` strips the `Received` chain entirely: over 37,789 messages from 2,622 of our own month files only `From`, `Date`, `Subject`, `Message-ID`, `References` and `In-Reply-To` survive, and the `Message-ID` host seam is worth 156 | 37,789 messages | worth | n/a [detail](#machine-written-mail-headers-in-bulk-mailing-list-archives) |
| Web archives holding their own pre-2002 crawls | 2026-08-18 | 2001 | n/a | n/a | n/a | n/a | Counted rather than hoped: Wikipedia's list of initiatives (109 rows), MemGator's `archives.json` (20 endpoints) and the IIPC directory (48 permalinks). The Memento TimeTravel aggregator no longer exists, `timetravel.mementoweb.org` | n/a | n/a | n/a [detail](#web-archives-holding-their-own-pre-2002-crawls) |
| Kulturarw3, National Library of Sweden | 2026-08-18 | n/a | n/a | n/a | n/a | n/a | The largest IA-free in-window corpus known, and the door is shut: access is on-site only and "You cannot search freely for a word or subject, but must enter, for example, `www.sf.se`", so the interface cannot emit an unknown hostname. | n/a | n/a | n/a [detail](#kulturarw3-national-library-of-sweden) |
| Quoted `whois` records pasted into Usenet bodies | 2026-08-18 | n/a | port 43 whois | n/a | 68.2% already held | 95.0 EE (2026-08-18) | 50x under the bar. Self-dating on the registry's own `Record created on 18-Feb-1998.` line, so the paste date is irrelevant to the year claimed. Priced from disk at zero network cost over 28.20 GB: 488 pairs, 68.2% already held, 155 net-new | 28.20 GB | Priced | n/a [detail](#quoted-whois-records-pasted-into-usenet-bodies) |
| The ISI RFC 1480 US Domain Registry | 2026-08-18 | 2000-2001 | n/a | n/a | 97.7% already known | 0.9 EE (2026-08-18) | Four dated in-window editions recovered, and the registry added four names between August 2000 and November 2001, so the legitimate first-appearance diff prices at 1 net-new pair and 0.9 EE, while dating every name in each edition would | n/a | n/a | n/a [detail](#the-isi-rfc-1480-us-domain-registry) |
| Another precomputed IA capture census in a research repository | 2026-08-18 | n/a | n/a | n/a | n/a | 0.63 EE (2026-08-18) | The whole in-window population is four items, three already in this register and one new: Weber's DRUM deposit `10.13020/D62684`, 74.83 GB in 16 tar parts, measuring 45,130 of 45,130 sampled pairs already held and 1 net-new pair worth 0.63 | 74.83 GB | worth | n/a [detail](#another-precomputed-ia-capture-census-in-a-research-repository) |
| Discmaster, the index over archived media contents | 2026-08-18 | n/a | robots refusal | n/a | 95.6% overlap | 78.9 EE (2026-08-18) | Works, and the media population is already ours: the deduplicated `.url` population is 125 net-new pairs and 78.9 EE at 95.6% overlap. Bulk endpoint `search?download=true` returns every match as one tar.gz up to 1 GiB; `robots.txt` says | n/a | n/a | n/a [detail](#discmaster-the-index-over-archived-media-contents) |
| Government grant and award records 1996-2001 | 2026-08-18 | 1996-2001 | n/a | n/a | n/a | n/a | Clears the item screen 3.8x over at 456,700 dated in-window items and still dies, because 0.042 pairs per item is a property of subject matter: NSF CSE 0.0471, BIO 0.0152, GEO and TIP 0.0000, NIH 0.0012 at 164 distinct hostnames in 372,444 | n/a | n/a | n/a [detail](#government-grant-and-award-records-1996-2001) |
| Dated newswire and press-release full text | 2026-08-18 | n/a | n/a | n/a | n/a | n/a | Do not sign the NIST agreement. An ungated corpus larger than Reuters RCV1 exists, `usenet-clari.` at 22 items and 21,309,542,972 bytes with Business Wire and PR Newswire full text, and it fails on era: across four group files parsed in | 21,309,542,972 bytes, 22 items | n/a | n/a [detail](#dated-newswire-and-press-release-full-text) |
| Machine-written network diagnostics pasted into Usenet bodies | 2026-08-18 | n/a | n/a | n/a | n/a | 165.7 EE (2026-08-18) | 29,040 of 219,447,104 in-window messages carry a diagnostic structure, one in 7,557, capping the lens at 1,220 pairs against a 5,000 bar. Measured 297 net-new post-split pairs and 165.7 EE, reduced by a hand audit to roughly 150 pairs and | n/a | n/a | n/a [detail](#machine-written-network-diagnostics-pasted-into-usenet-bodies) |
| Dated announcements of new domain registrations | 2026-08-18 | n/a | n/a | n/a | n/a | n/a | Right about dating, wrong about volume: a registry of this era published either dates without names (statistics, as at `domainz.net.nz/newsstand/stats/` and every InterNIC and NSI registration report) or names without dates (a zone | n/a | n/a | n/a [detail](#dated-announcements-of-new-domain-registrations) |
| Discmaster by file size, and the April 1998 `.jp` registry listing | 2026-08-18 | 1998 | discmaster index | n/a | 87.5% already held | n/a | The route works and the snapshot is 87.5% already held. `email.domains`, 2,085,500 bytes and 42,701 lines, at `/japan/email.domains` on the `ftp.cs.arizona.edu` mirror, item 19864, self-dating from its own header "Registered Domains in JP | 2,085,500 bytes | n/a | n/a [detail](#discmaster-by-file-size-and-the-april-1998-jp-registry-listing) |
| Afilias Land Rush 2 schedule | 2026-08-25 | n/a | n/a | n/a | n/a | n/a | 0.00 post-split, because exactly 1 of the 4,257 names is dated anywhere in the store. `landrush2.afilias.info` resolves at 66.199.183.26 and refuses TCP 80; the surviving fragment, `onlinedomain.com`'s | 82,107 bytes | n/a | n/a [detail](#afilias-land-rush-2-schedule) |
| The ICANN forum `.info` Sunrise lists | 2026-08-25 | n/a | n/a | n/a | n/a | 1,328.60 EE (2026-08-25) | A decision for a human at 1,328.60 EE post-split. `forum.icann.org/newtldagmts/` is 7,169 message pages frozen since March 2002; largest item `3C8A91B500002319.html` carries `Date/Time: Sat, March 9, 2002 at 10:50 PM GMT` and "Listed below | n/a | n/a | n/a [detail](#the-icann-forum-info-sunrise-lists) |
| A 2001 squidGuard blacklist | 2026-08-25 | 2001 | n/a | n/a | n/a | 10,736.2 EE (2026-08-25) | 10,736.2 EE, licence GNU GPL v2 verbatim in `COPYING`, and it triggers this register's own reopen condition. One request to `archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`, 1,852,659 bytes, yields | 1,852,659 bytes | reopen | n/a [detail](#a-2001-squidguard-blacklist) |
| The `.us` locality gap | 2026-08-25 | 1997-2001 | n/a | n/a | n/a | 3,500 EE (2026-08-25) | 61% dead names: of 9,680 `.us` domains held in window and missing 2001, 6,948 were last seen in July 1997 and only 1,473 reach 2000, so the addressable share is nearer 3,500 EE than 8,964.65. Against a control, only 37.65% of the 12,080 | n/a | n/a | n/a [detail](#the-us-locality-gap) |
| Southern and Central Europe FTP hosts | 2026-08-25 | n/a | ftp listing | n/a | n/a | n/a | The host layer is dead, not refusing: of 50 hosts screened, 26 are NXDOMAIN (`ftp.nic.at`, `ftp.nic.fr`, `ftp.cnr.it`, `ftp.switch.ch`, `ftp.huji.ac.il` among them) and nine resolve but refuse ports 21, 80 and 443, against a control where | n/a | n/a | n/a [detail](#southern-and-central-europe-ftp-hosts) |
| The 2001-2003 frozen-mirror sweep | 2026-08-25 | 2001 | port 43 whois | n/a | n/a | 741.61 EE (2026-08-25) | Both screened artifacts were already answered: the Edelman whois transcriptions re-found by a second route price at 741.61 EE against the 2,968.49 EE already banked from a fuller parse, its independent 2001 slice giving 1,003 | n/a | banked | n/a [detail](#the-2001-2003-frozen-mirror-sweep) |
| Raw AXFR output published openly | 2026-08-25 | n/a | ftp listing | n/a | n/a | 99.7 EE (2026-08-25) | Surviving editions are 1995 only, corrected 2026-08-30: a 1999-01-07 edition also survives (`ftp.apnic.net/apnic/arin/arin.zones.tar.gz`, above), and it paid 99.7 EE because a reverse tree names the operators we already hold. | 2,332,217 bytes | n/a | n/a [detail](#raw-axfr-output-published-openly) |
| Forged-header corpora, the Lazarus remailer logs | 2026-08-25 | 2001 | n/a | n/a | n/a | 115.83 EE (2026-08-25) | 115.83 EE, because only 1,053 of its 23,102 canonical names are held. The dating is the cleanest seen here: a complete 12-month 2001 series, 57,368,107 bytes over 13 files, each file's mtime landing on the last day of the month its filename | 57,368,107 bytes, 13 files | n/a | n/a [detail](#forged-header-corpora-the-lazarus-remailer-logs) |
| The 2001 threshold qualified | 2026-08-25 | 2001 | n/a | n/a | n/a | 95.67 EE (2026-08-25) | It is a population average, not a universal rate: `WinNetMagCD.chm`, 146,221,869 bytes dated `2001-12-05 18:11:43` in the ISO9660 directory record, yields 2,334 canonical names of which 2,296 are held and only 157 are held-missing-2001 | 146,221,869 bytes | n/a | n/a [detail](#the-2001-threshold-qualified) |
| The 2001 hunt: five routes closed and one prize sized | 2026-08-25 | 2001 | n/a | n/a | n/a | 273,600 EE (2026-08-25) | A full 2001 `.info` register would be worth about 273,600 EE, since the store holds 21,609 `.info` at 2001 against about 750,000 that existed by year end, and it does not survive: ICANN's Registry Operator's Reports are aggregate counts | n/a | worth | n/a [detail](#the-2001-hunt-five-routes-closed-and-one-prize-sized) |
| DNS-walk output across the RIPE region | 2026-08-25 | 1999-2001 | ftp listing | n/a | n/a | n/a | Structurally dead by RIPE's own dated decision, verbatim from `ftp.uni-erlangen.de/pub/ripe.net/ripe/hostcount/README`, mtime 3 July 2001: `01/02/1999 Access to the host output files was restricted` and `03/07/2001 Access to the error files | n/a | n/a | n/a [detail](#dns-walk-output-across-the-ripe-region) |
| The 2001 threshold | 2026-08-25 | 2001 | n/a | n/a | n/a | 1,000 EE (2026-08-25) | P(store lacks 2001 given domain held): `com` 0.611 (4,264,044 of 6,980,240), `net` 0.653, `org` 0.568, `uk` 0.309, `de` 0.841, `au` 0.406, `ca` 0.478, `nz` 0.545. EE per already-held name in a 2001-dated artifact: `com` 0.386, `org` 0.404 | n/a | n/a | n/a [detail](#the-2001-threshold) |
| The long-running-series lens | 2026-08-25 | 1996-2001 | n/a | n/a | 97.6% already held | 4.44 EE (2026-08-25) | An IRR/RADB dump is 97.6% already held and paid 4.44 EE, because 95.2% of its names were already held in that very year: 13,674 in-window `changed:` lines collapse to 532 pairs of which 25 are net-new. The screen is held and missing this | n/a | n/a | n/a [detail](#the-long-running-series-lens) |
| `ftp.nluug.nl` refuses four Claude agent names | 2026-08-25 | n/a | robots refusal | n/a | n/a | n/a | `ftp.nluug.nl/robots.txt` lists `ClaudeBot`, `Claude-User`, `Claude-Web` and `Claude-SearchBot`, each with `Disallow: /`. Also refused and not pursued: `ftp.fu-berlin.de`, `ftp.uni-stuttgart.de`, `ftp.tu-chemnitz.de`. `ftp.radb.net` serves | n/a | n/a | n/a [detail](#ftp-nluug-nl-refuses-four-claude-agent-names) |
| `.nz` port 43 | 2026-08-25 | n/a | n/a | n/a | n/a | 7,586 EE (2026-08-25) | 7,586 EE measured and refused by the registry's own terms, which sit about 1,100 bytes into the same response, after the record. 200 domains from 47,914 held `.nz` names, 123 dated, 122 in-window against 1 out, 0.1600 net-new per held | 1,100 bytes | n/a | n/a [detail](#nz-port-43) |
| The nw.com survey series | 2026-08-25 | 1996-1997 | n/a | n/a | n/a | 14,956.4 EE (2026-08-25) | Complete and fully held: a December 1998 capture of the `nw.com/zone/` listing shows exactly 9507, 9601, 9607, 9701 and 9707, so the survey was semi-annual and there is no 9604, 9610 or 9704 to find. `hosts-per-net` is counts without names. | n/a | find | n/a [detail](#the-nw-com-survey-series) |
| Promotion tranche and holdings audit | 2026-08-25 | n/a | n/a | n/a | n/a | 1,805 EE (2026-08-25) | 1,805 EE banked with no decision, of which the promotion tranche is 2,476 pairs and 1,556.6 EE: `usenet_mention` 808.5, `usenet_address_mention` 664.7, `usenet_bare_mention` 360.0, `rtfm_faq_mention` 41.2, `trade_press_mention` 12.6 | n/a | banked | n/a [detail](#promotion-tranche-and-holdings-audit) |
| The `can.domain` classification ruling | 2026-08-25 | n/a | n/a | n/a | n/a | 9,551.2 EE (2026-08-25) | Not a source, a ruling: the CA Domain Registry's notices measure 11,418 pairs and 9,551.2 EE if the registry self-dates against 936 pairs and 783.0 EE if a human typed it, a 12.2x gap turning on whether a `Date-Approved:` field printed by | n/a | not a source | n/a [detail](#the-can-domain-classification-ruling) |
| ERIC | 2026-08-25 | n/a | n/a | n/a | 93.0% of pairs already held | n/a | Grey literature passes the density screen at 221x formal prose, 1,697 URL occurrences in 5,003,152 words or 0.339 per 1,000 against Hansard's 0.00153, and fails the authority screen at 93.0% of pairs already held. The union holds 184 `.edu` | n/a | n/a | n/a [detail](#eric) |
| Grey literature as a live lens | 2026-08-25 | n/a | n/a | n/a | 89.3% already held | n/a | First ERIC sample: 190,789 in-window records of which 40.4% are `ED`-type with full text, 54 PDFs giving 3.55M characters and 75 canonical pairs at 89.3% already held, 4 post-split. | n/a | n/a | n/a |
| Blocklists bundled in dated anti-spam software on period media | 2026-08-25 | 1996-2001 | discmaster index | n/a | n/a | 1,689.5 EE (2026-08-25) | A new source class. Consumer products shipped their blocklist as a plain data file and hundreds of 1996-2001 CD-ROMs preserve those files with per-file mtimes on the media, so discmaster's `tsMin`/`tsMax` filter makes the era screen a | 320,099 bytes | n/a | n/a [detail](#blocklists-bundled-in-dated-anti-spam-software-on-period-media) |
| The adversarial law refined | 2026-08-25 | 2000 | n/a | n/a | 50.4% held | 18.2 EE (2026-08-25) | It pays only if the adversary did not crawl. A period-CD squidGuard list headed `# This list was compiled in 39:33:10 on 2000.10.18 14:13:23.` is worth 18.2 EE with 38,876 of 39,082 domains, 99.47%, already held, and the same header says | n/a | worth | n/a [detail](#the-adversarial-law-refined) |
| `cryptome.org`, `tbtf.com`, `www.openpgp.net` refuse ClaudeBot by name | 2026-08-25 | n/a | robots refusal | n/a | n/a | n/a | `cryptome.org` 403s robots.txt itself and 403s on the ClaudeBot token specifically: same URL, same minutes, curl default UA 200 and 114,247 bytes, honest project UA 200 and 114,247, `ClaudeBot/1.0` 403 and 159 bytes. Not evaded by changing | 114,247 bytes | n/a | n/a [detail](#cryptome-org-tbtf-com-www-openpgp-net-refuse-claudebot-by-name) |
| Abandoned `.part` journals, local half | 2026-08-25 | n/a | cdx query | n/a | n/a | 919 EE (2026-08-25) | 919 EE banked. A collector killed by a deadline, a signal or a crash never renames its journal, so its work sits where no glob matches: the paused local collector's `cdx_pool_20260824T142945Z.jsonl.gz.part` held 579 queried, 575 answered | n/a | banked | n/a [detail](#abandoned-part-journals-local-half) |
| A 2003 whois transcription on an abandoned academic page | 2026-08-25 | n/a | port 43 whois | n/a | n/a | 2,968.49 EE (2026-08-25) | 2,968.49 EE over 4,747 net-new pairs, no licence at all. Ben Edelman's three listings on Harvard Berkman Center space, 81 pages, 13,507,154 bytes, 15,990 entries, 8,787 dated. Each record carries its own `Dates of creation / last | 13,507,154 bytes, 81 pages | n/a | n/a [detail](#a-2003-whois-transcription-on-an-abandoned-academic-page) |
| The reciprocal-traffic industry | 2026-08-25 | n/a | wayback replay | n/a | 98.39% already held | n/a | The blocklist inversion does not generalise: the two traffic-derived artifacts reachable off Wayback measure 99.55% and 98.39% already held, worse than the 87-99% curated band, because a visitor log's hostname field is reverse DNS and the | n/a | n/a | n/a [detail](#the-reciprocal-traffic-industry) |
| Blocklists as a lens | 2026-08-25 | 1997 | discmaster index | n/a | n/a | 2,189.4 EE (2026-08-25) | Already-held on a blocklist is about 50% (junkfilter 50.4%, SurfWatch 49.7%) against 87.5% to 99.8% on every authority-selected corpus, because a blocklist selects for what somebody wanted to block. `junkfilter_dated_blocklist` found and in | 900 KB | n/a | n/a [detail](#blocklists-as-a-lens) |
| 1999 InterNIC zones on the JPNIC mirror | 2026-08-25 | 1999 | n/a | n/a | n/a | 179.8 EE (2026-08-25) | 179.8 EE, banked, needing no decision. `tomocha.net/files/dns/` holds `gov.zone`, `edu.zone` and `root.zone`, all filed 2002-02-26, and the file date is not the artifact's date: `gov.zone` carries SOA serial `1999111901` and the other two | n/a | banked | n/a [detail](#1999-internic-zones-on-the-jpnic-mirror) |
| Stranded RDAP journals on the VPS | 2026-08-25 | n/a | cdx query | n/a | n/a | 3,599.2 EE (2026-08-25) | 3,599.2 EE banked over 5,877 net-new pairs, the oldest sitting since 22 August, because `maintain.sh` rsyncs `rdap_.jsonl.gz` and `cdx_.jsonl.gz` and never `.jsonl.gz.part`. Five abandoned partials, 62 MB, 502,293 readable records, 110,499 | 62 MB | banked | n/a [detail](#stranded-rdap-journals-on-the-vps) |
| The frozen-mirror rule applied a second time | 2026-08-24 | 1999 | robots refusal | n/a | n/a | 1,623.0 EE (2026-08-24) | The surviving registers are on personal pages, not institutional ones. Found and admitted: JPNIC's own `.jp` register at 30 April 1999,, 6,185,475 bytes, `Last-Modified: Fri, 30 Apr 1999 04:43:08 GMT`, repriced from the bytes at 72,704 | 6,185,475 bytes | admitted | <https://tomocha.net/files/dns/domain-list.txt> [detail](#the-frozen-mirror-rule-applied-a-second-time) |
| Integrity audit over every held gzip | 2026-08-24 | 2000 | cdx query | n/a | n/a | n/a | `gzip -t` over all 6,168 `.gz` files in `data/raw` outside the Usenet trees, 10.8 GB: 39 fail and every one is accounted for. 21 under `probes/` are deliberate prefix samples at exactly 65536 and 50000 bytes; of the real 18 | 10.8 GB | n/a | n/a [detail](#integrity-audit-over-every-held-gzip) |
| The 1999 RIPE database on a document mirror | 2026-08-24 | 1999 | ftp listing | n/a | n/a | 90,799 EE (2026-08-24) | 90,799 EE, not banked because of its own copyright header. FUNET mirrored RIPE's whole document tree into `/pub/netinfo/` and stopped updating, so the mirror froze holding the pre-GDPR original:, 71,919,736 bytes, `Last-Modified: Tue, 03 | 71,919,736 bytes | banked | <http://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz> [detail](#the-1999-ripe-database-on-a-document-mirror) |
| `data/raw/usenet_new/`, 50 GB unseen | 2026-08-24 | n/a | bytes already on disk | n/a | n/a | 35.8 EE (2026-08-24) | `ingest_new_usenet.sh` reads `DIR="data/raw/usenet"`, so 7,531 archives and 50 GB in `data/raw/usenet_new/` were never looked at. Measured over 4,052 MB and five hierarchies: 57,913 dated pairs, 57,847 already held, 99.89% saturation, 66 | 50 GB | n/a | n/a [detail](#data-raw-usenet-new-50-gb-unseen) |
| Zone files off the Internet Archive | 2026-08-24 | n/a | n/a | n/a | n/a | n/a | Nobody archived scratch. Three organisations transferred exactly the data wanted and all three published only the aggregate or the current state. The six InterNIC zones survive because they sat in a document mirror alongside RFCs, so the | n/a | n/a | n/a [detail](#zone-files-off-the-internet-archive) |
| `ftp.isc.org` disallows everything | 2026-08-24 | n/a | robots refusal | n/a | n/a | n/a | `ftp.isc.org/robots.txt` returns `Disallow: /` for all agents. The ISC survey finding it produced stands and the held `isc_survey` data came from other routes, but no further request may go there. Read robots.txt before the first request | n/a | n/a | n/a [detail](#ftp-isc-org-disallows-everything) |
| Mailing-list subscriber populations, refuted | 2026-08-24 | n/a | n/a | n/a | n/a | 0.00106 EE (2026-08-24) | A participant population does not give one domain per participant, it gives one per employer or ISP: 15,968 IETF senders collapse to 1,713 domains (9.3:1), 16,051 r-help senders to 1,053 (15.2:1), 6,118 FreeBSD senders to 1,627. Measured | n/a | n/a | n/a [detail](#mailing-list-subscriber-populations-refuted) |
| `data/raw/cdx_suffix/` | 2026-08-24 | n/a | cdx query | n/a | n/a | n/a | Worth exactly 0. The suffix sweep writes two journals per batch and only the per-domain form at `data/raw/cdx/cdx_suffix_.jsonl.gz` is needed; the raw capture form here, 58 journals and 389,393,904 bytes over 46,779,589 lines, is the same | 389,393,904 bytes, 58 journals | Worth | n/a [detail](#data-raw-cdx-suffix) |
| National web-archive indexes, three new doors | 2026-08-24 | 2000 | robots refusal | n/a | n/a | 1,000 EE (2026-08-24) | All three price below 1,000 EE, because a national archive's in-window holding is either an IA back-file donation we hold or a curated slice of institutions the baseline holds first. Library of Congress US Elections Web Archive | 1,971,201,167 bytes | n/a | n/a [detail](#national-web-archive-indexes-three-new-doors) |
| `arquivo.pt/robots.txt` breached | 2026-08-24 | n/a | robots refusal | n/a | n/a | n/a | Line 752 carries `Disallow: /datasets` inside the `User-agent: ` block with `Crawl-delay: 5`, and only two agent blocks exist. Ten ranged GETs against `/datasets/linkgraphs/` breached it, and the same path disallows the original collection | n/a | n/a | n/a [detail](#arquivo-pt-robots-txt-breached) |
| The UKWA host link graph truncation | 2026-08-24 | n/a | wayback replay | n/a | n/a | n/a | Truncated by the archive, not by our download, and not resumable from this host. The local copy is exactly 2,147,483,648 bytes, `gzip -t` fails with "unexpected end of file", and the Wayback `id_` capture reports `content-range: bytes | 2,147,483,648 bytes | n/a | n/a [detail](#the-ukwa-host-link-graph-truncation) |
| InterNIC zone files at the `nic.mil` mirror, admitted | 2026-08-24 | 1997-1999 | n/a | n/a | n/a | 8,993.1 EE (2026-08-24) | Master, on the artifact alone: the SOA serial `1997041800` sits on line 2 inside the payload and the IA capture of 1997-04-20 fixes when the file existed. An NS record in `.org` is the delegation itself, the registry serving that name at | n/a | n/a | n/a [detail](#internic-zone-files-at-the-nic-mil-mirror-admitted) |
| More InterNIC zone files, and `ftp.internic.net/domain/` | 2026-08-18 | n/a | cdx query | n/a | n/a | n/a | The population is six and we hold all six, so `internic_zone` cannot be widened. One CDX listing of `nic.mil/oroot.html/` returns the complete contents: `arpa` 694 bytes, `mil` 3,265, `root` 10,219, `gov` 16,251, `edu` 110,995, `org` | 694 bytes | n/a | n/a [detail](#more-internic-zone-files-and-ftp-internic-net-domain) |
| The `.au` registry family: AUNIC, auDA, AARNet | 2026-08-18 | n/a | cdx query | n/a | n/a | n/a | Does not survive in bulk. AUNIC's archived footprint is 1,605 captures whose only domain-bearing shape is `aunicstatus.pl?domain-name=<name>`, extractable free from the CDX index: 104 such captures yield 17 distinct `.au` names. A capture | 1,605 captures | n/a | n/a [detail](#the-au-registry-family-aunic-auda-aarnet) |
| CDX public-suffix sweep as a bulk channel | 2026-08-22 | n/a | cdx query | n/a | n/a | 4,800 EE (2026-08-22) | Demoted from channel to trickle. Twelve swept suffixes, 159 MB of journal, reduce to 68,386 in-window registrable pairs of which 5,722 are net-new, worth 4,800 EE, and every net-new pair is `.ca` or `.us`: `co.uk` and `ac.uk` are saturated. | 159 MB | worth | n/a [detail](#cdx-public-suffix-sweep-as-a-bulk-channel) |
| Common Crawl domain vertices as RDAP candidate supply | 2026-08-22 | n/a | rdap query | n/a | n/a | n/a | Admitted as a thin but genuine channel: not a dating source but a bulk supply of names to ask the registry about, our own RDAP engine supplying the date. `cc-main-2020-jul-aug-sep-domain-vertices.txt.gz` is HTTP 200 at 655,075,092 bytes and | 655,075,092 bytes | Admitted | n/a [detail](#common-crawl-domain-vertices-as-rdap-candidate-supply) |
| Common Crawl 2018 minus 2020 | 2026-08-22 | n/a | n/a | n/a | n/a | 4.7 EE (2026-08-22) | A real but small enrichment. The 2018 vertex file is HTTP 200 at 523,819,137 bytes holding 35,882,170 registrable `.com`/`.net`, of which 11,019,564 are absent from the 2020 file. A 19,918-query pilot gives 1.11% of queries returning an | 523,819,137 bytes | n/a | n/a [detail](#common-crawl-2018-minus-2020) |
| A registration SPAN from an RDAP creation date | 2026-08-23 | n/a | rdap query | n/a | n/a | 1,704,843 EE (2026-08-23) | Forbidden by rule 6 after being measured, and it is the largest thing this project has priced: applied to the 3,174,957 banked in-window creations the span would claim 11,038,108 pairs, of which 2,885,782 are net-new, worth 1,704,843 EE. | n/a | priced | n/a [detail](#a-registration-span-from-an-rdap-creation-date) |
| `link_target` as a ranking signal for the archive queue | 2026-08-23 | n/a | cdx query | n/a | n/a | 297 EE (2026-08-23) | Admitted, needing no new approval, at 297 EE per 1,000 queries: it changes who we ask rather than what counts as evidence, since the resulting capture is `cdx_timestamp`. `link_target` stays candidate-only, 4,115,694 rows. Against the | 1,000 queries | Admitted | n/a [detail](#link-target-as-a-ranking-signal-for-the-archive-queue) |
| RIPE database bulk dumps | 2026-08-23 | n/a | n/a | n/a | n/a | n/a | GDPR dummification closes it, and the reason generalises to every RIR. On the full `ripe.db.mntner.gz` file, 64,310 objects, exactly one distinct email domain survives, `ripe.net`, appearing 120,470 times, every object carrying a "all data | n/a | n/a | n/a [detail](#ripe-database-bulk-dumps) |
| The darkened Dartmouth/NBER metadata item | 2026-08-23 | n/a | archive.org metadata api | n/a | n/a | n/a | It reopened and is worth zero. `archive.org/metadata/DARTMOUTH-NBER-RESEARCH-2017-metadata` now returns a 13-file listing with no restriction, and `domain-year-captures.txt` is 227,919,677 bytes, byte-identical in size to the copy on disk | 227,919,677 bytes | reopened | n/a [detail](#the-darkened-dartmouth-nber-metadata-item) |
| Zenodo banner-ad corpus, `zenodo.org/records/8408539` | 2026-08-23 | 1999-2001 | cdx query | n/a | n/a | 432.81 EE (2026-08-23) | Real, in-window, correctly shaped and too small. A 215 MB JSON of 22,915 banner images mined from archived snapshots of URLs taken from six printed directories published 1999-2001, each `appearances` entry carrying a 14-digit Wayback | 215 MB | n/a | n/a [detail](#zenodo-banner-ad-corpus-zenodo-org-records-8408539) |
| AFNIC `.fr` OPENDATA back editions | 2026-08-23 | n/a | n/a | n/a | n/a | 781.98 EE (2026-08-23) | The mechanism is wrong: measured on 202011 (494,444,288 bytes) and 202201 (549,508,248 bytes), taking only the creation year as rule 6 requires, each yields exactly the same 65,268 in-window rows, because OPENDATA is a snapshot of names | 494,444,288 bytes | n/a | n/a [detail](#afnic-fr-opendata-back-editions) |
| SEC EDGAR beyond the closed row: 8-K, DEF 14A, 10-KSB | 2026-08-24 | n/a | n/a | n/a | n/a | 5,884 EE (2026-08-24) | Real, in-window, dated by EDGAR itself and too small at 5,884 net-new EE, 2.0% of the gate. One filing is dated by the `Date Filed` column of `full-index/<year>/QTR<n>/form.idx`, an EDGAR-assigned date, filtered before extraction: 222,232 | n/a | n/a | n/a [detail](#sec-edgar-beyond-the-closed-row-8-k-def-14a-10-ksb) |
| Federal Audit Clearinghouse historic Single Audit filings 1998-2001 | 2026-08-24 | 1998-2001 | n/a | n/a | n/a | 2,406.69 EE (2026-08-24) | Admissible and small: 2,406.69 net-new EE. One item is one e-mail field on one filing row, dated by that row's own signature date, `AUDITEEDATESIGNED` or `CPADATESIGNED`, which is a date a human wrote down, so it takes the corroboration | n/a | n/a | n/a [detail](#federal-audit-clearinghouse-historic-single-audit-filings-1998-2001) |
| UK Companies House bulk corporate filings | 2026-08-24 | 1996-2001 | n/a | n/a | n/a | n/a | Out of window by construction: the Accounts Bulk Data files are named by publication date and the published range does not reach 1996-2001, and the Company Data Product is a current-state snapshot with no per-row filing date and no website | n/a | n/a | n/a [detail](#uk-companies-house-bulk-corporate-filings) |
| Reuters RCV1 newswire | 2026-08-27 | 1996-1997 | n/a | n/a | n/a | n/a | Not fetchable and screened at a few hundred EE, so the signature is not worth chasing. `trec.nist.gov/data/reuters/reuters.html` distributes it only by written request and signed agreement. Two independent bounds: the corpus spans | n/a | worth | n/a [detail](#reuters-rcv1-newswire) |
| `discmaster.textfiles.com` as a CLASS rather than a query | 2026-08-27 | n/a | robots refusal | n/a | n/a | 1,055.3 EE (2026-08-27) | Priced at 1,055.3 EE, which is the lens's whole yield: one banked-pending artifact (`antispam_media_blocklist`) and a `.jp` listing rejected at 185.3, against an index of 1,718,970,121 files already recorded saturated by filename and by | 1,718,970,121 files | Priced | n/a [detail](#discmaster-textfiles-com-as-a-class-rather-than-a-query) |
| The IA "Web Data Services" extraction family, both arms | 2026-08-27 | 1996-2001 | cdx query | n/a | n/a | 100.2 EE (2026-08-27) | Priced and closed, and it is law 1 measured on the corpus most likely to beat it. The ccTLD arm is one member: `Poland_pl-ccTLD_2001-12-31`, 19 items of about 10.8 GB, `access-restricted-item: true`, and `.pl` weighs 0.107. The in-window | 10.8 GB, 19 items | Priced | n/a [detail](#the-ia-web-data-services-extraction-family-both-arms) |
| The Wayback availability endpoint as a SECOND dating engine, and the 2.4M undated pool it was aimed at | 2026-08-30 | 2000-2001 | robots refusal | is `archived_snapshots.closest.timestamp`, the 14-digit capture stamp the Wayback index wrote when the crawler fetched | 73.0% of what cdx returns is already held | 1,494 EE (2026-08-30) | n/a | 1,798 requests | FIND | <https://archive.org/wayback/available?url=> [detail](#the-wayback-availability-endpoint-as-a-second-dating-engine-and-the-2-) |
| Reading reviewer benchmark-release diffs to fingerprint other contributors' sources | 2026-08-31 | 1996-2000 | n/a | n/a | n/a | 0 EE (2026-08-31) | FIND, 0 EE from the diff itself (already merged by construction). `comm -13` across 11 consecutive `feedback//merged` releases named three populations worth pursuing: UMN DRUM `EARLYWEB_1996_2000` parts 01-02 (3.72 GB unfetched, projected | 3.72 GB | FIND | n/a [detail](#reading-reviewer-benchmark-release-diffs-to-fingerprint-other-contribu) |
| RDAP-liveness tiebreaker for the query queue, verified and patched but not wired | 2026-08-31 | n/a | rdap query | n/a | n/a | 0 EE (2026-08-31) | FIND, 0 EE banked (a ranking method, not a source). Verifies the `sources.md:590` finding: 99.851% of the `.com` gap population already carries an RDAP verdict, 61.775% live, reproducing the banked figures to within | n/a | FIND, not a source | n/a [detail](#rdap-liveness-tiebreaker-for-the-query-queue-verified-and-patched-but-) |
| NYPW TimeMaps, re-priced on the 2000 partition instead of the saturated 1996 one | 2026-08-31 | 1997-2000 | cdx query | is field 3 of each TimeMap row, IA's own 14-digit capture stamp (`cdx_timestamp`). | n/a | 4,146.8 EE (2026-08-31) | FIND at 4,146.8 net-new post-split EE over 6,424 pairs | n/a | FIND | <https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_deeplinks_part00o.tar.gz> [detail](#nypw-timemaps-re-priced-on-the-2000-partition-instead-of-the-saturated) |
| Whois-server and TLD-registry-index file census, discmaster | 2026-09-01 | 2001 | port 43 whois | n/a | 79.3% one-edit-from-held | 9.7 EE (2026-09-01) | FIND at 9.7 EE post-split, parked pending, not banked: fails standing-rule condition 2 (dating is a media mtime `discmaster` renders, not a stamp written into the artifact's own bytes). | n/a | FIND | n/a [detail](#whois-server-and-tld-registry-index-file-census-discmaster) |

## `usenet_announce` and `usenet_mention`: dated website announcements from Usenet

Giganews' 2013 Usenet donation to the Internet Archive: dated posts quoting site URLs. Full per-group
`.mbox.zip` files in the hierarchy items, e.g.
`https://archive.org/download/usenet-comp/comp.infosystems.www.announce.mbox.zip`, sha1 per file.
**Dating: each message's own `Date:` header, with the globally unique `Message-ID` as the evidence
value, so a reviewer can name the exact post behind any year; intrinsic to the artifact rather than
recovered from a crawl.**
`usenet_announce` (`dated_directory`) where another source already places the domain in `domain_year`;
the URL beside the date is human-typed, so it takes the corroboration split and a Usenet-only name is
`usenet_mention` (`link_target`) in the candidate pool. 2,017,182 evidence rows, 1,022,707 domains;
seams `usenet_address` 62,820.7 EE, `usenet_bare` 28,460.3 EE.

Closed:

- Per-date Giganews exports: `comp.infosystems.www.announce.20140404.mbox.gz` holds nine posts, all
  2005 to 2010.
- `Message-ID`, `Reply-To`, `Sender`, `NNTP-Posting-Host`: 2,869 net-new of 1,025,582 pairs, 1,038.4 EE.
- `Path:`: 13.89 EE on a 400-archive sample, and none before 2000.
- `alt.irc`, `alt.music.oasis`: HTTP 500 or 502 on every attempt, 0.05% of the corpus.
- `alt.*` screening: 1,013 EE per GB against a corpus mean of 1,065.

## `tucows_catalogue` and `tucows_mention`: the Tucows Software Library

32,600 items donated to archive.org in 2004, 11,499 in window, each with a release `date` and a
`creator` field holding the vendor's home page URL.
`https://archive.org/services/search/v1/scrape?q=collection:tucows+AND+year:[1996+TO+2001]&fields=identifier,date,creator&count=10000`
**Dating: the item's own release `date`, a structured catalogue field rather than free text, with the
identifier as the evidence value, openable at `https://archive.org/details/<identifier>`.**
`tucows_catalogue`, split because the catalogue was donated in 2004, so a `creator` URL may record
where a vendor lived then rather than at release: 942 net-new pairs entered the annual files, 746
domains the candidate pool as `tucows_mention`.

Closed: Winsite `INDEX.TXT` (7,057 entries, zero vendor domains), Programmer's Library `FILES.txt`
(no URLs), CNET Download.com (zero vendor URLs), SimTel (216 GB tarball, no author domains in its CD
indexes): pre-web in design, settling the CD-ROM catalogue family.

## `maillist_archive` and `maillist_archive_mention`: public pipermail list archives

Pipermail per-month files of raw messages with headers, from `mail.python.org/pipermail/` and
`mail.gnome.org/archives/`: 2,558 in-window month files, 579,808 messages dated 1996-2001.

```bash
uv run python scripts/sources/mail_corpora/collect_mailing_lists.py --harvest --write
uv run ark ingest maillist_dated      data/raw/maillists/maillist_dated.jsonl.gz
uv run ark ingest maillist_candidates data/raw/maillists/maillist_candidates.jsonl.gz
```

**Dating: each message's own `Date:` header, read per message, not the month in the filename: a month
file is assembled by arrival, so 450 of 581,323 messages date outside the window and are dropped.**
`dated_directory` corroborated, `link_target` otherwise: a mail body is human-typed, so it takes the
corroboration split. 1,458 net-new pairs, 833.17 EE.

Closed for breadth: 0.00145 and 0.00121 EE per in-window message against 0.0067 for Enron, 83.6% of
pairs already held. `lists.debian.org` no bulk month file, `lists.samba.org` 426, `sourceware.org`
403. `lore.kernel.org` HTML is behind Anubis, but `git clone https://lore.kernel.org/lkml/0` serves fine
and public-inbox stores each sender as the git commit author: 81,741 in-window messages, 92.2% held,
80.19 EE post-split.

## `enron_email` and `enron_email_mention`: the FERC Enron corpus

FERC's Enron email release, about 500,000 messages from 150 employees, mostly 1999-2002.

```bash
curl -L -o data/raw/source_probe_260806/enron.tar.gz \
  https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
uv run python scripts/sources/mail_corpora/collect_enron.py --write
uv run ark ingest enron_dated      data/raw/enron/enron_dated.jsonl.gz
uv run ark ingest enron_candidates data/raw/enron/enron_candidates.jsonl.gz
```

**Dating: each message's own `Date:` header, carried inside the message rather than assigned by a
reader; out-of-window messages are dropped rather than pulled in, since the corpus runs past 2001.**
`dated_directory` corroborated, `link_target` otherwise: mail bodies are human-typed, so this takes
the corroboration split. 5,134 net-new pairs, 3,241.9 EE, 0.0067 EE per in-window message.


### `attrition_defacement`: the attrition.org web defacement mirror

Web defacement mirror, January 1999 to 21 May 2001: date, defacer, organisation, defaced hostname. Republished as `attrition-org/web-hack-mirror`; its 33 index pages sit at `data/raw/source_probe_260806/attrition/`, and `just collect attrition` replays them without a request.

```
https://raw.githubusercontent.com/attrition-org/web-hack-mirror/main/mirror/{1995,1996,1997,1998}.html
https://raw.githubusercontent.com/attrition-org/web-hack-mirror/main/mirror/{1999,2000}-{01..12}.html
https://raw.githubusercontent.com/attrition-org/web-hack-mirror/main/mirror/2001-{01..05}.html
```

Skip the 265 per-TLD and per-defacer breakout pages: same rows re-sliced.

**Dating: each row opens with a two-digit date the mirror stamped on the day it captured the defacement, then the host in parentheses, and a defaced host was serving that day.**

```
[99.11.30] Li [potus] Coronus Networking ( www.coronus.com )
```

Evidence type `artifact_listing`, self-dating, no corroboration split. Ingested: 5,816 net-new pairs, 2,791.4410 EE.

### `pandora_titles`: the National Library of Australia title index, as candidate seeds

PANDORA's Title Entry Page index, 87,732 rows of `tep_id, name, gathered_url, surt`, CC0, at `data/raw/pandora-titles/`. <https://github.com/GLAM-Workbench/trove-web-archives-titles>

```bash
uv run python scripts/sources/directories/seed_pandora_titles.py    # -> pandora_hosts.txt
uv run ark seed data/raw/pandora-titles/pandora_hosts.txt
```

**Dating: none. No date column of any kind, so nothing in it can evidence a year; seed-only permanently.** Evidence type: none. 29,432 names unknown to the store enter the candidate pool claiming nothing.

### `udrp_wipo`: WIPO domain-name dispute decisions, 1999-2001

Every UDRP case, the disputed domain in its own column of the case table.

```bash
uv run python scripts/sources/directories/collect_udrp_proceedings.py  # -> items.jsonl, one row per case
uv run python scripts/pricing/price_items.py --items <items.jsonl>
```

**Dating: the filing year encoded in the provider-assigned case number, not the decision date, since a case filed in 2000 may be decided in 2001 and the domain existed at filing.** Read the second table cell only; stop on repeated pages, not empty ones.

Readings: `artifact_listing`, self-dating, 5,389 pairs, 3,281.0 EE; `dated_directory` with the corroboration split, 956 pairs, 593.5 EE. Store holds all five providers: WIPO 5,963 rows, NAF 2,575, DeC 210, eResolution 133, CPR 42.

Closed here, ceiling about 90 EE, never reopen on availability:

- NAF `adrforum.com/domain-dispute/search-decisions`: 200 but client-side only, no server-rendered index.
- A larger NAF shortfall: Zenodo 21310923 counts 1,426 Forum decisions for 2000-2001 against 2,573 NAF domains held.
- ICANN `archive.icann.org/en/udrp/proceedings/domains-list.txt` (4,666,685 bytes), `proceedings-list.txt` (2,924,147 bytes): 8,662 in-window pairs, 90 net-new.
- Zenodo 16954717 `full-udrp-parsed-proceedings.jsonl.gz`: 158 net-new, 90.10 EE, and its `submitted` field is corrupt (`D2002-0431` carries 1999-08-26), so trusting it fabricates 518 1999 pairs.

### Bytes already on disk that nothing reads

- `pandora-titles/`, 13 MB: seeded, seed-only; `data/raw/pandora/` is a byte-identical copy.
- `source_probe_260806/hathitrust_ef/`, 12 MB: 73 extracted-features files pulled before the HathiTrust rejection, never measured, so that rejection does not cover them.
- `source_probe_260806/attrition/`, 2.7 MB: the 33 defacement index pages, ingested.
- `usenet_hdr/`, 40 MB: already in the store under `usenet_addr_*`; a reproduction gap only, no `SourceSpec` replays its 19,224 evidence rows.
- `source_probe_260806/scripts/` and `logs/`: the 6 August measurement scripts and their output, which is the 938 MB.

### UK Government Web Archive

The National Archives' CDX endpoint, UK government sites from 1996.

```bash
curl -sS -A '<a browser User-Agent>' \
  'https://webarchive.nationalarchives.gov.uk/ukgwa/cdx?url=number-10.gov.uk&matchType=domain&from=1996&to=2001&limit=5&fl=timestamp&output=json'
```

An honest project UA gets `302 Found` with a 0-byte body; a browser UA answers in 0.23 s. `from`, `to` and `filter=statuscode:200` are honoured.

**Dating: the CDX `timestamp` the crawler writes at the moment of capture.** Evidence type `cdx_timestamp`. Earliest coverage seen `mod.uk` 19961111.

**Verdict: real but tiny.** Government-only, seven for seven non-government hosts absent, addressable population 250 domains, so the collector costs more than the answers.

---


## archive.org FTP mirror archives, 2001 mtimes inside the ZIPs (closed, zero)

**Proved zero.** 638 of 651 ZIP/TAR FTP-mirror archives listed; 143,338 rows dated 2001 across 254 of them, so the control passed, yet all 69 filename-regex hits on 2001 rows are false positives. Vhost variant zero too: the one archive clearing 200 domain-shaped segments is a DOS `.COM` executable collection.

---

## JISC UK Web Domain Dataset per-year CDX (`ukwa.ds.2/cdx/`): found, sized, NOT retrievable

One CDX file per year 1996 to 2013 at `webarchive.org.uk/datasets/ukwa.ds.2/cdx/`, 13.45 GB compressed in-window, which would be `cdx_timestamp` with no split. Not retrievable: IA never captured the files, the publisher serves stubs, archive.org returns `numFound` 0, and the British Library replied on 2026-07-22 that access returns Autumn 2026, first stage a per-URL lookup. Reopen when bulk access returns.

**Banked from the same dataset, 9.81 EE:** `bl-uk-linkage.tsv` (724,598 bytes) and
`york-ac-uk-linkage.tsv.gz` (2,244,274 bytes) in `linkage/`, `year|source|target` rows read by
the existing `ukwa_link_source` parser. **Field 1 is the crawl year written by the archive's
link-graph extractor, not asserted by a person.** Class `link_source`. 1,899 and 3,731 in-window
pairs, 99.9% and 99.8% already held, 1 and 9 net-new pairs. Target-selected at `bl.uk` and
`york.ac.uk`, so they do not re-price the full `host-linkage.tsv.gz`.

---

## namewinner.com expiring-domain list, 2001-10-26 (PRICED, needs a Decision)

Dotster's expiring-domain auction list, `http://namewinner.com/whole_list.php?del=tab`, capture
`20011026120205`, 20,943 distinct registrable domains, 25.6% held. **Every row carries the
per-item date `25-OCT-01`: the file holds 20,945 occurrences of that string and no other date
string of that shape, printed by the registrar's own expiring-domain system, and the capture
fixes the instant at 2001-10-26 12:02 UTC.** A soon-to-expire listing states the name is
registered now. Class `artifact_listing`, master-eligible; a registrar database dump, not
human-typed, so no split. Master reading 18,951 net-new pairs, 11,555.0 EE.

2002 sibling filed separately: capture `20020407171418`, 52,204 domains dated `05-APR-02` to `10-APR-02`, needing the one-year-term inference to reach 2001, 4,134 pairs and 2,543.2 EE. Only four of 21 `whole_list*.php` captures carry content, the rest 373 to 415 bytes.

dailychanges.com: `ns=LAME-DELEGATION.ORG&date=2002-08-01` is 4,511 names at 66.7% held, 1,076.3 EE, against 0.021 EE per name on four registrar pages, so held-fraction tracks the age of the nameserver's population.

Closed: `deleteddomains.com` list endpoints are 3.0-3.4 KB query forms with no result set; `snapnames.com` lists sit behind `/protect/` login; `pool.com` is one domain per page; `unclaimeddomains.com` has no TLD and no date; `deletedomains.com` largest capture 2,987 bytes; `domainstate.com` zero CDX rows 2001-2003; `dotster.com` no bulk list in 2,583 captures. `domainsbot.com` is untested, CDX never answered.

---

## US Domain delegated-subdomains list (PRICED, needs a Decision), and the ISC survey closed for good

`us-domain-delegated.txt`, the US Domain Registry's list of delegated `.us` zones, at `pub/rfc/`
inside the `2015.04.ftp.isc.org.tar` mirror on archive.org and at
`www.isi.edu/in-notes/us-domain-delegated.txt`, captured 2000-08-15, 2000-12-06, 2001-04-11 and
2001-06-06 (last three byte-identical at 435,847 B). **Dated twice by machine: tar-preserved
member mtimes (1996-10-09, 1996-11-20, 1999-03-22, rotations `.0`-`.5` from 1999-02-19 to
1999-03-18, monotone in both date and size), and `cdx_timestamp` on the 2000 and 2001
captures.** Class `artifact_listing`, master-eligible. Union 13,816 net-new pairs post-split,
12,775.5 EE. Typo upper bound 17.8%; 1997 and 1998 unreachable. `ftp.isc.org` robots.txt is a
blanket `Disallow: /`, so use the mirror only.

ISC Domain Survey closed permanently: `www/survey/archive-data/` ends at `9707.domains.gz` and every file in `reports/1998/` through `reports/2002/` is 1.4-21 KB of per-TLD counts. `enterprise-numbers` (339,504 bytes, 1999-03-22): 2,348 of 2,445 domains already held, 48.1 EE.

FTP-mirror-ZIP gaps closed: ranged ZIP64 central-directory reads listed all 9 truncated ZIPs complete, three zero-row archives are corrupt uploads at exactly 4,294,967,295 bytes, and the single bulk host artifact in all 42 is the `us-domain-delegated.txt` family.

---


## Academic repositories and DOI datasets: CLOSED, by enumeration through five APIs and two registries

DRUM's six-item "Link Lists for Websites" family and DataCite filtered on `dates` in 1996-2001 both leave only DOI `10.13020/d62684`, already ingested; Harvard Dataverse file-level search returns 0 for `domains.txt`, `hostnames.txt`, `zonefile`, `hostlist` and ten more shapes; re3data's 3,521 repositories give three name matches, all held or priced. `api.osf.io/robots.txt` is a blanket `Disallow: /`, so OSF is closed on robots, not content.

## Dated internet-trade directories (ISPs and web hosts): closed, and the ceiling is the reason

Across every 1996-2002 capture of `thelist.com` and `thelist.internet.com` the largest object of any kind is a 14,390-byte GIF, and the whole 1996-2001 ISP and news-server population is a few thousand hosts already held, returning zero novel domains over 73,751 Usenet messages. Boardwatch's ISP Directory volumes stay blocked because `..._djvu.txt` returns a 146-byte stub; reopen on a route to those volumes' text.

## discmaster by FILENAME: reopen condition resolved, and the lens is saturated

`qfields=name`, `mode=deep` and `YYYYMMDD` dates make the endpoint answer in about 5 seconds, discharging the recorded timeout closure. Nine filename queries over an index of 1,718,970,121 files return only already-priced squidGuard lists and software furniture, and `email.domains` returns exactly one file, the `.jp` listing rejected at 185.3 EE. Preserved media is exhausted by name and by size.

### us-domain-delegated.txt

The `.us` delegated-domain zone list, five in-window editions (1996-10-09, 1996-11-20,
1999-03-22, 2000-08-15, 2001-06-06). The 2001 edition fetched live at 435,846 bytes with 6,512
zone rows:
`web.archive.org/web/20010606153725id_/http://www.isi.edu/in-notes/us-domain-delegated.txt`; the
1996 and 1999 editions sit at `pub/rfc/` inside `archive.org/details/2015.04.ftp.isc.org`. **The
file carries no in-body date, so the edition is fixed by the crawler-written capture timestamp
in its filename, and `_USD_EDITION` skips any file it cannot date rather than guessing.**
`parse_us_domain_delegated` reads column 2 only, so column 3 contacts are never read as
delegations. Approved master by Ivo on the delegation argument: **+15,173.22 EE over 16,384
pairs.**

## `squidguard_2001_blacklist`: BANKED 10,376.92 EE, and the closure it reopens

Robot-compiled proxy blacklists shipped as squidGuard 1.2.0 samples:
`archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`, 1,852,659
bytes, holding `squidguard-1.2.0/samples/dest/blacklists.tar.gz`. **Each list carries its own
compile stamp on the line before `compiled from`: `# This list was compiled in 19:44:45 on
2001.12.15 19:56:41.`, written by `squidGuardRobot-2.3.4`, which names itself and asserts a
successful fetch (`654820 links, of which 510389 tested successfully`), so nobody typed the list
and it takes no corroboration split.** Every stamp falls between 2001.12.15 and 2001.12.18, tar
member mtimes agreeing. Licence GPL v2, verbatim in `squidguard-1.2.0/COPYING`. 18,000 pairs
banked; diff `-` lines are removals and were dropped. `mail/domains` has no compile header and
is skipped.

## The squidGuard contrib blacklist at its ORIGIN, two 2001 editions (PRICED, needs a Decision)

The list the banked `squidguard_2001_blacklist` is a distribution sample OF, taken from the host that
compiled it rather than from a release tarball, and it survives in Wayback at two dates inside 2001:
`web.archive.org/web/20010710215730id_/http://ftp.ost.eltele.no/pub/www/proxy/squidGuard/contrib/blacklists.tar.gz`,
403,211 bytes, gzip mtime 2001-07-09 13:39:23, and the previous edition left on disk as
`blacklists.tar.gz~` at capture `20010911061641`, 1,576,754 bytes, gzip mtime 2001-09-09 07:55:13.
Found by reading the 2001-12-12 capture of `www.squidguard.org/blacklist/`, which names the download
URL and the two alternative lists. Staged at `data/raw/squidguard_contrib_2001/`.

**What dates one item is the same machine-written header the banked edition was approved on**, one per
category file: `# This list was compiled in 79:50:07 on 2001.07.03 08:08:29.` from
`squidGuardRobot-2.2.13` over `286445 links, of which 230616 tested successfully`, and
`# This list was compiled in 33:22:40 on 2001.09.09 09:48:47.` from `squidGuardRobot-2.3.4` over
`2402 link sources and 463098 links`. The robot names itself and asserts a successful fetch, so nothing
was typed by a person and no corroboration split applies. Every tar member mtime agrees, running
2001-07-03 to 2001-07-09 and 2001-08-10 to 2001-09-09, and the per-date `newdomains.YYYYMMDD` and
`newurls.YYYYMMDD` files carry the date in the filename as well. `mail/domains` has no compile header
and is skipped, exactly as in the banked edition.

**Measured 2026-08-27 against the live store, which already holds the December edition: 2,553 net-new
post-split pairs and 1,506.4 EE**, all at 2001, from 74 content files, 75,347 distinct hostnames and
42,321 registrable domains. Before the split it is 3,292 pairs and 1,960.0 EE. By TLD: `com` 2,283,
`de` 183, `net` 73, `org` 6, `nl` 3, `ch` 2. Typo upper bound 49.1%. The two editions read 406.7 EE
(July, 7,035 domains, 6,258 held) and 1,368.0 EE (September, 37,186 domains, 34,163 held).

**39,029 of the 42,321 domains, 92.2%, already carry 2001**, and that is the December edition's doing
rather than the store's general coverage, which is the same "editions within one year are worth one
edition" law that made the 175 unbanked 2001 diffs pay zero. It shows up a second way: adding the
`urls` files and the dated new-entry files moves the reading from 1,488.1 to 1,506.4 EE, **18.3 EE**,
where the same addition on the December edition was worth 32%. What is left after December is the
names the robot found in July and September and had dropped by mid-December, which is a real and
bounded residue rather than a second copy of the same list.

**Licence is the one thing to check before ingesting and it is NOT settled by the banked entry.** Both
tarballs hold `blacklists/README` and no `COPYING`: GPL v2 covers the squidGuard source distribution
the December sample came in, and these two files are the standalone data drop from the project's own
FTP host, carrying only the README's "entierly products of a dumb robot" warning.


## RIPE NCC's reply, 2026-08-26: permission given, and what the file actually contains

The request quoted the file, its "Restricted rights" notice and the use. RIPE NCC Member Services
replied: "As long as the data is publicly available and visible to you, you are
welcome to use it for your research", the one condition being not to make a large number of requests
involving personal data against the live database. We make none: the artifact is a static file on
disk. A census of all 63 attribute codes returns zero for person, address, phone, fax, e-mail,
nic-hdl and role. The report attributes the RIPE NCC.

## `ripe_dbase_1999`: BANKED 90,770.29 EE, the most PAIRS of any source this round

The 1999-08-04 RIPE database snapshot, 1,232,554 distinct registrable names, at
`ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz`.
**Dating: the dump's own header line `# 990804 00:07:01`, written by RIPE's export process and read
rather than assumed, so it evidences 1999 and no other year; a file with no `# YYMMDD HH:MM:SS` line,
or a stamp outside 1996-2001, is refused.** 641,038 net-new pairs at 1999.
`parse_ripe_dbase_1999` reads `*dn:` and nothing else, held there by four tests.

## `namewinner_expiring`: BANKED 11,546.26 EE on the master reading

A dump out of a registrar's expiring-domain database, at
`web.archive.org/web/20011026120205id_/http://namewinner.com/whole_list.php?del=tab`, 581,560 bytes,
tab-separated plain text despite the `.php`.
**Dating: each row carries its own expiry date, `25-OCT-01`, 20,945 occurrences and no other date of
that shape in the file; the parser reads the row's date, not the filename or the capture, so the
2002-04 capture's `25-APR-02` rows are refused one at a time.** 18,937 pairs at 2001. No corroboration
split: being registered is the only way onto the list, so it dates novel names too.

## `can_domain_registry_notices`: BANKED 7,934.20 EE on a one-word ruling

Registry approval notices posted to `can.domain`, at
`archive.org/download/usenet-can/can.domain.mbox.zip`, 14,326,153 bytes, 37,578 approval fields; the
item is named for the hierarchy, not the group.
**Dating: the `Date-Approved:` field the registry prints inside its own approval notice, in
machine-formatted aligned columns with ISO-style dates, the registry's own act rather than a
description of someone else's.** `whois_creation`, that year only, 9,485 pairs. A record block is
bounded by the next `Subdomain:` line, so a neighbour's date cannot attach.

Closed alongside it: `Date-Modified:` is **0.0 EE**, nine such records archive-wide; and the
better-named decoys `usenet-can.domain` (208 KB) and
`FULL-USENET-BACKUP-2020-Oct-can.domain.189.mbox.7z` (124 KB) hold zero `Date-Approved:` fields.

## SEC EDGAR filings, re-measured: right size, wrong shape, and too slow to help this round

Not banked: 1999 QTR1 gave 0 net-new post-split over 389 filings, 2001 QTR4 gave 13 net-new and 8.0
EE, and the bulk `Feeds/<year>/QTR<n>/` route 404s for 1996, 1999 and 2001, leaving one request per
filing, ~90 hours. **Reopen as a background job with an absolute deadline over the
2000-2001 quarters.**

## `dartmouth_bfs_seed` and `cctld_register_listing_inbody`: BANKED 3,018.18 EE

**`dartmouth_bfs_seed`**: a level 0 BFS CDX crawl, 2,442 pairs over 18,940 domains. **Dating: `cdx_timestamp` on field 2 of each CDX row, written by the archive at
capture, self-dating, no split.** Levels 2 and 3 are closed at 0.00, 0.00 and 0.59 EE per MB against level 0's 104.7.

**`cctld_register_listing_inbody`**: 10,177 pairs, from TWNIC's `.tw` frozen-domain list and IDNIC's
`.id` unpaid-fees table. **Dating: TWNIC's page stamps itself `更新時間: 2001/8/27 20:0:31` and lists
names whose registration expired between 2001-05-29 and 2001-08-26, so each was in the register during
2001; each IDNIC row carries its own `Jatuh Tempo` due date, the registry stating the boundary of that
registration's paid period.** The evidence value carries the date that justifies the row, `@1998` for a
row-dated name, the page stamp otherwise.

## BANKED: `ripe_dbase_changed`, 399,401 pairs and 58,398 EE, and the round crosses 5%

The `changed:` attributes of the domain objects in the 1999-08-04 RIPE snapshot already on disk.
**Dating: a `changed:` line is `address SPACE date` and carries its own 8-digit date, recording an
update applied to that object by a party with authority over it. An object cannot be modified if it does
not exist, so the line is its own dated record of existence in its own year, the shape rule 6 demands
and one a creation date can never supply.** The changer is a ccTLD registry role account in the large
majority of cases, DENIC's `hostmaster@nic.de` alone writing 49.4% of the 2,016,169 lines; for the tail
the claim is only that somebody entitled to modify the object did so. By year 1996 18,944 / 1997 67,515 / 1998 312,942, 1999 zero, which is the thin end of the store's
coverage. The pattern captures only the trailing 8-digit group; three tests fail on a leaked address.

## `usenet_whois_paste`: BANKED 30.4 EE

Registry whois records people pasted whole into Usenet posts, read out of the 16,849 archives already
on disk under `data/raw/usenet_{bulk,new,probe,probe5,msft}` (`https://archive.org/download/usenet-<hierarchy>/<group>.mbox.zip`).
**What dates one item is the registry's own line inside the pasted block, `Record created on
20-Jul-2000.`, written by InterNIC and not by the poster, so it fixes the registration year whatever
year the post carries; rule 6 gives that year alone.** 769 in-window pairs, 636 on corroborated
domains, 92.1% of them already held, **50 net-new pairs and 30.4 net-new post-split EE**; the 133
names seen only here take the split and go to the candidate pool as `link_target`.

## Candidate-only pools

These earned no year and no row in any annual file. They are named because they are `source` values in
`audit/source_contribution.csv` and a reader tracing that column should find them here: `candidate_hosts`
(hostnames seen without a dated observation), `udrp_hosts` (disputed names from UDRP dockets),
`H008-pool-names` (a pricing probe's name list), `attrition_out_of_window_hosts` (defaced hosts whose
defacement date falls outside 1996-2001), and four US federal registers whose web-address columns
are current-state rather than dated, `fac_single_audit_candidates`, `fac_cpa_firm_candidates`,
`imls_library_survey_candidates` and `ncua_call_report_candidates`. **A current-state snapshot cannot
evidence a past year**, which is why all four are pools and not sources.

---

## `chastity_list_blacklist`: BANKED on a tar member header, ranked first in the triage queue

**The link, and the terms.** `https://archive.debian.org/debian/pool/main/c/chastity-list/chastity-list_0.5.orig.tar.gz`,
720,609 bytes, staged at `data/raw/chastity/`. The chastity project's category ACL files for
squidGuard, by Roy-Magne Mo. **Licence GNU GPL v2, verbatim in `COPYING`**, so redistribution and
derivative use are granted outright; `archive.debian.org` serves no robots.txt (HTTP 404), and the
file was fetched with one request against a host that publishes no restriction.

**Why it meets the standard.** What dates one item is a stamp a program wrote inside the artifact:
**the tar member header `Dec 14 2001`, carried by every one of the 258 members of the orig tarball**,
corroborated from inside by 209 per-date diff filenames running `domains.20010813.diff` through
`domains.20011201.diff`, monotone and all in window. That is the identical argument already approved
for the 1997 half of `junkfilter_dated_blocklist`, so no new evidence class is invented. Class
`dated_directory`, master-eligible. A blocklist entry is a claim the host was live and serving when
the maintainer wrote it down, which is an assertion about a state at an instant the artifact stamps
itself, and rule 6 is respected because the edition evidences 2001 and no other year.

**The split is applied and costs almost nothing here, by construction.** The list is hand-maintained,
so the name is a person's typing and takes the corroboration split. `scripts/sources/blocklists/split_chastity.py`
applies the strict predicate, that the domain already carries an assigned year in `domain_year`, and
writes two lanes: **92,068 of 97,937 distinct registrable domains are corroborated, 94.0%**, and the
remaining 5,869 park as `link_target` candidates that date nothing. The measured yield sits on the
corroborated lane because "held" and "corroborated" are the same test.

**Measurement**: 136,885 base list lines across 13 categories yield 97,937 distinct registrable
domains, of which 24,927 are held with no 2001 record, **14,229.0 net-new post-split EE at 2001**,
`.com` carrying it at 20,149 pairs and 12,736.2 EE. Reproduced on 2026-08-31 against the live store
at 97,937 / 92,068 / 94.0% against the 2026-08-27 reading of 97,937 / 92,059 / 94.0%, the nine-domain
drift being five days of ingest.

**Do not re-price this population at an earlier year.** The same names read naively at
held-in-any-year-and-missing-Y give 45,506 at 1999 and 12,699 at 2000, against 323 and 329 on the
adjacent screen: the naive figure overstates 1999 headroom **141x** and 2000 headroom **39x**, because
a blacklist's population was registered in the two years before its compile, so the store's gap at
those years is non-existence rather than missing data. squidGuard reproduced the same effect
independently at 167x. The out-of-window sibling `chastity-list_0.5.20020928.orig.tar.gz` is stamped
`Sep 28 2002` and cannot date a year; the whole SourceForge release history is three December 2001
releases, so no earlier edition exists to find.

**How it was found, since the method outranks the source.** **ONE request per Debian release for
`dists/<rel>/main/binary-i386/Packages.gz` indexes every package name, version, size and description
in that release**, which is the `ls-lR` trick applied to a package archive and turns a whole
distribution into an offline grep. Grepping the potato and woody indexes for blocklist-shaped
descriptions gave 41 and 81 candidates; the largest in woody was this one, 701,038 bytes, described
as "blacklists for SquidGuard".

---

## `granitecanyon_zone_rejects`: BANKED on a nightly error log the operator never meant as a customer list

**The links.** Seven objects, 1,567,653 bytes, refetched 2026-08-31 by
`scripts/sources/registries/collect_granitecanyon.py` and each one matching its 2026-08-29 byte count exactly:

- `https://web.archive.org/web/20010601000000id_/http://soa.granitecanyon.com/stale_30Nov1999.txt`
  (205,787 B, 14,522 zone names, the 1999 prune list)
- `https://web.archive.org/web/20010223195457id_/http://soa.granitecanyon.com/ZoneRejects/` (193,389 B)
  and the same path at `20010508024101` (212,935 B), `20010611192639` (215,340 B),
  `20010626115208` (222,405 B), `20010901062251` (245,087 B) and `20011204210150` (272,710 B)

**Why it meets the standard.** What dates one item is a stamp the operator's own program wrote
inside the artifact: each reject edition prints `Rejected Zone List:  <D-Mon-YYYY HH:MM GMT>` in its
own bytes, and all six in-window editions were verified on refetch to stamp themselves **23-Feb,
7-May, 11-Jun, 26-Jun, 31-Aug and 4-Dec 2001**, every one agreeing with its capture timestamp. The
1999 prune list is dated by `status.shtml`'s "29 November 1999 ... here is the list of pruned zones"
and by its own filename. So one row is Granite Canyon's nameserver holding that zone in its BIND
configuration at the instant the file was generated, which is a machine's configuration record
rather than anyone's description of one. Class `artifact_listing`, master-eligible, already
approved. Killer 8 order is respected: the grounds are the self-stamp plus the capture, and the
overlap with the store is cited afterwards as a check, never as the argument.

**The split is applied.** The zone name was typed by a customer into a submission form, so the
corroboration split applies and only already-held names earn a year.
`scripts/sources/registries/split_granitecanyon.py` writes one lane pair per edition, so the year always comes from
the artifact and never from a default. Refetched and re-split on 2026-08-31 against the live store:
prune list **13,199 zones, 7,970 dated (60.4% held)**, reject editions 46.5% to 52.1% held,
**17,424 dated rows and 15,114 candidate rows** in total. `to_registrable` drops the
`.in-addr.arpa` reverse zones and the malformed rows on its own, which matters because `.arpa`
carries the highest weight in the model and `ark check` refuses it outright.

**Measurement**: 1,732.9 net-new post-split EE over 3,059 pairs, 0.102 EE per listed name, by year
{1999: 2,001, 2001: 1,058}, mean weight 0.5665. Pre-split is 10,272 pairs and 5,813.2 EE and
**overstates by 3.4x, so do not quote it**. The 1999 list alone is 1,125.5 EE and the 2001 reject
union alone 607.3 EE, so a held name in a 2001 edition is worth 2.3x the same name in a 1999 one.

**The held-fraction is the finding, and it is the transferable part.** 60.4% and 46.8% held,
against 87 to 99% for authority corpora, ~50% for blocklists, 98.4 to 99.6% for visitor logs and
~5% for forged-header spam corpora. A zone is not a page, so no crawler reaches it through a link
and the artifact is not head-selected: these are people who had a domain and no server. The
population also does not collapse on the 2001 threshold, P(lacks 2001 | held) measuring com
**0.5745**, net 0.6174, org 0.5113 against the store-wide law's 0.611 / 0.653 / 0.568.

**Method, in three parts.** (1) **A free-DNS operator's CUSTOMER population is the tail and its
OPERATOR population is not**, and the two look identical until you ask who typed the name: the
zone-file-RHS closure measured nameserver operators at 99.3% held, and the same service read from
the other end measures 46.8%. The discriminator is whether the selection predicate is "runs a
nameserver" or "asked somebody else to run one". (2) **When a service hides its inventory behind a
login, look for its ERROR LOG.** All four other operators refused to publish a customer list
(secondary.com behind `/auth/`, zoneedit.com behind `login.html`, xname.org behind a per-zone
password, freedns.com an empty index); the one that published a nightly list of the zones its BIND
could not load gave away 4,369 names it never meant to. Reject lists, prune lists, lame-delegation
reports and stale-zone reports are machine-generated, self-stamped and regenerated on a schedule,
so every capture is a fresh dated edition and nobody thinks of them as a customer list. (3)
**Enumerate a dead site's list files from its own dated changelog, not from an index**: four
captures of `status.shtml` named every list file the site ever served and dated each, which a CDX
prefix query would have cost many more requests to establish.

**Exhaustion, so nobody re-probes it**: six ZoneRejects editions exist in 2001 and no more,
fourteen probes across 2001-01 to 2002-04 collapsing onto those six timestamps. A seventh edition
dated 26-May-2002 is **out of window and cannot date a year**, and the collector deliberately does
not fetch it. The predecessor `zoneRejects.txt` is 9 names at 2000-03-03 and HTTP 403 at every later
capture.

**A collection trap worth recording, because it cost a wasted pass.** The first refetch built the
replay URL as `{stamp}id_{host}` with no slash after `id_`, and web.archive.org answered every one
of the seven with the same 154,263-byte "Wayback Machine" interstitial. A size floor set at half the
expected bytes passed all seven, because the interstitial is larger than half of 193,389, so the run
reported success and wrote seven near-identical files. **A size floor is not a content check**: the
collector now rejects any body whose first bytes are an HTML5 document, and the correct form is
`{stamp}id_/{host}`.

---

## `cctld_register_listing_capture`: BANKED at 2,450.2 EE, against a source register that claimed 3,496.0

**The links, recorded because the entry had none and two of the four artifacts could not be
found from the description alone.** All four refetched and repriced from the bytes on 2026-08-31:

- **SaudiNIC `AllSA`**: `https://web.archive.org/web/20010414064415id_/http://www.saudinic.net.sa/cgi-bin/indexing.cgi?AllSA=AllSA`
  (1,458,399 B). Sibling `?AllComSA=AllComSA` at `20010414071027` is a subset and was not fetched
- **`.nu` expiry list**: `https://web.archive.org/web/20011222202631id_/http://www.nunames.nu/notRenewed.cfm`
  (1,162,481 B)
- **ISOC-IL `.il` register**: `https://web.archive.org/web/19980120012100id_/http://www.isoc.org.il/domains.html`
  (273,464 B)
- **NIC Malta**: `https://web.archive.org/web/19980525073234id_/http://www.um.edu.mt/nic/dir/` (20,269 B)

**Why it meets the standard, and the split differs per artifact.** SaudiNIC's page describes
itself as "A searchable directory for all registered domains under .SA" and is generated by
`indexing.cgi` out of the register, so the registry is stating its own register's contents and the
Wayback capture fixes the instant: `cdx_timestamp`, master-eligible, and **no split**, on the same
grounds as the already-approved in-body sibling (TWNIC, IDNIC, RESTENA), which is ingested with no
split step at all. `.nu`'s `notRenewed.cfm` is stronger than the class requires: **every row
carries its own machine-written `Expired` date** (`0372-pizza.nu` / `09-Nov-2001`), so the year
comes from the row, and a name whose registration lapsed in 2001 was in the register during 2001
and the artifact implies nothing about another year. ISOC-IL self-stamps `Document Modified:
3-1-98` but is a hand-kept directory with an organisation typed beside each name
(`arachim.ac.il - Michlalah - Jerusalem`), so **the split applies**. NIC Malta is hand-kept too.

**Measured, and the source register was 1.4x high overall and 817x high on one component:**

| artifact | claimed EE | measured EE | names | held |
| --- | --- | --- | --- | --- |
| SaudiNIC `AllSA` 2001 | 1,506.4 | **1,387.2** (no split) | 3,094 | 383 (12.4%) |
| `.nu` notRenewed 2001 | 144.1 | **959.8** (no split) | 3,495 | 51 (1.5%) |
| ISOC-IL 1998 | 375.0 | **101.4** (post-split) | 5,408 | 4,851 (89.7%) |
| NIC Malta 1998 | 1,470.5 | **1.8** (post-split) | 203 | 200 (98.5%) |
| total | 3,496.0 | **2,450.2** | | |

**NIC Malta is the lesson and it is worth more than the artifact.** The register claimed 1,624
pairs and 1,470.5 EE, the largest single component, and no such artifact exists: `nic.org.mt` has
**162 captures in the whole window and its largest object is a 3,908-byte GIF**. The real page is
on the university host, holds **203 names**, and **refuses the liveness claim this class rests
on** in its own words: "Sites are not required to be on-line prior to name registration. This
means that some of the links below may still be unreachable", and "This directory is not updated
regularly". It is banked at 1.8 EE so the negative is measured rather than assumed.

**Two collection traps, both of which produced a false zero in this run.** (1) **A CDX `limit` is
a false zero.** `notRenewed.cfm` was reported absent from `nunames.nu` after a `limit=2000` query
returned no match, and the page exists: the limit truncated the listing before reaching it. Query
the exact path with `matchType=exact` before concluding a page was never captured. (2) **A
registry's listing may not be on the registry's host.** NIC Malta's directory sat under
`um.edu.mt/nic/`, the university that ran the registry, and no query against `nic.org.mt` or
`nic.mt` could ever have found it.

**Why `.nu` is the find here and SaudiNIC is not, despite SaudiNIC being larger.** SaudiNIC is
12.4% held and `.nu` is **1.5% held**, so almost the entire `.nu` list is a population the store
has never seen, and `.nu` at 0.2787 still beats `.il` at 0.1958. The register had this component
at 144.1 EE, 6.7x low, because it priced it on the capture stamp and never read the per-row date
column that makes the whole list datable.

---

## MYNIC's fortnightly Domain Name Listing: SETTLED, the split does not apply, 6,883.1 EE

**The link.** `http://www.mynic.net.my/my/stats/<month><year>-{1,2}.htm`, 55 distinct pages of which
the `-1` and `-2` halves carry names and the bare-month pages are statistics tables. **34 of the 35
in-window name-bearing halves were fetched and parsed**; `dec2001-1.htm` has only a 318-byte empty
capture, and `feb2002-1` / `feb2003-1` are out of window. Staged at `data/raw/mynic/`.

**What dates one item**: the per-day heading above each block, `15 March 2001`, with `New` or
`Delete` beside the name, so MYNIC is stating that this name entered or left its register that day.
Both actions date the year and only that year: a name deleted on 15 March 2001 was in the register
until then. Class `artifact_listing`.

**The question this entry settles is the corroboration split, and the answer is that it does not
apply, on a test rather than on a judgement.** MYNIC also published a monthly statistics table
giving per-day, per-TLD New and Delete counts, with the note "Please click on the date to get daily
New and Delete domain name listings". If the listing is a complete enumeration out of the register,
its rows must reproduce those counts. For March 2001 the statistics table gives **New 850, Delete
166**; parsing the two listing halves gives **New 850, Delete 165**. An exact match on New and one
row short on Delete. **A hand-compiled list cannot reproduce a registry's own published counts
850/850**, so the listing and the statistics table are two views of one database, and this is the
registry stating its own register exactly as SaudiNIC's `AllSA` and the already-approved TWNIC,
IDNIC and RESTENA listings do, all of which are ingested with no split step.

**Measured whole-tree, against the live store on 2026-08-31**: 12,118 rows (10,322 `New`, 1,796
`Delete`) over years {2000: 3,716, 2001: 8,402}, giving 11,690 distinct pairs over 11,564 domains,
2,609 already held. **Unsplit 9,081 pairs and 6,883.1 EE**; post-split 1,558 pairs and 1,180.8 EE.
Mean weight 0.7579, `.my` at 0.7580. Net-new by year {2000: 1,202, 2001: 356}, typo upper bound
26.6%. The source register estimated "near 10,000 and 400" for the whole tree, so it was **1.45x
high on the unsplit reading and 3x LOW on the split one**, which is why the whole tree was measured
rather than scaled from 25 pages.

**A weaker signal that was nearly used as the argument, recorded so it is not trusted next time.**
Alphabetical ordering within a day and TLD group looks like a database `ORDER BY` and was the first
argument reached for, but it holds in only **75.2% of 472 groups**: `New` rows are sorted and
`Delete` rows are not, and a day-heading regex that misses some headings merges two days and makes
sorted runs look unsorted. **Ordering is a hint; reproducing the publisher's own counts is a test.**

---

## CO.ZA suspension and deletion queues, the wider tree VERIFIED at 3,704.3 EE, and a 16-character truncation

**The links.** The CO.ZA registry's own CGI, on **two hostnames**, which is what the wider tree
amounts to: `http://co.za/cgi-bin/{warn.sh,todel.sh}` and the same paths on `posix.co.za` and
`www.posix.co.za`, the host of the company that administered CO.ZA. **22 captures return HTTP 200**
against the 11 the register had verified on `co.za` alone, and the `posix` half is not a duplicate:
its earliest editions are **1997-12-21 and 1998-01-17, earlier than any `co.za` capture**. Staged
at `data/raw/coza/`, 22 objects.

**What dates one item**: the Wayback capture stamp, since neither page carries an in-body date.
`todel.sh` is headed "Domains in CO.ZA to be deleted ... The following domains are shortlisted for
deletion. This is due to lack of payment", and `warn.sh` is a separate list, "Domains in CO.ZA to be
or on Suspension ... shortlisted for or have been suspended. Within a couple of invoice runs they
will move to the Deletion queue". Both assert the name is in the register at that instant.
`cdx_timestamp`. **No split**: these are shell CGI reading the register, so it is the registry
stating its own register, the same grounds as MYNIC and SaudiNIC.

**Measured, 2026-08-31, truncated labels excluded**: 12,404 rows over years {1997: 1,656, 1998:
5,551, 1999: 3,074, 2000: 2,123}, 5,439 distinct pairs over 4,360 domains, 1,613 already held.
**Unsplit 3,826 pairs and 3,704.3 EE**; post-split 1,251 pairs and 1,211.2 EE. Mean weight 0.9682,
all `.za`. So the agent's unverified wider-tree figure of 4,462 EE was **1.2x high**, and the
register's verified 2,720.6 sat between the two because it read ten captures of one host.

**The reason to exclude 640 rows, and it is a defect in the artifact rather than in the parse.**
The registry's CGI prints bare labels in **fixed 16-character columns and truncates the name to
fit, in the `href` as well as the anchor text**, so `sahomeimprovement` is served as
`sahomeimprovemen`, and `museum-of-freedom`, `cruisesinternational`, `australianimmigration` and
`thevirtualprinter` are all cut the same way. The label-length histogram shows the damage plainly:
303 labels of 15 characters against a spike of **640 at exactly 16**. Every 16-character label is
therefore a possible fragment, and admitting them would mint well-formed domains that never
existed, which no invariant in `ark check` would catch. All 640 are dropped.

**Note the years before pricing this against the queue.** The captures run 1997-12 to 2000-08 with
**nothing in 2001**, and 1,018 of the 1,251 post-split pairs land at 1998. Measured headroom at
1996-to-1997 is 103,953 pairs against 6,708,320 at 2000-to-2001, so this source is high weight in
the thin years rather than in the year that pays.

---

## Federal Audit Clearinghouse Single Audit filings: CLOSED ON ACCESS, and the primary source is a blanket robots refusal

**The primary source, which is what was asked for and had never been recorded.** The landing page
is `https://www.fac.gov/data/download/historic/`, "Data from 1998-2015 ... Single Audit submissions
collected by the Census FAC from 1998 to 2015 ... provided as-is for historical research and is not
included in our web-based search or API". The per-year files it links are
`https://app.fac.gov/dissemination/public-data/census/csv/census-{1998,1999,2000,2001}.zip`, with a
`.sha1` beside each, and a combined `census-1998-2015.zip` of 413 MB.

**The claim is structurally correct, and the data dictionary confirms it.**
`https://www.fac.gov/data/download/historic-dictionary/` documents **`AUDITEEEMAIL`, "Auditee Email
address, 60 characters max"** and **`AUDITEEDATESIGNED`, "Date of auditee signature, mm/dd/yyyy"**,
plus `CPAEMAIL` and `CPADATESIGNED`, present across every form revision covering our window. So one
item really is one e-mail field on one filing row dated by that row's own signature date.

**But the route is closed, and this is decided before the human-typed question is even reached.**
`https://app.fac.gov/robots.txt` is exactly `User-agent: *` / `Disallow: /`. Every data file is on
that host; only the landing page and the dictionary are on `www.fac.gov`, whose robots.txt is
`User-agent: *` / `Disallow:` and permits everything. `harvester.census.gov`, the Census Bureau host
that ran the FAC until 2023, now 302s to `outage.census.gov/maintenance.html` and serves no data.
**No open mirror exists**: `catalog.data.gov`'s package API answers HTTP 404 for the search, and
archive.org's `advancedsearch.php` returns 46 items for "federal audit clearinghouse" of which the
only FAC-related ones, `GithubArchiveOf_GSA_GSA-TTS_FAC` and `...FAC-Frontend`, are the
application's **source code and not its data**.

**Two further facts worth recording.** The historic dataset **begins at 1998**, so 1996 and 1997 are
unreachable through it whatever happens. And the 2,406.69 EE figure of 2026-08-24 was measured with
a specificity that implies the bytes were genuinely read, including 18,698 e-mail rows dropped for
signature dates outside the window, mostly FY2001 audits signed in 2002. **Nothing under `data/raw`
or `private/` holds those bytes now, and the only route to them breaches a `Disallow: /`**, so that
measurement is neither reproducible nor repeatable by us. It is recorded here, unbanked.

**One route remains and it is a letter, not a fetch.** GSA publishes the dataset for historical
research and `www.fac.gov` invites exactly that use, so a request for a copy or for permission to
retrieve the four in-window ZIPs is the correct next step, and it joins the letters already open on
the Edelman CIPA terms. Do not re-probe `app.fac.gov`, `harvester.census.gov`, data.gov or
archive.org for this corpus.

---

## `fac_single_audit`: BANKED at 1,403.2 EE, on bytes a human downloaded because the host refuses robots

**The links, and the provenance, which is unusual for this project and is the point.** Landing page
`https://www.fac.gov/data/download/historic/`; the four in-window files are
`https://app.fac.gov/dissemination/public-data/census/csv/census-{1998,1999,2000,2001}.zip`
(15 / 16 / 16 / 20 MB) with a `.sha1` beside each. **`app.fac.gov/robots.txt` is `User-agent: *` /
`Disallow: /`**, so no automated client of ours may fetch them, and the route was recorded closed on
2026-08-31. **Ivo downloaded all four by hand the same day**, which robots.txt does not govern
because it governs robots, and **all four SHA1s verify** against GSA's published digests
(`7037c86d…`, `d03838ed…`, `94f7fadf…`, `5de0abcd…`). Staged at `data/raw/fac/`. The archives carry
**no licence or README of their own**, only CSVs, so the terms are the landing page's "provided
as-is for historical research" plus US federal public domain. `www.fac.gov` itself is
`Disallow:` and permits everything, which is how the dictionary was read.

**Why it meets the standard.** One item is one e-mail address field on one Single Audit filing row,
dated by that row's own signature date: `AUDITEEDATESIGNED` "Date of auditee signature" or
`CPADATESIGNED`, both documented in GSA's historic data dictionary and both present in
`ELECAUDITHEADER.csv` for every year in the window (columns 24/25 and 37/38 of 95). The address is
the auditee's or the audit firm's own, so the row asserts the domain was in use on the day a
certifying official signed. Class `dated_directory`, master-eligible. Rule 6 holds: a signature
dates its own year only.

**`AUDITYEAR` is a trap and this is the transferable part.** Every row also carries the audit year
and the two do not agree, because 1998 filings are routinely signed in 1999 and FY2001 audits in
2002. Screening on the signature date drops **18,979 of the 75,311 e-mail fields, 25.2%**, and
dating on `AUDITYEAR` would have imported every one silently. The register's 2026-08-24 pass
reported 18,698 on the same screen, so the two agree to 1.5% and the discipline reproduces on
independently obtained bytes. **When a dated corpus carries two plausible date columns, measure how
far apart they are before choosing.**

**Measured, 2026-08-31, against the live store**: 139,978 filing rows, 75,311 e-mail fields, 55,563
in-window items over 17,208 distinct pairs and 9,952 domains, **13,796 pairs already held (80.2%)**.
**Post-split 2,081 pairs and 1,403.2 EE**, mean weight 0.6743, by year {1997: 1, 1998: 165, 1999:
505, 2000: 559, 2001: 851} and by TLD {com 1,278, org 461, us 228, net 99, edu 9, cc 3}. Unsplit
would be 3,412 pairs and 2,320.5 EE. The register's 2,406.69 has decayed to 1,403.2 in seven days,
almost entirely against this project's own ingests of the same morning, which is the standing
warning that an unbanked source decays as the store grows.

**The population is `.com`, not `.edu`, and the earlier expectation was wrong.** This corpus was
expected to die to the split the way ERIC did, where 184 `.edu` pairs yielded one survivor. It does
not, because auditees and audit firms filed with commercial addresses: of 55,563 in-window items the
TLD mix is `com` 33,819, `net` 9,201, `us` 5,683, `org` 4,362 and `edu` only 1,826 with `gov` 572.
**A "federal dataset" is not the same population as a "federal institutional corpus", and the
address column decides which it is.**

**The split applies and earns its place, with the cost recorded rather than assumed.** A person
typed each address into a form, so novel names take the split. A random sample of the 1,147 novel
names shows why: `campell.edu` for Campbell, `clakamas.or.us` for Clackamas, `staate.oh.us`,
`selfsuffciency.com`, and `kl2.ca.us`, where the letter `l` was typed for the digit `1` in `k12`.
Separately, **18.0% of novel names are a character prepended to a name the store already dates**,
`aarthurandersen.com` for arthurandersen.com, `aattglobal.net` for attglobal.net, `1mc.edu` for
mc.edu, which is an import defect rather than anyone's honest typing. **But the split is not
costless**: the same sample holds `isler-eugene.com`, a real Eugene accountancy firm, and
`sau38.k12.nh.us`, a real New Hampshire School Administrative Unit, neither of which any crawler
reaches. The measured typo upper bound is **69.7%, the highest in the register**, and it is an
UPPER bound: the sample puts the true rate nearer a third. So 1,444 uncorroborated rows park as
`link_target` and the 917.3 EE difference between the split and unsplit readings can be recovered
later on a human ruling, without refetching anything.

**A method note on the sampling, because it produced a wrong reading first.** Inspecting novel names
in alphabetical order made the prepended-character defect look like the whole story, since those
cases cluster at `1`, `9` and `a`. A random sample put it at 18.0% and revealed the ordinary typos
and the real long-tail names underneath. **Sample randomly, never off the head of a sorted list.**

**Loose ends, so nobody re-probes them.** The historic dataset begins at **1998**, so 1996 and 1997
are unreachable through it. `harvester.census.gov`, the Census host that ran the FAC until 2023, now
302s to a maintenance page. No open mirror exists: `catalog.data.gov`'s package API answers 404 and
archive.org holds only the application's source code, `GithubArchiveOf_GSA_GSA-TTS_FAC`. The other
seven CSVs in each ZIP were not used: `ELECAUDITS.csv` is the largest by far (48-62 MB) and is the
per-award detail, carrying no address column.

---

## Integrity audit: the Usenet channel's self-corroboration, measured and bounded at 0.265% of what we ship

A 2026-08-31 research round closed the `uk.*`/`de.*` Usenet hierarchies and raised a wider alarm:
that the corroboration split has gone **circular** on the whole Usenet channel, because a name our
own earlier sweep dated is what corroborates a new Usenet file dating it again, and that "every
Usenet-lineage figure banked since 2026-08-17 should be re-checked". **The alarm is directionally
right and the magnitude is small. Both halves were measured rather than assumed.**

**The mechanism is real.** Anti-spam address munging turns a real address into a fake domain, and
our extractors banked the result. Every one of the nine names the round named is carrying dated
years: `nospambigfoot.com` at 1997, 1999, 2000, 2001, `nospam.ac.uk` at all six years,
`btnospaminternet.com`, `deletethis.com`, `nospamblueyonder.co.uk`. A second and separate defect
sits beside it: **bare public suffixes banked as though they were domains**, `ac.ie`, `com.hu`,
`gov.gb`, `free.uk`, plus `go.nl`, `com.us`, `co.jo`, `gov.ru` and 1,222 more.
`ark check`'s `registered_domain_format` cannot catch either, because both are lexically
well-formed lowercase names, and `to_registrable` rejects `co.uk` and `com` while **accepting**
`ac.ie`, `com.hu` and `gov.gb`, so the PSL screen has holes.

**The magnitude, measured three ways.** Store-wide, munging-token pairs are 2,227 across all
sources, of which ours contribute 1,038 (`usenet_announce` 530, `usenet_address` 493,
`usenet_bare` 15) and **`prior_task` contributes 1,060, more than we do**, so this is not a defect
unique to this project. Suspected bare suffixes carrying dated years are 1,230 distinct names and
3,945 pairs, 1,544.2 EE, 0.855% of the banked increment. **But what matters is what is SHIPPED**,
and in `output/netnew/` the two defects together are **818 pairs and 478.5 EE across 283,091
shipped rows, 0.265% of the claimed increment**: 189 bare-suffix pairs at 88.4 EE and 629 munged
pairs at 390.1 EE. So the round's "27.2% garbage" figure was true of its own small probe
population and does not transfer to the store.

**Not fixed here, and deliberately.** Removing 818 pairs means deleting `domain_year` rows and
their evidence, and the honest fix is a new invariant plus a PSL refresh, which is a change to the
gate rather than a data edit. Recorded as a **pre-submission cleanup item**, since 478 EE is
immaterial to the 5% trigger but a reviewer validating our files would reasonably flag `gov.gb`.

**The transferable rule.** **A corroboration split is only as independent as its partner source.**
When the partner is a class this project has already swept at scale, the split validates nothing
and the failure is invisible in the headline: the same bytes and the same parse priced 22,838 EE
against the current baseline and 252 EE against `merged260810`, a 91x spread, and the check that
revealed it was a grep over `feedback/*/merged*` and over our own journals, both in minutes.
**Price a Usenet-lineage source against a reviewer cut from before our own collector last ran in
that channel.**

## `urlmerchant_inventory`: BANKED, a broker's whole for-sale inventory printed as static A-Z pages

`https://web.archive.org/web/20010901000000id_/http://www.urlmerchant.com:80/domains/domain_a.html`
(the letter series `domain_<a-z|0-9>[_<n>].html`, ~40 KB and 100 names a page; counts page
`http://www.urlmerchant.com/statistics.html` at capture `20011231002753` states "Total Domain Names
Listed: 156,122"). **What dates one page is its own generator stamp,
`<META NAME="UPDATED" CONTENT="Tuesday, Jul 17 2001 1:19:41 AM">`, written by the program that
printed the table out of URLMerchant's listings database, with the Wayback capture fixing when the
archive saw it; the stamp is read per page and never inferred from the capture, so the 4 pages
stamped 2002 are dropped whole.** Names are owner-submitted, so the corroboration split applies:
**1,591.9 net-new post-split EE over 2,557 pairs, all 2001**, from 244 pages, 23,875 distinct
domains and 14.2% held, the 20,492 novel names parking as candidates. **Why a 14% held-fraction
paid: 75.6% of the held names were missing 2001**, because a broker's inventory is tail names the
store only ever saw once. Screen on `held x P(missing the artifact's year)`, not on held alone.

## `jeb_bush_gubernatorial_email`: BANKED at 3,546.1 EE, and the URL this row exists to record

`https://archive.org/download/JebBushEmails/JebBushEmails-Text.7z`, 411,928,998 bytes, sha256
`821e796f7d9dcd0a5bcb08eaf70760d50f5296481f2175ac4ed45b3301f41f75`, 626 files, **505,927 messages
dated inside the window** out of 2.4M. **What dates one item is the message block's own unindented
`Sent:` line, `Sent:\tMonday, December 4, 2000 12:38 AM`, written by the sending mail client into
the export, the same basis and the same evidence type as the banked `enron_email`.** The
corroboration split applies, a person having typed most of the addresses: **3,546.1 net-new
post-split EE over 5,692 pairs**, 90.8% of 57,934 distinct domains already held, 83.2% of the pairs
adjacent-year corroborated, 2001 4,505 of them. Hosts are anchored on an `@`, a scheme or a `www.`
label, because the wide pattern turns `Candace Rice.To tell the truth` into `rice.to` and cost
200.8 EE of fabricated high-weight pairs. **This is the row the 2026-08-24 measurement at line 703
should have carried and did not**: seven days unbanked with no URL recorded cost 264 EE to the
store's own growth, and the hypothesis that inbound public mail beats outbound official mail is
refuted with the sign reversed, `From:` 1,235.4 EE against `To:`/`Cc:` 1,410.3 EE, because the
public writes in from AOL rather than from a domain it owns.

## `internic_zone_hostnames`: HELD OUT at hostname grain 2026-09-02 (had exported as 11,860.7 EE), the column the zone parser threw away

**Status.** An NS target observes a nameserver, not a site: 20,835 hostname rows removed under the
purpose rule, parents still dated. Entry kept as written at admission.

`https://web.archive.org/web/19970420113748id_/http://nic.mil/oroot.html/org.zone.gz` (1,317,986 B),
`.../19970420112952id_/http://nic.mil/oroot.html/edu.zone.gz` (111,076 B) and
`.../19970420113002id_/http://nic.mil/oroot.html/gov.zone.gz` (15,972 B), plus the `mil`, `root` and
`arpa` files from the same crawl, all on disk as `data/raw/internic_zones/*.zone.gz` since 2026-08-18.
**What dates one item is the zone's own SOA serial on line 2 of the payload, `1997041800`, the same
stamp and the same `artifact_listing` class Ivo decided master for these exact bytes on 2026-08-24.**
A registry zone file is TWO hostname corpora and `parse_internic_zone` reads only the left one: the
owner of an NS record is the delegation, the right-hand side is the nameserver that serves it. At
registrable grain the right-hand side is worthless, measured and closed at 63 pairs on 2026-08-29
(line 881), because `ns1.psi.net` collapses to an operator every crawl already holds. At the hostname
grain the reviewer accepted on 2026-09-01 the same 21,498 hosts are 90% absent: **19,211 (hostname,
1997) records and 11,860.7 EE net-new against the live store AND the reviewer's own 1997 file**, no
split, com 4,713.6 EE, net 2,245.5, edu 1,979.4, org 1,502.6. Admitted by the loop under the
standing rule and ingested as `internic_zone_hostnames` (`ark ingest-zone-hostnames`). **The lens this
opens: nameservers, mail exchangers and FTP mirrors are exactly the hosts a web crawler never fetches,
so any DNS-side or mail-side artifact over held registrables is the hostname unit's natural prey even
where its registrables are saturated.** Two lanes parked in `approved-sources-list.md` with figures:
the 1999 tomocha zones at **4,678.2 EE** (terms, condition 3) and the fleet's Usenet server-header
census at a fleet-measured 2,368 EE on one probe (conditions 1 and 4, and the reviewer's own 0901
closure of dated Usenet copies).

## `squidguard_2001_hostnames` and `chastity_list_hostnames`: BANKED at 3,441.8 EE, the blocklists read one level down

`http://archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz` (1,852,659 B,
member `samples/dest/blacklists.tar.gz`) and
`https://archive.debian.org/debian/pool/main/c/chastity-list/chastity-list_0.5.orig.tar.gz`
(720,609 B), both on disk since August. **What dates one item is unchanged from the banked registrable
lanes**: squidGuard's own compile header, `# This list was compiled in 0:00:20 on 2001.12.18 15:04:29.`
(`artifact_listing`, master 2026-08-26, no split, the robot tested the links), and chastity's tar member
header `Dec 14 2001` on every file (`dated_directory`, master 2026-08-31, hand-kept, so the split
applies: a host counts only beneath a parent that already carries a year). A blocklist names the
offending HOST, and `parse_squidguard_blacklist` collapsed `members.tripod.com/x` to `tripod.com`, which
is why the fleet's `banked_lists_hostname_grain` probe (line 816, first priced at 836 EE on the
`domains` lane alone) found a residue. Density is low and predictable: a `domains` file is ~50% IPv4
addresses, ~45% bare registrables, 4-7% sub-hosts. Re-priced on the live store 2026-09-02 from the
bytes, `domains`, `urls` and dated diff lanes together, parent held at 2001 and hostname absent from
both `hostname_year` and the reviewer's own 2001 file: squidGuard 4,323 hosts, 2,093 net-new, 1,059.8
EE; chastity 10,929 hosts, 46 parked by the split, 5,615 net-new, 2,381.9 EE. **Banked 7,708 (hostname,
2001) records, 3,441.8 EE**, by TLD on the pre-ingest union com 1,997.4 EE, net 723.9, org 159.1, fr 154.2; largest parents `free.fr` 1,311,
`fsn.net` 677, `multimania.com` 289, `cjb.net` 233. Admitted by the loop under the standing rule
(`ark ingest-blocklist-hostnames`; the chastity lane reads the TARBALL, because the stamp is the tar
header and extraction loses it). The reusable point: **every banked list-shaped source that named
hosts and was collapsed to registrables is a hostname-grain reopen at zero requests**; junkfilter,
SpamEater and the hosts file are mail-sender lists and name registrables, so they are not.

## `early_web_cdx_hostnames`: BANKED at 631,148.1 EE, and 99.9997% of it is the `www.` seam

`https://archive.org/details/early-web_cdx-lang-cdxa`, 224 `*.cdx.gz` (184,858,264 B), on disk as
`data/raw/early_web/` since July and banked then at registrable grain (line 173). **What dates one
item is unchanged: the row's own 14-digit capture timestamp, field 2 of the classic CDX line,
`uk,co,bucksnet,homepages)/ 19981202041041 http://homepages.bucksnet.co.uk:80/ text/html 200`,
class `cdx_timestamp`, quoted in every evidence value.** `scripts/sources/early_web/early_web_hostgrain.py`
re-emits each part as a `{url, timestamp}` journal (HTTP 200 rows, as the registrable ingest read
them) and `ark ingest-hostnames data/raw/early_web_hostgrain/` fills `hostname_year`. Re-priced on
the live store after the ingest, against both `hostname_year` and the reviewer's own `merged260901`
files: 1,763,562 rows written, 599,946 verbatim in his file for that year and excluded, **1,163,616
(hostname, year) records and 631,148.1 EE net-new, 1996-1999 only** (1996 47,933.4, 1997 38,094.5,
1998 256,111.1, 1999 289,009.0; com 424,850.2, uk 49,027.7, org 37,508.9, net 28,872.9). The fleet's
snapshot census (`early_web_cdx_hostname_grain`) reproduces to 0.01%. **The disclosure that decides
what this is worth: 1,163,612 of the 1,163,616 records are `www.<held registrable>`.** His files
carry Early Web's non-`www.` hosts by name (`ei.haygroup.com`, `frontpage.helicon.net` sit verbatim
in his 1999 file, 1,489,119 non-`www.` multi-label names in that one file against 385 `www.` ones),
so the baseline holds 99.9994% of the non-`www.` hostnames and the corpus is IA-derived (law 1)
everywhere except the `www.` seam. Under the unit already shipped (the NYPW re-read was 93.6% `www.`
forms) the figure stands; if his calculator strips `www.` it is 0, and the same answer reprices the
4.2M NYPW `www.` records already delivered. Both readings go in the report, and the question goes to
him with the delivery. Admitted by the loop under the standing rule. **The transferable point: any
classic or NYPW-shaped CDX corpus on disk is a hostname-grain reopen at zero requests, and the
first thing to measure is the `www.` share of what survives the baseline.**

## `isc_survey_hostnames`: HELD OUT at hostname grain 2026-09-02 (had exported as 9,167,369.2 EE), the column the registrable unit threw away

**Status.** Ingested and then removed from `hostname_year` under the purpose rule below: a reverse-DNS
walk observes a machine answering, not a site, and 65% of these names are dialup or workstation
shapes for which no archived page can exist. The 18,147,169 rows still date their parents; the lane
is one line (`WEB_FACING_HOST_SOURCES`) to restore if the reviewer rules DNS listings count. The
entry below is kept as written at admission.

`http://nw.com/zone/9607.hosts/uk.gz` and its siblings, through the 1996-1997 Wayback captures of
`nw.com` (for example
<http://web.archive.org/web/19970529075101id_/http://nw.com.:80/zone/9607.hosts/uk.gz>, 4,105,718 B,
byte-identical to `wb_nw_9607_uk.gz` already on disk): the per-TLD host files of the Network Wizards
/ ISC Internet Domain Survey, the exact bytes `isc_survey` was banked on in July, 579 files across
the 9607, 9701 and 9707 editions. Every line is `IP hostname`, the survey's record of a host
answering the reverse-DNS walk that month, and the registrable ingest kept only the parent, which is
why the family read as complete and fully held (line 1144, 14,956.4 EE, 0 parents missing).
**What dates one item is the survey's own `YYMM` edition code, carried in the artifact's path
(`/zone/9607.hosts/uk.gz` = July 1996), class `artifact_listing`**, the same stamp and the same
decision the registrable lane stands on, with the Wayback capture fixing that the file existed then;
the reviewer confirmed in writing on 2026-07-24 that a dated DNS survey enters the annual files on
exactly this stamp. Ingested by `ark ingest-isc-hostnames`, one ledger row per file. Recomputed from
the shipped manifest: **18,117,395 records and 9,167,369.2 EE**, 1996 7,581,259 / 4,055,578.8 and
1997 10,536,136 / 5,111,790.5; largest TLDs `au` 1,361,609, `mil` 1,278,383, `ca` 1,153,457, `us`
1,003,058, `gov` 840,040, `org` 883,273, `uk` 604,234, `net` 1,249,300. **The disclosure that decides
what it is worth: 65% of the records have a dialup or numbered-workstation shape**
(`pc50.btbcs.bt.co.uk`, `dynws2.mdx.ac.uk`, 62,374 `x.demon.co.uk` nodenames in one file), the
figure the report quotes, measured over the shipped files by `DIALUP_SHAPE` in
`scripts/round/fill_report.py`; a cruder first-label test gives 67.1%, so read it as about
two thirds either way. They are real hosts the walk resolved, they satisfy
the reviewer's validity rule and they carry the edition's stamp, and he discards at merge what he
does not want, which is his stated procedure; the share is quoted in the report and in the report's
limitations so the cut is one filter on the manifest. Admitted by the loop under the standing rule.
**The transferable point, and it is the same one the zone-NS and blocklist reopens made: when the
counting unit changes, the first place to look is a column of an artifact already banked, not a new
artifact.** This one had been closed twice at registrable grain.

## `usfedgov_extract_hostnames`: BANKED at 39,340.0 EE over six merged indexes, 1996-2001

`https://archive.org/download/USFEDGOV-EXTRACT-2001/USFEDGOV-EXTRACT-2001.cdx.gz`, 1,364,737,799 B,
asserted byte-exact against `archive.org/metadata/USFEDGOV-EXTRACT-2001` before anything was read
(collections earlygovweb / webdataservices / web, `access-restricted` unset, `archive.org/robots.txt`
read whole, only `/control/` and `/report/` disallowed). A ZipNum merged index: concatenated gzip
members under one `CDX N b a m s k r M S V g` header, 48,110,426 rows, every timestamp 2001, 33,631
distinct hosts. **What dates one item is the capture timestamp on the row, `20011128173757`-form,
written by the crawler at fetch time, class `cdx_timestamp`**, quoted in every evidence value with
the Wayback replay of that capture as the URL. `scripts/sources/usfedgov/usfedgov_hostgrain.py`
keeps one capture per (host, year), the earliest 200 or else the earliest of any status (a 4xx is
still a dated answer from that host), and writes the journal `ark ingest-hostnames` reads. Re-priced
on the live store after the ingest, against `hostname_year` and the reviewer's 2001 file: 31,218
proper hostnames written, 8,801 verbatim in his file and excluded, **22,417 (hostname, 2001) records
and 21,925.9 EE net-new**, gov 21,620.9; largest parents `lanl.gov` 10,110, `nist.gov` 4,126,
`nasa.gov` 3,267, many of them workstation names captured as embed or link targets, which pass his
validity rule and carry their own stamp, and which he discards at merge if he wants. The 176 parents
not held at 2001 earn their year from the same rows (152.5 EE), which is the whole registrable-grain
yield and confirms the two saturation closures at that grain (lines 1065, 1174). The five sibling indexes for 1996-2000 (27,817,540 /
253,426,221 / 137,976,602 / 394,804,120 / 1,076,439,217 B, same path, none access-restricted, each
byte-checked the same way) were fetched and read whole on 2026-09-02 and ingested through the same
converter: 1996 104 records / 101.8 EE, 1997 293 / 280.9, 1998 2,738 / 2,681.2, 1999 6,712 / 6,577.7,
2000 7,996 / 7,772.5, so the family stands at **40,260 records and 39,340.0 EE** across the six years,
recomputed from the shipped manifest. **Method worth keeping: for any `webdataservices` or
`earlygovweb` item, pull the one merged `<item>.cdx.gz` and census it offline; the 1.7 MB
`.cdx.idx` alone lists block-leading SURT keys, a free lower bound on distinct hosts before any
large fetch.** Admitted by the loop under the standing rule.

## `ripe_nserver_hostnames`: HELD OUT at hostname grain 2026-09-02 (had exported as 11,780.1 EE), the attribute both RIPE parsers skip

**Status.** An `nserver:` attribute observes a nameserver, not a site: 51,281 hostname rows removed
under the purpose rule, parents still dated. Entry kept as written at admission.

`https://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz` (71,919,736 B, `Last-Modified: Tue, 03 Aug
1999 21:27:00 GMT`) and `https://ftp.funet.fi/pub/netinfo/RIPE/dbase/split/ripe.db.domain.gz`
(5,452,546 B), both on disk and both banked for their delegated names (`ripe_dbase_1999`,
`ripe_dbase_changed`, `ripe_dbase_split_2004`). **What dates one item is the same stamp each lane
was decided on: the dump's own generation line `# 990804 00:07:01` for the snapshot (1999 only, rule
6), and the object's latest `changed:` line, `changed: mx@lucky.net 20010716`, for the split
edition, read as the registry stating that the object's nserver set stood as written in that
year. Class `artifact_listing`, no split: a machine wrote it, the same instrument as the NS
right-hand side of a zone file.** `*ns:` at registrable grain was closed on yield (line 916, 70.4
EE) and the fleet's reprice reproduces that at 254 EE: 98% of the nameserver operators are held.
That was the kill under the old unit and is the enabling condition under the new one.
`ark ingest-ripe-nserver-hostnames` reads only the nameserver value, the object key and the trailing
date of `changed:`, under the RIPE NCC's written permission of 2026-08-26, and
`tests/test_ripe_nserver_hostnames.py` fails on a personal-data leak exactly as the registrable
lanes' tests do; reverse-zone objects are kept because their nameservers are hosts the registry
stated on the same day. Re-priced on the live store after the ingest, against `hostname_year` and
the reviewer's files: snapshot arm 40,065 rows, 1,133 excluded, **38,932 (hostname, 1999) records,
8,552.5 EE**; split arm 11,216 rows over 1996-2001, 307 excluded, **10,909 records, 3,227.6 EE**, of
which 2000 and 2001 carry 2,573.6. Together **49,841 records, 11,780.1 EE**, net 2,647.8, com
2,520.8, de 1,460.2, uk 686.9, it 675.5; largest parents `cnr.it` 127, `pair.com` 114, `uu.net` 64.
The 1,232 parents not yet held earn their year from the same rows (442.9 EE), the fleet's
registrable-unit figure. Admitted by the loop under the standing rule. **The reusable rule: when a
file already banked on one attribute carries a second machine-written attribute naming
infrastructure, reprice that attribute under the hostname unit before hunting a new file.**

## Detail

Each entry above whose row could not carry all of it, in the words it was written in.
The row is a projection of this, never the only copy.

### inaddr-reverse-tree-ns-hostnames-1997-1999

**inaddr_reverse_tree_ns_hostnames_1997_1999 (2026-09-02, fleet 20260902T0232Z)**

**FIND at 4655.5 EE, against the ark-data sync.** What dates one item: ARIN arm: BIND 8's
transfer comment at the head of each zone member, `;. Artifact:
<https://ftp.apnic.net/apnic/arin/arin.zones.tar.gz>. both arms read whole, no sampling.

### isc-survey-host-files-hostname-grain

**isc_survey_host_files_hostname_grain (2026-09-02, fleet 20260902T0232Z)**

**FIND at 818952 EE, against the ark-data sync.** What dates one item: the survey `YYMM` in the
artifact path (`9607.hosts/` = July 1996 PTR walk), class `artifact_listing`, already master for
`isc_survey`;. Artifact:
<http://web.archive.org/web/19970529075101id_/http://nw.com.:80/zone/9607.hosts/uk.gz>.
`9607.hosts/uk.gz` (4,105,718 B via Wayback replay, gzip -t OK), 652,649 lines, 647,589 distinct
hosts, 615,247 valid non-registrable hostnames beneath a `.uk` registrable.

### usenet-pasted-machine-blocks-hostname-grain

**usenet_pasted_machine_blocks_hostname_grain (2026-09-02, fleet 20260902T0232Z)**

**FIND at 6200 EE, against the ark-data sync.** What dates one item: the post's own `Date:`
header (`Date: 1999/12/30` in the old Google form, RFC 822 in the rest), the same stamp the
approved Usenet body classes already use;. Artifact:
<https://archive.org/download/usenet-comp/comp.protocols.dns.bind.mbox.zip>. two whole groups
from `archive.org/download/usenet-comp/`, not a sample.

### usenet-uk-and-edu-header-fqdns

**usenet_uk_and_edu_header_fqdns (2026-09-02, fleet 20260902T0232Z)**

**FIND at 2537 EE, against the ark-data sync.** What dates one item: the message's own `Date:`
header (fallback: the X-Trace epoch the injecting server wrote), and the hostname is written by
the NNTP server, not the poster: `X-Tr. Artifact:
<https://archive.org/download/usenet-uk/uk.comp.os.win95.mbox.zip>. `uk.comp.os.win95.mbox.zip`
(27,709,004 B, 60,588 messages, ~42,000 in window 1996-2001) parsed headers-only in-stream.

### usfedgov-extract-1996-2000-hostname-grain

**usfedgov_extract_1996_2000_hostname_grain (2026-09-02, fleet 20260902T0232Z)**

**FIND at 18702.8 EE, against the ark-data sync.** What dates one item: the 14-digit CDX capture
timestamp on the row itself (`20000508164730`-form), written by the crawler at fetch time;.
Artifact: <https://archive.org/download/USFEDGOV-EXTRACT-<year>/USFEDGOV-EXTRACT-<year>.cdx.gz>.
no probe needed after the first item: every one of the five merged indexes was fetched whole
(1,890,463,700 B, each byte-exact against `archive.org/metadata/USFEDGOV-EXTRACT-<year>` `size`)
and read whole, so these are measurements, not pro

### dartmouth-captures-hostname-grain

**dartmouth_captures_hostname_grain (2026-09-02, fleet 20260902T0034Z)**

**FIND at 0 EE, against the ark-data sync.** What dates one item: field 2 of the CDX row, the
14-digit capture timestamp written by the archive (`cdx_timestamp`), identical to what dates the
banked `dartmouth_nber_captures` ro. Artifact:
<https://archive.org/download/DARTMOUTH-NBER-RESEARCH-2017-metadata/domain-year-captures.txt>.
ARM 1 (`domain-year-captures.txt`): two disjoint Range slices, bytes 0-4194303 and
120000000-122097151, 277,011 rows.

### early-web-cdx-hostname-grain

**early_web_cdx_hostname_grain (2026-09-02, fleet 20260902T0034Z)**

**FIND at 631215.8 EE, against the ark-data sync.** What dates one item: the row's own 14-digit
capture timestamp, field 2 of the classic CDX line, class `cdx_timestamp`, quoted beside the
hostname exactly as the NYPW reprice did (e.. Artifact:
<https://archive.org/details/early-web_cdx-lang-cdxa>. no probe needed, the whole artifact is
177 MB and was read whole (224 files, 4,383,611 rows, 4,210,462 in-window HTTP-200 captures,
years 1996-1999 only, none dated 2000 or 2001).

### ripe1999-nserver-hostnames

**ripe1999_nserver_hostnames (2026-09-02, fleet 20260902T0034Z)**

**FIND at 11400 EE, against the ark-data sync.** What dates one item: the dump's own
machine-written cut stamp on line 2 of the payload, `# 990804 00:07:01`, the same stamp
`ripe_dbase_1999` was approved on.. Artifact:
<https://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz,>. no probe needed: the artifact is one
71,919,736 B file, refetched in one request and censused whole offline.

### usfedgov-extract-hostname-grain

**usfedgov_extract_hostname_grain (2026-09-02, fleet 20260902T0034Z)**

**FIND at 21713 EE, against the ark-data sync.** What dates one item: the CDX capture timestamp
on the row itself, `20011128173757`-form, written by the crawler at fetch time;. Artifact:
<https://archive.org/download/USFEDGOV-EXTRACT-2001/USFEDGOV-EXTRACT-2001.cdx.gz,>. whole 2001
merged ZipNum index read, not a sample: 48,110,425 CDX rows, every timestamp 2001, 33,631
distinct hostnames, 33,492 valid by the fixed hostname regex (IP literals dropped).

### banked-lists-hostname-grain

**banked_lists_hostname_grain (2026-09-02, fleet 20260901T2358Z)**

**FIND at 2967.5 EE, against the ark-data sync.** What dates one item: unchanged from the banked
registrable ingests: squidGuard's machine-written compile stamp `# This list was compiled in
.... Artifact:
<http://archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz>. The
whole population, not a sample, because both artifacts are under 2 MB.

### usenet-header-fqdn-census

**usenet_header_fqdn_census (2026-09-02, fleet 20260901T2358Z)**

**FIND at 6877 EE, against the ark-data sync.** What dates one item: the message's own `Date:`
header (and for X-Trace rows the injecting server's own epoch stamp, e.g.. Artifact:
<https://archive.org/download/usenet-demon/demon.ip.support.pc.mbox.zip>.
`demon.ip.support.pc.mbox.zip` (15,308,303 B, 17,469 messages) then
`demon.ip.support.newuser.mbox.zip` (39,971,141 B, 54,703 messages), both from
`https://archive.org/download/usenet-demon/`, parsed in-stream, headers only.

### hostname-benchmark-headroom

**hostname_benchmark_headroom (2026-09-02, fleet 20260901T2246Z)**

**FIND at 0 EE, against the ark-data sync.** What dates one item: nothing, this is a coverage
measurement over held files. not a source.

### usenet-header-fqdn-census-2

**usenet_header_fqdn_census (2026-09-02, fleet 20260901T2246Z)**

**FIND at 2368 EE, against the ark-data sync.** What dates one item: the message's own `Date:`
header fixes the year;. Artifact: <https://archive.org/download/usenet-demon/<group>.mbox.zip>.
four archive.org `usenet-*` mbox zips, 44.4 MB compressed, 76,889 messages, parsed in-stream,
nothing extracted.

### zone-ns-glue-hostnames

**zone_ns_glue_hostnames (2026-09-02, fleet 20260901T2246Z)**

**FIND at 11862.5 EE, against the ark-data sync.** What dates one item: the zone's own SOA
serial `1997041800` on line 2 of the payload (all three zones), fixed in time by IA captures
19970420113748 (org), 19970420112952 (edu), 1997. Artifact:
<https://web.archive.org/web/19970420113748id_/http://nic.mil/oroot.html/org.zone.gz>. the whole
1997 lane, not a sample: org+edu+gov zones (1,444,034 B gz, the banked bytes refetched at their
recorded IA URLs).

### cdx-nonzero-status-rows

**cdx_nonzero_status_rows (2026-09-01, fleet 20260901T1557Z)**

**FIND at 33.35 EE, against the ark-data sync.** What dates one item: the CDX capture timestamp
of a non-200 response.. Artifact:
<https://archive.org/download/nypw_timemaps/1998/nypw_timemaps1998_deeplinks_part01o.tar.gz>.
TWO already-ingested `nypw_timemaps` parts, chosen so that every HTTP-200 row is guaranteed
already banked and any net-new pair MUST come from a dropped non-200 row.

### gap-queue-high-weight-tld-tail

**gap_queue_high_weight_tld_tail (2026-09-01, fleet 20260901T1400Z)**

**FIND at 0 EE, against the ark-data sync.** What dates one item: nothing.. no probe and no
fetch, because the whole hypothesis is one query over the store, which

### parked-approval-queue-reprice

**parked_approval_queue_reprice (2026-09-01, fleet 20260901T1400Z)**

**FIND at 12024 EE, against the ark-data sync.** What dates one item: nothing new is dated
here.. the kill screen was five parked sources.

### law-1-conditional-test-is-ia-derived-net-new-only-on-domains-we-ve-nev

**Law 1 conditional test: is IA-derived net-new only on domains we've never queried?
(2026-09-01)**

**FIND, 0 EE net-new banked, redirects an existing collector.** Measured against
`data/raw/cdx/*.jsonl.gz` (1,137 journals) and NYPW's 1,306,611 pairs: what dates one item is
the TimeMap's `cdx_timestamp`. Law 1 splits into discovery (holds absolutely: 14 of 652,853
domains, 0.002%) and completeness (false by two orders of magnitude: the real driver is capture
year, not prior query history). | **CORRECTION, 2026-09-01 01:55, from the ingest ledger.** This
run's `next` section told the operator to redirect the NYPW download queue to the 2001 folder,
on a claim that `nypw_timemaps2001_deeplinks_part00o` paid 147,449 net-new pairs and 66,312 EE
against 1,398 pairs for twelve 1999 and 2000 partitions, a 1,265x per-record ratio. **That is
wrong by roughly four orders of magnitude and the redirect was not made.** `ark ingest` reports
the 2001 part at **`'year_rows': 6`**, six, against 94,695 for `2000_rootURLs_part00r`, 42,757
for `part04r` and about 234,000 across the thirteen 1999 and 2000 partitions. Two other runs the
same night agree with the ledger and not with this one: the re-opener measured that same file at
2.6 EE with 108,863 of 108,870 pairs already held, and the saturation fit put the 2001 folder at
0.1 EE/MB against rootURLs 376.4. The conditional itself, 0.1198 net-new on never-asked domains
against 0.0320 on asked ones, is not disputed here and is worth keeping; only the partition
recommendation is withdrawn. **The general lesson is the one CLAUDE.md already states: verify
every number, including a subagent's. What made this one catchable is that the ingest ledger
records `year_rows` per file, so any claim about what a partition paid can be checked against
what it actually wrote, for free.**

### nerd-world-what-s-new-register-tree-https-web-archive-org-web-20011030

**Nerd World "What's New" register tree,
`https://web.archive.org/web/20011030063818id_/http://www.nerdworld.com/whatsnew.html`
(2026-09-01)**

**FIND, 235.0 EE, parked pending (fails standing-rule condition 2).** What dates one item: the
Wayback capture stamp on each category page (`dated_directory`), machine-written but not printed
inside the artifact itself; 399 of 2,059 distinct domains held-and-missing-2001.

### urlmerchant-s-for-sale-inventory-continued-past-its-first-244-pages

**URLMerchant's for-sale inventory, continued past its first 244 pages (2026-08-31)**

**FIND, in progress: 606.3 EE measured over 974 net-new post-split pairs from 95 pages fetched
at 2001 captures, projecting to 9,254 EE across the full ~1,562-page namespace; still
fetching.** Same artifact and method as the banked `urlmerchant_inventory` row (1,591.9 EE over
244 pages): distinct-domain sampling gives 13.6% held, 75.6% of held missing 2001, mean weight
0.6225. What dates one item is unchanged, the page's own `<META NAME="UPDATED">` generator
stamp. The 1999/2000 captures of the same namespace are unmeasured and would add a second and
third year to the same held names at no new discovery cost.

### the-rdap-404-verdict-as-a-liveness-prior-on-the-cdx-gap-queue-does-a-n

**The RDAP 404 verdict as a LIVENESS PRIOR on the CDX gap queue: does a name that is
unregistered today answer a 2001 capture query less often than one that is still registered
(2026-08-31)**

**FIND, and the mechanism is confirmed at z = 53.6 while the economics miss the hypothesis' own
900 EE/hour floor by 6x to 9x. Measured +0.0805 EE per `.com` query, +17.56%, or +97 to +161 EE
per collector-hour. ZERO requests: no host contacted, no robots applies.** **Not a source and
must never be read as one.** An RDAP 404 in 2026 says the name is unregistered today and
evidences no year; it changes WHICH name the CDX engine asks about, and the pair that results is
still `cdx_timestamp`, exactly as `link_target` is already used as a ranking signal. No new
class, no approval needed. **Method, and it is the result worth keeping: a hypothesis whose kill
screen needs live requests should first be checked for whether the experiment has already been
run and journalled.** The designed A/B was 1,000 live queries; the retrospective join of
`data/raw/cdx/*.jsonl.gz` (1,112 files, 2,952,695 rows of `{domain, status, years}`) against
`data/raw/rdap*/**/*.jsonl.gz` (416 files, 6.5 GB, 33,778,743 rows of `{domain, status}`) gave
278,678 paired observations in 75 s. **Our own journals are a paired observational dataset**:
any collector writing `{key, status}` and any other writing `{key, outcome}` join into a free
experiment on whichever ordering is in question, and nothing is fetched, so no rate change can
confound it, which is the trap that produced the earlier wrong law about ranking inside the
Verisign clamp. **Measurement**, distinct domains not `domain_year` rows, restricted to walked
names held at 2000 in the gap-queue families: RDAP-200 n = 70,982 P(walk returned 2001) =
**0.8529**, RDAP-404 n = 6,731 **0.5191**, difference 0.3338, se 0.00623, lift 1.643x. Premise
verified first: 18,593,773 rows at 200 and 15,029,917 at 404 against the 18,587,509 / 15,025,140
claimed, correct to 0.03%. **Not composition**: the live arm wins in every TLD stratum with both
arms above 200 (com 0.8434/0.5821, org 0.7917/0.6216, ca 0.7002/0.5177, net 0.7870/0.6937, co.uk
0.3700/0.3149), no reversal, so no Simpson's paradox. **Not an existing ranker in disguise**:
within `.com` held at 2000, `cdx_gtail` 0.8288/0.4284, `cdx_vedge` 0.8169/0.3253, `cdx_gap`
0.9235/0.7728. **The honest boundary**: `cdx_linkhint` is flat at 0.7150/0.7196, because a
link-hint queue has already selected for survival, so do not apply it there. **The counterweight
the hypothesis did not anticipate, and it is the transferable law: for any ranking signal
measure BOTH the hit-rate lift AND the saturation of the arm it favours, because they point
opposite ways.** The dead names are the residue: P(store lacks 2001 | held 2000) is 0.5948 for
live `.com` and 0.8027 for dead. Quoting the hit rate alone overstated the value 3.7x. Priced
against the queue as it stands (live share 0.6183), mixed order pays 0.4586 EE/query and
live-first 0.5391. **Prove the ranker is not already sorted before pricing a reordering**: live
fraction by position quintile is noisy and non-monotone in all three live queue files
(`gap_ranked_20260824` 0.853/0.878/0.911/0.965/0.845, `queue_edge_local`
0.618/0.619/0.607/0.549/0.758, `queue_unasked_ranked` 0.133/0.192/0.195/0.158/0.129), so the
gain is real and not already banked. **It is free where the money is**: 3,425,055 of 3,429,775
`.com` gap names already carry an RDAP verdict, 99.86%, so the `.com` reordering costs no
Verisign quota; the uncovered 40.4% is almost entirely `.de` (980,570 gap names, 923 verdicts)
and should not be chased. Rate taken from journal timestamps rather than assumed: ~2,000 q/h
across the two collectors. **Operational**: the store was locked by a live writer throughout and
`data/exports/*.txt` reproduced the held sets to 0.007% (6,562,432 vs 6,562,859
held-at-2000-missing-2001), so reporting work need not wait 900 s on the lock. **Apply as a
tiebreaker sort key, never a filter** (dead names still pay 0.328 EE), and not on
`cdx_linkhint`. **What this run could not settle**: every walked journal is already ingested, so
"would have been net-new at query time" needs a live interleaved run; the direction and the
ratio are settled without it.

### a-pre-1999-ripe-database-split-an-edition-of-ripe-db-dated-1996-1997-o

**A pre-1999 RIPE database split, an edition of `ripe.db` dated 1996, 1997 or 1998
(2026-08-31)**

**The hypothesis' artifact does not exist on any reachable host, and a 1996 or 1997 edition
would have been worth 123 and 502 EE anyway, priced free off the 1999 file already on disk. The
FIND is a file the hypothesis did not name:
`https://ftp.funet.fi/pub/netinfo/RIPE/dbase/split/ripe.db.domain.gz`, 5,452,546 B,
`Last-Modified: Tue, 09 Nov 2004 23:31:00 GMT`.** What dates one item is the object's own
`changed:` transaction line, `changed:      ovema@a.sol.no 19971128` under `domain:     
hasselblad.gm`, the database's record of an update applied to that object. **Banked 913.84 EE
over 1,510 pairs** as `ripe_dbase_split_2004`, 1998 4 / 1999 253 / 2000 792 / 2001 461, admitted
under the standing rule; see `docs/approved-sources-list.md`. `docs/sources.md` line 597 is
corrected in place: FUNET's `split/` is a 2004 edition, not 15 same-1999-edition subsets, and
the claim that the 2000-and-2001 `changed:` route does not exist was wrong. **Do not re-test the
existence hunt**: `ftp.ripe.net/ripe/dbase/` is the current edition only, FUNET `archive/` is
one 1998 incident log (`981027-incident.New.gz`, 6,130 transaction lines, 6,125 `[person]`, **0
`[domain]`**) plus nineteen server-source tarballs, uni-erlangen is a live 2026 mirror,
`ftp.icm.edu.pl` has no RIPE tree, and archive.org `advancedsearch.php` returns numFound 0 for
`ripe.db`, `ripe.db.gz` and `ripe dbase` against a same-session control `ripe.net` = 19.
**Method: price an earlier snapshot of a database you already hold, for free, off the snapshot
you hold.** The `changed:` history inside one dated dump says which years each object was alive
and which are already banked, so the whole time axis prices before a request; here it gives the
general law that **going BACKWARDS from a churned registry dump is worth almost nothing, because
84% of objects alive in year Y already carry a `changed:` line in Y, and going FORWARDS is where
the value is**. Also: **a mirror's `split/` can be a different edition from the same mirror's
whole-database file**, five years apart in one directory, so read mtimes per file and never
trust a previous sweep's one-line summary of a directory you can list in one request. And **a
ccTLD register can sit inside an RIR database belonging to another continent**: `.gm` (Gambia,
weight 0.9969) was run out of Norway and its 558 pairs outweigh `.bg` and `.mc` together. **Two
open leads, in order**: a late-1998 edition projects **8,712 EE** and only RIPE NCC can supply
it, so the route is a letter to the address that granted the 1999 file on 2026-08-26; and a
**2000-2003 frozen mirror holding a whole `ripe.db.gz`** is worth thousands, because RIPE
deleted the forward ccTLD objects between the two editions (1.23M forward names in 1999, 6,160
in 2004).

### the-on-disk-url-corpus-as-an-artifact-finder-which-paths-we-already-ho

**The on-disk URL corpus as an artifact FINDER: which PATHS we already hold promise a machine
dump (2026-08-30)**

**FIND, 157.8 net-new post-split EE over 250 pairs, every one at 2001**, parked on condition 2
of the standing rule. Eleven archived listing pages, largest
`https://web.archive.org/web/20011023104545id_/http://www.domainsww.com/Domain_Listing.htm`;
**what dates one item is the Wayback capture stamp on the page and nothing inside it**, and the
names are human-typed, so they take the corroboration split. 1,245 distinct domains and only
**32.0% held in any year**, because a for-sale listing prints speculator inventory that never
resolved; the 250 that pay are 62.8% of the 398 held names, which is the population `com` 2001
threshold of 0.611, so these pages carry no year advantage of their own. **Method, and it costs
zero requests: match the PATH, never the raw URL** (host-inclusive is 375x noisier, 117,912 hits
against 314, over the 118,142,155 URLs of `data/raw/webbase/webbase-2001.urls.gz`), keep only
the domain-specific signatures (`all_domains`, `domainlist`, `newdomains`, `whole_list`,
`zone_file`, `deleted`, `expiring`) since the generic dump words produced no survivor, and
settle each candidate in two requests with `archive.org/wayback/available` plus one `id_` fetch.
290 of the 314 candidates are unscreened and worth roughly 1,900 EE more at the measured 11
useful pages per 24. Detail in `docs/approved-sources-list.md`.

### public-mailman-subscriber-rosters-the-membership-table-rather-than-the

**Public Mailman subscriber rosters, the membership table rather than the messages
(2026-08-30)**

**FIND, 89.4 net-new post-split EE over 179 pairs, 178 of them at 2001**, parked on condition 2
of the standing rule. Five in-window rosters, largest
`https://web.archive.org/web/20010717203344id_/http://mail.python.org:80/mailman/roster/mailman-users`;
**the roster page carries no internal date stamp, so the Wayback capture timestamp alone dates
it**. 2,358 distinct registrable domains, **96.8% held** and 92.1% of those already carrying
2001, so a roster is a discovery loss and a year win: the 181 held-and-missing-2001 names are
the whole payout, at **0.0379 EE per listed subscriber domain** and 17.9 EE per page. Saturation
is visible at n=5 (2,921 per-page names against a union of 2,358, 19.3% duplication), so 5,000
EE needs ~280 more public in-window rosters against a measured 1.1% conversion of probed roster
URLs. **Method: a mail archive already on disk is a free URL generator for a family it is not
itself a member of**, since every Mailman message footer prints `/mailman/listinfo/<list>`,
which turned 868 MB of on-disk archives into 463 host/list pairs at zero network cost, and
`archive.org/wayback/available` prices a family when CDX is off limits. Mailman's members-only
default killed 4 of the 9 in-window captures and each is recognisable as a 324-519 B stub
without reading the body. Detail in `docs/approved-sources-list.md`.

### registry-whois-records-transcribed-into-artifacts-that-stamp-themselve

**Registry whois records transcribed into artifacts that stamp themselves: pasted whois blocks
in the on-disk Usenet spool, and the registrar creation dates recited in WIPO and NAF decisions
(2026-08-30)**

**FIND, BANKED at 30.4 EE on the Usenet arm** (see `usenet_whois_paste` below), the UDRP arm
PARKED. The Usenet arm reads the registry's own `Record created on 20-Jul-2000.` line out of
16,849 archives already on disk at zero network cost: 769 in-window pairs, 92.1% already held,
50 net-new pairs. **The UDRP arm fails condition 2 of the standing rule and is not ingested**:
the date reaches the artifact as a panellist's sentence, `The Whois record of the domain
MUSICWEB was created on January 10, 1995` (WIPO D2000-0001), which is a human recitation of a
machine stamp and not the stamp itself, and `adrforum.com/robots.txt` answers with a redirect
body rather than the file, so the NAF arm never had its terms read either. Measured anyway at
1,125 WIPO and 550 NAF decisions fetched: WIPO 284 pairs, 73.6% held, 46.2 EE; NAF 70 pairs,
75.7% held, 10.4 EE. **The family ceiling is 21,284 EE only if every one of the 8,892 disputed
names earned every missing year, and rule 6 gives a creation date its own year alone, so the
real ceiling is a small fraction of that.** Two things worth carrying. **A whois block puts the
name twenty to forty lines above its creation line, so the binding is the whole risk**: an
earlier pass bound `openssl.org`'s 1998 date to `engelschall.com` because a message quoted the
same block three times and the HTML-escaped copy defeated a start-anchored name pattern while
the date pattern still matched, the same mis-binding that once overstated the Edelman
transcriptions by 47%. Fix is one normalisation both patterns read, plus a 40-line look-back cap
carried on every row so it can be re-argued against data. **And `whois_creation` rows are
year-checked against the first four-digit run in their evidence value**, so a value naming a
group and a Message-ID would be read as the year 2000 on every row out of
`microsoft.public.win2000.dns`: put the registry's own date first.

### free-dns-hosted-zone-inventories-the-nameserver-s-own-list-of-the-zone

**Free-DNS hosted-zone inventories, the nameserver's own list of the zones it was configured to
serve (Granite Canyon, secondary.com, zoneedit.com, xname.org, freedns.com) (2026-08-29)**

**FIND at 1,732.9 net-new post-split EE over 3,059 pairs from seven objects and 1,567,653 B,
0.102 EE per listed name, confirmed on one of five hosts and refuted on the other four.** What
dates one item: the list stamps its own generation instant (`Rejected Zone List: 7-May-2001
22:11 GMT`; status.shtml's "29 November 1999 ... here is the list of pruned zones") and the IA
capture fixes when it existed, so one row is Granite Canyon's nameserver holding that zone in
its BIND configuration at that instant, class `artifact_listing`. The zone name was typed by the
customer into a submission form, so the corroboration split applies and only already-held
domains earn a year. **The artifacts**: `stale_30Nov1999.txt` (205,787 B, 14,522 zone names)
plus the six in-window editions of `soa.granitecanyon.com/ZoneRejects/` (1,361,866 B, 2,948 to
4,097 forward zones each). **Measurement**, `scripts/pricing/price_items.py --all-tlds` over
18,797 items: 17,049 distinct pairs over 16,979 domains, 6,777 already held, pre-split 10,272
pairs and 5,813.2 EE (overstates 3.4x, do not quote), **post-split 3,059 pairs and 1,732.9 EE at
mean weight 0.5665**, by year {1999: 2,001, 2001: 1,058}, by TLD {com 1,613, net 407, org 300,
ch 58, de 51, nu 49}, 7,213 pairs and 6,828 names to the candidate pool, typo upper bound 57.1%
(856 of 1,500). An independent duckdb screen sampling DISTINCT DOMAINS agrees to about 1%:
stale_30Nov1999 13,199 distinct domains, 7,969 held-any (60.4%), 2,026 held-and-missing-1999
against price_items' 2,001; the 2001 ZoneRejects union 4,092 domains, 1,916 held-any (46.8%),
1,071 held-and-missing-2001 against 1,058. **The held-fraction is the finding**: 60.4% and 46.8%
against 87 to 99% for authority corpora, ~50% for blocklists and 98.4 to 99.6% for visitor logs,
because a zone is not a page, so no crawler reaches it through a link and the artifact is not
head-selected. **And the population does not collapse on the 2001 threshold**: P(lacks 2001 |
held) here is com 0.5745, net 0.6174, org 0.5113 against the store-wide law's 0.611 / 0.653 /
0.568, within 6%, and yield per held name at 2001 is 0.317 EE against the 0.386 the law
predicts. At 1999 the same population gives com 0.2539, so a held name in a 2001 edition is
worth 2.3x one in a 1999 edition; the 1999 list alone is 1,125.5 EE and the 2001 reject union
alone 607.3 EE. **Refutations**: secondary.com (2001-05-16), zoneedit.com (2001-06-04) and
xname.org (2001-10-27) put the whole zone inventory behind `/auth/`, `login.html` and a per-zone
password, and freedns.com served an empty Apache index. **Method, and it is the transferable
part.** (1) A free-DNS operator's CUSTOMER population is the tail and its OPERATOR population is
not, and the two look identical until you ask who typed the name: the zone-file-RHS closure the
same week measured nameserver operators at 99.3% held-at-year and concluded that any population
defined by "this host answers DNS" is the ISC survey's own, but the same service read from the
other end measures 46.8% held and 0.5745. The discriminator is whether the selection predicate
is "runs a nameserver" or "asked somebody else to run one". (2) **When a service hides its
inventory behind a login, look for its ERROR LOG.** All four operators refused to publish a
customer list; the one that published a nightly list of the zones its BIND could not load gave
away 4,369 names it never meant to. Reject lists, prune lists, lame-delegation reports and
stale-zone reports are machine-generated, self-stamped and regenerated on a schedule, so every
capture is a fresh dated edition and nobody thinks of them as a customer list. (3) **Enumerate a
dead site's list files from its own dated changelog, not from an index**: four captures of
`status.shtml` at 1999-02-22, 2000-03-11, 2001-06 and 2002-06-06 named every list file the site
ever served and dated each, which a CDX prefix query would have cost many more requests to
establish. **Exhaustion**: six ZoneRejects editions exist in 2001 and no more, fourteen probes
across 2001-01 to 2002-04 collapsing onto those six timestamps; the 2002-05-26 edition is out of
window and cannot date a year; and the predecessor `zoneRejects.txt` is 9 names at 2000-03-03
and HTTP 403 at every later capture. Not a by-construction zero: no `granitecanyon` directory
exists under `data/raw` and this table records no ingest, and what already dates the held names
on a 400-domain sample is `prior_task` 196, `usenet_announce` 48, `domain_creation_bulk` 33,
`isc_survey` 33, `rdap_snapshot` 26. Prior art: the 2026-08-24 row below records this family at
1,881.1 EE against a 5,000 bar and kept no URL and no bytes, so it was not reproducible; 1,732.9
is that figure decayed by five days of ingest. Cost 40 archive.org fetches, no other host
touched, zero CDX queries. **Density per LISTED name is 0.102 EE combined, 0.148 at 2001 and
0.085 at 1999, 6x to 30x the curated-directory floor of 0.005 to 0.017**, so the ~83,000-name
floor that class demands becomes about 7,000 to 12,000 names here. Family CLOSED at those seven
objects: `granitecanyon / artifact_listing` is in `approved-sources-list.md` awaiting a human
`Decision:` line, the bytes are already fetched and nothing is ingested.

### free-for-all-ffa-link-pages-ffanet-com-and-the-networks-around-it-wher

**Free-for-all (FFA) link pages, ffanet.com and the networks around it, where the self-dating
premise is REFUTED and the family pays anyway on the 2001 year screen (2026-08-28)**

**FIND at 25.2 net-new post-split EE over 41 pairs from 9 pages and 178,235 B, 0.0726 EE per
listed distinct domain, effectively all of it from ONE page.** What dates one item: the Wayback
capture instant of a member FFA page, which displays the posted link as live text at that
instant. Class `dated_directory`, master-eligible; approval request filed, not ingested. **The
hypothesis's own premise dies first.** It says an FFA page stamps every entry with its own date,
so no capture is needed. Counting date literals against link count across all 9 pages:
`iwv2000.htm` 506 links / 0 stamps, `bds.htm` 307 / 0, `list.pl` 123 / 0, `linkstoyou.com` 38 /
0. The only page with per-entry dates is `freeforall.net`, 90 links / 63 stamps, and it is a
hand-curated "free stuff" table (Title / Info / Date, MMDDYY) and not an FFA page at all. So
this is an ordinary `dated_directory` and the date is in the capture. **The 4.56% question the
brief said decides the family is answered 20x the other way**: 347 distinct 2001 domains, 317
held (91.35%), against the remailer corpus's 4.56%, because an FFA submitter is advertising and
must post a URL that resolves. **And the whole yield is the year, exactly as squidGuard.** 2001
captures: 347 distinct, 91.35% held, 41 held-and-missing-2001, **25.1997 EE**, all 41 `com` 37 /
`net` 4, mean weight 0.6146, and all 41 are held at 2000 so the adjacent-year figure equals the
raw one. 2000 captures: 175 distinct, **175 of 175 held and all 175 already carrying 2000,
0.0000 EE**. Gross pre-split is 71 pairs / 43.4 EE and overstates 1.7x, do not quote. Typo upper
bound 40.8%; 21 of 347 novel to the store. The redirector killer that closed WebRing and
`free_host_member_indexes` does NOT fire: FFA entries are plain `href`s to the submitter's own
URL. What erodes the count instead is submitters without a domain posting on a free host, so the
registrable name collapses onto one certainly held that year (`roibot.com` x8, `hotyellow98.com`
x7, `angelfire.com` x6, `homestead.com` x5, `geocities.com` x4), which is why held-at-2001 is
87.1% where the `.com` population predicts 38.9%. Artifacts:
`web.archive.org/web/<ts>id_/http://pages.ffanet.com:80/links/<member>.htm`, 47,810 B (`bds.htm`
20000706234213) and 71,305 B (`iwv2000.htm` 20010307072648); the 110-member roster is
`ffanet.com:80/links/list.pl?` at 20000304021731, 14,590 B; plus `freeforall.net`
20010722003910, `linkstoyou.com` 20010630123832, `ffanet.com` 20010709121131, `ffanetwork.com`
20010721153909, `freeffa.com` 20010720133803, `ffapages.com` 20010302105939, `1-2-free.com`
20010622230517. Not archived: `ffanet.com/ffalist.htm`, `ffa.net`, `ffaking.com`,
`1st-in-links.com`. Out of window and NOT to be fetched: `addfreelinks.com` 2010, `ffagold.com`
2003, `ffamaster.com` 2002, `ffa-links.com` 2002. Method, three parts. (1) **Probe availability
before replay**: `archive.org/wayback/available?url=&timestamp=` answers in ~1.5 s where
`web/<ts>id_/` took 25 to 120 s under contention, so one cheap probe per URL turns every miss
into a 1.5 s miss and keeps off `/cdx` entirely. (2) **Audit the date claim before pricing the
corpus**: date literals against link count is one pass and it refuted the premise outright; a
hypothesis resting on "the artifact carries a per-entry date" should be tested by that ratio on
page one. (3) **A curated page inside a family is not an instance of it**: `freeforall.net`
looks like the hypothesis confirmed and is the one page that is not an FFA page; pricing it
alone would have reported a self-dating family that does not exist. Tools at `scratchpad/ffa/`.
Continuation, ONLY at 2001: ~25 EE per 2001-captured member page means ~40 pages for 1,000 EE
and ~200 for 5,000; pull `list.pl` at several captures since the roster rotates,
availability-probe every member URL at a 2001 pin, discard 2000 captures unmeasured, replay the
survivors. Page size predicts yield in this sample but is confounded with year and wants
separating on the next 20 pages. Rights: `list.pl` asserts sole intellectual property over the
ROSTER, member pages carry a normal copyright line, measurement unaffected. `web.archive.org`
serves no robots.txt (404, verified); `archive.org` disallows only `/control/` and `/report/`.

### 2001-nonprofit-portals-a-find-that-closes-its-own-family-and-the-head-

**2001 nonprofit portals, a FIND that closes its own family, and the head-selection law
operating INSIDE one directory (2026-08-28)**

**FIND at 202.2 net-new post-split EE over 289 pairs, all at 2001, mean weight 0.6996 (org 257 /
com 29 / net 3), from 19 dated pages and 601,956 B; and the family is CLOSED at that figure,
because its entire enumerable population is 1,843 names against the 9,116 that 1,000 EE needs.**
Class `dated_directory`, master-eligible, approval request filed with `Decision: pending`; NOT
ingested. Dating rests on the Wayback capture instant alone, since no page in the family carries
a usable self-date (the Foundation Center list pages print none), so the corroboration split is
taken. The paying seven, all `web/<ts>id_/`:
`fdncenter.org/funders/grantmaker/gws_pubch/pubch_list.html` at 20011102033013 (740 domains),
`gws_priv/priv_list.html` at 20011024182703 (548), `gws_priv/priv2.html` at 20011004165617 (546,
a Netscape-4 duplicate that checks priv_list is complete), `gws_corp/corp_list.html` at
20010806091046 (376), `interaction.org/members/` at 20011101195341 (149),
`foundations.org/grantmakers.html` at 20011015131123 (99), `igc.org/igc/gateway/index.html` at
20011011002103 (36). Priced with `scripts/pricing/price_items.py --all-tlds` against
merged260827: 1,843 distinct pairs over 1,843 domains, 1,523 already held AT 2001 (82.6%), only
29 names never held anywhere (98.43% held), pre-split 320 pairs and 223.6 EE (overstates 1.11x,
do not quote), **post-split 289 pairs and 202.2 EE**, typo upper bound 37.8%. An independent
duckdb screen sampling DISTINCT DOMAINS over the three fdncenter `_list` pages agrees to 0.36%
(1,648 listed, 1,619 held, 1,349 carrying 2001, 268 held-and-missing at 187.43 EE against
price_items' 269 at 188.1). **279 of the 289 gain domains (96.5%) are held at 2000**, so this is
adjacent-year headroom and not a death gap. Rates: **0.1097 EE per listed domain, 10.6 EE per
dated page fetched.** Head-selection penalty measured at 4.34x: only 15.93% of held names here
lack 2001 (289/1,814) against the `.org` population's 69.15%; `.org` at weight 0.7101 makes one
already-held name dated 2001 worth 0.491 EE, above `.com`'s 0.386. **The method, and it is the
result: within one nonprofit directory the discriminator is whether the listed entity's website
is a CORPORATE domain or a standalone nonprofit domain, and it is readable off the section name
before any fetch.** The Foundation Center's four sections are one artifact family, one crawl,
one page shape, one capture window, and they spread 10.1x: priv_list 548 listed / 532 held / 375
carrying 2001 / 157 gain / 109.98 EE = **0.2007 EE per listed name**; pubch_list 740 / 728 / 625
/ 103 / 72.08 = 0.0974; interaction 149 / 149 / 134 / 15 / 10.65 = 0.0715; foundations.org 99 /
99 / 94 / 5 / 3.47 = 0.0351; **corp_list 376 / 373 / 362 / 11 / 7.50 = 0.0199**. The reason is
visible in the names: corporate giving programs live at `abbott.com`, `aetna.com`, `adobe.com`,
`agilent.com`, so 97.05% of the held ones already carry 2001, while private foundations live on
their own small `.org` domains and only 70.5% do. So split a directory by listed-entity type and
price only the nonprofit-domain sections; **per-arm attribution before quoting any per-item
rate.** Second method find: **on any alphabet-indexed directory look for the single-page variant
FIRST.** `priv1.html` offers A-to-Z browse plus one link labelled only "related document", and
that link is `priv_list.html`, the complete unannotated roster of all 26 letters in one file,
both cheaper (1 request against 26) and the higher-coverage surface. **Why the family dies, and
it is the pre-download screen: volume and browsability are anticorrelated across this whole
sector.** Every 2001 nonprofit portal with five-figure record counts put them behind a search
form and has no captured multi-record surface, GuideStar ~640,000 orgs and Idealist ~20,000
being one record per request, while CharityChoice states "more than 7,000 entries in 27
categories" in its own meta description and archives only the FORM (`searchtdframe.htm` at
20011020104216, whose only captured frame is `searchtdpage.htm`). The rosters that ARE browsable
are the small accreditation-shaped bodies. Measured zeros, each fetched and parsed rather than
assumed: `netministries.org/see/churches/` at 20000920005932 is 58 B of "*Sorry* cannot find
that church"; `idealist.org/orgs/` at 19991002025040 yields 0 external hosts;
`give.org/reports/index.asp` at 20011002001937 yields 2, both `bbb.org` and `adobe.com`, because
a BBB charity report links to its own internal report page and never to the charity;
`oneworld.org/partners/`, `charitynet.org/` and `wango.org/` yield 0. Genuine 404s against a
passing control: the whole `gws_comm` community-foundations section and
`helping.org/nonprofit/`. archive.org's item store holds no bulk artifact for the family:
`advancedsearch.php` on guidestar / charity directory / nonprofit directory / grantmaker web
sites / foundation center, each AND `date:[1996-01-01 TO 2001-12-31]`, returns numFound 3, 11,
27, 0 and 2,500, and every in-window hit is a printed fundraising handbook or an ERIC paper. Two
traps. **`archive.org/wayback/available` returned NONE for `priv_a.html`, which the replay
endpoint's own 302 then resolved to 20011024145446**, reproducing the false zero recorded on
2026-08-27; the replay 302 got the same four probes right including two genuine 404s, so re-test
every `available` zero against `/web/<ts>/URL` with a known-good control before recording it.
And **a sub-1KB 2001 page is often a `navigator.appVersion` browser fork, not the content**:
`gws_priv/priv.html` is 849 B of JavaScript branching to `priv1.html` or `priv2.html`, and a
reader that took it as the section would have filed the largest arm in the family as empty.
Operationally, **`web.archive.org` and `archive.org` fail independently, so use the healthy one
for the question it can answer**: replay refused roughly half of all TCP connections through
this run (4 of 6, 3 of 6, 4 of 6 in three timed probes, a flat ~3.4 s connect failure, no 429,
no 503, no `Retry-After`) while `archive.org/wayback/available` answered 200 continuously, so
existence and URL-variant mapping were done entirely on archive.org at ~1 q/s and the expensive
`id_` fetches restricted to confirmed timestamps. That refusal is capacity and wants a flat 8 s
retry, not exponential backoff; treating it as absence would have filed four live pages as
unreachable. Do not re-test the Foundation Center Grantmaker Web Sites (`gws_comm` was never
captured, and its A-Z letter pages are the same names annotated, so 78 further fetches add
nothing), helping.org, GuideStar, Idealist, CharityChoice, netministries, give.org, oneworld,
wango, charitynet or foundations.org. **The one thread that belongs to a different family:**
`igc.org/igc/gateway/index.html` names 36 hosts of which several are `*.igc.apc.org` subdomains,
the signature of a **nonprofit ISP hosting its members**, and a member list from IGC, EcoNet,
PeaceNet or an ISP association is a different population from a directory of organisations that
already had their own domain.

### seal-and-certification-rosters-the-one-shape-of-customer-showcase-that

**Seal and certification rosters, the one shape of "customer showcase" that pays (2026-08-27)**

**FIND, 1,581.7 net-new post-split EE over 2,554 pairs, and a discriminator that splits the
family in two.** BBBOnLine's Reliability participant directory is an alphabetically enumerable
36-page namespace, `http://www.bbbonline.org/search/Relresult.asp?letter=<@,0-9,A-Z>`, linked
from `search/Relbrowse.asp`; 33 letters have a 2001 capture, 3,574,800 bytes, 7,605 participant
rows, 9,019 distinct registrable domains under a weighted TLD. Sampled DISTINCT DOMAINS: 8,286
held any year (91.9%), 5,911 already carrying 2001, **2,375 held-and-missing-2001, of which
2,222 (93.6%) are adjacent held-2000-and-missing-2001** rather than death-gap.
`scripts/pricing/price_items.py --all-tlds` against merged260827: 3,109 net-new pairs and
1,919.7 EE pre-split (do not quote), **2,376 pairs and 1,470.1 EE post-split**, mean weight
0.6187, `com` 2,163 / `net` 175 / `org` 23, typo upper bound 46.3%; an independent duckdb year
screen gives 2,375 pairs and 1,469.5 EE, agreeing to 0.04%. TRUSTe's licensee roster
(`truste.org/users/users_lookup.html` at `20010603230742`) adds 1,522 domains, 99.0% held, 1,323
already at 2001, **184 held-and-missing-2001 and 115.1 EE**, which is 0.076 EE per listed name
against BBBOnLine's 0.163: the head-corpus law exactly, since TRUSTe licensed `abc.com`,
`about.com` and `expedia.com` while BBBOnLine listed air-conditioning contractors and local
ISPs. **The reusable discriminator: a provider-run member index links the member THROUGH the
provider and so cannot name the member's own domain (measured at 0.0 EE the same day,
`free_host_member_indexes`), while a seal or certification roster MUST print the member's own
domain, because the domain is what is being certified.** So the pre-download question is whether
the listing's subject is the customer's SITE or the customer's ACCOUNT, and the whole 7,600-row
database comes out in 36 requests with no CDX query anywhere. Two traps paid for here:
`archive.org/wayback/available` returns the CLOSEST capture, which for a `20011215` target lands
in 2002-01 for a third of the letters and would silently import a 2002 roster as a 2001
observation, so target `20010901` and reject any timestamp not starting `2001`; and this
template writes `HREF=http://...` UNQUOTED, so a quoted-href regex reports 0 absolute links on a
347,822-byte page holding 1,013 of them, which is how a real source gets buried. Approval
requests filed as `bbbonline_reliability_roster / artifact_listing` at potential 87 and
`truste_licensee_roster / artifact_listing` at potential 55, both Decision pending, neither
ingested; both readings are on the sheet, since the master reading (a roster generated from a
participant database is not something a human typed, the `namewinner_expiring` argument) is
1,919.7 EE against 1,470.1 EE split. Three cheap increments left: the Privacy programme's
separate roster at `search/Pribrowse.asp`, the three letters (`L`, `V`, `6`) with no 2001
capture, and the same namespace at 1999 and 2000 captures, where the adjacent-year law says
price one letter page before fetching 36. The family is otherwise thin: 12 payment-gateway,
storefront and certificate-issuer hosts were screened at 2001 and none carries a merchant
listing (`cybercash.com` an 11,247 B shell, `ccbill.com` 1,910 B, `shopnow.com` 983 B,
`ibill.com` only a `/Members/` login, `authorizenet.com` no directory link, `miva.com` and
`mercantec.com` link a storefront), and `dotcomdirectory.com` delegates every category listing
to `dotcomdirectory.net`, which has NO capture at all.

### bruce-guenter-s-spam-archive-re-priced-the-advertised-url-is-refuted-a

**Bruce Guenter's spam archive re-priced: the advertised URL is refuted and the RECIPIENT header
is the find (2026-08-27)**

**1,288.1 net-new post-split EE over 3,053 pairs, 6.6x the 2026-08-15 reading of the same bytes,
and the hypothesis that produced it is refuted with the sign reversed.** The lens was the URL a
spam ADVERTISES rather than the sender it forges, on the argument that a spammer paying for
traffic must name a real live site. Five populations were cut out of the same 20,010 messages
(`untroubled.org/spam/1998.7z` through `2001.7z`, 9,312,329 B, plus two 1997-1998 header dumps)
and priced separately by `scripts/pricing/price_items.py --all-tlds`, sampling DISTINCT DOMAINS:
recipient (To/Cc/Bcc/Delivered-To) 10,313 domains, **91.1% held**, mean weight 0.549, 566.2 EE;
sender (asserted plus all relays) 15,379, 82.7%, 680.9 EE; observed (last-hop `Received:` only)
8,999, 82.6%, 485.5 EE; asserted (From/Return-Path/Message-ID) 7,486, 83.3%, 219.7 EE; **body
(advertised URLs) 4,820 domains, 77.3% held, the WORST of the five, 139.6 EE**; union 26,112
domains, 29,356 pairs, 83.9% held, **1,288.1 EE**. The advertised domain is disposable,
registered days before the campaign, so it is exactly the name the store does not hold, and
under the split not holding it earns nothing: 678 of its 4,820 names are new even to the
candidate pool. **Two laws come out of this.** (1) **Forgery does not predict the held fraction
at all.** What the receiver observed on the wire (peer hostname, HELO, IP, not under the
spammer's control) reads 82.6% and what the sender asserted reads 83.3%, indistinguishable. So
the register's 4.56% figure from the Lazarus remailer logs is not a law about forged headers, it
is a property of remailer nym addresses; direct-to-MX bulk mail forges plausible real ISP
domains because it wants to look deliverable, and its forged senders are 18x more likely to be
held. **Ask which FIELD, not whether it is forged**: established business or ISP (recipient,
pays), Asian open relay (observed, weight 0.313), disposable landing site (body, 77.3%). (2)
**The harvested recipient list is the highest-value field in a message**, 91.1% held at weight
0.549, the only population high on both screens, because a harvested address sits at an
established English-language business that survived, and 2001 spam BCCs an alphabetical walk of
somebody's zone rather than human-typed names. Dating: the qmail maildir filename is a unix
epoch written by the RECEIVING MTA and the last-hop `Received:` line restates it; 20,007 of
20,010 filename epochs agree with the archive's own directory year, and the spammer's forgeable
`Date:` header is ignored. 2001 carries 2,794 of the 3,053 pairs (1998 115, 2000 91, 1999 50,
1997 3) because 14,732 of the 20,010 messages are 2001; by TLD com 1,353, jp 245, net 194, kr
193, tw 131, de 102. Adjacent-year check: 1,106.8 EE, 85.9%, sits on a domain held at Y-1 or
Y+1, so it is not the contaminated held-any-year shape. Gross before the split is 7,325 pairs
and 3,470.5 EE: do not quote. Ten random scoring pairs were traced to the byte that dates them
and all ten confirmed. **Why the 2026-08-15 row read 195.5 EE over 4,793 domains and these bytes
hold 26,112: nothing was MIME-decoded.** 2001 spam hides its URL in base64 or quoted-printable
HTML, and an `email` walk with `get_payload(decode=True)` over every text/* part yields
78,753,891 bytes of body and a URL in 11,734 of 20,010 messages where a raw grep finds almost
none. **A filename epoch is a delivery stamp only in a maildir**: all 401 files in
`1997-1998-headers.tar.bz2` carry epochs inside 89 seconds of 1998-03-26, which is when the
mailbox was dumped, and only the mbox `From ` separator in the sibling reaches 1997. Licence:
"Permission is hereby granted to use this archive without restriction", robots.txt 50 B denying
only `/stats/` and `/lists/`. **The family is exhausted**: the `untroubled_spam_archive` item on
archive.org is byte-identical file for file, `spamarchive.org` is now a Syracuse
window-replacement business and so is a proved zero rather than a refusal, and Ling-Spam is 481
messages and body-only. Sizing for a future trap: 0.0644 EE and 1.30 distinct domains per
message, so 5,000 EE needs about 78,000 in-window trapped messages. Raised for approval as
`untroubled_spam_headers / artifact_listing`. **Re-run the MIME and recipient laws over every
mail-shaped corpus already ingested** (`data/raw/enron`, `data/raw/maillists`,
`data/raw/usenet`): anything ingested from HTML hypermail never saw a header at all.

### free-hosting-and-isp-member-indexes-re-tested-at-2001-on-the-right-scr

**Free-hosting and ISP member indexes, re-tested at 2001 on the right screen (2026-08-27)**

**Still 0.0 EE, and now for the right reason, plus a mechanism that generalises.** The
2026-08-08 closure used the RETIRED novelty screen ("617 domains at 97.4% already held"),
written 17 days before the 2001-threshold law, which is the same error corrected for Stanford
WebBase, so it was worth one re-test. Four fresh artifacts plus three host homepages as
controls, all reachable: Tripod's member index at `20010515062824` (173 B), GeoCities'
neighbourhoods at `20000901091820` (567 B), Bigstep's example sites at `20010603211725` (17,627
B), NetNation's `/customer/` at `20010601115834` (15,861 B), and `pair.com`, `he.net`,
`netnation.com` at 2001. `scripts/pricing/price_items.py` over all seven against the live store:
**7 items, all in window, 15 distinct registrable domains, 16 pairs, 16 of 16 already held, 0
net-new before AND after the split, 0.0 EE**. Year screen on distinct domains: 15/15 held, **15
already carrying 2001, held-and-missing-2001 = 0**. Every one of the 15 is a provider or
ad-network name (`tripod.com`, `geocities.com`, `bigstep.com`, `netnation.com`, `pair.com`,
`he.net`, `bfast.com`, `yimg.com`), 12 of them held across all six years. **The mechanism is the
transferable part: a provider-run member index links members through the PROVIDER, so it cannot
name a member's own domain even when the member has one.** Tripod's index is a 301 stub naming
`tripod.com`; GeoCities' is a meta-refresh into `cgi-bin/hood/geo`, so there is no bulk index
artifact at all. **The vanity-domain carve-out was tested on its best instance and refuted**:
Bigstep hosted small BUSINESSES with their own domains and showcases 13 members in 17,627 bytes
while naming **zero** of their domains, because each member is a thumbnail
(`ss_bookbouquet.gif`) linked through bigstep.com; exactly one member name was recoverable
anywhere on the page, from a caption, and the store holds it at 2000 and 2001. NetNation's
`/customer/` is a login portal with four hostnames, all NetNation's own, and `pair.com` and
`he.net` carry no customer-list navigation at 2001. This is the same death WebRing took, reached
on a host whose members were businesses rather than hobbyists, which is the strongest form of
the carve-out. Volume kills what the mechanism leaves: at 1 recoverable domain per 13 showcased
members, the ~2,590 held `com` names 1,000 EE needs at 2001 would take about 33,600 members over
roughly 2,600 pages. Ten guessed customer-list paths returned NONE from the availability API,
but a positive control proved that was wrong paths and not missing captures: the same API
returns 2001 captures for all three bare hosts. Method worth keeping:
**`archive.org/wayback/available?url=...&timestamp=YYYYMMDD` finds captures without touching a
metered CDX** (`web.archive.org` returns 404 for robots.txt so carries no file; `archive.org`'s
is 12 lines, `/control/` and `/report/` only, naming no Claude agent), and **fetch the `id_`
replay form** or Wayback's link rewriting turns every outbound href into `web.archive.org` and
the extraction measures the archive instead of the artifact. A retry wrapper is required:
`web.archive.org` refused the connection on 6 of 14 attempts and succeeded on retry every time.
The one population left in this family is NameZero, which registered real `.com` domains for
over 400,000 free members by May 2000 and was then the largest single registrant in the world;
its 2001 site publishes no member directory, so it is unreachable through this lens and would
have to come from registry or WHOIS data, where the Verisign pool is already spent. Do not
re-test free-hosting or ISP member indexes on any screen.

### site-meter-and-the-counter-service-lens-re-proposed-and-closed-without

**Site Meter and the counter-service lens, re-proposed and closed without a fetch (2026-08-27)**

**0 EE, duplicate lens.** The hypothesis named theCounter, NedStat, eXTReMe Tracking and Site
Meter; the counter-directory row above sizes the first three by name in the same sweep
(`nedstat.com` 3,392 in-window captures, `extreme-dm.com` 7, `thecounter.com` 0) and closes the
family on measurement: `hitbox.com`'s head page at 1998-02-05 gives 48 registrable domains, **48
of 48 already held AT 1998, 0.0 EE**, the deep rank pages carry 0 member rows, and the whole
in-window list-page universe is 483 captures with **none at 2001**. Site Meter is the only
member never named in `docs/sources.md` (grepped `sitemeter|site
meter|statcounter|webtrends|hitbox|websidestory` across `docs/`, one hit). It is not an
exception: sitemeter.com launched 1999 and its public surface is per-member stats pages plus a
ranked top-sites list, the identical shape, and the closure's mechanism is structural rather
than host-specific. No new measurement was taken and none is warranted. **The cheap pre-download
test this leaves behind: a service's public list is not its database, it is the marketing head
of it.** The only version of this family that could ever pass the authority screen is the
inverse shape, a public artifact that is NOT rank-ordered so that publication is not
head-selection: a full alphabetical member index, an embedder manifest, or a billing list. Do
not re-test traffic or counter services.

### the-wayback-refused-this-ip-hour-measured-it-was-not-us-not-a-block-an

**The "Wayback refused this IP" hour, measured: it was not us, not a block, and not that hour
(2026-08-27)**

**The refusal is real but it is REPLAY ONLY, and the concurrency hypothesis is refuted three
ways.** The flag said `web.archive.org` refused this IP at the TCP layer through most of the
15:00 UTC hour while `ark cdx` ran two clients. Four corrections, all measured. **(1) The hour
is wrong by two.** Every log this project writes is local CEST, so the window was **13:05 to
13:35 UTC**, and anyone correlating it against the archive's own status history would have read
the wrong hour. **(2) There was one `ark cdx` client, not two**: `cdx_pool` stopped at 08:02Z
and only `cdx_gtail` was running; the second client was the iteration's OWN replay fetcher,
sequential, one socket, started 13:10:28Z. **(3) Throughput is invariant to our concurrency.**
Six batches today, worker count 8, 8, 3, 3, 3, 8: rates 8.93, 10.03, 8.90, 9.05, 7.16 and 8.31
domains/min. Cutting workers from 8 to 3 at 10:46Z changed the rate by 0.3% and the failure rate
went the WRONG way, 3.67% to 6.17% to 7.83% to 18.45%, then FELL to 8.62% when workers went back
to 8. A 2.7x change in our own in-flight requests moves neither number, because `throttles` ran
at roughly one per query all day and `final_delay_ms` was pinned at its 3.0s ceiling in every
completed batch: the bottleneck is server-side per-query latency shared across workers, so we
were never the limiting party. **(4) It was not an IP-level block, because the index kept
answering.** In the incident batch the CDX index still completed 233 queries and answered
**81.5% of them 200**. A block on this IP would take both services; instead, in the same
minutes, `web.archive.org/cdx/search/cdx` ran at ~8.3 domains/min while
`web.archive.org/web/<ts>id_/` produced **21 successes in 26.9 minutes, then zero in the 5m10s
to 13:42:32Z**. The two are different tiers and only the replay tier fell over. **It also did
not end at 13:35Z**: the replay client was still alive and still producing nothing seven minutes
later, so "most of that hour" understates the duration and misattributes the boundary to the
supervisor restart that happened to fall there. **The reusable finding is the forensic gap: a
per-minute series cannot be reconstructed from the cdx journals at all.** Journal records carry
`domain`, `status`, `strategy`, `truncated` and `years` and **no timestamp**; the only
per-second stream is the tqdm progress bar on stderr, which `supervise_cdx_pool.sh` strips with
`grep -v "domain/s]"` before appending to the shared log, and `BATCH_OUT` is truncated on every
dispatch. So the finest retrospective resolution this project can ever reach on a past window is
one batch, about an hour. The supervisor already computes `journal_bytes()` every `CHECK` and
logs it only on a stall; logging it unconditionally would give a 15-minute series for free. **Do
not make that edit while a supervisor is running**: bash reads a script lazily by byte offset,
so editing a live `supervise_cdx_pool.sh` can corrupt the loop mid-flight. **The operational
rule: when the archive slows, do not throttle ourselves further. Check the index separately from
replay first, because only one of them is usually down, and our worker count is not what either
responds to.**

### the-debian-package-archive-as-a-blocklist-seam-and-the-one-find-in-it

**The Debian package archive as a blocklist seam, and the one find in it (2026-08-27)**

**14,229.0 EE found, and the method is the reusable part: ONE request per release indexes every
package in it.** `archive.debian.org` has no robots.txt, and
`dists/<rel>/main/binary-i386/Packages.gz` carries every package name, version, size and
description for that release. Fetched for all five in-window releases: bo 213,586 B, hamm
331,271, slink 493,436, potato 823,298, woody 1,773,087. That is the `ls-lR` trick applied to a
package archive, and it turns a whole distribution into an offline grep. Narrow blocklist regex
over the five: **bo 0 hits, hamm 2, slink 2, potato 1, woody 4**. **The find is `chastity-list
0.5`**, 701,038 B in woody and described as "blacklists for SquidGuard", whose source tarball is
tar-stamped `Dec 14 2001` with per-date diffs inside the window: 97,937 distinct domains,
**94.0% held**, 24,927 held-and-missing-2001, **14,229.0 EE**, GPL v2. Filed as
`chastity_list_blacklist / dated_directory`, pending, ranked first in the triage queue.
**`junkbuster` is the seam's other member and is worthless**: present in hamm, slink, potato and
woody at 78 to 104 KB, but `/etc/junkbuster/blockfile` is 2,108 bytes in 1998 and 2,058 in 2000
and is headed "Illustrative Blockfile", with **4 non-comment lines** in every one of the three
in-window versions. Closed. `chastity-list_0.5.20020928` is the out-of-window sibling, stamped
`Sep 28 2002`, recorded so nobody fetches it twice.

### the-tomocha-net-refusal-applied-to-one-file-and-not-the-other

The `tomocha.net` refusal, applied to one file and not the other (2026-08-27)

**An inconsistency in this register, found by the same consistency check that caught the RDAP
terms, and it currently costs nothing.** `tomocha.net/robots.txt` carries `User-agent:
ClaudeBot` / `Disallow: /` at lines 51-52, and on 2026-08-25 `jpnic_register` was withdrawn for
it with the note that its 1,623 EE "stands and must not be used". **But 179.8 EE from the same
host on the same day was banked**: the 1999 InterNIC `edu` and `gov` zones at
`tomocha.net/files/dns/`, ledgered as `edu.zone.19991120.gz` at 13,822 rows and
`gov.zone.19991119.gz` at 1,306. There is no principled difference between them on content,
since tomocha mirrors somebody else's register in both cases, so either the refusal covers both
files or it covers neither. **Measured cost of resolving it either way is zero for this round**:
`internic_zone` at 1999 is 0 pairs and 0.0 EE net-new against `merged260827`, all of it already
merged into his baseline, so nothing is withdrawable and only the register's wording is at
stake. Raised for Ivo rather than decided.

### the-expansion-corpus-s-unpromoted-half

The expansion corpus's unpromoted half (2026-08-27)

**A real gap in the promotion tool worth about 3 EE.** `build_promotion_journals.py` covers
eight mention sources and `page_expansion` is not one of them, so its candidate half had never
been re-promoted. By the re-split law that should pay; it does not, because the corpus is tiny:
**696 evidence rows over 551 distinct domains**, of which 695 have a domain some other source
now dates and only **5 (domain, year) pairs are held-but-missing-that-year**. Adding
`page_expansion` to the promotion tool is correct and is not worth doing for the yield.

### ranking-the-candidate-pool-by-corroboration-instead-of-by-a-modelled-h

Ranking the candidate pool by corroboration instead of by a modelled hit rate (2026-08-27)

**Built, measured, and deliberately NOT switched into a running engine.** The modelled ranking's
failure mode is fabricated names, so the fix is a filter the model cannot express: how many
INDEPENDENT sources name the string at all. Over the whole pool, **86.32% of 2,376,036 names are
named by exactly one source**, which is where a generator's output lands; keeping the
multi-source slice leaves **325,127 names worth 209,036 EE** if each gained one year, led by
`.au` 0.9904, `.gov` 0.9825 and `.uk` 0.9813 instead of by a fabricated `.ca` block.
`scripts/engines/build_multisrc_queue.py` rebuilds it. **Status is honest: unmeasured against
the gap population**, which cannot contain a fabricated name at all since a gap target is a name
already held, and the engine that would have been switched was measuring 1.67 years per query at
the time. A working engine is not a test bed.

### re-splitting-a-mention-corpus-against-a-grown-store-measured-twice

**Re-splitting a mention corpus against a grown store, measured twice (2026-08-27)**

**The largest lever found in this round, and it reads nothing new.** The corroboration split
promotes a mention to a dated record only when some OTHER source already places that domain in a
year, and that test is re-evaluated on every split run. So the same journals are worth more as
the store grows. Measured on two corpora on one morning: **addresses**, 60 new archives plus a
re-split of the 2026-08-08 journals gave 51,235 pairs and 30,645.6 EE, of which roughly 700
pairs are attributable to the new archives; **bare hostnames**, one bank re-splitting 601,738
recovered rows gave 16,114 pairs and 11,447.7 EE against 188 pairs and 128.17 EE for the 400 new
archives that triggered it. **So the ratio of re-split to new-reading is about 40:1 and 90:1.**
It also corrects a projection quoted earlier the same day: `project_usenet_bare.py` priced the
seam at 514 to 1,007 EE, which is the right answer to "what do new archives add" and the wrong
answer to "what does running the bank step add". Both figures are correct about different
questions. **The announce corpus has no cheap equivalent**: `split_usenet.py` takes archives
rather than journals, so its re-split is the promotion tranche, measured the same morning at
5,779 pairs and 1,824.4 EE. **Run the split, not the reader, first, and re-run it after any
large ingest.**

### funet-s-frozen-netinfo-mirror-swept-by-its-own-index

FUNET's frozen `netinfo` mirror, swept by its own index (2026-08-27)

**The one-request `ls-lR` trick worked and the prize it named is gone, but the lead it leaves is
worth finishing.** FUNET is the host that supplied `ripe_dbase_1999` and has NO robots.txt at
all, so nothing there forbids us. `/pub/netinfo/ls-lR.test`, one request, 351,368 bytes, 5,795
lines, indexes the whole subtree offline: 563 files dated 1996-2001 over 62,188,621 bytes. **The
two largest are a registry dump**, in
`/pub/netinfo/FUNET/history/a.dump.of.funet.fi-ftp.archive.1996-10-25/netinfo/netinfo/`:
`domain-contacts.txt.Z` at **35,571,481 bytes** and `domain-info.txt` at **9,918,513 bytes**,
both stamped `Jun 23 1996`, which is InterNIC's own domain register frozen inside a 1996 FTP
dump. **Both are 404 and the negative is proved against a known positive**: in the same minute
and over the same protocol, `/pub/netinfo/RIPE/dbase/ripe.db.gz` still answers HTTP 200 with
71,919,736 bytes and `Last-Modified: Tue, 03 Aug 1999 21:27:00 GMT`, so the server serves deep
paths under that tree and the files are genuinely gone. `ls-lR.test` is a stale index of a tree
since removed, and `/pub/netinfo/FUNET/history/` now lists only a `README.FTP-1997-and-older`
where the dump stood. **The upstream was then checked and is empty too, so this is CLOSED.** The
index named what to look for, `domain-info.txt` and `domain-contacts.txt` under InterNIC's own
`netinfo`. First attempt failed at transport level and was recorded as unfinished rather than
zero; retried with `--retry-all-errors`, `rs.internic.net/netinfo` returns HTTP 200 and empty
while the `nw.com/zone/` control returns rows in the same session. A filename filter over the
whole `internic.net` domain then settles it: `original:.*domain-contacts.*` returns **zero
rows**, `.*netinfo.*` returns only 404s and referrer noise, and `.*domain-info.*` returns 12
rows which are the HTML `/domain-info/` FAQ section rather than the file, so the filter
mechanism demonstrably works and the two zeros are real. Note the year: a 1996-dated register
dates 1996, our thinnest year, where the whole 1996-to-1997 adjacent gap is 109,796 domains and
66,701.7 EE gross, so the ceiling is real but bounded.

### the-bare-hostname-usenet-seam-priced-over-the-pools-still-on-disk

The bare-hostname Usenet seam, priced over the pools still on disk (2026-08-27)

**128.17 EE over 400 archives, projecting to 514-1,007 EE over all 16,797, so worth free CPU and
nothing more.** `collect_usenet_bare.py` reads the plain `foo.com` in running prose that no
other extractor sees, and it had the same empty-directory bug as the address extractor. Spread
sample of 400 `usenet_bulk` archives, 3,922,752 messages, 1,956,416 in window: 13,685 distinct
pairs gross, of which 9,964 were already asserted by `usenet_announce` or `usenet_address`,
11,135 already assigned by some source, 2,362 uncorroborated, and **188 marginal net-new**.
**Gross would have read 8,748.19 EE against a marginal 128.17, a 68x overstatement**, which is
the clearest single illustration of why this project quotes net-new post-split.
`project_usenet_bare.py`'s three fits: linear 5,382 EE, the shape already known to overstate by
24x; saturation 514 EE with half-yield at 1,402 archives; power law 1,007 EE at exponent 0.60.
The sample's own curve rises 48, 57, 128 EE at 110, 210 and 400 archives, so saturation is real
but not yet biting. Needs no decision: `usenet_bare / dated_directory` is already master.

### the-rebuilt-candidate-pool-cdx-queue-an-80x-collapse-and-a-measured-re

The rebuilt candidate-pool CDX queue, an 80x collapse and a measured revert (2026-08-27)

**Recorded as a measurement, deliberately NOT as a law about ranking, because that mistake has
already been made once here.** Rebuilding `queue_pool_local.txt` against the new baseline took
the local engine from 1.15-1.66 years per query, over five finished journals on 26 August, to
**0.014 and then 0.020**. What rules out throttling, which is what produced the withdrawn
sixtyfold claim on 2026-08-26, is that failures FELL from 58% to 9% and 312 of 342 requests were
answered: the archive replied and the names simply had no in-window capture, which is a
population property and not a rate property. The cause is visible in the queue head: **18,184 of
the first 20,000 lines are `.ca`**, and they are fabricated pool strings such as
`afakeaddress.ca`, `lgffu.ca` and `doodoo.cg`. This is the `.mil` failure the queue builder's
own docstring records from 11 August, recurring under a different TLD once `.ca` gained enough
dated rows for `pool_plausibility` to rank it while its pool stayed fabricated. **No re-tuning
was done under time pressure.** The gap population cannot have this defect, since a gap target
is a name already held, so the local engine was moved to the unreached tail of the gap ranking,
positions 200,001 to 409,075, 209,075 targets and all `.com` at the head. First reading there:
**15 queried, 15 answered, 32 year-records, 0% failures, 2.13 years per query.**

### the-whole-rdap-query-route-closed-on-the-registries-own-terms

The whole RDAP query route, closed on the registries' own terms (2026-08-27)

**The terms were inside every response the entire time, in the `notices` block, so this cost
nothing to find and three days of engine time not to.** Read out of our own journals for
Verisign, PIR and Nominet, and from the page Verisign's notice links to. **Verisign**
(`verisign.com/legal-center/rdap-terms/`): you will not "enable high volume, automated,
electronic processes that send queries or data to the systems of Verisign or an ICANN-accredited
registrar, except as reasonably necessary to register domain names or modify existing
registrations". **PIR** the same clause and carve-out, plus "Abuse of the RDAP system through
data mining is mitigated by detecting and limiting bulk query access". **Nominet** the same
clause with NO carve-out, and separately "You are explicitly prohibited from extracting, copying
and/or using or re-using in any form and by any means (electronically or not) all or part
(quantitatively or qualitatively) of the contents of the RDAP database without prior and
explicit permission". **CIRA** the same, rejected the same morning. So the engine pointed at
Nominet on 2026-08-24 "needing no approval" was right about the evidence class and wrong about
the terms, three days after `CLAUDE.md` recorded that `.uk` says the same thing. Both engines
stopped 2026-08-27 07:47 and 07:51; `ark rdap` now refuses `com`, `net`, `org`, `uk`, `ca` and
`nz` in code and needs a named written permission to send one query. Exposure: the class holds
748,099 pairs and 459,792.0 EE, of which only **1,615 pairs and 851.0 EE are unshipped**,
because the rest is already merged into his baseline. Only Nominet's clause reaches USE as well
as collection, so only its 121 unshipped pairs and 118.7 EE are a withdrawal question. **The
route reopens on a written permission of the RIPE kind and on nothing else.**

### the-vps-rdap-journals-nobody-had-banked-priced-at-zero

The VPS RDAP journals nobody had banked, priced at zero (2026-08-27)

**A collector alive for 45 hours writing nothing, and 85 MB of journal that paid 0.00 EE.** The
VPS sibling sweep showed `up 2-16:29` in the process table while its newest journal had last
been written at 2026-08-25 08:51:28 UTC. Six `.part` files, 85,373,766 bytes, were snapshotted
and ingested: 701,225 journal lines, 112,114 records with in-window creation dates, **0 evidence
rows and 0 year rows**, because earlier snapshots of the same files had already been banked and
the queries since had added nothing. Two lessons, both already in `CLAUDE.md` and both
re-earned: presence, progress and yield are three questions, and a `.part` is worth snapshotting
the moment its writer stops rather than when someone notices.

### the-residual-audit-s-unread-flag-priced

The residual audit's `unread` flag, priced (2026-08-27)

**Worth 22.2 EE, not the "cheapest yield in the project" the audit calls it, because it counts
FILES and not value.** Four files matched a documented ingest glob and no ingest had read them.
Three are `us_domain_delegated` captures at 2000-12-06, 2001-02-01 and 2001-04-11, and all three
are **byte-identical to each other** at 435,847 bytes, one md5: the same delegated-zone list
fetched at three instants. The already-ingested 20000815 and 20010606 editions cover those names
at 2000 and at 2001, so the trio adds 24 pairs and 22.2 EE, all from the 2000 capture, and
exactly zero from either 2001 capture. Predicted 24 net-new before ingesting and the ingest
wrote 24 year_rows, so the pricing method is sound and the population is spent. The fourth file,
one `cdx_pool` journal of 9,381 bytes, paid 175 pairs. **Rule: price an `unread` count by
content, not by file count. Duplicate captures of one artifact inflate it, and a second capture
of an unchanged list can only add a year the store may already hold.**

### every-rdap-served-tld-ranked-by-headroom-the-family-closed-on-measurem

Every RDAP-served TLD ranked by headroom, the family closed on measurement (2026-08-27)

**Systematic rather than guessed, and `.ca` is the only one worth a conversation.** The IANA
bootstrap was joined against our own holdings and each TLD priced at held-domains x weight x the
29.3% in-window rate measured on Nominet. Ceilings: `.ca` **25,377 EE**, `.nl` 9,200, `.sg`
4,233, `.br` 3,934, `.no` 3,105, `.cc` 2,443, `.info` 2,322, `.pl` 2,158, `.tw` 2,057, `.fi`
1,968, `.gov` 1,942, `.to` 1,908, `.cz` 1,371, `.ar` 1,260. Everything below `.ca` is under
10,000 and mostly low-weight, so **the family is closed except for `.ca`**: no further endpoint
is worth a licence question. `.gov` publishes no creation date and is already closed. Both live
probes work and both bind use to terms: `.sg` serves `nus.edu.sg` at `('registration',
'1996-09-02T16:00:00Z')` and prints "This data is provided for information purposes only" with
its policy documents linked but unread, so it is filed pending rather than queried, at a ceiling
too small to justify the reading. **`.ca` is live, serves an in-window creation date, and its
Terms of Use forbid the query.** The IANA bootstrap gives endpoints for `ca`, `au`, `in`, `uk`
and `sg`; `.au`, `.in`, `.nz`, `.za`, `.ie` and `.us` were already closed on an earlier probe.
`.ca` was not. One query to `https://rdap.ca.fury.ca/rdap/domain/rita.ca` returns
`('registration', '2001-02-01T17:11:06Z')`, the same `whois_creation` semantics already
approved. Ceiling **~25,377 EE**, from 103,541 held in-window `.ca` domains at `.ca`'s 0.8365
and the 29.3% in-window rate measured on Nominet. **It died on terms, not on evidence.** The
record carries a Legal Notice binding use to CIRA's Terms of Use; that page answers HTTP 403
behind a Cloudflare challenge, so Ivo fetched it from a browser on 2026-08-27 and it forbids
this on four separate grounds: s.10(c) bars any robot retrieving the site "to collect
information about other users or domain names"; s.11 permits WHOIS use "solely" to check
availability, identify a holder or contact a holder; s.11 lists "unauthorised aggregation or
collection of information from the WHOIS database" as prohibited; and s.11 bars "automated
processes that send multiple queries". s.4 licenses content for non-commercial use only, and
this work is paid. **Closed. Reopen only on written CIRA permission of the RIPE kind.**
`robots.txt` is 8 lines, names no agent and disallows only `/wp-admin/`, `/?s=` and `/search/`,
so robots is not the obstacle. Filed as `cira_ca_rdap / whois_creation`, pending, needing either
a human reading of the Terms or a letter of the RIPE kind. `.sg` is untried and worth 31,793
held pairs, far less.

### the-vps-journal-backlog-and-why-the-cycle-undercounted-it

The VPS journal backlog, and why the cycle undercounted it (2026-08-27)

**125 journals had never come home and they were worth 40,893.6 EE, which is more than
everything else this night produced combined.** `just cycle` reported "rsync 2 VPS journals
home"; the real diff between the two machines was **125 files and 416 MB**, 122 of them
`cdx_suffix` sweeps and 3 `cdx_vedge`. Converted with `cdx_suffix_convert.py`, which collapses
capture rows into per-domain year sets and enters as the already-approved `cdx_snapshot /
cdx_timestamp`, they gave 141,013 domains with in-window captures, 122,842 evidence rows and
48,056 year rows. Measured against a pre-ingest snapshot: **50,102 net-new pairs, 40,893.6 EE**,
taking the store from 5.3405% to 5.6514%. **The lesson is about the counter, not the VPS**: the
cycle counts what a documented glob matches on THIS machine, so work finished on another one is
invisible to it until it is copied. Diff the two file lists directly rather than trusting the
count, and do it before spending a single new query, because these were queries already paid
for.

### scholarly-index-sweep-for-deposited-early-web-data

Scholarly-index sweep for deposited early-web data (2026-08-24)

Failed positive control: OpenAlex `early web` returns 314 works and not one is the UMN DRUM
dataset already ingested here. `type:dataset` 1996-2005 with web/URL/domain returns 3,363 works
and no URL corpus; `domain` in scholarly search means protein domain. Route shut.

### the-pre-nominet-and-nominet-uk-register

The pre-Nominet and Nominet `.uk` register (2026-08-24)

The file never existed. 12,491 captures over 2,710 URLs of `nic.uk`, `nominet.org.uk`,
`nominet.net`; largest object ever served is a 94,785-byte membership list, worth 2 net-new
pairs, 1.96 EE. Register exposed only per-name; `members-private/expanded-whois/` is HTTP 401.

### ark-gaps-queue-ranking

`ark gaps` queue ranking (2026-08-24)

Not a source: the bracketed-gap queue, 451,490 domains at a 264,814 EE ceiling, ranks by weight
and returns 31 years from 600 queries (5.2%) against 673 years from 600 on the `.com`-heavy file
it replaced. Reordered to put `.com`/`.net`/`.org`/`.uk` first.

### not-your-parents-web-timemaps-deferral-converted-to-reject

Not Your Parents' Web TimeMaps, deferral converted to REJECT (2026-08-24)

Tested at `1996/..._deeplinks_part00o.tar.gz`, 5,641,617 bytes: 17,035 in-window pairs, 17,006
already held, 29 net-new, 14.2 EE. Folder year is year of first archive, not of content, so the
1996 folder's net-new pairs land in 1998, 1999 and 2001.

### registry-change-reports-across-five-regions

Registry change reports across five regions (2026-08-24)

Paid about 7,500 EE over eight small artifacts (TWNIC 1,275.0, SaudiNIC 1,506.4, NIC Malta
1,470.5, NIC Venezuela 1,131.3, IDNIC 872.6, RESTENA 708.5, ISOC-IL 375.0, `.nu` 144.1). gTLD
side empty: the only in-window listing is `greatdomains.com`, 2,466 owner-submitted records,
about 104 EE after the split.

### national-register-listings-the-ie-shape-across-nine-namespaces

National register listings, the `.ie` shape across nine namespaces (2026-08-24)

Two paid (`.my` MYNIC, `co.za`), six empty on measurement: `.nz` whole Domainz site is 170 URLs
yielding 5 and 1 names, `.au` largest AUNIC page yields 10 names all worked examples, `.ca`
counts only, `.sg` and `.hk` no listing, `.ph` a rolling 30-day expiry window.

### pricing-on-parser-raw-rather-than-canonical-form

Pricing on parser `raw` rather than canonical form (2026-08-24)

`ukwa_geoindex` priced at 4,509.1 EE over 4,595 pairs, admitted at 4,493.0 over 4,591. Joining
`BulkRecord.raw` URLs against `domain_year` finds zero held and returns top TLDs `htm` 2,106,483
and `html` 2,055,761. After canonicalisation 17,912,511 rows collapse to 289,857 pairs, 285,262
already held.

### datacite-sweep-for-deposited-early-web-datasets

DataCite sweep for deposited early-web datasets (2026-08-24)

Eight query shapes against `api.datacite.org/dois` surface nothing not already held: link
list/graph plus web gives 21 hits, the only in-window one the UKWA host link graph; `early web`
gives 19 hits whose only deposits are UMN DRUM and the Zenodo banner ads; `web crawl` 1997-2006
zero.

### nominet-rdap-over-held-uk-banked

Nominet RDAP over held `.uk`, banked (2026-08-24)

Banked, no approval needed. `rdap.nominet.uk` publishes a machine-written `registration` event
with a full timestamp, verified `demon.co.uk` `1996-05-05T21:08:48Z`, reached through the IANA
bootstrap by `ark rdap`. Evidence type `rdap_snapshot / whois_creation`, `Decision: master`
since phase 4. On 400 seeded held `.uk` names read at 157 answers: 29.3% in-window, 19 of 46
pairs net-new, 118.8 EE per 1,000 queries.

### ucsf-industry-documents-library

UCSF Industry Documents Library (2026-08-24)

3,826,999 in-window documents with per-document `documentdate`, and 6,000 fetched give 216 pairs
for 146.6 EE after the corroboration split, because 89% of the net-new names are dated nowhere
else. Whole-population projection about 730 EE post-split.

### organisational-mail-releases-beyond-enron

Organisational mail releases beyond Enron (2026-08-24)

One real member, 67x short: `jeb_bush_gubernatorial_email`, 411,928,998 bytes, 626 born-digital
files, 519,581 in-window `Sent:`/`Date:` headers, 4,011 EE over 6,412 net-new post-split pairs
of which only 1,607.7 EE comes from a `To:`/`Cc:` line.

### generated-rdap-target-populations-and-what-order-to-query-them-in

Generated RDAP target populations, and what ORDER to query them in (2026-08-24, extended
2026-08-27)

Four populations of 1,500 to 3,000 names queried direct to Verisign: English dictionary words
13.5 EE per 1,000 queries (28.00% in-window) but finite at ~235,000 words and 92.4% already
held, sibling TLDs of held names 9.7 (5.64%), random four-character strings 6.3, invented
two-word compounds **0.0** over 859 queries. Siblings won on material: 14,080,169 names against
a dictionary that exhausts in an hour. **The pilot rate does not survive contact with the whole
queue, and the reason is the transferable part.** Measured 47,164 queries into a later run:
**8.2 EE per 1,000**, with the in-window hit rate splitting **7.3-fold** by how many of the six
years the store holds the sibling's BASE label, 7.84% at six years against 1.08% at one, and
**54% of an unranked queue hangs off one-year labels**. A label the archive sees across all six
years belonged to a going concern, and a going concern of that era defensively registered the
other two gTLDs in that era; a label seen once is as likely to be a typo or a parked name that
never had a sibling. `scripts/engines/rank_sibling_queue.py` sorts on that. **And the registry,
not the ordering, is what governs the rate.** Per-minute counts from the journals: the unranked
run held **65 queries a second flat for seventeen minutes** with no decay, then every later run
collapsed to about 1 q/s whatever order it used, including a shuffled run over the same
population. Verisign served **64,568 queries and then clamped for at least twenty-five minutes
across three restarts**, so all three ordering experiments ran inside one quota and none of them
measured ordering. A first reading of this as "ranking loses sixtyfold" was wrong and is
withdrawn. What ranking demonstrably does, being a property of the population rather than the
limiter, is raise the answered-200 share from 18.7% to 74.4% and the in-window rate from 1.80%
to 4.02%. The queue ships shuffled (`--shuffle`), deterministically, and settling whether
ranking pays needs a rested registry. **Rule: a generated population needs an ordering as much
as it needs a generator, and the ordering is measurable from the engine's own answers after an
hour.**

### ukwa-ds-1-classification-list

UKWA ds.1 classification list (2026-08-16)

Recovered from Wayback at `opendata/ukwa.ds.1/classification/classification.tsv`, 3,011,797
bytes over 26,910 rows, and deliberately not ingested: columns are category, title and URL with
no date field of any kind, so it is candidate-pool only, and UKWA's selective archive began
after 2001.

### library-catalogue-records-with-a-marc-856-url-measured

Library catalogue records with a MARC 856 URL, measured (2026-08-16)

47 qualifying records in 48.2 MB of Scriblio give 13 domains, 12 already held, one net-new and
that one a public-suffix subdomain. Dating and URL-bearing are anticorrelated: LC books carry an
in-window MARC 005 on 28.25% of records and hold 67 hosts in 72,588; LC serials hold 3,492 hosts
and carry one on 0.34%.

### search-engine-indexes-1996-2001-the-whole-family

Search engine indexes 1996-2001, the whole family (2026-08-16)

Not one machine-readable dated hostname list survives. AltaVista's May 1999 crawl of 203M URLs
was never published and Yahoo Webscope no longer resolves; six archive.org sweeps over Lycos,
Excite, HotBot/Inktomi, Infoseek, Northern Light and WebCrawler return zero index artifacts. All
three surviving in-window Open Directory dumps are already held.

### ipeds-institutional-characteristics

IPEDS institutional characteristics (2026-08-16)

Of 3,251 domains in `IC99_HD`, 2,946 are already dated 1999, the exact year the file attests,
leaving 147 post-split pairs and 100.8 EE. The web-address column exists for one in-window year
only. `.edu` is 95.5% saturated at the year an institutional directory attests.

### not-your-parents-web-timemaps-ia-nypw-timemaps

Not Your Parents' Web TimeMaps, IA `nypw_timemaps` (2026-08-16)

Deferred on cost: in-window folders total 19,350,762,163 bytes, field 3 of a TimeMap line is a
14-digit capture timestamp so the year is per-record, but the methodology paper
(arXiv:2507.14752) documents downsampling and the sibling `nypw_firstcdx` is already rejected at
53 net-new domains over 6.28M lines.

### parallel-language-records-of-the-early-web

Parallel Language Records of the Early Web (2026-08-16)

No date of any kind in a record: README plus shard 00 (42,290 lines) confirm SURT pattern then
`<lang> <url>`, the only date being collection-level "captured before year 2000". Its 1,164,183
records also select for multilingual mirrors, top tuples `ca-sg` 134,941, `de-en-fr` 89,557.

### rfc-and-internet-draft-documents

RFC and Internet-Draft documents (2026-08-11)

Complete RFC population plus a 12.2% draft sample: 3,605 in-window pairs, 3,151 already held,
140 net-new after the split worth 88.2 EE. The split does not protect against fictional
hostnames, and this corpus is full of them (`acmecorp.com`, `bigco.com`, `widgetco.com`).

### internic-public-zone-files-via-wayback

InterNIC public zone files via Wayback (2026-08-08)

Absent: `internic.net` under `matchType=domain` holds 8,001 captures of which 16 resemble data
and those are single-domain whois lookups; `ftp.internic.net/domain` captures are 435-byte
stubs. Trap: `url=host/path/*` with `matchType=prefix` returns zero even for known captures, so
drop the `*`.

### other-national-web-archives-non-nordic

Other national web archives, non-Nordic (2026-08-08)

Australia's AWA is the only open in-window index and it is IA data: 13 of 13 cross-checked
domains return identical year sets from AWA and the IA CDX, 0 AWA-only pairs, every in-window
row from `NLA-EXTRACTION-1996-2004-ARCS-PART-*`. Japan, Austria, Catalonia, Slovenia, Croatia,
Netherlands, Singapore, Estonia, Switzerland, Germany, Spain and Italy all postdate the window.

### nordic-and-baltic-national-web-archives

Nordic and Baltic national web archives (2026-08-08)

Seven of eight have no public in-window index. Iceland's `vefsafn.is` pywb CDX serves in-window
captures but cannot be enumerated, capping the addressable set at 2,540 known `.is` names: 66
lookups, 0 unknown domains, 867 projected EE. Sweden's Kulturarw3 is reading-room terminal only.

### shareware-and-cd-rom-catalogues-beyond-tucows

Shareware and CD-ROM catalogues beyond Tucows (2026-08-08)

Info-Mac worked to exhaustion: 2,604 domains, 2,477 already held, 234 pairs, 134.15 EE.
garbo.uwasa.fi's master index contains one domain, its own. Trap: an archive.org software scrape
reports 682 net-new domains and all are spurious, 15,399 of 15,521 hits coming from modern
uploader prose.

### research-crawl-datasets-remaining-angles

Research crawl datasets, remaining angles (2026-08-08)

academictorrents 2,851 items with 0 in-window web crawls, `collection:webarchivedatasets`
exactly 8 items, LAW/UNIMI 2 in-window graphs (`cnr-2000` is 325,557 URLs to one domain), CAIDA
no hostname inventory, RIPE Hostcount aggregates only. The parallel-language salvage nets +374
EE and scores negative on the project's own estimator.

### ukwa-per-year-bulk-cdx

UKWA per-year bulk CDX

Not publicly retrievable in 2026: dead host, soft-404 successor, 404 DOI, never
Wayback-captured. Probe the data paths, not the repository front page:
`https://www.webarchive.org.uk/datasets/ukwa.ds.2/cdx/1999.cdx.gz`, with
`linkage/host-linkage.tsv.gz` as the positive control, a file we hold 2 GiB of that returns the
same 159-byte stub. Access requested.

### other-cctld-registry-open-data

Other ccTLD registry open data

Nothing free reaches 1996-2001. CENTR aggregates only, OpenINTEL starts 2015, commercial WHOIS
is paid. Re-checked for a per-domain file carrying both a creation and a withdrawal date:
Nominet, auDA, InternetNZ, CIRA, SGNIC, IEDR, SWITCH and SIDN publish daily feeds, dashboards or
top-N rankings, none per-domain lifecycle. AFNIC `.fr` is the only one and is already banked.

### ukwa-per-year-bulk-cdx-2026-recheck

UKWA per-year bulk CDX (2026 recheck)

Docs survive at `ukwa.github.io/opendata/ukwa.ds.2/cdx/`; the download host serves the same
159-byte stub and the DOI 403s behind Cloudflare. Wayback captured the directory listing but
never the `.gz` files. In-window size would have been about 13.4 GB.

### mailing-list-archives

Mailing-list archives (2026-08-01)

Population is wrong. archive.org's in-window holdings are hobbyist digests (`sf-lovers`,
`GLOWBUGS`); the W3C public lists are small and technical, `www-announce` running for 3 archive
periods, `www-talk` 121, `www-html` 246. A 1997 `www-announce` month carries 53 messages against
the 20,000-plus domains one Usenet commerce group yields.

### archive-org-books-three-collections

archive.org books, three collections (2026-08-05)

`subject:(internet)`: 57 of 60 sampled in-window items publish no downloadable `_djvu.txt`, 2
net-new pairs. `collection:folkscanomy_computer`: 36 of 40 unreachable, 2 net-new pairs from 40
items. In-window book scans largely carry no OCR text layer.

### internet-traffic-archive-web-traces

Internet Traffic Archive web traces (2026-08-06)

`ita.ee.lbl.gov` is alive and the ideal dataset is unusable: UC Berkeley Home IP 1996, 9,244,728
requests, has anonymised URLs, its own format example being `GET 9168504434183313441..gif`.
`BU-Web-Client` has clear URLs and runs 1994-1995, out of window.

### shareware-cd-rom-catalogues-on-archive-org

Shareware CD-ROM catalogues on archive.org (2026-08-06)

archive.org cannot list inside an ISO: `/download/<item>/<file>.ISO/` ends "failed to obtain
file list", so measuring density costs a full ISO download per item, 127 MB to 1,300 MB. The
3,578 `cdbbsarchive` items also carry no `date` or `year` metadata.

### ntp-survey-1999-nelson-minar-mit-media-lab

NTP Survey 1999, Nelson Minar / MIT Media Lab (2026-08-15)

Live index, dead payloads. `alumni.media.mit.edu/~nelson/research/ntp-survey99/data/` is 4,337
bytes of period HTML listing `ntp-survey-1999.tar.bz2` and siblings; the census of 175,527 NTP
hosts is orthogonal to a capture-derived baseline and unreachable.

### dot-com-deadpool-and-failure-lists-2000-2001

Dot-com deadpool and failure lists, 2000-2001 (2026-08-15)

Short life is necessary and not sufficient: a funded dot-com ran a marketing budget and was
captured repeatedly before it folded. The population is celebrated failures, which is authority
selection, and the store holds every one. What pays is short life plus low traffic.

### bruce-guenter-s-spam-archive-untroubled-org-spam

Bruce Guenter's spam archive, `untroubled.org/spam/` (2026-08-15)

312 net-new pairs and 195.5 EE after the split, 16x below the bar. `1998.7z` through `2001.7z`
total 9.3 MB and expand to 20,010 messages each carrying its own `Date` header, but 19,992
in-window messages name only 5,342 pairs over 4,793 domains and 3,203 of those are already held.
**Superseded 2026-08-27: this reading understates the same bytes 6.6x.** Nothing was
MIME-decoded and only the sender side was read; the corpus holds 26,112 domains and 1,288.1 EE.
See the re-price row at the top of this table.

### anti-spam-blocklists-and-blackhole-lists-1997-2001

Anti-spam blocklists and blackhole lists, 1997-2001 (2026-08-15)

Every in-window blocklist is IP-based, not domain-based: MAPS RBL, ORBS, the Dial-Up List and
SPEWS all publish addresses and netblocks, and the output unit is the registered domain. The
domain-bearing variant, spam sightings in `news.admin.net-abuse.*`, is already ingested.

### the-whole-webarchive-org-uk-datasets-tree

The whole `webarchive.org.uk/datasets/` tree (2026-08-15)

The stub is the tree, not the file: `/datasets/ukwa.ds.2/geo/` returns the same 159-byte "400
Redirect" body under HTTP 200 as `linkage/host-linkage.tsv.gz`, a file we hold. The Geoindex
behind it is 700,641,549 lines covering 1996-2010, about 8 GB gzipped, all `.uk`. Another URL
did open it: see `## ukwa_geoindex`.

### alexa-ia-donated-crawl-items-on-archive-org-their-cdx-indexes

Alexa / IA donated crawl items on archive.org, their CDX indexes (2026-08-15)

The bulk index exists and is access-controlled: in-window items carry per-item CDX
(`FS-587676-c.cdx.gz` at 104 MB, a 1999 item at 631 MB) and a ranged GET returns HTTP 401 with a
172-byte body, so the restriction covers the index and not merely the payload WARCs. Reopens
only on an access grant. The 401 is per-collection and does not reach the `webdataservices`
national extractions.

### national-library-historical-web-extractions-on-archive-org-ina-fr-fccn

National-library historical web extractions on archive.org: INA `.fr`, FCCN `.pt`, NLI `.ie`
(2026-08-18)

Enumerated by scraping all 34,841 identifiers containing `HISTORICAL`: `INA-HISTORICAL-*` 49
items, `FCCN-PT-HISTORICAL-*` and `PT-HISTORICAL-*` 31, `NLI-IE-*` 46. Ireland is the only
high-weight one and its earliest item date is 2002. The other two refuse their indexes with HTTP
401 and 403.

### openpgp-keyserver-bulk-dumps-sks-and-hockeypuck

OpenPGP keyserver bulk dumps, SKS and Hockeypuck (2026-08-18)

Nine dump hosts are dead, NXDOMAIN or 404; `pgp.key-server.io/sks-dump/` serves a squatted
1,095-byte redirect stub under HTTP 200; `keys.openpgp.org` publishes no dump by design;
archive.org and Zenodo hold none against a working positive control.

### curated-distribution-keyrings-debian-removed-keys-and-emeritus-gnu-apa

Curated distribution keyrings: Debian removed-keys and emeritus, GNU, Apache KEYS (2026-08-18)

Retrievable, correctly dated and 70x too small. Priced on the UID binding signature over 4,096
items: 1,418 pairs, 1,273 already held (89.8%), 69 net-new pairs, 44.4 EE. `debian.org` alone is
1,033 of the in-window user IDs, and a current keyring garbage-collects departed maintainers.

### x-509-certificate-corpora-with-notbefore-in-1996-2001

X.509 certificate corpora with `notBefore` in 1996-2001 (2026-08-18)

`notBefore` is CA-written into a signed structure and genuinely self-dating; the population
fails. The only retrievable in-window corpus is `hg.mozilla.org`'s 139 revisions of
`certdata.txt`, and a census of its 126 in-window certs gives 1 net-new pair worth 0.6 EE, with
0 of the 126 end-entity web-server certificates.

### machine-written-mail-headers-in-bulk-mailing-list-archives

Machine-written mail headers in bulk mailing-list archives (2026-08-18)

`pipermail` strips the `Received` chain entirely: over 37,789 messages from 2,622 of our own
month files only `From`, `Date`, `Subject`, `Message-ID`, `References` and `In-Reply-To`
survive, and the `Message-ID` host seam is worth 156 net-new pairs and 107.3 EE over the whole
579,808-message corpus.

### web-archives-holding-their-own-pre-2002-crawls

Web archives holding their own pre-2002 crawls (2026-08-18)

Counted rather than hoped: Wikipedia's list of initiatives (109 rows), MemGator's
`archives.json` (20 endpoints) and the IIPC directory (48 permalinks). The Memento TimeTravel
aggregator no longer exists, `timetravel.mementoweb.org`, `labs.mementoweb.org` and
`aggregator.mementoweb.org` all having no DNS record. Of the 13 initiatives created 2001 or
earlier, one is the Internet Archive and three are already closed here.

### kulturarw3-national-library-of-sweden

Kulturarw3, National Library of Sweden (2026-08-18)

The largest IA-free in-window corpus known, and the door is shut: access is on-site only and
"You cannot search freely for a word or subject, but must enter, for example, `www.sf.se`", so
the interface cannot emit an unknown hostname. `kulturarw.kb.se` and `kulturarw3.kb.se` resolve
to `selma.kb.se` and refuse TCP.

### quoted-whois-records-pasted-into-usenet-bodies

Quoted `whois` records pasted into Usenet bodies (2026-08-18)

50x under the bar. Self-dating on the registry's own `Record created on 18-Feb-1998.` line, so
the paste date is irrelevant to the year claimed. Priced from disk at zero network cost over
28.20 GB: 488 pairs, 68.2% already held, 155 net-new pre-split, 95.0 EE.

### the-isi-rfc-1480-us-domain-registry

The ISI RFC 1480 US Domain Registry (2026-08-18)

Four dated in-window editions recovered, and the registry added four names between August 2000
and November 2001, so the legitimate first-appearance diff prices at 1 net-new pair and 0.9 EE,
while dating every name in each edition would have claimed 13,014. Its contact column
re-confirms 97.7% already known.

### another-precomputed-ia-capture-census-in-a-research-repository

Another precomputed IA capture census in a research repository (2026-08-18)

The whole in-window population is four items, three already in this register and one new:
Weber's DRUM deposit `10.13020/D62684`, 74.83 GB in 16 tar parts, measuring 45,130 of 45,130
sampled pairs already held and 1 net-new pair worth 0.63 EE from 226,171 rows. ICPSR, OSF and
Dryad were blank against working controls.

### discmaster-the-index-over-archived-media-contents

Discmaster, the index over archived media contents (2026-08-18)

Works, and the media population is already ours: the deduplicated `.url` population is 125
net-new pairs and 78.9 EE at 95.6% overlap. Bulk endpoint `search?download=true` returns every
match as one tar.gz up to 1 GiB; `robots.txt` says Disallow and carries its own written
exception for limited targeted research automation.

### government-grant-and-award-records-1996-2001

Government grant and award records 1996-2001 (2026-08-18)

Clears the item screen 3.8x over at 456,700 dated in-window items and still dies, because 0.042
pairs per item is a property of subject matter: NSF CSE 0.0471, BIO 0.0152, GEO and TIP 0.0000,
NIH 0.0012 at 164 distinct hostnames in 372,444 abstracts. The contact field is current-state
refreshed under a frozen date, caught by `gmail.com` appearing 61 times on 1996-2001 awards.

### dated-newswire-and-press-release-full-text

Dated newswire and press-release full text (2026-08-18)

Do not sign the NIST agreement. An ungated corpus larger than Reuters RCV1 exists,
`usenet-clari.*` at 22 items and 21,309,542,972 bytes with Business Wire and PR Newswire full
text, and it fails on era: across four group files parsed in full and six censused, the earliest
message is uniformly 2003-06-23.

### machine-written-network-diagnostics-pasted-into-usenet-bodies

Machine-written network diagnostics pasted into Usenet bodies (2026-08-18)

29,040 of 219,447,104 in-window messages carry a diagnostic structure, one in 7,557, capping the
lens at 1,220 pairs against a 5,000 bar. Measured 297 net-new post-split pairs and 165.7 EE,
reduced by a hand audit to roughly 150 pairs and 70 EE for 383 GiB read.

### dated-announcements-of-new-domain-registrations

Dated announcements of new domain registrations (2026-08-18)

Right about dating, wrong about volume: a registry of this era published either dates without
names (statistics, as at `domainz.net.nz/newsstand/stats/` and every InterNIC and NSI
registration report) or names without dates (a zone snapshot).

### discmaster-by-file-size-and-the-april-1998-jp-registry-listing

Discmaster by file size, and the April 1998 `.jp` registry listing (2026-08-18)

The route works and the snapshot is 87.5% already held. `email.domains`, 2,085,500 bytes and
42,701 lines, at `/japan/email.domains` on the `ftp.cs.arizona.edu` mirror, item 19864,
self-dating from its own header "Registered Domains in JP (Apr 30 1998)". `dedup=1` kills the
connection; every other parameter is fine.

### afilias-land-rush-2-schedule

Afilias Land Rush 2 schedule (2026-08-25)

0.00 post-split, because exactly 1 of the 4,257 names is dated anywhere in the store.
`landrush2.afilias.info` resolves at 66.199.183.26 and refuses TCP 80; the surviving fragment,
`onlinedomain.com`'s `LR2-list-of-4257-available-domains.txt` at 82,107 bytes, carries
`"copyrightYear":"2012"` and is the subset still unregistered in 2012.

### the-icann-forum-info-sunrise-lists

The ICANN forum `.info` Sunrise lists (2026-08-25)

A decision for a human at 1,328.60 EE post-split. `forum.icann.org/newtldagmts/` is 7,169
message pages frozen since March 2002; largest item `3C8A91B500002319.html` carries `Date/Time:
Sat, March 9, 2002 at 10:50 PM GMT` and "Listed below are the 6122 names registered at Sunrise
by Worldnic", of which 5,279 parse. Union with WIPO's `.info` Sunrise case index: 7,988 names,
7,284 net-new.

### a-2001-squidguard-blacklist

A 2001 squidGuard blacklist (2026-08-25)

10,736.2 EE, licence GNU GPL v2 verbatim in `COPYING`, and it triggers this register's own
reopen condition. One request to
`archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`, 1,852,659
bytes, yields `samples/dest/blacklists.tar.gz` at tar mtime `Dec 18 2001`, whose files carry the
machine-written header `# This list was compiled in 0:00:20 on 2001.12.18 15:04:29.` and dated
diffs to `domains.20011218.diff`. **The header asserts liveness rather than listing, so no
split: `squidGuardRobot-2.3.4` generated it.** 44,130 canonical names, 18,588 net-new (domain,
2001) pairs.

### the-us-locality-gap

The `.us` locality gap (2026-08-25)

61% dead names: of 9,680 `.us` domains held in window and missing 2001, 6,948 were last seen in
July 1997 and only 1,473 reach 2000, so the addressable share is nearer 3,500 EE than 8,964.65.
Against a control, only 37.65% of the 12,080 `.us` names the ISC 1997 walk attests have any 2001
record, `.com` from the same file 40.31%. Compute headroom from the adjacent year only.

### southern-and-central-europe-ftp-hosts

Southern and Central Europe FTP hosts (2026-08-25)

The host layer is dead, not refusing: of 50 hosts screened, 26 are NXDOMAIN (`ftp.nic.at`,
`ftp.nic.fr`, `ftp.cnr.it`, `ftp.switch.ch`, `ftp.huji.ac.il` among them) and nine resolve but
refuse ports 21, 80 and 443, against a control where `ftp.funet.fi:21`, `ftp.gnu.org:21` and
`ftp.arnes.si:21` were open in the same minutes. Every survivor is a pruned modern distro mirror
with zero netinfo paths. Also shut structurally by RIPE's 1999-02-01 restriction, which covers
`.gr` and `.il`.

### the-2001-2003-frozen-mirror-sweep

The 2001-2003 frozen-mirror sweep (2026-08-25)

Both screened artifacts were already answered: the Edelman whois transcriptions re-found by a
second route price at 741.61 EE against the 2,968.49 EE already banked from a fuller parse, its
independent 2001 slice giving 1,003 held-missing-2001 at 618.71 EE.

### raw-axfr-output-published-openly

Raw AXFR output published openly (2026-08-25)

Surviving editions are 1995 only, **corrected 2026-08-30: a 1999-01-07 edition also survives**
(`ftp.apnic.net/apnic/arin/arin.zones.tar.gz`, above), and it paid 99.7 EE because a reverse
tree names the operators we already hold.
`ftp.ripe.net/ripe/local-ir/inaddrcount/data/193.in-addr.arpa.output.gz`, 2,332,217 bytes and
491,640 lines, is a genuine raw AXFR transcript with 50,141 PTR targets, dated three independent
ways all 1995: HTTP `Last-Modified: Tue, 02 May 1995 21:00:00 GMT`, FTP mtime `03-May-1995
19:36`, and the SOA line `95042701 ;serial (version)` inside the bytes.

### forged-header-corpora-the-lazarus-remailer-logs

Forged-header corpora, the Lazarus remailer logs (2026-08-25)

115.83 EE, because only 1,053 of its 23,102 canonical names are held. The dating is the cleanest
seen here: a complete 12-month 2001 series, 57,368,107 bytes over 13 files, each file's mtime
landing on the last day of the month its filename names, with zero cross-month bleed and an
in-header `Fri Mar  2 00:45:13 EST 2001`. Licence: none found.

### the-2001-threshold-qualified

The 2001 threshold qualified (2026-08-25)

It is a population average, not a universal rate: `WinNetMagCD.chm`, 146,221,869 bytes dated
`2001-12-05 18:11:43` in the ISO9660 directory record, yields 2,334 canonical names of which
2,296 are held and only 157 are held-missing-2001, measuring 95.67 EE or 0.041 EE per name
against 0.31 for a random sample of held `.com`. Head-selected corpora need about 24,000 names.

### the-2001-hunt-five-routes-closed-and-one-prize-sized

The 2001 hunt: five routes closed and one prize sized (2026-08-25)

A full 2001 `.info` register would be worth about 273,600 EE, since the store holds 21,609
`.info` at 2001 against about 750,000 that existed by year end, and it does not survive: ICANN's
Registry Operator's Reports are aggregate counts plus registrar names, the January 2005 `.info`
report yielding 148 bare names in "Section 7" at 145 net-new and 52.90 EE. Correction to a
reported trap: `to_registrable` does not drop a CRLF-terminated name, returning `example.com`
for `'example.com\r'`.

### dns-walk-output-across-the-ripe-region

DNS-walk output across the RIPE region (2026-08-25)

Structurally dead by RIPE's own dated decision, verbatim from
`ftp.uni-erlangen.de/pub/ripe.net/ripe/hostcount/README`, mtime 3 July 2001: `01/02/1999  Access
to the host output files was restricted` and `03/07/2001  Access to the error files was
restricted as well`. The sibling `METHOD` confirms the output was "transferring every possible
Domain Name System zones under the mentioned top level domains". Closes about 14 namespaces
without probing them.

### the-2001-threshold

The 2001 threshold (2026-08-25)

P(store lacks 2001 given domain held): `com` 0.611 (4,264,044 of 6,980,240), `net` 0.653, `org`
0.568, `uk` 0.309, `de` 0.841, `au` 0.406, `ca` 0.478, `nz` 0.545. EE per already-held name in a
2001-dated artifact: `com` 0.386, `org` 0.404, `au` 0.402, `ca` 0.400, `uk` 0.303, `nz` 0.539,
`de` 0.111. So 1,000 EE needs about 2,590 held `com` names, a 32x relaxation of the
curated-directory floor, and it applies only to 2001.

### the-long-running-series-lens

The long-running-series lens (2026-08-25)

An IRR/RADB dump is 97.6% already held and paid 4.44 EE, because 95.2% of its names were already
held in that very year: 13,674 in-window `changed:` lines collapse to 532 pairs of which 25 are
net-new. The screen is held and missing this year. Aim at 2001, not 1996.

### ftp-nluug-nl-refuses-four-claude-agent-names

`ftp.nluug.nl` refuses four Claude agent names (2026-08-25)

`ftp.nluug.nl/robots.txt` lists `ClaudeBot`, `Claude-User`, `Claude-Web` and `Claude-SearchBot`,
each with `Disallow: /`. Also refused and not pursued: `ftp.fu-berlin.de`,
`ftp.uni-stuttgart.de`, `ftp.tu-chemnitz.de`. `ftp.radb.net` serves no HTTP at all.

### nz-port-43

`.nz` port 43 (2026-08-25)

7,586 EE measured and refused by the registry's own terms, which sit about 1,100 bytes into the
same response, after the record. 200 domains from 47,914 held `.nz` names, 123 dated, 122
in-window against 1 out, 0.1600 net-new per held domain, CI 5,177 to 9,995. Read past the record
on any port-43 source.

### the-nw-com-survey-series

The nw.com survey series (2026-08-25)

Complete and fully held: a December 1998 capture of the `nw.com/zone/` listing shows exactly
9507, 9601, 9607, 9701 and 9707, so the survey was semi-annual and there is no 9604, 9610 or
9704 to find. `hosts-per-net` is counts without names. The family already paid 14,956.4 EE, the
best 1996-1997 source in the project.

### promotion-tranche-and-holdings-audit

Promotion tranche and holdings audit (2026-08-25)

1,805 EE banked with no decision, of which the promotion tranche is 2,476 pairs and 1,556.6 EE:
`usenet_mention` 808.5, `usenet_address_mention` 664.7, `usenet_bare_mention` 360.0,
`rtfm_faq_mention` 41.2, `trade_press_mention` 12.6, `enron_email_mention` 0.7. Promotion
compounds off every master ingest, 157 of those pairs being `.ie` because `iedr_register` landed
the day before.

### the-can-domain-classification-ruling

The `can.domain` classification ruling (2026-08-25)

Not a source, a ruling: the CA Domain Registry's notices measure 11,418 pairs and 9,551.2 EE if
the registry self-dates against 936 pairs and 783.0 EE if a human typed it, a 12.2x gap turning
on whether a `Date-Approved:` field printed by the registry is the registry stating its
database. The 936 are banked, so the incremental prize is about 10,482 pairs and 8,768 EE for
zero further collection.

### eric

ERIC (2026-08-25)

Grey literature passes the density screen at 221x formal prose, 1,697 URL occurrences in
5,003,152 words or 0.339 per 1,000 against Hansard's 0.00153, and fails the authority screen at
93.0% of pairs already held. The union holds 184 `.edu` pairs and exactly one survives.

### blocklists-bundled-in-dated-anti-spam-software-on-period-media

Blocklists bundled in dated anti-spam software on period media (2026-08-25)

A new source class. Consumer products shipped their blocklist as a plain data file and hundreds
of 1996-2001 CD-ROMs preserve those files with per-file mtimes on the media, so discmaster's
`tsMin`/`tsMax` filter makes the era screen a query. 24 dated in-window artifacts across five
products, union 2,855 net-new pairs and 1,689.5 post-split EE, of which the licence-clean share
is 1,055.3 EE and the unlicensed 2001 `BlackList` table inside `data.mdb`, 320,099 bytes and
10,088 rows, is 967.1 EE. Worst typo bound on the project at 73.7%.

### the-adversarial-law-refined

The adversarial law refined (2026-08-25)

It pays only if the adversary did not crawl. A period-CD squidGuard list headed `# This list was
compiled in 39:33:10 on 2000.10.18 14:13:23.` is worth 18.2 EE with 38,876 of 39,082 domains,
99.47%, already held, and the same header says why: "compiled from 3405 link sources and 739695
links". Non-crawl channels still win: junkfilter 50.4% held, SpamEater 59.1%, Edelman 25.8%.

### cryptome-org-tbtf-com-www-openpgp-net-refuse-claudebot-by-name

`cryptome.org`, `tbtf.com`, `www.openpgp.net` refuse ClaudeBot by name (2026-08-25)

`cryptome.org` 403s robots.txt itself and 403s on the ClaudeBot token specifically: same URL,
same minutes, curl default UA 200 and 114,247 bytes, honest project UA 200 and 114,247,
`ClaudeBot/1.0` 403 and 159 bytes. Not evaded by changing UA. `marc.info` is `User-agent: * /
Disallow: /`.

### abandoned-part-journals-local-half

Abandoned `.part` journals, local half (2026-08-25)

919 EE banked. A collector killed by a deadline, a signal or a crash never renames its journal,
so its work sits where no glob matches: the paused local collector's
`cdx_pool_20260824T142945Z.jsonl.gz.part` held 579 queried, 575 answered, 758 year-records.

### a-2003-whois-transcription-on-an-abandoned-academic-page

A 2003 whois transcription on an abandoned academic page (2026-08-25)

2,968.49 EE over 4,747 net-new pairs, no licence at all. Ben Edelman's three listings on Harvard
Berkman Center space, 81 pages, 13,507,154 bytes, 15,990 entries, 8,787 dated. **Each record
carries its own `Dates of creation / last modification / expiration: 27-Feb-2000 / ...`,
transcribed from registrar whois, under the page's own "All data is as of January-October
2003".** Human-typed transcription, so it takes the corroboration split.

### the-reciprocal-traffic-industry

The reciprocal-traffic industry (2026-08-25)

The blocklist inversion does not generalise: the two traffic-derived artifacts reachable off
Wayback measure 99.55% and 98.39% already held, worse than the 87-99% curated band, because a
visitor log's hostname field is reverse DNS and the long tail resolves to its ISP
(`splitrock.net`, `pacbell.net`, `prodigy.net`).

### blocklists-as-a-lens

Blocklists as a lens (2026-08-25)

Already-held on a blocklist is about 50% (junkfilter 50.4%, SurfWatch 49.7%) against 87.5% to
99.8% on every authority-selected corpus, because a blocklist selects for what somebody wanted
to block. `junkfilter_dated_blocklist` found and in the queue at 2,189.4 EE: Gregory Sutter's
procmail filter at `junkfilter.zer0.org/pkg/`, 13 ISO-dated in-window editions plus two 1997
tarballs, about 900 KB, dated three independent machine-written ways that agree, with 42,005 of
42,034 tokens domain-shaped. CyberNOT is dead in DNS; the surviving peacefire mirror's
1,000-name list is 32.2 EE; `discmaster_by_file_size` closed at 185.3 EE.

### 1999-internic-zones-on-the-jpnic-mirror

1999 InterNIC zones on the JPNIC mirror (2026-08-25)

179.8 EE, banked, needing no decision. `tomocha.net/files/dns/` holds `gov.zone`, `edu.zone` and
`root.zone`, all filed 2002-02-26, **and the file date is not the artifact's date: `gov.zone`
carries SOA serial `1999111901` and the other two `1999112000`, inside the payload**, with
`gov.zone` ending on InterNIC's own `;End of file.` marker. `gov` 784 pairs at 1999, 601 held,
183 net-new; `edu` 5,850 pairs, all already held.

### stranded-rdap-journals-on-the-vps

Stranded RDAP journals on the VPS (2026-08-25)

3,599.2 EE banked over 5,877 net-new pairs, the oldest sitting since 22 August, because
`maintain.sh` rsyncs `rdap_*.jsonl.gz` and `cdx_*.jsonl.gz` and never `*.jsonl.gz.part`. Five
abandoned partials, 62 MB, 502,293 readable records, 110,499 in-window creations, 104,622
already held.

### the-frozen-mirror-rule-applied-a-second-time

The frozen-mirror rule applied a second time (2026-08-24)

The surviving registers are on personal pages, not institutional ones. Found and admitted:
JPNIC's own `.jp` register at 30 April 1999, `https://tomocha.net/files/dns/domain-list.txt`,
6,185,475 bytes, `Last-Modified: Fri, 30 Apr 1999 04:43:08 GMT`, repriced from the bytes at
72,704 names, 45,877 already dated 1999, 26,827 net-new pairs, 1,623.0 EE. Withdrawn on the
`tomocha.net` by-name robots refusal above.

### integrity-audit-over-every-held-gzip

Integrity audit over every held gzip (2026-08-24)

`gzip -t` over all 6,168 `.gz` files in `data/raw` outside the Usenet trees, 10.8 GB: 39 fail
and every one is accounted for. 21 under `probes/` are deliberate prefix samples at exactly
65536 and 50000 bytes; of the real 18, `ukwa/host-linkage.tsv.gz` is the archive's 2 GiB replay
ceiling, six are `cdx_suffix` journals already measured at net-new zero, and `odp/c2000.gz` is a
known truncated partial.

### the-1999-ripe-database-on-a-document-mirror

The 1999 RIPE database on a document mirror (2026-08-24)

90,799 EE, not banked because of its own copyright header. FUNET mirrored RIPE's whole document
tree into `/pub/netinfo/` and stopped updating, so the mirror froze holding the pre-GDPR
original: `http://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz`, 71,919,736 bytes,
`Last-Modified: Tue, 03 Aug 1999 21:27:00 GMT`. Integrity: `gzip -t` clean, 20,528,780 lines,
its own `# 990804 00:07:01` on line 2 and its own `# EOF` terminator.

### data-raw-usenet-new-50-gb-unseen

`data/raw/usenet_new/`, 50 GB unseen (2026-08-24)

`ingest_new_usenet.sh` reads `DIR="data/raw/usenet"`, so 7,531 archives and 50 GB in
`data/raw/usenet_new/` were never looked at. Measured over 4,052 MB and five hierarchies: 57,913
dated pairs, 57,847 already held, 99.89% saturation, 66 net-new pairs and 35.8 EE. `bit` and
`linux` gave 0 over 207 MB.

### zone-files-off-the-internet-archive

Zone files off the Internet Archive (2026-08-24)

Nobody archived scratch. Three organisations transferred exactly the data wanted and all three
published only the aggregate or the current state. The six InterNIC zones survive because they
sat in a document mirror alongside RFCs, so the productive question is which registry filed its
zone next to its documents. RIPE NCC Hostcount is the most valuable negative of the session.

### ftp-isc-org-disallows-everything

`ftp.isc.org` disallows everything (2026-08-24)

`ftp.isc.org/robots.txt` returns `Disallow: /` for all agents. The ISC survey finding it
produced stands and the held `isc_survey` data came from other routes, but no further request
may go there. Read robots.txt before the first request and record the read.

### mailing-list-subscriber-populations-refuted

Mailing-list subscriber populations, refuted (2026-08-24)

A participant population does not give one domain per participant, it gives one per employer or
ISP: 15,968 IETF senders collapse to 1,713 domains (9.3:1), 16,051 r-help senders to 1,053
(15.2:1), 6,118 FreeBSD senders to 1,627. Measured 0.00106 EE per in-window message post-split,
so 1,000 EE needs about 944,000 in-window messages on one unmined host and nothing reachable is
that big.

### data-raw-cdx-suffix

`data/raw/cdx_suffix/` (2026-08-24)

Worth exactly 0. The suffix sweep writes two journals per batch and only the per-domain form at
`data/raw/cdx/cdx_suffix_*.jsonl.gz` is needed; the raw capture form here, 58 journals and
389,393,904 bytes over 46,779,589 lines, is the same observations in a shape nothing reads.

### national-web-archive-indexes-three-new-doors

National web-archive indexes, three new doors (2026-08-24)

All three price below 1,000 EE, because a national archive's in-window holding is either an IA
back-file donation we hold or a curated slice of institutions the baseline holds first. Library
of Congress US Elections Web Archive, `data.labs.loc.gov/us-elections/by-year/2000/`, enumerable
from `manifest.txt`, 3,521 gzipped SURT CDX files at 1,971,201,167 bytes, robots 404, genuinely
not IA-derived. NLA ships taxonomy graphs with no hostnames; LAC Canada has 64 datasets and none
is a web index; Memento aggregators are NXDOMAIN. The UKWA open-data inventory is exhausted end
to end.

### arquivo-pt-robots-txt-breached

`arquivo.pt/robots.txt` breached (2026-08-24)

Line 752 carries `Disallow: /datasets` inside the `User-agent: *` block with `Crawl-delay: 5`,
and only two agent blocks exist. Ten ranged GETs against `/datasets/linkgraphs/` breached it,
and the same path disallows the original collection of `arquivo_ia` and `arquivo_roteiro` from
`/datasets/cdxj/`. The data is held and the evidence stands; no further request may go to
`arquivo.pt/datasets`.

### the-ukwa-host-link-graph-truncation

The UKWA host link graph truncation (2026-08-24)

Truncated by the archive, not by our download, and not resumable from this host. The local copy
is exactly 2,147,483,648 bytes, `gzip -t` fails with "unexpected end of file", and the Wayback
`id_` capture reports `content-range: bytes 0-0/20928588915`, so 10.26% of a master-eligible
source has been read and that tenth paid 231,865 evidence rows over 183,515 domains and 116,467
assigned pairs.

### internic-zone-files-at-the-nic-mil-mirror-admitted

InterNIC zone files at the `nic.mil` mirror, admitted (2026-08-24)

**Master, on the artifact alone: the SOA serial `1997041800` sits on line 2 inside the payload
and the IA capture of 1997-04-20 fixes when the file existed. An NS record in `.org` is the
delegation itself, the registry serving that name at that instant, so killer 2 does not reach a
zone file.** All six zones re-verified, `gzip -t` passing and each ending on InterNIC's own
`;End of file.` marker: `org` 154,141 lines, `edu` 12,132, `gov` 1,805, `mil` 301 at serial
`1997041700`, `root` 1,316, `arpa` 35. Ingested at 12,503 net-new pairs and 8,993.1 EE, of which
12,320 are 1997 under serial `1997041800` and 183 are 1999 from a `gov` zone at serial
`1999111901`, with 4,889 of the net-new names dated at no in-window year at all.

### more-internic-zone-files-and-ftp-internic-net-domain

More InterNIC zone files, and `ftp.internic.net/domain/` (2026-08-18)

The population is six and we hold all six, so `internic_zone` cannot be widened. One CDX listing
of `nic.mil/oroot.html/` returns the complete contents: `arpa` 694 bytes, `mil` 3,265, `root`
10,219, `gov` 16,251, `edu` 110,995, `org` 1,318,217, summing to 1,459,641 against 1,458,311 on
disk. There is no `com.zone` or `net.zone` anywhere on the mirror.

### the-au-registry-family-aunic-auda-aarnet

The `.au` registry family: AUNIC, auDA, AARNet (2026-08-18)

Does not survive in bulk. AUNIC's archived footprint is 1,605 captures whose only domain-bearing
shape is `aunicstatus.pl?domain-name=<name>`, extractable free from the CDX index: 104 such
captures yield 17 distinct `.au` names. A capture of a lookup would be candidate-only in any
case.

### cdx-public-suffix-sweep-as-a-bulk-channel

CDX public-suffix sweep as a bulk channel (2026-08-22)

Demoted from channel to trickle. Twelve swept suffixes, 159 MB of journal, reduce to 68,386
in-window registrable pairs of which 5,722 are net-new, worth 4,800 EE, and every net-new pair
is `.ca` or `.us`: `co.uk` and `ac.uk` are saturated. The ceiling is structural, because the
bare TLD is HTTP 403 so `.com` cannot be enumerated this way.

### common-crawl-domain-vertices-as-rdap-candidate-supply

Common Crawl domain vertices as RDAP candidate supply (2026-08-22)

Admitted as a thin but genuine channel: not a dating source but a bulk supply of names to ask
the registry about, our own RDAP engine supplying the date.
`cc-main-2020-jul-aug-sep-domain-vertices.txt.gz` is HTTP 200 at 655,075,092 bytes and holds
88,591,818 domains in reversed-label form, of which 44,321,990 are registrable `.com`/`.net` and
40,989,363 are in neither the store nor the RDAP asked-ledger. A 19,987-query pilot answered
11,268 and returned 138 in-window pairs, 0.69% of queries.

### common-crawl-2018-minus-2020

Common Crawl 2018 minus 2020 (2026-08-22)

A real but small enrichment. The 2018 vertex file is HTTP 200 at 523,819,137 bytes holding
35,882,170 registrable `.com`/`.net`, of which 11,019,564 are absent from the 2020 file. A
19,918-query pilot gives 1.11% of queries returning an in-window creation date against 0.69%, a
1.6x gross lift, and 4.7 EE per thousand queries against 4.2, a 1.12x net lift.

### a-registration-span-from-an-rdap-creation-date

A registration SPAN from an RDAP creation date (2026-08-23)

Forbidden by rule 6 after being measured, and it is the largest thing this project has priced:
applied to the 3,174,957 banked in-window creations the span would claim 11,038,108 pairs, of
which 2,885,782 are net-new, worth 1,704,843 EE. Rule 6 holds that a creation date alone does
not establish continued registration in any subsequent year.

### link-target-as-a-ranking-signal-for-the-archive-queue

`link_target` as a ranking signal for the archive queue (2026-08-23)

Admitted, needing no new approval, at 297 EE per 1,000 queries: it changes who we ask rather
than what counts as evidence, since the resulting capture is `cdx_timestamp`. `link_target`
stays candidate-only, 4,115,694 rows. Against the reviewer's own baseline, a link's year is
confirmed 85.3% of the time.

### ripe-database-bulk-dumps

RIPE database bulk dumps (2026-08-23)

GDPR dummification closes it, and the reason generalises to every RIR. On the full
`ripe.db.mntner.gz` file, 64,310 objects, exactly one distinct email domain survives,
`ripe.net`, appearing 120,470 times, every object carrying a "all data that is generally
regarded as personal data has been removed" notice. Only 219 objects have a `created:` date.

### the-darkened-dartmouth-nber-metadata-item

The darkened Dartmouth/NBER metadata item (2026-08-23)

It reopened and is worth zero. `archive.org/metadata/DARTMOUTH-NBER-RESEARCH-2017-metadata` now
returns a 13-file listing with no restriction, and `domain-year-captures.txt` is 227,919,677
bytes, byte-identical in size to the copy on disk; the siblings are the same data plus two
out-of-window rows, with identical 765,194 in-window distinct pairs. Through the canonical
funnel, 764,982 canonical pairs and 0 net-new.

### zenodo-banner-ad-corpus-zenodo-org-records-8408539

Zenodo banner-ad corpus, `zenodo.org/records/8408539` (2026-08-23)

Real, in-window, correctly shaped and too small. A 215 MB JSON of 22,915 banner images mined
from archived snapshots of URLs taken from six printed directories published 1999-2001, **each
`appearances` entry carrying a 14-digit Wayback timestamp beside the page URL, so a pair is
`cdx_timestamp` and self-dating**. 92,218 in-window appearances become 12,353 pairs over 7,600
domains and 934 net-new pairs worth 432.81 EE.

### afnic-fr-opendata-back-editions

AFNIC `.fr` OPENDATA back editions (2026-08-23)

The mechanism is wrong: measured on 202011 (494,444,288 bytes) and 202201 (549,508,248 bytes),
taking only the creation year as rule 6 requires, each yields exactly the same 65,268 in-window
rows, because OPENDATA is a snapshot of names currently registered at publication, so a domain
deleted before 2020 appears in neither. Union 65,170 pairs, 57,511 already assigned, 7,659
net-new worth 781.98 EE. A back edition only helps when the publication is a cumulative register
rather than a current-state snapshot.

### sec-edgar-beyond-the-closed-row-8-k-def-14a-10-ksb

SEC EDGAR beyond the closed row: 8-K, DEF 14A, 10-KSB (2026-08-24)

Real, in-window, dated by EDGAR itself and too small at 5,884 net-new EE, 2.0% of the gate.
**One filing is dated by the `Date Filed` column of `full-index/<year>/QTR<n>/form.idx`, an
EDGAR-assigned date, filtered before extraction**: 222,232 filings of these three types in
window. The best-value unbuilt source on the register, and not a round.

### federal-audit-clearinghouse-historic-single-audit-filings-1998-2001

Federal Audit Clearinghouse historic Single Audit filings 1998-2001 (2026-08-24)

Admissible and small: 2,406.69 net-new EE. **One item is one e-mail field on one filing row,
dated by that row's own signature date, `AUDITEEDATESIGNED` or `CPADATESIGNED`**, which is a
date a human wrote down, so it takes the corroboration split. The date check bites: the
signature histogram runs 1997-2009 and 18,698 e-mail rows were dropped for falling outside the
window, most of them FY2001 audits signed in 2002. Taking the audit year instead would have
imported every one silently.

### uk-companies-house-bulk-corporate-filings

UK Companies House bulk corporate filings (2026-08-24)

Out of window by construction: the Accounts Bulk Data files are named by publication date and
the published range does not reach 1996-2001, and the Company Data Product is a current-state
snapshot with no per-row filing date and no website field.

### reuters-rcv1-newswire

Reuters RCV1 newswire (2026-08-27)

Not fetchable and screened at a few hundred EE, so the signature is not worth chasing.
`trec.nist.gov/data/reuters/reuters.html` distributes it only by written request and signed
agreement. Two independent bounds: the corpus spans 1996-08-20 to 1997-08-19, so it dates ONLY
1996 and 1997, where the store's adjacent headroom is 103,953 pairs against 6.7M at
2000-to-2001; and newswire is formal prose, which measured 0.00153 URLs per 1,000 words on
Hansard, putting 806,791 stories of about 186M words in the hundreds of URLs, nearly all head
names already held.

### discmaster-textfiles-com-as-a-class-rather-than-a-query

`discmaster.textfiles.com` as a CLASS rather than a query (2026-08-27)

Priced at **1,055.3 EE**, which is the lens's whole yield: one banked-pending artifact
(`antispam_media_blocklist`) and a `.jp` listing rejected at 185.3, against an index of
1,718,970,121 files already recorded saturated by filename and by size. Its robots.txt is
`User-agent: * / Disallow: /` followed by a note exempting researchers making "somewhat limited
or somewhat targeted" requests, so a sweep is refused by the directive and a targeted query is
all the note allows.

### the-ia-web-data-services-extraction-family-both-arms

The IA "Web Data Services" extraction family, both arms (2026-08-27)

Priced and closed, and it is law 1 measured on the corpus most likely to beat it. The ccTLD arm
is one member: `Poland_pl-ccTLD_2001-12-31`, 19 items of about 10.8 GB, `access-restricted-item:
true`, and `.pl` weighs 0.107. The in-window value is its `earlygovweb` sibling
`USFEDGOV-EXTRACT-1996..2001`, public, with a 0.5 MB `.arc.os.cdx.gz` beside every 100 MB ARC so
a year prices without touching a payload. **1996, all 99 parts: 647,995 CDX rows every one
stamped 1996, 2,660 hosts, 287 registrable domains, all 287 already held at 1996, zero
net-new.** 2001, 253 of 5,802 parts: 2,158,981 rows all stamped 2001, 11,369 hosts, 735
registrable domains, 633 held at 2001, 102 net-new pairs and 100.2 EE self-dating, and the
domain space saturates hard enough (25 parts gave 452 domains, 253 gave 735) that the whole 754
GB item is a few hundred EE at the ceiling. A 754 GB extraction of the 2001 federal web, dated
by the archive's own stamp, at 0.9825 per pair, pays nothing because the baseline came from the
same archive.

### the-wayback-availability-endpoint-as-a-second-dating-engine-and-the-2-

**The Wayback availability endpoint as a SECOND dating engine, and the 2.4M undated pool it was
aimed at (2026-08-30)**

**FIND on the ENGINE at 1,494 EE/hour, CLOSED on the TARGET at 114 EE/hour, 99.52 net-new
post-split EE in hand, and PARKED on the two-client cap.**
`https://archive.org/wayback/available?url=<domain>&timestamp=YYYYMMDD`, JSON at 100 to 260 B;
what dates one item is `archived_snapshots.closest.timestamp`, the 14-digit capture stamp the
Wayback index wrote when the crawler fetched the page, and never the top-level `timestamp` the
caller echoed in. 1,798 requests, 1,786 200s, 12 `429` honoured, `web.archive.org/cdx` never
touched; `archive.org/robots.txt` is 238 B and 12 lines, read whole first, one `User-agent: *`
group disallowing only `/control/` and `/report/` and no Claude-named group. **Rate
independence, the load-bearing claim, holds**: 1,600 requests at 2 workers took 1,261.8 s =
**1.27 q/s at 0.67% throttled, measured in the same minutes both cdx collectors were running**,
against `cdx_gtail`'s own log at 600 queries per 32.5-minute batch = **0.308 q/s at 27.3%
throttled** (batch starts 11:26:41, 11:59:14, 12:33:46, 13:05:19, and 13:38:26 confirms the
cadence), so one availability client is **2.06x both cdx collectors combined** on a budget that
did not throttle while theirs did. Graded against cdx ground truth already on disk with no new
cdx requests: 204 cdx year-pairs over 150 domains, 187 recovered = **91.7% recall, 94.3% at
2001, and 40 of 40 cdx-negative domains came back empty**. **The hypothesis's target is dead**:
the undated pool is 2,410,144 domains and **98.4% of it is `usenet_address_mention` (1,216,749),
`usenet_mention` (1,034,270) and `usenet_bare_mention` (120,466)**, all four counts reproduced
here; 600 distinct domains at 19990101 gave 31 in-window (5.17%) against 97.5% on 40 interleaved
controls = 0.0264 EE per query, **114 EE/hour, closed**, and the 214,959 `.edu` / 186,965 `.mil`
/ 186,076 `.gov` names in it against a real `.mil` namespace of about ten thousand say why: it
is anti-harvester munging and Message-ID parse noise, not names. **Re-aimed it is 13.1x
better**: 6,568,275 domains held at 2000 and missing 2001 (4,137,392 in com/net/org/uk,
re-measured here, not the 4,256,799 first claimed), 240 sampled by hash order at ONE query
pinned to 20010701, **132 hits = 55.0% = 0.3459 EE per query = 1,494 EE/hour** over a queue
worth ~1.43M EE gross. Priced against the live store over all journals: 415 capture pairs on 335
domains **sampled as DOMAINS, never as `domain_year` rows**, 251 already held (the
by-construction trap, those journals are ingested), **164 net-new, every one at 2001, 99.52
EE**, no split because a capture stamp is master evidence. Two defects reproduced and both make
a zero a lower bound and never a false year: status-200 captures only, and `www.` canonicalised
away. **Nothing was retained and nothing is ingested**: banking any of it means standing a third
bulk archive client against a rule that caps them at two, so it parks as
`wayback_availability_2001` pending Ivo. **The 2.06x rate ratio is the WRONG statistic and is
corrected here, in both directions.** cdx returns a whole year set per query and availability
pinned at 2001 returns at most one year, so in GROSS in-window pairs per hour cdx WINS, 1.583
pairs per query x 0.616 q/s = 3,511 against 2,515. But priced in NET-NEW EE the order reverses:
1,200 `cdx_gtail` queries out of the 10:33 and 11:05 journals, which are **not yet ingested**
(the last ingested is 09:26, so this is a real pre-ingest snapshot and not the by-construction
trap), gave 1,900 in-window pairs of which 1,386 were already held, **514 net-new pairs and
324.90 EE = 0.2707 net-new EE per query = 600 net-new EE/hour for both cdx collectors
combined**. Availability is **0.3459 net-new EE per query and 2.5x cdx per hour**, and it wins
per query as well as per second because its queue guarantees a hit is net-new while cdx's does
not: 73.0% of what cdx returns is already held. The per-query win is narrow, 132/240 is 55.0%
+/- 6.3% so the lower bound is 0.306 against 0.2707, and the two queues are not identical. **So
the cost of the ruling is now a number: retiring one cdx collector costs 300 EE/hour and buys
1,494.** Five methods, in `discovery.md` order of use: prove a second endpoint is a second
budget by running it WHILE the first is throttled and comparing throttle rates, 0.67% against
27.3%; **price a proposed collector against the incumbent in net-new EE per QUERY off an
un-ingested journal, never in q/s, because rate and gross pairs mislead in opposite directions
here**; grade a dating engine against cdx journals already on disk, since
`data/raw/cdx/*.jsonl.gz` is a free labelled set whose NEGATIVES are what turn "it answers" into
"it does not invent"; price a candidate pool by `GROUP BY discovered_source` before pointing
anything at it, which predicted the 5.17% from one query; and the unit is one query pinned at
20010701, not a six-year enumeration (0.208 pairs per query) and not a midpoint screen.

### reading-reviewer-benchmark-release-diffs-to-fingerprint-other-contribu

**Reading reviewer benchmark-release diffs to fingerprint other contributors' sources
(2026-08-31)**

**FIND, 0 EE from the diff itself (already merged by construction).** `comm -13` across 11
consecutive `feedback/**/merged*` releases named three populations worth pursuing: UMN DRUM
`EARLYWEB_1996_2000` parts 01-02 (3.72 GB unfetched, projected ~50,000-103,000 EE), a
`verified_submission_0817` contributor, and an unidentified 2001-dated all-`.co.uk` register
listing of 58,546 names (~57,451 EE) inside the 260820->260821 increment.

### rdap-liveness-tiebreaker-for-the-query-queue-verified-and-patched-but-

**RDAP-liveness tiebreaker for the query queue, verified and patched but not wired
(2026-08-31)**

**FIND, 0 EE banked (a ranking method, not a source).** Verifies the `sources.md:590` finding:
99.851% of the `.com` gap population already carries an RDAP verdict, 61.775% live, reproducing
the banked figures to within 0.05pp. Worth +97 to +161 EE/collector-hour on the gap arm; a full
three-file patch to `build_query_queue.py` is written in the finding but not applied (write
barrier).

### nypw-timemaps-re-priced-on-the-2000-partition-instead-of-the-saturated

**NYPW TimeMaps, re-priced on the 2000 partition instead of the saturated 1996 one
(2026-08-31)**

**FIND at 4,146.8 net-new post-split EE over 6,424 pairs**, reopening a 2026-08-24 closure (14.2
EE) that tested only the 1996 folder.
`https://archive.org/download/nypw_timemaps/2000/nypw_timemaps2000_deeplinks_part00o.tar.gz` and
`.../rootURLs_part02r.tar.gz`; what dates one item is field 3 of each TimeMap row, IA's own
14-digit capture stamp (`cdx_timestamp`). Folder year = first-capture year, so 1997-2000 folders
add years to domains the store already holds; 1996 and 2001 folders are dead by construction
(already tested).

### whois-server-and-tld-registry-index-file-census-discmaster

**Whois-server and TLD-registry-index file census, discmaster (2026-09-01)**

**FIND at 9.7 EE post-split, parked pending, not banked**: fails standing-rule condition 2
(dating is a media mtime `discmaster` renders, not a stamp written into the artifact's own
bytes).
`discmaster.textfiles.com/search?q={whois.conf,whois-servers,tld_serv_list,whois.txt}&qfields=name&mode=deep&tsMin=19960101&tsMax=20011231`,
complete 14-file in-window population. 880 pairs over 468 domains, 22 net-new post-split, all
2001, 79.3% one-edit-from-held (figure is an upper bound).
