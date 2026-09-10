#!/usr/bin/env bash
# Fold whatever the collectors have finished into the store, on a loop.
#
# One loop rather than one per source, because DuckDB takes a single writer and
# two ingest loops would collide at whatever interval they happened to share.
# Serialising them here costs nothing: each is seconds of work against hours of
# collection.
#
# Only COMPLETE journals are ingested. A collector writes `<name>.part` and
# renames on exit, so anything matching `*.jsonl.gz` is finished; ingesting a
# half-written journal would ledger it at a partial hash and make the rest of
# that run permanently unreachable.
#
# **That rule is right about LIVE partials and wrong about ABANDONED ones**, and
# the difference is measurable in EE. A collector killed by a deadline, a signal
# or a crash never renames, so its work sits in a `.part` no glob will ever
# match. Locally on 2026-08-25 that was three files holding 1,451 year rows and
# about 919 equivalent-English, the oldest abandoned on 18 August; remotely it
# was five files, 62 MB and 3,599 EE. **The staleness test separates the two
# cases**: nothing has written to an abandoned partial for hours, while a live
# one grows every few seconds. 90 minutes is comfortably past any batch's write
# interval, so a partial older than that belongs to a dead run and can be
# promoted to its final name safely.
#
# Usage: bash scripts/harness/maintain.sh [iterations] [sleep_seconds]
set -uo pipefail

ITERATIONS="${1:-30}"
PAUSE="${2:-900}"
LOG="data/logs/maintain.log"
mkdir -p data/logs

# The VPS address is deliberately not in the repository: the repo is public and the
# address is private infrastructure. Set ARK_VPS in the environment or in local.env
# at the repo root (gitignored), e.g. ARK_VPS=user@host.
ROOT_FOR_ENV="$(cd "$(dirname "$0")" && git rev-parse --show-toplevel 2>/dev/null || pwd)"
[ -f "$ROOT_FOR_ENV/local.env" ] && . "$ROOT_FOR_ENV/local.env"
VPS="${ARK_VPS:?set ARK_VPS (user@host), in the environment or in local.env}"
VPS_REPO="${ARK_VPS_REPO:-/projects/proj-internet-digital-ark}"

# One `ark ingest` per SOURCE, not one per file. This is the whole fix for a
# measured problem: the four per-file loops this replaces spawned 636 separate
# invocations per pass at the current file counts, each one opening the store
# read-write, reading the ledger, finding the file already banked and closing. With
# PAUSE at 150s that is 636 write-lock acquisitions every two and a half minutes,
# and the lock was measured **held 16 of 18 samples over 90 seconds, 89%**, on
# 11 August. Every reader queued behind it: the pricer, the state generator, the
# residual auditor, and `ark seed`, which could not get in at all. The log carries
# 7,646 `already ingested, skipping` lines across 6,156 invocations, which is the
# same story counted a second way.
#
# Batching changes nothing about what gets ingested. `ingest_files` sorts the paths
# itself, skips per file from the ledger, and wraps each file in its own
# `try/except` that counts `files_failed` and continues, so a bad file is contained
# exactly as it was before and now shows up in the summary instead of scrolling past
# in a shell loop. It also collapses 636 `record_metrics` rows and 636
# `_enqueue_unverified` passes into one each.
#
# Re-offering every journal on disk stays deliberate and unchanged: ledgering is by
# content hash, so an already-ingested journal costs milliseconds, and it is what
# rescues a journal orphaned by a failed ingest. On 1 August two journals holding 92
# archives' worth of work were written, failed against a locked store, and nothing
# would ever have offered them again.
#
# The one limit to watch is the argument list. 636 paths is roughly 30 KB, far below
# ARG_MAX, but a glob grown into the thousands would need `xargs`: an `ls` over
# 19,231 usenet archives has already overflowed exec once in this project.
ingest_all() {
    local key="$1"
    shift
    # An unmatched glob arrives as the literal pattern, so test the first argument
    # rather than trusting that the shell expanded anything.
    [ -e "$1" ] || return 0
    uv run ark ingest "$key" "$@" >> "$LOG" 2>&1
}

for i in $(seq 1 "$ITERATIONS"); do
    echo "$(date '+%F %T') pass ${i}" >> "$LOG"

    # Fetch the other machine's journals before ingesting anything, because work
    # that is still on the VPS appears in no number measured here. Leaving this to
    # a human has failed twice: 5,793 year-records sat remote for a day and a half
    # in July, and 1,500 queries sat remote overnight on 7 August while a monitor
    # with a stale filename glob reported everything home.
    #
    # `--ignore-existing` never rewrites a journal already here, and a failure is
    # not fatal: the VPN is often down, and a pass that cannot reach the VPS should
    # still fold in everything local. `-o BatchMode=yes` so a missing key fails fast
    # rather than blocking the loop on a password prompt.
    rsync -a --ignore-existing --timeout=120 \
        -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        "${VPS}:${VPS_REPO}/data/raw/cdx/cdx_*.jsonl.gz" data/raw/cdx/ \
        >> "$LOG" 2>&1 || echo "  vps unreachable this pass, continuing" >> "$LOG"

    # **And the RDAP journals, which this block did not fetch until 2026-08-21.**
    # The VPS was put on RDAP that evening and produced 67 journals in three hours;
    # every one of them was stranded, because the pattern above names only `cdx_`.
    # That is the same defect the comment above describes, repeated on a new prefix,
    # which is the argument for fetching by DIRECTORY rather than by a hand-written
    # glob: a new collector on the remote machine should not be able to write work
    # that no pass here can see.
    mkdir -p data/raw/rdap
    rsync -a --ignore-existing --timeout=120 \
        -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
        "${VPS}:${VPS_REPO}/data/raw/rdap/rdap_*.jsonl.gz" data/raw/rdap/ \
        >> "$LOG" 2>&1 || echo "  vps rdap unreachable this pass, continuing" >> "$LOG"

    # **And the ABANDONED partials, which is the third time this defect has bitten.**
    # The two globs above take `*.jsonl.gz` and never `*.jsonl.gz.part`, so a batch
    # that dies mid-round leaves its work on the VPS where no pass can see it. On
    # 2026-08-25 that was **five files, 62 MB, 502,293 records and 3,599.2 net-new
    # equivalent-English**, the oldest stranded since 22 August. The comment above
    # already argued for fetching by directory rather than by hand-written glob, and
    # this is that argument applied a third time.
    #
    # **Only STALE partials are taken, and the staleness test is the whole safety
    # argument.** A live `.part` is still growing, and copying it here under its
    # final name would ingest a prefix; when the completed journal arrived later, the
    # ledger keys on content, so the same name with a different hash would be REFUSED
    # and the full journal lost. 90 minutes is comfortably past any batch's write
    # interval, so anything older than that belongs to a dead run.
    stale=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$VPS" \
        "find '$VPS_REPO'/data/raw/rdap '$VPS_REPO'/data/raw/cdx -name '*.jsonl.gz.part' -mmin +90 2>/dev/null" \
        2>/dev/null)
    for remote in $stale; do
        base=$(basename "$remote" .part)
        case "$base" in
            rdap_*) local_dir=data/raw/rdap ;;
            cdx_*)  local_dir=data/raw/cdx ;;
            *) continue ;;
        esac
        [ -e "$local_dir/$base" ] && continue
        rsync -a --timeout=120 -e "ssh -o ConnectTimeout=15 -o BatchMode=yes" \
            "${VPS}:${remote}" "$local_dir/$base" >> "$LOG" 2>&1 \
            && echo "  recovered abandoned partial $base" >> "$LOG"
    done

    bash scripts/sources/usenet/ingest_new_usenet.sh auto >> "$LOG" 2>&1

    # Every journal on disk is re-offered, not only the ones this pass produced.
    # See `ingest_all` above for why that is cheap and what it rescues.
    ingest_all usenet_dated      data/raw/usenet/usenet_dated_*.jsonl.gz
    ingest_all usenet_candidates data/raw/usenet/usenet_candidates_*.jsonl.gz

    # CDX candidate journals, which is what turns a discovered name into a net-new
    # domain.
    # Promote LOCAL abandoned partials before the ingest sees them. Same 90-minute
    # staleness rule as the remote recovery below, and the same reason: a partial
    # with no final counterpart is a dead run's work, not a live run's file.
    for part in data/raw/cdx/*.jsonl.gz.part data/raw/rdap/*.jsonl.gz.part; do
        [ -e "$part" ] || continue
        final="${part%.part}"
        [ -e "$final" ] && continue
        if [ -z "$(find "$part" -mmin +90 2>/dev/null)" ]; then continue; fi
        cp "$part" "$final" && echo "  promoted abandoned partial $(basename "$final")" >> "$LOG"
    done

    ingest_all cdx_snapshot      data/raw/cdx/cdx_*.jsonl.gz

    # The SAME journals one level down, which is free and was not done until
    # 2026-09-04. `ark.cdx` used to ask `fl=timestamp` and keep `{domain, years}`, so
    # 2,984,321 answers across 1,163 journals record no host at all; the query now asks
    # for `timestamp,original` and every record carries a `hosts` map. This converts that
    # map and ingests it, so a gap query about a domain we already hold also harvests the
    # hosts beneath it, at no extra request. Journals written before the change yield
    # nothing here, which is correct: the information is not in them.
    uv run python scripts/engines/cdx_gap_hostgrain.py >> "$LOG" 2>&1 || true
    if compgen -G "data/raw/cdx_gap_hostgrain/cdx_gap_*.jsonl.gz" > /dev/null; then
        uv run ark ingest-hostnames data/raw/cdx_gap_hostgrain >> "$LOG" 2>&1 || true
    fi

    # And the suffix sweep's own journals, the other half of the standing hostname
    # priority: `platform_sweep.sh` writes `{url, timestamp}` continuously and nothing
    # here read them, so a sweep's work only became records when somebody ingested by
    # hand. Same failure as the RDAP journals below, on a newer collector.
    if compgen -G "data/raw/cdx_suffix/suffix_*.jsonl.gz" > /dev/null; then
        uv run ark ingest-hostnames data/raw/cdx_suffix >> "$LOG" 2>&1 || true
        # **And the same journals' REGISTRABLE half, which had been dropped since
        # 2026-08-27.** The sweep's rows carry a capture stamp for a bare registrable as
        # often as for a host: 19,744,519 of them across the corpus, which the hostname
        # funnel correctly refuses because they belong in `domain_year`. The converter that
        # collapses them into the approved `cdx_snapshot` shape was run by hand, and the
        # newest file it had produced was five weeks old, so every sweep since then had its
        # registrable half discarded. Free evidence, from requests already paid for, and it
        # is also the capacity Ivo's standing rule reserves for registrables.
        uv run python scripts/engines/cdx_suffix_convert.py >> "$LOG" 2>&1 || true
        ingest_all cdx_snapshot data/raw/cdx/cdx_suffix_*.jsonl.gz
    fi

    # **The three body-URL lanes built on 2026-09-04, which this loop did not know about.**
    # Usenet, mailing lists and Enron all ship `{item, year, text}` shards and each has its
    # own approved ingest, and every one of them was folded by hand. That is the fifth time
    # in this project that a collector's work was invisible until a loop read it, after the
    # VPS journals in July, the RDAP journals in August and both halves of the suffix sweep
    # earlier today. Three of the five were created the same day the pattern was named, which
    # is the argument for adding the line here as part of building a lane rather than after.
    #
    # Each is idempotent per shard and skips on content, so a pass over unchanged shards costs
    # a hash and nothing else.
    for pool in data/raw/usenet_*_items; do
        [ -d "$pool" ] && uv run ark ingest-usenet-hostnames "$pool" >> "$LOG" 2>&1 || true
    done
    if [ -d data/raw/maillists_items ]; then
        uv run ark ingest-maillist-hostnames data/raw/maillists_items >> "$LOG" 2>&1 || true
    fi
    if [ -d data/raw/enron_items ]; then
        uv run ark ingest-enron-hostnames data/raw/enron_items >> "$LOG" 2>&1 || true
    fi

    # Registry journals, which this loop did not know about until 8 August. The
    # RDAP sweep of the candidate pool wrote 19,705 in-window creation dates,
    # roughly 12,000 equivalent-English, and every one of them sat unread on disk
    # because nothing here looked. A collector whose journals no loop ingests is
    # a collector whose work is invisible to every measurement taken afterwards,
    # which is the same failure the VPS journals caused twice.
    ingest_all rdap_snapshot     data/raw/rdap/rdap_*.jsonl.gz

    # **Measure the promotion tranche every pass, and never bank it here.** The split
    # is deliberate: `build_promotion_journals.py` prints its ingests rather than
    # running them because whether to bank a tranche is a judgement, and
    # `bank_promotion.sh` exists for when that judgement is made. What was missing is
    # that nobody SAW the number, so a tranche could sit unmeasured for days.
    #
    # It compounds, which is why it belongs on the loop rather than on a schedule of
    # its own: a mention is promoted when some OTHER source dates its domain, so every
    # master ingest above can unlock pool names that the previous pass could not admit.
    # On 2026-08-25 the `.ie` register landing the day before contributed 157 of 2,476
    # pairs, and the tranche measured 1,556.6 equivalent-English.
    #
    # No `--write`, so this touches nothing.
    uv run python scripts/engines/build_promotion_journals.py --tag "dryrun$(date -u '+%Y%m%d')" \
        >> "$LOG" 2>&1 || echo "  promotion dry run failed this pass, continuing" >> "$LOG"

    sleep "$PAUSE"
done
echo "$(date '+%F %T') maintenance loop finished" >> "$LOG"
