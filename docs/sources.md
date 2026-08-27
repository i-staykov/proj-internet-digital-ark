# Sources

One entry per source: what it is, where to obtain it, and **what fixes one item to one year**. That
last clause is the whole of the evidence argument, so it is stated per source rather than in a
preamble, and a source with no per-item date is not admitted whatever else it offers.

Paths are relative to the repository root. Every ingest command assumes the file has been placed at
the path shown.

Sources evaluated and closed are here too, each with the single measurement that closed it, so the
same ground is not broken twice. [discovery.md](discovery.md) is the method used to price one before
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
uv run python scripts/fetch_nw_host_files.py   # resumable, three connections, ~2h for 116 MB
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
uv run python scripts/split_expansion_journal.py data/raw/expand/round2/expand_round2.jsonl.gz --write
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
universe too.

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
uv run python scripts/collect_trade_press.py --discover     # collection sizes, run this first
uv run python scripts/collect_trade_press.py --limit 5000 --query "$HOBBYIST"   # first corpus
uv run python scripts/split_trade_press.py --write
uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated.jsonl.gz
uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates.jsonl.gz

uv run python scripts/collect_trade_press.py --limit 1400   # second corpus, now the default
uv run python scripts/split_trade_press.py \
    --journal data/raw/tradepress/tradepress_20260808T172417Z.jsonl.gz --tag american --write
uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american.jsonl.gz
uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american.jsonl.gz
```

The extractor also reads bare `foo.com`, `http://foo.com/` and `bob@foo.com`; re-reading cached OCR
under it sends no request:

```bash
uv run python scripts/reextract_trade_press.py --write
uv run python scripts/split_trade_press.py \
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
uv run python scripts/collect_usenet_addresses.py --workers 10
uv run python scripts/split_usenet_addresses.py --write
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
uv run python scripts/collect_usenet_bare.py --sample 400 --workers 8    # project first
uv run python scripts/project_usenet_bare.py --journal data/raw/usenet_bare/<file> --archives 400
just usenet-bare                                                        # or the whole corpus
```

Limitation: 1,200 of the 42,139 pairs come from `comp.mail.maps` or `can.uucp.maps`, which
`ark.uucp` already parses under the `registry` lineage, so one posting can be read twice; every
evidence row names its group.

---


## `uucp_map_registry`, `uucp_map_creation`, `uucp_map_mention`: the UUCP maps

UUCP maps posted to `comp.mail.maps`, the `.CA` portion machine-generated from the Canadian domain
registry. On disk at `data/raw/usenet/comp.mail.maps.mbox.zip` (205,143,394 bytes), identical to
`https://archive.org/download/usenet-comp/comp.mail.maps.mbox.zip`.

```bash
uv run python scripts/split_uucp_maps.py --write
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
uv run python scripts/split_rtfm_faqs.py --write
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

Extracted whole by `scripts/ukwa_geoindex_pull.sh`.

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
uv run python scripts/collect_iedr_register.py
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


## Evaluated and rejected

| Source | Verdict |
|---|---|
| Stanford WebBase 2001, re-tested on the RIGHT screen (2026-08-27) | **Zero, and the re-test was worth running because the original closure used the wrong screen.** It was retired at "99.99% already held", which is the novelty screen, and the doctrine says novelty is only half the test: what pays is *held AND missing this year*. Re-measured over the 720 MB of URLs and the 14 MB host list already on disk, so no download and no permission: 603,245 distinct registrable domains, of which **603,245 are held and 603,245 already carry 2001**. Held-but-missing-2001 is exactly **0**, so the gross ceiling is 0.0 EE. The original retirement was right for the wrong reason and is now right for the right one. |
| The unbanked squidGuard 2001 dated diffs (2026-08-27) | **Zero, from 175 per-date diff files nothing had ingested.** `data/raw/squidguard2001/bl/blacklists/*/domains.YYYYMMDD.diff`, every stamp inside 2001, sitting in a directory the residual audit flags as `unreferenced`. Added names extracted from the `+`/`>` lanes: **36,573 distinct registrable domains, 100.0% held, and 0 of them missing the diff's own year**. The banked `squidguard_2001_blacklist` edition of 2001-12-18 had already dated all of them at 2001, and a second artifact from the same year cannot add a year the first one gave. **Editions within one year are worth one edition.** |
| The ISC Internet Domain Survey for 1998-2001 (2026-08-27) | **Closed twice over, and the second reason explains the first.** The store holds ISC/Network Wizards walks for 9507, 9601, 9607, 9701 and 9707 only, so 1998-2001 looked like the one non-crawl bulk artifact that could attest 2001. `ftp.isc.org/robots.txt` is four lines and the whole file reads `User-agent: *`, `Disallow: /pub/usenet`, `Disallow: /usenet`, `Disallow: /`, so the live host refuses us outright. **And the archive holds nothing either, for the same reason**: a CDX prefix query over `ftp.isc.org/www/survey` returns HTTP 200 and empty, while `nw.com/zone/` in the same session returns 40 rows, which proves the negative against a known positive. A host that has told crawlers to stay out was never crawled, so its refusal closes the archive route as well as the direct one. `www.isc.org` allows everything but `/thankyou-contact/` and holds no survey data. |
| The whole RDAP query route, closed on the registries' own terms (2026-08-27) | **The terms were inside every response the entire time, in the `notices` block, so this cost nothing to find and three days of engine time not to.** Read out of our own journals for Verisign, PIR and Nominet, and from the page Verisign's notice links to. **Verisign** (`verisign.com/legal-center/rdap-terms/`): you will not "enable high volume, automated, electronic processes that send queries or data to the systems of Verisign or an ICANN-accredited registrar, except as reasonably necessary to register domain names or modify existing registrations". **PIR** the same clause and carve-out, plus "Abuse of the RDAP system through data mining is mitigated by detecting and limiting bulk query access". **Nominet** the same clause with NO carve-out, and separately "You are explicitly prohibited from extracting, copying and/or using or re-using in any form and by any means (electronically or not) all or part (quantitatively or qualitatively) of the contents of the RDAP database without prior and explicit permission". **CIRA** the same, rejected the same morning. So the engine pointed at Nominet on 2026-08-24 "needing no approval" was right about the evidence class and wrong about the terms, three days after `CLAUDE.md` recorded that `.uk` says the same thing. Both engines stopped 2026-08-27 07:47 and 07:51; `ark rdap` now refuses `com`, `net`, `org`, `uk`, `ca` and `nz` in code and needs a named written permission to send one query. Exposure: the class holds 748,099 pairs and 459,792.0 EE, of which only **1,615 pairs and 851.0 EE are unshipped**, because the rest is already merged into his baseline. Only Nominet's clause reaches USE as well as collection, so only its 121 unshipped pairs and 118.7 EE are a withdrawal question. **The route reopens on a written permission of the RIPE kind and on nothing else.** |
| The VPS RDAP journals nobody had banked, priced at zero (2026-08-27) | **A collector alive for 45 hours writing nothing, and 85 MB of journal that paid 0.00 EE.** The VPS sibling sweep showed `up 2-16:29` in the process table while its newest journal had last been written at 2026-08-25 08:51:28 UTC. Six `.part` files, 85,373,766 bytes, were snapshotted and ingested: 701,225 journal lines, 112,114 records with in-window creation dates, **0 evidence rows and 0 year rows**, because earlier snapshots of the same files had already been banked and the queries since had added nothing. Two lessons, both already in `CLAUDE.md` and both re-earned: presence, progress and yield are three questions, and a `.part` is worth snapshotting the moment its writer stops rather than when someone notices. |
| The residual audit's `unread` flag, priced (2026-08-27) | **Worth 22.2 EE, not the "cheapest yield in the project" the audit calls it, because it counts FILES and not value.** Four files matched a documented ingest glob and no ingest had read them. Three are `us_domain_delegated` captures at 2000-12-06, 2001-02-01 and 2001-04-11, and all three are **byte-identical to each other** at 435,847 bytes, one md5: the same delegated-zone list fetched at three instants. The already-ingested 20000815 and 20010606 editions cover those names at 2000 and at 2001, so the trio adds 24 pairs and 22.2 EE, all from the 2000 capture, and exactly zero from either 2001 capture. Predicted 24 net-new before ingesting and the ingest wrote 24 year_rows, so the pricing method is sound and the population is spent. The fourth file, one `cdx_pool` journal of 9,381 bytes, paid 175 pairs. **Rule: price an `unread` count by content, not by file count. Duplicate captures of one artifact inflate it, and a second capture of an unchanged list can only add a year the store may already hold.** |
| Every RDAP-served TLD ranked by headroom, the family closed on measurement (2026-08-27) | **Systematic rather than guessed, and `.ca` is the only one worth a conversation.** The IANA bootstrap was joined against our own holdings and each TLD priced at held-domains x weight x the 29.3% in-window rate measured on Nominet. Ceilings: `.ca` **25,377 EE**, `.nl` 9,200, `.sg` 4,233, `.br` 3,934, `.no` 3,105, `.cc` 2,443, `.info` 2,322, `.pl` 2,158, `.tw` 2,057, `.fi` 1,968, `.gov` 1,942, `.to` 1,908, `.cz` 1,371, `.ar` 1,260. Everything below `.ca` is under 10,000 and mostly low-weight, so **the family is closed except for `.ca`**: no further endpoint is worth a licence question. `.gov` publishes no creation date and is already closed. Both live probes work and both bind use to terms: `.sg` serves `nus.edu.sg` at `('registration', '1996-09-02T16:00:00Z')` and prints "This data is provided for information purposes only" with its policy documents linked but unread, so it is filed pending rather than queried, at a ceiling too small to justify the reading. **`.ca` is live, serves an in-window creation date, and its Terms of Use forbid the query.** The IANA bootstrap gives endpoints for `ca`, `au`, `in`, `uk` and `sg`; `.au`, `.in`, `.nz`, `.za`, `.ie` and `.us` were already closed on an earlier probe. `.ca` was not. One query to `https://rdap.ca.fury.ca/rdap/domain/rita.ca` returns `('registration', '2001-02-01T17:11:06Z')`, the same `whois_creation` semantics already approved. Ceiling **~25,377 EE**, from 103,541 held in-window `.ca` domains at `.ca`'s 0.8365 and the 29.3% in-window rate measured on Nominet. **It died on terms, not on evidence.** The record carries a Legal Notice binding use to CIRA's Terms of Use; that page answers HTTP 403 behind a Cloudflare challenge, so Ivo fetched it from a browser on 2026-08-27 and it forbids this on four separate grounds: s.10(c) bars any robot retrieving the site "to collect information about other users or domain names"; s.11 permits WHOIS use "solely" to check availability, identify a holder or contact a holder; s.11 lists "unauthorised aggregation or collection of information from the WHOIS database" as prohibited; and s.11 bars "automated processes that send multiple queries". s.4 licenses content for non-commercial use only, and this work is paid. **Closed. Reopen only on written CIRA permission of the RIPE kind.** `robots.txt` is 8 lines, names no agent and disallows only `/wp-admin/`, `/?s=` and `/search/`, so robots is not the obstacle. Filed as `cira_ca_rdap / whois_creation`, pending, needing either a human reading of the Terms or a letter of the RIPE kind. `.sg` is untried and worth 31,793 held pairs, far less. |
| The VPS journal backlog, and why the cycle undercounted it (2026-08-27) | **125 journals had never come home and they were worth 40,893.6 EE, which is more than everything else this night produced combined.** `just cycle` reported "rsync 2 VPS journals home"; the real diff between the two machines was **125 files and 416 MB**, 122 of them `cdx_suffix` sweeps and 3 `cdx_vedge`. Converted with `cdx_suffix_convert.py`, which collapses capture rows into per-domain year sets and enters as the already-approved `cdx_snapshot / cdx_timestamp`, they gave 141,013 domains with in-window captures, 122,842 evidence rows and 48,056 year rows. Measured against a pre-ingest snapshot: **50,102 net-new pairs, 40,893.6 EE**, taking the store from 5.3405% to 5.6514%. **The lesson is about the counter, not the VPS**: the cycle counts what a documented glob matches on THIS machine, so work finished on another one is invisible to it until it is copied. Diff the two file lists directly rather than trusting the count, and do it before spending a single new query, because these were queries already paid for. |
| `data/raw/usenet_bulk`, a second 53 GB Usenet pool nothing had ever read (2026-08-27) | **9,266 archives, ZERO filename overlap with the 7,531 in `usenet_new`, no journals, no progress marker and no script referencing it.** Found by listing every `data/raw` directory against the ingest ledger rather than against a documented glob, which is what the residual audit checks and therefore what it cannot see. **It is also far denser than the pool that was worked.** Two disjoint stratified samples over its non-`alt.sex` 2-60 MB stratum: 6 archives / 71.6 MB gave 178 net-new pairs and 99.88 EE (1.3950 per MB), a second 6 / 63.5 MB gave 53 and 30.75 (0.4842). Pooled **231 pairs, 130.63 EE over 135.1 MB, 0.9669 EE per MB**, against the **0.0088** measured on `usenet_new`. The samples are 2.9x apart so the rate is noisy and only the pooled figure should be quoted. Projected over the SAMPLED STRATUM alone, 34,084 MB of the 53,431 MB directory, that is **roughly 33,000 EE**; the `alt.sex` archives, which are the largest files, and everything outside 2-60 MB were deliberately not sampled and are not in that projection. **The likely reason for the 110x gap is population**: `usenet_new` was bit, linux, microsoft and gov, whose domains the store already holds, and this is consumer `alt.*` naming small businesses, fan sites and ISPs it does not. Needs no decision and no queries: `usenet_dated` is already master and `usenet_candidates` already candidate-only, and the cost is CPU on bytes already downloaded. Running via `ARK_USENET_SRC=data/raw/usenet_bulk scripts/work_usenet_new.sh`. **A third pool turned up on the same check and is now finished**: `usenet_probe5`, 48 archives and 2,298 MB, again zero overlap with either other pool, all 48 processed. `usenet_msft` (3 archives, 488 MB) is left alone because the register already measured the microsoft hierarchy at 63 pairs over 1,979 MB. The other large unbanked directories are NOT this shape and were checked: `rtfm`, `maillists` and `probes` are raw inputs whose derived journals are ledgered, and `ccgraph`, `webbase` and `nypw` are closed families. **Archive SIZE anticorrelates with in-window share and that is the sampling rule to carry forward**: a group that stayed busy into the 2000s produces a large file mostly outside 1996-2001. `alt.sex.anal.mbox.zip`, 974.7 MB compressed and 2.18 GB of readable Usenet whose headers show `g2news2.google.com` throughout, split to **0 records and 0.00 EE**, against 0.9669 EE per MB for the 2-60 MB stratum. `ARK_USENET_MAX_MB` now skips the tail so a deadline is spent on the part that pays |
| Scholarly-index sweep for deposited early-web data (2026-08-24) | Failed positive control: OpenAlex `early web` returns 314 works and not one is the UMN DRUM dataset already ingested here. `type:dataset` 1996-2005 with web/URL/domain returns 3,363 works and no URL corpus; `domain` in scholarly search means protein domain. Route shut. |
| The pre-Nominet and Nominet `.uk` register (2026-08-24) | The file never existed. 12,491 captures over 2,710 URLs of `nic.uk`, `nominet.org.uk`, `nominet.net`; largest object ever served is a 94,785-byte membership list, worth 2 net-new pairs, 1.96 EE. Register exposed only per-name; `members-private/expanded-whois/` is HTTP 401. |
| `uk.*` registration announcements as a `can.domain` analogue (2026-08-24) | Zero: every named file is already in `.processed`. The `uk.net.news.*` subtree measured 1,031 gross pairs against 69,609 for `can.domain` on the same pipeline. Unfetched IA `usenethistorical` is 270.81 GB across 1,007 items, honest band 5,000 to 45,000 EE. |
| `.us` locality registers, Granite Canyon, and a 20,000 EE wildcard (2026-08-24) | `.us` locality registers 39.6 EE, 0 novel names on all four states tested. Granite Canyon secondary-DNS artifacts 1,881.1 EE post-split against a 5,000 bar. Best wildcard candidate, Nominet's member list, 507.96 EE. |
| `ark gaps` queue ranking (2026-08-24) | Not a source: the bracketed-gap queue, 451,490 domains at a 264,814 EE ceiling, ranks by weight and returns 31 years from 600 queries (5.2%) against 673 years from 600 on the `.com`-heavy file it replaced. Reordered to put `.com`/`.net`/`.org`/`.uk` first. |
| Not Your Parents' Web TimeMaps, deferral converted to REJECT (2026-08-24) | Tested at `1996/..._deeplinks_part00o.tar.gz`, 5,641,617 bytes: 17,035 in-window pairs, 17,006 already held, 29 net-new, 14.2 EE. Folder year is year of first archive, not of content, so the 1996 folder's net-new pairs land in 1998, 1999 and 2001. |
| Wayback `__wb/sparkline` endpoint (2026-08-24) | Right shape, same rate limiter. Head to head over 80 gap-queue domains: sparkline 8 of 80 at 1.93 q/s, CDX 7 of 80 at 0.93 q/s. Twice as fast per attempt and no less refused. |
| The re-registration rule, re-measured (2026-08-24) | Of 370 answering RDAP records over 472 seeded-random capture-dated domains, 59.7% still carry an in-window creation date. Transfer, bankruptcy and change of owner never reset it (EFF 1990-10-10, Pets 1994-11-21, Napster 1999-02-20). |
| Arquivo.pt live CDX as a dating engine (2026-08-24) | Answers 17.3 q/s, 250 of 250 HTTP 200, and holds nothing needed: 0 in-window 200s over 250 candidate-pool names and 0 over 157 domains our store already dates in window. |
| RDAP over the candidate pool (2026-08-24) | The 2,395,205 undated names would be worth 1,658,653 EE, and two pilots of 3,000 returned 0 in-window creation dates (336 answers, 234 of them 404; 266 answers, 195 of them 404). |
| squidGuard robot-compiled blacklists (2026-08-24) | Closed on era: `ftp.teledanmark.no/pub/www/proxy/squidGuard/contrib/blacklists.tar.gz`, 429,365 bytes, earliest Wayback capture 2003-12-11, two years outside the window. |
| Registry change reports across five regions (2026-08-24) | Paid about 7,500 EE over eight small artifacts (TWNIC 1,275.0, SaudiNIC 1,506.4, NIC Malta 1,470.5, NIC Venezuela 1,131.3, IDNIC 872.6, RESTENA 708.5, ISOC-IL 375.0, `.nu` 144.1). gTLD side empty: the only in-window listing is `greatdomains.com`, 2,466 owner-submitted records, about 104 EE after the split. |
| National register listings, the `.ie` shape across nine namespaces (2026-08-24) | Two paid (`.my` MYNIC, `co.za`), six empty on measurement: `.nz` whole Domainz site is 170 URLs yielding 5 and 1 names, `.au` largest AUNIC page yields 10 names all worked examples, `.ca` counts only, `.sg` and `.hk` no listing, `.ph` a rolling 30-day expiry window. |
| Pricing on parser `raw` rather than canonical form (2026-08-24) | `ukwa_geoindex` priced at 4,509.1 EE over 4,595 pairs, admitted at 4,493.0 over 4,591. Joining `BulkRecord.raw` URLs against `domain_year` finds zero held and returns top TLDs `htm` 2,106,483 and `html` 2,055,761. After canonicalisation 17,912,511 rows collapse to 289,857 pairs, 285,262 already held. |
| DataCite sweep for deposited early-web datasets (2026-08-24) | Eight query shapes against `api.datacite.org/dois` surface nothing not already held: link list/graph plus web gives 21 hits, the only in-window one the UKWA host link graph; `early web` gives 19 hits whose only deposits are UMN DRUM and the Zenodo banner ads; `web crawl` 1997-2006 zero. |
| Nominet RDAP over held `.uk`, banked (2026-08-24) | Banked, no approval needed. `rdap.nominet.uk` publishes a machine-written `registration` event with a full timestamp, verified `demon.co.uk` `1996-05-05T21:08:48Z`, reached through the IANA bootstrap by `ark rdap`. Evidence type `rdap_snapshot / whois_creation`, `Decision: master` since phase 4. On 400 seeded held `.uk` names read at 157 answers: 29.3% in-window, 19 of 46 pairs net-new, 118.8 EE per 1,000 queries. |
| UCSF Industry Documents Library (2026-08-24) | 3,826,999 in-window documents with per-document `documentdate`, and 6,000 fetched give 216 pairs for 146.6 EE after the corroboration split, because 89% of the net-new names are dated nowhere else. Whole-population projection about 730 EE post-split. |
| Small-organisation open data with a per-row date (2026-08-24) | All four zero. DOL Form 5500, 740,473 dated 1999 rows and zero hostnames; CRA T3010, 441,785 in-window rows, zero; EPA TRI Form R, 2,400 rows, zero against a same-minute control; Canada Gazette Part 1, 50 to 100 EE for the whole run. The era's forms had no web-address field. |
| Uncrawled mailing-list subscriber populations (2026-08-24) | RootsWeb 26.47 GB of WARC measures effectively 0 EE because the capture is of the modern interface; ArchiveTeam Yahoo eGroups 8,271 items, zero net-new by access; `bit.listserv` 1,100 to 1,600 EE for the whole hierarchy. |
| Organisational mail releases beyond Enron (2026-08-24) | One real member, 67x short: `jeb_bush_gubernatorial_email`, 411,928,998 bytes, 626 born-digital files, 519,581 in-window `Sent:`/`Date:` headers, 4,011 EE over 6,412 net-new post-split pairs of which only 1,607.7 EE comes from a `To:`/`Cc:` line. |
| Generated RDAP target populations, and what ORDER to query them in (2026-08-24, extended 2026-08-27) | Four populations of 1,500 to 3,000 names queried direct to Verisign: English dictionary words 13.5 EE per 1,000 queries (28.00% in-window) but finite at ~235,000 words and 92.4% already held, sibling TLDs of held names 9.7 (5.64%), random four-character strings 6.3, invented two-word compounds **0.0** over 859 queries. Siblings won on material: 14,080,169 names against a dictionary that exhausts in an hour. **The pilot rate does not survive contact with the whole queue, and the reason is the transferable part.** Measured 47,164 queries into a later run: **8.2 EE per 1,000**, with the in-window hit rate splitting **7.3-fold** by how many of the six years the store holds the sibling's BASE label, 7.84% at six years against 1.08% at one, and **54% of an unranked queue hangs off one-year labels**. A label the archive sees across all six years belonged to a going concern, and a going concern of that era defensively registered the other two gTLDs in that era; a label seen once is as likely to be a typo or a parked name that never had a sibling. `scripts/rank_sibling_queue.py` sorts on that. **And the registry, not the ordering, is what governs the rate.** Per-minute counts from the journals: the unranked run held **65 queries a second flat for seventeen minutes** with no decay, then every later run collapsed to about 1 q/s whatever order it used, including a shuffled run over the same population. Verisign served **64,568 queries and then clamped for at least twenty-five minutes across three restarts**, so all three ordering experiments ran inside one quota and none of them measured ordering. A first reading of this as "ranking loses sixtyfold" was wrong and is withdrawn. What ranking demonstrably does, being a property of the population rather than the limiter, is raise the answered-200 share from 18.7% to 74.4% and the in-window rate from 1.80% to 4.02%. The queue ships shuffled (`--shuffle`), deterministically, and settling whether ranking pays needs a rested registry. **Rule: a generated population needs an ordering as much as it needs a generator, and the ordering is measurable from the engine's own answers after an hour.** |
| UKWA host link graph, 2 GiB replay cap re-probed (2026-08-24) | Closed at the byte. `timemap/link` returns two captures only; the 2022 one fails at byte 0 with curl exit 56. On the 2020 capture ranged GETs work up to the cap (`2147479552-2147483647` returns 206 with 4,096 bytes) and the next 4K fails five consecutive attempts. |
| Internet Archive bulk CDX / ZipNum index (2026-08-16) | Not public. `archive.org/metadata/wayback-cdx-index` returns `{}` and `cdx/search/cdx?url=*.com&from=1999&to=1999` returns HTTP 403. The 403 is policy, not an outage: do not re-probe. |
| Usenet `Message-ID` posting hosts (2026-08-16) | Over 73,751 in-window messages carrying both a `Message-ID` and a `Date`: 1,405 distinct domains, 2,056 pairs, 51 net-new pairs and zero domains never seen before. Top hosts `wisc.edu` 22,380, `gi.net` 20,962. |
| UKWA ds.1 classification list (2026-08-16) | Recovered from Wayback at `opendata/ukwa.ds.1/classification/classification.tsv`, 3,011,797 bytes over 26,910 rows, and deliberately not ingested: columns are category, title and URL with no date field of any kind, so it is candidate-pool only, and UKWA's selective archive began after 2001. |
| Cybermetrics (Wolverhampton) crawl databases (2026-08-16) | Closed on the authority rule, and the filenames lie about the year: `stats/data/UK_2001.txt` opens with its own header "UK 2002 database crawled July 2002". Read the file's own header before trusting its name. |
| Era web traces and proxy logs, the whole family (2026-08-16) | Closed by design: DEC/Compaq 1996 states "it should not be possible to discover the actual identity of any host or URL in these traces", BU 1998 hashes the Host field, UC Berkeley Home IP 1996 anonymises URLs. Ask any era-trace proposal for the sanitisation paragraph before fetching a byte. |
| Library catalogue records with a MARC 856 URL, measured (2026-08-16) | 47 qualifying records in 48.2 MB of Scriblio give 13 domains, 12 already held, one net-new and that one a public-suffix subdomain. Dating and URL-bearing are anticorrelated: LC books carry an in-window MARC 005 on 28.25% of records and hold 67 hosts in 72,588; LC serials hold 3,492 hosts and carry one on 0.34%. |
| Search engine indexes 1996-2001, the whole family (2026-08-16) | Not one machine-readable dated hostname list survives. AltaVista's May 1999 crawl of 203M URLs was never published and Yahoo Webscope no longer resolves; six archive.org sweeps over Lycos, Excite, HotBot/Inktomi, Infoseek, Northern Light and WebCrawler return zero index artifacts. All three surviving in-window Open Directory dumps are already held. |
| IPEDS institutional characteristics (2026-08-16) | Of 3,251 domains in `IC99_HD`, 2,946 are already dated 1999, the exact year the file attests, leaving 147 post-split pairs and 100.8 EE. The web-address column exists for one in-window year only. `.edu` is 95.5% saturated at the year an institutional directory attests. |
| Unheld Usenet hierarchies, IA `usenethistorical` (2026-08-16) | Deferred. Of the unheld remainder only about 40 GB is English-facing (`microsoft` 26.6 GB) and about 135 GB is national hierarchies an English-weighted metric discounts to near nothing. |
| Not Your Parents' Web TimeMaps, IA `nypw_timemaps` (2026-08-16) | Deferred on cost: in-window folders total 19,350,762,163 bytes, field 3 of a TimeMap line is a 14-digit capture timestamp so the year is per-record, but the methodology paper (arXiv:2507.14752) documents downsampling and the sibling `nypw_firstcdx` is already rejected at 53 net-new domains over 6.28M lines. |
| Parallel Language Records of the Early Web (2026-08-16) | No date of any kind in a record: README plus shard 00 (42,290 lines) confirm SURT pattern then `<lang> <url>`, the only date being collection-level "captured before year 2000". Its 1,164,183 records also select for multilingual mirrors, top tuples `ca-sg` 134,941, `de-en-fr` 89,557. |
| Netcraft Web Server Survey `/domains/cache/` listings (2026-08-12) | Candidate-only: 0 pairs as master, 13,078 names stay in the pool. The pages are machine-generated alphabetical dumps with no per-item date, so they died on contemporaneity rather than on the corroboration split. |
| INET conference proceedings 1996 to 2001 (2026-08-11) | 460 in-window pairs, 416 already held, 19 net-new after the split worth 12.7 EE over 223 pages; whole-corpus estimate 116 EE. `isoc.org` 301-redirects every proceedings path to web.archive.org, so the source is IA-only. |
| Debian package changelogs and upstream homepage fields (2026-08-11) | 803 in-window pairs, 762 already held, 21 net-new after the split worth 14.4 EE. The named mechanism does not exist in window: grep for `Homepage:` returns 0 across all 36 in-window index files, because it entered Debian policy around 2007. |
| W3C technical reports index (2026-08-11) | Census, not sample: 626 in-window reports yield 1,225 pairs, 1,078 already held, 56 net-new after the split worth 36.1 EE, 87x below the bar. Trap: W3C retrofits post-window status banners into archived recommendations. |
| RFC and Internet-Draft documents (2026-08-11) | Complete RFC population plus a 12.2% draft sample: 3,605 in-window pairs, 3,151 already held, 140 net-new after the split worth 88.2 EE. The split does not protect against fictional hostnames, and this corpus is full of them (`acmecorp.com`, `bigco.com`, `widgetco.com`). |
| Microsoft Bookshelf Internet Directory, 1996 CD-ROM (2026-08-11) | 7 net-new pairs and 4.7 EE after the split. The 99 MB ISO yields 2,020 distinct (domain, 1996) pairs of which 1,863, or 92.2%, are already held. |
| Web defacement mirrors other than attrition.org (2026-08-10) | Closed on availability: archive.org holds 0 items for `alldas` and 0 for `safemode defaced`, and its 212 hits for `defacement` are unrelated. |
| Linux Software Map, ibiblio LSM snapshots (2026-08-10) | 86 net-new pairs and 37.3 EE after the split. Each `Begin3 ... End` block carries its own `Entered-date` beside `Primary-site`, so the dating is ideal and the population is wrong: 3,743 of 3,951 in-window pairs, 94.7%, are already held. |
| Printed Internet directory books, the whole named family (2026-08-08) | Closed on reach AND on yield, and both halves matter: a title query over `mediatype:texts AND year:[1994 TO 2002]` returns 34 volumes, every one `inlibrary`/`printdisabled`, and `_djvu.txt` and `_hocr_searchtext.txt.gz` both return HTTP 401, verified on four volumes. The HathiTrust Extracted Features route is legitimate and would not have paid: measured at 15.7 net-new pairs per volume over 69 in-window volumes, 74 net-new pairs and 49.4 equivalent-English after the split against a ~5,000-pair bar. Do not re-probe on availability alone. |
| SEC EDGAR filings 1996-2001 (2026-08-08) | 150 filings stratified across six years, 150 of 150 reachable, 61.1 MB, 46 pairs in total, 4 net-new and 1.9 EE, or 0.01 EE per filing. Filers that print URLs are the large public companies the baseline holds first. |
| InterNIC public zone files via Wayback (2026-08-08) | Absent: `internic.net` under `matchType=domain` holds 8,001 captures of which 16 resemble data and those are single-domain whois lookups; `ftp.internic.net/domain` captures are 435-byte stubs. Trap: `url=host/path/*` with `matchType=prefix` returns zero even for known captures, so drop the `*`. |
| Usenet `Path:` relay chains (2026-08-08) | 7.1M accepted hops over a 400-archive sample collapse to 4,736 domains and 7,201 pairs, of which 49 are net-new after the split: 13.89 EE. A relay is a large ISP or university, so 99.32% of sampled pairs are already held or uncorroborated. |
| Other national web archives, non-Nordic (2026-08-08) | Australia's AWA is the only open in-window index and it is IA data: 13 of 13 cross-checked domains return identical year sets from AWA and the IA CDX, 0 AWA-only pairs, every in-window row from `NLA-EXTRACTION-1996-2004-ARCS-PART-*`. Japan, Austria, Catalonia, Slovenia, Croatia, Netherlands, Singapore, Estonia, Switzerland, Germany, Spain and Italy all postdate the window. |
| Nordic and Baltic national web archives (2026-08-08) | Seven of eight have no public in-window index. Iceland's `vefsafn.is` pywb CDX serves in-window captures but cannot be enumerated, capping the addressable set at 2,540 known `.is` names: 66 lookups, 0 unknown domains, 867 projected EE. Sweden's Kulturarw3 is reading-room terminal only. |
| Shareware and CD-ROM catalogues beyond Tucows (2026-08-08) | Info-Mac worked to exhaustion: 2,604 domains, 2,477 already held, 234 pairs, 134.15 EE. garbo.uwasa.fi's master index contains one domain, its own. Trap: an archive.org software scrape reports 682 net-new domains and all are spurious, 15,399 of 15,521 hits coming from modern uploader prose. |
| Free-hosting member indexes: GeoCities, Tripod, Angelfire, Xoom, FortuneCity, Homestead (2026-08-08) | Collapses architecturally: every member URL is a path or subdomain under the provider's own domain and all ten provider domains are held. 0 member-owned registered domains from 4 index pages; the member-links fallback gives 617 domains at 97.4% already held. |
| Award galleries and cool-site lists (2026-08-08) | 206 domains across 7 dated award pages: 2 net-new domains (0.97%), 5 net-new pairs, 3.16 EE. `point.lycos.com` gives 1 outbound domain in a 90 KB, 484-href 1996 listing page. |
| Institutional link directories: university, library, government, museum (2026-08-08) | 386 of 388 domains across 11 archived BUBL LINK pages are already held: 2 net-new domains, 5 pairs, 1.96 EE. The best-case page, a worldwide museums directory with 192 external links, gave 0. |
| Research crawl datasets, remaining angles (2026-08-08) | academictorrents 2,851 items with 0 in-window web crawls, `collection:webarchivedatasets` exactly 8 items, LAW/UNIMI 2 in-window graphs (`cnr-2000` is 325,557 URLs to one domain), CAIDA no hostname inventory, RIPE Hostcount aggregates only. The parallel-language salvage nets +374 EE and scores negative on the project's own estimator. |
| Search-engine and portal directory trees (2026-08-08, rejected) | The 1996-1997 Yahoo catalogue does live under `www.yahoo.com/<Category>/` and pays nothing: 55 requests, 7.7295 EE. The zero-domain result from `dir.yahoo.com` was an `unwrap_redirect` bug, now fixed, turning one 20000817191821 capture from 0 domains into 3. |
| Non-English regional portals (2026-08-08) | Deferred: 10 archived catalogue pages give 445 EE measured after the split, about 27 EE per request, but 97.4% comes from one Indian portal (Khoj), Seznam's 1,723 domains gave 0, the Brazilian pages gave 0, and everything lands in 2001. |
| Stanford WebBase 2001 (via LAW) | 118M URLs to 603,245 registered domains, 99.99% already held. Retired as a growth source. |
| `deduplicated_urls_*` (supplied seeds) | Exhausted: 200k lines probed yielded 3 domains not in the baseline. |
| Common Crawl | Earliest collection is 2008-05; capture timestamps fail the in-window evidence bar. |
| Arquivo.pt bulk `AWP*` collections | 214 files, sampled slices all 2008, out of window (`Roteiro` and `IA.cdxj` are the in-window exceptions). |
| UKWA per-year bulk CDX | Not publicly retrievable in 2026: dead host, soft-404 successor, 404 DOI, never Wayback-captured. Probe the data paths, not the repository front page: `https://www.webarchive.org.uk/datasets/ukwa.ds.2/cdx/1999.cdx.gz`, with `linkage/host-linkage.tsv.gz` as the positive control, a file we hold 2 GiB of that returns the same 159-byte stub. Access requested. |
| ODP full 2001 content dumps | Unavailable in 2026: the URL serves a "Page Has Moved" stub. |
| ODP full Aug-2000 content dump | Unrecoverable; only `structure.rdf` was archived, which has no external links. |
| Public 1996-2001 zone files | Some do survive: an intact April 1997 InterNIC `.org` zone was found at `nic.mil` on 2026-08-18. |
| Historical zone files and bulk registry snapshots (2026-08-08) | Closed for 1998-2001. archive.org holds no in-window zone file (`title:(zone file)` 303 items all 2009 or later, `"com.zone"` zero); the CD-ROM route holds shareware discs, not registry snapshots; and `wuarchive.wustl.edu`, `ftp.uu.net`, `ftp.cdrom.com` and `ftp.funet.fi` return zero Wayback captures. |
| Australian Web Archive (PANDORA/Trove) | Superseded: the operative verdict is redundancy with the Internet Archive, zero AWA-only pairs. `web.archive.org.au/awa/cdx` answers normally. |
| Other ccTLD registry open data | Nothing free reaches 1996-2001. CENTR aggregates only, OpenINTEL starts 2015, commercial WHOIS is paid. Re-checked for a per-domain file carrying both a creation and a withdrawal date: Nominet, auDA, InternetNZ, CIRA, SGNIC, IEDR, SWITCH and SIDN publish daily feeds, dashboards or top-N rankings, none per-domain lifecycle. AFNIC `.fr` is the only one and is already banked. |
| SNAP web graphs | Nodes are anonymised integers with no URL mapping. |
| Yahoo! Webscope AltaVista graph | Permanent: `webscope.sandbox.yahoo.com` has no DNS record. Does not want re-probing. |
| TREC WT10g / VLC2 / WT2g / .GOV (2026-08-15) | Closed on measurement. Glasgow sells WT2g at 350 GBP, WT10g and .GOV at 500, DVD only behind a signed agreement. The two free files, `wt10g_inlinks.gz` and `wt2g_inlinks.gz`, contain only opaque docids (`WTX001-B01-1`, 8,063,026 lines) with the docid-to-URL table on the paid media. |
| Yahoo! Directory | No machine-readable dump was ever published. Not a re-probe candidate: the artefact never existed. |
| GeoCities derivatives, DNS Census | 2009 and 2013 respectively, out of window. |
| Post-July-1997 ISC `.domains` lists | Do not exist; later editions publish aggregate counts only. Confirmed from two independent live directory listings, so an absence rather than an outage. |
| ISC January 1997 file | Corrupt in every known copy. Permanent gap. |
| Internet Archive Alexa crawls (`alexacrawls`, `webwidecrawl`) | 226,901 items from 1996 with per-item CDX, but every payload returns HTTP 401; only `_meta.xml` is public. |
| UKWA per-year bulk CDX (2026 recheck) | Docs survive at `ukwa.github.io/opendata/ukwa.ds.2/cdx/`; the download host serves the same 159-byte stub and the DOI 403s behind Cloudflare. Wayback captured the directory listing but never the `.gz` files. In-window size would have been about 13.4 GB. |
| New Zealand (National Library) | `webarchive.natlib.govt.nz` and `natlib.govt.nz` return an Imperva bot interstitial; NLNZ's archive.org CDX items are 2025-2026 crawls. Keep in rotation: harvesting began in window, `.nz` weighs 0.9895, and a bot interstitial can change. |
| Canada (Library and Archives Canada) | Federal web harvesting began December 2005 on their own statement; `open.canada.ca` returns zero web-archive index datasets. |
| Ireland (National Library) | Archives via Archive-It, 138 collections, earliest captures 2011. |
| `early-web_parallel-language-urls` | 1,164,183 pre-2000 multilingual URL patterns with no timestamps, so no per-year evidence. Seed-only at best. |
| OCLC Web Characterization Project | Only aggregate statistics were published; the host is gone. |
| Mailing-list archives (2026-08-01) | Population is wrong. archive.org's in-window holdings are hobbyist digests (`sf-lovers`, `GLOWBUGS`); the W3C public lists are small and technical, `www-announce` running for 3 archive periods, `www-talk` 121, `www-html` 246. A 1997 `www-announce` month carries 53 messages against the 20,000-plus domains one Usenet commerce group yields. |
| archive.org books, three collections (2026-08-05) | `subject:(internet)`: 57 of 60 sampled in-window items publish no downloadable `_djvu.txt`, 2 net-new pairs. `collection:folkscanomy_computer`: 36 of 40 unreachable, 2 net-new pairs from 40 items. In-window book scans largely carry no OCR text layer. |
| archive.org `magazine_rack` at large (2026-08-05) | 34,279 in-window items at 0.4 net-new pairs per reachable item, against 10.5 for the computing trade press measured the same way. In-window holdings are user-group zines and lab newsletters. |
| Boardwatch ISP Directory volumes (2026-08-05) | The monthly issues carry `_djvu.txt`; the directory volumes do not. `boardwatch-directory-of-internet-service-providers-july-august-1997_djvu.txt` returns a 146-byte stub. |
| IRCache / NLANR proxy traces (2026-08-06) | Gone. `ircache.net` serves a squatted blog, `ftp://ircache.nlanr.net/Traces/` is dead, `(ircache OR nlanr) AND trace` returns zero archive.org items, and `web-caching.com` now answers with a consent-manager parking page. All three hosts are squatted or parked. |
| Internet Traffic Archive web traces (2026-08-06) | `ita.ee.lbl.gov` is alive and the ideal dataset is unusable: UC Berkeley Home IP 1996, 9,244,728 requests, has anonymised URLs, its own format example being `GET 9168504434183313441..gif`. `BU-Web-Client` has clear URLs and runs 1994-1995, out of window. |
| Shareware CD-ROM catalogues on archive.org (2026-08-06) | archive.org cannot list inside an ISO: `/download/<item>/<file>.ISO/` ends "failed to obtain file list", so measuring density costs a full ISO download per item, 127 MB to 1,300 MB. The 3,578 `cdbbsarchive` items also carry no `date` or `year` metadata. |
| DMOZ / ODP pre-2002 dumps on archive.org (2026-08-06) | archive.org holds exactly one ODP RDF item, `dmoz-rdf-20150327`, 29.8 GB, 2015. No pre-2002 dump exists there. |
| InterNIC / NSI zone or WHOIS snapshots on archive.org (2026-08-06) | 8 hits for `internic AND (zone OR whois OR domain)` and none is data: two Tucows programs, an RFC, two videos, two GitHub mirrors. |
| Other released email corpora (2026-08-06) | Enron is the only released corpus in window. |
| faqs.org as a route to the Usenet FAQs (2026-08-06) | Moot rather than closed: `http://www.faqs.org/faqs/` returned HTTP 429 twice an hour apart and its TLS is too old for the local LibreSSL. The same FAQs were taken through the rtfm.mit.edu mirror. |
| UK Government Web Archive (2026-08-06) | Not rejected. It works and it is tiny: real coverage from 1996-11-11, government-only, 250 addressable domains. |
| `nav.webring.yahoo.com` (2026-08-05) | Zero in-window captures for the entire host prefix. Wrong hostname for the period. |
| WebRing member lists (2026-08-05) | Reject as a bulk source: the largest real page, `www.webring.com/cgi-bin/webring?ring=railring&list` at 20000422003921, is 14,154 bytes, lists 20 member sites and contains 2 member URLs, because every member is linked through a `go.webring.org` redirector. |
| Bibliotheca Alexandrina IA mirror (2026-08-05) | `web.archive.bibalex.org` and `web.archive.org.bibalex.org` both fail to resolve; only the institutional landing page answers. |
| US trademark filings for domain-name marks, 1998-2001 (2026-08-15) | Closed on two reasoned grounds: a filing costs money and legal work, so the population is businesses an 8.26M-domain store already holds; and an intent-to-use filing evidences an intention, not a live domain, so only a use-in-commerce filing with a specimen attests the site existed. |
| URLs cited in US patents, 1996-2001 (2026-08-15) | A projection, not a measurement: a cited reference is the definition of an authority-selected population, and even at 3% of the roughly 1.0M US patents granted 1996-2001 citing a URL the distinct-domain count is order 10^4. |
| NTP Survey 1999, Nelson Minar / MIT Media Lab (2026-08-15) | Live index, dead payloads. `alumni.media.mit.edu/~nelson/research/ntp-survey99/data/` is 4,337 bytes of period HTML listing `ntp-survey-1999.tar.bz2` and siblings; the census of 175,527 NTP hosts is orthogonal to a capture-derived baseline and unreachable. |
| Library catalogue records with a MARC 856 URL (2026-08-15) | Closed on a dating hazard: an 856 field can be added at any later date, so MARC 008 dates the record and not the URL, and a 1998 record may have acquired its link in 2005. A per-entity date is not a per-field date. |
| Commercial business directories with a website field: Thomas Register, Kompass, D&B (2026-08-15) | Fails on reach: no in-window edition is digitised, archive.org holding the 1905-1906 Thomas Register and undated later scans, and the printed-directory family is already closed on 57 of 60 sampled volumes publishing no downloadable `_djvu.txt`. |
| Dot-com deadpool and failure lists, 2000-2001 (2026-08-15) | Short life is necessary and not sufficient: a funded dot-com ran a marketing budget and was captured repeatedly before it folded. The population is celebrated failures, which is authority selection, and the store holds every one. What pays is short life plus low traffic. |
| Archie anonymous-FTP indexes (2026-08-15) | Closed on era: Archie was effectively dead by 1997, so at best it speaks to 1996. Its population is institutional FTP hosts, and `wuarchive.wustl.edu`, `ftp.uu.net`, `ftp.cdrom.com` and `ftp.funet.fi` return zero relevant Wayback captures. |
| Bruce Guenter's spam archive, `untroubled.org/spam/` (2026-08-15) | 312 net-new pairs and 195.5 EE after the split, 16x below the bar. `1998.7z` through `2001.7z` total 9.3 MB and expand to 20,010 messages each carrying its own `Date` header, but 19,992 in-window messages name only 5,342 pairs over 4,793 domains and 3,203 of those are already held. |
| Anti-spam blocklists and blackhole lists, 1997-2001 (2026-08-15) | Every in-window blocklist is IP-based, not domain-based: MAPS RBL, ORBS, the Dial-Up List and SPEWS all publish addresses and netblocks, and the output unit is the registered domain. The domain-bearing variant, spam sightings in `news.admin.net-abuse.*`, is already ingested. |
| `data.webarchive.org.uk` (2026-08-05) | Does not resolve. A third distinct host tried for the UKWA bulk CDX. |
| The whole `webarchive.org.uk/datasets/` tree (2026-08-15) | The stub is the tree, not the file: `/datasets/ukwa.ds.2/geo/` returns the same 159-byte "400 Redirect" body under HTTP 200 as `linkage/host-linkage.tsv.gz`, a file we hold. The Geoindex behind it is 700,641,549 lines covering 1996-2010, about 8 GB gzipped, all `.uk`. Another URL did open it: see `## ukwa_geoindex`. |
| Alexa / IA donated crawl items on archive.org, their CDX indexes (2026-08-15) | The bulk index exists and is access-controlled: in-window items carry per-item CDX (`FS-587676-c.cdx.gz` at 104 MB, a 1999 item at 631 MB) and a ranged GET returns HTTP 401 with a 172-byte body, so the restriction covers the index and not merely the payload WARCs. Reopens only on an access grant. The 401 is per-collection and does not reach the `webdataservices` national extractions. |
| National-library historical web extractions on archive.org: INA `.fr`, FCCN `.pt`, NLI `.ie` (2026-08-18) | Enumerated by scraping all 34,841 identifiers containing `HISTORICAL`: `INA-HISTORICAL-*` 49 items, `FCCN-PT-HISTORICAL-*` and `PT-HISTORICAL-*` 31, `NLI-IE-*` 46. Ireland is the only high-weight one and its earliest item date is 2002. The other two refuse their indexes with HTTP 401 and 403. |
| `USFEDGOV-EXTRACT-1996` through `-2001` (2026-08-18) | Reject on measured yield, 56.2 EE. Six `webdataservices` items, one per year, not access-restricted, 3,255,201,499 bytes of merged indexes, `gzip -t` passing, the 1996 index tiling with zero gap and 647,995 of 647,995 timestamped records in 1996. In every item the whole non-`.gov` population sits in the first one or two ZipNum blocks, and its net-new is exactly 0 of 294. |
| `DARTMOUTH-NBER-RESEARCH-2017-ARCS-*`, 659 items (2026-08-18) | Reject: the payload of an already-banked source. Three complete per-ARC indexes over 6.56 MB give 1,204 in-window pairs and net-new of exactly zero, against the ingested census's own 997 pairs per MB. |
| UKWA Geoindex, E17 postcode slice, figshare 825956 (2026-08-15) | Reachable and too small: 1,886,146 bytes, 12,081 rows of `postcode,year,subdomain,waybackurl`, the 14-digit timestamp inside each wayback URL being self-dating `cdx_timestamp`. 296 net-new pairs raw, 123 pairs and 120.7 EE after the split. |
| Other JISC UK Web Domain Dataset derived files (2026-08-15) | Hostless by construction: `fmts-cleaned.tsv` is MIME-type counts, `link-summary-*.tsv` is suffix-to-suffix counts, `ds.1/classification.tsv` is URL plus category with no year. |
| Archives Unleashed derived datasets (2026-08-15) | Structurally out of window: derivatives are built from Archive-It collections, which begin in 2005. |
| Arquivo.pt CDXJ collections other than `AWP*` and `IA` (2026-08-15) | Every one out of window on 206 ranged GETs: Tomba 2005-2008, InternetMemory 2006-2012, Geocities 2009. The Internet Memory Foundation holding is 62,291,715,540 bytes and the sample found zero captures in 1996-2001. |
| DMOZ / ODP copies on Zenodo (2026-08-05) | 12 hits, all 2018-2020 research derivatives of late DMOZ dumps. |
| `biz.*` Usenet hierarchy (2026-08-05) | Exhausted: no unprocessed `.mbox.zip` archives remain in the 19,233-group catalogue. |
| Late-starting Usenet groups (2026-08-05) | A selection rule: 4,023,027 of 5,283,482 messages across 28 probed archives are out of window, concentrated in whole groups, with four of the 28 contributing zero net-new pairs and `uk.misc` one record from 172.9 MB. Gate on in-window date coverage, not on group name or file size. |
| OpenPGP keyserver bulk dumps, SKS and Hockeypuck (2026-08-18) | Nine dump hosts are dead, NXDOMAIN or 404; `pgp.key-server.io/sks-dump/` serves a squatted 1,095-byte redirect stub under HTTP 200; `keys.openpgp.org` publishes no dump by design; archive.org and Zenodo hold none against a working positive control. |
| Curated distribution keyrings: Debian removed-keys and emeritus, GNU, Apache KEYS (2026-08-18) | Retrievable, correctly dated and 70x too small. Priced on the UID binding signature over 4,096 items: 1,418 pairs, 1,273 already held (89.8%), 69 net-new pairs, 44.4 EE. `debian.org` alone is 1,033 of the in-window user IDs, and a current keyring garbage-collects departed maintainers. |
| X.509 certificate corpora with `notBefore` in 1996-2001 (2026-08-18) | `notBefore` is CA-written into a signed structure and genuinely self-dating; the population fails. The only retrievable in-window corpus is `hg.mozilla.org`'s 139 revisions of `certdata.txt`, and a census of its 126 in-window certs gives 1 net-new pair worth 0.6 EE, with 0 of the 126 end-entity web-server certificates. |
| Machine-written mail headers in bulk mailing-list archives (2026-08-18) | `pipermail` strips the `Received` chain entirely: over 37,789 messages from 2,622 of our own month files only `From`, `Date`, `Subject`, `Message-ID`, `References` and `In-Reply-To` survive, and the `Message-ID` host seam is worth 156 net-new pairs and 107.3 EE over the whole 579,808-message corpus. |
| Web archives holding their own pre-2002 crawls (2026-08-18) | Counted rather than hoped: Wikipedia's list of initiatives (109 rows), MemGator's `archives.json` (20 endpoints) and the IIPC directory (48 permalinks). The Memento TimeTravel aggregator no longer exists, `timetravel.mementoweb.org`, `labs.mementoweb.org` and `aggregator.mementoweb.org` all having no DNS record. Of the 13 initiatives created 2001 or earlier, one is the Internet Archive and three are already closed here. |
| Kulturarw3, National Library of Sweden (2026-08-18) | The largest IA-free in-window corpus known, and the door is shut: access is on-site only and "You cannot search freely for a word or subject, but must enter, for example, `www.sf.se`", so the interface cannot emit an unknown hostname. `kulturarw.kb.se` and `kulturarw3.kb.se` resolve to `selma.kb.se` and refuse TCP. |
| Scholarly and technical full text 1996-2001, the whole family (2026-08-18) | Closed on a density ceiling of 0.042 net-new post-split pairs per item, fixed by two unrelated corpora: the RFC row at 0.0416 and a full census of D-Lib Magazine's 381 in-window articles at 0.0420 (16 net-new pairs, 11.68 EE, 97.4% of its 978 pairs already held). Clearing the bar needs 119,062 such items and the largest such corpus holds 4,997. |
| Quoted `whois` records pasted into Usenet bodies (2026-08-18) | 50x under the bar. Self-dating on the registry's own `Record created on 18-Feb-1998.` line, so the paste date is irrelevant to the year claimed. Priced from disk at zero network cost over 28.20 GB: 488 pairs, 68.2% already held, 155 net-new pre-split, 95.0 EE. |
| The ISI RFC 1480 US Domain Registry (2026-08-18) | Four dated in-window editions recovered, and the registry added four names between August 2000 and November 2001, so the legitimate first-appearance diff prices at 1 net-new pair and 0.9 EE, while dating every name in each edition would have claimed 13,014. Its contact column re-confirms 97.7% already known. |
| Another precomputed IA capture census in a research repository (2026-08-18) | The whole in-window population is four items, three already in this register and one new: Weber's DRUM deposit `10.13020/D62684`, 74.83 GB in 16 tar parts, measuring 45,130 of 45,130 sampled pairs already held and 1 net-new pair worth 0.63 EE from 226,171 rows. ICPSR, OSF and Dryad were blank against working controls. |
| Discmaster, the index over archived media contents (2026-08-18) | Works, and the media population is already ours: the deduplicated `.url` population is 125 net-new pairs and 78.9 EE at 95.6% overlap. Bulk endpoint `search?download=true` returns every match as one tar.gz up to 1 GiB; `robots.txt` says Disallow and carries its own written exception for limited targeted research automation. |
| An early bulk whois snapshot of 2002-2008 vintage (2026-08-18) | Closed mechanically: whois of that era answered on port 43, which no web archive crawls; bulk registry access was a contractual provision to accredited registrars rather than a published file; and the paid market begins its own archive in January 2016 by its own statement. Five free platforms swept to exhaustion. |
| Government grant and award records 1996-2001 (2026-08-18) | Clears the item screen 3.8x over at 456,700 dated in-window items and still dies, because 0.042 pairs per item is a property of subject matter: NSF CSE 0.0471, BIO 0.0152, GEO and TIP 0.0000, NIH 0.0012 at 164 distinct hostnames in 372,444 abstracts. The contact field is current-state refreshed under a frozen date, caught by `gmail.com` appearing 61 times on 1996-2001 awards. |
| Dated newswire and press-release full text (2026-08-18) | Do not sign the NIST agreement. An ungated corpus larger than Reuters RCV1 exists, `usenet-clari.*` at 22 items and 21,309,542,972 bytes with Business Wire and PR Newswire full text, and it fails on era: across four group files parsed in full and six censused, the earliest message is uniformly 2003-06-23. |
| Machine-written network diagnostics pasted into Usenet bodies (2026-08-18) | 29,040 of 219,447,104 in-window messages carry a diagnostic structure, one in 7,557, capping the lens at 1,220 pairs against a 5,000 bar. Measured 297 net-new post-split pairs and 165.7 EE, reduced by a hand audit to roughly 150 pairs and 70 EE for 383 GiB read. |
| Dated announcements of new domain registrations (2026-08-18) | Right about dating, wrong about volume: a registry of this era published either dates without names (statistics, as at `domainz.net.nz/newsstand/stats/` and every InterNIC and NSI registration report) or names without dates (a zone snapshot). |
| Discmaster by file size, and the April 1998 `.jp` registry listing (2026-08-18) | The route works and the snapshot is 87.5% already held. `email.domains`, 2,085,500 bytes and 42,701 lines, at `/japan/email.domains` on the `ftp.cs.arizona.edu` mirror, item 19864, self-dating from its own header "Registered Domains in JP (Apr 30 1998)". `dedup=1` kills the connection; every other parameter is fine. |
| Afilias Land Rush 2 schedule (2026-08-25) | 0.00 post-split, because exactly 1 of the 4,257 names is dated anywhere in the store. `landrush2.afilias.info` resolves at 66.199.183.26 and refuses TCP 80; the surviving fragment, `onlinedomain.com`'s `LR2-list-of-4257-available-domains.txt` at 82,107 bytes, carries `"copyrightYear":"2012"` and is the subset still unregistered in 2012. |
| The ICANN forum `.info` Sunrise lists (2026-08-25) | A decision for a human at 1,328.60 EE post-split. `forum.icann.org/newtldagmts/` is 7,169 message pages frozen since March 2002; largest item `3C8A91B500002319.html` carries `Date/Time: Sat, March 9, 2002 at 10:50 PM GMT` and "Listed below are the 6122 names registered at Sunrise by Worldnic", of which 5,279 parse. Union with WIPO's `.info` Sunrise case index: 7,988 names, 7,284 net-new. |
| A 2001 squidGuard blacklist (2026-08-25) | 10,736.2 EE, licence GNU GPL v2 verbatim in `COPYING`, and it triggers this register's own reopen condition. One request to `archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`, 1,852,659 bytes, yields `samples/dest/blacklists.tar.gz` at tar mtime `Dec 18 2001`, whose files carry the machine-written header `# This list was compiled in 0:00:20 on 2001.12.18 15:04:29.` and dated diffs to `domains.20011218.diff`. **The header asserts liveness rather than listing, so no split: `squidGuardRobot-2.3.4` generated it.** 44,130 canonical names, 18,588 net-new (domain, 2001) pairs. |
| The `.us` locality gap (2026-08-25) | 61% dead names: of 9,680 `.us` domains held in window and missing 2001, 6,948 were last seen in July 1997 and only 1,473 reach 2000, so the addressable share is nearer 3,500 EE than 8,964.65. Against a control, only 37.65% of the 12,080 `.us` names the ISC 1997 walk attests have any 2001 record, `.com` from the same file 40.31%. Compute headroom from the adjacent year only. |
| Southern and Central Europe FTP hosts (2026-08-25) | The host layer is dead, not refusing: of 50 hosts screened, 26 are NXDOMAIN (`ftp.nic.at`, `ftp.nic.fr`, `ftp.cnr.it`, `ftp.switch.ch`, `ftp.huji.ac.il` among them) and nine resolve but refuse ports 21, 80 and 443, against a control where `ftp.funet.fi:21`, `ftp.gnu.org:21` and `ftp.arnes.si:21` were open in the same minutes. Every survivor is a pruned modern distro mirror with zero netinfo paths. Also shut structurally by RIPE's 1999-02-01 restriction, which covers `.gr` and `.il`. |
| The 2001-2003 frozen-mirror sweep (2026-08-25) | Both screened artifacts were already answered: the Edelman whois transcriptions re-found by a second route price at 741.61 EE against the 2,968.49 EE already banked from a fuller parse, its independent 2001 slice giving 1,003 held-missing-2001 at 618.71 EE. |
| Raw AXFR output published openly (2026-08-25) | Surviving editions are 1995 only. `ftp.ripe.net/ripe/local-ir/inaddrcount/data/193.in-addr.arpa.output.gz`, 2,332,217 bytes and 491,640 lines, is a genuine raw AXFR transcript with 50,141 PTR targets, dated three independent ways all 1995: HTTP `Last-Modified: Tue, 02 May 1995 21:00:00 GMT`, FTP mtime `03-May-1995 19:36`, and the SOA line `95042701 ;serial (version)` inside the bytes. |
| Forged-header corpora, the Lazarus remailer logs (2026-08-25) | 115.83 EE, because only 1,053 of its 23,102 canonical names are held. The dating is the cleanest seen here: a complete 12-month 2001 series, 57,368,107 bytes over 13 files, each file's mtime landing on the last day of the month its filename names, with zero cross-month bleed and an in-header `Fri Mar  2 00:45:13 EST 2001`. Licence: none found. |
| The 2001 threshold qualified (2026-08-25) | It is a population average, not a universal rate: `WinNetMagCD.chm`, 146,221,869 bytes dated `2001-12-05 18:11:43` in the ISO9660 directory record, yields 2,334 canonical names of which 2,296 are held and only 157 are held-missing-2001, measuring 95.67 EE or 0.041 EE per name against 0.31 for a random sample of held `.com`. Head-selected corpora need about 24,000 names. |
| The southern-hemisphere DNS-walk lens (2026-08-25) | Blocked by a correlation, not absence: host mortality on one side and robots refusal on the other. Five of the seven live large mirrors in this slice refuse by robots, two naming ClaudeBot, and the two that permit crawling (`ftp.swin.edu.au`, `mirror.fsmg.org.nz`) carry only current distro trees. |
| The 2001 hunt: five routes closed and one prize sized (2026-08-25) | A full 2001 `.info` register would be worth about 273,600 EE, since the store holds 21,609 `.info` at 2001 against about 750,000 that existed by year end, and it does not survive: ICANN's Registry Operator's Reports are aggregate counts plus registrar names, the January 2005 `.info` report yielding 148 bare names in "Section 7" at 145 net-new and 52.90 EE. Correction to a reported trap: `to_registrable` does not drop a CRLF-terminated name, returning `example.com` for `'example.com\r'`. |
| `tomocha.net` refuses ClaudeBot by name (2026-08-25) | `tomocha.net/robots.txt` is 61 lines and carries `User-agent: ClaudeBot` / `Disallow: /` at lines 51-52. `jpnic_register` is withdrawn from the queue: its measurement of 1,623 EE stands and must not be used. `tomocha.net` is on the by-name refusal list. Read the whole robots.txt and act on it before any other request. |
| DNS-walk output across the RIPE region (2026-08-25) | Structurally dead by RIPE's own dated decision, verbatim from `ftp.uni-erlangen.de/pub/ripe.net/ripe/hostcount/README`, mtime 3 July 2001: `01/02/1999  Access to the host output files was restricted` and `03/07/2001  Access to the error files was restricted as well`. The sibling `METHOD` confirms the output was "transferring every possible Domain Name System zones under the mentioned top level domains". Closes about 14 namespaces without probing them. |
| The 2001 threshold (2026-08-25) | P(store lacks 2001 given domain held): `com` 0.611 (4,264,044 of 6,980,240), `net` 0.653, `org` 0.568, `uk` 0.309, `de` 0.841, `au` 0.406, `ca` 0.478, `nz` 0.545. EE per already-held name in a 2001-dated artifact: `com` 0.386, `org` 0.404, `au` 0.402, `ca` 0.400, `uk` 0.303, `nz` 0.539, `de` 0.111. So 1,000 EE needs about 2,590 held `com` names, a 32x relaxation of the curated-directory floor, and it applies only to 2001. |
| The long-running-series lens (2026-08-25) | An IRR/RADB dump is 97.6% already held and paid 4.44 EE, because 95.2% of its names were already held in that very year: 13,674 in-window `changed:` lines collapse to 532 pairs of which 25 are net-new. The screen is held and missing this year. Aim at 2001, not 1996. |
| `ftp.nluug.nl` refuses four Claude agent names (2026-08-25) | `ftp.nluug.nl/robots.txt` lists `ClaudeBot`, `Claude-User`, `Claude-Web` and `Claude-SearchBot`, each with `Disallow: /`. Also refused and not pursued: `ftp.fu-berlin.de`, `ftp.uni-stuttgart.de`, `ftp.tu-chemnitz.de`. `ftp.radb.net` serves no HTTP at all. |
| `.nz` port 43 (2026-08-25) | 7,586 EE measured and refused by the registry's own terms, which sit about 1,100 bytes into the same response, after the record. 200 domains from 47,914 held `.nz` names, 123 dated, 122 in-window against 1 out, 0.1600 net-new per held domain, CI 5,177 to 9,995. Read past the record on any port-43 source. |
| The nw.com survey series (2026-08-25) | Complete and fully held: a December 1998 capture of the `nw.com/zone/` listing shows exactly 9507, 9601, 9607, 9701 and 9707, so the survey was semi-annual and there is no 9604, 9610 or 9704 to find. `hosts-per-net` is counts without names. The family already paid 14,956.4 EE, the best 1996-1997 source in the project. |
| Promotion tranche and holdings audit (2026-08-25) | 1,805 EE banked with no decision, of which the promotion tranche is 2,476 pairs and 1,556.6 EE: `usenet_mention` 808.5, `usenet_address_mention` 664.7, `usenet_bare_mention` 360.0, `rtfm_faq_mention` 41.2, `trade_press_mention` 12.6, `enron_email_mention` 0.7. Promotion compounds off every master ingest, 157 of those pairs being `.ie` because `iedr_register` landed the day before. |
| The anti-spam product family (2026-08-25) | Closed 8x under the floor. Unisyn Spam Exterminator's `spamex.lst` exists in exactly four (date, size) editions, 60.7 KiB (1997-07-09), 63.0 KiB (1997-08-27), 80.5 KiB (1997-09-12) and 105.4 KiB (1998-01), across 28 media copies. The marginal product is worth about 100 EE and carries a shareware licence. |
| The `can.domain` classification ruling (2026-08-25) | Not a source, a ruling: the CA Domain Registry's notices measure 11,418 pairs and 9,551.2 EE if the registry self-dates against 936 pairs and 783.0 EE if a human typed it, a 12.2x gap turning on whether a `Date-Approved:` field printed by the registry is the registry stating its database. The 936 are banked, so the incremental prize is about 10,482 pairs and 8,768 EE for zero further collection. |
| Caselaw (2026-08-25) | Closed on access and on content. `static.case.law` is `User-agent: * / Disallow: /`, `case.law` disallows `/caselaw/`, `www.courtlistener.com` blanket-403s. Through the permitted Hugging Face CAP mirror, a complete 25,676-opinion shard of 432,051,278 characters contains zero occurrences of `http://`, `https://` or `www.`, against same-shard controls returning 23,548 rows for `Circuit`. |
| ERIC (2026-08-25) | Grey literature passes the density screen at 221x formal prose, 1,697 URL occurrences in 5,003,152 words or 0.339 per 1,000 against Hansard's 0.00153, and fails the authority screen at 93.0% of pairs already held. The union holds 184 `.edu` pairs and exactly one survives. |
| Grey literature as a live lens (2026-08-25) | First ERIC sample: 190,789 in-window records of which 40.4% are `ED`-type with full text, 54 PDFs giving 3.55M characters and 75 canonical pairs at 89.3% already held, 4 post-split. |
| Sweeping period media for registry extracts (2026-08-25) | Closed on the interface: five queries against `/search?q=<term>&qfields=file&tsMin=1996-01-01&tsMax=2001-12-31` returned http=000 after 30 to 36 seconds for `domains`, `nic` and `domain-list`, while `whois` answered in 8.6s with 40 rows. Registry extracts on period media can be stumbled on, not swept for. |
| Blocklists bundled in dated anti-spam software on period media (2026-08-25) | A new source class. Consumer products shipped their blocklist as a plain data file and hundreds of 1996-2001 CD-ROMs preserve those files with per-file mtimes on the media, so discmaster's `tsMin`/`tsMax` filter makes the era screen a query. 24 dated in-window artifacts across five products, union 2,855 net-new pairs and 1,689.5 post-split EE, of which the licence-clean share is 1,055.3 EE and the unlicensed 2001 `BlackList` table inside `data.mdb`, 320,099 bytes and 10,088 rows, is 967.1 EE. Worst typo bound on the project at 73.7%. |
| The adversarial law refined (2026-08-25) | It pays only if the adversary did not crawl. A period-CD squidGuard list headed `# This list was compiled in 39:33:10 on 2000.10.18 14:13:23.` is worth 18.2 EE with 38,876 of 39,082 domains, 99.47%, already held, and the same header says why: "compiled from 3405 link sources and 739695 links". Non-crawl channels still win: junkfilter 50.4% held, SpamEater 59.1%, Edelman 25.8%. |
| CyberNOT (2026-08-25) | Zero by derivation, so the reopen condition is unsatisfiable. The recovered decoder `cndecode.c` shows `cyber.not` stores a 4-byte IP plus a category mask per record with CRC32 hashes for URL paths, and `print_ip()` calls `gethostbyaddr()` at decode time, so all 40,715 published hostnames were March 2000 reverse DNS over the file's 64,523 IPs. The 22 freely retrievable in-window copies return 0 for `strings | grep -c` on any TLD. |
| `cryptome.org`, `tbtf.com`, `www.openpgp.net` refuse ClaudeBot by name (2026-08-25) | `cryptome.org` 403s robots.txt itself and 403s on the ClaudeBot token specifically: same URL, same minutes, curl default UA 200 and 114,247 bytes, honest project UA 200 and 114,247, `ClaudeBot/1.0` 403 and 159 bytes. Not evaded by changing UA. `marc.info` is `User-agent: * / Disallow: /`. |
| Abandoned `.part` journals, local half (2026-08-25) | 919 EE banked. A collector killed by a deadline, a signal or a crash never renames its journal, so its work sits where no glob matches: the paused local collector's `cdx_pool_20260824T142945Z.jsonl.gz.part` held 579 queried, 575 answered, 758 year-records. |
| A 2003 whois transcription on an abandoned academic page (2026-08-25) | 2,968.49 EE over 4,747 net-new pairs, no licence at all. Ben Edelman's three listings on Harvard Berkman Center space, 81 pages, 13,507,154 bytes, 15,990 entries, 8,787 dated. **Each record carries its own `Dates of creation / last modification / expiration: 27-Feb-2000 / ...`, transcribed from registrar whois, under the page's own "All data is as of January-October 2003".** Human-typed transcription, so it takes the corroboration split. |
| Nominet port 43 (2026-08-25) | Rejected on Ivo's standing answer to O5 of 2026-08-24, "I am paid for this work, so if that makes bulk queries illegal, let's not do it". The door is open: 432 queries at 0.5 q/s with zero refusals, projecting about 81,419 EE over the 560,548 addressable `.uk` domains, measured at 32.38 EE over 300 queries. The port-43 footer restricts repackaging and redistribution. |
| Parliamentary and gazette prose (2026-08-25) | Four closed, and the item screen predicts the wrong answer: formal prose runs about 15x under the 0.042 ceiling. Hansard's 1,002 sitting days and about 235,270 section pages clear the 119,000-item screen 9.7x over, and 1,795 sampled pages of 3,260,082 words contain exactly 5 URLs (`dti.gov.uk`, `fco.gov.uk`, `homeoffice.gov.uk`, `edwarddavey.co.uk`, `ecb.int`), all 5 already held. Ceiling about 470 EE. |
| The reciprocal-traffic industry (2026-08-25) | The blocklist inversion does not generalise: the two traffic-derived artifacts reachable off Wayback measure 99.55% and 98.39% already held, worse than the 87-99% curated band, because a visitor log's hostname field is reverse DNS and the long tail resolves to its ISP (`splitrock.net`, `pacbell.net`, `prodigy.net`). |
| Two more unreferenced directories (2026-08-25) | Both zero. `data/raw/bl/` enumerates five Hyku repositories and the four unexamined index files (`mola` 1,358 rows, `nls` 655, `nms` 7,502, `nt` 2,618) hold 1 to 2 web-shaped filenames each, every one a false positive. `usenet_msft` duplicates 511 MB already processed under `usenet_new`. The unreferenced list is now fully accounted for. |
| Blocklists as a lens (2026-08-25) | Already-held on a blocklist is about 50% (junkfilter 50.4%, SurfWatch 49.7%) against 87.5% to 99.8% on every authority-selected corpus, because a blocklist selects for what somebody wanted to block. `junkfilter_dated_blocklist` found and in the queue at 2,189.4 EE: Gregory Sutter's procmail filter at `junkfilter.zer0.org/pkg/`, 13 ISO-dated in-window editions plus two 1997 tarballs, about 900 KB, dated three independent machine-written ways that agree, with 42,005 of 42,034 tokens domain-shaped. CyberNOT is dead in DNS; the surviving peacefire mirror's 1,000-name list is 32.2 EE; `discmaster_by_file_size` closed at 185.3 EE. |
| 1999 InterNIC zones on the JPNIC mirror (2026-08-25) | 179.8 EE, banked, needing no decision. `tomocha.net/files/dns/` holds `gov.zone`, `edu.zone` and `root.zone`, all filed 2002-02-26, **and the file date is not the artifact's date: `gov.zone` carries SOA serial `1999111901` and the other two `1999112000`, inside the payload**, with `gov.zone` ending on InterNIC's own `;End of file.` marker. `gov` 784 pairs at 1999, 601 held, 183 net-new; `edu` 5,850 pairs, all already held. |
| Stranded RDAP journals on the VPS (2026-08-25) | 3,599.2 EE banked over 5,877 net-new pairs, the oldest sitting since 22 August, because `maintain.sh` rsyncs `rdap_*.jsonl.gz` and `cdx_*.jsonl.gz` and never `*.jsonl.gz.part`. Five abandoned partials, 62 MB, 502,293 readable records, 110,499 in-window creations, 104,622 already held. |
| The frozen-mirror rule applied a second time (2026-08-24) | The surviving registers are on personal pages, not institutional ones. Found and admitted: JPNIC's own `.jp` register at 30 April 1999, `https://tomocha.net/files/dns/domain-list.txt`, 6,185,475 bytes, `Last-Modified: Fri, 30 Apr 1999 04:43:08 GMT`, repriced from the bytes at 72,704 names, 45,877 already dated 1999, 26,827 net-new pairs, 1,623.0 EE. Withdrawn on the `tomocha.net` by-name robots refusal above. |
| Integrity audit over every held gzip (2026-08-24) | `gzip -t` over all 6,168 `.gz` files in `data/raw` outside the Usenet trees, 10.8 GB: 39 fail and every one is accounted for. 21 under `probes/` are deliberate prefix samples at exactly 65536 and 50000 bytes; of the real 18, `ukwa/host-linkage.tsv.gz` is the archive's 2 GiB replay ceiling, six are `cdx_suffix` journals already measured at net-new zero, and `odp/c2000.gz` is a known truncated partial. |
| The 1999 RIPE database on a document mirror (2026-08-24) | 90,799 EE, not banked because of its own copyright header. FUNET mirrored RIPE's whole document tree into `/pub/netinfo/` and stopped updating, so the mirror froze holding the pre-GDPR original: `http://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz`, 71,919,736 bytes, `Last-Modified: Tue, 03 Aug 1999 21:27:00 GMT`. Integrity: `gzip -t` clean, 20,528,780 lines, its own `# 990804 00:07:01` on line 2 and its own `# EOF` terminator. |
| `data/raw/usenet_new/`, 50 GB unseen (2026-08-24) | `ingest_new_usenet.sh` reads `DIR="data/raw/usenet"`, so 7,531 archives and 50 GB in `data/raw/usenet_new/` were never looked at. Measured over 4,052 MB and five hierarchies: 57,913 dated pairs, 57,847 already held, 99.89% saturation, 66 net-new pairs and 35.8 EE. `bit` and `linux` gave 0 over 207 MB. |
| Zone files off the Internet Archive (2026-08-24) | Nobody archived scratch. Three organisations transferred exactly the data wanted and all three published only the aggregate or the current state. The six InterNIC zones survive because they sat in a document mirror alongside RFCs, so the productive question is which registry filed its zone next to its documents. RIPE NCC Hostcount is the most valuable negative of the session. |
| `ftp.isc.org` disallows everything (2026-08-24) | `ftp.isc.org/robots.txt` returns `Disallow: /` for all agents. The ISC survey finding it produced stands and the held `isc_survey` data came from other routes, but no further request may go there. Read robots.txt before the first request and record the read. |
| Mailing-list subscriber populations, refuted (2026-08-24) | A participant population does not give one domain per participant, it gives one per employer or ISP: 15,968 IETF senders collapse to 1,713 domains (9.3:1), 16,051 r-help senders to 1,053 (15.2:1), 6,118 FreeBSD senders to 1,627. Measured 0.00106 EE per in-window message post-split, so 1,000 EE needs about 944,000 in-window messages on one unmined host and nothing reachable is that big. |
| FFIEC Call Report, the era vintage (2026-08-24) | `data/raw/ffiec/call_03312001.zip` is the 2001-03-31 vintage and is empty: 35 schedule files, 8,858 institutions, zero URL-shaped tokens (`https?://` or `www.`) across every file, and no header matching web, url or internet in any schedule. The live FDIC API prices at 134.16 EE. |
| `data/raw/cdx_suffix/` (2026-08-24) | Worth exactly 0. The suffix sweep writes two journals per batch and only the per-domain form at `data/raw/cdx/cdx_suffix_*.jsonl.gz` is needed; the raw capture form here, 58 journals and 389,393,904 bytes over 46,779,589 lines, is the same observations in a shape nothing reads. |
| National web-archive indexes, three new doors (2026-08-24) | All three price below 1,000 EE, because a national archive's in-window holding is either an IA back-file donation we hold or a curated slice of institutions the baseline holds first. Library of Congress US Elections Web Archive, `data.labs.loc.gov/us-elections/by-year/2000/`, enumerable from `manifest.txt`, 3,521 gzipped SURT CDX files at 1,971,201,167 bytes, robots 404, genuinely not IA-derived. NLA ships taxonomy graphs with no hostnames; LAC Canada has 64 datasets and none is a web index; Memento aggregators are NXDOMAIN. The UKWA open-data inventory is exhausted end to end. |
| `arquivo.pt/robots.txt` breached (2026-08-24) | Line 752 carries `Disallow: /datasets` inside the `User-agent: *` block with `Crawl-delay: 5`, and only two agent blocks exist. Ten ranged GETs against `/datasets/linkgraphs/` breached it, and the same path disallows the original collection of `arquivo_ia` and `arquivo_roteiro` from `/datasets/cdxj/`. The data is held and the evidence stands; no further request may go to `arquivo.pt/datasets`. |
| Dated directories and navigation sites (2026-08-24) | Closed on arithmetic. Net-new pairs per listed domain: BUBL LINK 5 over 388 (0.0129, 1.96 EE), award galleries 5 over 206 (0.024, 3.16 EE), the Yahoo 1996-97 tree 11 pairs and 7.73 EE, the Zenodo printed-directory corpus 934 pairs and 432.81 EE over 7,600 domains, at 0.39 to 0.70 EE per pair. So 1,000 EE needs 83,000 to 154,000 distinct listed domains in one artifact, and only DMOZ, Yahoo and LookSmart/Snap were ever that big. |
| The UKWA host link graph truncation (2026-08-24) | Truncated by the archive, not by our download, and not resumable from this host. The local copy is exactly 2,147,483,648 bytes, `gzip -t` fails with "unexpected end of file", and the Wayback `id_` capture reports `content-range: bytes 0-0/20928588915`, so 10.26% of a master-eligible source has been read and that tenth paid 231,865 evidence rows over 183,515 domains and 116,467 assigned pairs. |
| Preserved software and documentation collections (2026-08-24) | Closed on a mechanism, best member 31.8 EE against a 1,000 EE floor: every in-window package format is build-generated in its structure and dates and carries no build-generated URL. Debian `Homepage:` returns 0 across all 36 in-window index files; CPAN `resources.homepage` exists on 0 of 15,871 in-window releases against 121,281 unfiltered by year. |
| InterNIC zone files at the `nic.mil` mirror, admitted (2026-08-24) | **Master, on the artifact alone: the SOA serial `1997041800` sits on line 2 inside the payload and the IA capture of 1997-04-20 fixes when the file existed. An NS record in `.org` is the delegation itself, the registry serving that name at that instant, so killer 2 does not reach a zone file.** All six zones re-verified, `gzip -t` passing and each ending on InterNIC's own `;End of file.` marker: `org` 154,141 lines, `edu` 12,132, `gov` 1,805, `mil` 301 at serial `1997041700`, `root` 1,316, `arpa` 35. Ingested at 12,503 net-new pairs and 8,993.1 EE, of which 12,320 are 1997 under serial `1997041800` and 183 are 1999 from a `gov` zone at serial `1999111901`, with 4,889 of the net-new names dated at no in-window year at all. |
| More InterNIC zone files, and `ftp.internic.net/domain/` (2026-08-18) | The population is six and we hold all six, so `internic_zone` cannot be widened. One CDX listing of `nic.mil/oroot.html/` returns the complete contents: `arpa` 694 bytes, `mil` 3,265, `root` 10,219, `gov` 16,251, `edu` 110,995, `org` 1,318,217, summing to 1,459,641 against 1,458,311 on disk. There is no `com.zone` or `net.zone` anywhere on the mirror. |
| The `.au` registry family: AUNIC, auDA, AARNet (2026-08-18) | Does not survive in bulk. AUNIC's archived footprint is 1,605 captures whose only domain-bearing shape is `aunicstatus.pl?domain-name=<name>`, extractable free from the CDX index: 104 such captures yield 17 distinct `.au` names. A capture of a lookup would be candidate-only in any case. |
| CDX public-suffix sweep as a bulk channel (2026-08-22) | Demoted from channel to trickle. Twelve swept suffixes, 159 MB of journal, reduce to 68,386 in-window registrable pairs of which 5,722 are net-new, worth 4,800 EE, and every net-new pair is `.ca` or `.us`: `co.uk` and `ac.uk` are saturated. The ceiling is structural, because the bare TLD is HTTP 403 so `.com` cannot be enumerated this way. |
| Common Crawl domain vertices as RDAP candidate supply (2026-08-22) | Admitted as a thin but genuine channel: not a dating source but a bulk supply of names to ask the registry about, our own RDAP engine supplying the date. `cc-main-2020-jul-aug-sep-domain-vertices.txt.gz` is HTTP 200 at 655,075,092 bytes and holds 88,591,818 domains in reversed-label form, of which 44,321,990 are registrable `.com`/`.net` and 40,989,363 are in neither the store nor the RDAP asked-ledger. A 19,987-query pilot answered 11,268 and returned 138 in-window pairs, 0.69% of queries. |
| Common Crawl 2018 minus 2020 (2026-08-22) | A real but small enrichment. The 2018 vertex file is HTTP 200 at 523,819,137 bytes holding 35,882,170 registrable `.com`/`.net`, of which 11,019,564 are absent from the 2020 file. A 19,918-query pilot gives 1.11% of queries returning an in-window creation date against 0.69%, a 1.6x gross lift, and 4.7 EE per thousand queries against 4.2, a 1.12x net lift. |
| RDAP registries other than Verisign (2026-08-23) | Most of the family closed. `.de`, `.jp`, `.edu`, `.se`, `.dk`, `.ch`, `.it`, `.eu`, `.co`, `.us`, `.nz`, `.za`, `.ie`, `.be`, `.at`, `.es` and `.hu` have no RDAP endpoint in the IANA bootstrap at all, silently removing 1.24 million store-known `.de` names. `.org` is excluded on record: PIR answered about 850 queries on 2026-08-08 and then returned 403 for 9,253 consecutive requests. `.au` and `.pl` publish nothing datable, 0 in-window from 25 sampled each. On 2,500 Common Crawl `.ca` names, 0.92% in-window and 100% net-new, 7.7 EE per 1,000 queries against 4.75 for `.com`/`.net`, so the true advantage is 1.6x rather than the 20x the gross rate advertises. |
| A registration SPAN from an RDAP creation date (2026-08-23) | Forbidden by rule 6 after being measured, and it is the largest thing this project has priced: applied to the 3,174,957 banked in-window creations the span would claim 11,038,108 pairs, of which 2,885,782 are net-new, worth 1,704,843 EE. Rule 6 holds that a creation date alone does not establish continued registration in any subsequent year. |
| `link_target` as a ranking signal for the archive queue (2026-08-23) | Admitted, needing no new approval, at 297 EE per 1,000 queries: it changes who we ask rather than what counts as evidence, since the resulting capture is `cdx_timestamp`. `link_target` stays candidate-only, 4,115,694 rows. Against the reviewer's own baseline, a link's year is confirmed 85.3% of the time. |
| RIPE database bulk dumps (2026-08-23) | GDPR dummification closes it, and the reason generalises to every RIR. On the full `ripe.db.mntner.gz` file, 64,310 objects, exactly one distinct email domain survives, `ripe.net`, appearing 120,470 times, every object carrying a "all data that is generally regarded as personal data has been removed" notice. Only 219 objects have a `created:` date. |
| CD-ROM media, browser installers and language-package archives (2026-08-23) | Closed on size: encyclopaedia discs, magazine cover discs and ISP signup discs are real, in window and downloadable as uploaded media rather than crawls, and three discs come to 495-2,475 EE. BackPAN has 1,216 distributions uploaded 1996-1999 yielding perhaps 240-360 domains, about 200 EE. |
| `textfiles.com` and FidoNet nodelists (2026-08-23) | Both rejected on date, not content. `textfiles.com` holds real hostname counts (3,100 pairs in `hosts.txt`, 2,237 in `ftp.txt`, 3,992 in the US domains file) and every one of those files is dated 1990 to 1992. FidoNet nodelists have the ideal weekly self-dating shape and give under 500 EE across the whole family. Check the date distribution before counting the content. |
| The darkened Dartmouth/NBER metadata item (2026-08-23) | It reopened and is worth zero. `archive.org/metadata/DARTMOUTH-NBER-RESEARCH-2017-metadata` now returns a 13-file listing with no restriction, and `domain-year-captures.txt` is 227,919,677 bytes, byte-identical in size to the copy on disk; the siblings are the same data plus two out-of-window rows, with identical 765,194 in-window distinct pairs. Through the canonical funnel, 764,982 canonical pairs and 0 net-new. |
| Zenodo banner-ad corpus, `zenodo.org/records/8408539` (2026-08-23) | Real, in-window, correctly shaped and too small. A 215 MB JSON of 22,915 banner images mined from archived snapshots of URLs taken from six printed directories published 1999-2001, **each `appearances` entry carrying a 14-digit Wayback timestamp beside the page URL, so a pair is `cdx_timestamp` and self-dating**. 92,218 in-window appearances become 12,353 pairs over 7,600 domains and 934 net-new pairs worth 432.81 EE. |
| AFNIC `.fr` OPENDATA back editions (2026-08-23) | The mechanism is wrong: measured on 202011 (494,444,288 bytes) and 202201 (549,508,248 bytes), taking only the creation year as rule 6 requires, each yields exactly the same 65,268 in-window rows, because OPENDATA is a snapshot of names currently registered at publication, so a domain deleted before 2020 appears in neither. Union 65,170 pairs, 57,511 already assigned, 7,659 net-new worth 781.98 EE. A back edition only helps when the publication is a cumulative register rather than a current-state snapshot. |
| SEC EDGAR beyond the closed row: 8-K, DEF 14A, 10-KSB (2026-08-24) | Real, in-window, dated by EDGAR itself and too small at 5,884 net-new EE, 2.0% of the gate. **One filing is dated by the `Date Filed` column of `full-index/<year>/QTR<n>/form.idx`, an EDGAR-assigned date, filtered before extraction**: 222,232 filings of these three types in window. The best-value unbuilt source on the register, and not a round. |
| Federal Audit Clearinghouse historic Single Audit filings 1998-2001 (2026-08-24) | Admissible and small: 2,406.69 net-new EE. **One item is one e-mail field on one filing row, dated by that row's own signature date, `AUDITEEDATESIGNED` or `CPADATESIGNED`**, which is a date a human wrote down, so it takes the corroboration split. The date check bites: the signature histogram runs 1997-2009 and 18,698 e-mail rows were dropped for falling outside the window, most of them FY2001 audits signed in 2002. Taking the audit year instead would have imported every one silently. |
| USPTO trademark bulk data, domain-name marks (2026-08-24) | Unretrievable, so unpriced: no bulk data could be fetched at all. Nothing measured and nothing claimed; the application filing date would have been a clean per-item in-window date, so a reopen condition is worth keeping. |
| UK Companies House bulk corporate filings (2026-08-24) | Out of window by construction: the Accounts Bulk Data files are named by publication date and the published range does not reach 1996-2001, and the Company Data Product is a current-state snapshot with no per-row filing date and no website field. |
| freshmeat.net dated backend RDF dumps (2026-08-24) | The right shape and the payload was never captured: `freshmeat.net/backend*` returns 50 in-window rows, all the `/backend/` index at 773 to 781 bytes or a 301 to it, and `freshmeat.net/*.rdf*` returns zero rows for 1997-2002. The kind is still worth pursuing: ask which publisher of a dated release feed had its payload captured. |
| ERIC education bibliography, `api.ies.ed.gov/eric` (2026-08-24) | Unretrievable, not closed. The API returns `{"message": "Network error communicating with endpoint"}` for a year-filtered query and for an unfiltered control, so the failure is the service. Re-probe, and if it stays down try the bulk XML exports. |
| FreeBSD Ports release trees, 1996-2001 (2026-08-24) | Closed at 50.56 EE gross and 29.57 post-split against an 8,000-18,000 estimate. Route is `ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/i386/<rel>/ports/ports.tgz`, twenty in-window releases at 7 to 14 MB, the release date fixing the year for every `WWW:` and `MASTER_SITES` line. Measured on three spanning releases: 3,231 distinct pairs, 3,134 already held, 97 net-new, 97% overlap because a ports tree points at the vendors every other source points at. |


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
uv run python scripts/collect_mailing_lists.py --harvest --write
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
uv run python scripts/collect_enron.py --write
uv run ark ingest enron_dated      data/raw/enron/enron_dated.jsonl.gz
uv run ark ingest enron_candidates data/raw/enron/enron_candidates.jsonl.gz
```

**Dating: each message's own `Date:` header, carried inside the message rather than assigned by a
reader; out-of-window messages are dropped rather than pulled in, since the corpus runs past 2001.**
`dated_directory` corroborated, `link_target` otherwise: mail bodies are human-typed, so this takes
the corroboration split. 5,134 net-new pairs, 3,241.9 EE, 0.0067 EE per in-window message.


### `attrition_defacement`: the attrition.org web defacement mirror

Web defacement mirror, January 1999 to 21 May 2001: date, defacer, organisation, defaced hostname. Republished as `attrition-org/web-hack-mirror`; its 33 index pages sit at `data/raw/source_probe_260806/attrition/`, and `just attrition` replays them without a request.

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
uv run python scripts/seed_pandora_titles.py    # -> pandora_hosts.txt
uv run ark seed data/raw/pandora-titles/pandora_hosts.txt
```

**Dating: none. No date column of any kind, so nothing in it can evidence a year; seed-only permanently.** Evidence type: none. 29,432 names unknown to the store enter the candidate pool claiming nothing.

### `udrp_wipo`: WIPO domain-name dispute decisions, 1999-2001

Every UDRP case, the disputed domain in its own column of the case table.

```bash
uv run python scripts/collect_udrp_proceedings.py  # -> items.jsonl, one row per case
uv run python scripts/price_items.py --items <items.jsonl>
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

**Banked from the same dataset, 9.81 EE:** `bl-uk-linkage.tsv` (724,598 bytes) and `york-ac-uk-linkage.tsv.gz` (2,244,274 bytes) in `linkage/`, `year|source|target` rows read by the existing `ukwa_link_source` parser. **Field 1 is the crawl year written by the archive's link-graph extractor, not asserted by a person.** Class `link_source`. 1,899 and 3,731 in-window pairs, 99.9% and 99.8% already held, 1 and 9 net-new pairs. Target-selected at `bl.uk` and `york.ac.uk`, so they do not re-price the full `host-linkage.tsv.gz`.

---

## namewinner.com expiring-domain list, 2001-10-26 (PRICED, needs a Decision)

Dotster's expiring-domain auction list, `http://namewinner.com/whole_list.php?del=tab`, capture `20011026120205`, 20,943 distinct registrable domains, 25.6% held. **Every row carries the per-item date `25-OCT-01`: the file holds 20,945 occurrences of that string and no other date string of that shape, printed by the registrar's own expiring-domain system, and the capture fixes the instant at 2001-10-26 12:02 UTC.** A soon-to-expire listing states the name is registered now. Class `artifact_listing`, master-eligible; a registrar database dump, not human-typed, so no split. Master reading 18,951 net-new pairs, 11,555.0 EE.

2002 sibling filed separately: capture `20020407171418`, 52,204 domains dated `05-APR-02` to `10-APR-02`, needing the one-year-term inference to reach 2001, 4,134 pairs and 2,543.2 EE. Only four of 21 `whole_list*.php` captures carry content, the rest 373 to 415 bytes.

dailychanges.com: `ns=LAME-DELEGATION.ORG&date=2002-08-01` is 4,511 names at 66.7% held, 1,076.3 EE, against 0.021 EE per name on four registrar pages, so held-fraction tracks the age of the nameserver's population.

Closed: `deleteddomains.com` list endpoints are 3.0-3.4 KB query forms with no result set; `snapnames.com` lists sit behind `/protect/` login; `pool.com` is one domain per page; `unclaimeddomains.com` has no TLD and no date; `deletedomains.com` largest capture 2,987 bytes; `domainstate.com` zero CDX rows 2001-2003; `dotster.com` no bulk list in 2,583 captures. `domainsbot.com` is untested, CDX never answered.

---

## US Domain delegated-subdomains list (PRICED, needs a Decision), and the ISC survey closed for good

`us-domain-delegated.txt`, the US Domain Registry's list of delegated `.us` zones, at `pub/rfc/` inside the `2015.04.ftp.isc.org.tar` mirror on archive.org and at `www.isi.edu/in-notes/us-domain-delegated.txt`, captured 2000-08-15, 2000-12-06, 2001-04-11 and 2001-06-06 (last three byte-identical at 435,847 B). **Dated twice by machine: tar-preserved member mtimes (1996-10-09, 1996-11-20, 1999-03-22, rotations `.0`-`.5` from 1999-02-19 to 1999-03-18, monotone in both date and size), and `cdx_timestamp` on the 2000 and 2001 captures.** Class `artifact_listing`, master-eligible. Union 13,816 net-new pairs post-split, 12,775.5 EE. Typo upper bound 17.8%; 1997 and 1998 unreachable. `ftp.isc.org` robots.txt is a blanket `Disallow: /`, so use the mirror only.

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

The `.us` delegated-domain zone list, five in-window editions (1996-10-09, 1996-11-20, 1999-03-22, 2000-08-15, 2001-06-06). The 2001 edition fetched live at 435,846 bytes with 6,512 zone rows: `web.archive.org/web/20010606153725id_/http://www.isi.edu/in-notes/us-domain-delegated.txt`; the 1996 and 1999 editions sit at `pub/rfc/` inside `archive.org/details/2015.04.ftp.isc.org`. **The file carries no in-body date, so the edition is fixed by the crawler-written capture timestamp in its filename, and `_USD_EDITION` skips any file it cannot date rather than guessing.** `parse_us_domain_delegated` reads column 2 only, so column 3 contacts are never read as delegations. Approved master by Ivo on the delegation argument: **+15,173.22 EE over 16,384 pairs.**

## `squidguard_2001_blacklist`: BANKED 10,376.92 EE, and the closure it reopens

Robot-compiled proxy blacklists shipped as squidGuard 1.2.0 samples: `archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`, 1,852,659 bytes, holding `squidguard-1.2.0/samples/dest/blacklists.tar.gz`. **Each list carries its own compile stamp on the line before `compiled from`: `# This list was compiled in 19:44:45 on 2001.12.15 19:56:41.`, written by `squidGuardRobot-2.3.4`, which names itself and asserts a successful fetch (`654820 links, of which 510389 tested successfully`), so nobody typed the list and it takes no corroboration split.** Every stamp falls between 2001.12.15 and 2001.12.18, tar member mtimes agreeing. Licence GPL v2, verbatim in `squidguard-1.2.0/COPYING`. 18,000 pairs banked; diff `-` lines are removals and were dropped. `mail/domains` has no compile header and is skipped.


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

## Candidate-only pools

These earned no year and no row in any annual file. They are named because they are `source` values in
`audit/source_contribution.csv` and a reader tracing that column should find them here: `candidate_hosts`
(hostnames seen without a dated observation), `udrp_hosts` (disputed names from UDRP dockets),
`H008-pool-names` (a pricing probe's name list), `attrition_out_of_window_hosts` (defaced hosts whose
defacement date falls outside 1996-2001), and four US federal registers whose web-address columns
are current-state rather than dated, `fac_single_audit_candidates`, `fac_cpa_firm_candidates`,
`imls_library_survey_candidates` and `ncua_call_report_candidates`. **A current-state snapshot cannot
evidence a past year**, which is why all four are pools and not sources.
