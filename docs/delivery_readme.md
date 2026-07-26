# Internet Digital Ark: 1996-2001 annual domain lists

Evidence-backed annual domain lists for 1996-2001, built on top of the supplied ~8.2M-line
baseline. Every line in an annual file traces to a specific dated observation.

**463,566 net-new registered domains over 1,322,365 net-new (domain, year) pairs**, plus 3,595,769
hostname and URL download seeds. Method and results: `report.docx`.

## What is in here

| Path | Contents |
|---|---|
| `report.docx`, `report.md` | The report: counting unit, normalization, validity and salvage rules, dropped-domain statistics, source contributions, annual evidence logic, deduplication, limitations, results |
| `masters/1996.txt` … `2001.txt` | **Final annual lists**: baseline plus additions, deduplicated within each year, one registered domain per line |
| `additions/1996.txt` … `2001.txt` | **Additions only**: what this work added on top of the baseline |
| `additions/evidence_manifest.csv` | One row per added (domain, year) with the evidence behind it |
| `candidates.txt` | Domains lacking year-specific evidence. Never mixed into the annual lists |
| `dropped_domains.txt` | Baseline lines excluded by the pipeline, grouped by reason |
| `provenance/` | The full evidence graph as Parquet, plus `LOAD.sql`. This is what makes the result checkable offline |
| `audit/` | Normalization and salvage audit files, and the per-source contribution tables |
| `logs/` | Execution logs from the runs that produced this |
| `seeds/` | The auxiliary hostname and URL seed pool, and the page lists used for expansion |
| `journals/` | The raw responses of every archive, registry and page query made |
| `source/` | The code and configuration that produced everything here, plus the commit it was built from |
| `sources.md` | Per-source detail: what each source is, how it was obtained, what fixes its dates, what it yielded |
| `SHA256SUMS` | Checksum for every file in this archive |

`source/` contains the code's own README, which documents the pipeline command by command. This
file describes the archive.

## Checking the result

Three levels, in increasing cost. **The first two need no downloads and no network.**

**1. Verify what is here** (minutes). The annual lists, the manifest and the provenance graph are
self-contained, so any line can be traced to its evidence:

```
cd provenance
duckdb -init LOAD.sql        # or: python -c "import duckdb; ..." using the same SQL
```

`LOAD.sql` rebuilds a queryable store from the Parquet files and ends with a worked example that
traces one domain-year to the observations supporting it. Cross-checks worth running: the six
`additions/` files should total 1,322,365 lines, and every one of those pairs should appear in
`additions/evidence_manifest.csv`.

**2. Re-derive the result from the shipped inputs** (about 10 minutes). Unpack the code, restore the
journals, and rebuild. The collectors are not re-run: every archive and registry query was recorded
with its raw response, so the rebuild replays stored bytes instead of asking services that answer
differently today.

```
tar -xzf source/source.tar.gz -C source/ && cd source
uv sync
just reproduce
just check          # lint, tests, then the nine data invariants
```

The code README lists the same run as numbered steps with the output each should print, and says
where to put the journals and the bulk source files.

**3. Rebuild from the original sources** (hours). Only needed to re-derive the bulk sources
themselves. Their download routes are in `sources.md`; they total about 51 GB, of which a single
47 GB capture index is the bulk. **Skipping that one file costs exactly 17,696 pairs over 7,001
domains and leaves about 4 GB to download**, which reproduces 98.7% of the result.

## Evidence standard

A domain is in `masters/<year>.txt` only with item-level evidence for that year: a web-archive
capture, a dated survey or directory file, a host-link-graph row, a registry record, or the
baseline's own prior evidence. An earlier appearance never implies a later year.

Registry records are read two ways, deliberately. An RDAP response carries no registration history,
so it attests its creation year only. The `.fr` registry file attests every in-window year between
creation and deletion, because that registry documents its creation date as "the last creation date
of the domain name", which places it at or after any earlier deletion. The report gives the citation
and the size of the exposure if that reading is rejected.

Data that only suggests a domain existed, such as being linked to from another site, never assigns a
year. It goes to `candidates.txt` until it earns its own evidence.
