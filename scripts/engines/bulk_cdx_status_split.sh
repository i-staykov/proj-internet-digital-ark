#!/usr/bin/env bash
# Stream one bulk IA CDX file once and split its in-window rows by HTTP status.
#
# The node CDX and the Dartmouth items were banked from their 200 rows only, while the sweep has
# taken 2xx and 3xx since ADR-011. This reads a `CDX N b a m s ...` file from a URL without
# storing it (57.6 GB would break the disk floor) and writes three things under <out>:
#   <prefix>_3xx.jsonl.gz   `{url, timestamp}` journals of in-window 3xx rows, ingestable
#   <prefix>_4xx.jsonl.gz   the same for 4xx, priced only: ADR-011 keeps them out
#   <prefix>_status.tsv     the in-window status histogram and the row counts
# Each is written as `.part` and renamed only after the stream ends cleanly, so a dropped
# connection leaves nothing an ingest could mistake for a whole file.
#
# Usage: bash scripts/engines/bulk_cdx_status_split.sh <url> <out dir> <prefix>
set -uo pipefail

URL="${1:?url of a .gz CDX file}"
OUT="${2:?output directory}"
PREFIX="${3:?journal prefix, e.g. hostcdx_ia600702}"
UA="InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
mkdir -p "$OUT"

# One long transfer dropped at 7% on 2026-09-22 and a gzip stream cannot resume, so the file is
# fetched in ranges: each chunk lands on disk, is checked against its expected size, retried
# whole if short, and only then fed on in order.
CHUNK="${ARK_CHUNK_BYTES:-$((512 * 1024 * 1024))}"
fetch() {
    case "$URL" in
    file://*) cat "${URL#file://}"; return ;;
    esac
    local size off end tries part="$OUT/.${PREFIX}.chunk"
    size=$(curl -sSfIL -A "$UA" "$URL" | awk -F': ' 'tolower($1)=="content-length" {n=$2} END {print n+0}')
    [ "$size" -gt 0 ] || { echo "no content-length for $URL" >&2; return 1; }
    for ((off = 0; off < size; off += CHUNK)); do
        end=$((off + CHUNK - 1)); [ "$end" -ge "$size" ] && end=$((size - 1))
        for tries in 1 2 3 4 5 6; do
            curl -sSfL -A "$UA" -r "$off-$end" -o "$part" "$URL" \
                && [ "$(wc -c < "$part")" -eq $((end - off + 1)) ] && break
            echo "range $off-$end try $tries failed, retrying in 60s" >&2
            sleep 60
        done
        [ "$(wc -c < "$part" 2>/dev/null || echo 0)" -eq $((end - off + 1)) ] || return 1
        cat "$part"
    done
    rm -f "$part"
}

fetch | gzip -cd | awk \
    -v j3="gzip > '$OUT/${PREFIX}_3xx.jsonl.gz.part'" \
    -v j4="gzip > '$OUT/${PREFIX}_4xx.jsonl.gz.part'" \
    -v hist="$OUT/${PREFIX}_status.tsv.part" '
    { rows++ }
    length($2) == 14 && substr($2, 1, 4) >= "1996" && substr($2, 1, 4) <= "2001" {
        # the SURT head of a node CDX is IP literals, which name no host
        if ($1 ~ /^[0-9]/) { ip++; next }
        inwin++
        s[$5]++
        line = sprintf("{\"url\": \"%s\", \"timestamp\": \"%s\"}", $3, $2)
        if ($5 ~ /^3[0-9][0-9]$/) print line | j3
        else if ($5 ~ /^4[0-9][0-9]$/) print line | j4
    }
    END {
        printf "rows\t%d\nin_window\t%d\nip_literal_in_window\t%d\n", rows, inwin, ip > hist
        for (k in s) printf "status_%s\t%d\n", k, s[k] > hist
        close(j3); close(j4); close(hist)
    }'
status=("${PIPESTATUS[@]}")
if [ "${status[0]}" != 0 ] || [ "${status[1]}" != 0 ] || [ "${status[2]}" != 0 ]; then
    echo "stream failed (fetch ${status[0]}, gzip ${status[1]}, awk ${status[2]}); .part files left" >&2
    exit 1
fi
for f in "$OUT/${PREFIX}_3xx.jsonl.gz" "$OUT/${PREFIX}_4xx.jsonl.gz" "$OUT/${PREFIX}_status.tsv"; do
    # awk opens a pipe only when it writes a row, so a status with no rows has no part yet
    [ -e "$f.part" ] || gzip -c < /dev/null > "$f.part"
    mv "$f.part" "$f"
done
cat "$OUT/${PREFIX}_status.tsv"
