# Internet Digital Ark: round 12

Additions to your annual files, against your release `merge261008-3`, scored by your calculator. No
record is in your file for its year.

## 1. Results

| | 1996 to 2001 | 2002 to 2013 | check |
|------------------|-----------------:|-----------------:|----:|
| Original total, records | 136,209,327 | 367,376,239 | 1 |
| Equivalent-English total | 74,492,066.7780 | 196,062,811.5051 | 2 |
| Increment, records | 27,491 | 15,116,853 | 3 |
| Equivalent-English increment | 25,538.6729 | 14,561,981.6574 | 4 |
| Equivalent-English after merge | 74,517,605.4509 | 210,624,793.1625 | 2 + 4 |
| Growth rate | 0.0343% | 7.4272% | 5 |
| Score, t = 73 days (2 August to 14 October 2026) | S = 10 x (0.0342837486 / 73) = 0.004696404 | S = 10 x (7.4272023060 / 73) = 1.017424973 | 5 |

Combined increment: 14,587,520.3303 equivalent-English (25,538.6729 + 14,561,981.6574). Each numbered check is a
pasted command in `README.md`, section Check.
The additions hold 9,449,390 distinct names (check 6). Per year: `audit/merge_stats_ark_*.csv`
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
- `extended_years/`: per year, `YYYY.txt` (the same as `additions/YYYY.txt`), ours, none in your file for that year;
  `evidence_ledger.csv`, one capture URL per record. Your release is not shipped back.
- `audit/merge_audit_ark_*.json`: the merge against your release, in your column names;
  28 of 28 reconciliation checks passed (`bash verify.sh` prints the count).
- `Open Research Questions/`: section IV-A, with each test's code, log, sample and screenshots.
- Candidate files list names without a 2xx or 3xx capture for their year and count in no figure
  above. `README.md` lists every folder and the rebuild.
