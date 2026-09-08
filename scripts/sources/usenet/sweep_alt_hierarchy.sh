#!/usr/bin/env bash
# Read the `alt` hierarchy's body URLs, the partition C-68 was measured WITHOUT.
#
# **Why this needs no approval.** `usenet_body_url_hostnames / link_source` is master
# (C-68, Ivo 2026-09-04). That decision was measured over "every hierarchy of the
# catalogue except `alt`, all read whole": thirteen pools, 224 GB, 119,640 EE after the
# alias seam and the sampled fiction rate. So `alt` is the same artifact, the same
# extractor and the same class, on the partition nobody has read. C-77 says a different
# partition is a fresh lead rather than a closed one.
#
# **What it is worth, and why the order is what it is.** Two measurements on 2026-09-08,
# both priced with `price_hostnames.py` against the live store.
#   Three mid-size groups, 307,750,500 B (`alt.lawyers`, `alt.music.mp3`,
#   `alt.folklore.computers`): 11,587 distinct host-years, 3,435 already in the store,
#   **410 net-new host-years worth 222.4278 EE**, plus 91 registrable pairs worth 50.7506
#   EE. Of those bytes only 178 MB was in window, so 1.25 EE per in-window MB.
#   Then the two biggest discussion groups, 1,872,269,724 B (`alt.answers`, `alt.religion`):
#   43,590 distinct host-years, 17,385 already in the store, **NET-NEW 0, 0.0000 EE**.
# So the big groups are saturated, and biggest-first was exactly backwards: `alt.answers` is
# the FAQ group, its URLs are the most-posted URLs on Usenet, and the thirteen pools C-68
# already read hold every one of them. `alt.religion` returned 276,256 posts and NONE in
# window at all, as `alt.folklore.computers` did, so a group's bytes are not its evidence.
# The order is therefore ASCENDING size, and the 2 MB floor turned out to be the wrong edge.
# Measured after the 2 to 150 MB band was read whole (4,843 groups, 62 shards): it realises
# **134 EE/GB**. The band BELOW it, 0.3 to 2 MB, 4,004 groups and 3.6 GB, realises
# **1,303.0012 EE at hostname grain plus 528.5108 EE of registrable pairs, so 509 EE/GB**, almost
# four times better, and only 6.4% of it is the `www.<held name>` alias seam against 73.7% for
# Arquivo's crawl. The reason is saturation: 63% of a small group's posts fall inside 1996-2001
# and its URLs are the ones nobody else reposted, while a popular group's URLs are already held
# from the thirteen pools C-68 read. **So the smallest groups are the densest, not the emptiest**,
# and the assumption that "under 2 MB is usually an archive with no in-window post" was wrong.
# The band edges are parameters now, and each band's realised rate is measured before the next.
#
# **Which host this touches.** `archive.org/download/usenet-alt`, an item download. That
# is NOT `web.archive.org/cdx`, which the two collectors meter, so this runs beside them
# and is not a third CDX client (C-77, rule 6). One connection at a time per batch, an
# honest User-Agent naming the project and a contact.
#
# **Why it streams.** 193 GB of zips against 183 GB of free space, so a batch is fetched,
# extracted to `{item, year, text}` shards of a few hundred KB each, and its zips are
# deleted before the next batch. Only the shards survive, and `ark ingest-usenet-hostnames`
# is idempotent per shard, so an interrupted run loses at most one batch.
#
# Usage: bash scripts/sources/usenet/sweep_alt_hierarchy.sh <deadline_epoch> [batch_gb] [workers]

set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

DEADLINE="${1:?usage: sweep_alt_hierarchy.sh <deadline_epoch> [batch_gb] [workers] [min_mb] [max_mb]}"
BATCH_GB="${2:-8}"
WORKERS="${3:-6}"
# **The band is a parameter because its edges were an assumption.** The 2 MB floor was reasoned,
# not measured: "under 2 MB is usually an archive with no in-window post". The 2 to 150 MB band is
# now read whole (4,843 groups) and realised 134 EE/GB, so the untested edges are worth a
# measurement of their own. Changing either edge writes a new plan.
MIN_MB="${4:-2}"
MAX_MB="${5:-150}"
PLAN_TAG="$(printf '%s_%s' "$MIN_MB" "$MAX_MB")"
UA="ark-research/1.0 (+historical domain census; ivaylo.staykov@taktile.com)"
BASE="https://archive.org/download/usenet-alt"
WORK="data/raw/usenet_alt_work"
ITEMS="data/raw/usenet_alt_items"
PLAN="data/raw/usenet_alt_plan_${PLAN_TAG}.txt"
DONE="data/raw/usenet_alt_done.txt"

mkdir -p "$WORK" "$ITEMS"
touch "$DONE"

# The plan is written once and then only read, so a restart takes the same order.
if [ ! -s "$PLAN" ]; then
    uv run python - "$MIN_MB" "$MAX_MB" > "$PLAN" <<'PY'
import json
import sys

low = int(float(sys.argv[1]) * 1_000_000)
high = int(float(sys.argv[2]) * 1_000_000)
c = json.load(open("data/raw/usenet_catalog.json"))
JUNK = ("alt.binaries", "alt.sex", "alt.anonymous", "alt.warez", "alt.mag.", "alt.0.")
# 2 MB to 150 MB: under 2 MB is usually an archive with no in-window post, over 150 MB is
# a popular group whose URLs the already-read pools hold. Both measured, see the header.
rows = [
    (int(e["size"]), e["name"])
    for e in c["alt"]
    if e.get("name", "").endswith(".mbox.zip")
    and not e["name"].lower().startswith(JUNK)
    and low <= int(e["size"]) < high
]
rows.sort()
for size, name in rows:
    print(f"{size}\t{name}")
PY
fi

# **A run id, because the batch counter alone recycles shard names across runs.** Measured
# 2026-09-08: the lane was stopped and restarted, its counter began at 1 again, and its first
# batch's shards overwrote the first run's `batch1_shard_*`. Nothing banked was lost, because
# `ark ingest-usenet-hostnames` refuses a ledgered name whose sha256 differs rather than skipping
# it, but the next ingest would have failed. The run id makes a shard name unique for good.
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
batch=0
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    batch=$(( batch + 1 ))
    # Take the next names whose sizes sum under the batch budget.
    awk -v done_file="$DONE" -v budget="$(( BATCH_GB * 1000000000 ))" '
        BEGIN { while ((getline line < done_file) > 0) seen[line] = 1 }
        seen[$2] { next }
        { if (run + $1 > budget && n > 0) exit; run += $1; n++; print $2 }
    ' "$PLAN" > "$WORK/batch.txt"
    if [ ! -s "$WORK/batch.txt" ]; then
        echo "plan exhausted after $(wc -l < "$DONE" | tr -d ' ') groups"
        break
    fi
    echo "=== batch $batch: $(wc -l < "$WORK/batch.txt" | tr -d ' ') groups, $(awk -v d="$WORK/batch.txt" 'BEGIN{while((getline l < d)>0) want[l]=1} want[$2]{s+=$1} END{printf "%.1f", s/1e9}' "$PLAN") GB ==="

    # Six connections. Measured 2026-09-08: one connection to `archive.org/download`
    # runs at about 2.5 MB/s, so two ran the first batch at 5.1 MB/s and the whole
    # 193 GB lane would have taken 10.7 hours. Six is the rate that fits the lane in
    # the round and stays modest for one host; the extraction behind it keeps up.
    xargs -P 6 -I{} curl -sSfL --retry 3 --retry-delay 5 -A "$UA" \
        -o "$WORK/{}" "$BASE/{}" < "$WORK/batch.txt"

    uv run python scripts/sources/usenet/build_usenet_pool.py "$WORK" "$ITEMS.batch$batch" "$WORKERS"

    # Shards carry the batch in their name, so nothing collides and the ingest ledger
    # keys each one separately.
    if [ -d "$ITEMS.batch$batch" ]; then
        for shard in "$ITEMS.batch$batch"/shard_*.jsonl.gz; do
            [ -e "$shard" ] || continue
            mv "$shard" "$ITEMS/${RUN_ID}_batch${batch}_$(basename "$shard")"
        done
        rm -rf "$ITEMS.batch$batch"
    fi

    cat "$WORK/batch.txt" >> "$DONE"
    find "$WORK" -name '*.mbox.zip' -delete
    echo "batch $batch done, $(ls "$ITEMS" | wc -l | tr -d ' ') shards held, $(df -g . | awk 'NR==2{print $4}') GB free"
done
echo "deadline reached or plan exhausted"
