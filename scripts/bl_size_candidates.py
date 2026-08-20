"""Size the interesting-looking files found by the repository index.

The index carries names only, because a HEAD to `/downloads/` returns a 302 whose
Location has the filename but no length. The length is on the S3 URL the redirect
points at, so this follows exactly one redirect and asks for one byte.

    uv run python scripts/bl_size_candidates.py geoindex web-archives woa
"""

import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
INDEX = Path("data/raw/bl/file_index.tsv")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_opener = urllib.request.build_opener(NoRedirect)


def size_of(fid: str) -> int:
    """Bytes behind a file_set id, or -1."""
    req = urllib.request.Request(
        f"https://bl.iro.bl.uk/downloads/{fid}", headers={"User-Agent": UA}
    )
    try:
        _opener.open(req, timeout=60)
        return -1
    except urllib.error.HTTPError as exc:
        target = exc.headers.get("Location")
        if not target:
            return -1
    except Exception:
        return -1
    try:
        req2 = urllib.request.Request(target, headers={"User-Agent": UA, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req2, timeout=60) as resp:
            rng = resp.headers.get("Content-Range") or ""
            m = re.search(r"/(\d+)$", rng)
            return int(m.group(1)) if m else -1
    except Exception:
        return -1


def main() -> None:
    patterns = [p.lower() for p in sys.argv[1:]] or ["geoindex"]
    rows = []
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        fid, name = line.split("\t", 1)
        if any(p in name.lower() for p in patterns):
            rows.append((fid, name))
    print(f"{len(rows)} match {patterns}")
    for fid, name in rows:
        size = size_of(fid)
        flag = "  <-- BULK" if size > 500_000_000 else ""
        print(f"  {size / 1e9:9.3f} GB  {name[:60]:<60} {fid}{flag}")
        time.sleep(0.3)


if __name__ == "__main__":
    main()
