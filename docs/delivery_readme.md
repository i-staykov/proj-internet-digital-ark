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
- **`additions/` and `hostnames/` are the deliverable and `candidates.txt` is separate.** The
  first holds registrable domains, the second valid hostnames beneath them (the unit the
  reviewer accepted on 2026-09-01), disjoint per year and each backed by its own evidence
  manifest. A name in `candidates.txt` has been seen but has not earned a year, and is never
  mixed into the annual lists.

## What is in here

| Path | Contents |
|---|---|
| `report.docx`, `report.md` | The report: methods, results, per-source yield, limitations |
| `masters/<year>.txt` | **Final annual lists**: the reference baseline normalized to registered domains, plus the additions. Not a line-for-line sum of `baseline/` and `additions/`, because normalization collapses subdomains; `audit/year_growth.csv` reconciles it exactly |
| `additions/<year>.txt` | **Additions only**, against the reference baseline |
| `additions/evidence_manifest.csv` | One row per added (domain, year) with the evidence behind it |
| `hostnames/<year>_hostnames.txt` | **Hostname additions**, the second output unit: valid hostnames beneath held registrables, disjoint from `additions/` |
| `hostnames/hostnames_evidence_manifest.csv` | One row per added (hostname, year) with its parent, source, method and the capture behind it |
| `candidates.txt` | Domains lacking year-specific evidence. Never mixed into the annual lists |
| `baseline/original/` | The first supplied baseline. `ark ingest-legacy` reads these, so tier 3 starts here |
| `baseline/<release>/` | **The reference the additions are counted against**, the reviewer's own reissued corpus shipped back so the archive is checkable on its own. See `baseline/README.txt` |
| `dropped_domains.txt` | Baseline lines excluded by the pipeline, grouped by reason |
| `provenance/` | The evidence graph as Parquet, plus `trace.py` and `LOAD.sql`. This is what makes the result checkable offline |
| `audit/` | Normalization and salvage audits, the per-source contribution table, the source-saturation ledger, and `year_growth.csv`, which reconciles `masters/` against `baseline/` plus `additions/` exactly |
| `journals/` | The raw response of every archive and page query, plus the extraction journals. This is what tier 3 replays, so every network stage reproduces offline. **The directory tree is the one the pipeline expects**, so `cp -R journals/. data/raw/` restores it and the ingest commands find their inputs. **Eight journal sets are excluded on size** (about 19 GB against under 2 GB for the rest); `journals/README.txt` names them, every assignment they back remains checkable through `provenance/`, and they are available on request |
| `logs/` | Execution logs from the runs that produced this |
| `seeds/` | The auxiliary hostname and URL seed pool, and the page lists used for expansion |
| `source/` | The code that produced everything here, plus the commit it was built from; `fleet.tar.gz` is the unattended research loop (workflows, prompts, policy, hypothesis register) at `FLEET_COMMIT.txt` |
| `sources.md` | Per-source detail, including **the commands to download each**, and one row per source evaluated |
| `sources-closed.md` | The other half of that register: one row per family closed on a measurement, with the figure and the reason |
| `experience-summary.md` | **D2**: what worked, what did not, measured yields, limits, lessons, reusable techniques, and where to go next. `sources.md` and `sources-closed.md` beside it are the full register this distils |
| `metric-explained.md` | **D4**: the equivalent-English metric. The weights, the model version, the formula, how invalid and unmatched records are treated, and the four totals, each with the command that regenerates it |
| `audit/merge_stats_ark_*.csv` | **D3**: the merge against the current baseline in the reviewer's own column names, so his audit and this one can be diffed directly |
| `audit/merge_audit_ark_*.json` | **D3**: the same figures plus every reconciliation check that was run, and whether it passed |
| `equivalent_english_domain_calculator/` | **D4**: the reviewer's own scorer, vendored unmodified with its fixed model, so every figure here can be re-derived without fetching anything |
| `SHA256SUMS`, `verify.sh` | Checksum for every file, and the checker |


## The four deliverables he asked for on 2026-08-17

Named here in his order, because the table above is sorted by path.

| | he asked for | where it is |
|---|---|---|
| **D1** | the complete runnable code, scripts, configurations, dependencies and execution instructions | `source/source.tar.gz`, which is the repository at the commit named in `source/COMMIT.txt`, including `pyproject.toml` and `uv.lock`. Execution instructions are its `README.md` and the three tiers below |
| **D2** | a concise experience summary | `experience-summary.md`, with `sources.md` and `sources-closed.md` as the full register behind it |
| **D3** | the code and explanation that normalises, merges and deduplicates against the latest baseline, with overlap counts, the accepted increment and reconciliation checks | `source/scripts/round/merge_against_baseline.py`, its output in `audit/merge_stats_ark_*.csv` and `audit/merge_audit_ark_*.json`, explained in section 5 of `metric-explained.md` |
| **D4** | the runnable equivalent-English calculation and its explanation | `equivalent_english_domain_calculator/` and `metric-explained.md` |

`verify.sh` checks all four: check 5 that the code snapshot carries its lockfile, 6 that the summary
covers every topic he listed, 7 that every reconciliation check in the merge audit passed, and 8 that
his own calculator, run here, reproduces the audit's baseline figure.

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
shasum -a 256 -c [ARCHIVE].tar.gz.sha256
```

Then from inside this folder:

```
bash verify.sh
```

It needs only `shasum` and `python3`, prints a verdict per check, and exits non-zero on failure.
**Eleven checks.** The first six are the result and the evidence behind it: every file against
`SHA256SUMS`, the annual addition files and their counts, every added pair present in
`additions/evidence_manifest.csv`, the hostname files and their counts (disjoint from
`additions/`), every hostname traced to a capture, and every assignment in the Parquet provenance
resolving to an evidence row shipped beside it. Checks 7 to 11 are the four artifacts of the
section above, D1 to D4: that the code snapshot carries its dependency manifest and lockfile, that
the experience summary covers every topic asked for, that every reconciliation check in the merge
audit passed and that the audit agrees with the shipped files on the record count, and that **the
reviewer's own calculator, run from inside this archive, reproduces the audit's baseline figure**.

It prints SKIP where the thing a check examines is not in the archive, and says which of the eleven
failed rather than only that something did. The last check needs a writable extraction, because it runs the
calculator into `audit/` and cleans up after itself.

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
    cmp output/netnew/${y}_hostnames.txt ../hostnames/${y}_hostnames.txt
    cmp data/exports/$y.txt             ../masters/$y.txt
done
cmp output/netnew/evidence_manifest.csv ../additions/evidence_manifest.csv
cmp output/netnew/hostnames_evidence_manifest.csv ../hostnames/hostnames_evidence_manifest.csv
cmp output/candidate_unverified.txt      ../candidates.txt
```

The archive renames things, so here is the map:

| in the rebuild | in this archive |
|---|---|
| `output/netnew/<year>.txt` | `additions/<year>.txt` |
| `output/netnew/evidence_manifest.csv` | `additions/evidence_manifest.csv` |
| `output/netnew/<year>_hostnames.txt` | `hostnames/<year>_hostnames.txt` |
| `output/netnew/hostnames_evidence_manifest.csv` | `hostnames/hostnames_evidence_manifest.csv` |
| `output/candidate_unverified.txt` | `candidates.txt` |
| `data/exports/<year>.txt` | `masters/<year>.txt` |
| `output/provenance/` | `provenance/` |

This proves the shipped lists follow from the shipped evidence. It does not re-derive the evidence
from the original sources, which is tier 3.

### 3. Rebuild from the original sources (a download, then about 20 minutes)

**`README.md` inside `source/` documents the route step by step**, with each source's download address
in `sources.md`.

```
tar -xzf source/source.tar.gz -C source/ && cd source   # if not already done in step 2
uv sync
cp -R ../baseline/original/. legacy-data/                # the first supplied baseline
mkdir -p data/raw && cp -R ../journals/. data/raw/       # the replay inputs, tree preserved
just reproduce
```

The `journals/` copy is what makes the network stages reproduce offline: every ingest command
addresses its inputs by nested path, and the archive ships that tree rather than a flat directory so
this one command restores it. Without it `just journals` runs clean and ingests nothing, which is how
it behaved before 2026-08-18. **The five excluded journal sets will replay nothing** until they are restored: the RDAP
logs on request, the other four by re-deriving them from the public sources `sources.md` links.
Every assignment they back is checkable by tier 2, which is the route below.

About 50 GB, of which a single 47 GB capture index is most. **Skipping the Arquivo indexes leaves
about 3 GB.** Those per-source cost figures were measured on the phase-1 archive and have not been
re-measured since, so treat them as indicative.

**What tier 3 cannot re-derive, stated plainly, because the figure used to be wrong by four orders of
magnitude.** This paragraph said "the gap is two sources with no journal to replay, whose 840 domains
return to the candidate pool". That was true of phase 1 and has not been true since phase 5. Measured
on 2026-08-27:

| | assignments | share |
|---|--:|--:|
| carrying this project's own evidence | 7,254,144 | |
| **not re-derivable by tier 3** | **3,139,263** | **43.3%** |

Three sources account for all of it. `domain_creation_bulk`, 2,165,506 assignments, is a Kaggle
dataset that needs an account and may not be redistributed. `dartmouth_nber_captures`, 227,273, came
from an archive.org item that **stopped serving the day after it was downloaded**, so it cannot be
re-fetched by us or by anyone. `rdap_snapshot`, 746,484, is the one whose journals exist and are held
back on size, as the layout table above says; ask and they will be sent. `sources.md` gives the
acquisition route for all three, and `audit/dartmouth_nber_captures_audit.csv` and
`audit/domain_creation_bulk_audit.csv` record what the first two contributed.

**Tier 2 reproduces all of it, and that is the check to run.** The provenance export ships the
evidence row behind every single assignment, including those 3,139,263, which is why `verify.sh`
check 4 tests that every assignment resolves to an evidence row **in this archive**. Tier 3 proves
the evidence follows from the source data; tier 2 proves the result follows from the evidence. Only
the first is limited by what a third party is willing to keep serving.

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
