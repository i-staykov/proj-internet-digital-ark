"""Extract candidate domains from the bank returns that carry a usable value.

Names only, for the candidate pool. Neither source is in-window. The FFIEC Call
Report reported a website from 1999-03-31, but the CDR publishes the column empty
through 2004-09-30 and as the redaction marker CONF through 2005-09-30, so the
earliest quarter with real addresses is 2005-12-31. The FDIC institution table is
the bank's site as it stands today.
"""

import collections
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, "src")
from ark.canonical import reject_reason, to_registrable  # noqa: E402

CALL_ZIP = Path("data/raw/ffiec/call_12312005.zip")
FDIC_DIR = Path("data/raw/ffiec/fdic")
OUT = Path("data/raw/seeds/ffiec_call_report_candidates.txt")


def column(zf: zipfile.ZipFile, code: str) -> list[str]:
    for name in zf.namelist():
        if not name.endswith(".txt"):
            continue
        raw = zf.read(name).decode("utf-8", "replace").splitlines()
        head = raw[0].split("\t")
        if code not in head:
            continue
        i = head.index(code)
        vals = [f[i].strip() for line in raw[2:] if len(f := line.split("\t")) > i and f[i].strip()]
        print(f"  {code} in {name.split('Schedule ')[-1]}: {len(vals)} non-empty of {len(raw) - 2}")
        return vals
    return []


def canon(values: list[str], label: str) -> set[str]:
    ok, bad = set(), collections.Counter()
    for v in values:
        d = to_registrable(v)
        if d:
            ok.add(d)
        else:
            bad[reject_reason(v) or "unknown"] += 1
    pct = 100 * sum(bad.values()) / len(values) if values else 0
    print(f"{label}: {len(values)} raw, {len(ok)} distinct registrable, {sum(bad.values())} rejected ({pct:.1f}%)")
    for reason, n in bad.most_common():
        print(f"    reject {n:6d}  {reason}")
    return ok


def novelty(con, label: str, domains: set[str]) -> None:
    if not domains:
        print(f"  {label:12s}      0 distinct")
        return
    con.execute("create or replace temp table s1(domain varchar)")
    con.executemany("insert into s1 values (?)", [(d,) for d in sorted(domains)])
    held = con.execute("select count(*) from s1 join domain using (domain)").fetchone()[0]
    print(f"  {label:12s} {len(domains):6d} distinct, {held:6d} held, {len(domains) - held:6d} net-new")


def main() -> None:
    zf = zipfile.ZipFile(CALL_ZIP)
    print(f"{CALL_ZIP.name}:")
    web_raw = [v for v in column(zf, "TEXT4087") if v != "CONF"]
    mail_raw = [v for v in column(zf, "TEXT4086") if v != "CONF"]
    print(f"  after dropping CONF: website {len(web_raw)}, e-mail {len(mail_raw)}")

    fdic_raw = []
    for p in sorted(FDIC_DIR.glob("inst_*.json")):
        for rec in json.load(open(p))["data"]:
            v = (rec["data"].get("WEBADDR") or "").strip()
            if v:
                fdic_raw.append(v)

    print()
    web = canon(web_raw, "FFIEC Call Report 2005-12-31 TEXT4087 website")
    mail = canon(mail_raw, "FFIEC Call Report 2005-12-31 TEXT4086 e-mail")
    fdic = canon(fdic_raw, "FDIC institutions WEBADDR (current state)")

    all_ = web | mail | fdic
    print()
    print(f"raw values read       : {len(web_raw) + len(mail_raw) + len(fdic_raw)}")
    print(f"union distinct domains: {len(all_)}")
    print(f"  call-only           : {len(web - fdic)}")
    print(f"  fdic-only           : {len(fdic - web)}")
    print(f"  in both             : {len(web & fdic)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(sorted(all_)) + "\n")
    print(f"wrote {OUT} ({len(all_)} lines)")

    from ark.db import connect_read_only_patiently

    con = connect_read_only_patiently()
    con.execute("create temp table cand(domain varchar)")
    con.executemany("insert into cand values (?)", [(d,) for d in sorted(all_)])
    held = con.execute("select count(*) from cand c join domain d using (domain)").fetchone()[0]
    dated = con.execute(
        "select count(distinct c.domain) from cand c join domain_year y on y.domain = c.domain"
    ).fetchone()[0]
    print()
    print(f"already in store      : {held}")
    print(f"of which dated        : {dated}")
    print(f"net-new candidates    : {len(all_) - held}")
    novelty(con, "call web", web)
    novelty(con, "fdic", fdic)
    novelty(con, "call-only", web - fdic)


if __name__ == "__main__":
    main()
