# Sources

A four-row stand-in for the open register: one row with every cell filled, one row that
says nothing (`n/a` throughout), one whose dating clause and reopen condition are only in
its `## Detail` block, and one with an empty verdict cell, whose verdict word and empty
link have to survive being read out of its prose.

| source | version or date | coverage period | retrieval method | what dates one item | baseline overlap | net-new EE (date) | quality issues | effort | verdict | link |
|---|---|---|---|---|---|---|---|---|---|---|
| every_cell_filled | 2026-09-01 | 1999-2001 | ftp listing | the archive member's own mtime, machine-written | 41.2% already held | 1,234.5 EE (2026-09-01) | one mirror refused by name, so the walk is partial | 88 MB, 4 files | FIND | <https://example.org/tree/ls-lR.gz> |
| says_nothing | 2026-08-30 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| detail_carries_it | 2026-08-28 | 2001 | http download | n/a | n/a | 0 EE (2026-08-28) | n/a | n/a | n/a | <https://example.org/list.txt> [detail](#detail-carries-it) |
| blocked_by_robots | 2026-08-27 fleet 20260827T0101Z | 1996 | robots refusal | n/a | n/a | 0 EE (2026-08-27) | BLOCKED before any fetch: the host disallows us by name | n/a |  |  |

## Detail

### detail-carries-it

What dates one item: the page's own footer stamp, written by the CGI. Measured 0 EE
because every name on it is held at 2001 already. Reopen only if a 2002 edition turns up.
