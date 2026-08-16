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

| Round | Sent | Baseline | Net-new pairs | Equivalent-English | Growth | Outcome | What was new |
|---|---|---|--:|--:|--:|---|---|
| phase-1 | 2026-07-26 | `original` | 1,429,524 | 756,559.29 | 17.38% on records | merged as `merged260727` | first delivery: baseline normalization, capture-backed additions |
| phase-2 | 2026-07-29 | `merged260727` | 17,418 | | | rolled into phase-3 | expansion rounds, candidate pool split out |
| phase-3 | 2026-08-02 | `merged260730` | 151,949 | 91,814.69 | 1.6600% | merged as `merged260802-2` | English verification engine, two disjoint shipped sets |
| phase-4 | 2026-08-09 | `merged260802-2` | 946,266 | 603,401.78 | **10.7310%** | **accepted in full 2026-08-10, reissued as `merged260810`** | Usenet bare-domain forms, registry creation dates over the candidate pool, UUCP registry maps, Enron and mailing-list corpora, rtfm FAQs, American trade press |
| phase-5 | 2026-08-17 | `merged260815` | 2,835,893 | 1,694,957.87 | **20.3066%** | sent | the archive's own capture census, bulk registry creation dates, a UKWA parser reading 6.76% of its file, the recovered January 1997 domain survey |

Growth is always quoted against the baseline in the same row, which is the reviewer's convention. The
same 603,401.78 equivalent-English is 9.69% against `merged260810`, so a percentage lifted out of this
table without its baseline means nothing.

**phase-4 in one line:** the round crossed 10% against `merged260802-2`, re-scored with the reviewer's
own `equivalent_english_domains.py`, which rejected none of the 946,266 records, found none already in
his merged files, and agreed with our total to 0.0000. All integrity invariants pass. It was the first
round shipped without the retired English partition: the deliverable is `additions/`, with
`candidates.txt` beside it.

**phase-4's acceptance is verified from the files, not taken on trust.** `merged260810` minus
`merged260802-2` is exactly 946,266 lines, and on the sorted annual files `comm` shows **zero** lines
dropped in either direction, with the lines he added byte-identical to `sort output/netnew/<year>.txt`.
He merged precisely what was sent and added nothing of his own.

Rows for rounds packaged before this folder existed are filled in from their reports where the
archive survives, and left blank where it does not. Blank means unrecorded, not zero.

**Two corrections made on 2026-08-17, both about who did what.** Phase 1's row was blank because the
equivalent-English metric did not exist in July, so no figure was ever quoted for it. Its record count
is the reviewer's own ("the six yearly files grew from 8,224,963 to 9,654,487 records, adding 1,429,524
records (17.38%)", feedback of 2026-07-27) and the weight beside it is the difference between those same
two releases under the unchanged model, computed on 2026-08-17. It is the largest single round this
project has delivered, and it had been missing from the cumulative figure entirely.

And phase 2's row said it was "merged as `merged260730`", which credits this project with a round it did
not send. `merged260727` to `merged260730` is **+609,145 records from an external contributor**, filed
under `feedback-external-phase-2/`; its own feedback describes regional directory harvesting across
Brazil, China, Poland, the Czech Republic, Korea, Latin America, Australia, South Africa, India, Japan
and Europe, plus the non-English ODP/DMOZ World branch. This project's phase 2 was **17,418 net-new
pairs** (`docs/notes.md`, 2026-07-28/29) and was never shipped as a scored round; it was rolled into
phase 3's 151,949. Never add that step to a cumulative total.
