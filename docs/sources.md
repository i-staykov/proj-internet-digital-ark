# Sources

One section per source: what it is, **how to obtain it**, what fixes its dates, and why it carries
the evidence type it does.

Paths are relative to the repository root. Every ingest command assumes the file has been placed at
the path shown.

Each section carries a **Residual** line: what has been processed, what visibly remains, and what a
next pass would cost per unit of equivalent-English. That is the reviewer's standing question about
every source already used, so it is answered per source rather than in one place. Where the residual
is a guess rather than a measurement it says so.

[discovery.md](discovery.md) is the method for pricing a source before building a collector.
[brief_amendments.md](brief_amendments.md) is what is currently being asked for.

## Summary

**The per-source figures are not repeated here.** They live in
`audit/source_contribution.csv`, which `ark export` rewrites from the store on every run, and the
report's per-source table is generated from the same data. Quoting counts in two places is how they
come to disagree, so this file describes the sources and the CSV counts them. A hand-copied snapshot
once lived here claiming to be generated, and by the time anyone checked it had omitted the round's
largest contributor entirely and understated two others twofold.

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
| `netnew_pairs` | of those, the pairs that are additions against the current reviewer baseline |
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
baseline additions are scored against. That one ships beside it in `baseline/<release>/`, named for
the reviewer release it came from and identified in `baseline/README.txt`; the code's single source
of truth for which release is current is `CURRENT_BASELINE_MARKER` in `src/ark/baseline.py`.

```bash
cp -R <archive>/baseline/original legacy-data
uv run ark ingest-legacy --legacy-dir legacy-data --marker-prefix original
```

**Both flags are required.** With neither, `ingest-legacy` reads `CURRENT_BASELINE_DIR` instead, which
is the current reviewer release and not this one. With only `--legacy-dir`, the marker prefix still
defaults to the current release, the composed marker already exists in the ledger, and all six files
are skipped behind six reassuring "already ingested" lines.

**Date semantics.** The file a line appears in is its year. No inference.

**Evidence type: `prior_reused`.** Prior evidence, reused as given. Excluded from the scored metric,
since it is the baseline rather than an addition.

**Caveat.** The supplied merge statistics count hostname lines while this pipeline counts registered
domains, so the two are not directly comparable.

**Residual.** Small for year evidence and real for association work. 12,572 lines of the current
release are rejected at ingest and grouped in `output/legacy_review/dropped_domains.txt` (9,581
distinct entries: invalid hostname syntax, bare public suffixes, IP addresses, unknown suffixes); none
of them is recoverable as a registered domain, which is why they are dropped rather than pooled.
Measured: `deduplicated_urls_2001-2002.txt` yielded **0** new candidates over 1,097,867 lines, and the
2002-2014 files are out of window and can never carry an in-window year. Their value is as
association material for linking known organisations to hostnames, not as year evidence.

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

**The per-TLD host files, added 8 August.** The same 1996 `nw.com` crawl captured far more than the
`.domains` lists: **583 per-TLD host files across three survey editions**, `9607.hosts/`,
`9701.hosts/` and `9707.hosts/`, 116 MB in all, one file per TLD holding `IP hostname` pairs. Only
`9607.hosts/org.gz` had ever been fetched. `parse_isc_survey` already reads that form, so they need
no new code, only the right filename so the `YYMM` date rule fires.

```bash
uv run python scripts/fetch_nw_host_files.py   # resumable, three connections, ~2h for 116 MB
uv run ark ingest isc_survey data/raw/isc_survey/*.gz
```

The fetch has one trap in it: `http://web.archive.org/web/<ts>id_/<url>` answers **302** for these
captures, so a run that does not follow redirects writes 583 empty files and reports success.

Measured before ingest on the four largest English-weighted files of the 1996 edition (`uk`, `ca`,
`au`, `net`): **268 domains the store does not hold for 1996, worth 237.42 equivalent-English.**
There is no `com.gz` and no `edu.gz` in any edition, which caps this: the enumeration that would have
mattered most is the one the crawl did not take.

**Ingested in full on 2026-08-10, and the four-file sample understated it by two orders of magnitude.**
581 shards are now in the ledger over 24,255,322 records: 179 for the 1996-07 edition, 192 for
1997-01, 209 for 1997-07. They contributed **42,299 net-new pairs worth 14,956.3877
equivalent-English** at mean weight 0.3536, re-scored with the reviewer's own calculator with zero
records rejected.

**Where it lands is what makes it valuable, not the volume.** 4,899 records into 1996 and 37,400 into
1997, which is **+0.7001%** and **+1.4313%** against those years' own baselines, against 0.0042% to
0.1700% for the other four years. Those are the two years the Internet Archive cannot supply in bulk:
only 5.4% of 1996 pairs and 12.6% of 1997 pairs have an in-year capture at all. **This is the best
1996-1997 source in the project.**

Worth recording plainly, because it is the reviewer's first priority in miniature: the files had been on
disk since 5 August and **no ingest had ever read them**. They entered the store only because a broken
step earlier in `just sources` was fixed and the stage then ran to completion, which its glob does
automatically. The sample above was measured and then never followed up. **Diff what is on disk against
the ingest ledger before searching for anything new.**

**Residual: nearly closed, and cheaply.** `scripts/fetch_nw_host_files.py` is resumable and skips what
is present; 579 of about 583 files are down, with zero empty files, so finishing costs a handful of
requests. The hard cap stands and is not a gap in our work: no `com.gz` and no `edu.gz` exists in any
edition. The `.domains` name lists stop at 9707, confirmed from two independent live directory listings,
so there is no later edition to fetch.

**Caveats.** The claim is "seen in DNS on the survey date", not "registered". The January 1997
`.domains` file is corrupt in every known copy, and the corruption is worth naming because a partial
recovery looks like a success: ISC's `9607.domains.gz` decompresses 97% of its bytes but yields
**3,835 newlines against the good copy's 488,069**, the deflate stream having desynchronised a few
thousand lines in, after which it decodes as plausible-looking garbage. The raw name lists stop at
July 1997, confirmed from two independent live listings, `ftp.isc.org/www/survey/archive-data/` and
the survey author's `3waylabs.com/zone/`; the `WWW-9801/` and `WWW-9807/` directories on the latter
look like the missing 1998 editions and hold aggregate report HTML only. So DNS-derived evidence
here is a 1996-1997 window.

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

**Rate, measured.** The binding constraint is the archive's per-IP concurrency, not our worker count:
8 and 12 workers measure the same, **506 against 510 queries an hour**. Raising the worker count
changes the failure mode, not the rate. What raises the ceiling is a second source address. The lever
is **requests per verdict**, not requests in flight, which is why one collapsed query answering six
years replaced a six-query-per-domain loop.

**Hit rates, measured.** Two populations, and they behave very differently.

| population | what a hit gives | measured hit rate |
|---|---|---|
| gap pool: a domain missing a year it is bracketed by | the bracketed year, sometimes more | 96.0%, 96.9%, 97.1%, 97.5% on consecutive batches |
| candidate pool: a domain held with no year at all | a name that becomes net-new, not just a new year | 90.6% for a link harvested off an archived page, down to 36.9% for a name merely mentioned in Usenet text |

**Residual.** Both pools grow faster than the engine closes them, and that is structural rather than a
backlog: a larger merged baseline creates new bracketed gaps. Measured before the `merged260810` load,
the gap pool held **498,993 domains over 521,618 gap pairs** (up from 466,353) and the RDAP-addressable
pool **5,446,733 domains over 8,842,356 years** (up from 5,252,052). `merged260810` then added 946,266
pairs, so by the same mechanism the gap queue should have grown again. **Measure it before ordering a
queue off it**, because a queue written a day earlier is structurally blind to what has landed since:
that exact staleness once cost a queue 102,628 targets worth 63,333 equivalent-English.

Two thin years are thin for a reason, measured rather than assumed: on 200 pairs with no known capture,
**1996 returns an in-year capture 5.4% of the time and 1997 12.6%**, against 9.1% overall. Those years
are worth a minority share of the budget rather than none, which is what the early-year interleave in
`ark gaps` is sized from. 1996 cannot be bought from the Internet Archive in bulk; it has to be reached
deliberately.

---

## `rdap` and `rdap_snapshot`: registry creation dates

**What it is.** Registry RDAP lookups, reading the `registration` event year. Since 2026-08-08 they
go **straight to the authoritative registry**, resolved per TLD from the IANA bootstrap file, with
the `rdap.org` redirector kept only as the fallback for a TLD the bootstrap does not list. Two source
names: `rdap_snapshot` is the journalled path, `rdap` is an earlier tranche written before
journalling existed.

**Get it.** As above, collection and interpretation are separate, and the journals ship.

```bash
uv run ark gaps --creation --out data/raw/rdap/creation_candidates.txt
uv run ark rdap data/raw/rdap/creation_candidates.txt
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
```

Bootstrap: <https://data.iana.org/rdap/dns.json> (1,200 TLDs, cached at
`data/raw/rdap/iana_rdap_bootstrap.json`, refreshed weekly). Redirector, fallback only:
<https://rdap.org/>

**The candidate-pool route (2026-08-08).** The command above asks only domains that already hold a
year. The other population is the **candidate pool**, 2,537,091 names the store carries with no year
at all, of which **2,008,557 sit in a TLD that has an RDAP service and existed in the window**. A
creation date landing in window gives such a name its first year, so a hit there is a net-new domain
rather than only a net-new pair.

```bash
uv run python scripts/build_rdap_pool_list.py --tlds com,net --limit 1400000 \
    --out data/raw/rdap/pool_targets_verisign.txt
bash scripts/rdap_pool_sweep.sh 6 100000 32
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_pool_*.jsonl.gz
```

**Measured rate, 2026-08-08.** Going direct is the whole difference. Through the redirector the
pilot managed **0.83 q/s with 18.8% of queries refused with HTTP 429**: `rdap.org` is a free service
metering the client, not the registries behind it. Direct to Verisign, 2,400 measured queries per
level, **not one refusal at any level**:

| workers | rate | refused |
| --- | --- | --- |
| 4 | 19.1 q/s | 0% |
| 8 | 30.8 q/s | 0% |
| 16 | 44.4 q/s | 0% |
| 32 | **75.0 q/s** | 0% |
| 64 | 46.2 q/s | 0% |

Throughput turns over above 32 workers, and the turn is local (no refusals, no `Retry-After`), so 32
is the settled setting: a 90x improvement on the redirector. Registries are paced separately, one
`RateGovernor` per endpoint host, so a slow registry never holds up a fast one. That separation was
worth having: `.au` answered **11 queries in 10 minutes** while Verisign was running at full speed.

**Which registries are worth a night.** Probed 150 queries each, then swept the ones that paid.
Measured over the whole 391,461-query sweep, `rate` being in-window dates per **answer**:

| TLD | registry | queries | answered | in-window | rate | EE |
| --- | --- | --: | --: | --: | --: | --: |
| `.com` | Verisign | 244,279 | 244,223 | 35,074 | 14.4% | 22,170 |
| `.net` | Verisign | 114,454 | 114,447 | 11,282 | 9.9% | 5,111 |
| `.ca` | CIRA | 22,448 | 22,443 | 2,107 | 9.4% | 1,763 |
| `.org` | PIR | 10,104 | 848 | 211 | 24.9% | 150 |
| `.uk` | Nominet | 144 | 134 | 21 | 15.7% | 21 |
| `.au` | auDA | 30 | 17 | 0 | 0% | 0 |

**Where the admitted pairs actually came from**, attributed by the URL each stored row cites rather
than by which script ran: of the 48,394 net-new pairs, **48,259 came from the registries' own servers**
(Verisign 45,934, CIRA 2,106, PIR 204, Nominet 15) and **135, or 0.28%, from the `rdap.org`
redirector**, which was the initial pilot and was abandoned the same evening. That attribution matters
for one reason: the gain belongs to the direct route, so anyone reading the 90x rate improvement and
the 48,394 pairs together is reading cause and effect correctly.

Only Verisign is worth a night at this scale. It answered **244,223 of 244,279 `.com` queries** with
no decay in the answer rate and three refusals in the whole run, and the two Verisign TLDs are 1.34M
of the addressable pool. The others each failed differently and each failure is worth knowing:

- **PIR blocks rather than throttles.** It answered the first ~850 `.org` queries normally and then
  returned **403 for 9,253 consecutive requests**. RFC 7480 reserves no status for "you are blocked",
  and 403 was not in the throttle set, so the governor read every one as a plain error and never
  slowed down. It is in the throttle set now, and treated as the harsh kind that trips the breaker.
  Watch the **answer** rate, not the query rate: on queries `.org` looks like a yield collapse to
  1.6%, and on answers it is the best rate of any TLD measured.
- **Nominet refuses early and hard.** Three refusals in the first fourteen queries at 0.5 q/s, so it
  was stopped there, on the rule that a source blocked tonight is a source lost for the round.
- **`.au` dates nothing.** auDA re-registered the namespace in 2002 and the creation dates come back
  stamped with the migration.

`.au` is also the cautionary one for ranking. Ordered purely on expected equivalent-English it sorted
**first in the whole queue**, on the pool-wide prior times a 0.9904 share, ahead of 1.34M Verisign
names. Ordering by expected value will do this whenever the probability half of the estimate is a
guess, so probe a registry before spending a night on it: 150 queries is enough.

**The same mistake found again on 2026-08-10, in `.gov`, and now caught for one query.** Looking for
headroom beyond Verisign, `.gov` came fourth by unasked volume with **185,803 pool names at a 0.9825
share**, an upper bound of 182,551 EE, ahead of `.uk` and `.ca` together. It is fabricated. The
discriminator is **names holding a year against names in the pool**: `.com` 0.3, `.uk` 0.3, **`.gov`
182.0, `.mil` 2,623.6**. Against a baseline 11.4M records deep a real namespace cannot carry 182 undated
candidates for every dated one, and the sample confirms it: `wavohsdojde.gov` and `xkgnmoaeg.gov` are
invented, while `empty.gov`, `unit.gov`, `higher.gov` and `dessert.gov` are prose words a bare-host rule
read as hostnames. `.mil` is excluded already, but only because no RDAP service answers for it.
`build_rdap_pool_list.py` now prints this ratio per askable TLD and warns above 10x. It **warns rather
than excludes**, since which TLDs to drop is a judgement about the corpus and `--tlds` already acts on
it. **A high English share times an invented name is still zero.**

**Headroom, measured 2026-08-10:** 81 askable TLDs hold 2,069,480 pool names, 786,349 already asked,
so **1,357,792 have never been asked**: `com` 357,948, `net` 323,352, `org` 308,231, `gov` 185,803
(fabricated, above), `uk` 66,590, `ca` 28,191, `au` 22,596.

**`.org` is the largest plausible thing left, and it is blocked on a registry rather than on work.**
308,231 unasked names at a 0.7101 share, and unlike `.gov` its pool is a real namespace: the pool-to-dated
ratio is **1.09**, in the same band as `.net` at 1.51 and `.ca` at 1.03. Its in-window rate is also the
best measured anywhere, **24.9%**, which would put an upper bound near 54,000 EE on the unasked set.
Three reasons that bound is soft and should not be quoted as a projection: the 24.9% rests on **848
answers** before PIR returned 403 for 9,253 consecutive requests; yield decays down the list as it does
everywhere; and the pool visibly mixes real names (`royalminky.org`, `psi-corps.org`) with
harvester-munged ones (`tvgjxjxlov.org`, `wyulceufb.org`), which return 404 rather than a date. **The
next step is a small slow probe, not a sweep**, and it is a decision rather than a task: it means going
back to a registry that has already refused us, so pace it well under whatever tripped the 403, honour
every `Retry-After`, and stop on the first refusal. `SPEC.md` VI is the licence for adapting to a rate
limit rather than stopping outright; it is not a licence for ignoring one.

**Rate and decay re-measured 2026-08-10 over a fresh 300,000-query sweep of `com,net`.** Direct to
Verisign at 32 workers sustained **118 queries a second**, above the 75 q/s of 8 August, with 17
throttles in a 100,000-query batch and no refusals, so the ceiling is still not found. Of 300,000
queries, **30.2% returned a creation date of any year and 8.73% returned one in window**, giving
**0.0552 equivalent-English per query against the 0.077 the builder expected, or 72% of it**. About
311,000 names had already been asked before this sweep, so this is the tail of the head. It contributed
**26,193 records over 26,193 distinct domains worth 16,556.5953 EE** at mean weight 0.6321, every one a
net-new domain because every one was a candidate holding no year.

**The crossover question, answered with the right denominator.** The standing question was where the
RDAP tail's marginal EE per query falls below the archive queue's head. Per query the archive wins
easily, 0.7869 against 0.0552. Per **hour** it is the reverse: the archive is capped by per-IP
concurrency at about 506 queries an hour, so it buys roughly 400 EE an hour, while RDAP at 118 q/s buys
roughly 23,000. **The two bind on different constraints, so per query is the wrong denominator.** Run
both.

**Yield decays down the list, and that is what ends a sweep.** The list is ordered by how many
distinct sources saw each name, and `.com` returned 19.2% in-window over its first 100,000 queries,
11.4% over the next 100,000, then 8.4%; `.net` went 20.3% to 4.1% over 114,000. Nothing is wrong when
this happens, the pool simply runs out of names real enough to have been registered. Switch TLD when
expected EE per query falls below another list's, and stop when it falls below what the same hour
buys elsewhere.

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

A second catalogue was added on 8 August and is not worth running again: the 1996-1997 Yahoo tree
under `www.yahoo.com/<Category>/`, collected by `scripts/collect_yahoo_directory.py`. It contributed
11 pairs and 7.7295 EE from 55 archive requests and is documented as rejected in the table below;
the script stays because the route it uses, dating a page from the capture the snapshot redirect
lands on, is reusable and costs one request instead of two.

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
  same URL universe. `legacy/scripts/measure_nypw_yield.py` reproduces the measurement in about two
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

## `trade_press` and `trade_press_mention`: scanned computer magazines

**What it is.** archive.org's scanned, OCR'd computer press with hard publication dates in item
metadata. A 1997 issue printing `foo.com` dates `foo.com` for 1997, the same shape as a dated
directory page.

**Get it.** `archive.org/advancedsearch.php`, then `archive.org/download/<id>/<id>_djvu.txt`. Not
`web.archive.org`, so it competes with nothing. Two corpora, worked in that order on 8 August:

| corpus | query | in-window items |
| --- | --- | --- |
| hobbyist | `collection:computermagazines OR collection:byte-magazine OR boardwatch` | 4,030 |
| American | `collection:computerworld OR collection:pub_computerworld OR collection:applemagazines OR (identifier:bub_gb* AND (title:infoworld OR title:"network world" OR title:computerworld OR title:"pc mag"))` | 1,288 |

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

The second split takes `--journal` and `--tag` because the ingest ledger keys on content hash:
`tradepress_dated.jsonl.gz` is already ledgered, so a second corpus has to arrive under its own
name or be correctly refused with an sha256 mismatch.

**Date semantics.** The item's `year` field, the publication date of the issue. No inference.

**Evidence type: `dated_directory` after the corroboration split.** OCR fabricates hostnames, so
the pattern is anchored to the TLDs the metric rewards and every match goes through the pinned
public suffix list. Names seen only here go to the candidate pool. Lineage `trade_press`, which is
independent of every crawl, of Usenet and of the software catalogue.

**Measured yield, 8 August: 4,030 in-window items, 1,384 with retrievable text (34.3%), 79,287
(domain, year) rows, of which 25,603 corroborated and 1,334 net-new, worth 887.7
equivalent-English.**

**Verdict: real but small, and the projection was 5x optimistic. The reason is worth keeping.**
The 5 August pilot measured 10.5 net-new pairs per reachable item on a 40-item sample of
`collection:computermagazines` and projected 5,000-12,000 pairs and 3,200-7,600 equivalent-English.
Worked in full the collection turns out to be far more European and hobbyist than its name
suggests: `EnigmaAmiga`, `Elettronica2000`, `Electronique_et_Loisirs`. That is the same
composition that made the general `magazine_rack` yield 0.4 pairs an item, and a 40-item sample of
a 4,030-item collection could not see it. Reachability went the other way, 34.3% measured against
27.5% projected, so the pilot was pessimistic on access and optimistic on content, and content is
what decided it.

**The second corpus, 8 August: the American trade weeklies, and the composition theory is refuted.**
`collection:computermagazines` being European and hobbyist was read as the *cause* of the shortfall,
predicting that the American weeklies would beat it several-fold. They do not. Both corpora, both
measured against the live store at split time and both confirmed by the ingest's own `year_rows`:

| corpus | items | with text | rows | corroborated | net-new pairs | net-new EE | EE per reachable item |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hobbyist | 4,030 | 1,384 (34.3%) | 79,287 | 25,603 (32.3%) | 1,334 | 887.70 | 0.641 |
| American | 1,288 | 1,007 (79.2%) | 57,367 | 11,832 (80.0%) | 709 | 452.50 | 0.449 |

American corpus per title, from the split's own breakdown:

| title | how it is held | rows | corroborated | net-new | net-new EE |
| --- | --- | --- | --- | --- | --- |
| Computerworld, scanned | `collection:computerworld` | 6,548 | 5,068 | 314 | 200.68 |
| Computerworld, microfilm | `collection:pub_computerworld` | 5,674 | 5,024 | 311 | 198.64 |
| InfoWorld, Network World, PC Mag | Google Books `bub_gb_*` | 2,195 | 1,461 | 78 | 49.38 |
| Macworld | `collection:applemagazines` | 359 | 260 | 5 | 3.16 |

**Per reachable item the American corpus is worse, 0.449 equivalent-English against 0.641.** It is
much cleaner and much more available, which is real and is what "an American weekly prints real
company addresses" actually buys: 79.2% of items publish text against 34.3%, and 80.0% of extracted
rows are corroborated against 32.3%, so far less of it is OCR invention. It is not more *net-new*,
because a store already holding 9.6 million pairs holds nearly everything Computerworld printed.
Mean weight of a net-new pair is 0.638 here against 0.665 there: the same pairs, at the same price,
in smaller numbers. **The evidence class is saturated, and the corpus was never the variable.**

**The `.de`/`.it` explanation could not have been the mechanism, and checking it takes one grep.**
`DOMAIN_RE` only ever matched `com|net|org|edu|gov|us|uk|au|ca|nz|ie|za|sg`, so a German or Italian
address is not extracted at all and cannot dilute anything. Measured over the journals, the
hobbyist corpus's 22,229 distinct domains carry a *higher* mean English weight than the American
corpus's, **0.6825 against 0.6494**, because 6.7% of them are `.uk` at 0.9813 and 6.0% are `.au` at
0.9904, against the American corpus's 86.6% `.com` at 0.6321. A composition story that the
extractor makes impossible should not have survived one reading of the regex.

**Correction, 8 August: a third of the addresses on those pages were never read.** The shared
extractor `probe_texts_corpus.domains_in` required two labels before the TLD, so it matched
`www.foo.com` and silently dropped `foo.com`, `http://foo.com/` and `bob@foo.com`. Printed copy
drops the `www.` constantly, so this was not a rare case. Re-reading the OCR **already cached on
disk**, with no request sent, took the corpus from 30,513 (domain, year) rows to 43,816, and after
the same corroboration split **816 of those are net-new, worth 509.84 equivalent-English**, against
887.7 for the entire original run. `scripts/reextract_trade_press.py` does it:

```bash
uv run python scripts/reextract_trade_press.py --write
uv run python scripts/split_trade_press.py \
    --journal data/raw/tradepress/tradepress_reextract_<stamp>.jsonl.gz --tag reextract --write
uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_reextract.jsonl.gz
uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_reextract.jsonl.gz
```

The gained names are 654 `.com`, 72 `.net`, 57 `.org` and 8 others, so the fix lands squarely on the
TLDs the metric pays for. `split_rtfm_faqs.py` imports the same function and has the same hole, so
the rtfm corpus is worth re-reading on the same argument. The narrowness was deliberate and its
reason was sound, that a permissive dot rule over OCR turns sentence punctuation into hostnames; the
defence now sits in a lookbehind that stops a match starting inside a longer dotted token, and
`end.Company` and `readme.txt` are still refused. **This is the third time on this project that the
win was in bytes already on disk rather than in a new corpus**, after the UUCP maps and the Usenet
address forms, and all three were found by asking what the parser actually reads.

**The bare-name fix applies to the American issues too, and there it is worth more than the issues
were.** The corrected extractor landed at 19:33 on 8 August, while the American collector was
already running and holding the old pattern in memory, so its 1,007 issues were read with the
narrow regex. Re-reading the whole cache afterwards, 1,703 items rather than 855, gives **881
further net-new pairs worth 551.83 equivalent-English**, against 452.50 for the collection run
itself. Of those, 247 pairs (152.38 EE) are hobbyist-corpus names that only became corroborated
because the American ingest had just put their domains into `domain_year`, which is the
corroboration split working as intended in both directions.

```bash
uv run python scripts/reextract_trade_press.py --write
uv run python scripts/split_trade_press.py \
    --journal data/raw/tradepress/tradepress_reextract_20260808T191538Z.jsonl.gz \
    --tag american_bare --write
uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american_bare.jsonl.gz
uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american_bare.jsonl.gz
```

**Trade press total for 8 August: 1,590 net-new pairs worth 1,004.33 equivalent-English**, by title
Computerworld scanned 678 (430.56), Computerworld microfilm 521 (330.42), hobbyist corpus newly
corroborated 247 (152.38), InfoWorld/Network World/PC Mag 130 (82.05), Macworld/MacAddict 14 (8.93);
by year 1996:94, 1997:164, 1998:315, 1999:416, 2000:387, 2001:214. Attributed store-side by joining
`domain_year.evidence_id` to the `trade_press` evidence rows, not by trusting the collector's count.

**Do not re-run it wider; there is nothing left to widen to.** Verified one term at a time with
`--discover`: there is no `pub_infoworld`, `pub_network-world`, `pub_pc-week`, `pub_internet-world`,
`pub_cio`, `pub_web-techniques`, `drdobbs`, `linuxjournal` or `maccompendium` collection, in or out
of window, and no `sim_*` microfilm run of any computing title except Computerworld. InfoWorld and
Network World survive only as Google Books scans under `bub_gb_*`, which is why that query term is
written by identifier and title rather than by collection. `boardwatch`, `pcmag`, `wired-magazine`
and `internet-magazines` are not collection names either and return zero when queried as such; the
Boardwatch items reachable by free-text search are already inside the first run. The remaining large
corpora are rejected on measurement: `magazine_rack` (34,288 items, 0.4 net-new pairs each),
`folkscanomy_computer` (519 items, 36 of 40 unreachable), and **`sim_microfilm` at large** (57,245
in-window items, but a 1,500-item sample is scientific journals, government gazettes and single-page
"Table of Contents" stubs, so it is the `magazine_rack` trap at 45x the size).

---

## `usenet_address` and `usenet_address_mention`: the addresses the extractor never read

**What it is.** The same 19,083 Usenet archives already ingested, re-read for three
address forms `domains_in_message` has never looked at: `ftp://` hosts, `mailto:` links, and
addresses typed in the message body. In 1996 an `ftp://` address was often the only address a
software vendor published.

**Get it.** Nothing to fetch. The archives are already at `data/raw/usenet/*.mbox.zip`.

```bash
uv run python scripts/collect_usenet_addresses.py --workers 10
uv run python scripts/split_usenet_addresses.py --write
uv run ark ingest usenet_addr_dated      data/raw/usenet_addr/usenet_addr_dated.jsonl.gz
uv run ark ingest usenet_addr_candidates data/raw/usenet_addr/usenet_addr_candidates.jsonl.gz
```

**Why it is not the token scan that was already rejected.** A generic dot-rule scan of the same
text was measured on `alt.bbs.lists` and found 1,972 tokens the production extractor misses, of
which 354 net-new, worth at most 193 equivalent-English and visibly contaminated (`ads.my`,
`article.pl`, `lol.ie`). Every pattern here is anchored to a scheme, an `@`, or both, and the host
must end in a TLD the metric rewards. Each match goes through the pinned public suffix list.

**Date semantics.** The posting date of the message the address appears in, identical to
`usenet_announce`. Nothing new is claimed about dating.

**Evidence type.** `dated_directory` after the corroboration split, `link_target` otherwise, and
the split matters more here than anywhere else in the project. Lineage is `usenet`: an
announcement post and an address inside that same post are one observation, not two.

**Measured yield, 8 August.** Whole corpus, 404.8 GB, **507,255,617 messages of which 216,052,984
in window**, zero archive failures. **2,440,926 distinct (domain, year) pairs the current extractor
misses.** After the split: 861,988 corroborated, of which **102,577 net-new, worth 62,820.7
equivalent-English**; 1,578,938 uncorroborated rows carrying **1,474,528 names new to the candidate
pool**. Round moved 7.8676% to 9.0768%.

**The number that would have been wrong.** Quoting the raw 2,440,926 as yield would have
overstated this source **24-fold**. A 120-archive pilot (2.17 GB, 0.58% of the corpus) measured
14,581 net-new pairs worth 10,188.6 EE and its linear extrapolation came to 1.9M EE; the true
figure is 62,820.7. Both errors point the same way, and both are avoided by walking the corpus and
applying the split before quoting anything.

**Transferable finding.** Before rejecting a source that has already been ingested, check what the
parser actually reads. Two of this sprint's three wins came from files already on disk and already
marked processed.

---

## `usenet_bare` and `usenet_bare_mention`: the bare `foo.com` in the message bodies

**What it is.** The same 19,231 Usenet archives, read a third time, for the one address form no
extractor here has ever looked at: a plain `foo.com` written in prose with no scheme, no `www.` and
no `@`. `domains_in_message` reads `http(s)://`, `www.` hosts and the `From:` header;
`usenet_address` added `ftp://`, `mailto:` and typed email addresses. Every one of those is anchored
on a scheme, a `www.` label or an `@`. In 1996-1999 people wrote addresses bare constantly.

**Get it.** Nothing to fetch, nothing to download, no network at all.

```bash
uv run python scripts/collect_usenet_bare.py --sample 400 --workers 8    # project first
uv run python scripts/project_usenet_bare.py --journal data/raw/usenet_bare/<file> --archives 400
just usenet-bare                                                        # or the whole corpus
```

**Why the refusal was reversed, which is the whole argument.** `_BARE_WWW` was deliberately anchored
on the `www.` label, on the reasoning that a bare name in running prose is more often a company name,
a file name or half an email address than an address, and that the evidence wall was worth more than
the recall. That reasoning is sound about prose and wrong about where the wall is. **Every row from
this corpus passes `split_by_corroboration` before it can date anything.** A (domain, year) becomes a
dated master record only when an independent lineage already places that domain in `domain_year`, and
a company name or a file name is not a registered domain any independent lineage attests. It lands in
the candidate pool and asserts nothing. The pattern can therefore afford recall, because the split,
not the pattern, is the defence. Measured: **36.3% of the extracted rows were uncorroborated and went
to the pool**, which is the wall doing its work in public.

**The false-positive guards, all in `ark.usenet` and all unit-pinned.** A TLD allowlist, the same one
the trade-press extractor uses, because the TLD is the only anchor a bare name has. A lookbehind
`(?<![\w.@/-])` that stops a match starting inside a longer dotted token, keeping this off hosts
already inside a URL or an email address. A lookahead `(?![a-z0-9@-])` that refuses `end.Company` and
refuses a domain-shaped email local part like `john.com@example.org`. Greedy labels so `foo.com.au`
matches whole rather than being read as `foo.com`. An all-digits rule, because `4.0.2.au`
canonicalises to the invented name `2.au`. And **body text only, never headers**: `Path:`, `Xref:`
and `Newsgroups:` are dotted tokens by construction, and a bare rule over them reads news servers and
vanity newsgroup names such as `alt.isd.net` as announced websites.

**Date semantics.** The posting date of the message, identical to `usenet_announce`. Nothing new is
claimed about dating. **Evidence type** `dated_directory` after the split, `link_target` otherwise.
**Lineage** `usenet`: a URL, an address and a bare host in one post are one observation, not three.

**Measured yield, 8 August, whole corpus.** 411.0 GB, **515,079,416 messages of which 219,447,104 in
window**, zero archive failures, about three hours at 8 workers. 6,155,415 in-window messages carry a
bare host no existing extractor sees, giving **601,738 distinct (domain, year) pairs**. After the
split: 383,106 corroborated and 218,632 to the candidate pool, of which 145,442 names were new to it.
**42,139 of the corroborated pairs were not yet held, worth 28,460.3 equivalent-English**, measured as
the scoreboard delta across the ingest and not as a set difference. Round moved 9.9464% to
**10.4525%**. All integrity checks pass.

**Overlap is most of the gross, which is why only the marginal figure is quoted.** Of the 601,738
extracted pairs, **269,773 were already asserted by `usenet_announce` or `usenet_address`** and
340,963 were already assigned by some source. The gross carries 416,446.4 equivalent-English, so
quoting it would have overstated this source **15-fold**; quoting the corroborated half without
deduping against what is already held would have overstated it nine-fold on pairs.

**The projection held, and the sample was honest about its own uncertainty.** A 400-archive evenly
spaced sample (13.7 GB, 2.1% of archives) measured 1,321 marginal pairs worth 837.08 EE against the
live store. Linear said 40,245 EE, the saturating fit said 31,724, a power law fitted to the sample's
own curve said 18,873 with an exponent of 0.88. The truth was 28,460.3, inside that spread and 71% of
the linear figure. Two things made the difference from the header-mode failure that projected 10,889
and delivered 1,038: the sample was measured against the **live** store rather than a snapshot taken
before an intervening ingest, and it was deduped explicitly against both existing Usenet sources.

**Where it comes from, which is a finding in itself.** The single largest contributor is
`can.domain`, the CA registry newsgroup, at 7,137 net-new pairs, followed by
`alt.domain-names.forsale` at 1,858 and `alt.sources` at 844. By TLD the net-new pairs are 25,898
`.com`, 7,640 `.ca`, 4,145 `.net`, 1,977 `.org` and 1,689 `.uk`, so the yield lands on the TLDs the
metric pays for. By year it is heaviest exactly where the crawl is weakest, 9,498 in 1998 and 11,192
in 1999.

**One limitation, named rather than hidden.** 1,200 of the 42,139 net-new pairs are first seen in
`comp.mail.maps` or `can.uucp.maps`, which are registry map postings that `ark.uucp` already parses
properly under the `registry` lineage. Reading them again as prose files those rows under `usenet`,
so a pair carrying both could look independently corroborated when it is one posting read twice.
This is 2.8% of the yield, it is the same treatment `usenet_announce` and `usenet_address` already
give those groups, and every evidence row names its group, so a reviewer who wants them out needs a
query rather than a reingest.

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

**Re-read later the same day, +1,570 pairs and +1,167.4 EE, no request sent.** This script imports
`probe_texts_corpus.domains_in` rather than copying it, so it inherited that extractor's fix for
free: the pattern used to require two labels before the TLD, reading `www.foo.com` and dropping
`foo.com`, and a FAQ drops the `www.` constantly. The same 8,408 documents went from 34,216 rows to
**46,583**, of which 40,922 corroborated. A re-run needs `--tag`, because the ingest ledger keys on
content hash and refuses a rewritten journal under an already-ingested name.

```bash
just rtfm-faqs reextract
```

**The transferable part.** An imported extractor spreads its bugs and its fixes silently. When
`domains_in` changes, every corpus reading through it is stale until re-run, and nothing in the
pipeline says so. Both re-reads found their yield in bytes already on disk.

---

## Evaluated and rejected

Recorded so that negative results are visible rather than silently omitted.

| Source | Verdict |
|---|---|
| Microsoft Bookshelf Internet Directory, 1996 CD-ROM (2026-08-11) | **Rejected on measurement: 7 net-new pairs and 4.7 equivalent-English after the corroboration split.** Found by web search rather than recall, and worth recording because it is a real distinction inside a family already closed: the `cdbbsarchive` verdict says of shareware discs "not measured, and not worth measuring", and a 1996 Microsoft *Internet Directory* is a different payload with no OCR in it at all. So the closure's central argument, that for an OCR source the net-new half and the damaged half are the same population, did not apply. Measured anyway and it fails on overlap instead: the 99 MB ISO yields 2,020 distinct (domain, 1996) pairs of which **1,863, or 92.2%, are already held**, and the raw net-new figure of 157 pairs overstates the source **25.9x** against the 7 the split admits. **The typo bound is the useful number: 66.9% of the net-new names are one edit from a name the store already holds**, because the actual URL payload sits inside a compressed 1996 Microsoft Multimedia Viewer database and what is extractable in plain bytes is a keyword index of site titles plus Usenet group names. Treated as `typed` rather than self-dating for exactly that reason, so the contamination went to the candidate pool instead of into annual files. **Reopen only on a decoder for the .MVB payload**, which would be a different and much cleaner extraction |
| Web defacement mirrors other than attrition.org (2026-08-10) | **Closed on availability, and it was the best remaining idea in the class that pays.** The three sources that worked this round are machine-generated records about *all* domains rather than human curation of notable ones, which is why they are net-new where curated directories are not, and a defacement mirror is exactly that: self-dating `artifact_listing`, no corroboration split, and the population is whoever got hacked rather than whoever was famous. attrition's own index copies its pre-1999 entries from **earlier mirrors**, so siblings demonstrably existed. None survives as retrievable data. archive.org holds **0** items for `alldas` and **0** for `safemode defaced`, and its 212 hits for `defacement` are unrelated (a 2011 news clip, a malware source dump, Indian parliamentary library scans). GitHub, which is the only reason attrition's own mirror survives at all after its 2021 republication, holds no sibling: `alldas` returns 14 repos and every one is an unrelated modern dashboard, and the sole defacement archive there is `Mirror-H.org`, a 2010s collection well out of window. **Reopen only on a named surviving mirror**, since the family is right and the artifacts are gone |
| Linux Software Map, ibiblio LSM snapshots (2026-08-10) | **Generated by `just screen`, priced the same hour, rejected: 86 net-new pairs and 37.3 equivalent-English after the split.** The structure is ideal and is why it was worth an hour: `https://www.ibiblio.org/pub/Linux/docs/LSM/` serves dated snapshots in window (`LSM.1999-08-29`, `LSM.1999-08-30`, then monthly `LSM.2001-06-01` to `LSM.2001-12-01`), each record is a `Begin3 ... End` block carrying its own `Entered-date` beside `Primary-site`, `Alternate-site`, `Author` and `Maintained-by`, so the date is intrinsic to the record and the hostname sits next to it. That is the Tucows shape, which worked. **The population is wrong.** 4,560 records, 3,946 in window, 3,951 distinct in-window pairs over 2,066 domains, and **3,743 of the pairs, 94.7%, are already held**. Of the 208 that are not, the corroboration split admits **86, worth 37.3 EE at mean weight 0.4338**, with `.de` the second TLD; 122 pairs and 56 names go to the pool. A Linux author's own homepage is exactly the heavily-crawled population a CDX-derived baseline holds first, which is the fifth family to fail this way after relay hops, institutional directories, award galleries and mailing lists. **Two facts worth keeping.** The snapshots are **not** purely cumulative: the 1999-08-29 file carries 897 in-window pairs the 2001-12-01 file does not, so a single latest snapshot is not the whole source. And `Entered-date` is written at least four ways (`27OCT97`, `1999-08-29`, `12/03/98`, `Oct 1997`), so a single-format parser silently drops most of the corpus. Two requests to a non-IA host, no IA budget spent |
| Printed Internet directory books, the whole named family (2026-08-08) | **Closed from three directions, and the 5 August entry below understated why.** The canonical titles do exist and were enumerated rather than guessed: a title query over `mediatype:texts AND year:[1994 TO 2002]` returns 34 of them, including `internetyellowpa00hahn` (Hahn 1994), `newridersofficia0000unse` and `newridersofficia00lorn` (New Riders 1996 and 1998), `quesofficialinte0000turn` (Que 2001 edition), `harleyhahnsinter00hahnrich` (2000), `mecklermediasoff0000unse` (1996), `luckmansworldwid0000unse_1997ed`, `wholeinternetuse00edkr` (Krol 1994) and `1998aolmembersed0000newr`. **Every one of the 34 is `inlibrary`/`printdisabled`.** (1) The text files are listed in item metadata but `_djvu.txt` and `_hocr_searchtext.txt.gz` both return **HTTP 401**, verified on four volumes. (2) Search-inside is not a way round it: `fulltext/inside.php` returns **403 Item not available** on the correct `path`, and returns `{"matches":[],"error":"No hOCR or Abbyy file present"}` on a wrong one, so a bad parameter is indistinguishable from an empty book unless both are tried. `api.archivelab.org` no longer resolves. (3) The open-access complement is not the same population: the same title query with `-collection:inlibrary -collection:printdisabled` leaves **144 items and not one directory book**, being ERIC education papers, microfiche and museum-website evaluations. **And the payload would not have paid anyway**, which is the finding to keep: HathiTrust Extracted Features is the legitimate non-consumptive route into in-copyright print, it was measured on 69 in-window volumes at 15.7 net-new pairs each, and the net-new names are `0fficemed.com`, `0steopath0mline.com`, `26o0.com`. **Re-measured on 2026-08-11 and the verdict holds**, which is recorded because the re-measurement should not have happened: the 71 EF volumes were still on disk, `just screen` reported this entry as closed on *availability* and told a reader to re-probe it, and its single-valued classifier hid the fact that the HathiTrust half was closed on a **measurement**. The independent run: 69 in-window volumes, 2,551 hostname-shaped tokens, 1,425 distinct in-window pairs, of which 1,124 of 1,284 matched pairs are already held, leaving **74 net-new pairs and 49.4 equivalent-English after the corroboration split** against a ~5,000-pair bar, and a 64.4% typo bound that here measures OCR damage rather than signal. The screener now reports both closure reasons when an entry carries both. **For an OCR source the net-new half and the OCR-damaged half are the same population**, because the real domains in these books are already held; usable yield was ~330 EE for 6+ hours. Do not reopen on a new identifier list |
| SEC EDGAR filings 1996-2001 (2026-08-08) | Genuinely untried, born-digital rather than OCR, hard filing dates, US commercial filers, and **measured at a reject**. 150 filings stratified across the six years from `full-index/<year>/QTR<n>/form.idx`, biased towards the forms most likely to print an address (10-K, 10-K405, S-1, SB-2, 424B): **150 of 150 reachable, 61.1 MB, and 46 (domain, year) pairs in total.** Against the store that is **4 net-new pairs, 3 of them corroborated, 1.9 equivalent-English, or 0.01 EE per filing.** Filings are legal and financial prose that barely print URLs, and the filers that do are large public companies the baseline holds first, which is the same failure mode as award galleries and institutional directories. Whole-window projection over ~530,000 filings is ~5,000 EE for roughly 200 GB of download. The born-digital argument is real and is why this was worth testing, but density beat it |
| InterNIC public zone files, via Wayback (2026-08-08) | The existing "no 1998-2001 zone files survive" entry lists DNS-OARC, resellers and academic torrents as checked and **not Wayback**, which is precisely how the ISC survey files were recovered from `nw.com`. Now checked and still absent: `internic.net` under `matchType=domain` holds 8,001 captures of which **16 have a path resembling data at all**, and those are `cgi-bin/whois?...` single-domain lookups, not bulk files. `ftp.internic.net/domain` and `rs.internic.net/domain` captures are 2017-2018 directory stubs of 435 bytes. **A trap that cost a false negative first:** passing `url=host/path/*` together with `matchType=prefix` returns **zero** even for captures known to exist, so the control query `nw.com/zone/*` reported the ISC files absent; drop the `*` and it returns 41 rows. Any CDX zero from a prefix query must be re-run against a known-good control before it is believed |
| Usenet `Path:` relay chains (2026-08-08) | The premise holds and the parser works: a 400-archive random sample (6.60 GB, 9,136,539 messages, 4,156,456 in window) reads 9,719,750 hop tokens as 7,112,259 accepted hosts (73.2%), 1,516,019 dotless UUCP node names, 793,245 pseudo-hops and 298,227 public-suffix rejects that are overwhelmingly bare IP addresses. **Those 7.1M accepted hops collapse to 4,736 distinct domains and 7,201 (domain, year) pairs, of which 49 are net-new against the LIVE store after the corroboration split: 13.89 equivalent-English.** Two structural reasons, each fatal alone. A relay is a large ISP or a university, which is exactly the population a CDX-derived baseline holds first in every year, so **99.32% of sampled pairs are already held or uncorroborated** and the 49 survivors average an English weight of 0.2834 because the tail that is left is `.jp`, `.de`, `.dk`, `.ch`. And the Giganews donation carries the header only from 2000: of 886,496 in-window `Path:` lines, **1996-1999 account for 887 and 2001 alone for 750,686**, so the seam cannot reach the thin years at all (fresh pairs by year: 1996 zero, 1997 zero, 1998 two, 1999 zero, 2000 twenty-eight, 2001 nineteen). That is absence rather than a parser bug, and it was checked: only 138 messages of 3,269,960 hid the header past the 4 KB head window. Honest log-saturation projection over the whole 383 GB corpus is **~15,300 raw pairs and ~30 EE**; even the linear extrapolation that overstated the recovered-address seam 24-fold gives 668 EE, against a 3,000 EE bar. Forged hops are present and visible (`2dafkyapz7.net`, `9hehgkrs.net`, `3o4rihgoih.no`), the same family as the `dumicsamvfs.mil` forgeries already on record; the split routes them to candidates, so they cost nothing, but they confirm a `Path:` line is free text of the riskiest kind |
| Other national web archives, non-Nordic (2026-08-08) | Australia's AWA is the only one with an open index AND in-window holdings, and it is Internet Archive data: 13 of 13 cross-checked domains return an identical year set from AWA and the IA CDX, **0 AWA-only pairs**, and every in-window row comes from `NLA-EXTRACTION-1996-2004-ARCS-PART-*`, an IA donation to the NLA. Japan NDL 2002, Austria 2008, Catalonia 2005, Slovenia 2008, Croatia 2004, Netherlands 2007, Singapore 2006, Estonia 2006, Switzerland 2008, Germany 2012, Spain 2009, Italy 2006 all postdate the window. **This supersedes the reason given in the Australian Web Archive entry below**, which rests on a 60-domain PANDORA sample that found no in-window captures: a 200-domain sample of Usenet-derived `.au` candidates on the same endpoint got 41. The reject stands on redundancy with the IA, not on absence, and stating it wrongly would lead a future session to conclude the endpoint is empty when it is not |
| Nordic and Baltic national web archives (2026-08-08) | Seven of eight have no public in-window index. Iceland's `vefsafn.is` runs an open unauthenticated pywb CDX genuinely serving 1996-2001 captures, but it cannot be enumerated (`matchType=domain` over the bare TLD 502s, `showNumPages` times out, key-range scan refused), so the addressable set is capped at the 2,540 `.is` domains already known. 66 lookups, **0 truly-unknown domains, 867 projected EE = +0.017%**; 20 random `.com`/`.net`/`.org` candidates returned 0 in-window captures. The in-window material is an IA back-file donation (`ICELAND-HISTORICAL-1995-2004-*`) predating their own stated 2004 start. Sweden's Kulturarw3 began 1996 and holds 500M+ pages but is **reading-room terminal only**, no API, no free-text; `.se` carries an English share of 0.2135, so even a complete host list is low-weight. Worth an access letter, not a collector |
| Shareware and CD-ROM catalogues beyond Tucows (2026-08-08) | Info-Mac worked to exhaustion (8,446 of 8,453 in-window entries): 2,604 domains of which 2,477 already held, **124 net-new domains, 234 pairs, 134.15 EE**. garbo.uwasa.fi's complete MS-DOS master index contains **one** domain, its own. Jumbo.com per-program pages are 74-byte stubs; ZDNet Software Library info pages yield zero vendor domains. **Trap:** an archive.org scrape over `mediatype:software AND year:[1996 TO 2001] AND -collection:tucows` reports 682 net-new domains and they are entirely spurious, 15,399 of 15,521 hits coming from modern uploader `description` prose stamped with the software's release year (archive.org 1350, github.com 252, wikipedia.org 165). Tucows is safe only because its vendor URL sits in a structured `creator` field; just 68 non-Tucows in-window items have one. **There is no second Tucows** |
| Free-hosting member indexes: GeoCities, Tripod, Angelfire, Xoom, FortuneCity, Homestead (2026-08-08) | Collapses architecturally rather than empirically: every member URL is a path or subdomain under the provider's own registered domain, which the PSL canonicaliser collapses, and all ten provider domains are already held. **0 member-owned registered domains from 4 index pages.** Tripod's member-directory record carries exactly one off-host domain and it is `bfast.com`, an affiliate network, on every page. The fallback (member links pages) gives 617 domains at **97.4% already held**, and its 16 net-new names are uncorroborated so they land candidate-only. For any new free host the only question is whether members got their own registered domain, answerable in one line with `to_registrable` |
| Award galleries and cool-site lists (2026-08-08) | 206 domains across 7 dated award pages, two independent sources, all six window years: **2 net-new domains (0.97%), 5 net-new pairs, 3.16 EE**. Whole-family projection ~79 EE for ~370 archive requests, about 0.21 EE per request against the gap engine's 0.6. Award lists select the most-linked sites of their era, which is exactly what a CDX-derived baseline holds first. Record `point.lycos.com` (Lycos Top 5%) as a separate WebRing-shaped rejection: 18,496 in-window captures but **1 outbound domain in a 90 KB, 484-href 1996 listing page**, every entry linking to an internal one-site-per-page review |
| Institutional link directories: university, library, government, museum (2026-08-08) | **386 of 388 domains across 11 archived BUBL LINK pages are already held: 2 net-new domains, 5 pairs, 1.96 EE.** The deliberately chosen best-case page, a worldwide museums directory with 192 external links, gave 0 net-new. Mean English weight is high (0.7869) and novelty is near zero, because a curated institutional directory selects for authority and authoritative sites are what the baseline holds first. No bulk or non-IA route: 8 of 8 classic gateways are dead as live sites, `webarchive.loc.gov` is Cloudflare-challenged, and loc.gov's in-window web-archive slice is 15 items. ~0.02 EE per page fetch |
| Research crawl datasets, remaining angles (2026-08-08) | Family enumerated to exhaustion: academictorrents 2,851 items with **0 in-window web crawls**, `collection:webarchivedatasets` exactly 8 items with only the two already-documented `early-web_*` in window, LAW/UNIMI 2 in-window graphs (`cnr-2000` = 325,557 URLs to **1** domain), CAIDA no hostname inventory, RIPE Hostcount per-TLD aggregates only. The `early-web_parallel-language-urls` salvage **nets +374 EE, not the +6,137 first claimed**: its 9,355 net-new domains carry no timestamp of any kind, so each costs one archive query at 0.645 EE against a 0.6005 marginal displaced query, and 1,007 are already in the live queue. Scored by the project's own estimator it is **negative**. The 2,223 in-window `mediatype:web` items (alexacrawls, webwidecrawl, cuilcrawl, inaweb) carry real 14-digit timestamps and every payload is **HTTP 401**: an access negotiation, not an engineering task |
| Search-engine and portal directory trees (2026-08-08, re-opened and now **rejected**) | Deferred on 8 August on two facts. **The first was a bug and is fixed:** `ark.expand.outbound_domains` returned zero from every `dir.yahoo.com` capture because Yahoo routed entries through `srd.yahoo.com/.../*<url>`, and `unwrap_redirect` now turns that same 20000817191821 capture from **0 domains into 3**. So the family had genuinely been measured on broken code. **The second was true and is worth nothing.** The 1996-1997 catalogue does live under `www.yahoo.com/<Category>/` in a population nobody had enumerated; walked and ingested the same evening it gives **1997: 20 requests, 295 domains, 9 pairs, 6.1161 EE (0.3058/req); 1996: 30 requests, 182 domains, 0 pairs, 0.0000 EE; 1996 best case: 5 requests, 193 domains, 2 pairs, 1.6134 EE (0.3227/req)**. Total **55 requests, 7.7295 EE, 0.1405 per request against the gap engine's 0.959**, about 7x worse. The best-case row is what closes it: `Business_and_Economy/Companies/Construction/` at 35,953 bytes lists **173 sites in one page** and yielded 2 net-new pairs, so the fat and thin ends of the tree land within 0.02 EE per request of each other. Page yield is not the problem: median 7, 4 and 17 domains a page and **zero of 50 usable pages at zero**, against 8 of 18 before. **The store already holds every name on them:** 284 of 284 domains on the 1997 pages and 121 of 121 on the 1996 pages, the latter carrying an assignment in all six window years. The thin-year argument runs backwards, 8.0% of held domains carry a 1996 pair store-wide against 85.6-100% of Yahoo's, because 1996 is thin from Usenet- and registry-derived single-year names, not from missing famous sites. `split_by_corroboration` never fired once, 0 uncorroborated of 594. **Two traps worth keeping.** CDX cannot enumerate this: `www.yahoo.com/*` and `www.yahoo.com/Business_and_Economy/*` both 504 at a flat 60.5 s and a 14-category sweep produced nothing in 45 minutes. And the cheaper route generalises: `web/<stamp>id_/<url>` redirects to the nearest capture, so one request buys the real capture date, the bytes and the next level's links, where enumerating first would have cost a second request per page. Collector kept at `scripts/collect_yahoo_directory.py` for replay, not wired into `just` |
| Non-English regional portals (2026-08-08) | **Deferred, small but the best EE-per-request in the round.** 10 archived catalogue pages gave 1,749 raw net-new pairs, but that is a pre-split figure: `split_by_corroboration` demotes never-before-seen names to candidate-only and removes 59% of them, leaving **445 EE measured, ~1,200 projected for ~42 requests**, about 27 EE per request against the queue's 0.6. 97.4% came from **one** Indian portal (Khoj); the densest Czech page (Seznam, 1,723 domains) gave 0 and the Brazilian pages (900 domains) gave 0. Everything it produces is year 2001, already the store's fattest year. Do not seed the peer portals: the one peer tested, asiaco.com, had no archived listing pages at all |
| Stanford WebBase 2001 (via LAW) | 118M URLs to 603,245 registered domains, **99.99% already held**. Retired as a growth source |
| `deduplicated_urls_*` (supplied seeds) | Effectively exhausted: 200k lines probed yielded 3 domains not in the baseline |
| Common Crawl | Earliest collection is 2008-05; capture timestamps fail the in-window evidence bar |
| Arquivo.pt bulk `AWP*` collections | 214 files, sampled slices are all 2008. Out of window (`Roteiro` and `IA.cdxj` are the in-window exceptions) |
| UKWA per-year bulk CDX | Not publicly retrievable in 2026: dead host, soft-404 successor, 404 DOI, never Wayback-captured. Access requested |
| ODP full 2001 content dumps | Verified unavailable in 2026: the URL serves a "Page Has Moved" stub |
| ODP full Aug-2000 content dump | Unrecoverable; only `structure.rdf` was archived, which has no external links |
| Public 1998-2001 zone files | None survive anywhere checked (DNS-OARC, resellers, academic torrents) |
| Historical zone files and bulk registry snapshots, the family closed out (2026-08-08) | The last routes the earlier rows left open are now checked, and the family is **closed for 1998-2001**. (1) **archive.org holds no in-window zone file.** `title:(zone file)` returns 303 items and every one is 2009 or later (`ee_zone_file_202404`, `root_zone_file_202206`); `mediatype:data` restricted to 1996-2002 returns 20 items and none is DNS data; `"com.zone"` returns **zero**; `description:(internic) AND mediatype:software` returns 4 items, all modern GitHub mirrors. (2) **The CD-ROM route is empty too**: the Walnut Creek, InfoMagic and "Internet in a Box" items are FreeBSD, Linux and Windows shareware discs, not registry snapshots. (3) **Academic FTP mirrors were never captured**: `wuarchive.wustl.edu`, `ftp.uu.net`, `ftp.cdrom.com` and `ftp.funet.fi` return **zero** Wayback captures matching `zone`, `domain-info` or `internic`, and `rs.internic.net/netinfo/*` holds only 404s. (4) **DNS-OARC is out of window by design**: root zone from June 1999 and it lists TLDs rather than domains, per-TLD zones only from March 2009. (5) **The survey name lists really do stop at 9707**, confirmed from two independent live directory listings rather than inferred: ISC's own `ftp.isc.org/www/survey/archive-data/` and the survey author's `3waylabs.com/zone/`. The later `WWW-9801/` and `WWW-9807/` directories on the author's site contain **only aggregate report HTML**, no name lists. (6) **ISC's own 9607 and 9701 copies are corrupt in a specific, unrecoverable way**, worth recording so the next person does not retry them: `9607.domains.gz` recovers 6,562,719 of 6,755,227 bytes but only **3,835 newlines against 488,069** in the good Wayback copy, because the deflate stream desynchronises early and the rest decodes as plausible-looking garbage (`vanoqoykoorrlykddoldnabykeec.gc`). A partial gzip recovery here is not a partial file, it is a few thousand good lines followed by fiction |
| Australian Web Archive (PANDORA/Trove) | **Superseded 2026-08-01; the full account is in the `Australian Web Archive` section earlier in this file, and the operative verdict is redundancy with the Internet Archive rather than unreachability: zero AWA-only pairs.** The earlier entry said both endpoints served an Anubis challenge. Half of that is now wrong: `web.archive.org.au/awa/cdx` answers normally |
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
| archive.org **`magazine_rack`** at large (2026-08-05) | 34,279 in-window items but **0.4 net-new pairs per reachable item**, against 10.5 for the computing trade press measured the same way on the same day. In-window holdings are Amiga user-group zines and laboratory newsletters, which print almost no URLs. The periodical route is only worth taking when scoped to computing and internet titles, and even then it saturates: see the `trade_press` section, which closed the whole American and hobbyist computing press at 5,318 in-window items |
| Boardwatch **ISP Directory** volumes (2026-08-05) | The monthly magazine issues carry `_djvu.txt`; the separately catalogued directory volumes do not. `boardwatch-directory-of-internet-service-providers-july-august-1997_djvu.txt` returns a 146-byte stub. The most ISP-dense artifact of the family is the one without machine-readable text |
| **IRCache / NLANR proxy traces** (2026-08-06) | Dated squid logs holding millions of real URLs, the most promising lead on that day's list, and it is gone. `ircache.net` now serves a squatted blog; `ftp://ircache.nlanr.net/Traces/` is dead; `(ircache OR nlanr) AND trace` returns **zero** archive.org items; `web-caching.com` times out. No route in |
| **Internet Traffic Archive** web traces (2026-08-06) | `ita.ee.lbl.gov` is alive and the one dataset that would have been ideal is unusable. **UC Berkeley Home IP, 1996, 9,244,728 requests** has **anonymised URLs**: the dataset's own format example is `GET 9168504434183313441..gif`. `BU-Web-Client` has URLs in the clear but runs November 1994 to May 1995, out of window. `WorldCup98` and the NASA, EPA and ClarkNet logs are single-server request logs with no third-party hostnames |
| **Shareware CD-ROM catalogues on archive.org** (2026-08-06) | The mechanism fails before the content question. `cdbbsarchive` holds 3,578 items, but archive.org **cannot list inside an ISO**: `/download/<item>/<file>.ISO/` returns a View Archive page ending `failed to obtain file list`. So measuring density costs a full ISO download per item, 127 MB to 1,300 MB. The items also carry **no `date` or `year` metadata**; the only date is transcribed into the title. Not measured, and not worth measuring: `FILES.BBS` blurbs are about 45 characters and rarely hold a URL |
| **DMOZ / ODP pre-2002 dumps on archive.org** (2026-08-06) | `archive.org` holds **exactly one** ODP RDF item, `dmoz-rdf-20150327`, 29.8 GB, 2015. There is no pre-2002 dump anywhere on it. The existing ODP rejection now covers archive.org too |
| **InterNIC / NSI zone or WHOIS snapshots on archive.org** (2026-08-06) | 8 hits for `internic AND (zone OR whois OR domain)` and none is data: two Tucows programs, an RFC, two videos, two GitHub mirrors |
| **Other released email corpora** (2026-08-06) | Searched for a Jeb Bush release, whose 1999-2007 span would straddle the window: 5 hits, all video or news. **Enron is the only released corpus in window** |
| **faqs.org as a route to the Usenet FAQs** (2026-08-06) | `http://www.faqs.org/faqs/` returned HTTP 429 on two attempts an hour apart, and the host's TLS is too old for the local LibreSSL so `https://` fails outright. Moot rather than closed: the same FAQs were taken through the rtfm.mit.edu mirror instead, see the `rtfm_faq` section, and much of the overlap is inside the Usenet corpus anyway |
| **UK Government Web Archive** (2026-08-06) | **Not rejected. It works and it is tiny.** Documented in its own section above: real coverage from 1996-11-11, government-only, 250 addressable domains. Kept out of the rejected register so nobody closes it by mistake |
| `nav.webring.yahoo.com` (2026-08-05) | **Zero in-window captures** for the entire host prefix. Wrong hostname for the period |
| WebRing member lists (2026-08-05) | Named in the phase-2 feedback and now measured. In-window captures exist under `matchType=domain` for `webring.org` (from 19961019) and `webring.com` (from 19981212), and the large ones are real pages rather than stubs: `www.webring.com/cgi-bin/webring?ring=railring&list` at 20000422003921 is 14,154 bytes. But **that page lists 20 member sites and contains 2 member URLs**: every member is linked through a redirector, `go.webring.org/go?ring=railring;id=878;go`, and the visible text carries each site's title and description with **zero bare URLs**. The member domains are not in the artifact. Recovering them costs one Wayback redirect per member against pages holding ~20 members each, which competes for IA budget with the gap engine's 96% hit rate. **Reject as a bulk source.** Two traps worth keeping: `matchType=prefix` on `www.webring.org/*` returns zero because the lists are query strings off the site root, so a wrong match type is indistinguishable from an absent source; and sorting CDX rows by `length` is what separates a real page from a stub |
| Bibliotheca Alexandrina IA mirror (2026-08-05) | `web.archive.bibalex.org` and `web.archive.org.bibalex.org` both fail to resolve; only the institutional landing page answers. This was the most promising non-IA route to early captures and it no longer exists |
| `data.webarchive.org.uk` (2026-08-05) | Does not resolve. A third distinct host tried for the UKWA bulk CDX, after the 159-byte stub and the 403 DOI. Still no route in |
| DMOZ / ODP copies on Zenodo (2026-08-05) | 12 hits, all 2018-2020 research derivatives of late DMOZ dumps. Out of window, and description text rather than dated listings. The ODP rejection stands |
| `biz.*` Usenet hierarchy (2026-08-05) | Exhausted: no unprocessed `.mbox.zip` archives remain in the 19,233-group catalogue |
| Late-starting Usenet groups (2026-08-05) | A selection rule rather than a rejection, and it costs more than any single source above. **4,023,027 of 5,283,482 messages across 28 probed archives are out of window**, concentrated in whole groups: four of the 28 contributed exactly zero net-new pairs, and `uk.misc` gave one record from 172.9 MB. Gate on in-window date coverage, not on group name or file size |


## `usenet_announce` and `usenet_mention`: dated website announcements from Usenet

Adopted 2026-08-01, and the largest single addition of phase-4. Giganews donated its Usenet
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
  pair because the whole group is 2006 to 2013. `legacy/scripts/fetch_usenet_groups.py` selected on the
  group *name* and ranks by expected yield, with announcement forums first and commerce second,
  because ordering by size put dead vanity archives at the head of the queue. 628 groups selected
  within a 100 MB per-group cap, 5.7 GB in total.
- **Two selection rules that are really the same rule.** Short tokens are matched as whole
  dot-separated components, because `talk.bizarre` contains "biz" and is not a commerce group. That
  is the trap `is_moderated_announce` hit when a suffix test reported `news.announce.conferences` as
  ordinary discussion. And `net` was tried as a component token and removed: it matches
  `alt.isd.net` and `alt.toxiccrisko.net`, which are vanity groups announcing nothing.
- **Operationally, it runs alongside the query engines rather than competing with them.** It downloads
  from `archive.org/download/`, a different service from the `web.archive.org` CDX and replay endpoints
  the verification engine meters against, so both can run at once. That property is what made the bulk
  Usenet nights possible while the engines were saturated, and it is worth checking for in any new
  source: which host does it actually touch?

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
in-window capture, a 62% hit rate**. All integrity checks pass.

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

**How the route opened up, in stages.** Marginal yield was still high at the fourth group ingested
(the second pair added 25,401 pairs), which is what justified pursuing it to the whole catalogue. The
group counts quoted in the next three paragraphs describe the state at the time each measurement was
taken; the **Residual** block at the end of this section has the current position.

**And the shortlist itself was the limit, measured 2026-08-05.** The name filter is now drained: all
697 downloaded archives are in `.processed` and `biz.*` holds nothing unprocessed. That looked like
the end of the route and is not. The filter only ever selected groups whose *names* contain
`announce`, `business` or `commerce`, so an ordinary discussion group had never been tried. Eleven
were: `uk.d-i-y`, `uk.finance`, `uk.local.london`, `uk.jobs.offered`, `rec.food.recipes`,
`rec.travel.usa-canada`, `comp.infosystems.www.misc` and others. Eight of them return **8,819 net-new
pairs at a mean equivalent-English weight of 0.7389**, roughly 1,102 per group, concentrated in
1999-2001. Ordinary conversation quotes URLs and every post is dated, so the announcement framing was
an accident of how the corpus was first found. At that point 18,536 groups were still unfetched.

**The decay was then measured rather than assumed, and it is nearly flat.** 28 groups accumulate to
**20,159 net-new pairs and 14,266 equivalent-English at a mean weight of 0.7077**, against a store
already holding 8,812,701 assigned pairs. The cumulative curve fits `a * g^0.909`, an exponent close
enough to 1 that saturation has barely started, which projects to roughly 138,000 pairs at 200 groups
and 466,000 across all 761 groups of `uk.*`, `aus.*` and `can.*`. **The right selector is neither
name nor size but in-window date coverage:** 4,023,027 of 5,283,482 probed messages are out of
window, and the waste is concentrated in whole groups, four of the 28 yielding exactly zero. Reading
a few thousand `Date` headers before committing to a download removes most of it. The sharpest case
measured was `uk.misc`, which returned a single record from 172.9 MB because the group's traffic
postdates the window almost entirely.

**Measured union over 1,706 archives: 147,271 net-new pairs, 85,721 net-new domains, 98,066
equivalent-English at mean weight 0.6659.** That was 1,706 of the 3,479 archives held at the time, so it
describes 8.9% of today's corpus and is a floor rather than a total. It is **superseded as the way to ask
this question**: it was measured before those archives were ingested, and once a corpus is in the store
the same script cannot be re-run for an answer. Use the per-hierarchy attribution in the Residual block
below instead, which covers all 19,231 archives and needs no parsing at all. What the store
holds from the whole corpus is the figure to quote instead: `usenet_announce` carries 2,017,182 evidence
rows over 1,022,707 distinct domains. Measured in one pass rather than summed across tranches,
because each tranche was differenced against the store separately and adding them would double count
shared pairs. Of those, 74,508 pairs are on domains another source already attests and can carry the
post date immediately (48,821 equivalent-English); 72,763 are on names seen only in Usenet and go to
the candidate pool under the standing admission rule, at a 35.8% typo upper bound. **Small groups
yield about 37 net-new pairs per megabyte against 4.5 for large ones**, because a small archive
belongs to a group that died early and therefore falls inside the window, so the download queue
should run ascending by size.

**Residual: the download is finished and the recall is not.** Audited in full on 2026-08-10, with every
figure below re-derived that day and independently re-checked:

| | |
|---|--:|
| catalogue (`data/raw/usenet_catalog.json`), 12 hierarchies | 19,233 groups, 411,214,378,850 bytes |
| on disk in `data/raw/usenet/` | 19,231 groups, 411,023,158,296 bytes |
| in `.processed`, set-identical to disk in both directions | 19,231 |
| archives on disk that are unread | **0** |
| archives whose size differs from the catalogue's | **0**, and no partial or `.tmp` file anywhere |

**Only two groups are missing and neither is fetchable:** `alt.irc` (94,850,788 bytes) and
`alt.music.oasis` (96,369,766 bytes), both of which the host answered with HTTP 500 or 502 on every
attempt across two separate retry runs. Together they are 0.05% of the corpus. **Treat the download as
complete**, and every figure elsewhere in this section about groups remaining as superseded.

What remains is **recall over 383 GB already paid for**, which is a different and much cheaper kind of
work:

- **Per-hierarchy yield is now measured, and `measure_usenet_yield.py` was the wrong instrument for it.**
  An earlier version of this block said 17,525 archives "have never been through
  `measure_usenet_yield.py`" and treated that as the gap to close. Running it would have proved nothing:
  that script measures what an archive **would** add, every archive is already ingested, so it reads
  near zero by construction. That is trap 9 inverted, a population that structurally excludes the
  outcome being counted.
  The answerable question is what each hierarchy **did** contribute, and it is a store-side join rather
  than a corpus walk. Every Usenet evidence row carries its newsgroup as the first token of
  `evidence_value`, and `domain_year.evidence_id` names the one row that won each assignment, so the
  yield partitions by group with no double counting. Measured 2026-08-10, read-only:

  | hierarchy | GB | groups | groups that won a pair | pairs assigned | domains | EE assigned | EE per GB |
  |---|--:|--:|--:|--:|--:|--:|--:|
  | `alt` | 234.1 | 15,288 | 8,262 | 439,717 | 352,489 | 237,158 | 1,013 |
  | `comp` | 33.1 | 1,205 | 1,013 | 165,636 | 140,565 | 80,686 | 2,441 |
  | `rec` | 55.5 | 919 | 736 | 101,192 | 89,557 | 55,886 | 1,008 |
  | `uk` | 14.5 | 495 | 393 | 40,898 | 36,281 | 14,495 | 1,001 |
  | `misc` | 9.7 | 242 | 187 | 19,701 | 18,587 | 11,277 | 1,158 |
  | `soc` | 32.3 | 341 | 261 | 20,798 | 19,517 | 9,617 | 297 |
  | `sci` | 11.6 | 237 | 201 | 14,980 | 13,852 | 7,754 | 671 |
  | `news` | 5.9 | 60 | 36 | 10,986 | 9,991 | 6,049 | 1,025 |
  | `aus` | 5.3 | 195 | 155 | 15,570 | 13,999 | 5,504 | 1,030 |
  | `can` | 2.2 | 109 | 90 | 13,453 | 12,889 | 5,359 | 2,478 |
  | `biz` | 1.2 | 95 | 67 | 7,043 | 6,727 | 3,583 | 3,105 |
  | `talk` | 6.0 | 47 | 27 | 630 | 628 | 359 | 60 |

  **`EE assigned` is what the seam won historically and is all credited in `merged260810`**, so it is a
  density prior for choosing where to widen an extractor, not available headroom. Net-new
  equivalent-English is 0.0 for every hierarchy, which the same query confirms. The figure attributes a
  pair to the evidence row that **won** it, so it understates what a hierarchy merely asserts: many
  Usenet-asserted pairs were assigned from a CDX row instead.
  `legacy/scripts/screen_usenet_archives.py` still lists any archive with 0.0% in-window coverage, which
  is how a silently barren group shows up.
- **Two seams have measurable coverage gaps, both small and both precise.** The header run and the
  first address run each covered **19,083 archives**, not 19,231: the 148-archive batch ingested on
  2026-08-08 as tag `auto084548` landed between them, so those 148 were never header-scanned. And the
  bare-host pass enumerated all 19,231 archives but **only 9,759 of them produced a single row**, which
  is a fact about sparsity worth knowing before extrapolating from any sample of it.
- **Extraction seams are the lever, and three have already been worked.** `usenet_address` (ftp://,
  mailto: and typed addresses) returned 62,820.7 EE, `usenet_bare` (a plain `foo.com` in prose)
  returned 28,460.3 EE, and both read bytes already on disk with no request sent. The pattern
  generalises: **before writing a source off, check what the parser actually reads.**
  `comp.mail.maps` sat in `.processed` for a day with 1,480,910 UUCP registry entries read as nothing,
  because a URL regex cannot see a payload in a record format.
- **The machine-written header seams are closed, measured over the whole corpus.**
  `Message-ID`, `Reply-To`, `Sender` and `NNTP-Posting-Host` together gave 1,025,582 pairs, 207,980
  corroborated, **2,869 net-new, 1,038.4 EE** and are exhausted. `Path:` gave 7.1 million parsed hops
  across 4,736 distinct domains and **13.89 EE on a 400-archive sample, projecting to about 30 EE for
  the corpus**; the Giganews donation carries no `Path:` header before 2000 at all (197, 278, 202 and
  210 in-window lines for 1996 to 1999 against 750,686 for 2001). Neither should be re-proposed.
- **`alt.*` is priced, and it is proportionate rather than exceptional. It is no longer an open
  question.** The catalogue holds **15,288 `alt.*` groups, 234,057,485,934 bytes**, of which 15,286 are
  on disk and all 15,286 are in `.processed` (the two absent are the unfetchable pair above). An
  earlier version of this section said "14,910 groups, 229 GB", which was the **remainder still
  unprocessed at the end of 2026-08-01** and reproduces exactly from the ingest log; it was never a
  statement about what had been downloaded. A later version called its yield "entirely unmeasured" and
  the single largest open question about this corpus, answerable by a screening pass over local files.
  Measured instead from the store on 2026-08-10, per the table above: `alt.*` is **57% of the bytes and
  54% of the assigned equivalent-English**, at **1,013 EE per GB against a corpus mean of 1,065**. The
  standing **[GUESS]** that many small `alt.*` groups are vanity archives announcing nothing is half
  right and its conclusion was wrong: **7,026 of its 15,288 groups won nothing at all**, so it holds at
  group level, and it does not hold at hierarchy level, which is the level the decision is taken at.
  Screening `alt.*` will not find a hidden tranche, and it needs no screening pass.
- **Diminishing returns are measured, not feared:** the cumulative curve fits `a * g^0.909`, so
  saturation had barely started at 28 groups, and 4,023,027 of 5,283,482 probed messages were out of
  window, which is where three quarters of the bytes went.

## `tucows_catalogue` and `tucows_mention`: the Tucows Software Library

Adopted 2026-08-01. A dated index file in the sense of III.1, and the best-behaved dating of any
source assessed in phase-4.

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

---

## `maillist_archive` and `maillist_archive_mention`: public pipermail list archives

**What it is.** The per-month archive files that GNU Mailman's pipermail publishes, one file per
list per month, each holding the raw messages with their headers. Two hosts are wired:
`mail.python.org/pipermail/` and `mail.gnome.org/archives/`. Together they publish **2,558 in-window
month files carrying 579,808 messages dated 1996-2001**.

**Get it.** Two steps, harvest then parse, and no `web.archive.org` request at any point.

```bash
uv run python scripts/collect_mailing_lists.py --harvest --write
uv run ark ingest maillist_dated      data/raw/maillists/maillist_dated.jsonl.gz
uv run ark ingest maillist_candidates data/raw/maillists/maillist_candidates.jsonl.gz
```

Or `just maillists`. The harvest takes about six minutes for 740 MB.

**Date semantics.** Each message's own `Date:` header, read per message, not the month in the
filename. That matters because a pipermail month file is assembled by arrival and carries stragglers:
450 of the 581,323 messages read date outside the window and are dropped rather than pulled into it.

**Evidence types.** `dated_directory` for the corroborated half, `link_target` for the rest, which is
the split every free-text source takes here: a mail body is human-typed, so a name no other source
attests earns no year and goes to the candidate pool.

**Lineage `mailing_list`, and the collector is what makes that honest.** `python-list` and
`python-announce-list` are bidirectionally gatewayed with `comp.lang.python`, so their messages are
the same messages the Usenet corpus already holds. They are excluded at collection time
(`SKIP_LISTS`), 64 month files, so a pair confirmed by both a list and a Usenet post is genuinely two
observations rather than one counted twice.

**Measured yield: 26,174 in-window (domain, year) pairs, of which 21,882 corroborated and
1,458 net-new, worth 833.17 equivalent-English.** 4,292 uncorroborated names went to the candidate
pool. Concentrated late, as the corpus is: 2000 555, 2001 548, 1999 238, 1998 107, 1997 5, 1996 5.
Net-new TLDs are 796 `.com`, 217 `.net`, 182 `.org`, 89 `.de`.

**Do not scale this family, and the measurement is why.** Per in-window message the two hosts yield
**0.00145 and 0.00121 equivalent-English**, against **0.0067 for the Enron corpus**, so a public
technical list is about five times weaker per message than corporate mail. At that rate 32,000
equivalent-English would need roughly **25 million in-window messages**, and the whole reachable
family is nowhere near it. The reason is the one the Usenet `Path:` header already taught: a
mailing list selects for an authoritative, heavily-crawled population, and 83.6% of the pairs it
finds are pairs the store already holds.

**Most of the rest of the family is not reachable anyway**, checked 8 August: `lists.debian.org`
publishes no per-month bulk file, only one HTML page per message; `lists.samba.org` answers HTTP
426; `sourceware.org` 403; `lore.kernel.org` sits behind an Anubis proof-of-work challenge.
`mailman.nanog.org` and `mail-archives.apache.org` do answer and are small (NANOG's January 1999 is
8 KB). The 2026-08-01 rejection of this family was right about the W3C lists and about archive.org's
holdings; what it missed is that pipermail hosts publish bulk month files, which is what made the
measurement above possible at all.

**Residual.** Closed for breadth on the measurement above: more hosts cannot pay, and most are
unreachable. One question is open and is about recall rather than breadth. 868 MB of text on disk
produced 833.17 equivalent-English, and both `data/reports/maillist_*_audit.csv` files are
header-only stubs, so **[GUESS]** a low-recall extraction pattern is as plausible an explanation as a
barren corpus. One recall measurement over the bytes already held would settle it, which is cheap;
a wider crawl would not, and is ruled out above.

---

## `enron_email` and `enron_email_mention`: the FERC Enron corpus

**What it is.** The Enron email corpus released by the Federal Energy Regulatory Commission during its
investigation, about 500,000 messages from 150 employees, mostly 1999-2002. Every message carries its
own `Date:` header, and corporate mail quotes vendor, partner and press hostnames that no directory
ever listed.

**Get it.** A single tarball, about 423 MB compressed, then parse. No `web.archive.org` request.

```bash
# The path matters: collect_enron.py reads this exact file, and this line used to name
# data/raw/enron/enron_mail.tar.gz, which nothing writes and nothing reads. A
# reproduction following it downloaded 423 MB to a path the collector then ignored.
curl -L -o data/raw/source_probe_260806/enron.tar.gz \
  https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
uv run python scripts/collect_enron.py --write
uv run ark ingest enron_dated      data/raw/enron/enron_dated.jsonl.gz
uv run ark ingest enron_candidates data/raw/enron/enron_candidates.jsonl.gz
```

Or `just enron`. Note the collector opens the store to run the corroboration split, so it will fail
against a live `just maintain` holding the write lock; run it between passes.

**Date semantics.** Each message's own `Date:` header, per message. Out-of-window messages are dropped
rather than pulled into the window, which matters here because the corpus runs past 2001.

**Evidence types.** `dated_directory` for the corroborated half, `link_target` for the rest. Mail
bodies are human-typed, so this takes the corroboration split like every free-text source: a name no
other source attests earns no year and goes to the candidate pool.

**Lineage `corporate_email`.** Independent of every web crawl, of Usenet and of the mailing lists, so
a pair it confirms alongside a capture is genuine cross-lineage corroboration.

**Measured yield: 5,134 net-new pairs worth 3,241.9 equivalent-English.** Per in-window message it
yields **0.0067 equivalent-English**, about five times the rate of a public technical list, which is
the comparison that closed the mailing-list family for breadth.

**Residual.** **[GUESS]** unmeasured, and the same recall question as the mailing lists: 423 MB in,
3,241.9 EE out, with both audit CSVs written as header-only stubs. The corpus is a fixed release with
no further date partitions to fetch, so any remaining value is in extraction recall over bytes already
held, not in more download. Ranking below the Usenet seams for that reason: 423 MB against 383 GB.

---

## Measured, and each blocked on something other than work

Documented here rather than in the rejected register **because neither is rejected**. Both were measured
against the store and both clear the acceptance bar in [discovery.md](discovery.md). The first has since
been built and ingested; the second is a deliberate decision not to.

### attrition.org web defacement mirror

**What it is.** attrition.org ran a web defacement mirror from January 1999 to 21 May 2001, with
pre-1999 entries copied from earlier mirrors. Each entry is a date, a defacer, an organisation name
and the hostname that was defaced. **A defaced host is a host that was serving on that day**, so the
record is contemporaneous evidence of existence with the date printed in the record itself.

**Get it.** Republished on GitHub in March 2021 as `attrition-org/web-hack-mirror`. Only the index
pages are needed, 33 files and 2,394,351 bytes, and all 33 are **already downloaded** to
`data/raw/source_probe_260806/attrition/`:

```
https://raw.githubusercontent.com/attrition-org/web-hack-mirror/main/mirror/{1995,1996,1997,1998}.html
https://raw.githubusercontent.com/attrition-org/web-hack-mirror/main/mirror/{1999,2000}-{01..12}.html
https://raw.githubusercontent.com/attrition-org/web-hack-mirror/main/mirror/2001-{01..05}.html
```

Do **not** also take the 265 per-TLD and per-defacer breakout pages (`com.html`, `uk.html`, ...): they
re-slice the same rows and would double count.

**Date semantics.** Each row begins with a two-digit date the mirror operators printed on the day they
captured the defacement, followed by the host in parentheses. One regex for each:

```
[99.11.30] Li [potus] Coronus Networking ( www.coronus.com )
```

**Evidence type: `artifact_listing`**, self-dating, so it would not take the corroboration split.

**Measured.** 13,732 rows carrying both a date and a host (30 host-lines had no date and were
dropped), 12,671 in-window pairs over 12,327 registrable domains, of which **6,458 net-new pairs over
3,214 net-new domains, worth 3,174.08 equivalent-English at mean weight 0.4915**. By year: 1996 3,
1997 3, 1998 61, 1999 1,505, 2000 2,518, 2001 2,368. By TLD: com 2,943, br 471, org 378, net 375,
mx 166, cn 151, uk 122, tw 118, il 112.

**Ingested 2026-08-10.** `just attrition`, and it sends no request: the 33 index pages were already on
disk. Re-derived in the tree rather than trusting the probe's TSV, which is why the figures below differ
slightly from the 6 August measurement.

```
33 pages, 13,793 rows
  13,647 dates confirmed by both witnesses     55 single-witness
      12 day-level disagreements, kept          2 year-level disagreements, dropped
      77 rows with no host, dropped           127 rows dated 1 or 2 January (0.92%)
  13,712 in-window records -> 12,653 distinct (domain, year) over 12,309 domains
```

**Contributed 5,816 net-new pairs worth 2,791.4410 equivalent-English** at mean weight 0.4800,
re-scored with the reviewer's own calculator: zero records rejected, zero already in his merged files,
agreement to 0.0000. The remaining 6,837 of its 12,653 pairs are corroboration for years another source
already established, which is worth having on its own: this is a lineage no other source shares.

**The 6 August estimate was 11% high**, 6,458 pairs and 3,174.08 EE against 5,816 and 2,791.44, and the
reason is the standing one: the store grew between the measurement and the ingest, so pairs counted as
net-new then were already held by the time it ran. Two of the difference are the year-disagreement rows.

**Three honest weaknesses.**

- **The date is when the mirror recorded the defacement**, at most a day or two after the host was seen
  live. That is well inside a year boundary except at New Year. **Measured: 127 of 13,793 rows, 0.92%,
  are dated 1 or 2 January**, which bounds the exposure. Noted rather than fixed: there is no evidence
  that would resolve an individual row, and moving them all back a year would invent a claim.
- **Mean weight 0.4800 is low**, just above the 0.4 floor at which volume has to justify itself.
  Defacers of 1999-2001 favoured `.br`, `.mx`, `.cn`, `.tw` and `.kr`, and it shows.
- **It is a 1999-2001 source**: 1996 to 1998 contribute 67 pairs between them.

**On the licence.** The mirror repository is published `CC-BY-NC-SA`. What we take from it are facts,
`(hostname, year)` pairs, not its pages, its prose or its selection: no attrition.org text is
redistributed, and the corpus it feeds is one source among forty-two contributing 5,816 of 11.4M
records. Attribution is given here and in the report, and every row carries an evidence URL pointing at
the mirror entry it came from, which is stronger attribution than the licence asks for. Recorded so the
position is auditable rather than assumed, and it is **reversible**: the rows carry their own
`source_id`, so `attrition_defacement` can be removed and the export regenerated if the view ever
changes.

**Residual: closed.** The index is complete for the mirror's whole run, January 1999 to 21 May 2001
plus the copied-in pre-1999 entries, and the 265 per-TLD and per-defacer breakout pages re-slice the
same rows rather than adding any. There is no more of this source to take.

### `pandora_titles`: the National Library of Australia title index, as candidate seeds

**What it is.** PANDORA's Title Entry Page index, 87,732 rows of `tep_id, name, gathered_url, surt`,
published CC0 by the GLAM Workbench. Already on disk at `data/raw/pandora-titles/`, with its schema
and the crawl documentation beside it.

**Get it.** <https://github.com/GLAM-Workbench/trove-web-archives-titles>

```bash
uv run python scripts/seed_pandora_titles.py    # -> pandora_hosts.txt
uv run ark seed data/raw/pandora-titles/pandora_hosts.txt
```

Or `just pandora-seed`.

**Date semantics: none, and that is the whole verdict.** The index has **no date column of any kind**,
so nothing in it can evidence a year and it is **seed-only** permanently. Writing its names into annual
files would be the DMOZ error `SPEC.md` III.3 names explicitly.

**Evidence type: none.** The names enter the candidate pool with no evidence row and claim nothing.

**Measured 2026-08-10, read-only, no network.** 87,732 rows, 87,658 carrying a URL, 2,285 URLs from
which no registrable name could be read, **35,391 distinct registrable domains, of which 29,432 the
store did not know at all.** By TLD the new names are `au` 16,658, `com` 8,271, `org` 3,002, `net` 757.

**Why it was seeded, and why nothing is expected from it.** The reviewer asked for the pool to be as
large as practicable (III.2, IX) and `.au` carries the highest English share in the table at 0.9904, so
an upper bound of **24,571 EE** applies if every new name earned exactly one year. That is an
**UPPER BOUND and not a projection**, and the measured expectation is close to zero for two recorded
reasons: a 60-domain sample of this list against the working AWA endpoint returned **zero** in-window
captures, and the index spans PANDORA's whole run rather than the window, so a large share of its titles
postdate 2001 outright. Seeding costs one local pass and no requests, and the pool scorer ranks these
names by measured hit rate, so if they are worthless they sit in the queue's tail and cost nothing.

**Residual: closed for this file.** The index is complete as published. The `surt` column is a reordered
form of the same URL and adds no names. `data/raw/pandora/` is a byte-identical copy.

### `udrp_wipo`: WIPO domain-name dispute decisions, 1999-2001

**Measured and blocked on a classification decision rather than on work**, which is the same position
attrition.org was in when it was blocked on a licence. Recorded here in full because it is the highest
absent-share source measured on this project.

**What it is.** Every UDRP case WIPO has decided, published with a case number whose year is the filing
year, and with the disputed domain in **its own column** of the case table. A case exists only because
the domain was registered and in dispute, so the record attests existence in that year **without
depending on a crawler having visited the site**.

**How it was found**, which is the transferable part. Not by recall and not by browsing: by asking what
the three sources that actually paid this round have in common. Registry creation dates, dated DNS
survey shards and a defacement mirror are all **machine-generated records about whoever happened to be
there**, rather than human curation of who was notable. Every family that has failed on measurement here
selects for authority; this class does not. A dispute docket is that shape, and nothing in the register
covered it.

**Get it.** Non-IA host, so it spends no archive budget. 133 requests for the whole window at 1.5 s
apart.

```bash
uv run python scripts/collect_udrp_cases.py     # -> items.jsonl, one row per case
uv run python scripts/price_items.py --items <items.jsonl>
```

**Date semantics.** The filing year from the case number, deliberately rather than the decision date: a
case filed late in 2000 may be decided in 2001, and the domain certainly existed at filing, so the case
year is the earlier and safer claim.

**Measured 2026-08-11 against the live store.** 3,325 cases, **6,069 distinct (domain, year) pairs over
6,041 domains, of which only 680 are already held**. 88.8% absent, and the reason is structural: a
disputed name is often a typosquat taken down within weeks, which is exactly what a crawl never sees.
By TLD the net-new part is `com` 847, `net` 75, `org` 34; by year 2000 576 and 2001 380 after the split.

| reading | net-new pairs | equivalent-English | mean weight |
|---|--:|--:|--:|
| `artifact_listing`, self-dating | **5,389** | **3,281.0** | 0.6208 |
| `dated_directory`, with the corroboration split | 956 | 593.5 | 0.6208 |

**The open question is which of those applies**, and it is a 5.5x difference. The case for
`artifact_listing` is that `attrition_defacement` already occupies that class on identical logic, that
the domain sits in a structured column rather than in prose exactly as Tucows' `creator` field does, and
that an arbitration panel naming a registrar is a stronger authority than a directory page. The case
against is that self-dating leaves no wall behind the extraction, so an error becomes a master claim.

**One figure that must not be misread.** The typo bound reports 36.3% of net-new names within one edit
of a held name. Here **that measures the signal rather than the noise**, because a typosquat is one edit
from a famous name by construction. It is the only source measured on this project where a high
edit-distance score is evidence that the extraction is finding the right thing.

**Two extraction facts worth keeping.** The first version read every hostname between one case number
and the next and swept in `www3.wipo.int` from the page furniture; taking the second table cell only
fixed it, and for a self-dating source that narrowing is not optional. And past a year's last case the
endpoint returns the same page rather than an empty one, so a fetcher must stop on repeats rather than
on emptiness.

**Residual: the list is a floor, and the gap is behind a JavaScript app.** ICANN's page calls itself
"an incomplete list of UDRP proceedings", and the shortfall is measurable in one direction: WIPO's own
case index returns 3,325 cases for 1999-2001 against the 3,246 ICANN lists, so about 79 WIPO cases are
missing from the consolidated table. The larger gap is NAF, which ICANN lists 1,743 of while its actual
caseload over those years was larger. **Checked 2026-08-11 and closed on availability rather than value:**
`adrforum.com/domain-dispute/search-decisions` answers 200 but is a client-side application with no
server-rendered form, links or year index, so enumerating it needs browser automation. Individual
decisions do resolve at `/DomainDecisions/<numeric id>.htm`, but the ids are opaque and finding the
in-window range would mean thousands of speculative requests at someone else's expense, which fails the
good-citizen rule for a marginal gain over what ICANN already publishes.

**Two providers therefore remain unmeasured**, and the honest statement of the headroom is: if the
missing NAF share resembles the measured one, the family plausibly holds one and a half to two times what
is ingested. **[PROJECTION, not a measurement.]** Reopen on a server-rendered NAF index, a bulk export,
or an academic mirror of the decisions.

### Bytes already on disk that nothing reads

Four directories under `data/raw/` held downloaded material with **no parser, no `SourceSpec` and no
ingest line**. They are listed here because the reviewer's first priority is unprocessed files, and
these are the literal answer to it. None is a promise of yield; each is a measurement that costs no
network. **`just residual` now finds this class mechanically**, so the table below is the state of the
four as of 2026-08-10 rather than the way to discover the next one.

| on disk | size | state |
|---|---|---|
| `data/raw/pandora-titles/` | 13 MB | **Read on 2026-08-10 and seeded, seed-only. See the section below.** The National Library of Australia's PANDORA title index, with `pandora-titles-schema.json` beside it and `auscrawls.pdf` describing the crawls. `data/raw/pandora/` holds a byte-identical second copy of the CSV, which nothing reads |
| `data/raw/source_probe_260806/hathitrust_ef/` | 12 MB | 73 HathiTrust extracted-features files plus `hathi_candidates.tsv`. The HathiTrust route as a whole is rejected in the register above, but this residue was pulled before that verdict and never measured, so the rejection does not actually cover it |
| `data/raw/source_probe_260806/attrition/` | 2.7 MB | The 33 index pages for the defacement mirror, measured and documented in its own section above. Blocked on the licence question, not on work |
| `data/raw/usenet_hdr/` | 40 MB | The machine-written-header journals, including a 5.2 MB dated half. The **evidence is already in the store**, ingested by hand under the `usenet_addr_*` source keys, so this is not unmined yield. It is a **reproduction gap**: no `usenet_hdr` `SourceSpec` exists and no `just journals` line replays it, so a rebuild from journals reconstructs the store without those 19,224 evidence rows. The seam itself is closed on measurement, above |

`data/raw/source_probe_260806/scripts/` holds the measurement scripts for the 6 August discovery
session, each of which opens the store read-only, and `logs/` holds their output. That is what the
938 MB directory is; without this paragraph it is unlabelled.

### UK Government Web Archive

**What it is.** The National Archives' own web archive, with a CDX endpoint, covering UK government
sites from 1996.

**Get it.** Two traps, both measured, and each one produced a false "empty" reading first.

```bash
curl -sS -A '<a browser User-Agent>' \
  'https://webarchive.nationalarchives.gov.uk/ukgwa/cdx?url=number-10.gov.uk&matchType=domain&from=1996&to=2001&limit=5&fl=timestamp&output=json'
```

1. **The User-Agent decides whether it answers at all.** With an honest project UA every request
   returns `302 Found` with a 0-byte body. With a browser UA it answers in 0.23 s, the fastest
   endpoint measured that day. Use the `/ukgwa/` prefix explicitly.
2. `from`, `to` and `filter=statuscode:200` **are** honoured. A first pass concluded they were
   ignored; that was the 302, not the parameters.

**Pre-2002 coverage is real, measured:** `mod.uk` 19961111, `open.gov.uk` 19970428, `dti.gov.uk`
19970119, `detr.gov.uk` 19980613, `coi.gov.uk` 19990116. Earliest seen 1996-11-11, so coverage reaches
the start of the window.

**Evidence type: `cdx_timestamp`.**

**Residual: real but tiny, and that is the whole verdict.** Measured government-only, seven for seven
non-government hosts absent (`bbc.co.uk`, `demon.co.uk`, `tesco.co.uk`, `ft.com`, `cam.ac.uk`,
`oxford.ac.uk`, `nissan.com.au` all empty). The addressable population in the gap list is `gov.uk`
225 + `police.uk` 19 + `nhs.uk` 5 + `nls.uk` 1 = **250 domains**, plus a handful of bare `.uk`
government hosts. At 0.23 s each that is under a minute of queries, so **the collector costs more than
the answers**. Worth twenty minutes as a special case reusing an existing CDX adapter with a different
base URL and a browser UA, and worth nothing as a project. `.uk` weight is 0.9813, which is the only
reason it is on the list at all.
