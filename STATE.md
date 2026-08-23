# State, 2026-08-23 20:50Z (paused for tokens, wake 00:20Z / 02:20 CEST)

## Position
Gate **668,118 EE** (5% of `merged260821`, fixed until Ding reissues). Hold **372,772**. **Gap 295,347.**
Store accrues 2,553-4,152 EE/hour, so querying alone is 3-5 days. **Only a bulk dated corpus closes this.**

## Running, do not restart
2 RDAP workers, 1 CDX supervisor + worker, `maintain.sh`. Hourly cron `cccba25e` fires the hunt cycle.

## In flight, collect these first
- `w2zfevh5g` bulk-corpus-hunt: 9 untried artifact kinds (software release feeds, regulatory filings,
  award lists, ezines, hosting lists, domain market, library catalogues, academic supplementary, wildcard).
  Each must price net-new EE against the store. **Verify every number before acting.**
- `wp3qhqt60` hunt-new-sources: 3 verdicts still pending (LoC US Elections 2000, Netarkivet and Arquivo
  link graphs).

## Measured and closed tonight, do not retry
| candidate | net-new EE |
|---|--:|
| Dartmouth/NBER reopened (item answers again, payload already banked) | **0** |
| Zenodo banner ads | 433 |
| AFNIC `.fr` back editions (OPENDATA is a current-state snapshot, so back editions add nothing) | 782 |
| ODP alternate dump host `rdf.dmoz.org` | 0 in-window captures |
| Usenet mention promotion re-run | 163 |

**UKWA host linkage, C-30, re-probed and still shut.** Our copy is exactly 2147483648 bytes, a 2 GiB
replay cap rather than a network drop, so the other 18.9 GB is structurally unreachable. The resolved
capture `20200106181208id_` refuses ranged requests at transport level while a CDX control returns 200,
and the original host still serves a 159-byte stub. Worth ~1.1M EE if it ever opens: re-probe, do not
re-reason.

## Done tonight
- ~30,000 lines deleted: `docs/archive/`, `legacy/`, 3 handoffs, 24 one-shot scripts.
- `CLAUDE.md` 59 lines with a prompted hierarchy and a change-the-method-not-the-effort rule.
- Report template cut 363 -> 212 lines, architecture section 121 -> 50, collector table 38 -> 20 rows.
- Email fully generated from `docs/email-sections.md`; no hand-work left in the ship path.

## Open risks
- Archive is 1.9 GB against a ~1 GB target. `evidence.parquet` is 1.3 GB and 86% of it is the reviewer's
  own baseline returning to him. A consistent slice (drop baseline rows from BOTH `domain_year` and
  `evidence`) lands near 300 MB, but dropping one side alone broke tier-2 reproduction once, so the slice
  must be cut on both or not at all. Not attempted yet.
- `docs/sources.md` compression was discarded: 66 blocking fact losses, 4 blocking reproduction.
