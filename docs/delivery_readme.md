# Internet Digital Ark: 1996-2001 annual domain lists

Evidence-backed annual domain lists for 1996-2001. Every line in an annual file traces to a specific
dated observation: a capture the Internet Archive holds, a registry record, or an address printed in
a dated artifact.

**The counts live in `report.docx` and in `verify.sh`, not here.** Quoting figures in two places is how
they come to disagree. `bash verify.sh` prints the current totals from the shipped files in about ten
seconds.

Two things to know before opening anything:

- **The reference baseline is the one in `baseline/`, named for the reviewer release it came from,
  and `baseline/README.txt` says which.** Additions are counted against it, so a figure quoted
  against any earlier release is not comparable.
- **`additions/` is the deliverable and `candidates.txt` is separate.** A name in `candidates.txt`
  has been seen but has not earned a year, and is never mixed into the annual lists.

## What is in here

| Path | Contents |
|---|---|
| `report.docx`, `report.md` | The report: methods, results, per-source yield, limitations |
| `masters/<year>.txt` | **Final annual lists**: the reference baseline normalized to registered domains, plus the additions. Not a line-for-line sum of `baseline/` and `additions/`, because normalization collapses subdomains; `audit/year_growth.csv` reconciles it exactly |
| `additions/<year>.txt` | **Additions only**, against the reference baseline |
| `additions/evidence_manifest.csv` | One row per added (domain, year) with the evidence behind it |
| `candidates.txt` | Domains lacking year-specific evidence. Never mixed into the annual lists |
| `baseline/original/` | The first supplied baseline. `ark ingest-legacy` reads these, so tier 3 starts here |
| `baseline/<release>/` | **The reference the additions are counted against**, the reviewer's own reissued corpus shipped back so the archive is checkable on its own. See `baseline/README.txt` |
| `dropped_domains.txt` | Baseline lines excluded by the pipeline, grouped by reason |
| `provenance/` | The evidence graph as Parquet, plus `trace.py` and `LOAD.sql`. This is what makes the result checkable offline |
| `audit/` | Normalization and salvage audits, the per-source contribution table, and `year_growth.csv`, which reconciles `masters/` against `baseline/` plus `additions/` exactly |
| `journals/` | The raw response of every archive, registry and page query ever made, plus the extraction journals. This is what tier 3 replays, so every network stage reproduces offline |
| `logs/` | Execution logs from the runs that produced this |
| `seeds/` | The auxiliary hostname and URL seed pool, and the page lists used for expansion |
| `source/` | The code that produced everything here, plus the commit it was built from |
| `sources.md` | Per-source detail, including **the commands to download each** and what was rejected |
| `SHA256SUMS`, `verify.sh` | Checksum for every file, and the checker |


## File formats

- **Every `.txt` list**: one registered domain per line, lowercase ASCII, C-locale sorted, newline
  terminated, no header, no blank lines. A "registered domain" is the name at the registrable boundary
  under the Public Suffix List, so `www.example.co.uk` appears as `example.co.uk`. This is the counting
  unit throughout, and it is why these totals differ from a raw line count of the same source data.
- **Every `.csv`**: RFC 4180, comma separated, UTF-8, one header row.
- **`journals/*.jsonl.gz`**: gzipped JSON Lines, one object per query made.
- **`provenance/*.parquet`**: Parquet with ZSTD, readable by any engine. `LOAD.sql` recreates the
  tables in DuckDB; `trace.py` answers the common question without SQL.
- **Empty `audit/*.csv` files are meaningful, not broken.** A header and no rows records that the
  audited condition did not occur. A missing file would be ambiguous; an empty one is not.

## Checking the result

### 1. Verify what is here (about 10 seconds)

The `.sha256` sidecar is delivered **beside** the `.tar.gz`, not inside it:

```
shasum -a 256 -c internet-digital-ark-1996-2001.tar.gz.sha256
```

Then from inside this folder:

```
bash verify.sh
```

It needs only `shasum` and `python3`, prints a verdict per check, and exits non-zero on failure. It
checks every file against `SHA256SUMS`, counts the annual addition files, and confirms every pair
appears in `additions/evidence_manifest.csv`. It prints WARN rather than PASS where a check would be
vacuous, and SKIP where the thing it checks is not in the archive.

To look up why a single domain is in a given year, no database needed, only
[`uv`](https://docs.astral.sh/uv/):

```
cd provenance
uv run --with duckdb --no-project python trace.py                    # what is in the export
uv run --with duckdb --no-project python trace.py bbc.co.uk 1999     # why this domain, this year
```

One line per observation: which source saw the domain, what kind of evidence, and the artifact or
capture timestamp, with a link where one exists.

### 2. Rebuild the result from the evidence (about 1 minute)

No source data and no network: the export holds every observation and every assignment.

```
tar -xzf source/source.tar.gz -C source/ && cd source
uv sync
uv run ark rebuild ../provenance     # annual files, masters, candidates, manifest
uv run ark check                     # the integrity invariants
```

Everything comes back byte-identical:

```
for y in 1996 1997 1998 1999 2000 2001; do
    cmp output/netnew/$y.txt            ../additions/$y.txt
    cmp data/exports/$y.txt             ../masters/$y.txt
done
cmp output/netnew/evidence_manifest.csv ../additions/evidence_manifest.csv
cmp output/candidate_unverified.txt      ../candidates.txt
```

The archive renames things, so here is the map:

| in the rebuild | in this archive |
|---|---|
| `output/netnew/<year>.txt` | `additions/<year>.txt` |
| `output/netnew/evidence_manifest.csv` | `additions/evidence_manifest.csv` |
| `output/candidate_unverified.txt` | `candidates.txt` |
| `data/exports/<year>.txt` | `masters/<year>.txt` |
| `output/provenance/` | `provenance/` |

This proves the shipped lists follow from the shipped evidence. It does not re-derive the evidence
from the original sources, which is tier 3.

### 3. Rebuild from the original sources (a download, then about 20 minutes)

**`README.md` inside `source/` documents the route step by step**, with each source's download address
in `sources.md`.

```
cp -R ../baseline/original/. legacy-data/       # from inside the unpacked source/
just reproduce
```

About 50 GB, of which a single 47 GB capture index is most. **Skipping the Arquivo indexes leaves
about 3 GB** and reproduced 98.7% of the phase-1 archive. Measured on that archive this returned 99.77%
of its pairs with all invariants passing; those per-source cost figures have not been re-measured for
this round, so treat them as indicative. The gap is two sources with no journal to replay, whose 840
domains return to the candidate pool. Tier 2 above is the byte-for-byte check.

Two sources are live rather than hash-pinned, so a later download need not match: the `.fr` file is
republished monthly (this used the June 2026 edition) and the Internet Scout feed keeps growing. The
journals and the provenance export shipped here do not move.

## Evidence standard

A domain is in `masters/<year>.txt` only with item-level evidence for that year: a web-archive capture,
a dated survey or directory file, a host-link-graph row, a registry record, or the baseline's own prior
evidence. An earlier appearance never implies a later year.

Data that only suggests a domain existed, such as being linked to from another site, never assigns a
year. It goes to `candidates.txt` until it earns its own evidence.

The report gives the standard in full, including how registry dates are read and which evidence
types may back an annual entry.
