# Submissions

What went out, for the current round and the one before it: each folder holds its
`MANIFEST.txt`, which names the commit and the baseline release, and the `.sha256` of its
archive. The report and registers as sent are at the commit the manifest names, except phase-9's,
which are at 37e331cc: its manifest names a commit no branch holds. The archives are git-ignored.

After the Drive steps, every older round is on Drive under `gdrive:ark-offsite/submissions/`,
behind an `offsite.py --verify` receipt. When the next round ships, the older of the two kept
rounds goes the same way: `just verify raw`, then `offsite.py --manifest`, `--upload --yes` and
`--verify`, then `git rm` of its folder within the receipt's 24 hours.

The round-by-round figures, sent against credited, are in `docs/registers/rounds.md`.
