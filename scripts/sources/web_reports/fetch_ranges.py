"""One large file as an ordered byte stream on stdout, fetched as ranges on several connections.

A single gzip stream cannot be read from its middle, so the download bounds any pass over one,
and archive.org gives one connection a few MB/s. Chunks of CHUNK bytes are asked on
`connections` at once and written in order, so `gzip -dc` and a grep read behind it as one
stream. A failed chunk is asked again after 30 s, ten times, and a 429 or a 503 waits its
Retry-After; stderr says every GB how far it is. Stdlib only.

    python3 scripts/sources/web_reports/fetch_ranges.py URL [connections [last_byte]] | gzip -dc
"""

from __future__ import annotations

import itertools
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "internet-digital-ark/1.0 (index grep)"  # the tool and its version, as the host asks
CHUNK = 32 << 20


def ranged(url: str, first: int, last: int) -> tuple[bytes, str, int]:
    """The bytes first to last, the URL that served them and the file's size."""
    wait = 30
    for _ in range(10):
        try:
            head = {"User-Agent": UA, "Range": f"bytes={first}-{last}"}
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=head), timeout=300
            ) as r:
                data, size = r.read(), int(r.headers["Content-Range"].rpartition("/")[2])
                if len(data) == min(last, size - 1) - first + 1:
                    return data, r.geturl(), size
        except urllib.error.HTTPError as exc:
            busy = exc.code in (429, 503) and exc.headers.get("Retry-After", "").isdigit()
            wait = min(int(exc.headers["Retry-After"]), 600) if busy else 30
        except (OSError, ValueError, KeyError):
            wait = 30
        time.sleep(wait)
    raise SystemExit(f"bytes {first}-{last} did not come")


def main() -> None:
    url, at_once = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4
    data, url, size = ranged(url, 0, CHUNK - 1)  # the mirror the first answer came from
    end = min(size, int(sys.argv[3]) + 1) if len(sys.argv) > 3 else size
    out, t0, done = sys.stdout.buffer, time.time(), 0
    with ThreadPoolExecutor(at_once) as pool:
        starts = iter(range(CHUNK, end, CHUNK))

        def ask(n: int) -> list:
            return [
                pool.submit(ranged, url, a, min(a + CHUNK, end) - 1)
                for a in itertools.islice(starts, n)
            ]

        asked = ask(at_once * 2)
        while True:
            out.write(data[: end - done])
            done += len(data)
            if done >> 30 != (done - len(data)) >> 30:
                rate = done / (time.time() - t0) / 1e6
                say = f"{done / 1e9:.1f} of {end / 1e9:.1f} GB, {rate:.1f} MB/s"
                print(say, file=sys.stderr, flush=True)
            if not asked:
                break
            data = asked.pop(0).result()[0]
            asked += ask(1)
    out.flush()


if __name__ == "__main__":
    main()
