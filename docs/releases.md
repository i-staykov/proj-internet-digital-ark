# Releases

The reviewer reissues the merged 1996-2001 corpus after every round he accepts, and on most
days in between. One row per release he has named, oldest first.

- `released` is the date the marker encodes, the only date every release carries.
- `received` is `yes` when his zip or its extracted tree is on disk. Three markers he scored
  rounds against were intermediate merges he never sent; their row names the mail that quoted
  their totals and the received release that holds them.
- The year cells are `wc -l` over `1996.txt` to `2001.txt` of the extracted tree.
- `sha256` is of his zip where one exists, because his bytes are the artifact of record, and
  of our `zstd -19` tarball at `data/archive/<marker>.tar.zst` where none does: the five early
  releases were extracted and the zip discarded, so the tarball is the copy that leaves the
  machine. `merged260715-2` is the task's original corpus and lives in `legacy-data/`.

`pending` is a cell the script has not been able to measure yet; `none` is a cell nothing can
ever fill. `scripts/round/releases.py` fills the table from `feedback/` and `data/archive/`,
writes only the cells it can compute, and prints the `zstd` command for any tree that still has
neither zip nor tarball (`--zstd` runs it). The table, not the script, is the record: an
off-site copy is verified against these hashes.

<!-- releases:table -->
| marker | released | received | 1996 | 1997 | 1998 | 1999 | 2000 | 2001 | artifact | sha256 |
|---|---|---|---|---|---|---|---|---|---|---|
| `merged260715-2` | 2026-07-15 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260727` | 2026-07-27 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260730` | 2026-07-30 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260802-2` | 2026-08-02 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260810` | 2026-08-10 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260815` | 2026-08-15 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260817` | 2026-08-17 | not received: totals from the reviewer's mail of 2026-08-18, superseded by `merged260817-2` | none | none | none | none | none | none | none | none |
| `merged260817-2` | 2026-08-17 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260820` | 2026-08-20 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260821` | 2026-08-21 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260826` | 2026-08-26 | not received: totals from the reviewer's mail of 2026-08-27, superseded by `merged260827` | none | none | none | none | none | none | none | none |
| `merged260827` | 2026-08-27 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260827-2` | 2026-08-27 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260830` | 2026-08-30 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260901` | 2026-09-01 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260902` | 2026-09-02 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
| `merged260902-2` | 2026-09-02 | not received: totals from the reviewer's mail of 2026-09-02, superseded by `merged260902-3` | none | none | none | none | none | none | none | none |
| `merged260902-3` | 2026-09-02 | yes | pending | pending | pending | pending | pending | pending | pending | pending |
<!-- /releases:table -->
