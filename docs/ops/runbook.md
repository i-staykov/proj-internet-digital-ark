# Runbook

Rules: `AGENTS.md`, cited by name. Facts: `docs/lore/laws.md`. Fleet: ark-fleet `README.md`.

## When prompted, in this order

1. `just cycle` (the hook printed the brief); settle what it names that a program cannot decide.
2. Pick one lens (the `hunt-family` skill). Before any request, ask the disk: `just find <term>`,
   `just screen --dating <self|typed|undated> "<what the source is>"`, a grep of `data/raw/`.
3. Price what you find on both tracks, as Figures says (the brief, XIV; the `price-source` skill;
   `AGENTS.md`, The window). A candidate needs no approval: `uv run ark seed <file>` pools it.
4. Write the source's one `docs/registers/sources.md` row: its link and what dates one item.
   It banks through `just approve <spec> --journal <j>` and its `Decision:` line, then a hand
   ingest as "The sync lock" shows.
5. Replace the row with the result.

## Working in the checkout

- The main checkout stays on `live` (`AGENTS.md`, Git).
- The agent shell is zsh: an unquoted `$VAR` never splits; spell a list out, or use `${=VAR}`.
- The tick and the bank commit `docs/registers/` on the branch that is out and push `live`; their
  preflight refuses `main`, a diverged clone, any modified tracked file but `retention.md`,
  and an untracked file under `docs/registers/`, so leave no
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
when the walk's code or lane count changes (`scripts/engines/cdx_walk_jobs.py`). A page's 1996 to
2001 rows land in `data/raw/cdx_suffix/`, its 2002 to 2013 rows in
`data/raw/extended/ia_cdx_hostnames/`; the tick re-ranks the queue by measured EE per request,
and `local.env` exports
`ARK_BANK_JOURNAL_HOURS=1`, so each hour's journals bank that hour. `pause-platform` idles them.

**Runner lanes** (`.github/workflows/runner-lanes.yml`, `scripts/engines/runner_slices.py`): IA
throttles per address, so an hourly job on GitHub's runners walks one slice the bank cut
(`docs/registers/runner/slice_*.txt`; `cadence`, a one-line PR, keeps that many cut, the jobs an
hour plus one) from its own address and uploads the journals as an artifact; the tick banks them
as `runner0`, its row beside the lanes' in `data/logs/productivity.tsv` and the heartbeat. The
runners are one of the Channel's three clients: while `cadence` is set the bank host runs two
lanes, the first slice cut only once they do, and the third lane is back 90 minutes after the
runners' turn ends, the hour a job that read live before may still walk. GitHub's Additional
Product Terms for Actions tie use to the repository's own software project, which this
collection step is. Two stop signals: IA refusing, which the bank reads off a pulled log (a pause
of 15 minutes or more, or under 10% of 20 or more requests answered) and writes as
`docs/registers/runner/STOP`, every slice deleted and no job asking until a PR lifts it; and a
mail from GitHub about the runners' use (a
failed run's is not one), on which the owner runs `gh workflow disable runner-lanes.yml` and
zeroes `cadence` by PR.

**The tick** (`scripts/harness/scheduled_sync.sh`, or `just sync` by hand) opens no store. It
pulls each lane's finished journals, and runs `just bank` when `scripts/harness/bank_trigger.py check` names what arrived: a
changed approvals page, a new baseline, an approved journal the last bank could not fetch, or
moved journals; the last two alone wait `ARK_BANK_JOURNAL_HOURS`.

**The bank** folds journals, exports the claim and gates; ingests what was approved and gates
again; rebuilds `docs/ROUND.md`, commits,
pushes `live` and rebuilds `output/price_snapshot` for `just price`. A red writes
`data/logs/bank_red.json`, and after an approved ingest takes those rows out with
`scripts/harness/unbank_source.py`, except a source that held rows before the bank: its rows stay
and the red says so. Every tick then prints `BANK RED`. Read the red, fix, then `just red-clear`
(the lock, the export, the check, and the clear only on green). A triage run's restart and walk
go through `scripts/agents/triage.py`, whose header names their guards.

**The agent** (`ark-agent.timer` at :38; `just agent <mode>` by hand) is one run of
`scripts/agents/run_agent.sh` in one of four modes: `triage` hourly, `work` when the queue holds an item, `cdx` daily at 06 UTC and `scout` four times a day at 03, 09, 15 and 21 UTC (`agent/policy.json` `schedule`); its header says what a run is; its ledger is `data/logs/agent_runs.tsv`.

**Asks.** `scripts/harness/sync_approvals.py` files one `needs-owner` issue and one PR per
pending block once the asks together reach the gate; a merge (`AGENTS.md`, Git) approves one.

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
rebuilds; it reads no store, where `scripts/pricing/price_items.py` gives registrable grain and `just price-hosts <dir>` hostname grain. `LC_ALL=C comm -23` of a sorted corpus against `data/held/<marker>/all.txt` diffs against his
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

Nothing of his enters the store. His release comes by his mail; the owner downloads it to the
laptop, where intake runs, since his calculator outgrows the VM's memory (`docs/lore/laws.md`). In
a worktree there:

```bash
just intake <his.zip> [--sha256 <digest>]   # verify, extract, remeasure with his calculator, point data/baseline.json at the new marker, `ark intake`
uv run python scripts/round/extract_ding_docs.py --package <dir> --archive '<archive> (<date>)' --stamp <date>   # a task package only
```

then PR `data/baseline.json`, `releases.md`, `rounds.md` and the brief. A bank on a JSON whose
held sets are missing goes red, so: `just hold`, merge the PR, copy the zip to the VM, and in `~/ark`
there `git pull --ff-only`, the same `just intake` with the same flags (it finds his figures in the
JSON, skips the calculator and writes only the held sets), `rm -rf` the replaced release's `ding/`
tree, then `just hold off`.

`ark intake` checks each of his files once and writes `data/held/<marker>/` (`all.txt`,
`candidates.txt`, `held.json`, and a sorted copy of any file of his that is not sorted, unique and
lowercase), about 4.3 GB, dropping the previous release's. While those are missing or stale, export,
stats, seed and the pricers refuse and `ark check` FAILs, each naming `ark intake`. Export before
the check: a check after a new release but before the export flags every credited name; a round
diffed against a stale release counts credited work as net-new. His verdict's row in
`docs/registers/rounds.md` is `uv run python scripts/round/rounds.py --mail <file> --round <n>
--received '<stamp>'`.
