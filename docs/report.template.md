# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists and to the candidate pool, against your release
`[BASELINE]`. "The specification" is your
`Internet_Digital_Ark_Project_0917_Update.docx` of 17 September, "the evidence rule" its section XIII
(Mandatory Evidence Classification and Hostname Integrity Gate), "the two open questions" its
section IV-A. EE is equivalent-English.

## 1. Results

| | |
|---|--:|
| 1. Total original domain-year records 1996-2001 | [BASELINEPAIRS] |
| 2. Equivalent-English total | [EEBASELINE] |
| 3. Increment | **[TOTAL]** records |
| 4. Equivalent-English increment | **[EE]** |
| 5. Equivalent-English growth rate | **[EEGROWTH]** |

[REGPAIRS] records ([REGEE] EE) are registrable domains, in `additions/`; [HOSTPAIRS] ([HOSTEE] EE)
are hostnames, in `hostnames/`; every record carries its own exact-host capture in that year.
[NEWDOMAINS] registrable domains are absent from your six files in every year; the rest fills years
on names you hold.

[PER_YEAR_TABLE]

**The candidate track, claimed separately and never added to the above.** `candidate_additions.txt`:
[CANDADD] names, [CANDTRACKEE] EE, **[CANDTRACKPCT]** of the same denominator, after removing every
name in your `candidate_pool.txt` or annual files. [CANDREG] are registrable domains whose only dated
evidence the evidence rule keeps out of the annual files (registry zone and drop lists, dated
directories, author e-mail hosts); [CANDHOST] are hostnames from the two collections of section 3.

[CUMULATIVE_SENTENCE]

## 2. What is new, and where it came from

[ATTRIBUTION_TOP]

`ia_cdx_domain_sweep` queries the Internet Archive's capture index (CDX) domain by domain for
names in your files and keeps every captured hostname beneath them, each with the archive's own
14-digit timestamp, the evidence rule's reference pattern. `bulk_cdx_file` is two such indexes
**read whole at hostname grain**, keeping every HTTP 200 row dated 1996-2001:

- **Dartmouth NBER ARCS**, a research crawl collection on archive.org with a CDX beside each of
  its 282 items: the 25 with 1996-2001 stamps, read whole (4.1 GB), paid 134,564 records and
  83,868 EE. At registrable-domain level it adds nothing, every domain already held; one level
  down it pays.
- **Storage node ia600702**, the public 57.6 GB CDX of every capture on one archive.org node:
  1,031,419,773 rows, 14,192,504 of them HTTP 200 and dated 1996-2001, 931,864 host-years,
  **88.8% already in your release or our store**; the rest, 104,347 records, paid 50,722 EE. A
  bulk index read now measures the benchmark's saturation as much as it adds to it.

Our research loop now rejects, before download, any hostname source whose evidence class the
evidence rule keeps out of the annual files; the last such download was 8.5 GB for nothing
shippable.

## 3. Two candidate collections, separate from the annual files

`isc_survey_hostnames/` holds what round 9's 13.1 million Internet Domain Survey hosts left outside
your release: [CANDISC] hosts of the 1996-1997 surveys, candidates by your ruling of 5 September that
a DNS listing is not website evidence.

`server_header_hostnames/` is new, as the evidence rule instructs for mail and Usenet delivery
headers: [CANDHDR] exact hostnames whose only dated evidence is a header a mail or news server wrote
about itself (`Received: by`, `Path`, `X-Trace`, `NNTP-Posting-Host`), proof of a host in service,
not of a website. It ships with per-host provenance and the seven-column exclusion ledger of its
validation run; a host promotes only beside an exact-host capture for that year.

Its worth, measured on 98,381 header-dated host-years from eight Usenet hierarchies, against
captures already in our store: **1.16% carry an exact-host capture for the same year** (95% interval
1.10 to 1.23), against 0.14% to 0.82% at a year shifted by one to three; 2.10% in any in-window year, beside the
2.67% you measured on Internet Domain Survey hosts over 1996-2013. By leftmost label: dial-up shaped
names 0.06%, infrastructure names 4.07%, `www` and `web` names 31.1%. All are lower bounds (partial
index, Usenet only) and rank the verification queue.

## 4. The two open questions

**Q1. Discovering pre-1996 web data at scale.**

No pre-1996 hostname can meet the evidence rule as written: every qualifying pattern is a web
capture, and the Internet Archive began crawling in 1996. The question needs a pre-1996 evidence
standard before it needs sources; we propose three tiers, named by what wrote the date.

Tier A, a pre-1996 web capture held by another custodian (national libraries, university archives,
software mirrors that kept HTTP logs): the evidence rule's own standard, small and institutional in
coverage. Tier B, a server naming the exact host at a date: news and mail headers as in section 3,
dated FTP mirror listings, UUCP maps; before 1996 the only machine-stamped option, proving a host in
service, not a website. Tier C, dated human-written mentions: candidates only.

What we can add is the tier-B corpus and its cost: about 110 GB of Usenet reaching before 1996 is
already on disk with per-post `Date` and server headers, and the shipped extractor reads 2.6
million host-carrying posts an hour. Limits: the server's clock dates it, the hosts are servers and
relays, coverage skews to institutions that ran news. Retention: a pre-1996 collection held apart
from 1996-2001, with source, message-id, header field and stamp per host, and an overlap report
against the benchmark.

**Q2. Determining the year a website existed more accurately.**

Three evidence levels with measured error rates, the level travelling with the record. Direct: an
exact-host capture in the target year from an archive index or a custodian's per-host
extract, the only route into an annual file. Availability check: the Wayback Machine availability
API, graded against CDX ground truth on disk, 187 of 204 year-pairs recovered (91.7%, 94.3% at 2001)
and 40 of 40 CDX-negative domains empty; it returns HTTP 200 captures only and drops `www.`, so
every miss under-claims. Discovery-only: DNS surveys and server-written headers at the rates of
section 3, which rank a verification queue before a request is spent.

Reconciliation: at export every candidate is diffed against your `candidate_pool.txt` and six
annual files, and a name accepted annually leaves the pool. We propose one field per record,
`evidence_level` (direct, discovery, unresolved), so the reconciliation is machine-checkable on your
side; our manifests carry `evidence_type` and `acquisition_method`, from which it is a lookup.
Promotion only beside an exact-host, target-year capture; nothing is inferred between a bare name
and its `www.` form or between adjacent years.

Where the availability check pays: of 6,568,275 domains held in 2000 and missing 2001, one query
pinned at mid-2001 recovers 55.0% +/- 6.3%; on names with no dated evidence at all it yields 114 EE
an hour, too little to run. Both instruments err toward omission.

## 5. Merge, overlap and reconciliation

[MERGE_RECONCILIATION]

## 6. Reproduction and limits

[REPRODUCTION_RESULT] `README.md` gives the route and the file map. Code: `source/source.tar.gz` at
the commit in `source/COMMIT.txt`, the research loop as `source/fleet.tar.gz`; method and results:
`experience-summary.md` and `findings.md`; the merge audit: section 5 and `audit/`; your calculator,
copied in unmodified: `equivalent_english_domain_calculator/`.

Two gaps against the evidence rule: the seven-column exclusion ledger exists for the header
collection's run only (`candidates_unparsed.txt` carries a reason per line for the rest), and the
TLD gate is the public suffix list plus nine retired ccTLDs, not a documented IANA list. Worth
expanding next, priced in `experience-summary.md`: dated registry datasets for the candidate track,
and exact-host captures beside the two candidate collections, the one route that promotes either.
