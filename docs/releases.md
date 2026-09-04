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
| `merged260727` | 2026-07-27 | yes | 721,671 | 1,354,970 | 1,226,197 | 1,939,757 | 1,497,895 | 2,913,997 | merged260727.tar.zst | 97238aa30230f507f19b0a23426db49602cfd2f29058c9fe4a952e376ca29ddd |
| `merged260730` | 2026-07-30 | yes | 722,785 | 1,360,891 | 1,241,155 | 2,007,588 | 1,710,945 | 3,220,268 | merged260730.tar.zst | be45b092c703d1964ce20901a93b9c03fab4134360b81394e2b31a93a15ea4ce |
| `merged260802-2` | 2026-08-02 | yes | 734,323 | 1,381,002 | 1,279,247 | 2,038,912 | 1,743,022 | 3,239,262 | merged260802-2.tar.zst | d3afc4a2892d02b02c67cde9d21b44cd7c66f1669198f9c33c7841d53941011e |
| `merged260810` | 2026-08-10 | yes | 759,624 | 1,440,158 | 1,456,208 | 2,299,385 | 1,994,624 | 3,412,035 | merged260810.tar.zst | 6631e5184b42dfc539bb9c37c81e731d183aea4878c03b42f7da33fd02aebb3e |
| `merged260815` | 2026-08-15 | yes | 761,196 | 1,458,027 | 1,672,543 | 3,250,749 | 4,873,520 | 3,412,472 | merged260815.tar.zst | 9357831a7bddf52743a3e285581029defce86c5a8aa8660be307b6e80245e445 |
| `merged260817` | 2026-08-17 | not received: totals from the reviewer's mail of 2026-08-18, superseded by `merged260817-2` | none | none | none | none | none | none | none | none |
| `merged260817-2` | 2026-08-17 | yes | 866,106 | 1,891,288 | 2,542,320 | 5,118,082 | 7,678,002 | 4,395,620 | Domain_Data_Collection_Task_0817_Update.zip | 7dd564e5a499679480671c2306074a704483f8f3b296a6d5f16cd4e0c422eceb |
| `merged260820` | 2026-08-20 | yes | 866,121 | 1,891,385 | 2,542,524 | 5,118,493 | 7,680,197 | 4,916,847 | Domain_Data_Collection_Task_0820_Update_v2.zip | d09ba50b3ab239506af4535a85a1d35a5cf3b8f88012178037829dd3c9f864d0 |
| `merged260821` | 2026-08-21 | yes | 866,121 | 1,891,386 | 2,542,561 | 5,118,649 | 9,670,871 | 4,975,393 | Domain_Data_Collection_Task_0821_Update.zip | bc5d8e244dfe9a5945f49d3b040d9151d307d9f4b6a7b8e1e67121d086a032f9 |
| `merged260826` | 2026-08-26 | not received: totals from the reviewer's mail of 2026-08-27, superseded by `merged260827` | none | none | none | none | none | none | none | none |
| `merged260827` | 2026-08-27 | yes | 964,009 | 2,040,555 | 2,997,600 | 5,946,477 | 9,837,612 | 5,366,066 | Domain_Data_Collection_Task_0827_Update.zip | db3451260defeedc06ff4091aaf5c4bcd4cef4beea9c1f5299bc054d1bab5b2f |
| `merged260827-2` | 2026-08-27 | yes | 966,755 | 2,077,481 | 2,999,788 | 5,953,365 | 9,852,923 | 5,383,547 | Domain_Data_Collection_Task_0827_UpdateV2.zip | 3f1853a1f7e8bdf3ba02f48d498e4b753d2778c51728a560befc09f40fd8ab00 |
| `merged260830` | 2026-08-30 | yes | 966,768 | 2,077,499 | 2,999,816 | 6,025,141 | 9,964,780 | 5,846,393 | Domain_Data_Collection_Task_0831_UpdateV2.zip | c29a7d8c58bf2c9ca57c4f399a47d99f18d6a5d263aea1f6bd3e4c6380d25347 |
| `merged260901` | 2026-09-01 | yes | 979,994 | 2,161,231 | 3,119,897 | 6,345,942 | 10,705,102 | 10,536,760 | Domain_Data_Collection_Task_0901_UpdateV2.zip | cef4252c942127920d7ad414da46179aeb12bfa9adc9db6e6cfeea4068b526a0 |
| `merged260902` | 2026-09-02 | yes | 980,829 | 2,176,285 | 3,158,358 | 6,469,427 | 10,993,896 | 12,893,608 | Domain_Data_Collection_Task_0902_Update.zip | 2abac74044921880e888681f5e451d4d57fff62fb125fa79b2fef6883802ba13 |
| `merged260902-2` | 2026-09-02 | not received: totals from the reviewer's mail of 2026-09-02, superseded by `merged260902-3` | none | none | none | none | none | none | none | none |
| `merged260902-3` | 2026-09-02 | yes | 1,005,048 | 2,225,880 | 3,291,631 | 6,717,097 | 11,328,087 | 14,669,545 | Domain_Data_Collection_Task_0902_UpdateV3.zip | 1add3cf239812259c152ebeb77bb1936f520ce83c9d4ae4ea6efab20be1532f9 |
| `merged260903-3` | 2026-09-03 | yes | 1,006,150 | 2,232,838 | 3,310,415 | 6,768,552 | 11,455,431 | 18,320,377 | Domain_Data_Collection_Task_0903_UpdateV3.zip | 47fa39c9fa00667bd9db5cdff69201be19ec78735c63a3314c29a68739078868 |
| `merged260904` | 2026-09-04 | yes | 1,006,242 | 2,233,960 | 3,313,711 | 6,777,836 | 11,490,583 | 18,413,465 | Domain_Data_Collection_Task_0904_Update.zip | 9b034ec5a9ea69a3affd6f7fe8c25153445c1fb3c60f11146e59a1e397b00e29 |
<!-- /releases:table -->
