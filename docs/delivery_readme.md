# Internet Digital Ark: Delivery Archive

Evidence-backed annual domain lists for **1996–2001**, grown on top of the provided
~8.2M-line baseline. Every annual-file entry traces to item-level, per-year evidence.

**Headline (2026-07-25):** 463,364 net-new registered domains · 1,303,508 net-new
(domain, year) pairs, on top of 4.82M baseline domains. Full analysis in `report.docx`.

## What's in this archive

| Path | Contents |
|---|---|
| `report.docx` / `report.md` | The delivery report (sources, architecture, results, limitations, reproduction) |
| `masters/1996.txt … 2001.txt` | **Merged master year lists**: baseline + net-new, deduplicated within each year, one registered domain per line |
| `additions/1996.txt … 2001.txt` | **Net-new additions only**: the domains this program added on top of the baseline |
| `additions/evidence_manifest.csv` | **Provenance export**: one row per added (domain, year), carrying the representative evidence row behind it. Corroborating evidence is not exported: the store holds 11.05M evidence rows against 1.3M exported, and the cross-validation figures in the report are computed from the store |
| `candidates.txt` | Candidate/unresolved domains (no per-year evidence yet); never mixed into the annual masters |
| `dropped_domains.txt` | Baseline lines excluded by the pipeline, grouped by reason |
| `audit/` | Normalization/salvage audit CSVs (every correction and drop, per source) |
| `logs/` | Execution logs from every run. Per-run statistics live in the store's `run_metrics` table and are summarised in the report rather than exported separately |
| `source/` | Full source code + config snapshot (also the git repo) |
| `sources.md` | Per-source documentation: acquisition method, how the year is established, why each carries its evidence type, measured yield, caveats, reproduction command |
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

Within `whois_creation`, RDAP rows attest **the creation year only**, per brief III.6: an
RDAP response carries no registration history, so it cannot speak to any later year, and
RDAP spans ~590 registries whose creation-date semantics are not established (9,664
assignments that had relied on an inferred registration interval were withdrawn on
2026-07-25). AFNIC `.fr` rows attest every in-window year of the span
`[creation, deletion-or-now]`, because AFNIC's own registrar documentation states that its
creation date is "the last creation date of the domain name", which puts it at or after any
prior deletion and makes the span continuous by construction. Report §2 gives the citation,
the two reproducible live cases, and the size of the exposure if a reviewer rejects it.

## How to reproduce

With only [`uv`](https://docs.astral.sh/uv/) installed, first unpack the code snapshot,
then run from inside it:

```
tar -xzf source/source.tar.gz -C source/
cd source
```

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
uv run ark gaps --creation                                   # -> creation_candidates.txt
uv run ark rdap  data/raw/rdap/creation_candidates.txt       # query RDAP -> run journal
uv run ark gaps                                             # -> gap_candidates.txt
uv run ark cdx   data/raw/cdx/gap_candidates.txt --workers 8   # query IA CDX -> run journal
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz   # journal -> creation-year evidence
uv run ark ingest cdx_snapshot  data/raw/cdx/cdx_*.jsonl.gz     # journal -> per-year capture evidence
uv run ark export                                     # regenerate masters/additions/manifest
uv run ark stats                                      # the scoreboard
uv run ark check                                      # integrity gate (must pass)
```

Raw source files (download URLs and rescue notes) are documented per-source in
`notes.md`. Downloaded data is not shipped in the archive; it regenerates from those
URLs. The method is fully in `source/`.
