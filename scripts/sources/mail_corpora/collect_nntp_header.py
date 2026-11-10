"""Relay and rDNS hosts from `Received:` (Gmane: `Original-Received:`) of 1996-2001
list articles on a public NNTP server, one connection, HEAD commands pipelined in batches.

    NNTP_SERVER=news.php.net NNTP_TAG=php \
      uv run python scripts/sources/mail_corpora/collect_nntp_header.py GROUPS OUT [GROUP ...]

GROUPS is a JSONL of rows {g, n, lo, hi, y} (`scan_nntp_groups.py`): each group's range and
its first article's year. Writes rows `{host, year, file, pos, field}` for
`ark ingest-staged-messages`: file `nntp://<server>/<group>`, pos the article.
A message is dated by its own Date: header; the Apache lane's `by_hosts` reads the unfolded
block after `Original-Received:` is renamed back to `Received:`, each line only when its own
`;` stamp is in the Date year: an NNTP group has no month file to cross-check against.
"""

import importlib.util
import json
import os
import socket
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GROUPS, OUT = Path(sys.argv[1]), Path(sys.argv[2])

SERVER = os.environ.get("NNTP_SERVER", "news.gmane.io")
TAG = os.environ.get("NNTP_TAG", "gmane")
ONLY = set(sys.argv[3:])
sys.path.insert(0, str(REPO / "src"))
from ark.usenet import message_year  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "ap", REPO / "scripts/sources/mail_corpora/build_apache_header_pool.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
unfold, by_hosts, IN_WINDOW = _mod.unfold, _mod.by_hosts, _mod.IN_WINDOW
_rd = importlib.util.spec_from_file_location(
    "rd", REPO / "scripts/sources/mail_corpora/build_received_rdns_pool.py"
)
_rdm = importlib.util.module_from_spec(_rd)
_rd.loader.exec_module(_rdm)
rdns_hosts = _rdm.rdns_hosts
BATCH = 100


class NNTP:
    def __init__(self):
        self.connect()

    def connect(self):
        self.s = socket.create_connection((SERVER, 119), timeout=120)
        self.f = self.s.makefile("rwb")
        self.line()

    def line(self):
        return self.f.readline().decode("latin1").rstrip("\r\n")

    def send(self, cmds):
        self.f.write("".join(c + "\r\n" for c in cmds).encode())
        self.f.flush()

    def multi(self):
        first = self.line()
        out = []
        if first[:1] == "2":
            while True:
                row = self.line()
                if row == ".":
                    break
                out.append(row[1:] if row.startswith("..") else row)
        return first, out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    groups = []
    for raw in open(GROUPS):
        d = json.loads(raw)
        if d["g"].startswith("gwene."):
            continue  # RSS feeds turned into articles: no mail, no Received
        if d.get("y") and d["y"] < 2002 and (not ONLY or d["g"] in ONLY):
            groups.append(d)
    done_p = OUT / "swept.txt"
    done = set(done_p.read_text().split()) if done_p.exists() else set()
    st = dict.fromkeys(["articles", "in_window", "with_hosts", "no_by_host", "undated"], 0)
    nn = NNTP()
    shard = open(OUT / f"{TAG}_messages.jsonl", "a")
    donef = open(done_p, "a")
    for d in sorted(groups, key=lambda d: d["g"]):
        g = d["g"]
        if g in done:
            continue
        for attempt in range(5):
            try:
                nn.send([f"GROUP {g}"])
                nn.line()
                # overview first: only articles whose Date is in window get a HEAD
                want = []
                lo, hi = d["lo"], d["hi"]
                step = 20000
                stop = False
                for a in range(lo, hi + 1, step):
                    nn.send([f"XOVER {a}-{min(a + step - 1, hi)}"])
                    _, rows = nn.multi()
                    for r in rows:
                        p = r.split("\t")
                        if len(p) < 4:
                            continue
                        y = message_year(p[3])
                        if y in IN_WINDOW:
                            want.append(int(p[0]))
                        elif y and y > 2003:
                            stop = True
                    if stop:
                        break
                for i in range(0, len(want), BATCH):
                    chunk = want[i : i + BATCH]
                    nn.send([f"HEAD {n}" for n in chunk])
                    for n in chunk:
                        first, lines = nn.multi()
                        if not first.startswith("221"):
                            continue
                        st["articles"] += 1
                        block = unfold(lines)
                        block = "\n".join(
                            "Received:" + x[len("Original-Received:") :]
                            if x.lower().startswith("original-received:")
                            else x
                            for x in block.split("\n")
                        )
                        year = None
                        for x in block.split("\n"):
                            if x[:5].lower() == "date:":
                                year = message_year(x.split(":", 1)[1])
                                break
                        if year not in IN_WINDOW:
                            st["undated"] += 1
                            continue
                        st["in_window"] += 1
                        # a by host counts only on a line its own server stamped in the
                        # Date year, so a client clock set years wrong dates nothing
                        hosts = by_hosts(
                            "\n".join(
                                x
                                for x in block.split("\n")
                                if x[:9].lower() == "received:"
                                and ";" in x
                                and message_year(x.rsplit(";", 1)[1]) == year
                            )
                        )
                        rd = rdns_hosts(block, year)
                        if not hosts and not rd:
                            st["no_by_host"] += 1
                            continue
                        st["with_hosts"] += 1
                        for f, hs in (("received_by", hosts), ("rdns", rd)):
                            for h in sorted(set(hs)):
                                row = {"host": h, "year": year, "file": f"nntp://{SERVER}/{g}"}
                                row |= {"pos": n, "field": f}
                                shard.write(json.dumps(row) + "\n")
                shard.flush()
                donef.write(g + "\n")
                donef.flush()
                print(g, len(want), json.dumps(st), flush=True)
                break
            except (TimeoutError, OSError) as e:
                print("retry", g, e, flush=True)
                time.sleep(10 * (attempt + 1))
                nn.connect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
