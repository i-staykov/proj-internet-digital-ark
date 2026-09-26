# Internet Digital Ark: round 10

Evidence-backed annual domain lists for 1996-2001. **The annual files are a website-evidence
product** under the evidence rule (section XIII of your specification of 17 September, Mandatory
Evidence Classification and Hostname Integrity Gate): a line qualifies only on exact-host,
year-specific web evidence, and a name known by any other route ships as a candidate instead. The
standard is at the end.

**The counts are in `report.md` and printed by `bash verify.sh`, not here.**

Before opening anything:

- **Additions are counted against the release in `baseline/`; `baseline/README.txt` names it.** A
  figure against any earlier release is not comparable.
- **`additions/` and `hostnames/` are the deliverable and `candidates.txt` is separate.** The
  first holds registrable domains, the second valid hostnames beneath them, disjoint per year and
  each backed by its own evidence manifest. A name in `candidates.txt` has been seen but has not
  earned a year, and is never mixed into the annual lists.
- **`isc_survey_hostnames/` (the Internet Systems Consortium Domain Survey) and
  `server_header_hostnames/` are candidate collections**, claimed with `candidates.txt` in
  `candidate_additions.txt` and priced separately at the same rate. Nothing in them enters an
  annual figure.

## What is in here

| Path | Contents |
|---|---|
| `report.docx`, `report.md` | The report: methods, results, per-source yield, limitations |
| `masters/<year>.txt` | **Secondary registrable roll-up**: the reference baseline normalized to registered domains, plus registrable additions. `audit/year_growth.csv` reconciles this roll-up. It is not the full hostname result: merge both `additions/` and `hostnames/` into the reference annual files without collapsing hostnames |
| `additions/<year>.txt` | **Additions only**, against the reference baseline |
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
| `candidate_additions.txt` | **The candidate-track claim, one pool**: every candidate collection we hold, registrable domains, ISC survey hostnames and server-header hostnames together, minus every name in your `candidate_pool.txt` or in any of your six annual files. Provenance per name is in `provenance/`, `isc_survey_hostnames/isc_survey_provenance.csv` and `server_header_hostnames/header_candidates_provenance.csv`, not in this list |
| `candidate_additions_summary.json` | That pool's measured size and equivalent-English, split by counting unit, tied to the reference release |
| `candidates_unparsed.txt` | **The separately labelled unparsed file your specification asks for**, one row per malformed-but-recoverable value with the reason the parser refused it: `not_rfc1123` (underscores and over-long labels, which the era really had), `no_public_suffix`, `reverse_dns`. Read from the capture journals on 4 September; in no figure |
| `baseline/<release>/` | **The reference the additions are counted against**, including the six annual files and `candidate_pool.txt` for exact-name ISC reconciliation. See `baseline/README.txt` |
| `provenance/` | The evidence graph as Parquet, plus `trace.py` and `LOAD.sql`. This is what makes the result checkable offline |
| `audit/` | Normalization and salvage audits, the per-source contribution table, the source-saturation ledger, and `year_growth.csv`, which reconciles `masters/` against `baseline/` plus `additions/` exactly |
| `audit/source_saturation_ledger.csv` | One row per source family evaluated, generated from `sources.md` and `sources-closed.md` by column header, never hand-maintained. **Thirteen columns**, one per field of the schema you asked for (`coverage_period`, `retrieval_method`, `baseline_overlap`, `effort` and `source_link` among them). `n/a` means the source entry does not say; an empty cell means that page has no such column |
| `journals/` | The raw response of every archive and page query, plus the extraction journals: the offline inputs of the full replay (step 3 under "Checking the result"). **Twelve journal sets are excluded on size** (about 39 GB against under 1 GB for the rest); `journals/README.txt` names them, every assignment they back remains checkable through `provenance/`, and they are available on request |
| `logs/` | Execution logs from the runs that produced this |
| `seeds/` | The auxiliary hostname and URL seed pool, and the page lists used for expansion |
| `source/` | The code that produced everything here, plus the commit it was built from; `fleet.tar.gz` is the code of the unattended research agents (workflows, prompts, policy), at the commit named in `FLEET_COMMIT.txt` |
| `sources.md` | One row per source not closed: what dates one item and **a link to its download address**. Each ingest spec is on `docs/registers/approved-sources-list.md` inside `source/` |
| `sources-closed.md` | The other half of the source list: one row per family closed on a measurement, with the figure and the reason |
| `findings.md` | The round's research findings in full, with the measurement behind each. The report cites them rather than carrying them |
| `experience-summary.md` | What worked, what did not, measured yields, limits, lessons, reusable techniques, and where to go next. `sources.md` and `sources-closed.md` beside it are the full source list this distils |
| `metric-explained.md` | The equivalent-English metric. The weights, the model version, the formula, how invalid and unmatched records are treated, and the four totals, each with the command that regenerates it |
| `audit/merge_stats_ark_*.csv` | The merge against the current baseline in your own column names, so your audit and this one can be diffed directly |
| `audit/merge_audit_ark_*.json` | The same figures plus every reconciliation check that was run, and whether it passed |
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

- **Generated `.txt` name lists**: one name per line, lowercase ASCII, C-locale sorted, newline
  terminated, no header, no blank lines. Masters and registrable additions use the Public Suffix
  List boundary. Hostname additions and ISC candidates retain the exact hostname without collapsing
  it to its parent or removing `www.`.
- **Every `.csv`**: RFC 4180, comma separated, UTF-8, one header row.
- **`journals/*.jsonl.gz`**: gzipped JSON Lines, one object per query made.
- **`provenance/*.parquet`**: Parquet with ZSTD, readable by any engine. `LOAD.sql` recreates the
  tables in DuckDB; `trace.py` answers the common question without SQL.
- **An `audit/*.csv` with a header and no rows** means the audited condition did not occur.

## Checking the result

### 1. Verify what is here

The `.sha256` sidecar is delivered **beside** the `.tar.gz`, not inside it:

```
shasum -a 256 -c [ARCHIVE].tar.gz.sha256
```

Then from inside this folder:

```
bash verify.sh
```

It needs `shasum`, `python3` and `uv` for the ISC file audit, prints a verdict per check, and exits
non-zero on failure. **Thirteen labelled verdicts**: checksums; the six annual and six hostname
files with their counts, their disjointness and an evidence row per line; the ISC collection
disjoint from your candidate pool and annual files, with its equivalent-English total reproduced;
the header collection complete and inside the claim; every provenance assignment resolving to an
evidence row shipped beside it; and the four deliverables: the code snapshot carries its lockfile,
the experience summary covers every topic asked for, every merge reconciliation check passed and
agrees with the shipped files, and **your own calculator, run from inside this archive, reproduces
the audit's baseline figure**. SKIP means the checked thing is not in the archive. The last check
needs a writable extraction, because it runs the calculator into `audit/` and cleans up after itself.

To look up why a single domain is in a given year, no database needed, only
[`uv`](https://docs.astral.sh/uv/):

```
cd provenance
uv run --with duckdb --no-project python trace.py                    # what is in the export
uv run --with duckdb --no-project python trace.py bbc.co.uk 1999     # why this domain, this year
```

One line per observation: which source saw the domain, what kind of evidence, and the artifact or
capture timestamp, with a link where one exists.

### 2. Rebuild the result from the evidence

No source data and no network: the export holds every observation this project made and every
assignment resting on one, but not your own rows (one evidence row per pair your release already
carries was 3 GB of a 5 GB archive and repeated your own file). Two consequences. The rebuilt
`masters/` are our own web-evidenced records, your rows not among them. And the registrable
additions and the candidate lists come back as supersets, because the store also excludes a
registrable domain your release holds only as hostnames beneath it, and the shipped provenance does
not record that; every shipped line is among them, which the second block below checks.

```
tar -xzf source/source.tar.gz -C source/ && cd source
uv sync
uv run ark rebuild ../provenance     # annual files, candidates, manifest
uv run ark check                     # the integrity invariants
```

Byte-identical:

```
for y in 1996 1997 1998 1999 2000 2001; do
    cmp output/netnew/${y}_hostnames.txt ../hostnames/${y}_hostnames.txt
    cmp output/netnew/$y-ISC.txt        ../isc_survey_hostnames/$y-ISC.txt
done
cmp output/netnew/hostnames_evidence_manifest.csv ../hostnames/hostnames_evidence_manifest.csv
cmp output/netnew/isc_candidates.txt ../isc_survey_hostnames/isc_candidates.txt
cmp output/netnew/isc_survey_provenance.csv ../isc_survey_hostnames/isc_survey_provenance.csv
cmp output/netnew/isc_candidates_summary.json ../isc_survey_hostnames/isc_candidates_summary.json
for f in header_candidates.txt header_candidates_provenance.csv header_candidates_summary.json header_candidates_exclusions.csv; do
    cmp output/netnew/$f ../server_header_hostnames/$f
done
```

Supersets, every shipped line present (each count is 0):

```
for y in 1996 1997 1998 1999 2000 2001; do
    comm -23 <(sort ../additions/$y.txt) <(sort output/netnew/$y.txt) | wc -l
done
comm -23 <(sort ../candidates.txt) <(sort output/candidate_unverified.txt) | wc -l
comm -23 <(sort ../candidate_additions.txt) <(sort output/netnew/candidate_additions.txt) | wc -l
```

This proves the shipped lists follow from the shipped evidence. It does not re-derive the evidence
from the original sources, which is tier 3.

### 3. Rebuild from the original sources (not run this round)

**`README.md` inside `source/` documents the route step by step**. Each source's row in `sources.md`
links its download address, and `docs/registers/approved-sources-list.md` in `source/` carries its
ingest spec.

```
tar -xzf source/source.tar.gz -C source/ && cd source   # if not already done in step 2
uv sync
mkdir -p data/raw && cp -R ../journals/. data/raw/       # the replay inputs, tree preserved
just reproduce                  # the command runner: https://just.systems
```

Without `journals/` in `data/raw/` the replay runs clean and ingests nothing. The excluded sets
replay nothing until restored: the RDAP logs on request, the rest by re-downloading from the
link in each one's `sources.md` row; every assignment they back is checked by step 2. The replay
also needs the first baseline release in `legacy-data/`, which this archive does not carry.

About 50 GB of downloads, of which the 47 GB Arquivo.pt (Portuguese web archive) capture index is
most; sizes measured once, on the first delivery, indicative.

**What the replay cannot re-derive.** Three sources cannot be re-fetched: `domain_creation_bulk` (a
Kaggle dataset that needs an account and may not be redistributed), `dartmouth_nber_captures` (an
archive.org item that stopped serving the day after it was downloaded) and `rdap_snapshot` (journals
held back on size, sent on request). Each one's `sources.md` row links the address it came from and
the approved page names its ingest spec; `audit/dartmouth_nber_captures_audit.csv` and
`audit/domain_creation_bulk_audit.csv` record what the first two contributed. **Step 2 reproduces
all of it, and that is the check to run**: the provenance export ships the evidence row behind every
assignment, which is why the `evidence wall intact` verdict of `verify.sh` tests that every
assignment resolves to an evidence row in this archive.

Two live sources need not match a later download: the `.fr` open-data file (June 2026 edition used
here) and the Internet Scout feed. The journals and the provenance export shipped here do not move.

## Evidence standard

**The evidence rule: the annual master is a website-evidence product.** A hostname-year enters
`masters/`, `additions/` or `hostnames/` only on retained evidence of that exact hostname's web
presence in that year, in one of the rule's four forms:

- an exact-host Internet Archive CDX capture, with the captured URL or hostname and the target-year
  timestamp retained;
- a dated webpage snapshot;
- a dated web link-graph record that identifies the target hostname;
- a trusted custodian's documented per-host/year non-error web-capture extract.

Evidence for a parent domain or for another hostname variant does not carry, in either direction
between a bare name and its `www.` form. An earlier appearance never implies a later year.

DNS observations, registry, RDAP and WHOIS registration events, mail and Usenet delivery headers,
and textual mentions are discovery evidence rather than website evidence. They ship in the candidate
collections with their provenance and a verification route, and are promoted only when paired with
exact-host, target-year website evidence.
