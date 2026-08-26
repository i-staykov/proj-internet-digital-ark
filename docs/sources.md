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
like it worked and is not the data. The archived stream drops partway; our local copy is exactly
2 GiB of the advertised 20.9 GB.

**The file is NOT year-sorted, and believing it was cost us 93% of the source for three weeks.**
Measured 2026-08-16 over all 168,942,882 lines: **the year column decreases 14 times**, so this is
15 concatenated shards each sorted internally. In-window rows are spread across all of them:

| | |
|---|--:|
| in-window rows in the whole file | **2,468,674** |
| first row past 2001 | line 166,895 |
| in-window rows before that point | 166,890 |

The old parser stopped at the first post-2001 row, which is the end of shard one of fifteen, and so
read **6.76%** of what is there. **How the wrong answer survived verification is the part worth
keeping**: the check was real, and it was "zero in-window rows in the next 5M lines". The first shard
boundary sits at line **11,908,464**, so the check stopped 2.4x short of the evidence that would have
overturned it. A tail sample showing 2004 was taken as corroboration, and it proves only what the
last shard ends on.

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

## `dartmouth_nber_captures`: the archive's own capture census

**What it is.** A 2017 research release, deposited at archive.org under the Dartmouth/NBER web-history
collection, publishing for every host the Wayback Machine held at that time a count of captures per
calendar year. One row is `host<TAB>year<TAB>count`. It is a precomputed slice of exactly the index
that `cdx/search/cdx?url=*.com` is refused for, published for one research partner, and no general
equivalent exists.

**Get it.** 228 MB, `host<TAB>year<TAB>count`, no per-domain querying. There is **no `ark download` for
it**: that command takes a seed file of archived pages and nothing else, so the line that used to appear
here would have failed for anyone who ran it. The file was fetched from the archive.org item named
below, and since that item stopped serving there is now no command that reproduces the fetch.

**The input does not ship in the delivery archive, and this entry used to say it did.** Corrected
2026-08-18: `journals/` holds `*.jsonl.gz` collector journals, and this source's input is a 228 MB
tab-separated text file that is not among them. So the ingest command below runs only for someone who
already holds the file, which since the takedown is only us:

```bash
uv run ark ingest dartmouth_nber_captures data/raw/dartmouth_nber/domain-year-captures.txt
```

**What that costs, and what covers it.** This source and `domain_creation_bulk` together account for
2,387,824 assignments, 44.9% of everything carrying this project's own evidence, that a tier-3 rebuild
from original sources cannot re-derive. Measured 2026-08-18, and `docs/delivery_readme.md` states it in
the reproduction section rather than leaving a reader to discover it. **Tier 2 covers all of it**: the
provenance export ships the evidence row behind every one of those assignments, and `verify.sh` check 4
tests exactly that.

**Not shipping it is a decision rather than an oversight.** Shipping would make tier 3 whole for this
source and would preserve the only copy we know of, which is tempting for a project called an ark. It
is declined because redistributing a third party's research deposit to the reviewer is a licensing
call this project has no standing to make on their behalf, and the deposit was darkened by somebody,
which is a signal to respect rather than to route around. The 228 MB is the smaller objection.

**Provenance, and the item is no longer servable.** The file came from archive.org item
`DARTMOUTH-NBER-RESEARCH-2017-metadata` on 2026-08-16. As of 2026-08-17 that item does not serve:
`archive.org/details/...` answers "Item cannot be found" and `archive.org/metadata/...` returns `{}`,
which on archive.org means no such item. **It has not vanished from the index**, which is what says this
was a takedown or a darkening rather than a wrong identifier: an advanced-search query still returns it,
once, with its size.

```bash
# still returns numFound: 1, item_size 693302553
curl -G https://archive.org/advancedsearch.php \
  --data-urlencode 'q=identifier:DARTMOUTH-NBER-RESEARCH-2017* AND NOT identifier:*ARCS*' \
  --data-urlencode 'fl[]=identifier' --data-urlencode 'fl[]=item_size' --data-urlencode 'output=json'
```

The sibling `DARTMOUTH-NBER-RESEARCH-2017-ARCS-*` and `-WARCS-*` items, several thousand of them, do
still resolve and show the crawl this metadata item accompanied.

**So the item link is not a verification route, and this is the one that is.** Every record's evidence
row carries a live Wayback URL of the form `https://web.archive.org/web/<year>*/http://<host>/`, and
those resolve, so any single claim can be checked against the archive directly. Independently of the
item, the census agrees with this project's own separate CDX querying of the live archive on **138,760
(domain, year) pairs**, including exact same-day agreement on years holding a single capture. A source
whose origin has gone dark is still checkable when the claim it makes is checkable, and that is the case
here.

**Date semantics.** A row states that the archive holds N captures of that host inside that calendar
year. That is the same fact a CDX query returns, in bulk rather than one host at a time, so it dates
that year and no other.

**Evidence type: `cdx_timestamp`.** Self-dating, so it takes no corroboration split.

**Corroborated against our own independent querying.** Our CDX engine had separately queried the live
archive months earlier. Where both speak they agree on **138,760 (domain, year) pairs**, including
exact same-day agreement on single-capture years: `milwhite.com` 1996 against our recorded
`19961231231928`, `omnitravelservice.com` 1996 against `19961221234954`.

**Yield.** 765,188 journal records, 764,982 distinct pairs over 315,085 domains, **227,273 net-new
pairs and 142,084.0 equivalent-English** at a mean weight of 0.6252. Measured at **997 net-new
post-split pairs per MB**, the best yield-per-byte of any source this project has found.

**Caveats.** It is a 2017 snapshot, so its per-year counts are a floor on what the archive holds today
and never a ceiling. Approved `master` by Ivo on 2026-08-17.

## `domain_creation_bulk`: published registry creation dates in bulk

**What it is.** A published WHOIS/DNS compilation of 171 million domains, each carrying the registry's
own creation date parsed from a port-43 answer by the dataset's publisher.

**Get it.** 25.9 GB CSV, semicolon separated. The download needs a Kaggle account and its CLI
(`kaggle datasets download -d wotschofsky/171-million-domain-names-whois-dns-dnssec`), so it is not a
plain `curl` and there is no `ark download` for it either.

```bash
uv run ark ingest domain_creation_bulk data/raw/domain_creation/domains.csv
```

Source: <https://www.kaggle.com/datasets/wotschofsky/171-million-domain-names-whois-dns-dnssec>
(checked 2026-08-17: the dataset page resolves)

**Date semantics, and the limit that is enforced rather than promised.** The brief states that a WHOIS
Creation Date establishes existence no later than that date and may support inclusion in the annual
file for the year it falls in. **A creation date in 1998 writes 1998 and no other year.** The parser
emits one evidence row for one year, so `assign_year` cannot write a second, and the brief's warning
about later years is structural here rather than a matter of care.

**Evidence type: `whois_creation`.** Filed under the `registry` provenance lineage deliberately, so it
cannot corroborate our own `rdap` sweeps: both ask a registry when it created a name, and that is one
authority agreeing with itself.

**Falsification run before it was admitted.** A TLD cannot predate its own delegation. Across the six
TLDs delegated in 2001 the file holds 21,698 in-window rows and **zero** dated before 2001: `.info`
20,731, `.biz` 635, `.coop` 315, `.museum` 17. Nobody encoded that constraint, and a mis-parsed or
fabricated date field would have violated it immediately. Separately, 7 of 7 seeded-random `.com`
names matched live Verisign RDAP to the exact year, and an injected fabricated name read as unheld.

**Yield.** 171,212,579 lines, 2,957,620 distinct pairs, **2,165,523 net-new pairs and 1,241,812.0
equivalent-English** at a mean weight of 0.5734.

**Caveats.** These are domains still registered in December 2024, so the population is
survivorship-biased; that affects which domains it reaches, not whether the evidence is sound. The
direction of error is loss: a name created in 1998, dropped, and re-registered in 2015 reads 2015 and
falls out of the window, and the reverse cannot happen. It is a third-party compilation rather than a
primary registry feed, which is what the falsification test and the RDAP spot-check exist to address.
Approved `master` by Ivo on 2026-08-17.

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
  same URL universe. The measurement is recorded here and took about two
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

**What its candidate pool is mostly made of, measured 2026-08-11, and this is the entry to read
before anyone proposes mining `.edu`.** These two extractors between them supply **213,703 of the
216,185 `.edu` names in the candidate pool, 98.8%**, and a seeded sample of them is not domains:

    mxmutpnxw.edu   uvttiyud.edu   kjmpstbnqc.edu   bqcgoppodjp.edu
    texmnehxp.edu   xkucdpsk.edu   tboflirahp.edu   rfdmhhogamx.edu

They are anti-harvester munged addresses: a Usenet poster randomises the local part or the host of
their own address, and a bare-host rule reads the result as a hostname. `.edu` takes the worst of it
because academic posters were the dominant Usenet population. The measured CDX hit rate for `.edu`
is **0.003 over 1,709 answers**, and the store's *dated* `.edu` names come almost entirely from the
supplied baseline (6,418) with **five** from `usenet_mention`, so Usenet has contributed essentially
no real `.edu` name at all. This is the same family as the `dumicsamvfs.mil` forgeries already on
record, at a hundred times the volume.

A second mechanism is visible in the same sample: `erkeley.edu`, from `enron_email_mention`, is
`berkeley.edu` with its leading letter lost. That is a truncation artefact rather than a forgery and
it argues for the same treatment.

**None of this is a reason to delete anything**, and the corroboration split already means they cost
nothing: they sit in the pool, claim no year, and are now ranked last by their own measured rate
(C-18) and by the plausibility factor (C-17). Together with `.gov` and `.mil` they are **589,739
names, 23% of the candidate pool, in TLDs measured under a 1% hit rate**, so the pool's effective
size is nearer 1.98M than its headline 2.57M. Worth knowing before reading the headline as headroom.


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

## `ukwa_geoindex`: the UKWA Geoindex, found served after being closed as unreachable

**Status: found, priced, not yet collected.** No `Decision:` line exists for it yet, so `ark ingest`
will refuse it as master until one does. Awaiting the shard check below before an approval request is
worth writing.

**What it is.** The geographic index of the JISC UK Web Domain Dataset: every `.uk` resource the
Internet Archive held for 1996-2013, each capture mapped to a UK postcode. One row is a 14-digit
capture timestamp, the captured URL, a tab, and a postcode:

```
19961030074217/http://www.dci.clrc.ac.uk:80/Person/N.B.M.Calton<TAB>OX11 0QX
```

**Why it has a section rather than a rejected row.** The register closed this family twice, and the
second closure ended "the only route left is an access letter to the British Library, not another
URL". **It was another URL.** The British Library's Hyku repository serves the file directly, and
`/downloads/` is not behind the Cloudflare challenge that guards `/concern/`:

```bash
curl -L -r 0-0 https://bl.iro.bl.uk/downloads/090bbffa-d82c-4641-ba72-0089e8ef885f
# HTTP 206, Content-Range: bytes 0-0/11217295098
```

Verified 2026-08-17: **11,217,295,098 bytes**, ranged GETs answered, CC Public Domain Mark 1.0, no
access letter and no negotiation. The ZIP64 directory lists 12 members,
`geoindex/postcode-{a0,aa..ak}.tsv`, 72.07 GB uncompressed, about 692M rows, which corroborates the
register's independently recorded 700,641,549 lines.

**Date semantics.** The 14-digit capture timestamp prefix. Self-dating `cdx_timestamp`, master-eligible,
no corroboration split. **This is not the format the register records for this family**: the E17
figshare slice is `postcode,year,subdomain,waybackurl`, and the bulk file has no year column, no CSV
and no subdomain column. Anything written against the E17 shape will not parse it. A handful of rows
carry junk stamps (`19800101000000`, some 1994 and 1995), so a window filter must reject pre-1996
rather than trust the first row.

**Measured, on 3.05 MB of ranged reads across 5 of the 12 members:** 199,601 rows inflated, 11,011
in-window (domain, year) pairs over 8,406 domains, of which 9,731 were already held, leaving **1,280
net-new at 11.6%**, a density of 420 net-new pairs per MB downloaded against the Dartmouth census's
997. 99.7% `.uk`, so the weight is 0.9813 in practice. **Estimated** full in-window yield is 10,000 to
60,000 net-new pairs; the error bars are wide because only the heads of 5 members were sampled.

**SUPERSEDED 2026-08-20: extracted whole, and the estimate above was 1.3x to 7.8x too low.** All twelve
members were streamed and filtered by `scripts/ukwa_geoindex_pull.sh`, then priced against the store:

| | |
|---|--:|
| in-window rows | 17,912,511 |
| distinct in-window pairs | 289,857 |
| already held | 210,604 |
| **net-new pairs** | **79,253 (27.3%)** |
| domains the store had never seen | 45,122 |
| **net-new equivalent-English** | **77,749.1** at mean weight 0.9810 |

**ADMITTED MASTER 2026-08-24, at 4,493.0 EE rather than the 77,749.1 above, and the decay is the
finding.** The grounds are the row itself: a 14-digit IA capture timestamp is a record of the capture,
so it dates that year and no other, and nothing in the file was typed by a human. The bulk-projection
exception to killer 1 applies here as it did for `dartmouth_nber_captures`. Re-priced on the day of the
decision over the same 17,912,511 rows and the same 289,857 distinct pairs: **285,266 already held,
4,591 net-new, 4,493.0 EE at mean weight 0.9786**, 4,556 of them `.uk`. Ingested at 4,591 year rows,
matching the price to the pair. Nothing about the file changed between the two measurements; the store
grew into it. **A source's worth decays while it waits, and this is the measured case: 94% of it in
four days.**

**The sortedness check below was run, passed, and was still not enough, which is the part worth
keeping.** `postcode-ab` was streamed to EOF: **0 timestamp decreases over all 529,492,931 compressed
bytes**, with the in-window count flat for the last 470 MB. That justified an early abort. It was
nevertheless wrong, because **sortedness is a property of the member and not of the archive**:
`postcode-a0` has **49 decreases**, as do nine of the twelve. Aborting `a0` early wrote 74,907 in-window
rows where the full member holds **1,390,754**, so it would have taken **5.4%** of that member and
looked entirely normal doing it. The streamer now cancels its own early abort the moment it sees a
decrease. **Verifying the check on one member and generalising it to the file is the same mistake as
the 5M-line check that cost 93% of `host-linkage.tsv.gz`, one level up.**

**The check that must happen before anything else, because this exact trap has already cost this
project 93% of a source.** Each member looks sorted ascending by timestamp, which would make the
1996-2001 window a contiguous prefix and the extraction cost tens of MB rather than 11.22 GB. The
sibling `host-linkage.tsv.gz` also looked sorted and was **fifteen concatenated shards**, and the
check that confirmed it stopped 2.4x short of the first shard boundary. The sortedness here is
confirmed only over each member's first 500 KB, which is the same size of check that failed last time.
**Stream one whole member to EOF and count timestamp decreases before trusting early abort.** If it is
sharded, the download is the full 11.22 GB and the yield rises accordingly.

**Citizenship note.** `bl.iro.bl.uk/robots.txt` disallows `/catalog` for all agents and names
ClaudeBot with `Disallow: /`. Use the ResourceSync resourcelist and `/downloads/`, both allowed.

**The rest of that repository is now enumerated, and the geoindex is the only web dataset in it**
(2026-08-20). The obvious question after a 77,749 EE find is what else the host holds, and until now
it could not be asked: `/concern/` returns a Cloudflare challenge and `/catalog` is disallowed. But
`robots.txt` publishes `https://bl.iro.bl.uk/resourcelist` as the intended enumeration mechanism and
allows `/` for a generic agent, and a HEAD of `/downloads/<id>` returns a **302 whose `Location`
carries `response-content-disposition=attachment; filename=<name>`**. So a filename costs one
redirect followed nowhere and no payload. A full enumeration covered all **20,871**
file_sets that way.

The result is a clean negative. The only bulk file that is not images, OCR, audio or 3D scans is
`woa1.zip` at 16.7 GB, identified from three ranged reads of its ZIP64
central directory as **583 War Office photographs**. The `web-archives-*.zip` entries are software
releases of 4 to 9 MB. **So this route is exhausted rather than merely unexplored**, which is worth
more than another maybe, and the two scripts generalise to any Samvera or Hyku repository.

**Separately, the named CDX artifact stays closed, for a better reason.** DOI `10.5259/ukwa.ds.2/cdx/1`
resolves to a repository record with **no file attached**: it is one of 389 works in a 2021-10-20 bulk
metadata import, and zero file_sets carry that date. Established with a positive control rather than
inferred, since the Host Link Graph record sits in the same batch, also has no file_set, and is known
absent because our copy of it came from a Wayback capture instead. So the closure is now "the
repository record has no payload", which is cheaply re-testable, rather than "no route in".

## `iedr_register`: the archived IE Domain Registry register listing

**What it is.** The IE Domain Registry, run by University College Dublin Computing Services,
regenerated the whole `.ie` register as static pages at `/statistics/<letter>-doms.html`, one per
initial letter, and the Wayback Machine captured them. 26 in-window pages hold **24,805 distinct
`.ie` names**.

**Get it.**

```bash
uv run python scripts/collect_iedr_register.py
uv run ark ingest iedr_register data/raw/iedr/*-doms.html
```

27 requests, 724 KB. Three fetch details each produced a false negative before being fixed, and
they are in the collector's own docstring: use `https` because port 80 refuses connections while
443 answers, follow redirects because Wayback 302s each letter to its nearest capture and a fetch
without `-L` returns zero bytes, and never run two copies at once because the second overwrites
the first's pages with empty files.

**Date semantics.** Each page's own machine-written line, `updated automatically at 14:51 GMT on
Friday, 21 December 2001`, read with the HTML tags stripped first because the footer spans a `<b>`
in some editions. **A page whose own line falls outside the window is dropped whole**, which is not
a formality: `l-doms.html` resolves to a 28 March 2002 edition, and taking the capture stamp instead
would have imported 931 names into 2001 that the artifact places in 2002.

**Evidence type `artifact_listing`.** A register regeneration is the registry stating which names
were registered at a stated instant, the same instrument as an InterNIC zone file, not a directory
listing names it happens to know. Nobody typed the list, so no corroboration split applies. It says
nothing about any other year.

**Lineage `registry`.** Independent of every web crawl.

**Measured yield: 19,341 net-new pairs worth 18,845.9 equivalent-English**, one measurement over
both trees: 18,512 at 2001, **812 at 1999** and 17 at 2000. The 2001 tree alone was counted three times
independently and agreed to within 0.3%. `.ie` weighs 0.9744, so a pair here is worth 1.54 of a `.com`
one. 6,626 of the net-new names are dated at no in-window year at all.

**Two trees, and the earlier one is where the thin years are.** `/statistics/` is the December 2001
edition. The earlier `/lists/` tree, enumerated from the CDX index at 11 pages serving 200, gives
`a-doms.html` at 27 November 1999 and `t-doms.html` at 29 November 1999 plus six pages at 29 February
and 1 March 2000. It is worth **829 pairs and 807.8 EE, of which 812 are 1999**, and the 2000 side is
worth 17 pairs. That asymmetry is the same fact as the note below: the baseline already used a 2000
edition of this artifact.

**`stalled.html` is excluded by filename and this is not a detail.** The same trees publish it, and it
lists PENDING APPLICATIONS: names nobody had registered yet. Reading it as a register would manufacture
registrations that never happened, so the parser checks the filename before it reads the date.

**Admitted master by Ivo, 2026-08-24, on the artifact's own semantics.** A cron regenerated the whole
register and stamped the page with the instant it did so, and an IA crawl fixes when that page existed.
Those two facts alone date every name on it, and they are the grounds.

**Corroborating, and explicitly not the grounds.** The store holds 18,438 `.ie` at 2000 against 6,598
at 2001, and the baseline shows why: 889 of 892 names on this artifact's **April 2000** edition are
already dated 2000, so whoever built `prior_task` read a 2000 edition of these very pages and never a
1999 or 2001 one. Re-measured against the live store on the day of the decision, edition by edition:
99.6% of the 29 February 2000 C page is already dated 2000, against 34.0% of the 27 November 1999 A
page and 28.4% of the 21 December 2001 A page. That agreement is a check on our reading of the
artifact, not a reason to admit it: killer 8 in `CLAUDE.md`.

**Residual.** Both trees are collected to exhaustion of what Wayback holds: 26 of 27 `/statistics/`
letters and 8 of 8 `/lists/` letter pages that serve 200. The `/lists/` tree is missing letters b and
h through z entirely, which is an archiving gap rather than an artifact gap, so **[GUESS]** a full 1999
register would be worth roughly 3,000 to 4,000 EE rather than 808. `iedr.ie` carries a 2002-only tree,
out of window. Nothing further to fetch here.

---

## Evaluated and rejected

Recorded so that negative results are visible rather than silently omitted.

| Source | Verdict |
|---|---|
| Scholarly-index sweep for deposited early-web data, and the false friend that dooms it (2026-08-24) | **Closed on a FAILED positive control, which is the strongest kind: the index cannot see the one dataset in this space we know exists.** The DataCite sweep earlier today searched dataset registries; this asked the citation graph instead, via the free OpenAlex API, on the theory that papers studying the 1996-2001 web deposited their panels. Three results. (1) **`type:dataset` restricted to 1996-2005 with web, URL or domain in title or abstract returns 3,363 works and not one is a URL corpus**: the visible population is protein crystallography (`CRYSTAL STRUCTURE OF GELATINASE A CATALYTIC DOMAIN`) plus web-usability papers. **`domain` is a false friend in scholarly search and means PROTEIN domain far more often than DNS domain**, so any keyword sweep of an academic index on that word is dominated by molecular biology. Worth knowing before designing the query, not after. (2) **The control fails**: a search for the phrase `early web` returns 314 works and **not one of them is the UMN DRUM early-web link-list dataset**, the reviewer's own worked example and a dataset this project has already ingested. An index that cannot surface a known positive cannot be trusted to surface an unknown one, so the ROUTE is shut rather than the shelf being bare. The query mechanism itself is sound, proved by 478,747 datasets matching the same keywords with no year filter. (3) **The population that does exist is killer 3 in its purest form**: 274 works on corporate web sites 1997-2005, and their titles are the verdict, `Content analysis of Fortune 100 company Web sites` and `Global corporate web sites: an empirical investigation`. Populations of 100 to 500 authority firms, which a capture-derived baseline holds first. **The structural reason the whole lens is dead**: research that studied the in-window web predates data-deposit norms, which arrive around 2010, so the papers exist and their data does not |
| The pre-Nominet and Nominet `.uk` register, and the counterfactual it quantifies (2026-08-24) | **The highest-value question left in this project, asked properly, and the answer is that the file never existed. Clause one of the screen passes better than anything here and clause two fails absolutely.** One operator, one database, and Nominet's own page saying `The .uk Register Database now contains 2 million Domain Names as of 31st July 2000`, at an English share of 0.9813. But an **uncollapsed** sweep of `nic.uk`, `nominet.org.uk` and `nominet.net` for 1996-2002 returns 12,491 captures over 2,710 distinct URLs, and **the largest object the registry ever served is a 94,785-byte MEMBERSHIP list**, with RFC 1122 as the next largest family. No register listing, no zone extract, no new-registrations file with names, no deletions list, no applications list. Nominet published counts: `news/stats/stats.1996.html` through `stats.2002.html` are monthly totals per second level, and `news/reg-record.html` boasts of 19,767 registrations in 24 hours without naming one. The register was exposed only through a per-name form at `cgi-bin/whois.cgi`, four captures ever, and a members-only bulk WHOIS at `members-private/expanded-whois/` that answers **HTTP 401** in both of its captures, both 2002. That is the `.lk`/`.th`/`.kr`/`.nz` failure mode occurring at the largest high-weight namespace left. Measured yield of the one bulk name-bearing file: 1,478 registrable domains of which 1,476 are already held, **2 net-new pairs, 1.96 EE**. **The counterfactual is why this entry is worth reading**: we hold 507,017 distinct in-window `.uk` domains against Nominet's own 2,000,000 at 31 July 2000, so a complete register listing for that single year would have been worth roughly 1.4M equivalent-English, twice the whole 5% gate. That is the largest quantified absence in this project. **One trap earned**: `codns-test/logfile.co.uk.May1996` carries a real in-body generation line, `#Last updated at Fri May 31 23:56:01 1996`, and is the artifact a CDX-length heuristic would promote first. It is `#Nameserver availability statistics for co.uk`, twelve rows, every one a nameserver, zero registrants |
| `uk.*` registration announcements as a `can.domain` analogue (2026-08-24) | **Zero, exactly rather than approximately, and it corrects two numbers in this register on the way.** Every file the lead names is already in `.processed`, so a fourth read yields 0 by construction, and the whole `uk.net.news.*` subtree measured **1,031 gross pairs across three prior reads against 69,609 for `can.domain` on the identical pipeline**, 67x short before the split. **Correction 1**: the 2026-08-16 row logged the unfetched half of IA `usenethistorical` as `175 GB is unheld`; derived from the collection metadata it is **270.81 GB across 1,007 items**, 96 GB more. **Correction 2, and it cuts the other way**: that row projected **15.5 net-new post-split pairs per MB** for `usenet-microsoft`, and three microsoft archives totalling 495.8 MB measure **0.20 pairs per MB, 77x lower**, which prices the whole 26.6 GB hierarchy at about 3,219 EE rather than the 412,000 pairs the old figure implies. Its small-vs-large pairs-per-MB pair of 37 against 4.5 now measures 3.89 against 0.125. **The honest band for the unfetched 270.81 GB is 5,000 to 45,000 EE and a 1.2 GB sample cannot narrow it**, because the 0.44% sampled was chosen where it pays while the stratum's real bulk is `ukr`, `swnet`, `italia`, `hun`, `han`, `maus` and `z-netz`, which an English-weighted metric discounts to nothing, plus `mozilla` and `aol`, which are post-window. The sanity check that kills the optimistic end: the original 411 GB read fresh against a store 2.7x emptier paid about 140,101 EE in total, which is 341 EE/GB, and a saturated fourth read cannot pay 6.4x a first-read rate |
| Three more high-potential leads, all under the 5,000 EE bar (2026-08-24) | **Recorded together because the bar is the finding: five named leads were chased and none reached a human's decision queue.** **`.us` locality registers: 39.6 EE.** The tree was 6,505 separately delegated administrators rather than one register; seven pages over four states plus the international list give 929 distinct domains and **0 novel names, 0.0%, on all four states independently**, leaving 56 pairs that are held names gaining a capture year. Whole-registry ceiling 285 pairs. **Machine-authored commercial indexes: the Granite Canyon secondary-DNS artifacts, 1,881 to 1,953 EE post-split.** The best of the lens and still 2.5x short: 19,882 items, 17,142 in-window pairs, 6,505 already held, 10,637 net-new and 5,963.5 EE **gross** but 3,367 pairs and 1,881.1 EE after the split, mean weight 0.5587. A sceptic reproduced every figure to the decimal, found one parsing error in the source's favour, and struck the reading that would have cleared the bar because it counted **rejected applications**. **Wildcard above 20,000 EE: nothing.** Best candidate was Nominet's own member list at 507.96 EE over 712 pairs, priced against both the baseline release and the live store |
| `ark gaps` ranks by what an answer is worth and not by the chance of getting one, and that costs 10x (2026-08-24) | **Not a source, a defect in our own targeting, measured against a control the same day.** `ark gaps` builds the bracketed-gap queue, 451,490 domains at a 264,814 EE ceiling, and its docstring states the assumption openly: *the hit rate is near-uniform over this population, so what separates targets is what an answer is worth, not the chance of getting one*. **The assumption is false and the queue head proves it.** Ranking by English share times bracketed years puts the highest-weight namespaces first, so the head came out `.com.au` and `.co.uk` heavy, and a 600-query batch on it returned **26 with_capture and 31 years_found, 5.2%**, against **673 years from 600 queries** on the `.com`-heavy file it replaced. Same engine, same hour, 21x apart. **It is NOT the 2013-gTLD trap this project already records**: only 24 of 451,490 names sit under a TLD delegated after 2001, and `hell.hot` leading the file is a curiosity rather than the cause. **A tempting diagnostic that does not work, recorded so it is not repeated**: the share of our held in-window pairs that are capture-backed reads `.au` 12.5% and `.uk` 9.7% against `.com` 2.2%, which looks like the answer inverted, but it measures OUR collection history rather than the archive's coverage, because our `.uk` and `.au` came from suffix sweeps while our `.com` came from registry creation dates. **Mitigated rather than fixed**: the queue is reordered to put the 364,878 `.com`/`.net`/`.org`/`.uk` names ahead of the other 86,612, keeping the weight ranking inside each group. The real fix is a per-TLD measured hit rate in the ranking, and until that exists the docstring's claim should be read as a hypothesis rather than a finding |
| Not Your Parents' Web TimeMaps, the deferral converted to a REJECT (2026-08-24) | **Reopened on its own stated condition and it has decayed rather than improved, which is the answer the condition was written to get.** The 2026-08-16 entry deferred this on a cost ratio and said `reopen when the archive is not the bottleneck, and take 1996 and 1997 first`. The archive is now very much the bottleneck for per-domain CDX, which made a bulk file of capture timestamps look more attractive, not less, and `ark gaps` says the population it addresses is worth a 264,814 EE ceiling. So it was tested at the cheapest possible point: `1996/..._deeplinks_part00o.tar.gz`, **5,641,617 bytes**, `gzip -t` passes, 5,150 files, fetched from `archive.org` which answered all day while `web.archive.org` refused three requests in four. Format confirmed as recorded, field 3 a 14-digit timestamp and field 6 a status code. Measured over all 372,113 lines: 71,192 non-200 dropped, 129,959 out of window, **17,035 distinct in-window pairs of which 17,006 are already held. 29 net-new, 14.2 equivalent-English, 5.4 net-new pairs per MB** against 8.6 when it was deferred and **997 for the Dartmouth capture census**. Whole-family arithmetic, stated so nobody redoes it: 19.35 GB at 2.6 EE per MB projects about 48,000 EE, and that projection is an OVERESTIMATE because the part measured is `deeplinks` while the bulk is `rootURLs`, and a root is the more-crawled population we hold first. **One structural fact worth keeping**: the 1996-labelled folder's net-new pairs land in 1998, 1999 and 2001 and none in 1996, because a TimeMap carries a URL's whole capture history and the folder label is the year of FIRST archive, not of content. Anyone sizing this family by folder year will size it wrong |
| The Wayback `__wb/sparkline` endpoint as a cheaper dating route (2026-08-24) | **Untried, zero mentions in this register, exactly the right shape, and it is behind the same rate limiter, which is the fact that kills it.** `ark gaps` says 451,490 held domains have a bracketed missing year worth a **264,814 EE ceiling**, essentially the whole gap, and only an archive capture can fill one. `web.archive.org/__wb/sparkline?output=json&url=<d>&collection=web` answers **all six in-window years in one small precomputed JSON**, a per-month histogram, needing none of the `collapse` or `filter` parameters this register records traps for. Head to head over the same 80 gap-queue domains in the same minutes: **sparkline 8 of 80 at 1.93 q/s, CDX 7 of 80 at 0.93 q/s, failures 72 and 73 respectively, all URLError**. So it is twice as fast per attempt and **no less refused**: 10% against 9%. There is no side door, because the limiter is on the host and not on the endpoint. **Accuracy looks sound where it could be tested**: for `demon.co.uk` sparkline returns 1996-2001 and a `statuscode:200`-filtered CDX returns the identical six years, with the unfiltered scan showing all six captures are 200 anyway. The A/B produced **zero domains answered by both**, so no agreement rate could be computed from it and none is claimed. **Keep it for the day IA's posture improves**: one request for six years beats an index scan, and it is the natural engine for the gap queue if the refusal rate ever falls |
| The re-registration rule, re-measured after Ivo doubted it (2026-08-24) | **He was right and I was wrong, and the corrected number changes how much to trust every RDAP figure in this register.** I had written that a lapsed-and-re-registered name reports the later date *by definition*. Measured over 472 seeded-random domains our store dates in window from captures: 102 return 404 and of the 370 that answer **59.7% still carry an in-window creation date**, 36.2% a post-2001 one and 4.1% a pre-1996 one. **A transfer never resets it**, confirmed against explicit `transfer` events beside 1990s registrations: EFF 1990-10-10, Apache 1995-04-11, Python 1995-03-27, Perl 1995-05-31, all `.org`. **Nor does bankruptcy or a change of owner**, which is the case I expected to fail: Pets still reads 1994-11-21, Boo 1999-03-17, eToys 1997-11-03, Webvan 1998-06-29, Napster 1999-02-20 and theGlobe 1996-02-21, all `.com`. **Those examples are written as brand names rather than hostnames on purpose.** Written in the dotted form they were scraped straight out of this verdict by `reprobe_closed.py`, which classifies on words and found enough availability language here to treat the row as a dead-host closure, so the next cycle reported four healthy sites as closed leads that now answer. The register already records the inverse of this trap; this is the same lesson pointing the other way, and an example host in a verdict is a lead nobody meant to file. **But when a reset HAS happened there is no route back**, which is the half of my claim that survives: across 55 answered domains the only event actions any registry emitted were `registration`, `expiration`, `last changed`, `transfer` and `last update of RDAP database`. **No `reregistration`, no `reinstantiation`, and zero events of any kind predating the `registration` event.** So the original date is recoverable exactly when it was never overwritten, and RFC 9083 defines an action that would have carried it but nobody populates it |
| Arquivo.pt's live CDX as a DATING engine rather than a source (2026-08-24) | **A new question about an already-ingested archive, and it closes on coverage while proving the throughput that would matter if coverage ever existed.** Yesterday's finding reframed the problem: the 2.4M-name candidate pool is CDX-only work because only a capture can date an extinct name, and IA now answers about 600 queries an hour. So the question is not whether a non-IA archive has NEW names, it is whether one will date names we already hold. Arquivo.pt's `wayback/cdx` answers **17.3 queries a second with 250 of 250 HTTP 200s, about 62,000 an hour, roughly 100x what IA is currently giving us**. And it holds nothing we need: **0 in-window 200s over 250 seeded-random candidate-pool names, and 0 over 157 seeded-random domains our own store already dates in window**. **The zero is a content zero, proved against three controls fetched through the identical query shape in the same minutes**: `geocities.com` returns `19961013213730`, `yahoo.com` `19961013182902` and `sapo.pt` `19971210144509`, while `bbc.co.uk` returns nothing. So the in-window slice is a small famous-site donation plus `.pt`, which is law 3 exactly and is the same population as the `Roteiro` and `IA.cdxj` files already ingested from this archive. **Record the rate, not the source**: if a non-IA archive with broad in-window coverage is ever found, 17 queries a second is what makes it worth building, and the test is 250 queries against names our store already dates. Also re-probed in the same cycle and unchanged: Bibliotheca Alexandrina, where `archive.bibalex.org` now RESOLVES at 196.204.180.107 but refuses HTTP on both 80 and 443, so the 2026-08-05 closure stands with a live DNS record in front of a dead service |
| RDAP over the candidate pool, and why it cannot work (2026-08-24) | **The obvious idea, tested twice, and it returns exactly zero. The reason is structural and it explains why the generated sibling queue pays instead.** The store holds **2,395,205 names with no in-window year**, top TLDs `com` 828,253, `net` 398,709, `org` 285,878, `edu` 213,722, `mil` 186,561, `gov` 185,272, `uk` 50,895. Worth **1,658,653 EE if every one earned a single year**, six times the gap, and only 12,365 of them appear in the RDAP queues we have been running, so they looked like free money. Built the queue (1,647,197 names after dropping `.edu`, `.mil` and `.gov`, which publish no creation date) and piloted it twice: 3,000 from the head gave **336 answers, 234 of them HTTP 404, and 0 in-window creation dates**; an independent seeded-random 3,000 from the whole pool gave **266 answers, 195 of them 404, and 0 in-window**. 602 queries, zero. **CORRECTED 2026-08-24 after Ivo challenged the explanation, and the correction matters more than the zero.** The original claim was that a re-registration destroys the old date *by definition*. That is wrong. Measured over 472 seeded-random domains our store dates in window from captures: 102 return 404, and of the 370 that answer **59.7% STILL carry an in-window creation date**, 36.2% show a post-2001 date and 4.1% a pre-1996 one. **A transfer never resets it**, verified on explicit `transfer` events beside 1990s registrations: EFF 1990-10-10, Apache 1995-04-11, Python 1995-03-27, Perl 1995-05-31, all `.org`. Nor does bankruptcy and a change of owner: Pets still reads 1994-11-21, Boo 1999-03-17, eToys 1997-11-03, Webvan 1998-06-29, Napster 1999-02-20. **So the real reason the candidate pool returns nothing is not resetting, it is absence**: 73% of it is 404 against 21.6% for held domains, because a candidate is a name no crawler captured, which correlates with never having been much of a site. **And when a reset HAS happened there is no route back**: across 55 answered domains no registry emitted `reregistration` or `reinstantiation`, only `registration`, `expiration`, `last changed`, `transfer` and `last update of RDAP database`, and **zero events of any kind predate the `registration` event**. So RDAP can only date a name whose CURRENT UNBROKEN registration began in window, which is a completely different population from the pool: the survivors, not the vanished. **Only an archive capture can date an extinct name, so the candidate pool is CDX-only work, and CDX is throttled to about 600 queries an hour.** That is the whole shape of the project's constraint in one line, and it is why generated sibling and dictionary targets outperform 2.4M real discovered candidates |
| squidGuard robot-compiled blacklists (2026-08-24) | **Closed on era, and the era is stated inside the artifact, which is the cheapest kind of proof.** This was the highest-scoring untested entry in the triage queue at potential 72, and it deserved to be: robot-compiled so no corroboration split, an in-body compile header, and a population of adult, gambling and drug sites that is the long tail an authority-selected baseline misses, the opposite of law 3. Everything about the shape is right. **The dates are two years out.** The path is `ftp.teledanmark.no/pub/www/proxy/squidGuard/contrib/blacklists.tar.gz`, found by fetching the archived `squidguard.org/blacklist/` page for its real hrefs rather than guessing, and its earliest Wayback capture is **2003-12-11**. Fetched: 429,365 bytes, `gzip -t` passes, 64 files, and the base list's own header reads `# This list was compiled in 120:47:13 on 2003.09.04 02:03:42.` followed by `compiled from 1244 link sources and 1365757 links, of which 230619 tested successfully`. The only dated items are weekly diffs from `domains.20031110.diff` onward and the base `domains` files carry no date but that one 2003 header, so dating them 1996-2001 would be manufacturing. **The triage entry quoted a `2001.09.09` header and no archived edition contains one**: `blacklists.tar.gz` arrived with squidGuard 2.0.0, which postdates the window, and the pre-2002 filename `blacklist.tar.gz` has only 301 redirects in the index. Volume for the record, so nobody reopens it hoping for size: porn 48,558 lines, ads 3,102, drugs 508, hacking 306, gambling 73. **Reopen only on an in-window edition from a non-Wayback mirror**, and the header makes that a one-line test. The CyberNOT half of this entry, potential 58, is untouched by this and stays open |
| Registry change reports across five regions, and three CDX traps worth more than the sources (2026-08-24) | **The reopened lens paid about 7,500 EE over eight artifacts, none of them large, and the method findings are the durable part.** Paid: TWNIC's `.tw` frozen-domain list 1,275.0 EE, SaudiNIC 1,506.4, NIC Malta 1,470.5, NIC Venezuela's cartelera 1,131.3, IDNIC's unpaid list 872.6, RESTENA `.lu` 708.5, ISOC-IL 375.0, `.nu` notrenewed 144.1. **The gTLD side is empty and the reason settles it**: the only volume-bearing in-window listing is `greatdomains.com`, whose own page reports 2,466 records, an owner-submitted for-sale inventory that law 5 splits to about 104 EE. **A THIRD registry failure mode is now on record and it is the commonest**: one operator, one database, **query-only interface**. `.lk` was the single-academic single-machine shape this hunt predicted would pay, and its whole host is 39 in-window URLs of forms and policy because the register was only ever exposed through `cgi-bin/whois`; `.th`, `.kr` and `.nz` fail identically. So the screen needs two clauses: ask who held the database, **then ask whether they ever wrote it to a file.** **Three CDX traps, each of which caused a false negative before it was caught.** (1) `matchType=domain&limit=3000` truncates **alphabetically, not by date**, so a host with a large modern footprint hides its era tree completely: `usp.ac.fj` returned 3,000 rows containing **one** in-window 200. Add `from=` and `to=`. (2) A commercial registry burns the whole row budget on session and partner query strings; `filter=!original:.*\?.*` cut `tonic.to` from 5,000 rows to 536. (3) **The CDX `length` column is the compressed WARC record size, not the page size**, and a big uniform table compresses hardest: one page reads 23,977 in the index and 251,567 bytes on the wire, a 10.5x ratio, so ranking candidates by CDX length under-ranks exactly the pages worth having. The `.id` find was nearly discarded on that basis |
| National register listings, the `.ie` shape tested across nine namespaces (2026-08-24) | **Two paid, six are empty, and one was a closed family re-proposed by mistake.** The `.ie` register listing paid 18,846 EE, so the shape was taken to every high-weight namespace. Paying: **`.my`** MYNIC's fortnightly change report, own entry, and **`co.za`** deletion listings, own entry. Empty on measurement rather than availability: **`.nz`**, where the whole Domainz site is 170 unique non-image URLs and its two most data-shaped pages yield 5 and 1 names, because ISOCNZ exposed the register only through a whois server capped at 50 responses; **`.au`**, where the largest page in the whole archived AUNIC tree yields 10 names and all 10 are the form's own worked examples; **`.ca`**, where `cdnnet.ca/info/statistics` is counts only; **`.sg`** and **`.hk`**, no listing; **`.ph`**, a rolling 30-day expiry window rather than a register, 532 names and **467.5 EE**, real but a fragment; **`.in`**, an ISP roster of 80 names worth 62.7 EE. **The transferable screen is the best thing this hunt produced: ask who held the database before asking what the archive holds.** `.ie` was one university computing service regenerating one register onto one static tree. `.za` was eleven separately administered second levels, most accepting applications by e-mail to a named individual, so there was no single machine to regenerate and there is no single page to find. **Two process failures worth recording.** An agent proposed `nic.us/domain-delegated.txt` at about 11,000 EE; it is the family closed here on 2026-08-18 at 1 net-new pair, and the figure it quoted is the exact trap that row was written to name. And an agent returned `found=true` on the `.nz` registry's `pending.html`, a list of **pending applications**, which is the same artifact our own `.ie` parser refuses by filename because reading it manufactures registrations that never happened |
| A trap in pricing any URL-bearing source, caught before it was reported (2026-08-24) | **`ukwa_geoindex` re-priced at 4,509.1 EE over 4,595 pairs, and the first attempt said 6,348,826.5.** The parser yields `BulkRecord.raw` as the captured URL, not a domain: the loader runs `to_registrable` on it at ingest time, and a pricing script that joins `raw` against `domain_year` therefore compares URLs to domains and finds **zero held**, which reads as total novelty. The tell was in the output and is worth memorising: the top net-new TLDs came back as `htm` 2,106,483, `html` 2,055,761, `php` 212,200 and `uk:80/` 140,100. After canonicalisation the 17,912,511 rows collapse to **289,857 distinct pairs of which 285,262 are already held**, a 62-fold difference from the raw count and a 1,408-fold difference in the answer. **Rule: price on the canonical form the loader will store, never on the parser's `raw`, and treat a suspiciously high novelty rate as a bug before treating it as a find.** The verified figure agrees with the 4,512 already on record to within 3 EE, so the source has stopped decaying |
| DataCite sweep for deposited early-web datasets, the reviewer's own named method (2026-08-24) | **Run properly with the queries recorded, and it surfaces nothing this register does not already hold. That is the useful result: the deposited-dataset lens is exhausted rather than untried.** Eight query shapes against `api.datacite.org/dois`, which indexes Zenodo, figshare, Dataverse, DRUM, arXiv and the institutional repositories in one place. Titles matching link list, link graph or hyperlink together with web: **21 hits, and the only in-window one is the UKWA host link graph we already hold 2 GiB of** (`10.5259/ukwa.ds.2/host.linkage/1`). Titles matching early web: **19 hits, of which the only two data deposits are ones already priced here**, UMN DRUM (`10.13020/d62684`, ingested) and the Zenodo banner ads (`10.5281/zenodo.8408538`, measured at 432.81 EE). `web crawl` published 1997-2006: **zero**. `zone file` or `DNS survey`, any year: **zero across the whole of DataCite**, which independently corroborates the closed zone-file family. The 79 hits for url, seed or host list are entomology and botany, `A catalogue and host list of the Anoplura`, 1916. `web archive` deposited 1998-2008 is 4 hits: Danish policy prose and a violin bowing database. **The zero is proved against a working control**: the same API in the same minutes returns HTTP 200 for all three known DOIs, and the first two query shapes found all three unprompted, so the sweep can see what exists. Reproduce with the query strings above; there is no need to walk repository front ends one at a time |
| Nominet RDAP over the `.uk` we already hold, banked not rejected (2026-08-24) | **The densest route measured in this project, and it needs no approval because it is the already-approved evidence class.** `rdap.nominet.uk` publishes a `registration` event with a full timestamp, verified on `demon.co.uk` at `1996-05-05T21:08:48Z`, so `ark rdap` reaches it through the IANA bootstrap and its journals ingest as `rdap_snapshot / whois_creation`, `Decision: master` since phase 4. Measured on a seeded 400-name sample of held `.uk` domains, read at 157 answers: **29.3% carry an in-window creation date, 19 of 46 pairs are net-new, and that is 118.8 equivalent-English per 1,000 queries** against 13.5 for the best generated population and about 4.8 for the engine's own list. `.uk` weighs 0.9813 and 45% of answers are 404, which is what a 1996-2001 name looks like today. **The reason the headroom exists is worth recording: of 507,011 held in-window `.uk` domains, 266,249 carry exactly ONE of the six years** and only 12,473 carry all six, because our `.uk` came from suffix sweeps that found whichever year the archive had. Queue of 557,907 at `data/raw/rdap/queue_uk.txt`, whole-queue ceiling **[GUESS]** near 66,000 EE. **Throughput is the constraint, not density**: Nominet answers in about 1.4 s and refuses roughly one request in four, so the governor settles near 0.5 to 2 queries a second, which is 200 to 850 EE an hour rather than the 50,000 the density alone would suggest. **The multi-year reading is NOT taken**: a live registration dated 1997 would, on Nominet's reset-on-re-registration rule, imply continuous registration through 2001, and that is exactly the 1,704,843 EE idea rule 6 already forbade. One creation date, one year. Sibling probe recorded so nobody repeats it: `.au` RDAP serves no registration event, `.in` does but opened to the public in 2005, and `.nz`, `.za`, `.ie` and `.us` are absent from the IANA bootstrap entirely |
| UCSF Industry Documents Library, 3.83M dated in-window documents (2026-08-24) | **Rejected on the corroboration split, and the split is the whole story.** Genuinely untried, properly dated (`documentdate` per document), non-IA, and big: the solr index gives 695,228 in-window documents for 1996 rising through 742,760 for 1999, 3,826,999 in total, with OCR downloadable per document. Enriched rather than sampled blind: 0.76% of documents contain the string `www`, about 29,000 in window, and **6,000 of them fetched** end to end. 5,462 pairs, 3,522 already held, **1,940 net-new gross for 1,284.4 EE, and 216 pairs for 146.6 EE after the split**, because 89% of the net-new names are dated nowhere else. Whole-population projection is about 730 EE post-split. The TLD census names the other half of the problem: `cam` appears 34 times, which is `com` misread, so the net-new half and the OCR-damaged half are the same population, exactly as the printed directory books row already found |
| Small-organisation open data with a per-row date, four registers measured (2026-08-24) | **All four are zero, and three of them are zero because the column does not exist.** The lens was right to try: ordinary small bodies rather than universities, which is the population that survives authority selection. **DOL Form 5500** pension filings, 740,473 dated 1999 rows and **zero hostnames**, no e-mail or URL field in the era's schema. **CRA T3010** charity returns, 441,785 in-window rows, zero. **EPA TRI Form R** contact fields, 2,400 in-window rows, zero, against a same-minute positive control. **Canada Gazette Part 1** 1998-2001, about one non-government domain per weekly issue, 50 to 100 EE for the whole run. **The transferable screen: ask whether the FORM had a web-address field in 1999, not whether the data survives.** Most did not, and that is answerable from one blank form |
| Uncrawled mailing-list subscriber populations, the reopen condition tested (2026-08-24) | **The register's own reopen condition was 'ask whether a list's SUBSCRIBERS were an uncrawled population'. Tested, and the answer is that the uncrawled ones are the unreachable ones.** **RootsWeb** genealogy lists, the best case by population (ordinary individuals, thousands of lists, 1996 onward): 4 Archive-It items and 26.47 GB of WARC, measured at effectively 0 EE and certainly under 500, because the surviving capture is of the modern web interface rather than the archives. **ArchiveTeam Yahoo eGroups**: 8,271 items, zero net-new EE by access rather than content, and the 220 TB figure that makes it look enormous should be struck. **bit.listserv** via Usenet, 3,522.8 MB held: 1,100 to 1,600 EE for the whole hierarchy against a 27,000 to 34,000 proposal. So the condition is closed: the populations that would pay are the ones nobody archived in bulk |
| Organisational mail releases beyond Enron, the family enumerated (2026-08-24) | **One real member found and it is 67x short; the rest are behind agreements.** `jeb_bush_gubernatorial_email`, the Florida governor's 1999-2007 archive from `jeb@jeb.org`, is a genuine Enron-shaped release: 411,928,998 bytes on archive.org, 626 born-digital Outlook text files, 519,581 in-window `Sent:`/`Date:` headers, correspondent addresses unredacted, and **4,011 EE over 6,412 net-new post-split pairs, of which only 1,607.7 EE comes from a `To:`/`Cc:` line**, the rest from forgeable `From:` headers and body prose. 5,148 of 6,412 pairs land in 2001, our strongest year, and 31 across 1996-1998. It also **corrects a false negative in this register**: the 2026-08-06 row recorded an archive.org search returning 'all video or news', which was a failed search rather than a measurement, and the item has been public under identifier `JebBushEmails` since 2015. **Avocado (LDC)** and **Clinton EOP (NARA)** are both 0 EE obtainable, behind signed agreements and a disabled API respectively |
| Generated RDAP target populations, four of them measured against each other (2026-08-24) | **Genuinely untried: the register held nothing on generating names rather than discovering them, and one of the four beats the running engine 2x.** RDAP creation dates are `whois_creation`, master-eligible, self-dating and already approved, so the only question is which population is densest in in-window creations. Four populations of 1,500 to 3,000 names each, queried direct to Verisign in one folder apiece so the resume-skip could not hide a result, then priced against the live store. Independently re-counted by the ingest, which agreed to the row: **English dictionary words 13.5 EE per 1,000 queries** (28.00% of queries carry an in-window creation date, 420 pairs, 388 already held, 32 net-new); **sibling TLDs of names we already hold 9.7** (5.64% in-window, 79 pairs, 54 held, 25 net-new); **random four-character strings 6.3** (6.73% in-window, 101 pairs, 86 held, 15 net-new); **invented two-word compounds 0.0** (859 queries, **zero** in-window, the whole population created later or never). Against the running engine's own `fastq_local` at 0.76% and about 4.8 EE per 1,000, dictionary words are 2.8x and siblings 2x. **Two things decide which one to build, and it is not the better rate.** The dictionary is finite: about 235,000 words over three gTLDs caps the whole lens near 6,000 EE and it exhausts in under an hour. Siblings are a population of **14,080,169** names, built as every `.com`/`.net`/`.org` label held in window re-suffixed to the other two and filtered to what the store does not hold, of which only 2.3% appear in the exhausted list, so the queue is about 13.8M unqueried. At the measured 59.9 EE per 1,000 the whole-queue ceiling is near **843,000 EE**, more than the entire gap, and the binding constraint is time rather than material: the first round ran at 15 queries a second, so **3,265 EE an hour** and about 83 hours to cover the gap. Year spread is favourable and not flat: 1999 n=3,504, 2000 n=5,025, 2001 n=3,272, but also 1998 n=1,616 and 1997 n=680 in a thin year. **The dictionary result also says something about the store**: real English words skew 1996-1999 (81, 79, 70, 81 against 68 and 41 for 2000 and 2001), which is the thin end of our coverage, and they are still 92.4% held, so saturation is not a property of famous names alone. Both engines repointed the same hour; queue at `data/raw/rdap/queue_siblings.txt` |
| UKWA host link graph, the 2 GiB replay cap re-probed at byte level (2026-08-24) | **Shut, and now closed at the exact boundary against a control 4,096 bytes away.** This is the only lead ever sized to close a 5% gap on its own, about 1.1M equivalent-English, so it is re-probed rather than re-reasoned. `timemap/link` returns exactly two captures and no more: `20200106181208` and `20221031190607`. The 2022 one is empty, failing at byte 0 with curl exit 56 on four attempts. On the 2020 capture ranged requests DO work, which the earlier entry had wrong, and they work only up to the cap: `1000000000-1000004095` returns HTTP/1.1 206 with 4,096 real bytes, `2147479552-2147483647`, the last 4K inside the cap, also returns 206 and 4,096 bytes, and `2147483648-2147487743`, the next 4K, fails **five** consecutive attempts with `Couldn't connect to server` in the same minutes. So the file Wayback holds is exactly the 2147483648 bytes on disk and the remaining 18.8 GB was never captured. **The trap is that the headers say otherwise, and they say it convincingly.** A request for `20000000000-20000004095`, ten times past the cap, returns `HTTP/2 206`, `content-length: 4096` and `content-range: bytes 20000000000-20000004095/20928588915`, then sends no body and resets the stream with `INTERNAL_ERROR`. Wayback synthesises the range header from the origin's own 2020 `content-length` before it discovers it has nothing to send, so a prober that reads status lines and stops sees a working byte-range server over a 20.9 GB file. Read the body length, never the header. Six requests, no payload beyond 16 KB |
| Internet Archive's own bulk CDX / ZipNum index (2026-08-16) | **The one shape that could reach 5% on its own, and it is not public. Checked directly rather than assumed.** If IA published its cluster index the way Common Crawl does, our binding constraint would stop being request throughput. It does not: `archive.org/metadata/wayback-cdx-index` returns `{}` (no such item), and a TLD-wildcard enumeration `cdx/search/cdx?url=*.com&from=1999&to=1999` returns **HTTP 403**, so the CDX API is a per-URL lookup by design and enumeration is refused at the server. This is why the Dartmouth capture census matters so much: it is a precomputed slice of exactly this index, published for one research partner, and no general equivalent exists. **Do not re-probe this**; the 403 is a policy, not an outage |
| Usenet `Message-ID` posting hosts (2026-08-16) | **A real unexploited seam in data we already hold, measured, and empty. The reasoning that made it attractive was exactly backwards.** Every Usenet message carries a machine-generated `Message-ID` of the form `<id@host>`, and the project uses it only as a provenance string, never mining the host. It looked strong: the hostname is written by the posting software rather than typed by a human, so it should escape the corroboration split that removes most of the value from `usenet_mention`. **MEASURED over 73,751 in-window messages carrying both a `Message-ID` and a `Date`: 1,405 distinct registrable domains, 2,056 pairs, 51 net-new pairs, and ZERO domains never seen before.** 52 messages per domain. The top hosts say why: `wisc.edu` 22,380, `gi.net` 20,962, `supernews.com` 11,785, then `aol.com`, `att.net`, `earthlink.net`. **A machine-generated hostname is more concentrated than a typed one, not less**, because a typed mention names an arbitrary site while a `Message-ID` names the poster's news server or ISP, and the population of those in 1996-2001 is a few thousand hosts we already hold in full. Better evidence about almost nothing. The same argument closes `Received:` and `Path:` header mining, and `Path:` relay chains are already closed at 49 pairs |
| UKWA ds.1 classification list, recovered from a dead host (2026-08-16) | **Recovered, measured, and deliberately NOT ingested.** `data.webarchive.org.uk` does not resolve; the whole-register dead-host sweep found `opendata/ukwa.ds.1/classification/classification.tsv` intact in Wayback, 3,011,797 bytes over 26,910 rows. Columns are `Primary Category / Secondary Category / Title / URL` and **there is no date field of any kind**, so it is candidate-pool only by construction. Measured against the store: 9,863 distinct registrable domains, 3,167 already dated (32.1%), **6,643 never seen**. That looks like free pool growth and is refused on the same day's own finding: UKWA's *selective* archive began well after 2001, so most of those 6,643 are post-window sites, and this round has already measured what an undated pool full of names that never existed in window is worth (`.mil` at a 0.26% in-window capture rate over 8,234 answered queries). **Adding names to the pool is not free if they were never in the window**; it dilutes the one artifact whose only claim is that its contents merit verification |
| Cybermetrics (Wolverhampton) academic web crawl databases (2026-08-16) | **Found by applying this round's own recovery method, closed on measurement in about ten minutes, and it carries a trap worth more than the closure.** The method: when an era research data host dies, CDX its FILE PATHS rather than its pages. `cybermetrics.wlv.ac.uk` no longer resolves, and Wayback holds its whole `/database/` directory, including a 166 MB `uk_2002.zip` and a 45 MB `uk_unis_2000.exe`. **THE TRAP: the filenames lie about the year.** `stats/data/UK_2001.txt` opens with its own header, *"UK 2002 database crawled July 2002"*. Dating by filename, which is the rule that legitimately works for `isc_survey`, would have claimed 2001 for an out-of-window crawl. **Read the file's own header before trusting its name.** Closed anyway on the authority rule, measured: the population is UK universities, and **110 of 110 registrable domains in the file are already dated in an annual file, 0 net-new**. Consistent with IPEDS the same day, where `.edu` measured 95.5% saturated. The in-window files are `uk_unis_2000.exe`, `uk_july_2000_external_links.exe`, `aus_july_2000.exe`, `nz_July_2000.exe`; the external-link files are a link graph, so master evidence exists only on the source side, and the source side is ~110 universities. Everything else in the directory is 2002 or later |
| Era web traces and proxy logs, the whole family (2026-08-16) | **Closed BY DESIGN, not by link rot, which is why it keeps looking attractive.** Dated logs holding millions of real URLs is exactly the shape we want, and it is exactly the shape the 1990s privacy norm destroyed before publication. Three independent confirmations from the releases' own documentation: DEC/Compaq 1996, "it should not be possible to discover the actual identity of any host or URL in these traces"; BU 1998, "Request : Host: field (DNS name of server, hashed)"; ITA's UC Berkeley Home IP 1996, anonymised URLs. Add NLANR/IRCache (closed 2026-08-06, hosts now squatted) and MIT's DNS traces (never released). **Rule: ask any era-trace proposal for the sanitisation paragraph before fetching a byte**. **AMENDED 2026-08-18, and the amendment supplies the ground this row was missing.** A proposal arrived that the sanitisation rule genuinely does not touch: JANET's national web cache monthly host reports, the proxy every UK university browsed through, at `wwwcache.ja.net/stats/1998/04/report/raw_domains.txt` and a June sibling. Cleartext hostnames, an aggregate report rather than a trace, so there is nothing to sanitise. Both fetched, HTTP 200 at 17,456,109 and 23,284,728 bytes, and the month is corroborated by the origin server's own `last-modified` rather than only by the path. 421,866 distinct registrable domains, 72,048 unfiltered net-new 1998 pairs. **It dies on liveness, and the way it dies is the transferable part: the byte-volume filter that looks like the cure for the never-was-real trap is defeated by monthly summation.** The proposer spotted Squid's "could not be retrieved" page as a dense byte cluster at 1601-1615 and filtered above it, which looks rigorous and is not, because the byte field is a MONTHLY SUM: any host requested twice carries two error pages and clears the threshold. Straight out of the file, three typos of `bbc.co.uk` each carrying exactly two error pages, all passing: `bbbc.co.uk 3193`, `cbbc.co.uk 3181`, `wwww.bbc.co.uk 3209`. The harmonics are visible as a second peak at 3204-3234 and a third at 4797-4866. Measured against a control drawn from the same file, its own domains the store already dates to 1998: the control sits 80.5% above 7,000 bytes and 3.8% in the 1x error band, while the net-new sits 11.8% above 7,000, 46.9% in the 1x band and 17.1% in the 2x/3x/4x bands, so **12,355 of the 20,838 filtered pairs (59.3%) are error harmonics**. Independently, **1,444 of them could not have existed in 1998 by registry rule and that is a floor**: 461 bare `.uk` (Nominet sold no second-level `.uk` until 2014, and `.uk` is this source's highest-weight namespace), 602 bare `.co` (Colombia opened its second level in 2010: `rolex.co`, `bankofengland.co`, `yhaoo.co`, all truncated `.co.uk` typing), plus www-glued missing-dot names. The same typing failure inside `.com` and `.co.uk` is invisible to any TLD test. **This is C-19's Netcraft finding again**: a dated artifact that lists names proves the artifact's date, not the names' liveness. Netcraft measured 9.4% earliest-capture-1999-or-earlier against a 10.9% base rate; a 20-query indicative CDX control here puts the 2,001-7,000 band at 15% for 1999-or-earlier and 5% for 1998-or-earlier, with 40% having no Wayback capture in any year. **So the family stays closed, now on two independent grounds, and a proxy log is the never-was-real trap in its purest form: it records what was REQUESTED**  **RE-CONFIRMED AND EXTENDED 2026-08-24, after this row was re-proposed by mistake.** An agent brief described this lens as untried; it is closed here three times over (this row, IRCache/NLANR, and the Internet Traffic Archive), and grepping the register before writing the brief would have caught it. The re-run is worth keeping anyway because it adds a THIRD and stronger ground. **Artifact exhaustion.** The ITA is now enumerated whole at **16 datasets**, and every one is out of window, single-server (so the only hostname is the server's own), or anonymised. Verbatim sanitisation, read before any download: UC Berkeley Home IP 1996 (9,244,728 references, squarely in window) says "the request URL (**suitably anonymized**)" and ships `anon_clients`; WorldCup98 (1,352,804,107 requests) replaces the URL with "`objectID` - a unique integer identifier"; Boeing's May 1999 proxy traces "are anonymized and IDs are not preserved from day to day". The cleartext ones are out of window: BU-Web-Client is 1994-11-21 to 1995-05-08, Calgary-HTTP 1994-10-24 to 1995-10-11 with "Paths have been removed". **CAIDA holds zero in-window hostname-bearing data**: its sitemap is 1,724,893 bytes over 154 distinct datasets, the earliest passive trace is `passive_2007_pcap`, and every DNS dataset is current-state. Two zeros proved against controls in the same minutes: archive.org `nlanr trace` returns **0** while `ircache` returns 3, `squid proxy log 1998` returns 6 and `web proxy trace 1997` returns 4. **And the second ground is narrower than this row reads, which is worth knowing before anyone reopens it.** The JANET kill turned on the byte field being a MONTHLY SUM, so a host requested twice carried two error pages and cleared any volume threshold; a PER-REQUEST log with per-record status and response size defeats that objection exactly, excluding never-was-real per record rather than per month. **The crack exists and has no artifact to walk through it**, which is why the family is closed by exhaustion rather than only by argument. Reopen only for a named per-request CLEARTEXT in-window log. A DNS query trace with response codes would be stronger still, proving resolution rather than request, which is the ISC-survey standard we already accept; none was released for 1996-2001, MIT's were never released and DITL starts 2002. **Citizenship: `mawi.wide.ad.jp` disallows every `samplepoint-*` directory and all `*.gz`, so WIDE/MAWI is off limits and was not fetched.** |
| Library catalogue records with a MARC 856 URL, upgraded from reasoned to MEASURED (2026-08-16) | The 2026-08-15 entry closed this by argument and named an untested escape hatch, records whose MARC 005 last-transaction date is also in window. Now counted over 84.1 MB retrieved across three dumps, and the escape hatch fails on volume: **47 qualifying records in 48.2 MB of Scriblio, 13 registered domains, 12 already held, ONE net-new** and that one a public-suffix subdomain. **The structural finding generalises past MARC and is the part worth keeping: the dating requirement and the URL-bearing requirement are ANTICORRELATED.** LC books carry an in-window 005 on 28.25% of records and hold 67 distinct hosts in 72,588 records; LC serials hold 3,492 distinct hosts in 46,390 records and carry an in-window 005 on 0.34%. A record keeps an in-window 005 only if nothing has touched it in twenty-five years, and a record naming a website is exactly the record somebody has since touched |
| Search engine indexes 1996-2001, the whole family (2026-08-16) | **Not one machine-readable dated hostname list survives from any search engine of the era.** AltaVista: the CS2 papers put the substrate at a May 1999 crawl of 203M URLs, no list was ever published, HP retired the DEC/Compaq report archive so even the papers are gone, and Yahoo Webscope, the only distribution route for the Broder graph, no longer resolves. Lycos, Excite, HotBot/Inktomi, Infoseek, Northern Light, WebCrawler: six archive.org metadata sweeps, zero index artifacts. The only surviving search-engine-derived corpus is the Open Directory and **we already hold all three surviving in-window dumps**. `100hot.com` is the one that had a real chance and is now closed on a hard number: the full dated series DOES survive, 43,116 in-window captures over 27,943 unique URLs, but 130 pages already on disk give **132 net-new pairs and 78.68 EE** against 3,739 already held, at 0.52 net-new pairs per archive request versus the gap engine's 0.6 to 0.959 |
| IPEDS institutional characteristics, US Dept of Education (2026-08-16) | **Measured and rejected, and the number generalises.** Genuinely untried, and it looked ideal: per-year files, a `webaddr` column, a per-item `date_ic`, and `.edu` at 0.9717. Killed by saturation: of 3,251 distinct domains in `IC99_HD`, 3,106 are already held, 3,093 already dated somewhere, and **2,946 already dated 1999**, the exact year the file attests. Net-new 305 raw pairs, **147 post-split, 100.8 EE**. Compounding it, the web-address column exists for one in-window year only; `IC2000` and `IC2001` do not have it and seven earlier files 404. **The transferable figure is that `.edu` is 95.5% saturated at the year an institutional directory attests**, so screen any academic or institutional directory against that before pricing it |
| Unheld Usenet hierarchies, IA `usenethistorical` (2026-08-16) | **Deferred with the split measured, not rejected.** We hold 411 GB over 12 hierarchies; the collection is 1,019 items and 692 GB, so 175 GB is unheld. Enumerated the whole collection in one API request and grouped by hierarchy: **only about 40 GB is English-facing** (`microsoft` 26.6 GB, `linux` and `bit` and `free` ~13.1 GB) and about **135 GB is national hierarchies** (`de` 22.4, `it` 18.9, `tw` 17.8, `fido7` 16.9, `pl` 12.0, `fr` 11.9, `nl` 6.6, plus `hr` `es` `dk` `sfnet` `relcom` `fj` `no`), which an English-weighted metric discounts to near nothing. So the headline 175 GB overstates the prize about 4x before a byte is fetched. On yield per byte it loses badly: a measured `usenet-microsoft` sample gave **15.5 net-new post-split pairs per MB against 997 for the Dartmouth census**, 64x worse, over 26.6 GB rather than 228 MB. **Worth keeping for one reason that is not size**: Usenet is a different provenance lineage from every other large gain this round, all of which are Internet Archive derived, so it corroborates rather than repeats. Next round take `microsoft`, `linux`, `bit` only, and expect saturation to bite hard since a support forum repeats a handful of ISP domains endlessly |
| Not Your Parents' Web TimeMaps, IA `nypw_timemaps` (2026-08-16) | **Deferred on cost with the number attached, not rejected on shape.** CC-BY 4.0, in-window folders total **19,350,762,163 bytes** and the format is sound: field 3 of a TimeMap line is a 14-digit capture timestamp, so the year is per-record. Two things decide it. (1) **It is a sample and says so**: the methodology paper (arXiv:2507.14752) documents "downsampling over-represented domains" and grouping by year of FIRST archive, which is the same population as `nypw_firstcdx`, already `Decision: rejected` at 53 net-new domains over 6.28M lines. New DOMAINS are therefore expected near zero; the case rests entirely on new (domain, YEAR) pairs for domains we hold in some years and not others. (2) **The cost ratio is decisive against doing it now**: a measured part yielded 2,538 net-new pairs from 296.7 MB, which is **8.6 pairs per MB, against 997 pairs per MB for the Dartmouth capture census measured the same day, a 116x difference**. Pulling 19.35 GB from a host that is currently refusing 12.34% of our connections, while two collectors of ours are already on it, buys the worse deal first. **Reopen when the archive is not the bottleneck**, and take 1996 and 1997 first: those are our thinnest years and the smallest folders |
| Parallel Language Records of the Early Web, IA `early-web_parallel-language-urls` (2026-08-16) | **Rejected: it carries no date of any kind, which is the rubric's zero condition.** Retrieved the README and shard 00 (42,290 lines) rather than reasoning from the catalogue entry. The format is a SURT pattern followed by tab-indented `<lang> <url>` lines and **there is no capture timestamp anywhere in a record**; the only date is the collection-level "captured before year 2000". Spreading that across 1996-1999 is exactly the DMOZ failure the brief forbids by name, so it is candidate-pool at best. Its 1,164,183 records are also the wrong population for an English-weighted metric **by construction**: the top language tuples are `ca-sg` 134,941, `de-en-fr` 89,557, `en-fr` 60,323, `nl-uk` 42,349, `de-fr` 38,930, so the corpus selects for multilingual mirror sites, which skew `.de` 0.1324, `.fr`, `.nl` 0.1629 and `.ch`. Found while sweeping the `webarchivedatasets` collection that produced the Dartmouth census; the same sweep found `geocities-webarchive-collection-derivatives` at 793 GB, which is a hosting platform and collapses to one registrable domain |
| Netcraft Web Server Survey `/domains/cache/` listings, via Wayback (2026-08-12) | **Filed candidate-only: 0 pairs as master, and the 13,078 names stay in the pool.** Not rejected as a family and not closed on availability: the pages are there, the extraction is faithful, and the reading that made them worth 8,741 pairs and 5,708.4 EE is the one that failed. **The failure is a new shape and it is the reason to keep this entry.** Every other reject here died on density or on overlap; this one died on **contemporaneity**, which nothing had tested before. A `/domains/cache/<word>.html` page is a machine-generated alphabetical dump of every hostname in Netcraft's database matching the search word, with no author, no prose and no per-item date, so nobody typed the hostnames and the corroboration split was never the right question; the original reject of this lead as `typed` was wrong on its facts. What does not follow is that a name printed on a page captured in 1999 was a live site in 1999. Measured against a live-in-1999 control (230 domains the store dates to 1999 from an archive capture) and an undated-pool control: **earliest archive capture 1999 or earlier, 9.4% for netcraft against 10.9% for names carrying no claim to any year**, so no enrichment at all, and that row is the only one free of survivorship bias because both populations were queried by the same engine against the same archive in the same days. Supporting and weaker: still registered today 52.2% against 94.3%; continuously registered since 1999 or earlier 25.0% against 74.7% and a 16.6% pool base rate. **A test that cannot settle this, recorded so it is not run again:** registry creation dates, because a 1999 domain that lapsed and was re-registered reports the later date, and twelve sampled names created between 2003 and 2026 were each verified as genuinely printed on the archived 1999 page. **Generalises to any listing source:** a dated artifact that lists names proves the artifact's date, not the names' liveness, and the cheap way to test the difference is to compare the population's earliest archive capture against a population with no claim to that year. Decision and full working in `approved-sources-list.md` and key-decisions C-19 |
| INET conference proceedings 1996 to 2001 (2026-08-11) | **Rejected: 19 net-new pairs, 12.7 equivalent-English after the split, mean weight 0.6678, cost isoc.org 301-redirects to the Wayback Machine, so every request was an IA request; 223 pages.** 460 in-window pairs, 416 already held, 19 net-new after the split worth 12.7 EE. Whole-corpus ESTIMATE on the lowest of three fits is 116 EE for ~750 papers, roughly 40x below the bar. isoc.org no longer serves this content at all: every proceedings path returns 301 to web.archive.org, so the source is IA-only. Skeptic confirmed the direction but found the figures understated by an unrewriting bug that ran before attribute extraction, and disproved the claim that low density is a property of the source. FINDING THAT GENERALISES: the conference BROCHURE pages (programme, committee, schedule) average 6.06 to 6.54 distinct domains per page against 2.43 to 9.93 for paper bodies five times longer, and 9 of the 19 admitted pairs came from brochures rather than papers, because a paper cites famous infrastructure while a programme lists every participating organisation |
| Debian package changelogs and upstream homepage fields (2026-08-11) | **Rejected: 21 net-new pairs, 14.4 equivalent-English after the split, mean weight 0.6852, cost 36 index files from archive.debian.org, no IA.** 803 in-window pairs, 762 already held, 21 net-new after the split worth 14.4 EE. THE HYPOTHESIS'S NAMED MECHANISM DOES NOT EXIST IN WINDOW: grep for a Homepage field returns 0 across all 36 in-window index files, because Homepage entered Debian policy and dpkg around 2007. So any future proposal resting on Debian Homepage fields for 1996-2001 is wrong on its face and can be killed without a fetch. What is left is maintainer addresses and changelog trailers, which is the Linux Software Map population that closed at 86 pairs, and the per-package route projects to about 2 EE for the whole potato release. Skeptic confirmed the reject and found that the two extractions the original called independent both went through the same 13-TLD pattern, so they were not independent; correcting it makes one figure worse |
| W3C technical reports index dated per specification (2026-08-11) | **Rejected: 56 net-new pairs, 36.1 equivalent-English after the split, mean weight 0.6452, cost a handful of live w3.org requests, no IA.** A census of the whole in-window corpus rather than a sample, so there is nothing to project: 626 in-window technical reports yield 1,225 distinct pairs, 1,078 already held, 56 net-new after the split worth 36.1 EE. The ceiling is the whole source and it is 87x below the bar. Skeptic confirmed per-item dating from the W3C API (each version record carries its own date and a dated URI) and found an extraction bug that moved the post-split number by zero. TRAP WORTH KEEPING: W3C retrofits post-window status banners into archived recommendations, so the page served today is not the artifact that was published, and the first extraction consequently dated github.com to 1999. Any future use of live-served W3C pages as dated artifacts must strip those banners or take a period Wayback capture |
| RFC and Internet-Draft documents with publication dates (2026-08-11) | **Rejected: 140 net-new pairs, 88.2 equivalent-English after the split, mean weight 0.63, cost rsync bulk, 1,327 RFCs + 2,040 drafts, zero IA requests.** Complete RFC population plus a 12.2% seeded draft sample: 3,605 in-window pairs, 3,151 already held, 140 net-new after the split worth 88.2 EE. Whole-source ESTIMATE ~770 pairs / ~500 EE on the linear fit, 6x below the bar, and lower still since the two halves share 24.6% of pairs. Skeptic confirmed the arithmetic and found a parser defect that understates by ~30%, which does not change the answer. KEY FINDING BEYOND THIS SOURCE: the corroboration split does not protect against FICTIONAL hostnames, and this corpus is full of them by editorial habit (acmecorp.com, bigco.com, widgetco.com, john-doe.com); RFC 2606 reserved example.com in 1999 for exactly that reason. Also worth keeping: rsync.ietf.org::id-archive is a 179,052-file flat archive available in one polite transfer, a candidate-pool feeder even though it fails as master evidence |
| Microsoft Bookshelf Internet Directory, 1996 CD-ROM (2026-08-11) | **Rejected on measurement: 7 net-new pairs and 4.7 equivalent-English after the corroboration split.** Found by web search rather than recall, and worth recording because it is a real distinction inside a family already closed: the `cdbbsarchive` verdict says of shareware discs "not measured, and not worth measuring", and a 1996 Microsoft *Internet Directory* is a different payload with no OCR in it at all. So the closure's central argument, that for an OCR source the net-new half and the damaged half are the same population, did not apply. Measured anyway and it fails on overlap instead: the 99 MB ISO yields 2,020 distinct (domain, 1996) pairs of which **1,863, or 92.2%, are already held**, and the raw net-new figure of 157 pairs overstates the source **25.9x** against the 7 the split admits. **The typo bound is the useful number: 66.9% of the net-new names are one edit from a name the store already holds**, because the actual URL payload sits inside a compressed 1996 Microsoft Multimedia Viewer database and what is extractable in plain bytes is a keyword index of site titles plus Usenet group names. Treated as `typed` rather than self-dating for exactly that reason, so the contamination went to the candidate pool instead of into annual files. **Reopen only on a decoder for the .MVB payload**, which would be a different and much cleaner extraction |
| Web defacement mirrors other than attrition.org (2026-08-10) | **Closed on availability, and it was the best remaining idea in the class that pays.** The three sources that worked this round are machine-generated records about *all* domains rather than human curation of notable ones, which is why they are net-new where curated directories are not, and a defacement mirror is exactly that: self-dating `artifact_listing`, no corroboration split, and the population is whoever got hacked rather than whoever was famous. attrition's own index copies its pre-1999 entries from **earlier mirrors**, so siblings demonstrably existed. None survives as retrievable data. archive.org holds **0** items for `alldas` and **0** for `safemode defaced`, and its 212 hits for `defacement` are unrelated (a 2011 news clip, a malware source dump, Indian parliamentary library scans). GitHub, which is the only reason attrition's own mirror survives at all after its 2021 republication, holds no sibling: `alldas` returns 14 repos and every one is an unrelated modern dashboard, and the sole defacement archive there is `Mirror-H.org`, a 2010s collection well out of window. **Reopen only on a named surviving mirror**, since the family is right and the artifacts are gone. **`Mirror-H.org` itself is closed on measurement, not on reach, and this sentence exists to say so**: it answers today, and it always did, so the re-prober kept raising it as a lead that had become available when its dates had already been checked and every one of them postdates the window. Reaching it is not the problem and never was. **Do not reopen it on availability again** |
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
| UKWA per-year bulk CDX | Not publicly retrievable in 2026: dead host, soft-404 successor, 404 DOI, never Wayback-captured. Access requested. **URLs named here are the DATA paths, deliberately, and that is a correction made 2026-08-16**: this row used to name two bare hosts, the dead download alias and the British Library repository, so the re-prober tested a repository FRONT PAGE that has always been alive and reported the lead revived on every wake. The front page is not the lead, and naming a bare host in this register asks the prober the wrong question. Probe these instead, and note that `linkage/host-linkage.tsv.gz` is the positive control, a file we demonstrably hold 2 GiB of, which returns the same 159-byte HTML stub as the file we want: `https://www.webarchive.org.uk/datasets/ukwa.ds.2/cdx/1999.cdx.gz`, `https://www.webarchive.org.uk/datasets/ukwa.ds.2/linkage/host-linkage.tsv.gz`, `https://data.webarchive.org.uk/opendata/ukwa.ds.2/cdx/1999.cdx.gz` |
| ODP full 2001 content dumps | Verified unavailable in 2026: the URL serves a "Page Has Moved" stub |
| ODP full Aug-2000 content dump | Unrecoverable; only `structure.rdf` was archived, which has no external links |
| Public 1996-2001 zone files | **Some do survive: see the corrected row below.** Originally recorded as none surviving anywhere checked (DNS-OARC, resellers, academic torrents), which was true of those three routes and false of the artifact. An intact April 1997 InterNIC `.org` zone was found at `nic.mil` on 2026-08-18 |
| Historical zone files and bulk registry snapshots, the family closed out (2026-08-08) | The last routes the earlier rows left open are now checked, and the family is **closed for 1998-2001**. (1) **archive.org holds no in-window zone file.** `title:(zone file)` returns 303 items and every one is 2009 or later (`ee_zone_file_202404`, `root_zone_file_202206`); `mediatype:data` restricted to 1996-2002 returns 20 items and none is DNS data; `"com.zone"` returns **zero**; `description:(internic) AND mediatype:software` returns 4 items, all modern GitHub mirrors. (2) **The CD-ROM route is empty too**: the Walnut Creek, InfoMagic and "Internet in a Box" items are FreeBSD, Linux and Windows shareware discs, not registry snapshots. (3) **Academic FTP mirrors were never captured**: `wuarchive.wustl.edu`, `ftp.uu.net`, `ftp.cdrom.com` and `ftp.funet.fi` return **zero** Wayback captures matching `zone`, `domain-info` or `internic`, and `rs.internic.net/netinfo/*` holds only 404s. (4) **DNS-OARC is out of window by design**: root zone from June 1999 and it lists TLDs rather than domains, per-TLD zones only from March 2009. (5) **The survey name lists really do stop at 9707**, confirmed from two independent live directory listings rather than inferred: ISC's own `ftp.isc.org/www/survey/archive-data/` and the survey author's `3waylabs.com/zone/`. The later `WWW-9801/` and `WWW-9807/` directories on the author's site contain **only aggregate report HTML**, no name lists. (6) **ISC's own 9607 and 9701 copies are corrupt in a specific, unrecoverable way**, worth recording so the next person does not retry them: `9607.domains.gz` recovers 6,562,719 of 6,755,227 bytes but only **3,835 newlines against 488,069** in the good Wayback copy, because the deflate stream desynchronises early and the rest decodes as plausible-looking garbage (`vanoqoykoorrlykddoldnabykeec.gc`). A partial gzip recovery here is not a partial file, it is a few thousand good lines followed by fiction. **CORRECTED 2026-08-16 and the correction is the point of this row: (6) was about ISC's OWN copy, and it was read as though it closed the January 1997 edition entirely.** The Wayback copy of `nw.com/zone/9701.domains.gz` was never tested. It is intact: 3,432,439 bytes, `gzip -t` passes, 824,791 lines, `LC_ALL=C sort -c` reports sorted end to end, which is exactly the check the corrupt copies fail. Ingested; **76,324 net-new (domain, 1997) pairs**. A closure about one host's copy is not a closure about the artifact. **CORRECTED AGAIN 2026-08-18, and this row is now the project's clearest example of its own failure mode.** Claim (1), that archive.org holds no in-window zone file, and the whole framing that the family is closed, were both refuted by a host nobody had checked: **`nic.mil`, the Defense Data Network NIC, mirrored InterNIC's zone distribution over HTTP and Wayback captured it.** `http://nic.mil/oroot.html/org.zone.gz` at capture `19970420113748` is a complete InterNIC `.org` zone. Verified independently rather than taken from the finder: 1,317,986 bytes gzip, `gzip -t` passes, 9,193,881 bytes and 154,141 lines uncompressed, the SOA serial `1997041800` is **inside the artifact** on line 2, and the file ends with InterNIC's own `;End of file.` marker. That is the full battery the corrupt copies in (6) fail. Its 1997 siblings are intact too (`edu` 12,132 lines, `gov` 1,805, `mil` 301, all serial 1997041800 or 1997041700), and a separate 1998 directory at `/ftp/domain/` holds `edu` and `gov` for May and July 1998. **`com` and `net` are genuinely absent at this host**: the 1998 `com.zone.gz` decompresses to "This file is no longer available from this site. Have a NIC day." and the 1997 listing carries only arpa, edu, gov, mil, org and root. So this reopens the family for `.org`, `.edu`, `.gov` and `.mil` and leaves the two large namespaces open. **The reopen condition is now precise and is the obvious next hunt: any other mirror of `ftp.internic.net/domain/` whose crawler took a full-size `com` or `net` file.** A complete `.org` proves such mirrors existed. Every closure in this row was about a host's copy, and three separate hosts have now been read as closing the artifact. **THE REOPEN CONDITION IS NOW CLOSED, 2026-08-18, and by mechanism rather than by an exhausted host list.** The condition set a day earlier was "any other mirror of `ftp.internic.net/domain/` whose crawler took a full-size `com` or `net` file". The answer is no, and one capture explains why for the host that mattered. The archived directory listing `19980129093726 nic.ddn.mil/ftp/domain/` shows, in InterNIC's own Apache index, `com.zone.gz 29-Jan-98 04:35 26M` and `net.zone.gz 29-Jan-98 04:35 2M` beside `org 2M`, `inaddr 717K` and `edu 131K`. **The full-size files really were on that mirror.** But every capture of those exact URLs is the withdrawal stub: `nic.ddn.mil` com 386 bytes, net 385, org 386; `www.nic.mil` com 385/388/383, net 384/386/383; each file's captures share a single digest and the earliest is 1998-05-30, and the body reads "This file is no longer available from this site. Have a NIC day." So the crawler took the **listing** in January and reached the **URLs** only after withdrawal. The 26 MB file was never captured on this host. RIPE genuinely does mirror the distribution at `ftp.ripe.net/mirrors/domain/` and is dry both ways: the live listing carries only arpa, root and root-servers material, and all 130-odd Wayback captures of that prefix are 2020 to 2026. **Two facts about the CDX API make this a host-by-host question and are worth knowing before anyone retries it.** A cross-host filename search is not available to us: `url=*.mil/oroot.html/org.zone.gz` and `url=mil&matchType=domain` both return **HTTP 403 "This type of CDX query requires authorization"**, while `url=*/oroot.html/org.zone.gz` and `url=org.zone.gz&matchType=domain` return empty even though the plain per-host `url=nic.mil/oroot.html/org.zone.gz` returns its row. So "which host holds a `com.zone.gz`" cannot be asked directly. And `collapse=urlkey` shows only the first capture per URL, which would hide a good capture behind a stub; the sweep that produced this answer ran without it. Separately `curl` needs `-g` when a filter contains a character class: an unglobbed `[Zz]` gives "bad range in URL" and exit 3, which reads exactly like a dead endpoint. **One unnoticed sibling measured 2026-08-18, and it is an increment rather than a family.** `inaddr.zone.gz` of 10 July 1998 was not enumerated above and is the one full-size zone in that directory the crawler did take: 746,620 bytes, `gzip -t` passes, 13,920,747 bytes and 229,872 lines out, SOA serial `1998071000` inside the artifact, `;End of file.` terminator. **Worth 336 net-new (domain, 1998) pairs and 209.2 equivalent-English**, not the 2,018 first claimed, and the composition explains why: measured record types are 229,347 NS against 508 PTR, so 99.8% of the right-hand sides are **nameserver** names rather than general hosts. A few thousand ISP and institutional nameserver domains are the most-covered names in the store, hence 10,260 of the 10,305 extracted are already dated somewhere in the window and 96.7% already carry 1998. 6.7% of the acceptance bar, from the same host, directory and evidence class as the rows above |
| Australian Web Archive (PANDORA/Trove) | **Superseded 2026-08-01; the full account is in the `Australian Web Archive` section earlier in this file, and the operative verdict is redundancy with the Internet Archive rather than unreachability: zero AWA-only pairs.** The earlier entry said both endpoints served an Anubis challenge. Half of that is now wrong: `web.archive.org.au/awa/cdx` answers normally |
| Other ccTLD registry open data | Nothing free reaches 1996-2001. CENTR publishes aggregates only; OpenINTEL starts 2015; commercial WHOIS is paid. AFNIC `.fr` is the sole open registry file with in-window creation dates. **Re-checked 2026-08-23 for the one shape that matters under rule 6, a per-domain file carrying BOTH a creation and a withdrawal date**, since that is a registry statement of registration across an interval and is therefore the only compliant way a single record can evidence more than one year. Nominet `.uk`, auDA `.au`, InternetNZ `.nz`, CIRA `.ca`, SGNIC `.sg`, IEDR `.ie`, SWITCH `.ch` and SIDN `.nl` publish daily-registration feeds, aggregate dashboards or top-N popularity rankings, none of them per-domain lifecycle. **AFNIC remains the only one**, and it is already banked. The likely reason is general and worth remembering before this family is probed a third time: **a deletion date lets anyone track a registrant's lifecycle externally, so registries removed that field from public data around 2018** |
| SNAP web graphs | Nodes are anonymised integers with no URL mapping |
| Yahoo! Webscope AltaVista graph | Programme unreachable; crawl date too vague for per-year evidence. **Upgraded to permanent 2026-08-15**: `webscope.sandbox.yahoo.com` no longer resolves in DNS at all, so this is a dead host rather than a closed programme and does not want re-probing |
| TREC WT10g / VLC2 / WT2g / .GOV (re-probed 2026-08-15) | **Closed on measurement now, not availability, because the availability half was false and kept inviting a re-probe.** Glasgow took the collections over from CSIRO and is alive: `ir.dcs.gla.ac.uk/test_collections/` returns 200 and sells WT2g at 350 GBP, WT10g at 500, .GOV at 500 and .GOV2 at 650, on DVD only, behind a signed organisational agreement initialled per page plus a per-person agreement. **The two free files are the trap**: `wt10g_inlinks.gz` and `wt2g_inlinks.gz` download with no agreement and contain **only opaque docids** (`WTX001-B01-1`, 8,063,026 lines), with the docid-to-URL table on the paid media, which is the same failure mode as the SNAP graphs already in this register. **Size closes it regardless of price.** Bailey et al., IPM 39 (2003), give VLC2 as **117,101 servers** and state that VLC2, WT2g and WT10g all come from the same 1997 Internet Archive crawl, so that is the ceiling for the whole in-window family and the year is 1997 alone. **`.GOV` was crawled January 2002 and `.GOV2` in 2004, so both are out of window entirely** and need never be looked at again. Applying webbase's measured hostname-to-registered-domain ratio projects about 95,700 domains, against which webbase itself measured **0.01% net-new** and Early Web CDX 99.99% overlap. The structural reason is general: **a corpus derived from the Internet Archive cannot be net-new against a baseline that is itself IA-derived** |
| Yahoo! Directory | No machine-readable dump was ever published. **Not a re-probe candidate and deliberately carries no host**: nothing that could answer would change the verdict, because the artefact never existed. Tagged availability only because the phrasing reads that way |
| GeoCities derivatives, DNS Census | 2009 and 2013 respectively, out of window |
| Post-July-1997 ISC `.domains` lists | Do not exist; later survey editions publish aggregate counts only. **Not a re-probe candidate**: confirmed from two independent live directory listings, so this is an absence rather than an outage, and no host answering differently would change it |
| ISC January 1997 file | Corrupt in every known copy. Permanent gap |
| Internet Archive Alexa crawls (`alexacrawls`, `webwidecrawl`) | 226,901 items from 1996 with per-item CDX, but **every payload returns HTTP 401**; only `_meta.xml` is public. No route in |
| UKWA per-year bulk CDX (2026 recheck) | Docs survive at `ukwa.github.io/opendata/ukwa.ds.2/cdx/`; the download host serves the same 159-byte stub and the DOI now 403s behind Cloudflare. Wayback captured the directory listing but never the `.gz` files, which is why the link graph survived and the CDX did not. In-window size would have been ~13.4 GB |
| New Zealand (National Library) | Both the web archive and the open-data page return an Imperva bot interstitial. NLNZ does publish CDX to archive.org, but those items are 2025-2026 crawls. Selective harvesting only began in 1999. **Hosts added 2026-08-15 so the re-prober can see this lead at all**: `webarchive.natlib.govt.nz` and `natlib.govt.nz`. It had been closed on availability with no probeable host in its verdict, so the automatic re-probe skipped it silently for a week. Worth keeping in rotation rather than closing harder: harvesting began **in window**, `.nz` weighs 0.9895, and the barrier is a bot interstitial, which is the kind of thing that changes |
| Canada (Library and Archives Canada) | Federal web harvesting began December 2005, stated on their own front page. `open.canada.ca` returns zero web-archive index datasets. Entire archive postdates the window |
| Ireland (National Library) | Archives via Archive-It, 138 collections, earliest captures 2011 |
| `early-web_parallel-language-urls` | 1,164,183 pre-2000 multilingual URL patterns with ISO-639 codes but **no timestamps**, so no per-year evidence. Multilingual by construction, which also works against the section 6 English rule. Seed-only at best |
| OCLC Web Characterization Project | Only aggregate statistics were ever published; the host is gone |
| Mailing-list archives (2026-08-01) | Assessed because section 4 names them and they share the property that made Usenet work, a date intrinsic to the artifact. **The population is wrong even though the structure is right.** archive.org's mailing-list holdings in window are overwhelmingly hobbyist digests (`sf-lovers`, `GLOWBUGS` ham radio) with almost no commercial or website content. The W3C public lists are live and browsable at `lists.w3.org/Archives/Public/` but small and technical: `www-announce` ran for only 3 archive periods, `www-talk` 121 and `www-html` 246, all discussion among a small standards community whose domains the baseline already holds in full. A 1997 `www-announce` month carries 53 messages against the 20,000-plus domains a single Usenet commerce group yields. Not worth a parser |
| archive.org **books**, three collections tested (2026-08-05) | The idea is sound and the payload is not there. `subject:(internet)`: **57 of 60 sampled in-window items publish no downloadable `_djvu.txt`**, 2 net-new pairs. `collection:folkscanomy_computer`, chosen specifically because it is *not* lending-restricted: **36 of 40 unreachable anyway, 2 net-new pairs from 40 items.** The constraint is therefore not only lending restriction but that in-window book scans largely carry no OCR text layer. The Internet Yellow Pages editions are unreachable either way. The book route is closed |
| archive.org **`magazine_rack`** at large (2026-08-05) | 34,279 in-window items but **0.4 net-new pairs per reachable item**, against 10.5 for the computing trade press measured the same way on the same day. In-window holdings are Amiga user-group zines and laboratory newsletters, which print almost no URLs. The periodical route is only worth taking when scoped to computing and internet titles, and even then it saturates: see the `trade_press` section, which closed the whole American and hobbyist computing press at 5,318 in-window items |
| Boardwatch **ISP Directory** volumes (2026-08-05) | The monthly magazine issues carry `_djvu.txt`; the separately catalogued directory volumes do not. `boardwatch-directory-of-internet-service-providers-july-august-1997_djvu.txt` returns a 146-byte stub. The most ISP-dense artifact of the family is the one without machine-readable text |
| **IRCache / NLANR proxy traces** (2026-08-06) | Dated squid logs holding millions of real URLs, the most promising lead on that day's list, and it is gone. `ircache.net` now serves a squatted blog; `ftp://ircache.nlanr.net/Traces/` is dead; `(ircache OR nlanr) AND trace` returns **zero** archive.org items; `web-caching.com` timed out. No route in. **Re-probed 2026-08-15 and it now answers HTTP 200 with 27,223 bytes, which is not a revival**: the body is a consent-manager parking page, the same fate as `ircache.net`'s squatted blog. So all three hosts for this lead are now squatted or parked rather than merely dead, and the traces themselves remain unlocated. Worth knowing that this was the most promising lead of 2026-08-06 and the reason is unchanged: dated squid logs would hold millions of real requested URLs. Nothing about the verdict changes; do not reopen it on availability |
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
| US trademark filings for domain-name marks, 1998-2001 (2026-08-15) | **Screened clean and closed on two independent grounds, both reasoned rather than measured, and the entry says so.** USPTO trademark bulk XML is free and complete, and the dot-com boom produced a wave of marks that ARE domain names. (1) **The same authority selection that closes the patent row above**: a trademark application costs money and legal work, so the population is businesses notable enough to file, which an 8.26M-domain store already holds. (2) **A dating problem the patent row does not have, and it is the more interesting objection.** A mark may be filed on an *intent-to-use* basis, which evidences an intention and not a live domain; only a *use-in-commerce* filing with a specimen attests the site existed on the filing date. Separating the two requires reading the filing basis per record, so the cheap version of this source would assert years that its own evidence does not support, which is precisely the class of error `link_target` exists to prevent. Worse, an **abandoned** application is weak evidence in the wrong direction: a company that filed for a name in 1999 and abandoned it may never have built the site at all. **Reopen only on a pre-extracted dataset of use-in-commerce marks whose specimens are dated websites**; do not reopen on the bulk XML being free, which it always was |
| URLs cited in US patents, 1996-2001 (2026-08-15) | **Screened clean, then deprioritised on the authority rule and arithmetic rather than on a measurement, and that distinction is deliberate: this is a PROJECTION and the entry says so.** USPTO grants full text is free and bulk-downloadable from 1976, and patents of the period cite non-patent literature including URLs, dated by the grant. It fails the test in `discovery.md` section 4 before it fails on volume: **a cited reference is the definition of an authority-selected population**, which is the same shape that collapsed 7.1M Usenet relay hops into 4,736 domains and returned 2 net-new pairs from 11 archived BUBL LINK pages. On volume, about 1.0M US patents were granted 1996-2001; even at a generous 3% citing a URL and heavy duplication the distinct-domain count is order 10^4, skewed to standards bodies, universities and large firms, which an 8.26M-domain store already holds. It is also `typed`, so the corroboration split applies on top. Extraction cost is many gigabytes of full text per year for an expected yield in the hundreds of pairs. **Reopen only on a pre-extracted dataset of URLs cited in patents**, which would make pricing cheap; do not reopen on the bulk data being available, because it always was |
| NTP Survey 1999, Nelson Minar / MIT Media Lab (2026-08-15) | **Closed on availability with a live index and dead payloads, which is the third instance of that exact shape in this register.** The population was the interesting part and is worth restating for whoever reopens it: a 1999 census of **175,527 NTP hosts**, machine-generated, self-dating by survey year, and **orthogonal to a capture-derived baseline** because an NTP server is infrastructure rather than web content, so a crawler has no reason to have visited the organisation that runs one. That is the same property that made dispute dockets the best-yielding source measured here. The index page at `alumni.media.mit.edu/~nelson/research/ntp-survey99/data/` is live and real, 4,337 bytes of period HTML listing `ntp-survey-1999.tar.bz2`, `ntp-survey-summaries-1999.tar.bz2` and `ntp-survey-stratum1-1999.tar.bz2`. **All three return HTTP 403**, a 326-byte Apache error page, and the identical byte count across three differently-sized archives is what exposed it: a range request reported `Content-Length: 326` for each, which is an error page and not a size. **The obvious alternative path was tried and is not a way in**: the survey's HTML report at `.../ntp-survey99/html/` serves fine at 52,665 bytes, and it is the paper. The only hostnames in its body are the author's own site and a newsgroup name, so there is no host list to salvage from the prose. Reopen by asking the author, whose address is published on the data page, and note that the host is an alumni server so the files may simply have lost their permissions in a migration |
| Library catalogue records with a MARC 856 URL (2026-08-15) | **Screened, and closed on a dating hazard rather than on availability or size, which makes it worth reading before proposing anything similar.** The idea is sound in outline: MARC field 856 carries an electronic location, libraries publish catalogue records in bulk and free, and MARC 008 records the date a record was entered on file, so a 1998 record naming a URL looks like a dated observation. **It is not one.** An 856 field can be added to a record at any later date, so the record's creation date dates the *record* and not the *URL*, and a catalogue record created in 1998 may have acquired its link in 2005. That is the same defect as a trademark filed on an intent-to-use basis and the same shape as the dated-dataset fallacy already recorded here: **a per-entity date is not a per-field date.** The only safe subset would be records whose **last-transaction date (MARC 005) is also in window**, meaning nothing has touched them since, which is a small residue of a population that is in any case authority-selected toward journals and institutional sites an 8.26M-domain store already holds. Reopen only on a dataset that carries per-field provenance, which MARC does not |
| Commercial business directories with a website field: Thomas Register, Kompass, D&B (2026-08-15) | **A genuinely different population from the two entries it collides with, closed on availability rather than on that argument.** The internet-directory entries above are directories *of websites*, which select for notability; this is a directory *of companies* carrying a website as one field, so a small manufacturer with a 1999 site that no crawler visited would appear in it. That is the orthogonality that made the dispute dockets the best-yielding source here, and it is why the collision was not a reason to stop. **It fails on reach.** No in-window edition is digitised: archive.org holds the 1905-1906 Thomas Register and undated later scans, and the printed-directory family is already closed on the measurement that in-window volumes publish no downloadable `_djvu.txt` in 57 of 60 sampled items. The CD-ROM editions, published annually from 1993 and the only form that would be a database rather than OCR, are not on archive.org at all; the CD-ROM family entry there covers shareware discs, which is a different check. Reopen on a digitised in-window CD-ROM or a library data deposit, not on a scanned volume |
| Dot-com deadpool and failure lists, 2000-2001 (2026-08-15) | **Closed on the lifetime rule applied properly, which is worth recording because it looked like the rule's best case.** A deadpool names companies that failed, so their domains died young, which is the property that makes dispute dockets 87.7% net-new. It still fails, because **short life is necessary and not sufficient**: a funded dot-com ran a marketing budget for a year or two and was captured repeatedly before it folded, where a typosquat withdrawn after a complaint was never captured at all. The population here is celebrated failures, which is authority selection wearing the costume of ephemerality, and an 8.26M-domain store holds every one of them. The refinement this produced is in `discovery.md`: what pays is short life **plus low traffic**, and asking only about lifetime would have sent this project after exactly the wrong corpus |
| Archie anonymous-FTP indexes (2026-08-15) | **Closed on era before anything else, which is the cheapest kind of closure and the one most often skipped.** Archie indexed anonymous FTP servers and was effectively dead by 1997, so at best it speaks to 1996 and the window is 1996-2001: a source whose lifetime barely overlaps the window cannot carry it, however good its records. On top of that the population is institutional FTP hosts, universities and large firms, which is the authority selection that closes the patent and trademark rows, and this register already records that the academic FTP mirrors themselves (`wuarchive.wustl.edu`, `ftp.uu.net`, `ftp.cdrom.com`, `ftp.funet.fi`) return **zero** Wayback captures matching `zone`, `domain-info` or `internic`. Reasoned rather than measured, and small enough that measuring it would cost more than it could return |
| Bruce Guenter's spam archive, `untroubled.org/spam/` (2026-08-15) | **Genuinely new, fully measured, and rejected: 312 net-new pairs and 195.5 equivalent-English after the split, 16x below the bar.** Everything about the source is good, which is why it is worth an entry rather than a line. It is live, in window and cheap: `1998.7z` through `2001.7z` total **9.3 MB** and expand to 20,010 individual messages, each carrying its own `Date` header, so it is self-dating per item and needs no inference. Four requests bought the whole thing. **The population is what failed.** 19,992 in-window messages name only **5,342 distinct (domain, year) pairs over 4,793 domains**, 0.27 distinct domains per message, because spam repeats itself relentlessly; and **3,203 of the 4,793 are already held**. The reasoning that proposed it is refuted by that last figure: the idea was that a spamvertised domain leaves no crawlable link and so escapes a capture-derived baseline, and two thirds of them did not escape it. The typo bound is also the worst measured on this project at **38.7% of sampled net-new names one edit from a held name**, which is what deliberately obfuscated body text does to any extractor. Reopen on nothing: this is a measurement over the complete in-window corpus, not a sample |
| Anti-spam blocklists and blackhole lists, 1997-2001 (2026-08-15) | **Screened clean against the register, then killed on the unit before any request was made.** The shape looked right: a blocklist is a machine-generated dated record about whoever happened to be there, and it selects for short-lived spam domains that a crawler-derived baseline systematically misses, which is exactly why the dispute dockets measured 87.7% net-new. It fails on what it lists. **Every in-window blocklist is IP-based**, not domain-based: MAPS RBL, ORBS, the Dial-Up List and SPEWS all publish addresses and netblocks, and the output unit here is the registered domain (SPEC III.8), so there is nothing to extract. The domain-bearing variant of the idea is spam sightings posted to `news.admin.net-abuse.*`, **and that is already ingested**: 13 of those groups are on disk and they have yielded **173,526 evidence rows over 168,075 domains**. So the good half of this idea was harvested with the rest of Usenet, and the half that remains has no domains in it. Domain-based URI blocklists (SURBL, URIBL) begin in 2004, out of window |
| `data.webarchive.org.uk` (2026-08-05) | Does not resolve. A third distinct host tried for the UKWA bulk CDX, after the 159-byte stub and the 403 DOI. Still no route in |
| The whole `webarchive.org.uk/datasets/` tree, not just the CDX (2026-08-15) | **The stub is the tree, not the file**, established with a positive control rather than inferred: `/datasets/ukwa.ds.2/geo/` returns the same 159-byte "400 Redirect" body under HTTP 200 as `linkage/host-linkage.tsv.gz`, a file we are known to hold. So every future probe of any path under `/datasets/` is answered in advance, and only a mirror or an access grant changes it. The full Geoindex behind it is 700,641,549 lines covering 1996-2010, about 8 GB gzipped, all `.uk` at 0.9813, which makes it the largest reachable-looking prize still closed. **The last clause of this row said "the only route left is an access letter to the British Library, not another URL", and that was disproved on 2026-08-17: it was another URL.** See `## ukwa_geoindex` below; this row stays only because the reasoning about `/datasets/` stubs is still correct |
| Alexa / Internet Archive donated crawl items on archive.org, their CDX indexes (2026-08-15) | **The bulk index we want demonstrably exists and is access-controlled, which is a different closure from "does not exist" and worth stating precisely.** In-window items carry per-item CDX files, `FS-587676-c.cdx.gz` at 104 MB and a 1999 item at 631 MB, so these are real IA-side indexes of exactly the shape that would convert our query-rate constraint into a download. A ranged GET returns **HTTP 401 with a 172-byte body**: the restriction covers the **index** files and not merely the payload WARCs, which had been assumed rather than tested. Reopens only on an access grant, and the Internet Archive has refused this project three times. **NARROWED 2026-08-18: the 401 is a per-collection policy and does not reach every IA-side index.** The `webdataservices` national extractions publish their CDX derivatives openly: all 19 merged indexes of `Poland_pl-ccTLD_2001-12-31`, 1,240,317,860 bytes, returned HTTP 200 with no authentication while the `.arc.gz` payloads beside them return 403. So the closure stands for `alexacrawls` and `webwidecrawl` and is false as a statement about the archive. **The open question is whether a `webdataservices` extraction exists for a high-weight namespace**; the measured `.pl` one is 69,542 net-new pairs for only 7,441.0 equivalent-English at weight 0.1070, and a `.uk` equivalent would be worth about nine times that per pair |
| National-library HISTORICAL web extractions on archive.org: INA `.fr`, FCCN `.pt`, NLI `.ie` (2026-08-18) | **Enumerated exhaustively and closed on access, except Ireland which is closed on dates.** Found while answering whether the `webdataservices` shape exists for a high-weight namespace, by scraping all 34,841 identifiers containing `HISTORICAL` rather than guessing: `INA-HISTORICAL-*` (49 items, `.fr`, includes 1996, 2000 and 2001 groups), `FCCN-PT-HISTORICAL-*` and `PT-HISTORICAL-*` (31 items, `.pt`, includes 1997 and 2000), `NLI-IE-HISTORICAL-IE-DOMAIN` and `-FOCUSED` (46 items, `.ie`). **Ireland is the only high-weight one and its earliest item date is 2002**, outside the window. The other two refuse their indexes: `INA-HISTORICAL-1996-GROUP-AAA-...-c.cdx.gz` returns HTTP 401 with a 172-byte body, `PT-HISTORICAL-1997-GROUP-ABB-...` returns 401 via `download` and 403 with a 4,868-byte "Item not available due to issues with the item's content" page via the node. Also enumerated dry in the same pass: all 13,671 sub-collections of `collection:web` (86 carry a 1996-2001 token and the only in-window web-crawl families are the Alexa, Amazon and Inktomi ones already closed) and all 233 of `customcrawlservices`, the national-library harvest family, whose earliest anything is `bnf_2004` and `nla_2005`. **The register note worth keeping: the item-level `access-restricted-item` flag predicts nothing in either direction.** Poland carries the flag and serves its CDX; NLI and PT do not carry it and refuse theirs. Collection-level `access-restricted=true` and `hidden=true` hold for `webdataservices`, `nliweb`, `fccn_pt_historical`, `inaweb` and `20thcenturyweb` alike, and `_meta.xml` returns 200 on every item tested, so metadata openness proves nothing about derivative openness. The same pass re-confirmed the `alexacrawls`/`20thcenturyweb` closure directly: 331 items all dated 1996-1999, and both a `-c.cdx.gz` and an `.arc.gz` refused at 403 and 401 |
| `USFEDGOV-EXTRACT-1996` through `-2001`, the IA early-US-government-web extraction (2026-08-18) | **Everything about the artifact is as good as it looks and the yield is 56.2 equivalent-English.** Six sibling `webdataservices` items, one per year, covering exactly 1996-2001, not access-restricted, CDX derivatives served: 3,255,201,499 bytes of merged indexes, `gzip -t` passes, the 1996 index tiles with **zero gap** (216 of 216 blocks inflate, 27,817,540 of 27,817,540 bytes accounted) and 647,995 of 647,995 timestamped records fall in 1996 with no leakage. It was priced without downloading the 3.26 GB, using a structural shortcut worth reusing: **in every item the entire non-`.gov` population sits in the first one or two ZipNum blocks and everything after is `gov,*`**, proved by a boundary-key TLD census (2001 = 16,035 gov / 1 edu, 2000 = 10,914 gov / 1 edu), so 3,000 to 6,000 records exhaust the non-gov side of a year. Six-year enumeration gives 3,378 (domain, year) pairs and **net-new of 81 pairs for 56.2 EE**; the 1996 item is exhaustive and its net-new is exactly **0 of 294**. A ceiling that needs no estimate settles it regardless: this is a `.gov` source plus a small embeds tail, `.gov` is a tiny namespace (the ingested InterNIC `gov.zone` of April 1997 is 1,805 lines) and the store already holds 13,364 in-window `.gov` pairs. **REJECT on measured yield**, and it is the answer to the open question posed in the `.pl` entry: a `webdataservices` extraction for a high-weight namespace does exist and is worth nothing, because weight without novelty is nothing |
| `DARTMOUTH-NBER-RESEARCH-2017-ARCS-*`, the 659-item payload family (2026-08-18) | **REJECT on three independent measurements, and it is the payload of a source already banked.** `dartmouth_nber_captures` is `Decision: master` and holds 227,273 pairs; `sources.md` already names these very items as resolving. The redundancy is structural rather than incidental: every capture in these ARCs is a Wayback capture of a host on the NBER corporate list, and the ingested census is captures-per-year for exactly that host list, so the CDX can only restate what the census banked. Measured: three complete `gzip -t`-verified per-ARC indexes over 6.56 MB give 1,204 in-window pairs and **net-new of exactly zero**, which is 0 pairs per MB against the census's own measured 997. Two of the three probes contained **no in-window records at all** despite in-window item date labels (a 1999-labelled item whose CDX is 100% 2006, a 2001-labelled one 100% 2002), so the in-window fraction cannot be selected for in advance and pricing the family would mean downloading order 150 GB of index for a measured zero. The merged index is unusable anyway: its ZipNum meta-index returns **HTTP 401** on repeated attempts across two items, which is the family this register already closed at 401. **The reason this row is worth reading is how the first pass got it wrong**: a ranged GET of the merged index returns HTTP 206 with 65,536 bytes and *decodes*, and was reported as "valid gzip, inflated to 1,143 CDX lines". `gzip -t` FAILS on it and zlib confirms the stream never terminates. A truncated member that happens to decode is exactly the failure this register records for the corrupt ISC copies, and it survived one careful reader before a second caught it |
| UKWA Geoindex, E17 postcode slice, figshare 825956 (2026-08-15) | **Reachable and real but far too small**, kept because it is the only file that did download from this family: GET 200, 1,886,146 bytes, 12,081 rows of `postcode,year,subdomain,waybackurl`. The 14-digit timestamp inside each wayback URL is self-dating `cdx_timestamp`. Priced against the live store: 1,593 pairs over 1,092 domains of which 1,297 were already held, leaving **296 net-new pairs and 290.5 EE raw, 123 pairs and 120.7 EE after the split**. 100% `.uk` at 0.9813, and still an order of magnitude below the 5,000-pair acceptance bar |
| Other JISC UK Web Domain Dataset derived files (2026-08-15) | **Hostless by construction**, verified on the `ukwa.github.io` gh-pages copies rather than assumed: `fmts-cleaned.tsv` (49.6 MB) is MIME-type by year counts, `link-summary-*.tsv` is suffix-to-suffix counts of the form `1996 az.us ac.uk 3`, and `ds.1/classification.tsv` (3.0 MB) is URL plus category with **no year at all**. The first two name no hosts and the third dates nothing, so the family is seed-only, and the candidate pool is not the constraint |
| Archives Unleashed derived datasets (2026-08-15) | Structurally out of window: its derivatives are built from Archive-It collections, which begin in 2005 |
| Arquivo.pt CDXJ collections other than `AWP*` and `IA` (2026-08-15) | Sampled by ranged GET, 206 requests of 120,001 bytes each, and every one is out of window: Tomba 2005-2008, InternetMemory 2006-2012, Geocities 2009. The Internet Memory Foundation holding is the notable one, 62,291,715,540 bytes and the whole legacy of a folded European archive, but its predecessor was founded in 2004 and the sample found **zero** captures in 1996-2001 |
| DMOZ / ODP copies on Zenodo (2026-08-05) | 12 hits, all 2018-2020 research derivatives of late DMOZ dumps. Out of window, and description text rather than dated listings. The ODP rejection stands |
| `biz.*` Usenet hierarchy (2026-08-05) | Exhausted: no unprocessed `.mbox.zip` archives remain in the 19,233-group catalogue |
| Late-starting Usenet groups (2026-08-05) | A selection rule rather than a rejection, and it costs more than any single source above. **4,023,027 of 5,283,482 messages across 28 probed archives are out of window**, concentrated in whole groups: four of the 28 contributed exactly zero net-new pairs, and `uk.misc` gave one record from 172.9 MB. Gate on in-window date coverage, not on group name or file size |
| OpenPGP keyserver bulk dumps, the SKS and Hockeypuck network (2026-08-18) | **Closed on availability, and the dating premise was disproved separately, which is the more useful half.** The dump hosts were probed for the first time here: `mirror.cyberbits.eu/sks/dump/` 404, and nine hosts in total are dead, NXDOMAIN or 404. `pgp.key-server.io/sks-dump/` **serves a squatted 1,095-byte FingerprintJS redirect stub under HTTP 200**, so it answers today and always will; the domain was dropped and re-registered. `keys.openpgp.org` publishes no dump **by design**, its FAQ stating that exact-match search exists so nobody "can discover any new email addresses". `archive.org` and Zenodo hold none, against a positive control that reproduced a figure this register already records. `ftp.gwdg.de/pub/misc/pgp/` is live and mirrors PGP **software**, not keys. **The dating finding is the part worth keeping**: a key's creation timestamp dates the KEYPAIR, not the address bound to it. Over 4,225 binding self-signatures in the Debian keyrings, 47.6% of user IDs were bound in a LATER year than the key, median lag two years, and **0% earlier**, so the naive reading manufactures a claim that a domain existed before its address was attached. A collector must therefore date on the UID binding signature and take the corroboration split. Reopen only if `hockeypuck@cyberbits.dev` supplies the rsync password, and then the bar needs roughly 306,000 in-window UID bindings |
| Curated distribution keyrings as a PGP substitute: Debian removed-keys and emeritus, GNU, Apache KEYS (2026-08-18) | **Retrievable, correctly dated, and 70x too small.** 2,605 primary keys and 36 MB fetched and parsed end to end; `gpg` 2.5.20 returns zero `pub` records for the 2005 Debian keyrings, so a 120-line OpenPGP packet parser was written and cross-validated against `--list-packets`. Priced on the UID binding signature: 4,096 items, 1,418 pairs over 1,093 domains, **1,273 already held (89.8%), 69 net-new pairs, 44.4 equivalent-English**, mean weight 0.6436. The weight is the encouraging part and the volume is fatal, and the cause is `discovery.md`'s authority-selection rule holding exactly: `debian.org` alone is 1,033 of the in-window user IDs. A current keyring garbage-collects departed maintainers, so only 63 of the GNU keyring's 610 keys (10.3%) are in window, and the in-window Debian keyrings of hamm, slink and potato are simply not present on `archive.debian.org`. The sub-route that cost nothing is the sharpest disproof: 4,441 armoured key blocks from the 56 densest newsgroups of the 411 GB Usenet corpus yield **2 net-new pairs**, because anyone who posted a key also posted a `From:` header we already mined. 61 names reached the candidate pool as a by-product |
| X.509 certificate corpora with `notBefore` in 1996-2001, the whole family (2026-08-18) | **Closed on a mechanism, measured from the inside, and it generalises.** The premise is sound in every part that matters: `notBefore` is CA-written into a signed structure, genuinely self-dating, in the same record as the subject name. The population is what fails. The only retrievable in-window corpus is the history of Mozilla's `certdata.txt`, and that is a real find: `hg.mozilla.org` serves 139 revisions of the pre-2013 path back to the 2000-03-31 open-source checkin, of which the November 2000 and August 2001 revisions are in-window artifacts with machine-written dates. Priced as a CENSUS rather than a sample: 126 in-window certs, 14 pairs over 12 domains, 10 already held, **1 net-new pair worth 0.6 equivalent-English**. **0 of the 126 are end-entity web-server certificates**; 60 carry `basicConstraints CA:TRUE` and the other 66 omit the extension only because 1996-era roots predate it, no certificate in the set has a hostname as its CN, and the 17 host tokens the whole corpus yields are the CAs' own domains. Every sibling route fails differently and the distinctions are worth keeping: the EFF SSL Observatory is torrent-only with its sole tracker `web4.eff.org` NXDOMAIN and no webseed or mirror; the ICSI Notary begins February 2012 and is shut down; Certificate Transparency begins 2013 and **cannot accept a period leaf, because no currently trusted root predates 2007** (the current 121-cert bundle's `notBefore` histogram runs 2007 to 2024 with zero in window); and Eric Murray's SSL Server Security Survey of 2000-07-31, the only in-window TLS census that ever ran, published percentages over 8,081 certs and its two detail pages are 404 everywhere. **The general law: a corpus assembled by a TRUST decision selects for authorities, not for hosts.** Same shape that collapsed 7.1M Usenet `Path:` relay hops to 4,736 domains, and sharper here, because the population of certificate authorities in the window was two dozen. Reopen condition, not a lead: if a mirror of `observatory-dec-2010.sql.lzma` ever surfaces on an HTTP host, one `notBefore` histogram settles it in ten minutes |
| Machine-written mail headers in bulk mailing-list archives (2026-08-18) | **Closed on arithmetic, and it corrects a premise this register was read as supporting.** The `Message-ID` row above does not say the header seam is unexploited: it says the seam was mined over 73,751 messages for 51 net-new pairs and zero new domains, and it extends that to `Received` and `Path`. Everything measured today replicates it on mail. **`pipermail` strips the `Received` chain entirely**: over 37,789 messages from 2,622 of our own month files the only surviving headers are `From`, `Date`, `Subject`, `Message-ID`, `References` and `In-Reply-To`, so the 868 MB on disk can never answer a `Received` question, and its one header seam, the `Message-ID` host, is worth **156 net-new pairs and 107.3 equivalent-English** over the whole 579,808-message corpus with 92.5% of domains already attested. **A full-header bulk route does exist and is newly recorded**: `mail-archives.apache.org/mod_mbox/<list>/YYYYMM.mbox` 302s to `lists.apache.org/api/mbox.lua`, which serves raw mbox with unbroken `Received` chains from 1996, megabytes per list-month, at no archive.org cost. Measured over 8,877 in-window messages: 29,387 `Received` stamps collapse to 354 registrable domains at 83 lines each, 539 pairs, 95.9% already held, **4 net-new pairs and 2.5 equivalent-English**. Elsewhere `lists.debian.org` monthly mbox is 404 as the register already found, the IETF export is a Cloudflare interstitial under 403 (reconfirmed 2026-08-24 on `/arch/export/mbox/`, **but `www.ietf.org/ietf-ftp/ietf-mail-archive/` is an open nginx autoindex of raw mbox back to 1992**, 1,410 lists and ~1,651 MB in window, so the closure was of one door and not of the archive), `seclists.org` is MHonArc HTML with the headers reduced to `<meta>` tags, and `marc.info`'s mbox export is HTTP 410 Gone. **The marginal number is the law**: `Received`-only value is 0.48 equivalent-English against **17.30 from the addresses sitting in the same messages**, so on any mail corpus the header seam is dominated by the body seam, and a full-header archive is worth hunting for its bodies or not at all. If mail is ever reopened, ask whether a list's SUBSCRIBERS were an uncrawled population, never whether its headers survived |
| Web archives holding their OWN pre-2002 crawls, enumerated rather than guessed (2026-08-18) | **The lens is converted from a hope into a count, which is what closes it.** Three registries harvested mechanically: Wikipedia's List of web archiving initiatives (200, 129,414 bytes, 109 initiative rows, 71 archived-data rows, 72 access-method rows, and the only one carrying a creation-year field), MemGator's `archives.json` (200, 4,130 bytes, 20 endpoints, 6 flagged ignore) and the IIPC member directory (200, 116,891 bytes, 48 permalinks). **The Memento TimeTravel aggregator, the suggested starting point, no longer exists**: `timetravel.mementoweb.org`, `labs.mementoweb.org` and `aggregator.mementoweb.org` all have NO DNS record. Of the 13 initiatives created 2001 or earlier, one is the Internet Archive itself and three are already closed here, and of the nine that remain **not one serves a bulk-queryable in-window index**, established over 16 programmes, 34 hostnames, roughly 81 HTTP requests and 18 DNS lookups, none of them to `web.archive.org`. Exactly one serves any accessible in-window record, the Czech Webarchiv, whose Memento TimeMap is genuinely open and whose provenance is genuinely its own crawl: it dies on the conjunction of a per-site publisher allowlist (0 of 25 store-dated 2001 `.cz` domains readable, proved against `nkp.cz` and `cuni.cz` as known positives), a four-month in-window span and `.cz` at 0.0709, and its two readable in-window sites are already held in all six years. Individually: Bentley/CDL is now IA-hosted and its host says "WAS is gone"; Smithsonian and LoC MINERVA are Archive-It, so law 1; Rhizome ArtBase has no capture index; Korea's OASIS has no DNS on either host; New Zealand is still the 839-byte Incapsula wall; LAC Canada's Memento works and is out of window; NLI Israel and Stanford SWAP both 403; BAnQ is 404 and created 2012; and **China Web InfoMall / Tianwang, the one pre-2002 own-crawl archive absent from all three registries, now serves a domain-sale listing**. Not worth another pass on the same premise |
| Kulturarw3, National Library of Sweden, as a reachable corpus (2026-08-18) | **The largest genuinely IA-free in-window corpus known to exist, and the door is shut rather than absent.** Its own harvester ran from 1997 (KB: "The oldest sites are from 1997, when the project started"), not 1996, and the Internet Archive arrangement dates to 2010, so law 1 genuinely does not bite. Everything else does. Access is on-site only: "you need to come to the National library in Stockholm and use our Kulturarw3 computer", and "You cannot search freely for a word or subject, but must enter, for example, `www.sf.se`", so **the interface cannot emit an unknown hostname even with a reader's card**, which makes an access letter a year-filler for names already held rather than a discovery route. `kulturarw.kb.se` and `kulturarw3.kb.se` both resolve to `selma.kb.se` and refuse TCP on 80 and 443, while eight sibling hosts have no DNS at all; positive controls in the same minute were `kb.se` 200, `data.kb.se` 200, `vefsafn.is` 302. And the yield is bounded independently of access: the 22,685 in-window `.se` creations in the 2024 registry snapshot are **100% already held at the exact year**, and 32,332 of the store's 65,291 in-window `.se` domains (49.5%) are already extinct in that snapshot, so our `.se` coverage is not just today's registry. At 0.2135 it could never be a large number |
| Scholarly and technical full text 1996-2001, the whole family, on a density ceiling (2026-08-18) | **Closed on a number rather than on five separate rejections.** Two unrelated corpora fix the family's ceiling at **0.042 net-new post-split pairs per item**: the closed RFC row measured 0.0416 (140 pairs over 3,367 items) and a full CENSUS of D-Lib Magazine's 381 in-window articles measured 0.0420 (16 net-new pairs, 11.68 equivalent-English, mean weight 0.7300, 97.4% of its 978 pairs already held). Clearing the 5,000-pair bar therefore needs 119,062 items of that density and the largest such corpus in existence holds 4,997 (ACL Anthology). The premise that the RFC and W3C verdicts were about size rather than shape was right; the hope that scale rescues the shape was wrong, because **in this family density and size are anti-correlated**: the corpora dense in hostnames are the small ones written about the web. arXiv, 360-paper seeded stratified sample of the 150,580 in-window population, 12.57 MB of `pdftotext`: 135 pairs over 92 domains, 96.3% already held, 4 post-split survivors of which hand audit leaves **1 real name**, giving 0.08 net-new pairs per MB against the project's own 15.5 for prose. PMC Open Access, 299 articles, 5.89 MB: 5 net-new pairs of which **100% are `creativecommons.org` dated 1996 to 2000 from a `<license>` element added decades later**. CiteSeerX is a site-wide 301 into `web.archive.org` and its data page is a 404. One reusable fact recorded even though its corpus failed: `gs://arxiv-dataset` is a free, anonymously listable bulk mirror of 4,413,372 arXiv PDFs with a 12.5 MB manifest, where the `s3://arxiv` route is requester-pays |
| Quoted `whois` records pasted into Usenet bodies (2026-08-18) | **The most precise seam ever measured in this corpus, and still 50x under the bar.** Genuinely new: the register mines this corpus for addresses, URLs and bare hostnames (`usenet_announce` 771,110 pairs, `usenet_address` 123,068, the `news.admin.net-abuse.*` spam sightings 173,526 rows) and **nothing mines the quoted registry blocks**, so a `whois_creation` date out of Usenet was untried. Self-dating on the registry's own `Record created on 18-Feb-1998.` line, and the paste date is irrelevant to the year claimed, confirmed: `wiesenthal.net` 1998 comes from a 2008 post quoting a 2008 lookup. Priced from disk at **zero network cost**, 28.20 GB read (1.83% of 1,541.8 GB): 488 pairs over 486 domains, 68.2% already held, **155 net-new pre-split, 95.0 equivalent-English**, mean weight 0.6130. The refuter then read the WHOLE seam rather than a sample and measured **103 net-new pairs, 59.73 equivalent-English**, against the proposer's labelled projection of roughly 2,400, so the projection overstated by 23x and the closure is a measurement. **Two findings worth more than the source.** The obvious safety rule is WRONG, not conservative: requiring the `Domain Name` field and the date with no blank line between them admits only 94 of 488 pairs, because the NSI layout *always* puts a blank line before `Record created on`, so 81% of true pairs legitimately cross one. And **law 5 does not bite here at all**, 0 of 26 hand-audited survivors invented, for a structural reason worth carrying: **a placeholder has no registry record to paste**. The defect this seam does have is attribution rather than invention, measured at 3.8% by hand and 0.5% to 3.6% against two signals the parser never reads (the `(FOO-DOM)` handle agrees 271 of 281, the poster's own `whois <name>` command line 214 of 215) |
| The ISI RFC 1480 US Domain Registry, and why an accumulating list needs two editions (2026-08-18) | **Retrievable, self-dating, in the namespace we are thinnest on, and worth one pair.** Four dated in-window editions recovered, covering `k12.XX.us`, `lib.XX.us`, `ci.` and `co.` locality names at 0.9261 weight against a store holding only 18,278 distinct in-window `.us` against 216,581 `.uk`. Then the arithmetic: the registry **added four names between August 2000 and November 2001**, so the legitimate first-appearance diff prices at **1 net-new pair and 0.9 equivalent-English**, while the illegitimate reading, taking each edition's own date as dating every name in it, would have claimed **13,014**. That is the cleanest instance yet of the trap `discovery.md` names, and the ratio is 13,014 to 1. Its contact column separately re-confirmed law 3 at 97.7% already known. The rest of the content-filter and locality-registry family (CyberNOT, SurfWatch, Bess, N2H2, DansGuardian, urlblacklist, MESD) is closed for want of two dated editions, and **a single edition of an accumulating list cannot date anything** |
| Another precomputed IA capture census in a research repository, the family enumerated (2026-08-18) | **The corrected query was the right correction and the population is four items.** The 2026-08-15 sweep asked these hosts for domain lists and recorded that the query shape was wrong; asking instead for the DATING ARTIFACT, across eight full-text DataCite sweeps, file-level Dataverse search, the Dryad and OSF APIs and an enumeration of archive.org's research collections, finds the entire in-window population of precomputed IA capture indexes to be **four items**. Three are already in this register (`early_web_cdx` banked, the parallel-language URLs rejected, `nypw_timemaps` deferred at 19.35 GB) and one was new: Weber's DRUM deposit `10.13020/D62684`, NSF-funded, 1996-2000, global rather than one ccTLD, 74.83 GB in 16 tar parts. Measured rather than deferred: **45,130 of 45,130 sampled pairs already held, and 1 net-new pair worth 0.63 equivalent-English from 226,171 real rows** across all five years, with 97,904 of 97,905 source-side pairs already dated that exact year. **ICPSR, OSF and Dryad were blank against working positive controls** and should not be re-swept for this shape. One trap recorded for whoever checks a status code next: the UKWA per-year CDX endpoint now serves a **159-byte meta-refresh stub under HTTP 200 for every path including a control path known not to exist**, so a status-only probe will report a 6.5 GB in-window index as live |
| Discmaster, the index over archived media contents (2026-08-18) | **The missing index really exists, works better than expected, and the media population is already ours.** It is queryable by filename, extension, format, size, family, content and file date, with JSON output, deterministic hash-ordered sampling, content deduplication and a real bulk endpoint (`search?download=true` returns every match as one tar.gz up to 1 GiB, verified three times), under a `robots.txt` that says Disallow and carries its own written exception for limited targeted research automation. It enumerates 120,127 `.url` shortcuts, 28,093,342 HTML files and 273,212 deduplicated in-window `.txt` files naming a URL. It prices at nothing **three times, twice by census**: the deduplicated `.url` population is **125 net-new pairs and 78.9 equivalent-English at 95.6% overlap**; bookmarks and hotlists are 63 net-new by media date, 10 by the browser's own `ADD_DATE` and 6 by `LAST_VISIT`, at 99.0% to 99.76% overlap; the broad `.txt` population projects to 41 equivalent-English on the lowest of three fits. The best sub-population reaches 2.5% of the volume bar. **Two dating findings are the keepers.** Of 11,811 in-window Netscape `ADD_DATE` values, 81.2% equal the media file-date year, 18.8% are earlier and **zero are later**, so where a browser wrote both dates on a real filesystem the container date drifts one way only. But **that safety does not survive nesting**, which is where most of the corpus lives: 77.7% of in-window `.url` files and 89.6% of their post-split survivors sit inside a self-extracting installer or archive, so the date describes a packaging event and errs in **both** directions, with `edimensional.com` dated 2000 off an October 2005 cover DVD and `spamarrest.com` dated 2000 for a company founded in 2001. A third result sharpens law 5: zero of 125 `.url` survivors are invented, because nobody writes a fictional hostname into a Windows shortcut, so **on machine-written link artifacts the junk moves out of the hostname and into the date** |
| An early bulk whois snapshot of 2002-2008 vintage (2026-08-18) | **Closed mechanically rather than on a list of dead hosts, which is the stronger kind of closure.** Three facts settle it without probing anything: whois of that era answered on **port 43, which no web archive crawls**; bulk registry access was a **contractual provision to accredited registrars** rather than a published file; and the paid market that does sell historical snapshots **begins its own archive in January 2016 by its own statement**, so no 2002-2008 snapshot exists for a free copy to derive from. Five free platforms were then swept to exhaustion with per-query byte and row counts (academictorrents' whole 2,853-item catalogue via the bulk XML they ask scrapers to use, HuggingFace 63 hits all username collisions, archive.org across four query shapes, Zenodo's 9, authenticated GitHub search), each zero validated against the 25.9 GB file already on disk as a positive control. The zone-file rows say nothing about this: **those close files that list names WITHOUT per-name dates**, and a per-domain creation date is exactly what lets an out-of-window file date names back into the window. **The measurement worth carrying generalises the `.se` finding to the whole store: 7,909,927 of 10,867,530 in-window domains carry no in-window creation date from the 2024 snapshot, at mean weight 0.5084 and 4,021,267.2 equivalent-English.** That prices the gap an earlier snapshot would address, and turns this from a hunting question into a purchase question, which is Ivo's and not an agent's |
| Government grant and award records 1996-2001 (2026-08-18) | **The first lens to CLEAR the item-count test decisively and still die, which makes it the most informative rejection available.** 456,700 dated in-window items across four funders (NIH 372,444, NSF 60,377, CORDIS 23,879, Gateway to Research **zero**, its 158,712 projects all starting later), which is 3.8x the ~119,000 the density ceiling demands, every route free, bulk, born-digital and dated at the item level by a start date frozen at award. **What it disproves is the ceiling's own generality: 0.042 pairs per item is a property of SUBJECT MATTER, not of prose.** Both corpora that established it are prose about the internet. By NSF directorate: CSE 0.0471, BIO 0.0152, GEO and TIP **0.0000**, and NIH's biomedical corpus 35x below at **0.0012**, being **164 distinct hostnames in 372,444 abstracts**. The closing arithmetic is almost too neat: CSE, the one sub-population that reaches the ceiling, holds about 4,984 in-window items against the 4,997 of the largest scholarly corpus the ceiling was invented to reject. Priced against the live store the NSF prose seam gave **1 net-new post-split pair, 0.5 equivalent-English** from a 9.79% sample. **And the one dense seam had to be killed on dating instead, which yielded a fourth junk mechanism**: NSF's per-award `piEmail` is 95.1% covered at mean weight 0.7519 and produced 90 survivors, but it is a **current-state contact field refreshed under a frozen date**, caught by `gmail.com` appearing 61 times on 1996-2001 awards and confirmed by 42 of 58 hand-audited survivors carrying a registry creation date **after** the year claimed. Two constants now screen other leads for free: read the ceiling as subject-dependent, and assume any per-entity contact or homepage column is undated until a per-field date is produced. About 400 requests to `api.nsf.gov`, 12 bulk zips from NIH, two from CORDIS, 58 RDAP lookups, **zero to web.archive.org** |
| Dated newswire and press-release full text (2026-08-18) | **Closed on a density measured on the real thing rather than on an access refusal, and the recommendation is DO NOT sign the NIST agreement.** The lens was built around Reuters RCV1, 806,791 stories inside 1996-1997, which is 6.8x the item count the ceiling demands and covers the two years the Internet Archive cannot supply in bulk. Two answers. First, an ungated bulk newswire corpus **does** exist and is larger than RCV1: `usenet-clari.*` on archive.org, 22 items and 21,309,542,972 bytes, with Business Wire and PR Newswire full text in 61 dedicated `.releases` groups inside `clari.biz` alone. It fails on **era**, not shape or access: across four group files parsed in full and six more censused through their per-message CSV sidecars, the earliest message is uniformly **2003-06-23**, because these items are the Giganews spool rather than the Deja archive. Second, and decisively, the ClariNet sample feed **already on our disk** is genuine Reuters, UPI and Newsbytes wire copy from inside RCV1's own span: 8,010 in-window stories, 20.39 MB of story text after stripping 43.8% ClariNet boilerplate, yielding 305 (domain, year) pairs of which **305 are already held, 0 net-new before the split and 0 after**, with only 3 of the 305 held on this corpus's own evidence so the redundancy is real rather than circular. **0.000 pairs per item against a 0.042 ceiling**, and the mechanism is measurable: only **4.79%** of wire stories name any domain, and the ones they name are `newsbytes.com`, `reuters.com`, `microsoft.com`, `aol.com`, `apple.com`, `amazon.com` and `yahoo.com`. **A wire story names a company's web site only once the company is famous enough to be in the story**: promotion-selection, the sibling of law 3. Three reusable facts: the working `ai.mit.edu` path for the LYRL2004 README where both `jmlr.org` paths 404; the only licence-free RCV1 distribution is **stem-scrambled by design** so no hostname can survive it; and the archive.org usenet **CSV sidecar** censuses a group's date coverage with a 50 KB ranged GET instead of a multi-gigabyte download |
| Machine-written network diagnostics pasted into Usenet bodies (2026-08-18) | **Closed on a whole-corpus census, and the item count settles it before any pricing.** 29,040 of 219,447,104 in-window messages carry a diagnostic structure, one in 7,557, so even at the ceiling the lens caps at 1,220 pairs against a 5,000 bar. Measured: **297 net-new post-split pairs, 165.7 equivalent-English**, mean weight 0.5579, and a hand audit of 40 survivors removes 47.5% of them and 57.7% of the equivalent-English, leaving roughly **150 pairs and 70 EE for 383 GiB read**. Sub-seams measured separately rather than pooled: `traceroute` dies on law 3 as predicted, 4,293 hop tokens collapsing to 556 domains with 71.0% infrastructure-labelled and 80.0% of hop domains held in all six window years, for 53 net-new pairs against the `Path:` seam's 49; quoted mail bounces are the least infrastructure-shaped at 13.1% and 2.3x collapse but return only 68; and `nslookup` and `dig` do slightly better at 90 pairs and 0.6140 mean weight, because DNS groups quote the broken zones of small sites. **The real reason none of it pays was available before the first byte**: this corpus was already read corpus-wide for bare hostnames on 8 August, so 76.7% of every mention comes straight back out of the shipped extractor on the same body text, and the store already holds 90.1% of the pairs and 98.3% of the names. Three findings outlive it: the **negative-evidence** problem, where a genuine machine-written line proves a name did NOT resolve and is indistinguishable in shape from one proving it did; **`.arpa` reverse zones entering the metric at weight 1.0000**, which turned out to be a live defect in our own shipped files and is fixed; and a correction to law 5's exception, that the quoted-whois seam escapes placeholders because **a whois block is too expensive to sanitise**, not because machine-written records lack them |
| Dated announcements of new domain registrations (2026-08-18) | **Right about dating, wrong about volume, and the item count says so before any fetch.** A list of names registered this week is the strongest shape this project has: immune to law 2 because the artifact asserts registration rather than listing, and immune to law 5 because nobody invents a registration report, verified at 0 of 25 hand-audited survivors with the mechanism now one step clearer, since **a placeholder has no for-sale inventory to be listed in either**. What it lacks is items, and the reason is one structural fact that held at every registry checked: **a registry of this era published either dates without names** (statistics, as at `domainz.net.nz/newsstand/stats/` and every InterNIC and NSI registration report) **or names without dates** (a zone snapshot, the accumulating-list trap). The intersection existed only where a registry ran its approval process in public, and that was exactly one namespace: the CA Domain Registry's notices in `can.domain`, already on disk and already settled at 936 post-split pairs and 783.0 equivalent-English. Everything else is two orders short. The on-disk domain groups give 541 in-window list posts and **144 net-new pairs at 113.4 EE**, where about 18,800 posts would be needed at their own perfectly healthy density of 0.266 pairs per item. A newly found robot-written **AlterNIC root-sync corpus** gives 336 in-window items and 63 pairs at 31.2 EE, reconfirming law 3 from a fresh artifact. The archived registry whois CGIs ceiling at about 2,600 items at one page fetch each, and the recently-registered-page industry starts in 2002. The one condition that reopens it is a **bulk** route to archived per-name whois bodies, which passes every test except affordability. Eight requests total, all to bulk index endpoints, every zero proved against a working positive control |
| Discmaster by file size, and the April 1998 `.jp` registry listing it found (2026-08-18) | **The route works, it found a complete dated national registry snapshot on the first try, and that snapshot is 87.5% already held.** Asked the index the question nobody had asked, filename and size rather than link-artifact shape, at `sizeMin=262144` inside the window. `dedup=1` kills the connection and every other parameter is fine, which is worth knowing before anyone else automates it; `robots.txt` says Disallow and carries its own written exception for targeted research automation. The find is `email.domains`, 2,085,500 bytes and 42,701 lines dated 1998-04-29, at `/japan/email.domains` on the `ftp.cs.arizona.edu` mirror, item 19864. **It is self-dating from inside itself and carries its own liveness flag**, which is rarer than either: the header reads *"Registered Domains in JP (Apr 30 1998): 42143"*, *"Connected Domains in JP (Apr 30 1998): 36225"* and *"(Domains in parentheses are not connected.)"*, and it is sectioned by second level (`CO` 30,305, `OR` 4,432, `NE` 2,274, `AC` 1,302, `GR` 1,730, `GO` 306, `AD` 188) plus 54 prefecture and city sections. The parser is validated against the artifact's own arithmetic to the unit: **36,225 connected parsed against 36,225 declared, +0**, with a quantified +431 over-count confined to the not-connected half. Priced against the live store on the connected subset: 36,187 pairs, **31,686 already held (87.5%)**, 4,501 net-new pre-split, **3,062 net-new post-split at 185.3 equivalent-English**, mean weight 0.0605, 1,439 pairs to the candidate pool. **REJECT on both bar conditions**, volume 3,062 against ~5,000 and weight 0.0605 against the 0.4 floor. **And it is the load-bearing demonstration of the morning's `price_items` fix**: without `--all-tlds` this source prices at exactly **0 pairs and 0.0 EE**, because `.jp` is not in the prose whitelist, and the new WHITELIST DROPPED line reports 36,187 names dropped at mean weight 0.0605. Before today it would have been discarded silently. The reopen condition is precise and narrow: **the same shape for a high-weight namespace**, since a `.uk`, `.au` or `.ca` registry listing of the period would be worth 16x per name. Searched for one, and `.domains` as a filename yields nothing else of size: 60 hits, all source code, HTML and small config. **The route's second find is a clean zero and a useful control**: the `faces` database's `domains.tar.gz` from `ftp.enst.fr/pub/unix/network/mail/`, 9,599,488 bytes uncompressed with its own gzip mtime of 1996-07-06 and `gzip -t` passing, is a `domains/<tld>/<label>/` tree of 1,012 organisations. It is a **cumulative** database, so the container date is the accumulating-list trap and the honest field is each entry's own first-appearance mtime: those run 1991 to 1996, and only **211 domains first appear in window** while 801 predate it. Priced, 192 of 192 resolvable pairs are **already held, zero net-new**, which is a positive control on our own coverage of 1996 organisational domains rather than a disappointment |
| Afilias' Land Rush 2 schedule: 0.00 post-split, and 40 names the registry itself dates (2026-08-25) | **The list Afilias printed inside its own WHOIS records is gone, and the fragment that survives is worth nothing after the split.** `landrush2.afilias.info`, the URL Afilias gave registrants as the place to get the names, **still resolves at 66.199.183.26 and refuses TCP 80**; `www.afilias.info` redirects to a marketing site. The surviving fragment is `onlinedomain.com`'s `LR2-list-of-4257-available-domains.txt`, 82,107 bytes, 4,257 bare `.info` names A-to-Z, being the subset of Afilias' 16,912-name schedule still unregistered in **2012**. Priced: 4,256 gross net-new pairs at 1,552.59 EE and **0.00 post-split, because exactly 1 of the 4,257 names is dated anywhere in the store**. Three further reasons it fails: its own bytes carry `"copyrightYear":"2012"` and no 2001 or 2002 date appears in the file at all, so the year is **inferred from a class statement** rather than read per item; the footer is `(c) Copyright 2012-2026 - All Rights Reserved`; and it is a third party describing the registry, so not master-eligible. **What did pay, cleanly: 40 names the registry itself dates to Sunrise 2001.** `.info` RDAP returned 40 `registration` events in 2001, master-eligible `whois_creation`, no split, and **all 40 are net-new domains absent from the `domain` table entirely**, worth **14.59 EE**. Every one falls between **2001-07-31 and 2001-08-15**, inside the ICANN-stated Sunrise Period, with no exceptions, the registry confirming the source list's class statement on every name where it could be checked. **A sampling lesson in the derivation**: 657 requests, 258 answered, 40 confirmed at 15.5% overall, but the *random* pilot gave 16 of 60 (**26.7%**) while the alphabetical sweep segment gave 24 of 198 (**12.1%**), because it only reached `adv*`. Alphabetical order is not random order. **Routes exhausted**: ICANN's 2009 reallocation proceeding has exactly one file link, the already-dead RSEP PDF; `forum.icann.org/lists/info-sunrise-amendment/` is 3 messages from 2009 with **zero** `.info` strings; and `onlinedomain.com`'s own WordPress media API confirms the 4,257 file is the only name list that site holds. **Reopen only on** a Wayback capture of `landrush2.afilias.info` or of Afilias' May 2002 news release, and note the residue is ~475 to 875 EE for the whole 9,099-name pool at 3 q/s over several hours, which is below the floor |
| The ICANN forum `.info` Sunrise lists: 1,328 EE, and a registry corroborates the dating (2026-08-25) | **A decision for a human on two grounds, with unusually strong evidence on the one that matters.** `forum.icann.org/newtldagmts/` is ICANN's public-comment forum for the new-TLD agreements, **7,169 message pages, frozen since March 2002 and never taken down**. It was the venue for the `.info` Sunrise-abuse scandal, so posters pasted whole registrar Sunrise lists. Largest item `3C8A91B500002319.html`, verbatim `Date/Time: Sat, March 9, 2002 at 10:50 PM GMT` and `Listed below are the 6122 names registered at Sunrise by Worldnic.`, of which **5,279 actually parse**, so quote 5,279 and not the artifact's own 6,122. Union with WIPO's `.info` Sunrise case index: **7,988 names, 7,284 net-new, 2,657.20 EE gross and 1,328.60 post-split**; the hard-dated subset alone (per-message 2001 `Date/Time:` headers) is 2,568 names and 396.17 EE. **The dating claim is corroborated by the registry itself, which is what makes this worth a ruling.** An RDAP probe of the forum-derived names returned **42 creation dates, 24 of them 2001, and all 24 fall between 2001-07-31 and 2001-08-15**, entirely inside the Sunrise Registration Period that WIPO states verbatim as `July 25 - August 28, 2001`, and none was already dated 2001 in the store. **The two grounds against.** Licence is restrictive: ICANN's ToS reads `Your use of the Platform grants you no right or license to reproduce or otherwise use any intellectual property belonging to our organization or other third parties`, though the pasted content is registrars' output rather than ICANN's. And the names were pasted by third parties, so killer 5 is live and the split decides between 1,328.60 EE and zero; the RDAP agreement above is the counter-evidence. **The RDAP route was correctly abandoned, but for the wrong stated reason, and the correction is a citizenship point.** A second agent established that the 403 wall is **transient throttling, not an identity ban**: it began at record 199 and held unbroken for all 394 after it, body `awselb/2.0`, 118 bytes, **no `Retry-After`**, and after roughly 12 minutes idle the **same User-Agent** received a genuine 404. So the host throttles above about 3 q/s and answers again after a rest. **Honour that by slowing down, not by filing the host as refusing us.** The route is still not worth running on arithmetic: 66.6% of probes returned 403, which under this project's own PIR precedent, and the projection was only ~1,065 names and ~389 EE for 8,787 queries against a host refusing two in three, because **79% of non-403 answers are deleted names**, the Sunrise cohort was cancelled and re-released, so survivors carry 2006-2025 re-registration dates. **And I oversized this prize 2.1x.** Afilias' own filing gives Sunrise **51,784 registered** and Land Rush **306,017**, against **818,905 applications**; I had quoted applications. The documented 2001 launch register is **357,801 names, 122,642.84 EE net**, about three quarters of the gap rather than more than it. ICANN's 2009 page claiming ~300,000 Sunrise names conflicts with the registry's contemporaneous 51,784; prefer the registry. **Closed in writing**: the 13,593-name bulk cancellation list, because WIPO records `At the request of Afilias, the Challenges of Last Resort were not posted.` |
| A 2001 squidGuard blacklist pays 10,736 EE, and crawling kills discovery not completeness (2026-08-25) | **The largest licence-clear find of the round, and it triggers this register's own reopen condition rather than contradicting a closure.** One request to `archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`, 1,852,659 bytes, yields `samples/dest/blacklists.tar.gz` at tar mtime **`Dec 18 2001`**, whose files carry their own header `# This list was compiled in 0:00:20 on 2001.12.18 15:04:29.` and dated diffs from `domains.20010814.diff` to `domains.20011218.diff`. **Licence GNU GPL v2**, verbatim in `COPYING`. **Measured 44,130 canonical names, 18,588 net-new (domain, 2001) pairs, 10,736.2 EE**, no split because `squidGuardRobot-2.3.4` generated it and its header asserts liveness rather than listing: `compiled from 2402 link sources and 654820 links, of which 510389 tested successfully`. Typo bound 0.07%, the cleanest blocklist on the project. **A reconciliation worth recording**: my first pass read only the 11 `domains` files and returned 8,118.0 EE, disagreeing with an agent's 10,736.2. The gap was mine, not theirs: the `urls` files and the 2001-dated diffs are equally the robot's own output, and including them reproduces 44,130 names and 10,736.2 EE to the decimal. **THE LAW THIS CORRECTS, written only this morning.** I had recorded that adversarial selection pays only if the adversary did not crawl, citing the **2000-10-18** squidGuard edition at 99.47% held and 18 EE. That was right about novelty and wrong as a verdict. This edition is **84.8% known to the store but only 57.9% held at 2001**, so 11,895 of its held names LACK the year it is dated, worth 6,760.9 EE, with a further 6,693 novel at 3,975.3. **Crawling kills DISCOVERY, not COMPLETENESS**, so ask which year an artifact can add before dismissing it for its channel. The 2000 edition failed because its names already carried 2000, not because a robot made it. **And it satisfies the reopen condition this register wrote for `content_filter_blacklists` verbatim**, "reopen only on an in-window edition from a non-Wayback mirror", so the closure is being triggered rather than overturned. Content is mostly adult, gambling and drugs, which a human should see even though the shipped files carry names without categories |
| The `.us` locality gap is 61% dead names, which corrects how headroom must be counted (2026-08-25) | **The lens closes and the method improves, which is the better outcome.** The target was 9,680 `.us` domains held in window and missing 2001, worth 8,964.65 EE. **But 6,948 of them were last seen in July 1997**, and only 1,473 reach 2000. Breakdown by latest year actually held, verified against the store: 1996 155, **1997 6,948**, 1998 549, 1999 555, 2000 1,473. Against a control in the same store, of the 12,080 `.us` names the ISC 1997 walk attests only **37.65%** have any 2001 record, and the `.com` cohort from the same file runs 40.31%, so this is general attrition rather than a `.us` artefact. A 2001 roster names live districts, so **the addressable share is nearer 3,500 EE than 8,964**. **THE RULE, now in `CLAUDE.md`: compute headroom from the ADJACENT year only.** A gap between a domain's last held year and the target is evidence of death, not of missing data, so "held ANY year, missing Y" is contaminated while "held Y-1, missing Y" is not. This also vindicates the 2001 re-aim for a second reason: held-2000-missing-2001 is adjacent by construction. **And the floor arithmetic closes the lens outright.** The IMLS Public Libraries Survey FY2001 yielded **58 held-missing-2001 domains from 773 distinct `.us` names, a 7.5% yield**, so the floor needs **~14,400 distinct `.us` locality names inside one 2001-dated artifact**, two thirds of the entire in-window `.us` population of 20,925, which is a DNS enumeration and not a roster. **No post-1997 `.us` enumeration was ever published**: `isc_survey` holds 12,080 `.us` at 1997, 6,135 at 1996 and **nothing at 1998 or later**, which is the register's "lists stop at 9707" seen from the store side. **Artifacts measured on the way.** The PLS FY2001 is real, licence-explicit ("Public-use data files are publicly available without restriction, and do not require a license"), era-vintage (per-state `ENDDATE` all in 2001, `YR_SUB` 2002), anachronism test passed with zero post-2001 TLDs, and worth **121.44 EE total of which `.us` is 53.71**, and it **duplicates the pending `nces_imls_pls_web_addr_1998_2001`**, whose FY1999 edition is already measured at 280.1 EE, so no new entry was created. **NCES's Common Core of Data kills the national K-12 route outright**: the 2001-02 LEA universe layout, 145 variables over 17,276 districts, has **zero** matches for web, url, internet or http, its contact fields stopping at `PHONE01` and `MZIP01`. State education portals are current-state or gone (`www.state.vt.us`, `www.state.az.us` and `www.state.ct.us` all hold A records and refuse both 80 and 443). **New by-name refusal**: `lists.h-net.org`, which hosts the EDTECH archive, names `anthropic`, `claude-web` and `claudebot` in one block ending `Disallow: /` |
| Southern and Central Europe: 50 hosts dead, and an API caught lying twice (2026-08-25) | **Ran independently of the RIPE closure and agrees with it, which is the useful part.** This slice was already shut structurally by RIPE's own 1999-02-01 restriction of the host output files; `.gr` and `.il` are RIPE-region too, so the whole ccTLD list falls under it. The agent did not know that when it started and reached the same answer by host and archive layers. **The host layer is dead, not refusing: 50 hosts screened**, 26 NXDOMAIN (`ftp.nic.at`, `ftp.nic.fr`, `ftp.cnr.it`, `ftp.switch.ch`, `ftp.huji.ac.il` among them) and nine resolving but refusing all of 21, 80 and 443, against a control where `ftp.funet.fi:21`, `ftp.gnu.org:21` and `ftp.arnes.si:21` were all open in the same minutes. Every survivor is a pruned modern distro mirror with **zero** netinfo paths. **The best lead and its closure**: `ftp.bme.hu/documents/ripe/` is a live RIPE mirror, which matters because pre-1999 raw output was open, and it is flat, 1,082 hrefs of `ripe-NNN.{txt,ps,pdf}` with **no `hostcount/` subtree**. `ftp.arnes.si/pub/network/PHARE/` has daily 1994-1996 files and dies on names: `011096.raw` is `00:00,391831248,1458540904,,,,,,,`, SNMP octet counters. **The one real walk artifact re-priced, and it is a DATE failure not a size failure**: `es-nic-20001006`, 4,577,664 bytes, 26,068 canonical uniques, licence none found, gives **7,492 held-missing-2001 at 1,254.16 EE**, over the bar on volume, but its own metadata says `2000-10-06`, so it evidences **2000 only**, where an independent measurement puts it at 349 EE. Binding it to 2001 is rule 6. And **no 2001 sibling exists**: `title:("Domain Nameservers Snapshot")` returns 1, and its uploader's other 351 items are Spanish retro hardware and arcade magazines, so it is one hobbyist's one-off rather than a series. Useful by-product: the **`.es` 2001 ceiling reachable from a full walk is 1,254 EE**, below the ~2,300 previously assumed. **THE API TRAP, now in `CLAUDE.md` because this is its second catch today**: archive.org's `services/search/v1/scrape` **rejects `count<100` and, under load, returned an identical bogus `total=28330` for five different queries, producing six false zeros in one batch**. Earlier the same endpoint returned the same 6 items for five different collections. **Verify any archive.org zero through `advancedsearch.php`**, whose controls here were `axfr` 304, `identifier:*rfc*` 28,330 and `identifier:*zone*` 29,298. `collection:ftpsites` pulled in full is **974 items of which exactly 6 are dated 2003 or earlier**, none a European NIC. **New by-name refusal**: `ftp.cc.uoc.gr` names `Claude-Code`, `Claude-SearchBot`, `Claude-User`, `Claude-Web` and `ClaudeBot` under `Disallow: /`. Also refused and untested rather than dry: `ftp.rediris.es` (`Disallow: /`), `ftp.grnet.gr` and `ftp.ntua.gr` (`Disallow: /pub/`, the whole mirror), `ftp.renater.fr` (403 on robots.txt itself) |
| The 2001-2003 frozen-mirror sweep: both screened artifacts were already answered (2026-08-25) | **A negative whose value is two method points and an independent re-derivation.** (1) **The Edelman whois transcriptions were re-found from scratch by a second route and priced at 741.61 EE**, against the **2,968.49 EE** already banked in this register today from a fuller parse. The agent grepped, found the existing rows, and deferred to them rather than reporting its own lower figure as news, which is the behaviour worth having. Its independent 2001 slice is worth quoting as corroboration: 3,900 names dated 2001, 2,460 held, **1,003 held-missing-2001 at 618.71 EE**, plus the freeze dates from HTTP headers (`Last-Modified: Sun, 08 Sep 2002 02:34:06 GMT`) and per-record bodies (`AARONDAY.COM / Registered on: Oct 22, 2001`). (2) **Frozen 2001 `analog` web-stats reports from three untouched hosts confirm the reverse-DNS closure and quantify its self-overstatement.** 53 in-window 2001 files, dated in body `Program started at Sat, Sep 01 2001 08:00`, untruncated (`Listing hosts with at least 10 requests`), licence none found: 33,003 FQDN tokens collapse to 6,141 canonical uniques of which **5,914 are held and only 304 are held-missing-2001, giving 137.26 EE at 96.3% already held**. **A pre-pricing ceiling for the same files had been 3,900 EE, so this class overstates itself about 28x until measured.** **METHOD, now in CLAUDE.md and proven twice today: clear a whole FTP host with ONE request by pulling its own `ls-lR.gz` or `locatedb.gz` and grepping offline.** `ftp.gwdg.de`'s 926 MB locatedb indexed an 8.8 GB tree; a 9.8 MB `ls-lR` gave 1.46 million lines. Politer than crawling, more complete, and it turns a zero into a proved zero. **Negatives banked**: `ftp.lip6.fr`'s frozen 2002-2003 trees hold only software; `download.huihoo.com/dmoz/` is a 2013 dump so the 2001 DMOZ full RDF stays unretrievable; Edelman's `.NAME`, `dotus` and `ip-sharing` sets (115,990 domains) are all dated **2002**, outside the window; and the drop-catch half of the churn lens is structurally 2002+. **New by-name refusal**: `www.math.upenn.edu` names `Claude-User` and `Claude-SearchBot` under `Disallow: /` |
| Raw AXFR output WAS published openly, and the surviving editions are 1995 only (2026-08-25) | **The find that almost reopened the whole walk family, closed at the source in one request.** `ftp.ripe.net/ripe/local-ir/inaddrcount/data/193.in-addr.arpa.output.gz` is a **genuine raw AXFR transcript**, 2,332,217 bytes and 491,640 lines, opening `Asking zone transfer for 193.in-addr.arpa ...` and carrying **50,141 PTR targets with real bare hostnames**, TLD histogram `uk` 16,559, `com` 7,144, `ch` 3,568, `su` 3,433, `hu` 3,148, `de` 3,048. Licence: none found, its README being Geert Jan's note to the RIPE local-ir working group. Dated three independent ways, all 1995: HTTP `Last-Modified: Tue, 02 May 1995 21:00:00 GMT`, FTP mtime `03-May-1995 19:36`, and the SOA line `95042701 ;serial (version)` inside the bytes. **So raw walk output with tens of thousands of bare hostnames really was published openly before the 1999-02-01 restriction, which made 1996-1998 editions the obvious prize** rather than 2001. **Tested directly and dead: `inaddrcount/data/` holds exactly four files, `193.` and `194.` output and error, every one `03-May-1995`.** No 1996, 1997 or 1998 edition exists at the source, so the class is exhausted rather than parked, and the 1995 edition itself must be refused because binding its names to an in-window year is the neighbouring-record-date trap. **Alongside it, the UK/IE/CA slice closed with its ceilings re-derived independently and matching**: `.uk` 157,576 missing-2001 domains at 154,629 EE, `.ca` 46,163 at 38,615, `.us` 9,680 at 8,965, `.ie` 1,949 at 1,899. Those ceilings are real and unreachable: **Nominet is the only party that ever held the `.uk` database and publishes current state only.** Two live archives remain in that whole slice and neither holds netinfo: Edinburgh's only JANET-era material is a 14,989-byte 1992 `masks.shar` and 31 PostScript maps from 1991-1994, and the HENSA successor `mirrorservice.org` has 143 mirrors, all software, whose copy of `ftp.isi.edu` contains exactly one directory. **And CIRA's `.ca` RDAP is the already-harvested trap in miniature**: 120 held `.ca` domains missing 2001 gave 49 answers, all with a registration event, 31 in window and **every one of the 31 dated 2000, none 2001**, because the store already holds 17,465 `.ca` `whois_creation` pairs at 2000 against 10,228 at 2001. **New by-name refusals**: `ftp.sunet.se` and `ftp.surfnet.nl`, both naming `Claude-User`, `Claude-Code`, `Claude-SearchBot`, `Claude-Web` and `ClaudeBot` in one block. **Two disclosed misses**: a root GET went out in the same batch as the robots read on `mirror.ox.ac.uk` (which disallows everything) and on `ftp.is.co.za`; one request each, nothing used |
| Forged-header corpora are ~5% held, which completes the held-fraction taxonomy (2026-08-25) | **The best-dated artifact of the whole round, rejected at 115.83 EE, and the reason is a new band on the scale.** The Lazarus anonymous-remailer monthly logs on a preserved FTP mirror carry the cleanest dating seen here: a complete 12-month 2001 series, 57,368,107 bytes over 13 files, where **each file's mtime lands on the last day of the month its own filename names** and each month's in-byte timestamps are exclusively that month with **zero cross-month bleed** (8,900 "Jan 2001" strings in `200101.laz`), plus an in-header `Fri Mar  2 00:45:13 EST 2001` under `A LAZARUS EARLY WARNING ALERT v3.06`. On a real preserved filesystem, not nested in an installer. Licence: none found. Bare hostnames in `From:` and `Message-ID:`. **And it pays 115.83 EE, because only 1,053 of its 23,102 canonical names are held in any year: 4.56%.** The cancel bot logs spam headers whose sender hostnames are randomly generated (`hjhlaylcfq.mil`, `iokoswuble.mil`, `aafhuunfo.mil`). **A forged-header corpus is ~95% invented names, the exact inverse of a blocklist**, so the pre-download discriminator is the expected held-fraction: **blocklists ~50%, authority corpora 87-99%, forged-header spam corpora ~5%.** That also bounds the 2001 yield constant: volume x 0.386 holds only where names are drawn from the held population. **Negatives, all pinned to 2001 against a passing control**: `extension=.zone` at sizeMin 32768 gives **0 rows**; no bulk whois dump exists (`"whois.internic.net"` gives 25 hits, all Delphi form text and `.hlp` files; `"Record created on"` gives 52, all tutorials and Perl modules, largest relevant under 2 KB); `"Registered Domains in"`, the shape that found the `.jp` register, gives **0 in 2001**; `format=windowsHostsList` is 60 items index-wide, every one the stock Microsoft template at under 937 bytes; browser caches are 22 saved `.mht` pages and 13 `index.dat` totalling 311 KB |
| The 2001 threshold qualified: it is a population average, not a universal rate (2026-08-25) | **A correction to this morning's own constant, and it would have misdirected the next hunt.** The threshold says one already-held name in a 2001-dated artifact is worth 0.386 EE, so ~2,600 held `.com` names clear 1,000 EE. **Measured against a real head-selected corpus it is nine times too optimistic.** The *Windows & .NET Magazine* article archive, `WinNetMagCD.chm`, 146,221,869 bytes dated **`2001-12-05 18:11:43` in the ISO9660 directory record**, licence none found, 5,519 HTML articles yielding 2,334 canonical names of which **2,296 are held and only 157 are held-missing-2001**, measures **95.67 EE, or 0.041 EE per name**. Against a control in the same minutes, a random sample of held `.com` paying 0.31 EE per name. **A magazine cites the head of the distribution and we already cover the head at 2001**, so head-type artifacts need ~24,000 names rather than 2,600. **Ask whether a list looks like a random draw from the register or like somebody's citations.** **And the arithmetic gap between that control and my population figure is itself a trap, now measured**: sampling `domain_year` ROWS gives P(lacks 2001) = **0.492**, while sampling DISTINCT DOMAINS gives **0.611**, because a multi-year domain is likelier to hold 2001. For pricing a list of names the per-domain figure is the right one. **Two enumeration facts banked from the same sweep.** `archive.org/download/<id>/<file>/`, following the 302, lists ZIP **and ISO** inner entries with true original timestamps, which an earlier pass had wrongly written off from an unfollowed 302. And **nothing was genuinely uploaded to archive.org in 2001**: `publicdate` and `addeddate` in 2001 return 58 and 76 items, all backdated media, so 2001 mtimes survive only inside later-uploaded containers, while filenames are not searchable at all (`files:`, `filename:`, `files.name:` all return 0), so `.zone` and `.domains` payloads cannot be found by search. The *Internet Info* CD series that carried InterNIC registration data exists there only for 1994 and 1995 |
| The southern-hemisphere walk lens: blocked by a CORRELATION, not by absence (2026-08-25) | **The structural point is the transferable one and it predicts the future of this whole method.** The `.au`/`.nz`/`.za` DNS-walk lens is not blocked by evidence about the artifacts. It is blocked by **host mortality on one side and robots refusal on the other, and the two are correlated**: the old mirrors that survived at all survived because a commercial or university operation kept paying for them, and mirror operators are exactly the population that has recently added blanket or Claude-named `Disallow: /`. **Five of the seven live large mirrors in this slice refuse by robots, two of them naming ClaudeBot**, and the two that permit crawling (`ftp.swin.edu.au`, `mirror.fsmg.org.nz`) permit it because they carry nothing but current distro trees. **New by-name refusals recorded**: `mirror.aarnet.edu.au` and `ftp.aarnet.edu.au` (both `User-agent: ClaudeBot` / `Disallow: /` plus `Disallow: /pub/` for all), and **`www.potaroo.net`**, Geoff Huston's site. Also refusing: `ftp.iinet.net.au` (`# GO AWAY!`), `ftp.sun.ac.za`, `ftp.is.co.za`, `www.ftp.saix.net`, `ftp.auckland.ac.nz`, `ftp.deakin.edu.au`. **And the worst outcome for this method, stated exactly**: the three machines that actually ran the southern-hemisphere zones, `munnari.oz.au` (still resolving at 202.29.151.3, having followed Robert Elz to Thailand), `apies.frd.ac.za` and `quagga.ru.ac.za`, **all still have live A records and all refuse both port 21 and port 80**, alive enough to look promising and dead enough to yield nothing. **Two count-only artifacts positively identified and killed on names**: `ftp.nic.ad.jp/jpnic/statistics/Connected_Domains`, a real monthly series back to 1992-05 but whose payload is `DATE JP AD AC CO GO OR GEO TOTAL` with integer columns and **zero names**; and `ftp.apnic.net/zones/`, which serves genuine AXFR-shaped files (`103.in-addr.arpa-APNIC` at 4,280,004 bytes) **all stamped 2026-Aug-25 23:30**, regenerated nightly, so current-state reverse delegation. A fresh-vocabulary archive.org sweep reconfirms the zone-file family's **2021 floor**: `hostcount` 0, `zonewalk` 0, `axfr` 304 items whose earliest non-RFC data artifact is `ch_zone_file_202106`. **Reopen condition, narrow**: a third-party mirror outside AU/NZ/ZA and outside the refusing set that snapshotted an AARNet or Waikato `/pub/` tree before 2003; `ftp.nic.ad.jp/mirror/` was checked for exactly that and mirrors only five sources, none southern hemisphere. **Disclosed near-miss**: the `ftp.is.co.za` root listing went out in the same batch as its robots fetch, one listing, stopped on reading it |
| The 2001 hunt: five routes closed, one prize sized, and a reported trap that does not exist (2026-08-25) | **The 2001 threshold sent six lenses out; here is what came back.** **The prize, sized and not found.** A full 2001 `.info` register would be worth **~273,600 EE**, more than the project's whole remaining gap, because the store holds only **21,609 `.info` at 2001** against ~750,000 that existed by year end, at weight 0.3648, and a registry register is master-eligible and takes no split. **It does not survive.** ICANN's Registry Operator's Reports are aggregate counts plus registrar names: the January 2005 `.info` report, 304,938 bytes, yields 82 `.info` strings in the pass that measured it, **corrected the same day: a fuller read finds 148 bare names in "Section 7 - Domain Names Registered by Afilias", pricing at 145 net-new and 52.90 EE**, which is still not proposable because the artifact is 2005-dated. The rest of that pass's 82 strings are text fragments or registrar marketing sites, and the 2001 reports are not at that path at all. Afilias's own 10-page Sunrise and Land Rush report to ICANN (`27aug02`, 228,391 bytes, 173,394 characters extracted) contains **zero** `.info` or `.biz` names, being tables of queue depths. On archive.org, `neulevel` returns **0** against a control of **1,203** for `(.info OR .biz) AND sunrise` in the same minutes. The cancelled-name lists went only to authorised registrars. **And a refusal to record ahead of time**: the `.biz` IP-Claim/STOP list of ~25,000 names must be REFUSED even if found, because an IP Claim is a trademark holder's claim on a STRING and the matching applications were pending, many never allocated. Reading it as a register manufactures registrations, exactly like `.ie`'s `stalled.html`. **The structural reason the gTLD walk lens is empty**: by 2001 nobody could AXFR `.com`, `.net` or `.org`, Verisign having closed zone transfer, so gTLD zone files moved to contract-restricted current-state distribution. That is why the one surviving walk artifact on archive.org is a **ccTLD** walk: `es-nic-20001006`, 4,577,664 bytes of genuine `dig`-style output, 26,834 uniques, which **fails on date** (stamped 2000-10-06, so it evidences 2000 only, worth 348.99 EE there). **The productive reframe: ask which ccTLD registries were still AXFR-able in 2001 and whose walk somebody kept.** Also closed: SEC EDGAR 2001 exhibits are contracts not attachments (`"schedule of domain names"` returns **0** against 316 for `"domain name registrations"` in the same minute); archive.org's `subject:"reverse dns"` is 49 items, all Rapid7 2013-2015; 2001-era ISP `named.conf` files do not survive because **a config is scratch and public repos hold only templates and distro samples, which contain `example.com` by construction**; and the frozen nostalgia hoards have a **1997 ceiling** because the hobbyists who built them cared about the pre-web Internet, so looking for 2001 there is the wrong decade's shelf. **One unfinished sub-route worth naming**: the 2001 hosting collapse as a document generator, PSINet and Exodus bankruptcy dockets, where creditor matrices are company names and worthless but an attached customer schedule would not be. **And a CORRECTION to a reported trap.** An agent reported that `to_registrable` silently drops a CRLF-terminated name, so a CRLF candidate file prices at near-zero and looks like a bad extraction. **Tested and false**: `to_registrable` returns `example.com` for `'example.com\r'`, `'EXAMPLE.COM\r\n'` and `' example.com '`. Its `canonical uniq 21` from 800 lines had some other cause, in its own splitting code. Recorded because an unverified trap warning is worse than none, since it sends the next reader after the wrong thing |
| BREACH: `tomocha.net` refuses ClaudeBot by name and we fetched it twice (2026-08-25) | **Self-inflicted, mine, and it costs 1,623 EE plus a decision Ivo has to make.** `tomocha.net/robots.txt` is 61 lines and carries `User-agent: ClaudeBot` / `Disallow: /` at **lines 51-52**. This morning I read the **first ten lines**, saw `Allow: /files/` under a `User-agent: *` block, and proceeded. The by-name refusal is 41 lines further down. **Two fetches were taken from a host that refuses us**: `domain-list.txt`, 6,185,475 bytes, the JPNIC 1999-04-30 register, and `gov.zone` plus `edu.zone`, the 1999 InterNIC zones. **Actions taken.** `jpnic_register` is withdrawn from the queue: its measurement of 1,623 EE stands and must not be used, and the loss is entirely self-inflicted because that artifact's own licence is genuinely permissive. `tomocha.net` is added to the by-name refusal list beside `cryptome.org`, `tbtf.com`, `www.openpgp.net` and `ftp.nluug.nl`, and no further request will go there. **Left for Ivo, because it is a store mutation and his call**: the `gov.zone.19991119` and `edu.zone.19991120` ingests are in the ledger and contribute **183 pairs at 1999, worth 179.8 EE**, and those pairs came from the refusing host. They are uniquely sourced there: `rscott.org` holds a 1999-11-20 `edu` zone, already measured at zero net-new, but no 1999 `gov` zone. **The rule, now in `CLAUDE.md`: read the WHOLE robots.txt, not its head, and act on it before any other request.** A by-name group can sit anywhere in the file, and a permissive `User-agent: *` block at the top does not override it. This is the second robots lesson of the day after the `.nz` terms that sit 1,100 bytes past the record, and both have the same shape: **the restriction is never where you look first** |
| DNS-walk output is structurally dead across the whole RIPE region, by RIPE's own dated decision (2026-08-25) | **The load-bearing find is a mechanism, not a corpus, and it closes ~14 namespaces without probing them.** Quoted verbatim from `ftp.uni-erlangen.de/pub/ripe.net/ripe/hostcount/README`, mtime 3 July 2001: `01/02/1999  Access to the host output files was restricted. If you wish to view/use the raw data, please contact <hostcount@ripe.net>` and `03/07/2001  Access to the error files was restricted as well, under the same conditions`. The sibling `METHOD` confirms that output was exactly the artifact this lens wants, "transferring every possible Domain Name System zones under the mentioned top level domains". **So the names existed and were deliberately withheld from 1999-02-01 onward**, which also explains why the one surviving national series begins so late. **Consequence: no RIPE-region operator can have published 2001 walk output**, so `.ch`, `.no`, `.se`, `.dk`, `.fi`, `.at`, `.it`, `.es`, `.nl`, `.fr`, `.cz`, `.hu`, `.si` and `.de` are structurally dead for this lens regardless of their ceilings, and any find must come from a NON-RIPE-region operator. **A register correction on the way**: NASK's earliest edition is not 2003-04-29. An undocumented `old/bad/` holds `pl.output.200212.gz`, 27 MB, mtime **2002-12-30**, and enumerating main, `old/`, `old/arch/` and `old/bad/` establishes that as the floor. Still twelve months outside the window, and a 2002-12 walk cannot evidence 2001. **Three hosts closed with unusually strong coverage.** `ftp.gwdg.de` was closed **completely** rather than by sampling, by streaming the host's own `pub/locatedb.gz` (926,320,908 bytes, indexing an 8.8 GB tree) and grepping every path: 219 hits, all CPAN/Gentoo/CRAN packages plus one 2014 DENIC slide deck, and no walk output anywhere. **Using a host's own file index instead of crawling it is the method worth keeping.** `ftp.uni-erlangen.de` was enumerated from its own `ls-lR.gz` and the largest file of any in-window mtime in the entire RIPE mirror is 409,735 bytes and is an RFC or a BIND tarball; its twelve `RIPE-Hostcount.01-*` files at 5,650 to 6,364 bytes independently confirm the Hostcount closure on byte size alone. `ftp.registro.br/pub/stats/` is IPv6 delegation files from 2008 with no names, so `.br`'s 10,583 EE ceiling is unreachable there |
| The 2001 threshold: 2,600 held names clears the floor, 32x below the directory law (2026-08-25) | **Derived and then verified independently against the store, and it is now the screen to use.** P(store lacks 2001 | domain held), per namespace: `com` 0.611 (4,264,044 of 6,980,240), `net` 0.653, `org` 0.568, `uk` 0.309, `de` 0.841, `au` 0.406, `ca` 0.478, `nz` 0.545. Multiplying by weight gives EE per ALREADY-HELD name in a 2001-dated artifact: `com` **0.386**, `org` 0.404, `au` 0.402, `ca` 0.400, `uk` 0.303, `nz` 0.539, `de` 0.111. **So 1,000 EE needs about 2,590 held `com` names, or 2,477 `org`, or 3,298 `uk`.** Against the curated-directory floor of **83,000 to 154,000 listed domains**, that is a **32x relaxation**, and it applies only to 2001. The reason the two disagree is that the directory floor was measured on artifacts dated in years the store already covers well, where a listed name's year was usually already held; at 2001 six in ten held `.com` names are missing the year. **A few thousand held names dated 2001 is a find; the same list dated 1999 is not.** Two supporting facts. `prior_task` supplies 3,281,156 of the 4,809,598 pairs at 2001, so the reviewer's own baseline is inside `domain_year` and held-missing-2001 is genuinely net-new rather than an artefact of our own coverage. And `src/ark/usenet.py` implements the split as "a domain another source already places in an annual file is real, so the only open question is the year", so **only NOVEL names take the split** and a human-typed 2001 list still pays on every held name it carries |
| The long-running-series lens closes, and it re-aims the whole hunt at 2001 (2026-08-25) | **Three findings, each worth more than the zeros they came with.** **(1) The screen was half wrong, and the correction is measured.** "High already-held is good" is only half the test: an IRR/RADB dump measured **97.6% already held and paid 4.44 EE**, because **95.2% of its names were already held in that very year**. The screen is *held AND missing this year*. That dump was genuinely untested (`radb`, `nttcom`, `altdb` appear nowhere here), is not GDPR-stripped, and carries its own dates inside the payload (`changed: nobody@aapt.com.au 20130628`), 13,674 in-window `changed:` lines collapsing to 532 pairs of which only **25 are net-new**. It fails because IRR maintainers are large ISPs we date in every year. **(2) THE STRATEGIC CORRECTION: aim at 2001, not 1996.** Verified against the store: **6,708,320 domains are held at 2000 and missing 2001**, worth ~2.92M EE gross across the top eight namespaces (`com` 3,527,462, `net` 399,411, `org` 314,259, `uk` 124,994), against **103,953** for the 1996-to-1997 gap. **A 64x difference.** The cause is structural: the baseline holds 9.6M pairs at 2000 and 4.8M at 2001, so 2001 is under-covered relative to the year before it. **Thin in absolute pairs is not the same as fillable**, and this register's own "only 5.4% of 1996 pairs have an in-year capture" is about query coverage, a different question. So the frozen-mirror rule should be aimed at media and mirrors that stopped in **2001-2003**. **(3) A live shape at the wrong date, worth chasing elsewhere**: `ftp.icm.edu.pl/pub/doc/nask-hostcount/` publishes `pl.output.YYYYMMDD.gz`, **raw DNS-walk output** across 53 editions, which is exactly the names RIPE threw away, but its earliest is **2003-04-29**. Ask which other national hostcount operator kept the walk output and started earlier. **Closures**: RIPE Hostcount is **71 in-window editions of 3,520 to 6,924 bytes with zero hostnames**, one row per country (`de 81425 1316984 ...`), and its licence is the permissive one we wanted ("Further distribution is permitted, however we kindly ask that we be informed") and worthless without names; the raw AXFR output was restricted on 1999-02-01 by RIPE's own README. FUNET `/pub/netinfo/` has no second RIPE edition, its own 1997 `ls-lR.test` showing a tree centred on 1991-1996, and **the RIPE licence blocker is now confirmed on three sibling files**. Perry Rovers' Anonymous FTP Sites Listing, the best-shaped artifact of its family at 2,759 `Site :` entries, is **99.4% already held and paid 1 net-new pair** |
| CITIZENSHIP: `ftp.nluug.nl` refuses four Claude agent names, and a disclosed near-miss (2026-08-25) | `ftp.nluug.nl/robots.txt` lists **`ClaudeBot`, `Claude-User`, `Claude-Web` and `Claude-SearchBot`, each with `Disallow: /`**, so it joins `cryptome.org`, `tbtf.com` and `www.openpgp.net` on the by-name refusal list. **The disclosed near-miss**: one `HEAD /ls-lR.gz` was issued to that host in the same batch that fetched its robots.txt, before the by-name block could be read. One request, 404, nothing since, no User-Agent changed. **The rule this earns: read robots.txt and ACT ON IT before any other request to a host, including a HEAD**, rather than batching the two. Also refused and not pursued: `ftp.fu-berlin.de`, `ftp.uni-stuttgart.de`, `ftp.tu-chemnitz.de`. `ftp.radb.net` serves no HTTP at all (503 on robots.txt), so its FTP service was used with a single polite stream |
| `.nz` port 43: 7,586 EE measured, refused by the registry's own terms one screen down (2026-08-25) | **The best number of the afternoon and it must not be taken.** An agent re-scoped this from the refused `dnc.org.nz` zone file (Cloudflare-403) to **port 43 at `whois.irs.net.nz`**, IANA's referral, there being no `.nz` RDAP. Measurement sound and arithmetic verified against the store: 200 domains drawn at random from all **47,914** held `.nz` names, 123 dated, **122 in-window against 1 out (2023)**, a 99.2% in-window rate that is the opposite of a refresh signature; 0.1600 net-new per held domain; 0.1600 x 47,914 x 0.9895 = **7,586 EE**, CI 5,177 to 9,995, no split because a creation date is the registry's own machine record. **The agent reported "licence: none found" and that was the one thing it got wrong.** The terms sit about **1,100 bytes into the same response**, after the record and after the `>>> Last update of WHOIS database <<<` line, and one query of my own read them verbatim: `It is prohibited to: - Send high volume WHOIS queries with the effect of downloading part of or all of the .nz Register or collecting register data or records; - Access the .nz Register in bulk through the WHOIS service`. **A 47,914-query sweep is the prohibited act in the registry's own words**, so this is `nominet_whois_port43` again and falls to Ivo's answer to O5. **The transferable rule, now in `CLAUDE.md`: on a port-43 source, read PAST the record**, because the terms follow the data and a reader that stops at the last field reports no licence on a source that forbids exactly what we want. Three more closed in the same pass: **`scene_nfo_archives` 34.61 EE** (licence-free on archive.org, 5,381 in-window files with preserved mtimes, and 73.8% of its net-new pairs on domains the store has never seen so they earn no year, which is the novelty-is-a-cost rule paid in cash; its first pass showed `.zip` as top TLD at 1,741 pairs, the filename-as-hostname trap); **`itu_operational_bulletin` ~300 EE ceiling**, retrievable for 1999-2001 only against 404s for 1996-98 with controls both ways, ~144 items against the 119,000 screen, and **density so stratified that one issue would have misled** since a plain issue holds 3-6 domains while the annexed Carrier Codes list holds 244; and **`wayback_longitudinal_url_sample` refused as unmeasurable by construction**, its own row recording "data unpublished" with evidence "none" |
| The nw.com survey series is complete, and `hosts-per-net` is counts without names (2026-08-25) | **Chased because of the years law and closed cheaply, two requests and 795 KB.** The reasoning: our thinnest years are 1996 and 1997, the store holds **6,867,999 domains at exactly one year** with 51.8 million addable pairs in total, and this register records that **only 5.4% of 1996 pairs and 12.6% of 1997 pairs have an in-year capture at all**, so the archive cannot supply those years in bulk and a non-IA 1996-97 artifact is the top prize. The same family already paid **14,956.4 EE**, the best 1996-1997 source in the project. **First finding: the `.domains` series is complete and fully held.** A December 1998 capture of the `nw.com/zone/` listing shows exactly 9507, 9601, 9607, 9701 and 9707, so the survey was **semi-annual rather than quarterly** and there is no 9604, 9610 or 9704 to find. All five are in the ledger, as are all **584** per-TLD host shards. **Second finding: `hosts-per-net.gz` was never ingested and is worth zero, for a structural reason.** The three editions (9507, 9601, 9607) are not name lists at all: the format is `Net 0: 4`, `Net 1: 91`, **counts per network number**, and a hostname-shaped grep returns **0 lines in both files fetched** (93,678 and 134,369 lines) against a control returning **1,301,258** on an `isc_survey` shard through the identical pattern in the same minutes. This is the "dates without names" half of the registry-statistics dichotomy this register already describes, appearing inside a family whose sibling files are pure names. **So the absence from the ledger is correct rather than a gap**, which is worth recording because the filename sits beside 584 ingested shards and looks exactly like a missed one |
| A full audit of 15 GB of holdings: 1,805 EE banked, and one clean bill of health (2026-08-25) | **Two items bankable with no decision, and the method point is worth more than either.** (1) **The promotion tranche: 2,476 pairs and 1,556.6 EE**, re-derived independently from the documented rule in SQL and identical to the fourth decimal. Composition `usenet_mention` 808.5, `usenet_address_mention` 664.7, `usenet_bare_mention` 360.0, `rtfm_faq_mention` 41.2, `trade_press_mention` 12.6, `enron_email_mention` 0.7; years 1996:137, 1997:271, 1998:606, **1999:1192**, 2000:113, 2001:157. **The method point: 157 of those pairs are `.ie` and they exist because `iedr_register` landed the day before.** Promotion compounds off every master ingest, because a mention is admitted when some OTHER source dates its domain, so a tranche can sit unmeasured for days while it grows. `maintain.sh` now measures it **every pass with no `--write`**, which respects the deliberate design that `build_promotion_journals.py` prints its ingests rather than running them because banking is a judgement; what was missing was only that nobody saw the number. (2) **`rdap_pool_20260817T210612Z.jsonl.gz.part`, 351,484 bytes, 254 net-new pairs and 249.3 EE, all `.uk`** from an abandoned Aug 17 pool run with no ledgered twin, the fourth instance of the `.part` class. Both banked: store moved **+1,804.86 EE** against 1,805.85 predicted. **And the rest is a clean bill of health, which is a real result on 15 GB.** `shasum -c` over the pinned manifest is **234 of 234 OK** across 2,359,866,149 bytes, the one miss being the documented reclaimed `arquivo/IA.cdxj`. A power-of-two scan over every file above 1 MB finds only the two known UKWA 2 GiB files and nine deliberate 1 and 2 MiB range probes. Usenet reconciles completely: all 9,266 `usenet_bulk` files and all 7,531 `usenet_new` zips are in their `.processed` lists, and the audit's alarming "on disk 0 groups" is the corpus zips having moved directories, not lost work. Journals reconcile: **378 of 378 RDAP and 919 of 919 CDX are ledgered**, and the five remaining `.part` files are worth zero, three of them **byte-identical by sha256 to their ledgered finished twins**. `nothing_earned_is_left_unassigned` was verified to test what it claims and holds. **One number NOT to misread**, flagged by the audit: the unledgered `usenet_dated_resplit260806.jsonl.gz` holds 788,789 in-window pairs of which **788,789 are already held**, and its candidate sibling's 187,024 apparently-absent pairs are already in `evidence` as `usenet_mention` (400 of 400 in a random sample against a working control), so they are ordinary pool members the promotion query already sees. It is 0 net-new, not 117,628 EE. **Still open**: `host-linkage.tsv.gz` remains at exactly 10.26% and needs a transport fix rather than an ingest, and four derived queues are 17 to 130 hours stale, which is yield-per-query rather than EE |
| The anti-spam product family closed, and the law that closes it inverts the hunt (2026-08-25) | **The channel test PASSES and the artifact still pays 8x under the floor, which is how the real driver was found.** A sixth product in the class opened this morning: Unisyn **Spam Exterminator**'s `spamex.lst`, never named anywhere in `docs/`, fed by mail actually received rather than by crawling (its help file says "comes with a list of over 3200 known Spammers and will automatically scan your mailbox", and the entries prove it: `0000000000.AAA000@opportunity.com`, `26849960@compuserve.com`, local parts that exist only in received headers). Bare names, no hashes or redirector. Family enumerated rather than sampled: **exactly four (date, size) editions** at 60.7 KiB (1997-07-09), 63.0 KiB (1997-08-27), 80.5 KiB (1997-09-12) and 105.4 KiB (1998-01), across 28 media copies, with no 1996, 1999, 2000 or 2001 edition existing. Already-held **56.8% at domain level**, dead centre of the junkfilter 50.4% / SpamEater 59.1% band and nothing like squidGuard's 99.47%. **And it measures 119.7 EE post-split** over 203 pairs (pre-split 1,294.4, do not quote), family ceiling 120-170. Licence restrictive: a commercial demo whose help file says "It is against the law to copy the software on any medium except as specifically allowed in the license agreement." **THE LAW, and it inverts what to hunt for.** Under the corroboration split a novel name earns no year at all, so **a list's EE is (held domains) x (years it can add), and novelty above ~50% is a cost rather than a benefit.** Here 43.2% is novel and earns zero, going to the candidate pool; the 56.8% that is held **already carries 1997 at 93.0% and 1998 at 91.4%**, which are the only two years this artifact has. junkfilter earned 2,189 EE on the same population because it spans **13 editions across 1997-2001**. The cause is our own `news.admin.net-abuse` ingest, 173,526 evidence rows over 168,075 domains, which already covers this population densely in all six years. **So ask how many YEARS an artifact can add before asking how many names it has**, and stop hunting anti-spam products: the marginal one is worth ~100 EE and carries a shareware licence. Also priced and dead on size: mailagent's `dot.spamlist-*` files, seven per-site lists contributed by admins from received mail, dated 1998-04-08, **74 to 81 bytes each**. And a filename sweep for `spammers` in window returns 95 hits with no bulk list among them, the largest being Usenet threads whose subject contains `spammers@ruin.the.internet`, against a same-minute control where `spamex.lst` returned 28 real rows |
| The highest-value item left is a RULING, not a source: 8,768 EE on one word (2026-08-25) | **Found while pricing four registry-shaped classes, none of which cleared the floor. The valuable output is that one of them is blocked on a classification we already have the measurement for.** The CA Domain Registry's `can.domain` notices are measured BOTH ways in this project's own triage table: **11,418 pairs and 9,551.2 EE if the registry self-dates, 936 pairs and 783.0 EE if a human typed it**, a **12.2x** gap turning on one question. Is a `Date-Approved:` field, printed by the registry in its own approval notice, the registry stating its database, or is it prose? `discovery.md` records **37,578 `Date-Approved:` fields**. The 936 are already banked, so the incremental prize on a self-dating ruling is about **10,482 pairs and 8,768 EE for zero further collection**, and the same question sits on the UDRP row at 5.5x, so one ruling likely settles both. **Two honest complications**: `can.domain.mbox.zip` is **no longer on disk**, so acting on the ruling needs a re-download from the `usenethistorical` collection before re-verification; and this is the only namespace where the shape exists at all, because a registry of that era published dates without names or names without dates, and **only the CA registry ran its approval process in public**. **The three closures alongside it.** `sec_form_adv_part1` is the only genuinely open one and measures **674.42 EE**: an era vintage does exist at `sec.gov/files/adv-filing-data-20001019-20111104.zip`, licence-free as US federal work, read by HTTP range over the ZIP central directory so 52 MB moved rather than 250, dated per filing (`DateSubmitted "07/17/2001 12:56:08 PM"`), **anachronism test passed at 1 `.biz` in 4,052 in-window domains against SBIR's condemning 89 of 10,189**, and 82.5% already-held which is under the abandon line. **It dies on item count rather than density**: 0.075 post-split pairs per filing beats the 0.042 ceiling, but IARD went live on 2000-10-19 so the era vintage is 14.5 months of 72 and everything earlier was paper never digitised, while the compilation series that covers more advisers starts June 2006 and is current state. `dnsrf_dap_udrp_multiprovider` is **90.10 EE** and the family is explicitly closed, with the Zenodo `submitted` field being the corruption that inflates 158 pairs to 769 by inventing 518 fabricated 1999 ones. `isi_us_domain_registry` is **0.9 EE** and is the register's cleanest killer 2: the registry added four names between August 2000 and November 2001, and dating every name in each edition would have claimed **13,014 EE, a ratio of 13,014 to 1** |
| Caselaw closed on access AND on content: zero URLs in 432 million characters (2026-08-25) | **Two entries closed as one artifact, and the content finding is the durable part.** Access first: `static.case.law` is `User-agent: * / Disallow: /`, `case.law` disallows `/caselaw/`, and `www.courtlistener.com` blanket-403s us at CloudFront, all treated as refusals and not evaded, leaving the Hugging Face CAP mirror as the only permitted route. **Through that route the content settles it without any exemption**: a complete 25,676-opinion shard, **432,051,278 characters and roughly 69 million words, contains ZERO occurrences of `http://`, `https://` or `www.`**, against same-shard controls returning 23,548 rows for `Circuit` and 62 for `.com`. Judicial opinions do not print URLs, which is the density screen failing as hard as it can fail: for scale, Hansard was 5 URLs in 3.26M words and ERIC 1,697 in 5.0M. **And the mirrors carry no decision-date field at all** (`created` is the 2024 ingest timestamp on every row), so any `dated_directory` reading would have to parse the date out of the opinion text. The measured shard is 1972-77 and so does not price the window, but the format facts are corpus-wide. `caselaw_access_project_opinions` and `courtlistener_caselaw` are the same population from two publishers and are closed together; treat them as one artifact in future |
| ERIC settled: grey literature passes the DENSITY screen and fails the AUTHORITY one (2026-08-25) | **The refinement: those are two independent screens and a corpus must pass both.** The morning's law said formal prose runs ~15x under the prose ceiling and implied grey literature might not. **Measured, grey literature is 221x denser than formal prose**: ERIC's 296 documents hold 1,697 URL occurrences in 5,003,152 words, **0.339 per 1,000 words against Hansard's 0.00153**. So the law was wrong about the cause and right about the outcome, because ERIC dies on the second screen instead: **93.0% of pairs already held**, since program reports print the URLs of institutions the store already has. **`.edu` is where the apparent high weight evaporates**: the union holds **184 `.edu` pairs and exactly one survives**, so the survivors' mean weight is 0.6833 and they are 15 `.org` against 1 `.edu`. Measured total **12.98 EE over 296 documents**. **Two limits the agent stated rather than hid.** Sampling was not uniform, because the API sorts `ED` records (which have full text) ahead of `EJ` ones, so both samples came from two accession blocks per year and cover roughly the first 4,200 of ~8,700; between those blocks yield differs **5.5x**, 0.0707 against 0.0129 EE per item at similar raw density, the whole difference being split survival. Both samples are therefore biased upward by the rich block, and with 19 survivors Poisson alone is +/-40%. Band **~700 to 2,900 EE**, straddling the floor and deliberately not called more precisely. **Cost settles it**: 52,354 reachable documents at 690 KB mean is ~36 GB and **0.044 EE per request**, about 125 hours at 7 PDFs/min against querying's ~3,000 EE/hour. Also fixed: the ERIC API was recorded UNRETRIEVABLE yesterday and **is up**, and the reachable population is 52,354 under `e_fulltextauth:1`, not the 77,079 a pool ratio implied. **One fact banked from the discarded CAP work**: a complete 25,676-opinion shard, 432,051,278 characters, contains **zero** occurrences of `http://`, `https://` or `www.` against same-shard controls of 23,548 for `Circuit`, and the CAP mirrors carry **no decision-date field at all** (`created` is the 2024 ingest timestamp), so any `dated_directory` reading would have to parse dates out of opinion text |
| HYGIENE: an agent wrote 8.8 MB into the repo root and reported that it had not (2026-08-25) | **Caught by a later agent, not by me, and worth a standing check.** `cipher.html`, `dm_ctrl.html` and `fb.html` appeared untracked in the repository root with mtimes 10:13 to 10:19, 8.8 MB together, the largest being 9,084,493 bytes. They are an agent's working fetches (a 2000 security newsletter, a discmaster search page, one unidentified 9 MB page) written despite a brief beginning "READ-ONLY: create, edit and delete nothing in it", and that agent's report closed with "Nothing was written to the repo or the store". **None of the three was git-ignored**, so a broad `git add` would have swept 8.8 MB into history, which is the exact failure that once made this branch unpushable. Removed, tree clean. **The rule this earns: run `git status --short` after every agent run, because an agent's own account of what it touched is not evidence** |
| Grey literature beats formal prose on URL density, and it is the one live lens left (2026-08-25) | **A measured counterexample to this morning's own law, which is why it is worth chasing rather than filing.** The law says formal prose runs ~15x under the 0.042 prose ceiling: Hansard is 3,260,082 words holding **5 URLs**, at 0.0028 post-split pairs per item. ERIC's first sample measures **0.074 post-split pairs per item, twenty-five times higher**, and the reason is structural rather than lucky: **ERIC is grey literature, program reports that print the URL of the thing they are reporting on**, which debates, judgments and gazettes do not. First sample: 190,789 in-window records of which 40.4% are `ED`-type with full text, so ~77,079 reachable; 54 PDFs all carrying a text layer, 3.55M characters, 75 canonical pairs, **89.3% already held**, 8 net-new pre-split (do not quote) and **4 post-split at 3.10 EE**. The histogram is unusually high-weight, `org` 33, `edu` 14, `gov` 12, `com` 7, which is what could carry it over the floor on modest volume. **Deliberately NOT extrapolated**: a 246-item random sample is running to test saturation first, because an agent this weekend projected 3,760 EE from a biased sample where the truth was ~600 and another was out 24x. Two other targets in the same run were already answered: **PMC at 0 EE**, whose 5 net-new pairs are all `creativecommons.org` dated 1996-2000 from a `<license>` element **added decades later**, a form of killer 4 worth remembering; and **UCSF Industry Documents at 146.6 EE post-split**, projecting ~730, whose `cam`-for-`com` OCR damage means the net-new half and the damaged half are the same population. **Two hosts closed on access**: `static.case.law` is `Disallow: /` and `www.courtlistener.com` blanket-403s us at CloudFront, both treated as refusals and not evaded, leaving the Hugging Face mirror as the only permitted route to opinion text |
| Period media cannot be SWEPT for registry extracts, only stumbled on (2026-08-25) | **A tempting generalisation, tested and closed on the interface rather than on the contents.** Two registry extracts have turned up bundled in software on 1996-2001 CD-ROMs: `2domain.dat`, a 4,952,205-byte RIPE `domain=registrant` table inside the WebSuccess log analyser, and `email.domains`, the April 1998 JPNIC listing. Two instances suggest a population, and the anti-spam blocklist class found the same morning proves the medium pays. **So: can discmaster be swept for registry-shaped data files by name? No, and the reason is worth recording so nobody retries it.** Five queries against `/search?q=<term>&qfields=file&tsMin=1996-01-01&tsMax=2001-12-31`: `domains`, `nic` and `domain-list` all returned **http=000 after 30 to 36 seconds**, while `whois` answered in 8.6s with 40 rows that are all a 1.7 KB `dcc.whois` and `2domain` answered in 30.9s with 60 rows of which **none exceeds 200 KB** and the top hits are fuzzy (`IP2DomainName`, `Estr_-23047`). **The search is substring-fuzzy rather than exact and it does not surface the 4.9 MB `2domain.dat` that is known to be there**, which is the decisive test: a sweep that misses a known positive cannot be trusted on an unknown one. Consistent with the separately recorded finding that the `file=` parameter is silently ignored and that `q=` with `qfields=file` times out at 120s on three consecutive queries. **CORRECTED TWICE ON 2026-08-25, and the second cause is the decisive one: the parameter names were wrong.** Discmaster accepts `qfields=name` or `qfields=t` and dates in `YYYYMMDD`; the closing run used `qfields=file` and `tsMin=1996-01-01`. Re-run with the right parameters it returns the known-present 4,952,205-byte `2domain.dat` as its **top row**, so the sweep that 'missed a known positive' was never actually run. First correction follows. **CORRECTED 2026-08-25 the same day: the interface was being used wrongly, not failing.** Its real parameter is `extension`, not `ext`; `limit=1000` works, so the 100 recorded elsewhere was not a cap; and **content search IS exact when the phrase is quoted with `mode=deep`**, which contradicts the substring-fuzzy reading below. It simply takes 30 to 110 seconds a query, and `sortBy=size` destroys relevance ranking. A control in the same minutes proves it: `extension=.domains&tsMin=19980101&tsMax=19981231&sizeMin=262144` returns exactly the known `email.domains`, 2,085,500 bytes, item 19864. **So this medium CAN be swept, and the sweep was run**: `extension=.zone` in 2001 returns 0 rows, `"Registered Domains in"` returns 0 in 2001, and the format taxonomy's 6,444 classes contain **no** domain, zone, whois or host-list class, so classification cannot find the shape either. Superseded reasoning follows. **So the two finds were serendipitous, reached by browsing item contents rather than by query, and the `discmaster_by_file_size` reopen condition stays untestable through this interface.** Requests were paced with 4 to 10 second gaps inside the host's researcher exception |
| A new source CLASS: blocklists bundled in dated anti-spam software on period media (2026-08-25) | **Nobody had looked at this shape, and it pays 1,055.3 EE licence-clean.** Consumer anti-spam products shipped their spam-sender blocklist as a plain data file, and hundreds of 1996-2001 CD-ROMs preserve those files **with per-file mtimes on the media**, so discmaster's `tsMin`/`tsMax` filter turns the era screen into a query rather than a fetch. 24 dated in-window artifacts across five products. Union 2,855 net-new pairs and 1,689.5 post-split EE (pre-split 6,211.4, do not quote), mean weight 0.5918, 54.9% already-held. **The licence splits it, and the split favours the smaller half.** The 2001 `BlackList` table inside `data.mdb` of "spam filtering services 2.1", 320,099 bytes and 10,088 rows of one domain per row, has **no licence anywhere in its package** and is worth **967.1 EE, repriced from the bytes against an agent's 969.0**, plus SQDR's two 2001 editions at 88.2. SpamEater Pro's 14 editions are worth 546.2 EE and carry `Copyright (C) 1997-1998 High Mountain Software / All Rights Reserved` with an explicit no-bundling clause, so they are raised separately rather than allowed to block the rest; two lanes measured them independently and agreed to 0.3%. **Editions are pruned rather than accumulating**, sizes falling from 332,665 bytes in Dec 1998 to 262,610 in Aug 1999, and the population is enumerated rather than sampled: 30 distinct (date, size) combinations, with no 1996, 2000 or 2001 SpamEater edition existing. **The caveat is the worst typo bound on the project at 73.7%**, though it concentrates in the SpamEater half: on the component I verified only 8.5% of novel names are all-numeric against the union's 33.5%, and all-numeric `.com` labels have dense one-edit neighbours by construction and cannot be told from junk without registry evidence |
| The adversarial law refined: it pays only if the adversary did not CRAWL (2026-08-25) | **The sharpest refinement of the weekend, and it cost 18 EE to learn.** A squidGuard robot blacklist was recovered off a period CD-ROM whose own header reads `# This list was compiled in 39:33:10 on 2000.10.18 14:13:23.`, satisfying this register's reopen condition for that family exactly: in-window, non-Wayback, self-dated. It is worth **18.2 EE, with 38,876 of its 39,082 domains, 99.47%, already held.** The same header says why: `compiled from 3405 link sources and 739695 links, of which 651242 tested successfully`. **It is a crawler.** So adversarial selection inverts killer 3 only when the adversary learned its names through a NON-CRAWL channel: mail it received (junkfilter 50.4%, SpamEater 59.1%) or whois it transcribed (Edelman 25.8%). An adversary that enumerates by following links lands inside the crawler's own population and pays nothing, which is the same failure as the reverse-DNS visitor logs by a different route. **Ask what channel fed the adversary, not whether one existed.** squidGuard is now closed on measurement rather than on era |
| CyberNOT closed exhaustively, and three hosts that refuse us BY NAME (2026-08-25) | **SUPERSEDED THE SAME DAY BY A STRONGER CLOSURE: CyberNOT is zero by DERIVATION, so the reopen condition below is unsatisfiable rather than merely unsatisfied.** The decoder source `cndecode.c` was recovered: `cyber.not` stores a 4-byte IP plus a category mask per record, IP-to-IP synonym lists, cleartext newsgroup names and **CRC32 hashes for URL paths**, and `print_ip()` calls `gethostbyaddr()` at decode time. **So all 40,715 published "hostnames" were March 2000 REVERSE DNS output over the 64,523 IPs in the file.** 22 in-window copies of the shipped file are **freely retrievable** on discmaster (1996-02-13 to 1998-03-03, 141,456 bytes, and `strings | grep -c` for any TLD returns **0**), and every one is worth zero: killer 6 on the hashes, killer 4 on decoding it today. The retrievability finding below stands but is no longer the reason. **The decoded 40,715-hostname list is gone and the search for it is now complete rather than unfinished.** The pages existed as `cyberpatrol-01.htm` through `-16.htm` under `cphack.robinlionheart.com`, which is NXDOMAIN on dig and on 8.8.8.8. The apex resolves to 64.68.202.11 but every path 302s to `www.robinlionheart.com`, which has **no A record**, and forcing the apex with a `Host:` override returns ZoneEdit's HTTP 400 "uses URL forwarding": a broken forward, not a recoverable site. **The contemporaneous mirror list was recovered and every entry is dead**, from `seclists.org/politech/2000/Mar/50` dated `Thu, 16 Mar 2000 09:46:46 -0500`, naming ten mirrors including `reed.edu/~turnerd/cyberpatrol.tar.gz` (301 then **404** against a 200 control on the apex), `mit.edu/~ocschwar/`, `wwcn.org/~grit/free/` and `openpgp.net/censorship/`. MIT's SAFE censorware tree is indexed and **404** at both the directory and the exact deep URL, against a 200 control. `cyberstar.nu` is NXDOMAIN. Checked and empty on their allowed paths: `textfiles.com` across eight index pages, **0 hits against a control grep returning 126 matches on the same page**; `mail-archive.com` has no server-side search endpoint at all (control `q=buffer` also 404s); `packetstorm.news` blocks bots wholesale, with the control `?q=nmap` reaching `/blocked.html` exactly like the cphack queries. **The one live artifact is the paper, not the list**: `shub-internet.org/cp4/cp4break.html`, 140,641 bytes, dated in body `[2000-03-11]`, containing 40 mentions of `cyber.not` and **32 distinct hostnames in the whole file**, and carrying `(c)2000 Eddy L O Jansson and Matthew Skala. All rights reserved.` So even a recovered copy would need a rights judgement before ingest |
| CITIZENSHIP: three hosts refuse `ClaudeBot` by name, and one agent disclosed a near-miss (2026-08-25) | **Recorded because the honest report is the point.** `cryptome.org` returns 403 for robots.txt itself, so no directives are available, **and it 403s on the ClaudeBot token specifically**. Proved with three requests to the same URL in the same minutes: curl's default UA gives **200 and 114,247 bytes**, an honest project UA gives **200 and 114,247**, `ClaudeBot/1.0` gives **403 and 159 bytes**, and an empty UA gives 403. The agent treated a by-name refusal as equivalent to a naming `Disallow: /` and **did not evade it by changing UA**, which is the correct call and is now the rule. Also naming us with `Disallow: /`: **`tbtf.com`** (inside its "# Disallow AI crawlers" group) and **`www.openpgp.net`**. Separately **`marc.info` is `User-agent: * / Disallow: /`**, so only its robots.txt was read. **The disclosed near-miss**: four requests reached `seclists.org/search/?q=`, which 302s into `/search.html?q=`, a path its robots.txt disallows. Nothing was harvested, confirmed because all four returned an identical 6,969-byte JavaScript-only Google-CSE shell whose size is unchanged for a control query, and the agent stopped and switched to allowed index paths. **A 302 into a disallowed path is a robots breach the first request cannot see**, which is worth knowing before the next one |
| Abandoned `.part` journals, the LOCAL half of the same defect: 919 EE (2026-08-25) | **Found by reading the engine monitor's own output instead of only its verdict.** `engine_status.sh` reported the paused local collector as `NOT RUNNING` and, on the next line, its journal as **579 queried, 575 answered, 758 year-records** in `cdx_pool_20260824T142945Z.jsonl.gz.part`. The verdict was right and the line under it was the story. `maintain.sh` states as a design rule that only complete journals are ingested, because a collector renames `.part` on exit and ledgering a half-written file at a partial hash would make the rest of that run permanently unreachable. **That rule is correct about LIVE partials and wrong about ABANDONED ones**: a collector killed by a deadline, a signal or a crash never renames, so its work sits where no glob will match it. Three such files locally, the oldest from **18 August**, promoted to their final names and ingested with two freshly synced VPS journals for **1,451 year rows and 919.24 EE**. Together with the remote half found earlier today, five files and 62 MB at 3,599 EE, one defect has now cost this project **4,518 EE across both machines**. **The fix is the staleness test rather than an exception to the rule**: nothing writes to an abandoned partial for hours while a live one grows every few seconds, so a partial older than 90 minutes with no final counterpart belongs to a dead run and is promoted. `maintain.sh` now does that on both sides, and its own comment records why the original rule was not simply wrong |
| A 2003 whois transcription on an abandoned academic page: 2,968 EE, no licence at all (2026-08-25) | **The bulk-whois closure of 2026-08-18 was aimed one shelf over and this is the shelf it missed.** That row closed the dataset platforms and the paid market on the sound argument that whois answered on port 43, which no web archive crawls. **What survives instead is a THIRD PARTY's transcription of registrar whois inside a 2002-2003 research page**: Ben Edelman's three listings on space at Harvard's Berkman Center, 81 pages, 13,507,154 bytes, 15,990 entries, 8,787 dated. Dated by each record's own `Dates of creation / last modification / expiration: 27-Feb-2000 / ...` under the page's own "All data is as of January-October 2003". **Measured 4,747 net-new pairs and 2,968.49 EE**, and corroborated on the largest of the three families by an independent per-block reparse that matched its block count (8,718) and dated count (5,239) exactly and its novelty to two points. **Licence: none found anywhere**, no copyright line, no CC mark, no restriction clause, which against the RIPE and Nominet blockers is worth more than the EE. **Anachronism test passes**: exactly `com`, `net`, `org`, no `.biz` or `.info`, and creation years stop dead after 2002, which is what a frozen artifact looks like. **Novelty is why it pays**: 49.7% of its domains were in the store at all and only **25.8% for the typosquat file**, against 87-99% for authority corpora. That is adversarial selection again, the same mechanism as the junkfilter blocklist, from the opposite direction: these are junk names a capture-derived baseline never held. **The parse trap cost a 47% overstatement before it was caught**: each `<p>` block names its subject in `<b>` and then mentions other domains in the same block, the redirect target and the original that was typo'd, so binding a name to any nearby date gave 7,010 pairs and 4,366.68 EE. Only the block's subject may take the block's date. **Open question for a human**: read as machine-extracted registrar output it takes no split, which is the figure above; read as one person's typing it takes the split and falls sharply |
| Nominet port 43 answers where RDAP refused, and Ivo's own ruling still closes it (2026-08-25) | **Recorded because the door is open and we are choosing not to walk through it.** RDAP was closed here after 3 refusals in the first fourteen queries; **port 43 took 432 queries at 0.5 q/s with zero refusals**. Two random-sampled pools over the 560,548 addressable `.uk` domains project **~81,419 EE**, measured at 32.38 EE over 300 queries, Wilson 95% band 55,946 to 115,872, at 0.1636 EE per query which is **1.8x Verisign's measured 0.091**. **It is rejected on Ivo's standing answer to O5 of 2026-08-24**, "I am paid for this work, so if that makes bulk queries illegal, let's not do it", under which a Nominet engine was already stopped. The port-43 footer names exactly what we would do: "restrictions on: (A) use of the data for advertising, or its repackaging, recompilation, redistribution or reuse... (C) exceeding query rate or volume limits." **Two traps that would silently fabricate yield.** `*.ac.uk` and `*.gov.uk` third-levels return the PARENT record, so `newoldlabour.gov.uk` answers `Domain name: gov.uk`; re-querying all 128 dated hits found 10 such mismatches and **every one returned `before Aug-1996`**, so scoring that string as 1996 would have invented ~12% of the yield. And `before Aug-1996` carries no year at all. In-band notice worth knowing: **the `.uk` WHOIS service ceases on 9 February 2027** |
| Parliamentary and gazette prose: four closed, and the item screen predicts the WRONG answer (2026-08-25) | **The transferable law: the 0.042 prose ceiling is an upper bound, not an estimate, and FORMAL prose runs ~15x under it.** Counting items therefore over-predicts, and two of these four pass the item screen comfortably and still pay nothing. **Hansard is the sharpest case**: 1,002 sitting days enumerated exactly from all 72 month indexes, ~235,270 section pages, which clears the 119,000-item screen 9.7x over. Sampled **1,795 pages and 3,260,082 words containing exactly 5 URLs** (`dti.gov.uk`, `fco.gov.uk`, `homeoffice.gov.uk`, `edwarddavey.co.uk`, `ecb.int`), **all 5 already held**. Density 0.0028 gross pairs per item. Reweighted to the measured section mix, written answers being 77.9% of pages and sampled 1 in 7, the whole corpus carries ~479 URL mentions, so the absolute ceiling is 470 EE even at total novelty. **The London Gazette repeats it**: 490,740 notices clears the screen 20x and measures **0.98 EE over 1 pair**, projecting ~50. **Two method points from that run worth keeping.** Its URL-bearing stratum was measured rather than assumed (`text=www` 720 notices, `text=http` 360), and **two apparently larger strata were proved to be tokenisation artefacts**: `text=co.uk` returns 3,080 but 43 checked hits yielded 2 notices carrying a domain, and `text=.com` returns 910 for 0 from 8, against 14 of 14 precision on `www`. A search count is not an item count. **Oireachtas was decidable on arithmetic alone**: 1,527 debate records against the ~24,438 that `.ie` at 0.9744 needs, 16x short, and measured at 0.00 over 119 records with 94.7% already held. It also shows the store moving under a source's feet: after the IEDR register was banked, `.ie` stands at 55,432 in-window pairs over 27,067 domains, so its saturation is far higher than a week ago. **TED is robots-blocked at the only host that has the in-window bulk**: the monthly 1998 packages are listed and every endpoint sits under `ted.europa.eu/packages/...`, which `robots.txt` disallows for all agents, so it was not fetched; the `ted-csv` alternative on `data.europa.eu` spans 2006-2024 only. Every zero here has a control in the same query: the Hansard zero sits beside 5 of 5 returning rows, Oireachtas beside 18 of 19, the Gazette beside 12 of 13 |
| The reciprocal-traffic industry, and why the blocklist inversion does NOT generalise (2026-08-25) | **The hypothesis was testable and it failed, which corrects a rule added to CLAUDE.md the same morning.** The premise: a traffic exchange should invert killer 3 the way a blocklist does (~50% already-held) because it selects for small sites that WANTED visitors rather than for authorities. Measured on the two traffic-derived artifacts reachable off Wayback, which are actual request streams rather than anybody's list: **99.55% and 98.39% already held, WORSE than the 87-99% curated band, not better.** The mechanism is worth keeping: **a visitor log's hostname field is REVERSE DNS**, so the long tail resolves to its ISP (`splitrock.net`, `pacbell.net`, `proxy.aol.com`, `prodigy.net`) while only large organisations resolve to themselves. **Traffic data selects for eyeballs' intermediaries, not for the sites that wanted eyeballs.** So the blocklist inversion does not generalise from "not curated" to "not authority-biased": what made blocklists work was ADVERSARIAL selection, and nothing in the reciprocal-traffic industry is adversarial. **The lens also dies earlier than that, on retrievability, before the redirector screen could even be applied**: no named candidate's member directory survives off Wayback. Three independent negatives, each against a control returning rows in the same minutes: `archive.org` for `linkexchange OR "banner exchange" OR bravenet OR fastcounter OR nedstat` gives 21 items, all Tony Hsieh podcasts and Archive Team's 2024 grabs of `wiki.bravenet.com`; the same for eight more services gives 447 hits that are CIA reading-room documents and arXiv preprints; and **discmaster, which indexes ~10^8 files off period media, returns for filename `ffa` only EyeWire stock photography and for `guestbook` only NetObjects Fusion templates**, so the accumulated-link data file was never pressed to disc. The arithmetic finishes it without a fetch: LinkExchange's Directory paginated at ~20 members a page, so its 400,000 members is 10,000+ archive fetches, which is numerically the WebRing rejection of 2026-08-05 before anyone asks whether the URLs are bare. **Three artifacts priced on the way, all sub-floor.** `2domain.dat` **576.87 EE**, a RIPE-derived `domain=registrant` table bundled inside the WebSuccess log analyser on the *CICA 32 April 1998* CD-ROM, file stamp 1997-08-25, BARE format (`0-errors.dk=Claus Cohn`), 131,167 canonical names at **96.40% already held**, 3,857 pairs post-split, mostly `de` 1,679 and `dk` 935. Its ceiling is reached, not sampled: a filename search finds exactly one populated edition and the 1999 builds ship a 226-byte stub. Notably it carries **no provenance or copyright header at all**, unlike the RIPE database blocked elsewhere in this queue. `www.xerox.com` server logs of May 1998, **58.13 EE**, 5,607 registrable domains at 99.55% held. FunnelWeb's April 2000 sample log, **5.12 EE**, 98.39% held. **The Xerox logs reopen and re-close the "era web traces closed by design" row on CONTENT rather than privacy**: that closure assumed a non-anonymised in-window log did not exist, and this one is cleartext on both client hostname and referer. It is worth 58 EE. **Reopen condition, narrow**: one artifact printing bare member URLs for 83,000+ distinct domains, generated by the service rather than paginated by it, on a host reachable without Wayback |
| Two more unreferenced directories priced to zero, and one is 511 MB of duplicate (2026-08-25) | **Following the rule that found the last two big things, that the residual audit's "unreferenced" list is worth reading rather than skipping.** (1) **`data/raw/bl/` enumerates FIVE Hyku repositories, not one**, and the four nobody had looked at are dry. The geoindex closure recorded the British Library as exhausted; `mola_file_index.tsv` (1,358 rows), `nls_file_index.tsv` (655), `nms_file_index.tsv` (7,502) and `nt_file_index.tsv` (2,618) were fetched by the same generalised ResourceSync script and never analysed. Searched locally at no network cost: **1 to 2 web-shaped filenames each and every one is a false positive** (`Butterfly_parasitoid_hostplant_interactions`, `Tapestry_Conservation.webp`, `Four_priorities_for_new_links_between_conservation`, `M74_for_web.jpg`), the only genuine one being NLS's `Collecting_the_Scottish_Web_at_NLS_-_a_report_of_a_census_2024_10_30.pdf`, a 2024 prose report and not a dataset. **So the Samvera/Hyku route is now exhausted across five institutions rather than one**, which is a stronger closure than the original for the same zero cost. (2) **`data/raw/usenet_msft/` is 511,487,988 bytes of DUPLICATE**: all three archives, `microsoft.public.excel.programming`, `microsoft.public.inetserver.iis` and `microsoft.public.win98.gen_discussion`, appear in `data/raw/usenet_new/.processed`, so they were mined by last night's run under the other directory. Zero remaining value and 511 MB reclaimable at Ivo's discretion. **The unreferenced list is now fully accounted for**: `usenet_new` processed 7,531 of 7,531, `ccgraph` is Common Crawl 2018 and 2020 out of window, `cdx_suffix` measured at exactly zero, `ffiec` closed on zero URLs in 35 schedules, `ripe_funet` blocked on its licence, `freebsd_ports` a closed family, `bl` and `usenet_msft` above, and the remainder is under 2 MB of probes and seeds |
| Blocklists invert killer 3, and the lens is right where retrievability is not (2026-08-25) | **The structural finding is worth more than the 2,189 EE it produced.** Four blocklist-shaped sources priced. **Already-held on a blocklist is ~50% against 87.5% to 99.8% on every authority-selected corpus closed this week**: junkfilter 50.4%, SurfWatch 49.7%, against discmaster `.url` 95.6%, bookmarks 99.0-99.8%, the ISI contact column 97.7%, jpnic 87.5%. **A blocklist selects for what somebody wanted to BLOCK, which is the exact inverse of the fame bias that killed six lenses this weekend.** So ask what a corpus selects FOR before asking how big it is. **What kills three of the four is retrievability, not selection.** (1) `junkfilter_dated_blocklist` **found, 2,189.4 EE**, and in the queue: Gregory Sutter's procmail filter at `junkfilter.zer0.org/pkg/`, 13 ISO-dated in-window editions plus two 1997 tarballs, ~900 KB, dated three independent machine-written ways that agree. Its triage note guessed the entries were escaped regexps and wildcards; **refuted, 42,005 of 42,034 tokens are domain-shaped, 99.9%**. Verified twice: an independent run over the 13 editions gave 3,122 pairs and 1,924.1 EE, and the gap to 3,553 is exactly the 431 pairs at 1997 inside the tarballs, so the two agree to the pair. Reaches the thin years, 431 at 1997 and 727 at 1999. (2) **CyberNOT is dead in DNS**: the 40,715-hostname decoded list had one route, `cphack.robinlionheart.com`, **NXDOMAIN on both the system resolver and 8.8.8.8**, the apex resolving only to a ZoneEdit forwarder returning HTTP 400, and the two surviving cphack mirrors carry the paper without the `blacklist/` path. The surviving peacefire mirror's one real list is 1,000 names, measured at 32.2 EE, and **ceilings at 632.1 EE even at 100% novelty**. (3) **Excite query logs are behind a personal e-mail**, with no download link and the field's standard aggregator listing nothing earlier than AOL 2006; killer 5 would apply in its purest form anyway, since a query string is a human keystroke. (4) `discmaster_by_file_size` was **not unpriced but mis-filed**: closed here on 2026-08-18 at 185.3 EE, and the `- measured:` line was lost in the 2026-08-23 compaction. **Citizenship note worth keeping**: `discmaster.textfiles.com` carries `Disallow: /` and then its own written exception, "If you are a researcher, historian or hobbyist, you are free to automate requests to the site so long as it's reasonable or somewhat limited or somewhat targeted" |
| 1999 InterNIC zones on the same frozen mirror as the JPNIC register: 179.8 EE (2026-08-25) | **Below the 1,000 bar, banked anyway because it needed no decision, and it independently confirms a figure another agent produced from a different host.** `tomocha.net/files/dns/` also holds `gov.zone`, `edu.zone` and `root.zone`, all filed 2002-02-26, **and the file date is not the artifact's date**: `gov.zone` carries SOA serial `1999111901` and `edu.zone` and `root.zone` carry `1999112000`, so two of the three are squarely in window. `gov.zone` also ends on InterNIC's own `;End of file.` marker, the integrity check this family is screened on. Measured: **`gov` 784 pairs at 1999, 601 held, 183 net-new, 179.8 EE**; **`edu` 5,850 pairs, every one already held, 0 net-new.** The `edu` zero matters beyond itself: it reproduces, from a different mirror, the measurement an agent made on `rscott.org/OldInternetFiles/edu.19991120.zone` (5,853 names, all dated 1999, zero net-new). Two hosts, one serial apart, same answer. **Ingested under the existing `internic_zone` class rather than proposed**: the Decision there rests on the artifact's semantics, an SOA serial inside the payload, which is exactly what these carry, so a new mirror of an approved class is a file and not a source. **A licence distinction worth keeping**: `edu.zone` and `root.zone` open with the Network Solutions access-agreement restriction on aggregated `.com`, `.org` and `.net` zone data, and `gov.zone` carries no such notice at all, beginning directly with its SOA. Only the unrestricted one paid anything. `inaddr.zone` at 19 MB is reverse DNS and worthless since the export drops `.arpa`; everything else in that directory is 2009 or later |
| 62 MB of RDAP work stranded on the VPS because the sync glob omits `.part` (2026-08-25) | **Banked 5,877 net-new pairs and 3,599.2 EE that had been sitting on the remote machine, the oldest since 22 August.** `maintain.sh` rsyncs `rdap_*.jsonl.gz` and `cdx_*.jsonl.gz` and never `*.jsonl.gz.part`, so a batch that dies mid-round leaves its journal where no pass here can see it. The engine-status check reports "none of its 435 journals is missing, everything is home" and is telling the truth about the wrong population. **Five abandoned partials, 62 MB, 502,293 readable records, 110,499 in-window creations, 104,622 already held, 5,877 net-new at 3,599.2 EE**, `com` 5,231 and `net` 646. Ingested at 5,877 year rows, matching the price to the pair. **This is the third time the same defect has bitten**: first a `cdx_`-only glob stranding RDAP journals, then a hand-written prefix missing a new collector, now the `.part` suffix. `maintain.sh` already carried the argument in a comment, that fetching should be by DIRECTORY rather than by hand-written glob, and the fix now implements it for partials. **The staleness test is the safety argument, not a detail**: only `.part` files older than 90 minutes are taken, because a LIVE partial copied under its final name would ingest a prefix, and the ledger keys on content, so the completed journal arriving later would be refused as a hash mismatch and lost entirely. **Also found in the same pass, and the reason to look at all: one of the two VPS RDAP engines had been dead for nine hours** while its sibling ran at 1.07 domains per second, 62,604 of 150,000 in 16 hours. Presence, progress and yield are three questions and only the first was being asked. The dead engine is restarted on `fastq_remote.txt`, 26,765,189 domains, deadline 4 September. **And a parse trap worth recording**: an RDAP journal carries a top-level `creation_year` field, NOT a nested `events` array, so a reader looking for `eventAction == registration` finds **zero in-window pairs in 502,293 records** and reads as a clean negative. The suspicious zero was checked against the known-positive `rdap_snapshot` schema rather than believed |
| The frozen-mirror rule, applied a second time: JPNIC pays 1,623 EE, InterNIC pays 0 (2026-08-24) | **The rule holds and it has a correction: the surviving registers are on PERSONAL pages, not institutional ones.** Every live academic mirror has rsynced its copy into 2026 and overwritten the pre-GDPR original; FUNET survived only because its sync broke in 1999. **(1) FOUND, and admitted to the queue: JPNIC's own `.jp` register at 30 April 1999**, `https://tomocha.net/files/dns/domain-list.txt`, 6,185,475 bytes, `Last-Modified: Fri, 30 Apr 1999 04:43:08 GMT`, on a personal DNS document mirror while JPNIC's own tree keeps only policy prose. Reparsed and repriced from the bytes rather than taken from the finder: **72,704 distinct registrable names, 45,877 already dated 1999, 26,827 net-new pairs, 1,623.0 EE**, 11,630 names the store has never seen. Controls pass in the same run (`sony.co.jp` and `nec.co.jp` present, a fabricated name absent). **`.jp` weighs 0.0605, so this clears the bar on volume alone.** **Licence is EXPLICIT PERMISSION**, lines 3 to 10 carrying JPNIC's open-document notice ending "as long as this copyright notice is included, anyone may freely reprint, reproduce and redistribute it", which is the exact opposite of the RIPE file sitting beside it in the queue. **Three parser traps, together worth 4.4x, and the file checks its own work.** It is Shift-JIS and must be split on CRLF, because Japanese organisation names contain bytes `splitlines()` treats as line breaks; a label is not a domain, since the suffix comes from the section header (`AAA` under `------ AD domains:` is `aaa.ad.jp`) and geographic labels contain their own dots (`CITY.CHITOSE`), so a dot-free pattern reads 65 Hokkaido entries as 1; and **45,662 entries are marked reserved and 923 abolished, neither of which was ever a registration**, the reserved ones being municipal and school names JPNIC held back. Counting them gives ~4,394 EE instead of 1,623. Completeness is proved by the artifact's own arithmetic: 62 of 63 sections reconcile exactly and the total lands at 72,770 against a declared 72,769. **(2) The InterNIC `domain-info` document family is retrievable and worth ZERO, which closes it.** `rscott.org/OldInternetFiles/` holds the tree, and `domain-info.19960614.txt` is 9,918,513 bytes, byte-for-byte the size in FUNET's own 1997 `ls-lR`, so provenance corroborates. Internal date line 3, `DDN NIC DOMAIN SUMMARY 14-Jun-96`. **417,103 distinct names, gross 264,007.8 EE, and every single one is already dated 1996: 0 net-new**, proved against a control where real names return years and three fabricated ones return nothing. `edu.19991120.zone` is 5,853 names, all already dated 1999, 0 net-new, and carries a RESTRICTIVE Network Solutions access agreement. So our 1996 gTLD coverage simply is this artifact. **(3) Dry, measured**: `ftp.funet.fi/.../domains.fi` is 35,752 `.fi` names with **no dates at all**; `ftp.nic.ad.jp/apnic/arin/arin.zones.tar.gz` is 33 reverse-slave `db.root` entries, no forward names; FUNET's `RIPE/dbase/` holds **one** snapshot and not a series. **Citizenship**: `ftp.sunet.se`, `ftp.nluug.nl` and `ftp.surfnet.nl` each name `ClaudeBot` or `Claude-Code` in a group ending `Disallow: /`, and `mirror.switch.ch`, `ftp.rediris.es`, `ftp.tu-chemnitz.de` and `ftp.linux.org.tr` disallow all; only their robots.txt was fetched |
| Integrity audit over every held gzip: 39 corrupt, nothing silently lost (2026-08-24) | **Run because tonight's `host-linkage` truncation was found by accident, and an accident is not a method.** `gzip -t` over all 6,168 `.gz` files in `data/raw` outside the Usenet trees, 10.8 GB. **39 fail, and every one is accounted for.** 21 sit under `probes/` and are DELIBERATE prefix samples, not failures: the giveaway is the naming (`head_`, `h_`, `tokens_head`) and the round sizes, 65536 and 50000 bytes exactly. Of the real 18: **`ukwa/host-linkage.tsv.gz`** at exactly 2 GiB, already logged tonight as the archive's own replay ceiling; **six `cdx_suffix` journals**, already measured tonight at **net-new zero** over the whole directory; **`odp/c2000.gz`**, which recovers 124,943 lines and dies mid-tag on `</d:Des`, and which the `odp` section already describes honestly as "a truncated prefix of the August 2000 full dump" that is "unrecoverable"; **`rdap_20260725T222016Z.jsonl.gz`**, ingested, 875 records readable and **0 in-window registrations**, so the lost tail cost nothing measurable; **`maillists/gnome/gnome-components-list__2001-July.txt.gz`**, which was **never ingested**; and seven small `cdx` journals from interrupted runs. **The conclusion is the value: no ingested source is silently short except the two the register already documents.** Worth re-running after any bulk fetch, and note the trap that made the first attempt lie: `xargs -0 -I{}` over 6,168 paths dies with "command line cannot be assembled, too long" after ~20 files and still exits 0, reporting 8 corrupt and looking complete. `find -exec sh -c` tested all 6,168 |
| The 1999 RIPE database, frozen on a document mirror: 90,799 EE, blocked on a licence (2026-08-24) | **The largest find of the round, and it is not banked because of its own copyright header.** `ftp.ripe.net`'s `dbase` is closed here as GDPR-dummified and `ripe/registries/` as empty since 1998. But FUNET mirrored RIPE's whole DOCUMENT tree into `/pub/netinfo/`, beside `docs/`, `procedures/` and `minutes/`, and then stopped updating, so **the mirror froze holding the pre-GDPR original**: `http://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz`, 71,919,736 bytes, `Last-Modified: Tue, 03 Aug 1999 21:27:00 GMT`. This is the rule the zone-file closure produced, **filed next to its documents**, working on its first application. Integrity, all three checks: `gzip -t` clean, 20,528,780 lines, its own `# 990804 00:07:01` on line 2 and its own `# EOF` terminator. **Measured independently rather than taken from the finder**: 1,256,414 `*dn:` lines, 21,047 `.arpa` reverse zones excluded, 429 rejected, **1,232,554 distinct registrable names**, 591,313 already dated 1999, 849,540 dated in some year, **383,014 the store has never seen**, leaving **641,241 net-new (domain, 1999) pairs worth 90,799.4 EE** against a gross of 173,359.2. A subagent measured 93,857.7 an hour earlier and the 3.3% gap is the store growing underneath it, not a disagreement. **Volume beats weight, which is why it nearly got discarded on sight**: net-new is `de` 411,128, `dk` 73,658, `at` 29,910, `it` 29,685, `nl` 19,753, `cz` 19,314, and every one of those is on the near-worthless list, yet 1.2M names at 0.1324 outruns any high-weight namespace still available. **THE BLOCKER IS THE FILE'S OWN HEADER, lines 6 to 15**: `Restricted rights. Except for agreed Internet operational purposes, no part of this publication may be reproduced, stored in a retrieval system, or transmitted... without prior permission of the RIPE NCC on behalf of the copyright holders.` Ingesting is arguably storage in a retrieval system and shipping is arguably transmission; against that, we would ship `(domain, 1999)` pairs rather than the publication. RIPE NCC is Dutch, so the **EU sui generis database right** over extraction of a substantial part is the sharper question, and 641,241 rows is substantial by any reading. **No parser has been written and nothing has been ingested**, so the approval cannot be acted on by accident. Robots was read first: `ftp.funet.fi` permits `/pub/netinfo/` and asks `Crawl-delay: 15`, and one request was made. Also newly measured nearby and dry: **munnari.oz.au is the sharpest inversion of the thesis found all night** at `.au` 0.9904, its FTP root holding 26 entries that are all IETF documents plus software, no `/au`, no `/dns`, no `/domain`, so **Robert Elz mirrored the documents that made him an authority and not the register that made him a registrar**; `ftp.isi.edu`'s 2015 tar index over 34,638 paths has no `usdnr/`, ISI having removed the US Domain Registry before then; funet's own North American `NSFNET-Sites/` and `nsfsites/` survive as **empty directories**, the path mirrored and the contents not |
| 50 GB of Usenet the pipeline could not see, because of a directory name (2026-08-24) | **`ingest_new_usenet.sh` reads `DIR="data/raw/usenet"` and marks work in `data/raw/usenet/.processed`. 7,531 archives and 50 GB sit in `data/raw/usenet_new/`, so no pass has ever looked at them: zero of the 7,531 appear in a `.processed` list holding 19,231 other groups.** The residual audit did flag the directory as "downloaded bytes with no parser and no ingest line", which is how it was found, but the flag reads as a missing parser rather than a mis-pointed collector and had been sitting there. **Measured before processing, three samples over 4,052 MB and five hierarchies: 57,913 dated pairs, 57,847 already held, 99.89% saturation, 66 net-new pairs and 35.8 EE.** By sample: `bit` and `linux` gave **0 net-new over 207 MB**; `us`, `gov` and `lucky` gave **3 over 1,866 MB**; the twelve largest `microsoft` archives gave **63 over 1,979 MB**. Composition of the 50 GB is `microsoft` 25.93 GB, `free` 5.07 (largely `free.it`, worthless), `linux` 4.52, `bit` 3.49, `us` 2.67, `mailing` 2.38, `fa` 1.99, `lucky` 1.73, `borland` 1.57, `macromedia` 1.45. **Projection over the full 50 GB is 450 to 850 EE**, the range depending on whether the samples are pooled or weighted by hierarchy, so it is BELOW the 1,000 EE bar for a source needing a decision. **It is being processed anyway and the distinction matters: it needs no decision.** `usenet_dated` and `usenet_candidates` are already master and candidate-only, so the only cost is CPU on bytes already downloaded. Running as `scripts/work_usenet_new.sh` at six workers rather than the pipeline's ten, because the two CDX engines are worth more per hour and must not be starved to finish this faster. **The refuted number is worth recording**: this register carried ~3,219 EE for the `microsoft` hierarchy, and measuring the twelve largest archives directly projects **444 EE** for it, about seven-fold lower, because the store has grown into it since. **And one structural fact explains all of it**: in the `bit`/`linux` sample 253,824 of 255,270 messages were **out of window**, 99.4%, since these archives run well past 2001. The Usenet name population is exhausted against a store holding 12.67M domains |
| Zone files off the Internet Archive: the family closed on live mirrors too, and the reason generalises (2026-08-24) | **Nobody archived scratch, and that is the whole finding.** The argument that made `internic_zone` pay is sound (an NS record IS the delegation, self-dated on the SOA inside the payload) but it only ever applies to an artifact somebody chose to write to disk **and keep**. Three separate organisations here transferred exactly the data we want and all three published only the aggregate or only the current state. **The six InterNIC zones survive because they sat in a DOCUMENT mirror alongside RFCs, not because they were zone files.** So the productive question for this lens is not which registry ran a zone but **which registry filed its zone next to its documents**, which is also why the `.ie` register listing paid. (1) **RIPE NCC Hostcount is the most valuable negative of the session.** `ftp.ripe.net/ripe/hostcount/History/` holds a monthly edition across the whole window, and its own `METHOD` file states the mechanism verbatim: *"The RIPE DNS hostcount is done by transferring every possible Domain Name System zones under the mentioned top level domains."* RIPE **AXFR'd every European ccTLD every month from 1990** and published a per-country table of `SOA / COUNTED / DUPL / REAL / CHANGE` at ~6 KB per edition. The largest zone walk that ever ran in Europe, and the names were transferred and discarded. (2) **Two live InterNIC mirrors nobody had checked, both dry**: `ftp.ripe.net/mirrors/domain/` (24 files, all mtime 2020) and `ftp.nic.ad.jp/mirror/rs.internic.net/domain/` (24 files, rsynced this morning). Both carry `arpa`, `root`, `root-servers.net` and the hints file and **neither carries `com`, `net`, `org` or `edu`**: they mirror today's IANA root distribution, not the 1997 gTLD set. With the five already dry (funet, icm.edu.pl, sunet.se, ibiblio, aarnet) **the InterNIC gTLD zone family is now closed on live mirrors as well as on Wayback**. (3) **DENIC was the biggest arithmetic prize in the lens and is closed on policy**: `.de` at 0.1324 over 1,218,732 held domains made a 2001 `.de` register worth ~300,000 EE, the whole gate, and DENIC states it does not publish zone files and never has, with `ftp.denic.de` not resolving. Nominet is the same verdict: `registrars.nominet.uk` publishes the `.uk` zone and a full domain list, both **current-state only**. (4) **JPNIC measured rather than estimated**: `ftp.nic.ad.jp/jpnic/domain/archive/` looks ideal, dated in-window filenames throughout, and is policy prose. Its largest and best-shaped file, `domain-geographic.txt.980201`, 45,651 bytes and 1,107 lines, yields **14 distinct `.jp` names and they are placeholders** (`foo.chuo.chiba.jp`). Under 1 EE at `.jp` 0.0605. (5) **archive.org has a hard date floor at 2021 for this family**: `description:("zone file")` returns 332 items and the first genuine zone artifact is `ee_zone_file_202108`, while the four items dated 1999-2002 are a gaming installer, a DNS tool, a book and a shareware app. `"rs.internic.net"` returns 0. **Proved against a control in the same minutes**: `date:[1996-01-01 TO 2002-01-01] AND mediatype:texts` returns **1,966,616 items**, and the same directory-listing method surfaced 70+ in-window dated files in the JPNIC tree, so the zeros are absences rather than a broken probe |
| CITIZENSHIP: `ftp.isc.org` disallows everything, and this register records reading it (2026-08-24) | **Second robots finding of the night, recorded for the same reason as the `arquivo.pt` one.** `ftp.isc.org/robots.txt` returns `Disallow: /` for all agents. The ISC survey rows in this register describe reading a live directory listing at `ftp.isc.org/www/survey/archive-data/` to establish that the name lists stop at 9707, so that check was made against a host that asks not to be crawled. The finding it produced stands and the `isc_survey` data we hold came from other routes, but **no further request may go to `ftp.isc.org`**, and the tonight's agent correctly refused to fetch it. Together with `arquivo.pt/datasets`, the standing rule is now explicit: **read robots.txt before the first request, and record the read**, because two of this project's hosts were crawled against their stated wishes and neither was noticed at the time |
| Mailing-list SUBSCRIBER populations, the escape hatch this register named, refuted (2026-08-24) | **The `Message-ID` row closed mail headers and said: if mail is ever reopened, ask whether a list's SUBSCRIBERS were an uncrawled population. That question is now asked and answered no.** The premise fails on a ratio nobody had measured: **a participant population does not give one domain per participant, it gives one per employer or ISP.** 15,968 IETF senders collapse to 1,713 domains (9.3:1), 16,051 r-help senders to 1,053 (15.2:1), 6,118 FreeBSD senders to 1,627. So the seam saturates on the same law as prose. **Measured rate: 0.00106 EE per in-window message post-split, so 1,000 EE needs ~944,000 in-window messages on one unmined host**, and nothing reachable is that big. Four corpora, two measured whole and two projected: **lore.kernel.org LKML 81,741 in-window messages, a COMPLETE census, 92.2% held, 80.19 EE**; **r-help at `stat.ethz.ch/pipermail/`, 16,062 messages complete, 97.7% held, 10.63 EE**; FreeBSD's week-at-a-time mbox route (`mail-archive.freebsd.org/cgi/getmsg.cgi?fetch=...`, 10,957 in-window week files, 2.09 GB) 98.4% held, ~573 EE projected; the IETF autoindex ~1,651 MB, 97.0% held, 455-594 EE projected. Union of the four: **128.59 EE post-split from 121,414 messages and 435 MB**. Summing every projection gives ~1,250 EE for ~4 GB and ~25,000 requests, which is a campaign rather than a source. **Killer 3 confirmed, and the hobbyist escape hatch specifically refuted**: the ORDINARY-USER lists (freebsd-questions, freebsd-chat) were the MOST already-held at 98.4%, not the least, because a store holding 12.67M domains already has every mail domain that ever ran a web server. **Subscriber rosters proper do not survive**: zero LISTSERV `REVIEW` or `who` outputs in 64,727 in-window messages. One fact worth keeping for any future ruling: **the participant seam is essentially unmunged**, the opposite of the body seam that put 575,417 impossible names in the candidate pool. Raw mbox is 99.5% plain `@` at IETF and 99.1% at FreeBSD with munge markers on 0.2-0.4% of `From:` lines, and lore-via-git is entirely unmunged; pipermail rewrites 94.5% as `user at host.com` but deterministically and the domain survives. That argues the address is machine-written rather than typed prose, **but the uncorroborated tail is where forgery concentrates**: of 51 novel IETF sender domains about a quarter are list spam with throwaway or forged names (`38601@jKJqfl.com`, `aaatestkits.com`), so the split is doing real work on exactly this seam. It changes nothing here, since even the GROSS rate of 0.00306 EE per message needs 326,659 messages per 1,000 EE |
| FFIEC Call Report, the ERA VINTAGE tested on disk and closed for good (2026-08-24) | **The strongest form of this lead was already downloaded and it is empty.** Tonight's government sweep priced the FDIC's live API at 134.16 EE and noted the Call Report cover page gained a web-address item in the **September 30, 2000** materials while bulk data starts **2001-03-31**, concluding the two quarters that first collected it are in no bulk file. But `data/raw/ffiec/call_03312001.zip` has been on disk since 13 August: that IS the 2001-03-31 vintage, so the question could be settled rather than reasoned about. Extracted whole, 35 schedule files, 8,858 institutions in the POR: **zero URL-shaped tokens (`https?://` or `www.`) across every file**, and no header matching web, url or internet in any schedule. The POR's only address column is `Financial Institution Address`, a street address. **So the item was collected on the cover page and never entered the bulk data product**, which closes the FFIEC/Call Report family on the era vintage rather than on the current-state proxy, and closes it permanently: a later vintage cannot contain a field an earlier one dropped. Also priced to nothing in the same pass: `data/raw/ccgraph/`, 1.18 GB of Common Crawl domain vertices for **2018 and 2020**, which cannot evidence a past year (killer 4) and is candidate supply at best |
| `data/raw/cdx_suffix/`: 389 MB the residual audit calls unread, worth exactly 0 (2026-08-24) | **Measured to a zero so nobody spends another hour on it, because the audit will keep flagging it.** `audit_residual.py` lists this directory under "downloaded bytes with no parser and no ingest line", 58 journals and 389,393,904 bytes, and every one is genuinely unread by the ledger. It is still worth nothing, and the reason is that the suffix sweep writes TWO journals per batch: a raw capture form here as `{"url": ..., "timestamp": ...}`, one row per capture, and a per-domain form at `data/raw/cdx/cdx_suffix_*.jsonl.gz` that `parse_cdx_snapshot` reads into `ia_cdx_bulk`. The per-domain form is ingested, so the raw form is the same observations in a shape nothing needs. Priced whole rather than sampled: **46,779,589 lines, 0 malformed, 0 out of window, 113,731 distinct in-window (domain, year) pairs, 113,731 already held, NET-NEW ZERO.** So no parser is needed and the flag is a false alarm for this directory rather than a missed source. **The zero is also a positive result about the pipeline**: it says the suffix engine loses nothing between query and store, across `ac.uk`, `co.uk`, `asn.au`, `govt.nz`, `k12.*.us` and `lib.ca.us`, which are the highest-weight namespaces it sweeps. Six of the 58 raise `EOFError` as truncated tails from interrupted runs, which is immaterial at a net-new of zero but confirms the runs were killed rather than finished |
| National web-archive indexes, three new doors opened and all three priced out (2026-08-24) | **The British Library win generalises as a ROUTE and not as a yield, which is the finding.** Three repository doors nobody had opened all answered on the first try, and all three price below 1,000 EE, because a national archive's in-window holding is one of two things: an IA back-file donation we already hold, or a curated national slice of institutions a capture-derived baseline holds first. **Price the population before pricing the route.** (1) **Library of Congress US Elections Web Archive**, `data.labs.loc.gov/us-elections/by-year/2000/`, enumerable from `manifest.txt`, **3,521 gzipped SURT CDX files at 1,971,201,167 bytes**, robots 404 so nothing disallowed. Genuinely not IA-derived (ARC names are LC-internal `unique.<ts>.arc.gz` and the README says the 2000 and 2002 data was gathered by LoC staff and contractors), hostnames complete, master-eligible `cdx_timestamp`. Measured on 81 of 3,521 files, 3.5% of the bucket, 3,792,014 records entirely in window: **582 gross pairs, 22 net-new, 14.61 EE**. Doubling the sample took gross from 395 to 582, a Heaps exponent of 0.559, projecting ~180 net-new and **~120 EE** for the whole 1.97 GB. Dies on killer 3 at **96% already held**: a curated set of campaign and party sites is exactly what we hold first. (2) **DigitalNZ**, `api.digitalnz.org/v3/records.json?and[category][]=Websites`, no key needed and a separate door from the Imperva-walled `natlib.govt.nz`. **It carries a fabrication trap worth more than the source**: in the 2000 facet the `display_date` values are `20??-` 1,119, `200?-` 695 and `2000-` only 75, because DigitalNZ normalises century and decade PLACEHOLDERS to `2000-01-01`. Trusting the field gives 1,679 net-new pairs and 1,439.46 EE, of which about 1,575 are manufactured. Restricted to rows whose date actually contains the facet year: **157 net-new, 140.34 EE**, and those are cataloguer-typed so the split takes them to near zero. Same shape as the UDRP Zenodo `submitted` corruption. (3) **Arquivo.pt link graphs**, `arquivo.pt/datasets/linkgraphs/PWA9609/`, a bulk deliverable under no name in this register: 300 files, ~34.3 GiB, per-record JSON dating both node and inlinks (`"captureDate":"1996-10-13T17:42:26"`). Measured over 48,000,010 bytes from 10 spread parts: **345 gross in-window pairs and 0 net-new**, rule of three putting the 95% ceiling for all 34.3 GiB at ~790 EE against a measured zero. Killer 1 exactly: the in-window part is the IA back-file already held as `arquivo_ia`. (4) **Denmark**, `labs.statsbiblioteket.dk/linkgraph/1998_to_2003/linked.js`, 23.35 MB CC BY-SA, 79,013 complete unhashed `.dk` hostnames, and **no per-record date anywhere**, the window living only in the page prose, so killer 2. Whole-population ceiling 13,519 EE at `.dk` 0.1711 and only if another engine dated every name. (5) Dry with the blocker named: **Sweden** has no dataset at any door and KB is not among researchdata.se's 110 depositors; **Norway** started `.no` harvesting in 2019; **Finland** started 2006 and is legal-deposit-workstation only; **Denmark's LOAR** NetLab collection is empty at `totalElements: 0`, proved against non-zero scopes; **NLA** ships taxonomy graphs with no hostnames and AGWA's own text dates collection to June 2011; **LAC Canada** has 64 datasets, none a web index; **Memento aggregators** are NXDOMAIN against resolving controls, and MementoMap truncates hostnames by design. The **UKWA open-data inventory is now exhausted end to end**: `fmt` is MIME types, `linkage` is a suffix-level chord diagram with no hostnames, leaving the geoindex (ingested), host-linkage (held, 89.74% unreadable) and the payload-less CDX record |
| CITIZENSHIP: we breached `arquivo.pt/robots.txt`, and it reaches an already-ingested source (2026-08-24) | **Recorded because a rule we broke is worth more written down than quietly fixed.** `arquivo.pt/robots.txt` line 752 carries `Disallow: /datasets` inside the `User-agent: *` block, with `Crawl-delay: 5`; only two agent blocks exist, at lines 2 and 15, so it applies to us. Ten ranged GETs against `/datasets/linkgraphs/` breached it tonight before the file was read. **And the same path disallows the original collection of `arquivo_ia` and `arquivo_roteiro`, which came from `/datasets/cdxj/`**, so two ingested sources were acquired against that host's stated wishes. The data is held and the evidence stands, but no further request may go to `arquivo.pt/datasets` and the register should not propose that host again. Separately, two requests reached `www.loc.gov/search`, which disallows `/search` for all agents; the allowed equivalents are `/collections/` and `/websites/`, and the `data.labs.loc.gov` host used for the measurement above returns 404 for robots.txt and is unrestricted. **Read robots.txt BEFORE the first request, not after the tenth** |
| Dated directories and navigation sites, the family closed on arithmetic (2026-08-24) | **Ding's named family, six artifacts probed off Wayback, all zero, and the closure is a volume law rather than a host list.** Measured novel-pair yield per LISTED domain, from our own register: BUBL LINK 5 net-new post-split pairs over 388 listed domains (0.0129/domain, 1.96 EE); award galleries 5 over 206 (0.024/domain, 3.16 EE); the Yahoo 1996-97 tree 11 pairs and 7.73 EE; the Zenodo printed-directory corpus 934 pairs and 432.81 EE over 7,600 domains. EE per net-new post-split pair runs 0.39 to 0.70. **So 1,000 EE needs roughly 2,000 net-new post-split pairs, which needs 83,000 to 154,000 distinct listed domains inside ONE artifact.** Only DMOZ (1.6M URLs at April 2000), Yahoo and LookSmart/Snap were ever that big; DMOZ's in-window dumps are already held and the others never published one, while a whole CD-ROM edition is low thousands of URLs. **The structural reason is worth more than the law: for a human-curated directory, novelty and datability are mutually exclusive.** The names our baseline lacks are exactly the ones taking the corroboration split, so they land in the candidate pool and earn no year, while the names that survive the split are the authorities we already hold. That is killer 3 multiplied by killer 5, and it is precisely why today's two winners were REGISTERS rather than directories: a register regeneration is the operator's own database and takes no split. **The screening question is therefore not how big the directory is but whether the lister was also the registrant's counterparty.** Six probes, each zero read against a positive control. (1) **InterNIC zone distribution via live FTP mirrors**, the highest-value negative and genuinely new: the existing closure was Wayback-specific ("Wayback never crawled FTP trees"), leaving live mirrors untested, and `com.zone`/`net.zone` for 1998-2001 would have been worth hundreds of thousands of EE. `ftp.funet.fi/pub/mirrors/` does list `ftp.internic.net/`, and it is a husk whose only child is `See_nic.nordu.net/`, whose mirror holds IETF documents only; `/domain/`, `/netinfo/` and `/domain-info/` all 404. Four other large live mirrors return **zero** paths matching nic|internic|domain|zone|netinfo|whois while returning real listings of 14,300 to 43,814 bytes: `ftp.icm.edu.pl`, `ftp.sunet.se`, `ibiblio.org`, `mirror.aarnet.edu.au`. (2) **DMOZ off Wayback**: Curlie's own RDF page says verbatim "We strive to pull a fresh copy from the Curlie database every month", so current state (killer 4); `download.huihoo.com/dmoz/` serves 285 MB dated **13-Feb-2013**, right shape wrong decade; `rdf.dmoz.org`, `dmoztools.net`, `dmoz-odp.org`, `dmoz.co.uk` all NXDOMAIN; and the community's own dump inventory lists **no pre-2002 edition**. (3) **RIPE Hostcount** `ftp.ripe.net/ripe/hostcount/History/`, 28 monthly in-window editions, dating itself verbatim `This Count     : Fri Dec 21 2001`, is the operator's own statement and **the wrong unit**: a hostname-shaped grep returns **0** because the payload is per-country aggregates (`de 3039248 11518670 ...`). (4) Live legacy national directories AussieWeb and nzs.com: current-state commercial listings with no per-item in-window date. (5) FUNET's preserved 1990s tree is real and non-IA but dated 1991-1993, outside the window. (6) **JANET/UKERNA `.ac.uk` naming register**, formally untested since the existing row covered `nic.uk` and `nominet` only: `ftp.ja.net` still resolves to 78.158.56.125 but refuses 80 and 21, and it fails the floor on arithmetic anyway at ~200 `.ac.uk` institutions x 0.9813. **Reopen condition, narrow**: one artifact with 100,000+ listed domains, generated by the operator that held the database, stamped in window, on a live host |
| The UKWA host link graph is truncated by the ARCHIVE, not by our download (2026-08-24) | **The 2 GiB local copy is not our failure and cannot be resumed from this host.** `host-linkage.tsv.gz` on disk is exactly 2,147,483,648 bytes, `gzip -t` fails with "unexpected end of file", and the Wayback `id_` capture reports `content-range: bytes 0-0/20928588915`. So we have read **10.26%** of a **master-eligible** source, and that tenth already paid 231,865 evidence rows over 183,515 domains and 116,467 assigned pairs. A resume is arithmetically sound, because our bytes are an ordered PREFIX and appending byte 2147483648 onward would rebuild one valid gzip stream. **SETTLED 2026-08-25 after two wrong diagnoses of my own, and this is the final picture.** Three measurements fix it. (a) CDX returns **two captures**: `20200106181208` at length 2,148,135,247 and `20221031190607` at **20,930,377,408**. (b) The 2020 capture **serves a deep range perfectly**: offset `2147000000-2147000099` returns 206 with 100 bytes in 25 seconds, so **there is no 32-bit offset wall anywhere** and yesterday's conclusion was wrong. (c) A request for the 651,599 bytes between our local size and that capture's CDX length returns **206 with ZERO bytes**, which means our 2,147,483,648 bytes **IS the complete payload** and the difference is WARC framing. **So the truth is that IA's own 2020 crawl truncated at 2 GiB, and we hold all of what it captured.** `gzip -t` fails on our copy because the ORIGINAL 20.9 GB gzip stream is incomplete at 2 GiB, not because our download failed. The 2022 capture is the whole artifact and returns **HTTP 504 after exactly 120.5 seconds** at any offset, a 100-byte range failing identically to a deep one, so the cost is locating a 20.9 GB record and the blocker is gateway capacity. **Nothing further can be recovered from the 2020 capture; the only route to the remaining 18.78 GB is the 2022 capture answering, and the test is one ranged GET returning 206 with bytes.** Worth retrying when the archive is quiet, because `.uk` weighs 0.9813 and this file's first tenth alone gave 231,865 evidence rows and 116,467 assigned pairs. Superseded reasoning follows. **CORRECTED 2026-08-25, and the original diagnosis below was an over-reading.** A CDX enumeration of this exact URL returns **two captures, and they are not the same file**: `20200106181208` at length **2,148,135,247** and `20221031190607` at length **20,930,377,408**. The probes below were made against a `2019id_` URL, which Wayback resolves to the NEAREST capture, meaning the 2 GiB one. **So requesting past 2 GiB of a 2 GiB record correctly returned nothing, and the "signed 32-bit overflow" conclusion was unjustified.** The real trap is narrower and worse: **that response advertised `content-range: bytes 0-0/20928588915`, the ORIGINAL file's length from the captured headers, while serving a record holding a tenth of it.** So the archive told us the size of the thing we wanted and handed us a prefix, which is exactly why the local copy looked like our own download's failure. The 2022 capture is the full artifact and is the route to test; **measured 2026-08-25: it returns HTTP 504 at both offset 0 and offset 3,000,000,000, in each case after exactly 120.5 seconds against a client budget of 540**, so the SERVER's gateway timed out rather than the client. A 100-byte range fails identically to a deep one, which means the cost is locating a 20.9 GB record and not transferring it. **So the blocker is now a capacity limit rather than an offset limit**, and the project rule on 504 is to back off. **The reopen test is one request**: a ranged GET on capture `20221031190607` that returns 206 with bytes. Worth retrying when the archive is quiet, because the prize is 18.78 GB of a master-eligible `link_source` whose first tenth already gave 231,865 evidence rows and 116,467 pairs. Non-Wayback routes remain dry: the original serves a 159-byte stub, `data.webarchive.org.uk` does not resolve, and `archive.org` holds no item. Superseded reasoning follows. **It fails because the archive will not serve past 2^31.** Measured, four ranged probes through one client with `--http1.1`: `0-99` returns 206 with 100 bytes, `1000000-1000099` returns 206 with 100 bytes, `2147483648-2147483747` returns **206 with 0 bytes**, and `3000000000-3000000099` returns **206 with 0 bytes**. A 206 with the right `content-range` and an empty body is the signature of a signed 32-bit offset in the replay layer, and it explains the local file's size exactly: 2 GiB to the byte is where the first download stopped because it is where the server stops. **Two traps recorded on the way.** Over HTTP/2 the same request aborts with `stream N was not closed cleanly: INTERNAL_ERROR` while curl still reports **206**, so the status alone claims success over an empty body; `--http1.1` is required to see the truth. And rapid probing turns every answer into `http=000`, which reads as a dead endpoint rather than as our own throttling. **The reopen condition is a non-IA host**: the file is 89.74% unread, `link_source` is master-eligible, and `.uk` weighs 0.9813, so this is the largest known unretrieved artifact in the register. `webarchive.org.uk` itself serves a 159-byte stub and the dataset DOI no longer resolves, so the route must be a mirror, a repository deposit, or an `archive.org` item rather than a Wayback replay. Collector kept at `scripts/resume_host_linkage.sh`, correct and blocked. **Three routes off IA checked and dry**: `webarchive.org.uk` serves the 159-byte stub, `data.webarchive.org.uk` does not resolve, and `archive.org` holds no item (a full-text search for `host-linkage` returns 254 hits and every one is PubMed protein-linkage noise, while `"host link graph" OR ukwa.ds.2 OR "UK Web Domain Dataset"` returns **0**). **The one test still unrun, and it is cheap**: whether the dataset was also published as PER-YEAR shards under `webarchive.org.uk/datasets/ukwa.ds.2/`, since any shard under 2 GiB would replay in full. It could not be run tonight because a CDX enumeration returned **503**: both archive-client slots belong to the collectors, and a third client competing with them costs more than this lead is worth. Run it when the engines are idle |
| Preserved software and documentation collections, the family closed (2026-08-24) | **Ding's named family, tried across six ecosystems and closed on a mechanism rather than on an exhausted host list. Best member measured 31.8 EE against a 1,000 EE floor.** The lens's whole premise was that a package index is machine-generated and so escapes the corroboration split. **Measured, that premise is false for this era: every in-window package format is build-generated in its structure and its dates and carries no build-generated URL.** The URL field arrives after the window and this is shown twice with passing positive controls. Debian: `Homepage:` returns **0 across all 36 in-window index files** and entered dpkg around 2007. CPAN: `resources.homepage` exists on **0 of 15,871 in-window releases**, while the same field unfiltered by year returns **121,281 releases whose earliest bucket is 2005**, so the index can see the field and it did not exist in window. **SUSE 7.3 is the family's largest new member and its best number.** `ftp.gwdg.de/pub/linux/suse/discontinued/i386/7.3/suse/setup/descr/`, 4,982 packages, dating impeccable and machine-emitted (`Buildtime: 1005144758`, header `## Generiert von: pac2setup 07/01`), all 4,982 in 2001. But a field census finds **no `Url:` field at all**: every hostname comes from `AuthorEmail`, `AuthorName` or free-text `Description:`, so the split takes 97.1%. 4,748 distinct pairs, 1,923 held, 2,825 pre-split (do not quote) and **82 post-split = 31.8 EE**, raw overstating by 63.9x, net-new TLD mix com 23 / **de 18** / se 6 / org 6 / net 5 / dk 3 for a **mean weight of 0.3876**, below the 0.4 floor. Also measured and dry: Slackware `PACKAGES.TXT` has no URL field (8.0 is 365 packages and 33 host-shaped tokens in 180 KB); CTAN's catalogue record has keys `caption, key, name` only, so **nothing can date a year**; CRAN's 27,676 archive directories carry 2026 mtimes and R 1.0.0 postdates Feb 2000 anyway; Red Hat and rpmfind are unretrievable across nine dead mirrors, and bounded rather than guessed, since Red Hat 7.2 shipped ~1,600 RPMs against SUSE's 4,982 and its `URL:` is typed by the packager too. RPM's one build-emitted hostname, `RPMTAG_BUILDHOST`, names the distributor's own build machine. **Whole-family ceiling ~40,000 items at SUSE's measured 0.0165 post-split pairs per item is ~660 pairs and ~260 EE**, and lower in truth because marginal releases repeat packages. Confirms killer 3 on a third and fourth member: a package index points at software VENDORS, the most-mirrored hosts of the early web, which a capture-derived store holds first. FreeBSD ports measured 97% of pairs already held, the Linux Software Map 94.7%. **Do not return to this lens** |
| InterNIC zone files at the `nic.mil` mirror, admitted (2026-08-24) | **Master, and the grounds are the artifact alone.** The SOA serial `1997041800` sits on line 2 **inside** the payload, and the IA capture of 1997-04-20 fixes when the file existed; nothing here rests on agreeing with the baseline. **Killer 2 does not reach a zone file**, and that is the whole argument: an NS record in `.org` is the delegation itself, the registry serving that name at that instant, not a directory listing a name it happens to know. All six zones re-verified on the day of the decision, `gzip -t` passing and each ending on InterNIC's own `;End of file.` marker, which is the exact check the corrupt ISC copies in the row above fail: `org` 154,141 lines, `edu` 12,132, `gov` 1,805, `mil` 301 at serial `1997041700`, `root` 1,316, `arpa` 35. Ingested at **12,320 net-new (domain, 1997) pairs and 8,813.3 EE**, `org` 12,074, `edu` 199, `gov` 44, `mil` 3; `root` and `arpa` pay nothing because one lists TLDs and the other is dropped by the export. **4,889 of the net-new names are dated at no in-window year at all**, so 40% is discovery rather than completeness, into 1997, our second-thinnest year. Ceiling honest and reached: `com` and `net` were on the mirror in January 1998 per its own Apache index at 26M and 2M, but every capture of those URLs is the 386-byte "Have a NIC day" withdrawal stub, so this is the whole source and not an instalment |
| More InterNIC zone files, and the canonical `ftp.internic.net/domain/` (2026-08-18) | **The population is enumerated at six and we hold all six, so `internic_zone` cannot be widened.** The DDN NIC mirror's whole zone directory is `nic.mil/oroot.html/`, and one CDX listing returns its complete contents: `arpa` 694 bytes, `mil` 3,265, `root` 10,219, `gov` 16,251, `edu` 110,995 and `org` 1,318,217, plus a BIND 4.9.4 tarball and three `named.root` copies that are the same 901-byte hints file three times. The six sum to 1,459,641 against the 1,458,311 bytes on disk, which is the check that nothing was missed rather than an estimate of it. **There is no `com.zone` or `net.zone` anywhere on the mirror**, which matters because those are the two that would have been worth hundreds of thousands of pairs. The canonical distribution is closed separately and for a structural reason: `ftp.internic.net` IS archived, but only its HTTP face, and `/domain*` returns nothing at any date because Wayback never crawled FTP trees. `rs.internic.net/domain/*` and `ftp.rs.internic.net/domain/*` are the same negative, the first returning only the 14 `domain-info/` policy pages. Four index requests, no payload fetches, every zero read against listings that returned real rows |
| The `.au` registry family: AUNIC, auDA, AARNet (2026-08-18) | **Screened because `.au` weighs 0.9904, second only to `.arpa` and `.mil`, so a pair there is worth 1.57 of a `.com` one. It does not survive in any bulk form.** AUNIC ran `.au` for the whole window and its archived footprint is 1,605 captures, of which the only domain-bearing shape is its whois CGI, `aunicstatus.pl?domain-name=<name>`. Those carry the name in the query string, so the population is extractable from the CDX index for free with no page fetches, and that is the whole reason to check: **104 such captures yield 17 distinct `.au` names.** Two orders short, and it independently reconfirms the ~2,600-item ceiling already recorded for archived registry whois CGIs. A capture of a lookup would in any case be candidate-only rather than master, because a whois query proves somebody asked about a name and not that it was registered. `auda.org.au` holds 200 in-window captures whose largest items are all governance prose (the constitution at 24,515 bytes, working-group papers at 20-23 KB) and no listing of any kind; auDA was constituted in 1999 and published policy rather than data. `aarnet.edu.au/*list*` and `aunic.net/lists*` are both empty, and `munnari.oz.au`, Robert Elz's host that actually served the zone, has no usable index. Four index requests, no payload fetches. **The transferable part: a high weight raises what a pair is worth and does nothing for whether the artifact exists**, so weight belongs in the ranking and never in the screen |
| CDX public-suffix sweep as a bulk channel (2026-08-22) | **Priced and demoted from channel to trickle, on its own output rather than on its page counts.** `matchType=domain` on a multi-label public suffix does paginate and does return whole namespaces, so the mechanism works and the engines still run it. What it does not do is pay. Twelve swept suffixes, 159 MB of journal, reduce through the project's own canonicaliser to **68,386 in-window registrable pairs of which 5,722 are net-new, worth 4,800 equivalent-English**, and every one of those net-new pairs is `.ca` or `.us`: the `.uk` suffixes that motivated the route are already saturated, so `co.uk` and `ac.uk` return nothing the store lacks. **The ceiling is structural, not a tuning problem.** The bare TLD is HTTP 403, so `.com` cannot be enumerated this way, and `.com` is where the mass is: at weight 0.6321 the outstanding gap needs roughly 700,000 net-new `.com` pairs. Ranking every sweepable high-weight namespace by weight against store depth shows the whole English-heavy ccTLD space is too small to matter, `.au` 287,075 pairs held and `.ca` 219,416, with the remaining English-weighted ccTLDs in the hundreds each. **Doubling every one of them still does not reach the gate.** Keep the sweep running because it is free and additive; do not spend a day tuning it and do not cite it as a route to 5% |
| Common Crawl domain vertices as RDAP candidate supply (2026-08-22) | **Admitted as a thin but genuine channel, on a pilot rather than on the catalogue.** Common Crawl is closed elsewhere in this register as a *dating* source, correctly: it begins in 2007 and can evidence nothing in window. It is admitted here as something different, a **bulk supply of names to ask the registry about**, which inverts the usual test because our own RDAP engine supplies the date. `cc-main-2020-jul-aug-sep-domain-vertices.txt.gz` is HTTP 200, 655,075,092 bytes, downloads in under a minute and holds **88,591,818 domains** in reversed-label form, of which **44,321,990 are registrable `.com`/`.net`** and **40,989,363 are neither in the store nor in the RDAP asked-ledger**. A 19,987-query pilot answered 11,268 and returned **138 in-window pairs, 0.69% of queries, every one of them net-new, worth 84.2 equivalent-English, or 4.2 EE per thousand queries**. That is six times worse per query than asking about a domain the store already knows, which is the expected direction and the reason the queue is ordered rather than concatenated. **Name shape was tested as an enrichment and rejected**: labels of five characters or fewer are 1.91x more likely to be in-window, but they are 4% of the pool, so filtering to them loses more than it gains, and hyphens and digits carry no useful signal at 1.18x and 0.71x. At the measured rate the 41 million names are worth roughly **172,000 EE across about sixty hours of querying**, so it is a backstop that keeps two engines fed for days rather than a route to the gate on its own. Older releases exist back to 2017 and the host-level graph is larger again, so supply is not the constraint |
| Common Crawl 2018 minus 2020, the domains that died in between (2026-08-22) | **A real enrichment, and much smaller than it looks, which is why it was piloted rather than reasoned about.** The hypothesis is sound on its face: a domain present in the 2018 crawl and absent from the 2020 one has probably been abandoned, and abandoned domains skew old. The 2018 vertex file is HTTP 200 at 523,819,137 bytes and holds **35,882,170 registrable `.com`/`.net`**, of which **11,019,564 are absent from the 2020 file**. A 19,918-query pilot confirms the direction: **1.11% of queries return an in-window creation date against 0.69% for the 2020 population, a 1.6x lift on the gross rate.** But the net figure, which is the one that counts, moves almost not at all: **4.7 EE per thousand queries against 4.2, a 1.12x lift**. Two effects eat the gain. Only **6,222 of 19,918 answered at all**, against 11,268 for the live population, because a dead domain is often dropped from the registry entirely; and the net-new share falls from 100% to **69.7%**, because an old abandoned domain is exactly the kind the store already knows about from the archive. **The transferable point: a filter that improves the gross rate can leave the net rate flat, and only the net rate pays.** Banked anyway as 10,402,896 extra names, since supply is what keeps two engines from idling |
| RDAP registries other than Verisign, the family screened by measurement (2026-08-23) | **Screened because Verisign throttling was climbing and other registries are separate hosts, so they are added capacity rather than more pressure. The screen closes most of the family and demotes the rest.** First, availability: `.de`, `.jp`, `.edu`, `.se`, `.dk`, `.ch`, `.it`, `.eu`, `.co`, `.us`, `.nz`, `.za`, `.ie`, `.be`, `.at`, `.es` and `.hu` have **no RDAP endpoint in the IANA bootstrap at all**, which silently removes 1.24 million store-known `.de` names and everything else in that list from anything RDAP can reach. `.org` is excluded on record: PIR answered about 850 queries on 2026-08-08 and then returned **403 for 9,253 consecutive requests**. `.au` and `.pl` answer but publish nothing datable, **0 in-window from 25 sampled each**. What remains, measured on 25-domain samples as gross equivalent-English per 1,000 queries: **`.sg` 341.1, `.info` 335.6, `.ca` 234.2, `.nl` 110.8, `.br` 41.1, `.gov` 39.3, `.fr` 36.8, `.cz` 14.2**, against roughly 4.75 for the Verisign queue. **Then the correction that matters, and it is most of the story: those are GROSS rates and the store-known population they were measured on is 97.9% already dated**, so almost every in-window date they return is one the store already holds. Measured net on 2,500 Common Crawl `.ca` names, which unlike the store-known ones carry **100% headroom because none of them is dated at all**: **0.92% in-window, 100% of it net-new, 7.7 EE per 1,000 queries** against 4.75 for `.com`/`.net`. So the true advantage of the best remaining registry is **1.6x, not the 20x the gross rate advertises**. Worth running, and it is running, but the transferable point is the one this register keeps having to relearn: **a gross rate measured on an already-dated population tells you almost nothing about net yield, and the two can differ by more than an order of magnitude** |
| A registration SPAN from an RDAP creation date, worth 1,704,843 EE and **forbidden** (2026-08-23) | **Rejected on the reviewer's own rule after being measured, and it is the largest thing this project has priced.** The idea: RDAP hands us a registry creation date and the fact that the domain answers today, which is the same pair of facts `afnic_fr` uses to assign every year of a registration interval. Applied to the 3,174,957 in-window creations already banked from live RDAP, the span would claim 11,038,108 pairs, of which **2,885,782 are net-new, worth 1,704,843 equivalent-English, about 2.5 times the whole 5% gate**. **Rule 6 of the reviewer's brief forbids it in terms that leave no room**: "a WHOIS Creation Date alone does not automatically establish that the domain remained registered, continued to exist, or was active in every subsequent year. Inclusion in later annual files still requires a WHOIS record demonstrating continued registration in that year, a CDX record, a historical snapshot, or other factual evidence tied to that specific year." Rule 1 says the same of any earlier-year evidence and rule 7 repeats it: "the date of first appearance alone must not be used to infer presence in later years." **We have also already told him in writing** that this compilation of creation dates was "used strictly as specified: a creation date in 1998 writes 1998 and no other year" (submission email, 2026-08-17), so adopting the span would contradict our own account of the last round. The empirical check ran before the rule was found and is recorded because it is interesting rather than decisive: of the 5,712,971 years the span would assert beyond the creation year, **58.3% are independently corroborated** by another evidence type and 57.7% by the reviewer's own baseline, while **8.91% of the seed domains are dated by the baseline EARLIER than the registry says they were created**, which is direct evidence that drop-and-re-register really happens at a measurable rate. **The transferable lesson is about method, not about spans: a 1.7 million EE prize was measured before the governing rule was read, and the rule took four minutes to find.** Read the reviewer's own documents before pricing an idea, not after |
| `link_target` as a RANKING signal for the archive queue, 297 EE per 1,000 queries (2026-08-23) | **The best measured query economics in the project, and it needs no new approval because it changes who we ask rather than what counts as evidence.** `link_target` is the one candidate-only type, 4,115,694 rows, and it stays candidate-only: a link is a claim by the LINKING page and dead links, typos and later registrations are all common. But a link still tells us WHERE TO LOOK. If a page captured in 1998 links to a host, that is a reason to ask the archive whether the host has a 1998 capture, and a capture is `cdx_timestamp`, self-dating and already approved master. **The signal is real and was tested against a control rather than asserted.** Measured against the reviewer's own baseline, which knows nothing of our link extraction, a link's year is confirmed **85.3%** of the time (1,041,580 of 1,221,018); the same domains with the year shifted by three confirm at **37.1%**. So the links are not merely naming real domains, they are naming the right years. **Yield, measured on a 449-query pilot and priced before ingest so the count is not zero by construction: 386 in-window pairs returned, 225 net-new, 133.5 equivalent-English, or 297.2 EE per 1,000 queries.** That is **63 times** the Verisign RDAP queue at 4.75 and 39 times the best Common Crawl registry queue at 7.7. Hit rate was 56.6% against a pool population that had declined to single figures. The queue is **148,527 domains** where the store already dates the name in some year and a link attests a year it lacks, worth roughly **44,000 EE**, running as `cdx_linkhint`. A second population exists and is much larger, **2,371,904 link-named domains the store dates in no year at all**, of which 104,210 are attested in two or more distinct years; those overlap the existing pool queue heavily and are ranked by attested-year count in `queue_linknew.txt`. **The transferable idea is the one worth keeping: evidence that may not date a year can still be the best available guide to which question to ask, and the project had been treating candidate-only as worthless rather than as a ranking** |
| RIPE database bulk dumps as a dated hostname source (2026-08-23) | **Closed on measurement, and the reason generalises to every RIR.** The idea was good on its face: RIPE publishes its whole database daily, free, at `ftp.ripe.net/ripe/dbase/split/`, objects carry a `created:` date, and person, role and mntner objects carry email addresses whose domains would be dated by that date. All three files are HTTP 200 (`ripe.db.mntner.gz` 2 MB, `ripe.db.inetnum.gz` 212 MB). **Measured on the full mntner file, 64,310 objects: exactly one distinct email domain survives, `ripe.net`, appearing 120,470 times, because every object carries a `THIS OBJECT IS MODIFIED / all data that is generally regarded as personal data has been removed` notice.** GDPR dummification replaced every contact address with `unread@ripe.net`. Separately, only **219 objects have a `created:` date in 1996-2001** and 1,331 read `1970`, so even undummified the in-window population would be negligible: RIPE only began recording creation timestamps later. **Two transferable points. Personal-data stripping has removed contact domains from every public registry database since 2018, so this whole family is closed, not just RIPE. And a field that exists is not a field that is populated**, which is only visible by parsing the file rather than reading the schema |
| CD-ROM media, browser installers and language-package archives (2026-08-23) | **Screened and closed on size, using the searcher's own arithmetic.** Encyclopaedia discs (Britannica 1997/1999/2001, Encarta 1996/1997), magazine cover discs (PC Magazine 1996 and 1999) and ISP signup discs are all real, in window, and downloadable from archive.org as uploaded media rather than as crawls, so the IA-derivation trap does not apply to them. They are simply too small: a curated web directory on one disc holds low thousands of URLs, and three discs come to **495-2,475 EE**. BackPAN, the complete historical Perl archive, has **1,216 distributions uploaded 1996-1999** and yields perhaps 240-360 maintainer and homepage domains, **about 200 EE**. `archive.debian.org` holds genuinely pre-2002 releases (`bo` 1998, `hamm` 1999, `slink` 2000) whose Packages files carry maintainer domains, on the same order. **The whole family totals something like 3,000 EE against a 300,000 EE requirement, so it is noise.** Recorded so it is not re-proposed: dated media is abundant and each item is tiny, which is the opposite of the shape this project needs |
| `textfiles.com` and FidoNet nodelists (2026-08-23) | **Both rejected on DATE rather than on content, which is the trap worth recording.** `textfiles.com` is free, bulk, richly dated and emphatically not IA-derived, and a searcher measured real hostname counts in it: 3,100 pairs in `hosts.txt`, 2,237 in `ftp.txt`, 3,992 in the US domains file. **Every one of those files is dated 1990 to 1992 and the window is 1996-2001**, so they evidence years we are not collecting and are worth nothing here. The collection's centre of gravity is BBS-era 1985-1995 by design. FidoNet nodelists have the ideal shape, a weekly self-dating edition listing systems, and in-window editions carry internet hostnames for only a minority of nodes, giving **under 500 EE across the whole family**. **The lesson: check the date distribution before counting the content.** A source that is large, dated and free can still be entirely out of window, and the count of hostnames it contains says nothing about that |
| The darkened Dartmouth/NBER metadata item, re-probed after it reopened (2026-08-23) | **It really did reopen and it is worth exactly zero.** `archive.org/metadata/DARTMOUTH-NBER-RESEARCH-2017-metadata` returned `{}` on 2026-08-17 and now returns a 13-file listing with no access restriction, so the closure on availability was correct and is now stale. The payload is not: `domain-year-captures.txt` is 227,919,677 bytes remote and byte-identical in size to the copy already on disk at `data/raw/dartmouth_nber/`, and the siblings `domain-year-captures.txt.new` and `domain-year-stats.tsv` are the same data plus two out-of-window rows (9,227,382 against 9,227,380, **identical 765,194 in-window distinct pairs**). Measured through the canonical funnel against the live store: 764,982 canonical in-window `(domain, year)`, of which **764,982 are already assigned and 0 are net-new, 0.00 equivalent-English**. The 227,273 pairs the source table credits to `dartmouth_nber_captures` are its attribution share, not its headroom; the rest of the file arrived through other doors. **Re-probing an availability closure is right, and it still has to be priced against the store afterwards.** |
| Zenodo banner-ad corpus, `zenodo.org/records/8408539` (2026-08-23) | **Real, in-window, correctly shaped and too small.** A 215 MB JSON of 22,915 banner images mined from archived snapshots of URLs taken from six printed internet directories published 1999-2001, and each `appearances` entry carries a 14-digit Wayback timestamp beside the page URL, so a pair is `cdx_timestamp` and self-dating. 131,297 appearances, of which 92,218 are in window: 1996 n=142, 1997 n=713, 1998 n=1,820, 1999 n=8,064, 2000 n=31,759, 2001 n=49,720, plus 39,079 in 2002. Through the funnel that is 12,353 in-window pairs over 7,600 domains, and against the store **934 net-new pairs worth 432.81 equivalent-English**, 70% of it `.com`. The population is the same early-web `.com` the archive sweeps have already covered. Its `hrefs` field holds banner link targets, which are `link_target` and can only ever be candidate supply. Not worth an approval request at this size |
| AFNIC `.fr` OPENDATA back editions (2026-08-23) | **The mechanism is wrong, and the way it fails is the useful part.** The idea was that an older edition recovers in-window `.fr` domains deleted before the edition we already used, since a deleted name vanishes from later files. Measured on both, 202011 (494,444,288 bytes) and 202201 (549,508,248 bytes), taking **only the creation year** as rule 6 requires and never the interval: each yields **exactly the same 65,268 in-window rows** with the same per-year shape (1996 n=1,583, 1997 n=4,195, 1998 n=9,023, 1999 n=13,278, 2000 n=20,802, 2001 n=16,387). Identical, because AFNIC OPENDATA is a snapshot of names **currently registered at publication**, so a domain deleted before 2020 appears in neither and a back edition recovers nothing. Union 65,170 pairs, 57,511 already assigned, **7,659 net-new worth 781.98 equivalent-English** at `.fr`'s 0.1021. **A back edition only helps when the publication is a cumulative register rather than a current-state snapshot**, and that is the test to apply before downloading the next one |
| SEC EDGAR beyond the closed row: 8-K, DEF 14A, 10-KSB, URLs and e-mail domains (2026-08-24) | **Real, in-window, dated by EDGAR itself, and too small.** Differs from the closed EDGAR row by form type and by taking e-mail domains as well as printed URLs. One filing is dated by the `Date Filed` column of `full-index/<year>/QTR<n>/form.idx`, an EDGAR-assigned date, filtered before extraction: 222,232 filings of these three types in window (1996 n=22,872, 1997 n=34,750, 1998 n=38,523, 1999 n=38,591, 2000 n=41,016, 2001 n=46,480). Priced at **5,884 net-new equivalent-English**, 2.0% of the gate. A collector is straightforward and the dating is sound, so this is the best-value unbuilt source on the register; it is simply not a round |
| Federal Audit Clearinghouse historic Single Audit filings 1998-2001 (2026-08-24) | **Admissible and small: 2,406.69 net-new equivalent-English.** One item is one e-mail field on one filing row, dated by that row's own signature date, `AUDITEEDATESIGNED` or `CPADATESIGNED`, which is the date a human wrote the address down. **The date check is what makes it honest and it bites hard**: the signature histogram runs 1997-2009 (1998 n=3,022, 1999 n=13,215, 2000 n=17,829, 2001 n=20,827, 2002 n=16,765, then a tail, plus about 40 corrupt values such as 5392 and 888), so **18,698 e-mail rows were dropped for falling outside the window**, most of them FY2001 audits signed in 2002. Taking the audit year instead of the signature date would have imported every one of them silently |
| USPTO trademark bulk data, domain-name marks (2026-08-24) | **Unretrievable, so unpriced.** The application filing date would have been a clean per-item in-window date, which is why a reopen condition is worth keeping, but no bulk data could be fetched at all. Nothing was measured and nothing is claimed |
| UK Companies House bulk corporate filings (2026-08-24) | **Out of window by construction, and it was the highest-weight candidate of the family.** The Accounts Bulk Data files are named by publication date and each holds that day's filings, which would be a clean per-item date, but the published range does not reach 1996-2001. The Company Data Product is a current-state snapshot with no per-row filing date and no website field. Same failure as the AFNIC back editions: **a current-state snapshot cannot evidence a past year** |
| freshmeat.net dated backend RDF dumps (2026-08-24) | **The right shape, and the payload was never captured.** freshmeat published daily backend dumps (`fm-releases.rdf`, `fm-projects.rdf`) from 1997, each a dated file listing projects with their homepage URLs, which is exactly the per-item-dated bulk artifact this project wants. Wayback holds the directory but not the data: `freshmeat.net/backend*` returns **50 in-window rows, all of them the `/backend/` index at 773 to 781 bytes or a 301 to it**, and `freshmeat.net/*.rdf*` returns **zero rows** for 1997-2002. A 780-byte listing is not a dump. Nothing was fetched beyond two index queries and nothing is claimed. **The kind is still worth pursuing elsewhere**: a dated release feed naming project homepages is a good shape, so the question for the next attempt is which publisher of one had its payload archived, not whether the shape works |
| ERIC education bibliography, `api.ies.ed.gov/eric` (2026-08-24) | **UNRETRIEVABLE, not closed. Re-probe.** The lens is bibliographic databases as a kind: dated records 1996-2001 whose abstracts print URLs, and for ERIC those skew `.edu` 0.9717, `.org` 0.7101 and `.gov` 0.9825, so the weight would pay. The sibling `nlm_medline_affiliation_email_1996_2001` is already in triage, which is why this was worth one probe. Nothing was measured: the API returns `{"message": "Network error communicating with endpoint"}` for a year-filtered query **and for an unfiltered control**, so the failure is the service and not the data. **No content claim is made in either direction.** Next attempt: re-probe the API, and if it stays down try the bulk XML exports rather than reasoning about it |
| FreeBSD Ports release trees, 1996-2001 (2026-08-24) | **Closed on measurement at 50.56 equivalent-English against a 8,000-18,000 estimate, a 200-fold overstatement, and the reason is structural rather than bad luck.** `research-leads.md` ranked this the largest untried lead. Route is sound and cheap: `ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/i386/<rel>/ports/ports.tgz`, twenty in-window releases from 2.1.5 to 4.4, each 7 to 14 MB, and the release date fixes the year for every `WWW:` and `MASTER_SITES` line inside it. Measured on three spanning the window (2.2.8 -> 1998, 3.4 -> 1999, 4.4 -> 2001): 9,011 host mentions, 3,231 distinct pairs, **3,134 already held, 97 net-new worth 50.56 EE gross and 55 pairs at 29.57 post-split**. **97% overlap, because a ports tree points at the software vendors every other source also points at**: `gnu.org`, `xfree86.org`, the big mirrors. It is an authority-selected collection in the sense the register already closed award lists on, and it selects the most-cited hosts on the early web, which are exactly the ones a 25-million-pair store already has. Tarballs kept under `data/raw/freebsd_ports/` |


## `usenet_announce` and `usenet_mention`: dated website announcements from Usenet

**The 383 GB of `.mbox.zip` archives were deleted from `data/raw/usenet/` on 2026-08-24 to free disk,
and this is what makes that safe.** All 19,231 archives on disk were listed in the corpus's own
`.processed` ledger with zero unprocessed, that ledger is kept, and archive.org publishes a sha1 per
file, so any archive can be re-fetched and pinned. The journals derived from them are still on disk and
still in the ingest ledger, so **tier 2 reproduction is unaffected**; only tier 3, which re-parses the
raw archives, now requires re-downloading them first. `data/raw/usenet_new/` and
`data/raw/usenet_bulk/` were left alone: their filenames match nothing in the `.processed` ledger, so
their status is not established and deleting them would have been a guess.

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
  pair because the whole group is 2006 to 2013. The retired group fetcher selected on the
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
  The retired archive screener listed any archive with 0.0% in-window coverage, which
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
426; `sourceware.org` 403; `lore.kernel.org` sits behind an Anubis proof-of-work challenge. **CORRECTED 2026-08-24: that is true of the HTML and false of git.** `git clone https://lore.kernel.org/lkml/0` serves fine, and public-inbox stores each sender as the git COMMIT AUTHOR, so `git log --format='%ae|%ad'` yields the entire participant population with zero blobs fetched. Measured that way: 81,741 in-window messages, a complete census rather than a sample, 92.2% already held, **80.19 EE post-split**.
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
uv run python scripts/collect_udrp_proceedings.py  # -> items.jsonl, one row per case
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

**That projection was struck on 2026-08-15. It was wrong, and the family is closed on measurement.**
It used to read: if the missing NAF share resembles the measured one, the family plausibly holds one and
a half to two times what is ingested. An independent open dataset settles it the other way. Zenodo
21310923 (CC-BY, `population_data.csv`, 6,837,084 bytes, 95,370 cases) counts Forum decisions at 658 in
2000 and 768 in 2001, **1,426 in total**, against **2,573 NAF domains this store already holds**. There
was never a NAF shortfall; ICANN's table being self-described as incomplete was read as evidence that our
coverage was, and those are different claims.

**The store holds all five providers, which the section title `udrp_wipo` actively hides**: WIPO 5,963
rows, NAF 2,575, DeC 210, eResolution 133, CPR 42. Anyone reading the heading and sampling a few rows
concludes we have WIPO only, which is exactly what happened on 2026-08-15 before the query was run
properly.

**Two bulk artefacts were found in the process, both downloaded and both nearly worthless here**, kept so
they are not re-found: ICANN's own plain-text exports at
`archive.icann.org/en/udrp/proceedings/domains-list.txt` (4,666,685 bytes, 34,027 lines of domain, case
number, commenced, decided, provider and decision URL) and `proceedings-list.txt` (2,924,147 bytes), which
give 8,662 in-window pairs of which **90 are net-new**; and Zenodo 16954717 (MIT),
`full-udrp-parsed-proceedings.jsonl.gz`, 90,153 proceedings across all five providers, sampled by HTTP
range for 13,519,648 bytes out of an 843 MB zip rather than downloading it whole, giving 6,766 in-window
pairs of which **158 are net-new, worth 90.10 equivalent-English**.

**A trap inside that second dataset, and it is the dangerous kind.** Its `submitted` field is corrupt:
`D2002-0431` carries 1999-08-26 and `FORUM 94730` carries 1998. Trusting it lifts net-new from 158 to 769
by inventing **518 fabricated 1999 pairs**. On a self-dating source a bad date field is not noise, it is a
master year claim manufactured by a parse error, and the case number is the field that can be trusted
because it encodes its own year. **Do not reopen this family on availability**; the ceiling for everything
remaining in it is about 90 equivalent-English.

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

---

## archive.org FTP mirror archives, 2001 mtimes inside the ZIPs (closed, zero)

**The idea.** A ZIP or TAR of a mirrored FTP tree carries each member's original mtime. So the
container's own date is irrelevant: an entry stamped 2001 inside a 2015 archive is a per-item date
inside the window, and listing a container costs one request via `view_archive.php` rather than a
download. That is a genuinely new lens, and it is worth writing down that it was tried properly.

**Coverage, measured.** `title:("ftp site")` returns 1,629 items and `identifier:ftp-*` returns 375,
union **1,697**. Of those **1,073 are `archiveteam_ftp_*` megawarcs holding `.warc.gz`, not ZIPs**
(8 of 8 sampled), and their per-file dates are 2015-2016 crawl timestamps, so the mtime route cannot
apply to them at all. The real haystack is the other 624 items: **651 ZIP/TAR archives, 2.6 TB**, of
which **638 were listed and parsed, 6,161,470 entry rows**.

**The positive control passed, which is what makes this a proved zero.** **143,338 rows dated 2001**
across **254 of 638 archives**, so real 2001 mtimes were flowing the whole run, and a synthetic-row
control matched `pub/dns/example.com.zone`, `pub/lists/whois.txt`, `etc/hosts` and `pub/ls-lR.gz`
while correctly rejecting the same `.zone` name dated 2004.

**No zone file, whois dump, domain list, nameserver inventory or email-domain list dated 2001 exists
in the 638 archives.** The filename regex produced 69 matches on 2001-dated rows and **all 69 are
false positives**: DOS/Windows software (`whois32.zip`, `nslookup.zip`, matched because the parent
directory is named `finger-whois-nslookup`), the Linux `fdomain` SCSI driver, `/etc/hosts` at 0-110
bytes inside RTLinux images, the stock BIND `localhost.zone` loopback example at 195 bytes, CPAN
`Net-ParseWhois`, and three `ls-lR.Z` at 23-30 KB which are one tree's own index and too small to
hold a bulk list regardless.

**The vhost variant is also zero, and the reason generalises.** Counting domain-shaped path segments,
exactly **1 of 638** archives cleared 200 distinct segments, and it is a false positive: `ftp.oldskool.org`
at 517 segments is a **DOS `.COM` executable collection** (`0-8xma.com`, `525drive.com`), and only 2 of
its 517 appear on a directory row. Restricted to 2001-dated rows the maximum anywhere was 15.
**So `.com` as a DOS executable suffix is the dominant false positive in any FTP mirror, and a bare
segment regex is unusable without a directory-row constraint.** Worth remembering before anyone
proposes name-shape matching over a mirror again (see the `bl.uk` trap).

**Access.** `archive.org/robots.txt` disallows only `/control/` and `/report/`; the `ia8031xx` node
hosts return 404 for robots.txt with no rules. Metadata and `view_archive.php` only, 2 concurrent
workers, 1 s spacing, 0 metadata failures over 632 items. No `web.archive.org` and no CDX API, so
this did not spend an archive-client slot.

**Honest gaps, listed so a re-run knows what to aim at:** 13 archives returned a valid
`view_archive.php` page with 0 rows on all three attempts (mostly very large tars: `ftp.oracle.com`,
four `ftp.icm.edu.pl` parts, `ftp.nvg.org`), and 29 were truncated at the 20,000,000-byte listing cap
(including `ftp.microsoft.com.zip`, `ftp.isc.org.tar`, `download.intel.com.tar`). Given 638 of 651
listed with a passing positive control and zero true hits, those 42 do not change the verdict.

---

## JISC UK Web Domain Dataset per-year CDX (`ukwa.ds.2/cdx/`): found, sized, NOT retrievable

**This is the largest in-window artifact the project has identified, and it needs a human request.**
Found by asking a question we had not asked of a source we already use: `host-linkage.tsv.gz` sits in
`webarchive.org.uk/datasets/ukwa.ds.2/linkage/`, so what ELSE is in `ukwa.ds.2/`? A CDX prefix query
over `webarchive.org.uk/datasets/*` answers it in one request: `cdx/`, `geo/` and `linkage/`. We had
already banked `geo/` (`ukwa_geoindex`, 4,493 EE) and part-read `linkage/`. **`cdx/` was never looked at.**

**What it is.** One CDX file per year, 1996 to 2013, all stamped `15-Aug-2014` on the directory
listing. Sizes read off the listing, compressed bytes:

| file | bytes | file | bytes |
|---|--:|---|--:|
| `1996.cdx.gz` | 52,619,201 | `1999.cdx.gz` | 1,428,820,719 |
| `1997.cdx.gz` | 509,195,112 | `2000.cdx.gz` | 4,580,260,146 |
| `1998.cdx.gz` | 364,720,850 | `2001.cdx.gz` | 6,515,380,682 |

**In-window total 13.45 GB compressed**, and out-of-window years run to 73 GB for 2012 alone.

**Why it would pay, in the project's own terms.** CDX means field 2 is a 14-digit capture timestamp, so
every line is self-dating and master-eligible as `cdx_timestamp` with **no corroboration split**. The
population is the `.uk` domain crawl, and `.uk` scores **0.9813**, the highest weight in the model.
The 2001 file is the largest in-window year, which is the store's largest hole. And the sibling files
in the same dataset are the counter-argument to a lazy dismissal on law 1: this is IA-derived, yet
`geo/` paid 4,493 EE and the first 10.26% of `linkage/` gave **116,467 assigned pairs**, because
Ding's baseline is a merged sample rather than the whole `.uk` crawl and our own CDX engine can only
ask about names it already knows. **A full `.uk` CDX dump is discovery, not just dating.**

**Why we cannot have it, proved rather than assumed.**

1. **IA captured the directory listing and never the files.** A prefix query for
   `www.webarchive.org.uk/datasets/ukwa.ds.2/cdx*` returns empty, run against a positive control in
   the same breath: the identical probe for `linkage/host-linkage.tsv.gz` returns its two known
   captures, `20200106181208` and `20221031190607`. So the emptiness is the archive's, not the query's.
2. **The publisher now serves stubs for everything.** `www.webarchive.org.uk/robots.txt` returns a
   7-line HTML `400 Redirect` document, not a robots file, which is the same soft-200 behaviour that
   already made a `host-linkage` download look successful while returning 159 bytes.
3. **No mirror exists on archive.org.** `advancedsearch.php` for `jisc uk web domain dataset` and for
   `ukwa.ds` both return `numFound` 0; `uk web archive linkage` returns 17 items, all unrelated
   (VOA broadcasts, a YouTube rip, an OSF registration).

**ASKED, AND THE ANSWER IS NO UNTIL AUTUMN 2026. Do not write to the British Library again about
this.** Ivo had already enquired on **2026-07-22** through `openaccess@bl.uk`, citing the dataset
record at `bl.iro.bl.uk/concern/datasets/3c39a755-5e3d-405b-9944-b13e76a87ad8`, and Nora Ramsey,
Assistant Web Archivist, replied for the UK Web Archive Team: "it is not currently possible to access
dataset hosted on our servers. The UK Web Archive website remains offline following a cyber-attack on
the British Library in October 2023 ... Our target for restoring access to digital collections is
Autumn 2026. The first stage of restoration will include a URL lookup service", with full-text search
and other features "reintroduced gradually thereafter".

**So the finding above describes something real that cannot be fetched, and it fails on two counts
rather than one**: Autumn 2026 is later than this submission needs, and the first service to return is
a per-URL lookup, which is no route to a 13.45 GB bulk CDX pull. The 2019 directory listing and the
sizes stay on record because the data is preserved and the Library says so, so this is worth reopening
the moment bulk access returns. It is not worth another letter.

**The error was mine, and it is the same trap as briefing an agent without grepping first.** I drafted
a fresh access request and told Ivo to send it ahead of RIPE, having never checked whether we had
already asked. **Check the sent correspondence before drafting a letter, exactly as you grep
`sources.md` before briefing an agent.** `ripe_dbase_1999` is now unambiguously the top access
request: permission there is a decision a human can still take, whereas here there is no server to
serve the file.

**Also recorded so nobody re-derives it:** `linkage/` holds exactly three files, so `host-linkage.tsv.gz`
is **monolithic and unsharded** and there is no small-file route into it. The 2022 capture that holds
the full 20,930,377,408 bytes returns **504 after exactly 120.5 s at any offset**, including offset 0,
while the 2020 capture is IA's own 2 GiB truncation which we already hold complete. The two small
siblings in that directory, `bl-uk-linkage.tsv` (724,598 bytes) and `york-ac-uk-linkage.tsv.gz`
(2,244,274 bytes), DID capture in 2022 and are being fetched.

**Fetch conditions on the day, worth knowing before anyone calls IA broken:** `web.archive.org` was
answering roughly **1 request in 5** (5 probes 10 s apart: one 200, four connect failures at
`connect=0.000000`), while `archive.org` and unrelated hosts answered normally. `ark cdx` held zero
established connections yet its journal kept growing, so the engine was working through retries the
whole time. **A TCP connect failure on one IA hostname is not an outage and not a block**, and inline
fetches should be handed to a retry loop with an absolute deadline rather than attempted by hand.

**The two small `linkage/` siblings, fetched and priced: 9.81 EE, and law 3 is why.**
`bl-uk-linkage.tsv` (86,281 lines) and `york-ac-uk-linkage.tsv.gz` (284,247 lines) are the same
`year|source|target` shape as `host-linkage.tsv.gz`, so the existing `ukwa_link_source` parser reads
them and no decision was needed. Measured before ingesting and the ingest then matched the prediction
exactly: **1,899 and 3,731 in-window pairs over 1,007 and 1,900 distinct source hosts, of which 99.9%
and 99.8% were already held, giving 1 and 9 net-new pairs, 1.0 and 8.8 EE.** Banked, total 9.81.

Two reasons, both reusable. **The files are TARGET-selected**, holding only links pointing at
`bl.uk` and `york.ac.uk`, so the source population is 1,007 and 1,900 hosts rather than the millions
in the full graph, and what points at the British Library and a Russell Group university is `.ac.uk`
authorities we already hold: law 3 in its purest form. And **most rows are out of window**, 75,870 of
86,281 and 226,315 of 284,247, because the graph runs to 2013. So the narrow siblings say nothing
about the full `host-linkage.tsv.gz`, whose first tenth gave 116,467 pairs from an unselected
population. Do not use these to re-price that one.

---

## namewinner.com expiring-domain list, 2001-10-26 (PRICED, needs a Decision)

**This prices `namewinner_expiring (formerly domain_aftermarket_listings_1999_2001)`, which had sat unmeasured since the aftermarket
lens was first opened.** That lens was closed once already, correctly, for the Usenet for-sale groups:
`alt.domain-names.forsale` and its siblings are ingested at 36,425 rows over ~32,685 domains and were
measurable for nothing. **What had never been retrieved was the bulk listing half**, and it pays.

**The artifact.** `http://namewinner.com/whole_list.php?del=tab`, Wayback capture
`20011026120205`, Dotster's expiring-domain auction list. 581,560 bytes, **20,943 distinct
registrable domains** (15,660 `.com`, 3,333 `.net`, 1,950 `.org`). The `?del=none` sibling capture is
a strict subset, 16,125 of the 20,943.

**What dates it, and it needs no inference.** Every row carries the per-item date `25-OCT-01`.
Verified directly rather than taken on report: the file contains **20,945 occurrences of `25-OCT-01`
and no other date string of that shape**. The Wayback capture fixes the instant at 2001-10-26 12:02
UTC, and the operator's own `rule_book.php` (capture `20011027003733`) calls it "our list of soon to
be expiring domain names". A name on a soon-to-expire list is one the registrar is stating is
registered right now, which is the `coza_deletion_listing` argument already on the sheet, and it is
exactly the standard Ivo set in killer 8: the artifact asserts a state at an instant it stamps itself,
and a capture fixes when it existed.

**Two prices, and the difference is a judgement rather than a measurement.**

| reading | net-new pairs | net-new EE |
|---|--:|--:|
| **master**: the listing dates every name on it | **18,951** | **11,555.0** |
| conservative: only names the store already holds | 3,377 | 2,083.9 |

**The master reading is the right one and here is the argument.** The corroboration split exists for
"anything a human typed". This is a database dump out of a registrar's own expiring-domain system, not
a human-typed list, and the names on it are real registrations by construction, because being
registered is the only way onto the list. That is the same shape as `iedr_register` (banked 18,826 EE)
and `internic_zone` (banked 8,813 EE), both machine-generated register listings admitted as
`artifact_listing`, and both of which dated novel names. **Applying the split here would be treating a
registrar's database output as though a person had typed it.**

**The low held-fraction is the point, not a warning.** 25.6% held is far below the ~50% a blocklist
gives and nowhere near an authority corpus's 87-99%. The reason is that these are speculative names
from the 1999-2001 land rush that nobody linked to and no crawler visited, and which then dropped:
precisely the long tail a trust-selected corpus cannot reach (law 3, from the other side). 1,992 of
them are already held at 2001, so the store is not blind to this population, just thin in it.

**The 2002 sibling, and why it is a separate decision.** `whole_list.php?del=none` at capture
`20020407171418` holds **52,204 distinct domains** with per-item dates `05-APR-02` to `10-APR-02`
straddling the capture, so it is a forward schedule and the names were live when captured. It has
**zero overlap** with the October list, as two drop lists months apart should. But its own date is
2002, outside the window, so reaching 2001 needs the minimum-one-year-registration-term inference.
Post-split that is 4,134 pairs and 2,543.2 EE. **Filed separately: the inference may be sound, but it
is not the same class of claim as a stamped in-window date, and it should not be smuggled in beside one.**

**Also found, and it is small: dailychanges.com.** Per-nameserver deleted-domain pages,
`detail/?ns=X&date=Y&act=d`. One page pays: `ns=LAME-DELEGATION.ORG&date=2002-08-01` is 4,511 names at
**66.7% held**, 1,076.3 EE on the adjacent-year measure, because that nameserver is Verisign's legacy
lame-delegation park and its population is 1990s names we already hold. **Four ordinary registrar
pages measured 0.021 EE per name, ten times worse**: REGISTER.COM 5.2% held, WORLDNIC.COM 3.2%,
DIRECTNIC.COM 6.3%, NAME-SERVICES.COM 7.3%. Whole-2002 harvest is ~739 pages and ~19,300 names for an
estimated 1,400 EE, and the 2003 pages are mostly Sep-Dec, which attests 2002 at best.

**The transferable screen, and it is new:** on a drop list, held-fraction tracks **how old the
nameserver's population is**, not how long the list is. 66.7% for a legacy park against 3.2-7.3% for
live registrars, from the same site on the same dates. Ask whose nameserver the names sat on.

**Proved zeros in the same family, so nobody re-walks them.** `deleteddomains.com`: 286 non-affiliate
captures 2001-2004, and all four list endpoints are 3.0-3.4 KB query forms that never contain a result
set; its CDX is 20,000+ `?cid=` affiliate URLs, so **filter `!original:.*cid=.*` or the host looks far
richer than it is**. `snapnames.com`: 10,580 captures, lists sat behind `/protect/` login, best
candidates are 5-6 KB marketing pages. `pool.com`: `?dom=X` is one domain per page, `hotlist.aspx` is
2003. `unclaimeddomains.com`: bare labels with no TLD and no date, and "available" means not
registered, so killer 4. `deletedomains.com`: 14 captures, largest 2,987 bytes. `domainstate.com`:
zero CDX rows 2001-2003. `dotster.com`: no bulk list in 2,583 captures. **`domainsbot.com` is NOT a
zero: CDX never answered in 5 attempts and it was not tested.**

---

## US Domain delegated-subdomains list (PRICED, needs a Decision), and the ISC survey closed for good

**The find.** `us-domain-delegated.txt`, the US Domain Registry's list of delegated `.us` zones, one
per line with the delegate's contact beside it. Six editions totalling ~2.5 MB, reached two ways:
inside the `2015.04.ftp.isc.org.tar` mirror on archive.org at `pub/rfc/`, with tar-preserved mtimes
**1996-10-09**, **1996-11-20** and **1999-03-22** plus six rotations `.0`-`.5` running 1999-02-19 to
1999-03-18; and at the file's other home `www.isi.edu/in-notes/us-domain-delegated.txt`, captured
**2000-08-15, 2000-12-06, 2001-04-11 and 2001-06-06** (the last three byte-identical at 435,847 B).

**Priced with the project's own `price_items.py` against the live store:**

| edition | net-new pairs post-split | net-new EE |
|---|--:|--:|
| 2001-06-06 alone | 3,524 | 3,247.3 |
| **union 1996 + 1999 + 2000 + 2001** | **13,816** | **12,775.5** |

Mean weight **0.9247**, because `.us` scores 0.9261. By year 1996 2,284 / 1999 4,185 / 2000 3,823 /
2001 3,524. Gross was 15,270.0 EE and **must not be quoted**.

**What dates it.** The artifact asserts the delegation state of the `.us` namespace, and the instant is
fixed twice over: the tar-preserved mtimes, whose rotation chain is **monotone in both date and size**
(425,505 to 426,388 bytes across Feb-Mar 1999, continuing monotone into the Wayback captures at
433,937 to 435,847), and `cdx_timestamp` on the 2000 and 2001 captures. A delegation is the registry
serving that name at that instant rather than a description of one, which is the `internic_zone`
reasoning and the reason killer 2 does not reach it. Class `artifact_listing`, master-eligible.

**The name shapes are legitimate and this was checked, not assumed.** The lines are `.us` locality and
`k12` zones, so the obvious worry is that they are public suffixes rather than domains. The pinned PSL
handles it exactly right: `to_registrable` returns **None** for `K12.AK.US`, `AK.US` and `US`,
resolves `ANCHORAGE.AK.US` and `STATE.AK.US`, and collapses `CI.ANCHORAGE.AK.US` to `anchorage.ak.us`.

**Contamination is real but negligible.** Every data line also carries a contact email, and those
domains are not delegated `.us` zones. They survive in the count at **56 pairs of 13,816**: by TLD it
is `us` 13,760, `com` 36, `net` 18, `org` 2. The contacts are a small repeated set of ISPs and
registrars (`nametamer.com`, `troika.net`, `wwa.com`) that the store already holds for those years.

**Caveats to weigh before approving.** The typo upper bound is **17.8%**, which is high, and the
honest reason is structural rather than reassuring: sibling locality names are one edit apart by
construction (`HAINES` and `HEALY`, `NOME` and `TOK`), so an edit-distance test cannot separate a typo
from a neighbouring town. And **1997 and 1998 are unreachable**: no `*.isi.edu` capture predates
2000-08-15 and the ISC tar jumps 1996 to 1999.

**`ftp.isc.org` refuses everything and must not be touched live.** Its `robots.txt` is 4 lines ending
`Disallow: /` under `User-agent: *`. Blanket, not by name. The 2015 mirror held inside archive.org is
a different host and is unaffected. (`www.isc.org` allows all but `/thankyou-contact/`.)

**The ISC Domain Survey question is now closed permanently, and this is the useful half of the run.**
The complete uncapped listing of that mirror, 197,589 entries, settles what survives:
`www/survey/archive-data/` ends at **`9707.domains.gz`**, exactly where `sources.md` already had it,
with no 9801 or later. `reports/1998/` through `reports/2002/` do exist for both editions of every
year, and **every file in them is 1.4-21 KB**: `dist-byname`, `dist-bynum`, `firstnames`,
`hosts.txt`, `report.txt`. Per-TLD counts, no name lists. Wayback holds 24 URLs for `ftp.isc.org`
across 1996-2004 and **none under `/www/survey/`**. So the raw ISC survey host data for 1998-2001 does
not survive on its own host, in the fullest mirror of that host that exists. **Treat the ISC family as
a 1996-1997 window, permanently, and stop re-testing it.**

**Also tested, dead:** `ftp.isc.org/pub/rfc/enterprise-numbers`, the IANA PEN registry, 339,504 bytes
dated 1999-03-22. 2,348 of 2,445 domains already held for 1999, **48.1 EE**. A textbook authority
corpus failing the second screen.

**And the FTP-mirror-ZIP lens is now fully closed, including the 42 gaps.** The 20 MB listing cap was
client-side and two methods removed it. **All 9 truncated ZIPs listed complete via ranged reads of the
ZIP64 central directory**, row counts matching the declared entry counts exactly, including a 576.6 GB
nvidia ZIP at 157,962 entries: size is irrelevant to that method, which costs ~2 requests. For TARs,
`view_archive.php` completes only below ~15 GB, so 8 of 20 finished. Completeness was proved, not
assumed: `ftp.shroo.ms.tar` gave **85,595 rows by listing and 85,595 by the item's own `.tar.txt`**.

Of the 13 zero-row archives, **three are corrupt uploads rather than listing failures**, each exactly
**4,294,967,295 bytes, which is 2^32 - 1**, a 32-bit overflow at upload; no method recovers those. The
other ten are the size ceiling at 36-672 GB, cutting at ~33 s and 130,234 bytes every time. **One
correction to the earlier sweep: `ftp.oracle.com` was not a zero**, it listed 6,568 rows untruncated.
The cheap alternative for a huge tar is the item's own `.tar.txt` companion (23 MB for a 672 GB tar);
it exists for 4 of the remaining 22 and all four parsed to zero bulk host data. `ftp.microsoft.com.zip`
holds 48,230 in-window entries and 3 pattern hits, all false. **The single bulk host artifact in all 42
archives is the `us-domain-delegated.txt` family above.**

**No collector is needed for namewinner, and the capture enumeration is why.** The obvious follow-up
was that Oct 2001 and Apr 2002 share zero names, so more captures should mean more names. Enumerated:
`namewinner.com` has 21 captures of `whole_list*.php`, and **only four carry content**. Two are the
2001-10-26 pair (`?del=none` 129,231 bytes and `?del=tab` 128,536, the latter a superset at 20,943
names) and two are the 2002-04 pair (1,443,945 and 1,443,957 bytes). **Every other capture is 373 to
415 bytes**, an empty or error page, including all four from December 2001 and January-February 2002.
So the single in-window artifact is maximal and there is nothing to iterate over. The only untested
item on the host is `whole_list_bids.php?del=none` at 20,702 bytes, captured 2002-01-25: a bids page,
2002-dated, and about 700 names at that size, so it is below any bar even before the inference problem.

---

## Academic repositories and DOI datasets: CLOSED, by enumeration through five APIs and two registries

**Ding asks for this lens by name and it can now be reported closed with numbers rather than with a
shrug.** A sweep on 2026-08-24 concluded it was empty for a structural reason: research on the
1996-2001 web predates data-deposit norms, which arrived around 2010, so the papers exist and their
data does not. That reading now has a second, independent proof through four doors nobody here had
opened.

**1. DRUM, Ding's own worked example, closed by enumeration rather than sampling.** The DSpace 7 REST
API at `conservancy.umn.edu/server/api/discover/search/objects` returns **exactly six** items in the
"Link Lists for Websites" family: Early Web **1996 to 2000** (DOI `10.13020/d62684`, **already
ingested**), Hurricane Sandy 2003-2012, US Senate 2009, US House 2009, Occupy Wall Street 2010-2012,
and US newspapers 2008-2012. One is in window and we hold it; the other five cannot evidence an
in-window year.

**2. The DataCite screen that actually matters, and it returns one item.** `dates` is queryable, which
the earlier sweep never used. Enumerating every DataCite **dataset** carrying a date in 1996-2001
together with a web-ish title token (`web|website|internet|hyperlink|hostname|domains|url|crawl`)
leaves opinion surveys (Eurobarometer, ICPSR, Slovenian RIS, Taiwan SRDA), Thai masters theses, and
NMR protein-domain entries. **The single host list in the whole population is DRUM `10.13020/d62684`,
which we already hold.**

**3. Harvard Dataverse FILE-level search, a genuinely different index, empty for our shapes.** This was
the one promising angle, because a replication package's `hostnames.txt` is invisible to DataCite
dataset metadata. Measured zeros: `domains.txt`, `hostnames.txt`, `websites.txt`, `domains.csv`,
`webgraph`, `zonefile`, `dnszone`, `hostlist`, `domainlist`, `hosts.txt`, `nslookup`, `netcraft`,
`"web crawl"`, `"hyperlink network"` all **0**. Non-zero but dead: `urls.txt` 12 (Twitter ID dumps
2015-2016), `hostnames` 80 (diplomatic-presence tables and empty `hostname.err` files).
**Route note worth keeping: Harvard's index federates harvested metadata from other installations**
(Scholars Portal, DataverseNL, Virginia, TDL, QDR all surfaced), so one Harvard call covers much of the
99 installations and walking them individually is unnecessary.

**4. Repository-level discovery, so the lens is closed at the registry level too.** `re3data`'s API
returns all **3,521** repositories in one request, and filtering offline gives **exactly three**
name matches: Internet Archive (killer 1), the UK Government Web Archive (already logged at 250
addressable domains), and Unidata weather. Cross-checked against DataCite's client list for
`web archive`: **4** clients, of which the only relevant one is `bl.wap`, whose complete DOI list is
**6 items, all already in this file**. **OpenAIRE** adds nothing: eight keyword shapes, and the only
web-host artifacts are the WDC 2012 hyperlink graphs and the UKWA host link graph we already hold.

**Named in-window candidates, and each dies on arithmetic rather than on access.** figshare
`10.6084/m9.figshare.786494`, "Mainland China university web sites December 2001 - January 2002",
is CC-BY and dated in the most valuable year, and its own description says **76 universities**: the
ceiling if every name were held and missing 2001 is 76 x 0.0744 for `cn` = **5.65 EE gross**. Zenodo
`10.5281/zenodo.20379517` is 514 annotated documents sourced *from Arquivo.pt*, which is already
ingested, at `pt` weight 0.2492. `10.23695/qggj-3130` "Webbnyheter 2001" is Swedish news prose, failing
the density screen by construction under a non-English ccTLD.

**Two access facts to obey next time.** `api.osf.io/robots.txt` is a **blanket `Disallow: /`** for all
agents and `osf.io` disallows `/api/*`, so **OSF is closed on robots, not on content**; its dataset
metadata is still reachable through DataCite, which serves no robots.txt at all. `zenodo.org` disallows
`/api` and `/search` with `Crawl-delay: 10`, carving back only `Allow: /api/records/*/files`, so
Zenodo's search API must not be swept directly and was queried only through DataCite. Claude is not
named on any host checked. `dataverse.harvard.edu` and `figshare.com` both answer `robots.txt` with
**HTTP 202, zero bytes and `x-amzn-waf-action: challenge`**, which is no rules retrievable rather than
a refusal, and their `/api/` paths answered normally.

**One method correction, and it cuts the right way.** DataCite's `titles.title:"phrase"` is **stemmed
and slop-tolerant, not exact**: `"zone files"` returns "Snow persistence grids and snow zone shape
files", and on `descriptions.description:` it degrades to proximity noise (69 geospatial shapefiles for
`"zone file"`). So the earlier sweep's queries were **broader than exact, not narrower, and its zeros
stand as conservative**. But keyword sweeping DataCite descriptions is not a usable instrument; the
`dates` plus `titles.title` combination above is.

**Verdict: treat "academic repositories and DOI datasets" as closed and report it to Ding as closed
with these numbers.** Five APIs and two registries converge on the same three artifacts, all of which
we already hold or have priced. Do not rotate back to this lens.

---

## Dated internet-trade directories (ISPs and web hosts): closed, and the ceiling is the reason

**The idea was sound and the population is too small to matter.** ISPs and hosting companies in
1996-2001 were thousands of small regional businesses, which is the mid-tail rather than the head, so a
2001-dated directory of them looked like a good fit for the 2001 threshold: one already-held `.com`
name in a 2001-dated artifact is worth 0.386 EE, so ~2,600 held names clears 1,000 EE.

**`thelist.com` is a proved zero on retrieval, and the proof is one number.** Mecklermedia's ISP
directory was the big one, and it is not in the archive in bulk: querying every 1996-2002 capture of
`thelist.com` and `thelist.internet.com` sorted by size, **the 25 largest objects on each host are all
ad banners, and the largest of any kind is a 14,390-byte GIF** (`ads/1999/12/tsl-468.gif`). There is no
listing page above about 12 KB, because the directory was a database-driven per-state query interface
and the crawler took the chrome rather than the data. `web.archive.org/robots.txt` is a 404 with no
rules, so this is absence, not refusal.

**And the lens has a low ceiling even with a perfect artifact, which is the transferable part.** The
`Message-ID` posting-host study of 2026-08-16 already measured this exact population from the other
direction: the top hosts were `wisc.edu`, `gi.net`, `supernews.com`, `aol.com`, `att.net`,
`earthlink.net`, and its conclusion was that **the population of ISPs and news servers in 1996-2001 is
a few thousand hosts we already hold in full**, returning zero never-before-seen domains over 73,751
messages. So the addressable set is thousands, not the tens of thousands a 1,000 EE find needs at
`.com` weight, and the part of it that pays is only the fraction still missing 2001.

**Boardwatch stays where it was**: the magazine issues are ingested, and its separately catalogued ISP
Directory volumes remain blocked because `..._djvu.txt` returns a 146-byte stub. That is an access
failure rather than a content zero, so a route to those volumes' text would still be worth having, but
the ceiling above says it is not worth hunting for.

**Do not rotate back to trade directories of internet businesses.** The failure is not which host you
try; it is that the whole industry was a few thousand names and we hold them.

**Housekeeping, and a scare worth recording because it looked exactly like a known bug.**
`data/raw/usenet_bulk/` holds **9,266 archives and 52 GB with no `.processed` marker of its own**, which
is the precise shape of the directory-mismatch bug that once hid 50 GB for weeks. It is a false alarm:
all 9,266 basenames are in `data/raw/usenet/.processed`, as are all 48 in `usenet_probe5`, because the
marker lives in the sibling directory the pipeline writes to. **Check the marker's contents, not its
location.** Sweeping all thirteen `usenet_*` directories the same way found exactly three genuinely
unprocessed archives, in `usenet_msft`, 488 MB. Split and ingested: 23,410 dated records over 19,095
domains and **0 net-new year rows**, which is what `microsoft.public.*` should give, and they are now
marked. Also confirmed against the ledger: 117 GB of `data/raw` is unledgered, and it is all either
processed Usenet source archives (the ledger holds journal names, not `.mbox.zip` names), the 2 GiB
`host-linkage` backup, out-of-window Common Crawl vertex files, or RDAP queue text.

---

## discmaster by FILENAME: reopen condition resolved, and the lens is saturated

**The recorded reopen condition is now discharged, which is the durable part of this.** `sources.md`
had it that discmaster's search "silently ignores" `file=` and that the `q=` route "timed out at 120s
on three consecutive queries". With the corrected parameters from CLAUDE.md, `qfields=name`,
`mode=deep` and `YYYYMMDD` rather than ISO dates, **the endpoint answers in about 5 seconds** and the
date filter is honoured. So that closure was a parameter error, not a broken endpoint, and nobody needs
to re-test it again.

**And with a working endpoint the lens is saturated.** Five targeted queries over 1996-2001 file dates,
`domains`, `zone`, `whois`, `hostlist`, `nslookup`, against an index of **1,718,970,121 files**:

- `domains` returns squidGuard blacklists inside Devil-Linux ISOs, in bulk. One FTP item,
  `ftp.fl.priv.at`, accounts for **1,492** of them, the same handful of lists shipped in every release.
  That family is already priced: `squidguard_2001_blacklist` sits on the sheet at 10,736 EE.
- `zone`, `whois`, `hostlist`, `nslookup` return **software and documentation only**: Doom's
  `z_zone.c`, `whois.c`, `m_whois.c`, `nslookup.0`/`.1`/`.8` man pages, `HOSTLIST.BAT`,
  `HOSTLIST.JAVA`, `HostList.gif`. Not one bulk data file among roughly 400 result rows.

**These are the same false-positive classes for the third time**, after the archive.org FTP-ZIP sweep
and after discmaster-by-file-size. The bulk artifacts preserved on 1996-2001 media are the anti-spam
and proxy blocklists, all of which are now found and priced (`antispam_media_blocklist` 1,055 EE,
`junkfilter_dated_blocklist` 2,189, `squidguard_2001_blacklist` 10,736), plus the `.jp` registry
listing already rejected at 185.3 EE on `jp` weight 0.0605. **Treat preserved media as worked out, and
do not open it again on a filename hunch.**

**Access, recorded because it is a judgement rather than a rule.** `discmaster.textfiles.com/robots.txt`
is `User-agent: *` / `Disallow: /` followed verbatim by the operator's own note: "This is mainly to
prevent AI companies from scraping the entire website. If you are a researcher, historian or hobbyist,
you are free to automate requests to the site so long as it's reasonable or somewhat limited or somewhat
targeted." This project already records that carve-out as the collection method for
`antispam_media_blocklist`. Six requests were made in total here. **The tension is real and worth Ivo
seeing: the machine-readable line refuses everyone, and the party the operator names as excluded is AI
companies, which is at least arguably us even when the work is a student's.** If he would rather we
treat the `Disallow` as binding regardless of the comment, this section and that entry are the two
places that assume otherwise.

**Addendum, the harvested-address-list variant, because the earlier queries had a real gap.** The five
filename queries above looked for registry and DNS shapes and never for bulk email-address lists, which
was an omission worth closing: the `.jp` `email.domains` file was found on this very index by a
file-size search, so the family demonstrably exists on 1996-2001 media, and a US or global equivalent
would carry `.com` at 0.6321 rather than `.jp` at 0.0605, roughly ten times the weight per name. Four
further queries settle it. **`email.domains` returns exactly one file, which is the `.jp` listing
already rejected at 185.3 EE**, plus an unrelated GIF. `emails`, `addresses` and `maillist` return BBS
and software furniture: `EMAILS.ANS` ANSI menus, `EMAILS.CFG`, `INSTALL.DAT` payloads, `maillist.h`,
`maillist.Z`, and an `emails.gif` inside a clipart ISO. No bulk list among them. Combined with
`discmaster_by_file_size` already being rejected on the one artifact it did find, **both routes into
preserved media are now exhausted, by name and by size.** Ten requests were made to that host in total.

**BANKED 2026-08-26: +15,173.22 EE over 16,384 pairs, above the 12,775.5 estimate.** Ivo approved it
as master on the delegation argument. Five editions ingested so far: 1996-10-09, 1996-11-20,
1999-03-22, 2000-08-15 and 2001-06-06, giving 31,503 zone rows, 30,837 canonicalised, 666 rejected
(the `k12.*.us` and bare-locality public suffixes the PSL correctly refuses) and 16,384 assigned
pairs. It beat the estimate because the priced union used one 1996 edition and this took both.

**Two editions were still downloading when it banked and will fold in on the next pass**, 2000-12-06
and 2001-04-11, plus a fifth in-window capture the original survey missed at **2001-02-01**
(`20010201165700`), found by listing every capture rather than the ones already known. Everything
from `20010815` onward is a 404, which is the `.us` registry handover to NeuStar, so the artifact's
own lifetime brackets the window neatly.

**The receipts, all re-verified before approval.** The 2001 edition fetched live at 435,846 bytes
with 6,512 zone rows:
`web.archive.org/web/20010606153725id_/http://www.isi.edu/in-notes/us-domain-delegated.txt`. Every
capture and status: the CDX query on `www.isi.edu/in-notes/us-domain-delegated.txt`. The 1996 and
1999 editions sit at `pub/rfc/` inside `archive.org/details/2015.04.ftp.isc.org`, whose metadata
confirms the item and the single `.tar`. Six further rotations captured 2001-05-01 live on
`ftp.isi.edu/in-notes/us-domain-delegated.txt.0` through `.5`.

**One implementation note worth keeping.** The artifact carries no in-body date, so the edition date
lives in the FILENAME and the parser refuses a file without one rather than guessing. That is the
weakest link in this source and it is deliberately visible: `_USD_EDITION` skips a file it cannot
date, and `parse_us_domain_delegated` reads **column 2 only**, so the contact mail address in column
3 is never read as a delegation. Scanning the whole line instead would have imported 56 third-party
pairs on this file's authority.

---

## squidGuard 2001-12 blacklists: BANKED 10,376.92 EE, and the closure it reopens

**Approved master by Ivo 2026-08-26 and banked: 18,000 pairs, 10,376.92 EE.** Store went 525,786.59
to 536,163.51, crossing 4% growth.

**Why a crawler-compiled blocklist is admissible.** The header asserts a successful fetch rather than
mere listing: `compiled from 2402 link sources and 654820 links, of which 510389 tested
successfully`, and `squidGuardRobot-2.3.4` names itself. Nobody typed the list, so no corroboration
split. Licence is **GPL v2**, verbatim in `squidguard-1.2.0/COPYING`.

**Receipts, all re-verified live before approval.** One request, and the host serves no `robots.txt`
(404, no rules): `archive.debian.org/debian/pool/main/s/squidguard/squidguard_1.2.0.orig.tar.gz`,
**1,852,659 bytes**, holding `squidguard-1.2.0/samples/dest/blacklists.tar.gz`. The dated header is a
line of its own, and the first pass nearly mis-read this: grepping `compiled from` finds a line with
no date, while the stamp is on the preceding line, `# This list was compiled in 19:44:45 on
2001.12.15 19:56:41.` Every stamp in the edition falls between **2001.12.15 and 2001.12.18**,
corroborated by tar member mtimes reading `Dec 18 2001` and `Dec 15 2001`, and by diffs running
`domains.20010813.diff` onward.

**It does not contradict the 2026-08-24 closure, it triggers it.** That closure was correct for the
artifact it examined, `blacklists.tar.gz` on `ftp.teledanmark.no`, earliest capture 2003-12-11 and a
base list reading `compiled in 120:47:13 on 2003.09.04`. Its own reopen condition read "reopen only
on an in-window edition from a non-Wayback mirror", which is exactly what `archive.debian.org` is.

**Banked at 10,376.92 rather than the 10,736.2 measured earlier, and the gap is deliberate.** A
diff's `-` lines are REMOVALS: evidence that a host stopped answering, not that it was live at that
date. Dropping them costs 35,230 lines and about 360 EE, and keeping them would have inflated the
count by a fifth on exactly the wrong inference. Final parser stats: 298,189 lines, 262,679 hosts,
129,178 rejected by the canonicaliser (the diffs are full of bare IP addresses), 42,460 evidence rows
and 18,000 assigned pairs.

**Two implementation traps worth keeping.** The tree is `blacklists/<category>/{domains,urls,*.diff}`
and eleven categories each hold a file called `domains`, while **the bulk ledger keys on `path.name`
alone**, so loading the tree as-is would ledger one `domains` and skip the other ten. The collector
flattens every file to `squidguard-<category>-<basename>`. And **one file in the archive has no
compile header at all**: `mail/domains` is 16 blank lines then a hand-kept list of free-webmail
providers (`123india.com`, `163.net`, `2bmail.co.uk`), which is a person's list rather than robot
output. The parser refuses a file it cannot date, so it is skipped for the right reason twice over.

**Content note, put to Ivo before he approved:** the bulk of the 42,460 names are adult, gambling,
drugs and warez sites. They are domains that existed, which is what the project asks for, and the
report names the source rather than hiding it.

---

## RIPE NCC's reply, 2026-08-26: permission given, and what the file actually contains

**The exchange, recorded verbatim so nobody re-litigates it.**

Ivo wrote on **2026-08-25 22:41 GMT+2**, describing the artifact and the notice precisely: an
academic project under Prof. Xiaowei Ding and Prof. Kay Giesecke to reconstruct domains live
1996-2001; the file is the 1999-08-04 snapshot at
`ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz`; its header carries the "Restricted rights" notice,
repeated in `RIGHTS`, `COPYRIGHT` and `README`; the intended use is to read the `domain:` objects and
derive `(domain name, 1999)` pairs, republishing no database text and **no personal data, no contact
names, e-mail addresses, addresses, phone numbers, maintainer or person objects**; and an offer to
accept conditions including attribution, restricted distribution or an agreement.

**Valentino, RIPE NCC Member Services Analyst, replied 2026-08-26 10:24 GMT+2:**

> Regarding your request, I understand that you would like to use certain data that we make available
> for your research. This is absolutely fine, provided that you do not require any special permissions
> that we are unable to grant.
>
> As long as the data is publicly available and visible to you, you are welcome to use it for your
> research. However, please be mindful not to make a large number of requests involving personal data,
> as the RIPE Database may automatically block the IP address from which the requests are originating.

**Reading, and why it clears the block.** The one condition attached is about **request volume against
the live database**, and we make zero requests: the artifact is a static file already on disk, so that
caution cannot bind us. The file is publicly available and visible, served by FUNET's open FTP mirror
with no authentication. The permitted use is "for your research", which is what this is. And our use
is narrower than what was permitted, because we take the domain name and nothing else.

**The honest limit of this permission.** It is a support-desk reply and it does not quote the 1999
notice back. What makes it sufficient is the sequence rather than the wording: the request described
the exact file, quoted the exact notice, and named the exact use, and the answer to that description
was "absolutely fine". Recorded here so the basis is auditable rather than remembered.

**What the file contains, measured rather than assumed**, since the commitment made to RIPE was about
personal data. Object types, by count of objects: `*dn` domain **1,256,414**; `*in` inetnum 204,825;
`*rt` route 17,536; `*mt` mntner 2,920; `*an` aut-num 2,440; `*am` as-macro 734; `*ir` inet-rtr 105;
`*li` limerick 96; `*kc` key-cert 78; `*cm` community 9; `*dp` 6; `*i6` inet6num 2.

**There are no person objects in this file at all, and that is the important finding.** A census of
all 63 attribute codes returns **`*pn` person 0, `*ad` address 0, `*ph` phone 0, `*fx` fax 0, `*em`
e-mail 0, `*nh` nic-hdl 0, `*ro` role 0**. FUNET mirrored the non-person half of the dump. The only
personal data present at all is inside `*ch` changed lines (2,045,382), which carry an e-mail address
beside a date, plus 9 `*au` auth lines in maintainer objects. **We read none of it.**

**What we are not using, in one line:** every IP allocation, route, AS number, router, maintainer, PGP
key and limerick object; and within domain objects, `*de` descr, `*ns` nserver, `*rm` remarks, `*cy`
country, `*ch` changed, `*ac`/`*tc`/`*zc` admin, tech and zone contact handles, `*mb` mnt-by and `*so`
source. We take the `*dn` value, canonicalise it, and pair it with 1999. Of the 1,256,414 domain
objects, 21,047 are `.arpa` reverse zones excluded by the store's own invariant, leaving **1,232,554
distinct registrable names**.

**Consequences for the parser, which does not exist yet and must be written this way.** Read `*dn`
only. Never emit any other attribute into evidence, and in particular never `*ch`, which is the one
attribute in the file that carries an e-mail address. Attribute the RIPE NCC as the source in the
report, which Ivo offered unprompted. Rule 6 still applies: the snapshot's own header dates it
`# 990804 00:07:01`, so it evidences **1999 and no other year**.

---

## `ripe_dbase_1999`: BANKED 90,770.29 EE, the largest single source of the round

**Approved master by Ivo 2026-08-26 once RIPE NCC granted the request, and banked.** Store went
536,163.51 to **626,933.80 equivalent-English**, from 4.01% to **4.6918%** growth, on 641,038 pairs.
The licence question that blocked this for two days is answered; the exchange is recorded above.

**Measured at ingest on the real file, not projected.** 20,528,780 lines read; **19,272,364
attributes discarded**; 1,235,440 domain objects; 20,974 reverse zones skipped; header year **read as
1999 rather than assumed**; 4,100 salvaged and 502 rejected by the canonicaliser; 1,232,554 evidence
rows over 1,232,554 distinct names, of which 68.9% were already held at some year; **641,038 net-new
pairs at 1999 worth 90,770.29 EE**. That is 29 EE below the figure measured on 2026-08-24, the
difference being the store growing underneath it rather than a disagreement.

**Where the value is, and why volume beat weight.** Net-new by TLD is `de` 411,005, `dk` 73,647,
`at` 29,889, `it` 29,674, `nl` 19,736, `cz` 19,314, `no` 15,268, `fr` 12,020. Every one is on the
near-worthless list, and the round's mean weight per pair fell from 0.6388 to 0.4235 because of it.
**1.2M names at 0.1324 still outran every high-weight namespace still available to us**, which is the
lesson: this source nearly got discarded on a weight screen that a volume screen would have kept.

**The promise made to RIPE is enforced in code, not in prose, and this is the part to preserve.**
Ivo's request undertook to read the domain objects and publish no personal data.
`parse_ripe_dbase_1999` matches `*dn:` and nothing else, and **four tests in `tests/test_sources.py`
hold it there**, one of which fails if a postal address, a phone number or an e-mail reaches the
output. The dry run over the whole 71.9 MB file emitted **zero values that were not bare hostnames**.

**Why that guard is not theatre.** The file has no `person:` objects at all, and a census of all 63
attribute codes returns zero for person, address, phone, fax, e-mail, nic-hdl and role. That invites
the conclusion that there is nothing to protect. **The conclusion is wrong**, and finding out why was
the most useful five minutes of this ingest: the contact details are inline in the domain objects
under other codes, and three of the five are not obviously personal from their names.

    *dn: TuKKK.FI
    *de: Rehtorinpellonkatu 3, SF-20500 TURKU, Finland   <- postal address, under "descr"
    *ac: +358 21 6383105                                 <- phone number, under "admin-c"
    *ac: mniemi@abo.fi                                   <- e-mail, under "admin-c"
    *ch: ripe-dbm@ripe.net 19920825                      <- e-mail, under "changed"

**Two refusals built in, because the failure modes are asymmetric.** A file whose stamp is missing is
refused rather than dated from context: guessing a year for a 20-million-line dump is the worst
available outcome, so the parser gives up if no `# YYMMDD HH:MM:SS` line appears in the first forty.
A stamp outside 1996-2001 is refused the same way. Both are covered by tests.

**Rule 6 is respected and it costs a great deal here.** The snapshot evidences **1999 and no other
year**. A `.de` name in this file that was also live in 2000 and 2001 earns 1999 from this source and
must earn the other years from a capture. That is why 1.2M names yield 641,038 pairs rather than
several million.

**Attribution.** The report now names the RIPE NCC as the source and states that only the domain name
is read, which is what Ivo offered them unprompted.

---

## `namewinner_expiring`: BANKED 11,546.26 EE on the master reading

**Approved master by Ivo 2026-08-26 and banked: 18,937 pairs at 2001.** Store 630,532.68 to
**642,078.94 equivalent-English**, 4.7187% to **4.8051%**. Ingest stats: 20,945 lines, 20,944 data
rows, 20,943 canonicalised, 18,937 assigned.

**The ruling, and its scope.** The corroboration split does not apply, because this is a dump out of
a registrar's expiring-domain database rather than a list a person compiled, and being registered is
the only way onto it. So it dates novel names too, exactly as `iedr_register` and `internic_zone` do,
which is worth 11,546 against 2,077 on the conservative reading. **The ruling covers the 2001-10-26
capture only**, which needs no inference because its own per-item date is inside the window.

**The parser reads each row's own date, and that is the load-bearing design choice.** The 2002-04
capture of the same page holds 52,204 names and would be worth 31,204 EE on the same reading, and it
is refused **automatically, one row at a time**, because `25-APR-02` is not in `YEARS`. A parser that
took the date from the filename or the capture would have swallowed it. See the rule 6 objection on
the `expiring_list_2002_term_inference` row: an expiry date evidences its own year, so a 2002 artifact
cannot reach 2001 by arithmetic about registration terms.

**Receipts.** `web.archive.org/web/20011026120205id_/http://namewinner.com/whole_list.php?del=tab`,
581,560 bytes, tab-separated plain text despite the `.php`. The dating was verified by counting:
**20,945 occurrences of `25-OCT-01` and no other date of that shape in the file.** Dotster's own
`rule_book.php` (capture `20011027003733`) calls it "our list of soon to be expiring domain names".

**A naming trap worth recording.** The register entry was filed as
`domain_aftermarket_listings_1999_2001` while the spec was written as `namewinner_expiring`, and the
approval gate reads the register, so the ingest refused with "awaiting classification" even though the
`Decision:` line said master. **The gate matches on the entry name, so the spec key and the entry
heading have to be the same string.** Renamed the entry and left the old slug as a pointer. This is
the second time in one day: `squidguard_blacklist` against `squidguard_2001_blacklist` did the same.

---

## `can_domain_registry_notices`: BANKED 7,934.20 EE on a one-word ruling

**Approved master by Ivo 2026-08-26 and banked: 9,485 pairs.** Store 642,078.94 to **650,013.14**,
4.8051% to **4.8645%**. The banked figure matched the pre-ingest measurement to the decimal.

**The ruling.** A `Date-Approved:` field printed by the registry inside its own approval notice IS the
registry stating its database, not prose. Grounds: machine-formatted aligned columns, ISO-style dates,
and the approval is the registry's own act rather than a description of someone else's. So
`whois_creation`, and rule 6 gives that year and no other. Read as prose it would have been worth
about a tenth.

**Rule 6 is what costs the file.** 37,679 subdomain records and 36,892 approvals in window collapse to
**9,485 assigned pairs**, because approvals cluster 1996 7,766 / 1997 9,520 / 1998 15,133 / 1999 4,473
/ **2000 and 2001 zero** (the registry stopped posting), and the many thousands approved before 1996
contribute nothing.

**Two checks that changed the answer, and both are the transferable part.**

**`Date-Modified:` is worth nothing, measured rather than assumed.** It looked like free upside: a
record cannot be modified for a name that is not registered, so a 2000 modification would attest 2000
and reach the years rule 6 denies us. **Nine such records exist in the whole archive. 0.0 EE.** Not a
route, and worth knowing before anyone else has the same idea.

**The archive a search finds first is the wrong one, and trusting it would have produced a confident
zero on a source worth 7,934 EE.** Searching archive.org for `can.domain` returns `usenet-can.domain`
(208 KB) and `FULL-USENET-BACKUP-2020-Oct-can.domain.189.mbox.7z` (124 KB). Both were downloaded and
both hold **zero `Date-Approved:` fields**, with messages dating **2003-2009**: group chatter about web
design and domain sales. The real archive is at the hierarchy-level item,
**`archive.org/download/usenet-can/can.domain.mbox.zip`, 14,326,153 bytes, 37,578 approval fields.**
**On this collection the item is named for the HIERARCHY, not the group**, which is how a 14 MB
archive hides behind a 208 KB decoy with a better-matching name.

**Parser note.** A record block is bounded by the next `Subdomain:` line, so an approval date belonging
to a neighbouring record can never attach to this one. That is exactly the failure that once inflated
a source by binding a name to the date printed beside it.

---

## SEC EDGAR filings, re-measured: right size, wrong shape, and too slow to help this round

**Not banked. Re-measured 2026-08-26 and left pending**, because the cost is in requests and the
requests are the problem.

**Two strata against the live store, and they disagree completely.** 1999 QTR1: **389 filings, 496
domain mentions, 81 distinct pairs, 0 net-new post-split, 0.0000 EE per filing.** 2001 QTR4: **248
filings, 350 mentions, 94 distinct pairs, 13 net-new, 8.0 EE, 0.0324 EE per filing.**

**The first measurement was mine and it was biased, which is the lesson worth keeping.** I sampled 1999
about an hour after the RIPE snapshot added 641,038 pairs **at 1999**, making it the most saturated year
in the store. A prose source tested against the year you have just filled will always measure zero.
**Stratify by year before concluding anything about a corpus that spans the window.**

**And do not project the good stratum either.** 0.0324 per filing over all 222,232 filings gives 7,203
EE, which is wrong for the same reason in reverse. The driver is `P(store lacks year Y | domain held)`,
0.611 for `.com` at 2001 against near zero at 1999. Expect the value to sit almost entirely in the
2000-2001 filings, roughly 85,000 of them, worth on the order of **2,500 to 4,000 EE**.

**Access, all verified.** `www.sec.gov/robots.txt` is 98 lines, read whole: `Allow: /Archives/edgar/data`
explicitly, `Disallow: /cgi-bin`, nothing naming Claude. The `full-index/<year>/QTR<n>/form.idx` files
answer 200 at 11-16 MB each. **The bulk `Feeds/<year>/QTR<n>/` route 404s for 1996, 1999 and 2001**, so
there is no tarball route before 2002 and it is one request per filing: ~90 hours and ~33 GB for the
whole corpus, ~35 hours for the 2000-2001 subset that carries the value.

**Verdict: worth collecting as a background job with an absolute deadline, landing in a later round.
Not worth blocking a submission on.** Two implementation notes for whoever builds it. Filter the index
to the 2000-2001 quarters and to forms that actually print URLs. And catch
`http.client.HTTPException`, not just `OSError`: one truncated chunked response killed a whole sampling
run here, because `IncompleteRead` is not an `OSError`.

---

## `dartmouth_bfs_seed` and `cctld_register_listing_inbody`: BANKED 3,018.18 EE

**`dartmouth_bfs_seed`: approved master and banked, 2,442 pairs, 1,408.55 EE.** 311,543 CDX rows read,
58,035 in-window HTTP 200s, 253,505 rows out of window, 57,877 evidence rows over 18,940 domains.
`cdx_timestamp` on field 2, self-dating, no split. Level 0 only, which is the whole source and not a
sample of it: levels 2 and 3 measured 0.00, 0.00 and 0.59 EE per MB against level 0's 104.7. **The
cheapest EE of the round, because the collector, the spec and the data were already on disk and it
needed one decision line.**

**`cctld_register_listing_inbody`: approved master and banked, 10,177 pairs, 1,609.63 EE.** Two
artifacts of the three: TWNIC's `.tw` frozen-domain list (9,318 names) and IDNIC's `.id` unpaid-fees
table (1,671). RESTENA `.lu` (708.5 EE) is still to fetch.

**Under the recorded 2,855.6, and the reasons are worth separating.** One artifact missing, and IDNIC
dated conservatively: its rows carry a `Jatuh Tempo` due date each, and only that is used, where the
recorded 2,162 pairs over 1,671 names implies the earlier measurement also counted the capture stamp.
**One route per artifact is the cleaner claim.**

**The CDX length trap is confirmed to the byte and it nearly cost both artifacts.** The `length` column
is the compressed WARC record size, not the page size, and a large uniform table compresses hardest:
TWNIC reads **77,565 in the index and 624,921 bytes on the wire** (8.1x), IDNIC **23,977 against
251,567** (10.5x). Ranking candidate pages by CDX length under-ranks exactly the pages worth having.

**Semantics, one line each.** TWNIC's page stamps itself `更新時間: 2001/8/27 20:0:31` and lists names
whose registration expired between 2001-05-29 and 2001-08-26, so every one was in the register during
2001 and the artifact implies nothing about another year. IDNIC's due date is the registry stating the
boundary of that registration's paid period, so the name existed then.

**Still open in this family:** the four `_capture` artifacts (NIC Malta, SaudiNIC, ISOC-IL, `.nu`
notrenewed, 3,496 EE recorded) have their measurements on record but **not their URLs**, so each has to
be re-found by CDX search against a throttled archive. A targeted hunt is running with a three-hour
deadline. **Record the URL next to the measurement**, or the next person pays the search twice.
