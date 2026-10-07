# Internet Digital Ark: round [ROUND]

Additions to your 1996-2015 annual files, against your release `[BASELINE]`. EE is
equivalent-English, by your calculator and weights.

## Results

| | records | EE |
|---|--:|--:|
| 1996-2001 additions, the six annual files | [TOTAL] | [EE] |
| 2002-2015 additions, `extended_years/` | [EXTPAIRS] | [EXTEE] |
| Together | | **[GATEEE]** |

Growth over your 1996-2015 files as a whole ([GATEBASELINEEE] EE): **[GATEPCT]**.

No record is in your same-year file. Candidate files ship as before and are not counted above.

## Method

Every record is an exact host with its own 2xx or 3xx capture stamped in that year; nothing is
inferred from another year or another name.

**2002-2015** comes from four capture indexes, each read whole at hostname grain: the "Not Your
Parents' Web" TimeMaps (Internet Archive item `nypw_timemaps`), the public CDX of Internet Archive
storage node ia600702, the item CDX beside the Dartmouth-NBER ARCS collection, and Arquivo.pt's copy
of an Internet Archive index. Each host-year cites its earliest capture. `extended_years/` holds the
additions per year, the evidence ledger (one row per record: capture, file, line, file sha256), the
manifest and the dedup report.

**1996-2001** continues the capture-index research of the previous rounds; `provenance/` rebuilds
every record.

`verify_delivery.sh` re-checks the archive; `README.md` lists every file.
