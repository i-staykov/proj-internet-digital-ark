# Retired code

One line per capability removed from the tree, so a later run knows it existed and why it went.
The code itself is recoverable from git by the commit named here.

- **The local admitter** (`just bank`'s opt-in `claude -p` leg and `scripts/harness/admit_prompt.txt`):
  a model was woken on the laptop to decide whether a FIND could be approved, which billed the
  laptop's own Claude login at API rates and was off by default for that reason. S9 replaced the
  judgement with a lookup: `standing_rule.py` writes the `Decision:` line where Ivo's standing rule
  already authorises it and parks everything else for him. Removed in this commit, with `just bank`
  itself, which is now `just sync`.
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
  `Decision: pending` blocks of `docs/registers/approved-sources-list.md` and the open asks in
  `key-decisions.md`. No recipe called it. Removed in this commit; `key-decisions.md` now points
  at the register's own pending blocks.
- **The VPS collector restart** (`scripts/engines/restart_sweeps.sh`, 96 lines): stopped the two
  `ark-sweep` transient units and started as many as the two-client rule left, on the VPS. That host
  stopped collecting on 2026-09-09 (C-84) and its unit names exist nowhere else, so the script could
  only ever start a client that must not exist. Removed in this commit. What it defined and was worth
  keeping, counting clients by the journal they hold open rather than by process, is `local_clients()`
  in `scripts/harness/collectors.sh`; `extend_engines.sh` is the laptop's handover.
- **The second-machine bundle** (`scripts/engines/make_vps_bundle.sh`, `vps_bootstrap.sh`, 113
  lines): packed a shard list plus the journal history and started a supervisor on the VPS. The
  VPS stopped collecting on 2026-09-09 (ark-fleet S8): both CDX clients of C-77 are this
  laptop's, the fleet host runs research legs, and a script whose whole purpose is to start a
  third client there is a trap rather than a tool. Removed in this commit; the runbook's second
  machine section keeps the measurements that sized the split and points at `cdx_slot.sh` for the
  one thing a leg on that host may still ask.
- **Three VPS shell helpers** (`scripts/engines/pull_vps_journals.sh`, `vps_start_edge.sh`,
  `cdx_suffix_run.sh`, 280 lines): each retired by its own header comment or by
  `vps_bootstrap.sh`, and the journal rsync is inline in `just sync`. Nothing outside the three
  files named any of them. Removed in this commit.
- **The Yahoo directory collector** (`scripts/sources/directories/collect_yahoo_directory.py`
  and its test, 375 lines): the family was rejected at 7.73 EE and nothing called the collector.
  Removed in this commit.
- **Two one-shot fetchers** (`scripts/sources/directories/collect_dartmouth_bfs_seed.py`,
  `scripts/sources/registries/collect_namewinner_2001.py`, 152 lines): each ran once, and the
  bytes they fetched sit in `data/raw/dartmouth_bfs` and `data/raw/namewinner` with their refetch
  URLs in the register. Removed in this commit, which is what lifted the `xfail` on
  `test_every_script_has_a_caller`.
- **The register converter** (`scripts/round/convert_register.py`, 702 lines): the one-shot that
  rewrote 437 free-prose register entries into the eleven columns the ledger asks for, on
  2026-09-03, refusing to write unless every token of every entry survived into a row or a
  `## Detail` block. It has run, the register is in that shape, and running it again would
  re-convert what is already converted. The pre-conversion text is in this file's history and
  `bank_findings.py` now writes rows in the same eleven columns. Removed in this commit with
  its test, 131 lines, which pinned the conversion rather than the register.

- **The three one-shot store migrations** (`scripts/round/admit_www_of_parent.py`,
  `apply_hostname_purpose_rule.py`, `assign_unassigned_evidence.py`): each repaired a store
  filled before a rule the ingest and `ark check` now enforce, and each has run. `ark check` on
  2026-09-10 passes `a_www_record_has_its_own_evidence`, `a_bare_record_is_not_inferred_from_www`
  and `nothing_earned_is_left_unassigned` at 0 offending, so there is nothing left for them to
  find. A future regression is a defect in the lane that wrote it, to be fixed there rather than
  swept up afterwards. The decisions they carried out are still recorded in ADR-009, ADR-012 and
  `key-decisions.md`, which name these files as the thing that did it. Removed in this commit.
- **The sibling queue ranker** (`scripts/engines/rank_sibling_queue.py`): it re-ranked the
  generated sibling RDAP queue by how long the base label lived, a 7.3-fold hit-rate split it
  measured itself. The RDAP client was retired above, querying is closed on the registries' own
  terms, and the candidate-pool headroom it fed measured 0.107 points rather than the 1.47 once
  claimed. There is no queue left to rank. Removed in this commit.
- **The VPS suffix-journal puller** (`scripts/harness/pull_suffix_loop.sh`): it looped pull,
  ingest, sleep because `maintain.sh` rsynced `cdx_*` and not `cdx_suffix_*`, and 1,093 journals
  once sat on the VPS where no local pass could see them. Both halves of that gap are closed:
  `just sync` pulls `cdx_suffix` with the sweeper's open journals excluded, and `maintain.sh`
  ingests `data/raw/cdx_suffix/` on its fold loop. The collector lane also moved to the laptop,
  so there is nothing on the VPS to pull. Removed in this commit.
