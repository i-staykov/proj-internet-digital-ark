# Internet Digital Ark — Delivery Archive

Evidence-backed annual domain lists for **1996–2001**, grown on top of the provided
~8.2M-line baseline. Every annual-file entry traces to item-level, per-year evidence.

**Headline (2026-07-25):** 463,365 net-new registered domains · 1,302,735 net-new
(domain, year) pairs, on top of 4.82M baseline domains. Full analysis in `report.docx`.

## What's in this archive

| Path | Contents |
|---|---|
| `report.docx` / `report.md` | The delivery report (sources, architecture, results, limitations, reproduction) |
| `masters/1996.txt … 2001.txt` | **Merged master year lists** — baseline + net-new, deduplicated within each year, one registered domain per line |
| `additions/1996.txt … 2001.txt` | **Net-new additions only** — the domains this program added on top of the baseline |
| `additions/evidence_manifest.csv` | **Provenance export** — one row per (domain, year, source): the evidence behind every addition |
| `candidates.txt` | Candidate/unresolved domains (no per-year evidence yet); never mixed into the annual masters |
| `dropped_domains.txt` | Baseline lines excluded by the pipeline, grouped by reason |
| `audit/` | Normalization/salvage audit CSVs (every correction and drop, per source) |
| `logs/` | Execution logs + `run_metrics` outputs (per-run statistics) |
| `source/` | Full source code + config snapshot (also the git repo) |
| `notes.md` | The decision log: every source, method, yield, and caveat, with dates |
| `SHA256SUMS` | Checksums for every file in this archive |

## Evidence standard

An entry is in `masters/<year>.txt` only if it has item-level evidence for that year:
a web-archive capture (`cdx_timestamp`), a dated index/survey/directory file
(`artifact_listing` / `dated_directory`), a host/link-graph row (`link_source`), a
WHOIS/registry registration record (`whois_creation`), or reuse of the baseline's own
prior evidence (`prior_reused`). Confirmed by Prof. Ding (2026-07-24) that dated DNS
surveys, archive indexes, host/link graphs, dated directory/index files, and WHOIS
records all count as direct annual evidence. Candidate-only data never assigns a year.

## How to reproduce

With only [`uv`](https://docs.astral.sh/uv/) installed, from `source/`:

```
uv run ark ingest-legacy                              # load the baseline read-only
uv run ark ingest early_web  data/raw/early_web/*.cdx.gz
uv run ark ingest isc_survey data/raw/isc_survey/*.gz
uv run ark ingest arquivo_roteiro data/raw/arquivo/Roteiro.cdxj
uv run ark ingest arquivo_ia data/raw/arquivo/IA.cdxj
uv run ark ingest ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz
uv run ark ingest afnic_fr   data/raw/afnic/*.csv
uv run ark ingest odp        data/raw/odp/*.gz
uv run ark ingest internet_scout data/raw/scout/scout_oai.xml
uv run ark rdap  data/raw/ukwa/link_target_candidates.txt   # RDAP creation-date verification
uv run ark export                                     # regenerate masters/additions/manifest
uv run ark stats                                      # the scoreboard
uv run ark check                                      # integrity gate (must pass)
```

Raw source files (download URLs and rescue notes) are documented per-source in
`notes.md`. Downloaded data is not shipped in the archive; it regenerates from those
URLs. The method is fully in `source/`.
