# Internet Digital Ark: round [ROUND]

Additions to your annual files, against your release `[BASELINE]`, scored by your calculator. No
record is in your file for its year.

## 1. Results

| | 1996 to 2001 | 2002 to 2013 | check |
|------------------|-----------------:|-----------------:|----:|
| Original total, records | [BASELINEPAIRS] | 367,376,239 | 1 |
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

**One source**: the Internet Archive CDX API, `web.archive.org/cdx/search/cdx`. For 2002 to 2013
we query each public suffix, such as `co.uk`, with `matchType=domain` and read every result page.
1996 to 2001 holds hostnames (`hostnames/`) from those queries and registrable domains
(`additions/`) from one query per domain.

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
