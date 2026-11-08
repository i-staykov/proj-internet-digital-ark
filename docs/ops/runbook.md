# Runbook

Rules: `AGENTS.md`, cited by name. Facts: `docs/lore/laws.md`. Fleet: ark-fleet `README.md`.

## When prompted, in this order

1. `just cycle` (the hook printed the brief); settle what it names that a program cannot decide.
2. Pick one lens (the `hunt-family` skill). Before any request, ask the disk: `just find <term>`,
   `just screen --dating <self|typed|undated> "<what the source is>"`, a grep of `data/raw/`.
3. Price what you find on both tracks, as Figures says (the brief, XIV; the `price-source` skill;
   `AGENTS.md`, The window). A candidate needs no approval: `uv run ark seed <file>` pools it.
4. Write the source's one `docs/registers/sources.md` row: its link and what dates one item.
   A fleet find banks through the tick and the bank; your own through
   `just approve <spec> --journal <j>` and its
   `Decision:` line, then a hand ingest as "The sync lock" shows.
5. Replace the row with the result.

## Working in the checkout

- The main checkout stays on `live` (`AGENTS.md`, Git).
- The agent shell is zsh: an unquoted `$VAR` never splits; spell a list out, or use `${=VAR}`.
- The tick and the bank commit `docs/registers/` on the branch that is out and push `live`; their
  preflight refuses `main`, a diverged clone, any modified tracked file but `sources.md`,
  `sources-closed.md` and `queue.md`, and an untracked file under `docs/registers/`, so leave no
  edit there at :05. A refused tick banks nothing that hour: clean the tree (`git pull --rebase
  origin live` for a diverged clone), then `just sync`.
- A fresh clone has no store, so `database does not exist` or `Table with name ... does not exist`
  from `ark export` or `ark check` there is no invariant red. A worktree shares the checkout's
  store: its `data/` stays a directory holding its own tracked `baseline.json`, and every other
  entry of the checkout's `data/`, then `output`, `ding` and `local.env`, is linked in, so an
  intake commits `baseline.json` from the worktree and the checkout takes it on the pull.
- Read the registers through `just find <term>` (`--detail`: one approved entry) or the
  `register-reader` agent; `.claude/settings.json` denies reading `sources*.md`: append by heredoc.

## The sync lock

A reader blocks the writer (`docs/lore/laws.md`, Store). Anything that opens `data/ark.duckdb`
runs as one script between a take and a drop, so a failed step still drops the lock:

```bash
bash -c '
L=scripts/harness/sync_lock.sh
bash $L take $$ || exit                  # 3: a sync holds it, try later
trap "bash $L drop" EXIT; set -e
set -a; . ./local.env; set +a            # db.py reads ARK_DB_MEMORY_LIMIT only from the environment
just run ingest <spec> <journal>         # refuses under ARK_FREE_SPACE_GIB + ARK_WRITE_BUDGET_GIB free
just run export && just check data       # export always before check
'
```

When an output name may have been recycled, compare the ledger's sha256 with the bytes on disk
before ingesting or deleting anything.

**The gate** (`AGENTS.md`, Done): its store half is the block above. Once `bash
scripts/harness/sync_lock.sh holder` prints nothing, `git commit` runs the code half, the whole
suite with its output discarded, through the hook `just hooks` installs. A pytest, `ark check` or
commit beside it makes the hook refuse a green commit, and inside `just ship all` that aborts the
chain: commit alone, and rerun `uv run pytest -q -x > "$TMPDIR/pt.log" 2>&1; echo "exit=$?"`
alone, never through a pipe, before believing a refusal.

## The loop

**Collection.** `just walk install` keeps one lane per archive client running (`AGENTS.md`,
Channel): cron on the bank host, the `local` entry of its `ARK_HOSTS`, reinstalled by the tick
when the walk's code changes (`scripts/engines/cdx_walk_jobs.py`). A page's 1996 to 2001 rows
land in `data/raw/cdx_suffix/` and its 2002 to 2013 rows in `data/raw/extended/ia_cdx_hostnames/`;
the tick re-ranks the queue by measured EE per request, and `local.env` exports
`ARK_BANK_JOURNAL_HOURS=1`, so each hour's journals bank that hour. `pause-platform` idles them.

**The tick** (`scripts/harness/scheduled_sync.sh`, or `just sync` by hand) opens no store. It
pulls each lane's finished journals, and runs `just bank` when `scripts/harness/bank_trigger.py check` names what arrived: a
confirmed FIND or a drained read, a changed approvals page, a new baseline, an approved journal
the last bank could not fetch, or moved journals; the last two alone wait `ARK_BANK_JOURNAL_HOURS`.

**The bank** folds journals, exports the claim and gates; re-prices each confirmed FIND on the
store; ingests what was approved or decided and gates again; rebuilds `docs/ROUND.md`, commits,
pushes `live` and rebuilds `output/price_snapshot` for `just price`. A red writes
`data/logs/bank_red.json`, and after an approved ingest takes those rows out with
`scripts/harness/unbank_source.py`, except a source that held rows before the bank: its rows stay
and the red says so. Every tick then prints `BANK RED`. Read the red, fix, then `just red-clear`
(the lock, the export, the check, and the clear only on green). A triage run's restart and walk
go through `scripts/agents/triage.py`, whose header names their guards.

**The agent** (`ark-agent.timer` at :38; `just agent <mode>` by hand) is one run of
`scripts/agents/run_agent.sh` in one of four modes: `triage` hourly, `work` when the queue holds an item, `cdx` daily at 06 UTC and `scout` four times a day at 03, 09, 15 and 21 UTC (`agent/policy.json` `schedule`); its header says what a run is; its ledger is `data/logs/agent_runs.tsv`.

**Standing admissions.** The fleet tests each ark-fleet `policy.json` `standing` clause;
`scripts/harness/standing_rule.py` writes the `Decision:` line citing itself, or parks it naming the clause; the line stands only if `ark check` passes after the
ingest. `scripts/harness/sync_approvals.py` files one `needs-owner` issue and one PR per park once
the asks together reach the gate; a merge (`AGENTS.md`, Git) approves one.

**The VM** (`ARK_VM` in `local.env`, over the VPN) is set up from the laptop by `just vm install`,
`sudo -n` for the packages and linger, printing the root command it needs when
refused; it refuses while the tick is held. `just vm status|log` read it, status with the modes of
`hosts.yml` and `local.env`. `just vm token gh|claude` installs a token from stdin there and prints
the gh expiry or the agent pre-flight's answer. This checkout only pulls; it keeps no copy of the VM's data.

| on the VM | what |
|---|---|
| the login | `ark-sync.timer`: the tick and the bank from `~/ark`, once `data/ark.duckdb` is there; its lane is the `local` entry of `ARK_HOSTS`; `ark-agent.timer` once `~/.config/ark/agent.env` is there |
| secrets | `~/ark/local.env` and `~/.config/rclone/rclone.conf` at 600 (`scripts/harness/vm_install.sh`); gh's store, from `just vm token gh` with a fine-grained token: Contents and Issues read and write, Actions read, both repositories |
| an AV alert | hash the flagged file; a hit in a downloaded corpus is content and is kept; the detail goes under `private/security/` |

**The hold.** `just hold`, on the VM or from the laptop over `ARK_VM`, disables `ark-sync.timer`,
writes `pause-platform` here and on each host, and disables the fleet's `leg.yaml`, `read.yaml`
and `improver.yaml`; a `hold` label on an open ark-fleet issue does the same through the tick, the
timer left enabled so the tick reads the label's removal. `just hold status` shows each name and
`just hold off <name>` lifts one, or drops a name it does not know; `just hold off`, or the label
removed, lifts them all and starts `just bank --force` as `ark-bank-force` on the bank host (a
label still on holds again at the next tick). It
survives a reboot; while it lists `ark-sync.timer` the tick, the bank and the agent exit `held`,
and every collector stops asking within a page or a file. A dry run's hand tick passes it as
`ARK_HOLD_BYPASS=dry-run just sync`, inline for that one run.

## Commands

| to | run |
|---|---|
| one pass of every check | `just cycle`, which only reports; `just state` rebuilds `docs/ROUND.md`, `--check` exits 1 when stale |
| measure a URL with no Python | `just probe probes/<x>.toml`: priceable, never dates a year |
| download | `uv run python scripts/harness/fetch.py <url> [--to <path>\|-]`, which enforces robots, `Retry-After` and caps |
| re-ask leads closed on reach | `just reprobe` |
| re-price a parked source | `just price` or `just price-hosts` before reopening it: its net-new falls as the store grows |
| raise a class decision | `just approve <spec> --journal <j>` writes the pending block |
| prove what is on disk | `just verify raw`, `just verify offsite --verify`; in a worktree, whose `data/` entries are links offsite refuses and whose `submissions/` has no tarballs, `scripts/round/verify_raw.py` and `offsite.py` take `--root <checkout> --table docs/registers/retention.md`; `just vm status` for the hourly tick |
| a bank prints APPROVED AND NOT BANKED | `uv run python scripts/harness/bank_approved.py --write` refetches and ingests them |
| retention | `just prune`; the tick's `just prune --round --write` removes only what has proofs, a `data/ark.duckdb.pre-*.bak` once `data/baseline.json` credits a later round; backups need no Drive copy |
| triage a VM alert | a corpus path with an era worm is content; under `/home`, `/usr` or `/etc`, or a miner, backdoor or credential stealer: `auth.log` for non-publickey logins, `ss -tulpn`, `crontab -l` as both users, `systemctl --user list-units 'ark-*'` |

## Figures

`docs/ROUND.md` field 4 is the headline: the equivalent-English of the registrables and hostnames
that ship net-new against his 1996 to 2001 files, field 5 its percent of them. The gate's figures
are the two GATE lines beneath, each over his EE for its years: 1996 to 2001 (field 4) and 2002 to
2013 (`output/extended_years/`). The bank re-runs `scripts/round/extended_export.py` when
`data/raw/extended/<source>/` or his release moves, and a stale export withholds both. `just price
--items <f.jsonl>` is the snapshot's figure on both parts, from `output/price_snapshot`, which the bank
rebuilds; it reads no store, so the bank re-prices a FIND on the store, where
`scripts/pricing/price_items.py` gives registrable grain and `just price-hosts <dir>` hostname grain. `LC_ALL=C comm -23` of a sorted corpus against `data/held/<marker>/all.txt` diffs against his
names with no database, where `grep -Fxf` over his year files pins the CPU.

Draft findings into `docs/report.template.md` as they land; on the laptop, `just ship report
<archive.7z>` fills it from the archive's `audit/report_figures.json` with no store, into
`docs/report.md`, its `.docx` and the mail draft.

## Ship: the owner's procedure

The owner runs it (`AGENTS.md`, The owner decides; The window) once the gate issue,
labelled `needs-owner`, opens.

1. `just verify raw && just verify offsite --manifest && just verify offsite --upload --yes`.
   Nothing else uploads.
2. `just ship all` takes the sync lock, banks if anything arrived, exports in full, runs `ark check`,
   packages our additions alone (a stale or wrong export stamp refuses it), verifies as a reviewer would,
   re-scores with his calculator, puts the archive, its `.sha256` and `MANIFEST.txt` straight in
   `gdrive:ark-offsite/submissions/phase-N/` (`just ship drive`), closes the gate issue, and only then
   uploads and prunes verified round copies. It refuses while `just hold status` lists
   `ark-sync.timer`. `just ship --help` prints the chain; `just ship orq` prints Word's page count.
   Away from a session, the owner labels an open ark-fleet issue `ship-now` and the next tick
   runs it once; with `ARK_SHIP_NOW=1` in `local.env` the gate issue opens so labelled.
3. `ship all` ran the README's checksum and `verify.sh` on a fresh extraction; follow the rest
   through tier 2, cold, outside the repository (`docs/round/delivery_readme.md`). `just ship report
   <archive.7z>` writes the report, its `.docx` and the mail draft with the folder's link (sharing the
   folder stays with the owner); the edited `.docx` joins the archive by
   `rclone copy docs/report.docx gdrive:ark-offsite/submissions/phase-N/`. Then send, once the round
   cleanup `ship all` runs last exited zero (else `just ship verify` until it does).

## Intake

Nothing of his enters the store. The one step is the owner's: upload his zip or 7z and its
`<name>.sha256` to `gdrive:ark-offsite/releases/`. The next tick on the VM, after a green bank and
under the sync lock, copies it, checks the digest, runs `just intake` (extract, remeasure with his
calculator, point `data/baseline.json` at the new marker, `ark intake`, drop the release replaced),
transcribes a changed brief and pushes those pages and `releases.md` to `live`; the bank after it
re-exports (`scripts/harness/drive_intake.sh`). A mismatch, a failure, a zip with no digest or a VM
short of memory for his calculator is a `vm-alert`, and a failed upload waits for its line in
`data/logs/drive_intake.tsv` to go.

`ark intake` checks each of his files once and writes `data/held/<marker>/` (`all.txt`,
`candidates.txt`, `held.json`, and a sorted copy of any file of his that is not sorted, unique and
lowercase), about 4.3 GB, dropping the previous release's. While those are missing or stale, export,
stats, seed and the pricers refuse and `ark check` FAILs, each naming `ark intake`. Export before
the check: a check after a new release but before the export flags every credited name; a round
diffed against a stale release counts credited work as net-new. His verdict's row in
`docs/registers/rounds.md` is `uv run python scripts/round/rounds.py --mail <file> --round <n>
--received '<stamp>'`.
