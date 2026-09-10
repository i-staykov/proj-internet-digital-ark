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

91,472 records (65,738.2990 EE) are registrable domains in `additions/` and 3,308,090 (1,809,240.9377
EE) are hostnames beneath them in `hostnames/`. The two are disjoint in every year, neither is in
the baseline, and either set can be merged or discarded whole. The increment covers 85,238
distinct domains, 45,206 of which appear in none of your six files in any year.

| Year | Registrables | Hostnames | Equivalent-English added |
|------|-----------:|-----------:|--------------:|
| 1996 | 1,354 | 6,138 | 4,706.0329 |
| 1997 | 4,620 | 11,473 | 9,965.1210 |
| 1998 | 5,642 | 41,452 | 28,290.1568 |
| 1999 | 19,884 | 136,285 | 94,087.1613 |
| 2000 | 20,233 | 329,152 | 194,617.8658 |
| 2001 | 39,739 | 2,783,590 | 1,543,312.8989 |
| **Total** | **91,472** | **3,308,090** | **1,874,979.2367** |

Cumulative verified percentage 80.5097%, this round at its own unverified 5.3744% and round 1 on records. Time-weighted score 18.874694 over the three rounds you scored, your own figure where you stated one. Under your 0903 rule, at the origin your round 8 divisor implies (2026-09-04 less 33 days), this round is t = 39 and adds 1.378057.

## 2. What is new, and where it came from

| Source, unit | Artifact, and how it was obtained | What dates one record | Records | EE |
|--------------|--------------------------|----------------------|--------:|-------:|
| `ia_cdx_domain_sweep`, hostname | IA CDX `matchType=domain` sweeps, two clients, parents ranked by the hosts we lack | the row's own 14-digit capture timestamp | 2,262,861 | 1,353,286 |
| `usenet_server_written_header`, hostname | Usenet spool (IA), already held, re-read for the three headers a news server writes about itself: `Path:`, `X-Trace:`, `NNTP-Posting-Host:` | the post's own machine-written `Date:` header | 736,440 | 350,946 |
| `usenet_body_url`, hostname | Every non-alt Usenet hierarchy (IA), 224 GB read whole, hosts only from explicit http, https and ftp URLs in the post body | the post's own machine-written `Date:` header | 109,258 | 64,821 |
| `ia_cdx_bulk`, registrable | IA CDX per-domain queries over bracketed year gaps and the candidate pool | the capture timestamp of a URL on that host | 30,632 | 30,239 |
| `usenet_address`, registrable | Usenet archives (IA), sender and body addresses | the post's `Date:` header, corroborated by a second source | 33,288 | 19,565 |
| `poland_pl_extract_hostgrain`, hostname | Poland `.pl` ccTLD extraction 2001-12-31 (IA), 19 CDX indexes, 1.24 GB, each verified against its published sha256 | the row's own 14-digit capture timestamp, from the original URL and never the SURT key | 147,649 | 15,798 |
| `ietf_list_received_by`, hostname | IETF mail archive, one raw mbox per list-month | the message's `Date:` header, checked against the month the archive filed it under | 21,465 | 11,986 |
| `usenet_body_url_hostnames`, registrable | the registrable half of the Usenet body-URL lane | the post's own machine-written `Date:` header | 11,418 | 7,077 |
| `apache_list_received_by`, hostname | Apache mailing-list archive, the same clause at a second host | the message's `Date:` header, checked against the month the archive filed it under | 12,669 | 7,013 |
| `usenet_bare`, registrable | Usenet archives (IA), bare hostnames in bodies | the post's `Date:` header, corroborated by a second source | 7,520 | 4,875 |
| `arquivo_ia_cdxj_hostgrain`, hostname | Arquivo.pt `IA.cdxj` capture index, held since 2026-08, re-read at hostname grain | the row's own 14-digit capture timestamp | 16,366 | 4,144 |
| `usenet_header_fqdn_hostnames`, registrable | the registrable half of the Usenet server-header lane above | the post's own machine-written `Date:` header | 5,828 | 3,027 |
| `ia_cdx_gap_hostgrain`, hostname | IA CDX queries over bracketed year gaps, read at hostname grain | the row's own 14-digit capture timestamp | 1,382 | 1,248 |
| 7 further sources | each under 1,000 EE, listed in `audit/source_contribution.csv` | | 2,786 | 1,249 |
| **Total** | | | **3,399,562** | **1,875,273** |

The table counts every record submitted; the increment in section 1 is smaller because it excludes
the few your baseline already holds, which section 4 counts. Every stamp above is machine-written
and inside the artifact, so no human judgement dates a year, and the middle column says which stamp
for every source.

**One class is new.** A server writing its own name: the `Received: ... by <host>` clause a
receiving mail server writes about itself, and the `Path:`, `X-Trace:` and `NNTP-Posting-Host:`
headers a news server writes about a transaction it completed. No sender-supplied field is read.
`findings.md` section 1 gives the exclusions and the two parsing traps that had to be caught first.

A capture proves presence and never absence, and a server header attests the year of its own
message and no other, so both routes err toward omission rather than invention.

## 3. The candidate track

2,279,755 domains carry no evidence that earns them a year. They ship as `candidates.txt` and
reach no annual file. They are worth 1,582,744.5921 equivalent-English if every one were later
dated, which is a ceiling on future work and not a contribution to this round.

**New this round: the same pool also ships as one batch of year files, `candidates/<year>.txt`.**
Most of these names carry a dated observation that does not promote them, chiefly a link-target row
naming the domain in a crawl of that year, so the year says when the name was seen rather than that
it existed. The files overlap and their counts must not be summed as the pool size. Nothing here is
new data: every name is already in `candidates.txt`.

`isc_survey_hostnames/` is the separate provenance-linked candidate collection you specified on
2026-09-06: 17,669,437 hostname-years with per-host provenance, in no figure above.

## 4. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260908` | 65,313,842 | 34,887,095.7393 |
| **accepted increment** | **3,399,258** | **1,874,979.2367** |
| post-merge total | 68,713,100 | 36,762,074.9760 |

Of the 3,399,562 records submitted, **304 are already in the baseline** and are excluded, so the accepted increment above counts each remaining record once. **28 of 28 reconciliation checks pass**. `merge_against_baseline.py` unions both units into the baseline, deduplicates on the lowercased line within each year and scores every file with your own calculator; the per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in `audit/merge_stats_ark_*.csv`, in your column names.

## 5. Reproduction, and the four deliverables

`README.md` in the archive gives the route and the file map. Every evidence row names its source,
evidence type, dated value, URL and extraction method; `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` repeat those columns per record. Before sending, a fresh extraction of this archive was put through that route: all eleven `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` reproduces every per-year count, passes the seventeen invariants and returns all twenty-one result files byte-identical to the ones shipped. Tier 3, the full replay, was not run: about 50 GB, with eight journal sets held out of the archive on size.

**D1** code and instructions: `source/source.tar.gz` at `source/COMMIT.txt`, with the autonomous
research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`, with
this round's findings in `findings.md`. **D3** merge and dedup code, overlap and reconciliation:
section 4 and `audit/`. **D4** runnable metric code: `equivalent_english_domain_calculator/`, your
program vendored unmodified and explained in `metric-explained.md`.
