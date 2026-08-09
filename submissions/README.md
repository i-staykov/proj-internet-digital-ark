# Submissions, one folder per round

What was actually sent, round by round. `feedback-phase-*/` holds what came back; this holds what
went out, so the two can be read against each other.

`bash scripts/package_delivery.sh [round]` writes into `submissions/<round>/`, defaulting the round
to the current git branch. Each folder holds:

| File | |
|---|---|
| `internet-digital-ark-1996-2001.tar.gz` | the delivery archive. **Git-ignored**, gigabytes |
| `.tar.gz.sha256` | proves a recovered tarball is the one that was sent |
| `report.md` | the round report exactly as sent |
| `sources.md` | the source documentation exactly as sent |
| `MANIFEST.txt` | commit, baseline release, sizes, checksum, net-new pair count |

**To rebuild a superseded round's archive**, check out the commit `MANIFEST.txt` names and run
`just deliver && just package`. That is why the tarball does not need to be kept: the commit, the
provenance export and the raw journals reproduce it, and the checksum proves the rebuild matches.

## Rounds

| Round | Sent | Baseline | Net-new pairs | Equivalent-English | Growth | What was new |
|---|---|---|--:|--:|--:|---|
| phase-1 | 2026-07-26 | `original` | | | | first delivery: baseline normalization, capture-backed additions |
| phase-2 | 2026-07-29 | `merged260727` | | | | expansion rounds, candidate pool split out |
| phase-3 | 2026-08-02 | `merged260730` | | | | English verification engine, two disjoint shipped sets |
| phase-4 | 2026-08-09 | `merged260802-2` | 946,266 | 603,401.78 | **10.7310%** | Usenet bare-domain forms, registry creation dates over the candidate pool, UUCP registry maps, Enron and mailing-list corpora, rtfm FAQs, American trade press |

**phase-4 in one line:** the round crossed 10% on the equivalent-English metric, re-scored with the
reviewer's own `equivalent_english_domains.py`, which rejected none of the 946,266 records, found none
already in his merged files, and agreed with our total to 0.0000. All integrity invariants pass. This
is the first round shipped without the retired English partition: the deliverable is `additions/`,
with `candidates.txt` beside it.

Rows for rounds packaged before this folder existed are filled in from their reports where the
archive survives, and left blank where it does not. Blank means unrecorded, not zero.
