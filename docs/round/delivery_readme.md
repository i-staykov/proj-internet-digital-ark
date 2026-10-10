# Internet Digital Ark delivery

Evidence-backed annual domain lists for 1996-2013. **The annual files are a website-evidence
product** under section XIII of your specification: a line qualifies only on
exact-host, year-specific web evidence, and a name known by any other route ships as a candidate.
The standard is at the end. **The counts are in `report.md` and printed by `bash verify.sh`.**

- **Additions count against the release in `baseline/`, named in `baseline/README.txt`**, no other.
- **`additions/`, `hostnames/` and, for 2002 to 2013, `extended_years/` are the deliverable**:
  registrable domains and the valid hostnames beneath them, each backed by its own evidence.
- **`candidates.txt`, `isc_survey_hostnames/` (the Internet Systems Consortium Domain Survey) and
  `server_header_hostnames/` are candidate collections**, claimed together in
  `candidate_additions.txt` and priced separately at the same rate. None enters an annual figure.

## What is in here

| Path | Contents |
|---|---|
| `report.docx`, `report.md` | The report: methods, results, per-source yield, limitations |
| `masters/<year>.txt` | **Your annual file for that year merged with `additions/` and `hostnames/` by exact name**, no roll-up: `LC_ALL=C sort -m -u baseline/<release>/<year>.txt additions/<year>.txt hostnames/<year>_hostnames.txt`. `audit/year_growth.csv` reconciles it |
| `additions/<year>.txt` | **Additions only**, against the reference baseline |
| `extended_years/<year>.txt`, `extended_years/additions/<year>.txt` | 2002 to 2013, for each year with an addition: **your file merged with ours**, `LC_ALL=C sort -m -u`, and **ours alone**, each on its own capture that year. `evidence_ledger.csv` holds one capture per addition, `dedup_report.csv` your merge columns, `manifest.json` the sha256 of your file that `verify.sh` proves each merged file contains exactly |
| `additions/evidence_manifest.csv` | One row per added (domain, year) with the evidence behind it |
| `hostnames/<year>_hostnames.txt` | **Annual hostname additions**: qualifying exact hostnames beneath held registrables, disjoint from `additions/` |
| `hostnames/hostnames_evidence_manifest.csv` | One row per added (hostname, year) with its parent, source, method and the capture behind it |
| `isc_survey_hostnames/<year>-ISC.txt` | **Candidate collection**, grouped by DNS survey year, not annual website evidence |
| `isc_survey_hostnames/isc_candidates.txt` | The deduplicated candidate collection, one exact hostname per line across all survey years |
| `isc_survey_hostnames/isc_survey_provenance.csv` | Per-host provenance for every surviving hostname-year: survey edition, source filename, original or recovery URL, record location keyed by hostname, extraction method and target year |
| `isc_survey_hostnames/isc_candidates_summary.json` | Measured distinct candidate count and equivalent-English total, survey-year counts, provenance rows and TLD counts, tied to the reference release. Year counts must not be summed as the candidate score |
| `server_header_hostnames/header_candidates.txt` | **Candidate collection** under the evidence rule: exact hostnames whose only dated evidence is a server-written mail or Usenet header, not a web capture |
| `server_header_hostnames/header_candidates_provenance.csv` | Per-host provenance for every name: target year, source, acquisition method, evidence type, record location (archive item and message index) and source URL |
| `server_header_hostnames/header_candidates_summary.json` | Distinct count, equivalent-English, host-years by year and by source, provenance rows, rows the evidence rule's hostname integrity gate refused, and the promotion route |
| `server_header_hostnames/header_candidates_exclusions.csv` | The exclusion ledger of this collection's validation run: hostname, scope, source file, record location, exclusion reason, normalization decision, evidence reference |
| `candidates.txt` | Domains lacking year-specific evidence. Never mixed into the annual lists |
| `candidate_additions.txt` | **The candidate-track claim, one pool**: every candidate collection we hold, registrable domains, ISC survey hostnames and server-header hostnames together, minus every name in your `candidate_pool.txt` or in any of your six annual files. Provenance per name is in `provenance/`, `isc_survey_hostnames/isc_survey_provenance.csv` and `server_header_hostnames/header_candidates_provenance.csv` |
| `candidate_additions_summary.json` | That pool's measured size and equivalent-English, split by counting unit, tied to the reference release |
| `candidates_unparsed.txt` | **The separately labelled unparsed file your specification asks for**, one row per malformed-but-recoverable value with the reason the parser refused it: `not_rfc1123` (underscores and over-long labels, which the era really had), `no_public_suffix`, `reverse_dns`. Read from the capture journals; in no figure |
| `baseline/<release>/` | **The reference the additions are counted against**, including the six 1996 to 2001 annual files and `candidate_pool.txt` for exact-name ISC reconciliation; each 2002 to 2013 file of yours we add to is named by sha256 in `extended_years/manifest.json`. See `baseline/README.txt` |
| `provenance/` | The evidence graph as Parquet, plus `trace.py` and `LOAD.sql`. This is what makes the result checkable offline |
| `audit/` | Normalization and salvage audits, the per-source contribution table, the source-saturation ledger, and `year_growth.csv`, which reconciles `masters/` against `baseline/` plus `additions/` and `hostnames/` |
| `audit/source_saturation_ledger.csv` | One row per source family evaluated, generated from `sources.md` and `sources-closed.md` by column header. **Thirteen columns**, one per field of the schema you asked for (`coverage_period`, `retrieval_method`, `baseline_overlap`, `effort` and `source_link` among them). `n/a` means the source entry does not say; an empty cell means that page has no such column |
| `audit/merge_stats_ark_*.csv`, `audit/merge_audit_ark_*.json` | The merge against the current baseline in your own column names, plus every reconciliation check run and whether it passed, so your audit and this one can be diffed directly |
| `journals/` | The raw response of every archive and page query, plus the extraction journals: the offline inputs of step 3 below. **The largest journal sets are excluded on size**; `journals/README.txt` names them with their sizes, every assignment they back remains checkable through `provenance/`, and they are available on request |
| `logs/` | Execution logs from the runs that produced this |
| `seeds/` | The auxiliary hostname and URL seed pool, and the page lists used for expansion |
| `source/` | The code that produced everything here, plus the commit it was built from; `fleet.tar.gz` is the code of the unattended research agents (workflows, prompts, policy), at the commit named in `FLEET_COMMIT.txt` |
| `sources.md` | One row per source not closed: what dates one item and **a link to its download address**. Each ingest spec is on `docs/registers/approved-sources-list.md` inside `source/` |
| `sources-closed.md` | The other half of the source list: one row per family closed on a measurement, with the figure and the reason |
| `findings.md` | The round's research findings in full, with the measurement behind each |
| `experience-summary.md` | What worked, what did not, measured yields, limits, lessons, reusable techniques, and where to go next, distilled from `sources.md` and `sources-closed.md` |
| `Open Research Questions/` | **The two open research questions of section IV-A**: `Open Research Questions.docx`, with `tests.csv` (every test, its label and its cost), `sources.csv`, and the evidence, code, logs and samples it names |
| `开放性研究问题/` | The same answers as plain text, one file per question under the six headings of section X |
| `metric-explained.md` | The equivalent-English metric. The weights, the model version, the formula, how invalid and unmatched records are treated, and the four totals, each with the command that regenerates it |
| `equivalent_english_domain_calculator/` | Your own scorer, copied in unmodified with its fixed model, so every figure here can be re-derived without fetching anything |
| `SHA256SUMS`, `verify.sh`, `verify_isc_candidates.py` | Checksums and verification, including ISC candidate reconciliation, provenance coverage and equivalent-English recalculation |

## The four deliverables you asked for

| | you asked for | where it is |
|---|---|---|
| **D1** | the complete runnable code, scripts, configurations, dependencies and execution instructions | `source/source.tar.gz`, which is the repository at the commit named in `source/COMMIT.txt`, including `pyproject.toml` and `uv.lock`. Execution instructions are its `README.md` and the three tiers below |
| **D2** | a concise experience summary | `experience-summary.md`, with `sources.md` and `sources-closed.md` as the full source list behind it |
| **D3** | the code and explanation that normalises, merges and deduplicates against the latest baseline, with overlap counts, the accepted increment and reconciliation checks | `source/scripts/round/merge_against_baseline.py`, its output in `audit/merge_stats_ark_*.csv` and `audit/merge_audit_ark_*.json`, explained in section 5 of `metric-explained.md` |
| **D4** | the runnable equivalent-English calculation and its explanation | `equivalent_english_domain_calculator/` and `metric-explained.md` |

## File formats

- **Generated `.txt` name lists**: one name per line, lowercase, C-locale sorted, newline
  terminated, no header, no blank lines; every name of ours is ASCII. Registrable additions are
  registered domains at the Public Suffix List boundary. Masters, hostname additions and ISC
  candidates keep each exact name without collapsing it to its parent or removing `www.`.
- **Every `.csv`**: RFC 4180, comma separated, UTF-8, one header row. **An `audit/*.csv` with a
  header and no rows** means the audited condition did not occur.
- **`journals/*.jsonl.gz`**: gzipped JSON Lines, one object per query made.
- **`provenance/*.parquet`**: Parquet with ZSTD, readable by any engine. `LOAD.sql` recreates the
  tables in DuckDB; `trace.py` answers the common question without SQL.

## Checking the result

| Tier | What it proves | Needs |
|---|---|---|
| **1. Verify what is here** | Nothing has changed, and every pair traces to a recorded observation | this folder, `shasum`, `python3`, `uv` |
| **2. Rebuild from the evidence** | The shipped lists follow from the shipped evidence | `source/` and `provenance/`, no network |
| **3. Rebuild from the original sources** | The evidence follows from the source data | the source downloads and the first baseline release |

### 1. Verify what is here

```
shasum -a 256 -c [ARCHIVE].tar.gz.sha256   # the sidecar sits beside the .tar.gz, not inside it
bash verify.sh                             # from inside this folder
```

`verify.sh` prints **fifteen labelled verdicts** and exits non-zero on a failure: checksums; the
six annual and six hostname files with their counts, disjointness and an evidence row per line; the
ISC collection disjoint from your candidate pool and annual files, its equivalent-English total
reproduced; the header collection complete and inside the claim; every provenance assignment
resolving to an evidence row shipped beside it; the 2002 to 2013 merged files, each your own plus
additions you lack; the four deliverables, among them **your own calculator, run from inside this
archive, reproducing the audit's baseline figure**; and both open research questions folders. SKIP
means the checked thing is not in the archive. The calculator check needs a writable extraction: it
writes into `audit/` and cleans up after itself.

Why a single domain is in a given year, with no database, only [`uv`](https://docs.astral.sh/uv/),
one line per observation (source, kind of evidence, artifact or capture timestamp, link):

```
cd provenance
uv run --with duckdb --no-project python trace.py                    # what is in the export
uv run --with duckdb --no-project python trace.py bbc.co.uk 1999     # why this domain, this year
```

### 2. Rebuild the result from the evidence

No source data and no network: the export holds every observation this project made and every
assignment resting on one, but not your own rows. What your release holds is your files in
`baseline/`, compared by exact name: `ark intake` checks them and writes the sorted sets every
comparison reads, 4.3 GB under `source/data/held/`.

```
tar -xzf source/source.tar.gz -C source/ && cd source
uv sync
uv run ark intake                    # your release in ../baseline/, checked once
uv run ark rebuild ../provenance     # annual files, candidates, manifests
uv run ark check                     # the integrity invariants
# byte-identical:
for y in 1996 1997 1998 1999 2000 2001; do
    cmp output/netnew/$y.txt            ../additions/$y.txt
    cmp output/netnew/${y}_hostnames.txt ../hostnames/${y}_hostnames.txt
    cmp output/netnew/$y-ISC.txt        ../isc_survey_hostnames/$y-ISC.txt
done
cmp output/netnew/evidence_manifest.csv ../additions/evidence_manifest.csv
cmp output/netnew/hostnames_evidence_manifest.csv ../hostnames/hostnames_evidence_manifest.csv
cmp output/candidate_unverified.txt ../candidates.txt
cmp output/netnew/candidate_additions.txt ../candidate_additions.txt
for f in isc_candidates.txt isc_survey_provenance.csv isc_candidates_summary.json; do cmp output/netnew/$f ../isc_survey_hostnames/$f; done
for f in header_candidates{.txt,_provenance.csv,_summary.json,_exclusions.csv}; do cmp output/netnew/$f ../server_header_hostnames/$f; done
```

### 3. Rebuild from the original sources

Run from `source/`, extracted and synced as in step 2, with each bulk source from its `sources.md`
link in `data/raw/<source>/`, and the first baseline release, which this archive lacks, in
`legacy-data/`.

```
wc -l legacy-data/199[6-9].txt legacy-data/200[01].txt   # expect 8224963 total
mkdir -p data/raw && cp -R ../journals/. data/raw/       # the replay inputs, tree preserved
just reproduce                                           # the command runner: https://just.systems
cat output/netnew/199[6-9].txt output/netnew/200[01].txt | wc -l   # the registrable additions
```

`just reproduce <stage>` runs one of the six: `baseline` (`ark init`, then `ark intake` writes the
held sets), `sources` (the bulk ingests), `candidates`, `journals` (every stored network response,
replayed after the first three because the corroboration split judges a query against what the store
holds), `seeds`, and `deliver` (`ark export`, `ark stats`, then `ark check`, which reads the
exported files). Without `journals/` in `data/raw/` the replay ingests nothing, and the excluded
sets replay nothing until restored. The downloads come to about 50 GB, most of it the 47 GB
Arquivo.pt (Portuguese web archive) capture index.

**What the replay cannot re-derive.** Three sources cannot be re-fetched: `domain_creation_bulk` (a
Kaggle dataset that needs an account and may not be redistributed), `dartmouth_nber_captures` (an
archive.org item no longer served) and `rdap_snapshot` (journals held back on size, sent on
request); `audit/dartmouth_nber_captures_audit.csv` and `audit/domain_creation_bulk_audit.csv`
record what the first two contributed. **Step 2 reproduces all of it, and that is the check to
run.** Two live sources need not match a later download: the `.fr` open-data file (June 2026
edition) and the Internet Scout feed.

## Evidence standard

A hostname-year enters `additions/` or `hostnames/` only on retained evidence of that
exact hostname's web presence in that year, in one of the rule's four forms: an exact-host Internet
Archive CDX capture that answered 2xx or 3xx, with the captured URL and the target-year timestamp
retained; a dated webpage snapshot; a dated web link-graph record that identifies the hostname; or
a trusted custodian's documented per-host, per-year non-error web-capture extract. Evidence for a
parent or another variant does not carry, in either direction between a bare name and its `www.`
form, and an earlier appearance never implies a later year.

DNS observations, registry, RDAP and WHOIS registration events, error captures (4xx and 5xx), mail
and Usenet delivery headers and textual mentions are discovery evidence. They ship in the candidate
collections with their provenance and are promoted only when paired with exact-host, target-year
website evidence.
