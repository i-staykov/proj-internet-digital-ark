# Internet Digital Ark: round 11

Additions to your 1996-2015 annual files, against your release `merge261007-4`. EE is
equivalent-English, by your calculator and weights, copied unmodified in
`equivalent_english_domain_calculator/`.

## 1. Results

| | records | EE |
|---|--:|--:|
| 1996-2001 additions, the six annual files | 334,701 | 183,660.7777 |
| 2002-2015 additions, `extended_years/` | 108,817,300 | 55,063,838.2586 |
| Together | | **55,247,499.0363** |

Growth over your 1996-2015 files as a whole (254,042,498.3802 EE): **21.7473%**. Apart: 1996-2001
0.2473% of 74,253,225.6428 EE, 2002-2015 30.6269% of 179,789,272.7374 EE.

No record is in your file for its year. Candidate files ship as before and are not counted above.

## 2. The evidence rule

A record is one exact hostname and one year. It is kept when a capture index holds a 2xx or 3xx
capture of that exact host stamped in that year, the host passes your `HOST_RE`, and its TLD existed
that year; it is dropped when your file for that year holds the name. Nothing is inferred from
another year, no `www.` or bare variant is generated, and each record cites its earliest capture.

## 3. Sources, 2002-2015

Four capture indexes, each read whole at hostname grain; every row is a capture with the archive's
own 14-digit timestamp and status.

| Source | What it is | Read |
|---|---|---|
| Not Your Parents' Web TimeMaps, `archive.org/download/nypw_timemaps/`, CC BY 4.0 | one TimeMap per URL listing every capture with its status, 144 tarballs by year of first capture | all 144 tarballs, rows dated 2002-2015 |
| Internet Archive storage node ia600702, `archive.org/download/host_cdx_ia600702/ia600702.hostcdx.gz` | the public CDX of every capture on one node, 1,031,419,773 rows | the whole 57.6 GB file |
| Dartmouth-NBER ARCS, `archive.org/download/DARTMOUTH-NBER-RESEARCH-2017-ARCS-*/` | the Internet Archive's per-item CDX beside each item of the collection; no ARC is fetched | the 226 items with 2002-2015 stamps |
| Arquivo.pt, `arquivo.pt/datasets/cdxj/IA.cdxj` [fonte: Arquivo.pt, 07/10/2026] | Arquivo.pt's copy of an Internet Archive index, CDXJ | the whole file, its 2002-2008 captures |

`extended_years/` holds, per year, `additions/YYYY.txt` (ours alone) and `YYYY.txt` (your file
merged with ours); `evidence_ledger.csv`, one row per record: year, host, method, source file, line,
file sha256, capture URL; `dedup_report.csv` in your merge_stats columns; and `manifest.json`, the
inputs with their sha256 and the counts and EE per year.

## 4. Sources, 1996-2001

| Source | Unit | What dates one record | Records | EE |
|------------------------|------|----------------------------|--------:|-------:|
| `ia_cdx_domain_sweep` | hostname | the row's own 14-digit capture timestamp | 316,000 | 174,792 |
| `ia_cdx_bulk` | registrable | the capture timestamp of a URL on that host | 4,621 | 4,389 |
| 8 further sources | both | one row each in `sources.md` and `audit/source_contribution.csv` | 14,080 | 4,479 |
| **Total** | | | **334,701** | **183,661** |

The same rule, from the capture-index collectors of the previous rounds. `additions/` and
`hostnames/` hold the records with their evidence manifests, and `provenance/` rebuilds every one.

## 5. Checks and reproduction

The 1996-2001 merge audit, in your merge_stats form:

| | records | equivalent-English |
|---|--:|--:|
| baseline `merge261007-4` | 135,786,797 | 74,253,225.6428 |
| **accepted increment** | **334,701** | **183,660.7777** |
| post-merge total | 136,121,498 | 74,436,886.4205 |

**Not one of the 334,701 records submitted is already in the baseline; 28 of 28 reconciliation checks pass.** Per-check verdicts: `audit/merge_audit_ark_*.json`; the per-year form, in your column names: `audit/merge_stats_ark_*.csv`.

`verify.sh` in the archive re-checks every verdict, among them that no name in
`extended_years/additions/` is in your file for that year. `source/source.tar.gz` is the code at
`source/COMMIT.txt` and `source/fleet.tar.gz` the research loop; `README.md` gives the route from a
fresh extraction, and `sources.md` is the register of every source tried, with its decision.
