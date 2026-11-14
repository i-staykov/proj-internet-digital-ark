"""Path probe for a machine with Python 3.8: standard library only, no repo import.

For each host of a list it asks the Wayback Machine for the capture of /stats/ and /usage/
nearest 2001, `https://web.archive.org/web/2001id_/http://<host>/<path>/`. Never the CDX,
timemap or availability endpoints. The archive's robots.txt is read once and every ask is
matched against it (a 4xx answer means no rules, RFC 9309; any other failure ends the run).
One kept-alive connection a thread. A 429 or 503 rests every thread (60 s, 180 s, 600 s) and
the fourth in a row ends the run; a failed connect rests them and is asked again, ten in a row
end the run. A URL with a receipt is not asked again. A list built from his files runs only on
our own machines, never on a public runner.

    ARK_UA="<harness/fetch.py USER_AGENT>" python3 probe38.py HOSTS DEST [threads] [gap_s] [i/n]

Output, the replay reader's layout: DEST/<host>/<path>/_index.html and one JSON line an ask in
DEST/receipts.receipts (url, replay, memento, status, bytes, sha256, path).
"""

import concurrent.futures as cf
import hashlib
import http.client
import json
import os
import re
import sys
import threading
import time
import urllib.robotparser
import zlib

CFG = {"dest": "", "interval": 0.25, "ua": ""}
PATHS = ("stats", "usage")
ARCHIVE = "web.archive.org"
SAFE = re.compile(r"[^A-Za-z0-9._/~-]")
lock, gate, local = threading.Lock(), threading.Lock(), threading.local()
state = {"next": 0.0, "strikes": 0, "errors": 0, "stop": False, "got": 0, "miss": 0}

robots = urllib.robotparser.RobotFileParser()


def read_robots():
    conn = http.client.HTTPSConnection(ARCHIVE, timeout=60)
    conn.request("GET", "/robots.txt", headers={"User-Agent": CFG["ua"]})
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", "replace")
    conn.close()
    if 400 <= resp.status < 500:  # no robots file: nothing is barred (RFC 9309)
        robots.parse([])
        print(json.dumps({"robots": resp.status, "read_as": "no rules"}), flush=True)
    elif resp.status != 200:
        raise SystemExit(f"robots.txt answered {resp.status}: not probing")
    else:
        robots.parse(body.splitlines())


def wait_turn():
    """One start an interval. A rest another thread sets while this one sleeps binds it too:
    the turn is read again after every sleep and taken, under the lock a rest is set under,
    only once none is left."""
    with gate:
        while True:
            with lock:
                wait = state["next"] - time.time()
                if wait <= 0:
                    state["next"] = time.time() + CFG["interval"]
                    return
            time.sleep(wait)


def get(path):
    conn = getattr(local, "conn", None)
    if conn is None:
        conn = local.conn = http.client.HTTPSConnection(ARCHIVE, timeout=120)
    try:
        conn.request("GET", path, headers={"User-Agent": CFG["ua"], "Accept-Encoding": "identity"})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, dict((k.lower(), v) for k, v in resp.getheaders()), body
    except Exception:
        conn.close()
        local.conn = None
        raise


def ask(url, rec):
    while not state["stop"]:
        wait_turn()
        path = "/web/2001id_/" + url
        if not robots.can_fetch(CFG["ua"], "https://" + ARCHIVE + path):
            state["stop"] = True
            print(json.dumps({"stopped": "robots", "path": path}), flush=True)
            return
        try:
            status, headers, body = get(path)
            hops = 0
            while status in (301, 302, 303, 307) and hops < 4:
                loc = headers.get("location", "")
                if loc.startswith("https://" + ARCHIVE):
                    loc = loc[len("https://" + ARCHIVE) :]
                if not loc.startswith("/"):
                    break
                path = loc
                status, headers, body = get(path)
                hops += 1
        except (http.client.HTTPException, OSError):
            with lock:
                state["errors"] += 1
                state["next"] = max(state["next"], time.time() + min(300, 20 * state["errors"]))
                if state["errors"] >= 10:
                    state["stop"] = True
                    print(json.dumps({"stopped": "connect errors"}), flush=True)
            continue
        if status in (429, 503):
            with lock:
                state["strikes"] += 1
                if state["strikes"] >= 4:
                    state["stop"] = True
                    print(json.dumps({"stopped": "throttled", "status": status}), flush=True)
                    return
                state["next"] = time.time() + (60, 180, 600)[state["strikes"] - 1]
            continue
        hit = status == 200 and bool(re.search(r"/web/\d{14}", path))
        receipt = {
            "url": url,
            "replay": "https://" + ARCHIVE + path if hit else None,
            "memento": headers.get("memento-datetime"),
            "status": status,
            "bytes": 0,
            "sha256": None,
            "path": None,
        }
        if hit:
            host, _, rest = url.split("//", 1)[1].partition("/")
            name = host.lower() + "/" + SAFE.sub("_", rest.strip("/") + "/_index.html")
            out = os.path.join(CFG["dest"], name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(body)
            receipt.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), path=name)
        with lock:
            state["strikes"] = state["errors"] = 0
            state["got" if hit else "miss"] += 1
            rec.write(json.dumps(receipt) + "\n")
            rec.flush()
            if (state["got"] + state["miss"]) % 500 == 0:
                print(json.dumps({"got": state["got"], "miss": state["miss"]}), flush=True)
        return


def asks(hosts, shard, known):
    """The asks of one shard (i, n) of the hosts, less the URLs that hold a receipt."""
    mine = [h for h in hosts if zlib.crc32(h.encode()) % shard[1] == shard[0]]
    return [u for u in (f"http://{h}/{p}/" for h in mine for p in PATHS) if u not in known]


def main(argv):
    hosts_file, dest = argv[1], argv[2]
    threads = int(argv[3]) if len(argv) > 3 else 4
    shard = tuple(int(x) for x in argv[5].split("/")) if len(argv) > 5 else (0, 1)
    CFG.update(dest=dest, ua=os.environ["ARK_UA"])
    CFG["interval"] = float(argv[4]) if len(argv) > 4 else 0.25
    os.makedirs(dest, exist_ok=True)
    rec_path = os.path.join(dest, "receipts.receipts")
    known = set()
    if os.path.exists(rec_path):
        for line in open(rec_path):
            try:
                known.add(json.loads(line)["url"])
            except (ValueError, KeyError):
                pass
    urls = asks([h.strip() for h in open(hosts_file) if h.strip()], shard, known)
    print(json.dumps({"asks": len(urls), "already": len(known)}), flush=True)
    read_robots()
    with open(rec_path, "a") as rec, cf.ThreadPoolExecutor(threads) as ex:
        list(ex.map(lambda u: ask(u, rec), urls))
    done = not state["stop"]
    print(json.dumps({"done": done, "got": state["got"], "miss": state["miss"]}), flush=True)
    return 0 if done else 4


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
