#!/usr/bin/env bash
# Fetch the 19 item-level CDX indexes of the archive.org collection
# `Poland_pl-ccTLD_2001-12-31`, approved master by Ivo on 2026-09-10.
#
# The ARCs of that collection are `private: true` and are never touched. Only the
# `<item>.cdx.gz` index is fetched, and each one is public and served with 200.
#
# `receipts.tsv` beside this script holds the byte size and sha256 the scout read off
# every index on 2026-09-10. A file that does not match is deleted rather than kept,
# because a truncated index would date hosts from a half-read file and no later step
# could tell. That check is the whole reason this is a script and not a curl loop.
#
# Host is `archive.org/download/`, which is a different service from the
# `web.archive.org/cdx` endpoint the collectors meter against (C-77), so this runs
# beside them rather than as a third client on their channel.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

DEST="data/raw/poland_cdx"
LOG="data/logs/poland_fetch.log"
UA="InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
mkdir -p "$DEST" data/logs
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

ok=0
fail=0
while IFS=$'\t' read -r item bytes sha; do
    [ -n "$item" ] || continue
    out="$DEST/$item.cdx.gz"
    if [ -f "$out" ] && [ "$(stat -f %z "$out" 2>/dev/null || stat -c %s "$out")" = "$bytes" ]; then
        note "$item: already on disk at $bytes B"
        ok=$((ok + 1))
        continue
    fi
    url="https://archive.org/download/$item/$item.cdx.gz"
    note "$item: fetching $bytes B"
    if ! curl -fsSL --retry 5 --retry-delay 10 -A "$UA" -o "$out.part" "$url"; then
        note "$item: FETCH FAILED"
        rm -f "$out.part"
        fail=$((fail + 1))
        continue
    fi
    got_bytes="$(stat -f %z "$out.part" 2>/dev/null || stat -c %s "$out.part")"
    got_sha="$(shasum -a 256 "$out.part" | cut -d' ' -f1)"
    if [ "$got_bytes" != "$bytes" ] || [ "$got_sha" != "$sha" ]; then
        note "$item: MISMATCH, $got_bytes B sha $got_sha, discarding"
        rm -f "$out.part"
        fail=$((fail + 1))
        continue
    fi
    mv "$out.part" "$out"
    note "$item: verified"
    ok=$((ok + 1))
done < "scripts/sources/poland/receipts.tsv"

note "poland cdx fetch done: $ok verified, $fail failed"
[ "$fail" -eq 0 ]
