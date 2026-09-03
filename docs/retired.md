# Retired code

One line per capability removed from the tree, so a later run knows it existed and why it went.
The code itself is recoverable from git by the commit named here.

- **The RDAP client** (`src/ark/rdap.py`, the `ark rdap` command, `tests/test_rdap.py`, the
  `rdap-batch` recipe): querying is closed for good on the registries' own terms, so bootstrap,
  routing, retries and journal writing had no caller left. `attested_years` and `RDAP_REDIRECTOR`
  stayed, in `src/ark/sources.py`, because `parse_rdap_snapshot` still replays the journals the
  client wrote. Removed in this commit.
- **The overnight hunt and the agent loop** (`just hunt-overnight`, `just agent-loop`,
  `just agent-loop-log` and the scripts behind them): both drove an unattended session from
  outside itself on a local deadline, and the fleet does that job now on a schedule with
  per-run telemetry. The recipes went in the phase-7 restructure and the runbook kept
  describing them for two days. Removed in this commit.
- **The standalone output-unit pack** (`scripts/output_unit_pack/`, 534 lines): a one-off pack
  built on 2026-08-31 to hand the reviewer a self-contained unit checker, which meant a second
  copy of `canonical.py`, of the public suffix list and of the English-share table. A second copy
  of a table is how two figures drift, and `tests/test_english_share.py` had to allowlist it.
  Removed in this commit; the allowlist entry went with it.
- **The laptop agent fan-out** (`scripts/harness/agent_fanout.sh`, `agent_watchdog.sh`, 590
  lines): drove several agents from one laptop shell before the fleet existed. The fleet runs
  waves with its own telemetry, so nothing called these. `pick_hypotheses.py` and
  `researcher_brief.py` stay, both on the fleet's invoked list. Removed in this commit.
- **The decision sheet** (`scripts/harness/decision_sheet.py`, its test and the page it
  generated, `decisions-open.md`, 364 lines): a third copy of the pending queue, after the
  `Decision: pending` blocks of `docs/approved-sources-list.md` and the open asks in
  `key-decisions.md`. No recipe called it. Removed in this commit; `key-decisions.md` now points
  at the register's own pending blocks.
- **Three VPS shell helpers** (`scripts/engines/pull_vps_journals.sh`, `vps_start_edge.sh`,
  `cdx_suffix_run.sh`, 280 lines): each retired by its own header comment or by
  `vps_bootstrap.sh`, and the journal rsync is inline in `just bank`. Nothing outside the three
  files named any of them. Removed in this commit.
- **The Yahoo directory collector** (`scripts/sources/directories/collect_yahoo_directory.py`
  and its test, 375 lines): the family was rejected at 7.73 EE and nothing called the collector.
  Removed in this commit.
- **Two one-shot fetchers** (`scripts/sources/directories/collect_dartmouth_bfs_seed.py`,
  `scripts/sources/registries/collect_namewinner_2001.py`, 152 lines): each ran once, and the
  bytes they fetched sit in `data/raw/dartmouth_bfs` and `data/raw/namewinner` with their refetch
  URLs in the register. Removed in this commit, which is what lifted the `xfail` on
  `test_every_script_has_a_caller`.
