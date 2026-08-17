# Retired data directories

**All raw data is kept.** Nothing under `data/` was deleted in the phase-5 cleanup, and
nothing should be: the reviewer's first priority for this round is unprocessed files and
low-recall extraction over corpora already paid for, which makes every byte on disk a
candidate rather than clutter.

What this page does instead is **label the directories nobody reads any more**, so a
fresh agent can tell "retired" from "unmined". Those are different states and confusing
them costs either a wasted pass or a missed opportunity. The unmined ones are in
`docs/sources.md` under "Bytes already on disk that nothing reads"; the retired ones are
here.

| directory | size | what it is, and why nothing reads it |
|---|--:|---|
| `data/raw/lang/` | 3.0 MB | Page-language verdict journals from the retired English standard, plus `superseded/` holding verdicts from engine versions that were discarded after a defect was found. Only `legacy/src/language.py` can interpret them. They no longer ship in the delivery archive: an archive carrying them documents a rule nobody applies |
| `data/logs/lang_supervisor.log`, `lang_watchdog.log` | small | The retired engine's throughput logs. `fill_report.py` used to derive a "measured rate" figure from the first of these; that substitution is gone |
| `data/staging/usenet_resplit/` | 47 MB | The 6 August comparison staging area for a Usenet re-split. `scripts/diff_usenet_resplit.py` is the live tool that reads this shape, and it is worth keeping for exactly the work phase 5 wants: widening an extraction regex over a corpus already ingested without handing DuckDB duplicates |
| `data/raw/source_probe_260806/` | 938 MB | Artifacts, measurement scripts and logs from the 6 August discovery session. **Not retired in substance**: two of its leads are still open and documented in `docs/sources.md` (`attrition/`, and `hathitrust_ef/`). The `scripts/` inside it open the store read-only and each measurement's answer is in `docs/sources.md` or `docs/notes.md` |
| `data/raw/gapfill_candidates.txt` | 6.6 MB | A pre-metric gap-queue snapshot. Superseded by `scripts/build_query_queue.py`, which orders by expected net-new equivalent-English per query. Nothing in the tree references the file |
| `data/raw/usenet_probe2/`, `usenet_probe3/`, `usenet_probe4/` | empty | **Answered 2026-08-10: they are empty because they were successfully drained, and nothing was lost.** See below |
| `data/raw/usenet_bulk/` | 52 GB | Staging for the bulk Usenet download. Every one of its 9,266 archives is also in `data/raw/usenet/` and marked `.processed`, because `feed_usenet_bulk.sh` moves rather than copies and a retry re-downloaded on top of already-moved files. **The largest single reclaim available on the machine**, and it removes no unique data, but hash all 9,266 pairs before deleting rather than trusting the filename overlap |
| `data/raw/usenet_probe/`, `usenet_probe5/` | 42 MB, 2.2 GB | Same situation at smaller scale: 1 of 1 and 48 of 48 filenames also present in `data/raw/usenet/` and marked processed |
| `data/raw/pandora/` | 13 MB | A byte-identical second copy of `data/raw/pandora-titles/pandora-titles.csv`. The directory with the schema and the crawl documentation beside it is the one to keep |
| `data/reports/early_web_audit.csv`, `normalization_audit.csv` | 275 MB | July audit CSVs, predating roughly twenty-five sources. Both regenerate from the matching ingest. `package_delivery.sh` ships the whole of `data/reports/`, so leaving them means a phase-5 archive carries July audits |
| `data/ark.duckdb.pre-merged260810.bak` | 7.2 GB | The store as it stood before the `merged260810` baseline load. There is no unload command, so a baseline ingest is not reversible in place. **Delete once phase 5 has been reported**, the way the eight earlier `pre-*` copies were |

## Why the three probe directories are empty

They looked like a broken run and were not. `legacy/scripts/ingest_usenet_batched.sh` globs across
**all** `usenet_probe*/` directories into one queue and `mv`s archives into `data/raw/usenet/` in
batches of 400, because `ingest_new_usenet.sh` only reads that one directory. A `mv` out of a directory
updates the **source** directory's mtime, so 23:08:07, 23:20:14 and 23:42:29 are *removal* times, not
creation times. They are three of the nine "moving N archives" lines in `data/logs/usenet_batched.log`,
matching to the second, and that log ends:

```
2026-08-05 23:45:35 done: 4175 archives in data/raw/usenet, 4175 marked processed
```

Four independent checks that nothing was lost:

1. **Names.** All 3,479 archives the nine probe download logs recorded as fetched are on disk and in
   `.processed`, which `ingest_new_usenet.sh` writes only after both journal halves ingest cleanly.
2. **Bytes.** Every one of the 19,231 archives on disk matches its size in `data/raw/usenet_catalog.json`
   exactly, with zero mismatches, and there is no partial or `.tmp` file anywhere under `data/raw`.
3. **Log-independent.** Taking the union of every `fail` line in every file in `data/logs` gives 722
   unique group names; all of them are on disk except `alt.irc` and `alt.music.oasis`, which the host
   refused with HTTP 500 and 502 and which are the corpus's only two absent groups.
4. **Timings.** The 12 and 22 minute mtime gaps are ingest work, not backoff. Batch 1 took 12m07s
   because it carried the large `uk`, `aus` and `can` archives, and six further batches ran inside the
   22 minutes; a directory mtime records only the *last* removal.

Two hypotheses were excluded rather than merely not chosen. A zero-group probe run cannot have created
these directories, because `probe_usenet_groups.py` guards on `if not groups: raise SystemExit` **before**
its `mkdir`. And the one-shot `mv data/raw/usenet_probe*/*.mbox.zip` the research handback suggested
would have stamped all four directories with a single second, whereas the observed mtimes span three.

`usenet_probe/` keeps one file for a mundane reason: `comp.infosystems.www.misc.mbox.zip` was already in
`data/raw/usenet/` from 1 August, so the batched script's dedupe guard skipped it rather than moving it.
That is exactly the 3,479 downloaded against 3,478 queued discrepancy.

**They are inert. Deleting them is safe and re-running the drain over them is a no-op.**

## The instruments, which are not data and must not be pruned

Three artefacts are how the residual opportunity in every source gets priced. They look
like intermediate files and they are the measuring apparatus.

- **`data/queue.sqlite`** (352 MB): one row per fetch task, with its HTTP status and its
  transition through pending, in-flight and done or failed. It is the record of **which
  questions were asked, which failed, and which were never asked**, which is the whole
  of the reviewer's priority (a). Do not truncate it.
- **`data/raw/rdap/creation_years.csv`**: 6,510 network-derived creation years. Flagged
  in `docs/notes.md` as the only irreplaceable artefact in that directory, because
  re-deriving it means re-querying registries that now rate-limit harder.
- **`output/candidate_unverified.txt`** (35 MB) and **`output/seeds/`** (305 MB): the
  domains held with no year, and the hostname pool before it is collapsed to registered
  domains. The first is phase 5's work queue; the second is association material for the
  graph inference the reviewer asked for.
