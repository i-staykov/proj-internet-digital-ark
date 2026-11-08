"""The tick's own row, the VM's alerts and the daily heartbeat, run last by every tick.

    python3 scripts/harness/heartbeat.py STAMP START SYNC_RC CHECK_RC SYNC_OUT CHECK_OUT

- `data/logs/ticks.tsv` gains one row: stamp, verdict, seconds, banked or why not, free GiB
  (the disk's 7-day rate needs its own history). Rows past 90 days go. The verdict is `red` while
  `bank_red.json` stands, `held` when the recipe printed it, `refused` when the lock refused or the
  sync failed, `banked` when the bank wrote its stamp since START, else `idle`.
- Each cause on opens one `vm-alert` issue on ark-fleet titled `vm-alert: <cause>`, reopens a
  closed one, and leaves an open one alone: a failed check (one per FAIL, a reader stopped
  mid-item among them), BANK RED, two refused ticks in a row, a lane with work queued (pending
  subpages, or a last row other than its `pending=0` exit) and no answered page in 6 h, no
  successful agent run, no Claude pre-flight answered or no listing of the offsite remote in
  24 h, a reboot pending 24 h (the tick reboots, scheduled_sync.sh), under 14 days of disk or
  gh token. The triage reads them; the owner is asked nothing.
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

from ark.db import space  # noqa: E402
from ark.hygiene import local_hosts, scan  # noqa: E402

FLEET = "i-staykov/ark-fleet"
LOGS = ROOT / "data/logs"
TICKS = LOGS / "ticks.tsv"
KEEP_DAYS = 90
LANES = 3
STALL_H = 6
FLOOR_DAYS = 14
HEARTBEAT_TITLE = "VM heartbeat"
HEARTBEAT_HOUR = 6
STATE = Path(os.environ.get("ARK_STATE_DIR", Path.home() / "ark/state"))
REBOOT = Path(os.environ.get("ARK_REBOOT_FLAG", "/var/run/reboot-required"))
UPTIME = Path("/proc/uptime")
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
            if len(r) >= 5 and utc(r[0]) and float(r[4]) >= 0:
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


def disk(kept: list[list[str]], now: dt.datetime) -> tuple[float | None, str]:
    """Days to the floor at the 7-day rate, and its line."""
    rc, lines = space(root=ROOT)
    m = re.search(r"([\d.]+) GiB free, need ([\d.]+) GiB", lines[0])
    if not m:
        return None, f"disk: {lines[0]}"
    free, need = float(m[1]), float(m[2])
    week = [r for r in kept if utc(r[0]) >= now - dt.timedelta(days=7)]
    days = (utc(week[-1][0]) - utc(week[0][0])).total_seconds() / 86400
    rate = (float(week[0][4]) - float(week[-1][4])) / days if days >= 1 else 0.0
    if rate <= 0:
        return None, f"disk: {free:.1f} GiB free, need {need:.1f}, not shrinking over 7 days"
    left = (free - need) / rate
    return (
        left,
        f"disk: {free:.1f} GiB free, need {need:.1f}, {rate:.1f} GiB a day, {left:.0f} days left",
    )


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


def reboot(now: dt.datetime) -> tuple[bool, str]:
    """(pending 24 h, line): unattended-upgrades' flag, first seen by a tick, and the last boot."""
    seen = LOGS / ".reboot_seen"
    try:
        booted = now - dt.timedelta(seconds=float(UPTIME.read_text().split()[0]))
        boot = f"up since {booted:%F %H:%M} UTC"
    except (OSError, ValueError, IndexError):
        booted, boot = None, "boot time unknown"
    if not REBOOT.exists():
        seen.unlink(missing_ok=True)
        return False, f"reboot: none pending, {boot}"
    if not seen.exists() or booted and seen.stat().st_mtime < booted.timestamp():
        seen.touch()  # first seen, or seen before the reboot that cleared it
    since = dt.datetime.fromtimestamp(seen.stat().st_mtime, dt.UTC)
    return now - since >= dt.timedelta(hours=24), f"reboot: pending since {since:%F %H:%M}, {boot}"


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
    free = shutil.disk_usage(ROOT / "data").free / GIB
    secs = f"{now.timestamp() - float(start):.0f}"
    kept = append([stamp, word, secs, why.replace("\t", " ")[:200], f"{free:.1f}"], now)
    print(f"tick row: {word}, {why}")

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
    disk_days, disk_line = disk(kept, now)
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
    stuck, reboot_line = reboot(now)
    if stuck:
        causes["reboot pending 24 h"] = f"{reboot_line}; data/logs/scheduled_sync.log says why"
    alert(causes)

    today = now.strftime("%Y-%m-%d")
    day_file = LOGS / ".heartbeat_day"
    posted = day_file.read_text().strip() if day_file.exists() else ""
    # from 06 on, so a 05:05 tick running past 06:05 delays the day's post, never drops it
    if utc(stamp).hour >= HEARTBEAT_HOUR and posted != today:
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
                "header lane: no unit yet, not measured",
                *readers(),
                token_line,
                pre_line,
                off_line,
                reboot_line,
                f"hold: {held}",
                agent_line,
            ]
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
