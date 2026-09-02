# Submissions, one folder per round

What was actually sent, round by round. `feedback-phase-*/` holds what came back; this holds what
went out, so the two can be read against each other.

`bash scripts/round/package_delivery.sh [round]` writes into `submissions/<round>/`, defaulting the
round to the current git branch, except on the fleet's `live` branch, where it uses
`phase-<current round>` so repeated builds of one round do not pile up in a shared folder. One
folder per round, each holding:

| File | |
|---|---|
| `DomainDataCollectionTask_<stamp>_IvayloStaykov.tar.gz` | the delivery archive, in the name his 0901 update mandates. **Git-ignored**, gigabytes. Earlier rounds carry the older `internet-digital-ark-1996-2001.tar.gz` name |
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
| phase-5 | 2026-08-17 | `merged260815` | 2,838,715 | 1,697,224.86 | **20.3337%** | **accepted 2026-08-17 with nothing rejected, recalculated to 2,608,322 / 1,566,229.7613 / 14.901054% against `merged260817`, reissued as `merged260817-2`** | the archive's own capture census, bulk registry creation dates, a UKWA parser reading 6.76% of its file, the recovered January 1997 domain survey |
| phase-6 | **built, not sent** | `merged260821` | 1,929,655 | 713,481.4198 | 5.339483% | **rebuilt 2026-08-26, above the 5% threshold** | eleven new sources, the largest a second attribute of a file already on disk; generated RDAP target populations measured against each other; the RDAP query logs excluded from the archive on size |
| phase-7 | built 2026-09-02, not yet sent | `merged260902` | 2,541,429 (623,823 registrable + 1,917,606 hostname) | 1,458,263.2088 | **7.5794%** | archive `DomainDataCollectionTask_202609021011_IvayloStaykov.tar.gz`, 3.4 GB, sha256 in `phase-7/`; `verify.sh` (eleven checks) and the tier-2 rebuild pass from a fresh extraction | first round scored at the calculator's own unit: hostnames beneath held registrables ship as a second file per year, dated by their own captures (IA domain-wide sweeps of platform parents, NYPW TimeMaps, Early Web, USFEDGOV, two URL blocklists); eight sources admitted by the unattended loop under the standing rule. The hostname rule is read by its purpose: DNS-listed hosts (18.2M store rows, the ISC survey alone once exporting as 9.17M EE) and `www.<parent>` (5.2M rows) are held out with their evidence kept, which cut the first build of the same day from 25.6M hostnames and 13.34M EE to this figure |

Growth is always quoted against the baseline in the same row, which is the reviewer's convention. The
same 603,401.78 equivalent-English is 9.69% against `merged260810`, so a percentage lifted out of this
table without its baseline means nothing.

**A round can be accepted in full and still be credited less than it was sent for**, which happened
first in phase 5 and is not a rejection. He merges against whatever baseline is current when he reaches
the submission, and 230,393 of ours had already arrived in his interim `merged260817` through another
contributor. Nothing of ours was refused: his check found no invalid record, no duplicate, and evidence
behind every domain-year. `src/ark/baseline.py` therefore stores the ACCEPTED figure per round, because
the cumulative is the number the internal competition is scored on and the submitted figure would
double-count the overlap.

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
pairs** (2026-07-28/29) and was never shipped as a scored round; it was rolled into
phase 3's 151,949. Never add that step to a cumulative total.
