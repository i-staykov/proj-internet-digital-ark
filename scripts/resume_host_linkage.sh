#!/usr/bin/env bash
# Finish the UKWA host link graph, which we have been reading at 10.26% for a month.
#
# `data/raw/ukwa/host-linkage.tsv.gz` is exactly 2,147,483,648 bytes, which is 2 GiB
# to the byte, and `gzip -t` fails on it with "unexpected end of file". The archive
# holds 20,928,588,915. So the local copy is a clean truncation at a 2 GiB boundary
# and we have read a tenth of a master-eligible source. That tenth already gave
# 231,865 evidence rows over 183,515 distinct domains and 116,467 assigned pairs.
#
# **Why a resume works at all.** A gzip stream cannot be decompressed from an
# arbitrary offset, but ours is a PREFIX: bytes 0 to 2147483647 in order. Appending
# 2147483648 onward reconstructs a single valid stream, so this is a resume rather
# than a re-download, and the 2 GiB already on disk is not fetched twice.
#
# **The original address is a trap and must not be used.** `webarchive.org.uk` still
# answers HTTP 200 for this path with a 159-byte HTML stub, so a download from it
# looks like it worked and is not the data. The dataset DOI no longer resolves. The
# Wayback `id_` capture is the only route, and it answers ranged GETs: a probe for
# `bytes=0-0` returns 206 with `content-range: bytes 0-0/20928588915`.
#
# Chunked because a single 18.8 GB GET is what truncated the file the first time.
# Each chunk is verified by byte count before it is kept, so a short read is retried
# rather than appended, which is the failure mode that produced the 2 GiB file.
#
# Takes an absolute epoch deadline so it outlives the session that started it.
#
#     bash scripts/resume_host_linkage.sh <deadline_epoch> [chunk_mb]

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DEADLINE="${1:-0}"
CHUNK_MB="${2:-256}"
CHUNK=$((CHUNK_MB * 1024 * 1024))
TOTAL=20928588915
URL="https://web.archive.org/web/2019id_/https://www.webarchive.org.uk/datasets/ukwa.ds.2/linkage/host-linkage.tsv.gz"
UA="internet-digital-ark/1.0 (research; ivaylo.staykov@student.hpi.uni-potsdam.de)"
OUT="data/raw/ukwa/host-linkage.tsv.gz"
LOG="data/logs/host_linkage_resume.log"

mkdir -p data/logs data/raw/ukwa
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" >> "$LOG"; }

if [ "$DEADLINE" -le "$(date +%s)" ]; then
    note "deadline $DEADLINE is not in the future; refusing to start"
    exit 1
fi

# Never two copies at once. Running two geoindex pulls concurrently once emptied
# three of each other's pages, and the same mistake here would corrupt a 20 GB file
# by interleaving appends.
if pgrep -f "resume_host_linkage.sh" | grep -qv "^$$\$"; then
    note "another copy is already running; refusing to start a second"
    exit 1
fi

note "start: until $(date -u -r "$DEADLINE" '+%F %T UTC' 2>/dev/null || echo "$DEADLINE"), chunk=${CHUNK_MB}MB"

fail=0
while :; do
    have=$(stat -f %z "$OUT" 2>/dev/null || stat -c %s "$OUT" 2>/dev/null || echo 0)
    if [ "$have" -ge "$TOTAL" ]; then
        note "complete: $have of $TOTAL bytes"
        if gzip -t "$OUT" 2>/dev/null; then
            note "gzip -t PASS over the whole file"
        else
            note "gzip -t FAIL: the stream is complete by length but not by content"
        fi
        break
    fi
    if [ "$(date +%s)" -ge "$DEADLINE" ]; then
        note "deadline reached at $have of $TOTAL bytes ($((have * 100 / TOTAL))%), stopping cleanly"
        break
    fi

    end=$((have + CHUNK - 1))
    [ "$end" -ge "$TOTAL" ] && end=$((TOTAL - 1))
    want=$((end - have + 1))
    tmp="${OUT}.chunk"
    rm -f "$tmp"

    # `--http1.1` is not cosmetic. Over HTTP/2 the archive aborts a large ranged
    # read with "stream N was not closed cleanly: INTERNAL_ERROR", and curl still
    # reports 206, so the status alone says the transfer succeeded while the body
    # is empty. Measured here on the first chunk: http=206, got=0, want=268435456.
    code=$(curl -sS -L --http1.1 --max-time 900 --retry 0 \
        -A "$UA" -r "${have}-${end}" -o "$tmp" \
        -w '%{http_code}' "$URL" 2>>"$LOG")
    got=$(stat -f %z "$tmp" 2>/dev/null || stat -c %s "$tmp" 2>/dev/null || echo 0)

    # A short read is the failure that produced the 2 GiB file, so the count is
    # checked before anything is appended. 206 is the only success here: a 200 means
    # the range was ignored and the body starts at byte 0, which would corrupt the
    # stream if appended.
    if [ "$code" = "206" ] && [ "$got" -eq "$want" ]; then
        cat "$tmp" >> "$OUT"
        rm -f "$tmp"
        fail=0
        now=$((have + got))
        note "ok  $((now * 100 / TOTAL))%  $now/$TOTAL bytes"
    else
        rm -f "$tmp"
        fail=$((fail + 1))
        note "retry $fail: http=$code got=$got want=$want at offset $have"
        # Back off on refusal, and honour the archive's own pace. 429/503/504 are
        # the codes the project rule names; a 0 is a dropped connection.
        sleep $((fail < 6 ? fail * 20 : 120))
        if [ "$fail" -ge 40 ]; then
            note "40 consecutive failures at offset $have; stopping rather than hammering"
            break
        fi
    fi
done

note "exit at $(stat -f %z "$OUT" 2>/dev/null || echo 0) bytes"
