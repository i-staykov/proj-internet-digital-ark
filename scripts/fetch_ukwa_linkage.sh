#!/usr/bin/env bash
# Stream the JISC UK Web Domain Dataset host link graph and keep only in-window rows.
#
# **Why streaming rather than downloading.** The file is 20.9 GB gzipped, and the only
# copy anyone has found is a single Wayback capture, `20221031190607`, whose CDX row
# gives length 20,930,377,408. The live path at webarchive.org.uk answers 200 with a
# 159-byte redirect stub, the dataset DOI 404s, and archive.org holds no mirror, all
# checked 2026-08-20. We hold exactly 2,147,483,648 bytes of it, which is 2^31 to the
# byte and therefore a truncation artifact rather than the file's real end.
#
# Decompressing in the pipe and keeping only the 1996-2001 rows means the 209 GB of
# text never lands on disk and a stream that drops still leaves everything it reached.
# **Partial output is useful output here**, which is the property that makes this worth
# attempting at all against a source that has already dropped once.
#
# The row format is `year|source_host|target_host<TAB>count`, so the filter is on the
# leading year field and nothing is parsed that this does not need.
#
# **Run it with the collectors stopped.** It is a heavy client at the same host they
# use, and the project has been refused by the Internet Archive three times.
#
# **`--probe` asks whether the replay is serving at all, in one cheap request**, and is
# what the overnight loop calls. As of 2026-08-20 the replay returns HTTP 504 from nginx
# reproducibly, so an unconditional hourly retry would be a heavy request against a
# known failure, which is the kind of thing that gets a project blocked. The probe takes
# 15 seconds and only a success justifies the full stream.
#
# Usage: bash scripts/fetch_ukwa_linkage.sh [out.tsv.gz]
#        bash scripts/fetch_ukwa_linkage.sh --probe

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

URL="https://web.archive.org/web/20221031190607id_/https://www.webarchive.org.uk/datasets/ukwa.ds.2/linkage/host-linkage.tsv.gz"
UA="InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
LOG="data/logs/ukwa_linkage.log"
mkdir -p data/logs data/raw/ukwa
note() { printf '%s %s\n' "$(date -u '+%F %T UTC')" "$*" | tee -a "$LOG"; }

if [ "${1:-}" = "--probe" ]; then
    code=$(curl -sS -o /dev/null -w '%{http_code}' -r 0-1023 \
        -A "$UA" --connect-timeout 10 --max-time 15 "$URL" 2>/dev/null)
    if [ "$code" = "200" ] || [ "$code" = "206" ]; then
        note "PROBE: replay answers $code. The 20.9 GB capture may now be fetchable:"
        note "PROBE: stop the collectors and run scripts/fetch_ukwa_linkage.sh (see C-30)"
        exit 0
    fi
    note "probe: replay still not serving (HTTP $code)"
    exit 1
fi

OUT="${1:-data/raw/ukwa/host-linkage-inwindow.tsv.gz}"

mkdir -p "$(dirname "$OUT")"

note "streaming $URL"
note "keeping only rows whose year field is 1996-2001, into $OUT"

# `--retry` covers the 502/504s the replay of a 20.9 GB record throws when it is busy.
# No `--retry-all-errors`: a 403 means the archive is refusing us and retrying it is
# exactly the behaviour that gets a project blocked.
curl -sS --location --retry 5 --retry-delay 30 --retry-max-time 1800 \
     --speed-limit 1024 --speed-time 300 \
     -A "$UA" "$URL" 2>>"$LOG" \
  | gunzip -c 2>>"$LOG" \
  | awk -F'|' '$1 >= 1996 && $1 <= 2001' \
  | gzip -c > "$OUT.part"

status=${PIPESTATUS[0]}
note "curl exit $status"

if [ -s "$OUT.part" ]; then
    mv "$OUT.part" "$OUT"
    rows=$(gunzip -c "$OUT" | wc -l | tr -d ' ')
    bytes=$(wc -c < "$OUT" | tr -d ' ')
    note "kept $rows in-window rows, $bytes bytes compressed"
else
    note "nothing arrived; leaving $OUT.part in place for inspection"
fi
