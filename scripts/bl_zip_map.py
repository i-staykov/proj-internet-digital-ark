"""Read any BL repository ZIP's member table over HTTP, without downloading it.

Generalised from `ukwa_geoindex_map.py`, which did this for one hardcoded file.
The point is that a 16.7 GB archive can be identified for the cost of three ranged
reads, so a candidate can be priced before a byte of it is fetched.

    uv run python scripts/bl_zip_map.py <file_set_id>
"""

import json
import re
import struct
import sys
import urllib.error
import urllib.request

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_opener = urllib.request.build_opener(NoRedirect)


def resolve(fid: str) -> str:
    """The S3 URL behind a file_set id. Signed and short-lived, so resolve once."""
    req = urllib.request.Request(
        f"https://bl.iro.bl.uk/downloads/{fid}", headers={"User-Agent": UA}
    )
    try:
        _opener.open(req, timeout=60)
    except urllib.error.HTTPError as exc:
        target = exc.headers.get("Location")
        if target:
            return target
    raise SystemExit(f"no redirect for {fid}")


def get_range(url: str, start: int, end: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=180) as fh:
        return fh.read()


def total(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return int(fh.headers["Content-Range"].split("/")[1])


def members(url: str) -> list[dict]:
    size = total(url)
    print(f"  {size:,} bytes")
    tail = get_range(url, max(size - 200_000, 0), size - 1)

    i = tail.rfind(b"PK\x06\x07")
    if i >= 0:
        cd_off = struct.unpack_from("<Q", tail, i + 8)[0]
        head = get_range(url, cd_off, cd_off + 55)
        if head[:4] != b"PK\x06\x06":
            raise SystemExit("ZIP64 record not where the locator says")
        cd_size = struct.unpack_from("<Q", head, 40)[0]
        cd_start = struct.unpack_from("<Q", head, 48)[0]
    else:
        j = tail.rfind(b"PK\x05\x06")
        if j < 0:
            raise SystemExit("no end-of-central-directory found; not a zip?")
        cd_size = struct.unpack_from("<I", tail, j + 12)[0]
        cd_start = struct.unpack_from("<I", tail, j + 16)[0]

    cd = get_range(url, cd_start, cd_start + cd_size - 1)
    out, p = [], 0
    while p < len(cd) and cd[p : p + 4] == b"PK\x01\x02":
        csize = struct.unpack_from("<I", cd, p + 20)[0]
        usize = struct.unpack_from("<I", cd, p + 24)[0]
        nlen = struct.unpack_from("<H", cd, p + 28)[0]
        elen = struct.unpack_from("<H", cd, p + 30)[0]
        clen = struct.unpack_from("<H", cd, p + 32)[0]
        lho = struct.unpack_from("<I", cd, p + 42)[0]
        name = cd[p + 46 : p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen : p + 46 + nlen + elen]
        q = 0
        while q + 4 <= len(extra):
            hid, hsz = struct.unpack_from("<HH", extra, q)
            if hid == 0x0001:
                vals, r = [], q + 4
                while r + 8 <= q + 4 + hsz:
                    vals.append(struct.unpack_from("<Q", extra, r)[0])
                    r += 8
                k = 0
                if usize == 0xFFFFFFFF and k < len(vals):
                    usize, k = vals[k], k + 1
                if csize == 0xFFFFFFFF and k < len(vals):
                    csize, k = vals[k], k + 1
                if lho == 0xFFFFFFFF and k < len(vals):
                    lho, k = vals[k], k + 1
            q += 4 + hsz
        out.append(
            {
                "name": name,
                "compressed": csize,
                "uncompressed": usize,
                "local_header_offset": lho,
            }
        )
        p += 46 + nlen + elen + clen
    return out


def main() -> None:
    fid = sys.argv[1]
    url = resolve(fid)
    name = re.search(r"filename%3D([^&]+)", url)
    print(f"file_set {fid} -> {urllib.parse.unquote(name.group(1)) if name else '?'}")
    ms = members(url)
    print(f"  {len(ms)} members")
    for m in sorted(ms, key=lambda x: -x["uncompressed"])[:30]:
        print(
            f"    {m['uncompressed'] / 1e9:9.3f} GB out  "
            f"{m['compressed'] / 1e9:8.3f} GB in   {m['name'][:70]}"
        )
    out = f"data/raw/bl/zipmap_{fid}.json"
    with open(out, "w") as fh:
        json.dump({"url_expires": True, "members": ms}, fh, indent=1)
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
