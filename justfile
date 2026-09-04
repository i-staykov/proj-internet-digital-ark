# ark: the command set. `just` alone lists it.
#
# Thin wrappers over the `uv run ...` commands, so the ORDER is hard to get wrong.
# The raw commands stay the reproducibility contract, because they need nothing but
# uv installed; these recipes exist so nobody has to remember the sequence, not to
# hide what runs. docs/runbook.md is the long form: every command, and the output it
# should give.
#
# Quiet by default, so a session reading this output sees results and not shell.
#
# Eight recipes dispatch on their first argument rather than taking a name of their
# own: check, collect, engines, expand, reproduce, schedule, ship, verify. Each one
# prints its own choices when handed a word it does not know.

set quiet := true

# every recipe, plus the choices the dispatching ones take
help:
    just --list
    echo ""
    echo "Dispatching recipes:"
    echo "  just check <what>       all code data lint fmt test scan"
    echo "  just collect <source>   no source lists them"
    echo "  just engines <what>     status start stop"
    echo "  just expand <what>      round loop"
    echo "  just reproduce <stage>  all baseline sources candidates journals seeds deliver"
    echo "  just schedule <what>    install remove"
    echo "  just ship <stage>       all prep build package verify calculator docx draft"
    echo "  just verify <what>      raw trees delivery offsite"

# --- the environment ----------------------------------------------------------

# sync the locked environment (installs deps into .venv)
setup:
    uv sync

# Install the git hooks. The pre-commit hook runs the CODE gate and refuses a red
# commit, because the rule "never commit through a red gate" was written in
# CLAUDE.md and broken twice in one round: once by a pipe hiding pytest's exit
# status, once by a visible failure nobody acted on. Hooks live in hooks/ so they
# are versioned; .git/hooks is not.
#
# install the git hooks into .git/hooks
hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p .git/hooks
    for h in hooks/*; do
        n=$(basename "$h")
        ln -sf "../../hooks/$n" ".git/hooks/$n"
        echo "installed .git/hooks/$n -> hooks/$n"
    done

# run any CLI command directly, e.g. `just run stats` or `just run cdx --help`
run *args:
    uv run ark {{args}}

# --- validating ---------------------------------------------------------------

# On naming: `ark check` validates the DATA (the integrity invariants over the
# store) while the test suite validates the CODE. Naming either one plain "check"
# invites running one and believing the other passed, so each keeps its own word
# and the bare `just check` runs BOTH.
#
# `scan` is the last gate before tracked bytes are world-readable: secrets,
# routable addresses, local paths. The pre-commit hook and CI run that same command.
#
# validate: all (default) code data lint fmt test scan
check what="all":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{what}}" in
    lint) uv run ruff check . ;;
    fmt) uv run ruff format . ;;
    test) uv run pytest ;;
    scan) uv run python -m ark.hygiene ;;
    data) uv run ark check ;;
    code)
        uv run ruff check .
        uv run ruff format --check .
        uv run pytest
        ;;
    all)
        uv run ruff check .
        uv run ruff format --check .
        uv run pytest
        uv run ark check
        ;;
    *) echo "check: all code data lint fmt test scan" >&2; exit 2 ;;
    esac

# Prove what is on DISK, as opposed to the code or the store.
#
#   raw       checksum every local data entry and regenerate docs/retention.md. Writes
#             data/raw/<entry>/SHA256SUMS (untracked) plus a .stat sidecar, so a second
#             run hashes only files whose size or mtime moved; Usenet zips named in
#             usenet_catalog.json take IA's sha1 into SHA1SUMS instead of a rehash. A
#             path with no row in the table is not deletable. `--dry-run` says what a
#             run would hash and write, `--entry wwwvl` does one entry.
#   trees     prove an extracted release tree is recoverable from the artifact beside
#             it: every zip member compared to the file on disk by size and CRC-32,
#             without extracting anything. A tree it names byte-verified may be
#             deleted once the off-site copy exists.
#   delivery  check a built delivery the way a reviewer would: checksums, pair counts,
#             and that every shipped pair traces to an observation. Takes the
#             directory; `just ship` passes the newest stage rather than this default.
#   offsite   the off-site copy of what nothing else could bring back: our own
#             journals, the reviewer releases, the live inputs with no refetch route
#             and every unpriced corpus except the two Usenet ones archive.org serves
#             again. `--manifest` prices it and writes data/offsite-manifest.tsv,
#             `--upload` prints the rclone commands and `--upload --yes` runs them,
#             `--verify` compares the remote by hash without downloading and names
#             the entries safe to delete. Never deletes anything, either side.
#
# prove what is on disk: raw trees delivery offsite
verify what="" *args:
    #!/usr/bin/env bash
    set -euo pipefail
    set -- {{args}}
    case "{{what}}" in
    raw) uv run python scripts/round/verify_raw.py "$@" ;;
    trees) uv run python scripts/round/releases.py --verify-trees ;;
    delivery) bash scripts/round/verify_delivery.sh "${1:-output/internet-digital-ark-1996-2001}" ;;
    offsite) uv run python scripts/round/offsite.py "$@" ;;
    *) echo "verify: raw trees delivery offsite" >&2; exit 2 ;;
    esac

# --- where the round stands ---------------------------------------------------

# Assembled from the programs that own each figure rather than restating any of
# them: ark stats, round_figures.py, engine_status.sh, audit_residual.py and the
# open decisions. Nothing here is a second copy of a number, so it cannot drift.
# Pass --check to find out whether the file has gone stale: it compares the counts
# in its own footer against the store and exits 1 if the store has moved. The
# hand-written predecessor it replaces was accurate for exactly one day.
#
# regenerate docs/ROUND.md, the generated statement of where the round stands
state *args:
    uv run python scripts/round/build_round_state.py {{args}}

# Where the round stands in thirty lines, read from the snapshot that `just state`
# (so also `just cycle` and `just bank`) leaves in data/brief.json, plus
# private/handoff.md when the last session wrote one. Never opens the store or
# runs ssh, so a session-start hook can call it inside its timeout.
#
# where the round stands, read from the last snapshot rather than the store
brief:
    uv run python scripts/agents/brief.py

# The reviewer's first priority in one command: unprocessed files, globs that
# match too little, downloaded bytes with no parser, and derived lists a newer
# baseline has invalidated. Read-only, no network, and NOT a gate: it reports and
# exits 0, because unread material is a fact about the round rather than a broken
# invariant. Run it before deciding what to collect. It exists because the same
# diff, run by hand on 2026-08-10, found 496 ISC survey shards worth 14,956
# equivalent-English that had been on disk for five days.
#
# what is on disk that nothing has read, and what the documented path would miss
residual *args:
    uv run python scripts/harness/audit_residual.py {{args}}

# One pass of the harness: both collectors, unbanked journals, derived lists the
# store has outgrown, the hypothesis ledger, pending approvals, docs/ROUND.md. It
# rebuilds what it can and ends with the items no program can decide, which is the
# only part worth reading closely. Add --until EPOCH --every SECS to loop instead
# of running once, and --no-network to skip the re-probe, the only step that leaves
# the machine.
#
# check the round once and report what needs judgement
cycle *args:
    uv run python scripts/harness/discover_cycle.py {{args}}

# Drain the fleet's findings, admit any FIND, book everything, gate, push `live`, and
# refresh the VPS pricing snapshot. The one deliberate human-adjacent step of the loop
# (fleet plan, D3): run it whenever the laptop is open.
#
# drain the fleet's findings, admit, ingest, gate, push `live`
bank fleet="~/Documents/GitHub/ark-fleet":
    #!/usr/bin/env bash
    set -euo pipefail
    FLEET=$(eval echo {{fleet}})
    IN=data/fleet_findings/incoming
    mkdir -p "$IN" data/fleet_findings/banked data/logs
    PROCESSED=data/fleet_findings/processed_runs.txt; touch "$PROCESSED"
    command -v gh >/dev/null || { echo "needs gh"; exit 1; }
    # 0. Refuse a dirty or diverged clone before anything is fetched, then take the
    #    approvals merged from a phone as a fast-forward and bank what they approved.
    #    An ingest changes the store and no tracked file, so it is exported here and
    #    needs no commit.
    uv run python scripts/harness/bank_hygiene.py preflight
    BANKED=$(uv run python scripts/harness/bank_approved.py --write | tee /dev/stderr | grep -c '^== uv run ark ingest' || true)
    if [ "$BANKED" -gt 0 ]; then uv run ark export >/dev/null && uv run ark check | tail -1; fi
    # Anything still waiting on Ivo, first, so a bank never buries a decision.
    gh issue list --repo i-staykov/ark-fleet --state open --search "Approval needed" \
        --json title --jq '.[] | "AWAITING IVO: " + .title' 2>/dev/null || true
    # 1. Pull every unprocessed run's artifacts (findings + telemetry) from ark-fleet.
    gh run list --repo i-staykov/ark-fleet --limit 50 --status completed \
        --json databaseId --jq '.[].databaseId' | while read -r RID; do
        grep -qx "$RID" "$PROCESSED" && continue
        gh run download "$RID" --repo i-staykov/ark-fleet \
            --dir "$IN/run_$RID" >/dev/null 2>&1 || true
        echo "$RID" >> "$PROCESSED"
    done
    # Flatten: findings artifacts hold findings/*.md plus telemetry.json.
    LABEL=$(date -u +%Y%m%dT%H%MZ)
    find "$IN" -mindepth 2 -name '*.md' -exec mv -n {} "$IN/" \;
    # 2. The ledger row per telemetry file, then tidy.
    find "$IN" -mindepth 2 -name 'telemetry.json' | while read -r T; do
        python3 -c "import json,sys;d=json.load(open('$T'));print('$LABEL', d.get('tokens_in_plus_out',0), d.get('seven_day_pct','?'), sep='\t')" \
            >> data/logs/fleet_ledger.tsv || true
        rm -f "$T"
    done
    uv run python scripts/harness/bank_hygiene.py prune --write
    # Steps 3 and 4 need findings; 5 to 8 run on every bank, because the collectors
    # fill journals and the round can cross the gate with no fleet finding at all.
    if ! ls "$IN"/*.md >/dev/null 2>&1; then echo "nothing new to bank"; else
        # 3. Result lines first and pushed at once: a wave that picks while the admitter
        #    is still running (fifteen minutes on 2026-09-01) relaunched six settled slugs.
        uv run python scripts/harness/bank_findings.py "$IN" \
            --hypotheses "$FLEET/hypotheses.md" --run-label "$LABEL" --results-only
        (cd "$FLEET" && git add hypotheses.md && git commit -q -m "Result lines $LABEL" && git push -q) || true
        #    A FIND used to wake a model HERE, and that is how Ivo's personal account was
        #    being drained at API rates (2026-09-04). A local `claude -p` authenticates with
        #    the LAPTOP'S own Claude login, which is his Taktile account and has API pricing
        #    enabled; the fleet's workflows authenticate with `CLAUDE_CODE_OAUTH_TOKEN_PRIMARY`,
        #    the HPI account, which has limits and no API billing. So the same agent costs money
        #    in one place and consumes an allowance in the other, and this recipe was the one
        #    place where the token could not be chosen.
        #
        #    **Opt-in and off by default.** `just bank` still does everything else: drain the
        #    findings, write the result lines, run the scribe, gate, export and push. Admission
        #    is a model's judgement and belongs in the fleet, where the token is explicit.
        if grep -lE '^\s*verdict:\s*FIND' "$IN"/*.md >/dev/null 2>&1; then
            if [ "${ARK_LOCAL_ADMITTER:-0}" = "1" ]; then
                echo "FIND present: waking the LOCAL admitter (fable 5.1/medium)"
                echo "  NOTE: this bills the laptop's own Claude login, not the fleet's token."
                claude -p "$(cat scripts/harness/admit_prompt.txt)" --permission-mode auto \
                    --model claude-fable-5-1 --effort medium --output-format text \
                    > "data/logs/admit_$LABEL.log" 2>&1 < /dev/null || true
                tail -3 "data/logs/admit_$LABEL.log"
            else
                echo "FIND present, local admitter OFF: it would bill the laptop's own Claude"
                echo "  login at API rates. Set ARK_LOCAL_ADMITTER=1 to run it anyway, or let"
                echo "  the fleet admit it under the primary token."
            fi
        fi
        # 4. The deterministic scribe, then the gate, then one push.
        uv run python scripts/harness/bank_findings.py "$IN" \
            --hypotheses "$FLEET/hypotheses.md" --run-label "$LABEL"
        uv run ruff check . && uv run ruff format --check . && uv run pytest -q
        uv run ark export && uv run ark check
        git add docs/ src/ justfile 2>/dev/null || true
        git commit -q -m "Bank fleet findings $LABEL" || echo "register unchanged"
        git push -q origin live
        (cd "$FLEET" && git add hypotheses.md && git commit -q -m "Result lines $LABEL" && git push -q) || true
        mv "$IN" "data/fleet_findings/banked/$LABEL" && mkdir -p "$IN"
    fi
    # 5. Bring the VPS collectors' journals home and bank them: this replaced the
    # continuous pull loop when the laptop's role became episodic (fleet plan, D3).
    ROOT_FOR_ENV="$(pwd)"; [ -f "$ROOT_FOR_ENV/local.env" ] && . "$ROOT_FOR_ENV/local.env"
    : "${ARK_VPS:?set ARK_VPS}"
    rsync -a --ignore-existing "$ARK_VPS":/projects/proj-internet-digital-ark/data/raw/cdx/cdx_*.jsonl.gz data/raw/cdx/ || true
    uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz | tail -1 || true
    # the platform sweep's raw capture journals become hostname records (the second
    # unit, accepted 2026-09-01); idempotent per file. The registrable half goes
    # through cdx_suffix_convert.py by hand when a sweep completes, not per bank,
    # because the converter re-emits everything under a fresh tag on every run.
    # skip the journals a sweep still holds open: a half-copied one was once
    # ledgered at a third of its rows and had to be re-ingested by hand
    BUSY=$(ssh "$ARK_VPS" 'for p in $(pgrep -f cdx_suffix_sweep.py); do ls -l /proc/$p/fd 2>/dev/null | grep -o "suffix_[^ /]*jsonl.gz"; done; true' 2>/dev/null | sort -u)
    rsync -a --ignore-existing $(for b in $BUSY; do echo "--exclude=$b"; done) "$ARK_VPS":/projects/proj-internet-digital-ark/data/raw/cdx_suffix/suffix_*.jsonl.gz data/raw/cdx_suffix/ || true
    uv run ark ingest-hostnames data/raw/cdx_suffix/ | tail -1 || true
    # 6. Refresh the VPS pricing snapshot so the next wave prices against today.
    uv run ark export >/dev/null && uv run ark check | tail -1
    rsync -a output/netnew/ "$ARK_VPS":/projects/ark-data/netnew/ && echo "ark-data refreshed"
    uv run python scripts/round/round_figures.py | sed -n '5,7p'
    # 7. Refresh the brief snapshot; a failed refresh must not fail the bank.
    uv run python scripts/round/build_round_state.py | tail -1 || true
    # 8. The gate issue, once per crossing, read off the brief just written.
    uv run python scripts/harness/bank_hygiene.py gate --write || true

# The only route into the four register pages, and the cheap one: the deny in
# `.claude/settings.json` covers a `grep` or a `sed` on `docs/sources*.md`, and the two
# pages are 347 KB and 546 KB, so reading one spends the session's context on prose it
# never asked for. Every page is streamed a line at a time and one truncated line is
# printed per hit: page and line, source key, verdict, net-new EE, which shape the term
# sat in (row, detail, head, header, prose), and the matching text. A row is a projection
# of its entry, so a `detail` hit says the row does not carry what you asked about, and
# `--detail` is the only way to get that entry whole. Nothing prints over 40 lines
# without `--all`, and the suppressed count is stated. Exit 1 is "not in the register",
# exit 2 is "the search did not run", which are different answers.
#
# `just` splits recipe arguments, so a multi-word term goes to the script directly:
#     uv run python scripts/round/find.py "ftp listing"
#
#   just find iedr                            every hit, over all four pages
#   just find iedr_register --detail          that entry whole, capped at 40 lines
#   just find blocklist squidguard            hits under one source key
#   just find sources#ukwa_geoindex --detail  when one key names two entries
#
# search the four register pages, one truncated line per hit
find *args:
    uv run python scripts/round/find.py {{args}}

# The PreCompact hook writes private/handoff.md by itself. This is the same
# note by hand, from a transcript path, for a session being closed on purpose.
#
# write private/handoff.md from a transcript path
handoff transcript:
    printf '{"transcript_path": "%s", "trigger": "manual"}' '{{transcript}}' \
        | uv run python scripts/agents/handoff.py

# What filled the agent's context, read from the session transcript rather than a
# new log: the ten largest tool results with their tool, result bytes by tool,
# assistant text bytes and walls of text, and how often the session compacted.
# Records are deduplicated by uuid because resumed sessions copy earlier records
# into the new file. Newest transcript by default; give a path, or --all for one
# summary over every session. A diagnostic that may break on a harness upgrade,
# never a gate.
#
# measure what fills an agent's context from the newest transcript
context-report *args:
    uv run python scripts/agents/context_report.py {{args}}

# --- proposing and pricing a source -------------------------------------------

# The harness's working memory across sessions. `docs/sources.md` is the
# authoritative narrative and holds the ~60 verdicts the screener parses, but prose
# cannot carry STATUS, so it cannot answer what an unattended run asks every time it
# wakes up: what did I propose that I never finished pricing? `add` screens first and
# refuses a hypothesis with no dating claim; `close` prints the sources.md row to
# paste, so the two records cannot drift.
#
# NOTE: `just` splits recipe arguments, so a multi-word --verdict or --cost must go
# to the script directly: uv run python scripts/harness/hypothesis_ledger.py update ...
#
# the hypothesis ledger: proposed, priced, adopted or killed
hypo *args:
    uv run python scripts/harness/hypothesis_ledger.py {{args}}

# Does the proposal collide with one of the ~50 families already closed with a
# measurement, and what dates ONE of its items. The register is parsed out of
# docs/sources.md at run time rather than copied, so it cannot drift from the
# verdicts. Exits 2 if no dating claim is made, because a source whose items carry
# no date is seed-only and that decides what it can ever be. Example:
#   just screen --dating typed "1997 conference proceedings with affiliations"
#
# screen a source proposal against the closed register before it costs a request
screen *args:
    uv run python scripts/harness/screen_hypothesis.py {{args}}

# Turn a URL into a priceable journal from a TOML description, so a source can be
# measured before anyone decides whether it is worth a hand-written collector. Two
# of the last four sources considered were rejected on the number and never needed
# a parser at all, which is what this exists for. It refuses to guess a column, it
# reports what it threw away by reason, and its output has no ingest spec, so there
# is no path by which a probe can date a year (ADR-004). Then:
#   just price --items data/raw/probes/<name>.jsonl --label <name>
#
# price a source from a TOML description, writing no Python
probe spec *args:
    uv run python scripts/pricing/probe_source.py {{spec}} {{args}}

# Price a normalised {item, year, text} JSONL against the live store: net-new pairs
# and domains after the corroboration split, mean weight, a typo bound, and both a
# linear and a saturating projection with instructions to quote the lowest. Writes
# nothing. Only turning a source into dated items is source-specific; everything
# after that is this.
#
# price any dated corpus against the live store, writing nothing
price *args:
    uv run python scripts/pricing/price_items.py {{args}}

# The same question at the second accepted unit. `price` collapses every name to its
# registrable, which priced 180 suffix journals at 0 that were worth 301,650 EE in
# hostnames. This runs the ingest's own funnel over {url, timestamp} journals or
# --items JSONL and differences against hostname_year AND his baseline files, on a
# read-only connection, so a keep-until-priced corpus gets its number without the
# write lock.
#
# price a corpus at hostname grain against the live store, writing nothing
price-hosts *args:
    uv run python scripts/pricing/price_hostnames.py {{args}}

# A source class may not date a year until a human classifies it, and `ark ingest`
# enforces that rather than trusting anyone to remember. This writes the request:
# a seeded-random sample of real records with live links, the measured figures, and
# what the source is worth under each possible decision. The reviewer checks the
# links; the agent's argument is there to be checked, not believed. Candidate-only
# evidence needs no approval, since it can never date a year.
#
# ask a human to classify a source class before its records can date a year
approve *args:
    uv run python scripts/harness/request_approval.py {{args}}

# Ivo signs off the most promising source first, so the triage queue is kept in
# score order by a program rather than by anyone remembering. The judgement is in
# the `- potential:` line each entry declares; this only applies it. An entry with
# no score is a hard error, since a source that sorts to the bottom for want of a
# number is the one nobody ever looks at.
#
# sort the triage queue by declared potential, highest first
triage-rank *args:
    uv run python scripts/harness/rank_triage.py {{args}}

# Re-ask every source closed because something could not be REACHED, as opposed to
# closed because a measurement killed it. The register already names the hosts that
# failed, so this needs no new knowledge and no judgement: it extracts them from the
# verdict prose and asks again. A 200 is only reported as news when the verdict did
# not already predict one, because `ircache.net` answers today and the register says
# it "now serves a squatted blog".
#
# re-probe every availability-closed lead, and report only what changed
reprobe *args:
    uv run python scripts/harness/reprobe_closed.py {{args}}

# --- reproducing the result ---------------------------------------------------

# The whole result from an empty store, offline, in six stages. Needs the bulk
# sources in data/raw/ AND the supplied baseline in legacy-data/, since the annual
# masters are baseline plus additions and net-new is defined against it. Stages 1
# to 3 read the bulk files in data/raw/, stage 4 replays the journals the collectors
# already wrote, stage 5 rebuilds the hostname/URL seed pool, stage 6 writes and
# proves the deliverable. To collect NEW evidence, see the network recipes below.
#
# `just reproduce` runs all six in order; a stage name runs one.
#
# rebuild offline: all (default) baseline sources candidates journals seeds deliver
reproduce stage="all":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{stage}}" in
    all)
        for s in baseline sources candidates journals seeds deliver; do
            just reproduce "$s"
        done
        ;;
    # stage 1: create the stores, load the supplied baseline read-only (~2 min)
    baseline)
        uv run ark init
        uv run ark ingest-legacy
        uv run ark legacy-review
        uv run ark audit
        ;;
    # stage 2: ingest every bulk source already downloaded into data/raw/
    #
    # `arquivo_ia` is deliberately absent. `data/raw/arquivo/IA.cdxj` is 47 GB and was
    # deleted to reclaim disk once its 28,247 evidence rows were in the store, so its
    # evidence is present and its input file is not. Leaving the line in aborted this
    # whole stage on a missing file, which broke the reviewer-facing reproduction path.
    # To re-derive it rather than trust the store, download it first (the command is in
    # docs/sources.md) and run the commented line by hand. Same reason
    # `data/raw/checksums.sha256` verifies 234 files rather than 235.
    sources)
        uv run ark ingest early_web         data/raw/early_web/*.cdx.gz
        uv run ark ingest isc_survey        data/raw/isc_survey/*.gz
        uv run ark ingest internic_zone     data/raw/internic_zones/*.zone.gz
        uv run ark ingest internic_zone     data/raw/internic_zones/*.zone.*.gz
        # The nameserver TARGETS of the 1997 zones at hostname grain, admitted 2026-09-02
        # under the standing rule (11,860.7 EE). The 1999 tomocha files are deliberately
        # not listed: their terms are parked, see docs/approved-sources-list.md.
        uv run ark ingest-zone-hostnames data/raw/internic_zones/org.zone.gz data/raw/internic_zones/edu.zone.gz data/raw/internic_zones/gov.zone.gz data/raw/internic_zones/mil.zone.gz data/raw/internic_zones/root.zone.gz data/raw/internic_zones/arpa.zone.gz
        uv run ark ingest dartmouth_bfs_seed data/raw/dartmouth_bfs/*.cdx.gz
        # Admitted by the loop on 2026-09-01 under the standing rule: NYPW TimeMaps at
        # 4,146.8 EE post-split, 6,423 of its 6,424 pairs at 2001. The collector fetches
        # the three priced parts and flattens each tarball into one file:
        #   uv run python scripts/sources/nypw/collect_nypw_timemaps.py
        uv run ark ingest nypw_timemaps      data/raw/nypw_timemaps/*.cdx.gz
        # The non-200 lane of the same 34 files, admitted by the loop on 2026-09-01
        # under the standing rule. Ingest it AFTER the 200 lane above: that ordering
        # is what makes the store the control group for the relaxation.
        uv run ark ingest nypw_timemaps_nonok data/raw/nypw_timemaps/*.cdx.gz
        # `jpnic_register` was REJECTED by the reviewer, so `ark ingest` exits 2 and takes
        # the whole recipe with it. Left here, commented, because the artifact is on disk
        # and the next reader should see why it is not ingested rather than wonder.
        # uv run ark ingest jpnic_register   data/raw/jpnic_tomocha/domain-list.txt
        uv run ark ingest iedr_register     data/raw/iedr/*-doms.html
        uv run ark ingest us_domain_delegated data/raw/us_domain/*.txt
        uv run ark ingest squidguard_2001_blacklist data/raw/squidguard/*
        uv run ark ingest ripe_dbase_1999   data/raw/ripe_funet/ripe.db.gz
        uv run ark ingest ripe_dbase_changed data/raw/ripe_funet/ripe.db.gz
        uv run ark ingest ripe_dbase_split_2004 data/raw/ripe_funet_split/ripe.db.domain.gz
        uv run ark ingest namewinner_expiring data/raw/namewinner/*.tsv
        uv run ark ingest can_domain_registry_notices data/raw/can_domain/*.zip
        uv run ark ingest cctld_register_listing_inbody data/raw/cctld/*.html
        # Approved by Ivo on 2026-08-27: junkfilter at 2,189.4 EE and the Edelman whois
        # transcriptions at 2,968.5. The split step runs first because the ingest reads
        # its output, not the raw editions.
        uv run python scripts/sources/blocklists/split_junkfilter.py --write
        uv run ark ingest junkfilter_dated      data/raw/junkfilter/dated/*.txt
        uv run ark ingest junkfilter_candidates data/raw/junkfilter/cand/*.txt
        # Approved by Ivo on 2026-08-31: chastity-list at 14,229.0 EE, the largest single
        # source in the triage queue. Same shape as junkfilter, so the split runs first.
        uv run python scripts/sources/blocklists/split_chastity.py --write
        uv run ark ingest chastity_dated      data/raw/chastity/chastity-dated.*.txt
        uv run ark ingest chastity_candidates data/raw/chastity/chastity-cand.*.txt
        # Admitted by the loop on 2026-09-02 under the standing rule: the same two blocklists
        # read one level down, at hostname grain, 3,410.4 EE net-new. chastity's stamp is the
        # tar member header, so that lane reads the orig tarball rather than the unpacked tree.
        uv run ark ingest-blocklist-hostnames data/raw/squidguard/*
        uv run ark ingest-blocklist-hostnames data/raw/chastity/chastity-list_0.5.orig.tar.gz
        # Three more hostname-grain lanes admitted 2026-09-02 under the standing rule: the
        # nameservers RIPE domain objects point at (both FUNET editions), IA's Early Web index
        # re-emitted as capture journals, and the USFEDGOV-EXTRACT-2001 merged index reduced
        # to one capture per host (`scripts/sources/early_web/early_web_hostgrain.py`,
        # `scripts/sources/usfedgov/usfedgov_hostgrain.py`).
        uv run ark ingest-ripe-nserver-hostnames data/raw/ripe_funet/ripe.db.gz data/raw/ripe_funet_split/ripe.db.domain.gz
        uv run ark ingest-hostnames data/raw/early_web_hostgrain/ | tail -1 || true
        uv run ark ingest-hostnames data/raw/usfedgov_hostgrain/ | tail -1 || true
        # Two more admitted 2026-09-02: the USFEDGOV-EXTRACT 1996-2000 sibling indexes go
        # through the same hostgrain script into the same journal directory, and the ISC
        # survey per-TLD host files are read one level below the registrable `isc_survey` took.
        uv run ark ingest-isc-hostnames data/raw/isc_survey/wb_nw_*_*.gz | tail -1 || true
        # Admitted 2026-09-04 under the standing rule: the pipermail month files already on
        # disk for `maillist_dated`, read at hostname grain from their body URLs, 589.0 EE.
        uv run python scripts/sources/mail_corpora/build_maillist_pool.py data/raw/maillists data/raw/maillists_items 8
        uv run ark ingest-maillist-hostnames data/raw/maillists_items/ | tail -1 || true
        # Admitted 2026-09-04 under the standing rule: the CMU Enron release read at hostname
        # grain from its body URLs, the third member of the body-URL family. One 443 MB request.
        test -f data/raw/enron/enron_mail_20150507.tar.gz || curl -sS -L -A "internet-digital-ark research collector" -o data/raw/enron/enron_mail_20150507.tar.gz https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
        uv run python scripts/sources/mail_corpora/build_enron_pool.py data/raw/enron/enron_mail_20150507.tar.gz data/raw/enron_items
        uv run ark ingest-enron-hostnames data/raw/enron_items/ | tail -1 || true
        # Approved by Ivo on 2026-08-31 alongside chastity: Granite Canyon at 1,732.9 EE.
        # The collector runs first because the bytes are not kept in git.
        uv run python scripts/sources/registries/collect_granitecanyon.py
        uv run python scripts/sources/registries/split_granitecanyon.py --write
        uv run ark ingest granitecanyon_dated      data/raw/granitecanyon/granitecanyon-dated.*.txt
        uv run ark ingest granitecanyon_candidates data/raw/granitecanyon/granitecanyon-cand.*.txt
        # Approved by Ivo on 2026-08-31: the capture-dated ccTLD listings at 2,450.2 EE,
        # repriced from the bytes against a source register that claimed 3,496.0.
        uv run python scripts/sources/registries/collect_cctld_capture.py
        uv run python scripts/sources/registries/split_cctld_capture.py --write
        uv run ark ingest cctld_capture_dated      data/raw/cctld_capture/cctldcap-dated.*.txt
        uv run ark ingest cctld_capture_candidates data/raw/cctld_capture/cctldcap-cand.*.txt
        # Approved by Ivo on 2026-08-31: MYNIC at 6,883.1 EE and CO.ZA at 3,704.3. Neither
        # takes the split, since both are a registry reading out its own register.
        uv run python scripts/sources/registries/collect_mynic_coza.py
        uv run ark ingest mynic_change_report data/raw/mynic/*.htm
        uv run ark ingest coza_deletion_queue data/raw/coza/*.html
        # Approved by Ivo on 2026-08-31 at 1,403.2 EE post-split. NOT reproducible by a
        # collector: app.fac.gov is `User-agent: * / Disallow: /`, so the four census-<year>.zip
        # files must be downloaded BY HAND from https://www.fac.gov/data/download/historic/
        # and ELECAUDITHEADER.csv unpacked to data/raw/fac/header-<year>.csv.
        uv run python scripts/sources/mail_corpora/split_fac.py --write
        uv run ark ingest fac_dated      data/raw/fac/fac-dated.*.tsv
        uv run ark ingest fac_candidates data/raw/fac/fac-cand.*.tsv
        # Admitted by the loop on 2026-08-31 under the standing rule: the released Jeb Bush
        # gubernatorial mailbox at 3,546.1 EE (4,505 of its 5,692 pairs land at 2001) and a
        # domain broker inventory at 1,591.9 EE, all of it at 2001.
        uv run ark ingest jeb_mail_dated       data/raw/jeb_bush/jeb_mail_dated.jsonl.gz
        uv run ark ingest jeb_mail_candidates  data/raw/jeb_bush/jeb_mail_candidates.jsonl.gz
        uv run ark ingest urlmerchant_dated      data/raw/urlmerchant/urlmerchant_dated_b*.jsonl.gz
        uv run ark ingest urlmerchant_candidates data/raw/urlmerchant/urlmerchant_candidates_b*.jsonl.gz
        # Admitted under the standing rule of 2026-08-29: URLMerchant's for-sale inventory
        # at 1,591.9 EE post-split over 244 listing pages. The page collector outlives a
        # session, so a later batch takes its own `--tag` and its own pair of ingest lines.
        uv run python scripts/sources/directories/split_urlmerchant.py --tag b1 --write
        uv run ark ingest urlmerchant_dated      data/raw/urlmerchant/urlmerchant_dated_b1.jsonl.gz
        uv run ark ingest urlmerchant_candidates data/raw/urlmerchant/urlmerchant_candidates_b1.jsonl.gz
        # Admitted under the standing rule of 2026-08-29: Jeb Bush's gubernatorial mailbox
        # at 3,546.1 EE post-split. The extractor runs over the files unpacked from
        # JebBushEmails-Text.7z, which is 412 MB and not kept in git:
        #   curl -O https://archive.org/download/JebBushEmails/JebBushEmails-Text.7z
        #   7z x JebBushEmails-Text.7z -o<dir> 'Redacted/*'
        #   uv run python scripts/sources/mail_corpora/parse_jeb_mail.py --out-prefix data/raw/jeb_bush/jeb_bush \
        #       <dir>/Redacted/*.txt
        uv run python scripts/sources/mail_corpora/split_jeb_mail.py --write
        uv run ark ingest jeb_mail_dated      data/raw/jeb_bush/jeb_mail_dated.jsonl.gz
        uv run ark ingest jeb_mail_candidates data/raw/jeb_bush/jeb_mail_candidates.jsonl.gz
        uv run ark ingest early_bulk_whois_snapshot data/raw/edelman/*.html
        uv run ark ingest arquivo_roteiro   data/raw/arquivo/Roteiro.cdxj
        # uv run ark ingest arquivo_ia      data/raw/arquivo/IA.cdxj   # see above
        uv run ark ingest afnic_fr          data/raw/afnic/*NomsDeDomaineEnPointFr.csv
        uv run ark ingest internet_scout    data/raw/scout/scout_oai.xml
        uv run ark ingest odp               data/raw/odp/*.gz
        uv run ark ingest ukwa_link_source  data/raw/ukwa/host-linkage.tsv.gz
        uv run ark ingest ukwa_link_source  data/raw/ukwa/*-linkage.tsv
        uv run ark ingest ukwa_link_source  data/raw/ukwa/*-linkage.tsv.gz
        uv run ark ingest ukwa_link_target  data/raw/ukwa/host-linkage.tsv.gz
        # The BL geoindex extract. `ark ingest` refuses this until its `Decision:` line
        # is set in docs/approved-sources-list.md, so this line is a no-op until then and
        # is here so the documented reproduction is complete rather than nearly complete.
        # Build the input first with `bash scripts/sources/ukwa/ukwa_geoindex_pull.sh`.
        uv run ark ingest ukwa_geoindex     data/raw/ukwa/*_inwindow.tsv.gz
        uv run ark ingest ncsa_whats_new    data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv
        # These three were ingested by hand and reached 11.5% of all assignments while this
        # recipe, which README.md calls "the authoritative list of what gets ingested", did
        # not name them. Found on 2026-08-18 by auditing the delivery against D1.
        uv run ark ingest udrp_proceedings       data/raw/udrp/udrp_proceedings.jsonl.gz
        uv run ark ingest dartmouth_nber_captures data/raw/dartmouth_nber/domain-year-captures.txt
        uv run ark ingest domain_creation_bulk   data/raw/domain_creation/domains.csv
        ;;
    # stage 3: grow the candidate pool from the year-unlabelled host lists
    candidates)
        uv run ark seed data/raw/webbase/hosts.txt
        uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt
        uv run ark seed seeds/100hot_hosts.txt
        ;;
    # stage 4: replay the network journals already collected in data/raw/. This is
    # the reproduction path for the two network stages: it re-derives evidence from
    # the stored responses, so it needs no network and gives the same result every
    # time. To collect MORE, see the network recipes below.
    journals)
        uv run ark ingest cdx_snapshot  data/raw/cdx/cdx_*.jsonl.gz
        uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
        uv run ark ingest rdap_snapshot data/raw/rdap_gen/rdap_gen_*.jsonl.gz
        uv run ark ingest expansion_links     data/raw/expand/expand_*.jsonl.gz --round 1
        uv run ark ingest expansion_directory data/raw/expand/round2/expand_round2.jsonl.gz --round 2
        uv run ark ingest expansion_directory data/raw/expand/wwwvl/expand_wwwvl_corroborated.jsonl.gz --round 3
        uv run ark ingest expansion_links     data/raw/expand/wwwvl/expand_wwwvl_unverified.jsonl.gz --round 3
        uv run ark ingest expansion_directory data/raw/expand/round4/expand_round4_corroborated.jsonl.gz --round 4
        uv run ark ingest expansion_links     data/raw/expand/round4/expand_round4_unverified.jsonl.gz --round 4
        # Three directories, not one. The pools were added later and each wrote its
        # journals beside its own archives, so `data/raw/usenet/` alone reached 186 of
        # 1,064 ledgered files and the replay silently rebuilt a store without the rest.
        # The audit called all 1,798 of these "unreachable" and a hand reading of that
        # called them deleted; 1,759 of them were simply in a sibling directory.
        # One line per directory, because the residual audit reads the FIRST glob on an
        # `ark ingest` line and a backslash continuation is invisible to it. A glob it
        # cannot see is a glob nobody checks.
        uv run ark ingest usenet_dated        data/raw/usenet/usenet_dated*.jsonl.gz
        uv run ark ingest usenet_dated        data/raw/usenet_new/usenet_dated*.jsonl.gz
        uv run ark ingest usenet_dated        data/raw/usenet_de/usenet_dated*.jsonl.gz
        uv run ark ingest usenet_dated        data/staging/usenet_resplit/filtered/usenet_dated_resplit*.jsonl.gz
        uv run ark ingest usenet_candidates   data/raw/usenet/usenet_candidates*.jsonl.gz
        uv run ark ingest usenet_candidates   data/raw/usenet_new/usenet_candidates*.jsonl.gz
        uv run ark ingest usenet_candidates   data/raw/usenet_de/usenet_candidates*.jsonl.gz
        uv run ark ingest usenet_candidates   data/staging/usenet_resplit/filtered/usenet_candidates_resplit*.jsonl.gz
        uv run ark ingest tucows_dated        data/raw/tucows/tucows_dated.jsonl.gz
        uv run ark ingest tucows_candidates   data/raw/tucows/tucows_candidates.jsonl.gz
        # `_r2` is the second split of the recovered-address journals, run after the
        # extractor was widened. The first split is in the ledger but no longer on
        # disk; the second is a superset, so replaying it alone reconstructs the same
        # evidence. Regenerate with `just collect usenet-addresses`, which writes the
        # untagged names, then rename.
        # A glob rather than the one `_r2` file, because every later re-split writes its own
        # tagged pair and the split is now run on a loop. Named `_r*`, `_addr*` and `_cmp*`.
        uv run ark ingest usenet_addr_dated      data/raw/usenet_addr/usenet_addr_dated_*.jsonl.gz
        uv run ark ingest usenet_addr_candidates data/raw/usenet_addr/usenet_addr_candidates_*.jsonl.gz
        # The machine-written header seam. Same two source keys, because the headers
        # carry the same kind of claim as a typed address and no `usenet_hdr` spec
        # exists. Without these two lines a rebuild is 19,224 evidence rows short.
        uv run ark ingest usenet_addr_dated      data/raw/usenet_hdr/usenet_hdr_dated*.jsonl.gz
        uv run ark ingest usenet_addr_candidates data/raw/usenet_hdr/usenet_hdr_candidates*.jsonl.gz
        uv run ark ingest uucp_listing        data/raw/uucp/uucp_listing.jsonl.gz
        uv run ark ingest uucp_creation       data/raw/uucp/uucp_creation.jsonl.gz
        uv run ark ingest uucp_mentions       data/raw/uucp/uucp_mentions.jsonl.gz
        uv run ark ingest rtfm_dated          data/raw/rtfm/rtfm_dated.jsonl.gz
        uv run ark ingest rtfm_candidates     data/raw/rtfm/rtfm_candidates.jsonl.gz
        uv run ark ingest rtfm_dated          data/raw/rtfm/rtfm_dated_reextract.jsonl.gz
        uv run ark ingest rtfm_candidates     data/raw/rtfm/rtfm_candidates_reextract.jsonl.gz
        uv run ark ingest usenet_bare_dated      data/raw/usenet_bare/usenet_bare_dated*.jsonl.gz
        uv run ark ingest usenet_bare_candidates data/raw/usenet_bare/usenet_bare_candidates*.jsonl.gz
        # Registry whois records pasted into the bodies. The registry's own creation
        # line dates the row, not the post, so this is `whois_creation` and rule 6
        # gives that year alone. Regenerate with `just collect usenet-whois`.
        uv run ark ingest usenet_whois_dated      data/raw/usenet_whois/usenet_whois_dated*.jsonl.gz
        uv run ark ingest usenet_whois_candidates data/raw/usenet_whois/usenet_whois_candidates*.jsonl.gz
        # The promotion tranches, which live under `data/staging/` rather than `data/raw/`.
        # They were ingested and then unreachable from any documented glob, so a replay
        # rebuilt a store without them. They are regenerable by re-running
        # `build_promotion_journals.py`, but a reproduction path should not depend on that.
        uv run ark ingest enron_dated       data/staging/promotion/enron_dated_promoted_*.jsonl.gz
        uv run ark ingest maillist_dated    data/staging/promotion/maillist_dated_promoted_*.jsonl.gz
        uv run ark ingest rtfm_dated        data/staging/promotion/rtfm_dated_promoted_*.jsonl.gz
        uv run ark ingest tradepress_dated  data/staging/promotion/tradepress_dated_promoted_*.jsonl.gz
        uv run ark ingest tucows_dated      data/staging/promotion/tucows_dated_promoted_*.jsonl.gz
        uv run ark ingest usenet_dated      data/staging/promotion/usenet_dated_promoted_*.jsonl.gz
        uv run ark ingest usenet_addr_dated data/staging/promotion/usenet_addr_dated_promoted_*.jsonl.gz
        uv run ark ingest usenet_bare_dated data/staging/promotion/usenet_bare_dated_promoted_*.jsonl.gz
        uv run ark ingest attrition_dated     data/raw/attrition/attrition_dated.jsonl.gz
        uv run ark ingest enron_dated         data/raw/enron/enron_dated.jsonl.gz
        uv run ark ingest enron_candidates    data/raw/enron/enron_candidates.jsonl.gz
        uv run ark ingest maillist_dated      data/raw/maillists/maillist_dated.jsonl.gz
        uv run ark ingest maillist_candidates data/raw/maillists/maillist_candidates.jsonl.gz
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated.jsonl.gz
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates.jsonl.gz
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_reextract.jsonl.gz
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_reextract.jsonl.gz
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american.jsonl.gz
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american.jsonl.gz
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american_bare.jsonl.gz
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american_bare.jsonl.gz
        # The archived 1996-1997 Yahoo directory walk. Measured and rejected as a
        # route (55 requests bought 11 pairs), but its three journals were ingested,
        # so a rebuild without them is 670 records short of the store.
        uv run ark ingest expansion_directory data/raw/yahoo96/yahoo96_pilot1996_corroborated.jsonl.gz --round 5
        uv run ark ingest expansion_directory data/raw/yahoo96/yahoo96_fatpages1996_corroborated.jsonl.gz --round 5
        uv run ark ingest expansion_directory data/raw/yahoo96/yahoo96_expand_corroborated.jsonl.gz --round 5
        ;;
    # stage 5: rebuild the auxiliary seed pool, the hostnames and URLs that the
    # registered-domain counting unit drops. Reads the same source files again.
    seeds)
        uv run ark seed-pool isc_survey       data/raw/isc_survey/*.gz
        uv run ark seed-pool odp              data/raw/odp/*.gz
        uv run ark seed-pool internet_scout   data/raw/scout/scout_oai.xml
        uv run ark seed-pool ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz
        uv run ark seed-pool early_web        data/raw/early_web/*.cdx.gz
        ;;
    # stage 6: write the deliverable, then prove it. The order is not cosmetic:
    # `check`'s `additions_not_double_counted` invariant reads the exported annual
    # files, so running it before `export` compares this round's files against last
    # round's store and reports every already-credited pair as a violation. Export
    # first, always.
    deliver)
        uv run ark export
        uv run ark stats
        uv run ark check
        ;;
    *) echo "reproduce: all baseline sources candidates journals seeds deliver" >&2; exit 2 ;;
    esac

# tier 2: regenerate every result file from a provenance export instead, which
# needs no source data at all. About a minute, and byte-identical.
#
# tier 2: regenerate every result file from a provenance export
rebuild dir="output/provenance":
    uv run ark rebuild {{dir}}
    uv run ark check

# --- collecting more (network) ------------------------------------------------
# Each of these appends a journal to data/raw/ and writes no evidence, so they
# never hold the store's write lock and can run concurrently with each other.

# one archive-verification batch: which in-window years hold a capture
cdx-batch n="1200" workers="8":
    uv run ark gaps
    uv run ark cdx data/raw/cdx/gap_candidates.txt -n {{n}} --workers {{workers}} --timeout 70

# split the gap list across machines: disjoint by content hash, so no domain is
# ever queried twice and each slice keeps its share of the high-value head.
#
# split the gap list N ways for N machines (superseded by query-queue)
gap-shards n="2":
    #!/usr/bin/env bash
    set -euo pipefail
    for i in $(seq 0 $(({{n}} - 1))); do
        uv run ark gaps --shards {{n}} --shard "$i" --out "data/raw/cdx/gap_shard${i}.txt"
    done

# Supersedes running `gap-shards` and `build_pool_candidates.py` as two separate
# lists: the allocation between them was the expensive decision and it was being
# made by hand. Rebuild after a large ingest, since new evidence creates gaps as
# well as filling them, and a stale queue cannot reach what it does not list.
# With no argument it passes the measured weights and rates; `--dry-run` reports
# what the queue would return and writes nothing.
#
# one queue from both populations, best expected equivalent-English first
query-queue *args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "{{args}}" ]; then
        uv run python scripts/engines/build_query_queue.py --weights 78,22 --rates 916,262
    else
        uv run python scripts/engines/build_query_queue.py {{args}}
    fi

# the candidate pool instead of the gap pool: domains held with no year at all,
# so a capture adds a name rather than a year. Best English yield first, and the
# supervisor runs batches until the deadline epoch you give it.
#
# sweep the candidate pool at the archive, unattended until a deadline epoch
cdx-pool until batch="1200" workers="8":
    uv run python scripts/engines/build_pool_candidates.py
    bash scripts/engines/supervise_cdx_pool.sh {{until}} {{batch}} {{workers}} 900

# The CDX collectors on this machine.
#
#   status         what both engines are doing right now, and whether the VPS
#                  journals are home
#   start UNTIL    this machine's collector and the ingest loop, both detached, up
#                  to a deadline epoch: `just engines start $(date -u -v+12d +%s)`
#   stop           TERM to the supervisor runs its trap, which asks the batch to stop
#                  and lets it publish what it has: a stopped batch still writes its
#                  journal, so the only thing lost is the queries it had not made
#                  yet. Never `kill -9` here, that strands the `.part` and the work
#                  in it is unreachable.
#
# The standing hostname lane in one command (Ivo's priority, 2026-09-04). Two archive
# clients, which is the maximum: one walks the platforms we hold the FEWEST hosts under,
# one walks the high-weight suffix namespaces. The maintain loop folds both into the store
# as they write, so the lane needs no hand between starting it and reading the figures.
#
# `--net-new` on the ranker is the whole point: ranking by the hosts his benchmark carries
# asks "is this a real platform", and ranking by the hosts we LACK asks "what will the
# query add". With 13.7M hostname rows held those are different questions.
#
# start the hostname lane: two sweeps and the fold loop, to an absolute deadline
hostnames until:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python scripts/engines/rank_platform_parents.py --net-new \
        --out data/raw/cdx/platform_queue_netnew.txt --top 40
    nohup bash scripts/engines/platform_sweep.sh {{until}} \
        data/raw/cdx/platform_queue_netnew.txt > data/logs/platform_netnew.log 2>&1 < /dev/null &
    nohup bash scripts/engines/platform_sweep.sh {{until}} \
        data/raw/cdx/suffix_queue_r9.txt > data/logs/suffix_sweep.log 2>&1 < /dev/null &
    nohup bash scripts/harness/maintain.sh 420 24 > /dev/null 2>&1 < /dev/null &
    sleep 5
    echo "hostname lane started to $(date -r {{until}} '+%F %H:%M'); two clients, the maximum"
    pgrep -f cdx_suffix_sweep.py | wc -l | xargs echo "  sweep processes:"

# the CDX collectors: status start stop
engines what="status" *args:
    #!/usr/bin/env bash
    set -uo pipefail
    set -- {{args}}
    case "{{what}}" in
    status) bash scripts/engines/engine_status.sh ;;
    start)
        if [ $# -lt 1 ]; then echo "engines start UNTIL [batch] [workers]" >&2; exit 2; fi
        ARK_TARGETS=data/raw/cdx/queue_shard0.txt ARK_PREFIX=cdx_q0 \
            nohup caffeinate -i bash scripts/engines/supervise_cdx_pool.sh \
            "$1" "${2:-600}" "${3:-8}" 900 > /dev/null 2>&1 < /dev/null &
        nohup bash scripts/harness/maintain.sh 900 150 > /dev/null 2>&1 < /dev/null &
        sleep 5
        ps -eo pid,args | grep -E "supervise_cdx_poo[l]|maintain_phase[3]" || true
        ;;
    stop)
        pkill -TERM -f "supervise_cdx_pool[.]sh" 2>/dev/null || true
        pkill -TERM -f "maintain[.]sh" 2>/dev/null || true
        echo "waiting for the batch in flight to publish its journal"
        until ! pgrep -f "[a]rk cdx " >/dev/null && ! pgrep -f "[a]rk ingest" >/dev/null; do
            sleep 5
        done
        pkill -f "caffeinate -i bash scripts/supervise" 2>/dev/null || true
        echo "stopped; nothing left running:"
        ps -eo pid,args | grep -E "supervise_cdx_poo[l]|maintain_phase[3]|ar[k] cdx" || echo "  confirmed idle"
        ls data/raw/cdx/*.part 2>/dev/null && echo "WARNING: a .part was stranded" || echo "  no stranded .part files"
        ;;
    *) echo "engines: status start stop" >&2; exit 2 ;;
    esac

# Page expansion, the outbound-link route (brief section VII).
#
#   round SEEDS N  one round over a seed list, e.g.
#                  `just expand round seeds/expansion/seeds_round4.txt 5`. The split
#                  step is not optional: it keeps a curated page's transcription typos
#                  out of master evidence by demoting names no other source attests.
#   loop [D] [P]   one turn of the closed discovery loop: the engine's own hits become
#                  the next seed pages, their outbound domains become candidates, and
#                  the engine queries those in its turn. Unlike `round` no human picks
#                  the seeds, which is what stops this being a source that can run out.
#
# page expansion: round loop
expand what="" *args:
    #!/usr/bin/env bash
    set -euo pipefail
    set -- {{args}}
    case "{{what}}" in
    round)
        if [ $# -lt 2 ]; then echo "expand round SEEDS ROUND" >&2; exit 2; fi
        seeds="$1"; round="$2"
        uv run ark download "$seeds" -n 250 --workers 3 --captures 2 \
            --out "data/raw/expand/round${round}/expand_round${round}.jsonl.gz"
        uv run python scripts/engines/split_expansion_journal.py \
            "data/raw/expand/round${round}/expand_round${round}.jsonl.gz" --write
        uv run ark ingest expansion_directory \
            "data/raw/expand/round${round}/expand_round${round}_corroborated.jsonl.gz" --round "$round"
        uv run ark ingest expansion_links \
            "data/raw/expand/round${round}/expand_round${round}_unverified.jsonl.gz" --round "$round"
        ;;
    loop)
        uv run python scripts/engines/build_expand_seeds.py --recent 40 --domains "${1:-600}"
        stamp=$(date -u +%Y%m%dT%H%M%SZ)
        uv run ark download data/raw/expand/loop/seeds.txt -n "${2:-400}" --workers 2 \
            --delay 0.6 --captures 1 --out "data/raw/expand/loop/expand_${stamp}.jsonl.gz"
        uv run ark ingest expansion_links data/raw/expand/loop/expand_*.jsonl.gz --round 6
        ;;
    *) echo "expand: round loop" >&2; exit 2 ;;
    esac

# One loop rather than several, because DuckDB takes a single writer.
# fold everything the collectors have finished into the store, on a loop
maintain iterations="26" pause="900":
    bash scripts/harness/maintain.sh {{iterations}} {{pause}}

# --- the per-source collectors ------------------------------------------------

# One recipe, one source per invocation, dispatching to the same scripts each had
# its own recipe for. Each source is collect-then-split: the collector writes a
# journal and touches no database, the split sorts the journal into a dated half and
# a candidate half, and only then does anything reach the store. The split is the
# evidence wall for every free-text source, so it is not optional.
#
#   attrition                    the defacement mirror index, no request sent
#   enron                        the FERC corpus, dated per message
#   maillists                    public pipermail archives, dated per message
#   pandora-seed                 the PANDORA title index into the candidate pool
#   rtfm-faqs [tag]              the Usenet FAQ mirror, dated by revision header
#   trade-press [limit]          scanned computer magazines, dated by issue
#   trade-press-american [journal]
#   trade-press-reextract        re-read the cached OCR, no request sent
#   tucows                       software release dates plus the vendor's home page
#   usenet-addresses [mode] [workers]
#   usenet-bare [workers]        bare `foo.com` in the bodies
#   usenet-ingest [tag]          split and ingest whatever has finished downloading
#   usenet-measure ARCHIVES...   yield against the store BEFORE ingesting
#   usenet-whois [workers]       whois records pasted into the bodies
#   uucp-maps                    a .CA registry dump that travelled over Usenet
#
# run one per-source collector by name; no name lists them
collect source="" *args:
    #!/usr/bin/env bash
    set -euo pipefail
    set -- {{args}}
    case "{{source}}" in
    # Reads 33 index pages already on disk and sends no request. `artifact_listing`
    # and no corroboration split: the mirror saved a copy of the page at that host on
    # that date, so a name that did not resolve could not be in the index.
    attrition)
        uv run python scripts/sources/directories/collect_attrition.py --write
        uv run ark ingest attrition_dated data/raw/attrition/attrition_dated.jsonl.gz
        uv run ark seed data/raw/attrition/attrition_out_of_window_hosts.txt
        ;;
    # Pause `maintain` first: the extraction runs for minutes before it writes, and
    # it has no store-lock retry, so a maintain pass landing mid-run loses the work.
    enron)
        uv run python scripts/sources/mail_corpora/collect_enron.py --write
        uv run ark ingest enron_dated      data/raw/enron/enron_dated.jsonl.gz
        uv run ark ingest enron_candidates data/raw/enron/enron_candidates.jsonl.gz
        ;;
    # Harvest first, then parse: `--harvest` fetches about 2,600 month files from
    # two pipermail hosts, which takes six minutes and no archive.org budget.
    maillists)
        uv run python scripts/sources/mail_corpora/collect_mailing_lists.py --harvest --write
        uv run ark ingest maillist_dated      data/raw/maillists/maillist_dated.jsonl.gz
        uv run ark ingest maillist_candidates data/raw/maillists/maillist_candidates.jsonl.gz
        ;;
    # Seed-only and permanently so: the index carries no date column, so nothing in it
    # can evidence a year. 35,391 registrable domains, 29,432 of them unknown to the
    # store when measured on 2026-08-10. Expect pool growth and no annual-file growth:
    # a 60-domain sample on the AWA endpoint returned zero in-window captures.
    pandora-seed)
        uv run python scripts/sources/directories/seed_pandora_titles.py
        uv run ark seed data/raw/pandora-titles/pandora_hosts.txt
        ;;
    # Pass a tag on any re-run: it imports `probe_texts_corpus.domains_in`, so it
    # inherits that extractor's fixes, and the ledger refuses a rewritten journal.
    rtfm-faqs)
        tag="${1:-}"
        suffix=""; [ -n "$tag" ] && suffix="_$tag"
        uv run python scripts/sources/usenet/split_rtfm_faqs.py --write --tag "$tag"
        uv run ark ingest rtfm_dated      "data/raw/rtfm/rtfm_dated${suffix}.jsonl.gz"
        uv run ark ingest rtfm_candidates "data/raw/rtfm/rtfm_candidates${suffix}.jsonl.gz"
        ;;
    # Run --discover first: several plausible collection names do not exist and
    # silently return zero when queried with a collection: prefix.
    trade-press)
        uv run python scripts/sources/trade_press/collect_trade_press.py --discover
        uv run python scripts/sources/trade_press/collect_trade_press.py --limit "${1:-5000}"
        uv run python scripts/sources/trade_press/split_trade_press.py --write
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated.jsonl.gz
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates.jsonl.gz
        ;;
    # Both corpora are already worked and ingested; this is here to reproduce, not to
    # re-run. The collector writes a fresh timestamped journal, so pass its name to
    # the split. --tag keeps the ledger happy: tradepress_dated.jsonl.gz is taken.
    trade-press-american)
        journal="${1:-data/raw/tradepress/tradepress_20260808T172417Z.jsonl.gz}"
        uv run python scripts/sources/trade_press/collect_trade_press.py --limit 1400 --delay 0.6
        uv run python scripts/sources/trade_press/split_trade_press.py --journal "$journal" --tag american --write
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american.jsonl.gz
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american.jsonl.gz
        ;;
    # Sends no request: it re-reads the OCR under data/raw/texts/cache. Worth running
    # after any trade-press or rtfm collection, since both share the extractor that
    # used to drop bare two-label domains.
    trade-press-reextract)
        uv run python scripts/sources/trade_press/reextract_trade_press.py --write
        echo "now split the journal it names, with --tag reextract, then ingest both halves"
        ;;
    tucows)
        uv run python scripts/sources/directories/split_tucows.py --write
        uv run ark ingest tucows_dated data/raw/tucows/tucows_dated.jsonl.gz
        uv run ark ingest tucows_candidates data/raw/tucows/tucows_candidates.jsonl.gz
        ;;
    # mode=headers instead reads Message-ID, Reply-To, Sender and NNTP-Posting-Host.
    # The mode has to be threaded all the way through, because it changes the output
    # DIRECTORY as well as the extractor: `addresses` writes data/raw/usenet_addr and
    # `headers` writes data/raw/usenet_hdr. Passing it only to the collector, as this
    # once did, collected into one directory and then split and ingested the other, so
    # `mode=headers` silently re-ingested the address journals.
    usenet-addresses)
        mode="${1:-addresses}"; workers="${2:-10}"
        case "$mode" in
            addresses) dir=data/raw/usenet_addr; prefix=usenet_addr ;;
            headers)   dir=data/raw/usenet_hdr;  prefix=usenet_hdr  ;;
            *) echo "mode must be 'addresses' or 'headers'" >&2; exit 1 ;;
        esac
        uv run python scripts/sources/usenet/collect_usenet_addresses.py --mode "$mode" --workers "$workers"
        uv run python scripts/sources/usenet/split_usenet_addresses.py --in-dir "$dir" --out-prefix "$prefix" --write
        uv run ark ingest usenet_addr_dated      "$dir/${prefix}_dated.jsonl.gz"
        uv run ark ingest usenet_addr_candidates "$dir/${prefix}_candidates.jsonl.gz"
        ;;
    # Sends no request and takes about three hours of CPU at 8 workers. Run
    # `--sample 400` first if you want the projection before committing to it.
    usenet-bare)
        uv run python scripts/sources/usenet/collect_usenet_bare.py --workers "${1:-8}"
        uv run python scripts/sources/usenet/split_usenet_addresses.py --in-dir data/raw/usenet_bare --out-prefix usenet_bare --write
        uv run ark ingest usenet_bare_dated      data/raw/usenet_bare/usenet_bare_dated.jsonl.gz
        uv run ark ingest usenet_bare_candidates data/raw/usenet_bare/usenet_bare_candidates.jsonl.gz
        ;;
    usenet-ingest)
        bash scripts/sources/usenet/ingest_new_usenet.sh "${1:-auto}"
        ;;
    # The one source assessed without measuring first was estimated at 27,276 net-new
    # domains and measured at 53, so this is not optional caution.
    usenet-measure)
        uv run python scripts/sources/usenet/measure_usenet_yield.py "$@"
        ;;
    # Reads every archive in all five pools, so it takes about forty minutes of CPU
    # at 8 workers and sends no request. `ARK_USENET_SRC` picks the pool, because the
    # archives were downloaded into five directories and the default constant names
    # only the first, which is now empty.
    usenet-whois)
        for pool in usenet_bulk usenet_new usenet_probe usenet_probe5 usenet_msft; do
            [ -d "data/raw/$pool" ] || continue
            ARK_USENET_SRC="data/raw/$pool" uv run python scripts/sources/usenet/collect_usenet_whois.py \
                --workers "${1:-8}" --tag "$pool"
        done
        uv run python scripts/sources/usenet/split_usenet_whois.py --write
        uv run ark ingest usenet_whois_dated      data/raw/usenet_whois/usenet_whois_dated.jsonl.gz
        uv run ark ingest usenet_whois_candidates data/raw/usenet_whois/usenet_whois_candidates.jsonl.gz
        ;;
    # UUCP maps from comp.mail.maps: a .CA registry dump the Usenet parser read as prose
    uucp-maps)
        uv run python scripts/sources/usenet/split_uucp_maps.py --write
        uv run ark ingest uucp_listing  data/raw/uucp/uucp_listing.jsonl.gz
        uv run ark ingest uucp_creation data/raw/uucp/uucp_creation.jsonl.gz
        uv run ark ingest uucp_mentions data/raw/uucp/uucp_mentions.jsonl.gz
        ;;
    "")
        echo "collect <source> [args]. Sources:"
        echo "  attrition enron maillists pandora-seed rtfm-faqs trade-press"
        echo "  trade-press-american trade-press-reextract tucows usenet-addresses"
        echo "  usenet-bare usenet-ingest usenet-measure usenet-whois uucp-maps"
        echo "Arguments and what each one reads: docs/runbook.md"
        ;;
    *) echo "collect: no source called '{{source}}'; run 'just collect' for the list" >&2; exit 2 ;;
    esac

# --- retention ----------------------------------------------------------------

# Fill docs/releases.md from what is on disk: per-year line counts of every extracted
# release tree under feedback/, the sha256 of the reviewer's zip where one exists and
# of our data/archive/<marker>.tar.zst where it does not. Writes only the cells it can
# compute, so a hash outlives the zip leaving the machine. `just releases --zstd`
# packs the zip-less trees first; `--refresh` recounts and rehashes everything.
#
# fill docs/releases.md from the release trees on disk
releases *args:
    uv run python scripts/round/releases.py {{args}}

# Take one reviewer release: verify the zip's sha256 and record it, extract it beside the
# other releases, count the year files, remeasure them with his own calculator, point
# data/baseline.json at the new marker and refresh docs/releases.md. With --mail it also
# writes the round's row in docs/rounds.md. Every figure comes from the extracted files,
# never from his mail. Every step prints its wall time; a second run on the same zip
# changes nothing; --dry-run says what it would do; a marker already recorded under a
# different sha256 stops the run. It does NOT load the release into the store: that stays
# a separate deliberate `ark ingest-legacy` step.
#
# take one reviewer release: verify, extract, remeasure, record
intake *args:
    uv run python scripts/round/intake.py {{args}}

# Write a round's row in docs/rounds.md from the reviewer's verdict mail: his five
# figures parsed, S and t computed from the two stamps rather than read off the mail,
# and a benchmark he never sent marked not received. Pass the mail, the round label
# and the receipt stamp in his clock, e.g.
# `just rounds --mail private/mail/verdict7.txt --round 7 --received "2026-09-02 05:50"`.
#
# write a round's row in docs/rounds.md from his verdict mail
rounds *args:
    uv run python scripts/round/rounds.py {{args}}

# What the retention table says could be deleted, grouped by the conjunction that
# makes it safe, and what everything else is missing. Deletes nothing: no flag does.
#
# what could be deleted, grouped by the conjunction that makes it safe
prune *args:
    uv run python scripts/round/prune.py {{args}}

# --- shipping -----------------------------------------------------------------

# The round-end sequence, in the one order that works, as one recipe.
#
# `package_delivery.sh` refuses unless output/ matches the store EXACTLY, and the
# store moves every time the ingest loop banks a journal, which is every few minutes.
# So a hand-run `ark export && just ship package` races and refuses, and discovering
# that at 22:00 on the evening a round ships is the wrong time.
#
# Only the INGEST loop has to pause: collectors writing journals do not move the
# store, so they keep running and their work banks afterwards. Nothing is lost by
# stopping maintain.sh, since journals are ledgered by content hash and re-offering
# an ingested one is skipped in milliseconds.
#
# **Safe to rehearse with nothing decided.** `bank_approved.py` reports and SKIPS
# anything still pending, so running the chain before a decision arrives changes no
# verdict and still exercises every later step: the evening a round ships is the worst
# time to discover the packaging path is broken. `just ship --help` prints the chain
# and runs none of it, and `just ship draft` prints the mail it would send without
# writing it.
#
#   all [round]     the whole chain: bank the approved, regenerate the report and the
#                   .docx, quiesce ingestion, export, the invariants, package, verify
#                   the delivery as a reviewer would, re-check with his own
#                   calculator, write the mail draft, close the gate issue
#   prep            drain the platform sweeps into the store and stage the round for
#                   approval: pull journals from the VPS, ingest both output units,
#                   convert this month's sweeps' registrable half, export, gate,
#                   refresh the merge audit, print the figures
#   build [round]   the middle of the chain alone: pause ingestion, export, the
#                   invariants, regenerate and commit the report, package, verify
#   package [round] the archive alone, into submissions/<round>/
#   verify          the built delivery, from the newest stage directory
#   calculator      the reviewer's own calculator over the built files
#   docx SOURCE     one markdown report into the .docx he asks for
#   draft           print the mail draft; add --write to save it under private/
#
# ship the round: bank, export, gate, package, verify, draft the mail
ship stage="all" *args:
    #!/usr/bin/env bash
    set -uo pipefail
    set -- {{args}}

    # Restart the ingest loop whatever happens, including a failed package. The first
    # rehearsal of this recipe failed at the report guard and left ingestion dead; it
    # was noticed only because somebody was watching, and on the evening a round ships
    # nobody is. The continuous laptop loop retired when the fleet took over
    # (2026-09-01): restart it on exit ONLY if it was running when ship began.
    WAS_RUNNING=$(pgrep -f 'maintain[.]sh' >/dev/null && echo yes || echo no)
    restore() { [ "$WAS_RUNNING" = yes ] && ! pgrep -f 'maintain[.]sh' >/dev/null && \
        (nohup bash scripts/harness/maintain.sh 900 150 >/dev/null 2>&1 & echo "== ingest loop restarted ==") || true; }

    newest_stage() { ls -dt output/DomainDataCollectionTask_*_IvayloStaykov 2>/dev/null | head -1; }

    stage_prep() {
        source local.env
        # skip the journals a sweep still holds open: a half-copied one was once
        # ledgered at a third of its rows and had to be re-ingested by hand
        BUSY=$(ssh "$ARK_VPS" 'for p in $(pgrep -f cdx_suffix_sweep.py); do ls -l /proc/$p/fd 2>/dev/null | grep -o "suffix_[^ /]*jsonl.gz"; done; true' 2>/dev/null | sort -u)
        rsync -a --ignore-existing $(for b in $BUSY; do echo "--exclude=$b"; done) "$ARK_VPS":/projects/proj-internet-digital-ark/data/raw/cdx_suffix/suffix_*.jsonl.gz data/raw/cdx_suffix/ || true
        rsync -a --ignore-existing "$ARK_VPS":/projects/proj-internet-digital-ark/data/raw/cdx/cdx_*.jsonl.gz data/raw/cdx/ || true
        uv run ark ingest-hostnames data/raw/cdx_suffix/ | tail -1
        uv run python scripts/engines/cdx_suffix_convert.py --glob 'data/raw/cdx_suffix/suffix_*_202609*.jsonl.gz' --tag "platforms$(date -u +%Y%m%dT%H%M)"
        uv run ark ingest cdx_snapshot data/raw/cdx/cdx_suffix_platforms*.jsonl.gz | tail -1 || true
        uv run ark ingest cdx_snapshot data/raw/cdx/cdx_vedge_*.jsonl.gz data/raw/cdx/cdx_gaploc_*.jsonl.gz | tail -1 || true
        uv run ark export | tail -1
        uv run ark check | tail -1
        uv run python scripts/round/merge_against_baseline.py | tail -3
        uv run python scripts/round/round_figures.py | head -13
    }

    stage_build() {
        trap restore EXIT
        set -e
        echo "== pausing the ingest loop so the store stops moving =="
        pkill -f 'maintain[.]sh' 2>/dev/null || true
        until ! pgrep -f '[a]rk ingest' >/dev/null; do echo "  waiting for an ingest in flight"; sleep 10; done
        echo "== exporting =="
        uv run ark export
        echo "== the data invariants =="
        uv run ark check
        # `package_delivery.sh` regenerates the report and refuses if it changed, so a
        # human reviews the diff. Doing it here instead makes this a single pass: the
        # diff is by construction nothing but regenerated figures, and committing it
        # leaves exactly the same reviewable record in git history.
        echo "== regenerating the round report =="
        uv run python scripts/round/fill_report.py
        if ! git diff --quiet -- docs/report.md; then
            git --no-pager diff --stat -- docs/report.md
            git add docs/report.md
            git commit -q -m "Regenerate docs/report.md from the store before packaging"
            echo "== committed the regenerated report =="
        fi
        echo "== packaging =="
        bash scripts/round/package_delivery.sh "${1:-}"
        echo "== verifying the built delivery the way a reviewer would =="
        # The directory is passed explicitly. `verify_delivery.sh` defaults to its own
        # location, which is correct when it ships INSIDE a delivery and wrong when it is
        # run from this repository: the fourth rehearsal built a valid 1.4 GB archive and
        # then reported "additions/1996.txt is missing", because it had verified the
        # scripts/ directory rather than the delivery.
        # The stage name carries the mandatory submission stamp since 2026-09-01, so
        # resolve the newest one rather than hardcoding (a hardcoded path once verified
        # the PREVIOUS round's stage and reported its figures as this round's).
        bash scripts/round/verify_delivery.sh "$(newest_stage)"
    }

    # Close the gate issue only on a delivery that has been verified, and only when
    # one is open: `bank` latches it once per crossing, so a second close would be a
    # second notification for the same round.
    close_gate_issue() {
        if ! command -v gh >/dev/null 2>&1; then echo "no gh on PATH: gate issue left open"; return 0; fi
        local n
        n=$(gh issue list --repo i-staykov/ark-fleet --state open --search "in:title Round" \
            --json number,title --jq '.[] | select(.title | test("^Round [0-9]+ at ")) | .number' \
            2>/dev/null | head -1)
        if [ -z "$n" ]; then echo "no open gate issue to close"; return 0; fi
        if [ "${1:-}" = "--dry-run" ]; then echo "would close gate issue #$n"; return 0; fi
        gh issue close "$n" --repo i-staykov/ark-fleet --comment "Shipped and verified." \
            && echo "closed gate issue #$n"
    }

    case "{{stage}}" in
    -h|--help|help)
        echo "just ship <stage> [args]"
        echo "  all [round]      bank the approved, regenerate the report and the .docx,"
        echo "                   pause ingestion, export, the invariants, package, verify"
        echo "                   the delivery, the reviewer's calculator, the mail draft,"
        echo "                   then close the gate issue"
        echo "  prep             drain the sweeps, ingest, export, gate, merge audit, figures"
        echo "  build [round]    pause ingestion, export, invariants, report, package, verify"
        echo "  package [round]  the archive alone"
        echo "  verify           the newest built delivery, as a reviewer would"
        echo "  calculator       his own calculator over the built files"
        echo "  docx SOURCE      one markdown report into .docx"
        echo "  draft [--write]  the mail draft, printed unless --write"
        echo ""
        echo "Nothing above has run. A rehearsal with nothing decided:"
        echo "  just ship draft            print the mail, write nothing"
        echo "  just ship all              banks nothing still pending, and says so"
        ;;
    prep) stage_prep ;;
    build) stage_build "${1:-}" ;;
    package) bash scripts/round/package_delivery.sh "${1:-}" ;;
    verify) bash scripts/round/verify_delivery.sh "$(newest_stage)" ;;
    calculator) uv run python scripts/round/round_figures.py --verify ;;
    docx)
        if [ $# -lt 1 ]; then echo "ship docx SOURCE.md" >&2; exit 2; fi
        # The email carries the five fields and nothing else; the method goes in an
        # attached report, and Ding wants that attachment as .docx. Drafts under
        # `private/` carry a status block and a notes-to-self section, and the builder
        # strips both, because trimming them by eye is the operation that eventually
        # sends one.
        uv run python scripts/round/build_report_docx.py "$1" --keep-markdown
        ;;
    draft)
        uv run python scripts/round/ship_mail.py "$@"
        close_gate_issue --dry-run
        ;;
    all)
        set -e
        round="${1:-}"
        echo "== banking newly approved classes =="
        uv run python scripts/harness/bank_approved.py --write
        # Regenerate and COMMIT the report artifacts before packaging, not after.
        # `package_delivery.sh` refuses to run against a dirty tree, correctly, because
        # source/ would not match the results it ships. docs/report.docx and
        # docs/report-sendable.md are tracked and are rebuilt from docs/report.md, so
        # building them afterwards left the tree dirty and the first rehearsal of this
        # failed at the packaging step. Order matters here, not tidiness.
        echo "== regenerating the report and the .docx he asks for =="
        uv run python scripts/round/fill_report.py
        uv run python scripts/round/build_report_docx.py docs/report.md --keep-markdown
        if ! git diff --quiet -- docs/report.md docs/report.docx docs/report-sendable.md; then
            git add docs/report.md docs/report.docx docs/report-sendable.md
            git commit -q -m "Regenerate the round report and its .docx before packaging"
            echo "== committed the regenerated report artifacts =="
        fi
        stage_build "$round"
        echo "== the reviewer's own calculator =="
        uv run python scripts/round/round_figures.py --verify
        echo "== the mail draft =="
        uv run python scripts/round/ship_mail.py --write --archive "$(newest_stage)"
        close_gate_issue
        ;;
    *) echo "ship: all prep build package verify calculator docx draft (--help for the chain)" >&2; exit 2 ;;
    esac

# --- unattended ---------------------------------------------------------------

# Two launchd jobs. com.ark.bank runs `just bank` at five past every hour, so the
# round moves without a session open, and reads the `ship-now` label (the header of
# scripts/harness/scheduled_bank.sh). com.ark.cycle runs the health check four times
# a day; it reports and does not act, and scheduled_cycle.sh says why a restarting
# watchdog is the wrong shape here.
#
# **This needs Full Disk Access and will fail silently without it.** The repository
# lives under ~/Documents, which macOS TCC protects, and a launchd agent inherits no
# grant from the terminal that installed it. The first install exited 126 four times
# a day while `launchctl list` looked normal, so `install` runs the cycle job once as
# the probe and reports its exit status rather than trusting the load. launchd also
# starts with a bare PATH, which is why the templates carry one that finds just, uv,
# gh and claude: the second install exited 127 the same silent way.
#
# the launchd jobs that bank and health-check unattended: install remove status
schedule what="install":
    #!/usr/bin/env bash
    set -uo pipefail
    JOBS="com.ark.bank com.ark.cycle"
    case "{{what}}" in
    install)
        set -euo pipefail
        mkdir -p "$HOME/Library/LaunchAgents" data/logs
        for job in $JOBS; do
            plist="$HOME/Library/LaunchAgents/$job.plist"
            sed -e "s|ARK_ROOT|{{justfile_directory()}}|g" -e "s|ARK_HOME|$HOME|g" \
                "scripts/harness/$job.plist.template" > "$plist"
            launchctl unload "$plist" 2>/dev/null || true
            launchctl load "$plist"
            echo "loaded $job"
        done
        echo "running com.ark.cycle once to find out whether launchd can reach this directory"
        launchctl kickstart -k "gui/$(id -u)/com.ark.cycle" 2>/dev/null || true
        sleep 20
        status=$(launchctl list | awk '$3 == "com.ark.cycle" { print $2 }')
        if [ "${status:-0}" = "0" ]; then
            echo "OK: exited 0. com.ark.bank runs at :05 every hour and appends to data/logs/scheduled_bank.log"
        else
            echo "FAILED: last exit status $status"
            echo
            echo "  126 or 1 here is almost always macOS TCC: this repository is under"
            echo "  ~/Documents, and a launchd agent gets no access to it without a grant."
            echo "  Fix: System Settings > Privacy & Security > Full Disk Access, add"
            echo "  /bin/bash. Then run 'just schedule' again. 127 means a tool is not on"
            echo "  the PATH the template sets."
            echo
            echo "  Until then a terminal that runs 'just bank' hourly covers the same"
            echo "  ground, because it inherits the grant of the terminal that started it."
            tail -3 data/logs/scheduled_cycle.err 2>/dev/null || true
        fi
        ;;
    status)
        for job in $JOBS; do
            line=$(launchctl list | awk -v j="$job" '$3 == j { print "pid " $1 ", last exit " $2 }')
            echo "$job: ${line:-not loaded}"
        done
        for log in scheduled_bank scheduled_cycle; do
            [ -f "data/logs/$log.log" ] && { echo "--- data/logs/$log.log"; grep '^===== scheduled' "data/logs/$log.log" | tail -2; }
        done
        ;;
    remove)
        for job in $JOBS; do
            plist="$HOME/Library/LaunchAgents/$job.plist"
            launchctl unload "$plist" 2>/dev/null || true
            rm -f "$plist"
            echo "removed $job"
        done
        ;;
    *) echo "schedule: install remove status" >&2; exit 2 ;;
    esac
