# Retired code

One line per capability removed from the tree, so a later run knows it existed and why it went, and
does not rebuild it. The code itself is in git.

- **The RDAP client** (`src/ark/rdap.py`, `ark rdap`, `tests/test_rdap.py`, the `rdap-batch`
  recipe): querying is closed for good on the registries' own terms. `attested_years` and
  `RDAP_REDIRECTOR` stayed in `src/ark/sources.py`, because `parse_rdap_snapshot` still replays the
  journals the client wrote.
- **The sibling queue ranker** (`scripts/engines/rank_sibling_queue.py`): ranked the sibling RDAP
  queue by how long the base label lived, a 7.3-fold hit-rate split it measured itself. No queue is
  left to rank, and the candidate-pool headroom it fed measured 0.107 points, not the 1.47 once
  claimed.
- **The local admitter** (`just bank`'s opt-in `claude -p` leg, `scripts/harness/admit_prompt.txt`):
  woke a model on the laptop, which bills the laptop's own Claude login at API rates.
  `standing_rule.py` does the lookup instead and spends no tokens. `just bank` is now `just sync`.
- **The page-level English verification engine**: the reviewer replaced that standard with
  equivalent-English in August 2026. `domain_language` stays in `db.py` (documentation.md section 4).
- **The VPS collector scripts** (`restart_sweeps.sh`, `make_vps_bundle.sh`, `vps_bootstrap.sh`,
  `pull_vps_journals.sh`, `vps_start_edge.sh`, `cdx_suffix_run.sh`, `pull_suffix_loop.sh`): the CDX
  lane is the laptop's since 2026-09-09 (C-84), so a script whose purpose is to start a client on
  that host is a trap. Counting clients by the journal they hold open rather than by process
  survives as `local_clients()` in `scripts/harness/collectors.sh`; `just sync` pulls `cdx_suffix`
  and `maintain.sh` ingests it.
- **The laptop agent fan-out and the overnight hunt** (`agent_fanout.sh`, `agent_watchdog.sh`,
  `just hunt-overnight`, `just agent-loop`): drove unattended sessions from a local shell before the
  fleet existed. The fleet does it on a schedule with per-run telemetry.
- **The decision sheet** (`scripts/harness/decision_sheet.py` and `decisions-open.md`): a third copy
  of the pending queue, after `approved-sources-list.md`'s `Decision: pending` blocks and this
  repository's open asks.
- **The standalone output-unit pack** (`scripts/output_unit_pack/`): a self-contained unit checker
  for the reviewer, which meant a second copy of `canonical.py`, the public suffix list and the
  English-share table. A second copy of a table is how two figures drift.
- **The one-shot migrations and converters** (`admit_www_of_parent.py`,
  `apply_hostname_purpose_rule.py`, `assign_unassigned_evidence.py`, `convert_register.py`): each
  ran once against a store or a register filled before a rule the ingest and `ark check` now
  enforce. A future regression is a defect in the lane that wrote it, fixed there.
- **Three one-shot collectors** (`collect_yahoo_directory.py`, `collect_dartmouth_bfs_seed.py`,
  `collect_namewinner_2001.py`): the Yahoo family was rejected at 7.73 EE; the other two ran once
  and their bytes sit in `data/raw/` with refetch URLs in the register.
