"""Apply the corroboration split to the Federal Audit Clearinghouse Single Audit filings.

**What one item is.** One e-mail address field on one Single Audit filing row, dated by that
row's own signature date. `ELECAUDITHEADER.csv` carries two such pairs per filing,
`AUDITEEEMAIL` with `AUDITEEDATESIGNED` and `CPAEMAIL` with `CPADATESIGNED`, both documented
in GSA's own historic data dictionary. The domain is the part after the `@`.

**The signature date is the only date that may be used, and this is the trap the corpus sets.**
Every row also carries `AUDITYEAR`, and it does not agree: 1998 filings are routinely signed in
1999, and FY2001 audits in 2002. Taking `AUDITYEAR` would silently import **18,979 e-mail rows
whose signature falls outside 1996-2001**, which is 25.2% of the 75,311 e-mail fields present.
The register's earlier reading of this corpus reported 18,698 dropped on the same screen, so
the two agree to 1.5% and the discipline reproduces.

**The split applies, because a human typed the address into a form.** A random sample of the
novel names shows the split earning its place: `campell.edu` for Campbell, `clakamas.or.us` for
Clackamas, `staate.oh.us` for state.oh.us, `selfsuffciency.com`, and `kl2.ca.us` where the
letter `l` was typed for the digit `1` in `k12`. A separate mechanism accounts for 18.0% of
novel names on its own, a character prepended to a name the store already dates
(`aarthurandersen.com` for arthurandersen.com, `aattglobal.net` for attglobal.net, `1mc.edu`
for mc.edu), which is a data-entry or import defect rather than anyone's honest typing.

**But the split is not costless here and the register should say so.** The same sample holds
names that are plainly real and are exactly the long tail this project wants:
`isler-eugene.com` is a real Eugene accountancy firm and `sau38.k12.nh.us` a real New Hampshire
School Administrative Unit, and no crawler reaches either. The measured `typo upper bound` is
69.7%, the highest in the register, but it is an UPPER bound and the sample puts the true rate
nearer a third. So the uncorroborated lane is parked rather than discarded, and it can be
raised later on a human ruling without refetching anything.

    uv run python scripts/sources/mail_corpora/split_fac.py            # report only
    uv run python scripts/sources/mail_corpora/split_fac.py --write
"""

import argparse
import csv
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from ark.canonical import to_registrable  # noqa: E402
from ark.db import DEFAULT_DB_PATH, connect_read_only_patiently  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

SRC = Path("data/raw/fac")
# (address field, the signature date field that dates it), per GSA's data dictionary.
PAIRS = (("AUDITEEEMAIL", "AUDITEEDATESIGNED"), ("CPAEMAIL", "CPADATESIGNED"))
_ISO_YEAR = re.compile(r"^(\d{4})-\d{2}-\d{2}")
YEARS = range(1996, 2002)


def pairs_in(path: Path, stats: Counter) -> set[tuple[str, int]]:
    """(domain, signature year) from one year's filing header file."""
    out: set[tuple[str, int]] = set()
    with path.open(newline="", errors="replace") as handle:
        for row in csv.DictReader(handle):
            stats["filing_rows"] += 1
            for address_field, date_field in PAIRS:
                address = (row.get(address_field) or "").strip()
                if "@" not in address:
                    continue
                stats["email_fields"] += 1
                match = _ISO_YEAR.match((row.get(date_field) or "").strip())
                if match is None:
                    stats["no_parsable_signature_date"] += 1
                    continue
                year = int(match.group(1))
                if year not in YEARS:
                    stats["signed_out_of_window"] += 1
                    continue
                domain = to_registrable(address.rsplit("@", 1)[1].lower())
                if domain is None:
                    stats["address_not_registrable"] += 1
                    continue
                out.add((domain, year))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write the two lanes per year")
    args = ap.parse_args()

    headers = sorted(SRC.glob("header-*.csv"))
    if not headers:
        print(f"no `header-<year>.csv` under {SRC}; unpack ELECAUDITHEADER.csv from the ZIPs first")
        return 1

    stats: Counter = Counter()
    by_file = {path: pairs_in(path, stats) for path in headers}
    print(f"filing rows read          : {stats['filing_rows']:,}")
    print(f"e-mail fields present     : {stats['email_fields']:,}")
    dropped = stats["signed_out_of_window"]
    print(f"  signed OUT of 1996-2001 : {dropped:,}  <- AUDITYEAR would import these")
    print(f"  no parsable date        : {stats['no_parsable_signature_date']:,}")

    conn = connect_read_only_patiently(DEFAULT_DB_PATH)
    try:
        corroborated = {
            row[0] for row in conn.execute("SELECT DISTINCT domain FROM domain_year").fetchall()
        }
    finally:
        conn.close()
    print(f"\n{len(corroborated):,} domains already carry an assigned year\n")

    dated_ee = Decimal(0)
    total_dated = total_cand = 0
    for path, pairs in by_file.items():
        keep = sorted(p for p in pairs if p[0] in corroborated)
        park = sorted(p for p in pairs if p[0] not in corroborated)
        total_dated += len(keep)
        total_cand += len(park)
        dated_ee += sum((Decimal(weight_of(d.rsplit(".", 1)[-1])) for d, _y in keep), Decimal(0))
        print(
            f"  {path.stem}: {len(pairs):,} pairs -> {len(keep):,} dated, {len(park):,} candidate"
        )
        if args.write:
            stem = path.stem.replace("header-", "")
            for lane, rows in (("dated", keep), ("cand", park)):
                if not rows:
                    continue
                text = "".join(f"{domain}\t{year}\n" for domain, year in rows)
                (SRC / f"fac-{lane}.{stem}.tsv").write_text(text)

    print(f"\ntotal: {total_dated:,} dated rows, {total_cand:,} candidate rows")
    print(f"gross EE of the dated lane (before removing pairs already held): {dated_ee:,.1f}")
    if not args.write:
        print("\nreport only. Pass --write to emit the lanes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
