"""The tick's own row, the VM's alerts and the daily heartbeat, run last by every tick.

    python3 scripts/harness/heartbeat.py STAMP START SYNC_RC CHECK_RC SYNC_OUT CHECK_OUT

- `data/logs/ticks.tsv` gains one row: stamp, verdict, seconds, banked or why not. Rows past 90
  days go. The verdict is `red` while `bank_red.json` stands, `held` when the recipe printed it,
  `refused` when the lock refused or the sync failed, `banked` when the bank wrote its stamp
  since START, else `idle`.
- `data/logs/disk.tsv` gains the day's free GiB at the heartbeat tick: date, free GiB. The disk
  line's days to the floor is the 7-day rate over those readings.
- Each cause on opens one `vm-alert` issue on ark-fleet titled `vm-alert: <cause>`, reopens a
  closed one, and leaves an open one alone: a failed check (one per FAIL, a reader stopped
  mid-item among them), BANK RED, two refused ticks in a row, a lane with work queued (pending
  subpages, or a last row other than its `pending=0` exit) and no answered page in 6 h, no
  successful agent run, no Claude pre-flight answered or no listing of the offsite remote in
  24 h, under 14 days of disk or gh token. The triage reads them; the owner is asked nothing.
- The first tick from 06 UTC, once a day, comments the heartbeat on the open `VM heartbeat`
  issue, so its last comment says where the VM stands. A watchdog on ark-fleet alerts when that
  goes quiet.

Every body is written to a file and passes `ark.hygiene` first, else a fixed line replaces it.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ark.disk import space  # noqa: E402
from ark.hygiene import local_hosts, scan  # noqa: E402

FLEET = "i-staykov/ark-fleet"
LOGS = ROOT / "data/logs"
TICKS = LOGS / "ticks.tsv"
DISK = LOGS / "disk.tsv"
KEEP_DAYS = 90
LANES = 3
STALL_H = 6
FLOOR_DAYS = 14
HEARTBEAT_TITLE = "VM heartbeat"
HEARTBEAT_HOUR = 6
STATE = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state"))
GIB = 1024**3
# run_agent.sh's rows before the pre-flight and its refusal; a rate limit, the pre-flight's
# or the run's, answered the token
NO_PREFLIGHT = {
    "held", "busy", "no-token", "billing-guard", "no-claude", "no-prompt", "no-item",
    "bad-policy", "pacer-failed", "preflight-failed",
}  # fmt: skip


def utc(stamp: str) -> dt.datetime:
    """A `20261106T2005Z` or `20261106T200501Z` stamp as UTC."""
    fmt = "%Y%m%dT%H%M%SZ" if len(stamp) == 16 else "%Y%m%dT%H%MZ"
    return dt.datetime.strptime(stamp, fmt).replace(tzinfo=dt.UTC)


def gh(*args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True, cwd=ROOT, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return p.returncode, p.stdout.strip()


def verdict(sync_rc: int, sync_out: str, start: float) -> tuple[str, str]:
    # `just`'s own "error: recipe `sync` failed" line names no cause, so the line before it does
    lines = [
        ln.strip()
        for ln in sync_out.splitlines()
        if ln.strip() and not ln.lower().startswith("error: recipe")
    ]
    bank = next((ln for ln in reversed(lines) if ln.startswith("bank: ")), "")
    if (LOGS / "bank_red.json").exists():
        return "red", bank or "BANK RED stands"
    if "held" in lines:
        return "held", "the hold holds ark-sync.timer"
    if any("This one stops" in ln for ln in lines):
        return "refused", "a sync already held the lock"
    if sync_rc:
        return "refused", f"sync exit {sync_rc}: " + (lines[-1] if lines else "no output")
    stamp = LOGS / "bank_stamp.json"
    if stamp.exists() and stamp.stat().st_mtime >= start:
        return "banked", "banked"
    return "idle", bank or (lines[-1] if lines else "no output")


def rows() -> list[list[str]]:
    if not TICKS.exists():
        return []
    out = []
    for r in (ln.split("\t") for ln in TICKS.read_text().splitlines()):
        try:
            if len(r) >= 4 and utc(r[0]):
                out.append(r)
        except ValueError:
            continue  # a torn or hand-edited row
    return out


def append(row: list[str], now: dt.datetime) -> list[list[str]]:
    """Add the row, keep KEEP_DAYS, return what is kept."""
    cut = now - dt.timedelta(days=KEEP_DAYS)
    kept = [r for r in rows() if utc(r[0]) >= cut] + [row]
    TICKS.parent.mkdir(parents=True, exist_ok=True)
    tmp = TICKS.with_suffix(".tmp")
    tmp.write_text("".join("\t".join(r) + "\n" for r in kept))
    tmp.replace(TICKS)
    return kept


def readings() -> list[tuple[dt.date, float]]:
    """(date, free GiB) per row of disk.tsv, torn rows dropped, oldest first."""
    out = []
    for ln in DISK.read_text().splitlines() if DISK.exists() else []:
        try:
            day, free = ln.split("\t")
            out.append((dt.date.fromisoformat(day), float(free)))
        except ValueError:
            continue
    return sorted(out)


def record(today: dt.date, free: float) -> None:
    """The day's reading, its first; readings past KEEP_DAYS go."""
    had = readings()
    if any(d == today for d, _ in had):
        return
    kept = [(d, f) for d, f in had if d >= today - dt.timedelta(days=KEEP_DAYS)] + [(today, free)]
    DISK.parent.mkdir(parents=True, exist_ok=True)
    DISK.write_text("".join(f"{d}\t{f:.1f}\n" for d, f in kept))


def disk(today: dt.date) -> tuple[float | None, str]:
    """Days to the floor at the rate of the last 7 days' readings, and its line."""
    rc, lines = space(root=ROOT)
    m = re.search(r"([\d.]+) GiB free, need ([\d.]+) GiB", lines[0])
    if not m:
        return None, f"disk: {lines[0]}"
    free, need = float(m[1]), float(m[2])
    week = [(d, f) for d, f in readings() if d >= today - dt.timedelta(days=7)]
    head = f"disk: {free:.1f} GiB free, need {need:.1f}, "
    if len(week) < 2:
        return None, head + f"{len(week)} reading, no 7-day rate yet"
    rate = (week[0][1] - week[-1][1]) / (week[-1][0] - week[0][0]).days
    if rate <= 0:
        return None, head + "not shrinking"
    left = (free - need) / rate
    return left, head + f"{left:.0f} days to floor"


def token(now: dt.datetime) -> tuple[float | None, str]:
    rc, out = gh("api", "-i", "user")
    m = re.search(r"^github-authentication-token-expiration: (.+?)\s*$", out, re.M | re.I)
    if rc or not m:
        return None, "gh token: " + ("no expiry" if not rc else "unreadable")
    try:
        at = dt.datetime.strptime(m[1].replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None, f"gh token: expiry {m[1]} unreadable"
    left = (at.replace(tzinfo=dt.UTC) - now).total_seconds() / 86400
    return left, f"gh token: {left:.0f} days to expiry"


def lane(n: int, now: dt.datetime, yields: dict[str, str]) -> tuple[bool | None, str]:
    """(stalled, line): stalled is None where the lane does not walk here or is paused; the
    line is the lane's last productivity row (scripts/agents/lane_yield.py)."""
    folder = ROOT / f"data/raw/cdx_walk/lane{n}"
    log = folder / "log.tsv"
    if not log.exists():
        return None, f"lane{n}: not walked here"
    stall = now - dt.timedelta(hours=STALL_H)
    recent, last = 0, ""
    for ln in log.read_text(errors="replace").splitlines():
        last = ln or last
        r = ln.split("\t")
        if len(r) < 14 or r[7] != "200":
            continue
        try:
            at = utc(r[0])
        except ValueError:
            continue
        recent += at >= stall
    pending = folder / "pending.txt"
    # A finished lane's last row is its `# exit ... pending=0`, written again at each cron restart;
    # a killed one that never restarts is the check's stale-log FAIL.
    finished = last.startswith("# exit ") and last.rstrip().endswith("pending=0")
    queued = (pending.exists() and pending.read_text().strip() != "") or not finished
    paused = (STATE / "pause-platform").exists()
    stalled = None if paused else queued and recent == 0
    line = f"lane{n}: " + yields.get(f"lane{n}", "no productivity row")
    return stalled, line + (", paused" if paused else "")


def ledger() -> list[list[str]]:
    """The agent's runs (scripts/agents/agent_ledger.py), the header and torn rows left out."""
    path = LOGS / "agent_runs.tsv"
    runs = []
    for ln in path.read_text().splitlines() if path.exists() else []:
        r = ln.split("\t")
        try:
            if len(r) >= 11 and utc(r[0]) and float(r[7]) + float(r[8]) >= 0:
                runs.append(r)
        except ValueError:
            continue
    return runs


def agent(now: dt.datetime) -> tuple[bool, str]:
    """(a success in 24 h, line): runs, the windows spent, the review's decision."""
    runs = [r for r in ledger() if utc(r[0]) >= now - dt.timedelta(hours=24)]
    ok = sum(r[10].startswith("success") for r in runs)
    windows = f", windows {runs[-1][7]}% of 5 h and {runs[-1][8]}% of 7 d" if runs else ""
    return ok > 0, f"agent: {len(runs)} runs, {ok} succeeded{windows}; review: none yet (#526)"


def preflight(now: dt.datetime) -> tuple[bool, str]:
    """(answered in 24 h, line): the Claude token's last pre-flight that answered, from the ledger.

    Every row outside NO_PREFLIGHT comes after it answered, a `paced` one only when it carries
    the windows the pre-flight read (a back-off is paced before it, with none)."""
    runs = ledger()
    for r in reversed(runs):
        kind = r[10].split(":")[0]
        if kind in NO_PREFLIGHT or (kind == "paced" and float(r[7]) + float(r[8]) == 0):
            continue
        return utc(r[0]) >= now - dt.timedelta(hours=24), f"claude token: pre-flight ok at {r[0]}"
    return False, "claude token: no pre-flight ok" + (f", last row {runs[-1][10]}" if runs else "")


def offsite(now: dt.datetime) -> tuple[bool, str]:
    """(listed in 24 h, line): the tick's last successful listing of the offsite remote."""
    try:
        at = (LOGS / ".offsite_listed").read_text().strip()
        listed = utc(at)
    except (OSError, ValueError):
        return False, "offsite: never listed"
    return listed >= now - dt.timedelta(hours=24), f"offsite: listed at {at}"


def load(rel: str):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def yields() -> dict[str, str]:
    try:
        return load("scripts/agents/lane_yield.py").lines(LOGS / "productivity.tsv")
    except Exception:  # noqa: BLE001 - a script's import must not cost the heartbeat
        return {}


def readers() -> list[str]:
    try:
        mod = load("scripts/harness/check_unattended.py")
        return [f"{name}: {why}" for name, _ok, why in mod.readers()]
    except Exception as e:  # noqa: BLE001 - a reader's import must not cost the heartbeat
        return [f"readers: unreadable, {type(e).__name__}"]


def header() -> str:
    try:
        return load("scripts/sources/usenet/run_usenet_header_items.py").summary()
    except Exception as e:  # noqa: BLE001 - the lane's import must not cost the heartbeat
        return f"header lane: unreadable, {type(e).__name__}"


def clean(body: str, name: str) -> str:
    """The body if it passes the public scan, else a fixed line."""
    path = LOGS / f".{name}_body"
    path.write_text(body)
    if scan([path], local_hosts(ROOT / "local.env")):
        return "(the body failed the public scan; data/logs/scheduled_sync.log on the VM holds it)"
    return body


def alert(causes: dict[str, str]) -> None:
    """One `vm-alert` issue per cause: opened, reopened, never duplicated."""
    if not causes:
        return
    listed = ["issue", "list", "-R", FLEET, "--label", "vm-alert", "--state", "all"]
    rc, out = gh(*listed, "--limit", "500", "--json", "number,title,state")
    if rc:
        print(f"alerts: gh could not list, {len(causes)} wait for the next tick")
        return
    known = {i["title"]: i for i in json.loads(out or "[]")}
    for cause, body in causes.items():
        title, body = f"vm-alert: {cause}", clean(body, "vm_alert")
        have = known.get(title)
        if have is None:
            labelled = ("-R", FLEET, "--label", "vm-alert")
            rc, _ = gh("issue", "create", *labelled, "--title", title, "--body", body)
            print(f"alert {'opened' if rc == 0 else 'not opened, gh refused'}: {cause}")
        elif have["state"] != "OPEN":
            rc, _ = gh("issue", "reopen", str(have["number"]), "-R", FLEET, "--comment", body)
            print(f"alert {'reopened' if rc == 0 else 'not reopened, gh refused'}: {cause}")


def heartbeat(lines: list[str]) -> None:
    rc, out = gh(
        "issue", "list", "-R", FLEET, "--state", "open",
        "--search", f'in:title "{HEARTBEAT_TITLE}"', "--json", "number,title",
    )  # fmt: skip
    if rc:
        print("heartbeat: gh could not list, posted next day")
        return
    found = [i["number"] for i in json.loads(out or "[]") if i["title"] == HEARTBEAT_TITLE]
    body = clean("\n".join(lines), "heartbeat")
    if found:
        rc, _ = gh("issue", "comment", str(found[0]), "-R", FLEET, "--body", body)
    else:
        rc, _ = gh("issue", "create", "-R", FLEET, "--title", HEARTBEAT_TITLE, "--body", body)
    print("heartbeat: posted" if rc == 0 else "heartbeat: gh refused the post")
    if rc == 0:
        (LOGS / ".heartbeat_day").write_text(lines[0].split()[-1])


def main(argv: list[str]) -> int:
    stamp, start, sync_rc, check_rc, sync_out, check_out = argv
    now = dt.datetime.now(dt.UTC)
    sync_text = Path(sync_out).read_text(errors="replace") if Path(sync_out).exists() else ""
    check_text = Path(check_out).read_text(errors="replace") if Path(check_out).exists() else ""
    word, why = verdict(int(sync_rc), sync_text, float(start))
    secs = f"{now.timestamp() - float(start):.0f}"
    kept = append([stamp, word, secs, why.replace("\t", " ")[:200]], now)
    print(f"tick row: {word}, {why}")
    today = now.strftime("%Y-%m-%d")
    day_file = LOGS / ".heartbeat_day"
    posted = day_file.read_text().strip() if day_file.exists() else ""
    # from 06 on, so a 05:05 tick running past 06:05 delays the day's post, never drops it
    daily = utc(stamp).hour >= HEARTBEAT_HOUR and posted != today
    if daily:
        record(utc(stamp).date(), shutil.disk_usage(ROOT / "data").free / GIB)

    causes: dict[str, str] = {}
    for ln in check_text.splitlines():
        if ln.startswith("FAIL "):
            causes[f"check {ln[5:].split(':')[0]}"] = f"`just check unattended` at {stamp}: {ln}"
    if word == "red":
        causes["BANK RED"] = f"The tick at {stamp} found the bank red: {why}"
    if len(kept) >= 2 and kept[-1][1] == kept[-2][1] == "refused":
        causes["two refused ticks"] = f"Ticks {kept[-2][0]} and {stamp} refused: {why}"
    rows_of = yields()
    lanes = [lane(n, now, rows_of) for n in range(LANES)]
    for n, (stalled, line) in enumerate(lanes):
        if stalled:
            causes[f"lane{n} stalled"] = f"{line}; work queued and no answered page in {STALL_H} h"
    agent_ok, agent_line = agent(now)
    if not agent_ok:
        causes["no agent success in 24 h"] = agent_line
    disk_days, disk_line = disk(now.date())
    if disk_days is not None and disk_days < FLOOR_DAYS:
        causes["disk under 14 days"] = disk_line
    token_days, token_line = token(now)
    if token_days is not None and token_days < FLOOR_DAYS:
        causes["gh token under 14 days"] = token_line
    pre_ok, pre_line = preflight(now)
    if not pre_ok:
        causes["no Claude pre-flight ok in 24 h"] = pre_line
    off_ok, off_line = offsite(now)
    if not off_ok:
        causes["no offsite listing in 24 h"] = off_line
    alert(causes)

    if daily:
        round_md = ROOT / "docs/ROUND.md"
        text = round_md.read_text() if round_md.exists() else ""
        gate = [ln for ln in text.splitlines() if ln.startswith("GATE.")] or ["GATE: no ROUND.md"]
        last = [r for r in kept if utc(r[0]) >= now - dt.timedelta(hours=24)]
        counts = {w: sum(r[1] == w for r in last) for w in ("banked", "refused", "held", "red")}
        check_last = check_text.strip().splitlines()[-1] if check_text.strip() else "no output"
        hold = STATE / "hold"
        held = (
            (" ".join(hold.read_text().splitlines()[2:]) or "nothing named")
            if hold.exists()
            else "none"
        )
        heartbeat(
            [
                f"heartbeat {today}",
                *gate,
                check_last,
                disk_line,
                "ticks in 24 h: " + ", ".join(f"{n} {w}" for w, n in counts.items()),
                *(line for _s, line in lanes),
                header(),
                *readers(),
                token_line,
                pre_line,
                off_line,
                f"hold: {held}",
                agent_line,
            ]
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
