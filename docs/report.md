# Internet Digital Ark: round 9

Additions to the 1996-2001 annual lists, against `merged260908`. Every figure below is generated from
the evidence store, so nothing here can disagree with the files beside it. Receipts are in
`sources.md`, yields and failures in `experience-summary.md`, the route in `README.md`.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | 65,313,842 |
| 2. Equivalent-English total | 34,887,095.7393 |
| 3. Increment | **3,399,258** records |
| 4. Equivalent-English increment | **1,874,979.2367** |
| 5. Equivalent-English growth rate | **5.3744%** |

91,472 records (65,738.2990 EE) are registrable domains in `additions/`; 3,308,090 (1,809,240.9377 EE)
are hostnames beneath them in `hostnames/`. The two are disjoint in every year, neither is in the
baseline, your validator rejects none of them, and either set can be merged or discarded whole. The
increment covers 85,238 distinct domains, 45,206 of which appear in none of your six files
in any year.

| Year | Registrables | Hostnames | Equivalent-English added |
|------|-----------:|-----------:|--------------:|
| 1996 | 1,354 | 6,138 | 4,706.0329 |
| 1997 | 4,620 | 11,473 | 9,965.1210 |
| 1998 | 5,642 | 41,452 | 28,290.1568 |
| 1999 | 19,884 | 136,285 | 94,087.1613 |
| 2000 | 20,233 | 329,152 | 194,617.8658 |
| 2001 | 39,739 | 2,783,590 | 1,543,312.8989 |
| **Total** | **91,472** | **3,308,090** | **1,874,979.2367** |

Cumulative verified percentage 80.5097%, this round counted at its own unverified 5.3744% and round 1 on records rather than equivalent-English. Time-weighted score 18.874694 over the rounds you scored, your own figure used wherever you stated one. This round reads 26.872105 on the benchmark interval and 1.053808 on the assignment interval. **You scored round 8 as 10 x (18.769714 / 33) = 5.687792.** We cannot reproduce the 33: the benchmark interval gives t = 1 and the task-assignment interval t = 51 from 2026-07-21, the earliest date our records support. Which date is t_i counted from, and does it re-score the awarded rounds?

**The unit is the one you accepted on 2026-09-05 and has not moved.** A hostname record is
structurally valid, sits strictly beneath a registrable we hold for that same year, and carries its
own machine-written observation of that exact host serving in that year. Per your 2026-09-06 ruling
nothing is inferred from a bare name to its `www.` form or back: each record names its own host in
its own evidence row, and the invariant `a_www_record_has_its_own_evidence` refuses any that does
not.

## 2. What is new, and where it came from

| Source, unit | Artifact, and how it was obtained | What dates one record | Records | EE |
|--------------|--------------------------|----------------------|--------:|-------:|
| `ia_cdx_domain_sweep`, hostname | IA CDX `matchType=domain` sweeps, two clients, over parents ranked by the hosts we lack rather than the hosts they have | the row's own 14-digit capture timestamp | 2,262,861 | 1,353,286 |
| `usenet_server_written_header`, hostname | Usenet spool (IA), already held, re-read for the three headers a NEWS SERVER writes about itself: `Path:`, `X-Trace:` and `NNTP-Posting-Host:`. No sender-supplied field is read | the post's own machine-written `Date:` header | 736,440 | 350,946 |
| `usenet_body_url`, hostname | Every non-alt Usenet hierarchy of the archive.org collection, 224 GB read whole, hosts taken only from explicit http, https and ftp URLs in the post BODY | the post's own machine-written `Date:` header | 109,258 | 64,821 |
| `ia_cdx_bulk`, registrable | IA CDX per-domain queries over bracketed gaps and the candidate pool | the capture timestamp of a URL on that host | 30,632 | 30,239 |
| `usenet_address`, registrable | Usenet archives (IA), sender and body addresses | the post's `Date:` header, corroborated by a second source | 33,288 | 19,565 |
| `poland_pl_extract_hostgrain`, hostname | Poland `.pl` ccTLD extraction 2001-12-31 (IA, `webdataservices`), 19 item-level CDX indexes, 1.24 GB, each verified against its published sha256 before it was read | the row's own 14-digit capture timestamp, from the original URL and never the SURT key | 147,649 | 15,798 |
| `ietf_list_received_by`, hostname | IETF mail archive, one raw mbox per list-month, `ietf-mail-archive/` and `concluded-wg-ietf-mail-archive/` | the message's `Date:` header, checked against the month the archive filed it under | 21,465 | 11,986 |
| `usenet_body_url_hostnames`, registrable | the registrable half of the Usenet body-URL lane, hosts taken only from explicit http, https and ftp URLs in the post body | the post's own machine-written `Date:` header | 11,418 | 7,077 |
| `apache_list_received_by`, hostname | Apache mailing-list archive, the same `Received: ... by <host>` clause at a second host | the message's `Date:` header, checked against the month the archive filed it under | 12,669 | 7,013 |
| `usenet_bare`, registrable | Usenet archives (IA), bare hostnames in bodies | the post's `Date:` header, corroborated by a second source | 7,520 | 4,875 |
| `arquivo_ia_cdxj_hostgrain`, hostname | Arquivo.pt `IA.cdxj` capture index, held since 2026-08, re-read at hostname grain | the row's own 14-digit capture timestamp | 16,366 | 4,144 |
| `usenet_header_fqdn_hostnames`, registrable | the registrable half of the Usenet server-header lane above | the post's own machine-written `Date:` header | 5,828 | 3,027 |
| `ia_cdx_gap_hostgrain`, hostname | IA CDX queries over bracketed year gaps, read at hostname grain | the row's own 14-digit capture timestamp | 1,382 | 1,248 |
| 7 further sources | each under 1,000 EE, listed in `audit/source_contribution.csv` | | 2,786 | 1,249 |
| **Total** | | | **3,399,562** | **1,875,273** |

The table counts every record submitted; the increment in section 1 is smaller because it excludes
the few your baseline already holds, which section 5 counts. Every stamp above is machine-written
and inside the artifact, so no human judgement dates a year. Three routes carry the round, and each
answers "how do you know it existed that year" differently:

- **a capture index** (`ia_cdx_domain_sweep`, `poland_pl_extract_hostgrain`,
  `arquivo_ia_cdxj_hostgrain`): the row's own 14-digit capture timestamp on a URL on that exact
  host, 2xx or 3xx only.
- **a server writing its own name** (`usenet_server_written_header`, `ietf_list_received_by`,
  `apache_list_received_by`): the `Received: ... by <host>` clause a receiving mail server writes
  about itself, and its Usenet equivalents, dated by the message's own RFC 822 `Date:` header
  cross-checked against the month the archive filed it under. Section 3.
- **a URL a person typed** (`usenet_body_url`): an explicit http, https or ftp URL in a post body,
  dated by the post's own `Date:` header.

**21.9% of the hostname half is a `www.` form, against 95.0% last round.** The fall is a
consequence of the second route rather than a filter: a mail relay or a news server is not named
`www`, so this round's names are mostly ones your files could not already hold under another shape.

**Annual and candidate contributions, separately, as your section XI asks.** The five fields above
are annual records only. Beside them, 2,279,755 domains carry no in-window evidence, ship as
`candidates.txt`, reach no annual file, and are worth 1,582,744.5921 equivalent-English **if every
one were later dated**, which is a ceiling on future work and not a contribution to this round.
`isc_survey_hostnames/` ships as the separate provenance-linked candidate collection you specified
on 2026-09-06, 17,669,437 hostname-years with per-host provenance, and is in no figure above.

## 3. What we learned this round

**1. A server writing its own name is one evidence class, not one source, and it crosses
protocols.** Last round we admitted the `Received: ... by <host>` clause of a dated mailing-list
message: the receiving mail server names itself, about itself, in a transaction it completed. The
finding this round is that the clause is not the point, the *authorship* is. A news server writes
`Path:`, `X-Trace:` and `NNTP-Posting-Host:` about a transaction it completed in exactly the same
sense, so the same reading admits Usenet server headers with no new rule, and that lane paid
350,946 equivalent-English on 736,440 records from spool already on disk.
The same clause read at two mailing-list archives paid a further 18,999 on
34,134. **Three exclusions come with it, each costing yield:** the `from` HELO
name is chosen by the sender, the parenthesised reverse-DNS is written by the receiver but was
outside the approval, and a `Message-ID` host is stamped by the sending client. None of the three
is read.

**Two parsing traps, because both banked fiction before they were caught.** A news server appends
its own verdict to a `Path` element: `.POSTED` marks the injecting site, and left in place it banks
`news2-win.server.<parent>.posted` as a host in its own right, 2,006 rows in a 35 MB test.
`.MISMATCH` is the server stating that the reverse-DNS did **not** match, so those elements are
dropped rather than cleaned. A further filter removes dial-up lease names, which name a session and
not a machine: an address embedded in the label, a pool word beside a digit, a bare numeric or long
hex first label. It drops 6.5% of candidate hosts, measured against 6.9% expected.

**2. A closure is a measurement about our search, not a fact about the artifact, so the number
under it has to be re-measured before it is trusted.** The Usenet header class had been closed here
on 2026-09-08 as "224 GB, on neither machine any more". Re-measured from the archive's own metadata,
the two collections it was priced on are 15.3 GB, and 104.8 GB of the same corpus was already on the
laptop. The class needed no fetch at all, and it is the second-largest lane of this round. Two
further families closed at 0.0000 were re-probed for the same reason and were also wrong: one
because the inventory page was one link deeper than the sweep looked, one because an FTP index was
assumed already held and 31.5% to 64.3% of its hosts were missing at their own year. A verdict
resting on "we looked and found nothing" is now re-run against the artifact's own structure rather
than against the path we guessed.

**3. Rank a query queue on what is missing, and plan with the sustained rate rather than the
peak.** A domain-wide capture query is worth what the years we hold its parent in are worth, not
what its host count is, because a capture under a parent we do not hold that year cannot become a
record. Ranking parents on hosts-we-lack times years-we-hold, minus host-years already held, took
the accepted share of one night's sweep from 4.9% to 21%. The rate that ranking produces is not a
property of the source: the same query, code and two clients paid about 193,000 equivalent-English
per client-hour on a fresh ranked head and 210 per hour two nights later once that head was walked.
Measured over ten hours from a re-rank, two clients wrote 1,067 MB of journal for 247,042
equivalent-English, **231 per MB, where the head alone reads 565**. **The caution that goes with
it:** correlating a parent's rank against what it banked gives Spearman +0.746 over 198 parents,
which reads as an exactly inverted ranker and is not, because the head of any ranking is swept
first and re-measuring it measures sweep history. Over the 54 parents swept fresh from a new
ranking the same correlation is -0.655. Price a ranker only on parents it has never been used on.

## 4. Limitations, and what is worth expanding

A capture proves presence and never absence, so a year with no capture is unevidenced rather than
empty, and a server header attests the year of its own message and no other. Both routes err toward
omission. The units ship separately, so dropping the hostname files leaves the registrable round
intact at 65,738.2990 equivalent-English. A material share of archive requests fail at transport level
rather than with a status code, which is throttling seen from the other side of the socket.

**309 source families searched and recorded** in `sources.md` and `sources-closed.md`: 87 developed, 222 evaluated and closed with the measurement that closed them, so the same ground is not broken twice.

**Worth expanding next, in order.** The server-header class at the archives it has not been run
against, which is the one route this round that needed no new bandwidth. The ISP Usenet hierarchies,
15.3 GB, where the customer host appears rather than the news server. Sibling ccTLD extractions of
the shape `poland_pl_extract_hostgrain` reads, which exist for other national archives under the
same uploader. The second-level suffix namespaces at hostname grain, where `co.uk` alone is 3.39M
index blocks and 1.2% walked. Measured and closed this round: the `alt` Usenet remainder, on
saturation, and the Apache list archive, whose ceiling fell to 9,000 equivalent-English once the
class was measured rather than projected.

**One eligibility question we cannot settle ourselves.** An FTP index row carries the crawler's own
completion stamp for that exact host in that year, so the service answered and its files were
counted. That is stronger than a DNS observation, which your 0906 update makes candidate-only, but
it is not a webpage. We hold those rows out of the annual files until you rule, and they are in no
figure in this report.

## 5. Merge, overlap and reconciliation (D3)

| | records | equivalent-English |
|---|--:|--:|
| baseline `merged260908` | 65,313,842 | 34,887,095.7393 |
| **accepted increment** | **3,399,258** | **1,874,979.2367** |
| post-merge total | 68,713,100 | 36,762,074.9760 |

Of the 3,399,562 records submitted, **304 are already in the baseline** and are excluded, so the accepted increment above counts each remaining record once. **28 of 28 reconciliation checks pass**. `merge_against_baseline.py` unions both units into the baseline, deduplicates on the lowercased line within each year and scores every file with your own calculator; the per-check verdicts are in `audit/merge_audit_ark_*.json` and the per-year form in `audit/merge_stats_ark_*.csv`, in your column names.

## 6. Reproduction, and the four deliverables

`README.md` in the archive gives the route and the file map. Every evidence row names its source,
evidence type, dated value, URL and extraction method; `additions/evidence_manifest.csv` and
`hostnames/hostnames_evidence_manifest.csv` repeat those columns per record. Before sending, a fresh extraction of this archive was put through that route: all eleven `verify.sh` checks pass, and the tier-2 rebuild from `provenance/` reproduces every per-year count, passes the seventeen invariants and returns all twenty-one result files byte-identical to the ones shipped. Tier 3, the full replay, was not run: about 50 GB, with eight journal sets held out of the archive on size.

**D1** code and instructions: `source/source.tar.gz` at `source/COMMIT.txt`, with the autonomous
research loop as `source/fleet.tar.gz`. **D2** experience summary: `experience-summary.md`.
**D3** merge and dedup code, overlap and reconciliation: section 5 and `audit/`. **D4** runnable
metric code: `equivalent_english_domain_calculator/`, your program vendored unmodified and
explained in `metric-explained.md`.
