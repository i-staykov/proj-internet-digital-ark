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
Channel): cron on each `ARK_HOSTS` machine of `local.env`, `target:lane` each
(`scripts/engines/cdx_walk_jobs.py`). A page's 1996 to 2001 rows land in `data/raw/cdx_suffix/`
and its 2002 to 2013 rows in `data/raw/extended/ia_cdx_hostnames/`; the tick pulls each lane's
home and re-ranks the queue by measured EE per request, and `local.env` exports
`ARK_BANK_JOURNAL_HOURS=1`, so each hour's journals bank that hour. `pause-platform` idles them.

**The tick** (`scripts/harness/scheduled_sync.sh`, or `just sync` by hand) opens no store. It
drains the Leg and Read runs, books a drain with no confirmed FIND, pulls each lane's finished
journals, and runs `just bank` when `scripts/harness/bank_trigger.py check` names what arrived: a
confirmed FIND or a drained read, a changed approvals page, a new baseline, an approved journal
the last bank could not fetch, or moved journals; the last two alone wait `ARK_BANK_JOURNAL_HOURS`.

**The bank** folds journals, exports the claim and gates; re-prices each confirmed FIND on the
store; ingests what was approved or decided and gates again; rebuilds `docs/ROUND.md`, commits,
pushes `live` and the snapshot, and writes each lead's fate to the fleet. A red writes
`data/logs/bank_red.json`, and after an approved ingest takes those rows out with
`scripts/harness/unbank_source.py`, except a source that held rows before the bank: its rows stay
and the red says so. Every tick then prints `BANK RED`. Read the red, run the lock block's export
and check, fix, then `uv run python scripts/harness/bank_trigger.py clear`.

**Standing admissions.** The fleet tests each ark-fleet `policy.json` `standing` clause;
`scripts/harness/standing_rule.py` writes the `Decision:` line citing itself, or parks it naming the clause; the line stands only if `ark check` passes after the
ingest. `scripts/harness/sync_approvals.py` files one `needs-owner` issue and one PR per park once
the asks together reach the gate; a merge (`AGENTS.md`, Git) approves one.

**The VM** (`ARK_VM` in `local.env`, over the VPN) runs the tick as the `ark-sync.timer` user
service from `~/ark`, firing only once `data/ark.duckdb` is there, its own lane the `local`
entry of its `ARK_HOSTS`, installed there and never from here, and the fleet's runners as
`ARK_FLEET_USER`, an ordinary user whose legs read the bank's staged snapshot by path
(ark-fleet `README.md`). `just vm install` sets it up from the laptop, `sudo -n` for the
packages, the fleet user and linger, printing the root command it needs when refused, and
runs the fleet's installer as that user with `RUNNER_TOKEN` from this shell on its stdin;
it refuses while the tick is held. `gh auth login` there (repo, workflow) is the owner's,
once. `just vm status|log` read it. The cutover, on the VPN: `just vm install`; `gh auth
login` on the VM; `RUNNER_TOKEN=<from the fleet's Settings, Actions, Runners> just vm
install` again, which registers the runners; `just hold on`; `just vm copy`; on the VPS as
its fleet user `systemctl --user disable --now ark-runner@{1..5}.service`; `just schedule
remove`; `just hold off`. The VM's first bank at :05 then reproduces the figures of
`docs/ROUND.md`, nothing having arrived, and stages the snapshot; a leg before it refuses
the missing snapshot and costs nothing. This checkout only pulls from then on.

**The hold.** `just hold` disables `com.ark.sync` and the VM's timer, writes `pause-platform` here and on each host,
and disables the fleet's `leg.yaml`, `read.yaml` and `improver.yaml`; `just hold status` shows
each name and `just hold off <name>` lifts one, or drops a name it does not know. It survives a
reboot; while it lists `com.ark.sync` the tick and the bank exit `held` and `just schedule
install` refuses. A dry run's hand tick passes it as `ARK_HOLD_BYPASS=dry-run just sync`, inline
for that one run. Right after `just hold off com.ark.sync`, run `just bank --force` by hand: with
no `data/logs/bank_stamp.json` the first tick fires every reason, and the converter's first pass
takes about an hour.

## Commands

| to | run |
|---|---|
| one pass of every check | `just cycle`, which only reports; `just state` rebuilds `docs/ROUND.md`, `--check` exits 1 when stale |
| measure a URL with no Python | `just probe probes/<x>.toml`: priceable, never dates a year |
| download | `uv run python scripts/harness/fetch.py <url> [--to <path>\|-]`, which enforces robots, `Retry-After` and caps |
| re-ask leads closed on reach | `just reprobe` |
| re-price a parked source | `just price` or `just price-hosts` before reopening it: its net-new falls as the store grows |
| raise a class decision | `just approve <spec> --journal <j>` writes the pending block |
| prove what is on disk | `just verify raw`, `just verify offsite --verify`; in a worktree, whose `data/` entries are links offsite refuses and whose `submissions/` has no tarballs, `scripts/round/verify_raw.py` and `offsite.py` take `--root <checkout> --table docs/registers/retention.md`; `just schedule status` for the hourly job |
| a bank prints APPROVED AND NOT BANKED | `uv run python scripts/harness/bank_approved.py --write` refetches and ingests them |
| retention | `just prune`; `just prune --round --write` removes only what has its proofs, a `data/ark.duckdb.pre-*.bak` once a later credited round is in `data/baseline.json`; a backup needs no Drive copy |
| triage a VPS scanner alert | its File and Malware panes first: a corpus path with `JS/Obfuscator`, `HTML/` or an era worm is expected; under `/home`, `/usr` or `/etc`, or a miner, backdoor or credential stealer, check `auth.log` for non-publickey logins, `ss -tulpn`, crontabs and recently modified units. A laptop alert: `docs/ops/security-posture.md` |

## Figures

`docs/ROUND.md` field 4 is the headline: the equivalent-English of the registrables and hostnames
that ship net-new against his 1996 to 2001 files, field 5 its percent of them. The gate's figures
are the two GATE lines beneath, each over his EE for its years: 1996 to 2001 (field 4) and 2002 to
2013 (`output/extended_years/`). The bank re-runs `scripts/round/extended_export.py` when
`data/raw/extended/<source>/` or his release moves, and a stale export withholds both. `just price
--items <f.jsonl>` is the fleet's figure on both parts, from `output/fleet_snapshot`, which `just
sync` rebuilds; it reads no store, so the bank re-prices a FIND on the store, where
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
   re-scores with his calculator, puts the archive, its `.sha256` and `MANIFEST.txt` in
   `gdrive:ark-submissions/<release>/` (`just ship drive`), closes the gate issue, and only then
   uploads and prunes verified round copies. It refuses while `just hold status` lists
   `com.ark.sync`. `just ship --help` prints the chain; `just ship orq` prints Word's page count.
   Away from a session, the owner labels an open ark-fleet issue `ship-now` and the next tick
   runs it once; with `ARK_SHIP_NOW=1` in `local.env` the gate issue opens so labelled.
3. `ship all` ran the README's checksum and `verify.sh` on a fresh extraction; follow the rest
   through tier 2, cold, outside the repository (`docs/round/delivery_readme.md`). `just ship report
   <archive.7z>` writes the report, its `.docx` and the mail draft with the Drive link; the edited
   `.docx` joins the archive by `rclone copy docs/report.docx gdrive:ark-submissions/<release>/`.
   Then send, once the round cleanup `ship all` runs last exited zero (else `just ship verify`
   until it does).

## Intake

Nothing of his enters the store. In the sync-lock script, this replaces the ingest and export lines:

```bash
just intake <his.zip>      # verify the sha256, extract, remeasure with his calculator, point baseline.json at the new marker, then `ark intake`
just reproduce deliver     # export, stats, check, then prune.py --round --write
uv run python scripts/round/round_figures.py --verify
uv run python scripts/round/extract_ding_docs.py --package <dir> --archive '<archive> (<date>)' --stamp <date>   # a task package only
```

`ark intake` checks each of his files once and writes `data/held/<marker>/` (`all.txt`,
`candidates.txt`, `held.json`, and a sorted copy of any file of his that is not sorted, unique and
lowercase), about 4.3 GB, dropping the previous release's. While those are missing or stale, export,
stats, seed and the pricers refuse and `ark check` FAILs, each naming `ark intake`. Export before
the check: a check after a new release but before the export flags every credited name. `ark stats`
prints the release it measured against, and `--verify` reading zero overlap proves the export diffed
against the new one; a round diffed against a stale release counts credited work as net-new. On
`just intake`, `--mail <file> --round <n> --received '<stamp>'` also writes his verdict's row in
`docs/registers/rounds.md`. Run it all in a worktree and PR `data/baseline.json`, `releases.md`,
`rounds.md` and the brief: until the checkout pulls them, its held sets name a release its JSON
does not, so its export and pricers refuse, naming `ark intake`.
