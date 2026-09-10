# Internet Digital Ark: round 9

Additions to the 1996-2001 annual lists, against `merged260908`. Every figure is generated from the
evidence store, so nothing here can disagree with the files beside it. The round's research
findings are in `findings.md`, the failures, yields and next steps in `experience-summary.md`, the
per-source receipts in `sources.md`, and the route through the archive in `README.md`.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 65,313,842 |
| 2. Equivalent-English total | 34,887,095.7393 |
| 3. Increment | **3,399,258** records |
| 4. Equivalent-English increment | **1,874,979.2367** |
| 5. Equivalent-English growth rate | **5.3744%** |

91,168 records (65,738.2990 EE) are registrable domains in `additions/` and 3,308,090 (1,809,240.9377
EE) are hostnames beneath them in `hostnames/`: disjoint in every year, and either set can be
merged or discarded whole. 84,942 distinct domains carry the increment, 44,919 of them
absent from your six files in every year.

| Year | Registrables | Hostnames | Equivalent-English added |
|------|-----------:|-----------:|--------------:|
| 1996 | 1,354 | 6,138 | 4,706.0329 |
| 1997 | 4,620 | 11,473 | 9,965.1210 |
| 1998 | 5,642 | 41,452 | 28,290.1568 |
| 1999 | 19,884 | 136,285 | 94,087.1613 |
| 2000 | 20,232 | 329,152 | 194,617.8658 |
| 2001 | 39,436 | 2,783,590 | 1,543,312.8989 |
| **Total** | **91,168** | **3,308,090** | **1,874,979.2367** |

Cumulative verified percentage 80.5097%, this round at its own unverified 5.3744% and round 1 on records. Time-weighted score 18.874694 over the three rounds you scored, your own figure where you stated one. Under your 0903 rule, at the origin your round 8 divisor implies (2026-09-04 less 33 days), this round is t = 39 and adds 1.378057.

## 2. What is new, and where it came from

| Source, unit | Artifact, and how it was obtained | What dates one record | Records | EE |
|--------------|--------------------------|----------------------|--------:|-------:|
| `ia_cdx_domain_sweep`, hostname | IA CDX `matchType=domain` sweeps, two clients, parents ranked by the hosts we lack | the row's own 14-digit capture timestamp | 2,262,861 | 1,353,286 |
| `usenet_server_written_header`, hostname | Usenet spool (IA), already held, re-read for the three headers a news server writes about itself: `Path:`, `X-Trace:`, `NNTP-Posting-Host:` | the post's own machine-written `Date:` header | 736,440 | 350,946 |
| `usenet_body_url`, hostname | Every non-alt Usenet hierarchy (IA), 224 GB read whole, hosts only from explicit http, https and ftp URLs in the post body | the post's own machine-written `Date:` header | 109,258 | 64,821 |
| `ia_cdx_bulk`, registrable | IA CDX per-domain queries over bracketed year gaps and the candidate pool | the capture timestamp of a URL on that host | 30,343 | 29,954 |
| `usenet_address`, registrable | Usenet archives (IA), sender and body addresses | the post's `Date:` header, corroborated by a second source | 33,288 | 19,565 |
| `poland_pl_extract_hostgrain`, hostname | Poland `.pl` ccTLD extraction 2001-12-31 (IA), 19 CDX indexes, 1.24 GB, each verified against its published sha256 | the row's own 14-digit capture timestamp, from the original URL and never the SURT key | 147,649 | 15,798 |
| `ietf_list_received_by`, hostname | IETF mail archive, one raw mbox per list-month | the message's `Date:` header, checked against the month the archive filed it under | 21,465 | 11,986 |
| `usenet_body_url_hostnames`, registrable | the registrable half of the Usenet body-URL lane | the post's own machine-written `Date:` header | 11,413 | 7,074 |
| `apache_list_received_by`, hostname | Apache mailing-list archive, the same clause at a second host | the message's `Date:` header, checked against the month the archive filed it under | 12,669 | 7,013 |
| `usenet_bare`, registrable | Usenet archives (IA), bare hostnames in bodies | the post's `Date:` header, corroborated by a second source | 7,520 | 4,875 |
| `arquivo_ia_cdxj_hostgrain`, hostname | Arquivo.pt `IA.cdxj` capture index, held since 2026-08, re-read at hostname grain | the row's own 14-digit capture timestamp | 16,366 | 4,144 |
| `usenet_header_fqdn_hostnames`, registrable | the registrable half of the Usenet server-header lane above | the post's own machine-written `Date:` header | 5,826 | 3,026 |
| `ia_cdx_gap_hostgrain`, hostname | IA CDX queries over bracketed year gaps, read at hostname grain | the row's own 14-digit capture timestamp | 1,382 | 1,248 |
| 7 further sources | each under 1,000 EE, listed in `audit/source_contribution.csv` | | 2,778 | 1,244 |
| **Total** | | | **3,399,258** | **1,874,979** |

Every stamp is machine-written and inside the artifact, so no human judgement dates a year, and the
middle column names the stamp per source. Nothing here is a record you already hold: the export
diffs every shipped list against your own annual files, so section 5's overlap is zero by
construction.

**One class is new**, a server writing its own name: the `Received: ... by <host>` clause a
receiving mail server writes about itself, and the `Path:`, `X-Trace:` and `NNTP-Posting-Host:`
headers a news server writes about a transaction it completed. No sender-supplied field is read.
`findings.md` gives the exclusions and the two parsing traps caught first. A capture proves
presence and never absence, and a header attests its own message's year and no other, so both err
toward omission.

## 3. The candidate track, counted the same way

You score candidates separately, at the same rate, over the same denominator, so this is a
contribution and is held to the annual standard: every collection we hold unioned into one pool,
then diffed against your `candidate_pool.txt` and all six annual files.

| | Names | Equivalent-English |
|---|--:|--:|
| registrable domains | 29,327 | 4,237.1081 |
| exact hostnames | 13,109,834 | 6,691,826.9522 |
| **`candidate_additions.txt`** | **13,139,161** | **6,696,064.0603** |

**19.1935%** of the same denominator as section 1, never added to it.

The hostnames are the ISC Internet Domain Survey of 1996-1997, dated by each edition's own code:
a DNS observation, which your 0905 ruling makes candidate-only and promotable one host at a time on
exact-host web evidence. The registrables are names our lanes found without a year we could defend.
**Provenance is per name and not in this list**: `provenance/` joins each name to its evidence row,
and `isc_survey_hostnames/isc_survey_provenance.csv` carries the survey edition, source file,
recovery URL, record location, extraction method and year for every hostname, the shape you
specified on 2026-09-06. That folder still ships; its names are inside the pool and not counted
twice.

One measurement worth passing on: our working pool holds 2,279,755 undated names, of which
29,327 are absent from your files. Shipping a working set as a contribution would have
overstated that half of the track by 78x.

## 4. How the work runs, and where it goes next

Two archive clients at most, ever, with an honest User-Agent naming the project and a contact, and
they hold the CDX channel exclusively. An autonomous research harness runs beside them on a
self-hosted runner: one lane proposes sources, one prices each against a snapshot of the store, a
separate admitter re-derives every figure locally before anything is banked, and a re-opener
re-tests closed verdicts whenever a measurement screen retires. **The research lanes cannot write
to the store**, which is why an agent's own figure has never decided a record.

**No agent assigns a year, and no source reaches an annual file without a written decision.** A
year comes from a machine-written stamp inside the artifact; `ark ingest` refuses any class with no
`Decision:` line and refused twice this round until one existed. Eighteen invariants run before
every commit and again inside this archive.

Next, in the order we would spend the hours: the server-header class at the archives it has not
been run against, which needs no new bandwidth; the ISP Usenet hierarchies, where the customer host
appears rather than the news server; sibling national ccTLD extractions of the shape the Poland
index has; second-level suffix namespaces at hostname grain, where `co.uk` alone is 3.39M index
blocks and 1.2% walked; and promoting ISC candidates as exact-host web evidence arrives, the one
route that turns 6,691,826.9522 candidate equivalent-English into annual records.

## 5. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260908` | 65,313,842 | 34,887,095.7393 |
| **accepted increment** | **3,399,258** | **1,874,979.2367** |
| post-merge total | 68,713,100 | 36,762,074.9760 |

**Not one of the 3,399,258 records submitted is already in the baseline**, so every one of them counts exactly once: the export diffs each shipped list against your own annual files before it writes them. **28 of 28 reconciliation checks pass**. `merge_against_baseline.py` unions both units into the baseline, deduplicates on the lowercased line within each year and scores every file with your own calculator; the per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in `audit/merge_stats_ark_*.csv`, in your column names.

## 6. Reproduction, and the four deliverables

`README.md` in the archive gives the route and the file map. Every evidence row names its source,
evidence type, dated value, URL and extraction method; `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` repeat those columns per record. Before sending, a fresh extraction of this archive was put through that route: all eleven `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` reproduces every per-year count, passes the seventeen invariants and returns all twenty-one result files byte-identical to the ones shipped. Tier 3, the full replay, was not run: about 50 GB, with eight journal sets held out of the archive on size.

**D1** code and instructions: `source/source.tar.gz` at `source/COMMIT.txt`, with the autonomous
research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`, with
this round's findings in `findings.md`. **D3** merge and dedup code, overlap and reconciliation:
section 5 and `audit/`. **D4** runnable metric code: `equivalent_english_domain_calculator/`, your
program vendored unmodified and explained in `metric-explained.md`.
