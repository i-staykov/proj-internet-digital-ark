# Open Research Questions

Our answers to the two open research questions of section IV-A, tested against your release
[RELEASE] (built [BUILT_AT]).

Every finding names the test behind it, and every test carries one label:

- **Validated**: a second, independent run reproduced it.
- **Tested** (not independently verified): we ran it once; its code, log and sample are in
  this folder, so it can be re-run.
- **Pending validation**: proposed, not yet tested.

Each test's code, log, sample and source record are in this folder by id (`tests.csv`,
`sources.csv`); `screenshots/` holds [SCREENSHOTS].

## In short

**Web data from before [FIRST_YEAR].** The Internet Archive holds no capture before [FIRST_YEAR], not even
for the first web servers. Earlier web data survives in public bulk sources (Usenet archives,
archived CD-ROMs and FTP mirrors, network host tables, server logs) that can be downloaded and read
whole. Your [FIRST_YEAR] file already holds most of the hosts they name, so their main value is
dating hosts, not adding new ones.

**The year a website existed.** Only a capture of that exact host in that year assigns the year;
every other kind of evidence ranks candidates but never assigns a year. A live re-check confirms
our assigned years, while survey names and registration dates fail as year evidence.

## Q1. How can historical web data from before 1996 be discovered and acquired at scale?

### Proposed approaches

- **Find bulk sources that date their own records**: Usenet posts (by header), archived
   CD-ROMs and FTP mirrors (by disc or file), host tables (by edition), server logs (by request).
- **Download each whole**, record its `sha256`, and extract every host with its date and a
   locator (file and offset, or message ID).
- **Compare with your files**; keep the rest as a dated candidate collection.
- **Promote a host to an annual file only with a web capture from that year.**

The tests below cover finding, downloading and comparing; shipping the collection and promoting
its hosts are Pending validation.

### Completed related work or tests

A network error is retried, never counted as a missing capture.

[Q1_TABLE]

[Q1_MORE] more sources were checked but not run, or gave no new hosts (`tests.csv`).

### Preliminary technical-feasibility findings

- [Q1_IA_PRE1996_FINDING]
- Every source above was downloaded whole and parsed by a short script; for the two Validated
  ones, an independent second run fetched identical bytes and got the same result.
- [Q1_ARCHIVE_SCALE_FINDING]

### Preliminary practical-operability findings

- [Q1_USENET_WWW_ANNOUNCE_FINDING] The value lies in dating hosts and in hosts gone
  before [FIRST_YEAR].
- All sources tested are public. robots.txt refused three repositories (CU Scholar, UW
  ResearchWorks, Zenodo), and archive.org only lends its scans of printed Internet guides; each
  source's robots and terms check is in `evidence/<id>/`.

### Limitations

- A date from these sources shows that a host existed, not that it served a website.
- Host tables list machines, mostly military, academic and government; one server list and
  one disc cannot estimate coverage.
- Re-pricing a source test needs our name lists from the day it ran, which are not shipped.

### Next steps

Pending validation: ship the dated collection with its overlap with your files, and ask
national libraries and university archives which captures from before [FIRST_YEAR] they hold.

## Q2. How can the year in which a website existed be determined more accurately?

### Proposed approaches

Every record is one host in one year, and its evidence has one of three levels:

| level | what counts | what it may do |
|:------------|:--------------------------------------------|:--------------------------|
| Direct | a capture of that exact host in that year that answered `2xx` or `3xx`, a dated page, or a dated record | assign that year, and only that year |
| Discovery-only | DNS surveys, registries and WHOIS, mail and news headers, error captures | rank names to check, never assign a year |
| Unresolved | values no parser can read | stay apart, in their own file |

- A level belongs to a host and year: a name can be a candidate for one year, direct for another.
- No year is inferred from another year.
- A candidate enters an annual file only once its direct evidence is retained, and then leaves
  `candidate_pool.txt`; reconciling the two is a merge of sorted files.

### Completed related work or tests

Sampled tests queried the live archive or RDAP; the rest run on whole files (`logs/<id>/`).

[Q2_TABLE]

### Preliminary technical-feasibility findings

- [Q2_RECHECK_FINDING]

### Preliminary practical-operability findings

- [Q2_ISC_PROMOTION_FINDING]
- [Q2_RDAP_BOUNDS_FINDING]
- Continuity cannot be inferred: your files for consecutive years share only
  [CONTINUITY_2000_2001_PCT]% of their names.

### Limitations

- A missing capture never proves that a site was absent. [Q2_CAPTURE_CONTENT_FINDING]

### Next steps

Pending validation: an evidence-level column on every exported record, a content check on
every direct capture, and historical WHOIS and DNS tested as year bounds.
