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

Combined increment: [COMBINEDEE] equivalent-English ([EE] + [EXTEE]).
The additions hold [DISTINCTNEW] distinct names (check 6). Per year: `audit/merge_stats_ark_*.csv`
and `extended_years/dedup_report.csv`.

## 2. Checks

Inside the extracted archive, in `bash` with Python 3.10 or newer and `bc`, pasting from
`report.md`. Paste the first two lines once; each numbered check then prints its row's figures.
Check 2 takes about 7 minutes and up to 11 GB of memory.

    ee() { for f; do python3 equivalent_english_domain_calculator/equivalent_english_domains.py "$f" --output-dir "${TMPDIR:-/tmp}/ee"; done | awk '/^Equivalent-English/ {s += $NF} END {printf "%.4f\n", s}'; }
    B=baseline/[BASELINE]; X=extended_years
    # 1
    cat $B/????.txt | wc -l
    echo $(( $(cat $X/????.txt | wc -l) - $(cat $X/additions/*.txt | wc -l) ))
    # 2
    ee $B/????.txt
    echo "$(ee $X/????.txt) - $(ee $X/additions/*.txt)" | bc
    # 3
    cat additions/*.txt hostnames/*.txt | wc -l
    cat $X/additions/*.txt | wc -l
    # 4
    ee additions/*.txt hostnames/*.txt
    ee $X/additions/*.txt
    # 5, growth then S
    echo "g = 100 * [EE] / [EEBASELINE]; g; 10 * g / [TDAYS]" | tr -d , | bc -l
    echo "g = 100 * [EXTEE] / [EXTBASELINEEE]; g; 10 * g / [TDAYS]" | tr -d , | bc -l
    # 6
    cat additions/*.txt hostnames/*.txt $X/additions/*.txt | LC_ALL=C sort -u | wc -l

`bash verify.sh` confirms that each `extended_years/YYYY.txt`, minus our additions, is
byte-identical to your file (sha256 in `extended_years/manifest.json`), and re-checks the rest of
the archive.

## 3. Source and rule

**One source**: the Internet Archive CDX API, `web.archive.org/cdx/search/cdx`. For 2002 to 2013
we query each public suffix, such as `co.uk`, with `matchType=domain` and read every result page.
1996 to 2001 holds hostnames (`hostnames/`) from those queries and registrable domains
(`additions/`) from one query per domain.

**The rule.** A record is one exact hostname in one year. It is kept when a capture of that exact
host stamped in that year answered 2xx or 3xx, the host passes your `HOST_RE` and its TLD existed
that year; it is dropped when your file for that year holds the name. Nothing is inferred from
another year, no `www.` or bare variant is generated, and each record cites its capture.

## 4. Files

- `additions/`, `hostnames/`: 1996 to 2001 registrable domains and hostnames, one evidence row per
  record.
- `extended_years/`: per year, `additions/YYYY.txt` (ours) and `YYYY.txt` (yours merged with ours);
  `evidence_ledger.csv`, one capture URL per record.
- `audit/merge_audit_ark_*.json`: the merge against your release, in your column names;
  [RECONCILIATION] reconciliation checks passed (`bash verify.sh` prints the count).
- `Open Research Questions/`: section IV-A, with each test's code, log, sample and screenshots.
- Candidate files list names without a 2xx or 3xx capture for their year and count in no figure
  above. `README.md` lists every folder and the rebuild.
