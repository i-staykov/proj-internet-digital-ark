# Sources

One section per source: what it is, **how to obtain it**, what fixes its dates, and why it carries
the evidence type it does.

Paths are relative to the repository root. Every ingest command assumes the file has been placed at
the path shown.

## Summary

**The per-source figures are not repeated here.** They live in
`audit/source_contribution.csv`, which `ark export` rewrites from the store on every run, and the
report's per-source table is generated from the same data. This section previously carried a
hand-copied snapshot of that file which claimed to be generated and had drifted several rounds out of
date: it omitted the largest contributor of the current round entirely and understated two others by
a factor of two. Quoting counts in two places is how they come to disagree, so this file now
describes the sources and the CSV counts them.

Columns in `source_contribution.csv`:

| Column | Meaning |
|---|---|
| `source` | the source name, matching the `source` table in `provenance/` |
| `lineage` | the provenance family, used to decide whether two sources corroborate independently |
| `evidence_type` | which taxonomy entry its rows carry, and so whether it is master-eligible |
| `files_ingested` | source files or journals folded in |
| `evidence_rows` | observations recorded, whether or not they became assignments |
| `domains_touched` | distinct registered domains the source saw |
| `pairs_backed` | (domain, year) pairs it evidences, including pairs the baseline already held |
| `netnew_pairs` | of those, the pairs that are additions against merged260730 |
| `netnew_domains` | domains absent from the baseline in every year |
| `candidate_domains` | names it found that earned no year and went to the candidate pool |

`pairs_backed` and `netnew_pairs` differ, sometimes substantially, and the feedback asks for both:
a source can independently confirm a pair the baseline already contains, which is worth recording
even though it adds nothing to the headline.

---

## `prior_task`: the supplied baseline

**What it is.** The six annual files provided with the task (`1996.txt` through `2001.txt`),
8,224,963 hostname lines, plus `merge_stats_new0714.csv`.

**Get it.** Ships in the delivery archive under `baseline/original/`. Note that this is *not* the
baseline additions are scored against; that is `baseline/merged260730/`. See `baseline/README.txt`.

```bash
cp -R <archive>/baseline/original legacy-data
uv run ark ingest-legacy
```

**Date semantics.** The file a line appears in is its year. No inference.

**Evidence type: `prior_reused`.** Prior evidence, reused as given. Excluded from the scored metric,
since it is the baseline rather than an addition.

**Caveat.** The supplied merge statistics count hostname lines while this pipeline counts registered
domains, so the two are not directly comparable.

---

## `isc_survey`: Internet Domain Survey host lists

**What it is.** The Network Wizards / ISC Internet Domain Survey `.domains` lists, a twice-yearly
walk of the DNS. Five intact files survive for 1996-1997.

**Get it.** ISC's own copies fail their gzip integrity check, so these come from a 1996 Wayback
crawl of `nw.com` and from the survey author's live site.

```bash
mkdir -p data/raw/isc_survey && cd data/raw/isc_survey
curl -O http://web.archive.org/web/19961112163532id_/http://nw.com:80/zone/9507.domains.gz
curl -O http://web.archive.org/web/19961112163635id_/http://nw.com:80/zone/9601.domains.gz
curl -O http://web.archive.org/web/19961112163826id_/http://nw.com:80/zone/9607.domains.gz
curl -O http://3waylabs.com/zone/9707.domains.gz
cd - && uv run ark ingest isc_survey data/raw/isc_survey/*.gz
```

Verify against `data/raw/checksums.sha256`, which pins all five files.

**Date semantics.** The survey date is the `YYMM` code in the filename (`wb_nw_9607` = July 1996).
Every host in that file was observed in DNS on that date, so the file's provenance fixes the year
for all of its lines.

**Evidence type: `artifact_listing`.** A line in a dated data file whose provenance fixes the year.

**Caveats.** The claim is "seen in DNS on the survey date", not "registered". The January 1997 file
is corrupt in every known copy. The raw name lists stop at July 1997, because later editions publish
only aggregate counts, which is why DNS-derived evidence here is a 1996-1997 window only.

---

## `afnic_fr`: `.fr` registry open data

**What it is.** The monthly `.fr` open-data file, one row per domain name, with creation and
permanent-deletion dates.

**Get it.** Open licence, attribution only.

```bash
mkdir -p data/raw/afnic && cd data/raw/afnic
# from https://opendata.afnic.fr/ download the current "A" file (Noms de domaine en .fr)
unzip '*_OPENDATA_A.zip'
cd - && uv run ark ingest afnic_fr data/raw/afnic/*NomsDeDomaineEnPointFr.csv
```

Source: <https://opendata.afnic.fr/>

**Date semantics, and the argument for using an interval.** Each row carries a creation date and a
permanent-deletion date (blank while registered). The evidence claim is that the domain was
registered in every year the interval covers, which requires that the registry record a *new*
creation date when a deleted name is registered again. The registry states exactly that in its
*Technical Integration Guide* v3.0 (27 February 2015), on the `domain:info` fields:

> `<domain:crDate>` … in the current version of this interface, the timestamping information is
> **not aligned with the role described in RFC 5731** but copied from the "Whois" pattern. **The
> creation date is the last creation date of the domain name** or the date of the last transmission
> (trade or recover).

Guide: <https://www.afnic.fr/medias/documents/technique/integration-guide-en-2015-02-27.pdf>

So `crDate = max(last creation, last transmission)`, and both events necessarily fall after any
prior deletion, since a deleted name must be created again to exist. The interval
`[crDate, deletion-or-now]` therefore contains no deletion event: it is continuous by construction.
Reproducible corroboration, from the open-data file plus one `whois -h whois.nic.fr` query:
`bennegens-couverture.fr` and `mintrocket.fr` were both deleted in June 2026, re-registered in July,
and now report the later creation date.

**Evidence type: `whois_creation`.** Master, for every in-window year the interval covers. Each row
stores its interval verbatim (`registered 16-03-1999..active`), so any assignment is checkable from
the row alone.

**Caveats.** Errors are one-directional: because `crDate` can only be later than the true first
registration, an in-window domain later traded or re-registered falls outside the window and is
dropped, so the tranche undercounts and cannot overcount. The file omits `.fr` names deleted before
28 January 2014. `.fr` only. Discounting the interval reading to creation years alone would remove
69,111 pairs, and since every row stores its interval, that recomputation is mechanical. This file
is republished monthly and so cannot be hash-pinned: this delivery used the June 2026 edition, and
a later download will differ wherever a domain has been re-registered since.

---

## `ukwa_link_source` and `ukwa_link_target`: UK Web Archive host link graph

**What it is.** The JISC UK Web Domain Dataset host link graph 1996-2010, rows of
`year|source_host|target_host<TAB>count`.

**Get it.** From a Wayback capture. The original address still answers HTTP 200, but with a 159-byte
HTML stub rather than the file, and the dataset DOI no longer resolves, so a direct download looks
like it worked and is not the data. The archived stream drops partway, but the file is year-sorted,
so the 1996-2001 head transfers completely.

```bash
mkdir -p data/raw/ukwa && cd data/raw/ukwa
curl -L -o host-linkage.tsv.gz \
  "https://web.archive.org/web/2019id_/https://www.webarchive.org.uk/datasets/ukwa.ds.2/linkage/host-linkage.tsv.gz"
cd -
uv run ark ingest ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz
uv run ark ingest ukwa_link_target data/raw/ukwa/host-linkage.tsv.gz
```

**Date semantics.** The year column of each row, which is the crawl year that observed the link.

**Evidence types.** The **source** host was crawled successfully that year to produce the row, so it
carries `link_source` and is master-eligible. The **target** host was merely linked to, which shows
neither existence nor activity, so it carries `link_target` and is candidate-only. The same file is
therefore ingested twice, under two source names.

**Caveats.** `.uk`-weighted by construction. A target-side row is a claim by the linking site, not
evidence about the target.

---

## `arquivo_ia` and `arquivo_roteiro`: Arquivo.pt capture indexes

**What it is.** Two CDXJ capture indexes published by the Portuguese web archive: `IA.cdxj`, a
47 GB index donated by the Internet Archive covering 1996-2007, and `Roteiro.cdxj`, a smaller
early Portuguese-web collection.

**Get it.** A resumable single-connection download; `IA.cdxj` took about 8.5 hours.

```bash
mkdir -p data/raw/arquivo && cd data/raw/arquivo
curl -C - -O https://arquivo.pt/datasets/cdxj/IA.cdxj
curl -C - -O https://arquivo.pt/datasets/cdxj/Roteiro.cdxj
cd -
uv run ark ingest arquivo_ia data/raw/arquivo/IA.cdxj
uv run ark ingest arquivo_roteiro data/raw/arquivo/Roteiro.cdxj
```

Index: <https://arquivo.pt/datasets/cdxj/>

**Date semantics.** The 14-digit capture timestamp on each line.

**Evidence type: `cdx_timestamp`.** An archived capture with an in-year timestamp and HTTP 200.

**Caveats.** Portuguese-web weighted. `IA.cdxj` is the single largest
acquisition cost in the project; skipping both indexes costs 17,696 pairs over 7,001 domains.

---

## `odp`: Open Directory Project (DMOZ) RDF content dumps

**What it is.** Three surviving ODP content dumps: a truncated prefix of the August 2000 full dump,
and two complete Kids-and-Teens dumps from 2001.

**Get it.** The live URLs now serve a "Page Has Moved" stub, so these come from Wayback. Find the
captures, then fetch them:

```bash
curl -s "https://web.archive.org/cdx/search/cdx?url=dmoz.org/rdf/*&from=2000&to=2001&filter=statuscode:200&fl=timestamp,original"
mkdir -p data/raw/odp
# then, for each capture of interest:
curl -o data/raw/odp/c2000.gz "https://web.archive.org/web/<timestamp>id_/http://dmoz.org/rdf/content.rdf.u8.gz"
uv run ark ingest odp data/raw/odp/*.gz
```

Verify against `data/raw/checksums.sha256`, which pins all three files.

**Date semantics.** The dump's own generation stamp, corroborated by the Wayback capture timestamp
and the filename (`c2000` = 2000, `kt200106` = June 2001).

**Evidence type: `artifact_listing`.** The ingested artifact is a *dated data file*, not an undated
directory page, so every catalogued external URL inside it is a line in that file and the file's own
date fixes the year.

**Caveats.** The August 2000 full dump is unrecoverable: Wayback holds only that year's
`structure.rdf`, which carries no external links. The 2001 full content dumps are not retrievable.

---

## `early_web_cdx`: Internet Archive Early Web CDX dataset

**What it is.** A published CDX dataset of early-web captures, 224 gzipped index files.

**Get it.**

```bash
uvx --from internetarchive ia download early-web_cdx-lang-cdxa \
    --glob='*.cdx.gz' --destdir=data/raw/early_web --no-directories
uv run ark ingest early_web data/raw/early_web/*.cdx.gz
```

Item: <https://archive.org/details/early-web_cdx-lang-cdxa>

**Date semantics.** The 14-digit capture timestamp on each line.

**Evidence type: `cdx_timestamp`.**

**Caveat.** It overlaps the supplied baseline almost completely, which is itself derived from the
same archive, so its 2.28M evidence rows buy few new pairs. Those rows are corroboration.

---

## `ia_cdx_bulk`: Wayback CDX verification engine

**What it is.** Not a file but a query engine: one collapsed CDX query per domain, covering all six
years, run against domains that are missing a year they are bracketed by.

**Get it.** Collection writes a journal of raw responses; ingest interprets it. The journals ship in
the delivery archive under `journals/`, so this replays offline.

```bash
uv run ark gaps                                             # choose targets
uv run ark cdx data/raw/cdx/gap_candidates.txt --workers 8  # query, writes a journal
uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz  # journal -> evidence
```

Endpoint: <https://web.archive.org/cdx/search/cdx>

**Date semantics.** The 14-digit capture timestamps returned for the domain, collapsed to distinct
years client-side.

**Evidence type: `cdx_timestamp`.**

**Caveats.** A failure is never recorded as an absence: a domain is settled only by a real answer,
so an outage costs time rather than data. Concurrency and timeout settings, and the errors
encountered, are in the report.

---

## `rdap` and `rdap_snapshot`: registry creation dates

**What it is.** Registry RDAP lookups through the `rdap.org` redirector, reading the `registration`
event year. Two source names: `rdap_snapshot` is the journalled path, `rdap` is an earlier tranche
written before journalling existed.

**Get it.** As above, collection and interpretation are separate, and the journals ship.

```bash
uv run ark gaps --creation --out data/raw/rdap/creation_candidates.txt
uv run ark rdap data/raw/rdap/creation_candidates.txt
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
```

Redirector: <https://rdap.org/>

**Date semantics.** The `registration` event date, and nothing else. An RDAP response carries the
current state plus that one historical timestamp, with no registration history.

**Evidence type: `whois_creation`, creation year only.** A creation date supports the annual file for
the year it falls in and nothing further: on its own it does not establish that the domain remained
registered in any later year. This is deliberately stricter than the `.fr` interval reading above,
because RDAP spans ~590 registries whose creation-date semantics are not established.

**Caveats.** A domain dated outside 1996-2001 attests no year and stays a candidate. The legacy
`rdap` tranche has no hashed source file, and was not re-queried, because a re-query today returns
different creation dates for domains that have since changed hands.

---

## `page_directory` and `page_expansion`: archived curated directory pages

**What it is.** Wayback captures of pages that are curated catalogues, read for the sites they list.

**Get it.** Seeds are page lists, shipped in the archive under `seeds/expansion/`. Each round fetches
the pages, then splits the results by corroboration before ingesting.

```bash
uv run ark download seeds/expansion/seeds_round2.txt --out data/raw/expand/round2/expand_round2.jsonl.gz
uv run python scripts/split_expansion_journal.py data/raw/expand/round2/expand_round2.jsonl.gz --write
uv run ark ingest expansion_directory data/raw/expand/round2/*_corroborated.jsonl.gz --round 2
uv run ark ingest expansion_links     data/raw/expand/round2/*_unverified.jsonl.gz --round 2
```

Primary catalogue used: the WWW Virtual Library, <http://vlib.org/>

**Date semantics.** The capture timestamp of the directory page. A listing dated 1998 evidences its
entries for 1998 only.

**Evidence types.** A curated page's capture date is item-level evidence for the domains it lists, so
those carry `dated_directory`. The assertion that a page *is* a curated catalogue is made per seed
and on the record: for the Virtual Library it was taken from the catalogue's own capture, which
declares itself an expert-run catalogue and lists its subject sections. Everything else, and every
name no other source attests, carries `link_target` under `page_expansion` and is candidate-only,
because archived HTML carries transcription typos and a listing is ultimately a claim by the linking
page.

**Caveats.** English-language and academically weighted. Most seeded pages have no usable in-window
capture, which is normal for 1990s hosts.

---

## `internet_scout`: Internet Scout Report archive

**What it is.** A weekly curated review of scholarly, government and educational sites.

**Get it.** OAI-PMH bulk harvest. Two things to know: a bot user agent returns 403, so send a
browser one, and the endpoint pages 20 records at a time, so follow the `resumptionToken` until it
is empty and concatenate the pages into one file.

```bash
mkdir -p data/raw/scout
curl -A "Mozilla/5.0" \
  "https://archives.internetscout.org/OAI?verb=ListRecords&metadataPrefix=oai_dc" \
  >> data/raw/scout/scout_oai.xml
# then repeat with &resumptionToken=<token from the previous page> until none is returned
uv run ark ingest internet_scout data/raw/scout/scout_oai.xml
```

Endpoint: <https://archives.internetscout.org/OAI> (the older `scout.wisc.edu/archives/OAI`
redirects here)

**Date semantics.** The `dc:date` on each record gives the issue year; `dc:identifier` gives the
reviewed URL.

**Evidence type: `dated_directory`.** An editorial entry on a dated directory artifact.

**Caveat.** Scholarly and US-weighted by editorial policy. The feed is live and keeps growing, so
it cannot be hash-pinned either; a later harvest may hold records this one did not.

---

## `ncsa_whats_new`: NCSA "What's New" announcement pages

**What it is.** The era's announcement list for newly launched sites, published as dated issues.
The only surviving 1996 editorial directory artifact here.

**Get it.** The pages come from Wayback captures of the NCSA Mosaic site, harvested to one
`domain<TAB>date` row per announced entry.

```bash
curl -s "https://web.archive.org/cdx/search/cdx?url=ncsa.uiuc.edu/SDG/Software/Mosaic/Docs/whats-new*&from=1996&to=1996&filter=statuscode:200&fl=timestamp,original"
# fetch each monthly issue with the id_ modifier, then extract the announced entries
uv run ark ingest ncsa_whats_new data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv
```

**Date semantics.** The issue date carrying the entry. Every row is 1996.

**Evidence type: `dated_directory`.** Announcement entries are editorial: a site is listed because an
editor added it on a given date. Navigation and masthead links are not entries and are excluded.

**Caveat.** US and academic bias, being one institution's announcement list. One of the 4,916 names
is attested by no other source.

---

## `ia_cdx`: per-year CDX verification (superseded)

An earlier per-year query path, kept only so its 11 rows remain attributable. Superseded by the
collapsed six-year query in `ia_cdx_bulk`, which the head-to-head comparison in the report shows is
both faster and no less accurate.

---


## NYPW first-capture index: assessed and rejected on measurement

Assessed 2026-08-01. Worth recording in full, because the initial estimate was wrong by more than
two orders of magnitude and the reason is a units error that is easy to repeat.

- **What it is.** The Internet Archive's "Not Your Parents' Web" first-capture index
  (`https://archive.org/details/nypw_urls_CDXfirstentry`), one line per URL holding that URL's
  earliest Wayback capture in eight space-delimited fields. Public, no login, 321 MB for the roots
  file. A richer sibling, `nypw_timemaps` (CC-BY 4.0), holds full TimeMaps bucketed by year, 19.35
  GB for 1996-2001.
- **The first estimate said 27,276 net-new domains.** It compared NYPW's *registered domains*
  against `sort -u legacy-data/*.txt`, which is *raw hostname lines* from the *phase-1* baseline.
  Two compounding errors: a baseline holding only `www.foo.com` makes `foo.com` look new when
  canonicalization collapses both, and the phase-1 baseline predates merged260730.
- **Measured against the store, the whole file yields 60 net-new pairs over 53 net-new domains.**
  6,281,952 lines, 2,413,003 in-window pairs over 2,354,914 distinct in-window domains, of which the
  store already holds all but 53. A 99.998% overlap, which makes sense: it is a sample of the same
  Internet Archive CDX that the baseline and this project's own `early_web_cdx` and Wayback routes already
  drain.
- **Verdict: REJECT**, and do not pursue the 19.35 GB TimeMaps sibling either, since it samples the
  same URL universe. `scripts/measure_nypw_yield.py` reproduces the measurement in about two
  minutes. The parser (`nypw_firstcdx` in `sources.py`) is kept, tested and wired, so a future
  release of the same family can be measured without rebuilding it.

## Australian Web Archive: the CDX endpoint is reachable again

Feedback section 4 asks for previously unavailable sources to be revisited. This is one, and the
earlier rejection is now half wrong.

- `https://webarchive.nla.gov.au/awa/cdx` still returns an Anubis anti-bot challenge. Dead.
- **`https://web.archive.org.au/awa/cdx` answers normally**, verified 2026-08-01: it is a pywb
  server returning `text/x-cdxj`, supporting `url`, `matchType=domain`, `from`/`to`, `limit`,
  `collapse` and `output=json`. `?url=abc.net.au&from=1996&to=2001` returns a **19961017** capture
  out of `NLA-EXTRACTION-1996-2004-ARCS-PART-04571-000005.arc.gz`, so in-window data is present.
- **It is a lookup API, not a bulk dump**, so it needs a candidate list. The natural pairing is the
  PANDORA titles list (GLAM Workbench, CC0,
  `https://github.com/GLAM-Workbench/trove-web-archives-titles`): 87,757 rows, 42,671 distinct
  hosts, 35,396 registrable domains, of which 29,727 are absent from the 1996-2001 baseline. The
  CSV has no date column, so it is seed-only and every hit needs the CDX call.
- **Measured and rejected.** The PANDORA list gives 35,391 registered domains, of which **29,595
  are in no annual file** and 29,594 are not even known to the store as domains, so on paper it is a
  large English-language pool. A random 60-domain sample was then queried against the working
  endpoint with `from=1996&to=2001`: **60 answered, 0 transport failures, and 0 with any in-window
  capture.** PANDORA's selective harvesting is simply later than this window for the long tail; the
  in-window Australian material that does exist is already held.
- **Verdict: REJECT as both a net-new and a corroboration source**, on a clean 60-domain sample
  rather than the 39-host probe that first suggested it. The endpoint correction above still stands
  and is worth keeping: it is the answer to section 4's instruction to revisit blocked sources, and
  the next person should not spend the afternoon rediscovering that the NLA host moved.

## Source names that are not separate sources

`cdx_snapshot` is the journal-ingest specification that writes under the source name `ia_cdx_bulk`;
`rdap_snapshot` writes under `rdap_snapshot`, `early_web` under `early_web_cdx`, and
`expansion_directory` and `expansion_links` under `page_directory` and `page_expansion`.
`deduplicated_urls_2001-2002` and `mid_slice` are candidate-only names with zero evidence rows,
retained so earlier seeding runs stay attributable.

---

## `uucp_map_registry`, `uucp_map_creation`, `uucp_map_mention`: the UUCP maps

**What it is.** `comp.mail.maps` carried the UUCP maps, and from 1993 the `.CA` portion was
machine-generated from the Canadian domain registry. Each posting declares its own provenance
(`#R Automatically generated from a .CA domain registration form`) and lists one entry per
registered name keyed by `#N`, with the registrar's `received:` / `approved:` dates inside.

**Get it.** Already on disk at `data/raw/usenet/comp.mail.maps.mbox.zip` (205,143,394 bytes), and
identical to `https://archive.org/download/usenet-comp/comp.mail.maps.mbox.zip`.

```bash
uv run python scripts/split_uucp_maps.py --write
uv run ark ingest uucp_listing  data/raw/uucp/uucp_listing.jsonl.gz
uv run ark ingest uucp_creation data/raw/uucp/uucp_creation.jsonl.gz
uv run ark ingest uucp_mentions data/raw/uucp/uucp_mentions.jsonl.gz
```

**How it was found, which is the useful part.** The file had been marked done in `.processed`
since 7 August and the project took nothing from it. `domains_in_message` reads http(s) URLs, bare
`www.` hosts and the `From:` address, and a UUCP map entry contains none of those, so **1,480,910
`#N` registry lines across 23,768 postings were parsed as the sender's domain and discarded.**
Before rejecting a bulk text source, check whether its payload is in a record format rather than in
sentences.

**Date semantics and the provenance gate.** Only registry-generated files are regenerated from the
live registration database at posting time, so only they may take the posting date. Verified rather
than assumed: all 8,309 in-window registry postings carry an internal generation stamp in the same
year as their `Date:` header, 569,157 of 569,157 entries at gap zero, and all 118,766
`approved:`/`received:` lines occur inside registry-generated files and none anywhere else. Classic
hand-maintained maps are reposted containers whose entries refresh only when a site admin
resubmits: of 12,486 in-window entries carrying a `#W` stamp, only 1,031 are within a year of the
posting date. Those are candidate-only. The gate costs 578.6 equivalent-English and is the
difference between a registry claim and an inference.

**Evidence types.** `artifact_listing` for the posting date, the same type the ISC DNS survey
carries. `whois_creation` for the registrar's approval date, the same type AFNIC `.fr` carries.
`link_target` for the hand-maintained half. Lineage is `registry`, not `usenet`: the maps are
registry data that happened to travel over a newsgroup.

**Measured yield, 8 August.** 53,852 listing pairs of which **23,678 net-new (19,806.2 EE)**;
19,827 creation pairs of which **4,793 further net-new (4,009.3 EE)**; 5,733 hand-maintained pairs
to the candidate pool. **Total +23,815 equivalent-English, +0.42 percentage points**, with nothing
downloaded and nothing re-crawled.

**Caveat to carry to the reviewer.** The net-new set is essentially pure `.ca` at a mean weight of
0.8365, so the whole total rides on one row of the English-share table.

---

## `rtfm_faq` and `rtfm_faq_mention`: the Usenet FAQ mirror

**What it is.** The `rtfm.mit.edu` FTP mirror, 19,478 FAQ documents under `pub/usenet-by-group`.
A FAQ carries its own revision date and lists dozens of sites.

**Get it.** `https://archive.org/download/ftp_rtfm.mit.edu_2014.07/2014.07.rtfm.mit.edu.tar`
(1,691,248,640 bytes). The live `rtfm.mit.edu` refuses connections and `faqs.org` serves a
Cloudflare challenge on every path, so the archive.org mirror is the only route.

```bash
tar -xf 2014.07.rtfm.mit.edu.tar -C data/raw/rtfm rtfm.mit.edu/pub/usenet-by-group
uv run python scripts/split_rtfm_faqs.py --write
uv run ark ingest rtfm_dated      data/raw/rtfm/rtfm_dated.jsonl.gz
uv run ark ingest rtfm_candidates data/raw/rtfm/rtfm_candidates.jsonl.gz
```

**Date semantics, and the obvious choice is wrong.** rtfm keeps exactly one copy of each FAQ, the
last one the auto-reposter sent, so `Date:` is the date of a repost and not of the content. Of
12,318 documents carrying both a `Date:` and a revision header, **6,610 disagree**, and the
disagreement is one-directional: 3,296 cases where the repost is later against 4 where it is
earlier. Using `Date:` would have stamped 1998 content as 2004. The year therefore comes from
`Last-modified:` / `X-Last-Updated:` / `Version:`, with `Date:` only as a fallback for documents
carrying no revision header. That fallback errs late rather than early, which is the safe direction
for an existence claim.

**Evidence type: `dated_directory`, after the corroboration split.** Unlike the UUCP maps these
URLs are prose typed by a human, so the ordinary Usenet rule applies. Lineage is `usenet`: a FAQ
and an announcement post confirming the same pair are one body of observation, not two.

**Measured yield, 8 August.** 8,408 in-window documents, 34,216 (domain, year) rows, of which
30,808 corroborated and **3,596 net-new**; 3,408 uncorroborated rows to the candidate pool. The raw
set difference before the split was 12,337 pairs, and quoting that would have overstated the source
by 3.4x.

---

## Evaluated and rejected

Recorded so that negative results are visible rather than silently omitted.

| Source | Verdict |
|---|---|
| Other national web archives, non-Nordic (2026-08-08) | Australia's AWA is the only one with an open index AND in-window holdings, and it is Internet Archive data: 13 of 13 cross-checked domains return an identical year set from AWA and the IA CDX, **0 AWA-only pairs**, and every in-window row comes from `NLA-EXTRACTION-1996-2004-ARCS-PART-*`, an IA donation to the NLA. Japan NDL 2002, Austria 2008, Catalonia 2005, Slovenia 2008, Croatia 2004, Netherlands 2007, Singapore 2006, Estonia 2006, Switzerland 2008, Germany 2012, Spain 2009, Italy 2006 all postdate the window. **This supersedes the reason given in the Australian Web Archive entry below**, which rests on a 60-domain PANDORA sample that found no in-window captures: a 200-domain sample of Usenet-derived `.au` candidates on the same endpoint got 41. The reject stands on redundancy with the IA, not on absence, and stating it wrongly would lead a future session to conclude the endpoint is empty when it is not |
| Nordic and Baltic national web archives (2026-08-08) | Seven of eight have no public in-window index. Iceland's `vefsafn.is` runs an open unauthenticated pywb CDX genuinely serving 1996-2001 captures, but it cannot be enumerated (`matchType=domain` over the bare TLD 502s, `showNumPages` times out, key-range scan refused), so the addressable set is capped at the 2,540 `.is` domains already known. 66 lookups, **0 truly-unknown domains, 867 projected EE = +0.017%**; 20 random `.com`/`.net`/`.org` candidates returned 0 in-window captures. The in-window material is an IA back-file donation (`ICELAND-HISTORICAL-1995-2004-*`) predating their own stated 2004 start. Sweden's Kulturarw3 began 1996 and holds 500M+ pages but is **reading-room terminal only**, no API, no free-text; `.se` carries an English share of 0.2135, so even a complete host list is low-weight. Worth an access letter, not a collector |
| Shareware and CD-ROM catalogues beyond Tucows (2026-08-08) | Info-Mac worked to exhaustion (8,446 of 8,453 in-window entries): 2,604 domains of which 2,477 already held, **124 net-new domains, 234 pairs, 134.15 EE**. garbo.uwasa.fi's complete MS-DOS master index contains **one** domain, its own. Jumbo.com per-program pages are 74-byte stubs; ZDNet Software Library info pages yield zero vendor domains. **Trap:** an archive.org scrape over `mediatype:software AND year:[1996 TO 2001] AND -collection:tucows` reports 682 net-new domains and they are entirely spurious, 15,399 of 15,521 hits coming from modern uploader `description` prose stamped with the software's release year (archive.org 1350, github.com 252, wikipedia.org 165). Tucows is safe only because its vendor URL sits in a structured `creator` field; just 68 non-Tucows in-window items have one. **There is no second Tucows** |
| Free-hosting member indexes: GeoCities, Tripod, Angelfire, Xoom, FortuneCity, Homestead (2026-08-08) | Collapses architecturally rather than empirically: every member URL is a path or subdomain under the provider's own registered domain, which the PSL canonicaliser collapses, and all ten provider domains are already held. **0 member-owned registered domains from 4 index pages.** Tripod's member-directory record carries exactly one off-host domain and it is `bfast.com`, an affiliate network, on every page. The fallback (member links pages) gives 617 domains at **97.4% already held**, and its 16 net-new names are uncorroborated so they land candidate-only. For any new free host the only question is whether members got their own registered domain, answerable in one line with `to_registrable` |
| Award galleries and cool-site lists (2026-08-08) | 206 domains across 7 dated award pages, two independent sources, all six window years: **2 net-new domains (0.97%), 5 net-new pairs, 3.16 EE**. Whole-family projection ~79 EE for ~370 archive requests, about 0.21 EE per request against the gap engine's 0.6. Award lists select the most-linked sites of their era, which is exactly what a CDX-derived baseline holds first. Record `point.lycos.com` (Lycos Top 5%) as a separate WebRing-shaped rejection: 18,496 in-window captures but **1 outbound domain in a 90 KB, 484-href 1996 listing page**, every entry linking to an internal one-site-per-page review |
| Institutional link directories: university, library, government, museum (2026-08-08) | **386 of 388 domains across 11 archived BUBL LINK pages are already held: 2 net-new domains, 5 pairs, 1.96 EE.** The deliberately chosen best-case page, a worldwide museums directory with 192 external links, gave 0 net-new. Mean English weight is high (0.7869) and novelty is near zero, because a curated institutional directory selects for authority and authoritative sites are what the baseline holds first. No bulk or non-IA route: 8 of 8 classic gateways are dead as live sites, `webarchive.loc.gov` is Cloudflare-challenged, and loc.gov's in-window web-archive slice is 15 items. ~0.02 EE per page fetch |
| Research crawl datasets, remaining angles (2026-08-08) | Family enumerated to exhaustion: academictorrents 2,851 items with **0 in-window web crawls**, `collection:webarchivedatasets` exactly 8 items with only the two already-documented `early-web_*` in window, LAW/UNIMI 2 in-window graphs (`cnr-2000` = 325,557 URLs to **1** domain), CAIDA no hostname inventory, RIPE Hostcount per-TLD aggregates only. The `early-web_parallel-language-urls` salvage **nets +374 EE, not the +6,137 first claimed**: its 9,355 net-new domains carry no timestamp of any kind, so each costs one archive query at 0.645 EE against a 0.6005 marginal displaced query, and 1,007 are already in the live queue. Scored by the project's own estimator it is **negative**. The 2,223 in-window `mediatype:web` items (alexacrawls, webwidecrawl, cuilcrawl, inaweb) carry real 14-digit timestamps and every payload is **HTTP 401**: an access negotiation, not an engineering task |
| Search-engine and portal directory trees (2026-08-08) | **Not rejected, deferred, and the economics are why.** The date basis is sound and survived a staleness attack. Measured marginal value **1.61 EE per archive request against the gap engine's 0.959**, a 1.7x advantage rather than the 25-41x first claimed, on a 95% interval of [720, 22,404] EE for 5,891 requests, median page yield 0.45 EE and **8 of 18 uniformly-sampled pages at exactly zero**. Not worth displacing a metered engine while the queue still holds 746,204 EE. **Two findings to keep regardless.** `ark.expand.outbound_domains` returns **zero** domains from every 2000-2001 `dir.yahoo.com` capture because Yahoo routed entries through `srd.yahoo.com/.../*<url>`; on current code the source reports barren, and that redirector fix is worth making anyway. And the 5,891-page `Complete_List` slice holds **zero 1996 and zero 1997 captures**; the 1996 material lives under `www.yahoo.com/<Category>/` in an unenumerated population, which matters because 1996 is the store's thinnest year (635,058 pairs against 2,946,857 for 2001) |
| Non-English regional portals (2026-08-08) | **Deferred, small but the best EE-per-request in the round.** 10 archived catalogue pages gave 1,749 raw net-new pairs, but that is a pre-split figure: `split_by_corroboration` demotes never-before-seen names to candidate-only and removes 59% of them, leaving **445 EE measured, ~1,200 projected for ~42 requests**, about 27 EE per request against the queue's 0.6. 97.4% came from **one** Indian portal (Khoj); the densest Czech page (Seznam, 1,723 domains) gave 0 and the Brazilian pages (900 domains) gave 0. Everything it produces is year 2001, already the store's fattest year. Do not seed the peer portals: the one peer tested, asiaco.com, had no archived listing pages at all |
| Stanford WebBase 2001 (via LAW) | 118M URLs to 603,245 registered domains, **99.99% already held**. Retired as a growth source |
| `deduplicated_urls_*` (supplied seeds) | Effectively exhausted: 200k lines probed yielded 3 domains not in the baseline |
| Common Crawl | Earliest collection is 2008-05; capture timestamps fail the in-window evidence bar |
| Arquivo.pt bulk `AWP*` collections | 214 files, sampled slices are all 2008. Out of window (`Roteiro` and `IA.cdxj` are the in-window exceptions) |
| UKWA per-year bulk CDX | Not publicly retrievable in 2026: dead host, soft-404 successor, 404 DOI, never Wayback-captured. Access requested |
| ODP full 2001 content dumps | Verified unavailable in 2026: the URL serves a "Page Has Moved" stub |
| ODP full Aug-2000 content dump | Unrecoverable; only `structure.rdf` was archived, which has no external links |
| Public 1998-2001 zone files | None survive anywhere checked (DNS-OARC, resellers, academic torrents) |
| Australian Web Archive (PANDORA/Trove) | **Superseded 2026-08-01, see the section above.** The earlier entry said both endpoints served an Anubis challenge. Half of that is now wrong: `web.archive.org.au/awa/cdx` answers normally |
| Other ccTLD registry open data | Nothing free reaches 1996-2001. CENTR publishes aggregates only; OpenINTEL starts 2015; commercial WHOIS is paid. AFNIC `.fr` is the sole open registry file with in-window creation dates |
| SNAP web graphs | Nodes are anonymised integers with no URL mapping |
| Yahoo! Webscope AltaVista graph | Programme unreachable; crawl date too vague for per-year evidence |
| TREC WT10g / VLC2 | Agreement-gated, distributor unreachable, small in domain terms |
| Yahoo! Directory | No machine-readable dump was ever published |
| GeoCities derivatives, DNS Census | 2009 and 2013 respectively, out of window |
| Post-July-1997 ISC `.domains` lists | Do not exist; later survey editions publish aggregate counts only |
| ISC January 1997 file | Corrupt in every known copy. Permanent gap |
| Internet Archive Alexa crawls (`alexacrawls`, `webwidecrawl`) | 226,901 items from 1996 with per-item CDX, but **every payload returns HTTP 401**; only `_meta.xml` is public. No route in |
| UKWA per-year bulk CDX (2026 recheck) | Docs survive at `ukwa.github.io/opendata/ukwa.ds.2/cdx/`; the download host serves the same 159-byte stub and the DOI now 403s behind Cloudflare. Wayback captured the directory listing but never the `.gz` files, which is why the link graph survived and the CDX did not. In-window size would have been ~13.4 GB |
| New Zealand (National Library) | Both the web archive and the open-data page return an Imperva bot interstitial. NLNZ does publish CDX to archive.org, but those items are 2025-2026 crawls. Selective harvesting only began in 1999 |
| Canada (Library and Archives Canada) | Federal web harvesting began December 2005, stated on their own front page. `open.canada.ca` returns zero web-archive index datasets. Entire archive postdates the window |
| Ireland (National Library) | Archives via Archive-It, 138 collections, earliest captures 2011 |
| `early-web_parallel-language-urls` | 1,164,183 pre-2000 multilingual URL patterns with ISO-639 codes but **no timestamps**, so no per-year evidence. Multilingual by construction, which also works against the section 6 English rule. Seed-only at best |
| OCLC Web Characterization Project | Only aggregate statistics were ever published; the host is gone |
| Mailing-list archives (2026-08-01) | Assessed because section 4 names them and they share the property that made Usenet work, a date intrinsic to the artifact. **The population is wrong even though the structure is right.** archive.org's mailing-list holdings in window are overwhelmingly hobbyist digests (`sf-lovers`, `GLOWBUGS` ham radio) with almost no commercial or website content. The W3C public lists are live and browsable at `lists.w3.org/Archives/Public/` but small and technical: `www-announce` ran for only 3 archive periods, `www-talk` 121 and `www-html` 246, all discussion among a small standards community whose domains the baseline already holds in full. A 1997 `www-announce` month carries 53 messages against the 20,000-plus domains a single Usenet commerce group yields. Not worth a parser |
| archive.org **books**, three collections tested (2026-08-05) | The idea is sound and the payload is not there. `subject:(internet)`: **57 of 60 sampled in-window items publish no downloadable `_djvu.txt`**, 2 net-new pairs. `collection:folkscanomy_computer`, chosen specifically because it is *not* lending-restricted: **36 of 40 unreachable anyway, 2 net-new pairs from 40 items.** The constraint is therefore not only lending restriction but that in-window book scans largely carry no OCR text layer. The Internet Yellow Pages editions are unreachable either way. The book route is closed |
| archive.org **`magazine_rack`** at large (2026-08-05) | 34,279 in-window items but **0.4 net-new pairs per reachable item**, against 10.5 for the computing trade press measured the same way on the same day. In-window holdings are Amiga user-group zines and laboratory newsletters, which print almost no URLs. The periodical route is only worth taking when scoped to computing and internet titles: see `docs/source_research_260805.md` |
| Boardwatch **ISP Directory** volumes (2026-08-05) | The monthly magazine issues carry `_djvu.txt`; the separately catalogued directory volumes do not. `boardwatch-directory-of-internet-service-providers-july-august-1997_djvu.txt` returns a 146-byte stub. The most ISP-dense artifact of the family is the one without machine-readable text |
| `nav.webring.yahoo.com` (2026-08-05) | **Zero in-window captures** for the entire host prefix. Wrong hostname for the period |
| WebRing member lists (2026-08-05) | Named in the phase-2 feedback and now measured. In-window captures exist under `matchType=domain` for `webring.org` (from 19961019) and `webring.com` (from 19981212), and the large ones are real pages rather than stubs: `www.webring.com/cgi-bin/webring?ring=railring&list` at 20000422003921 is 14,154 bytes. But **that page lists 20 member sites and contains 2 member URLs**: every member is linked through a redirector, `go.webring.org/go?ring=railring;id=878;go`, and the visible text carries each site's title and description with **zero bare URLs**. The member domains are not in the artifact. Recovering them costs one Wayback redirect per member against pages holding ~20 members each, which competes for IA budget with the gap engine's 96% hit rate. **Reject as a bulk source.** Two traps worth keeping: `matchType=prefix` on `www.webring.org/*` returns zero because the lists are query strings off the site root, so a wrong match type is indistinguishable from an absent source; and sorting CDX rows by `length` is what separates a real page from a stub |
| Bibliotheca Alexandrina IA mirror (2026-08-05) | `web.archive.bibalex.org` and `web.archive.org.bibalex.org` both fail to resolve; only the institutional landing page answers. This was the most promising non-IA route to early captures and it no longer exists |
| `data.webarchive.org.uk` (2026-08-05) | Does not resolve. A third distinct host tried for the UKWA bulk CDX, after the 159-byte stub and the 403 DOI. Still no route in |
| DMOZ / ODP copies on Zenodo (2026-08-05) | 12 hits, all 2018-2020 research derivatives of late DMOZ dumps. Out of window, and description text rather than dated listings. The ODP rejection stands |
| `biz.*` Usenet hierarchy (2026-08-05) | Exhausted: no unprocessed `.mbox.zip` archives remain in the 19,233-group catalogue |
| Late-starting Usenet groups (2026-08-05) | A selection rule rather than a rejection, and it costs more than any single source above. **4,023,027 of 5,283,482 messages across 28 probed archives are out of window**, concentrated in whole groups: four of the 28 contributed exactly zero net-new pairs, and `uk.misc` gave one record from 172.9 MB. Gate on in-window date coverage, not on group name or file size |


## `usenet_announce` and `usenet_mention`: dated website announcements from Usenet

Adopted 2026-08-01, and the largest single addition of this round. Giganews donated its Usenet
archive to the Internet Archive in 2013; announcement and commerce groups carry a posting date beside
the URLs in each message.

- **Where.** Full per-group mbox archives inside the hierarchy items, for example
  `https://archive.org/download/usenet-comp/comp.infosystems.www.announce.mbox.zip`. No login.
  archive.org publishes a sha1 per file, so ingests are pinnable like every other raw source.
- **A trap worth naming.** The per-date Giganews exports (`usenet-comp.infosystems`,
  `usenet-comp.internet`) look like the right files and are nearly empty in window:
  `comp.infosystems.www.announce.20140404.mbox.gz` holds nine posts, all 2005 to 2010. Use the
  `.mbox.zip` full archives in the parent hierarchy item instead.
- **Year evidence.** The `Date:` header, and the `Message-ID` is the evidence value. Message IDs are
  globally unique by design, which makes this the "opaque record identifier" the integrity checks
  already expect from a `dated_directory` row: a reviewer can name the exact post behind any year.
- **Why it matters here specifically.** The date is intrinsic to the artifact rather than recovered
  from a crawl. The 1996 and 1997 additions are 0.4% and 0.0% capture-backed, so no amount of
  archive querying reaches them; a dated post does, because it does not need the site to have been
  crawled at all.
- **Provenance lineage:** `usenet`, its own family. The corpus is a donation of posts with no common
  ancestor with any web crawl, so a pair confirmed by both Usenet and a Wayback capture is genuine
  cross-lineage corroboration rather than the same organisation agreeing with itself.
- **Choosing which of the 19,233 groups to take, measured rather than guessed.** The donation is
  411 GB and size does not predict in-window yield: `alt.www.webmaster` cost 170 MB and returned one
  pair because the whole group is 2006 to 2013. `scripts/fetch_usenet_groups.py` selects on the
  group *name* and ranks by expected yield, with announcement forums first and commerce second,
  because ordering by size put dead vanity archives at the head of the queue. 628 groups selected
  within a 100 MB per-group cap, 5.7 GB in total.
- **Two selection rules that are really the same rule.** Short tokens are matched as whole
  dot-separated components, because `talk.bizarre` contains "biz" and is not a commerce group. That
  is the trap `is_moderated_announce` hit when a suffix test reported `news.announce.conferences` as
  ordinary discussion. And `net` was tried as a component token and removed: it matches
  `alt.isd.net` and `alt.toxiccrisko.net`, which are vanity groups announcing nothing.
- **Operationally, it is the secondary stream.** It downloads from `archive.org/download/`, a
  different service from the `web.archive.org` CDX and replay endpoints the English engine uses, so
  the two coexist. Everything it finds lands in the non-English-verified set by construction, since
  a Usenet post dates a domain and says nothing about the language of its website.

**Measured yield, 54 groups of 302 shortlisted.** Net-new pairs moved 32,698 to **96,158**, with
Tucows and the candidate verification included in the later figures:

| year | before | after | change |
|---|--:|--:|--:|
| 1996 | 4,994 | 10,076 | +102% |
| 1997 | 3,534 | 15,569 | +341% |
| 1998 | 6,029 | 25,313 | +320% |
| 1999 | 696 | 14,019 | **+1,914%** |
| 2000 | 9,702 | 18,902 | +95% |
| 2001 | 7,743 | 12,279 | +59% |

The candidate pool grew from 5,583 to 41,289, and verifying part of it produced the project's first
net-new **domains**: 1,730 Usenet-discovered candidates queried against the archive, **1,065 with an
in-window capture, a 62% hit rate**. All twelve integrity checks pass.

**The admission rule, which is the whole safety argument.** The post date is trustworthy and the URL
beside it is human-typed. 35.4% of never-before-seen names are within a single edit of a name the
store already holds, and the corpus visibly contains `weddinqnetwork.com` and `dmjbuisness.co.uk`.
So the same split `expand.py` applies to archived directory pages: a domain another source already
places in an annual file is real and only its year is open, so the post dates it
(`usenet_announce`, `dated_directory`); a name appearing only in Usenet is written as
`usenet_mention` (`link_target`) and routed to the candidate pool to earn its own evidence. The test
is "appears in `domain_year`", not "appears in `domain`", because the latter includes the candidate
pool and a typo recorded by an earlier round would corroborate itself.

Group purpose is recorded but does not gate admission, and that is the one place a reviewer might
reasonably disagree. Once corroboration has established the domain is real, a URL in a dated public
post is contemporaneous evidence of use whether the group was moderated or not. Every evidence row
names its group, so filtering to moderated announcement groups only needs a query, not a reingest.

**Two parser findings.** The Giganews donation rewrote a large share of `Date:` headers as a bare
`YYYY/MM/DD`, which `parsedate_to_datetime` rejects outright: 21,346 of 23,282 messages in
`comp.infosystems.www.announce`. Before that was handled the route measured 913 pairs and nothing
before 2000; after, 6,885 across all six years. And **group size does not predict in-window
content**: `alt.www.webmaster` is 170 MB and yielded one pair, being entirely 2006 to 2013.
Out-of-window and unreadable dates are now counted separately so the two are distinguishable.

**Remaining scale.** 302 groups shortlisted, four ingested. Marginal yield was still high at the
fourth (the second pair of groups added 25,401 pairs), so this route is nowhere near exhausted.

**And the shortlist itself was the limit, measured 2026-08-05.** The name filter is now drained: all
697 downloaded archives are in `.processed` and `biz.*` holds nothing unprocessed. That looked like
the end of the route and is not. The filter only ever selected groups whose *names* contain
`announce`, `business` or `commerce`, so an ordinary discussion group had never been tried. Eleven
were: `uk.d-i-y`, `uk.finance`, `uk.local.london`, `uk.jobs.offered`, `rec.food.recipes`,
`rec.travel.usa-canada`, `comp.infosystems.www.misc` and others. Eight of them return **8,819 net-new
pairs at a mean equivalent-English weight of 0.7389**, roughly 1,102 per group, concentrated in
1999-2001. Ordinary conversation quotes URLs and every post is dated, so the announcement framing was
an accident of how the corpus was first found. 18,536 groups remain unexploited.

**The decay was then measured rather than assumed, and it is nearly flat.** 28 groups accumulate to
**20,159 net-new pairs and 14,266 equivalent-English at a mean weight of 0.7077**, against a store
already holding 8,812,701 assigned pairs. The cumulative curve fits `a * g^0.909`, an exponent close
enough to 1 that saturation has barely started, which projects to roughly 138,000 pairs at 200 groups
and 466,000 across all 761 groups of `uk.*`, `aus.*` and `can.*`. **The right selector is neither
name nor size but in-window date coverage:** 4,023,027 of 5,283,482 probed messages are out of
window, and the waste is concentrated in whole groups, four of the 28 yielding exactly zero. Reading
a few thousand `Date` headers before committing to a download removes most of it. Full measurement,
the `uk.misc` diagnosis and the parser guidance are in `docs/source_research_260805.md`.

**Measured union over 1,706 archives: 147,271 net-new pairs, 85,721 net-new domains, 98,066
equivalent-English at mean weight 0.6659.** A further 1,773 archives are on disk unmeasured, having
arrived after that measurement launched, so this is a floor for the corpus already downloaded. Measured in one pass rather than summed across tranches,
because each tranche was differenced against the store separately and adding them would double count
shared pairs. Of those, 74,508 pairs are on domains another source already attests and can carry the
post date immediately (48,821 equivalent-English); 72,763 are on names seen only in Usenet and go to
the candidate pool under the standing admission rule, at a 35.8% typo upper bound. **Small groups
yield about 37 net-new pairs per megabyte against 4.5 for large ones**, because a small archive
belongs to a group that died early and therefore falls inside the window, so the download queue
should run ascending by size. Roughly 15,000 groups remain unworked.

## `tucows_catalogue` and `tucows_mention`: the Tucows Software Library

Adopted 2026-08-01. A dated index file in the sense of III.1, and the best-behaved dating of any
source assessed this round.

- **What it is.** ~32,600 items donated to archive.org in 2004, of which **11,499 fall in window**.
  Each carries a release `date` and a `creator` field holding the software vendor's home page URL.
- **Where.** Two cursor-paginated calls, no login:
  `https://archive.org/services/search/v1/scrape?q=collection:tucows+AND+year:[1996+TO+2001]&fields=identifier,date,creator&count=10000`
- **Year evidence.** The release date, with the item identifier as the evidence value, so a reviewer
  can open `https://archive.org/details/<identifier>` and see the record.
- **Provenance lineage:** `software_catalogue`, its own family. Independent of both web crawls and
  Usenet, so agreement with either is real corroboration.

**Measured yield.** 5,258 in-window pairs over 4,239 domains, of which **1,779 pairs and 775 domains
are net-new**. After the corroboration split, **942 net-new pairs** entered the annual files and 746
domains entered the candidate pool. Concentrated late: 2001 733, 2000 580, 1999 325, 1998 126.

**Why it is split despite validating well.** Its dating is far better than Usenet's: against evidence
the store already holds, the Tucows year is exactly right **78.7%** of the time and within one year
**95.4%**, against 51.1% and 88.7% for a Usenet post date. The vendor URL is also a single structured
field rather than free text, so it carries no transcription risk.

It is still split, and the reason is the one that mattered. The catalogue was donated in 2004, so a
`creator` URL may record where a vendor lived then rather than at release. The 78.7% agreement is
measured **only on domains the store already knows**, which are the long-lived, well-covered ones.
Drift would show precisely in the names never seen before, which are exactly the 775 that would
otherwise have become net-new domains on this source's unverified word. Consistency with the Usenet
rule also beats a one-off exception.

**Hard ceiling.** 2,036 of the 11,499 in-window items carry no `creator` at all, so roughly 18% of
the catalogue cannot contribute however it is treated.

**Measured negatives in the same family**, recorded so nobody repeats them: Winsite `INDEX.TXT`
(7,057 entries, two email addresses and zero vendor domains in the whole file), Programmer's Library
`FILES.txt` (authors identified by name and postal address, no URLs at all), CNET Download.com
(excellent per-item dates, zero vendor URLs, because CNET deliberately kept users on CNET-hosted
downloads), SimTel (mirror tarball is 216 GB and the CD indexes carry no author domains). Those
indexes are pre-web in design, which settles the whole CD-ROM catalogue family at once.
