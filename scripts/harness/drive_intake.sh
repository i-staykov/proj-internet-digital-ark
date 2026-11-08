#!/usr/bin/env bash
# His release from Drive, last in `just sync` on the bank host, under its lock and after a green
# bank: the oldest archive in gdrive:ark-offsite/releases/ whose `<name>.sha256` names a digest
# docs/registers/releases.md does not carry is copied into its own `ding/<digest>/`, checked
# against that digest, taken by `just intake`, and its pages committed and pushed to `live`. The
# next bank re-exports against it.
#
# Each upload is tried once: data/logs/drive_intake.tsv keys it on its digest and Drive's stamp,
# and deleting its line re-arms it. A mismatch, a failed intake or copy, an archive an hour without
# a digest or a VM short of memory for his calculator is one line of data/logs/.intake_alert,
# raised once as a vm-alert by heartbeat.py. A failed intake's pages go back to HEAD and its
# `ding/<digest>/` goes; `data/logs/intake_<digest>.log` says why.
#
#   bash scripts/harness/drive_intake.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
REMOTE=${ARK_RELEASES:-gdrive:ark-offsite/releases}
SEEN=data/logs/drive_intake.tsv ALERT=data/logs/.intake_alert
PAGES=(data/baseline.json docs/registers/releases.md docs/registers/rounds.md docs/brief/ding/project-brief.md)
RETRY="Deleting its line in $SEEN on the VM retries it."
mkdir -p data/logs ding && touch "$SEEN"

seen() { awk -F'\t' -v k="$1" '$1 == k {f = 1} END {exit !f}' "$SEEN"; }
mark() { printf '%s\t%s\n' "$1" "$2" >> "$SEEN"; }
alert() { printf 'intake: %s\t%s\n' "$1" "$2" >> "$ALERT"; echo "intake: $1: $2"; }
once() { seen "$1" || { mark "$1" "$2"; alert "$2" "$3"; }; }
current() { python3 -c 'import json, sys; print(json.load(open("data/baseline.json"))["current"][sys.argv[1]])' "$1"; }
digest() { shasum -a 256 "$1" | cut -d' ' -f1; }
# A Drive that does not answer costs the locked tick seconds; macOS, where no tick runs, has no timeout.
bound() { if command -v timeout > /dev/null; then timeout "$@"; else shift && "$@"; fi; }

# His calculator holds a year file's lines as a set, up to 6.43 bytes a byte (docs/lore/laws.md,
# Harness): the current release's largest year file, and the agent's 3 GB MemoryMax beside it,
# must fit in what is available, swap included.
fits() {
    python3 - "$(current directory)" << 'PY'
import pathlib, re, sys
info = pathlib.Path("/proc/meminfo")
if not info.exists():
    sys.exit(0)
kb = dict(re.findall(r"^(\w+):\s+(\d+) kB", info.read_text(), re.M))
have = (int(kb["MemAvailable"]) + int(kb["SwapFree"])) * 1024
years = pathlib.Path(sys.argv[1]).glob("[12]*.txt")
need = 6.5 * max((f.stat().st_size for f in years), default=0) + 3e9
print(f"{need / 1e9:.1f} GB needed, {have / 1e9:.1f} GB available with swap")
sys.exit(have < need)
PY
}

# His task brief, transcribed when the package holds one docs/brief/ding/ does not carry.
brief() {  # label package
    local f
    for f in "$2"/Internet_Digital_Ark_Project_*.docx; do
        [ -f "$f" ] && ! grep -qF "$(digest "$f")" docs/brief/ding/project-brief.md || continue
        uv run python scripts/round/extract_ding_docs.py --package "$2" --archive "$1 ($(date -u +%F))" \
            --stamp "$(date -u +%F)" || alert "$1: brief not transcribed" "$f; the rest was taken."
        return
    done
}

# A merge since the preflight is replayed under the lock, as the next preflight would.
push() {
    git push -q origin live && return
    git pull -q --rebase origin live && git push -q origin live && return
    git rebase --abort 2> /dev/null
    echo "intake: committed, not pushed; the next tick's preflight rebases it and its bank pushes it"
}

take() {  # name digest stamp size
    local name=$1 want=$2 key="$2 $3" label="$1 ${2:0:12}" dir="ding/${2:0:12}" prev now
    local log="data/logs/intake_${2:0:12}.log"
    rm -rf "$dir" && mkdir -p "$dir"
    # ten minutes, and a second for each 2 MB
    if ! bound $((600 + $4 / 2000000)) rclone copyto "$REMOTE/$name" "$dir/$name"; then
        rm -rf "$dir" && once "copy $key" "$label: copy failed" "rclone could not copy it; every tick retries."
        return
    fi
    if [ "$(digest "$dir/$name")" != "$want" ]; then
        rm -rf "$dir" && mark "$key" mismatch
        alert "$label: digest mismatch" "its bytes are not the sha256 its .sha256 names. $RETRY"
        return
    fi
    prev=$(current marker)
    just intake "$dir/$name" --sha256 "$want" --into "$dir" > "$log" 2>&1
    now=$(current marker)
    if [ "$now" = "$prev" ] || [ ! -f "data/held/$now/held.json" ]; then
        git checkout -q HEAD -- "${PAGES[@]}" && rm -rf "$dir" && mark "$key" failed
        alert "$label: failed" "\`just intake\` did not take it ($log); its pages are back at HEAD. $RETRY"
        return
    fi
    ! grep -q "no usable stamp" "$log" || alert "$label: no release time" "released_at is its date at 00:00."
    brief "$label" "$(dirname "$(current directory)")"
    mark "$key" "taken $now" && git add -u -- "${PAGES[@]}"
    git commit -q -m "Intake $now: his release $name from Drive" && push ||
        alert "$label: commit refused" "$now is taken, its pages uncommitted (the hook's tests read his model): every tick refuses until they are committed."
}

# A listing or a digest that times out is quiet: the offsite listing's 24 h alert covers it.
listing=$(bound 120 rclone lsf --files-only --format pst --separator '|' "$REMOTE" 2> /dev/null |
    sort -t'|' -k3,3 -k1,1) || exit 0
while IFS='|' read -r name size stamp; do
    case "$name" in *.zip | *.7z) ;; *) continue ;; esac
    want=""
    if awk -F'|' -v n="$name.sha256" '$1 == n {f = 1} END {exit !f}' <<< "$listing"; then
        want=$(bound 120 rclone cat "$REMOTE/$name.sha256" 2> /dev/null < /dev/null) || continue
        want=$(awk 'NR == 1 {print tolower($1)}' <<< "$want")
    fi
    if [[ ! "$want" =~ ^[0-9a-f]{64}$ ]]; then  # alerted on the second tick, so a digest a minute late is no alert
        seen "$name $stamp" && once "alert $name $stamp" "$name: no digest" \
            "it has no $name.sha256 opening with its sha256, so it is left there." || mark "$name $stamp" "no digest"
        continue
    fi
    grep -qiF "$want" docs/registers/releases.md && continue
    seen "$want $stamp" && continue
    if why=$(fits); then
        take "$name" "$want" "$stamp" "$size" < /dev/null
    else
        once "memory $want $stamp" "$name: short of memory" "it waits: $why; the swap step \`just vm install\` prints."
    fi
    break
done <<< "$listing"
