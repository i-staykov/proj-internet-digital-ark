# Internet Digital Ark: round [ROUND]

Additions to the 1996-2001 annual lists and to the candidate pool, against your release
`[BASELINE]`. "The specification" is your
`Internet_Digital_Ark_Project_0918_Update.docx` of 18 September, "the evidence rule" its section XIII
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
name your release already holds (section 3). [CANDREG] are registrable domains whose only dated
evidence the evidence rule keeps out of the annual files (registry zone and drop lists, dated
directories, author e-mail hosts); [CANDHOST] are hostnames, section 3.

[CUMULATIVE_SENTENCE]

## 2. What is new, and where it came from

[ATTRIBUTION_TOP]

`ia_cdx_domain_sweep` queries the Internet Archive's capture index (CDX) domain by domain for
names in your files and keeps every captured hostname beneath them, each with the archive's own
14-digit timestamp. `bulk_cdx_file` is two such indexes
**read whole at hostname grain**, keeping every HTTP 200 row dated 1996-2001:

- **Dartmouth NBER ARCS**, a research crawl collection on archive.org with a CDX beside each of
  its 282 items: the 25 with 1996-2001 stamps, read whole (4.1 GB), paid 134,564 records and
  83,868 EE. At registrable-domain level it adds nothing, every domain already held; one level
  down it pays.
- **Storage node ia600702**, the public 57.6 GB CDX of every capture on one archive.org node:
  1,031,419,773 rows, 14,192,504 of them HTTP 200 and dated 1996-2001, 931,864 host-years,
  **88.8% already in your release or our database**; the rest, 104,347 records, paid 50,722 EE. A
  bulk index read now measures the benchmark's saturation as much as it adds to it.

Our research loop now rejects, before download, any hostname source whose evidence class the
evidence rule keeps out of the annual files; the last such download was 8.5 GB for nothing
shippable.

## 3. The candidate claim, net of everything your release holds

`candidate_additions.txt` is every candidate we hold, [CANDADD] names, after removing
[CANDHELD] names that your release already holds outside the annual files: in
`candidate_pool.txt`, in `candidate_pool_unparsed_format.txt`, or in your
`isc_survey_hostnames/` collection, which holds nearly every Internet Domain Survey host we
collected. Names in any of your six annual files are removed as well. What remains is
[CANDREG] registrable domains and [CANDHOST] hostnames. `isc_survey_hostnames/` now ships
[CANDISC] hosts, since your collection already holds the rest.

`server_header_hostnames/` is new, as the evidence rule instructs for mail and Usenet delivery
headers: [CANDHDR] exact hostnames whose only dated evidence is a header a mail or news server wrote
about itself (`Received: by`, `Path`, `X-Trace`, `NNTP-Posting-Host`), proof of a host in service,
not of a website. It ships with per-host provenance and its run's exclusion ledger; a host
promotes only beside an exact-host capture for that year.

Its worth, measured on 98,381 header-dated host-years from eight Usenet hierarchies, against
captures already in our database: **1.16% carry an exact-host capture for the same year** (95% interval
1.10 to 1.23), against 0.14% to 0.82% at a year shifted by one to three; 2.10% in any in-window year, beside the
2.67% you measured on Internet Domain Survey hosts over 1996-2013. By leftmost label: dial-up shaped
names 0.06%, infrastructure names 4.07%, `www` and `web` names 31.1%. All are lower bounds (partial
index, Usenet only) and rank the verification queue.

## 4. The two open questions

Both are answered in `Open Research Questions/`, as `Open Research Questions.docx` with its tests,
sources, code, logs and samples beside it, and as plain text in `开放性研究问题/`, one file per
question under the six headings of section X.

## 5. Merge, overlap and reconciliation

[MERGE_RECONCILIATION]

## 6. Reproduction and limits

[REPRODUCTION_RESULT] `README.md` gives the route and the file map. Code: `source/source.tar.gz` at
the commit in `source/COMMIT.txt`, the research loop as `source/fleet.tar.gz`; method and results:
`experience-summary.md` and `findings.md`; the merge audit: section 5 and `audit/`; your calculator,
copied in unmodified: `equivalent_english_domain_calculator/`.

Two gaps against the evidence rule: the seven-column exclusion ledger exists for the header
collection's run only (`candidates_unparsed.txt` carries a reason per line for the rest), and the
TLD gate is the public suffix list plus nine retired ccTLDs, not a documented IANA list. One
conservative exclusion: a registrable domain your release holds only as hostnames beneath it is
treated as held, so 2,114 domain-years (1,019 EE) with their own exact-host capture are not
claimed; they are the excess the rebuild above returns.
