"""Ask the Archive's replay whether it holds a capture of each host's root near a stamp.

    python3 wayback_roots.py HOSTS OUT [--threads 8] [--interval 0.125] [--minutes 0]
        [--stamp 19990101000000]

One ask a host, `/web/<stamp>id_/http://<host>/`, redirects not followed: a 302 names the
nearest capture's stamp in its Location, a 200 answers at the stamp itself, a 404 means no
capture of that URL. No body is read past the headers. One line a host in OUT, `host status
stamp location-host` (`-` where there is none); a stamp in 1996 to 2001 is a lead that the
stager confirms as a capture of the exact host, since the replay folds www and bare names.
The CDX is never asked.

Politeness, as the link crawl's: one kept-alive connection a thread, one start gate over all
threads, `--interval` seconds between starts; a 429, a 503 or a failed connection rests every
thread (60 s, doubling to 960 s) and ten in a row with no answer between end the run; a kept
connection the far end closed while it idled is neither. A host
answered 503 twice with a normal answer between is written as 503 and not asked again.

Exit 0 all asked, 2 out of minutes, 3 ended by refusals, 4 stopped by a TERM or INT: the asks
in flight are written and no new one starts. Resumes from OUT, a torn last line cut off and
its host asked again. Standard library only, one file, so it runs on any machine.
"""

import argparse
import http.client
import os
import re
import signal
import threading
import time

AGENT = "ArkLinkCrawler/1.0 (research crawler of archived pages for historical hostname research)"
LOC = re.compile(r"/web/(\d{14})[a-z_]*/(?:https?://)?([^/:]+)")


def answer(host: str, stamp: str, status: int, location: str, memento: str) -> str:
    """The OUT line of one answered ask."""
    m = LOC.search(location)
    if m:
        ts, lh = m.group(1), m.group(2).lower()
    else:
        ts, lh = (stamp, host) if memento else ("-", "-")
    return f"{host} {status} {ts} {lh}\n"


def asked(path: str) -> set[str]:
    """The hosts OUT already answers; a last line torn by a kill is cut off the file."""
    try:
        with open(path, "rb") as fh:
            old = fh.read()
    except FileNotFoundError:
        return set()
    if old and not old.endswith(b"\n"):
        old = old[: old.rfind(b"\n") + 1]
        os.truncate(path, len(old))
    return {ln.split(" ", 1)[0] for ln in old.decode(errors="replace").split("\n") if ln}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("hosts")
    p.add_argument("out")
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--interval", type=float, default=0.125)
    p.add_argument("--minutes", type=float, default=0)
    p.add_argument("--stamp", default="19990101000000")
    a = p.parse_args()

    done = asked(a.out)
    with open(a.hosts) as fh:
        todo = [h for h in (ln.strip() for ln in fh) if h and h not in done]
    lock, gate, halt = threading.Lock(), threading.Lock(), threading.Event()
    state = {"i": 0, "next": 0.0, "bad": 0, "ok": 0, "stop": False}
    end = time.time() + a.minutes * 60 if a.minutes else None
    signal.signal(signal.SIGTERM, lambda *_: halt.set())
    signal.signal(signal.SIGINT, lambda *_: halt.set())
    out = open(a.out, "a")  # noqa: SIM115

    def take() -> str | None:
        with lock:
            over = end and time.time() > end
            if halt.is_set() or state["stop"] or state["i"] >= len(todo) or over:
                return None
            state["i"] += 1
            return todo[state["i"] - 1]

    def wait() -> None:
        with gate:
            now = time.time()
            t = max(now, state["next"])
            state["next"] = t + a.interval
        if t > now:
            halt.wait(t - now)

    def trouble(status: int) -> None:
        with lock:
            print(time.strftime("%H:%M:%S"), "rest after", status, "asked", state["i"], flush=True)
            state["bad"] += 1
            state["next"] = time.time() + min(960, 60 * 2 ** min(state["bad"] - 1, 4))
            if state["bad"] >= 10:
                state["stop"] = True

    def work() -> None:
        conn, used = None, 0.0
        while (host := take()) is not None:
            first = None  # normal answers counted when this host first answered 503
            line = f"{host} 0 - -\n"
            for _ in range(4):
                wait()
                if halt.is_set():  # not answered and not written: the next run asks it
                    return
                # The far end closes a kept connection that idles through a rest, and an ask on
                # it fails at once: that is no refusal. Counted as one it rests every thread
                # again while the connections that just answered idle in turn, and the run
                # never comes back. An idle connection is dropped before the ask, and a kept
                # one that fails is asked again on a new one.
                if conn is not None and time.time() - used > 20:
                    conn.close()
                    conn = None
                kept = conn is not None
                try:
                    if conn is None:
                        conn = http.client.HTTPConnection("web.archive.org", 80, timeout=45)
                    path = f"/web/{a.stamp}id_/http://{host}/"
                    conn.request("GET", path, headers={"User-Agent": AGENT})
                    r = conn.getresponse()
                    used = time.time()
                    loc, mem = r.getheader("Location") or "", r.getheader("Memento-Datetime") or ""
                    st = r.status
                    if st in (301, 302, 404, 403, 400):
                        r.read()
                    else:
                        r.close()
                        conn.close()
                        conn = None
                except (OSError, http.client.HTTPException) as e:
                    conn, st = None, 0
                    gone = (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError)
                    if kept and isinstance(e, gone):
                        continue
                own = st == 503 and first is not None and state["ok"] > first
                if st in (0, 429, 503) and not own:
                    if st == 503 and first is None:
                        first = state["ok"]
                    trouble(st)
                    if state["stop"]:
                        return
                    continue
                if not own:
                    with lock:
                        state["bad"] = 0
                        state["ok"] += 1
                line = answer(host, a.stamp, st, loc, mem)
                break
            with lock:
                out.write(line)
                out.flush()

    threads = [threading.Thread(target=work) for _ in range(a.threads)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out.close()
    print(
        f"asked {state['i']} of {len(todo)} in {time.time() - t0:.0f} s,"
        f" rests in a row {state['bad']}, ended by refusals {state['stop']}, halted {halt.is_set()}"
    )
    if state["stop"]:
        return 3
    if halt.is_set():
        return 4
    return 0 if state["i"] >= len(todo) else 2


if __name__ == "__main__":
    raise SystemExit(main())
