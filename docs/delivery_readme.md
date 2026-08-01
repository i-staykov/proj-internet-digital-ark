# Internet Digital Ark: 1996-2001 annual domain lists

Evidence-backed annual domain lists for 1996-2001. Every line in an annual file traces to a specific
dated observation, and from this round every line in the English-verified set traces to archived page
text that was read and classified.

**The counts live in `report.docx` and in `verify.sh`, not here.** This file describes the archive's
structure; quoting figures in two places is how they come to disagree, and this file has been wrong
about them before. `bash verify.sh` prints the current totals from the shipped files themselves in
about ten seconds.

Two things a reader should know before opening anything:

- **The reference baseline for this round is `merged260730`.** Additions are counted against it, so a
  figure quoted against any earlier baseline is not comparable.
- **`additions_english/` and `additions_unverified/` partition `additions/`.** They are disjoint and
  sum to the whole, so they can be added together without double counting. `verify.sh` checks that
  rather than asking you to trust it.

## What is in here

| Path | Contents |
|---|---|
| `report.docx`, `report.md` | The report: counting unit, normalization, validity and salvage rules, dropped-domain statistics, source contributions, annual evidence logic, deduplication, limitations, results |
| `masters/1996.txt` … `2001.txt` | **Final annual lists**: `merged260730` normalized to registered domains, plus our additions, deduplicated within each year. Not a line-for-line sum of `baseline/` and `additions/`, because normalization collapses subdomains and `dropped_domains.txt` removes invalid lines. `audit/year_growth.csv` reconciles it exactly |
| `additions/1996.txt` … `2001.txt` | **Additions only**: what this work added on top of the baseline |
| `additions/evidence_manifest.csv` | One row per added (domain, year) with the evidence behind it |
| `additions_english/1996.txt` … `2001.txt` | **English-verified additions**: the site's archived body text for that year was read and was more than half English |
| `additions_english/1996.csv` … `2001.csv` | The same pairs with the evidence. Columns: `domain,year,english_share,samples,snapshot_urls`, the last being space-separated Wayback `id_` URLs that can be refetched directly |
| `additions_english/language_summary.csv` | Per year and total: English, other-language, undetermined and not-yet-reached counts, plus the cross-year unique-domain roll-up |
| `additions_unverified/1996.txt` … `2001.txt` | **Everything else**, disjoint from the above. The two together are exactly `additions/` |
| `additions_unverified/1996.csv` … `2001.csv` | Per row a `status` (`disqualified` or `unchecked`) and, for a rejection, its `reason`. Columns: `domain,year,status,reason,english_share,top_other,snapshot_urls` |
| `additions_unverified/disqualified.csv` | The register: every pair we judged and rejected, one row each, with the reason and the pages read |
| `candidates.txt` | Domains lacking year-specific evidence. Never mixed into the annual lists |
| `baseline/original/` | The first supplied baseline. `ark ingest-legacy` reads these, so tier 3 starts here |
| `baseline/merged260730/` | **The reference this round's additions are counted against.** See `baseline/README.txt`: scoring against `original/` instead gives a larger number than the report claims |
| `dropped_domains.txt` | Baseline lines excluded by the pipeline, grouped by reason |
| `provenance/` | The full evidence graph as Parquet, plus `trace.py` and `LOAD.sql` for querying it. This is what makes the result checkable offline |
| `audit/` | Normalization and salvage audit files, the per-source contribution table, `year_growth.csv`, and `engine_review.md`: the adversarial review of the verification engine and the ten defects it found |
| `logs/` | Execution logs from the runs that produced this |
| `seeds/` | The auxiliary hostname and URL seed pool, and the page lists used for expansion |
| `journals/` | The raw responses of every archive, registry and page query made, plus the Usenet and Tucows extraction journals and the language verdicts. `lang_superseded/` holds verdicts from earlier engine versions, retained for audit and excluded from results by engine version |
| `source/` | The code and configuration that produced everything here, plus the commit it was built from |
| `sources.md` | Per-source detail: what each source is, **the commands to download it**, what fixes its dates, why it carries the evidence type it does, and what was rejected |
| `SHA256SUMS` | Checksum for every file in this archive |
| `verify.sh` | Runs every check below in one command |

## File formats

Stated because a reader should not have to infer them from a hexdump.

- **Every `.txt` list**: one registered domain per line, lowercase ASCII, C-locale sorted, newline
  terminated, no header, no blank lines, no comments. A "registered domain" is the name at the
  registrable boundary under the Public Suffix List, so `www.example.co.uk` appears as
  `example.co.uk`. This is the counting unit throughout, and it is why our totals differ from a raw
  line count of the same source data.
- **Every `.csv`**: RFC 4180, comma separated, UTF-8, one header row, fields quoted only where
  necessary. Column names are given in the table above for the annual CSVs and in `sources.md` for
  `source_contribution.csv`.
- **`journals/*.jsonl.gz`**: gzipped JSON Lines, one JSON object per query made. These are the raw
  responses, so a stage can be replayed from bytes rather than from a service whose answers change.
- **`provenance/*.parquet`**: Parquet with ZSTD compression, readable by any engine. `LOAD.sql`
  recreates the six tables in DuckDB; `trace.py` answers the common question without SQL.
- **Empty `audit/*.csv` files are meaningful, not broken.** Several audit files are a header and no
  rows, which records that the audited condition did not occur: nothing was salvaged by that rule,
  or no anomaly of that class was found. A missing file would be ambiguous, an empty one is not.

`source/source.tar.gz` holds the code's own README, which documents the pipeline command by command.
This file describes the archive.

## Checking the result

Three levels, in increasing cost. **The first two need no downloads and no network.**

### 1. Verify what is here (one command, about 10 seconds)

Before unpacking, from the folder that holds the archive. The `.sha256` sidecar is delivered
**beside** the `.tar.gz`, not inside it, so if you only have the unpacked folder skip to `verify.sh`:

```
shasum -a 256 -c internet-digital-ark-1996-2001.tar.gz.sha256
```

Then, from inside this folder:

```
bash verify.sh
```

It needs only `shasum` and `python3`, prints a verdict per check, and exits non-zero if any fails. It
checks every file against `SHA256SUMS`, prints the pair count of the six annual addition files,
confirms **every one of those pairs appears in `additions/evidence_manifest.csv`** so nothing is
asserted without a recorded observation, and confirms the two shipped sets partition the additions.

**It prints WARN rather than PASS where a check is vacuous.** If the English-verified set is empty,
every statement about it is trivially true, and six PASS lines would be exactly the wrong impression.


**On the three additions folders, and the one distinction that matters.** `additions/` is every
net-new (domain, year) pair, which is what a merge against the shared baseline is scored on.
`additions_english/` and `additions_unverified/` **partition** it: a pair is in exactly one of them,
and the two sum to the whole, so they can be added together without double counting. `verify.sh`
checks that rather than asking you to take it on trust.

A pair sits outside the English set for one of two very different reasons, and the `status` column
keeps them apart:

- **`disqualified`** means the engine reached this pair and it did not qualify. The `reason` says
  which of two things happened: the archived text was classified and was not majority English
  (`other_language`, `mixed_below_threshold`), or there was nothing there we could classify
  (`no_capture_in_year`, `no_readable_html_capture`, `insufficient_text`, `non_site_text`,
  `low_confidence`). Both are exclusions and both are documented per item in `disqualified.csv`, but
  they are different claims and the reason column keeps them apart. Any exclusion can be inspected
  and disputed.
- **`unchecked`** means the engine has not reached that pair yet. **No claim is made about its
  language, and none about whether the archive holds a capture for it.** Verification is rate-bound
  against `web.archive.org` and is still running; `language_summary.csv` reports how much of the
  list has been read so coverage is never overstated.

That second point is deliberate and load-bearing. The capture query filters on `statuscode:200` and
`mimetype:text/html`, so an empty answer means "nothing matching that filter", not "nothing at all".
Before `no_capture_in_year` is recorded, a second completely unfiltered index probe is sent; if that
also comes back empty the claim is earned, if it returns rows the reason becomes
`no_readable_html_capture`, and if the probe itself fails the pair is left unsettled with no verdict
written. No domain is excluded on the strength of a question that was not asked. Every
verdict records the exact snapshot URLs that were read, in the `domain_language` table of the
provenance export, so any one of them can be refetched and recomputed.
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
uv run ark lang-report               # regenerates the two disjoint sets and the language summary
uv run ark check                     # the twelve integrity invariants, against the rebuilt store
```

Then compare what it wrote against what shipped. All three sets come back byte-identical, which is
the point: the split is derived from the evidence, not asserted alongside it.

```
for y in 1996 1997 1998 1999 2000 2001; do
    cmp output/netnew/$y.txt            ../additions/$y.txt
    cmp output/netnew_english/$y.txt    ../additions_english/$y.txt
    cmp output/netnew_unverified/$y.txt ../additions_unverified/$y.txt
    cmp data/exports/$y.txt             ../masters/$y.txt
done
cmp output/netnew/evidence_manifest.csv ../additions/evidence_manifest.csv
cmp output/candidate_unverified.txt      ../candidates.txt
```

**The archive renames things, so here is the map.** The pipeline writes to `output/` and
`data/exports/`; the archive presents the same files under clearer names:

| in the rebuild | in this archive |
|---|---|
| `output/netnew/<year>.txt` | `additions/<year>.txt` |
| `output/netnew_english/<year>.txt` | `additions_english/<year>.txt` |
| `output/netnew_unverified/<year>.txt` | `additions_unverified/<year>.txt` |
| `output/netnew/evidence_manifest.csv` | `additions/evidence_manifest.csv` |
| `output/candidate_unverified.txt` | `candidates.txt` |
| `data/exports/<year>.txt` | `masters/<year>.txt` |
| `output/provenance/` | `provenance/` |

This proves the shipped lists follow from the shipped evidence. It does not re-derive the evidence
itself from the original sources, which is tier 3.

### 3. Rebuild from the original sources (a download, then about 20 minutes)

Only needed to re-derive the evidence itself. The supplied baseline ships here in `baseline/`; copy
it to `legacy-data/` inside the unpacked source. The bulk sources are the only thing to fetch, and
**`README.md` inside `source/` documents the route step by step**, with each source's download
address in `sources.md`.

```
cp -R ../baseline/original legacy-data       # from inside the unpacked source/
just reproduce
```

The bulk sources total about 50 GB, of which a single 47 GB capture index is most of it.
**Skipping the Arquivo indexes costs 17,696 pairs over 7,001 domains and leaves about 3 GB**,
reproducing 98.7% of the result.

Measured on the phase-1 archive this returned 99.77% of its pairs, all invariants passing. Those
per-source cost figures are from that measurement and have not been re-measured for this round,
so treat them as indicative. The
gap is two sources with no journal to replay: the legacy `rdap` tranche (3,106 pairs, see the
report's limitations) and a superseded CDX route (11). Their 840 domains return to the candidate
pool. Tier 2 above is the byte-for-byte check.

Two sources are also live rather than hash-pinned, so a later download need not match this one: the
`.fr` file is republished monthly (this used the June 2026 edition) and the Internet Scout feed
keeps growing. The journals and provenance export shipped here do not move.

## Evidence standard

A domain is in `masters/<year>.txt` only with item-level evidence for that year: a web-archive
capture, a dated survey or directory file, a host-link-graph row, a registry record, or the
baseline's own prior evidence. An earlier appearance never implies a later year. The report gives
the standard in full, including how registry dates are read.

Data that only suggests a domain existed, such as being linked to from another site, never assigns a
year. It goes to `candidates.txt` until it earns its own evidence.
