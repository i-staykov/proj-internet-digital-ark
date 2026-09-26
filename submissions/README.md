# Submissions

What went out, for the current round and the one before it: each folder holds its
`MANIFEST.txt`, which names the commit holding the report and registers as sent and the
baseline release, and the `.sha256` of its archive.

The archive, `DomainDataCollectionTask_<stamp>_IvayloStaykov.tar.gz`, is git-ignored and sits
beside them on the laptop. Every older round is on Drive under `gdrive:ark-offsite/submissions/`,
behind an `offsite.py --verify` receipt.

When the next round ships, the older of the two kept rounds goes the same way: `just verify
raw`, then `offsite.py --manifest`, `--upload --yes` and `--verify`, then `git rm` of its folder
within the receipt's 24 hours.

The round-by-round figures, sent against credited, are in `docs/registers/rounds.md`.
