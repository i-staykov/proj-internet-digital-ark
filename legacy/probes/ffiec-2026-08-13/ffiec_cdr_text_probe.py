"""Binary-search the first FFIEC CDR bulk period whose character columns carry values.

The 2001 files publish TEXT4087 and TEXT4086 as headers with every row blank, so the
question worth a measurement is which period the CDR actually backfilled text into.
"""

import datetime as dt
import html as H
import http.cookiejar
import io
import re
import urllib.parse
import urllib.request
import zipfile

UA = "InternetDigitalArk/1.0 (historical domain research; contact ivaylo.staykov@taktile.com)"
URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"
PRODUCT = "ReportingSeriesSinglePeriod"

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


def post(fields: dict[str, str]) -> tuple[bytes, dict]:
    req = urllib.request.Request(
        URL,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with opener.open(req, timeout=900) as r:
        return r.read(), dict(r.headers)


def rate(blob: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(blob))
    out = []
    for nm in z.namelist():
        if " ENT " not in nm and " CI " not in nm:
            continue
        raw = z.read(nm).decode("utf-8", "replace").splitlines()
        head = raw[0].split("\t")
        n = len(raw) - 2
        for want in ("TEXT4087", "TEXT4086", "RSSD9017", "TEXT8902"):
            if want not in head:
                continue
            i = head.index(want)
            pop = sum(1 for line in raw[2:] if len(f := line.split("\t")) > i and f[i].strip())
            out.append(f"{want}={pop}/{n} ({100 * pop / max(n, 1):.1f}%)")
    return "  ".join(out)


def main() -> None:
    page = opener.open(urllib.request.Request(URL), timeout=120).read().decode("utf-8", "replace")
    f = hidden(page)
    f["__EVENTTARGET"] = "ctl00$MainContentHolder$ListBox1"
    f["__EVENTARGUMENT"] = ""
    f["ctl00$MainContentHolder$ListBox1"] = PRODUCT
    body, _ = post(f)
    page2 = body.decode("utf-8", "replace")
    block = re.search(r'(?s)<select[^>]*id="DatesDropDownList"[^>]*>(.*?)</select>', page2).group(1)
    opts = re.findall(r'value="([^"]*)"[^>]*>(.*?)</option>', block)
    periods = sorted(
        ((dt.datetime.strptime(t.strip(), "%m/%d/%Y").date(), v) for v, t in opts),
        key=lambda x: x[0],
    )

    def fetch(idx: int) -> bytes:
        d, v = periods[idx]
        f2 = hidden(page2)
        f2["__EVENTTARGET"] = ""
        f2["__EVENTARGUMENT"] = ""
        f2["ctl00$MainContentHolder$ListBox1"] = PRODUCT
        f2["ctl00$MainContentHolder$DatesDropDownList"] = v
        f2["ctl00$MainContentHolder$FormatType"] = "TSVRadioButton"
        f2["ctl00$MainContentHolder$TabStrip1$Download_0"] = "Download"
        b, _ = post(f2)
        print(f"{d}  {len(b):>10,}b  {rate(b)}", flush=True)
        return b

    # lo is known blank (2001-03-31), hi known populated (latest)
    lo, hi = 0, len(periods) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        b = fetch(mid)
        z = zipfile.ZipFile(io.BytesIO(b))
        nm = next(n for n in z.namelist() if " ENT " in n)
        raw = z.read(nm).decode("utf-8", "replace").splitlines()
        head = raw[0].split("\t")
        i = head.index("RSSD9017")
        pop = sum(1 for line in raw[2:] if len(f3 := line.split("\t")) > i and f3[i].strip())
        if pop:
            hi = mid
        else:
            lo = mid
    print("last blank:", periods[lo][0], " first populated:", periods[hi][0])


if __name__ == "__main__":
    main()
