"""One-off fetch of FFIEC CDR Public Data Distribution bulk Call Report files.

The page is an ASP.NET WebForm: the reporting-period list is only populated by a
postback after a product is selected, so the download needs a three-step session
rather than a static URL.
"""

import http.cookiejar
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = "InternetDigitalArk/1.0 (historical domain research; contact ivaylo.staykov@taktile.com)"
URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"
OUT = Path("data/raw/ffiec")

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [
    ("User-Agent", UA),
    ("Accept", "text/html,application/xhtml+xml,*/*"),
    ("Referer", URL),
]


def hidden_fields(html: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', html):
        tag = m.group(0)
        name = re.search(r'name="([^"]+)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            out[name.group(1)] = _unescape(value.group(1) if value else "")
    return out


def _unescape(s: str) -> str:
    import html as h

    return h.unescape(s)


def post(fields: dict[str, str]) -> tuple[bytes, dict]:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(URL, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with opener.open(req, timeout=300) as r:
        return r.read(), dict(r.headers)


def options(html: str, select_id: str) -> list[tuple[str, str]]:
    m = re.search(rf'<select[^>]*id="{select_id}"[^>]*>(.*?)</select>', html, re.S)
    if not m:
        return []
    return [
        (_unescape(v), _unescape(t.strip()))
        for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', m.group(1), re.S)
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with opener.open(urllib.request.Request(URL), timeout=120) as r:
        html = r.read().decode("utf-8", "replace")

    product = "ReportingSeriesSinglePeriod"
    f = hidden_fields(html)
    f["__EVENTTARGET"] = "ctl00$MainContentHolder$ListBox1"
    f["__EVENTARGUMENT"] = ""
    f["ctl00$MainContentHolder$ListBox1"] = product
    body, _ = post(f)
    html2 = body.decode("utf-8", "replace")
    dates = options(html2, "DatesDropDownList")
    print("periods offered:", len(dates))
    for v, t in dates[-12:]:
        print("  ", v, "|", t)
    if not dates:
        Path(OUT / "cdr_step2.html").write_bytes(body)
        sys.exit("no periods returned; wrote cdr_step2.html")

    wanted = [d for d in dates if d[1].strip().endswith("2001")]
    print("in-window 2001 periods:", wanted)

    for value, text in wanted:
        f2 = hidden_fields(html2)
        f2["__EVENTTARGET"] = ""
        f2["__EVENTARGUMENT"] = ""
        f2["ctl00$MainContentHolder$ListBox1"] = product
        f2["ctl00$MainContentHolder$DatesDropDownList"] = value
        f2["ctl00$MainContentHolder$FormatType"] = "TSVRadioButton"
        f2["ctl00$MainContentHolder$TabStrip1$Download_0"] = "Download"
        body2, hdrs = post(f2)
        ctype = hdrs.get("Content-Type", "")
        name = re.sub(r"[^0-9A-Za-z]+", "", text) or value
        if "zip" in ctype or body2[:2] == b"PK":
            p = OUT / f"call_{name}.zip"
            p.write_bytes(body2)
            print("OK", text, ctype, len(body2), "->", p)
        else:
            p = OUT / f"call_{name}_FAIL.html"
            p.write_bytes(body2)
            print("FAIL", text, ctype, len(body2), "->", p)


if __name__ == "__main__":
    main()
