# Open Research Questions

Built [BUILT_AT] against your release [RELEASE]. Labels: Validated (reproduced
independently); Tested, not independently verified (run once); Pending validation (not yet
run).

## Q1. How can historical web data from before 1996 be discovered and acquired at scale?

### Proposed approaches

[Q1_IA_PRE1996_FINDING] Earlier web data survives in public bulk material, fetched and parsed
whole: Usenet archives, CD-ROM images and FTP mirrors on archive.org, host tables and
server logs. [Q1_USENET_WWW_ANNOUNCE_FINDING] So this material's value is dating hosts and
finding hosts gone before [FIRST_YEAR], not annual EE. We propose a dated candidate collection
with source, `sha256` and locator per host; a host enters an annual file only with a capture
from that year (Pending validation).

### Completed related work or tests

Script tests (`code/<id>.py`) read whole sources or seeded samples; a network error never
counts as no capture. Source tests measure the EE of hosts in neither your files nor ours,
against the release named in `tests.csv`, which lists [Q1_MORE] more, not run or with no EE,
with their reason.

[Q1_TABLE]

### Preliminary technical-feasibility findings

[Q1_ARCHIVE_SCALE_FINDING] Each host keeps a locator (file and offset, or message ID). A
second, independent run fetched each Validated source with the same `sha256` and priced it to
the same EE.

### Preliminary practical-operability findings

Every source tested is public and every request is logged, but robots.txt refused some
repositories (CU Scholar, UW ResearchWorks, Zenodo) and archive.org only lends its scans of
printed Internet guides (`tests.csv`); each source's robots and terms check is in
`evidence/<id>/`. A date from these sources shows a host existed, not that it served a
website.

### Limitations

Host tables list machines, mostly military, academic and government; one list and one disc
cannot estimate coverage. Re-pricing a source test needs our name lists from the day it ran,
which are not shipped.

### Next steps

Pending validation: the collection's overlap with your files, and asking national libraries
and university archives for captures from before [FIRST_YEAR].

## Q2. How can the year in which a website existed be determined more accurately?

### Proposed approaches

Evidence has three levels per host and year. **Direct**: an exact-host `2xx` or `3xx`
capture, dated page or dated record of that year; only it assigns a year, and only its own
year; a candidate enters an annual file only once that evidence is retained.
**Discovery-only**: DNS surveys, registries, headers and error captures rank names to check.
**Unresolved**: values no parser reads, kept apart. A level belongs to one host-year, not to a
host. Reconciling merges sorted files: a pool name already in an annual file leaves the pool,
and the rest stay in it with their source.

### Completed related work or tests

Tests without a script are commands (`logs/<id>/command.txt`), run from our source
(`../source/source.tar.gz`): `$HIS` is your release folder, `$NETNEW` and `$EXTENDED` our
export, `$AUDIT` and `$CDX` in `evidence/<id>/`.

[Q2_TABLE]

### Preliminary technical-feasibility findings

[Q2_RECHECK_FINDING] Every check merges sorted text files or draws a seeded sample, with no
database.

### Preliminary practical-operability findings

[Q2_ISC_PROMOTION_FINDING] [Q2_RDAP_BOUNDS_FINDING] Continuity cannot be inferred: your
consecutive files share only [CONTINUITY_2000_2001_PCT]% of names.

### Limitations

A missing capture never proves a site absent. [Q2_CAPTURE_CONTENT_FINDING]

### Next steps

Pending validation: an evidence-level column on every exported host-year record, a page read
per direct capture, and historical WHOIS and DNS as year bounds.

## Files

`tests.csv` lists every test by name and id, `sources.csv` every source. `code/`, `logs/`,
`samples/`, `evidence/` and `screenshots/` ([SCREENSHOTS]) hold their files, by id.
