#!/usr/bin/env bash
# One CDX question for one exact host, taken through the fleet host's single slot.
#
# **The two-client limit of C-77 binds the CDX CHANNEL, not a machine.** Both clients are the
# laptop's sweeps, and they are the guaranteed earner; a leg on the VPS that asked
# `web.archive.org/cdx` directly would be a third client nobody was accounting for, at the
# moment the archive has already refused this project outright three times. So a price or
# verify leg that needs to see whether one named host was captured asks through here:
# every query on the host serialises behind one lock, waits two seconds after the previous
# one, and honours `Retry-After` when the service says to slow down.
#
# **It refuses a sweep shape rather than trusting the caller not to write one.** A wildcard
# host, a `matchType` other than exact and a `collapse` walk are all the shapes that turn one
# question into a namespace crawl, and the leg brief asking for "a sample" is not what stops
# that happening. An exact host, a bounded row limit, one page.
#
# Usage:
#   bash scripts/harness/cdx_slot.sh www.example.com
#   bash scripts/harness/cdx_slot.sh example.com 'from=1996&to=2001&fl=original,timestamp'
#
# Prints the CDX rows on stdout and nothing else, so a caller can count lines. Exit 0 with
# no rows means the host has no captures; exit 3 means the slot was busy for the whole wait,
# 4 that the service asked for a longer pause than the leg has, and 5 a refused shape.
set -euo pipefail

HOST="${1:?usage: cdx_slot.sh <exact host> [extra CDX query]}"
EXTRA="${2:-}"
ENDPOINT="https://web.archive.org/cdx/search/cdx"
# Honest, and it names the project so the archive can find a human. Same string as src/ark.
UA="internet-digital-ark/1.0"
SLOT="${ARK_CDX_SLOT:-/projects/ark-data/cdx.slot}"
SPACING="${ARK_CDX_SPACING:-2}"
LIMIT="${ARK_CDX_LIMIT:-200}"
# Long enough that a leg waits for the other leg's query rather than skipping its sample,
# short enough that it cannot sit out its own ceiling.
WAIT="${ARK_CDX_WAIT:-120}"
MAX_RETRY_AFTER="${ARK_CDX_MAX_RETRY_AFTER:-60}"

die() { echo "cdx_slot: $2" >&2; exit "$1"; }

# An exact host and nothing else. `*` in either position, a bare registrable with a path, or
# a caller-supplied matchType or collapse are the sweep shapes.
case "$HOST" in
    *[!a-zA-Z0-9.-]* | *".."* | .* | -* | "") die 5 "not a plain hostname: $HOST" ;;
esac
printf '%s' "$HOST" | grep -qE '^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$' \
    || die 5 "not a plain hostname: $HOST"
case "$EXTRA" in
    *matchType* | *collapse* | *url=* | *\** ) die 5 "the extra query would walk a namespace: $EXTRA" ;;
esac

QUERY="url=$HOST&matchType=exact&output=json&limit=$LIMIT&fl=original,timestamp,statuscode"
[ -z "$EXTRA" ] || QUERY="$QUERY&$EXTRA"

# `ARK_CDX_DRY_RUN=1` prints the question and asks nobody, so a leg (and this repository's
# tests) can check the shape it is about to send without spending a seat on the channel.
if [ -n "${ARK_CDX_DRY_RUN:-}" ]; then
    echo "$ENDPOINT?$QUERY"
    exit 0
fi

# No lock, no query. A host without `flock` cannot serialise anything, and an
# unserialised query here is exactly the third client the limit exists to prevent.
command -v flock >/dev/null 2>&1 || die 3 "no flock on this host, so the slot cannot be held"

mkdir -p "$(dirname "$SLOT")" 2>/dev/null || true
exec 9>>"$SLOT" || die 3 "cannot open the slot at $SLOT"
flock -w "$WAIT" 9 || die 3 "the slot was busy for ${WAIT}s; the sample is not worth a second client"

# The spacing is measured from the LAST query through this slot, not from this process
# starting, which is the whole reason the timestamp lives in the lock file: two legs a second
# apart each thought they were the first one.
LAST=$(cat "$SLOT" 2>/dev/null | tail -1 | tr -dc '0-9')
NOW=$(date +%s)
if [ -n "$LAST" ] && [ "$LAST" -le "$NOW" ]; then
    GAP=$(( NOW - LAST ))
    [ "$GAP" -ge "$SPACING" ] || sleep $(( SPACING - GAP ))
fi

HEADERS=$(mktemp "${TMPDIR:-/tmp}/cdx_slot.XXXXXX")
BODY=$(mktemp "${TMPDIR:-/tmp}/cdx_slot.XXXXXX")
trap 'rm -f "$HEADERS" "$BODY"' EXIT

STATUS=$(curl -sS --max-time 90 -A "$UA" -D "$HEADERS" -o "$BODY" -w '%{http_code}' \
    "$ENDPOINT?$QUERY" || echo 000)
date +%s > "$SLOT"

# A rate limit is a signal to adapt, not to retry harder (brief section VII). One wait, and
# only when the service named a wait a leg can afford; otherwise the leg reports the refusal.
if [ "$STATUS" = 429 ] || [ "$STATUS" = 503 ]; then
    RETRY=$(grep -i '^retry-after:' "$HEADERS" | tail -1 | tr -dc '0-9')
    [ -n "$RETRY" ] || RETRY=$MAX_RETRY_AFTER
    [ "$RETRY" -le "$MAX_RETRY_AFTER" ] || die 4 "the service asked for ${RETRY}s, longer than a leg may hold the slot"
    echo "cdx_slot: HTTP $STATUS, honouring Retry-After ${RETRY}s" >&2
    sleep "$RETRY"
    STATUS=$(curl -sS --max-time 90 -A "$UA" -D "$HEADERS" -o "$BODY" -w '%{http_code}' \
        "$ENDPOINT?$QUERY" || echo 000)
    date +%s > "$SLOT"
fi

[ "$STATUS" = 200 ] || die 4 "HTTP $STATUS for $HOST"
cat "$BODY"
