"""Stream one member of the British Library geoindex and answer two questions at once.

**The question that decides what this source is worth.** Each member looks sorted
ascending by capture timestamp, which would put 1996-2001 in a contiguous prefix and
make the extraction tens of megabytes instead of 11.22 GB. Its sibling
`host-linkage.tsv.gz` looked sorted too and was fifteen concatenated shards, and the
check that confirmed it stopped 2.4x short of the first shard boundary, which cost the
project 93% of that source for three weeks. **So this streams a member to EOF and
counts timestamp decreases**, which is the check the register prescribes and the one
that was skipped last time.

It collects while it measures, because the download is the expensive part and a run
that answered the question but threw the rows away would have to be repeated.

A row is `<14-digit timestamp>/<url><TAB><postcode>`. A handful carry junk stamps
(`19800101000000`, some 1994 and 1995), so the window filter rejects pre-1996 rather
than trusting the first row.

    uv run python scripts/ukwa_geoindex_stream.py geoindex/postcode-ab.tsv

Writes `data/raw/ukwa/geoindex_<member>_inwindow.tsv.gz` and prints the verdict. It
does not touch `web.archive.org`, so it is safe beside the CDX collectors.
"""

import argparse
import gzip
import json
import re
import struct
import sys
import time
import urllib.request
import zlib
from pathlib import Path

URL = "https://bl.iro.bl.uk/downloads/090bbffa-d82c-4641-ba72-0089e8ef885f"
UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
MEMBERS = Path("data/raw/ukwa/geoindex_members.json")
STAMP = re.compile(rb"^(\d{14})/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("member", help="member name, e.g. geoindex/postcode-ab.tsv")
    ap.add_argument("--max-bytes", type=int, default=0, help="stop after N compressed bytes")
    ap.add_argument(
        "--stop-margin-mb",
        type=int,
        default=0,
        help=(
            "once past 2001, keep reading this many more compressed MB and stop if no "
            "further in-window row appears. 0 disables early abort and streams to EOF. "
            "**The abort is cancelled the moment a timestamp decrease is seen**, because "
            "a decrease means the member is sharded and in-window rows are spread through "
            "it. Members differ: `postcode-ab` has 0 decreases over all 529,492,931 of its "
            "compressed bytes, while `postcode-a0` has 49, so sortedness is a property of "
            "the member and not of the archive. That is the same trap that cost this "
            "project 93% of `host-linkage.tsv.gz` for three weeks."
        ),
    )
    args = ap.parse_args()

    members = {m["name"]: m for m in json.loads(MEMBERS.read_text())}
    if args.member not in members:
        sys.exit(f"unknown member; have {sorted(members)}")
    m = members[args.member]

    # The local file header repeats the name and extra field, and its extra field is
    # not the same length as the central directory's, so the data offset has to be
    # read from the local header rather than assumed.
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": UA,
            "Range": f"bytes={m['local_header_offset']}-{m['local_header_offset'] + 29}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as fh:
        lh = fh.read()
    if lh[:4] != b"PK\x03\x04":
        sys.exit("no local file header at the recorded offset")
    nlen, elen = struct.unpack_from("<HH", lh, 26)
    data_start = m["local_header_offset"] + 30 + nlen + elen
    data_end = data_start + m["compressed"] - 1
    if args.max_bytes:
        data_end = min(data_end, data_start + args.max_bytes - 1)

    print(f"member {args.member}")
    print(f"  compressed {m['compressed']:,}  uncompressed {m['uncompressed']:,}")
    print(f"  streaming bytes {data_start:,}-{data_end:,}")

    out_path = Path("data/raw/ukwa") / (
        args.member.replace("/", "_").replace(".tsv", "") + "_inwindow.tsv.gz"
    )
    out = gzip.open(out_path, "wt")

    req = urllib.request.Request(
        URL, headers={"User-Agent": UA, "Range": f"bytes={data_start}-{data_end}"}
    )
    dec = zlib.decompressobj(-15)

    rows = kept = decreases = junk = 0
    prev = None
    first_stamp = last_stamp = None
    lo_seen = hi_seen = None
    tail = b""
    started = time.time()
    raw_read = 0
    past_window_at = None
    aborted = False

    with urllib.request.urlopen(req, timeout=300) as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            raw_read += len(chunk)
            buf = tail + dec.decompress(chunk, 1 << 26)
            lines = buf.split(b"\n")
            tail = lines.pop()
            for line in lines:
                match = STAMP.match(line)
                if not match:
                    junk += 1
                    continue
                rows += 1
                stamp = match.group(1)
                if first_stamp is None:
                    first_stamp = stamp
                last_stamp = stamp
                if lo_seen is None or stamp < lo_seen:
                    lo_seen = stamp
                if hi_seen is None or stamp > hi_seen:
                    hi_seen = stamp
                if prev is not None and stamp < prev:
                    decreases += 1
                prev = stamp
                if b"1996" <= stamp[:4] <= b"2001":
                    kept += 1
                    past_window_at = None
                    out.write(line.decode("utf-8", "replace") + "\n")
                elif stamp[:4] > b"2001" and past_window_at is None:
                    past_window_at = raw_read
            if rows and rows % 5_000_000 < 200_000:
                rate = raw_read / max(time.time() - started, 1) / 1e6
                print(
                    f"    {rows:,} rows, {kept:,} in window, {decreases:,} decreases, "
                    f"{raw_read / 1e9:.2f} GB read, {rate:.1f} MB/s",
                    flush=True,
                )
            if (
                args.stop_margin_mb
                and decreases == 0
                and past_window_at is not None
                and raw_read - past_window_at > args.stop_margin_mb * (1 << 20)
            ):
                aborted = True
                print(
                    f"    past 2001 and {args.stop_margin_mb} MB of margin clean; stopping",
                    flush=True,
                )
                break

    out.close()
    print("\n== verdict ==")
    print(f"  rows            {rows:,}")
    print(f"  in window       {kept:,}")
    print(f"  unparsed        {junk:,}")
    print(f"  compressed read {raw_read:,} of {m['compressed']:,}")
    print(f"  first stamp     {(first_stamp or b'').decode()}")
    print(f"  last stamp      {(last_stamp or b'').decode()}")
    print(f"  min / max seen  {(lo_seen or b'').decode()} / {(hi_seen or b'').decode()}")
    print(f"  TIMESTAMP DECREASES: {decreases:,}")
    if aborted:
        print("  -> stopped early on the margin rule, which is sound only while the")
        print("     decrease count stays 0. A non-zero count above means this member is")
        print("     sharded and the early abort read a fraction of what is there.")
    elif decreases == 0:
        print("  -> sorted end to end, so the window is a contiguous prefix and an")
        print("     early abort is safe. Extraction is cheap.")
    else:
        print("  -> NOT sorted: it is sharded like host-linkage.tsv.gz was, so in-window")
        print("     rows are spread across the whole member and an early abort would")
        print("     read a fraction of what is there. The full member must be streamed.")
    print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
