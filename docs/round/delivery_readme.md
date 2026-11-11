# Internet Digital Ark delivery

Two sets, and a labelled third part outside both and outside the growth figure.

- `additions/`: hostnames and registrable domains for your annual files, 1996 to 2013, one file
  a year, none in your file for that year. Each name has its own web evidence of exactly that
  name in that year, of one of five kinds: a capture (1996 to 2001 a 2xx or 3xx capture that
  replays; 2002 to 2013 a 2xx or 3xx capture where the capture index records a status, else a
  capture from an index that records none, never a 4xx or 5xx), a dated link graph that names
  it, a custodian dataset's dated record of it, a captured bookmark file's entry for it
  dated by the browser's own `ADD_DATE`, or a dated usage report that logged a request
  referred from a page on it.
- `candidates/`: every other name we hold for 1996 to 2001, as one list, `candidates.txt`. None is
  in any file of your release or a 1996 to 2001 addition; one can be an addition of a later year. `provenance.csv` has one row a name: `name, year, class, source, source_file,
  position`, `source_file` the public file the name was read from and `position` the record
  naming it there. As your brief says: "When a candidate later has qualifying evidence, move only
  the verified hostname-year record into the relevant annual file."
- `year_evidence/`: names your release already holds, for a year your file for it lacks, each
  dated by our record of that year (a usage report, a message's `Date:`, a dump's stamp). Your
  second open research question asks: "How can the year in which a website existed be determined
  more accurately?" One `year,host` file a tier, the strongest first: `1_bracketed` (your files
  hold the name in a year before and a year after), `2_after_only`, `3_before_only`,
  `4_pool_only` (only in `candidate_pool.txt`), and `5_last_modified` (a 1996 to 2001 capture of
  the host whose own `Last-Modified` header dates the page to that earlier year). `provenance.csv` gives each row's class, public
  source, locator (a message or line in it, counted from 1) and tier; `tiers.csv` the sizes. It
  asks no credit; you decide.

[CLASS TABLE]

How to find a candidate at its position, by the position's form. Every count starts at 1, and a
line ends at a line feed only unless the row says otherwise.

| `position` holds | `source_file` | the name is |
|---|---|---|
| `<group>.mbox.zip#<n>` | the Usenet zip | in post n of its unpacked text (`unzip -p`), rule below |
| `<file>.usenet.7z#<n>` | the 7z | in post n of the unpacked mbox, same rule |
| `nntp://<server>/<group>#<n>` | the newsgroup | in article n on that server (`ARTICLE n`) |
| `<month>.txt#<n>`, `.txt.gz#<n>`, `mbox.lua?...#<n>`, a list's mbox or text | the month file | in message n, a message opening at each line `From <addr> <Www> <Mmm> <dd> <hh:mm:ss> <yyyy>`; a bare `From ` in a body opens none |
| `<month>.mail#<n>` (IETF) | the month file | in message n; a message ends at a line of four `\x01` (MMDF) or at such an envelope line outside a header, and only a message with a header counts |
| `rsync://.../<number>.log#<n>` (Debian bugs) | the bug log | in record n, opened by a line holding only `\x07` and closed by one holding only `\x03` |
| `.../web/<stamp>id_/<url>#<n>` or `<url>#<n>` (a usage or news-server report) | the Wayback page, or the page on its own site | on line n of the page as served, read as Latin-1, lines ending at CR LF, a lone CR or LF; a WebStat or WWWusage page prints it with its labels reversed (`com.example.www`) |
| `arc <offset> <length> #<n> <host>` (a report page read from an ARC file) | the `.arc.gz` file | in the ARC record at bytes offset to offset + length - 1, one gzip member, on line n of its HTTP body, lines ending at CR LF, a lone CR or LF |
| `<file>.tgz#<member>#<n>` (a traceroute set) | the archive | on line n of that member |
| `cdx capture <stamp> ...` or a 14-digit stamp | a Wayback URL | the capture at that stamp; a status 4xx or 5xx is why it is a candidate |
| `isc survey <edition> host <name>` | the survey file of that edition | on the line naming it |
| anything else | the published list or capture | on the line naming it |

A Usenet post opens at a line matching `^From (-?[0-9]+|[^ ]+@[^ ]+)` that is the first line or
follows a line that is empty or only white space, outside a header block (a header block ends at
its first such line). The zips hold lone carriage returns, which do not end a line.

## Check

Beside the download, then inside the extracted folder, with Python 3.10 or newer and
[`uv`](https://docs.astral.sh/uv/). The first line prints the sha256 given in the mail.

```
shasum -a 256 [ARCHIVE].7z
7z x [ARCHIVE].7z && cd [ARCHIVE]
B=/path/to/merge261104  # your release, not shipped back; additions/support/baseline/README.txt gives its sha256
HIS=$B bash additions/support/verify.sh
```

`verify.sh` prints PASS, FAIL or SKIP per check and exits non-zero on a FAIL; SKIP means the
checked thing is not in the archive, or `HIS` is unset. It checks the checksums, one evidence row
per addition, the additions against your files and their sha256, the candidates against every
file of your release and their provenance, and reruns your calculator on your 1996 file.

Each figure of the report, in `bash` with `bc`. Check 2 takes about 7 minutes and up to 11 GB.

```
ee() { for f; do python3 additions/support/equivalent_english_domain_calculator/equivalent_english_domains.py "$f" --output-dir "${TMPDIR:-/tmp}/ee"; done | awk '/^Equivalent-English/ {s += $NF} END {printf "%.4f\n", s}'; }
T=$(python3 -c 'import datetime as d; print((d.date.today() - d.date(2026, 8, 2)).days)')
# 1, your records: 1996 to 2001, then 2002 to 2013
cat $B/199[6-9].txt $B/200[01].txt | wc -l
cat $B/200[2-9].txt $B/201[0-3].txt | wc -l
# 2, your equivalent-English
E1=$(ee $B/199[6-9].txt $B/200[01].txt); echo $E1
E2=$(ee $B/200[2-9].txt $B/201[0-3].txt); echo $E2
# 3, our additions
cat additions/199[6-9].txt additions/200[01].txt | wc -l
cat additions/200[2-9].txt additions/201[0-3].txt | wc -l
# 4, their equivalent-English
A1=$(ee additions/199[6-9].txt additions/200[01].txt); echo $A1
A2=$(ee additions/200[2-9].txt additions/201[0-3].txt); echo $A2
# 5, growth in percent, then S = 10 x growth / t, with t in whole days since 2 August 2026
echo "g = 100 * $A1 / $E1; g; 10 * g / $T" | bc -l
echo "g = 100 * $A2 / $E2; g; 10 * g / $T" | bc -l
# 6, our candidates and their equivalent-English
wc -l < candidates/candidates.txt
ee candidates/candidates.txt
```

Rebuild both sets from the evidence, with no archive queries and no source data. `ark intake`
checks your release, linked in as `additions/support/baseline/merge261104`, and writes 4.2 GB:

```
ln -s "$B" additions/support/baseline/ && cd additions/support/source && tar -xzf source.tar.gz
uv sync && uv run ark intake && uv run ark rebuild ../../provenance && uv run ark check
for y in 1996 1997 1998 1999 2000 2001; do
    LC_ALL=C sort -m -u output/netnew/$y.txt output/netnew/${y}_hostnames.txt | cmp - ../../$y.txt
done
cmp output/netnew/candidate_additions.txt ../../../candidates/candidates.txt
cmp output/netnew/candidate_provenance.csv ../../../candidates/provenance.csv
```

To see the captures behind one name in one year:

```
uv run --with duckdb --no-project python additions/provenance/trace.py "$(head -1 additions/2001.txt)" 2001
```

## additions/

| Path | Contents |
|---|---|
| `<year>.txt` | ours for that year, none in your file for it |
| `provenance/` | `evidence_manifest.csv` and `hostnames_evidence_manifest.csv`, one evidence row per 1996 to 2001 addition, its `evidence_kind` last; `evidence_ledger.csv`, the journal line of one capture per 2002 to 2013 addition, with `dedup_report.csv` and `manifest.json` (inputs, your files' sha256); the evidence graph as Parquet with `trace.py` |
| `support/` | `verify.sh`; `audit/` (the merge against your release, report figures, per-source tables); `source/` (the code at `COMMIT.txt`, the agents at `FLEET_COMMIT.txt`); `journals/`, `seeds/`; `baseline/README.txt`; your calculator, unmodified; `experience-summary.md`, `metric-explained.md`, `sources.md`, `sources-closed.md`; `Open Research Questions/` |

Name lists are one lowercase name per line, `LC_ALL=C` sorted, without a header. Your file for a
year with ours is `LC_ALL=C sort -m -u $B/2001.txt additions/2001.txt`. Every `.csv` is RFC 4180 and
UTF-8 with one header row.
