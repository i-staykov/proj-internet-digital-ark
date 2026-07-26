# Internet Digital Ark: 1996-2001 annual domain lists

Evidence-backed annual domain lists for 1996-2001, built on top of the supplied ~8.2M-line
baseline. Every line in an annual file traces to a specific dated observation.

**1,322,365 net-new (domain, year) pairs over 463,566 net-new registered domains**, plus 3,595,769
hostname and URL download seeds. Method and results: `report.docx`.

## What is in here

| Path | Contents |
|---|---|
| `report.docx`, `report.md` | The report: counting unit, normalization, validity and salvage rules, dropped-domain statistics, source contributions, annual evidence logic, deduplication, limitations, results |
| `masters/1996.txt` … `2001.txt` | **Final annual lists**: baseline plus additions, deduplicated within each year, one registered domain per line |
| `additions/1996.txt` … `2001.txt` | **Additions only**: what this work added on top of the baseline |
| `additions/evidence_manifest.csv` | One row per added (domain, year) with the evidence behind it |
| `candidates.txt` | Domains lacking year-specific evidence. Never mixed into the annual lists |
| `baseline/` | The supplied 1996-2001 files this work was built on, unmodified, so no baseline has to be sourced separately |
| `dropped_domains.txt` | Baseline lines excluded by the pipeline, grouped by reason |
| `provenance/` | The full evidence graph as Parquet, plus `trace.py` and `LOAD.sql` for querying it. This is what makes the result checkable offline |
| `audit/` | Normalization and salvage audit files, and the per-source contribution tables |
| `logs/` | Execution logs from the runs that produced this |
| `seeds/` | The auxiliary hostname and URL seed pool, and the page lists used for expansion |
| `journals/` | The raw responses of every archive, registry and page query made |
| `source/` | The code and configuration that produced everything here, plus the commit it was built from |
| `sources.md` | Per-source detail: what each source is, **the commands to download it**, what fixes its dates, why it carries the evidence type it does, and what was rejected |
| `SHA256SUMS` | Checksum for every file in this archive |
| `verify.sh` | Runs every check below in one command |

`source/source.tar.gz` holds the code's own README, which documents the pipeline command by command.
This file describes the archive.

## Checking the result

Three levels, in increasing cost. **The first two need no downloads and no network.**

### 1. Verify what is here (one command, about 10 seconds)

Before unpacking, from the folder that holds the archive:

```
shasum -a 256 -c internet-digital-ark-1996-2001.tar.gz.sha256
```

Then, from inside this folder:

```
bash verify.sh
```

That checks every file against `SHA256SUMS`, prints the pair count of the six annual addition
files, and confirms **every one of those pairs appears in
`additions/evidence_manifest.csv`**, so nothing is asserted without a recorded observation. It
needs only `shasum` and `python3`, and prints a verdict per check.

To look up why any single domain is in any given year, use the provenance export. It needs no
database installed, only [`uv`](https://docs.astral.sh/uv/):

```
cd provenance
uv run --with duckdb --no-project python trace.py                    # what is in the export
uv run --with duckdb --no-project python trace.py bbc.co.uk 1999     # why this domain, this year
```

The second command prints one line per observation: which source saw the domain, what kind of
evidence it is, and the artifact or capture timestamp it came from, with a link where one exists.
Any domain from `masters/` or `additions/` works. If you already run DuckDB, `LOAD.sql` in the same
folder loads the five Parquet tables instead; run it from inside `provenance/`, since its paths are
relative.

### 2. Rebuild the result from the evidence (about 1 minute)

Regenerate every result file from `provenance/` and put the rebuilt store through the same
integrity gate. This needs **no source data and no network**: the export holds every observation
and every assignment, so the exporter can run over it again.

```
tar -xzf source/source.tar.gz -C source/ && cd source
uv sync
uv run ark rebuild ../provenance     # regenerates the annual files, masters, candidates, manifest
uv run ark check                     # the nine integrity invariants, against the rebuilt store
```

Then compare what it wrote against what shipped; they are byte-identical:

```
for y in 1996 1997 1998 1999 2000 2001; do cmp output/netnew/$y.txt ../additions/$y.txt; done
```

This proves the shipped lists follow from the shipped evidence. It does not re-derive the evidence
itself from the original sources, which is tier 3.

### 3. Rebuild from the original sources (hours)

Only needed to re-derive the evidence itself. The supplied baseline ships here in `baseline/`; copy
it to `legacy-data/` inside the unpacked source. The bulk sources are the only thing to fetch, and
**`README.md` inside `source/` documents the route step by step**, with each source's download
address in `sources.md`.

```
cp -R ../baseline legacy-data       # from inside the unpacked source/
just reproduce
```

The bulk sources total about 50 GB, of which a single 47 GB capture index is most of it.
**Skipping the Arquivo indexes costs 17,696 pairs over 7,001 domains and leaves about 3 GB**,
reproducing 98.7% of the result.

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
