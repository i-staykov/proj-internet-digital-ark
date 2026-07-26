# Internet Digital Ark: Delivery Archive

Evidence-backed annual domain lists for **1996-2001**, grown on top of the provided
~8.2M-line baseline. Every annual-file entry traces to item-level, per-year evidence.

**Headline (2026-07-26):** 463,565 net-new registered domains · 1,322,358 net-new
(domain, year) pairs, on top of 4.82M baseline domains, plus an auxiliary pool of
3,595,769 hostname and URL download seeds. Full analysis in `report.docx`.

## What's in this archive

| Path | Contents |
|---|---|
| `report.docx` / `report.md` | The delivery report (sources, architecture, results, limitations, reproduction) |
| `masters/1996.txt … 2001.txt` | **Merged master year lists**: baseline + net-new, deduplicated within each year, one registered domain per line |
| `additions/1996.txt … 2001.txt` | **Net-new additions only**: the domains this program added on top of the baseline |
| `additions/evidence_manifest.csv` | **Provenance export**: one row per added (domain, year), carrying the representative evidence row behind it. Corroborating evidence is not exported: the store holds roughly 11M evidence rows against the 1.3M exported here, and the cross-validation figures in the report are computed from the store |
| `candidates.txt` | Candidate/unresolved domains (no per-year evidence yet); never mixed into the annual masters |
| `seeds/download_seeds.txt` | **Auxiliary seed pool**: one hostname or URL per line, for subsequent webpage downloads. The registered domain is the counting unit for the annual files (III.8), so `www.foo.com` and `shop.foo.com` collapse to one line there; this pool keeps that granularity, which is what a crawler needs |
| `seeds/download_seeds.csv` | The same seeds with the registered domain, the year the source dates them to, and which source they came from |
| `journals/` | The raw responses of every archive and registry query made, one gzipped JSON-lines file per run. These are what make the two network stages reproducible offline: re-running the pipeline replays these bytes instead of re-querying services whose answers have since changed |
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

Put the bulk source files back under `data/raw/` (each one's download route is in
`sources.md`) and the provided baseline in `legacy-data/`. Then restore the shipped
journals to the directories the commands below read, by name:

```
cdx_*.jsonl.gz                  -> data/raw/cdx/
rdap_*.jsonl.gz                 -> data/raw/rdap/
expand_2*.jsonl.gz              -> data/raw/expand/
expand_round2.jsonl.gz          -> data/raw/expand/round2/
expand_wwwvl_*.jsonl.gz         -> data/raw/expand/wwwvl/
expand_round4*.jsonl.gz         -> data/raw/expand/round4/
```

The `seeds/expansion/*.txt` files are the page lists those fetches ran against, kept so
the section VII rounds can be repeated rather than only replayed. Then:

```
uv run ark init                                             # create the stores
uv run ark ingest-legacy                                    # load the baseline read-only
uv run ark legacy-review                                    # write dropped_domains.txt
uv run ark audit                                            # write the normalization audit

uv run ark ingest early_web         data/raw/early_web/*.cdx.gz
uv run ark ingest isc_survey        data/raw/isc_survey/*.gz
uv run ark ingest arquivo_roteiro   data/raw/arquivo/Roteiro.cdxj
uv run ark ingest arquivo_ia        data/raw/arquivo/IA.cdxj
uv run ark ingest afnic_fr          data/raw/afnic/*NomsDeDomaineEnPointFr.csv
uv run ark ingest internet_scout    data/raw/scout/scout_oai.xml
uv run ark ingest odp               data/raw/odp/*.gz
uv run ark ingest ukwa_link_source  data/raw/ukwa/host-linkage.tsv.gz
uv run ark ingest ukwa_link_target  data/raw/ukwa/host-linkage.tsv.gz

uv run ark seed data/raw/webbase/hosts.txt                  # candidate pool
uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt
uv run ark seed data/raw/100hot/candidate_hosts.txt

uv run ark ingest cdx_snapshot  data/raw/cdx/cdx_*.jsonl.gz    # replay the archive queries
uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz  # replay the registry queries
uv run ark ingest expansion_links     data/raw/expand/expand_*.jsonl.gz --round 1
uv run ark ingest expansion_directory data/raw/expand/round2/*.jsonl.gz --round 2
uv run ark ingest expansion_directory data/raw/expand/wwwvl/*_corroborated.jsonl.gz --round 3
uv run ark ingest expansion_links     data/raw/expand/wwwvl/*_unverified.jsonl.gz --round 3
uv run ark ingest expansion_directory data/raw/expand/round4/*_corroborated.jsonl.gz --round 4
uv run ark ingest expansion_links     data/raw/expand/round4/*_unverified.jsonl.gz --round 4

uv run ark seed-pool isc_survey       data/raw/isc_survey/*.gz    # the hostname/URL seed pool
uv run ark seed-pool odp              data/raw/odp/*.gz
uv run ark seed-pool internet_scout   data/raw/scout/scout_oai.xml
uv run ark seed-pool ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz
uv run ark seed-pool early_web        data/raw/early_web/*.cdx.gz

uv run ark export                                           # masters, additions, manifest
uv run ark stats                                            # the scoreboard
uv run ark check                                            # integrity gate (must pass)
```

**No network is required.** The two collectors are not re-run: `ingest cdx_snapshot` and
`ingest rdap_snapshot` read the shipped journals, so the result is derived from bytes in
this archive rather than from services that answer differently today. Each journal is
hashed into a ledger on ingest, so a file whose contents changed is refused rather than
silently loaded. To collect *more* evidence, `ark gaps` then `ark cdx` or `ark rdap` do
run against the live services; `README.md` in `source/` documents that path.

If [`just`](https://github.com/casey/just) is available, all of the above is
`just reproduce`, and `just check` additionally runs the code's own test suite.

Raw source files (download URLs and rescue notes) are documented per-source in
`sources.md`. Bulk downloads are not shipped in the archive; they regenerate from those
routes. The method is fully in `source/`.
