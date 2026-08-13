"""Find the earliest FFIEC CDR period whose TEXT4087 holds real URLs, not "CONF".

The column is published three ways over time: absent values (2001 to 2004-09), the
redaction marker CONF, and actual addresses. Only the third is worth harvesting, and
the earliest such quarter is the closest vintage this source can offer the window.
"""

import datetime as dt
import html as H
import http.cookiejar
import io
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

UA = "InternetDigitalArk/1.0 (historical domain research; contact ivaylo.staykov@taktile.com)"
URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"
PRODUCT = "ReportingSeriesSinglePeriod"
OUT = Path("data/raw/ffiec")

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", UA), ("Referer", URL)]


def hidden(h: str) -> dict[str, str]:
    d = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', h):
        t = m.group(0)
        n = re.search(r'name="([^"]+)"', t)
        v = re.search(r'value="([^"]*)"', t)
        if n:
            d[n.group(1)] = H.unescape(v.group(1) if v else "")
    return d


def post(fields: dict[str, str]) -> bytes:
    req = urllib.request.Request(
        URL,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with opener.open(req, timeout=900) as r:
        return r.read()


def distinct_urls(blob: bytes) -> int:
    z = zipfile.ZipFile(io.BytesIO(blob))
    for nm in z.namelist():
        if not nm.endswith(".txt"):
            continue
        raw = z.read(nm).decode("utf-8", "replace").splitlines()
        head = raw[0].split("\t")
        if "TEXT4087" not in head:
            continue
        i = head.index("TEXT4087")
        vals = {
            f[i].strip() for line in raw[2:] if len(f := line.split("\t")) > i and f[i].strip()
        }
        return len(vals - {"CONF"})
    return 0


def main() -> None:
    page = opener.open(urllib.request.Request(URL), timeout=120).read().decode("utf-8", "replace")
    f = hidden(page)
    f["__EVENTTARGET"] = "ctl00$MainContentHolder$ListBox1"
    f["__EVENTARGUMENT"] = ""
    f["ctl00$MainContentHolder$ListBox1"] = PRODUCT
    page2 = post(f).decode("utf-8", "replace")
    block = re.search(r'(?s)<select[^>]*id="DatesDropDownList"[^>]*>(.*?)</select>', page2).group(1)
    opts = re.findall(r'value="([^"]*)"[^>]*>(.*?)</option>', block)
    periods = sorted(
        ((dt.datetime.strptime(t.strip(), "%m/%d/%Y").date(), v) for v, t in opts),
        key=lambda x: x[0],
    )

    def fetch(i: int) -> bytes:
        d, v = periods[i]
        f2 = hidden(page2)
        f2["__EVENTTARGET"] = ""
        f2["__EVENTARGUMENT"] = ""
        f2["ctl00$MainContentHolder$ListBox1"] = PRODUCT
        f2["ctl00$MainContentHolder$DatesDropDownList"] = v
        f2["ctl00$MainContentHolder$FormatType"] = "TSVRadioButton"
        f2["ctl00$MainContentHolder$TabStrip1$Download_0"] = "Download"
        return post(f2)

    dates = [d for d, _ in periods]
    lo = dates.index(dt.date(2004, 12, 31))  # known CONF
    hi = dates.index(dt.date(2026, 3, 31))  # known real
    while hi - lo > 1:
        mid = (lo + hi) // 2
        blob = fetch(mid)
        n = distinct_urls(blob)
        print(f"{dates[mid]}  {len(blob):>10,}b  distinct real urls = {n}", flush=True)
        if n > 100:
            hi = mid
            (OUT / f"call_{dates[mid]:%m%d%Y}.zip").write_bytes(blob)
        else:
            lo = mid
    print("last CONF:", dates[lo], " first real:", dates[hi])
    blob = fetch(hi)
    p = OUT / f"call_{dates[hi]:%m%d%Y}.zip"
    p.write_bytes(blob)
    print("saved", p, distinct_urls(blob))


if __name__ == "__main__":
    main()
