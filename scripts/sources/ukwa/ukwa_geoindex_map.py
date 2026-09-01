"""Read the ZIP64 central directory of the British Library geoindex, over HTTP.

The file is 11,217,295,098 bytes at `bl.iro.bl.uk/downloads/`, CC Public Domain
Mark 1.0, and it answers ranged GETs, so its member table can be read without
downloading it. Nothing here fetches a member; this only prints the map.

    uv run python scripts/sources/ukwa/ukwa_geoindex_map.py
"""

import json
import struct
import sys
import urllib.request

URL = "https://bl.iro.bl.uk/downloads/090bbffa-d82c-4641-ba72-0089e8ef885f"
UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"


def get_range(start: int, end: int) -> bytes:
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=120) as fh:
        return fh.read()


def total_size() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=120) as fh:
        return int(fh.headers["Content-Range"].split("/")[1])


def main() -> None:
    size = total_size()
    print(f"file: {size:,} bytes")

    tail = get_range(size - 100_000, size - 1)

    i = tail.rfind(b"PK\x06\x07")  # ZIP64 end of central directory locator
    if i < 0:
        sys.exit("no ZIP64 locator found; not the expected container")
    cd64_off = struct.unpack_from("<Q", tail, i + 8)[0]

    head = get_range(cd64_off, cd64_off + 55)
    if head[:4] != b"PK\x06\x06":
        sys.exit("ZIP64 end-of-central-directory record not where the locator says")
    entries = struct.unpack_from("<Q", head, 32)[0]
    cd_size = struct.unpack_from("<Q", head, 40)[0]
    cd_off = struct.unpack_from("<Q", head, 48)[0]
    print(f"central directory: {entries} entries, {cd_size:,} bytes at {cd_off:,}")

    cd = get_range(cd_off, cd_off + cd_size - 1)

    members = []
    p = 0
    while p < len(cd) and cd[p : p + 4] == b"PK\x01\x02":
        method = struct.unpack_from("<H", cd, p + 10)[0]
        csize = struct.unpack_from("<I", cd, p + 20)[0]
        usize = struct.unpack_from("<I", cd, p + 24)[0]
        nlen = struct.unpack_from("<H", cd, p + 28)[0]
        elen = struct.unpack_from("<H", cd, p + 30)[0]
        clen = struct.unpack_from("<H", cd, p + 32)[0]
        lho = struct.unpack_from("<I", cd, p + 42)[0]
        name = cd[p + 46 : p + 46 + nlen].decode("utf-8", "replace")

        # ZIP64 extra field carries the real sizes when the 32-bit ones are 0xFFFFFFFF.
        extra = cd[p + 46 + nlen : p + 46 + nlen + elen]
        q = 0
        while q + 4 <= len(extra):
            hid, hsz = struct.unpack_from("<HH", extra, q)
            if hid == 0x0001:
                vals = []
                r = q + 4
                while r + 8 <= q + 4 + hsz:
                    vals.append(struct.unpack_from("<Q", extra, r)[0])
                    r += 8
                k = 0
                if usize == 0xFFFFFFFF and k < len(vals):
                    usize = vals[k]
                    k += 1
                if csize == 0xFFFFFFFF and k < len(vals):
                    csize = vals[k]
                    k += 1
                if lho == 0xFFFFFFFF and k < len(vals):
                    lho = vals[k]
                    k += 1
            q += 4 + hsz

        members.append(
            {
                "name": name,
                "method": method,
                "compressed": csize,
                "uncompressed": usize,
                "local_header_offset": lho,
            }
        )
        p += 46 + nlen + elen + clen

    print(f"\n{'member':<34}{'method':>7}{'compressed GB':>15}{'uncompressed GB':>17}")
    for m in members:
        print(
            f"{m['name']:<34}{m['method']:>7}"
            f"{m['compressed'] / 1e9:>15.3f}{m['uncompressed'] / 1e9:>17.3f}"
        )
    print(
        f"\ntotals: {sum(m['compressed'] for m in members) / 1e9:.2f} GB compressed, "
        f"{sum(m['uncompressed'] for m in members) / 1e9:.2f} GB uncompressed"
    )

    with open("data/raw/ukwa/geoindex_members.json", "w") as fh:
        json.dump(members, fh, indent=1)
    print("wrote data/raw/ukwa/geoindex_members.json")


if __name__ == "__main__":
    main()
