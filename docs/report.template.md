# Internet Digital Ark: round [ROUND]

Additions to your annual files, against your release `[BASELINE]`, scored by your calculator. No
record is in your file for its year.

## 1. Results

| | 1996 to 2001 | 2002 to 2013 | check |
|------------------|-----------------:|-----------------:|----:|
| Original total, records | [BASELINEPAIRS] | 411,293,455 | 1 |
| Equivalent-English total | [EEBASELINE] | [EXTBASELINEEE] | 2 |
| Increment, records | [TOTAL] | [EXTPAIRS] | 3 |
| Equivalent-English increment | [EE] | [EXTEE] | 4 |
| Equivalent-English after merge | [EEPOSTMERGE] | [EXTPOSTMERGE] | 2 + 4 |
| Growth rate | [EEGROWTH] | [EXTGROWTH] | 5 |
| Score, t = [TDAYS] days ([TSPAN]) | [SCORE_CORE] | [SCORE_EXT] | 5 |

Combined increment: [COMBINEDEE] equivalent-English ([EE] + [EXTEE]). Each numbered check is a
pasted command in `README.md`, section Check.
The additions hold [DISTINCTNEW] distinct names (check 6). Per year: `audit/merge_stats_ark_*.csv`
and `extended_years/dedup_report.csv`.

## 2. Source and rule

**Internet Archive CDX API** (`web.archive.org/cdx/search/cdx`): for 2002 to 2013 one
`matchType=domain` query per public suffix, such as `co.uk`, every result page read; for 1996 to
2001 hostnames from those queries and registrable domains from one query per domain. A row is
dated by the capture's own timestamp, answered 2xx or 3xx: your category (1), a CDX record with
an explicit capture timestamp for the exact hostname.

**End of Term web archive CDXJ indexes** (EOT-2004, -2008, -2012; eotarchive S3, CC0): the
crawler's capture stamp in the index line, status 2xx or 3xx: category (1), an archive capture
record with its timestamp.

**HTTP Archive request logs** (archive.org items `httparchive_2010` to `_2013`): each
WebPageTest run's own request log, one line per request stamped at fetch time with the host and
the response code; a 2xx or 3xx dates the exact host: category (3), a custodian's dataset with
item-level, year-specific records (item, zip, test and log line cited).

**ClueWeb09 url-docid map** (`ir.nist.gov`, the receipted prefix of its 2016 Wayback capture):
every page fetched in January and February 2009 with its docid; the documented crawl window dates
the host, the docid is the record: category (2), a dated, traceable crawl list.

**ClueWeb12 URL list** (LAW, `clueweb12-nat.urls.gz`): every page fetched 2012-02-10 to 05-10 in
crawl order; the documented window dates the host, the URL's ordinal is the record: category (2).

**Web Data Commons 2012 Hyperlink Graph host index** (`sd-index.gz`, extracted from the Common
Crawl 2012 corpus, crawled 2012-01-27 to 06-05): the hosts of the pages crawled, each with its
index; WDC kept only links to another crawled page, so every host had a page fetched: category
(2), a dated, traceable link graph listing the exact hostname.

**The rule.** A record is one exact hostname in one year. It is kept when a capture of that exact
host stamped in that year answered 2xx or 3xx, the host passes your `HOST_RE` and its TLD existed
that year; it is dropped when your file for that year holds the name. Nothing is inferred from
another year, no `www.` or bare variant is generated, and each record cites its capture.

## 3. Files

- `additions/`, `hostnames/`: 1996 to 2001 registrable domains and hostnames, one evidence row per
  record.
- `extended_years/`: per year, `YYYY.txt`, ours, none in your file for that year; `evidence_ledger.csv`,
  the journal line of one capture per record. Your release is not shipped back.
- `audit/merge_audit_ark_*.json`: the merge against your release, in your column names;
  [RECONCILIATION] reconciliation checks passed (`bash verify.sh` prints the count).
- `Open Research Questions/`: section IV-A, with each test's code, log, sample and screenshots.
- Candidate files list names without a 2xx or 3xx capture for their year and count in no figure
  above. `README.md` lists every folder and the rebuild.
