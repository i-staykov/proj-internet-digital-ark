# Internet Digital Ark delivery

Additions to your annual domain files, 1996 to 2013. A record is one exact hostname in one year,
kept on its own 2xx or 3xx web capture of that host in that year, and never one your file for that
year holds. `report.docx` gives the figures; each check below prints one of them.

## Check

Beside the download, then inside the extracted folder, with Python 3.10 or newer and
[`uv`](https://docs.astral.sh/uv/). The first line prints the sha256 given in the mail.

```
shasum -a 256 [ARCHIVE].7z
7z x [ARCHIVE].7z && cd [ARCHIVE]
B=/path/to/merge261016  # your release, not shipped back; baseline/README.txt gives its sha256
HIS=$B bash verify.sh
```

`verify.sh` prints PASS, FAIL or SKIP per check and exits non-zero on a FAIL; SKIP means the
checked thing is not in the archive, or `HIS` is unset. It checks the checksums, one evidence row
per record, the 2002 to 2013 additions against your files and their sha256, the candidate files
against your pool, and reruns your calculator on your 1996 file.

Each figure of the report's table, by its check number, in `bash` with `bc`. Paste the first
block once; check 2 takes about 7 minutes and up to 11 GB of memory.

```
ee() { for f; do python3 equivalent_english_domain_calculator/equivalent_english_domains.py "$f" --output-dir "${TMPDIR:-/tmp}/ee"; done | awk '/^Equivalent-English/ {s += $NF} END {printf "%.4f\n", s}'; }
X=extended_years
T=$(python3 -c 'import datetime as d; print((d.date.today() - d.date(2026, 8, 2)).days)')
```

```
# 1, your records: 1996 to 2001, then 2002 to 2013
cat $B/199?.txt $B/200[01].txt | wc -l
cat $B/200[2-9].txt $B/201[0-3].txt | wc -l
# 2, your equivalent-English
E1=$(ee $B/199?.txt $B/200[01].txt); echo $E1
E2=$(ee $B/200[2-9].txt $B/201[0-3].txt); echo $E2
# 3, our records
cat additions/*.txt hostnames/*.txt | wc -l
cat $X/20*.txt | wc -l
# 4, our equivalent-English
A1=$(ee additions/*.txt hostnames/*.txt); echo $A1
A2=$(ee $X/20*.txt); echo $A2
# 5, growth in percent, then S = 10 x growth / t, with t in whole days since 2 August 2026
echo "g = 100 * $A1 / $E1; g; 10 * g / $T" | bc -l
echo "g = 100 * $A2 / $E2; g; 10 * g / $T" | bc -l
# 6, distinct new names
cat additions/*.txt hostnames/*.txt $X/20*.txt | LC_ALL=C sort -u | wc -l
```

To see the captures behind one name in one year:

```
uv run --with duckdb --no-project python provenance/trace.py "$(head -1 additions/2001.txt)" 2001
```

Rebuild every 1996 to 2001 list from the evidence, with no archive queries and no source data.
`ark intake` checks your release, linked in as `baseline/merge261016`, and writes 4.5 GB under
`source/data/held/`:

```
ln -s "$B" baseline/ && tar -xzf source/source.tar.gz -C source/ && cd source
uv sync && uv run ark intake && uv run ark rebuild ../provenance && uv run ark check
for y in 1996 1997 1998 1999 2000 2001; do
    cmp output/netnew/$y.txt ../additions/$y.txt
    cmp output/netnew/${y}_hostnames.txt ../hostnames/${y}_hostnames.txt
    cmp output/netnew/$y-ISC.txt ../isc_survey_hostnames/$y-ISC.txt
done
cmp output/netnew/evidence_manifest.csv ../additions/evidence_manifest.csv
cmp output/netnew/hostnames_evidence_manifest.csv ../hostnames/hostnames_evidence_manifest.csv
cmp output/candidate_unverified.txt ../candidates.txt
cmp output/netnew/candidate_additions.txt ../candidate_additions.txt
for f in isc_candidates.txt isc_survey_provenance.csv isc_candidates_summary.json; do cmp output/netnew/$f ../isc_survey_hostnames/$f; done
for f in header_candidates{.txt,_provenance.csv,_summary.json,_exclusions.csv}; do cmp output/netnew/$f ../server_header_hostnames/$f; done
```

Rebuild from the original sources: inside `source/`, put each download from its `sources.md` link
in `data/raw/<source>/`, copy the journals in (`cp -R ../journals/. data/raw/`), put your first
release in `legacy-data/` and run `just reproduce` (needs `just`), about 50 GB. `domain_creation_bulk`,
`dartmouth_nber_captures` and `rdap_snapshot` cannot be fetched again; the rebuild above covers them.

## Contents

| Path | Contents |
|---|---|
| `additions/` | 1996 to 2001 registrable additions per year; `evidence_manifest.csv`, one evidence row each |
| `hostnames/` | 1996 to 2001 new hostnames per year, each below a registrable domain and never one itself, so none is also in `additions/`; `hostnames_evidence_manifest.csv`, one capture each |
| `masters/` | your 1996 to 2001 file merged with both by exact name, `LC_ALL=C sort -m -u` |
| `extended_years/` | 2002 to 2013: `<year>.txt` ours, none in your file for that year, `evidence_ledger.csv` the journal line of one capture per addition (line `line` of `journals/` plus `source_file` without `data/raw/` holds its `url`; that input's `replay` in `manifest.json`, filled with the row's `timestamp` and that `url`, is its replay link), `dedup_report.csv` in your merge columns, `manifest.json` the inputs and your files' sha256 |
| `baseline/README.txt` | your release the additions count against: the sha256 and line count of each file of it the checks read |
| `candidate_additions.txt`, `candidate_additions_summary.json` | every candidate name we hold that is in neither your pool nor your annual files, with their count and equivalent-English |
| `candidates.txt`, `isc_survey_hostnames/`, `server_header_hostnames/` | the candidate collections, each with provenance: names without year-specific web evidence, ISC Domain Survey hosts, and hosts named only in mail or Usenet server headers |
| `candidates_unparsed.txt` | values the parser refused, each with its reason |
| `provenance/` | the evidence graph of every name the lists hold, as Parquet, with `trace.py` and `LOAD.sql` |
| `audit/` | the merge against your release in your column names, `merge_stats_ark_*.csv` and `merge_audit_ark_*.json`; per-source contribution, source saturation, `year_growth.csv` and the ingest audits |
| `source/` | `source.tar.gz`, the code at `COMMIT.txt` with `pyproject.toml` and `uv.lock`; `fleet.tar.gz`, the research agents at `FLEET_COMMIT.txt` |
| `experience-summary.md`, `findings.md` | what worked and what did not; the findings with their measurements |
| `metric-explained.md`, `equivalent_english_domain_calculator/` | the metric, and your calculator, unmodified |
| `sources.md`, `sources-closed.md` | every source tried: those used, with their download link, and those dropped, with the measurement that ruled each out |
| `Open Research Questions/` | section IV-A: `Open Research Questions.docx` with each test's code, log, sample and screenshots |
| `journals/`, `logs/`, `seeds/` | the raw response behind every shipped evidence row (`journals/README.txt` names the sets left out on size), run logs, seed lists |
| `SHA256SUMS`, `verify.sh`, `verify_isc_candidates.py` | the checks above |

Name lists are one lowercase name per line, `LC_ALL=C` sorted, without a header. Every `.csv` is
RFC 4180 and UTF-8 with one header row; an `audit/` file with a header and no rows means the
audited condition did not occur. Journals are gzipped JSON Lines; provenance is Parquet.

Names found only in DNS, registry, RDAP or WHOIS records, in 4xx or 5xx captures, or in mail and
Usenet headers are candidates. A candidate enters an annual file only with a 2xx or 3xx capture of
that exact host in that year.
