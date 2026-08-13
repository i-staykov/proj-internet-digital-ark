"""Locate the earliest FFIEC CDR bulk period that actually publishes TEXT4087.

TEXT4087 sits in Schedule ENT in 2001 with every row blank, so both which schedule
carries it later and when it first has values have to be measured rather than assumed.
"""

import datetime as dt
import html as H
import http.cookiejar
import io
import re
import sys
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


def scan(blob: bytes) -> dict[str, tuple[str, int, int]]:
    z = zipfile.ZipFile(io.BytesIO(blob))
    found = {}
    for nm in z.namelist():
        if not nm.endswith(".txt") or nm == "Readme.txt":
            continue
        raw = z.read(nm).decode("utf-8", "replace").splitlines()
        head = raw[0].split("\t")
        for want in ("TEXT4087", "TEXT4086"):
            if want in head:
                i = head.index(want)
                pop = sum(
                    1 for line in raw[2:] if len(f := line.split("\t")) > i and f[i].strip()
                )
                found[want] = (nm.split("Schedule ")[-1][:5].strip(), pop, len(raw) - 2)
    return found


def main() -> None:
    page = opener.open(urllib.request.Request(URL), timeout=120).read().decode("utf-8", "replace")
    f = hidden(page)
    f["__EVENTTARGET"] = "ctl00$MainContentHolder$ListBox1"
    f["__EVENTARGUMENT"] = ""
    f["ctl00$MainContentHolder$ListBox1"] = PRODUCT
    page2 = post(f).decode("utf-8", "replace")
    block = re.search(r'(?s)<select[^>]*id="DatesDropDownList"[^>]*>(.*?)</select>', page2).group(1)
    opts = re.findall(r'value="([^"]*)"[^>]*>(.*?)</option>', block)
    by_date = {dt.datetime.strptime(t.strip(), "%m/%d/%Y").date(): v for v, t in opts}

    for target in sys.argv[1:]:
        d = dt.date.fromisoformat(target)
        f2 = hidden(page2)
        f2["__EVENTTARGET"] = ""
        f2["__EVENTARGUMENT"] = ""
        f2["ctl00$MainContentHolder$ListBox1"] = PRODUCT
        f2["ctl00$MainContentHolder$DatesDropDownList"] = by_date[d]
        f2["ctl00$MainContentHolder$FormatType"] = "TSVRadioButton"
        f2["ctl00$MainContentHolder$TabStrip1$Download_0"] = "Download"
        blob = post(f2)
        p = OUT / f"call_{d:%m%d%Y}.zip"
        p.write_bytes(blob)
        print(f"{d}  {len(blob):>10,}b  {scan(blob)}", flush=True)


if __name__ == "__main__":
    main()
