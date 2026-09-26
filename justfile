# ark: the command set. `just` alone lists it.
#
# Thin wrappers over the `uv run ...` commands, so the ORDER is hard to get wrong; the raw
# commands stay the reproducibility contract. docs/ops/runbook.md is the long form.

set quiet := true

# every recipe, plus the choices the dispatching ones take
help:
    just --list
    echo ""
    echo "Dispatching recipes:"
    echo "  just check <what>       all code data lint fmt test scan"
    echo "  just collect <source>   no source lists them"
    echo "  just collectors <what>  pause resume status"
    echo "  just expand <what>      round loop"
    echo "  just hold <what> [name] on off status"
    echo "  just reproduce <stage>  all baseline sources candidates journals seeds deliver"
    echo "  just schedule <what>    install remove"
    echo "  just ship <stage>       all prep build package verify calculator docx draft"
    echo "  just verify <what>      raw trees delivery offsite"

# --- the environment ----------------------------------------------------------

# sync the locked environment (installs deps into .venv)
setup:
    uv sync

# Hooks live in hooks/ because .git/hooks is not versioned.
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
    #!/usr/bin/env bash
    set -euo pipefail
    set -- {{args}}
    for arg in "$@"; do
        case "$arg" in
        ingest*|export)
            uv run python scripts/harness/bank_hygiene.py space
            break
            ;;
        *) ;;
        esac
    done
    uv run ark "$@"

# --- validating ---------------------------------------------------------------

# `ark check` validates the DATA, the test suite the CODE, and each keeps its own word;
# bare `just check` runs both. `scan` is the last gate before tracked bytes are
# world-readable, and is the command the pre-commit hook and CI run.
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

# Prove what is on DISK, as opposed to the code or the store. Long form: docs/ops/runbook.md.
#
#   raw       checksum every data entry and regenerate docs/registers/retention.md. A
#             path with no row in that table is not deletable.
#   trees     every zip member of a release against the file on disk, by size and CRC-32
#   delivery  a built delivery as the reviewer reads it: checksums, pair counts, and that
#             every shipped pair traces to an observation. Takes the directory.
#   offsite   the off-site copy of what nothing else could bring back. Never deletes
#             anything, either side.
#
# prove what is on disk: raw trees delivery offsite
verify what="" *args:
    #!/usr/bin/env bash
    set -euo pipefail
    set -- {{args}}
    case "{{what}}" in
    raw) uv run python scripts/round/verify_raw.py "$@" ;;
    trees) uv run python scripts/round/releases.py --verify-trees "$@" ;;
    delivery) bash scripts/round/verify_delivery.sh "${1:-output/internet-digital-ark-1996-2001}" ;;
    offsite) uv run python scripts/round/offsite.py "$@" ;;
    *) echo "verify: raw trees delivery offsite" >&2; exit 2 ;;
    esac

# --- where the round stands ---------------------------------------------------

# Assembled from the claim files and the programs that own each figure, so no number in it
# is a second copy. No store unless `--full`; `--check` exits 1 when a claim file has changed
# since the file's footer.
#
# regenerate docs/ROUND.md, the generated statement of where the round stands
state *args:
    uv run python scripts/harness/bank_hygiene.py space
    uv run python scripts/round/build_round_state.py {{args}}

# Reads the data/brief.json snapshot the bank and `just state` leave, plus private/handoff.md.
# Never opens the store or runs ssh, so a session-start hook can call it inside its timeout.
#
# where the round stands, read from the last snapshot rather than the store
brief:
    uv run python scripts/agents/brief.py

# The reviewer's first priority in one command: unprocessed files, globs that match too
# little, downloaded bytes with no parser, derived lists a newer baseline has invalidated.
# Read-only and NOT a gate; run by hand it once found 496 unread ISC survey shards worth
# 14,956 equivalent-English.
#
# what is on disk that nothing has read, and what the documented path would miss
residual *args:
    uv run python scripts/harness/audit_residual.py {{args}}

# One pass of the harness: collector yield, unbanked journals, derived lists the store has
# outgrown, the hypothesis ledger, pending approvals, docs/ROUND.md. It ends with the items
# no program can decide, which is the part worth reading. `--until EPOCH --every SECS`
# loops; `--no-network` skips the re-probe, the only step that leaves the machine.
#
# check the round once and report what needs judgement
cycle *args:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python scripts/harness/bank_hygiene.py space
    uv run python scripts/harness/discover_cycle.py {{args}}
    # The failure-state ledger his XI asks for, printed rather than logged: a lane that has
    # started failing looks exactly like a lane with nothing left to find. Never fatal.
    echo ""
    uv run python scripts/harness/query_health.py --write --tail 3 || true

# The hourly tick: drain the fleet's findings, book the ones that need no store, bring the
# suffix sweep's finished journals home, and call `just bank` only when `bank_trigger.py`
# names something that arrived. It opens no store itself, so a quiet hour holds no writer.
# launchd runs it hourly while the laptop is awake, and it is safe to run by hand.
#
# Idempotent by construction: an unfinished run is re-downloaded and a drained slug is dropped
# rather than re-booked. `data/logs/.sync.lock` is taken first and handed to the bank, so a
# hand run and the hourly job cannot meet in the store, and the one that arrives second says
# who has it and stops.
#
# drain and book the fleet's findings, then bank only what arrived
sync fleet="~/Documents/GitHub/ark-fleet":
    #!/usr/bin/env bash
    set -euo pipefail
    if bash scripts/harness/hold.sh holds com.ark.sync; then echo held; exit 0; fi
    # One lock, whoever started this: it lives here, where the work is, rather than around
    # one of the two ways of starting it.
    if ! bash scripts/harness/sync_lock.sh take $$; then exit 0; fi
    trap 'bash scripts/harness/sync_lock.sh drop' EXIT
    # ARK_VPS for the journals below, and the store's memory limit, which local.env assigns
    # without `export` and the bank's children need.
    [ -f local.env ] && . ./local.env
    [ -n "${ARK_DB_MEMORY_LIMIT:-}" ] && export ARK_DB_MEMORY_LIMIT
    FLEET=$(eval echo {{fleet}})
    IN=data/fleet_findings/incoming
    mkdir -p "$IN" data/fleet_findings/banked data/logs
    PROCESSED=data/fleet_findings/processed_runs.txt; touch "$PROCESSED"
    command -v gh >/dev/null || { echo "needs gh"; exit 1; }
    # 0. Refuse a dirty or diverged clone, then fast-forward the approvals merged from a
    #    phone. A changed approvals page is one of the things that calls the bank.
    uv run python scripts/harness/bank_hygiene.py preflight
    uv run python scripts/harness/bank_hygiene.py space
    # Anything still waiting on Ivo, first, so a sync never buries a decision.
    gh issue list --repo i-staykov/ark-fleet --state open --search "Approval needed" \
        --json title --jq '.[] | "AWAITING IVO: " + .title' 2>/dev/null || true
    # 1. Pull every unprocessed run's `findings-*` artifact from ark-fleet. **A finished
    #    SHARD is bankable before its wave is**, so in-progress runs are taken too and a run
    #    is marked PROCESSED only once it has completed. Name the wave workflow: `gh run
    #    list` with none lists CI too, fifty empty downloads an hour hiding the two that matter.
    gh run list --repo i-staykov/ark-fleet --workflow wave.yaml --limit 50 \
        --json databaseId,status --jq '.[] | [.databaseId, .status] | @tsv' \
        | while IFS=$'\t' read -r RID STATUS; do
        grep -qx "$RID" "$PROCESSED" && continue
        gh run download "$RID" --repo i-staykov/ark-fleet --pattern 'findings-*' \
            --dir "$IN/run_$RID" >/dev/null 2>&1 || true
        [ "$STATUS" = "completed" ] && echo "$RID" >> "$PROCESSED"
    done
    LABEL=$(date -u +%Y%m%dT%H%MZ)
    # One directory per lead at the top of the drain, the telemetry rows in the ledger.
    uv run python scripts/harness/fleet_findings.py drain "$IN"
    uv run python scripts/harness/bank_hygiene.py prune --write
    # 2. The fleet's schema: a sidecar nobody validated is prose with braces. The second
    #    price, on the live store, is the bank's.
    uv run python scripts/harness/fleet_findings.py validate "$IN" --fleet "$FLEET"
    # 2b. Restart the fleet's wave chain if it has stopped. It stops by design on a zero-leg
    #     wave, and the GitHub cron meant to restart it does not reliably fire.
    #     `discover_cycle.py` holds the check but its own caller is six-hourly, so this hourly
    #     one bounds the gap. Never fatal: a dead chain must not take the bank down with it.
    uv run python scripts/harness/discover_cycle.py --wave-only || true
    # 3 to 7 need findings. A confirmed FIND needs the live store for its second price, so its
    # whole drain goes to the bank; any other drain is booked here. The two shapes are tested
    # separately: `ls` over both globs fails when EITHER is unmatched.
    if ! compgen -G "$IN/*.md" >/dev/null && ! compgen -G "$IN/*/finding.json" >/dev/null; then
        echo "nothing new to book"
    else
        # 3. Result lines first and pushed at once: a wave that picks while the rest of this
        #    recipe is still running relaunches settled slugs.
        uv run python scripts/harness/bank_findings.py "$IN" \
            --hypotheses "$FLEET/hypotheses.md" --run-label "$LABEL" --results-only
        bash scripts/harness/push_fleet.sh "$FLEET" "$LABEL"
        if uv run python scripts/harness/bank_trigger.py check --find; then
            echo "a confirmed FIND: the bank books this whole drain"
        else
            # 4. The deterministic scribe: one row per finding, keyed on the slug so a
            #    re-drained run books nothing twice, a FIND into sources.md and every measured
            #    negative into sources-closed.md rather than as a row of `n/a` cells.
            SCRIBE=$(uv run python scripts/harness/bank_findings.py "$IN" \
                --hypotheses "$FLEET/hypotheses.md" --run-label "$LABEL" | tee /dev/stderr)
            NEW_ROWS=$(printf '%s\n' "$SCRIBE" | sed -n 's/^scribe: \([0-9]*\) new rows.*/\1/p')
            # 5. Pending approvals as one issue and one mergeable pull request each, and the
            #    lead queue, rebuilt against the banked slugs the last bank cached.
            uv run python scripts/harness/sync_approvals.py || true
            uv run python scripts/round/lead_queue.py --fleet "$FLEET" --cached --write || true
            # 6. One commit and one push, **only when the registers moved**: an empty commit
            #    says a wave was booked when none was.
            git add docs/registers/ docs/lore/key-decisions.md
            COMMITTED=no
            if git diff --cached --quiet; then
                echo "the registers are unchanged, so nothing is committed"
            else
                git commit -q -m "Sync fleet findings $LABEL"
                git push -q origin live
                COMMITTED=yes
            fi
            # 7. What became of each lead, back into the fleet's queue, with the result lines.
            #    **A run leaves `incoming/` only once its rows are committed**; anything else
            #    keeps it here for the next tick, which is safe because every step is keyed on
            #    the slug.
            uv run python scripts/harness/fleet_leads.py "$IN" --fleet "$FLEET" --write
            bash scripts/harness/push_fleet.sh "$FLEET" "$LABEL"
            if [ "$COMMITTED" = yes ] || [ "${NEW_ROWS:-1}" = 0 ]; then
                mv "$IN" "data/fleet_findings/banked/$LABEL" && mkdir -p "$IN"
            else
                echo "nothing was committed, so the drain stays in $IN for the next tick"
            fi
        fi
    fi
    # 8. The suffix sweep's finished journals, home from the VPS. Skip the journals a sweep
    #    still holds open: a half-copied one ledgers at a fraction of its rows. Every remote
    #    call is bounded, so an unreachable VPS costs seconds rather than the hour.
    : "${ARK_VPS:?set ARK_VPS}"
    BUSY=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$ARK_VPS" \
        'for p in $(pgrep -f cdx_suffix_sweep.py); do ls -l /proc/$p/fd 2>/dev/null | grep -o "suffix_[^ /]*jsonl.gz"; done; true' \
        </dev/null 2>/dev/null | sort -u) || true
    rsync -a --ignore-existing --timeout=120 -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        $(for b in $BUSY; do echo "--exclude=$b"; done) \
        "$ARK_VPS":/projects/proj-internet-digital-ark/data/raw/cdx_suffix/suffix_*.jsonl.gz data/raw/cdx_suffix/ || true
    # 9. The bank, only when something arrived. ARK_LOCK_HELD names this shell, so the bank
    #    runs under this lock; a red bank exits 1 and so does this tick.
    BANK_RC=0
    if WHY=$(uv run python scripts/harness/bank_trigger.py check); then
        ARK_FLEET="$FLEET" ARK_LOCK_HELD=$$ just bank || BANK_RC=$?
    else
        echo "$WHY"
    fi
    # 10. The gate issue, once per crossing, read off the brief the last bank wrote; then a
    #     snapshot push the last bank could not make, without the ack, its one store read.
    #     Never while a red stands: output/ then holds the export that failed its check.
    uv run python scripts/harness/bank_hygiene.py gate --write || true
    if [ -f data/logs/.push_pending ] && [ -f data/logs/bank_red.json ]; then
        echo "push: held while BANK RED stands"
    elif [ -f data/logs/.push_pending ]; then
        if bash scripts/harness/sync_fleet.sh --no-ack \
            && uv run python scripts/harness/snapshot_manifest.py --out output/fleet_snapshot \
                --publish-expected "$FLEET" \
            && bash scripts/harness/push_fleet.sh "$FLEET" "$LABEL" \
            && git -C "$FLEET" show origin/main:snapshot.json 2>/dev/null \
                | cmp -s - "$FLEET/snapshot.json"; then
            rm -f data/logs/.push_pending
            echo "push: the pending snapshot reached the VPS, and fleet main expects its claim"
        else
            echo "push: still pending, the next tick retries"
        fi
    fi
    exit "$BANK_RC"

# The store's only writer. It runs what arrived: new journals and a new baseline (c), a
# confirmed FIND (a), a changed approvals page or a standing-rule decision (b); then the round
# state, the stamp, one commit and the fleet's queue (d), and the snapshot push (e). Journals
# go first, so a FIND is priced on a store that holds them and a red there leaves no
# `Decision:` line behind. A red writes data/logs/bank_red.json, and nothing banks until
# `uv run python scripts/harness/bank_trigger.py clear`. The tick hands it the lock through
# ARK_LOCK_HELD; by hand it takes the lock and runs the preflight itself.
#
# bank what arrived: fold journals, re-price, decide, gate, push; --force banks regardless
bank *args:
    #!/usr/bin/env bash
    set -euo pipefail
    if bash scripts/harness/hold.sh holds com.ark.sync; then echo held; exit 0; fi
    # ARK_LOCK_HELD names the pid that holds the lock and is trusted only while the lock
    # agrees, so a value some later shell inherits takes the lock like anyone else.
    if [ -n "${ARK_LOCK_HELD:-}" ] \
        && [ "$(bash scripts/harness/sync_lock.sh holder 2>/dev/null || true)" = "$ARK_LOCK_HELD" ]; then
        CALLED=yes
    else
        CALLED=no
        if ! bash scripts/harness/sync_lock.sh take $$; then exit 0; fi
        trap 'bash scripts/harness/sync_lock.sh drop' EXIT
    fi
    [ -f local.env ] && . ./local.env
    [ -n "${ARK_DB_MEMORY_LIMIT:-}" ] && export ARK_DB_MEMORY_LIMIT
    FORCE=no
    for a in {{args}}; do
        case "$a" in
            --force) FORCE=yes ;;
            *) echo "bank: unknown argument $a"; exit 2 ;;
        esac
    done
    FLEET="${ARK_FLEET:-$HOME/Documents/GitHub/ark-fleet}"
    IN=data/fleet_findings/incoming
    mkdir -p "$IN" data/fleet_findings/banked data/logs
    LABEL=$(date -u +%Y%m%dT%H%MZ)
    # By hand, the clone gets the check the tick gave it: a red resets the registers to HEAD,
    # which loses nothing only when this bank's writes are the only uncommitted ones.
    [ "$CALLED" = yes ] || uv run python scripts/harness/bank_hygiene.py preflight
    # A red holds even under --force: someone reads it and clears it first.
    if WHY=$(uv run python scripts/harness/bank_trigger.py check); then
        :
    elif printf '%s\n' "$WHY" | grep -q 'BANK RED'; then
        echo "$WHY"; exit 1
    elif [ "$FORCE" = yes ]; then
        WHY="bank: forced"
    else
        echo "$WHY"; exit 0
    fi
    echo "$WHY"
    has() { printf '%s\n' "$WHY" | grep -q "^bank: $1"; }
    want() { [ "$FORCE" = yes ] || has "$1"; }
    RAN_A=no; RAN_B=no; EXPORTED=no; DECIDED=0; NEW_ROWS=""
    CHECK_LOG=$(mktemp)
    # c. Journals, then the export a new baseline needs too. Every ingest is keyed on its
    #    journal's sha256, so a folded journal costs a hash. A failed ingest is red like a
    #    failed gate, and nothing is taken back: a journal carries no `Decision:` line.
    if want journals || want baseline; then
        C_RAN=""; C_FAIL=""
        if want journals; then
            uv run python scripts/harness/bank_hygiene.py space
            bash scripts/sources/usenet/ingest_new_usenet.sh auto || C_FAIL="$C_FAIL usenet_auto"
            if compgen -G "data/raw/usenet/usenet_dated_*.jsonl.gz" >/dev/null; then
                C_RAN="$C_RAN usenet_dated"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest usenet_dated data/raw/usenet/usenet_dated_*.jsonl.gz | tail -1 \
                    || C_FAIL="$C_FAIL usenet_dated"
            fi
            if compgen -G "data/raw/usenet/usenet_candidates_*.jsonl.gz" >/dev/null; then
                C_RAN="$C_RAN usenet_candidates"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest usenet_candidates data/raw/usenet/usenet_candidates_*.jsonl.gz | tail -1 \
                    || C_FAIL="$C_FAIL usenet_candidates"
            fi
            # A partial nothing has written to for 90 minutes is a dead run's work, not a live
            # run's file, so it takes its final name before the ingest looks.
            for part in data/raw/cdx/*.jsonl.gz.part data/raw/rdap/*.jsonl.gz.part; do
                [ -e "$part" ] || continue
                final="${part%.part}"
                [ -e "$final" ] && continue
                if [ -z "$(find "$part" -mmin +90 2>/dev/null)" ]; then continue; fi
                cp "$part" "$final" && echo "promoted abandoned partial $(basename "$final")"
            done
            # The suffix sweep's exact-host registrables, as cdx_snapshot journals under
            # data/raw/cdx, so the one glob below folds both. It reads new or grown journals only.
            uv run python scripts/engines/cdx_suffix_convert.py || C_FAIL="$C_FAIL cdx_suffix_convert"
            if compgen -G "data/raw/cdx/cdx_*.jsonl.gz" >/dev/null; then
                C_RAN="$C_RAN cdx_snapshot"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest cdx_snapshot data/raw/cdx/cdx_*.jsonl.gz | tail -1 \
                    || C_FAIL="$C_FAIL cdx_snapshot"
            fi
            # The hosts beneath a domain a gap query already asked about, at no extra request.
            uv run python scripts/engines/cdx_gap_hostgrain.py || C_FAIL="$C_FAIL cdx_gap_hostgrain"
            if compgen -G "data/raw/cdx_gap_hostgrain/*.jsonl.gz" >/dev/null; then
                C_RAN="$C_RAN cdx_gap_hostgrain"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest-hostnames data/raw/cdx_gap_hostgrain | tail -1 \
                    || C_FAIL="$C_FAIL cdx_gap_hostgrain"
            fi
            if compgen -G "data/raw/cdx_suffix/*.jsonl.gz" >/dev/null; then
                C_RAN="$C_RAN cdx_suffix"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest-hostnames data/raw/cdx_suffix/ | tail -1 || C_FAIL="$C_FAIL cdx_suffix"
            fi
            # The body-URL lanes, each with its own approved ingest, each shard skipped on content.
            for pool in data/raw/usenet_*_items; do
                [ -d "$pool" ] || continue
                C_RAN="$C_RAN $pool"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest-usenet-hostnames "$pool" | tail -1 || C_FAIL="$C_FAIL $pool"
            done
            if [ -d data/raw/maillists_items ]; then
                C_RAN="$C_RAN maillists_items"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest-maillist-hostnames data/raw/maillists_items | tail -1 \
                    || C_FAIL="$C_FAIL maillists_items"
            fi
            if [ -d data/raw/enron_items ]; then
                C_RAN="$C_RAN enron_items"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest-enron-hostnames data/raw/enron_items | tail -1 \
                    || C_FAIL="$C_FAIL enron_items"
            fi
            if compgen -G "data/raw/rdap/rdap_*.jsonl.gz" >/dev/null; then
                C_RAN="$C_RAN rdap_snapshot"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz | tail -1 \
                    || C_FAIL="$C_FAIL rdap_snapshot"
            fi
        fi
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark export --claim >/dev/null || C_FAIL="$C_FAIL export"
        EXPORTED=yes
        touch data/logs/.push_pending
        CHECK_RC=0
        uv run ark check 2>&1 | tee "$CHECK_LOG" || CHECK_RC=$?
        if [ -n "$C_FAIL" ] || [ "$CHECK_RC" -ne 0 ]; then
            uv run python scripts/harness/bank_trigger.py red --step c \
                --ingested "$C_RAN" --failed "$C_FAIL" --check "$CHECK_LOG"
            echo "BANK RED at the journals, failed:${C_FAIL:- ark check}. Nothing banks until it is cleared."
            exit 1
        fi
    fi
    # a. A confirmed FIND, priced a second time on the live store, booked with both figures,
    #    asked for, and decided where the standing rule covers it. A FIND is always a reason,
    #    so --force adds nothing here.
    if has find; then
        RAN_A=yes
        uv run python scripts/harness/fleet_findings.py reprice "$IN"
        SCRIBE=$(uv run python scripts/harness/bank_findings.py "$IN" \
            --hypotheses "$FLEET/hypotheses.md" --run-label "$LABEL" | tee /dev/stderr)
        NEW_ROWS=$(printf '%s\n' "$SCRIBE" | sed -n 's/^scribe: \([0-9]*\) new rows.*/\1/p')
        uv run python scripts/harness/fleet_request.py "$IN" --write
        DECIDED=$(uv run python scripts/harness/standing_rule.py "$IN" --write \
            | tee /dev/stderr | grep -c '^decided:' || true)
    fi
    # b. Approvals merged, or the standing rule just decided: ingest, export, gate. The rule's
    #    fourth condition is `ark check` after the ingest, and a failed ingest takes the same
    #    road as a red gate: a `Decision:` line over an ingest that did not happen reads
    #    exactly like one that did.
    if want approvals || [ "$DECIDED" -gt 0 ]; then
        RAN_B=yes
        uv run python scripts/harness/bank_hygiene.py space
        BANK_LOG=$(mktemp)
        set +e
        uv run python scripts/harness/bank_approved.py --write | tee /dev/stderr > "$BANK_LOG"
        RC=${PIPESTATUS[0]}
        set -e
        INGESTED=$(awk '/^== uv run ark ingest/ {print $6}' "$BANK_LOG")
        # An approval whose journal is absent or whose refetch was refused stays a reason for the
        # trigger until a bank ingests it. One that lacks a line in its block waits for the edit,
        # which the trigger sees as a changed approvals page.
        if ! grep -E 'refetch FAILED|is not on this machine' "$BANK_LOG" > data/logs/bank_approvals_retry; then
            rm -f data/logs/bank_approvals_retry
        fi
        if [ "$RC" -eq 0 ] && [ -z "$INGESTED" ] && [ "$DECIDED" -eq 0 ]; then
            echo "bank: nothing newly approved to ingest"
        else
            if [ "$RC" -eq 0 ]; then
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark export --claim >/dev/null || RC=$?
                EXPORTED=yes
                touch data/logs/.push_pending
            fi
            if [ "$RC" -eq 0 ]; then uv run ark check 2>&1 | tee "$CHECK_LOG" || RC=$?; fi
            if [ "$RC" -eq 0 ] && [ -f data/logs/bank_approvals_retry ]; then
                echo "bank: green; an approved journal is still absent, so the next bank retries it"
            elif [ "$RC" -eq 0 ]; then
                echo "bank: green after the ingest, so $DECIDED standing-rule decision(s) stand"
            else
                # The rows come out, and the registers go back to HEAD rather than the index:
                # the scribe's rows are this bank's too, and a dirty register refuses every
                # later tick at the preflight.
                echo "GATE RED after an approved ingest: taking the rows and the lines back"
                if [ -n "$INGESTED" ]; then
                    uv run python scripts/harness/unbank_source.py $INGESTED --write
                fi
                git checkout HEAD -- docs/registers/ docs/lore/key-decisions.md
                uv run python scripts/harness/bank_trigger.py red --step b \
                    --ingested "$INGESTED" --check "$CHECK_LOG"
                uv run python scripts/harness/bank_hygiene.py space
                uv run ark export --claim >/dev/null || true
                if uv run ark check; then
                    echo "the store is green again; the sources are pending and nothing was banked"
                else
                    echo "STILL RED after the rollback, so the red was not this ingest's:"
                    echo "  read 'uv run ark check' before clearing the red."
                fi
                exit 1
            fi
        fi
    fi
    # d. The pages the store feeds, the stamp, one commit, the fleet's queue. The round state
    #    rewrites docs/ROUND.md, which git ignores because it names the collecting machine.
    if [ "$RAN_A" = yes ] || [ "$RAN_B" = yes ]; then
        uv run python scripts/harness/sync_approvals.py || true
        uv run python scripts/round/lead_queue.py --fleet "$FLEET" --write || true
    fi
    uv run python scripts/harness/bank_hygiene.py space
    uv run python scripts/round/build_round_state.py | tail -1 || true
    uv run python scripts/harness/bank_trigger.py stamp
    git add docs/registers/ docs/lore/key-decisions.md
    COMMITTED=no
    if git diff --cached --quiet; then
        echo "the registers are unchanged, so nothing is committed"
    else
        git commit -q -m "Sync fleet findings $LABEL"
        COMMITTED=yes
    fi
    # A commit an earlier bank could not push goes with this one.
    if [ -n "$(git rev-list origin/live..live 2>/dev/null)" ]; then git push -q origin live; fi
    if [ "$RAN_A" = yes ]; then
        uv run python scripts/harness/fleet_leads.py "$IN" --fleet "$FLEET" --write
        bash scripts/harness/push_fleet.sh "$FLEET" "$LABEL"
        if [ "$COMMITTED" = yes ] || [ "${NEW_ROWS:-1}" = 0 ]; then
            mv "$IN" "data/fleet_findings/banked/$LABEL" && mkdir -p "$IN"
        else
            echo "nothing was committed, so the drain stays in $IN"
        fi
    fi
    # e. The snapshot the fleet prices against, when this bank exported one, then its claim in
    #    the fleet's snapshot.json. data/logs/.push_pending goes once fleet main holds that.
    if [ "$EXPORTED" = no ]; then
        echo "push: nothing was exported, so the fleet's snapshot stands"
    elif bash scripts/harness/sync_fleet.sh \
        && uv run python scripts/harness/snapshot_manifest.py --out output/fleet_snapshot \
            --publish-expected "$FLEET" \
        && bash scripts/harness/push_fleet.sh "$FLEET" "$LABEL" \
        && git -C "$FLEET" show origin/main:snapshot.json 2>/dev/null \
            | cmp -s - "$FLEET/snapshot.json"; then
        rm -f data/logs/.push_pending
    else
        echo "push pending: the VPS or fleet main did not take the snapshot, the next tick retries"
    fi

# The only route into the four register pages: `.claude/settings.json` denies a `grep` or a
# `sed` on them, and reading one whole spends the session's context on prose it never asked
# for. One truncated line per hit: page and line, source key, verdict, net-new EE, the shape
# the term sat in, and the text. A row is a projection of its entry, so a `detail` hit says
# the row does not carry what you asked about, and `--detail` is the only way to get that
# entry whole. Nothing prints over 40 lines without `--all`. Exit 1 is "not in the register",
# exit 2 is "the search did not run": different answers.
#
#   just find iedr                            every hit, over all four pages
#   just find iedr_register --detail          that entry whole, capped at 40 lines
#   just find blocklist squidguard            hits under one source key
#   just find sources#ukwa_geoindex --detail  when one key names two entries
#   uv run python scripts/round/find.py "ftp listing"   multi-word: `just` splits arguments
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

# What filled the agent's context: the ten largest tool results, result bytes by tool,
# assistant text bytes and how often the session compacted. Newest transcript by default;
# give a path, or --all for every session. A diagnostic, never a gate.
#
# measure what fills an agent's context from the newest transcript
context-report *args:
    uv run python scripts/agents/context_report.py {{args}}

# --- proposing and pricing a source -------------------------------------------

# The harness's working memory across sessions: `docs/registers/sources.md` is the
# authoritative narrative but prose cannot carry STATUS, so it cannot answer what an
# unattended run asks on every wake, which is what it proposed and never finished pricing.
# `add` screens first and refuses a hypothesis with no dating claim; `close` prints the
# sources.md row to paste. A multi-word --verdict or --cost goes to
# scripts/harness/hypothesis_ledger.py directly, since `just` splits arguments.
#
# the hypothesis ledger: proposed, priced, adopted or killed
hypo *args:
    uv run python scripts/harness/hypothesis_ledger.py {{args}}

# Does the proposal collide with a family already closed with a measurement, and what dates
# ONE of its items. The register is parsed out of docs/registers/sources.md at run time
# rather than copied, so it cannot drift. Exits 2 if no dating claim is made: a source whose
# items carry no date is seed-only, and that decides what it can ever be.
#
# screen a source proposal against the closed register before it costs a request
screen *args:
    uv run python scripts/harness/screen_hypothesis.py {{args}}

# Turn a URL into a priceable journal from a TOML description, so a source can be measured
# before anyone decides whether it is worth a hand-written collector. It refuses to guess a
# column, reports what it threw away by reason, and its output has no ingest spec, so no
# probe can date a year (ADR-004). Then `just price --items data/raw/probes/<name>.jsonl`.
#
# price a source from a TOML description, writing no Python
probe spec *args:
    uv run python scripts/pricing/probe_source.py {{spec}} {{args}}

# Price a normalised {item, year, text} JSONL against the live store: net-new pairs and
# domains after the corroboration split, mean weight, a typo bound, and both a linear and a
# saturating projection, quoting the lowest. Writes nothing.
#
# price any dated corpus against the live store, writing nothing
price *args:
    uv run python scripts/pricing/price_items.py {{args}}

# The same question at the second accepted unit. `price` collapses every name to its
# registrable, which once priced 180 suffix journals at 0 that were worth 301,650 EE in
# hostnames. This runs the ingest's own funnel and differences against hostname_year AND his
# baseline files, read-only, so a corpus gets its number without the write lock.
#
# price a corpus at hostname grain against the live store, writing nothing
price-hosts *args:
    uv run python scripts/pricing/price_hostnames.py {{args}}

# A source class may not date a year until a human classifies it, and `ark ingest` enforces
# that rather than trusting anyone to remember. This writes the request: a seeded-random
# sample of real records with live links, the measured figures, and what the source is worth
# under each possible decision. Candidate-only evidence needs no approval.
#
# ask a human to classify a source class before its records can date a year
approve *args:
    uv run python scripts/harness/request_approval.py {{args}}

# The most promising source is signed off first, so a program keeps the triage queue in
# score order. The judgement is the `- potential:` line each entry declares; this only
# applies it. An entry with no score is a hard error.
#
# sort the triage queue by declared potential, highest first
triage-rank *args:
    uv run python scripts/harness/rank_triage.py {{args}}

# Re-ask every source closed because something could not be REACHED, as opposed to closed
# because a measurement killed it. It extracts the failed hosts from the verdict prose and
# asks again. A 200 is news only when the verdict did not already predict one.
#
# re-probe every availability-closed lead, and report only what changed
reprobe *args:
    uv run python scripts/harness/reprobe_closed.py {{args}}

# --- reproducing the result ---------------------------------------------------

# The whole result from an empty store, offline, in six stages. Needs the bulk sources in
# data/raw/ AND the supplied baseline in legacy-data/, since the annual masters are baseline
# plus additions and net-new is defined against it. To collect NEW evidence, see the network
# recipes below. `just reproduce` runs all six in order; a stage name runs one.
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
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-legacy
        uv run ark legacy-review
        uv run ark audit
        ;;
    # stage 2: ingest every bulk source already downloaded into data/raw/
    #
    # `arquivo_ia` is deliberately absent: `data/raw/arquivo/IA.cdxj` is 47 GB and was deleted
    # once its 28,247 evidence rows were in the store, so a live line would abort this whole
    # stage on a missing file. Download it first (the command is in docs/registers/sources.md)
    # and run the commented line by hand. Same reason checksums.sha256 verifies 234, not 235.
    sources)
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest early_web         data/raw/early_web/*.cdx.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest isc_survey        data/raw/isc_survey/*.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest internic_zone     data/raw/internic_zones/*.zone.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest internic_zone     data/raw/internic_zones/*.zone.*.gz
        # The nameserver TARGETS of the 1997 zones, at hostname grain. The 1999 tomocha
        # files are not listed: their terms are parked (approved-sources-list.md).
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-zone-hostnames data/raw/internic_zones/org.zone.gz data/raw/internic_zones/edu.zone.gz data/raw/internic_zones/gov.zone.gz data/raw/internic_zones/mil.zone.gz data/raw/internic_zones/root.zone.gz data/raw/internic_zones/arpa.zone.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest dartmouth_bfs_seed data/raw/dartmouth_bfs/*.cdx.gz
        # NYPW TimeMaps, post-split. The collector fetches the three priced parts and
        # flattens each tarball into one file:
        #   uv run python scripts/sources/nypw/collect_nypw_timemaps.py
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest nypw_timemaps      data/raw/nypw_timemaps/*.cdx.gz
        # The non-200 lane of the same 34 files. Ingest it AFTER the 200 lane above: that
        # ordering is what makes the store the control group for the relaxation.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest nypw_timemaps_nonok data/raw/nypw_timemaps/*.cdx.gz
        # `jpnic_register` was REJECTED by the reviewer, so `ark ingest` exits 2 and takes
        # the whole recipe with it. Left commented because the artifact is on disk.
        # uv run ark ingest jpnic_register   data/raw/jpnic_tomocha/domain-list.txt
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest iedr_register     data/raw/iedr/*-doms.html
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest us_domain_delegated data/raw/us_domain/*.txt
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest squidguard_2001_blacklist data/raw/squidguard/*
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ripe_dbase_1999   data/raw/ripe_funet/ripe.db.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ripe_dbase_changed data/raw/ripe_funet/ripe.db.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ripe_dbase_split_2004 data/raw/ripe_funet_split/ripe.db.domain.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest namewinner_expiring data/raw/namewinner/*.tsv
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest can_domain_registry_notices data/raw/can_domain/*.zip
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest cctld_register_listing_inbody data/raw/cctld/*.html
        # The split step runs first because the ingest reads its output, not the raw editions.
        uv run python scripts/sources/blocklists/split_junkfilter.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest junkfilter_dated      data/raw/junkfilter/dated/*.txt
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest junkfilter_candidates data/raw/junkfilter/cand/*.txt
        # Same shape as junkfilter, so the split runs first.
        uv run python scripts/sources/blocklists/split_chastity.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest chastity_dated      data/raw/chastity/chastity-dated.*.txt
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest chastity_candidates data/raw/chastity/chastity-cand.*.txt
        # The same two blocklists one level down, at hostname grain. chastity's stamp is the
        # tar member header, so that lane reads the orig tarball, not the unpacked tree.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-blocklist-hostnames data/raw/squidguard/*
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-blocklist-hostnames data/raw/chastity/chastity-list_0.5.orig.tar.gz
        # Three more hostname-grain lanes: the nameservers RIPE domain objects point at (both
        # FUNET editions), IA's Early Web index re-emitted as capture journals, and the
        # USFEDGOV-EXTRACT-2001 merged index reduced to one capture per host
        # (`early_web_hostgrain.py`, `usfedgov_hostgrain.py`).
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-ripe-nserver-hostnames data/raw/ripe_funet/ripe.db.gz data/raw/ripe_funet_split/ripe.db.domain.gz
        uv run python scripts/sources/early_web/early_web_hostgrain.py | tail -1
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-hostnames data/raw/early_web_hostgrain/ | tail -1 || true
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-hostnames data/raw/usfedgov_hostgrain/ | tail -1 || true
        # The USFEDGOV-EXTRACT 1996-2000 sibling indexes go through the same hostgrain script
        # into the same journal directory, and the ISC survey per-TLD host files are read one
        # level below the registrable `isc_survey` took.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-isc-hostnames data/raw/isc_survey/wb_nw_*_*.gz | tail -1 || true
        # The pipermail month files already on disk for `maillist_dated`, read at hostname
        # grain from their body URLs.
        uv run python scripts/sources/mail_corpora/build_maillist_pool.py data/raw/maillists data/raw/maillists_items 8
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-maillist-hostnames data/raw/maillists_items/ | tail -1 || true
        # The CMU Enron release at hostname grain from its body URLs, the third member of the
        # body-URL family. One 443 MB request.
        test -f data/raw/enron/enron_mail_20150507.tar.gz || curl -sS -L -A "internet-digital-ark research collector" -o data/raw/enron/enron_mail_20150507.tar.gz https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
        uv run python scripts/sources/mail_corpora/build_enron_pool.py data/raw/enron/enron_mail_20150507.tar.gz data/raw/enron_items
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-enron-hostnames data/raw/enron_items/ | tail -1 || true
        # The collector runs first because the bytes are not kept in git.
        uv run python scripts/sources/registries/collect_granitecanyon.py
        uv run python scripts/sources/registries/split_granitecanyon.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest granitecanyon_dated      data/raw/granitecanyon/granitecanyon-dated.*.txt
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest granitecanyon_candidates data/raw/granitecanyon/granitecanyon-cand.*.txt
        # The capture-dated ccTLD listings: collect, split, then ingest both halves.
        uv run python scripts/sources/registries/collect_cctld_capture.py
        uv run python scripts/sources/registries/split_cctld_capture.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest cctld_capture_dated      data/raw/cctld_capture/cctldcap-dated.*.txt
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest cctld_capture_candidates data/raw/cctld_capture/cctldcap-cand.*.txt
        # Neither takes the split: both are a registry reading out its own register.
        uv run python scripts/sources/registries/collect_mynic_coza.py
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest mynic_change_report data/raw/mynic/*.htm
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest coza_deletion_queue data/raw/coza/*.html
        # NOT reproducible by a collector: app.fac.gov is `User-agent: * / Disallow: /`,
        # so the four census-<year>.zip
        # files must be downloaded BY HAND from https://www.fac.gov/data/download/historic/
        # and ELECAUDITHEADER.csv unpacked to data/raw/fac/header-<year>.csv.
        uv run python scripts/sources/mail_corpora/split_fac.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest fac_dated      data/raw/fac/fac-dated.*.tsv
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest fac_candidates data/raw/fac/fac-cand.*.tsv
        # The Jeb Bush mailbox and the URLMerchant inventory, both almost entirely at 2001.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest jeb_mail_dated       data/raw/jeb_bush/jeb_mail_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest jeb_mail_candidates  data/raw/jeb_bush/jeb_mail_candidates.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest urlmerchant_dated      data/raw/urlmerchant/urlmerchant_dated_b*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest urlmerchant_candidates data/raw/urlmerchant/urlmerchant_candidates_b*.jsonl.gz
        # URLMerchant's for-sale inventory, post-split. The page collector outlives a session,
        # so a later batch takes its own `--tag` and its own pair of ingest lines.
        uv run python scripts/sources/directories/split_urlmerchant.py --tag b1 --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest urlmerchant_dated      data/raw/urlmerchant/urlmerchant_dated_b1.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest urlmerchant_candidates data/raw/urlmerchant/urlmerchant_candidates_b1.jsonl.gz
        # The extractor runs over the files unpacked from JebBushEmails-Text.7z, which is
        # 412 MB and not kept in git:
        #   curl -O https://archive.org/download/JebBushEmails/JebBushEmails-Text.7z
        #   7z x JebBushEmails-Text.7z -o<dir> 'Redacted/*'
        #   uv run python scripts/sources/mail_corpora/parse_jeb_mail.py --out-prefix data/raw/jeb_bush/jeb_bush \
        #       <dir>/Redacted/*.txt
        uv run python scripts/sources/mail_corpora/split_jeb_mail.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest jeb_mail_dated      data/raw/jeb_bush/jeb_mail_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest jeb_mail_candidates data/raw/jeb_bush/jeb_mail_candidates.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest early_bulk_whois_snapshot data/raw/edelman/*.html
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest arquivo_roteiro   data/raw/arquivo/Roteiro.cdxj
        # uv run ark ingest arquivo_ia      data/raw/arquivo/IA.cdxj   # see above
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest afnic_fr          data/raw/afnic/*NomsDeDomaineEnPointFr.csv
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest internet_scout    data/raw/scout/scout_oai.xml
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest odp               data/raw/odp/*.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ukwa_link_source  data/raw/ukwa/host-linkage.tsv.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ukwa_link_source  data/raw/ukwa/*-linkage.tsv
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ukwa_link_source  data/raw/ukwa/*-linkage.tsv.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ukwa_link_target  data/raw/ukwa/host-linkage.tsv.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ukwa_link_target_bare data/raw/ukwa/host-linkage.tsv.gz
        # The BL geoindex extract. `ark ingest` refuses it until its `Decision:` line is set,
        # so the line is a no-op until then and keeps the documented reproduction complete.
        # Build the input with `bash scripts/sources/ukwa/ukwa_geoindex_pull.sh`.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ukwa_geoindex     data/raw/ukwa/*_inwindow.tsv.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest ncsa_whats_new    data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv
        # These three once reached 11.5% of all assignments while this recipe, which README.md
        # calls "the authoritative list of what gets ingested", did not name them (D1).
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest udrp_proceedings       data/raw/udrp/udrp_proceedings.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest dk_hostmaster_dk_zonen_domains_txt_wayback_2001 data/raw/registry_lists/dk_hostmaster_domains_txt_2001.jsonl
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest dartmouth_nber_captures data/raw/dartmouth_nber/domain-year-captures.txt
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest domain_creation_bulk   data/raw/domain_creation/domains.csv
        ;;
    # stage 3: grow the candidate pool from the year-unlabelled host lists
    candidates)
        uv run ark seed data/raw/webbase/hosts.txt
        uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt
        uv run ark seed seeds/100hot_hosts.txt
        ;;
    # stage 4: replay the network journals already collected in data/raw/. It re-derives
    # evidence from the stored responses, so it needs no network and gives the same result
    # every time. To collect MORE, see the network recipes below.
    journals)
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest cdx_snapshot  data/raw/cdx/cdx_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rdap_snapshot data/raw/rdap_gen/rdap_gen_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_links     data/raw/expand/expand_*.jsonl.gz --round 1
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_directory data/raw/expand/round2/expand_round2.jsonl.gz --round 2
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_directory data/raw/expand/wwwvl/expand_wwwvl_corroborated.jsonl.gz --round 3
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_links     data/raw/expand/wwwvl/expand_wwwvl_unverified.jsonl.gz --round 3
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_directory data/raw/expand/round4/expand_round4_corroborated.jsonl.gz --round 4
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_links     data/raw/expand/round4/expand_round4_unverified.jsonl.gz --round 4
        # Three directories, not one: each pool wrote its journals beside its own archives,
        # and `data/raw/usenet/` alone reaches 186 of 1,064 ledgered files. One line per
        # directory, because the residual audit reads the FIRST glob on an `ark ingest` line
        # and a backslash continuation is invisible to it.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_dated        data/raw/usenet/usenet_dated*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_dated        data/raw/usenet_new/usenet_dated*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_dated        data/raw/usenet_de/usenet_dated*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_dated        data/staging/usenet_resplit/filtered/usenet_dated_resplit*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_candidates   data/raw/usenet/usenet_candidates*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_candidates   data/raw/usenet_new/usenet_candidates*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_candidates   data/raw/usenet_de/usenet_candidates*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_candidates   data/staging/usenet_resplit/filtered/usenet_candidates_resplit*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tucows_dated        data/raw/tucows/tucows_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tucows_candidates   data/raw/tucows/tucows_candidates.jsonl.gz
        # The recovered-address journals. The first split is in the ledger but no longer on
        # disk and the second is a superset, so replaying the glob reconstructs the same
        # evidence; every later re-split writes its own tagged pair (`_r*`, `_addr*`, `_cmp*`).
        # Regenerate with `just collect usenet-addresses`, which writes the untagged names.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_addr_dated      data/raw/usenet_addr/usenet_addr_dated_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_addr_candidates data/raw/usenet_addr/usenet_addr_candidates_*.jsonl.gz
        # The machine-written header seam, under the same two source keys because no
        # `usenet_hdr` spec exists. Without these two lines a rebuild is 19,224 rows short.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_addr_dated      data/raw/usenet_hdr/usenet_hdr_dated*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_addr_candidates data/raw/usenet_hdr/usenet_hdr_candidates*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest uucp_listing        data/raw/uucp/uucp_listing.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest uucp_creation       data/raw/uucp/uucp_creation.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest uucp_mentions       data/raw/uucp/uucp_mentions.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rtfm_dated          data/raw/rtfm/rtfm_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rtfm_candidates     data/raw/rtfm/rtfm_candidates.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rtfm_dated          data/raw/rtfm/rtfm_dated_reextract.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rtfm_candidates     data/raw/rtfm/rtfm_candidates_reextract.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_bare_dated      data/raw/usenet_bare/usenet_bare_dated*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_bare_candidates data/raw/usenet_bare/usenet_bare_candidates*.jsonl.gz
        # Registry whois records pasted into the bodies. The registry's own creation line
        # dates the row, not the post, so this is `whois_creation` and rule 6 gives that year
        # alone. Regenerate with `just collect usenet-whois`.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_whois_dated      data/raw/usenet_whois/usenet_whois_dated*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_whois_candidates data/raw/usenet_whois/usenet_whois_candidates*.jsonl.gz
        # The promotion tranches, which live under `data/staging/` rather than `data/raw/`.
        # Regenerable by re-running `build_promotion_journals.py`, but a reproduction path
        # should not depend on that.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest enron_dated       data/staging/promotion/enron_dated_promoted_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest maillist_dated    data/staging/promotion/maillist_dated_promoted_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rtfm_dated        data/staging/promotion/rtfm_dated_promoted_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_dated  data/staging/promotion/tradepress_dated_promoted_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tucows_dated      data/staging/promotion/tucows_dated_promoted_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_dated      data/staging/promotion/usenet_dated_promoted_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_addr_dated data/staging/promotion/usenet_addr_dated_promoted_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_bare_dated data/staging/promotion/usenet_bare_dated_promoted_*.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest attrition_dated     data/raw/attrition/attrition_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest enron_dated         data/raw/enron/enron_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest enron_candidates    data/raw/enron/enron_candidates.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest maillist_dated      data/raw/maillists/maillist_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest maillist_candidates data/raw/maillists/maillist_candidates.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_reextract.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_reextract.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american_bare.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american_bare.jsonl.gz
        # The archived 1996-1997 Yahoo directory walk, measured and rejected as a route (55
        # requests bought 11 pairs). Its three journals were ingested, so a rebuild without
        # them is 670 records short.
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_directory data/raw/yahoo96/yahoo96_pilot1996_corroborated.jsonl.gz --round 5
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_directory data/raw/yahoo96/yahoo96_fatpages1996_corroborated.jsonl.gz --round 5
        uv run python scripts/harness/bank_hygiene.py space
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
    # stage 6: write the deliverable, then prove it. Export FIRST, always: `check`'s
    # `additions_not_double_counted` invariant reads the exported annual files, so running
    # it first compares this round's files against last round's store and reports every
    # already-credited pair as a violation.
    deliver)
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark export
        uv run ark stats
        uv run ark check
        uv run python scripts/round/prune.py --round --write || echo "cleanup held unverified copies" >&2
        ;;
    *) echo "reproduce: all baseline sources candidates journals seeds deliver" >&2; exit 2 ;;
    esac

# Needs no source data at all. About a minute, and byte-identical.
#
# tier 2: regenerate every result file from a provenance export. `ark export` does not
# write that export unless asked, so refresh it with `ark export --provenance` first or
# this rebuilds whatever was last shipped.
rebuild dir="output/provenance":
    uv run ark rebuild {{dir}}
    uv run ark check

# --- collecting more (network) ------------------------------------------------
# Each of these appends a journal to data/raw/ and writes no evidence, so they
# never hold the store's write lock and can run concurrently with each other.

# The laptop's launchd-supervised parent sweep, a closed lane: `run` starts nothing. No start
# or stop, because launchd owns the process, and the pause flag is the only thing these three
# words touch.
#
#   pause    writes the flag a sweep checks between pages. Survives sleep and reboot.
#   resume   the flag is removed.
#   status   paused or not, clients on the channel, the last journal and its hit rate.
#
# the laptop CDX collectors: pause resume status
collectors what="status":
    #!/usr/bin/env bash
    set -uo pipefail
    case "{{what}}" in
    pause|resume|status) bash scripts/harness/collectors.sh {{what}} ;;
    *) echo "collectors: pause resume status" >&2; exit 2 ;;
    esac

# Page expansion, the outbound-link route (brief section VII).
#
#   round SEEDS N  one round over a seed list, e.g.
#   round SEEDS N  one round over a seed list, e.g.
#                  `just expand round seeds/expansion/seeds_round4.txt 5`. The split step
#                  keeps a curated page's transcription typos out of master evidence.
#   loop [D] [P]   one turn of the closed discovery loop: the engine's own hits become the
#                  next seed pages and their outbound domains become candidates. No human
#                  picks the seeds, which is what stops this being a source that runs out.
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
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_directory \
            "data/raw/expand/round${round}/expand_round${round}_corroborated.jsonl.gz" --round "$round"
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_links \
            "data/raw/expand/round${round}/expand_round${round}_unverified.jsonl.gz" --round "$round"
        ;;
    loop)
        uv run python scripts/engines/build_expand_seeds.py --recent 40 --domains "${1:-600}"
        stamp=$(date -u +%Y%m%dT%H%M%SZ)
        uv run ark download data/raw/expand/loop/seeds.txt -n "${2:-400}" --workers 2 \
            --delay 0.6 --captures 1 --out "data/raw/expand/loop/expand_${stamp}.jsonl.gz"
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest expansion_links data/raw/expand/loop/expand_*.jsonl.gz --round 6
        ;;
    *) echo "expand: round loop" >&2; exit 2 ;;
    esac

# --- the per-source collectors ------------------------------------------------

# One source per invocation. Each is collect-then-split: the collector writes a journal and
# touches no database, the split sorts it into a dated half and a candidate half. The split
# is the evidence wall for every free-text source, so it is not optional.
#
#   apache-headers               Apache list relay hosts, dated per message (C-83)
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
    # Approved under C-83 for the `Received: ... by <host>` clause alone. Discovery is 72
    # requests and resumable per month; the harvest honours `Crawl-delay: 5` and skips what
    # is on disk. A list-month limit as the first argument takes a measured slice.
    apache-headers)
        uv run python scripts/sources/mail_corpora/collect_apache_lists.py --discover
        uv run python scripts/sources/mail_corpora/collect_apache_lists.py --expand
        uv run python scripts/sources/mail_corpora/collect_apache_lists.py --harvest ${1:+--limit "$1"}
        uv run python scripts/sources/mail_corpora/build_apache_header_pool.py \
            data/raw/apache_lists data/raw/apache_header_items 8
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest-apache-header-hostnames data/raw/apache_header_items/
        ;;
    attrition)
        uv run python scripts/sources/directories/collect_attrition.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest attrition_dated data/raw/attrition/attrition_dated.jsonl.gz
        uv run ark seed data/raw/attrition/attrition_out_of_window_hosts.txt
        ;;
    # Take the sync lock first: the extraction runs for minutes before it writes, and
    # it has no store-lock retry, so a bank landing mid-run loses the work.
    enron)
        uv run python scripts/sources/mail_corpora/collect_enron.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest enron_dated      data/raw/enron/enron_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest enron_candidates data/raw/enron/enron_candidates.jsonl.gz
        ;;
    # Harvest first, then parse: `--harvest` fetches about 2,600 month files from
    # two pipermail hosts, which takes six minutes and no archive.org budget.
    maillists)
        uv run python scripts/sources/mail_corpora/collect_mailing_lists.py --harvest --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest maillist_dated      data/raw/maillists/maillist_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest maillist_candidates data/raw/maillists/maillist_candidates.jsonl.gz
        ;;
    # Seed-only and permanently so: the index carries no date column, so nothing in it can
    # evidence a year. 35,391 registrable domains, 29,432 unknown to the store when
    # measured. Expect pool growth and no annual-file growth: a 60-domain sample on the AWA
    # endpoint returned zero in-window captures.
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
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rtfm_dated      "data/raw/rtfm/rtfm_dated${suffix}.jsonl.gz"
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest rtfm_candidates "data/raw/rtfm/rtfm_candidates${suffix}.jsonl.gz"
        ;;
    # Run --discover first: several plausible collection names do not exist and
    # silently return zero when queried with a collection: prefix.
    trade-press)
        uv run python scripts/sources/trade_press/collect_trade_press.py --discover
        uv run python scripts/sources/trade_press/collect_trade_press.py --limit "${1:-5000}"
        uv run python scripts/sources/trade_press/split_trade_press.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates.jsonl.gz
        ;;
    # Both corpora are already worked and ingested; this is here to reproduce, not to
    # re-run. The collector writes a fresh timestamped journal, so pass its name to
    # the split. --tag keeps the ledger happy: tradepress_dated.jsonl.gz is taken.
    trade-press-american)
        journal="${1:-data/raw/tradepress/tradepress_20260808T172417Z.jsonl.gz}"
        uv run python scripts/sources/trade_press/collect_trade_press.py --limit 1400 --delay 0.6
        uv run python scripts/sources/trade_press/split_trade_press.py --journal "$journal" --tag american --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
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
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tucows_dated data/raw/tucows/tucows_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest tucows_candidates data/raw/tucows/tucows_candidates.jsonl.gz
        ;;
    # mode=headers instead reads Message-ID, Reply-To, Sender and NNTP-Posting-Host. The
    # mode changes the output DIRECTORY as well as the extractor, `addresses` writing
    # data/raw/usenet_addr and `headers` data/raw/usenet_hdr, so it must be threaded all the
    # way through: given only to the collector it silently re-ingests the address journals.
    usenet-addresses)
        mode="${1:-addresses}"; workers="${2:-10}"
        case "$mode" in
            addresses) dir=data/raw/usenet_addr; prefix=usenet_addr ;;
            headers)   dir=data/raw/usenet_hdr;  prefix=usenet_hdr  ;;
            *) echo "mode must be 'addresses' or 'headers'" >&2; exit 1 ;;
        esac
        uv run python scripts/sources/usenet/collect_usenet_addresses.py --mode "$mode" --workers "$workers"
        uv run python scripts/sources/usenet/split_usenet_addresses.py --in-dir "$dir" --out-prefix "$prefix" --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_addr_dated      "$dir/${prefix}_dated.jsonl.gz"
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_addr_candidates "$dir/${prefix}_candidates.jsonl.gz"
        ;;
    # Sends no request and takes about three hours of CPU at 8 workers. Run
    # `--sample 400` first if you want the projection before committing to it.
    usenet-bare)
        uv run python scripts/sources/usenet/collect_usenet_bare.py --workers "${1:-8}"
        uv run python scripts/sources/usenet/split_usenet_addresses.py --in-dir data/raw/usenet_bare --out-prefix usenet_bare --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_bare_dated      data/raw/usenet_bare/usenet_bare_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_bare_candidates data/raw/usenet_bare/usenet_bare_candidates.jsonl.gz
        ;;
    usenet-ingest)
        uv run python scripts/harness/bank_hygiene.py space
        bash scripts/sources/usenet/ingest_new_usenet.sh "${1:-auto}"
        ;;
    # The one source assessed without measuring first was estimated at 27,276 net-new
    # domains and measured at 53, so this is not optional caution.
    usenet-measure)
        uv run python scripts/sources/usenet/measure_usenet_yield.py "$@"
        ;;
    # Reads every archive in all five pools: about forty minutes of CPU at 8 workers and no
    # request. `ARK_USENET_SRC` picks the pool, because the default constant names only the
    # first directory, which is now empty.
    usenet-whois)
        for pool in usenet_bulk usenet_new usenet_probe usenet_probe5 usenet_msft; do
            [ -d "data/raw/$pool" ] || continue
            ARK_USENET_SRC="data/raw/$pool" uv run python scripts/sources/usenet/collect_usenet_whois.py \
                --workers "${1:-8}" --tag "$pool"
        done
        uv run python scripts/sources/usenet/split_usenet_whois.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_whois_dated      data/raw/usenet_whois/usenet_whois_dated.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest usenet_whois_candidates data/raw/usenet_whois/usenet_whois_candidates.jsonl.gz
        ;;
    # UUCP maps from comp.mail.maps: a .CA registry dump the Usenet parser read as prose
    uucp-maps)
        uv run python scripts/sources/usenet/split_uucp_maps.py --write
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest uucp_listing  data/raw/uucp/uucp_listing.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest uucp_creation data/raw/uucp/uucp_creation.jsonl.gz
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark ingest uucp_mentions data/raw/uucp/uucp_mentions.jsonl.gz
        ;;
    "")
        echo "collect <source> [args]. Sources:"
        echo "  attrition enron maillists pandora-seed rtfm-faqs trade-press"
        echo "  trade-press-american trade-press-reextract tucows usenet-addresses"
        echo "  usenet-bare usenet-ingest usenet-measure usenet-whois uucp-maps"
        echo "Arguments and what each one reads: docs/ops/runbook.md"
        ;;
    *) echo "collect: no source called '{{source}}'; run 'just collect' for the list" >&2; exit 2 ;;
    esac

# --- retention ----------------------------------------------------------------

# Fill docs/registers/releases.md from what is on disk: per-year line counts of every
# extracted release tree under feedback/, and the sha256 of the reviewer's zip or of our
# data/archive/<marker>.tar.zst where there is none. Writes only the cells it can compute, so
# a hash outlives the zip leaving the machine. `--zstd` packs the zip-less trees first;
# `--refresh` recounts and rehashes everything.
#
# fill docs/registers/releases.md from the release trees on disk
releases *args:
    uv run python scripts/round/releases.py {{args}}

# Take one reviewer release: verify the zip's sha256, extract it beside the other releases,
# count the year files, remeasure them with his own calculator, point data/baseline.json at
# the new marker and refresh docs/registers/releases.md; `--mail` also writes the round's row
# in docs/registers/rounds.md. Every figure comes from the extracted files, never from his
# mail. A second run on the same zip changes nothing, `--dry-run` says what it would do, and a
# marker already recorded under a different sha256 stops the run. It does NOT load the release
# into the store: that stays a separate deliberate `ark ingest-legacy` step.
#
# take one reviewer release: verify, extract, remeasure, record
intake *args:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python scripts/round/intake.py {{args}}
    # a new baseline the fleet cannot see prices every wave against a stale ceiling
    case "{{args}}" in *--dry-run*) exit 0 ;; esac
    bash scripts/harness/sync_fleet.sh
    FLEET="${ARK_FLEET:-$HOME/Documents/GitHub/ark-fleet}"
    LABEL=$(date -u +%Y%m%dT%H%MZ)
    uv run python scripts/harness/snapshot_manifest.py --out output/fleet_snapshot \
        --publish-expected "$FLEET" \
        && bash scripts/harness/push_fleet.sh "$FLEET" "$LABEL" \
        && git -C "$FLEET" show origin/main:snapshot.json 2>/dev/null \
            | cmp -s - "$FLEET/snapshot.json" \
        || { touch data/logs/.push_pending; echo "push pending: the next tick retries"; }

# Write a round's row in docs/registers/rounds.md from the reviewer's verdict mail: his five
# figures parsed, S and t computed from the two stamps rather than read off the mail, and a
# benchmark he never sent marked not received. Pass the mail, the round label and the receipt
# stamp in his clock, e.g.
# `just rounds --mail private/mail/verdict7.txt --round 7 --received "2026-09-02 05:50"`.
#
# write a round's row in docs/registers/rounds.md from his verdict mail
rounds *args:
    uv run python scripts/round/rounds.py {{args}}

# Legacy mode reports only. --round previews scoped backup/release cleanup;
# --round --write executes only when the retained copy is verified.
# Never deletes submissions/ or output/.
#
# report retention or preview/execute verified round cleanup
prune *args:
    uv run python scripts/round/prune.py {{args}}

# --- shipping -----------------------------------------------------------------

# The round-end sequence, in the one order that works, as one recipe. The stages, and what
# each one runs: `just ship --help`, which prints the chain and runs none of it.
#
# The store moves only inside `just bank`, and ship holds the sync lock from its bank to the
# package, so no tick banks in between. `package_delivery.sh` refuses unless the export stamp
# is a full export whose ledger matches the store and whose claim equals the bank's.
#
# **Safe to rehearse with nothing decided.** `bank_approved.py` reports and SKIPS anything
# still pending, and `just ship draft` prints the mail it would send without writing it.
#
# ship the round: bank, export, gate, package, verify, draft the mail
ship stage="all" *args:
    #!/usr/bin/env bash
    set -uo pipefail
    set -- {{args}}
    # The store's memory limit, as the bank has it, for the full export and the round state.
    [ -f local.env ] && . ./local.env
    [ -n "${ARK_DB_MEMORY_LIMIT:-}" ] && export ARK_DB_MEMORY_LIMIT

    newest_stage() { ls -dt output/DomainDataCollectionTask_*_IvayloStaykov 2>/dev/null | head -1; }

    # Round cleanup requires local checksums and verified remote copies; no upload.
    stage_retention() {
        just verify raw
        just verify offsite --manifest
        just verify offsite --verify
        just prune --round --write
    }

    # Taken once and held to exit, so no tick banks between the bank, the checks and the package.
    # The drop trap goes in only after our own take, because drop removes the lock whoever holds it.
    LOCKED=no
    hold_lock() {
        [ "$LOCKED" = yes ] && return 0
        if ! bash scripts/harness/sync_lock.sh take $$; then
            echo "ship: the sync lock is held, so nothing ran; run it again after that one" >&2
            exit 1
        fi
        LOCKED=yes
        trap 'bash scripts/harness/sync_lock.sh drop' EXIT
    }

    stage_prep() {
        set -e
        if bash scripts/harness/hold.sh holds com.ark.sync; then
            echo "ship prep: the hold is on, so the bank would not run" >&2
            exit 1
        fi
        hold_lock
        # A bank handed the lock skips its preflight, so ship runs it, as a bank by hand does.
        uv run python scripts/harness/bank_hygiene.py preflight
        BEFORE=$(cat output/netnew/export_stamp.json 2>/dev/null || true)
        ARK_LOCK_HELD=$$ just bank --force
        AFTER=$(cat output/netnew/export_stamp.json 2>/dev/null || true)
        if [ "$AFTER" = "$BEFORE" ] || ! grep -q '"mode": "claim"' <<<"$AFTER"; then
            echo "ship prep: the bank wrote no claim export" >&2
            exit 1
        fi
        # The promotion tranche, measured and never banked: without --write it writes nothing.
        uv run python scripts/engines/build_promotion_journals.py --tag "dryrun$(date -u +%Y%m%d)"
        uv run python scripts/round/merge_against_baseline.py | tail -3
        uv run python scripts/round/round_figures.py | sed -n '1,13p'
    }

    stage_build() {
        set -e
        hold_lock
        # The bank's claim, set aside where packaging compares it with the full export's.
        if ! grep -q '"mode": "claim"' output/netnew/export_stamp.json 2>/dev/null; then
            echo "== the claim export =="
            uv run python scripts/harness/bank_hygiene.py space
            uv run ark export --claim
        fi
        mkdir -p data/exports/claim
        cp output/netnew/candidate_additions.txt output/netnew/export_stamp.json data/exports/claim/
        echo "== the full export =="
        uv run python scripts/harness/bank_hygiene.py space
        uv run ark export --provenance
        echo "== the data invariants =="
        uv run ark check
        echo "== the round state, with the store sections =="
        uv run python scripts/round/build_round_state.py --full
        # `package_delivery.sh` regenerates the report and refuses a dirty tree or a report that
        # changed, so a human reviews the diff. Rebuilding and committing the report and its
        # .docx here makes this one pass: the diff is nothing but regenerated figures.
        echo "== regenerating the report and the .docx he asks for =="
        uv run python scripts/round/fill_report.py
        uv run python scripts/round/build_report_docx.py docs/report.md --keep-markdown
        if ! git diff --quiet -- docs/report.md docs/report.docx docs/report-sendable.md; then
            git add docs/report.md docs/report.docx docs/report-sendable.md
            git commit -q -m "Regenerate the round report and its .docx before packaging"
            echo "== committed the regenerated report artifacts =="
        fi
        echo "== packaging =="
        bash scripts/round/package_delivery.sh "${1:-}"
        echo "== verifying the built delivery the way a reviewer would =="
        # The directory is passed explicitly, and resolved as the newest stage rather than
        # hardcoded. `verify_delivery.sh` defaults to its own location, which is right when
        # it ships INSIDE a delivery and wrong from this repository; a hardcoded path once
        # verified the PREVIOUS round's stage and reported its figures as this round's.
        bash scripts/round/verify_delivery.sh "$(newest_stage)"
        stage_retention
    }

    # Close the gate issue only on a verified delivery, and only when one is open: the
    # issue is latched once per crossing, so a second close notifies twice for one round.
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
        echo "  all [round]      prep, then build, then the reviewer's calculator, the mail"
        echo "                   draft, and closing the gate issue"
        echo "  prep             take the sync lock, bank --force, promotion dry run, merge"
        echo "                   audit, figures"
        echo "  build [round]    take the sync lock, full export, invariants, round state,"
        echo "                   report and .docx, package, verify"
        echo "  package [round]  package, verify delivery and retained copies, round cleanup"
        echo "  verify           verify the newest delivery and retained copies, round cleanup"
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
    package)
        set -e
        hold_lock
        bash scripts/round/package_delivery.sh "${1:-}"
        bash scripts/round/verify_delivery.sh "$(newest_stage)"
        stage_retention
        ;;
    verify)
        set -e
        hold_lock
        bash scripts/round/verify_delivery.sh "$(newest_stage)"
        stage_retention
        ;;
    calculator) uv run python scripts/round/round_figures.py --verify ;;
    docx)
        if [ $# -lt 1 ]; then echo "ship docx SOURCE.md" >&2; exit 2; fi
        # The mail carries the five fields and nothing else; the method goes in an attached
        # report, as .docx. Drafts under `private/` carry a status block and a notes-to-self
        # section and the builder strips both, because trimming them by eye eventually sends one.
        uv run python scripts/round/build_report_docx.py "$1" --keep-markdown
        ;;
    draft)
        uv run python scripts/round/ship_mail.py "$@"
        close_gate_issue --dry-run
        ;;
    all)
        set -e
        round="${1:-}"
        stage_prep
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

# Long form: the header of scripts/harness/hold.sh and the runbook's hold row.
#
# stop every laptop job, flag and fleet workflow until lifted by hand: on off status
hold what="on" name="":
    bash scripts/harness/hold.sh {{what}} {{name}}

# The launchd jobs. com.ark.sync runs `just sync` at five past every hour, which banks what
# arrived without a session open, and reads the `ship-now` label (the header of
# scripts/harness/scheduled_sync.sh). com.ark.cycle runs the health check four times a day and
# reports rather than acts; scheduled_cycle.sh says why a restarting watchdog is the wrong
# shape here. com.ark.collectors is the closed CDX parent sweep lane: it runs once at load
# and exits.
#
# **The checkout lives under ~/GitHub so that none of this needs Full Disk Access.** Under
# ~/Documents, which macOS TCC protects, a launchd agent inherits no grant from the terminal
# that installed it and exits 126 with `launchctl list` looking normal, so `install` runs a job
# once as the probe and reports what it did. launchd also starts with a bare PATH, which is why
# the templates carry one that finds just, uv, gh and claude; 127 is that failure.
#
# A second argument names ONE job, because the three are switched on at different times and
# loading all three to get one would start banking unattended a round early.
#
# the launchd jobs that collect, bank and health-check unattended: install remove status
schedule what="install" job="":
    #!/usr/bin/env bash
    set -uo pipefail
    JOBS="com.ark.sync com.ark.cycle com.ark.collectors com.ark.digest"
    if [ -n "{{job}}" ]; then
        case " $JOBS " in
        *" {{job}} "*) JOBS="{{job}}" ;;
        *) echo "schedule: no such job {{job}}, one of: $JOBS" >&2; exit 2 ;;
        esac
    fi
    DOMAIN="gui/$(id -u)"
    case "{{what}}" in
    install)
        set -euo pipefail
        # A hold is lifted only by hand, and an install would lift it one job at a time.
        if bash scripts/harness/hold.sh holds; then
            echo "schedule: the laptop is held; lift it with 'just hold off' first" >&2
            exit 1
        fi
        mkdir -p "$HOME/Library/LaunchAgents" data/logs
        # The hourly job was com.ark.bank once. An installed plist outlives the rename and
        # names a script that no longer exists, firing a 127 every hour with `launchctl
        # list` looking normal, and `remove` cannot reach a name the list above has dropped.
        stale="$HOME/Library/LaunchAgents/com.ark.bank.plist"
        if [ -f "$stale" ]; then
            launchctl bootout "$DOMAIN/com.ark.bank" 2>/dev/null || true
            rm -f "$stale"
            echo "removed the superseded com.ark.bank job"
        fi
        for job in $JOBS; do
            plist="$HOME/Library/LaunchAgents/$job.plist"
            sed -e "s|ARK_ROOT|{{justfile_directory()}}|g" -e "s|ARK_HOME|$HOME|g" \
                "scripts/harness/$job.plist.template" > "$plist"
            launchctl bootout "$DOMAIN/$job" 2>/dev/null || true
            launchctl enable "$DOMAIN/$job"
            # A job still stopping from the bootout refuses the bootstrap once.
            launchctl bootstrap "$DOMAIN" "$plist" || { sleep 2; launchctl bootstrap "$DOMAIN" "$plist"; }
            echo "loaded $job"
        done
        # The probe is the cycle job when it was loaded, because it exits rather than
        # running for hours; otherwise the job just loaded answers for itself.
        probe=com.ark.cycle
        case " $JOBS " in *" com.ark.cycle "*) ;; *) probe="${JOBS%% *}" ;; esac
        echo "running $probe once to find out whether launchd can reach this directory"
        launchctl kickstart -k "$DOMAIN/$probe" 2>/dev/null || true
        sleep 20
        # A job that RUNS for hours has no exit status yet, so a pid is its pass and an exit
        # of 0 is the pass for one that finishes. Reading only the status calls a healthy
        # collector lane a failure.
        line=$(launchctl list | awk -v p="$probe" '$3 == p { print $1, $2 }')
        pid=${line%% *}
        status=${line##* }
        if [ -n "$line" ] && { [ "$pid" != "-" ] || [ "$status" = "0" ]; }; then
            if [ "$pid" != "-" ]; then
                echo "OK: $probe is running as pid $pid"
            else
                echo "OK: $probe exited 0"
            fi
            case " $JOBS " in
            *" com.ark.sync "*) echo "com.ark.sync runs at :05 every hour and appends to data/logs/scheduled_sync.log" ;;
            esac
            case " $JOBS " in
            *" com.ark.collectors "*) echo "com.ark.collectors is the closed CDX lane: it runs once and exits" ;;
            esac
        else
            echo "FAILED: ${line:-$probe is not loaded}"
            echo
            echo "  126 or 1 here means launchd cannot read this checkout. It lives"
            echo "  under ~/GitHub, which macOS does not protect, so the usual cause is"
            echo "  a plist still rendered from an old path, or a checkout moved under a"
            echo "  protected directory: re-run 'just schedule install' from where the"
            echo "  repository is now. 127 means a tool is not on the PATH the"
            echo "  template sets."
            echo
            echo "  Until then a terminal that runs 'just sync' hourly covers the same"
            echo "  ground, because it inherits the grant of the terminal that started it."
            tail -3 data/logs/scheduled_cycle.err 2>/dev/null || true
        fi
        ;;
    status)
        for job in $JOBS; do
            line=$(launchctl list | awk -v j="$job" '$3 == j { print "pid " $1 ", last exit " $2 }')
            echo "$job: ${line:-not loaded}"
        done
        for log in scheduled_sync scheduled_cycle; do
            [ -f "data/logs/$log.log" ] && { echo "--- data/logs/$log.log"; grep '^===== scheduled' "data/logs/$log.log" | tail -2; }
        done
        ;;
    remove)
        for job in $JOBS; do
            launchctl bootout "$DOMAIN/$job" 2>/dev/null || true
            rm -f "$HOME/Library/LaunchAgents/$job.plist"
            echo "removed $job"
        done
        ;;
    *) echo "schedule: install remove status" >&2; exit 2 ;;
    esac
