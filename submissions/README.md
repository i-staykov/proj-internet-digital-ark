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

The round-by-round figures, sent against credited, with the reviewer's release and receipt stamps,
are in `docs/rounds.md`, which stays out of the delivery. `MANIFEST.txt` in each folder here is the
record of what went out.
